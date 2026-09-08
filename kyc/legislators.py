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
import urllib.error
import urllib.request

SNAPSHOT_FILE = "congress_snapshot.json"

SOURCE_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)

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


def full_name(name):
    """Display name, tolerating entries with no ``official_full``."""
    if not isinstance(name, dict):
        return ""
    official = name.get("official_full")
    if official:
        return official
    parts = [name.get("first"), name.get("middle"), name.get("last")]
    return " ".join(p for p in parts if p)


def _fec_ids(entry, chamber):
    """FEC candidate ids for the seat this person currently holds.

    A long-serving senator carries their old House committee ids too, and
    attaching a House campaign's finance figures to a Senate profile is
    exactly the kind of silent, plausible-looking error this project exists
    to avoid. Senate ids start with S, House ids with H.
    """
    ids = entry.get("id", {}).get("fec") or []
    prefix = "S" if chamber == "Senate" else "H"
    matching = [i for i in ids if i.startswith(prefix)]
    # Fall back to every id rather than none: a caller that checks the state
    # can still use them, and dropping them would lose real information.
    return matching or list(ids)


def trim(entry):
    """Keep only the fields the pipeline actually reads.

    The full dataset is 1.4 MB of contact details and historical terms. The
    trimmed snapshot is small enough to commit and read in review, which is
    the point: a change in the membership of Congress should be a diff
    somebody can look at.
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
    return {
        "bioguide": bioguide.upper(),
        "name": full_name(entry.get("name", {})),
        "last": (entry.get("name") or {}).get("last", ""),
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
    }


def build_snapshot(rows, url=SOURCE_URL, fetched=None):
    """Assemble the committed snapshot from raw dataset rows."""
    people = [t for t in (trim(e) for e in rows) if t]
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


# -------------------------------------------------------------- reconciling

class Drift:
    """What the roster and the authoritative snapshot disagree about."""

    __slots__ = ("missing", "departed", "changed", "checked")

    def __init__(self):
        self.missing = []    # serving now, absent from the roster
        self.departed = []   # in the roster, no longer serving
        self.changed = []    # present in both, disagreeing on a field
        self.checked = 0

    @property
    def clean(self):
        return not (self.missing or self.departed or self.changed)

    def summary(self):
        return (
            f"{self.checked} matched, {len(self.missing)} missing, "
            f"{len(self.departed)} departed, {len(self.changed)} changed"
        )


# Roster column -> how to read the authoritative value. Only fields the
# authoritative dataset genuinely knows; it has nothing to say about
# education, net worth or committee assignments.
COMPARED_FIELDS = ("party", "state", "district", "chamber", "birthday")


def reconcile(member_rows, snapshot, district_parser=None):
    """Compare roster rows against the snapshot.

    *district_parser* is ``normalize.parse_district``; it is passed in rather
    than imported so this module stays free of the loader's import graph.
    """
    from .normalize import clean_str, parse_district

    parse = district_parser or parse_district
    authoritative = by_bioguide(snapshot)
    drift = Drift()

    seen = {}
    for row in member_rows:
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        if bioguide and bioguide != "N/A":
            seen.setdefault(bioguide, row)

    for bioguide, row in sorted(seen.items()):
        person = authoritative.get(bioguide)
        name = clean_str(row.get("Name"), "?")
        if person is None:
            drift.departed.append({"bioguide": bioguide, "name": name})
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

        for field in COMPARED_FIELDS:
            theirs = person.get(field)
            mine = ours[field]

            if field == "chamber":
                # The roster spells this "House" / "Senate" but candidate rows
                # carry suffixes, so compare by containment.
                if theirs and theirs not in mine:
                    drift.changed.append(_change(bioguide, name, field, mine, theirs))
                continue

            if field == "district":
                if person["chamber"] == "House" and mine != theirs:
                    drift.changed.append(_change(bioguide, name, field, mine, theirs))
                continue

            if field == "party":
                # "Democrat" and "Democratic" are the same party.
                if _party(mine) != _party(theirs) and mine != "Vacant":
                    drift.changed.append(_change(bioguide, name, field, mine, theirs))
                continue

            # An absent roster value is a gap to fill, not a contradiction to
            # report - the existing provenance machinery already labels it.
            if theirs and mine not in ("", "N/A", "Unknown") and mine != theirs:
                drift.changed.append(_change(bioguide, name, field, mine, theirs))

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
    "Status": lambda _p: "Active Member",
}


def row_for(person, fieldnames):
    """A roster row for a newly seated member, blank where we have no source."""
    row = {name: "" for name in fieldnames}
    for column, read in WRITABLE.items():
        if column in row:
            row[column] = read(person)
    return row


ROSTER_FOR_CHAMBER = {
    "House": "Cleaned_House_119th.csv",
    "Senate": "Cleaned_Senate_119th.csv",
}


def apply_missing(drift, root=".", today=None):
    """Append newly seated members to the roster CSVs.

    Only the columns in :data:`WRITABLE` are filled. Education, net worth,
    committees and platform are editorial research that no dataset supplies,
    so they stay empty and the provenance layer reports them as "No data" -
    which is true, and better than a plausible invention.

    Departed members are never removed automatically: a roster row may carry
    curated work, and taking someone out of Congress is a judgement that
    belongs in ``overrides.EXCLUDED_MEMBERS`` where it is visible.

    Returns ``{roster_filename: [names added]}``.
    """
    import csv

    added = {}
    for chamber, roster in ROSTER_FOR_CHAMBER.items():
        people = [p for p in drift.missing if p["chamber"] == chamber]
        if not people:
            continue

        path = os.path.join(root, roster)
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if not fieldnames:
            continue

        for person in people:
            row = row_for(person, fieldnames)
            if "Age" in row:
                row["Age"] = age_on(person.get("birthday"), today)
            rows.append(row)

        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)
        added[roster] = [p["name"] for p in people]
    return added


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
