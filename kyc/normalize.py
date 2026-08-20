"""Value normalisation shared by the member and candidate loaders.

Every helper here is total: it accepts whatever the CSVs contain (including
``None``, ``"nan"`` and empty strings) and returns a display-ready value.
"""

import math
import re

# Tokens that CSV exports use to mean "no value". Compared case-insensitively.
_NA_TOKENS = {"", "nan", "none", "n/a", "na", "unknown", "$nan", "null"}

US_STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
    "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI",
    "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC", "PUERTO RICO": "PR", "GUAM": "GU",
    "VIRGIN ISLANDS": "VI", "AMERICAN SAMOA": "AS", "NORTHERN MARIANA ISLANDS": "MP",
}

STATE_CODES = frozenset(US_STATES.values())

# Territories send non-voting delegates; excluded from chamber balance counts.
TERRITORIES = frozenset({"AS", "DC", "GU", "MP", "PR", "VI"})

# Longest first so "WEST VIRGINIA" is tested before "VIRGINIA".
_STATES_BY_LENGTH = sorted(US_STATES.items(), key=lambda kv: -len(kv[0]))


def is_missing(val):
    """True when *val* is one of the CSV placeholders for "no data"."""
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    return str(val).strip().lower() in _NA_TOKENS


def clean_str(val, default="N/A"):
    """Trim *val*, mapping any missing-data placeholder to *default*."""
    if is_missing(val):
        return default
    return str(val).strip()


def first_present(*vals, default="N/A"):
    """Return the first of *vals* that carries real data."""
    for val in vals:
        if not is_missing(val):
            return str(val).strip()
    return default


def parse_age(val):
    """Return age as an int, or ``"Unknown"`` when absent or nonsensical."""
    if is_missing(val):
        return "Unknown"
    try:
        age = int(float(str(val).strip()))
    except (ValueError, TypeError):
        return "Unknown"
    # Constitutional floor is 25 (House); anything past 110 is a data error.
    return age if 0 < age < 110 else "Unknown"


def fmt_curr(val):
    """Format a dollar figure.

    A genuine zero formats as ``$0.00`` rather than ``N/A`` - on a
    transparency site "raised nothing" and "we have no filing" are
    different claims and must not collapse into one label.
    """
    if is_missing(val):
        return "N/A"
    raw = str(val).strip()
    if raw.startswith("$"):
        return raw
    try:
        amount = float(raw.replace(",", ""))
    except ValueError:
        return raw
    if math.isnan(amount):
        return "N/A"
    return f"${amount:,.2f}"


def parse_state_abbrev(office_str):
    """Extract a two-letter state code from an office/district string.

    Handles ``"TX"``, ``"TX-32"`` and full names like ``"West Virginia"``.
    Bare two-letter tokens are only read from the *original* casing so that
    lowercase English words ("in", "or", "me") are never mistaken for states.
    """
    if is_missing(office_str):
        return "N/A"
    raw = str(office_str).strip()

    compact = raw.upper().replace(".", "")
    for full_name, code in _STATES_BY_LENGTH:
        if re.search(rf"\b{re.escape(full_name)}\b", compact):
            return code

    # "TX" / "TX-32" as the entire value, or an explicit district token.
    exact = re.fullmatch(r"([A-Za-z]{2})(?:-\d+)?", raw)
    if exact and exact.group(1).upper() in STATE_CODES:
        return exact.group(1).upper()

    district = re.search(r"\b([A-Z]{2})-\d+\b", raw)
    if district and district.group(1) in STATE_CODES:
        return district.group(1)

    bare = re.search(r"\b([A-Z]{2})\b", raw)
    if bare and bare.group(1) in STATE_CODES:
        return bare.group(1)

    return "N/A"


def parse_district(val, state=None):
    """Normalise a district value into ``(number, label)``.

    Accepts the shapes the two roster formats actually use - ``"District 3"``
    from the member CSVs, ``"TX-32"`` from the candidate CSVs, plus at-large
    spellings. At-large is number ``0`` with label ``"AL"``. Returns
    ``(None, None)`` when there is no district (Senate rows, missing data).
    """
    if is_missing(val):
        return None, None
    raw = str(val).strip()

    if re.search(r"at[\s-]?large", raw, re.IGNORECASE):
        return 0, "AL"

    # Strip a redundant state prefix: "TX-32" -> "32".
    if state and state != "N/A":
        raw = re.sub(rf"^{re.escape(state)}\s*-\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^district\s*", "", raw, flags=re.IGNORECASE).strip()

    match = re.search(r"\d+", raw)
    if not match:
        return None, None

    num = int(match.group(0))
    # A lone "0" in these rosters means the state's single at-large seat.
    return (0, "AL") if num == 0 else (num, str(num))


def office_label(chamber, state, district_label):
    """Human-readable seat label, e.g. ``"House - TX-32"`` / ``"Senate - TX"``."""
    state = state if state and state != "N/A" else ""
    if "Senate" in chamber:
        return f"Senate • {state}".strip() if state else "Senate"
    if "House" in chamber:
        if state and district_label:
            return f"House • {state}-{district_label}"
        return f"House • {state}".strip() if state else "House"
    return chamber
