import logging
from pathlib import Path

from automation_server_client import (
    AutomationServer,
    Credential,
)
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Konfiguration
# --------------------------------------------------
LOGIN_URL = "https://start.insubiz.dk/login"
CREDENTIAL_NAME = "Q_INSUBIZ"

SCREENSHOT_DIRECTORY = Path("screenshots")


# --------------------------------------------------
# Credentials
# --------------------------------------------------
def _get_insubiz_credentials() -> tuple[str, str]:
    """
    Henter og validerer Insubiz-login fra
    Automation Server.
    """
    try:
        AutomationServer.from_environment()
    except Exception as error:
        logger.exception(
            "Forbindelsen til Automation Server "
            "kunne ikke initialiseres."
        )

        raise RuntimeError(
            "Forbindelsen til Automation Server "
            "kunne ikke initialiseres."
        ) from error

    try:
        credential = Credential.get_credential(
            CREDENTIAL_NAME
        )
    except Exception as error:
        logger.exception(
            "Credentialen %s kunne ikke hentes fra "
            "Automation Server.",
            CREDENTIAL_NAME,
        )

        raise RuntimeError(
            "Insubiz-credentialen kunne ikke hentes "
            "fra Automation Server. "
            f"Credential-navn: {CREDENTIAL_NAME}."
        ) from error

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
            "Brugernavnet skal indeholde "
            "Insubiz-e-mailadressen."
        )

    if not password:
        raise RuntimeError(
            "Automation Server-credentialen "
            f"{CREDENTIAL_NAME!r} mangler en adgangskode."
        )

    return email, password


# --------------------------------------------------
# Login
# --------------------------------------------------
async def launch_insubiz(
    page: Page,
) -> None:
    """
    Åbner Insubiz og logger ind med credentials
    fra Automation Server.
    """
    if page.is_closed():
        raise RuntimeError(
            "Insubiz kunne ikke åbnes, fordi "
            "Playwright-siden er lukket."
        )

    email, password = _get_insubiz_credentials()

    logger.info(
        "Åbner Insubiz-login med credentialen %s.",
        CREDENTIAL_NAME,
    )

    try:
        await page.goto(
            LOGIN_URL,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            page=page,
            filename="fejl_navigation_login.png",
        )

        logger.exception(
            "Navigation til Insubiz-login fik timeout."
        )

        raise RuntimeError(
            "Insubiz-login kunne ikke åbnes inden for "
            "30 sekunder. "
            f"URL: {page.url}"
        ) from error

    if page.is_closed():
        raise RuntimeError(
            "Playwright-siden blev lukket under "
            "navigationen til Insubiz."
        )

    email_input = page.locator(
        'input[type="email"]'
        '[autocomplete="username"]:visible'
    ).first

    try:
        await email_input.wait_for(
            state="visible",
            timeout=15_000,
        )
    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            page=page,
            filename="fejl_emailfelt_mangler.png",
        )

        logger.exception(
            "Det synlige e-mailfelt blev ikke fundet."
        )

        raise RuntimeError(
            "E-mailfeltet blev ikke fundet på "
            "Insubiz-login-siden. "
            f"URL: {page.url}"
        ) from error

    login_form = email_input.locator(
        "xpath=ancestor::form[1]"
    )

    try:
        await login_form.wait_for(
            state="visible",
            timeout=15_000,
        )
    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            page=page,
            filename="fejl_loginformular_mangler.png",
        )

        logger.exception(
            "Loginformularen blev ikke fundet."
        )

        raise RuntimeError(
            "Loginformularen blev ikke fundet på "
            "Insubiz-login-siden. "
            f"URL: {page.url}"
        ) from error

    password_input = login_form.locator(
        'input[type="password"]'
        '[autocomplete="current-password"]'
    ).first

    try:
        await password_input.wait_for(
            state="visible",
            timeout=15_000,
        )
    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            page=page,
            filename="fejl_adgangskodefelt_mangler.png",
        )

        logger.exception(
            "Det synlige adgangskodefelt blev ikke fundet."
        )

        raise RuntimeError(
            "Adgangskodefeltet blev ikke fundet på "
            "Insubiz-login-siden. "
            f"URL: {page.url}"
        ) from error

    try:
        await email_input.fill(email)
        await password_input.fill(password)
    except Exception as error:
        await _take_screenshot(
            page=page,
            filename="fejl_udfyldning_login.png",
        )

        logger.exception(
            "Loginfelterne kunne ikke udfyldes."
        )

        raise RuntimeError(
            "Loginoplysningerne kunne ikke udfyldes "
            "på Insubiz-login-siden. "
            f"URL: {page.url}"
        ) from error

    logger.info(
        "Loginoplysninger er udfyldt. "
        "Sender Insubiz-loginformularen."
    )

    try:
        await password_input.press("Enter")
    except Exception as error:
        await _take_screenshot(
            page=page,
            filename="fejl_afsendelse_login.png",
        )

        logger.exception(
            "Insubiz-loginformularen kunne ikke sendes."
        )

        raise RuntimeError(
            "Insubiz-loginformularen kunne ikke sendes. "
            f"URL: {page.url}"
        ) from error

    try:
        await email_input.wait_for(
            state="hidden",
            timeout=30_000,
        )
    except PlaywrightTimeoutError as error:
        await _take_screenshot(
            page=page,
            filename="fejl_login.png",
        )

        error_message = await _get_error_message(
            page=page,
        )

        message = (
            "Login i Insubiz blev ikke gennemført "
            "inden for 30 sekunder."
        )

        if error_message:
            message += (
                f" Fejlbesked fra Insubiz: "
                f"{error_message}"
            )

        message += f" URL: {page.url}"

        logger.error(message)

        raise RuntimeError(message) from error

    await page.wait_for_timeout(2_000)

    logger.info(
        "Login i Insubiz blev gennemført. URL: %s",
        page.url,
    )


# --------------------------------------------------
# Fejlbesked
# --------------------------------------------------
async def _get_error_message(
    page: Page,
) -> str:
    """
    Finder en synlig fejlbesked på login-siden.
    """
    if page.is_closed():
        return ""

    error_locator = page.locator(
        ".v-messages__message:visible, "
        '[role="alert"]:visible, '
        ".v-alert:visible"
    ).first

    try:
        if await error_locator.count() == 0:
            return ""

        error_message = await error_locator.inner_text()

        return error_message.strip()
    except Exception:
        logger.debug(
            "En eventuel fejlbesked fra Insubiz "
        )