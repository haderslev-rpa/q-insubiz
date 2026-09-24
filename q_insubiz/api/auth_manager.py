from __future__ import annotations

import logging

from playwright.async_api import (
    APIRequestContext,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from q_insubiz.functionality.launch import (
    PlaywrightRecorder,
    launch_insubiz,
)


logger = logging.getLogger(__name__)


class InsubizAuthManager:
    """Administrerer en autentificeret Insubiz-session.

    Browseren anvendes til login og etablering af cookies.
    Browserkontekstens APIRequestContext genbruger derefter
    den autentificerede session til API-kald.

    En valgfri Playwright-recorder kan injiceres. Recorderen
    føres kun videre til launch_insubiz(), hvor screenshot og
    SharePoint-upload udelukkende anvendes ved fejl i UI- og
    Playwright-loginflowet.
    """

    def __init__(
        self,
        headless: bool = True,
        recorder: PlaywrightRecorder | None = None,
    ) -> None:
        """Opretter manageren med browser- og recorderindstillinger."""
        if not isinstance(headless, bool):
            raise TypeError(
                "headless skal være True eller False."
            )

        self._headless = headless
        self._recorder = recorder

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # --------------------------------------------------
    # EGENSKABER
    # --------------------------------------------------

    @property
    def headless(self) -> bool:
        """Returnerer browserens headless-indstilling."""
        return self._headless

    @property
    def recorder(self) -> PlaywrightRecorder | None:
        """Returnerer den valgfri Playwright-recorder."""
        return self._recorder

    @property
    def is_started(self) -> bool:
        """Returnerer True, når en brugbar session er startet."""
        return (
            self._playwright is not None
            and self._browser is not None
            and self._context is not None
            and self._page is not None
            and not self._page.is_closed()
        )

    # --------------------------------------------------
    # SESSION
    # --------------------------------------------------

    async def start(self) -> None:
        """Starter browseren og logger ind i Insubiz."""
        if self._context is not None:
            if self._page is None or self._page.is_closed():
                raise RuntimeError(
                    "Insubiz-konteksten findes, men den "
                    "autentificerede side er ikke tilgængelig."
                )

            return

        if any(
            value is not None
            for value in (
                self._playwright,
                self._browser,
                self._page,
            )
        ):
            logger.warning(
                "En delvist initialiseret Insubiz-session "
                "blev fundet og lukkes før genstart."
            )
            await self.close()

        try:
            self._playwright = (
                await async_playwright().start()
            )

            self._browser = (
                await self._playwright.chromium.launch(
                    headless=self._headless,
                )
            )

            self._context = (
                await self._browser.new_context(
                    viewport={
                        "width": 1440,
                        "height": 1000,
                    },
                )
            )

            self._page = await self._context.new_page()

            await launch_insubiz(
                page=self._page,
                recorder=self._recorder,
            )

            logger.info(
                "Den autentificerede Insubiz-session "
                "blev startet. Headless: %s.",
                self._headless,
            )

        except Exception:
            logger.exception(
                "Den autentificerede Insubiz-session "
                "kunne ikke startes."
            )

            await self.close()
            raise

    async def get_page(self) -> Page:
        """Returnerer den autentificerede Playwright-side.

        Browseren startes og login gennemføres automatisk,
        hvis sessionen ikke allerede er startet.
        """
        await self.start()

        if self._page is None:
            raise RuntimeError(
                "Den autentificerede Insubiz-side "
                "blev ikke oprettet."
            )

        if self._page.is_closed():
            raise RuntimeError(
                "Den autentificerede Insubiz-side "
                "er lukket."
            )

        return self._page

    async def get_request_context(
        self,
    ) -> APIRequestContext:
        """Returnerer browserkontekstens API-klient.

        API-klienten anvender samme cookies som browseren.
        """
        await self.start()

        if self._context is None:
            raise RuntimeError(
                "Insubiz-konteksten blev ikke oprettet."
            )

        return self._context.request

    async def refresh(self) -> None:
        """Lukker sessionen og logger ind igen."""
        logger.info(
            "Fornyer den autentificerede Insubiz-session."
        )

        await self.close()
        await self.start()

    # --------------------------------------------------
    # RECORDER
    # --------------------------------------------------

    def set_recorder(
        self,
        recorder: PlaywrightRecorder | None,
    ) -> None:
        """Udskifter recorderen til efterfølgende loginforsøg.

        Metoden ændrer ikke en allerede startet session. Recorderen
        anvendes næste gang launch_insubiz() udføres, eksempelvis ved
        refresh() eller efter close() og start().
        """
        self._recorder = recorder

    # --------------------------------------------------
    # OPRYDNING
    # --------------------------------------------------

    async def close(self) -> None:
        """Lukker browserkontekst, browser og Playwright."""
        context = self._context
        browser = self._browser
        playwright = self._playwright

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        if context is not None:
            try:
                await context.close()
            except Exception:
                logger.exception(
                    "Insubiz-browserkonteksten kunne "
                    "ikke lukkes korrekt."
                )

        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.exception(
                    "Insubiz-browseren kunne ikke "
                    "lukkes korrekt."
                )

        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                logger.exception(
                    "Playwright kunne ikke stoppes korrekt."
                )

        logger.info(
            "Den autentificerede Insubiz-session er lukket."
        )


__all__ = [
    "InsubizAuthManager",
]
