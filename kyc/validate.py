"""Data-quality checks over the built profiles.

The site makes factual claims about real candidates, so a silent data error is
the worst failure mode. ``python build_profile_site.py --check`` runs these and
prints anything suspicious; nothing here blocks a build.
"""

import collections

from . import overrides
from .normalize import TERRITORIES, clean_str
from .photos import PLACEHOLDER

# Expected chamber sizes for the 119th Congress.
EXPECTED_SENATE_SEATS = 100
EXPECTED_VOTING_HOUSE = 435
EXPECTED_SENATE_UP_2026 = 35

# Roster rows that stand in for an unresolved primary rather than a person.
PLACEHOLDER_NAMES = ("democratic nominee", "republican nominee", "tbd", "vacant")


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

    member_names = {p["name"] for p in profiles if not p["isCandidate"]}
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
    _ = member_names
    return issues


def run(profiles, raw):
    """Run every check. Returns a list of :class:`Issue`."""
    issues = []
    issues += check_chamber_sizes(profiles)
    issues += check_seats(profiles)
    issues += check_fields(profiles)
    issues += check_placeholders(profiles)
    issues += check_overrides(profiles, raw)
    return issues


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
