from __future__ import annotations

import asyncio
import logging
from typing import Any

from automation_server_client import (
    AutomationServer,
    Credential,
)
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from q_insubiz.selectors import InsubizSelectors


logger = logging.getLogger(__name__)


# --------------------------------------------------
# KONFIGURATION
# --------------------------------------------------

LOGIN_URL = "https://start.insubiz.dk/login"
CREDENTIAL_NAME = "Q_INSUBIZ"

# Navigationen fik tidligere kun 30 sekunder.
# Den får nu op til 90 sekunder pr. forsøg.
NAVIGATION_TIMEOUT_MS = 90_000

# Antal kontrollerede navigationsforsøg.
NAVIGATION_MAX_FORSOEG = 3

# Pause mellem navigationsforsøg.
# Pausen multipliceres med forsøgsnummeret.
NAVIGATION_RETRY_PAUSE_MS = 3_000

# Timeout til formularfelter.
ELEMENT_TIMEOUT_MS = 30_000

# Timeout efter klik på login.
LOGIN_TIMEOUT_MS = 60_000

FIELD_PAUSE_MS = 250
LOGIN_PAUSE_MS = 1_000


# --------------------------------------------------
# CREDENTIALS FRA DATA (JSON)
# --------------------------------------------------

def _get_credentials() -> tuple[str, str]:
    """Henter Insubiz-login fra credentialen Q_INSUBIZ."""
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

    data: Any = credential.data

    if not isinstance(data, dict):
        raise RuntimeError(
            "Data (JSON) på credentialen "
            f"{CREDENTIAL_NAME!r} skal være "
            "et JSON-objekt."
        )

    email = str(
        data.get("email")
        or ""
    ).strip()

    password = str(
        data.get("password")
        or ""
    )

    if not email:
        raise RuntimeError(
            "Data (JSON) på credentialen "
            f"{CREDENTIAL_NAME!r} mangler feltet "
            "'email'."
        )

    if not password:
        raise RuntimeError(
            "Data (JSON) på credentialen "
            f"{CREDENTIAL_NAME!r} mangler feltet "
            "'password'."
        )

    logger.info(
        "Insubiz-login blev hentet fra Data (JSON) "
        "på credentialen %s.",
        CREDENTIAL_NAME,
    )

    return email, password


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

async def _aabn_login_med_genforsoeg(
    *,
    page: Page,
) -> None:
    """Åbner Insubiz-login med kontrollerede genforsøg."""
    if page.is_closed():
        raise RuntimeError(
            "Insubiz-login kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    sidste_fejl: Exception | None = None

    for forsoeg in range(
        1,
        NAVIGATION_MAX_FORSOEG + 1,
    ):
        if page.is_closed():
            raise RuntimeError(
                "Playwright-siden blev lukket under "
                "navigationen til Insubiz."
            )

        logger.info(
            "Åbner Insubiz-login. "
            "Forsøg %s af %s. "
            "Timeout: %s sekunder.",
            forsoeg,
            NAVIGATION_MAX_FORSOEG,
            NAVIGATION_TIMEOUT_MS // 1_000,
        )

        try:
            response = await page.goto(
                LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT_MS,
            )

            if page.is_closed():
                raise RuntimeError(
                    "Playwright-siden blev lukket efter "
                    "navigationen til Insubiz."
                )

            http_status = (
                response.status
                if response is not None
                else None
            )

            if (
                http_status is not None
                and http_status >= 400
            ):
                raise RuntimeError(
                    "Insubiz-login returnerede en "
                    "HTTP-fejl. "
                    f"HTTP-status: {http_status}. "
                    f"URL: {page.url}."
                )

            logger.info(
                "Insubiz-login blev indlæst. "
                "Forsøg: %s. "
                "HTTP-status: %r. "
                "URL: %s.",
                forsoeg,
                http_status,
                page.url,
            )

            return

        except PlaywrightTimeoutError as error:
            sidste_fejl = error

            logger.warning(
                "Timeout ved åbning af Insubiz-login. "
                "Forsøg %s af %s. "
                "Timeout: %s sekunder. "
                "Aktuel URL: %s.",
                forsoeg,
                NAVIGATION_MAX_FORSOEG,
                NAVIGATION_TIMEOUT_MS // 1_000,
                page.url,
            )

            await _stop_eventuel_navigation(
                page=page,
            )

        except RuntimeError as error:
            sidste_fejl = error

            logger.warning(
                "Insubiz-login kunne ikke åbnes. "
                "Forsøg %s af %s. "
                "Fejl: %s",
                forsoeg,
                NAVIGATION_MAX_FORSOEG,
                error,
            )

        if forsoeg >= NAVIGATION_MAX_FORSOEG:
            break

        pause_ms = (
            NAVIGATION_RETRY_PAUSE_MS
            * forsoeg
        )

        logger.info(
            "Venter %s sekunder før næste "
            "navigationsforsøg.",
            pause_ms / 1_000,
        )

        await page.wait_for_timeout(
            pause_ms
        )

    raise RuntimeError(
        "Insubiz-login kunne ikke indlæses efter "
        f"{NAVIGATION_MAX_FORSOEG} forsøg. "
        f"Timeout pr. forsøg: "
        f"{NAVIGATION_TIMEOUT_MS // 1_000} sekunder. "
        f"Sidste URL: {page.url}. "
        f"Sidste fejl: "
        f"{type(sidste_fejl).__name__}: "
        f"{sidste_fejl}"
    ) from sidste_fejl


async def _stop_eventuel_navigation(
    *,
    page: Page,
) -> None:
    """Forsøger at stoppe en hængende browsernavigation."""
    if page.is_closed():
        return

    try:
        await page.evaluate(
            "window.stop()"
        )
    except Exception:
        logger.debug(
            "En hængende navigation kunne ikke "
            "stoppes med window.stop().",
            exc_info=True,
        )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

async def launch_insubiz(
    page: Page,
) -> None:
    """Åbner Insubiz og logger ind."""
    if page is None:
        raise ValueError(
            "page må ikke være None."
        )

    if page.is_closed():
        raise RuntimeError(
            "Insubiz kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    email, password = _get_credentials()

    try:
        await _aabn_login_med_genforsoeg(
            page=page,
        )

        email_input = page.locator(
            InsubizSelectors.EMAIL_INPUT
        ).first

        await email_input.wait_for(
            state="visible",
            timeout=ELEMENT_TIMEOUT_MS,
        )

        login_form = email_input.locator(
            "xpath=ancestor::form[1]"
        )

        await login_form.wait_for(
            state="visible",
            timeout=ELEMENT_TIMEOUT_MS,
        )

        password_input = login_form.locator(
            InsubizSelectors.PASSWORD_INPUT
        ).first

        await password_input.wait_for(
            state="visible",
            timeout=ELEMENT_TIMEOUT_MS,
        )

        await email_input.fill(
            email
        )

        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        actual_email = (
            await email_input.input_value()
        ).strip()

        if actual_email != email:
            raise RuntimeError(
                "E-mailadressen blev ikke indsat "
                "korrekt. "
                f"Forventet længde: {len(email)}. "
                f"Indsat længde: "
                f"{len(actual_email)}."
            )

        await email_input.press(
            "Tab"
        )

        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        await password_input.fill(
            password
        )

        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        actual_password = (
            await password_input.input_value()
        )

        if actual_password != password:
            raise RuntimeError(
                "Adgangskoden blev ikke indsat "
                "korrekt. "
                f"Forventet længde: "
                f"{len(password)}. "
                f"Indsat længde: "
                f"{len(actual_password)}."
            )

        login_button = login_form.locator(
            InsubizSelectors.LOGIN_BUTTON
        ).first

        if await login_button.count() > 0:
            await login_button.wait_for(
                state="visible",
                timeout=ELEMENT_TIMEOUT_MS,
            )

            if await login_button.is_disabled():
                error_message = (
                    await _get_error_message(
                        page=page,
                    )
                )

                message = (
                    "Login-knappen er deaktiveret "
                    "efter udfyldning af "
                    "loginformularen."
                )

                if error_message:
                    message += (
                        " Fejlbesked fra Insubiz: "
                        f"{error_message}"
                    )

                raise RuntimeError(
                    message
                )

            await login_button.click()

        else:
            logger.warning(
                "Login-knappen blev ikke fundet. "
                "Forsøger login med Enter."
            )

            await password_input.press(
                "Enter"
            )

        await _vent_paa_gennemfoert_login(
            page=page,
            email_input=email_input,
        )

        logger.info(
            "Login i Insubiz blev gennemført. "
            "URL: %s.",
            page.url,
        )

    except PlaywrightTimeoutError as error:
        error_message = (
            await _get_error_message(
                page=page,
            )
        )

        message = (
            "Login i Insubiz fik timeout efter "
            "navigationen til login-siden."
        )

        if error_message:
            message += (
                " Fejlbesked fra Insubiz: "
                f"{error_message}"
            )

        message += (
            f" URL: {page.url}. "
            f"Element-timeout: "
            f"{ELEMENT_TIMEOUT_MS // 1_000} sekunder. "
            f"Login-timeout: "
            f"{LOGIN_TIMEOUT_MS // 1_000} sekunder."
        )

        logger.exception(
            message
        )

        raise RuntimeError(
            message
        ) from error


async def _vent_paa_gennemfoert_login(
    *,
    page: Page,
    email_input: Any,
) -> None:
    """Venter på at loginformularen forsvinder."""
    try:
        await email_input.wait_for(
            state="hidden",
            timeout=LOGIN_TIMEOUT_MS,
        )

    except PlaywrightTimeoutError as error:
        error_message = (
            await _get_error_message(
                page=page,
            )
        )

        message = (
            "Loginformularen forsvandt ikke efter "
            "loginforsøget."
        )

        if error_message:
            message += (
                " Fejlbesked fra Insubiz: "
                f"{error_message}"
            )

        message += (
            f" URL: {page.url}. "
            f"Timeout: "
            f"{LOGIN_TIMEOUT_MS // 1_000} sekunder."
        )

        raise RuntimeError(
            message
        ) from error

    await page.wait_for_timeout(
        LOGIN_PAUSE_MS
    )


# --------------------------------------------------
# FEJLBESKED
# --------------------------------------------------

async def _get_error_message(
    *,
    page: Page,
) -> str:
    """Finder en synlig fejlbesked på login-siden."""
    if page is None:
        return ""

    if page.is_closed():
        return ""

    error_locator = page.locator(
        InsubizSelectors.LOGIN_ERROR
    ).first

    try:
        if await error_locator.count() == 0:
            return ""

        if not await error_locator.is_visible():
            return ""

        error_message = (
            await error_locator.inner_text()
        )

        return error_message.strip()

    except Exception:
        logger.debug(
            "En eventuel loginfejl kunne ikke "
            "aflæses.",
            exc_info=True,
        )

        return ""


__all__ = [
    "CREDENTIAL_NAME",
    "LOGIN_URL",
    "launch_insubiz",
]