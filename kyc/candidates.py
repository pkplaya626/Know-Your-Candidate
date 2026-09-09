"""The 2026 candidate field, from the FEC.

The roster CSVs carried 57 hand-curated challengers. Measured against the FEC,
that was not merely thin - it made the site say something false. 436 of the 474
races rendered as "No declared challenger", and only **four** of them were
genuinely uncontested: 372 had a challenger who had already raised $25,000 or
more. A voter reading their own district was being told nobody was running
against the incumbent when somebody plainly was.

So the field comes from the FEC, which is the authoritative register of who is
running for federal office, and the roster keeps its role as editorial detail
on top.

    python build_profile_site.py field            # refresh, then report
    python build_profile_site.py field --check    # report from the cache

Where the line is drawn
-----------------------

Every threshold in the receipts distribution is smooth - there is no natural
cliff to hide behind, and picking one would be inventing an editorial
judgement and presenting it as a fact.

So the line is the statutory one. Under 52 U.S.C. 30101(2) a person *becomes*
a candidate for federal office once they raise or spend more than $5,000. That
is the legal definition of the word this site uses, not a number chosen to
make a page look tidy. Above it: 2,056 challengers holding 100.0% of all
money raised in the field, across 451 of the races.

Everyone below it is still counted. ``filing_counts`` reports every filer per
race regardless of money, so a race is never described as uncontested when it
is not - which was the actual defect.
"""

import json
import os
import time

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "fec_field.json")

CYCLE = 2026

# 52 U.S.C. 30101(2): a person becomes a "candidate" for federal office on
# raising or spending more than $5,000. See the module docstring.
STATUTORY_THRESHOLD = 5000

# The FEC's incumbent_challenge codes. "I" is the sitting member, who already
# has a profile from the roster.
INCUMBENT = "I"

_FIELDS = (
    "candidate_id", "name", "office", "state", "district_number", "party",
    "party_full", "receipts", "disbursements", "cash_on_hand_end_period",
    "coverage_end_date", "incumbent_challenge", "candidate_status",
    "has_raised_funds",
)

# Deliberately NOT carried into a funding breakdown. This endpoint reports
# `individual_itemized_contributions` - only gifts over $200 - with no
# unitemized figure to pair it with. Rendering that as "Individual 60%,
# PACs 40%" would understate individual giving and overstate the PAC share on
# every profile, which is a subtler version of the placeholder problem: a
# number that looks researched and is wrong. The per-candidate endpoint used
# for incumbents returns the full breakdown; until a profile has been through
# that, funding_sources stays "No data".


class FieldError(RuntimeError):
    pass


# ------------------------------------------------------------------ fetching

def fetch(cycle=CYCLE, log=print):
    """Every active candidate for *cycle*, with their reported totals."""
    from . import fec

    rows = []
    for office in ("H", "S"):
        page = 1
        while True:
            payload = fec._get("/candidates/totals/", {
                "election_year": cycle, "office": office,
                "is_active_candidate": True, "per_page": 100, "page": page,
                "sort": "-receipts",
            })
            results = payload.get("results") or []
            rows.extend(results)
            pagination = payload.get("pagination") or {}
            if page == 1:
                log(f"    office {office}: {pagination.get('count', 0)} filers")
            if not results or page >= pagination.get("pages", 1):
                break
            page += 1
            time.sleep(0.25)

    if not rows:
        raise FieldError(f"the FEC returned no candidates for {cycle}")
    return [{key: row.get(key) for key in _FIELDS} for row in rows]


def build_cache(rows, cycle=CYCLE):
    """One row per candidate.

    ``/candidates/totals/`` returns a row per two-year period, so a candidate
    who has filed across several cycles comes back more than once - 4,350 rows
    for 3,781 people. Left as-is that would have overstated every race's filing
    count by the number of repeat filers in it, which is precisely the sort of
    number a reader would take at face value.

    Where a candidate appears twice, the row carrying real reported totals
    wins; between two of those, the larger receipts figure does.
    """
    best = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if not candidate_id:
            continue
        rank = (
            1 if row.get("coverage_end_date") else 0,
            row.get("receipts") or 0,
        )
        if candidate_id not in best or rank > best[candidate_id][0]:
            best[candidate_id] = (rank, row)

    unique = [entry[1] for _, entry in sorted(best.items())]
    return {"cycle": cycle, "count": len(unique), "candidates": unique}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            cache = json.load(handle)
    except (ValueError, OSError):
        return None
    return cache if cache.get("candidates") else None


# ------------------------------------------------------------------- shaping

def race_id(row, year=CYCLE):
    """The race a filing belongs to, matching :mod:`kyc.races`."""
    state = row.get("state")
    if not state:
        return None
    if row.get("office") == "S":
        return f"S-{state}-{year}"
    try:
        district = int(row.get("district_number"))
    except (TypeError, ValueError):
        return None
    return f"H-{state}-{district:02d}-{year}"


def filing_counts(cache, year=CYCLE):
    """``{race_id: number of people who have filed}``, at any funding level.

    Counted from everyone, not just those over the statutory threshold. The
    point is that no race is ever described as uncontested when somebody has
    filed for it.
    """
    counts = {}
    for row in (cache or {}).get("candidates", []):
        rid = race_id(row, year)
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return counts


# Generational and professional suffixes move to the end of a display name.
_SUFFIXES = {"JR": "Jr.", "SR": "Sr.", "II": "II", "III": "III", "IV": "IV",
             "V": "V", "MD": "M.D.", "PHD": "Ph.D.", "DDS": "D.D.S.",
             "ESQ": "Esq.", "DVM": "D.V.M."}

# Titles carry no information about who the person is and read as noise in
# the middle of a name ("Brian J Mr. Burley").
_HONORIFICS = {"MR", "MRS", "MS", "MISS"}

# Surname particles stay lowercase: "Van Der Berg" is wrong, "van der Berg"
# is what people actually write.
_PARTICLES = {"VAN", "VON", "DER", "DEN", "DE", "DEL", "DELLA", "DI", "DA",
              "DU", "LA", "LE", "TER", "BIN", "AL"}


def _cap(word):
    """Capitalise one name token, respecting the shapes that break .title()."""
    upper = word.upper()
    if upper.rstrip(".") in _SUFFIXES:
        return _SUFFIXES[upper.rstrip(".")]
    if "-" in word:
        return "-".join(_cap(part) for part in word.split("-"))
    if "'" in word:
        head, _, tail = word.partition("'")
        # D'Angelo, but O'Brien too - both capitalise after the apostrophe.
        return head.capitalize() + "'" + tail.capitalize()
    if upper.startswith("MC") and len(word) > 2:
        return "Mc" + word[2:].capitalize()
    if upper.startswith("MAC") and len(word) > 4:
        return "Mac" + word[3:].capitalize()
    return word.capitalize()


def display_name(filed_name):
    """A readable name from the FEC's filed form.

    The FEC files people as ``"ARENHOLZ, ASHLEY HINSON"`` and sometimes
    ``"CARL, JERRY LEE, JR"``. Only the order and casing change here - no part
    of the filed name is ever dropped except a bare honorific, and the
    original is kept on the profile as ``filedName`` so the source is still
    visible.
    """
    text = str(filed_name or "").strip()
    if not text:
        return ""

    parts = [p.strip() for p in text.split(",") if p.strip()]
    suffix = ""
    if len(parts) >= 3:
        # LAST, FIRST MIDDLE, SUFFIX
        surname, given, suffix = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        surname, given = parts
    else:
        surname, given = "", parts[0]

    words = given.split()
    # A suffix can also trail the given names: "DOE, JOHN JR".
    while words and words[-1].upper().rstrip(".") in _SUFFIXES:
        suffix = words.pop()
    words = [w for w in words if w.upper().rstrip(".") not in _HONORIFICS]

    ordered = words + surname.split()
    rendered = []
    for index, word in enumerate(ordered):
        # A particle only stays lowercase inside the name, never at the start.
        if index and word.upper() in _PARTICLES:
            rendered.append(word.lower())
        else:
            rendered.append(_cap(word))

    if suffix:
        rendered.append(_SUFFIXES.get(suffix.upper().rstrip("."), _cap(suffix)))
    return " ".join(rendered)


# Retained under the old name for callers; the behaviour is display_name's.
_title_case = display_name


PARTY_NAMES = {
    "DEM": "Democrat", "REP": "Republican", "IND": "Independent",
    "LIB": "Libertarian", "GRE": "Green", "CON": "Constitution",
    "DFL": "Democratic-Farmer Labor", "NPA": "No Party Affiliation",
    "OTH": "Other", "UNK": "Unknown", "W": "Write-in",
}


def party_label(row):
    code = str(row.get("party") or "").upper()
    if code in PARTY_NAMES:
        return PARTY_NAMES[code]
    full = row.get("party_full")
    return _title_case(full) if full else "Independent"


def _fold(text):
    import unicodedata
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()


def to_profiles(cache, existing, threshold=STATUTORY_THRESHOLD, claimed=None):
    """Profile records for filed candidates the roster does not already have.

    Deduplicated three ways, because the same person reaches this function by
    three routes: the FEC id already attached to a profile by the finance
    lookup, the folded name and seat, and the incumbent flag. A sitting member
    running for a different seat (a House member seeking a Senate seat) is the
    case that exercises all of them at once.
    """
    from .normalize import fmt_curr, office_label
    from .photos import PLACEHOLDER

    seen_ids = {p["fecCandidateId"] for p in existing if p.get("fecCandidateId")}
    # Ids already attached to a roster profile through the finance cache.
    seen_ids |= set(claimed or ())
    seen_people = {
        (_fold(p["name"]), p["state"], "S" if "Senate" in p["chamber"] else "H")
        for p in existing
    }

    # Sitting members, by the seat they hold and their exact first and last
    # names. The FEC's incumbent flag is not always current: South Carolina's
    # class-2 seat changed hands in July 2026, and the FEC still marks Lindsey
    # Graham as the incumbent, so Darline Graham's own committee arrives here
    # looking like a challenger to herself.
    #
    # The match is deliberately exact on both names and scoped to one race,
    # which is what keeps it clear of rule 3. Alaska's Senate race contains
    # both "Dan Sullivan" (the member) and a different "Daniel J Sullivan":
    # same surname, different given name, and both survive.
    incumbents = set()
    for p in existing:
        if p.get("isCandidate"):
            continue
        words = _fold(p["name"]).split()
        if len(words) >= 2 and p.get("raceId") is not None:
            incumbents.add((p["raceId"], words[0], words[-1]))
        elif len(words) >= 2:
            senate = "Senate" in p.get("chamber", "")
            rid = race_id({
                "state": p["state"], "office": "S" if senate else "H",
                "district_number": p.get("districtNum"),
            })
            if rid:
                incumbents.add((rid, words[0], words[-1]))

    profiles, skipped = [], 0
    for row in eligible(cache, threshold):
        candidate_id = row["candidate_id"]
        senate = row.get("office") == "S"
        name = display_name(row.get("name"))
        key = (_fold(name), row["state"], "S" if senate else "H")

        words = _fold(name).split()
        same_seat_member = (
            len(words) >= 2
            and (race_id(row), words[0], words[-1]) in incumbents
        )
        if candidate_id in seen_ids or key in seen_people or same_seat_member:
            skipped += 1
            continue
        seen_ids.add(candidate_id)
        seen_people.add(key)

        district_num = None if senate else int(row.get("district_number") or 0)
        district_label = None
        if not senate:
            district_label = "AL" if district_num == 0 else str(district_num)
        chamber = f"{'Senate' if senate else 'House'} (Candidate)"

        profiles.append({
            "id": f"FEC_{candidate_id}",
            "name": name,
            # The FEC's own spelling, kept so the source of the display name
            # above is always visible.
            "filedName": row.get("name"),
            "chamber": chamber,
            "party": party_label(row),
            "state": row["state"],
            "district": district_label or "N/A",
            "districtNum": district_num,
            "officeLabel": office_label(chamber, row["state"], district_label),
            "status": "Filed with the FEC",
            "term_start": "Jan. 3, 2027 (if elected)",
            "termEndYear": None,
            "electionYear": CYCLE,
            "isCandidate": True,
            "seatUp2026": True,
            "isUpIn2026": False,
            "seekingReelection2026": False,
            "upcomingPrimary": False,
            # Everything below is genuinely unknown for a filing-derived
            # profile. Left empty so the provenance layer reports it as such
            # rather than inventing a plausible sentence.
            "age": "Unknown",
            "birthdate": "",
            "education": "",
            "previous_professions": "",
            "platforms": "",
            "voting_alignment": "",
            "committees": "",
            "net_worth": "",
            "funding_sources": "",
            "receipts": fmt_curr(row.get("receipts")),
            "disbursements": fmt_curr(row.get("disbursements")),
            "cashOnHand": fmt_curr(row.get("cash_on_hand_end_period")),
            "financeSource": "FEC",
            "financeAsOf": (row.get("coverage_end_date") or "")[:10],
            "fecCandidateId": candidate_id,
            "source": "fec-field",
            # No speculative URL chain. For a roster candidate, guessing
            # "en.wikipedia.org/.../Special:FilePath/Jane_Doe.jpg" is a cheap
            # bet that often pays. For 1,979 people who mostly have no article
            # it is roughly 4,000 requests that 404 - which took the page's
            # load event to 59 seconds and pointed all of it at Wikipedia.
            # The build-time resolver finds the ones that do exist and
            # portraits.apply_cache puts them at the head of this list.
            "photos": [PLACEHOLDER],
        })
    return profiles, skipped


def eligible(cache, threshold=STATUTORY_THRESHOLD):
    """Filings at or above the statutory threshold, incumbents excluded.

    A sitting member already has a profile built from the roster; their own
    committee filing would duplicate them.
    """
    return [
        row for row in (cache or {}).get("candidates", [])
        if (row.get("receipts") or 0) >= threshold
        and (row.get("incumbent_challenge") or "") != INCUMBENT
        and row.get("state")
        and race_id(row)
    ]
