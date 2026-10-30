"""Parse BCRPData period labels and values, and format request periods."""

import re
from datetime import date

# The API uses both "Sep" (monthly series) and "Set" (daily series) for September.
MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip

FREQUENCIES = {"D": "diaria", "M": "mensual", "Q": "trimestral", "A": "anual"}

_DAILY = re.compile(r"^(\d{1,2})\.([A-Za-z]{3})\.(\d{2})$")  # 02.Ene.26
_MONTHLY = re.compile(r"^([A-Za-z]{3})\.(\d{4})$")  # Ene.2026
_QUARTERLY = re.compile(r"^T([1-4])\.(\d{2})$")  # T1.26
_ANNUAL = re.compile(r"^(\d{4})$")  # 2026


def frequency(code: str) -> str:
    """Frequency of a BCRP series code, taken from its last letter."""
    try:
        return FREQUENCIES[code[-1].upper()]
    except (KeyError, IndexError):
        raise ValueError(f"Unknown frequency for series code {code!r}") from None


def _month(abbr: str) -> int:
    try:
        return MONTHS[abbr.lower()]
    except KeyError:
        raise ValueError(f"Unknown month abbreviation {abbr!r}") from None


def parse_period(label: str) -> date:
    """Convert a period label to the first day of that period."""
    label = label.strip()
    if m := _DAILY.match(label):
        return date(2000 + int(m[3]), _month(m[2]), int(m[1]))
    if m := _MONTHLY.match(label):
        return date(int(m[2]), _month(m[1]), 1)
    if m := _QUARTERLY.match(label):
        return date(2000 + int(m[2]), 3 * int(m[1]) - 2, 1)
    if m := _ANNUAL.match(label):
        return date(int(m[1]), 1, 1)
    raise ValueError(f"Unrecognized BCRP period label {label!r}")


def parse_value(raw: str) -> float | None:
    """Convert an API value to float; "n.d." (not available) becomes None."""
    raw = raw.strip()
    if raw.lower() == "n.d." or not raw:
        return None
    return float(raw)


def format_period(day: date, freq: str) -> str:
    """Format a date as the period string the API expects for a frequency."""
    if freq == "diaria":
        return day.isoformat()
    if freq == "mensual":
        return f"{day.year}-{day.month}"
    if freq == "trimestral":
        return f"{day.year}-{(day.month - 1) // 3 + 1}"
    if freq == "anual":
        return str(day.year)
    raise ValueError(f"Unknown frequency {freq!r}")
