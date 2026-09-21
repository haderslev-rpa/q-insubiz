from __future__ import annotations

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
# Konfiguration
# --------------------------------------------------
LOGIN_URL = "https://start.insubiz.dk/login"
CREDENTIAL_NAME = "Q_INSUBIZ"

NAVIGATION_TIMEOUT_MS = 30_000
ELEMENT_TIMEOUT_MS = 15_000
LOGIN_TIMEOUT_MS = 30_000
FIELD_PAUSE_MS = 250
LOGIN_PAUSE_MS = 1_000


# --------------------------------------------------
# Credentials fra Data (JSON)
# --------------------------------------------------
def _get_credentials() -> tuple[str, str]:
    """
    Henter Insubiz-login fra Data (JSON) på
    Automation Server-credentialen Q_INSUBIZ.
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

    data: Any = credential.data

    if not isinstance(data, dict):
        raise RuntimeError(
            "Data (JSON) på credentialen "
            f"{CREDENTIAL_NAME!r} skal være "
            "et JSON-objekt."
        )

    email = str(
        data.get("email") or ""
    ).strip()
    password = str(
        data.get("password") or ""
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
# Login
# --------------------------------------------------
async def launch_insubiz(
    page: Page,
) -> None:
    """
    Åbner Insubiz og logger ind.

    E-mail og adgangskode hentes fra Data (JSON)
    på Automation Server-credentialen Q_INSUBIZ.
    """
    if page.is_closed():
        raise RuntimeError(
            "Insubiz kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    email, password = _get_credentials()

    try:
        await page.goto(
            LOGIN_URL,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
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

        await email_input.fill(email)
        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        actual_email = (
            await email_input.input_value()
        ).strip()

        if actual_email != email:
            raise RuntimeError(
                "E-mailadressen blev ikke indsat korrekt. "
                f"Forventet længde: {len(email)}. "
                f"Indsat længde: {len(actual_email)}."
            )

        await email_input.press("Tab")
        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        await password_input.fill(password)
        await page.wait_for_timeout(
            FIELD_PAUSE_MS
        )

        actual_password = (
            await password_input.input_value()
        )

        if actual_password != password:
            raise RuntimeError(
                "Adgangskoden blev ikke indsat korrekt. "
                f"Forventet længde: {len(password)}. "
                f"Indsat længde: {len(actual_password)}."
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
                error_message = await _get_error_message(
                    page=page,
                )

                message = (
                    "Login-knappen er deaktiveret efter "
                    "udfyldning af loginformularen."
                )

                if error_message:
                    message += (
                        " Fejlbesked fra Insubiz: "
                        f"{error_message}"
                    )

                raise RuntimeError(message)

            await login_button.click()
        else:
            logger.warning(
                "Login-knappen blev ikke fundet. "
                "Forsøger login med Enter."
            )
            await password_input.press("Enter")

        await email_input.wait_for(
            state="hidden",
            timeout=LOGIN_TIMEOUT_MS,
        )

        await page.wait_for_timeout(
            LOGIN_PAUSE_MS
        )

        logger.info(
            "Login i Insubiz blev gennemført. URL: %s.",
            page.url,
        )

    except PlaywrightTimeoutError as error:
        error_message = await _get_error_message(
            page=page,
        )

        message = "Login i Insubiz fik timeout."

        if error_message:
            message += (
                " Fejlbesked fra Insubiz: "
                f"{error_message}"
            )

        message += f" URL: {page.url}"

        logger.exception(message)
        raise RuntimeError(message) from error


# --------------------------------------------------
# Fejlbesked
# --------------------------------------------------
async def _get_error_message(
    *,
    page: Page,
) -> str:
    """Finder en synlig fejlbesked på login-siden."""
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
            "En eventuel loginfejl kunne ikke aflæses.",
            exc_info=True,
        )
        return ""


__all__ = [
    "CREDENTIAL_NAME",
    "LOGIN_URL",
    "launch_insubiz",
]
