from __future__ import annotations


class InsubizSelectors:
    """Selectors til login og generelle loginfejl i Insubiz."""

    EMAIL_INPUT = (
        'input[type="email"]'
        '[autocomplete="username"]:visible'
    )

    PASSWORD_INPUT = (
        'input[type="password"]'
        '[autocomplete="current-password"]'
    )

    LOGIN_BUTTON = (
        'button[type="submit"]:visible'
    )

    LOGIN_ERROR = (
        '.v-messages__message:visible, '
        '[role="alert"]:visible, '
        '.v-alert:visible'
    )


class SkadeSelectors:
    """
    Selectors til skadesiden, dokumentdialoger,
    rapporter og Digital Post.
    """

    # --------------------------------------------------
    # Skadenavigation
    # --------------------------------------------------
    SKADE_MENU = (
        'a[href="/incident/"]'
    )

    # --------------------------------------------------
    # Opret dokument fra skabelon
    # --------------------------------------------------
    aabn_dokumentdialog = (
        'button[aria-haspopup="dialog"]'
        ':has(svg path[d^="M14 2H6"])'
    )

    DOKUMENT_DIALOG_TITEL = (
        'div.v-card-title.bg-primary.text-white'
        ':has-text("Opret dokument fra skabelon")'
    )

    SKABELON_DROPDOWN = (
        'div.v-field__input'
        ':has(select option[value$=".docx"]) '
        'input[role="combobox"]'
    )

    AABEN_SKABELON_MENU = (
        '.v-overlay--active '
        '.v-list'
    )

    SKABELON_VALG = (
        '.v-overlay--active '
        '.v-list-item'
    )

    VALGT_SKABELON = (
        'div.v-field__input'
        ':has(select option[value$=".docx"]) '
        '.v-select__selection'
    )

    GEM_DOKUMENT_KNAP = (
        'button.main-btn'
        ':has(svg path[d^="M17 3H5"])'
        ':has-text("Gem")'
    )

    # --------------------------------------------------
    # Rapportmenu og EASY-rapport
    # --------------------------------------------------
    TRE_PRIK_MENU_KNAP = (
        'button[aria-haspopup="menu"]'
        ':has(svg path[d^="M12,16A2,2"])'
        ':visible'
    )

    AABEN_MENU = (
        '.v-overlay--active:visible'
    )

    DOWNLOAD_RAPPORT_MENU_VALG = (
        ':text-is("Download rapport")'
    )

    DOWNLOAD_RAPPORT_DIALOG = (
        '.v-overlay.v-overlay--active.v-dialog '
        '.v-overlay__content'
    )

    DOWNLOAD_RAPPORT_DIALOG_TITEL = (
        ':text-is("DOWNLOAD RAPPORT")'
    )

    EASY_RAPPORT_FLIS = (
        'div.v-card.printReport'
        ':has-text("SKEMA FOR EASY ARBEJDSSKADE")'
    )

    GEM_I_MAPPE_CHECKBOX = (
        'input[type="checkbox"]'
        '[aria-label="Gem i mappe"]'
    )

    # --------------------------------------------------
    # Send Digital Post
    # --------------------------------------------------
    SEND_DIGITAL_POST_KNAP = (
        'button[aria-haspopup="dialog"]'
        ':has(svg path[d^="M17,4H7A5,5"])'
    )

    SEND_DIGITAL_POST_TITEL = (
        'div.v-card-title.bg-primary.text-white'
        ':has-text("Send digital post (OneTooX)")'
    )

    CPR_INPUT = (
        'textarea.v-field__input'
    )

    DOKUMENTTITEL_INPUT = (
        'input.v-field__input[type="text"]'
        ':not([role="combobox"])'
    )

    # --------------------------------------------------
    # Dokumenttype
    # --------------------------------------------------
    DOKUMENTTYPE_FIELD = (
        'div.v-field__input'
        ':has(select option[value="1"])'
    )

    DOKUMENTTYPE_INPUT = (
        'div.v-field__input'
        ':has(select option[value="1"]) '
        'input[role="combobox"]'
        '[inputmode="none"]'
    )

    DOKUMENTTYPE_COMBOBOX = (
        'input[role="combobox"]'
        '[inputmode="none"]'
    )

    DOKUMENTTYPE_SELECTION = (
        'div.v-field__input'
        ':has(select option[value="1"]) '
        '.v-select__selection-text'
    )

    DOKUMENTTYPE_MENU = (
        '.v-overlay--active '
        '.v-list'
    )

    DOKUMENTTYPE_MENU_VALG = (
        '[role="option"]'
    )

    # --------------------------------------------------
    # Dokumentvælger
    # --------------------------------------------------
    HOVEDDOKUMENT_KNAP = (
        'button[aria-haspopup="dialog"]'
        ':has(svg path[d^="M16.5,6V17.5"])'
        ':has-text("Hoved dokument")'
    )

    BILAG_KNAP = (
        'button[aria-haspopup="dialog"]'
        ':has(svg path[d^="M16.5,6V17.5"])'
        ':has-text("Bilag")'
    )

    DOKUMENTVAEGER = (
        '.v-data-table.'
        'fileSystem--DirectoryList.'
        'filePicker'
    )

    DOKUMENTVAEGER_TITEL = (
        ':text-is("Dokumenter")'
    )

    DOKUMENTNAVN = (
        'tbody tr:not(.blankArea) '
        'span.filenameStyling'
    )

    DOKUMENTRAEKKE = (
        'tbody tr:not(.blankArea)'
    )

    DOKUMENT_CHECKBOX = (
        'input[type="checkbox"]'
    )

    CHECKBOX_WRAPPER = (
        '.v-selection-control__wrapper'
    )

    VEDHAEFT_KNAP = (
        'div.v-card-actions '
        'button.v-btn.v-btn--slim'
        '.v-btn--variant-outlined'
        ':has(.v-btn__content:has-text("Vedhæft"))'
    )

    # --------------------------------------------------
    # Vedhæftede dokumenter
    # --------------------------------------------------
    DOKUMENTCHIP = (
        'span.v-chip'
    )

    DOKUMENTCHIP_TEKST = (
        'span.v-chip '
        'span.text-truncate'
    )

    DOKUMENTCHIP_LUK = (
        'span.v-chip '
        'button[data-testid="close-chip"]'
    )

    # --------------------------------------------------
    # Send-knap
    # --------------------------------------------------
    SEND_KNAP = (
        'button'
        ':has(.v-btn__content:has-text("Send"))'
    )


__all__ = [
    "InsubizSelectors",
    "SkadeSelectors",
]
