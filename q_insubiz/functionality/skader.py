from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from playwright.async_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from q_insubiz.api.client import InsubizApiClient
from q_insubiz.models import (
    SendSkadeTilEasyResultat,
    SkadeStatus,
)
from q_insubiz.selectors import SkadeSelectors
from q_insubiz.utils import (
    normalize_columns,
    parse_excel_response,
)


logger = logging.getLogger(__name__)

TIMEOUT_MS = 15_000
UI_WAIT_MS = 1_500

SKADER_LISTE_ENDPOINT = "/ImportExport/ExportIncidents"
GET_INCIDENT_BY_ID_ENDPOINT = "/IncidentHandling/GetIncidentById"
UPDATE_INCIDENT_FIELDS_ENDPOINT = "/IncidentHandling/UpdateIncidentFields"
VALIDATE_INCIDENT_FOR_SEND_TO_EASY_ENDPOINT = (
    "/IncidentHandling/ValidateIncidentForSendToEasy"
)
SEND_INCIDENT_TO_EASY_ENDPOINT = "/IncidentHandling/SendIncidentToEasy"





EASY_STATUS_GODKENDT = "Godkendt hos EASY"
EASY_STATUS_AFSENDT_AFVENTER = "Afsendt til EASY, afventer"
EASY_STATUS_ALLEREDE_SENDT = frozenset(
    {
        " ".join(EASY_STATUS_GODKENDT.split()).casefold(),
        " ".join(EASY_STATUS_AFSENDT_AFVENTER.split()).casefold(),
    }
)

SKADER_LISTE_COLUMNS = [
    "Id",
    "IncidentNumberInternal",
    "IncidentType",
    "IncidentSubType",
    "IncidentStatus",
    "Created",
    "standardCase",
]


async def SKADER_LISTE(
    api_client: InsubizApiClient,
    *,
    customer_id: int | None = None,
    customer_segmentation_1: int = -1,
    customer_segmentation_2: int = -1,
    claim_group_id: int = 0,
    status_id: int = -2,
    created_year_from: int = 0,
    created_year_to: int = 2026,
    incident_year_from: int = 2025,
    incident_year_to: int = 2026,
    show_tree_data: bool = False,
    columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Henter skader som en liste af dictionaries."""
    _validate_list_parameters(
        customer_id=customer_id,
        customer_segmentation_1=customer_segmentation_1,
        customer_segmentation_2=customer_segmentation_2,
        claim_group_id=claim_group_id,
        status_id=status_id,
        created_year_from=created_year_from,
        created_year_to=created_year_to,
        incident_year_from=incident_year_from,
        incident_year_to=incident_year_to,
        show_tree_data=show_tree_data,
    )
    selected_columns = normalize_columns(
        columns=columns,
        default_columns=SKADER_LISTE_COLUMNS,
    )
    params: dict[str, str | int] = {
        "customerId": "null" if customer_id is None else customer_id,
        "customersegmentation1": customer_segmentation_1,
        "customersegmentation2": customer_segmentation_2,
        "claimGroupId": claim_group_id,
        "statusId": status_id,
        "createdYearFrom": created_year_from,
        "createdYearTo": created_year_to,
        "incidentYearFrom": incident_year_from,
        "incidentYearTo": incident_year_to,
        "showTreeData": str(show_tree_data).lower(),
    }
    try:
        content, content_type = await api_client.download(
            endpoint=SKADER_LISTE_ENDPOINT,
            method="POST",
            params=params,
            json_body=selected_columns,
        )
    except Exception as error:
        logger.exception("Skadelisten kunne ikke hentes fra Insubiz.")
        raise RuntimeError(
            "Skadelisten kunne ikke hentes fra Insubiz."
        ) from error

    rows = parse_excel_response(
        content=content,
        content_type=content_type,
        resource_name="skadeeksport",
    )
    logger.info("Skadelisten blev hentet. Antal rækker: %s.", len(rows))
    return rows


async def hent_skade_via_id(
    api_client: InsubizApiClient,
    skade_id: int | str,
) -> dict[str, Any]:
    """Henter en skade via det interne Insubiz-id."""
    normalized_skade_id = _normalize_skade_id(skade_id)
    try:
        response = await api_client.get(
            endpoint=GET_INCIDENT_BY_ID_ENDPOINT,
            params={"id": normalized_skade_id},
        )
    except Exception as error:
        logger.exception(
            "Skaden kunne ikke hentes. Skade-id: %s.",
            normalized_skade_id,
        )
        raise RuntimeError(
            "Skaden kunne ikke hentes fra Insubiz. "
            f"Skade-id: {normalized_skade_id}."
        ) from error

    if not isinstance(response, dict):
        raise RuntimeError(
            "GetIncidentById returnerede et uventet "
            f"format: {type(response).__name__}."
        )
    if not response:
        raise RuntimeError(
            "GetIncidentById returnerede et tomt svar. "
            f"Skade-id: {normalized_skade_id}."
        )
    return response


async def opdater_skade_status(
    api_client: InsubizApiClient,
    *,
    skade_id: int | str,
    last_editing: str,
    status: SkadeStatus | int,
) -> Any:
    """Opdaterer skadestatus med en kendt lastEditing."""
    normalized_skade_id = _normalize_skade_id(skade_id)
    normalized_last_editing = _normalize_last_editing(
        last_editing=last_editing
    )
    normalized_status = _normalize_skade_status(status=status)
    payload = {
        "recordId": normalized_skade_id,
        "lastEditing": normalized_last_editing,
        "Fields": [
            {"name": "status.id", "value": int(normalized_status)}
        ],
    }
    try:
        return await api_client.post(
            endpoint=UPDATE_INCIDENT_FIELDS_ENDPOINT,
            json_body=payload,
        )
    except Exception as error:
        logger.exception(
            "Skadestatus kunne ikke opdateres. Skade-id: %s. Status-id: %s.",
            normalized_skade_id,
            int(normalized_status),
        )
        raise RuntimeError(
            "Skadestatus kunne ikke opdateres. "
            f"Skade-id: {normalized_skade_id}."
        ) from error


async def opdater_skade_status_fra_seneste_data(
    api_client: InsubizApiClient,
    *,
    skade_id: int | str,
    status: SkadeStatus | int,
) -> Any:
    """Henter seneste lastEditing og opdaterer status."""
    skade = await hent_skade_via_id(
        api_client=api_client,
        skade_id=skade_id,
    )
    last_editing = skade.get("lastEditing")
    if not isinstance(last_editing, str) or not last_editing.strip():
        raise RuntimeError(
            "Skadesvaret mangler en gyldig lastEditing."
        )
    return await opdater_skade_status(
        api_client=api_client,
        skade_id=skade_id,
        last_editing=last_editing,
        status=status,
    )


async def send_skade_til_easy(
    api_client: InsubizApiClient,
    skade_id: int | str,
) -> SendSkadeTilEasyResultat:
    """Validerer skaden og sender den til EASY, hvis det er nødvendigt.

    Flowet følger Insubiz-brugerfladen:

    1. Hent skaden og kontrollér EASY-status.
    2. Kald ValidateIncidentForSendToEasy.
    3. Kald SendIncidentToEasy, hvis valideringen accepteres.
    4. Hent skaden igen og kontrollér EASY-status/reference.

    En serverfejl accepteres kun som gennemført afsendelse, hvis den
    efterfølgende kontrol viser en sendt EASY-status eller en reference.
    """
    normalized_skade_id = _normalize_skade_id(skade_id)

    incident_foer = await hent_skade_via_id(
        api_client=api_client,
        skade_id=normalized_skade_id,
    )
    easy_status_foer = _extract_easy_status_text(
        incident=incident_foer,
    )
    easy_reference_foer = _extract_easy_reference(
        incident=incident_foer,
    )

    logger.info(
        "Kontrollerer EASY-status før validering og afsendelse. "
        "Skade-id: %s. EASY-status: %r. "
        "EASY-reference fundet: %s.",
        normalized_skade_id,
        easy_status_foer,
        bool(easy_reference_foer),
    )

    if _er_allerede_sendt_til_easy(
        easy_status=easy_status_foer,
    ):
        return SendSkadeTilEasyResultat(
            skade_id=normalized_skade_id,
            easy_status_foer=easy_status_foer,
            easy_reference=easy_reference_foer,
            allerede_sendt=True,
            sendt_nu=False,
            besked=(
                "Skaden er allerede sendt til EASY. "
                f"Aktuel EASY-status: {easy_status_foer}."
            ),
            afsendelses_response=None,
        )

    validation_response = await valider_skade_foer_easy(
        api_client=api_client,
        skade_id=normalized_skade_id,
    )

    logger.info(
        "EASY-valideringen blev accepteret. "
        "Skade-id: %s. Response: %r.",
        normalized_skade_id,
        validation_response,
    )

    try:
        response = await api_client.get(
            endpoint=SEND_INCIDENT_TO_EASY_ENDPOINT,
            params={
                "id": normalized_skade_id,
            },
        )
    except Exception as send_error:
        return await _haandter_easy_sendefejl(
            api_client=api_client,
            skade_id=normalized_skade_id,
            easy_status_foer=easy_status_foer,
            easy_reference_foer=easy_reference_foer,
            validation_response=validation_response,
            send_error=send_error,
        )

    normalized_response = _normalize_send_response(
        response=response,
    )
    _validate_send_response(
        response=normalized_response,
        skade_id=normalized_skade_id,
    )

    incident_efter = await hent_skade_via_id(
        api_client=api_client,
        skade_id=normalized_skade_id,
    )
    easy_status_efter = _extract_easy_status_text(
        incident=incident_efter,
    )
    easy_reference_efter = _extract_easy_reference(
        incident=incident_efter,
    )

    if not (
        _er_allerede_sendt_til_easy(
            easy_status=easy_status_efter,
        )
        or bool(easy_reference_efter)
    ):
        raise RuntimeError(
            "SendIncidentToEasy returnerede uden fejl, men "
            "efterkontrollen viser ingen sendt status eller "
            "EASY-reference. "
            f"Skade-id: {normalized_skade_id}. "
            f"EASY-status før: {easy_status_foer!r}. "
            f"EASY-status efter: {easy_status_efter!r}. "
            f"EASY-reference efter: {easy_reference_efter!r}."
        )

    return SendSkadeTilEasyResultat(
        skade_id=normalized_skade_id,
        easy_status_foer=easy_status_foer,
        easy_reference=(
            easy_reference_efter
            or easy_reference_foer
        ),
        allerede_sendt=False,
        sendt_nu=True,
        besked=(
            "SendIncidentToEasy blev gennemført. "
            f"EASY-status efter: {easy_status_efter!r}."
        ),
        afsendelses_response=normalized_response,
    )


async def valider_skade_foer_easy(
    api_client: InsubizApiClient,
    skade_id: int | str,
) -> dict[str, Any]:
    """Kalder Insubiz-valideringen før EASY-afsendelse."""
    normalized_skade_id = _normalize_skade_id(skade_id)

    try:
        response = await api_client.get(
            endpoint=VALIDATE_INCIDENT_FOR_SEND_TO_EASY_ENDPOINT,
            params={
                "id": normalized_skade_id,
            },
        )
    except Exception as error:
        logger.exception(
            "EASY-valideringen fejlede. Skade-id: %s.",
            normalized_skade_id,
        )
        raise RuntimeError(
            "Skaden kunne ikke valideres før EASY-afsendelse. "
            f"Skade-id: {normalized_skade_id}. "
            f"Underliggende fejl: {type(error).__name__}: {error}"
        ) from error

    normalized_response = _normalize_easy_validation_response(
        response=response,
    )
    _validate_easy_validation_response(
        response=normalized_response,
        skade_id=normalized_skade_id,
    )
    return normalized_response


async def _haandter_easy_sendefejl(
    *,
    api_client: InsubizApiClient,
    skade_id: int,
    easy_status_foer: str,
    easy_reference_foer: str,
    validation_response: dict[str, Any],
    send_error: Exception,
) -> SendSkadeTilEasyResultat:
    """Efterkontrollerer skaden efter et mislykket EASY-sendekald."""
    logger.exception(
        "Afsendelse til EASY fejlede. Efterkontrollerer skaden. "
        "Skade-id: %s. EASY-status før: %r.",
        skade_id,
        easy_status_foer,
        exc_info=send_error,
    )

    try:
        incident_efter = await hent_skade_via_id(
            api_client=api_client,
            skade_id=skade_id,
        )
    except Exception as kontrol_error:
        raise RuntimeError(
            "Skaden kunne ikke sendes til EASY, og efterkontrollen "
            "kunne ikke hente skaden. "
            f"Skade-id: {skade_id}. "
            f"Valideringsresponse: {validation_response!r}. "
            f"Sendefejl: {type(send_error).__name__}: {send_error}. "
            "Efterkontrolfejl: "
            f"{type(kontrol_error).__name__}: {kontrol_error}"
        ) from send_error

    easy_status_efter = _extract_easy_status_text(
        incident=incident_efter,
    )
    easy_reference_efter = _extract_easy_reference(
        incident=incident_efter,
    )

    logger.info(
        "EASY-efterkontrol udført. Skade-id: %s. "
        "EASY-status før: %r. EASY-status efter: %r. "
        "EASY-reference efter fundet: %s.",
        skade_id,
        easy_status_foer,
        easy_status_efter,
        bool(easy_reference_efter),
    )

    if (
        _er_allerede_sendt_til_easy(
            easy_status=easy_status_efter,
        )
        or bool(easy_reference_efter)
    ):
        return SendSkadeTilEasyResultat(
            skade_id=skade_id,
            easy_status_foer=easy_status_foer,
            easy_reference=easy_reference_efter,
            allerede_sendt=False,
            sendt_nu=True,
            besked=(
                "Sendekaldet returnerede en fejl, men efterkontrollen "
                "viser, at skaden blev sendt til EASY. "
                f"EASY-status efter: {easy_status_efter!r}."
            ),
            afsendelses_response={
                "statusCode": None,
                "value": True,
                "text": (
                    "Efterkontrollen bekræftede EASY-afsendelsen "
                    "efter en serverfejl."
                ),
                "validationResponse": validation_response,
                "sendError": (
                    f"{type(send_error).__name__}: {send_error}"
                ),
            },
        )

    raise RuntimeError(
        "Skaden kunne ikke sendes til EASY, og efterkontrollen "
        "viser ingen sendt status eller EASY-reference. "
        f"Skade-id: {skade_id}. "
        f"EASY-status før: {easy_status_foer!r}. "
        f"EASY-status efter: {easy_status_efter!r}. "
        f"EASY-reference før: {easy_reference_foer!r}. "
        f"EASY-reference efter: {easy_reference_efter!r}. "
        f"Valideringsresponse: {validation_response!r}. "
        "Underliggende fejl: "
        f"{type(send_error).__name__}: {send_error}"
    ) from send_error


async def klik_paa_skade(page: Page) -> None:
    """Åbner Skade med kontrollerede fallbacks."""
    if page.is_closed():
        raise RuntimeError(
            "Skade kunne ikke åbnes, fordi siden er lukket."
        )

    skade_link = page.locator(
        SkadeSelectors.SKADE_MENU
    ).filter(has_text="Skade").first

    if await skade_link.count() == 0:
        skade_link = page.get_by_role(
            "link",
            name="Skade",
            exact=True,
        ).first

    await skade_link.wait_for(state="visible", timeout=TIMEOUT_MS)
    await skade_link.scroll_into_view_if_needed()
    try:
        await skade_link.click(timeout=5_000)
    except PlaywrightTimeoutError:
        await skade_link.click(force=True, timeout=5_000)

    await page.wait_for_timeout(UI_WAIT_MS)
    if "/incident/" not in page.url:
        await skade_link.evaluate("element => element.click()")
        await page.wait_for_timeout(UI_WAIT_MS)
    if "/incident/" not in page.url:
        href = await skade_link.get_attribute("href")
        await page.goto(
            f"https://start.insubiz.dk{href or '/incident/'}",
            wait_until="domcontentloaded",
            timeout=30_000,
        )

    await page.wait_for_url("**/incident/**", timeout=30_000)
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(UI_WAIT_MS)


async def opret_dokument_fra_skabelon(page: Page) -> Locator:
    """Åbner og returnerer dokumentdialogen."""
    button = page.locator(
        SkadeSelectors.aabn_dokumentdialog
    ).first
    await button.wait_for(state="visible", timeout=TIMEOUT_MS)
    if not await button.is_enabled():
        raise RuntimeError(
            "Knappen Opret dokument fra skabelon er ikke aktiveret."
        )
    await button.scroll_into_view_if_needed()
    await button.click()

    title = page.locator(
        SkadeSelectors.DOKUMENT_DIALOG_TITEL
    ).last
    await title.wait_for(state="visible", timeout=TIMEOUT_MS)
    dialog = title.locator(
        "xpath=ancestor::*[contains(@class, 'v-overlay__content')][1]"
    )
    await dialog.wait_for(state="visible", timeout=TIMEOUT_MS)

    dropdown = dialog.locator(
        SkadeSelectors.SKABELON_DROPDOWN
    ).first
    await dropdown.wait_for(state="visible", timeout=TIMEOUT_MS)
    await page.wait_for_timeout(UI_WAIT_MS)
    return dialog


async def vaelg_dokumentskabelon(
    page: Page,
    dialog: Locator,
    skabelon_navn: str,
) -> str:
    """Vælger og returnerer en dokumentskabelon."""
    normalized_name = _normalize_required_text(
        name="skabelon_navn",
        value=skabelon_navn,
    )
    dropdown = dialog.locator(
        SkadeSelectors.SKABELON_DROPDOWN
    ).first
    await dropdown.wait_for(state="visible", timeout=TIMEOUT_MS)
    await dropdown.click(force=True)
    try:
        await page.wait_for_function(
            "element => element.getAttribute('aria-expanded') === 'true'",
            arg=await dropdown.element_handle(),
            timeout=5_000,
        )
    except PlaywrightTimeoutError:
        await dropdown.focus()
        await dropdown.press("ArrowDown")

    await page.wait_for_timeout(UI_WAIT_MS)
    exact_name = re.compile(
        rf"^\s*{re.escape(normalized_name)}\s*$",
        re.IGNORECASE,
    )
    option = page.locator(
        SkadeSelectors.SKABELON_VALG
    ).filter(has_text=exact_name).last
    await option.wait_for(state="visible", timeout=TIMEOUT_MS)
    await option.scroll_into_view_if_needed()
    await option.click()
    await page.wait_for_timeout(UI_WAIT_MS)

    selection = dialog.locator(
        SkadeSelectors.VALGT_SKABELON
    ).first
    await selection.wait_for(state="visible", timeout=TIMEOUT_MS)
    selected_text = (await selection.inner_text()).strip()
    if normalized_name.casefold() not in selected_text.casefold():
        raise AssertionError(
            "Skabelonen blev ikke valgt korrekt. "
            f"Forventede: {normalized_name!r}. "
            f"Valgt: {selected_text!r}."
        )
    return selected_text


async def gem_dokument_fra_skabelon(
    page: Page,
    dialog: Locator,
) -> None:
    """Gemmer dokumentet og venter på lukket dialog."""
    gem_knap = dialog.locator(
        SkadeSelectors.GEM_DOKUMENT_KNAP
    ).first
    await gem_knap.wait_for(state="visible", timeout=TIMEOUT_MS)
    if not await gem_knap.is_enabled():
        raise RuntimeError("Knappen Gem er ikke aktiveret.")
    await gem_knap.click()
    await dialog.wait_for(state="hidden", timeout=30_000)
    await page.wait_for_timeout(UI_WAIT_MS)


async def download_easy_rapport_og_gem_i_mappe(page: Page) -> None:
    """Opretter Easy-rapport og gemmer den i mappen."""
    tre_prik_knapper = page.locator(
        SkadeSelectors.TRE_PRIK_MENU_KNAP
    )
    download_rapport: Locator | None = None

    for index in range(await tre_prik_knapper.count() - 1, -1, -1):
        button = tre_prik_knapper.nth(index)
        menu_id = await button.get_attribute("aria-controls")
        try:
            await button.scroll_into_view_if_needed()
            await button.evaluate("element => element.click()")
            await page.wait_for_timeout(UI_WAIT_MS)
            menu = (
                page.locator(f"#{menu_id}")
                if menu_id
                else page.locator(
                    SkadeSelectors.AABEN_MENU
                )
                .filter(has_text="Download rapport")
                .last
            )
            await menu.wait_for(state="visible", timeout=3_000)
            candidate = menu.get_by_text(
                "Download rapport",
                exact=True,
            ).first
            if await candidate.count() and await candidate.is_visible():
                download_rapport = candidate
                break
        except Exception:
            continue

    if download_rapport is None:
        raise RuntimeError(
            "Menupunktet Download rapport blev ikke fundet."
        )

    await download_rapport.click()
    await page.wait_for_timeout(UI_WAIT_MS)
    dialog = page.locator(
        SkadeSelectors.DOWNLOAD_RAPPORT_DIALOG
    ).filter(has_text="DOWNLOAD RAPPORT").last
    await dialog.wait_for(state="visible", timeout=TIMEOUT_MS)

    rapport_flise = dialog.locator(
        SkadeSelectors.EASY_RAPPORT_FLIS
    ).last
    await rapport_flise.wait_for(state="visible", timeout=TIMEOUT_MS)
    checkbox = rapport_flise.locator(
        SkadeSelectors.GEM_I_MAPPE_CHECKBOX
    ).first
    await checkbox.wait_for(state="attached", timeout=TIMEOUT_MS)

    if not await checkbox.is_checked():
        await rapport_flise.locator(
            SkadeSelectors.CHECKBOX_WRAPPER
        ).first.click(
            position={"x": 20, "y": 20},
            force=True,
        )
        await page.wait_for_function(
            "element => element.checked === true",
            arg=await checkbox.element_handle(),
            timeout=TIMEOUT_MS,
        )

    await page.wait_for_timeout(UI_WAIT_MS)
    await rapport_flise.click(
        position={"x": 220, "y": 35},
        force=True,
    )
    await page.wait_for_timeout(UI_WAIT_MS)


async def send_digital_post(
    page: Page,
    *,
    cpr_nummer: str,
    dokumenttitel: str,
    forsendelsestype: str,
    hoveddokument_navn: str,
    bilag_navn: str,
    test: bool = False,
) -> dict[str, Any]:
    """
    Udfylder digital post, vedhæfter dokumenterne og sender.

    Når test er True, udfyldes og kontrolleres formularen,
    men Send-knappen bliver ikke klikket. Standardværdien
    er False, så funktionen sender som udgangspunkt.
    """
    if not isinstance(test, bool):
        raise TypeError("test skal være True eller False.")

    values = {
        "cpr_nummer": _normalize_required_text(
            name="cpr_nummer",
            value=cpr_nummer,
        ),
        "dokumenttitel": _normalize_required_text(
            name="dokumenttitel",
            value=dokumenttitel,
        ),
        "forsendelsestype": _normalize_required_text(
            name="forsendelsestype",
            value=forsendelsestype,
        ),
        "hoveddokument": _normalize_required_text(
            name="hoveddokument_navn",
            value=hoveddokument_navn,
        ),
        "bilag": _normalize_required_text(
            name="bilag_navn",
            value=bilag_navn,
        ),
    }

    dialog = await _aabn_send_digital_post_dialog(page=page)

    await _fill_and_verify(
        field=dialog.locator(SkadeSelectors.CPR_INPUT).first,
        value=values["cpr_nummer"],
        field_name="CPR-nummer",
    )
    await _fill_and_verify(
        field=dialog.locator(
            SkadeSelectors.DOKUMENTTITEL_INPUT
        ).first,
        value=values["dokumenttitel"],
        field_name="dokumenttitel",
    )
    await _vaelg_forsendelsestype(
        page=page,
        dialog=dialog,
        forsendelsestype=values["forsendelsestype"],
    )

    hoved_rows, faktisk_hoveddokument = (
        await _aabn_og_vedhaeft_dokument(
            page=page,
            send_dialog=dialog,
            knap_selector=SkadeSelectors.HOVEDDOKUMENT_KNAP,
            dokument_navn=values["hoveddokument"],
            dokumenttype="hoveddokument",
        )
    )
    bilag_rows, faktisk_bilag = (
        await _aabn_og_vedhaeft_dokument(
            page=page,
            send_dialog=dialog,
            knap_selector=SkadeSelectors.BILAG_KNAP,
            dokument_navn=values["bilag"],
            dokumenttype="bilag",
        )
    )

    sendt = False

    if test:
        logger.info(
            "Digital post er udfyldt i testtilstand. "
            "Send-knappen blev ikke klikket."
        )
    else:
        await _klik_send_digital_post(
            page=page,
            dialog=dialog,
        )
        sendt = True

    return {
        "dokumenttitel": values["dokumenttitel"],
        "forsendelsestype": values["forsendelsestype"],
        "hoveddokument": values["hoveddokument"],
        "bilag": values["bilag"],
        "faktisk_hoveddokument": faktisk_hoveddokument,
        "faktisk_bilag": faktisk_bilag,
        "hoveddokumentvaelger_rækker": hoved_rows,
        "bilagsvaelger_rækker": bilag_rows,
        "test": test,
        "sendt": sendt,
    }


async def _aabn_send_digital_post_dialog(*, page: Page) -> Locator:
    button = page.locator(
        SkadeSelectors.SEND_DIGITAL_POST_KNAP
    ).first
    await button.wait_for(state="visible", timeout=TIMEOUT_MS)
    await button.scroll_into_view_if_needed()
    try:
        await button.click(timeout=5_000)
    except PlaywrightTimeoutError:
        await button.click(force=True, timeout=5_000)

    title = page.locator(
        SkadeSelectors.SEND_DIGITAL_POST_TITEL
    ).last
    await title.wait_for(state="visible", timeout=TIMEOUT_MS)
    dialog = title.locator(
        "xpath=ancestor::*[contains(@class, 'v-overlay__content')][1]"
    )
    await dialog.wait_for(state="visible", timeout=TIMEOUT_MS)
    await page.wait_for_timeout(UI_WAIT_MS)
    return dialog


async def _vaelg_forsendelsestype(
    *,
    page: Page,
    dialog: Locator,
    forsendelsestype: str,
) -> None:
    """Åbner dokumenttype-dropdownen og vælger værdien."""
    wrapper = dialog.locator(
        SkadeSelectors.DOKUMENTTYPE_FIELD
    ).first
    input_field = dialog.locator(
        SkadeSelectors.DOKUMENTTYPE_INPUT
    ).first

    await wrapper.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await input_field.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )

    menu_id = await input_field.get_attribute("aria-controls")
    await wrapper.click(force=True)
    await page.wait_for_timeout(UI_WAIT_MS)

    menu = (
        page.locator(f"#{menu_id}")
        if menu_id
        else page.locator(
            SkadeSelectors.DOKUMENTTYPE_MENU
        ).last
    )
    await menu.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )

    option = menu.locator(
        SkadeSelectors.DOKUMENTTYPE_MENU_VALG
    ).filter(
        has_text=re.compile(
            rf"^\s*{re.escape(forsendelsestype)}\s*$",
            re.IGNORECASE,
        )
    ).first
    await option.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await option.click()
    await page.wait_for_timeout(UI_WAIT_MS)

    selected_text = (
        await input_field.input_value()
    ).strip()

    if selected_text.casefold() != forsendelsestype.casefold():
        raise RuntimeError(
            "Dokumenttypen blev ikke valgt korrekt. "
            f"Forventede: {forsendelsestype!r}. "
            f"Modtog: {selected_text!r}."
        )


async def _aabn_og_vedhaeft_dokument(
    *,
    page: Page,
    send_dialog: Locator,
    knap_selector: str,
    dokument_navn: str,
    dokumenttype: str,
) -> tuple[list[str], str]:
    """Vælger, vedhæfter og kontrollerer et dokument."""
    button = send_dialog.locator(knap_selector).first
    await button.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await button.scroll_into_view_if_needed()

    try:
        await button.click(timeout=5_000)
    except PlaywrightTimeoutError:
        await button.click(force=True, timeout=5_000)

    picker = page.locator(SkadeSelectors.DOKUMENTVAEGER).last
    await picker.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await page.wait_for_timeout(UI_WAIT_MS)

    rows = await hent_dokumentnavne(
        dokumentvaelger=picker,
    )
    faktisk_dokumentnavn = await marker_dokument(
        dokumentvaelger=picker,
        dokument_navn=dokument_navn,
    )

    picker_dialog = picker.locator(
        "xpath=ancestor::*[contains(@class, 'v-overlay__content')][1]"
    )
    attach_button = picker_dialog.locator(
        SkadeSelectors.VEDHAEFT_KNAP
    ).first

    if await attach_button.count() == 0:
        attach_button = picker_dialog.get_by_role(
            "button",
            name="Vedhæft",
            exact=True,
        ).first

    await attach_button.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await attach_button.scroll_into_view_if_needed()

    if not await attach_button.is_enabled():
        raise RuntimeError(
            f"Vedhæft for {dokumenttype} er ikke aktiveret."
        )

    try:
        await attach_button.click(timeout=3_000)
    except PlaywrightTimeoutError:
        try:
            await attach_button.click(
                force=True,
                timeout=3_000,
            )
        except PlaywrightTimeoutError:
            await attach_button.evaluate(
                "element => element.click()"
            )

    try:
        await picker_dialog.wait_for(
            state="hidden",
            timeout=5_000,
        )
    except PlaywrightTimeoutError:
        if await attach_button.is_visible():
            await attach_button.evaluate(
                "element => element.click()"
            )
        await picker_dialog.wait_for(
            state="hidden",
            timeout=TIMEOUT_MS,
        )

    await page.locator(
        SkadeSelectors.SEND_DIGITAL_POST_TITEL
    ).last.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await page.wait_for_timeout(UI_WAIT_MS)

    vedhaeftet_filnavn = await _kontroller_vedhaeftet_chip(
        send_dialog=send_dialog,
        forventet_filnavn=faktisk_dokumentnavn,
    )

    logger.info(
        "%s blev vedhæftet og bekræftet: %s.",
        dokumenttype.capitalize(),
        vedhaeftet_filnavn,
    )

    return rows, vedhaeftet_filnavn


async def _kontroller_vedhaeftet_chip(
    *,
    send_dialog: Locator,
    forventet_filnavn: str,
) -> str:
    """Kontrollerer filnavnet i den vedhæftede dokumentchip."""
    forventet_normaliseret = _normalize_document_name(
        forventet_filnavn,
        remove_extension=True,
    )
    chips = send_dialog.locator(
        SkadeSelectors.DOKUMENTCHIP_TEKST
    )

    await chips.first.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )

    fundne_filnavne: list[str] = []

    for index in range(await chips.count()):
        chip_text = (
            await chips.nth(index).inner_text()
        ).strip()

        if not chip_text:
            continue

        fundne_filnavne.append(chip_text)
        faktisk_normaliseret = _normalize_document_name(
            chip_text,
            remove_extension=True,
        )

        if faktisk_normaliseret == forventet_normaliseret:
            return chip_text

    raise RuntimeError(
        "Det korrekte dokument blev ikke vist som chip "
        "efter Vedhæft. "
        f"Forventede: {forventet_filnavn!r}. "
        f"Fundne chips: {fundne_filnavne!r}."
    )


async def _klik_send_digital_post(
    *,
    page: Page,
    dialog: Locator,
) -> None:
    """Klikker på Send og venter på, at dialogen lukker."""
    send_button = dialog.locator(
        SkadeSelectors.SEND_KNAP
    ).last

    if await send_button.count() == 0:
        send_button = dialog.get_by_role(
            "button",
            name="Send",
            exact=True,
        ).last

    await send_button.wait_for(
        state="visible",
        timeout=TIMEOUT_MS,
    )
    await send_button.scroll_into_view_if_needed()

    if not await send_button.is_enabled():
        raise RuntimeError("Knappen Send er ikke aktiveret.")

    await send_button.click()
    await dialog.wait_for(
        state="hidden",
        timeout=30_000,
    )
    await page.wait_for_timeout(UI_WAIT_MS)

    logger.info("Digital post blev sendt.")


async def hent_dokumentnavne(
    *,
    dokumentvaelger: Locator,
) -> list[str]:
    """Returnerer alle filnavne i dokumentvælgeren."""
    documents = dokumentvaelger.locator(
        SkadeSelectors.DOKUMENTNAVN
    )
    result: list[str] = []
    for index in range(await documents.count()):
        document = documents.nth(index)
        title = await document.get_attribute("title")
        text = (title or await document.inner_text()).strip()
        if text:
            result.append(text)
    return result


async def marker_dokument(
    *,
    dokumentvaelger: Locator,
    dokument_navn: str,
) -> str:
    """Finder dokumentrækken og markerer checkboxen."""
    normalized_document_name = _normalize_required_text(
        name="dokument_navn",
        value=dokument_navn,
    )
    documents = dokumentvaelger.locator(
        SkadeSelectors.DOKUMENTNAVN
    )
    await documents.first.wait_for(state="visible", timeout=TIMEOUT_MS)
    available_documents: list[tuple[Locator, str]] = []

    for index in range(await documents.count()):
        document = documents.nth(index)
        if not await document.is_visible():
            continue
        title = await document.get_attribute("title")
        actual_name = (title or await document.inner_text()).strip()
        if actual_name:
            available_documents.append((document, actual_name))

    selected_document = _find_document_match(
        documents=available_documents,
        requested_name=normalized_document_name,
    )
    if selected_document is None:
        raise RuntimeError(
            f"Dokumentet {normalized_document_name!r} blev ikke fundet. "
            "Tilgængelige dokumenter: "
            f"{[name for _, name in available_documents]!r}."
        )

    filename, actual_name = selected_document
    row = filename.locator("xpath=ancestor::tr[1]")
    checkbox = row.locator(
        SkadeSelectors.DOKUMENT_CHECKBOX
    ).first
    await checkbox.wait_for(state="attached", timeout=TIMEOUT_MS)

    if not await checkbox.is_checked():
        wrapper = row.locator(
            SkadeSelectors.CHECKBOX_WRAPPER
        ).first
        await wrapper.wait_for(
            state="visible",
            timeout=TIMEOUT_MS,
        )

        try:
            await checkbox.check(
                force=True,
                timeout=3_000,
            )
        except Exception:
            pass

        if not await checkbox.is_checked():
            try:
                await wrapper.click(
                    force=True,
                    timeout=3_000,
                )
            except Exception:
                pass

        if not await checkbox.is_checked():
            await checkbox.evaluate(
                "element => element.click()"
            )

        try:
            await page_wait_for_checkbox(
                checkbox=checkbox,
            )
        except PlaywrightTimeoutError as error:
            raise RuntimeError(
                "Dokumentets checkbox blev ikke markeret. "
                f"Dokument: {actual_name!r}."
            ) from error

    if not await checkbox.is_checked():
        raise RuntimeError(
            "Dokumentet blev fundet, men checkboxen blev "
            f"ikke markeret. Dokument: {actual_name!r}."
        )

    logger.info(
        "Dokument markeret: %s. Input: %s.",
        actual_name,
        normalized_document_name,
    )
    return actual_name


async def page_wait_for_checkbox(*, checkbox: Locator) -> None:
    """Venter på, at dokumentcheckboxen bliver markeret."""
    handle = await checkbox.element_handle()
    if handle is None:
        raise RuntimeError("Checkbox-elementet kunne ikke aflæses.")
    await checkbox.page.wait_for_function(
        "element => element.checked === true",
        arg=handle,
        timeout=TIMEOUT_MS,
    )


async def _fill_and_verify(
    *,
    field: Locator,
    value: str,
    field_name: str,
) -> None:
    await field.wait_for(state="visible", timeout=TIMEOUT_MS)
    await field.fill(value)
    if (await field.input_value()).strip() != value:
        raise RuntimeError(f"{field_name} blev ikke indsat korrekt.")


def _find_document_match(
    *,
    documents: list[tuple[Locator, str]],
    requested_name: str,
) -> tuple[Locator, str] | None:
    requested_full = _normalize_document_name(
        requested_name,
        remove_extension=False,
    )
    requested_stem = _normalize_document_name(
        requested_name,
        remove_extension=True,
    )
    exact_full: list[tuple[Locator, str]] = []
    exact_stem: list[tuple[Locator, str]] = []
    prefixes: list[tuple[Locator, str]] = []

    for locator, actual_name in documents:
        actual_full = _normalize_document_name(
            actual_name,
            remove_extension=False,
        )
        actual_stem = _normalize_document_name(
            actual_name,
            remove_extension=True,
        )
        if actual_full == requested_full:
            exact_full.append((locator, actual_name))
        elif actual_stem == requested_stem:
            exact_stem.append((locator, actual_name))
        elif actual_stem.startswith(requested_stem):
            prefixes.append((locator, actual_name))

    for matches, match_type in (
        (exact_full, "fuldt filnavn"),
        (exact_stem, "titel uden filendelse"),
        (prefixes, "titelprefix"),
    ):
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(
                "Dokumentnavnet gav flere matches via "
                f"{match_type}. Input: {requested_name!r}. "
                f"Matches: {[name for _, name in matches]!r}."
            )
    return None


def _normalize_document_name(
    value: str,
    *,
    remove_extension: bool,
) -> str:
    normalized = " ".join(value.strip().split()).casefold()
    if remove_extension:
        for extension in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            if normalized.endswith(extension):
                normalized = normalized[:-len(extension)].rstrip()
                break
    return normalized


def _extract_easy_object(
    *,
    incident: dict[str, Any],
) -> dict[str, Any]:
    """Returnerer det indlejrede EASY-objekt, hvis det findes."""
    if not isinstance(incident, dict):
        raise TypeError(
            "incident skal være en dictionary."
        )

    easy = incident.get("easy")

    if easy is None:
        return {}

    if not isinstance(easy, dict):
        raise RuntimeError(
            "Feltet easy er ikke en dictionary. "
            f"Modtog: {type(easy).__name__}."
        )

    return easy


def _extract_easy_status_text(
    *,
    incident: dict[str, Any],
) -> str:
    """Henter EASY-status fra topniveau eller det indlejrede easy-objekt."""
    if not isinstance(incident, dict):
        raise TypeError(
            "incident skal være en dictionary."
        )

    easy = _extract_easy_object(
        incident=incident,
    )

    status = (
        incident.get("easyStatus")
        or incident.get("easy.status")
        or easy.get("easyStatus")
        or easy.get("status")
    )

    if status is None:
        return ""

    if isinstance(status, dict):
        return str(
            status.get("text")
            or status.get("name")
            or status.get("value")
            or ""
        ).strip()

    if isinstance(status, str):
        return status.strip()

    raise RuntimeError(
        "EASY-status havde et ugyldigt format. "
        f"Modtog: {type(status).__name__}. "
        f"Værdi: {status!r}."
    )


def _extract_easy_reference(
    *,
    incident: dict[str, Any],
) -> str:
    """Henter EASY-reference fra topniveau eller det indlejrede easy-objekt."""
    if not isinstance(incident, dict):
        raise TypeError(
            "incident skal være en dictionary."
        )

    easy = _extract_easy_object(
        incident=incident,
    )

    easy_reference = str(
        incident.get("easyRef")
        or incident.get("easy.ref")
        or easy.get("easyRef")
        or easy.get("ref")
        or ""
    ).strip()

    if easy_reference:
        return easy_reference

    claim_id = str(
        incident.get("easyClaimId")
        or incident.get("easy.claimId")
        or easy.get("easyClaimId")
        or easy.get("claimId")
        or ""
    ).strip()

    if claim_id in {
        "",
        "0",
        "None",
    }:
        return ""

    return claim_id


def _normalize_easy_status(value: str) -> str:
    """Normaliserer EASY-status til robust sammenligning."""
    return " ".join(
        str(value).strip().split()
    ).casefold()


def _er_allerede_sendt_til_easy(
    *,
    easy_status: str,
) -> bool:
    """Kontrollerer om EASY-status forhindrer genafsendelse."""
    return (
        _normalize_easy_status(easy_status)
        in EASY_STATUS_ALLEREDE_SENDT
    )


def _normalize_easy_validation_response(
    *,
    response: Any,
) -> dict[str, Any]:
    """Normaliserer de kendte svarformer fra EASY-valideringen."""
    if isinstance(response, dict):
        return response

    if isinstance(response, bool):
        return {
            "isValid": response,
            "value": response,
            "text": "OK" if response else "False",
        }

    if isinstance(response, list):
        return {
            "isValid": len(response) == 0,
            "errors": response,
            "value": response,
            "text": "",
        }

    if isinstance(response, str):
        return {
            "isValid": None,
            "value": response,
            "text": response.strip(),
        }

    if response is None:
        return {
            "isValid": None,
            "value": None,
            "text": "",
        }

    return {
        "isValid": None,
        "value": response,
        "text": str(response),
    }


def _validate_easy_validation_response(
    *,
    response: dict[str, Any],
    skade_id: int,
) -> None:
    """Afviser kun valideringssvar, der eksplicit melder fejl."""
    explicit_validity = response.get("isValid")

    if explicit_validity is None:
        explicit_validity = response.get("valid")

    if explicit_validity is None:
        explicit_validity = response.get("success")

    value = response.get("value")
    errors = (
        response.get("errors")
        or response.get("validationErrors")
        or response.get("messages")
        or []
    )
    text = str(
        response.get("text")
        or response.get("message")
        or response.get("error")
        or ""
    ).strip()
    normalized_text = text.casefold()

    if explicit_validity is False or value is False:
        raise RuntimeError(
            "EASY-valideringen afviste skaden. "
            f"Skade-id: {skade_id}. Response: {response!r}."
        )

    if errors:
        raise RuntimeError(
            "EASY-valideringen returnerede valideringsfejl. "
            f"Skade-id: {skade_id}. Fejl: {errors!r}."
        )

    if any(
        word in normalized_text
        for word in (
            "error",
            "fejl",
            "failed",
            "mislykkedes",
            "invalid",
            "ugyldig",
        )
    ):
        raise RuntimeError(
            "EASY-valideringen returnerede en fejltekst. "
            f"Skade-id: {skade_id}. Response: {response!r}."
        )


def _normalize_send_response(*, response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if isinstance(response, bool):
        return {
            "statusCode": 200,
            "value": response,
            "text": "OK" if response else "False",
        }
    if isinstance(response, str):
        return {
            "statusCode": 200,
            "value": None,
            "text": response.strip(),
        }
    if response is None:
        return {"statusCode": 200, "value": None, "text": ""}
    return {
        "statusCode": None,
        "value": response,
        "text": str(response),
    }


def _validate_send_response(
    *,
    response: dict[str, Any],
    skade_id: int,
) -> None:
    status_code = response.get("statusCode")
    value = response.get("value")
    text = str(response.get("text") or "").casefold()
    if status_code is not None and status_code != 200:
        raise RuntimeError(
            f"EASY-kald fejlede for skade {skade_id}: {response!r}."
        )
    if value is False:
        raise RuntimeError(
            f"EASY-kald returnerede False for skade {skade_id}."
        )
    if any(
        word in text
        for word in ("error", "fejl", "failed", "mislykkedes")
    ):
        raise RuntimeError(
            f"EASY-kald returnerede fejl for skade {skade_id}: "
            f"{response!r}."
        )


def _normalize_skade_id(skade_id: int | str) -> int:
    if isinstance(skade_id, bool):
        raise TypeError("skade_id må ikke være boolsk.")
    value = str(skade_id).strip()
    if not value or not value.isdigit():
        raise ValueError("skade_id skal være numerisk.")
    result = int(value)
    if result <= 0:
        raise ValueError("skade_id skal være større end 0.")
    return result


def _normalize_skade_status(*, status: SkadeStatus | int) -> SkadeStatus:
    if isinstance(status, bool):
        raise TypeError("status må ikke være boolsk.")
    try:
        return SkadeStatus(status)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Status understøttes ikke. "
            f"Tilladte værdier: {[int(v) for v in SkadeStatus]}."
        ) from error


def _normalize_last_editing(*, last_editing: str) -> str:
    if not isinstance(last_editing, str):
        raise TypeError("last_editing skal være tekst.")
    value = last_editing.strip()
    if not value:
        raise ValueError("last_editing må ikke være tom.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            "last_editing skal være et ISO-datoformat."
        ) from error
    return value


def _normalize_required_text(*, name: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} skal være tekst.")
    result = value.strip()
    if not result:
        raise ValueError(f"{name} må ikke være tom.")
    return result




def _validate_list_parameters(
    *,
    customer_id: int | None,
    customer_segmentation_1: int,
    customer_segmentation_2: int,
    claim_group_id: int,
    status_id: int,
    created_year_from: int,
    created_year_to: int,
    incident_year_from: int,
    incident_year_to: int,
    show_tree_data: bool,
) -> None:
    values = {
        "customer_segmentation_1": customer_segmentation_1,
        "customer_segmentation_2": customer_segmentation_2,
        "claim_group_id": claim_group_id,
        "status_id": status_id,
        "created_year_from": created_year_from,
        "created_year_to": created_year_to,
        "incident_year_from": incident_year_from,
        "incident_year_to": incident_year_to,
    }
    if customer_id is not None:
        values["customer_id"] = customer_id
    for name, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} skal være et heltal.")
    if not isinstance(show_tree_data, bool):
        raise TypeError("show_tree_data skal være boolsk.")
    if created_year_from > created_year_to:
        raise ValueError(
            "created_year_from må ikke være større end created_year_to."
        )
    if incident_year_from > incident_year_to:
        raise ValueError(
            "incident_year_from må ikke være større end incident_year_to."
        )






__all__ = [
    "EASY_STATUS_AFSENDT_AFVENTER",
    "EASY_STATUS_GODKENDT",
    "SKADER_LISTE",
    "SendSkadeTilEasyResultat",
    "SkadeStatus",
    "opret_dokument_fra_skabelon",
    "download_easy_rapport_og_gem_i_mappe",
    "gem_dokument_fra_skabelon",
    "hent_dokumentnavne",
    "hent_skade_via_id",
    "klik_paa_skade",
    "marker_dokument",
    "opdater_skade_status",
    "opdater_skade_status_fra_seneste_data",
    "send_digital_post",
    "send_skade_til_easy",
    "valider_skade_foer_easy",
    "vaelg_dokumentskabelon",
]
