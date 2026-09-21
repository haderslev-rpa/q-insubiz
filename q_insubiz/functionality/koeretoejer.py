import logging
from typing import Any


from q_insubiz.api.client import (
    InsubizApiClient,
)
from q_insubiz.utils import (
    normalize_columns,
    normalize_positive_id,
    parse_excel_response,
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
GET_VEHICLE_BY_ID_ENDPOINT = (
    "/Vehicle/GetVehicleById"
)

KOERETOEJER_LISTE_ENDPOINT = (
    "/ImportExport/ExportVehicles"
)


# --------------------------------------------------
# Standardkolonner
# --------------------------------------------------
KOERETOEJER_LISTE_COLUMNS = [
    "ChassisNumber",
    "ContactPerson1",
    "Registration",
]


# --------------------------------------------------
# Public funktion: Hent specifikt køretøj
# --------------------------------------------------
async def hent_koeretoej_via_id(
    api_client: InsubizApiClient,
    koeretoej_id: int | str,
) -> dict[str, Any]:
    """
    Henter alle oplysninger om et specifikt køretøj
    via køretøjets interne Insubiz-id.
    """
    normalized_id = normalize_positive_id(
        value=koeretoej_id,
        name="koeretoej_id",
    )

    logger.info(
        "Henter køretøj fra Insubiz. "
        "Køretøjs-id: %s.",
        normalized_id,
    )

    try:
        response = await api_client.get(
            endpoint=GET_VEHICLE_BY_ID_ENDPOINT,
            params={
                "id": normalized_id,
            },
        )
    except Exception as error:
        logger.exception(
            "Køretøjet kunne ikke hentes fra Insubiz. "
            "Køretøjs-id: %s.",
            normalized_id,
        )

        raise RuntimeError(
            "Køretøjet kunne ikke hentes fra Insubiz. "
            f"Køretøjs-id: {normalized_id}."
        ) from error

    koeretoej = _validate_koeretoej_response(
        response=response,
        koeretoej_id=normalized_id,
    )

    logger.info(
        "Køretøjet blev hentet fra Insubiz. "
        "Køretøjs-id: %s. Registrering: %s.",
        normalized_id,
        koeretoej.get("registration", ""),
    )

    return koeretoej


# --------------------------------------------------
# Bagudkompatibelt funktionsnavn
# --------------------------------------------------
async def Koeretoej(
    api_client: InsubizApiClient,
    vehicle_id: int | str,
) -> dict[str, Any]:
    """
    Bagudkompatibelt navn for hent_koeretoej_via_id.

    Nye kald bør bruge hent_koeretoej_via_id.
    """
    return await hent_koeretoej_via_id(
        api_client=api_client,
        koeretoej_id=vehicle_id,
    )


# --------------------------------------------------
# Public funktion: Hent køretøjsliste
# --------------------------------------------------
async def KOERETOEJER_LISTE(
    api_client: InsubizApiClient,
    *,
    customer_id: int = 0,
    show_tree_data: bool = False,
    active_only: bool = False,
    columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Henter en Excel-eksport med køretøjer fra Insubiz.

    Excel-filen behandles direkte i hukommelsen.
    Resultatet returneres som en liste af dictionaries.
    """
    _validate_liste_parameters(
        customer_id=customer_id,
        show_tree_data=show_tree_data,
        active_only=active_only,
    )

    selected_columns = normalize_columns(
        columns=columns,
        default_columns=KOERETOEJER_LISTE_COLUMNS,
    )

    params: dict[str, int | str] = {
        "customerId": customer_id,
        "showTreeData": str(
            show_tree_data
        ).lower(),
        "activeOnly": str(
            active_only
        ).lower(),
    }

    logger.info(
        "Henter køretøjsliste fra Insubiz. "
        "Kunde-id: %s. Kun aktive: %s.",
        customer_id,
        active_only,
    )

    try:
        content, content_type = (
            await api_client.download(
                endpoint=KOERETOEJER_LISTE_ENDPOINT,
                method="POST",
                params=params,
                json_body=selected_columns,
            )
        )
    except Exception as error:
        logger.exception(
            "Køretøjslisten kunne ikke hentes "
            "fra Insubiz."
        )

        raise RuntimeError(
            "Køretøjslisten kunne ikke hentes "
            "fra Insubiz."
        ) from error

    rows = parse_excel_response(
        content=content,
        content_type=content_type,
        resource_name="køretøjseksport",
    )

    logger.info(
        "Køretøjslisten blev hentet fra Insubiz. "
        "Antal rækker: %s.",
        len(rows),
    )

    return rows


# --------------------------------------------------
# Validering af køretøjs-id
# --------------------------------------------------


def _validate_koeretoej_response(
    *,
    response: Any,
    koeretoej_id: int,
) -> dict[str, Any]:
    """Validerer svaret fra GetVehicleById."""
    if response is None:
        raise RuntimeError(
            "Insubiz returnerede intet køretøj. "
            f"Køretøjs-id: {koeretoej_id}."
        )

    if not isinstance(response, dict):
        raise RuntimeError(
            "Insubiz returnerede et uventet format. "
            "Forventede en dictionary, men modtog "
            f"{type(response).__name__}. "
            f"Køretøjs-id: {koeretoej_id}."
        )

    if not response:
        raise RuntimeError(
            "Insubiz returnerede et tomt køretøj. "
            f"Køretøjs-id: {koeretoej_id}."
        )

    response_id = response.get("id")

    if response_id is None:
        raise RuntimeError(
            "Svaret fra Insubiz mangler feltet 'id'. "
            f"Køretøjs-id: {koeretoej_id}."
        )

    try:
        normalized_response_id = int(
            response_id
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "Svaret fra Insubiz indeholder et "
            "ugyldigt køretøjs-id. "
            f"Modtog: {response_id!r}."
        ) from error

    if normalized_response_id != koeretoej_id:
        raise RuntimeError(
            "Insubiz returnerede et andet køretøj "
            "end det forespurgte. "
            f"Forespurgt id: {koeretoej_id}. "
            f"Returneret id: {normalized_response_id}."
        )

    return response


# --------------------------------------------------
# Validering af listeparametre
# --------------------------------------------------
def _validate_liste_parameters(
    *,
    customer_id: int,
    show_tree_data: bool,
    active_only: bool,
) -> None:
    """Validerer parametrene til køretøjseksporten."""
    if (
        not isinstance(customer_id, int)
        or isinstance(customer_id, bool)
    ):
        raise TypeError(
            "customer_id skal være et heltal."
        )

    if customer_id < 0:
        raise ValueError(
            "customer_id må ikke være negativ."
        )

    if not isinstance(show_tree_data, bool):
        raise TypeError(
            "show_tree_data skal være True eller False."
        )

    if not isinstance(active_only, bool):
        raise TypeError(
            "active_only skal være True eller False."
        )

