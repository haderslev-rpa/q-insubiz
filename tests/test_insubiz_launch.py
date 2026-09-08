import asyncio
import os
from pathlib import Path

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


class Insubiz:
    LOGIN_URL = "https://start.insubiz.dk/login"

    def __init__(self, page: Page):
        self.page = page

    async def launch(
        self,
        email: str,
        password: str,
    ) -> None:
        """
        Åbner Insubiz og logger ind.
        """

        await self.page.goto(
            self.LOGIN_URL,
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        # Find det synlige emailfelt.
        email_input = self.page.locator(
            'input[type="email"]'
            '[autocomplete="username"]:visible'
        ).first

        await email_input.wait_for(
            state="visible",
            timeout=15_000,
        )

        # Find den formular, som det synlige emailfelt tilhører.
        login_form = email_input.locator(
            "xpath=ancestor::form[1]"
        )

        await login_form.wait_for(
            state="visible",
            timeout=15_000,
        )

        # Find adgangskodefeltet i den samme formular.
        password_input = login_form.locator(
            'input[type="password"]'
            '[autocomplete="current-password"]'
        ).first

        await password_input.wait_for(
            state="visible",
            timeout=15_000,
        )

        # Udfyld loginoplysninger.
        await email_input.fill(email)
        await password_input.fill(password)

        # Tryk Enter i adgangskodefeltet.
        await password_input.press("Enter")

        # Vent på, at loginformularen forsvinder.
        try:
            await email_input.wait_for(
                state="hidden",
                timeout=30_000,
            )

        except PlaywrightTimeoutError as error:
            await self.take_screenshot(
                "fejl_login.png"
            )

            error_message = await self.get_error_message()

            message = (
                "Login blev ikke gennemført inden for "
                "30 sekunder."
            )

            if error_message:
                message += f" Fejlbesked: {error_message}"

            message += f" URL: {self.page.url}"

            raise AssertionError(
                message
            ) from error

        await self.page.wait_for_timeout(2_000)

        await self.take_screenshot(
            "insubiz_logget_ind.png"
        )

    async def get_error_message(self) -> str:
        """
        Finder en synlig fejlmeddelelse på login-siden.
        """

        error_locator = self.page.locator(
            ".v-messages__message:visible, "
            '[role="alert"]:visible, '
            ".v-alert:visible"
        ).first

        if await error_locator.count() == 0:
            return ""

        try:
            return (
                await error_locator.inner_text()
            ).strip()

        except Exception:
            return ""

    async def take_screenshot(
        self,
        filename: str,
    ) -> None:
        """
        Gemmer et screenshot i mappen screenshots.
        """

        screenshot_directory = Path("screenshots")
        screenshot_directory.mkdir(exist_ok=True)

        await self.page.screenshot(
            path=str(
                screenshot_directory / filename
            ),
            full_page=True,
        )


async def test_insubiz_launch() -> None:
    """
    Manuel integrationstest af Insubiz.launch().
    """

    email = os.getenv("INSUBIZ_EMAIL")
    password = os.getenv("INSUBIZ_PASSWORD")

    if not email or not password:
        raise RuntimeError(
            "Miljøvariablerne INSUBIZ_EMAIL og "
            "INSUBIZ_PASSWORD skal være oprettet."
        )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=100,
        )

        context = await browser.new_context(
            viewport={
                "width": 1440,
                "height": 1000,
            },
        )

        page = await context.new_page()
        insubiz = Insubiz(page)

        try:
            await insubiz.launch(
                email=email,
                password=password,
            )

            visible_login_fields = page.locator(
                'input[type="email"]'
                '[autocomplete="username"]:visible'
            )

            assert await visible_login_fields.count() == 0, (
                "Loginfeltet er stadig synligt efter login. "
                f"URL: {page.url}"
            )

            print(
                f"Insubiz-login gennemført: {page.url}"
            )

            # Giver kort tid til at se resultatet.
            await page.wait_for_timeout(3_000)

        except Exception:
            await insubiz.take_screenshot(
                "fejl_test_insubiz.png"
            )
            raise

        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(
        test_insubiz_launch()
    )