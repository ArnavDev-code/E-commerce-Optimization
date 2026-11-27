"""Integrations package for external connectors and third-party data sources."""

from app.integrations.base import BaseConnector, SyncResult
from app.integrations.registry import ConnectorRegistry
from app.integrations.connectors.ga4.connector import GA4Connector

# Register default connectors
ConnectorRegistry.register("ga4", GA4Connector)

__all__ = [
    "BaseConnector",
    "SyncResult",
    "ConnectorRegistry",
    "GA4Connector",
]
