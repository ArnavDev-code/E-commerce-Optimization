"""Google Analytics Admin and Data API client."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

ADMIN_API_BASE = "https://analyticsadmin.googleapis.com/v1beta"
DATA_API_BASE = "https://analyticsdata.googleapis.com/v1beta"


class GA4ClientError(Exception):
    """Exception raised for Google Analytics API communication errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class GA4Client:
    """Client for Google Analytics Admin and Data APIs."""

    def __init__(self, access_token: str, timeout: float = 30.0):
        self.access_token = access_token
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute HTTP request with exponential backoff on 429/5xx errors."""
        retries = 0
        backoff = 1.0

        while True:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(
                        method=method,
                        url=url,
                        headers=self._headers,
                        json=json_data,
                    )

                    if response.status_code in (429, 500, 502, 503, 504) and retries < max_retries:
                        retries += 1
                        logger.warning(
                            f"GA4 request returned {response.status_code}. Retrying in {backoff}s (attempt {retries}/{max_retries})"
                        )
                        time.sleep(backoff)
                        backoff *= 2
                        continue

                    if response.status_code >= 400:
                        error_detail = response.text
                        try:
                            err_json = response.json()
                            error_detail = err_json.get("error", {}).get("message", response.text)
                        except Exception:
                            pass
                        raise GA4ClientError(
                            f"GA4 API error ({response.status_code}): {error_detail}",
                            status_code=response.status_code,
                            details=response.text,
                        )

                    return response.json()

            except httpx.RequestError as exc:
                if retries < max_retries:
                    retries += 1
                    logger.warning(f"Network error calling GA4 API: {exc}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise GA4ClientError(f"Network error calling GA4 API: {exc}")

    def list_account_summaries(self) -> List[Dict[str, Any]]:
        """List all Google Analytics accounts and their child properties accessible to the user."""
        url = f"{ADMIN_API_BASE}/accountSummaries"
        data = self._request_with_retry("GET", url)
        return data.get("accountSummaries", [])

    def run_report(
        self,
        property_id: str,
        date_ranges: List[Dict[str, str]],
        dimensions: List[Dict[str, str]],
        metrics: List[Dict[str, str]],
        dimension_filter: Optional[Dict[str, Any]] = None,
        limit: int = 10000,
    ) -> Dict[str, Any]:
        """Execute a GA4 report query via properties.runReport."""
        # Normalize property_id to digits
        clean_prop_id = property_id.replace("properties/", "").strip()
        url = f"{DATA_API_BASE}/properties/{clean_prop_id}:runReport"

        payload: Dict[str, Any] = {
            "dateRanges": date_ranges,
            "dimensions": dimensions,
            "metrics": metrics,
            "limit": limit,
        }
        if dimension_filter:
            payload["dimensionFilter"] = dimension_filter

        return self._request_with_retry("POST", url, json_data=payload)
