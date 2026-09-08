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
    """
    Konverterer en konfigurationsværdi til bool.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        normalized_value = value.strip().lower()

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


def _get_credential() -> Credential:
    """
    Henter Insubiz-credentialen fra Automation Server.
    """
    try:
        AutomationServer.from_environment()
    except Exception as error:
        raise RuntimeError(
            "Forbindelsen til Automation Server "
            "kunne ikke initialiseres."
        ) from error

    try:
        credential = Credential.get_credential(
            CREDENTIAL_NAME
        )
    except Exception as error:
        raise RuntimeError(
            "Credentialen kunne ikke hentes fra "
            "Automation Server. "
            f"Credential-navn: {CREDENTIAL_NAME}."
        ) from error

    return credential


def _get_login_information(
    credential: Credential,
) -> tuple[str, str]:
    """
    Læser og validerer e-mail og adgangskode.
    """
    email = str(
        credential.username or ""
    ).strip()

    password = str(
        credential.password or ""
    )

    if not email:
        raise RuntimeError(
            "Automation Server-credentialen "
            f"{CREDENTIAL_NAME!r} mangler et brugernavn. "
            "Brugernavnet skal indeholde Insubiz-e-mailen."
        )

    if not password:
        raise RuntimeError(
            "Automation Server-credentialen "
            f"{CREDENTIAL_NAME!r} mangler en adgangskode."
        )

    return email, password


def _get_configuration(
    credential: Credential,
) -> dict[str, Any]:
    """
    Returnerer credentialens konfigurationsdata.
    """
    configuration = credential.data

    if configuration is None:
        return {}

    if not isinstance(configuration, dict):
        raise RuntimeError(
            "Automation Server-credentialens data "
            "havde et ugyldigt format. "
            "Forventede en dictionary, "
            f"men modtog {type(configuration).__name__}."
        )

    return configuration


def _get_headless_setting(
    configuration: dict[str, Any],
    headless: bool | None,
) -> bool:
    """
    Bestemmer om browseren skal køre headless.
    """
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

    Loginoplysninger hentes fra Automation Server-
    credentialen Q_INSUBIZ.

    Browser-login foretages automatisk ved det første
    API-kald.
    """
    credential = _get_credential()

    email, password = _get_login_information(
        credential=credential,
    )

    configuration = _get_configuration(
        credential=credential,
    )

    resolved_headless = _get_headless_setting(
        configuration=configuration,
        headless=headless,
    )

    logger.info(
        "Opretter Insubiz API-klient med credentialen %s. "
        "Headless: %s.",
        CREDENTIAL_NAME,
        resolved_headless,
    )

    auth_manager = InsubizAuthManager(
        email=email,
        password=password,
        headless=resolved_headless,
    )

    return InsubizApiClient(
        auth_manager=auth_manager,
    )