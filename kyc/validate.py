"""Data-quality checks over the built profiles.

The site makes factual claims about real candidates, so a silent data error is
the worst failure mode. ``python build_profile_site.py --check`` runs these and
prints anything suspicious; nothing here blocks a build.
"""

import collections
import re

from . import overrides
from .normalize import TERRITORIES, clean_str
from .photos import PLACEHOLDER

# Expected chamber sizes for the 119th Congress.
EXPECTED_SENATE_SEATS = 100
EXPECTED_VOTING_HOUSE = 435
EXPECTED_SENATE_UP_2026 = 35

# Roster rows that stand in for an unresolved primary rather than a person.
PLACEHOLDER_NAMES = ("democratic nominee", "republican nominee", "tbd", "vacant")

# An opening tag or an HTML entity sitting in roster prose.
_MARKUP = re.compile(r"</?[a-zA-Z][^>]*>|&[a-zA-Z]{2,10};|&#\d+;")


class Issue:
    """One finding: ``level`` is ``"error"`` or ``"warn"``."""

    __slots__ = ("level", "code", "message", "detail")

    def __init__(self, level, code, message, detail=None):
        self.level = level
        self.code = code
        self.message = message
        self.detail = detail or []

    def __repr__(self):
        return f"<Issue {self.level} {self.code}>"


def _members(profiles):
    return [p for p in profiles if not p["isCandidate"]]


def check_chamber_sizes(profiles):
    issues = []
    members = _members(profiles)

    senate = [p for p in members if "Senate" in p["chamber"]]
    if len(senate) != EXPECTED_SENATE_SEATS:
        issues.append(Issue(
            "error", "senate-size",
            f"Expected {EXPECTED_SENATE_SEATS} Senate seats, found {len(senate)}",
        ))

    voting_house = [
        p for p in members if "House" in p["chamber"] and p["state"] not in TERRITORIES
    ]
    if len(voting_house) != EXPECTED_VOTING_HOUSE:
        issues.append(Issue(
            "warn", "house-size",
            f"Expected {EXPECTED_VOTING_HOUSE} voting House seats, found "
            f"{len(voting_house)} (vacancies and mid-term changes are normal)",
        ))

    up = [p for p in senate if p["seatUp2026"]]
    if len(up) != EXPECTED_SENATE_UP_2026:
        matched = {p["state"] for p in up}
        missing = sorted(set(overrides.SENATE_SEATS_UP_2026) - matched)
        issues.append(Issue(
            "error", "senate-up-2026",
            f"Expected {EXPECTED_SENATE_UP_2026} Senate seats up in 2026, matched {len(up)}",
            [f"no incumbent matched for: {', '.join(missing)}"] if missing else [],
        ))
    return issues


def check_seats(profiles):
    """Two senators per state, one House member per district."""
    issues = []
    members = _members(profiles)

    by_state = collections.Counter(
        p["state"] for p in members if "Senate" in p["chamber"]
    )
    odd = sorted(f"{st}={n}" for st, n in by_state.items() if n != 2)
    if odd:
        issues.append(Issue(
            "warn", "senate-per-state",
            f"{len(odd)} states without exactly 2 senators", odd,
        ))

    districts = collections.Counter(
        (p["state"], p["districtNum"])
        for p in members
        if "House" in p["chamber"] and p["districtNum"] is not None
    )
    dupes = sorted(f"{st}-{d} x{n}" for (st, d), n in districts.items() if n > 1)
    if dupes:
        issues.append(Issue("error", "duplicate-district",
                            f"{len(dupes)} districts with more than one member", dupes))
    return issues


def check_fields(profiles):
    """Fields whose absence degrades the page in a visible way."""
    issues = []

    no_state = [p["name"] for p in profiles if p["state"] in ("N/A", "")]
    if no_state:
        issues.append(Issue("warn", "missing-state",
                            f"{len(no_state)} profiles have no resolved state",
                            sorted(no_state)[:15]))

    no_district = [
        f"{p['name']} ({p['state']})" for p in profiles
        if "House" in p["chamber"] and p["districtNum"] is None
    ]
    if no_district:
        issues.append(Issue("warn", "missing-district",
                            f"{len(no_district)} House profiles have no district number",
                            sorted(no_district)[:15]))

    only_placeholder = [
        p["name"] for p in profiles
        if all(u == PLACEHOLDER for u in p["photos"])
    ]
    if only_placeholder:
        issues.append(Issue("warn", "no-photo-sources",
                            f"{len(only_placeholder)} profiles have no portrait URL to try",
                            sorted(only_placeholder)[:15]))

    for field, label in (("receipts", "campaign receipts"),
                         ("net_worth", "net worth"),
                         ("voting_alignment", "voting alignment")):
        missing = [p for p in profiles if p[field] == "N/A"]
        if missing:
            pct = 100 * len(missing) / max(len(profiles), 1)
            issues.append(Issue("warn", f"missing-{field}",
                                f"{len(missing)} of {len(profiles)} profiles "
                                f"({pct:.0f}%) have no {label}"))
    return issues


def check_placeholders(profiles):
    """Surface rows that stand in for an unresolved primary."""
    stand_ins = [
        f"{p['name']} - {p['state']} ({p['party']})"
        for p in profiles
        if any(tok in p["name"].lower() for tok in PLACEHOLDER_NAMES)
    ]
    if not stand_ins:
        return []
    return [Issue("warn", "placeholder-rows",
                  f"{len(stand_ins)} profiles are placeholders, not named people",
                  sorted(stand_ins))]


def check_overrides(profiles, raw):
    """Flag curated entries that no longer match anything.

    Stale overrides are invisible in the UI but quietly wrong, so they are
    worth reporting every build.
    """
    issues = []

    all_names = {p["name"] for p in profiles}

    dead_exclusions = sorted(
        n for n in overrides.EXCLUDED_MEMBERS
        if n not in {clean_str(r.get("Name"), "") for r in raw["members"]}
    )
    if dead_exclusions:
        issues.append(Issue("warn", "stale-exclusion",
                            f"{len(dead_exclusions)} excluded members are not in the roster",
                            dead_exclusions))

    dead_status = sorted(
        key for key in overrides.STATUS_OVERRIDES
        if not any(key.lower() in n.lower() for n in all_names)
    )
    if dead_status:
        issues.append(Issue("warn", "stale-status-override",
                            f"{len(dead_status)} status overrides match no profile",
                            dead_status))

    candidate_keys = {
        (p["name"], p["state"]) for p in profiles if p["isCandidate"]
    }
    dead_photos = sorted(
        f"{name} ({state})"
        for (name, state) in overrides.CANDIDATE_PHOTOS
        if (name, state) not in candidate_keys
    )
    if dead_photos:
        issues.append(Issue("warn", "stale-photo-override",
                            f"{len(dead_photos)} photo overrides match no candidate",
                            dead_photos))

    unmatched_seats = sorted(
        f"{st} ({surname})"
        for st, surname in overrides.SENATE_SEATS_UP_2026.items()
        if not any(
            p["state"] == st and "Senate" in p["chamber"] and p["seatUp2026"]
            for p in profiles if not p["isCandidate"]
        )
    )
    if unmatched_seats:
        issues.append(Issue("error", "unmatched-senate-seat",
                            f"{len(unmatched_seats)} 2026 Senate seats matched no sitting member",
                            unmatched_seats))

    # Not an error, just useful: members who are also 2026 candidates.
    duals = sorted(
        f"{p['name']}: {p['officeLabel']} -> {p['alsoRunningSeat']}"
        for p in profiles if p.get("alsoRunningSeat")
    )
    if duals:
        issues.append(Issue("warn", "dual-role",
                            f"{len(duals)} sitting members are also 2026 candidates", duals))
    return issues


def check_identity(profiles):
    """Every profile needs a unique, non-empty id and a name.

    The id is what a deep link (``#/profile/<id>``), the portrait cache and
    the race cross-links all key on. Two profiles sharing one id means a
    shared URL silently shows the wrong person.
    """
    issues = []

    ids = collections.Counter(p["id"] for p in profiles)
    dupes = sorted(f"{pid} x{n}" for pid, n in ids.items() if n > 1)
    if dupes:
        issues.append(Issue("error", "duplicate-id",
                            f"{len(dupes)} profile ids are used more than once", dupes))

    blank = [p.get("name", "?") for p in profiles if not str(p.get("id") or "").strip()]
    if blank:
        issues.append(Issue("error", "missing-id",
                            f"{len(blank)} profiles have no id", sorted(blank)[:15]))

    nameless = [p["id"] for p in profiles if not str(p.get("name") or "").strip()]
    if nameless:
        issues.append(Issue("error", "missing-name",
                            f"{len(nameless)} profiles have no name", sorted(nameless)[:15]))
    return issues


def check_races(profiles, races):
    """Race groupings must point at profiles that exist.

    The grid's By Race view resolves ids through the race lists; an id that
    matches nothing renders an empty race rather than an error, so it is
    invisible until someone notices a missing challenger.
    """
    if races is None:
        return []

    issues = []
    known = {p["id"] for p in profiles}

    dangling = sorted(
        f"{race['id']}: {pid}"
        for race in races
        for pid in race["incumbentIds"] + race["candidateIds"]
        if pid not in known
    )
    if dangling:
        issues.append(Issue("error", "dangling-race-member",
                            f"{len(dangling)} race entries name an unknown profile",
                            dangling))

    seen = collections.Counter(race["id"] for race in races)
    dupes = sorted(f"{rid} x{n}" for rid, n in seen.items() if n > 1)
    if dupes:
        issues.append(Issue("error", "duplicate-race",
                            f"{len(dupes)} race ids appear twice", dupes))

    # A profile flagged as contesting a 2026 seat but belonging to no race is
    # unreachable from the By Race view.
    grouped = {
        pid for race in races
        for pid in race["incumbentIds"] + race["candidateIds"]
    }
    orphans = sorted(
        f"{p['name']} ({p['officeLabel']})" for p in profiles
        if p.get("seatUp2026") and p["id"] not in grouped
    )
    if orphans:
        issues.append(Issue("warn", "unraced-profile",
                            f"{len(orphans)} profiles are on the 2026 ballot "
                            f"but belong to no race", orphans[:15]))
    return issues


def check_markup(profiles):
    """Roster text that would be read as markup if a render forgot to escape.

    The page escapes everything it renders, so this is a second line of
    defence rather than the only one - but a roster field carrying a tag is
    almost certainly a data-entry accident worth seeing either way.
    """
    hits = []
    for profile in profiles:
        for field, value in profile.items():
            if not isinstance(value, str):
                continue
            if _MARKUP.search(value):
                hits.append(f"{profile['name']}.{field}: {value[:60]}")
    if not hits:
        return []
    return [Issue("warn", "markup-in-data",
                  f"{len(hits)} fields contain markup-like text", sorted(hits)[:15])]


def check_geometry(profiles, geo):
    """Every state with a delegation needs a shape to click on."""
    if not geo:
        return []

    drawn = set(geo.get("states", {})) | {
        t["code"] for t in geo.get("territories", [])
    }
    represented = {
        p["state"] for p in profiles
        if p["state"] not in ("N/A", "") and not p["isCandidate"]
    }
    missing = sorted(represented - drawn)
    if missing:
        return [Issue("error", "unmapped-state",
                      f"{len(missing)} states have members but no shape on the map",
                      missing)]
    return []


# A snapshot older than this is reported. Congress changes often enough that
# a month-old membership list is a claim worth re-checking, and the whole
# point of committing the snapshot is that nothing silently goes stale.
SNAPSHOT_STALE_DAYS = 30


def check_snapshot(profiles, raw, snapshot):
    """Compare the rosters against the authoritative membership.

    The rosters are hand-curated and, measured field by field, accurate. What
    they cannot be on their own is current: two representatives seated in the
    week before this check was written were simply missing from the site, and
    nothing anywhere said so.
    """
    from . import legislators

    if not snapshot:
        return [Issue("warn", "no-snapshot",
                      "No congress_snapshot.json; membership was not checked "
                      "against the authoritative roster. Run 'congress'.")]

    issues = []

    age = legislators.snapshot_age_days(snapshot)
    if age is not None and age > SNAPSHOT_STALE_DAYS:
        issues.append(Issue(
            "warn", "stale-snapshot",
            f"The membership snapshot is {age} days old; run 'congress' to refresh it",
        ))

    drift = legislators.reconcile(raw["members"], snapshot)

    if drift.missing:
        issues.append(Issue(
            "error", "missing-member",
            f"{len(drift.missing)} people are serving in Congress but are not in "
            f"the roster",
            [f"{p['name']} ({p['chamber']} {p['state']}"
             + (f"-{p['district']}" if p["chamber"] == "House" else "")
             + f", seated {p['termStart']})" for p in drift.missing],
        ))

    if drift.departed:
        known = {n.lower() for n in overrides.EXCLUDED_MEMBERS}
        unexpected = [p for p in drift.departed if p["name"].lower() not in known]
        if unexpected:
            issues.append(Issue(
                "error", "departed-member",
                f"{len(unexpected)} roster entries are no longer serving",
                [f"{p['name']} ({p['bioguide']})" for p in unexpected],
            ))

    if drift.changed:
        issues.append(Issue(
            "error", "roster-disagrees",
            f"{len(drift.changed)} roster fields disagree with the authoritative roster",
            [f"{c['name']}: {c['field']} roster={c['roster']!r} "
             f"authoritative={c['authoritative']!r}" for c in drift.changed],
        ))

    # The curated 2026 Senate table against the terms senators are serving.
    derived = legislators.seats_up(snapshot, 2026)
    curated = overrides.SENATE_SEATS_UP_2026
    mismatched = sorted(set(derived) ^ set(curated))
    if mismatched:
        issues.append(Issue(
            "warn", "senate-table-drift",
            f"{len(mismatched)} states differ between the curated 2026 Senate "
            f"table and the real term dates",
            [f"{st}: curated={curated.get(st, '-')!r} "
             f"authoritative={derived.get(st, '-')!r}" for st in mismatched],
        ))

    _ = profiles
    return issues


# An FEC candidate id encodes the office and state it was filed for:
# S2NM00088 is a New Mexico Senate campaign, H6GA13062 a Georgia House one.
_FEC_ID = re.compile(r"^([HSP])\d([A-Z]{2})")


def check_finance(profiles, finance):
    """Every FEC figure must belong to the seat it is displayed under.

    Money attributed to the wrong person is the worst thing this site could
    do, and it would look completely normal on the page. The candidate id
    carries its own office and state, so the attribution can be checked
    against the profile rather than trusted.
    """
    if not finance:
        return []

    from . import fec

    issues = []
    wrong, unparsed = [], []

    for profile in profiles:
        record = finance.get(fec.profile_key(profile)) or {}
        candidate_id = record.get("candidate_id")
        if not candidate_id or record.get("receipts") is None:
            continue

        match = _FEC_ID.match(candidate_id)
        if not match:
            unparsed.append(f"{profile['name']}: {candidate_id}")
            continue

        office, state = match.groups()
        expected = "S" if "Senate" in profile["chamber"] else "H"
        if office != expected or state != profile["state"]:
            wrong.append(
                f"{profile['name']} ({profile['officeLabel']}) shows "
                f"{candidate_id}, filed as {office}-{state}"
                + (f" for {record.get('filed_name')}" if record.get("filed_name") else "")
            )

    if wrong:
        issues.append(Issue("error", "fec-attribution",
                            f"{len(wrong)} profiles show finance filed for another seat",
                            wrong))
    if unparsed:
        issues.append(Issue("warn", "fec-unparsed-id",
                            f"{len(unparsed)} FEC ids could not be read", unparsed))

    searched = [
        profile["name"] for profile in profiles
        if (finance.get(fec.profile_key(profile)) or {}).get("via") == "fec-search"
    ]
    if searched:
        # Not a problem, but worth seeing: these are the only ones matched by
        # a fuzzy name search rather than an authoritative id.
        issues.append(Issue("warn", "fec-name-matched",
                            f"{len(searched)} profiles were matched to the FEC by name, "
                            f"not by an authoritative id", sorted(searched)))
    return issues


def run(profiles, raw, races=None, geo=None, snapshot=None, finance=None):
    """Run every check. Returns a list of :class:`Issue`."""
    issues = []
    issues += check_identity(profiles)
    issues += check_chamber_sizes(profiles)
    issues += check_seats(profiles)
    issues += check_fields(profiles)
    issues += check_placeholders(profiles)
    issues += check_overrides(profiles, raw)
    issues += check_races(profiles, races)
    issues += check_markup(profiles)
    issues += check_geometry(profiles, geo)
    issues += check_snapshot(profiles, raw, snapshot)
    issues += check_finance(profiles, finance)
    return issues


def as_dict(issues, stats=None):
    """The report as JSON-serialisable data, for CI and tooling."""
    return {
        "errors": sum(1 for i in issues if i.level == "error"),
        "warnings": sum(1 for i in issues if i.level == "warn"),
        "stats": stats or {},
        "issues": [
            {
                "level": i.level,
                "code": i.code,
                "message": i.message,
                "detail": list(i.detail),
            }
            for i in issues
        ],
    }


def format_report(issues, verbose=False):
    """Render issues as plain text."""
    if not issues:
        return "[ok] No data-quality issues found."

    errors = [i for i in issues if i.level == "error"]
    warns = [i for i in issues if i.level == "warn"]

    lines = [f"Data quality: {len(errors)} error(s), {len(warns)} warning(s)", ""]
    for issue in errors + warns:
        marker = "ERROR" if issue.level == "error" else "warn "
        lines.append(f"  [{marker}] {issue.code}: {issue.message}")
        shown = issue.detail if verbose else issue.detail[:5]
        for item in shown:
            lines.append(f"           - {item}")
        if not verbose and len(issue.detail) > 5:
            lines.append(f"           ... {len(issue.detail) - 5} more (--verbose)")
    return "\n".join(lines)
