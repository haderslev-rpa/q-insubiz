import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.api.client import (
    InsubizApiClient,
)
from q_insubiz.api.koeretoej import (
    KOERETOEJER_LISTE,
)


# --------------------------------------------------
# Testindstillinger
# --------------------------------------------------
ANTAL_RAEKKER_TIL_UDSKRIFT = 100

COLUMNS = [
    "ChassisNumber",
    "ContactPerson1",
    "Registration",
]


def get_headless_setting() -> bool:
    """
    Læser INSUBIZ_HEADLESS fra miljøvariabler.
    """

    return os.getenv(
        "INSUBIZ_HEADLESS",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "ja",
    }


def print_rows(
    rows: list[dict[str, Any]],
    max_rows: int = 100,
) -> None:
    """
    Udskriver op til max_rows køretøjer som JSON.
    """

    rows_to_print = rows[:max_rows]

    print()
    print("=" * 80)
    print(
        f"KØRETØJER, VISER "
        f"{len(rows_to_print)} AF {len(rows)}"
    )
    print("=" * 80)

    if not rows_to_print:
        print("Der blev ikke fundet nogen køretøjer.")
        return

    for row_number, row in enumerate(
        rows_to_print,
        start=1,
    ):
        print()
        print("-" * 80)
        print(
            f"Række {row_number} "
            f"af {len(rows_to_print)}"
        )
        print("-" * 80)

        print(
            json.dumps(
                row,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    print()
    print("=" * 80)
    print(
        f"{len(rows_to_print)} rækker blev udskrevet."
    )
    print(
        f"Samlet antal køretøjer: {len(rows)}"
    )
    print("=" * 80)


async def main() -> None:
    """
    Tester hentning af køretøjslisten fra Insubiz.

    Eksporten behandles direkte i hukommelsen.
    Der bliver ikke gemt en fil.
    """

    load_dotenv()

    email = os.getenv(
        "INSUBIZ_EMAIL",
        "",
    ).strip()

    password = os.getenv(
        "INSUBIZ_PASSWORD",
        "",
    )

    if not email:
        raise RuntimeError(
            "INSUBIZ_EMAIL mangler i .env-filen."
        )

    if not password:
        raise RuntimeError(
            "INSUBIZ_PASSWORD mangler i .env-filen."
        )

    auth_manager = InsubizAuthManager(
        email=email,
        password=password,
        headless=get_headless_setting(),
    )

    api_client = InsubizApiClient(
        auth_manager=auth_manager,
    )

    try:
        result = await KOERETOEJER_LISTE(
            api_client=api_client,
            customer_id=0,
            show_tree_data=False,
            active_only=False,
            columns=COLUMNS,
        )

        if not isinstance(result, list):
            raise RuntimeError(
                "KOERETOEJER_LISTE returnerede et "
                "uventet format. Forventede en liste, "
                f"men modtog {type(result).__name__}."
            )

        for row_number, row in enumerate(
            result,
            start=1,
        ):
            if not isinstance(row, dict):
                raise RuntimeError(
                    "En række havde et uventet format. "
                    f"Række: {row_number}. "
                    "Forventede en dictionary, "
                    f"men modtog {type(row).__name__}."
                )

        print_rows(
            rows=result,
            max_rows=ANTAL_RAEKKER_TIL_UDSKRIFT,
        )

    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())