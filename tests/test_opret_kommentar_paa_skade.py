from __future__ import annotations

import asyncio
import html
import logging

from q_insubiz.api.auth_manager import InsubizAuthManager
from q_insubiz.functionality.skader import opret_kommentar_paa_skade

logger = logging.getLogger(__name__)


def laes_testinput() -> tuple[int, str, str]:
    """Læs og kontrollér skade-id, titel og kommentartekst."""
    skade_id_tekst = input("Skade-id til test: ").strip()
    if not skade_id_tekst.isdigit() or int(skade_id_tekst) <= 0:
        raise ValueError("Skade-id skal være et positivt heltal.")

    titel = input("Kommentarens titel: ").strip()
    if not titel:
        raise ValueError("Titlen må ikke være tom.")

    kommentartekst = input("Kommentartekst: ").strip()
    if not kommentartekst:
        raise ValueError("Kommentarteksten må ikke være tom.")

    return int(skade_id_tekst), titel, kommentartekst


async def test_opret_kommentar_paa_skade() -> None:
    """Opret én kommentar og kontrollér Insubiz-svaret."""
    skade_id, titel, kommentartekst = laes_testinput()

    print()
    print(f"Skade-id: {skade_id}")
    print(f"Titel: {titel}")
    print(f"Tekst: {kommentartekst}")
    print("OBS: Testen opretter en rigtig kommentar i Insubiz.")

    bekraeftelse = input(
        "Skriv OPRET for at oprette kommentaren: "
    ).strip()
    if bekraeftelse != "OPRET":
        print("Afbrudt. Ingen kommentar blev oprettet.")
        return

    auth_manager = InsubizAuthManager(headless=False)
    try:
        request_context = await auth_manager.get_request_context()

        kommentar = await opret_kommentar_paa_skade(
            request_context=request_context,
            skade_id=skade_id,
            titel=titel,
            kommentartekst=kommentartekst,
        )

        kommentar_id = kommentar.get("id")
        if kommentar.get("ibObject", {}).get("id") != skade_id:
            raise AssertionError(
                "Svaret indeholder ikke det forventede skade-id."
            )
        if kommentar.get("title") != titel:
            raise AssertionError(
                "Den gemte titel matcher ikke testens titel."
            )

        body = kommentar.get("body")
        if not isinstance(body, str):
            raise AssertionError(
                "Svaret indeholder ikke en kommentartekst."
            )

        # Funktionen fra sidste svar sender almindelig tekst som HTML.
        forventet_body = (
            "<p>"
            + html.escape(kommentartekst).replace("\n", "<br>")
            + "</p>"
        )
        if html.unescape(body) != html.unescape(forventet_body):
            raise AssertionError(
                "Den gemte kommentartekst matcher ikke testens tekst. "
                f"Kommentar-id: {kommentar_id}. "
                "Kontrollér kommentaren manuelt før et nyt forsøg."
            )

        print()
        print("TEST BESTÅET")
        print(f"Skade-id: {skade_id}")
        print(f"Kommentar-id: {kommentar_id}")
        print(f"Gemt titel: {kommentar['title']}")
        print(f"Gemt body: {body}")

    except Exception:
        logger.exception(
            "Kommentartesten fejlede for skade-id %s. "
            "Kontrollér, om kommentaren alligevel blev oprettet, "
            "før testen køres igen.",
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