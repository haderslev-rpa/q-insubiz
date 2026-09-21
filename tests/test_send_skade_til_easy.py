import asyncio
import json
from dataclasses import asdict

from q_insubiz.api.auth_manager import InsubizAuthManager
from q_insubiz.api.client import InsubizApiClient
from q_insubiz.functionality.skader import (
    EASY_STATUS_AFSENDT_AFVENTER,
    EASY_STATUS_GODKENDT,
    SendSkadeTilEasyResultat,
    send_skade_til_easy,
)


# --------------------------------------------------
# Testindstillinger
# --------------------------------------------------
HEADLESS = False

# Denne skade er oplyst som endnu ikke sendt til EASY.
SKADE_ID: int | str = 2490496


# --------------------------------------------------
# Hjælpefunktioner
# --------------------------------------------------
def normalize_text(value: str) -> str:
    """Normaliserer tekst til sammenligning."""
    return " ".join(value.split()).casefold()


def print_resultat(
    result: SendSkadeTilEasyResultat,
) -> None:
    """Udskriver resultatet som JSON."""
    print()
    print("Resultat fra EASY-kontrol og afsendelse:")
    print(
        json.dumps(
            asdict(result),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


def kontroller_resultat(
    *,
    result: SendSkadeTilEasyResultat,
    forventet_skade_id: int,
) -> None:
    """Kontrollerer et konsistent funktionsresultat."""
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

    if result.allerede_sendt:
        stopstatusser = {
            normalize_text(EASY_STATUS_GODKENDT),
            normalize_text(EASY_STATUS_AFSENDT_AFVENTER),
        }

        if normalize_text(
            result.easy_status_foer
        ) not in stopstatusser:
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
            "Skaden blev ikke sendt i denne kørsel."
        )

    if result.afsendelses_response is None:
        raise AssertionError(
            "Afsendelsesresponset mangler."
        )


# --------------------------------------------------
# Test
# --------------------------------------------------
async def test_send_skade_til_easy() -> None:
    """
    Kontrollerer easy.easyStatus.text og sender skaden,
    hvis den ikke allerede er sendt.

    Første kørsel på den angivne skade forventes at
    sende skaden. Senere kørsler accepterer, at skaden
    allerede har en af de to stopstatusser.
    """
    normalized_skade_id = int(
        str(SKADE_ID).strip()
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
        print("KONTROLLERER OG SENDER SKADE TIL EASY")
        print("=" * 80)
        print(f"Skade-id: {normalized_skade_id}")
        print("=" * 80)

        result = await send_skade_til_easy(
            api_client=api_client,
            skade_id=normalized_skade_id,
        )

        kontroller_resultat(
            result=result,
            forventet_skade_id=normalized_skade_id,
        )

        print_resultat(result)

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
                f"{result.easy_status_foer}"
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

    finally:
        await api_client.close()


# --------------------------------------------------
# Direkte kørsel fra VS Code
# --------------------------------------------------
if __name__ == "__main__":
    asyncio.run(
        test_send_skade_til_easy()
    )
