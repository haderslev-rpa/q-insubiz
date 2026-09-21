import logging
from typing import Any

from q_insubiz.api.client import InsubizApiClient
from q_insubiz.utils import (
    normalize_columns,
    normalize_non_negative_int,
    parse_excel_response,
    validate_bool,
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
EJENDOMME_LISTE_ENDPOINT = (
    "/ImportExport/ExportLocations"
)


# --------------------------------------------------
# Standardkolonner
# --------------------------------------------------
EJENDOMME_LISTE_COLUMNS = [
    "Name",
    "Address",
]


# --------------------------------------------------
# Public funktion: Hent ejendomsliste
# --------------------------------------------------
async def EJENDOMME_LISTE(
    api_client: InsubizApiClient,
    *,
    customer_id: int = 0,
    show_tree_data: bool = False,
    active_only: bool = False,
    columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Henter en Excel-eksport med ejendomme fra Insubiz.

    Excel-filen behandles direkte i hukommelsen og
    returneres som en liste af dictionaries.
    """
    normalize_non_negative_int(
        value=customer_id,
        name="customer_id",
    )
    validate_bool(
        value=show_tree_data,
        name="show_tree_data",
    )
    validate_bool(
        value=active_only,
        name="active_only",
    )

    selected_columns = normalize_columns(
        columns=columns,
        default_columns=EJENDOMME_LISTE_COLUMNS,
    )

    params: dict[str, int | str] = {
        "customerId": customer_id,
        "showTreeData": str(show_tree_data).lower(),
        "activeOnly": str(active_only).lower(),
    }

    logger.info(
        "Henter ejendomsliste fra Insubiz. "
        "Kunde-id: %s. Kun aktive: %s.",
        customer_id,
        active_only,
    )

    try:
        content, content_type = await api_client.download(
            endpoint=EJENDOMME_LISTE_ENDPOINT,
            method="POST",
            params=params,
            json_body=selected_columns,
        )
    except Exception as error:
        logger.exception(
            "Ejendomslisten kunne ikke hentes fra Insubiz."
        )
        raise RuntimeError(
            "Ejendomslisten kunne ikke hentes fra Insubiz."
        ) from error

    rows = parse_excel_response(
        content=content,
        content_type=content_type,
        resource_name="ejendomseksport",
    )

    logger.info(
        "Ejendomslisten blev hentet fra Insubiz. "
        "Antal rækker: %s.",
        len(rows),
    )

    return rows


__all__ = [
    "EJENDOMME_LISTE",
    "EJENDOMME_LISTE_COLUMNS",
    "EJENDOMME_LISTE_ENDPOINT",
]
