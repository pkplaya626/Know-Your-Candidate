"""Turn roster rows into the unified profile records the site renders.

All election derivation lives here. It used to run in the browser, duplicated
verbatim in both index.html and map.html, which meant the two pages could drift
apart and the same logic had to be maintained twice.
"""

import re
import unicodedata

from . import overrides
from .normalize import (
    TERRITORIES,
    clean_str,
    first_present,
    fmt_curr,
    is_missing,
    office_label,
    parse_age,
    parse_district,
    parse_state_abbrev,
)
from .photos import candidate_photos, member_photos

ELECTION_YEAR = 2026
NEXT_CONGRESS_START = "2027-01-03"


def _fold(text):
    """Strip accents so surname matching works on "Lujan" vs "Lujan"."""
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _chamber_kind(chamber):
    """Reduce a chamber string to ``"Senate"``, ``"House"`` or ``""``."""
    if "Senate" in chamber:
        return "Senate"
    if "House" in chamber:
        return "House"
    return ""


def _is_candidate(chamber, status):
    return "Candidate" in chamber or "candidate" in str(status).lower()


def _term_string(start, end_year):
    """Render a term as ``"<start> - <end>"``, tolerating a missing start."""
    start = clean_str(start, "N/A")
    base = start.split(" - ")[0].strip()
    if base in ("", "N/A"):
        return "N/A"
    return f"{base} - {end_year}-01-03" if end_year else base


def _senate_term_end(term_start):
    """Next odd-numbered year in which this Senate term expires.

    Senate terms run six years and end in January of an odd year, so we step
    forward from the start year in six-year hops until we pass the current
    Congress.
    """
    match = re.match(r"\s*(\d{4})", str(term_start or ""))
    if not match:
        return None
    end = int(match.group(1)) + 6
    while end < ELECTION_YEAR + 1:
        end += 6
    if end % 2 == 0:
        end += 1
    return end


def _dedup_members(rows):
    """One record per seat. Later rows win, matching the previous behaviour."""
    seats = {}
    for row in rows:
        chamber = clean_str(row.get("Chamber"), "")
        state = clean_str(row.get("State"), "")
        name = clean_str(row.get("Name"), "")
        district_raw = clean_str(row.get("District"), "")

        if "House" in chamber:
            num, _ = parse_district(district_raw, state)
            key = ("House", state, num if num is not None else district_raw.lower())
        elif "Vacant" in name:
            key = ("Vacant", state, district_raw)
        else:
            key = ("Senate", state, name)
        seats[key] = row
    return list(seats.values())


def _dedup_candidates(rows):
    """One record per (person, state, chamber).

    Keying on the bare name alone would merge two different people who happen
    to share a name and are running in different states.
    """
    people = {}
    for row in rows:
        name = clean_str(row.get("Name"), "")
        if not name or name == "N/A":
            continue
        office = clean_str(row.get("Office / District"), "")
        state = parse_state_abbrev(office)
        kind = _chamber_kind(clean_str(row.get("Chamber"), ""))
        people[(name.lower(), state, kind)] = row
    return list(people.values())


def _build_member(row, index):
    name = clean_str(row.get("Name"), "")
    bioguide = row.get("Bioguide ID")
    profile_id = clean_str(bioguide, "") or f"CURR_{index}"

    chamber = clean_str(row.get("Chamber"), "")
    kind = _chamber_kind(chamber)
    state = clean_str(row.get("State"), "N/A")

    district_num, district_label = (None, None)
    if kind == "House":
        district_num, district_label = parse_district(row.get("District"), state)

    status = overrides.status_override(name, clean_str(row.get("Status"), "Active Member"))
    not_seeking = overrides.is_not_seeking(status)

    # --- 2026 election derivation -------------------------------------
    seat_up = False
    end_year = None
    if kind == "House":
        # Every House seat is a two-year term, so all of them are on the
        # 2026 ballot regardless of whether the incumbent is running.
        seat_up = True
        end_year = ELECTION_YEAR + 1
    elif kind == "Senate":
        defender = overrides.SENATE_SEATS_UP_2026.get(state)
        if defender and defender.lower() in _fold(name).lower():
            seat_up = True
            end_year = ELECTION_YEAR + 1
        else:
            end_year = _senate_term_end(row.get("Term Start"))

    return {
        "id": profile_id,
        "name": name,
        "chamber": chamber,
        "party": clean_str(row.get("Party"), "Independent"),
        "state": state,
        "district": district_label or "N/A",
        "districtNum": district_num,
        "officeLabel": office_label(chamber, state, district_label),
        "status": status,
        "term_start": _term_string(row.get("Term Start"), end_year),
        "termEndYear": end_year,
        "electionYear": (end_year - 1) if end_year else None,
        "isCandidate": False,
        "seatUp2026": seat_up,
        # Retained under the original name for the page's existing filters.
        "isUpIn2026": seat_up,
        "seekingReelection2026": seat_up and not not_seeking,
        "age": parse_age(row.get("Age")),
        "birthdate": clean_str(row.get("Birthdate"), "Unknown"),
        "education": clean_str(row.get("Education"), "N/A"),
        "previous_professions": clean_str(row.get("Previous Professions"), "N/A"),
        "receipts": fmt_curr(row.get("Total Receipts")),
        "disbursements": fmt_curr(row.get("Total Disbursements")),
        "funding_sources": clean_str(row.get("Main Funding Sources"), "N/A"),
        "platforms": clean_str(row.get("Policy Focus & Platforms"), "N/A"),
        "voting_alignment": clean_str(row.get("Projected/Historical Voting Alignment"), "N/A"),
        "committees": clean_str(row.get("Committee Assignments"), "None"),
        "net_worth": clean_str(row.get("Estimated Net Worth"), "N/A"),
        "photos": member_photos(name, bioguide),
    }


def _build_candidate(row, index):
    name = clean_str(row.get("Name"), "")
    chamber_raw = clean_str(row.get("Chamber"), "Senate (Candidate)")
    kind = _chamber_kind(chamber_raw)
    office = clean_str(row.get("Office / District"), "")
    state = parse_state_abbrev(office)

    district_num, district_label = (None, None)
    if kind == "House":
        district_num, district_label = parse_district(office, state)

    status = clean_str(row.get("Status"), "Candidate")
    upcoming = str(row.get("Upcoming 2026 Primary", "")).strip().lower() == "true"
    if upcoming and "Upcoming" not in status:
        status = f"{status} (Upcoming Primary)"

    chamber = chamber_raw
    if "Candidate" not in chamber and "Winner" not in chamber:
        chamber = f"{chamber} (Candidate)"

    return {
        "id": f"CAND_{index}",
        "name": name,
        "chamber": chamber,
        "party": clean_str(row.get("Party"), "Independent"),
        "state": state,
        "district": district_label or "N/A",
        "districtNum": district_num,
        "officeLabel": office_label(chamber, state, district_label),
        "status": status,
        "term_start": clean_str(row.get("Projected Start"), "Jan. 3, 2027 (If elected)"),
        "termEndYear": None,
        "electionYear": ELECTION_YEAR,
        "isCandidate": True,
        "seatUp2026": True,
        "isUpIn2026": False,
        "seekingReelection2026": False,
        "upcomingPrimary": upcoming,
        "age": parse_age(row.get("Age")),
        "birthdate": clean_str(row.get("Birthdate"), "Unknown"),
        "education": clean_str(row.get("Education"), "N/A"),
        "previous_professions": clean_str(row.get("Previous Professions"), "N/A"),
        "receipts": fmt_curr(row.get("Campaign Receipts")),
        "disbursements": fmt_curr(row.get("Campaign Disbursements")),
        "funding_sources": clean_str(row.get("Main Funding Sources"), "N/A"),
        "platforms": first_present(
            row.get("Core Campaigning Issues & Platform Focus"),
            row.get("Policy Focus & Platforms"),
        ),
        "voting_alignment": clean_str(row.get("Projected/Historical Voting Alignment"), "N/A"),
        "committees": first_present(
            row.get("Historical Committee Assignments (If any)"),
            row.get("Committee Assignments"),
            default="None",
        ),
        "net_worth": clean_str(row.get("Estimated Net Worth"), "N/A"),
        "photos": candidate_photos(name, state),
    }


def _cross_link(profiles):
    """Link a sitting member to their own 2026 candidacy.

    Matched on folded name *and* state, so Rep. Mike Rogers (AL) is never
    linked to Senate candidate Mike Rogers (MI).
    """
    members = {}
    for profile in profiles:
        if not profile["isCandidate"]:
            members[(_fold(profile["name"]).lower(), profile["state"])] = profile

    links = 0
    for profile in profiles:
        if not profile["isCandidate"]:
            continue
        held = members.get((_fold(profile["name"]).lower(), profile["state"]))
        if held is None or held["chamber"] == profile["chamber"]:
            continue
        profile["incumbentId"] = held["id"]
        profile["incumbentSeat"] = held["officeLabel"]
        held["alsoRunningId"] = profile["id"]
        held["alsoRunningSeat"] = profile["officeLabel"]
        links += 1
    return links


def build_profiles(data):
    """Build the unified profile list from loaded roster rows.

    Returns ``(profiles, stats)``.
    """
    members = _dedup_members(data["members"])
    candidates = _dedup_candidates(data["candidates"])

    profiles = []
    for index, row in enumerate(members):
        if clean_str(row.get("Name"), "") in overrides.EXCLUDED_MEMBERS:
            continue
        profiles.append(_build_member(row, index))

    member_count = len(profiles)

    for index, row in enumerate(candidates):
        profiles.append(_build_candidate(row, index))

    links = _cross_link(profiles)

    # The page reads photo_url for the initial <img src>; keep it in step
    # with the head of the fallback chain.
    for profile in profiles:
        profile["photo_url"] = profile["photos"][0]

    voting_house = [
        p for p in profiles
        if p["chamber"] == "House" and p["state"] not in TERRITORIES
    ]
    stats = {
        "members": member_count,
        "candidates": len(profiles) - member_count,
        "total": len(profiles),
        "cross_linked": links,
        "senate_seats_up": sum(
            1 for p in profiles
            if p["seatUp2026"] and not p["isCandidate"] and "Senate" in p["chamber"]
        ),
        "voting_house": len(voting_house),
        "not_seeking": sum(
            1 for p in profiles
            if p["seatUp2026"] and not p["isCandidate"] and not p["seekingReelection2026"]
        ),
    }
    return profiles, stats
