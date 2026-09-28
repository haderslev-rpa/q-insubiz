from __future__ import annotations

"""Auth-manager til en eksternt ejet Playwright request-context."""

import logging

from playwright.async_api import APIRequestContext

logger = logging.getLogger(__name__)


class RequestContextAuthManager:
    """Eksponerer en eksisterende autentificeret request-context.

    Manageren ejer ikke request-contexten og lukker den derfor ikke.
    BrowserContexten og login-sessionen ejes af den kaldende proces.
    """

    def __init__(
        self,
        *,
        request_context: APIRequestContext,
    ) -> None:
        if request_context is None:
            raise TypeError("request_context må ikke være None.")

        self._request_context = request_context
        self._closed = False

    async def get_request_context(self) -> APIRequestContext:
        """Returnerer den eksternt ejede request-context."""
        if self._closed:
            raise RuntimeError("RequestContextAuthManager er lukket.")

        return self._request_context

    async def refresh(self) -> None:
        """Afviser automatisk fornyelse af den eksternt ejede session."""
        if self._closed:
            raise RuntimeError("RequestContextAuthManager er lukket.")

        raise RuntimeError(
            "Den delte Insubiz-session kunne ikke fornys automatisk. "
            "BrowserContexten ejes af den kaldende proces."
        )

    async def close(self) -> None:
        """Lukker adapteren uden at lukke request-contexten."""
        if self._closed:
            return

        self._closed = True
        logger.debug(
            "RequestContextAuthManager blev lukket uden at lukke "
            "den eksternt ejede APIRequestContext."
        )


__all__ = [
    "RequestContextAuthManager",
]
