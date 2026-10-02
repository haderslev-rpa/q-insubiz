from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from q_insubiz.api.auth_manager import InsubizAuthManager
from q_insubiz.functionality.skader import opret_kommentar_paa_skade

logger = logging.getLogger(__name__)

DANSK_TIDSZONE = ZoneInfo("Europe/Copenhagen")

HOVEDDOKUMENT = "Robot - henlæggelsesbrev.pdf"
BILAG = "Anmeldelse af arbejdsulykke - 202601494.pdf"


def laes_skade_id() -> int:
    """Læs og kontrollér skade-id fra terminalen."""
    tekst = input("Skade-id til test: ").strip()

    if not tekst.isdigit() or int(tekst) <= 0:
        raise ValueError("Skade-id skal være et positivt heltal.")

    return int(tekst)


def byg_kommentar() -> tuple[str, str]:
    """Returnér titel og kommentartekst."""
    nu = datetime.now(DANSK_TIDSZONE)

    titel = (
        "Henlæggelsesbrev afsendt til borger d. "
        f"{nu:%d-%m-%Y %H:%M}"
    )
    kommentartekst = (
        f"Hoved dokument: {HOVEDDOKUMENT}\n"
        f"Bilag: {BILAG}"
    )

    return titel, kommentartekst


def kontroller_svar(
    kommentar: dict,
    *,
    skade_id: int,
    titel: str,
    kommentartekst: str,
) -> int:
    """Kontrollér svaret og returnér kommentarens id."""
    kommentar_id = kommentar.get("id")

    if (
        isinstance(kommentar_id, bool)
        or not isinstance(kommentar_id, int)
        or kommentar_id <= 0
    ):
        raise AssertionError("Svaret mangler et gyldigt kommentar-id.")

    skade = kommentar.get("ibObject")
    if not isinstance(skade, dict) or skade.get("id") != skade_id:
        raise AssertionError(
            f"Kommentar {kommentar_id} matcher ikke skade-id {skade_id}."
        )

    if kommentar.get("title") != titel:
        raise AssertionError(
            f"Titlen på kommentar {kommentar_id} matcher ikke."
        )

    body = kommentar.get("body")
    if not isinstance(body, str):
        raise AssertionError(
            f"Kommentar {kommentar_id} mangler tekst i svaret."
        )

    # Kommentarfunktionen omdanner almindelig tekst til HTML.
    forventet_html = (
        "<p>"
        + html.escape(kommentartekst).replace("\n", "<br>")
        + "</p>"
    )

    if html.unescape(body) != html.unescape(forventet_html):
        raise AssertionError(
            "Den gemte tekst matcher ikke den forventede tekst. "
            f"Kommentar-id: {kommentar_id}. "
            "Kontrollér kommentaren i Insubiz før et nyt forsøg."
        )

    return kommentar_id


async def test_opret_kommentar_paa_skade() -> None:
    """Opret én kommentar efter manuel bekræftelse."""
    skade_id = laes_skade_id()
    titel, kommentartekst = byg_kommentar()

    print()
    print(f"Skade-id: {skade_id}")
    print(f"Titel: {titel}")
    print("Kommentar:")
    print(kommentartekst)
    print()
    print(
        "OBS: Dette opretter en rigtig kommentar. "
        "Kontrollér, at brevet faktisk er sendt, "
        "og at skade-id og filnavne er korrekte."
    )

    bekraeftelse = input("Skriv OPRET for at fortsætte: ").strip()
    if bekraeftelse != "OPRET":
        print("Afbrudt. Ingen kommentar blev oprettet.")
        return

    auth_manager = InsubizAuthManager(headless=True)

    try:
        request_context = await auth_manager.get_request_context()

        kommentar = await opret_kommentar_paa_skade(
            request_context=request_context,
            skade_id=skade_id,
            titel=titel,
            kommentartekst=kommentartekst,
        )

        kommentar_id = kontroller_svar(
            kommentar,
            skade_id=skade_id,
            titel=titel,
            kommentartekst=kommentartekst,
        )

        print()
        print("TEST BESTÅET")
        print(f"Skade-id: {skade_id}")
        print(f"Kommentar-id: {kommentar_id}")
        print(f"Titel: {titel}")
        print("Kommentar:")
        print(kommentartekst)

    except Exception:
        logger.exception(
            "Testen fejlede for skade-id %s. Kontrollér i Insubiz, "
            "om kommentaren blev oprettet, før testen køres igen.",
            skade_id,
        )
        raise
    finally:
        await auth_manager.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(test_opret_kommentar_paa_skade())