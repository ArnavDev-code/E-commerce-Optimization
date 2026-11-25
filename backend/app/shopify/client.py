"""Shopify GraphQL Admin API Client (Version 2026-10).

Features:
- Pinned to stable version 2026-10.
- Cost-aware throttling and rate limit handling.
- Exponential backoff retry on HTTP 429 and transient 5xx errors.
- Clean GraphQL error parsing and logging.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ShopifyApiError(Exception):
    """Exception raised for Shopify GraphQL API errors."""

    def __init__(self, message: str, errors: Optional[list] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.errors = errors or []
        self.status_code = status_code


class ShopifyGraphQLClient:
    """Production client for Shopify GraphQL Admin API 2026-10."""

    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        api_version: Optional[str] = None,
        timeout: float = 30.0,
    ):
        settings = get_settings()
        self.shop_domain = shop_domain.strip().lower()
        self.access_token = access_token.strip()
        self.api_version = api_version or settings.SHOPIFY_API_VERSION or "2026-10"
        self.timeout = timeout
        self.endpoint = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation with cost-aware rate limiting and retries."""
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
        }
        payload = {
            "query": query,
            "variables": variables or {},
        }

        retries = 0
        backoff = 1.0

        while True:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(self.endpoint, json=payload, headers=headers)

                # 1. Handle HTTP Rate Limits (429)
                if response.status_code == 429:
                    retries += 1
                    if retries > max_retries:
                        raise ShopifyApiError("Rate limit exceeded; max retries exhausted", status_code=429)

                    retry_after = float(response.headers.get("Retry-After", backoff))
                    logger.warning(
                        "Shopify API rate limit hit for %s; sleeping for %.2fs (retry %d/%d)",
                        self.shop_domain, retry_after, retries, max_retries,
                    )
                    time.sleep(retry_after)
                    backoff *= 2.0
                    continue

                # 2. Handle Transient Server Errors (500, 502, 503, 504)
                if response.status_code in (500, 502, 503, 504):
                    retries += 1
                    if retries > max_retries:
                        raise ShopifyApiError(
                            f"Shopify server error {response.status_code}; max retries exhausted",
                            status_code=response.status_code,
                        )
                    logger.warning(
                        "Shopify 5xx error (%d) for %s; backing off for %.2fs",
                        response.status_code, self.shop_domain, backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue

                # 3. Check for other HTTP errors
                response.raise_for_status()
                data = response.json()

                # 4. Check for top-level GraphQL errors
                if "errors" in data and data["errors"]:
                    errors = data["errors"]
                    # Check for GraphQL throttled error code
                    is_throttled = any(
                        isinstance(err, dict) and err.get("extensions", {}).get("code") == "THROTTLED"
                        for err in errors
                    )
                    if is_throttled and retries < max_retries:
                        retries += 1
                        time.sleep(backoff)
                        backoff *= 2.0
                        continue

                    error_msg = "; ".join(
                        err.get("message", str(err)) if isinstance(err, dict) else str(err)
                        for err in errors
                    )
                    raise ShopifyApiError(f"Shopify GraphQL Error: {error_msg}", errors=errors)

                # 5. Cost awareness logging (if available)
                extensions = data.get("extensions", {})
                cost_info = extensions.get("cost", {})
                throttle_status = cost_info.get("throttleStatus", {})
                if throttle_status:
                    avail = throttle_status.get("currentlyAvailable", 1000)
                    req_cost = cost_info.get("requestedQueryCost", 0)
                    if avail < req_cost:
                        restore_rate = throttle_status.get("restoreRate", 50)
                        sleep_needed = max(0.5, (req_cost - avail) / restore_rate)
                        logger.debug("Throttle buffer low on %s; pacing %.2fs", self.shop_domain, sleep_needed)
                        time.sleep(sleep_needed)

                return data.get("data", {})

            except httpx.RequestError as exc:
                retries += 1
                if retries > max_retries:
                    raise ShopifyApiError(f"Network transport error connecting to Shopify: {exc}")
                time.sleep(backoff)
                backoff *= 2.0
