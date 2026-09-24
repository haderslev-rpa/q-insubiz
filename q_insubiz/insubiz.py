from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import Locator, Page

from q_insubiz.functionality.launch import launch_insubiz
from q_insubiz.functionality import skader as skade_funktioner
from q_insubiz.selectors import InsubizSelectors


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Standardindstillinger
# --------------------------------------------------
SCREENSHOT_DIRECTORY = Path("screenshots")


class Insubiz:
    """
    Public facade til en Insubiz-session på en eksisterende
    Playwright-side.

    Browserens context ejer cookies og login-sessionen.
    Loginoplysninger hentes af launch_insubiz() fra
    Automation Server og overføres ikke til denne klasse.
    """

    def __init__(
        self,
        page: Page,
    ) -> None:
        self._validate_page(page)
        self._page = page

    @property
    def page(self) -> Page:
        """Returnerer den tilknyttede Playwright-side."""
        return self._page

    @property
    def is_closed(self) -> bool:
        """Returnerer True, hvis Playwright-siden er lukket."""
        return self._page.is_closed()

    async def launch(self) -> None:
        """Åbner Insubiz og logger ind via launch_insubiz()."""
        self._ensure_page_open(
            operation="Login i Insubiz",
        )

        await launch_insubiz(
            page=self._page,
        )

        logger.info(
            "Insubiz-sessionen blev startet. URL: %s.",
            self._page.url,
        )

    async def get_error_message(self) -> str:
        """Returnerer en synlig loginfejl fra siden."""
        if self._page.is_closed():
            return ""

        error_locator = self._page.locator(
            InsubizSelectors.LOGIN_ERROR
        ).first

        try:
            if await error_locator.count() == 0:
                return ""

            if not await error_locator.is_visible():
                return ""

            return (
                await error_locator.inner_text()
            ).strip()
        except Exception:
            logger.debug(
                "En eventuel fejlbesked kunne ikke aflæses.",
                exc_info=True,
            )
            return ""

    async def take_screenshot(
        self,
        filename: str,
        *,
        full_page: bool = True,
    ) -> Path:
        """Gemmer et screenshot og returnerer filstien."""
        self._ensure_page_open(
            operation="Screenshot",
        )

        if not isinstance(full_page, bool):
            raise TypeError(
                "full_page skal være True eller False."
            )

        normalized_filename = self._normalize_filename(
            filename
        )

        SCREENSHOT_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        screenshot_path = (
            SCREENSHOT_DIRECTORY / normalized_filename
        )

        try:
            await self._page.screenshot(
                path=str(screenshot_path),
                full_page=full_page,
            )
        except Exception as error:
            logger.exception(
                "Screenshot kunne ikke gemmes: %s.",
                screenshot_path,
            )
            raise RuntimeError(
                "Screenshot kunne ikke gemmes. "
                f"Fil: {screenshot_path}."
            ) from error

        logger.info(
            "Screenshot gemt: %s.",
            screenshot_path,
        )

        return screenshot_path

    async def vaelg_dokumentskabelon(
        self,
        *,
        dialog: Locator,
        skabelon_navn: str,
    ) -> str:
        """Vælger en skabelon i en åben dokumentdialog."""
        self._ensure_page_open(
            operation="Vælg dokumentskabelon",
        )

        return await skade_funktioner.vaelg_dokumentskabelon(
            page=self._page,
            dialog=dialog,
            skabelon_navn=skabelon_navn,
        )

    async def gem_dokument_fra_skabelon(
        self,
        *,
        dialog: Locator,
    ) -> None:
        """Gemmer dokumentet fra den valgte skabelon."""
        self._ensure_page_open(
            operation="Gem dokument fra skabelon",
        )

        await skade_funktioner.gem_dokument_fra_skabelon(
            page=self._page,
            dialog=dialog,
        )

    async def opret_dokument_fra_skabelon(
        self,
        *,
        skabelon_navn: str,
    ) -> str:
        """
        Åbner skabelondialogen, vælger skabelonen og gemmer
        dokumentet. Returnerer den bekræftede skabelontekst.
        """
        self._ensure_page_open(
            operation="Opret dokument fra skabelon",
        )

        dialog = await skade_funktioner.opret_dokument_fra_skabelon(
            page=self._page,
        )

        valgt_skabelon = await self.vaelg_dokumentskabelon(
            dialog=dialog,
            skabelon_navn=skabelon_navn,
        )

        await self.gem_dokument_fra_skabelon(
            dialog=dialog,
        )

        logger.info(
            "Dokument blev oprettet fra skabelon: %s.",
            valgt_skabelon,
        )

        return valgt_skabelon

    def _ensure_page_open(
        self,
        *,
        operation: str,
    ) -> None:
        """Kontrollerer, at siden er åben før en handling."""
        if self._page.is_closed():
            raise RuntimeError(
                f"{operation} kunne ikke udføres, "
                "fordi Playwright-siden er lukket."
            )

    @staticmethod
    def _validate_page(page: Any) -> None:
        """Validerer de Page-medlemmer, facaden anvender."""
        required_members = (
            "is_closed",
            "locator",
            "screenshot",
            "url",
        )

        missing_members = [
            member
            for member in required_members
            if not hasattr(page, member)
        ]

        if missing_members:
            raise TypeError(
                "page mangler nødvendige Playwright-medlemmer: "
                f"{missing_members!r}."
            )

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        """Validerer og normaliserer et screenshot-filnavn."""
        if not isinstance(filename, str):
            raise TypeError(
                "filename skal være tekst."
            )

        normalized_filename = filename.strip()

        if not normalized_filename:
            raise ValueError(
                "filename må ikke være tomt."
            )

        path = Path(normalized_filename)

        if path.name != normalized_filename:
            raise ValueError(
                "filename må kun være et filnavn og må "
                "ikke indeholde en mappesti."
            )

        if path.suffix.casefold() not in {
            ".png",
            ".jpg",
            ".jpeg",
        }:
            normalized_filename = (
                f"{normalized_filename}.png"
            )

        return normalized_filename


__all__ = [
    "Insubiz",
    "SCREENSHOT_DIRECTORY",
]
