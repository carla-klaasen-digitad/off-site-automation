"""Normalize month names — handles English and French, abbreviations, accents, case."""
from __future__ import annotations

MONTH_MAP = {
    # English — full
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    # English — abbreviated (with and without period)
    "jan": 1, "jan.": 1,
    "feb": 2, "feb.": 2,
    "mar": 3, "mar.": 3,
    "apr": 4, "apr.": 4,
    "jun": 6, "jun.": 6,
    "jul": 7, "jul.": 7,
    "aug": 8, "aug.": 8,
    "sep": 9, "sep.": 9, "sept": 9, "sept.": 9,
    "oct": 10, "oct.": 10,
    "nov": 11, "nov.": 11,
    "dec": 12, "dec.": 12,
    # French — full (with and without accents)
    "janvier": 1,
    "février": 2, "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8, "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12, "decembre": 12,
    # French — abbreviated
    "janv": 1, "janv.": 1,
    "févr": 2, "févr.": 2, "fevr": 2, "fevr.": 2,
    "avr": 4, "avr.": 4,
    "juil": 7, "juil.": 7,
    "août.": 8, "aout.": 8,
    "sept.": 9,
    "oct.": 10,
    "nov.": 11,
    "déc": 12, "déc.": 12, "dec": 12, "dec.": 12,
}


def normalize_month(value: str) -> int | None:
    """
    Convert a month string to its integer (1–12).
    Returns None if the value cannot be matched.
    """
    if not value:
        return None
    cleaned = value.strip().lower()
    return MONTH_MAP.get(cleaned)


def month_matches(cell_value: str, target_month: int) -> bool:
    """Return True if the cell value resolves to the target month number."""
    return normalize_month(cell_value) == target_month
