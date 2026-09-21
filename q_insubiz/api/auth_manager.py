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
    launch_insubiz,
)


logger = logging.getLogger(__name__)


class InsubizAuthManager:
    """
    Administrerer en autentificeret Insubiz-session.
    """

    def __init__(
        self,
        headless: bool = True,
    ) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> None:
        """
        Starter browseren og logger ind i Insubiz.
        """
        if self._context is not None:
            if self._page is None or self._page.is_closed():
                raise RuntimeError(
                    "Insubiz-konteksten findes, men den "
                    "autentificerede side er ikke tilgængelig."
                )

            return

        self._playwright = (
            await async_playwright().start()
        )

        try:
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
        """
        Returnerer den autentificerede Playwright-side.

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
        """
        Returnerer browserkontekstens API-klient.

        API-klienten anvender samme cookies som browseren.
        """
        await self.start()

        if self._context is None:
            raise RuntimeError(
                "Insubiz-konteksten blev ikke oprettet."
            )

        return self._context.request

    async def refresh(self) -> None:
        """
        Lukker sessionen og logger ind igen.
        """
        logger.info(
            "Fornyer den autentificerede Insubiz-session."
        )

        await self.close()
        await self.start()

    async def close(self) -> None:
        """
        Lukker browser og Playwright.
        """
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
