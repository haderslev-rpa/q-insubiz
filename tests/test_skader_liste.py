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
    SKADER_LISTE,
)


# --------------------------------------------------
# Testindstillinger
# --------------------------------------------------
HEADLESS = False
ANTAL_SKADER_TIL_UDSKRIFT = 25

CUSTOMER_ID: int | None = None
CUSTOMER_SEGMENTATION_1 = -1
CUSTOMER_SEGMENTATION_2 = -1
CLAIM_GROUP_ID = 0
STATUS_ID = -2
CREATED_YEAR_FROM = 0
CREATED_YEAR_TO = 2026
INCIDENT_YEAR_FROM = 2025
INCIDENT_YEAR_TO = 2026
SHOW_TREE_DATA = False

COLUMNS = [
    "Id",
    "IncidentNumberInternal",
    "IncidentType",
    "IncidentSubType",
    "IncidentStatus",
    "Created",
    "standardCase",
]


# --------------------------------------------------
# Resultatkontrol
# --------------------------------------------------
def kontroller_skader(
    skader: list[dict[str, Any]],
) -> None:
    """Kontrollerer skadelistens overordnede struktur."""
    if not isinstance(skader, list):
        raise AssertionError(
            "SKADER_LISTE returnerede et uventet format. "
            "Forventede en liste, men modtog "
            f"{type(skader).__name__}."
        )

    for row_number, skade in enumerate(
        skader,
        start=1,
    ):
        if not isinstance(skade, dict):
            raise AssertionError(
                "En skade havde et uventet format. "
                f"Række: {row_number}. "
                "Forventede en dictionary, men modtog "
                f"{type(skade).__name__}."
            )

        if not skade:
            raise AssertionError(
                "Skadelisten indeholder en tom række. "
                f"Række: {row_number}."
            )


# --------------------------------------------------
# Udskrift
# --------------------------------------------------
def print_skader(
    skader: list[dict[str, Any]],
    *,
    max_rows: int,
) -> None:
    """Udskriver et begrænset antal skader som JSON."""
    if isinstance(max_rows, bool) or not isinstance(
        max_rows,
        int,
    ):
        raise TypeError(
            "max_rows skal være et heltal."
        )

    if max_rows < 0:
        raise ValueError(
            "max_rows må ikke være negativ."
        )

    skader_til_udskrift = skader[:max_rows]

    print()
    print("=" * 80)
    print(
        "SKADER, VISER "
        f"{len(skader_til_udskrift)} AF {len(skader)}"
    )
    print("=" * 80)

    if not skader_til_udskrift:
        print("Der blev ikke fundet nogen skader.")
        print("=" * 80)
        return

    for row_number, skade in enumerate(
        skader_til_udskrift,
        start=1,
    ):
        print()
        print("-" * 80)
        print(
            f"Skade {row_number} "
            f"af {len(skader_til_udskrift)}"
        )
        print("-" * 80)
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
    print(
        f"{len(skader_til_udskrift)} "
        "skader blev udskrevet."
    )
    print(f"Samlet antal skader: {len(skader)}")
    print("=" * 80)


# --------------------------------------------------
# Integrationstest
# --------------------------------------------------
async def test_skader_liste() -> None:
    """
    Tester SKADER_LISTE fra q_insubiz.functionality.skader.

    Login foretages automatisk ved det første API-kald.
    Excel-eksporten behandles i skader.py og returneres
    til testen som en liste af dictionaries.
    """
    auth_manager = InsubizAuthManager(
        headless=HEADLESS,
    )

    api_client = InsubizApiClient(
        auth_manager=auth_manager,
    )

    try:
        print()
        print("Henter skadeliste fra Insubiz...")

        skader = await SKADER_LISTE(
            api_client=api_client,
            customer_id=CUSTOMER_ID,
            customer_segmentation_1=(
                CUSTOMER_SEGMENTATION_1
            ),
            customer_segmentation_2=(
                CUSTOMER_SEGMENTATION_2
            ),
            claim_group_id=CLAIM_GROUP_ID,
            status_id=STATUS_ID,
            created_year_from=CREATED_YEAR_FROM,
            created_year_to=CREATED_YEAR_TO,
            incident_year_from=INCIDENT_YEAR_FROM,
            incident_year_to=INCIDENT_YEAR_TO,
            show_tree_data=SHOW_TREE_DATA,
            columns=COLUMNS,
        )

        kontroller_skader(
            skader=skader,
        )

        print_skader(
            skader=skader,
            max_rows=ANTAL_SKADER_TIL_UDSKRIFT,
        )

        print()
        print("TEST BESTÅET")

    finally:
        await api_client.close()


# --------------------------------------------------
# Direkte kørsel fra VS Code
# --------------------------------------------------
if __name__ == "__main__":
    asyncio.run(
        test_skader_liste()
    )
