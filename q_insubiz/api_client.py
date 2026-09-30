from __future__ import annotations

"""Factory til en autentificeret Insubiz API-klient.

Modulet bestemmer browserens headless- og debug-indstillinger
og opretter InsubizAuthManager.

Loginoplysninger læses ikke i dette modul. launch_insubiz()
henter loginoplysninger fra Automation Server-credentialen
Q_INSUBIZ.

PlaywrightRunRecorder oprettes ikke af q-insubiz. Recorderen
skal leveres af den kaldende robotproces, som ejer den
BrowserSession, recorderen kræver.

En leveret recorder sendes kun videre, når debug=True.
launch_insubiz() anvender recorderen ved fejl i det konkrete
Playwright/UI-loginflow og kalder screenshot med always=True.
"""

import logging
from typing import Any

from automation_server_client import (
    AutomationServer,
    Credential,
)
from playwright.async_api import APIRequestContext
from q_haderslev_vbo.playwright.playwright_run_recorder import (
    PlaywrightRunRecorder,
)

from q_insubiz.api.auth_manager import (
    InsubizAuthManager,
)
from q_insubiz.api.client import (
    InsubizApiClient,
)
from q_insubiz.api.request_context_auth_manager import (
    RequestContextAuthManager,
)

from playwright.async_api import (
    BrowserContext,
    Page,
)

from q_insubiz.api.existing_context_auth_manager import (
    ExistingContextAuthManager,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# AUTOMATION SERVER
# --------------------------------------------------

CREDENTIAL_NAME = "Q_INSUBIZ"


# --------------------------------------------------
# STANDARDVÆRDIER
# --------------------------------------------------

DEFAULT_HEADLESS = True
DEFAULT_DEBUG = False


# --------------------------------------------------
# BOOL-KONFIGURATION
# --------------------------------------------------


def _normalize_bool(
    value: Any,
    *,
    default: bool,
) -> bool:
    """Konverterer en konfigurationsværdi til bool."""
    if not isinstance(default, bool):
        raise TypeError("default skal være True eller False.")

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
        f"Boolean-konfigurationen havde en ugyldig værdi. Modtog: {value!r}."
    )


# --------------------------------------------------
# AUTOMATION SERVER
# --------------------------------------------------


def _initialize_automation_server() -> None:
    """Initialiserer forbindelsen til Automation Server."""
    try:
        AutomationServer.from_environment()

    except Exception as error:
        raise RuntimeError(
            "Forbindelsen til Automation Server kunne ikke initialiseres."
        ) from error


def _get_credential() -> Credential:
    """Henter Insubiz-credentialen fra Automation Server."""
    _initialize_automation_server()

    try:
        return Credential.get_credential(CREDENTIAL_NAME)

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
        raise TypeError(
            "Automation Server-credentialens Data "
            "havde et ugyldigt format. "
            "Forventede en dictionary, men modtog "
            f"{type(configuration).__name__}."
        )

    return configuration


# --------------------------------------------------
# HEADLESS OG DEBUG
# --------------------------------------------------


def _get_headless_setting(
    *,
    configuration: dict[str, Any],
    headless: bool | None,
) -> bool:
    """Bestemmer om browseren skal køre headless."""
    if not isinstance(configuration, dict):
        raise TypeError("configuration skal være en dictionary.")

    if headless is not None:
        if not isinstance(headless, bool):
            raise TypeError("headless skal være True, False eller None.")

        return headless

    configured_value = configuration.get(
        "headless",
        DEFAULT_HEADLESS,
    )

    return _normalize_bool(
        configured_value,
        default=DEFAULT_HEADLESS,
    )


def _get_debug_setting(
    *,
    configuration: dict[str, Any],
    debug: bool | None,
) -> bool:
    """Bestemmer processens debug-indstilling."""
    if not isinstance(configuration, dict):
        raise TypeError("configuration skal være en dictionary.")

    if debug is not None:
        if not isinstance(debug, bool):
            raise TypeError("debug skal være True, False eller None.")

        return debug

    configured_value = configuration.get(
        "debug",
        DEFAULT_DEBUG,
    )

    return _normalize_bool(
        configured_value,
        default=DEFAULT_DEBUG,
    )


# --------------------------------------------------
# RECORDER
# --------------------------------------------------


def _validate_recorder(
    *,
    recorder: PlaywrightRunRecorder | None,
) -> None:
    """Validerer en eventuelt leveret recorder.

    Der anvendes strukturel validering frem for isinstance, så en
    kompatibel recorder eller test-double kan leveres på tværs af
    installerede pakkeversioner.
    """
    if recorder is None:
        return

    screenshot_method = getattr(
        recorder,
        "screenshot",
        None,
    )

    if not callable(screenshot_method):
        raise TypeError(
            "recorder skal have en callable "
            "screenshot-metode. "
            f"Modtog: {type(recorder).__name__}."
        )


# --------------------------------------------------
# PUBLIC FACTORY
# --------------------------------------------------


def create_api_client(
    *,
    headless: bool | None = None,
    debug: bool | None = None,
    recorder: PlaywrightRunRecorder | None = None,
) -> InsubizApiClient:
    """Opretter en autentificeret Insubiz API-klient.

    Loginoplysninger håndteres af launch_insubiz() via
    Automation Server-credentialen Q_INSUBIZ. Dette modul
    læser derfor ikke e-mail eller adgangskode og sender
    værdierne ikke til InsubizAuthManager.

    Hvis headless ikke angives direkte, læses værdien fra
    credentialens Data-felt. Mangler værdien, anvendes
    DEFAULT_HEADLESS.

    Hvis debug ikke angives direkte, læses værdien fra
    credentialens Data-felt. Mangler værdien, anvendes
    DEFAULT_DEBUG.

    Recorderen oprettes ikke af q-insubiz. Den skal leveres
    af den kaldende robotproces, som ejer BrowserSession.

    En leveret recorder sendes kun videre, når debug=True.
    Når debug=False, sendes recorder=None til auth manageren,
    og der tages derfor ikke screenshots fra loginflowet.
    """
    credential = _get_credential()

    configuration = _get_configuration(
        credential=credential,
    )

    resolved_headless = _get_headless_setting(
        configuration=configuration,
        headless=headless,
    )

    resolved_debug = _get_debug_setting(
        configuration=configuration,
        debug=debug,
    )

    _validate_recorder(
        recorder=recorder,
    )

    resolved_recorder = recorder if resolved_debug else None

    if resolved_debug and resolved_recorder is None:
        logger.warning(
            "Debug er aktiveret, men der blev ikke leveret "
            "en PlaywrightRunRecorder. Der kan derfor ikke "
            "tages screenshot ved Insubiz-loginfejl."
        )

    if not resolved_debug and recorder is not None:
        logger.info(
            "Den leverede PlaywrightRunRecorder anvendes ikke, fordi debug=False."
        )

    logger.info(
        "Opretter Insubiz API-klient. "
        "Credential: %s. "
        "Headless: %s. "
        "Debug: %s. "
        "Recorder aktiv: %s.",
        CREDENTIAL_NAME,
        resolved_headless,
        resolved_debug,
        resolved_recorder is not None,
    )

    auth_manager = InsubizAuthManager(
        headless=resolved_headless,
        recorder=resolved_recorder,
    )

    return InsubizApiClient(
        auth_manager=auth_manager,
    )

def create_api_client_from_context(
    *,
    context: BrowserContext,
    page: Page,
) -> InsubizApiClient:
    """Opretter en API-klient fra en eksisterende browsercontext.

    API-klienten genbruger cookies fra den eksisterende
    Playwright-session og starter ikke en ny browser.
    """
    if context is None:
        raise ValueError(
            "context må ikke være None."
        )

    if page is None:
        raise ValueError(
            "page må ikke være None."
        )

    if page.is_closed():
        raise RuntimeError(
            "API-klienten kunne ikke oprettes, fordi "
            "Playwright-siden er lukket."
        )

    auth_manager = ExistingContextAuthManager(
        context=context,
        page=page,
    )

    logger.info(
        "Opretter Insubiz API-klient fra eksisterende "
        "Playwright-browsercontext."
    )

    return InsubizApiClient(
        auth_manager=auth_manager,
    )

def create_api_client_from_request_context(
    *,
    request_context: APIRequestContext,
) -> InsubizApiClient:
    """Opretter en API-klient på en eksisterende request-context.

    Request-contexten ejes af den kaldende BrowserContext. Factoryen
    starter derfor ikke en ny browser, udfører ikke et ekstra login og
    lukker ikke request-contexten.
    """
    if request_context is None:
        raise TypeError("request_context må ikke være None.")

    auth_manager = RequestContextAuthManager(
        request_context=request_context,
    )

    logger.info("Opretter Insubiz API-klient på en eksisterende APIRequestContext.")

    return InsubizApiClient(
        auth_manager=auth_manager,
    )


__all__ = [
    "CREDENTIAL_NAME",
    "DEFAULT_DEBUG",
    "DEFAULT_HEADLESS",
    "create_api_client",
    "create_api_client_from_context",
]
