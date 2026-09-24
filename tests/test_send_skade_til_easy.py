from __future__ import annotations

"""Integrationstest af validering og afsendelse af en skade til EASY.

Testen følger Insubiz-flowet:

1. Opret en autentificeret API-klient.
2. Kald ValidateIncidentForSendToEasy.
3. Kald send_skade_til_easy.
4. Kontrollér det returnerede SendSkadeTilEasyResultat.
5. Udskriv et læsbart JSON-resultat.

Bemærk
------

send_skade_til_easy() udfører selv valideringskaldet før afsendelsen.
Det særskilte valideringskald i testen bruges kun til diagnostik, så det
faktiske valideringssvar kan ses i terminalen før den komplette funktion
køres.
"""

import asyncio
import json
from dataclasses import asdict
from typing import Any

from q_insubiz.api.auth_manager import InsubizAuthManager
from q_insubiz.api.client import InsubizApiClient
from q_insubiz.functionality.skader import (
    EASY_STATUS_AFSENDT_AFVENTER,
    EASY_STATUS_GODKENDT,
    SendSkadeTilEasyResultat,
    send_skade_til_easy,
    valider_skade_foer_easy,
)


# ------------------------------------------------------------
# TESTINDSTILLINGER
# ------------------------------------------------------------

HEADLESS = False

# Erstat skade-id'et, når en anden skade skal integrationstestes.
SKADE_ID: int | str = 2491803


# ------------------------------------------------------------
# HJÆLPEFUNKTIONER
# ------------------------------------------------------------


def normalize_text(value: Any) -> str:
    """Normaliserer tekst til robust sammenligning."""
    return " ".join(
        str(value).strip().split()
    ).casefold()


def print_json(
    *,
    overskrift: str,
    value: Any,
) -> None:
    """Udskriver en værdi som formateret JSON."""
    print()
    print("=" * 80)
    print(overskrift)
    print("=" * 80)
    print(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


def print_resultat(
    result: SendSkadeTilEasyResultat,
) -> None:
    """Udskriver EASY-resultatet som JSON."""
    print_json(
        overskrift="RESULTAT FRA EASY-KONTROL OG AFSENDELSE",
        value=asdict(result),
    )


def kontroller_resultat(
    *,
    result: SendSkadeTilEasyResultat,
    forventet_skade_id: int,
) -> None:
    """Kontrollerer et konsistent resultat fra EASY-funktionen."""
    if not isinstance(
        result,
        SendSkadeTilEasyResultat,
    ):
        raise AssertionError(
            "Resultatet skal være SendSkadeTilEasyResultat. "
            f"Modtog: {type(result).__name__}."
        )

    if result.skade_id != forventet_skade_id:
        raise AssertionError(
            "Resultatets skade-id matcher ikke. "
            f"Forventede: {forventet_skade_id}. "
            f"Modtog: {result.skade_id}."
        )

    if result.allerede_sendt == result.sendt_nu:
        raise AssertionError(
            "Præcis ét af felterne allerede_sendt og "
            "sendt_nu skal være True."
        )

    if not isinstance(result.besked, str) or not result.besked.strip():
        raise AssertionError(
            "Resultatets besked skal være en ikke-tom tekst."
        )

    if result.allerede_sendt:
        stopstatusser = {
            normalize_text(EASY_STATUS_GODKENDT),
            normalize_text(EASY_STATUS_AFSENDT_AFVENTER),
        }

        normalized_status = normalize_text(
            result.easy_status_foer
        )

        if normalized_status not in stopstatusser:
            raise AssertionError(
                "Skaden blev markeret som allerede sendt, "
                "men EASY-statussen er ikke en stopstatus. "
                f"Status: {result.easy_status_foer!r}."
            )

        if result.afsendelses_response is not None:
            raise AssertionError(
                "Der må ikke være et afsendelsessvar, "
                "når sendekaldet blev sprunget over."
            )

        return

    if not result.sendt_nu:
        raise AssertionError(
            "Skaden blev hverken markeret som allerede sendt "
            "eller sendt i denne kørsel."
        )

    if result.afsendelses_response is None:
        raise AssertionError(
            "Afsendelsesresponset mangler for en skade, "
            "der blev sendt i denne kørsel."
        )


def print_succes(
    *,
    result: SendSkadeTilEasyResultat,
) -> None:
    """Udskriver det validerede slutresultat."""
    print()
    print("=" * 80)

    if result.sendt_nu:
        print("SKADEN BLEV SENDT TIL EASY")
        print("=" * 80)
        print(f"Skade-id: {result.skade_id}")
        print(
            "EASY-status før afsendelse: "
            f"{result.easy_status_foer!r}"
        )
        print("SendIncidentToEasy kaldt: Ja")
    else:
        print("SKADEN VAR ALLEREDE SENDT TIL EASY")
        print("=" * 80)
        print(f"Skade-id: {result.skade_id}")
        print(
            "EASY-status: "
            f"{result.easy_status_foer!r}"
        )
        print("SendIncidentToEasy kaldt: Nej")

    if result.easy_reference:
        print(
            "EASY-reference: "
            f"{result.easy_reference}"
        )

    print("=" * 80)
    print(f"Besked: {result.besked}")
    print("=" * 80)
    print()
    print("TEST BESTÅET")


# ------------------------------------------------------------
# INTEGRATIONSTEST
# ------------------------------------------------------------


async def test_send_skade_til_easy() -> None:
    """Validerer og sender en konkret skade til EASY."""
    try:
        normalized_skade_id = int(
            str(SKADE_ID).strip()
        )
    except (TypeError, ValueError) as error:
        raise AssertionError(
            "SKADE_ID skal kunne konverteres til et heltal. "
            f"Modtog: {SKADE_ID!r}."
        ) from error

    if normalized_skade_id <= 0:
        raise AssertionError(
            "SKADE_ID skal være større end 0. "
            f"Modtog: {normalized_skade_id}."
        )

    auth_manager = InsubizAuthManager(
        headless=HEADLESS,
    )

    api_client = InsubizApiClient(
        auth_manager=auth_manager,
    )

    try:
        print()
        print("=" * 80)
        print("VALIDERER OG SENDER SKADE TIL EASY")
        print("=" * 80)
        print(f"Skade-id: {normalized_skade_id}")
        print(f"Headless: {HEADLESS}")
        print("=" * 80)

        validation_response = await valider_skade_foer_easy(
            api_client=api_client,
            skade_id=normalized_skade_id,
        )

        print_json(
            overskrift="RESPONSE FRA ValidateIncidentForSendToEasy",
            value=validation_response,
        )

        result = await send_skade_til_easy(
            api_client=api_client,
            skade_id=normalized_skade_id,
        )

        kontroller_resultat(
            result=result,
            forventet_skade_id=normalized_skade_id,
        )

        print_resultat(result)
        print_succes(result=result)

    except RuntimeError as error:
        print()
        print("=" * 80)
        print("TEST FEJLEDE")
        print("=" * 80)
        print(f"Skade-id: {normalized_skade_id}")
        print(f"Fejl: {error}")
        print("=" * 80)
        raise

    finally:
        await api_client.close()


# ------------------------------------------------------------
# DIREKTE KØRSEL FRA VS CODE
# ------------------------------------------------------------


if __name__ == "__main__":
    asyncio.run(
        test_send_skade_til_easy()
    )
