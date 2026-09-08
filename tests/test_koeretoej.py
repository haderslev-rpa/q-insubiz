import asyncio
import json
import os

from dotenv import load_dotenv

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)

from q_insubiz.api.client import (
    InsubizApiClient,
)

from q_insubiz.api.koeretoej import (
    Koeretoej,
)


async def main() -> None:
    load_dotenv()

    email = os.getenv(
        "INSUBIZ_EMAIL",
        "",
    ).strip()

    password = os.getenv(
        "INSUBIZ_PASSWORD",
        "",
    )

    vehicle_id = os.getenv(
        "INSUBIZ_TEST_VEHICLE_ID",
        "11115134",
    ).strip()

    if not email or not password:
        raise RuntimeError(
            "INSUBIZ_EMAIL og INSUBIZ_PASSWORD "
            "mangler i .env-filen."
        )

    auth_manager = InsubizAuthManager(
        email=email,
        password=password,
        headless=False,
    )

    api_client = InsubizApiClient(
        auth_manager=auth_manager,
    )

    try:
        result = await Koeretoej(
            api_client=api_client,
            vehicle_id=vehicle_id,
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())