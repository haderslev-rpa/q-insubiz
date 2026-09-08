from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from q_insubiz.functionality.launch import (
    launch_insubiz,
)


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
            return

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
        )

    async def get_request_context(self):
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

        await self.close()
        await self.start()

    async def close(self) -> None:
        """
        Lukker browser og Playwright.
        """

        if self._context is not None:
            await self._context.close()

        if self._browser is not None:
            await self._browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None