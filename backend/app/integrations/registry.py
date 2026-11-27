"""Registry for external data source connectors."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from app.integrations.base import BaseConnector

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Registry maintaining available data source connectors."""

    _registry: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, provider: str, connector_cls: Type[BaseConnector]) -> None:
        """Register a connector class for a given provider key."""
        cls._registry[provider.lower()] = connector_cls
        logger.info(f"Registered connector for provider: {provider.lower()}")

    @classmethod
    def get(cls, provider: str) -> Optional[Type[BaseConnector]]:
        """Retrieve a registered connector class by provider key."""
        return cls._registry.get(provider.lower())

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider keys."""
        return list(cls._registry.keys())
