import asyncio
import json
from typing import Any

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.api.client import (
    InsubizApiClient,
)
from q_insubiz.functionality.skader import (
    hent_skade_via_id,
)


# --------------------------------------------------
# Testindstillinger
# --------------------------------------------------
SKADE_ID = 2473395
HEADLESS = False


# --------------------------------------------------
# Hjælpefunktioner
# --------------------------------------------------
def hent_tekst(
    value: Any,
) -> str:
    """Henter text-feltet fra et objekt."""
    if not isinstance(value, dict):
        return ""

    return str(
        value.get("text") or ""
    ).strip()


def udskriv_felt(
    *,
    navn: str,
    value: Any,
) -> None:
    """Udskriver et felt med et læsbart navn."""
    print(
        f"{navn}: {value}"
    )


# --------------------------------------------------
# Test
# --------------------------------------------------
async def test_skade() -> None:
    """
    Henter en specifik skade fra Insubiz via skade-id.

    Testen kontrollerer kun svarstrukturen og udskriver
    de faktiske værdier. Testen forventer ikke bestemte
    forretningsværdier fra en bestemt skade.
    """
    auth_manager = InsubizAuthManager(
        headless=HEADLESS,
    )

    api_client = InsubizApiClient(
        auth_manager=auth_manager,
    )

    try:
        print()
        print("=" * 80)
        print("HENTER SKADE FRA INSUBIZ")
        print("=" * 80)
        print(f"Skade-id: {SKADE_ID}")

        skade: dict[str, Any] = (
            await hent_skade_via_id(
                api_client=api_client,
                skade_id=SKADE_ID,
            )
        )

        # ------------------------------------------
        # Kontrollér overordnet svar
        # ------------------------------------------
        if not isinstance(skade, dict):
            raise AssertionError(
                "hent_skade_via_id returnerede ikke "
                "en dictionary. "
                f"Modtog: {type(skade).__name__}."
            )

        if not skade:
            raise AssertionError(
                "Insubiz returnerede et tomt svar. "
                f"Skade-id: {SKADE_ID}."
            )

        # ------------------------------------------
        # Grundoplysninger
        # ------------------------------------------
        print()
        print("=" * 80)
        print("GRUNDOPLYSNINGER")
        print("=" * 80)

        udskriv_felt(
            navn="Forespurgt skade-id",
            value=SKADE_ID,
        )
        udskriv_felt(
            navn="Id fra svaret",
            value=skade.get("id"),
        )
        udskriv_felt(
            navn="Internt skadenummer",
            value=(
                skade.get("incidentNumberInternal")
                or skade.get("incidentNumber")
            ),
        )
        udskriv_felt(
            navn="Sidst redigeret",
            value=skade.get("lastEditing"),
        )

        # ------------------------------------------
        # Almindelig skadestatus
        # ------------------------------------------
        status = skade.get("status")

        print()
        print("=" * 80)
        print("SKADESTATUS")
        print("=" * 80)

        if isinstance(status, dict):
            udskriv_felt(
                navn="Status-id",
                value=status.get("id"),
            )
            udskriv_felt(
                navn="Status",
                value=status.get("text"),
            )
        else:
            udskriv_felt(
                navn="Status-id",
                value=skade.get("statusId"),
            )
            udskriv_felt(
                navn="Statusobjekt",
                value=status,
            )

        # ------------------------------------------
        # EASY-oplysninger
        # ------------------------------------------
        easy_status = skade.get("easyStatus")

        print()
        print("=" * 80)
        print("EASY-OPLYSNINGER")
        print("=" * 80)

        udskriv_felt(
            navn="EASY-reference",
            value=skade.get("easyRef"),
        )
        udskriv_felt(
            navn="EASY claim-id",
            value=skade.get("easyClaimId"),
        )
        udskriv_felt(
            navn="EASY-dato",
            value=skade.get("easyDate"),
        )
        udskriv_felt(
            navn="Dokument-uploadstatus",
            value=skade.get("documentUploadStatus"),
        )

        if isinstance(easy_status, dict):
            udskriv_felt(
                navn="EASY-status-id",
                value=easy_status.get("id"),
            )
            udskriv_felt(
                navn="EASY-status",
                value=easy_status.get("text"),
            )
        else:
            udskriv_felt(
                navn="EASY-statusobjekt",
                value=easy_status,
            )

        # ------------------------------------------
        # Relevansfelter
        # ------------------------------------------
        incident_data_relevance = skade.get(
            "incidentDataRelevance"
        )

        print()
        print("=" * 80)
        print("RELEVANSFELTER")
        print("=" * 80)

        if isinstance(incident_data_relevance, dict):
            relevante_felter = [
                "hasInfringingActsRelevant",
                "hasInfringingActsLightRelevant",
                "hasPrevetiveMeasureRelevant",
                "hasPrevetiveFormRelevant",
                "isTransportDataRelevant",
                "isEasyDataRelevant",
                "isPersonalInjuryRelevant",
            ]

            for feltnavn in relevante_felter:
                value = incident_data_relevance.get(
                    feltnavn
                )

                if (
                    value is not None
                    and not isinstance(value, bool)
                ):
                    raise AssertionError(
                        f"Feltet {feltnavn!r} skal være "
                        "bool eller None. "
                        f"Modtog: {type(value).__name__}."
                    )

                udskriv_felt(
                    navn=feltnavn,
                    value=value,
                )
        else:
            udskriv_felt(
                navn="incidentDataRelevance",
                value=incident_data_relevance,
            )

        # ------------------------------------------
        # Personskade
        # ------------------------------------------
        personal_injury = skade.get(
            "personalInjury"
        )

        print()
        print("=" * 80)
        print("PERSONSKADE")
        print("=" * 80)

        if isinstance(personal_injury, dict):
            udskriv_felt(
                navn="Kropsdel eller område",
                value=hent_tekst(
                    personal_injury.get(
                        "accidentBodyPart"
                    )
                ),
            )
            udskriv_felt(
                navn="Hændelsestype",
                value=hent_tekst(
                    personal_injury.get(
                        "accidentOccurence"
                    )
                ),
            )
            udskriv_felt(
                navn="Tidspunkt",
                value=personal_injury.get(
                    "accidentTime"
                ),
            )
            udskriv_felt(
                navn="Varighed",
                value=hent_tekst(
                    personal_injury.get(
                        "accidentDuration"
                    )
                ),
            )
            udskriv_felt(
                navn="Anmeldelsesstatus",
                value=hent_tekst(
                    personal_injury.get(
                        "accidentClaimStatus"
                    )
                ),
            )
            udskriv_felt(
                navn="Beskrivelse",
                value=personal_injury.get(
                    "accidentText"
                ),
            )
        else:
            udskriv_felt(
                navn="personalInjury",
                value=personal_injury,
            )

        # ------------------------------------------
        # Hele JSON-svaret
        # ------------------------------------------
        print()
        print("=" * 80)
        print("HELE SVARET FRA INSUBIZ")
        print("=" * 80)
        print(
            json.dumps(
                skade,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        print()
        print("=" * 80)
        print("TEST BESTÅET")
        print("=" * 80)

    finally:
        await api_client.close()


# --------------------------------------------------
# Direkte kørsel fra VS Code
# --------------------------------------------------
if __name__ == "__main__":
    asyncio.run(
        test_skade()
    )
