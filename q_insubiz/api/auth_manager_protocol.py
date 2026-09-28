from __future__ import annotations

"""Typekontrakt for auth-managers til InsubizApiClient."""

from typing import Protocol, runtime_checkable

from playwright.async_api import APIRequestContext


@runtime_checkable
class InsubizAuthManagerProtocol(Protocol):
    """Minimumskontrakt for en Insubiz auth-manager."""

    async def get_request_context(self) -> APIRequestContext:
        """Returnerer en autentificeret request-context."""
        ...

    async def refresh(self) -> None:
        """Fornyer den autentificerede session."""
        ...

    async def close(self) -> None:
        """Frigiver managerens ressourcer."""
        ...


__all__ = [
    "InsubizAuthManagerProtocol",
]
