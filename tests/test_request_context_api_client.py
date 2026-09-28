from __future__ import annotations

"""Enhedstests for API-klient på en eksisterende request-context."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from q_insubiz.api.client import InsubizApiClient
from q_insubiz.api.request_context_auth_manager import (
    RequestContextAuthManager,
)
from q_insubiz.api_client import (
    create_api_client_from_request_context,
)


def test_request_context_auth_manager_returnerer_context() -> None:
    request_context = Mock()
    auth_manager = RequestContextAuthManager(
        request_context=request_context,
    )
    result = asyncio.run(auth_manager.get_request_context())
    assert result is request_context


def test_request_context_auth_manager_lukker_ikke_context() -> None:
    request_context = Mock()
    request_context.dispose = AsyncMock()
    auth_manager = RequestContextAuthManager(
        request_context=request_context,
    )
    asyncio.run(auth_manager.close())
    request_context.dispose.assert_not_awaited()


def test_request_context_auth_manager_afviser_brug_efter_close() -> None:
    request_context = Mock()
    auth_manager = RequestContextAuthManager(
        request_context=request_context,
    )
    asyncio.run(auth_manager.close())
    with pytest.raises(RuntimeError, match="er lukket"):
        asyncio.run(auth_manager.get_request_context())


def test_request_context_auth_manager_afviser_refresh() -> None:
    request_context = Mock()
    auth_manager = RequestContextAuthManager(
        request_context=request_context,
    )
    with pytest.raises(RuntimeError, match="kunne ikke fornys"):
        asyncio.run(auth_manager.refresh())


def test_factory_returnerer_insubiz_api_client() -> None:
    request_context = Mock()
    api_client = create_api_client_from_request_context(
        request_context=request_context,
    )
    assert isinstance(api_client, InsubizApiClient)


def test_factory_afviser_none() -> None:
    with pytest.raises(TypeError, match="må ikke være None"):
        create_api_client_from_request_context(
            request_context=None,
        )
