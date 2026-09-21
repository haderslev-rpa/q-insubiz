from __future__ import annotations

import asyncio
import os
from typing import Any

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.functionality.skader import (
    klik_paa_skade,
    send_digital_post,
)
from q_insubiz.utils import (
    normalize_positive_id,
)


# --------------------------------------------------
# Testindstillinger
# --------------------------------------------------

HEADLESS = False

TIMEOUT_MS = 15_000
NAVIGATION_TIMEOUT_MS = 30_000
UI_WAIT_MS = 1_500

BASE_URL = "https://start.insubiz.dk"

SKADE_ID = 2489380

CPR_NUMMER = os.getenv(
    "CPR_NUMMER",
    "",
).strip()

DOKUMENTTITEL = (
    "Brev fra Haderslev kommune"
)

FORSENDELSESTYPE = (
    "Insubizbrev"
)

HOVEDDOKUMENT_NAVN = (
    "Robot - Henlæggelsesbrev"
)

BILAG_NAVN = (
    "Anmeldelse af arbejdsulykke"
)


# --------------------------------------------------
# Testinput
# --------------------------------------------------

def valider_testinput() -> int:
    """
    Validerer testinput uden at vise CPR-nummeret.

    Returnerer det normaliserede skade-id.
    """
    normalized_skade_id = normalize_positive_id(
        name="SKADE_ID",
        value=SKADE_ID,
    )

    if not CPR_NUMMER:
        raise RuntimeError(
            "Miljøvariablen CPR_NUMMER mangler. "
            "Angiv CPR_NUMMER før testen køres."
        )

    if not CPR_NUMMER.isdigit():
        raise ValueError(
            "Miljøvariablen CPR_NUMMER skal "
            "kun indeholde cifre."
        )

    if len(CPR_NUMMER) != 10:
        raise ValueError(
            "Miljøvariablen CPR_NUMMER skal "
            "indeholde præcis 10 cifre."
        )

    testvaerdier = {
        "DOKUMENTTITEL": DOKUMENTTITEL,
        "FORSENDELSESTYPE": FORSENDELSESTYPE,
        "HOVEDDOKUMENT_NAVN": HOVEDDOKUMENT_NAVN,
        "BILAG_NAVN": BILAG_NAVN,
    }

    for name, value in testvaerdier.items():
        if not isinstance(value, str):
            raise TypeError(
                f"{name} skal være tekst."
            )

        if not value.strip():
            raise ValueError(
                f"{name} må ikke være tom."
            )

    return normalized_skade_id


# --------------------------------------------------
# Åbn konkret skade
# --------------------------------------------------

async def aabn_skade_via_id(
    *,
    page: Page,
    skade_id: int | str,
) -> None:
    """Åbner skademodulet og den konkrete skade."""
    if page.is_closed():
        raise RuntimeError(
            "Skaden kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    normalized_skade_id = normalize_positive_id(
        name="skade_id",
        value=skade_id,
    )

    await klik_paa_skade(
        page=page,
    )

    skade_url = (
        f"{BASE_URL}/incident/"
        f"{normalized_skade_id}"
    )

    if str(normalized_skade_id) not in page.url:
        try:
            await page.goto(
                skade_url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError as error:
            raise RuntimeError(
                "Navigation til skaden fik timeout. "
                f"Skade-id: {normalized_skade_id}. "
                f"URL: {skade_url}."
            ) from error

    await page.wait_for_load_state(
        "domcontentloaded"
    )

    await page.wait_for_timeout(
        UI_WAIT_MS
    )

    if str(normalized_skade_id) in page.url:
        return

    synligt_skade_id = page.get_by_text(
        str(normalized_skade_id),
        exact=True,
    ).first

    try:
        await synligt_skade_id.wait_for(
            state="visible",
            timeout=TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as error:
        raise RuntimeError(
            "Den ønskede skade kunne ikke "
            "bekræftes som aktiv. "
            f"Skade-id: {normalized_skade_id}. "
            f"Aktuel URL: {page.url}."
        ) from error


# --------------------------------------------------
# Resultatkontrol
# --------------------------------------------------

def kontroller_resultat(
    *,
    resultat: dict[str, Any],
) -> None:
    """Kontrollerer resultatet fra send_digital_post."""
    if not isinstance(resultat, dict):
        raise AssertionError(
            "send_digital_post returnerede ikke "
            "en dictionary. "
            f"Modtog: {type(resultat).__name__}."
        )

    forventede_felter = {
        "dokumenttitel",
        "forsendelsestype",
        "hoveddokument",
        "bilag",
        "faktisk_hoveddokument",
        "faktisk_bilag",
        "hoveddokumentvaelger_rækker",
        "bilagsvaelger_rækker",
        "test",
        "sendt",
    }

    manglende_felter = (
        forventede_felter
        - resultat.keys()
    )

    if manglende_felter:
        raise AssertionError(
            "Resultatet mangler forventede felter. "
            f"Manglende felter: "
            f"{sorted(manglende_felter)!r}."
        )

    forventede_vaerdier = {
        "dokumenttitel": DOKUMENTTITEL,
        "forsendelsestype": FORSENDELSESTYPE,
        "hoveddokument": HOVEDDOKUMENT_NAVN,
        "bilag": BILAG_NAVN,
        "test": True,
        "sendt": False,
    }

    for (
        feltnavn,
        forventet_vaerdi,
    ) in forventede_vaerdier.items():
        faktisk_vaerdi = resultat.get(
            feltnavn
        )

        if faktisk_vaerdi != forventet_vaerdi:
            raise AssertionError(
                f"Resultatfeltet {feltnavn!r} "
                "matcher ikke. "
                f"Forventede: {forventet_vaerdi!r}. "
                f"Modtog: {faktisk_vaerdi!r}."
            )

    _kontroller_dokumentnavn(
        feltnavn="faktisk_hoveddokument",
        value=resultat.get(
            "faktisk_hoveddokument"
        ),
        forventet_navn=HOVEDDOKUMENT_NAVN,
    )

    _kontroller_dokumentnavn(
        feltnavn="faktisk_bilag",
        value=resultat.get(
            "faktisk_bilag"
        ),
        forventet_navn=BILAG_NAVN,
    )

    _kontroller_dokumentraekker(
        feltnavn=(
            "hoveddokumentvaelger_rækker"
        ),
        value=resultat.get(
            "hoveddokumentvaelger_rækker"
        ),
    )

    _kontroller_dokumentraekker(
        feltnavn=(
            "bilagsvaelger_rækker"
        ),
        value=resultat.get(
            "bilagsvaelger_rækker"
        ),
    )


def _kontroller_dokumentnavn(
    *,
    feltnavn: str,
    value: Any,
    forventet_navn: str,
) -> None:
    """Kontrollerer et dokumentnavn fra resultatet."""
    if not isinstance(value, str):
        raise AssertionError(
            f"Resultatfeltet {feltnavn!r} "
            "skal være tekst. "
            f"Modtog: {type(value).__name__}."
        )

    actual_name = value.strip()

    if not actual_name:
        raise AssertionError(
            f"Resultatfeltet {feltnavn!r} "
            "må ikke være tomt."
        )

    normalized_actual_name = (
        _normalize_document_name(
            actual_name
        )
    )

    normalized_expected_name = (
        _normalize_document_name(
            forventet_navn
        )
    )

    if (
        normalized_actual_name
        != normalized_expected_name
        and not normalized_actual_name.startswith(
            normalized_expected_name
        )
    ):
        raise AssertionError(
            f"Resultatfeltet {feltnavn!r} "
            "matcher ikke det forventede dokument. "
            f"Forventede: {forventet_navn!r}. "
            f"Modtog: {actual_name!r}."
        )


def _kontroller_dokumentraekker(
    *,
    feltnavn: str,
    value: Any,
) -> None:
    """Kontrollerer dokumentrækker fra en dokumentvælger."""
    if not isinstance(value, list):
        raise AssertionError(
            f"Resultatfeltet {feltnavn!r} "
            "skal være en liste. "
            f"Modtog: {type(value).__name__}."
        )

    if not value:
        raise AssertionError(
            f"Resultatfeltet {feltnavn!r} "
            "indeholder ingen dokumenter."
        )

    for index, dokumentnavn in enumerate(
        value,
        start=1,
    ):
        if not isinstance(dokumentnavn, str):
            raise AssertionError(
                f"Dokument nummer {index} i "
                f"{feltnavn!r} skal være tekst. "
                f"Modtog: "
                f"{type(dokumentnavn).__name__}."
            )

        if not dokumentnavn.strip():
            raise AssertionError(
                f"Dokument nummer {index} i "
                f"{feltnavn!r} er tomt."
            )


def _normalize_document_name(
    value: str,
) -> str:
    """Normaliserer et dokumentnavn til sammenligning."""
    normalized = " ".join(
        value.strip().split()
    ).casefold()

    extensions = (
        ".pdf",
        ".docx",
        ".doc",
        ".xlsx",
        ".xls",
    )

    for extension in extensions:
        if normalized.endswith(extension):
            return normalized[
                :-len(extension)
            ].rstrip()

    return normalized


# --------------------------------------------------
# Udskrift
# --------------------------------------------------

def udskriv_testindstillinger(
    *,
    skade_id: int,
) -> None:
    """Udskriver testens ikke-følsomme indstillinger."""
    print()
    print("=" * 80)
    print(
        "TESTER SEND DIGITAL POST "
        "UDEN AFSENDELSE"
    )
    print("=" * 80)
    print(f"Skade-id: {skade_id}")
    print(
        f"Dokumenttitel: {DOKUMENTTITEL}"
    )
    print(
        f"Forsendelsestype: {FORSENDELSESTYPE}"
    )
    print(
        "Hoveddokument: "
        f"{HOVEDDOKUMENT_NAVN}"
    )
    print(f"Bilag: {BILAG_NAVN}")
    print("CPR-nummer: [skjult]")
    print("Testtilstand: Ja")
    print("Afsluttende Send-knap klikkes: Nej")
    print("=" * 80)


def udskriv_resultat(
    *,
    resultat: dict[str, Any],
    skade_id: int,
) -> None:
    """Udskriver det kontrollerede testresultat."""
    hoveddokument_rows = resultat[
        "hoveddokumentvaelger_rækker"
    ]

    bilag_rows = resultat[
        "bilagsvaelger_rækker"
    ]

    print()
    print("=" * 80)
    print(
        "DIGITAL POST ER UDFYLDT KORREKT"
    )
    print("=" * 80)
    print(f"Skade-id: {skade_id}")
    print(
        "Dokumenttitel: "
        f"{resultat['dokumenttitel']}"
    )
    print(
        "Forsendelsestype: "
        f"{resultat['forsendelsestype']}"
    )
    print(
        "Hoveddokument-chip: "
        f"{resultat['faktisk_hoveddokument']}"
    )
    print(
        "Bilag-chip: "
        f"{resultat['faktisk_bilag']}"
    )
    print(
        "Antal rækker i "
        "hoveddokumentvælger: "
        f"{len(hoveddokument_rows)}"
    )
    print(
        "Antal rækker i bilagsvælger: "
        f"{len(bilag_rows)}"
    )
    print("Testtilstand: Ja")
    print(
        "Afsluttende Send-knap klikket: Nej"
    )
    print("Digital Post sendt: Nej")
    print("=" * 80)
    print()
    print("TEST BESTÅET")


# --------------------------------------------------
# Integrationstest
# --------------------------------------------------

async def test_send_digital_post_uden_afsendelse(
) -> None:
    """
    Tester produktionsfunktionen send_digital_post.

    Funktionen udfylder Digital Post-dialogen, vælger
    forsendelsestypen, vedhæfter hoveddokument og bilag
    og kontrollerer begge dokumentchips.

    test=True betyder, at Send-knappen ikke klikkes.
    """
    normalized_skade_id = valider_testinput()

    auth_manager = InsubizAuthManager(
        headless=HEADLESS,
    )

    page: Page | None = None

    try:
        page = await auth_manager.get_page()

        udskriv_testindstillinger(
            skade_id=normalized_skade_id,
        )

        await aabn_skade_via_id(
            page=page,
            skade_id=normalized_skade_id,
        )

        resultat = await send_digital_post(
            page=page,
            cpr_nummer=CPR_NUMMER,
            dokumenttitel=DOKUMENTTITEL,
            forsendelsestype=FORSENDELSESTYPE,
            hoveddokument_navn=(
                HOVEDDOKUMENT_NAVN
            ),
            bilag_navn=BILAG_NAVN,
            test=True,
        )

        kontroller_resultat(
            resultat=resultat,
        )

        udskriv_resultat(
            resultat=resultat,
            skade_id=normalized_skade_id,
        )

        await page.wait_for_timeout(
            UI_WAIT_MS
        )

    except Exception as error:
        print()
        print("=" * 80)
        print("TEST FEJLEDE")
        print("=" * 80)
        print(f"Fejl: {error}")

        if (
            page is not None
            and not page.is_closed()
        ):
            print(
                f"Aktuel URL: {page.url}"
            )

        print("=" * 80)

        raise

    finally:
        await auth_manager.close()


# --------------------------------------------------
# Direkte kørsel fra VS Code
# --------------------------------------------------

if __name__ == "__main__":
    asyncio.run(
        test_send_digital_post_uden_afsendelse()
    )