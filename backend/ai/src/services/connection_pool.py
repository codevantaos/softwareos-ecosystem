"""Connection Pool — Persistent httpx.AsyncClient pool for inference engine adapters.

Each engine adapter gets a dedicated pool with configurable limits,
timeouts, and keep-alive. Pools are created lazily and cleaned up
on shutdown.

URI: softwareos-base://backend/ai/services/connection_pool
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Default pool configuration
DEFAULT_MAX_CONNECTIONS = 20
DEFAULT_MAX_KEEPALIVE = 10
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 120.0
DEFAULT_WRITE_TIMEOUT = 30.0


class ConnectionPool:
    """Manages persistent HTTP connection pools per engine endpoint."""

    def __init__(
        self,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_keepalive: int = DEFAULT_MAX_KEEPALIVE,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        write_timeout: float = DEFAULT_WRITE_TIMEOUT,
    ) -> None:
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._write_timeout = write_timeout
        self._clients: Dict[str, httpx.AsyncClient] = {}

    def _build_client(self, base_url: str) -> httpx.AsyncClient:
        limits = httpx.Limits(
            max_connections=self._max_connections,
            max_keepalive_connections=self._max_keepalive,
        )
        timeout = httpx.Timeout(
            connect=self._connect_timeout,
            read=self._read_timeout,
            write=self._write_timeout,
            pool=self._connect_timeout,
        )
        return httpx.AsyncClient(
            base_url=base_url,
            limits=limits,
            timeout=timeout,
            http2=False,
            follow_redirects=False,
        )

    def get_client(self, engine_name: str, base_url: str) -> httpx.AsyncClient:
        """Get or create a persistent client for the given engine."""
        if engine_name not in self._clients:
            self._clients[engine_name] = self._build_client(base_url)
            logger.info(
                "ConnectionPool: created client for %s → %s (max_conn=%d)",
                engine_name,
                base_url,
                self._max_connections,
            )
        return self._clients[engine_name]

    async def close_client(self, engine_name: str) -> None:
        """Close a specific engine's client."""
        client = self._clients.pop(engine_name, None)
        if client:
            await client.aclose()
            logger.info("ConnectionPool: closed client for %s", engine_name)

    async def close_all(self) -> None:
        """Close all clients — call during application shutdown."""
        for name, client in self._clients.items():
            try:
                await client.aclose()
                logger.info("ConnectionPool: closed client for %s", name)
            except Exception as exc:
                logger.warning(
                    "ConnectionPool: error closing %s: %s", name, exc
                )
        self._clients.clear()

    @property
    def active_clients(self) -> int:
        return len(self._clients)

    def to_dict(self) -> dict:
        return {
            "active_clients": self.active_clients,
            "engines": list(self._clients.keys()),
            "max_connections_per_engine": self._max_connections,
            "max_keepalive_per_engine": self._max_keepalive,
            "connect_timeout": self._connect_timeout,
            "read_timeout": self._read_timeout,
        }