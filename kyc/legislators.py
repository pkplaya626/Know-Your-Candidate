"""The authoritative roster of sitting members, and reconciliation against it.

The roster CSVs are hand-curated, and measurement says they are *accurate*:
checked field by field against the ``congress-legislators`` dataset, they
disagree about nobody's party, state, district, chamber or birthdate. What
they cannot be is *current*. Congress changes between builds - a member dies,
resigns, or wins a special election - and a hand-maintained CSV has no way to
notice. Two representatives sworn in during the week before this module was
written were simply absent from the site, silently.

Staleness is the same class of failure this project treats as worst: not a
crash, just a quietly wrong claim about who represents you.

So the roster keeps its place as the editorial source of truth, and this
module keeps a trimmed snapshot of the authoritative dataset beside it. The
build compares the two and says so, loudly, when they have drifted.

    python build_profile_site.py congress            # refresh, then report
    python build_profile_site.py congress --check    # report, no network
    python build_profile_site.py congress --apply    # write the drift in

The snapshot is committed, so ``build`` stays offline and a change in the
membership of Congress shows up as a reviewable diff rather than as a silent
shift in the output.
"""

import datetime
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request

SNAPSHOT_FILE = "congress_snapshot.json"

SOURCE_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)
# Everyone who has left, with the day their last term ended: how a departure
# is told from a fault in the current file (see :func:`departures`).
HISTORICAL_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-historical.json"
)
# The same project's companion files: verified social-media accounts, and
# committee rosters with each member's rank and title.
SOCIAL_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-social-media.json"
)
MEMBERSHIP_URL = (
    "https://unitedstates.github.io/congress-legislators/committee-membership-current.json"
)
COMMITTEES_URL = (
    "https://unitedstates.github.io/congress-legislators/committees-current.json"
)
COMMITTEES_FILE = os.path.join("candidate_profiles_site", "data", "committees.json")

# The handles the page links. Ids (twitter_id, youtube_id) are kept for the
# YouTube channel URL, which needs one; everything else links by handle.
SOCIAL_KEYS = ("twitter", "facebook", "instagram", "youtube", "youtube_id",
               "bluesky", "mastodon")

_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 60

# Congress convenes on 3 January. A seat is on the ballot in *year* when the
# term it is currently serving ends between that January and the next one -
# which catches both the regular class and the appointed seats whose terms end
# on election day itself.
TERM_START_MONTH_DAY = "01-03"


class LegislatorsError(RuntimeError):
    """Raised when the authoritative dataset cannot be fetched or read."""


# ------------------------------------------------------------------ fetching

def fetch(url=SOURCE_URL, timeout=_TIMEOUT):
    """Download the current-legislators dataset."""
    request = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise LegislatorsError(f"Could not download {url}: {exc}") from exc

    try:
        rows = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise LegislatorsError(f"{url} did not return JSON: {exc}") from exc

    if not isinstance(rows, list) or not rows:
        raise LegislatorsError(f"{url} returned no legislators")
    return rows


def fetch_json(url, timeout=_TIMEOUT):
    """Download one of the companion datasets; raises :class:`LegislatorsError`."""
    request = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise LegislatorsError(f"Could not download {url}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise LegislatorsError(f"{url} did not return JSON: {exc}") from exc


def social_by_bioguide(rows):
    """``{bioguide: {twitter, facebook, ...}}`` from the social-media file."""
    out = {}
    for entry in rows or []:
        bioguide = ((entry.get("id") or {}).get("bioguide") or "").upper()
        social = entry.get("social") or {}
        kept = {k: social[k] for k in SOCIAL_KEYS if social.get(k)}
        if bioguide and kept:
            out[bioguide] = kept
    return out


def full_name(name):
    """Display name, tolerating entries with no ``official_full``."""
    if not isinstance(name, dict):
        return ""
    official = name.get("official_full")
    if official:
        return official
    parts = [name.get("first"), name.get("middle"), name.get("last")]
    return " ".join(p for p in parts if p)


NAME_PART_KEYS = ("first", "middle", "last", "nickname", "suffix", "official_full")

_INITIAL = re.compile(r"^[A-Z]\.$")
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")
_QUOTED = re.compile(r'\s*"([^"]+)"')


def name_parts(name):
    """The recorded parts of a ``name`` block, absent keys left out."""
    if not isinstance(name, dict):
        return {}
    return {k: name[k].strip() for k in NAME_PART_KEYS
            if isinstance(name.get(k), str) and name[k].strip()}


def fold_name(text):
    """Case- and accent-insensitive form, so "Díaz-Balart" equals "Diaz-Balart"."""
    normalized = unicodedata.normalize("NFD", str(text or ""))
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.lower().split())


def is_initial(word):
    """True for a bare initial such as ``"C."``."""
    return bool(_INITIAL.match(str(word or "").strip()))


def _with_suffix(base, suffix):
    return f"{base}, {suffix}" if suffix else base


def goes_by(person):
    """The name congress-legislators says a member goes by, or ``None``.

    Used only for roster names that open with a bare initial ("C. Franklin"):
    the nickname with the surname when a nickname is recorded, otherwise the
    middle name with the surname when the middle name is a real name rather
    than another initial. Nothing is guessed - a member whose record holds
    neither keeps the roster spelling.
    """
    parts = (person or {}).get("nameParts") or {}
    last = parts.get("last")
    if not last:
        return None
    if parts.get("nickname"):
        return _with_suffix(f"{parts['nickname']} {last}", parts.get("suffix"))
    middle = parts.get("middle")
    if middle and not is_initial(middle.split()[0]):
        return _with_suffix(f"{middle} {last}", parts.get("suffix"))
    return None


def aliases(person, display, extra=()):
    """Other names a voter may search a member by, from their record only.

    * ``official_full`` with any quoted nickname removed
      ('Earl L. "Buddy" Carter' -> "Earl L. Carter");
    * the nickname with the surname (and suffix): "Buddy Carter";
    * the Wikipedia article title without its disambiguator
      ("Jack Reed (Rhode Island politician)" -> "Jack Reed");
    * anything in *extra*, such as a roster spelling that is no longer the
      display name.

    The caller looks *person* up by bioguide id (rules 3 and 17), never by a
    name match. Aliases that fold to the display name, or to an earlier
    alias, are dropped, so the list only carries names that add something.
    """
    person = person or {}
    parts = person.get("nameParts") or {}
    found = []
    official = parts.get("official_full")
    if official:
        found.append(_QUOTED.sub("", official))
    if parts.get("nickname") and parts.get("last"):
        found.append(_with_suffix(f"{parts['nickname']} {parts['last']}", parts.get("suffix")))
    if person.get("wikipedia"):
        found.append(_PARENTHETICAL.sub("", person["wikipedia"]))
    found.extend(extra)

    seen = {fold_name(display)}
    out = []
    for alias in found:
        alias = " ".join(str(alias or "").split())
        key = fold_name(alias)
        if alias and key not in seen:
            seen.add(key)
            out.append(alias)
    return out


def _all_fec_ids(entry):
    """Every FEC candidate id the person has filed under, both chambers, with
    any congress-legislators does not list (``overrides.MEMBER_FEC_IDS``)."""
    from . import overrides

    ids = list(entry.get("id", {}).get("fec") or [])
    bioguide = str(entry.get("id", {}).get("bioguide") or "").upper()
    extra = overrides.MEMBER_FEC_IDS.get(bioguide)
    if extra and extra[0] not in ids:
        ids.append(extra[0])
    return ids


def _fec_ids(entry, chamber):
    """FEC candidate ids for the seat this person currently holds.

    A long-serving senator carries their old House committee ids too, and
    attaching a House campaign's finance figures to a Senate profile is
    exactly the kind of silent, plausible-looking error this project exists
    to avoid. Senate ids start with S, House ids with H. A member with no id
    for the chamber they sit in has none here: the other chamber's ids used
    to stand in, which would have put a new senator's House money on their
    Senate profile (rule 20).
    """
    prefix = "S" if chamber == "Senate" else "H"
    return [i for i in _all_fec_ids(entry) if i.startswith(prefix)]


def trim(entry, social=None):
    """Keep only the fields the pipeline actually reads.

    The full dataset is 1.4 MB of contact details and historical terms. The
    trimmed snapshot is small enough to commit and read in review, which is
    the point: a change in the membership of Congress should be a diff
    somebody can look at. The current term's contact details and the
    reference ids are kept because a voter's next question after "who
    represents me" is "how do I reach them" - and those change rarely, so
    the diff stays about membership.
    """
    terms = entry.get("terms") or []
    if not terms:
        return None
    term = terms[-1]
    ids = entry.get("id", {})
    bioguide = ids.get("bioguide")
    if not bioguide:
        return None

    chamber = "Senate" if term.get("type") == "sen" else "House"
    person = {
        "bioguide": bioguide.upper(),
        "name": full_name(entry.get("name", {})),
        "last": (entry.get("name") or {}).get("last", ""),
        # The parts of the name the dataset records, so the pipeline can
        # derive the names a voter actually types (see aliases()).
        "nameParts": name_parts(entry.get("name")),
        "chamber": chamber,
        "state": term.get("state"),
        "district": term.get("district") if chamber == "House" else None,
        "party": term.get("party"),
        "termStart": term.get("start"),
        "termEnd": term.get("end"),
        "senateClass": term.get("class") if chamber == "Senate" else None,
        "birthday": (entry.get("bio") or {}).get("birthday"),
        "wikipedia": ids.get("wikipedia"),
        "fec": _fec_ids(entry, chamber),
        # Every FEC id, both chambers: a member's own candidacy for the other
        # chamber is linked through it, never through a name (rule 17).
        # ``fec`` above stays chamber-filtered, for finance.
        "fecAll": sorted(set(_all_fec_ids(entry))),
        # How the current term began and why it ends: an appointee's seat is
        # filled by a special election, and is never called "re-elected".
        "how": term.get("how"),
        "endType": term.get("end-type"),
        # How to reach the office, as the member's own term record states it.
        "url": term.get("url"),
        "phone": term.get("phone"),
        "office": term.get("office"),
        "contactForm": term.get("contact_form"),
        # Reference ids, so the page can link the record elsewhere without
        # guessing a URL from a name.
        "govtrack": ids.get("govtrack"),
        "opensecrets": ids.get("opensecrets"),
        "votesmart": ids.get("votesmart"),
        "ballotpedia": ids.get("ballotpedia"),
    }
    handles = (social or {}).get(person["bioguide"])
    if handles:
        person["social"] = handles
    return person


def build_snapshot(rows, url=SOURCE_URL, fetched=None, social=None):
    """Assemble the committed snapshot from raw dataset rows.

    *social* is the parsed social-media file, or ``None`` when it could not
    be fetched - the snapshot is still valid without it.
    """
    handles = social_by_bioguide(social) if social else {}
    people = [t for t in (trim(e, handles) for e in rows) if t]
    if not people:
        raise LegislatorsError("no usable legislators in the dataset")
    people.sort(key=lambda p: p["bioguide"])
    return {
        "source": url,
        "fetched": fetched or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(timespec="seconds"),
        "count": len(people),
        "legislators": people,
    }


# ---------------------------------------------------------------- committees

def build_committees(membership, committees, fetched=None):
    """``{"committees": {code: {...}}, "members": {bioguide: [assignments]}}``.

    *membership* is ``committee-membership-current`` (``{code: [members]}``,
    where a subcommittee code is its parent's code plus a two-digit suffix),
    *committees* is ``committees-current`` (a list with nested
    ``subcommittees``). The roster CSV carries a hand-typed committee column;
    this is the authoritative one, with rank and title.
    """
    names = {}
    for committee in committees or []:
        code = committee.get("thomas_id")
        if not code:
            continue
        names[code] = {
            "name": committee.get("name"),
            "chamber": committee.get("type"),
            "url": committee.get("url"),
        }
        for sub in committee.get("subcommittees") or []:
            sub_code = f"{code}{sub.get('thomas_id')}"
            names[sub_code] = {
                "name": sub.get("name"),
                "chamber": committee.get("type"),
                "parent": code,
            }

    members = {}
    for code, roster in (membership or {}).items():
        for seat in roster or []:
            bioguide = (seat.get("bioguide") or "").upper()
            if not bioguide:
                continue
            members.setdefault(bioguide, []).append({
                "code": code,
                "rank": seat.get("rank"),
                "party": seat.get("party"),
                "title": seat.get("title"),
            })
    for roster in members.values():
        # Full committees first, then by rank, so the page can print them in
        # the order the member's own biography would.
        roster.sort(key=lambda a: (a["code"] in names and "parent" in names[a["code"]],
                                   a["code"], a["rank"] or 999))

    return {
        "source": MEMBERSHIP_URL,
        "fetched": fetched or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(timespec="seconds"),
        "committees": names,
        "members": members,
    }


def save_committees(data, root="."):
    path = os.path.join(root, COMMITTEES_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_committees(root="."):
    path = os.path.join(root, COMMITTEES_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, OSError):
        return None
    return data if data.get("members") else None


# Above this share of committee seats held by people no longer sitting, the
# rosters are a previous Congress's: on January 3 about a fifth of the seats
# go, and congress-legislators published the 119th's rosters two weeks after
# its members (2025-01-17). A resignation or two mid-Congress stays far below.
STALE_COMMITTEE_SHARE = 0.05


def committees_current(committees, snapshot):
    """*committees* when they are the sitting Congress's rosters, else None.

    Shown as current, a previous Congress's rosters would put the members
    who left on committees and the re-elected on seats they no longer hold.
    """
    if not committees or not snapshot:
        return committees
    sitting = {p["bioguide"] for p in snapshot.get("legislators", [])}
    holders = list((committees.get("members") or {}).keys())
    if not holders:
        return None
    gone = sum(1 for b in holders if b not in sitting)
    return None if gone > STALE_COMMITTEE_SHARE * len(holders) else committees


def assignments(committees, bioguide):
    """A member's committees as ``[{name, title, side, rank, sub, parent, url}]``."""
    if not committees:
        return []
    names = committees.get("committees") or {}
    out = []
    for seat in (committees.get("members") or {}).get((bioguide or "").upper(), []):
        info = names.get(seat["code"]) or {}
        parent = names.get(info.get("parent") or "", {})
        out.append({
            "code": seat["code"],
            "name": info.get("name") or seat["code"],
            "title": seat.get("title"),
            # "majority" or "minority": which side's seat this is. A title
            # alone cannot say - "Vice Chairman" leads the minority on Senate
            # Ethics and Intelligence and is a majority post elsewhere.
            "side": seat.get("party"),
            "rank": seat.get("rank"),
            "sub": bool(info.get("parent")),
            "parent": parent.get("name"),
            "url": info.get("url") or parent.get("url"),
        })
    return out


# --------------------------------------------------------------------- store

def snapshot_path(root="."):
    return os.path.join(root, SNAPSHOT_FILE)


def save_snapshot(snapshot, root="."):
    path = snapshot_path(root)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(snapshot, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_snapshot(root="."):
    """Read the committed snapshot, or ``None`` when there is not one.

    A missing snapshot degrades reconciliation to "not checked"; it never
    fails a build, in the same way a missing atlas degrades the map.
    """
    path = snapshot_path(root)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (ValueError, OSError):
        return None
    return snapshot if snapshot.get("legislators") else None


def by_bioguide(snapshot):
    return {p["bioguide"]: p for p in (snapshot or {}).get("legislators", [])}


def snapshot_age_days(snapshot, now=None):
    """Days since the snapshot was fetched, or ``None`` if unknown."""
    stamp = (snapshot or {}).get("fetched")
    if not stamp:
        return None
    try:
        fetched = datetime.datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=datetime.timezone.utc)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now - fetched).days


# ------------------------------------------------------------------ election

def senators_up(snapshot, year=2026):
    """Senators whose current term ends at the *year* election.

    Derived from the term each senator is actually serving rather than typed
    out by hand. The regular class ends on 3 January of the following year;
    seats filled by appointment after a resignation end on election day
    itself, which is why the window opens in January of the election year
    rather than testing a single date.
    """
    window_start = f"{year}-{TERM_START_MONTH_DAY}"
    window_end = f"{year + 1}-{TERM_START_MONTH_DAY}"

    return [
        person
        for person in (snapshot or {}).get("legislators", [])
        if person["chamber"] == "Senate"
        and window_start < (person.get("termEnd") or "") <= window_end
    ]


def seats_up_ids(snapshot, year=2026):
    """Bioguide ids of the senators on the *year* ballot.

    Matching on the id rather than on a surname is the point. The hand-typed
    table said ``"SC": "Graham"``, meaning Lindsey Graham - but that seat is
    now held by Darline Graham Nordone, and the entry kept matching only
    because she happens to share the surname. A replacement without that
    coincidence would have dropped a real 2026 Senate race off the site.
    """
    return {p["bioguide"] for p in senators_up(snapshot, year)}


def seats_up(snapshot, year=2026):
    """``{state: surname}``, in the shape of the hand-curated override table.

    Kept so validation can cross-check the two against each other.
    """
    return {p["state"]: p["last"] for p in senators_up(snapshot, year)}


def term_end_year(snapshot, bioguide):
    """Calendar year in which this member's current term ends, or ``None``."""
    person = by_bioguide(snapshot).get(str(bioguide).upper())
    end = (person or {}).get("termEnd") or ""
    try:
        return int(end[:4])
    except ValueError:
        return None


# Constitutional Senate classes are fixed to a cycle: Class I was elected in
# 2024, Class II in 2026, Class III in 2028, and each repeats every six years.
SENATE_CLASSES = (1, 2, 3)


def next_election(person):
    """The general-election year in which this senator's seat is next on the
    ballot, from the term actually being served - or ``None``.

    A regular term ends on 3 January, so the seat is on the ballot the
    November before (a term ending 2029-01-03 -> 2028). A seat filled by
    appointment ends on election day itself (Jon Husted's Class III term
    ends 2026-11-03), so a term ending in November or December is decided
    that same year: a special election, two years before the class's own
    cycle. Deriving it from the date rather than from the class is what
    puts those seats on the 2026 ballot.
    """
    end = (person or {}).get("termEnd") or ""
    try:
        year, month = int(end[:4]), int(end[5:7])
    except ValueError:
        return None
    return year if month >= 11 else year - 1


def senate_class(person):
    """1, 2 or 3 for a senator in the snapshot, else ``None``."""
    value = (person or {}).get("senateClass")
    return value if value in SENATE_CLASSES else None


def senate_cycle(person):
    """``{"senateClass", "nextElection", "senateSpecial"}`` for one senator.

    ``senateSpecial`` is true when the seat is on the ballot before its
    class's regular cycle - a special election for the remainder of a term.
    The class's regular year is the next election year congruent with the
    class (Class I 2024+6k, Class II 2026+6k, Class III 2028+6k).
    """
    cls = senate_class(person)
    year = next_election(person)
    special = False
    if cls and year:
        regular = 2022 + 2 * cls
        while regular < year:
            regular += 6
        special = regular != year
    return {"senateClass": cls, "nextElection": year, "senateSpecial": special}


# -------------------------------------------------------------- reconciling

class Drift:
    """What the roster and the authoritative snapshot disagree about."""

    __slots__ = ("missing", "departed", "expected", "changed", "reseated", "twice",
                 "checked")

    def __init__(self):
        self.missing = []    # serving now, absent from the roster
        self.departed = []   # in the roster, no longer serving, no record of why
        self.expected = []   # in the roster, and the records say the term ended
        self.changed = []    # present in both, disagreeing on a field
        self.reseated = []   # present in both, serving a term begun since the row
        self.twice = []      # one bioguide on more than one roster row
        self.checked = 0

    @property
    def clean(self):
        return not (self.missing or self.departed or self.expected or self.changed
                    or self.reseated or self.twice)

    def summary(self):
        return (
            f"{self.checked} matched, {len(self.missing)} missing, "
            f"{len(self.expected)} left at the end of a term, "
            f"{len(self.departed)} departed with no record of it, "
            f"{len(self.reseated)} serving a new term, {len(self.changed)} changed"
        )


# Roster column -> how to read the authoritative value. Only fields the
# authoritative dataset genuinely knows; it has nothing to say about
# education, net worth or committee assignments.
COMPARED_FIELDS = ("party", "state", "district", "chamber", "birthday")

# What a new term may change about a seat: the chamber (a representative
# elected to the Senate), the state with it, the district (a renumbered map).
# A new term never changes a person's party or birthday, so a difference in
# either is still reported for someone to look at.
SEAT_FIELDS = ("state", "district", "chamber")


def departures(bioguides, snapshot, historical=None):
    """Which of *bioguides* - roster members absent from *snapshot* - the
    record says have left. Decided by id, never by name (rules 3 and 17).

    ``{bioguide: {"left": "YYYY-MM-DD", "via": "legislators-historical"}}``
    for each one *historical*, ``legislators-historical``, lists with a last
    term ended on or before the day *snapshot* was read: a defeat, a
    retirement, a resignation, a death. The day is the one the record gives,
    which for an appointee is the day their successor was seated, not the
    special election's.

    Nothing else counts. That a term the previous snapshot gave has ended
    is not evidence: on January 3 it is true of every House member, so a
    current file that dropped someone by mistake would archive them, and
    the error rule 16 exists for would never fire. Congress's records move
    a person from the current file to the historical one in one commit, so
    a real departure is always in both reads. Anyone else is absent with no
    record of leaving, and stays ``departed``: an error until somebody
    looks. An unavailable *historical* concludes nothing (rule 8); the
    caller passes ``None`` and nobody is archived.
    """
    read = str((snapshot or {}).get("fetched") or "")[:10]
    if not read:
        return {}
    out = {}
    for entry in historical or []:
        bioguide = str((entry.get("id") or {}).get("bioguide") or "").upper()
        terms = entry.get("terms") or []
        left = str((terms[-1] if terms else {}).get("end") or "")
        if bioguide in bioguides and left and left <= read:
            out[bioguide] = {"left": left, "via": "legislators-historical"}
    return out


def roster_ids(member_rows):
    """The bioguide ids on the roster rows."""
    from .normalize import clean_str

    ids = set()
    for row in member_rows:
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        if bioguide and bioguide != "N/A":
            ids.add(bioguide)
    return ids


def reconcile(member_rows, snapshot, district_parser=None, ended=None):
    """Compare roster rows against the snapshot.

    *district_parser* is ``normalize.parse_district``; it is passed in rather
    than imported so this module stays free of the loader's import graph.

    *ended* is :func:`departures` for the rows absent from the snapshot.
    Those it names are ``expected``, the rest ``departed``. The build reads
    no historical file, so it passes nothing and every absence is
    ``departed``: ``congress --apply`` archives the expected ones first.

    A member serving a term that began after the row's ``Term Start`` is
    ``reseated``: re-elected, elected to the other chamber, or seated in a
    renumbered district. Their seat columns are the new term's to rewrite,
    so a difference in them is not ``changed``.
    """
    from .normalize import clean_str, parse_district

    parse = district_parser or parse_district
    authoritative = by_bioguide(snapshot)
    ended = ended or {}
    drift = Drift()

    seen, counts = {}, {}
    for row in member_rows:
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        if bioguide and bioguide != "N/A":
            seen.setdefault(bioguide, row)
            counts[bioguide] = counts.get(bioguide, 0) + 1
    drift.twice = sorted(f"{clean_str(seen[b].get('Name'), '?')} ({b})"
                         for b, n in counts.items() if n > 1)

    for bioguide, row in sorted(seen.items()):
        person = authoritative.get(bioguide)
        name = clean_str(row.get("Name"), "?")
        if person is None:
            gone = {"bioguide": bioguide, "name": name,
                    "chamber": clean_str(row.get("Chamber"), "")}
            if bioguide in ended:
                drift.expected.append(dict(gone, **ended[bioguide]))
            else:
                drift.departed.append(gone)
            continue

        drift.checked += 1
        state = clean_str(row.get("State"), "")
        ours = {
            "party": clean_str(row.get("Party"), ""),
            "state": state,
            "chamber": clean_str(row.get("Chamber"), ""),
            "birthday": clean_str(row.get("Birthdate"), ""),
            "district": parse(row.get("District"), state)[0],
        }
        began = clean_str(row.get("Term Start"), "")[:10]
        renewed = bool(began) and (person.get("termStart") or "") > began
        if renewed and person["chamber"] == "House" and state == person.get("state"):
            # A four-year seat is recorded one Congress at a time: Puerto
            # Rico's term from 2025 gains a 2027 entry that is not a new
            # term, and its start is still 2025.
            from .races import house_seat_up

            try:
                renewed = house_seat_up(state, int(person["termStart"][:4]) - 1)
            except ValueError:
                pass
        moved = []

        for field in COMPARED_FIELDS:
            theirs = person.get(field)
            mine = ours[field]

            if field == "chamber":
                # The roster spells this "House" / "Senate" but candidate rows
                # carry suffixes, so compare by containment.
                if theirs and theirs not in mine:
                    moved.append(_change(bioguide, name, field, mine, theirs))
                continue

            if field == "district":
                if person["chamber"] == "House" and mine != theirs:
                    moved.append(_change(bioguide, name, field, mine, theirs))
                continue

            if field == "party":
                # "Democrat" and "Democratic" are the same party.
                if _party(mine) != _party(theirs) and mine != "Vacant":
                    drift.changed.append(_change(bioguide, name, field, mine, theirs))
                continue

            # An absent roster value is a gap to fill, not a contradiction to
            # report - the existing provenance machinery already labels it.
            if theirs and mine not in ("", "N/A", "Unknown") and mine != theirs:
                if field in SEAT_FIELDS:
                    moved.append(_change(bioguide, name, field, mine, theirs))
                else:
                    drift.changed.append(_change(bioguide, name, field, mine, theirs))

        if renewed:
            drift.reseated.append({"bioguide": bioguide, "name": name, "person": person,
                                   "termStart": began, "moved": moved})
        else:
            drift.changed.extend(moved)

    for bioguide, person in sorted(authoritative.items()):
        if bioguide not in seen:
            drift.missing.append(person)

    return drift


def _party(value):
    return "Democrat" if "Democrat" in str(value) else str(value)


def _change(bioguide, name, field, ours, theirs):
    return {
        "bioguide": bioguide,
        "name": name,
        "field": field,
        "roster": ours,
        "authoritative": theirs,
    }


# ----------------------------------------------------------------- applying

# Roster columns this module is entitled to write. Everything else - education,
# net worth, committees, platform - is editorial and stays empty rather than
# being invented, so the provenance layer reports it as "No data".
WRITABLE = {
    "Name": lambda p: p["name"],
    "Bioguide ID": lambda p: p["bioguide"],
    "Chamber": lambda p: p["chamber"],
    "Party": lambda p: p["party"],
    "State": lambda p: p["state"],
    "District": lambda p: (
        "" if p["chamber"] == "Senate"
        else ("At-Large" if p["district"] == 0 else f"District {p['district']}")
    ),
    "Birthdate": lambda p: p.get("birthday") or "",
    "Term Start": lambda p: p.get("termStart") or "",
    "Term End Date": lambda p: p.get("termEnd") or "",
    "Status": lambda _p: "Active Member",
}

# What a new term rewrites on an existing row. Everything else on it - name
# as the roster spells it, education, professions, platform, voting record -
# is the person's, not the seat's, and stays. Every status note in the roster
# is about the term that ended ("Retiring in 2026").
RESEAT_COLUMNS = ("Chamber", "State", "District", "Term Start", "Term End Date", "Status")


def row_for(person, fieldnames):
    """A roster row for a newly seated member, blank where we have no source."""
    row = {name: "" for name in fieldnames}
    for column, read in WRITABLE.items():
        if column in row:
            row[column] = read(person)
    return row


# The rosters hold whoever the snapshot says is serving, of whichever
# Congress; the file names no longer claim one.
ROSTER_FOR_CHAMBER = {
    "House": "Cleaned_House.csv",
    "Senate": "Cleaned_Senate.csv",
}

# Members who have left, each row as the roster held it on the day it was
# archived, with when they left, the record that says so, and the last
# Congress they served in.
FORMER_ROSTER = "Former_Members.csv"
FORMER_COLUMNS = ("Left Office", "Left Via", "Last Congress")


def _read_rows(path):
    import csv

    if not os.path.exists(path):
        return None, []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_rows(path, fieldnames, rows):
    """Atomically (rule 7), dropping any key the file has no column for."""
    import csv

    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _row_id(row):
    return str(row.get("Bioguide ID") or "").strip().upper()


def apply(drift, root=".", today=None):
    """Write the drift into the roster CSVs.

    * ``missing``: a row for each newly seated member, with only the columns
      in :data:`WRITABLE` filled. Education, net worth, committees and
      platform are editorial research no dataset supplies, so they stay
      empty and the provenance layer reports "No data" - which is true, and
      better than a plausible invention (rule 28).
    * ``reseated``: the :data:`RESEAT_COLUMNS` of each row serving a new
      term are rewritten from the snapshot. A member elected to the other
      chamber moves to its file, and their committee assignments are
      emptied: they described the seat they left.
    * ``expected``: each member the record says has left (:func:`departures`)
      moves, row and all, to :data:`FORMER_ROSTER`.

    ``departed`` - absent with no record of leaving - is never touched: a
    roster row carries curated work, and the build's ``departed-member``
    error is how somebody finds out. Running it twice changes nothing.

    Returns ``{"added": {roster: [names]}, "reseated": {roster: [names]},
    "archived": [names]}``.
    """
    from . import cycle

    report = {"added": {}, "reseated": {}, "archived": []}
    files, gained = {}, set()
    for chamber, roster in ROSTER_FOR_CHAMBER.items():
        fieldnames, rows = _read_rows(os.path.join(root, roster))
        if fieldnames:
            files[chamber] = {"name": roster, "fieldnames": fieldnames, "rows": rows,
                              "dirty": False}
    if not files:
        return report

    def holder(bioguide):
        for chamber, held in files.items():
            for row in held["rows"]:
                if _row_id(row) == bioguide:
                    return chamber, row
        return None, None

    for seat in drift.reseated:
        person = seat["person"]
        chamber, row = holder(seat["bioguide"])
        if row is None:
            continue
        for column in RESEAT_COLUMNS:
            if column in row:
                row[column] = WRITABLE[column](person)
        files[chamber]["dirty"] = True
        target = person["chamber"]
        if target != chamber and target in files:
            row["Committee Assignments"] = ""
            files[chamber]["rows"].remove(row)
            files[target]["rows"].append(row)
            files[target]["dirty"] = True
            gained.add(target)
            chamber = target
        report["reseated"].setdefault(files[chamber]["name"], []).append(seat["name"])

    leaving = {p["bioguide"]: p for p in drift.expected}
    if leaving:
        path = os.path.join(root, FORMER_ROSTER)
        fieldnames, former = _read_rows(path)
        if not fieldnames:
            first = next(iter(files.values()))["fieldnames"]
            fieldnames = first + [c for c in FORMER_COLUMNS if c not in first]
        kept = {(_row_id(r), r.get("Left Office")) for r in former}
        for held in files.values():
            for row in [r for r in held["rows"] if _row_id(r) in leaving]:
                gone = leaving[_row_id(row)]
                last = cycle.congress_for_date(
                    datetime.date.fromisoformat(gone["left"]) - datetime.timedelta(days=1))
                if (_row_id(row), gone["left"]) not in kept:
                    former.append(dict(row, **{"Left Office": gone["left"],
                                               "Left Via": gone["via"],
                                               "Last Congress": str(last)}))
                    kept.add((_row_id(row), gone["left"]))
                    report["archived"].append(gone["name"])
                held["rows"].remove(row)
                held["dirty"] = True
        # The archive is written before the rosters, so an interruption
        # leaves a member in both - which the next run sees and finishes -
        # never in neither.
        if report["archived"]:
            _write_rows(path, fieldnames, former)

    for chamber, held in files.items():
        present = {_row_id(r) for r in held["rows"]}
        for person in drift.missing:
            if person["chamber"] != chamber or person["bioguide"] in present:
                continue
            row = row_for(person, held["fieldnames"])
            if "Age" in row:
                row["Age"] = age_on(person.get("birthday"), today)
            held["rows"].append(row)
            held["dirty"] = True
            report["added"].setdefault(held["name"], []).append(person["name"])

    # A moved row is written into its new file before it is taken out of the
    # old one: an interruption leaves it in both (member-twice, which the
    # next run finishes), never in neither.
    for chamber in sorted(files, key=lambda c: c not in gained):
        held = files[chamber]
        if held["dirty"]:
            _write_rows(os.path.join(root, held["name"]), held["fieldnames"], held["rows"])
    return report


def age_on(birthday, today=None):
    """Whole years between *birthday* and *today*, or ``""``."""
    if not birthday:
        return ""
    try:
        born = datetime.date.fromisoformat(birthday)
    except ValueError:
        return ""
    today = today or datetime.date.today()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return str(years) if 0 < years < 110 else ""
