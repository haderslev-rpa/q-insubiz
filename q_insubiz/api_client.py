from __future__ import annotations

import logging
from typing import Any

from automation_server_client import (
    AutomationServer,
    Credential,
)

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.api.client import (
    InsubizApiClient,
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Automation Server
# --------------------------------------------------
CREDENTIAL_NAME = "Q_INSUBIZ"


# --------------------------------------------------
# Standardværdier
# --------------------------------------------------
DEFAULT_HEADLESS = True


# --------------------------------------------------
# Hjælpefunktioner
# --------------------------------------------------
def _normalize_bool(
    value: Any,
    *,
    default: bool,
) -> bool:
    """Konverterer en konfigurationsværdi til bool."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int) and not isinstance(value, bool):
        return value != 0

    if isinstance(value, str):
        normalized_value = value.strip().casefold()

        if normalized_value in {
            "1",
            "true",
            "yes",
            "ja",
            "on",
        }:
            return True

        if normalized_value in {
            "0",
            "false",
            "no",
            "nej",
            "off",
            "",
        }:
            return False

    raise ValueError(
        "Boolean-konfigurationen havde en ugyldig værdi. "
        f"Modtog: {value!r}."
    )


def _initialize_automation_server() -> None:
    """Initialiserer forbindelsen til Automation Server."""
    try:
        AutomationServer.from_environment()
    except Exception as error:
        raise RuntimeError(
            "Forbindelsen til Automation Server "
            "kunne ikke initialiseres."
        ) from error


def _get_credential() -> Credential:
    """Henter Insubiz-credentialen fra Automation Server."""
    _initialize_automation_server()

    try:
        return Credential.get_credential(
            CREDENTIAL_NAME
        )
    except Exception as error:
        raise RuntimeError(
            "Credentialen kunne ikke hentes fra "
            "Automation Server. "
            f"Credential-navn: {CREDENTIAL_NAME}."
        ) from error


def _get_configuration(
    credential: Credential,
) -> dict[str, Any]:
    """Returnerer credentialens Data-konfiguration."""
    configuration = credential.data

    if configuration is None:
        return {}

    if not isinstance(configuration, dict):
        raise RuntimeError(
            "Automation Server-credentialens Data havde "
            "et ugyldigt format. Forventede en dictionary, "
            f"men modtog {type(configuration).__name__}."
        )

    return configuration


def _get_headless_setting(
    *,
    configuration: dict[str, Any],
    headless: bool | None,
) -> bool:
    """Bestemmer om browseren skal køre headless."""
    if headless is not None:
        if not isinstance(headless, bool):
            raise TypeError(
                "headless skal være True, False eller None."
            )

        return headless

    configured_value = configuration.get(
        "headless",
        DEFAULT_HEADLESS,
    )

    return _normalize_bool(
        configured_value,
        default=DEFAULT_HEADLESS,
    )


# --------------------------------------------------
# Public factory
# --------------------------------------------------
def create_api_client(
    *,
    headless: bool | None = None,
) -> InsubizApiClient:
    """
    Opretter en Insubiz API-klient.

    Loginoplysninger håndteres af launch_insubiz() via
    Automation Server-credentialen Q_INSUBIZ. Dette modul
    læser derfor ikke e-mail eller adgangskode og sender
    dem ikke til InsubizAuthManager.

    Hvis headless ikke angives direkte, læses værdien fra
    credentialens Data-felt. Mangler værdien, anvendes
    DEFAULT_HEADLESS.
    """
    credential = _get_credential()
    configuration = _get_configuration(
        credential=credential,
    )
    resolved_headless = _get_headless_setting(
        configuration=configuration,
        headless=headless,
    )

    logger.info(
        "Opretter Insubiz API-klient. "
        "Credential: %s. Headless: %s.",
        CREDENTIAL_NAME,
        resolved_headless,
    )

    auth_manager = InsubizAuthManager(
        headless=resolved_headless,
    )

    return InsubizApiClient(
        auth_manager=auth_manager,
    )


__all__ = [
    "CREDENTIAL_NAME",
    "DEFAULT_HEADLESS",
    "create_api_client",
]
