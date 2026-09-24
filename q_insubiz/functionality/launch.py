from __future__ import annotations

import logging
from typing import Any, Protocol

from automation_server_client import (
    AutomationServer,
    Credential,
)
from playwright.async_api import (
    Locator,
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

NAVIGATION_TIMEOUT_MS = 90_000
NAVIGATION_MAX_FORSOEG = 3
NAVIGATION_RETRY_PAUSE_MS = 3_000

ELEMENT_TIMEOUT_MS = 30_000
LOGIN_TIMEOUT_MS = 60_000
FIELD_PAUSE_MS = 250
LOGIN_PAUSE_MS = 1_000

SCREENSHOT_NAME_PREFIX = "insubiz_playwright_error"


# --------------------------------------------------
# RECORDER-INTERFACE
# --------------------------------------------------


class PlaywrightRecorder(Protocol):
    """Minimalt interface til screenshot og SharePoint-upload."""

    async def screenshot(
        self,
        page: Page,
        name: str,
        always: bool = False,
    ) -> Any:
        """Gemmer et screenshot og forsøger upload til SharePoint."""
        ...


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
# PUBLIC LOGIN
# --------------------------------------------------


async def launch_insubiz(
    page: Page,
    recorder: PlaywrightRecorder | None = None,
) -> None:
    """Åbner Insubiz og logger ind via brugerfladen.

    Credential- og Automation Server-fejl udløser ikke screenshot.
    Screenshot forsøges kun ved fejl i det konkrete Playwright/UI-flow.
    """
    if page is None:
        raise ValueError(
            "page må ikke være None."
        )

    if page.is_closed():
        raise RuntimeError(
            "Insubiz kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    # Ikke en UI- eller Playwright-handling.
    # Fejl her skal derfor ikke udløse screenshot.
    email, password = _get_credentials()

    try:
        await _udfoer_login_via_ui(
            page=page,
            email=email,
            password=password,
        )

    except Exception as error:
        # Kun fejl fra UI/Playwright-flowet kan nå denne fejlgren.
        await _tag_screenshot_ved_playwright_fejl(
            page=page,
            recorder=recorder,
            error=error,
        )

        error_message = await _get_error_message(
            page=page,
        )

        message = _opret_ui_fejlbesked(
            page=page,
            error=error,
            error_message=error_message,
        )

        logger.exception(
            message
        )

        raise RuntimeError(
            message
        ) from error


# --------------------------------------------------
# PLAYWRIGHT/UI-FLOW
# --------------------------------------------------


async def _udfoer_login_via_ui(
    *,
    page: Page,
    email: str,
    password: str,
) -> None:
    """Udfører hele loginflowet gennem Insubiz-brugerfladen."""
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

    await _udfyld_emailfelt(
        page=page,
        email_input=email_input,
        email=email,
    )

    await _udfyld_adgangskodefelt(
        page=page,
        password_input=password_input,
        password=password,
    )

    await _udfoer_loginhandling(
        page=page,
        login_form=login_form,
        password_input=password_input,
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


async def _udfyld_emailfelt(
    *,
    page: Page,
    email_input: Locator,
    email: str,
) -> None:
    """Udfylder og kontrollerer e-mailfeltet via Playwright."""
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
            "korrekt i Insubiz-brugerfladen. "
            f"Forventet længde: {len(email)}. "
            f"Indsat længde: {len(actual_email)}."
        )

    await email_input.press(
        "Tab"
    )

    await page.wait_for_timeout(
        FIELD_PAUSE_MS
    )


async def _udfyld_adgangskodefelt(
    *,
    page: Page,
    password_input: Locator,
    password: str,
) -> None:
    """Udfylder og kontrollerer adgangskodefeltet via Playwright."""
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
            "korrekt i Insubiz-brugerfladen. "
            f"Forventet længde: {len(password)}. "
            f"Indsat længde: {len(actual_password)}."
        )


async def _udfoer_loginhandling(
    *,
    page: Page,
    login_form: Locator,
    password_input: Locator,
) -> None:
    """Klikker på login-knappen eller bruger Enter som fallback."""
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
                "Login-knappen er deaktiveret "
                "efter udfyldning af loginformularen."
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
        return

    logger.warning(
        "Login-knappen blev ikke fundet. "
        "Forsøger login med Enter."
    )

    await password_input.press(
        "Enter"
    )


# --------------------------------------------------
# NAVIGATION MED GENFORSØG
# --------------------------------------------------


async def _aabn_login_med_genforsoeg(
    *,
    page: Page,
) -> None:
    """Åbner Insubiz-login med kontrollerede Playwright-genforsøg."""
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
                    "HTTP-fejl i browseren. "
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
                "Aktuel URL: %s.",
                forsoeg,
                NAVIGATION_MAX_FORSOEG,
                page.url,
            )

            await _stop_eventuel_navigation(
                page=page,
            )

        except RuntimeError as error:
            sidste_fejl = error

            logger.warning(
                "Insubiz-login kunne ikke åbnes i browseren. "
                "Forsøg %s af %s. Fejl: %s",
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
        "Insubiz-login kunne ikke indlæses i browseren "
        f"efter {NAVIGATION_MAX_FORSOEG} forsøg. "
        "Timeout pr. forsøg: "
        f"{NAVIGATION_TIMEOUT_MS // 1_000} sekunder. "
        f"Sidste URL: {page.url}. "
        "Sidste fejl: "
        f"{type(sidste_fejl).__name__}: {sidste_fejl}"
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
            "En hængende browsernavigation kunne "
            "ikke stoppes med window.stop().",
            exc_info=True,
        )


# --------------------------------------------------
# LOGINRESULTAT
# --------------------------------------------------


async def _vent_paa_gennemfoert_login(
    *,
    page: Page,
    email_input: Locator,
) -> None:
    """Venter på, at loginformularen forsvinder fra UI'et."""
    try:
        await email_input.wait_for(
            state="hidden",
            timeout=LOGIN_TIMEOUT_MS,
        )

    except PlaywrightTimeoutError as error:
        error_message = await _get_error_message(
            page=page,
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
            "Timeout: "
            f"{LOGIN_TIMEOUT_MS // 1_000} sekunder."
        )

        raise RuntimeError(
            message
        ) from error

    await page.wait_for_timeout(
        LOGIN_PAUSE_MS
    )


# --------------------------------------------------
# SCREENSHOT KUN VED PLAYWRIGHT/UI-FEJL
# --------------------------------------------------


async def _tag_screenshot_ved_playwright_fejl(
    *,
    page: Page,
    recorder: PlaywrightRecorder | None,
    error: BaseException,
) -> None:
    """Tager screenshot ved fejl i det konkrete Playwright/UI-flow."""
    if recorder is None:
        logger.warning(
            "Screenshot ved Playwright/UI-fejl blev ikke "
            "taget, fordi recorder ikke blev sendt med."
        )
        return

    if page.is_closed():
        logger.warning(
            "Screenshot ved Playwright/UI-fejl blev ikke "
            "taget, fordi Playwright-siden er lukket."
        )
        return

    screenshot_name = (
        f"{SCREENSHOT_NAME_PREFIX}_"
        f"{_normaliser_screenshot_navn(type(error).__name__)}"
    )

    try:
        await recorder.screenshot(
            page=page,
            name=screenshot_name,
            always=True,
        )

        logger.info(
            "Screenshot fra Playwright/UI-fejl blev "
            "gemt lokalt og forsøgt uploadet til SharePoint."
        )

    except Exception:
        # Screenshot eller SharePoint må aldrig skjule UI-fejlen.
        logger.exception(
            "Screenshot eller SharePoint-upload fejlede "
            "under håndtering af en Playwright/UI-fejl."
        )


def _normaliser_screenshot_navn(
    value: str,
) -> str:
    """Normaliserer en tekst til et sikkert screenshotnavn."""
    normalized_value = str(
        value
    ).strip()

    for character in (
        " ",
        "/",
        "\\",
        ":",
        ";",
    ):
        normalized_value = normalized_value.replace(
            character,
            "_",
        )

    return normalized_value or "UkendtFejl"


# --------------------------------------------------
# UI-FEJLBESKED
# --------------------------------------------------


def _opret_ui_fejlbesked(
    *,
    page: Page,
    error: BaseException,
    error_message: str,
) -> str:
    """Opretter en fejlbesked for Playwright/UI-loginflowet."""
    if isinstance(error, PlaywrightTimeoutError):
        message = "Login i Insubiz fik Playwright-timeout."
    else:
        message = "Login via Insubiz-brugerfladen fejlede."

    if error_message:
        message += (
            " Fejlbesked fra Insubiz: "
            f"{error_message}"
        )

    current_url = (
        page.url
        if not page.is_closed()
        else "[siden er lukket]"
    )

    message += (
        f" URL: {current_url}. "
        f"Fejltype: {type(error).__name__}. "
        f"Fejl: {error}"
    )

    return message


# --------------------------------------------------
# SYNLIG UI-FEJLBESKED
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

        error_message = await error_locator.inner_text()

        return error_message.strip()

    except Exception:
        logger.debug(
            "En eventuel UI-fejlbesked kunne ikke "
            "aflæses.",
            exc_info=True,
        )
        return ""


__all__ = [
    "CREDENTIAL_NAME",
    "LOGIN_URL",
    "PlaywrightRecorder",
    "launch_insubiz",
]
