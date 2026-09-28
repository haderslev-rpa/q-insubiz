from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.functionality.skader import (
    gem_dokument_fra_skabelon,
    klik_paa_skade,
    opret_dokument_fra_skabelon,
    vaelg_dokumentskabelon,
)
from q_insubiz.utils import (
    normalize_positive_id,
)


# --------------------------------------------------
# TESTINDSTILLINGER
# --------------------------------------------------

HEADLESS = False

BASE_URL = "https://start.insubiz.dk"

SKADE_ID: int | str = 2491158

SKABELON_NAVN = "Robot - Henlæggelsesbrev"

NAVIGATION_TIMEOUT_MS = 30_000

UI_WAIT_MS = 1_500


# --------------------------------------------------
# TESTINPUT
# --------------------------------------------------


def valider_testinput() -> tuple[int, str]:
    """Validerer og returnerer testens inputværdier."""
    normalized_skade_id = normalize_positive_id(
        name="SKADE_ID",
        value=SKADE_ID,
    )

    if not isinstance(SKABELON_NAVN, str):
        raise TypeError(
            "SKABELON_NAVN skal være tekst. "
            f"Modtog: {type(SKABELON_NAVN).__name__}."
        )

    normalized_skabelon_navn = SKABELON_NAVN.strip()

    if not normalized_skabelon_navn:
        raise ValueError(
            "SKABELON_NAVN må ikke være tom."
        )

    return (
        normalized_skade_id,
        normalized_skabelon_navn,
    )


# --------------------------------------------------
# ÅBN KONKRET SKADE
# --------------------------------------------------


async def aabn_skade_via_id(
    *,
    page: Page,
    skade_id: int,
) -> None:
    """Åbner skademodulet og navigerer til den konkrete skade."""
    if page.is_closed():
        raise RuntimeError(
            "Skaden kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    await klik_paa_skade(
        page=page,
    )

    skade_url = (
        f"{BASE_URL}/incident/"
        f"{skade_id}"
    )

    if str(skade_id) not in page.url:
        try:
            await page.goto(
                skade_url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError as error:
            raise RuntimeError(
                "Navigation til skaden fik timeout. "
                f"Skade-id: {skade_id}. "
                f"URL: {skade_url}."
            ) from error

    await page.wait_for_load_state(
        "domcontentloaded"
    )

    await page.wait_for_timeout(
        UI_WAIT_MS
    )

    if str(skade_id) in page.url:
        return

    synligt_skade_id = page.get_by_text(
        str(skade_id),
        exact=True,
    ).first

    try:
        await synligt_skade_id.wait_for(
            state="visible",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Den ønskede skade kunne ikke bekræftes "
            "som aktiv i Insubiz. "
            f"Skade-id: {skade_id}. "
            f"Aktuel URL: {page.url}."
        ) from error


# --------------------------------------------------
# DOKUMENTDIALOG
# --------------------------------------------------


async def opret_dokument(
    *,
    page: Page,
    skabelon_navn: str,
) -> str:
    """Åbner dialogen, vælger skabelonen og gemmer dokumentet."""
    dialog: Locator = await opret_dokument_fra_skabelon(
        page=page,
    )

    valgt_skabelon = await vaelg_dokumentskabelon(
        page=page,
        dialog=dialog,
        skabelon_navn=skabelon_navn,
    )

    await gem_dokument_fra_skabelon(
        page=page,
        dialog=dialog,
    )

    return valgt_skabelon


# --------------------------------------------------
# RESULTATKONTROL
# --------------------------------------------------


def kontroller_resultat(
    *,
    valgt_skabelon: Any,
    forventet_skabelon: str,
) -> None:
    """Kontrollerer den valgte skabelontekst."""
    if not isinstance(valgt_skabelon, str):
        raise AssertionError(
            "Den valgte skabelon skal være tekst. "
            f"Modtog: {type(valgt_skabelon).__name__}."
        )

    normalized_valgt_skabelon = (
        " ".join(
            valgt_skabelon.strip().split()
        ).casefold()
    )

    normalized_forventet_skabelon = (
        " ".join(
            forventet_skabelon.strip().split()
        ).casefold()
    )

    if not normalized_valgt_skabelon:
        raise AssertionError(
            "Den valgte skabelontekst er tom."
        )

    if (
        normalized_forventet_skabelon
        not in normalized_valgt_skabelon
    ):
        raise AssertionError(
            "Den valgte skabelon matcher ikke. "
            f"Forventede: {forventet_skabelon!r}. "
            f"Modtog: {valgt_skabelon!r}."
        )


# --------------------------------------------------
# UDSKRIFT
# --------------------------------------------------


def udskriv_testindstillinger(
    *,
    skade_id: int,
    skabelon_navn: str,
) -> None:
    """Udskriver testens indstillinger."""
    print()
    print("=" * 80)
    print("TESTER OPRET DOKUMENT FRA SKABELON")
    print("=" * 80)
    print(f"Skade-id: {skade_id}")
    print(f"Skabelon: {skabelon_navn}")
    print(f"Headless: {HEADLESS}")
    print("Dokumentet bliver oprettet og gemt: Ja")
    print("=" * 80)



def udskriv_resultat(
    *,
    skade_id: int,
    valgt_skabelon: str,
) -> None:
    """Udskriver det kontrollerede testresultat."""
    print()
    print("=" * 80)
    print("DOKUMENT BLEV OPRETTET FRA SKABELON")
    print("=" * 80)
    print(f"Skade-id: {skade_id}")
    print(f"Valgt skabelon: {valgt_skabelon}")
    print("Dokument gemt: Ja")
    print("=" * 80)
    print()
    print("TEST BESTÅET")


# --------------------------------------------------
# INTEGRATIONSTEST
# --------------------------------------------------


async def test_opret_dokument_fra_skabelon() -> None:
    """Tester oprettelse af et dokument på en konkret skade."""
    skade_id, skabelon_navn = valider_testinput()

    auth_manager = InsubizAuthManager(
        headless=HEADLESS,
    )

    page: Page | None = None

    try:
        page = await auth_manager.get_page()

        udskriv_testindstillinger(
            skade_id=skade_id,
            skabelon_navn=skabelon_navn,
        )

        await aabn_skade_via_id(
            page=page,
            skade_id=skade_id,
        )

        valgt_skabelon = await opret_dokument(
            page=page,
            skabelon_navn=skabelon_navn,
        )

        kontroller_resultat(
            valgt_skabelon=valgt_skabelon,
            forventet_skabelon=skabelon_navn,
        )

        udskriv_resultat(
            skade_id=skade_id,
            valgt_skabelon=valgt_skabelon,
        )

        await page.wait_for_timeout(
            UI_WAIT_MS
        )

    except Exception as error:
        print()
        print("=" * 80)
        print("TEST FEJLEDE")
        print("=" * 80)
        print(f"Skade-id: {skade_id}")
        print(f"Skabelon: {skabelon_navn}")
        print(f"Fejltype: {type(error).__name__}")
        print(f"Fejl: {error}")

        if (
            page is not None
            and not page.is_closed()
        ):
            print(f"Aktuel URL: {page.url}")

        print("=" * 80)
        raise

    finally:
        await auth_manager.close()


# --------------------------------------------------
# DIREKTE KØRSEL FRA VS CODE
# --------------------------------------------------


if __name__ == "__main__":
    asyncio.run(
        test_opret_dokument_fra_skabelon()
    )
