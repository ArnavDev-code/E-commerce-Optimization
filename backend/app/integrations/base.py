"""Base connector interface for external data integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple


class SyncResult:
    """Encapsulates the result of a data source sync operation."""

    def __init__(
        self,
        success: bool,
        records_synced: int = 0,
        error_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.records_synced = records_synced
        self.error_message = error_message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "records_synced": self.records_synced,
            "error_message": self.error_message,
            "details": self.details,
        }


class BaseConnector(ABC):
    """Abstract interface that all data source connectors must implement."""

    provider_name: str

    @abstractmethod
    def test_connection(self) -> bool:
        """Validate credentials and test connection to the external provider."""
        pass

    @abstractmethod
    def discover_resources(self) -> List[Dict[str, Any]]:
        """Discover available resources (e.g. accounts, properties, streams)."""
        pass

    @abstractmethod
    def initial_sync(
        self, date_range: Optional[Tuple[date, date]] = None
    ) -> SyncResult:
        """Run an initial historic or standard sync for the configured resource."""
        pass

    @abstractmethod
    def incremental_sync(
        self, since: Optional[datetime] = None
    ) -> SyncResult:
        """Sync new/updated records since the last sync."""
        pass

    @abstractmethod
    def normalize_data(self, raw_data: Any) -> List[Any]:
        """Normalize raw provider data into internal domain models."""
        pass

    @abstractmethod
    def get_sync_status(self) -> Dict[str, Any]:
        """Return the current sync status and health details."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Revoke tokens and clean up connection resources."""
        pass
