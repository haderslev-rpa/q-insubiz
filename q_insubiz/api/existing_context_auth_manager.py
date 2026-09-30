from __future__ import annotations

"""Auth manager til en eksisterende Playwright-browsercontext."""

from playwright.async_api import (
    APIRequestContext,
    BrowserContext,
    Page,
)


class ExistingContextAuthManager:
    """Bruger en eksisterende browsercontext og dens cookies.

    Klassen ejer ikke BrowserContext eller Page og lukker derfor
    ikke browserobjekterne.
    """

    def __init__(
        self,
        *,
        context: BrowserContext,
        page: Page,
    ) -> None:
        if context is None:
            raise ValueError(
                "context må ikke være None."
            )

        if page is None:
            raise ValueError(
                "page må ikke være None."
            )

        if page.is_closed():
            raise RuntimeError(
                "Playwright-siden er lukket."
            )

        self._context = context
        self._page = page

    async def start(self) -> None:
        """Validerer den eksisterende browsersession."""
        if self._page.is_closed():
            raise RuntimeError(
                "Den eksisterende Insubiz-side er lukket."
            )

    async def get_page(self) -> Page:
        """Returnerer den eksisterende Playwright-side."""
        await self.start()

        return self._page

    async def get_request_context(
        self,
    ) -> APIRequestContext:
        """Returnerer API-klienten med browserens cookies."""
        await self.start()

        return self._context.request

    async def refresh(self) -> None:
        """Validerer den eksisterende session igen."""
        await self.start()

    async def close(self) -> None:
        """Lukker intet, fordi main.py ejer browsercontexten."""
        return


__all__ = [
    "ExistingContextAuthManager",
]