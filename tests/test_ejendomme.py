import asyncio
import os
from typing import Any

from dotenv import load_dotenv

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.api.client import (
    InsubizApiClient,
)

# Ret importen til din konkrete funktion.
from q_insubiz.api.ejendomme import (
    EJENDOMME_LISTE,
)


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
    Udskriver op til max_rows resultater.
    """

    rows_to_print = rows[:max_rows]

    print(
        f"Viser {len(rows_to_print)} "
        f"af {len(rows)} rækker."
    )

    for row_number, row in enumerate(
        rows_to_print,
        start=1,
    ):
        print()
        print(
            f"Række {row_number}:"
        )

        for key, value in row.items():
            print(
                f"  {key}: {value}"
            )


async def main() -> None:
    """
    Tester EJENDOMME_LISTE.

    Login foretages automatisk ved det første API-kald.
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
        # Intet manuelt launch-kald her.
        # API-klienten starter selv browseren og logger ind.
        result = await EJENDOMME_LISTE(
            api_client=api_client,
        )

        if not isinstance(result, list):
            raise RuntimeError(
                "EJENDOMME_LISTE returnerede et "
                "uventet format. Forventede en liste, "
                f"men modtog {type(result).__name__}."
            )

        for row_number, row in enumerate(
            result,
            start=1,
        ):
            if not isinstance(row, dict):
                raise RuntimeError(
                    f"Række {row_number} havde et "
                    "uventet format. Forventede en "
                    "dictionary, men modtog "
                    f"{type(row).__name__}."
                )

        print_rows(
            rows=result,
            max_rows=100,
        )

    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())