"""Google Analytics 4 connector implementing the BaseConnector interface."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.integrations.base import BaseConnector, SyncResult
from app.integrations.connectors.ga4.client import GA4Client, GA4ClientError
from app.integrations.connectors.ga4.normalizer import normalize_ga4_report
from app.integrations.connectors.ga4.oauth import (
    GoogleOAuthError,
    refresh_access_token,
    revoke_token,
)
from app.models.analytics import GA4Metric
from app.models.connection import DataSourceConnection
from app.models.sync import SyncLog
from app.utils.security import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


class GA4Connector(BaseConnector):
    """Production GA4 connector handling OAuth token management and Data API ingestion."""

    provider_name: str = "ga4"

    def __init__(
        self,
        db: Session,
        store_id: uuid.UUID,
        connection: Optional[DataSourceConnection] = None,
    ):
        self.db = db
        self.store_id = store_id
        self._connection = connection

    def get_connection(self) -> Optional[DataSourceConnection]:
        """Fetch the current GA4 connection for this store."""
        if not self._connection:
            stmt = select(DataSourceConnection).where(
                DataSourceConnection.store_id == self.store_id,
                DataSourceConnection.provider == self.provider_name,
            )
            self._connection = self.db.execute(stmt).scalar_one_or_none()
        return self._connection

    def _get_valid_access_token(self) -> str:
        """Retrieve valid decrypted access token, refreshing automatically if expired."""
        conn = self.get_connection()
        if not conn or not conn.encrypted_access_token:
            raise GA4ClientError("GA4 is not connected for this store. Please connect first.")

        # Check token expiry (refresh if expires within 5 minutes)
        now_utc = datetime.now(timezone.utc)
        needs_refresh = False
        if conn.token_expiry:
            expiry = conn.token_expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= now_utc + timedelta(minutes=5):
                needs_refresh = True

        if needs_refresh and conn.encrypted_refresh_token:
            try:
                refresh_token_plain = decrypt_token(conn.encrypted_refresh_token)
                tokens = refresh_access_token(refresh_token_plain)
                new_access_token = tokens["access_token"]
                expires_in = tokens.get("expires_in", 3600)

                conn.encrypted_access_token = encrypt_token(new_access_token)
                conn.token_expiry = now_utc + timedelta(seconds=expires_in)
                conn.connection_status = "connected"
                self.db.commit()
                return new_access_token
            except Exception as exc:
                logger.error(f"Failed to refresh GA4 access token: {exc}")
                conn.connection_status = "expired"
                conn.last_sync_error = f"Token refresh failed: {exc}"
                self.db.commit()
                raise GA4ClientError(f"GA4 authentication expired. Please reconnect: {exc}")

        return decrypt_token(conn.encrypted_access_token)

    def _get_client(self) -> GA4Client:
        token = self._get_valid_access_token()
        return GA4Client(access_token=token)

    def test_connection(self) -> bool:
        """Validate connection by querying account summaries."""
        conn = self.get_connection()
        if not conn:
            return False

        try:
            client = self._get_client()
            client.list_account_summaries()
            conn.connection_status = "connected"
            conn.last_validated_at = datetime.now(timezone.utc)
            conn.last_sync_error = None
            self.db.commit()
            return True
        except Exception as exc:
            logger.error(f"GA4 test connection failed: {exc}")
            conn.connection_status = "error"
            conn.last_sync_error = str(exc)
            self.db.commit()
            return False

    def discover_resources(self) -> List[Dict[str, Any]]:
        """List GA4 accounts and their associated properties."""
        client = self._get_client()
        summaries = client.list_account_summaries()

        accounts: List[Dict[str, Any]] = []
        for acc in summaries:
            acc_id = acc.get("account", "").replace("accounts/", "")
            acc_name = acc.get("displayName", "Unnamed Account")
            props: List[Dict[str, Any]] = []
            for prop in acc.get("propertySummaries", []):
                p_id = prop.get("property", "").replace("properties/", "")
                props.append({
                    "property_id": p_id,
                    "display_name": prop.get("displayName", f"Property {p_id}"),
                    "account_id": acc_id,
                    "account_name": acc_name,
                })
            accounts.append({
                "account_id": acc_id,
                "display_name": acc_name,
                "properties": props,
            })
        return accounts

    def normalize_data(self, raw_data: Any) -> List[Any]:
        """Normalize raw GA4 data."""
        # Delegates to normalizer module
        return normalize_ga4_report(self.store_id, raw_data)

    def initial_sync(
        self, date_range: Optional[Tuple[date, date]] = None
    ) -> SyncResult:
        """Run initial historic sync for the past 30 days."""
        if date_range:
            start_str = date_range[0].strftime("%Y-%m-%d")
            end_str = date_range[1].strftime("%Y-%m-%d")
        else:
            start_str = "30daysAgo"
            end_str = "yesterday"

        return self._sync_reports(start_str, end_str)

    def incremental_sync(
        self, since: Optional[datetime] = None
    ) -> SyncResult:
        """Run incremental sync for the past 7 days."""
        if since:
            days_ago = max(1, (datetime.now(timezone.utc).date() - since.date()).days)
            start_str = f"{days_ago}daysAgo"
        else:
            start_str = "7daysAgo"
        end_str = "yesterday"

        return self._sync_reports(start_str, end_str)

    def _sync_reports(self, start_date_str: str, end_date_str: str) -> SyncResult:
        """Fetch, normalize, and upsert GA4 overall, device, and source reports."""
        conn = self.get_connection()
        if not conn or not conn.provider_property_id:
            return SyncResult(
                success=False,
                error_message="GA4 property not configured. Select a property first.",
            )

        sync_log = SyncLog(
            store_id=self.store_id,
            sync_type="ga4",
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(sync_log)
        self.db.commit()

        try:
            client = self._get_client()
            property_id = conn.provider_property_id
            date_ranges = [{"startDate": start_date_str, "endDate": end_date_str}]

            records_to_upsert: List[Dict[str, Any]] = []

            # 1. Overall daily report
            try:
                overall_report = client.run_report(
                    property_id=property_id,
                    date_ranges=date_ranges,
                    dimensions=[{"name": "date"}],
                    metrics=[
                        {"name": "sessions"},
                        {"name": "totalUsers"},
                        {"name": "screenPageViews"},
                        {"name": "itemsViewed"},
                        {"name": "itemsAddedToCart"},
                        {"name": "itemsCheckedOut"},
                        {"name": "ecommercePurchases"},
                        {"name": "purchaseRevenue"},
                    ],
                )
            except GA4ClientError:
                # Fallback to standard core metrics if ecommerce metrics are disabled
                logger.info("Ecommerce metrics query failed, falling back to basic session metrics.")
                overall_report = client.run_report(
                    property_id=property_id,
                    date_ranges=date_ranges,
                    dimensions=[{"name": "date"}],
                    metrics=[
                        {"name": "sessions"},
                        {"name": "totalUsers"},
                        {"name": "screenPageViews"},
                    ],
                )

            records_to_upsert.extend(
                normalize_ga4_report(
                    self.store_id, overall_report, dimension_type="overall"
                )
            )

            # 2. Device category breakdown
            device_report = client.run_report(
                property_id=property_id,
                date_ranges=date_ranges,
                dimensions=[{"name": "date"}, {"name": "deviceCategory"}],
                metrics=[
                    {"name": "sessions"},
                    {"name": "totalUsers"},
                    {"name": "screenPageViews"},
                ],
            )
            records_to_upsert.extend(
                normalize_ga4_report(
                    self.store_id,
                    device_report,
                    dimension_type="device",
                    dimension_name_key="deviceCategory",
                )
            )

            # 3. Traffic source breakdown
            source_report = client.run_report(
                property_id=property_id,
                date_ranges=date_ranges,
                dimensions=[{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
                metrics=[
                    {"name": "sessions"},
                    {"name": "totalUsers"},
                    {"name": "screenPageViews"},
                ],
            )
            records_to_upsert.extend(
                normalize_ga4_report(
                    self.store_id,
                    source_report,
                    dimension_type="source",
                    dimension_name_key="sessionDefaultChannelGroup",
                )
            )

            # Idempotent upsert into GA4Metric
            synced_count = 0
            for item in records_to_upsert:
                dim_val = item["dimension_value"]
                existing_stmt = select(GA4Metric).where(
                    GA4Metric.store_id == self.store_id,
                    GA4Metric.report_date == item["report_date"],
                    GA4Metric.dimension_type == item["dimension_type"],
                    GA4Metric.dimension_value == dim_val,
                )
                existing = self.db.execute(existing_stmt).scalar_one_or_none()

                if existing:
                    existing.sessions = item["sessions"]
                    existing.users = item["users"]
                    existing.page_views = item["page_views"]
                    existing.product_views = item["product_views"]
                    existing.add_to_carts = item["add_to_carts"]
                    existing.checkouts = item["checkouts"]
                    existing.purchases = item["purchases"]
                    existing.revenue = item["revenue"]
                else:
                    new_metric = GA4Metric(**item)
                    self.db.add(new_metric)
                synced_count += 1

            # Update connection and sync log
            now = datetime.now(timezone.utc)
            conn.last_sync_at = now
            conn.last_sync_error = None
            conn.connection_status = "connected"

            sync_log.status = "success"
            sync_log.records_synced = synced_count
            sync_log.completed_at = now
            self.db.commit()

            return SyncResult(success=True, records_synced=synced_count)

        except Exception as exc:
            logger.error(f"GA4 sync error: {exc}", exc_info=True)
            self.db.rollback()
            now = datetime.now(timezone.utc)
            if conn:
                conn.last_sync_error = str(exc)
                conn.connection_status = "error"
            sync_log.status = "failed"
            sync_log.error_message = str(exc)
            sync_log.completed_at = now
            self.db.commit()
            return SyncResult(success=False, error_message=str(exc))

    def get_sync_status(self) -> Dict[str, Any]:
        """Return the current connection and sync status."""
        conn = self.get_connection()
        if not conn:
            return {
                "is_connected": False,
                "connection_status": "disconnected",
                "provider_property_id": None,
                "provider_property_name": None,
                "last_validated_at": None,
                "last_sync_at": None,
                "last_sync_error": None,
                "token_expired": False,
            }

        token_expired = False
        if conn.token_expiry:
            expiry = conn.token_expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            token_expired = expiry <= datetime.now(timezone.utc)

        return {
            "is_connected": conn.connection_status == "connected",
            "connection_status": conn.connection_status,
            "provider_property_id": conn.provider_property_id,
            "provider_property_name": conn.provider_property_name,
            "last_validated_at": conn.last_validated_at,
            "last_sync_at": conn.last_sync_at,
            "last_sync_error": conn.last_sync_error,
            "token_expired": token_expired,
        }

    def disconnect(self) -> bool:
        """Revoke tokens and disconnect GA4 for this store."""
        conn = self.get_connection()
        if not conn:
            return True

        if conn.encrypted_access_token:
            try:
                plain_token = decrypt_token(conn.encrypted_access_token)
                revoke_token(plain_token)
            except Exception as exc:
                logger.warning(f"Could not revoke Google token: {exc}")

        conn.connection_status = "disconnected"
        conn.encrypted_access_token = None
        conn.encrypted_refresh_token = None
        conn.token_expiry = None
        conn.provider_property_id = None
        conn.provider_property_name = None
        conn.last_sync_error = None
        self.db.commit()
        return True
