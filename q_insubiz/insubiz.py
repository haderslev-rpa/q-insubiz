from pathlib import Path

from playwright.async_api import Page

from q_insubiz.functionality.launch import (
    launch,
)


class Insubiz:
    """
    Repræsenterer en autentificeret Insubiz-session.

    Objektet bruger en eksisterende Playwright-side.
    Browserens context gemmer cookies efter login.
    """

    LOGIN_URL = "https://start.insubiz.dk/login"

    def __init__(
        self,
        page: Page,
    ) -> None:
        self.page = page

    async def launch(
        self,
        email: str,
        password: str,
    ) -> None:
        """
        Logger ind i Insubiz.
        """

        await launch(
            self=self,
            email=email,
            password=password,
        )

    async def get_error_message(self) -> str:
        """
        Finder en synlig fejlbesked på login-siden.
        """

        error_locator = self.page.locator(
            ".v-messages__message:visible, "
            '[role="alert"]:visible, '
            ".v-alert:visible"
        ).first

        if await error_locator.count() == 0:
            return ""

        try:
            error_message = (
                await error_locator.inner_text()
            )

            return error_message.strip()

        except Exception:
            return ""

    async def take_screenshot(
        self,
        filename: str,
    ) -> None:
        """
        Gemmer et screenshot i mappen screenshots.
        """

        screenshot_directory = Path(
            "screenshots"
        )

        screenshot_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        await self.page.screenshot(
            path=str(
                screenshot_directory / filename
            ),
            full_page=True,
        )