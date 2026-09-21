from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


# --------------------------------------------------
# Skadestatus
# --------------------------------------------------
class SkadeStatus(IntEnum):
    """Understøttede statusværdier for en skade."""

    NY = 0
    AFSLUTTET = 3


# --------------------------------------------------
# Statusopdatering
# --------------------------------------------------
@dataclass(frozen=True, slots=True)
class SkadeStatusResultat:
    """Resultat fra en kontrolleret statusopdatering."""

    skade_id: int
    status_foer: int
    status_efter: int
    status: SkadeStatus
    last_editing_foer: str
    last_editing_efter: str
    update_response: Any


# --------------------------------------------------
# EASY-afsendelse
# --------------------------------------------------
@dataclass(frozen=True, slots=True)
class SendSkadeTilEasyResultat:
    """Resultat fra EASY-kontrol og eventuel afsendelse."""

    skade_id: int
    easy_status_foer: str
    easy_reference: str
    allerede_sendt: bool
    sendt_nu: bool
    besked: str
    afsendelses_response: dict[str, Any] | None

    def __post_init__(self) -> None:
        """Kontrollerer at resultatets tilstand er konsistent."""
        if isinstance(self.skade_id, bool) or not isinstance(
            self.skade_id,
            int,
        ):
            raise TypeError("skade_id skal være et heltal.")

        if self.skade_id <= 0:
            raise ValueError("skade_id skal være større end 0.")

        if self.allerede_sendt and self.sendt_nu:
            raise ValueError(
                "allerede_sendt og sendt_nu må ikke begge "
                "være True."
            )

        if not self.allerede_sendt and not self.sendt_nu:
            raise ValueError(
                "Præcis ét af felterne allerede_sendt og "
                "sendt_nu skal være True."
            )

        if self.allerede_sendt and (
            self.afsendelses_response is not None
        ):
            raise ValueError(
                "afsendelses_response skal være None, når "
                "skaden allerede var sendt."
            )

        if self.sendt_nu and self.afsendelses_response is None:
            raise ValueError(
                "afsendelses_response mangler, selv om "
                "skaden blev sendt nu."
            )


# --------------------------------------------------
# Digital post
# --------------------------------------------------
@dataclass(frozen=True, slots=True)
class SendDigitalPostResultat:
    """Resultat fra udfyldning og eventuel afsendelse."""

    dokumenttitel: str
    dokumenttype: str
    hoveddokument: str
    bilag: str
    faktisk_hoveddokument: str
    faktisk_bilag: str
    hoveddokumentvaelger_raekker: tuple[str, ...]
    bilagsvaelger_raekker: tuple[str, ...]
    test: bool
    sendt: bool

    def __post_init__(self) -> None:
        """Kontrollerer resultatets grundlæggende konsistens."""
        tekstfelter = {
            "dokumenttitel": self.dokumenttitel,
            "dokumenttype": self.dokumenttype,
            "hoveddokument": self.hoveddokument,
            "bilag": self.bilag,
            "faktisk_hoveddokument": self.faktisk_hoveddokument,
            "faktisk_bilag": self.faktisk_bilag,
        }

        for feltnavn, value in tekstfelter.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"{feltnavn} skal være tekst."
                )

            if not value.strip():
                raise ValueError(
                    f"{feltnavn} må ikke være tom."
                )

        if not isinstance(self.test, bool):
            raise TypeError("test skal være boolsk.")

        if not isinstance(self.sendt, bool):
            raise TypeError("sendt skal være boolsk.")

        if self.test and self.sendt:
            raise ValueError(
                "sendt må ikke være True, når test er True."
            )

        if not self.test and not self.sendt:
            raise ValueError(
                "sendt skal være True, når test er False."
            )


__all__ = [
    "SendDigitalPostResultat",
    "SendSkadeTilEasyResultat",
    "SkadeStatus",
    "SkadeStatusResultat",
]
