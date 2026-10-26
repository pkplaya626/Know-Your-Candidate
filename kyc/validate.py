"""Data-quality checks over the built profiles.

The site makes factual claims about real candidates, so a silent data error is
the worst failure mode. ``python build_profile_site.py --check`` runs these and
prints anything suspicious; nothing here blocks a build.
"""

import collections
import re
import urllib.parse

from . import overrides
from .normalize import TERRITORIES, clean_str
from .photos import PLACEHOLDER
from .portraits import wikimedia_file

# Expected chamber sizes for the 119th Congress.
EXPECTED_SENATE_SEATS = 100
EXPECTED_VOTING_HOUSE = 435

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
    """The members sitting now: never a candidate, never a former member."""
    from .record import seated

    return [p for p in profiles if seated(p)]


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

    return issues


def check_record(profiles, record, snapshot=None):
    """The frozen race record (kyc/record.py) against today's members.

    Every Senate race carries its class. Every incumbent the record names
    has a profile: on the roster, or archived when they left
    (``formerMember``, built from Former_Members.csv) - so a race never loses
    the person who held its seat. And, until the Congress the cycle elects
    is sitting, today's seats must be the record's: a race only the record
    has, or a seat only today has, is an error, except for a term that has
    ended (record.drift).
    """
    from . import cycle as cycle_mod, record as record_mod

    if not record:
        return [Issue("error", "no-record",
                      "no frozen race record; run: python build_profile_site.py record --freeze")]
    issues = []
    senate = {rid: race for rid, race in record["races"].items() if race["chamber"] == "Senate"}
    if not senate or any(not race.get("senateClass") for race in senate.values()):
        issues.append(Issue("error", "record-senate",
                            "the record's Senate races are missing or carry no class"))
    built = {p["id"] for p in profiles if not p.get("isCandidate")}
    lost = sorted(
        f"{rid} ({inc['name']}, {inc['bioguide']})"
        for rid, inc in record["incumbents"].items()
        if inc and inc["bioguide"] not in built)
    if lost:
        issues.append(Issue("error", "record-incumbent-missing",
                            f"{len(lost)} of the record's incumbents have no profile: not on "
                            f"the roster, and not archived in Former_Members.csv", lost))
    if snapshot and cycle_mod.phase(snapshot) == "campaign":
        live = record_mod.live_races(profiles, snapshot)
        apart = record_mod.drift(record, live, snapshot)
        if apart:
            issues.append(Issue("error", "record-drift",
                                f"{len(apart)} races differ between the frozen record and "
                                f"today's seats", apart))
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

    # A filed candidate the ballot page does not link to an article has no
    # portrait by design (rule 24), so they are not a finding. A member, a
    # curated challenger, or a filer with an article title and still no
    # portrait is.
    only_placeholder = [
        p["name"] for p in profiles
        if all(u == PLACEHOLDER for u in p["photos"])
        and (p.get("source") != "fec-field" or p.get("wikipedia"))
    ]
    if only_placeholder:
        issues.append(Issue("warn", "no-photo-sources",
                            f"{len(only_placeholder)} profiles have no portrait URL to try",
                            sorted(only_placeholder)[:15]))

    for field, label in (("receipts", "campaign receipts"),
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


def _new_term(profile):
    """A member serving a term begun since Election Day ("2027-01-03 - ...")."""
    from .cycle import CYCLE, general_election_day

    start = str(profile.get("term_start") or "")[:10]
    return (bool(re.match(r"\d{4}-\d{2}-\d{2}$", start))
            and start >= general_election_day(CYCLE).isoformat())


def check_overrides(profiles, raw):
    """Flag curated entries that no longer match anything.

    Stale overrides are invisible in the UI but quietly wrong, so they are
    worth reporting every build.
    """
    issues = []

    # Status notes are keyed on bioguide id only; one whose id is no longer
    # a member is invisible on the page but quietly wrong. A member serving a
    # term begun since Election Day has moved past their 2026 note, which no
    # longer applies (profiles._build_member) and can be deleted.
    member_ids = {p["id"] for p in profiles if not p.get("isCandidate")
                  and not p.get("raceRole") and not _new_term(p)}
    dead_ids = sorted(k for k in overrides.MEMBER_STATUS_BY_ID if k not in member_ids)
    if dead_ids:
        issues.append(Issue("warn", "stale-member-status",
                            f"{len(dead_ids)} id-keyed status overrides match no member",
                            dead_ids))

    # Another office's nominee is a claim about a ballot: one whose member
    # has gone shows nowhere, and after Election Day "nominee" is no longer
    # the news - the result is, read from the same page.
    dead_other = sorted(k for k in overrides.OTHER_OFFICE_NOMINEES if k not in member_ids)
    if dead_other:
        issues.append(Issue("warn", "stale-other-office",
                            f"{len(dead_other)} overrides.OTHER_OFFICE_NOMINEES entries match "
                            "no member", dead_other))
    import datetime
    from .cycle import CYCLE, general_election_day
    if overrides.OTHER_OFFICE_NOMINEES and \
            datetime.date.today() > general_election_day(CYCLE):
        issues.append(Issue("warn", "other-office-after-election",
                            f"{len(overrides.OTHER_OFFICE_NOMINEES)} members are shown as "
                            "another office's nominee after Election Day; read each result "
                            "from its source and replace or remove the entry",
                            sorted(overrides.OTHER_OFFICE_NOMINEES)))

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

    # Not an error, just useful: members who are also 2026 candidates.
    from .record import seated

    duals = sorted(
        f"{p['name']}: {p['officeLabel']} -> {p['alsoRunningSeat']}"
        for p in profiles if p.get("alsoRunningSeat") and seated(p)
    )
    if duals:
        issues.append(Issue("warn", "dual-role",
                            f"{len(duals)} sitting members are also 2026 candidates", duals))
    return issues


_CHAIR_TITLE = re.compile(r"^(co-?)?chair(man|woman|person)?$", re.I)


def check_committee_titles(profiles):
    """A minority seat titled as a committee's chair, and a curated title
    (overrides.COMMITTEE_TITLES) that no seat carries any more.

    The rosters titled the narcotics caucus's minority lead "Chairman", and
    the guide's table showed two chairmen of one panel. A minority seat
    leads its side as ranking member or vice chair; a chair title there is
    the rosters' word for a body that styles it otherwise, and needs the
    body's own word, with evidence, before it is shown as anything else.
    """
    issues = []
    styled = {(code, side, new) for (code, side, _old), (new, _why)
              in overrides.COMMITTEE_TITLES.items()}
    seen, odd = set(), []
    for p in profiles:
        for seat in p.get("committeeList") or []:
            key = (seat.get("code"), seat.get("side"), seat.get("title"))
            seen.add(key)
            if (seat.get("side") == "minority" and _CHAIR_TITLE.match(seat.get("title") or "")
                    and key not in styled):
                odd.append(f"{p['name']}: {seat['code']} {seat['title']}")
    if odd:
        issues.append(Issue("warn", "committee-minority-chair",
                            f"{len(odd)} minority seats carry a chair's title; record the "
                            "body's own style in overrides.COMMITTEE_TITLES", sorted(odd)))
    stale = sorted(f"{code} {side} {new}" for code, side, new in styled
                   if (code, side, new) not in seen)
    if stale and any(p.get("committeeList") for p in profiles):
        issues.append(Issue("warn", "stale-committee-title",
                            f"{len(stale)} curated committee titles match no seat", stale))
    held = {t for p in profiles for t in p.get("leadership") or []}
    unheld = sorted(old for old, (new, _why) in overrides.LEADERSHIP_TITLES.items()
                    if new not in held)
    if unheld and held:
        issues.append(Issue("warn", "stale-leadership-title",
                            f"{len(unheld)} curated leadership titles match no post", unheld))
    return issues


def check_pay(profiles, snapshot=None, today=None):
    """What the job pays (kyc/pay.py): a post paid more under a title the
    table does not hold would read as paid a member's rate, and a table
    whose year has passed is stale."""
    from . import cycle, pay

    try:
        sitting = cycle.snapshot_congress(snapshot) if snapshot else None
    except cycle.CycleError:
        sitting = None
    return [Issue(severity, code, message, items)
            for severity, code, message, items in pay.problems(profiles, sitting, today)]


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


def check_district_maps(races, district_maps, error=None):
    """A state's district map must describe the seats its races are for.

    The page reads "TX-9" off the map; if a state's delegation ever changed
    size, or a race were filed under a district the map does not have, every
    number on the page would point at the wrong shape and nothing would look
    wrong. Puerto Rico has no House race in 2026, so it has nothing to match.
    """
    if error:
        return [Issue("error", "district-map", f"District maps did not build: {error}")]
    if not races:
        return []
    wrong = []
    for code, state in sorted((district_maps or {}).items()):
        drawn = sorted(int(n) for n in state["plans"][-1]["districts"])
        raced = sorted(r.get("district") or 0 for r in races
                       if r.get("chamber") == "House" and r.get("state") == code)
        if raced and raced != drawn:
            wrong.append(f"{code}: map has {drawn[:3]}...{drawn[-3:]} ({len(drawn)}), "
                         f"races are for {raced[:3]}...{raced[-3:]} ({len(raced)})")
    if wrong:
        return [Issue("error", "district-map-seats",
                      f"{len(wrong)} district maps do not match their state's races", wrong)]
    return []


# A snapshot older than this is reported. Congress changes often enough that
# a month-old membership list is a claim worth re-checking, and the whole
# point of committing the snapshot is that nothing silently goes stale.
SNAPSHOT_STALE_DAYS = 30


# Days after a new Congress's terms begin before a snapshot of the old one is
# an error. refresh.yml runs every day from January 3 to 14 of the year after
# the cycle, and upstream switched the 119th in on the evening of January 3,
# so this is two scheduled runs (January 4 and 5) that failed to land it -
# with the site still naming the people who left as "who represents you".
SNAPSHOT_BEHIND_DAYS = 3


def check_snapshot(profiles, raw, snapshot, now=None):
    """Compare the rosters against the authoritative membership.

    The rosters are hand-curated and, measured field by field, accurate. What
    they cannot be on their own is current: two representatives seated in the
    week before this check was written were simply missing from the site, and
    nothing anywhere said so.
    """
    import datetime

    from . import cycle, legislators

    if not snapshot:
        return [Issue("warn", "no-snapshot",
                      "No congress_snapshot.json; membership was not checked "
                      "against the authoritative roster. Run 'congress'.")]

    issues = []
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    age = legislators.snapshot_age_days(snapshot, now)
    if age is not None and age > SNAPSHOT_STALE_DAYS:
        issues.append(Issue(
            "warn", "stale-snapshot",
            f"The membership snapshot is {age} days old; run 'congress' to refresh it",
        ))

    # The one check here that reads the clock on purpose, as stale-snapshot
    # does: every other check compares committed files with each other, so a
    # refresh that failed every day from January 3 would leave CI and the
    # deploy green on the old Congress's data.
    try:
        sitting = cycle.snapshot_congress(snapshot)
    except cycle.CycleError:
        sitting = None
    if sitting:
        today = (now or datetime.datetime.now(datetime.timezone.utc)).date()
        due = cycle.congress_start(sitting + 1) + datetime.timedelta(days=SNAPSHOT_BEHIND_DAYS)
        if today >= due:
            issues.append(Issue(
                "error", "snapshot-behind",
                f"The membership snapshot is of the {cycle.ordinal(sitting)} Congress, "
                f"and the {cycle.ordinal(sitting + 1)} has been sitting since "
                f"{cycle.congress_start(sitting + 1).isoformat()}; run 'congress --apply'",
            ))

    drift = legislators.reconcile(raw["members"], snapshot)

    if drift.twice:
        issues.append(Issue(
            "error", "member-twice",
            f"{len(drift.twice)} people are on more than one roster row", drift.twice,
        ))

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
        # Decided by id, never by a name list: `congress --apply` archives
        # whoever legislators-historical says left (legislators.departures),
        # so anyone still here has no record of it.
        issues.append(Issue(
            "error", "departed-member",
            f"{len(drift.departed)} roster entries are no longer serving; "
            f"'congress --apply' archives those the records say left",
            [f"{p['name']} ({p['bioguide']})" for p in drift.departed],
        ))

    # A new term's seat not yet written in is as wrong on the page as any
    # other disagreement (the profile is built from the row); `--apply`
    # rewrites it.
    moved = [c for seat in drift.reseated for c in seat["moved"]]
    if drift.changed or moved:
        issues.append(Issue(
            "error", "roster-disagrees",
            f"{len(drift.changed) + len(moved)} roster fields disagree with the "
            f"authoritative roster",
            [f"{c['name']}: {c['field']} roster={c['roster']!r} "
             f"authoritative={c['authoritative']!r}" for c in drift.changed]
            + [f"{c['name']}: {c['field']} roster={c['roster']!r} "
               f"authoritative={c['authoritative']!r} (a new term; 'congress --apply' "
               f"writes it)" for c in moved],
        ))

    # Only the date is behind: the profile reads the term from the snapshot.
    renewed = sorted(s["name"] for s in drift.reseated if not s["moved"])
    if renewed:
        issues.append(Issue(
            "warn", "term-not-renewed",
            f"{len(renewed)} roster rows still carry the previous term's start; "
            f"'congress --apply' writes the new one", renewed,
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
        and not profile.get("rosterFecId")
    ]
    if searched:
        # Not a problem, but worth seeing: these are the only ones matched by
        # a fuzzy name search rather than an authoritative id.
        issues.append(Issue("warn", "fec-name-matched",
                            f"{len(searched)} profiles were matched to the FEC by name, "
                            f"not by an authoritative id", sorted(searched)))
    return issues


def check_curated_candidates(profiles):
    """Every curated candidate names their own FEC filing, and every figure
    of money on the page came from the FEC.

    The curated rosters listed three governors who never filed for the
    Senate, each with a round-number total that reached the page as
    "Raised $22,000,000.00", and three nominees under a second profile the
    FEC's filing could not find. A row now carries the person's FEC id, and
    the id's own office and state must be the profile's (rule 20).
    """
    issues, missing, wrong, unnamed = [], [], [], []
    for profile in profiles:
        if not profile.get("isCandidate") or profile.get("source") == "fec-field":
            continue                        # members, and the FEC's own field
        if not re.match(r"^CAND_\d+$", profile.get("id") or ""):
            unnamed.append(f"{profile['name']} ({profile['officeLabel']}): "
                           f"ID {profile.get('id')!r}")
        fec_id = profile.get("rosterFecId") or ""
        match = _FEC_ID.match(fec_id)
        if not match:
            missing.append(f"{profile['id']} {profile['name']} ({profile['officeLabel']})"
                           + (f": {fec_id!r}" if fec_id else ""))
            continue
        office, state = match.groups()
        expected = "S" if "Senate" in profile["chamber"] else "H"
        if office != expected or state != profile["state"]:
            wrong.append(f"{profile['id']} {profile['name']} ({profile['officeLabel']}) "
                         f"names {fec_id}, filed as {office}-{state}")
    if unnamed:
        # The id is written in the row so that removing one renumbers nobody;
        # a row without it would take whatever id its position gave it.
        issues.append(Issue("error", "curated-no-id",
                            f"{len(unnamed)} curated candidates have no ID of the form "
                            f"CAND_<n> in their roster row", unnamed))
    if missing:
        issues.append(Issue("error", "curated-no-fec-id",
                            f"{len(missing)} curated candidates have no FEC candidate id; "
                            f"add it to the roster row or delete the row", missing))
    if wrong:
        issues.append(Issue("error", "curated-fec-id-seat",
                            f"{len(wrong)} curated candidates name another seat's filing", wrong))

    unsourced = [f"{p['name']} ({p['officeLabel']}): {p.get('receipts')}"
                 for p in profiles
                 if p.get("hasRealFinance") and p.get("financeSource") != "FEC"]
    if unsourced:
        issues.append(Issue("error", "finance-not-fec",
                            f"{len(unsourced)} profiles show money that did not come from the FEC",
                            unsourced))
    return issues


# Where a biography field may come from: the sources the page badges
# (assets/kyc.js FIELD_SOURCES). Anything else - a roster column typed by
# hand - is not shown (rule 86).
BIO_FIELDS = ("education", "previous_professions", "platforms")
BIO_SOURCES = {"wikipedia", "election-page", "campaign-site", "official-site",
               "member-wikipedia", "congressional-directory"}


def check_bio_sources(profiles):
    """A profile's education, previous careers or platform shown with no
    source the page can name. The rosters' columns for these were typed
    with no source and in uneven words - one member's platform "Anti-abortion
    legislation", four others' "Pro-life advocacy" (TRUST-05) - and they
    reached 537 member profiles unbadged, reading as fact."""
    unsourced = []
    for p in profiles:
        quality = p.get("quality") or {}
        for field in BIO_FIELDS:
            value = p.get(field)
            if value in (None, "") or quality.get(field):
                continue        # an absence, said as one
            if (p.get("fieldSources") or {}).get(field) not in BIO_SOURCES:
                unsourced.append(f"{p['name']} ({p.get('officeLabel')}): {field}")
    if unsourced:
        return [Issue("error", "bio-unsourced",
                      f"{len(unsourced)} biography fields would be shown with no named source",
                      unsourced)]
    return []


def check_duplicate_people(profiles):
    """Flag pairs in one race that look like the same person filed twice.

    Reported, never merged. Deciding automatically is not safe: Alaska's
    Senate race really does contain both Senator Dan Sullivan and a different
    Daniel J Sullivan, and a name-keyed merge once silently deleted six
    candidate records (rule 3). What the FEC gives us is two registrations,
    and two registrations is the honest thing to show until a person says
    otherwise.
    """
    import unicodedata

    def fold(text):
        normal = unicodedata.normalize("NFD", str(text))
        return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()

    def words(name):
        # A suffix is not a surname: Alaska's certified list prints "Daniel
        # J. Sullivan Jr.", and read as "Jr." the pair beside Senator Dan
        # Sullivan stopped being reported.
        out = [w.strip(",") for w in fold(name).split()]
        while len(out) > 1 and out[-1].rstrip(".") in ("jr", "sr", "ii", "iii", "iv"):
            out.pop()
        return out

    by_race = collections.defaultdict(list)
    for profile in profiles:
        if profile.get("raceId"):
            by_race[profile["raceId"]].append(profile)

    pairs, same = [], []
    for rid, people in sorted(by_race.items()):
        for i, first in enumerate(people):
            for second in people[i + 1:]:
                a, b = words(first["name"]), words(second["name"])
                if not a or not b or a[-1] != b[-1]:
                    continue
                line = (f"{rid}: {first['name']} ({first['id']}) / "
                        f"{second['name']} ({second['id']})")
                # The very same name twice in one race is what VA-11 showed
                # for Arthur Grahame Purves: one man, counted as two nominees.
                if a == b:
                    same.append(line)
                # Same surname, and one given name is a prefix of the other:
                # "Dan"/"Daniel", "Stephen"/"Stephen Edward".
                elif a[0] == b[0] or a[0].startswith(b[0]) or b[0].startswith(a[0]):
                    pairs.append(line)
    issues = []
    if same:
        issues.append(Issue(
            "warn", "same-name-in-race",
            f"{len(same)} races list two profiles under one name: fold them on an exact "
            "signal (rules 25, 72) or confirm they are two people", same))
    if pairs:
        issues.append(Issue(
            "warn", "possible-duplicate-person",
            f"{len(pairs)} pairs in one race may be the same person filed twice", pairs))
    return issues


# States whose primaries send more than one person per party to November.
# California and Washington run top-two primaries; Alaska sends four through.
# Everywhere else, two nominees from one party is a parsing error.
MULTI_NOMINEE_STATES = frozenset({"CA", "WA", "AK"})

# No primary decides who these are, so several can share a November ballot.
# These are results.party_key values - the key space nominees are grouped in -
# so "Independent", "unaffiliated" and "no party" all arrive as "independent".
UNPRIMARIED_PARTIES = frozenset({"independent", "all", "other", "write-in", "none"})

RACE_STATUSES = frozenset({"nominee", "eliminated", "withdrawn", "advanced", "unlisted",
                           "elected", "defeated", "runoff", "qualified"})
# On the November ballot, before and after it is counted (results.NOVEMBER).
NOVEMBER_STATUSES = frozenset({"nominee", "elected", "defeated", "runoff", "qualified"})


def _fold(text):
    import unicodedata
    normal = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def contest_of(profile):
    """The race a person is actually in: the seat they are contesting."""
    return profile.get("contestRaceId") or profile.get("raceId")


def check_results(profiles, races):
    """Primary outcomes must be internally consistent with the roster.

    The outcomes are read off Wikipedia election boxes and matched to FEC
    filers by name, and both steps can go quietly wrong: a mis-parsed box
    makes two people the Republican nominee for one seat, a loose name match
    marks a sitting member as beaten in a primary they won. Neither looks
    unusual on the page, so this is where it has to be caught.
    """
    if races is None:
        return []
    from .results import party_key

    issues = []
    by_id = {p["id"]: p for p in profiles}

    unknown = sorted(
        f"{p['name']}: {p['raceStatus']!r}" for p in profiles
        if p.get("raceStatus") and p["raceStatus"] not in RACE_STATUSES
    )
    if unknown:
        issues.append(Issue("error", "unknown-race-status",
                            f"{len(unknown)} profiles carry a race status the "
                            f"page does not know", unknown[:15]))

    contesting = collections.defaultdict(list)
    for profile in profiles:
        rid = contest_of(profile)
        if rid:
            contesting[rid].append(profile)

    crowded, empty, beaten, retired, two_won = [], [], [], [], []
    for race in races:
        if not race.get("settled"):
            continue
        people = contesting.get(race["id"], [])
        nominees = collections.defaultdict(dict)
        for p in people:
            if p.get("raceStatus") == "nominee":
                # Grouped by the line they are on in November, not the roster
                # party: NY-15's Jose Vega lost the Democratic primary and is
                # on the "Speak The Truth" line beside the Democratic nominee.
                # Keyed on the folded name: one person registered twice with
                # the FEC is one nominee, and is reported separately.
                line = p.get("ballotParty") or party_key(p["party"])
                nominees[line].setdefault(_fold(p["name"]), p)
        if race["state"] not in MULTI_NOMINEE_STATES:
            for party, found in sorted(nominees.items()):
                if len(found) > 1 and party not in UNPRIMARIED_PARTIES:
                    crowded.append(f"{race['id']}: {len(found)} {party} nominees - " +
                                   ", ".join(f"{p['name']} ({p['id']})"
                                             for p in found.values()))
        summary = race.get("results") or {}
        counted = [p for p in people if p.get("raceStatus") in NOVEMBER_STATUSES - {"nominee"}]
        if (not nominees and not counted and not summary.get("advanced")
                and not summary.get("otherNominees")):
            empty.append(race["id"])
        # One seat, one winner. Two "elected" is a page mid-edit read as a
        # result, or one person matched to two filings (rule 29).
        won = sorted({p["name"] for p in people if p.get("raceStatus") == "elected"} |
                     set(summary.get("otherElected") or ()))
        if len(won) > 1:
            two_won.append(f"{race['id']}: " + ", ".join(won))
        for pid in race["incumbentIds"]:
            member = by_id[pid]
            if member.get("contestRaceId") not in (None, race["id"]):
                continue           # judged in the race they are contesting
            status = member.get("raceStatus")
            if status in ("eliminated", "withdrawn") and member.get("seekingReelection2026"):
                beaten.append(f"{race['id']}: {member['name']} is {status} yet "
                              f"still marked as seeking re-election")
            if status in NOVEMBER_STATUSES and not member.get("seekingReelection2026"):
                retired.append(f"{race['id']}: {member['name']} is the nominee "
                               f"but the roster says not seeking re-election")

    if two_won:
        issues.append(Issue("error", "multiple-elected",
                            f"{len(two_won)} races read as electing more than one "
                            f"person", two_won))
    if crowded:
        issues.append(Issue("error", "multiple-nominees",
                            f"{len(crowded)} races give one party more than one "
                            f"nominee outside a top-two state", crowded))
    if empty:
        issues.append(Issue("warn", "settled-race-without-nominee",
                            f"{len(empty)} races are marked settled but nobody "
                            f"in them is a nominee or advanced to a runoff",
                            empty[:20]))
    if beaten:
        issues.append(Issue("error", "eliminated-incumbent-still-running",
                            f"{len(beaten)} sitting members lost or left their "
                            f"primary but still read as seeking re-election",
                            beaten))
    absent = sorted(
        f"{p['name']} ({p['officeLabel']}, {p['party']}): roster status {p['status']!r}"
        for p in profiles
        if not p["isCandidate"] and p.get("raceStatus") == "unlisted"
    )
    if absent:
        issues.append(Issue("warn", "member-not-on-ballot",
                            f"{len(absent)} sitting members are absent from their "
                            f"own party's decided primary and the November ballot; "
                            f"shown as not seeking re-election", absent))
    if retired:
        issues.append(Issue("warn", "nominee-marked-retiring",
                            f"{len(retired)} sitting members are nominees but the "
                            f"roster says they are not seeking re-election",
                            retired))
    return issues


def check_results_pages(cache):
    """What the last ``results`` run could not read, and what it overrode.

    A results page that is missing, unreadable or split into pages the
    parser did not follow leaves every race on it showing everyone who ever
    filed, and nothing on the site looks wrong. California's split did that
    to 52 races; the delegates' "the District of Columbia" titles did it to
    Norton and Plaskett.
    """
    if not cache:
        return []
    issues = []
    unparsed = list(cache.get("unparsedPages") or [])
    if unparsed:
        issues.append(Issue("error", "results-page-unparsed",
                            f"{len(unparsed)} results pages exist but have no district "
                            f"sections the parser can read; none of their races "
                            f"have results", unparsed))
    missing = list(cache.get("missingPages") or [])
    if missing:
        issues.append(Issue("warn", "results-page-missing",
                            f"{len(missing)} settled seats have no Wikipedia results "
                            f"page under any title asked for", missing))
    failed = list(cache.get("fetchFailed") or [])
    if failed:
        issues.append(Issue("warn", "results-fetch-failed",
                            f"{len(failed)} results pages could not be fetched; "
                            f"their races were left as they were", failed))
    unclear = [f"{name} ({rid}): the page names {', '.join(names)}"
               for name, rid, names in cache.get("unclear") or []]
    if unclear:
        # Shown with no result rather than "Not on the primary ballot": 36
        # people the page names under a nickname, six of them November
        # nominees, were told they were not on it.
        issues.append(Issue("warn", "results-name-unresolved",
                            f"{len(unclear)} filers in decided races may be named on the "
                            f"results page under another spelling: off the November ballot "
                            f"where every such name lost or withdrew, otherwise undecided. "
                            f"Settle each with an evidenced overrides.RESULT_NAMES entry",
                            sorted(unclear)))
    # Three days after Election Day a race the page has not called is worth a
    # person's look: Alaska's ranked-choice count is published as a table,
    # not an Election box, and would read "Awaiting result" for weeks.
    from .results import general_day, NOMINEE, NOVEMBER, QUALIFIED
    import datetime
    as_of = cache.get("asOf") or ""
    if as_of and as_of > (general_day() + datetime.timedelta(days=3)).isoformat():
        settled = set(NOVEMBER[1:]) - {QUALIFIED}
        uncalled = sorted(
            rid for rid, race in (cache.get("races") or {}).items()
            if race.get("source") == "qualified" or (
                (race.get("decided") or {}).get("general")
                and NOMINEE in (race.get("status") or {}).values()
                and not settled & set((race.get("status") or {}).values())))
        if uncalled:
            issues.append(Issue("warn", "general-uncalled",
                                f"{len(uncalled)} races have no November result on their "
                                f"page three days after Election Day; check the page's "
                                f"format (Alaska's ranked-choice table is not an Election "
                                f"box; Louisiana's open-primary page may not mark its result "
                                f"in one either)", uncalled))
    listed = cache.get("qualified") or {}
    if listed.get("carried"):
        issues.append(Issue("warn", "qualified-list-stale",
                            f"Louisiana's qualified list could not be read on {as_of}; the "
                            f"list read on {listed.get('fetched')} is shown", listed.get("races")))
    overridden = [n["text"] for n in cache.get("calendarNotes") or []
                  if isinstance(n, dict) and n.get("kind") == "open-primary"]
    if overridden:
        issues.append(Issue("warn", "calendar-override-disagrees",
                            f"{len(overridden)} seats use overrides.OPEN_PRIMARY_SEATS "
                            f"where the FEC calendar says otherwise; re-check the "
                            f"source when the FEC updates", overridden))
    return issues


def check_seats_contested(profiles):
    """Where the FEC and the roster disagree about who is running for what.

    A re-seated challenger is a roster row to correct; a member linked to a
    candidacy of a different party is almost certainly two people who share
    a name, and the link would mark the wrong seat open.
    """
    issues = []
    by_id = {p["id"]: p for p in profiles}

    reseated = sorted(
        f"{p['name']}: roster says {p['rosterSeat']}, FEC filing is for {p['officeLabel']}"
        for p in profiles if p.get("rosterSeat")
    )
    if reseated:
        issues.append(Issue("warn", "roster-seat-disagrees-with-fec",
                            f"{len(reseated)} roster challengers are filed for a "
                            f"different seat than the roster gives them; the "
                            f"filing was used", reseated))

    from .results import party_key

    switched = sorted(
        f"{p['name']} ({p['officeLabel']}): roster/FEC say {p['party']}, "
        f"the ballot says {p['ballotParty']}"
        for p in profiles
        if p.get("ballotParty") and party_key(p["party"]) != p["ballotParty"]
        and p["ballotParty"] in ("democratic", "republican", "libertarian",
                                 "green", "independent")
        and party_key(p["party"]) in ("democratic", "republican", "libertarian",
                                      "green", "independent")
    )
    if switched:
        issues.append(Issue("warn", "ballot-party-disagrees",
                            f"{len(switched)} profiles carry a party the ballot "
                            f"does not; the roster row or FEC record is stale",
                            switched))

    crossed = []
    for member in profiles:
        other = by_id.get(member.get("alsoRunningId"))
        if other and other["party"] != member["party"]:
            crossed.append(f"{member['name']} ({member['officeLabel']}, {member['party']}) "
                           f"-> {other['name']} ({other['officeLabel']}, {other['party']})")
    if crossed:
        issues.append(Issue("error", "cross-party-link",
                            f"{len(crossed)} members are linked to a candidacy under "
                            f"a different party - likely two people with one name",
                            crossed))
    return issues


def check_campaign_blocklist(campaigns):
    """Blocklist entries must still bar something, or they are stale.

    A dead entry left behind after a committee files a new address is
    harmless; one keyed on a mistyped host never blocked anything at all.
    """
    if campaigns is None:
        return []
    from .campaigns import blocked_sites

    used = {key for _, _, key in blocked_sites(campaigns)}
    stale = sorted(k for k in overrides.BLOCKED_CAMPAIGN_HOSTS if k not in used)
    if not stale:
        return []
    return [Issue("warn", "stale-campaign-block",
                  f"{len(stale)} blocked campaign hosts match no cached site", stale)]


def check_campaign_sites(profiles, enrichment):
    """Name every committee site the enrichment pass would not vouch for.

    A site that reads as hijacked or parked has already been taken off the
    profile by :func:`kyc.enrich.apply_cache`; it is listed so a person can
    confirm it and record the decision in ``BLOCKED_CAMPAIGN_HOSTS``. One that
    answered but does not name the candidate stays linked - most are pages
    built entirely in JavaScript - and is listed so a moved or lapsed domain
    is seen rather than shown.
    """
    if not enrichment:
        return []
    from .enrich import problems

    found = problems(profiles, enrichment)
    issues = []
    if found["withdrawn"]:
        issues.append(Issue("warn", "campaign-site-withdrawn",
                            f"{len(found['withdrawn'])} committee website(s) read as hijacked or "
                            "parked and are not linked; confirm and add to "
                            "BLOCKED_CAMPAIGN_HOSTS", found["withdrawn"]))
    if found["unconfirmed"]:
        issues.append(Issue("warn", "campaign-site-unconfirmed",
                            f"{len(found['unconfirmed'])} committee website(s) are linked but "
                            "their page did not confirm the candidate", found["unconfirmed"]))
    if found["compromised"]:
        issues.append(Issue("warn", "campaign-site-compromised",
                            f"{len(found['compromised'])} campaign website(s) hide gambling links "
                            "in their own pages; still linked", found["compromised"]))
    return issues


def _photograph(url):
    parts = wikimedia_file(url)
    return (parts[1], parts[2], urllib.parse.unquote(parts[3])) if parts else None


def check_photo_sets(profiles):
    """A profile's srcset lists sizes of its own portrait and nothing else.

    The browser picks an entry by screen density, so an entry from another
    file shows a reader on a different screen a different photograph, and
    nothing on either screen looks wrong. congress.gov, the House Clerk and
    the unitedstates project each hold a different photograph of most
    members, which is why only Wikimedia's sizes of one file qualify.
    """
    mixed = []
    for p in profiles:
        entries = p.get("photoSet") or []
        if not entries:
            continue
        head = _photograph((p.get("photos") or [None])[0])
        if head is None or any(_photograph(url) != head for _width, url in entries):
            mixed.append(f"{p['name']} ({p['state']})")
    if not mixed:
        return []
    return [Issue("error", "photo-set-mixes-photographs",
                  f"{len(mixed)} srcset(s) list a file other than the portrait they size",
                  mixed)]


def check_photo_credits(profiles):
    """Every photograph a profile shows says whose it is, and a Commons
    file says on what licence (rule 87).

    148 of 381 Wikimedia portraits were CC BY or CC BY-SA, whose terms
    require the author, the licence and a link beside the photograph, and
    none was credited; the footer credited every portrait to Congress.gov.
    A portrait with no credit, or a Commons portrait whose file's licence
    was never read, fails: run ``portraits`` to read it."""
    from .photos import PLACEHOLDER

    uncredited, unlicensed = [], []
    for p in profiles:
        first = (p.get("photos") or [PLACEHOLDER])[0]
        if first == PLACEHOLDER:
            continue
        credit = p.get("photoCredit") or {}
        if wikimedia_file(first) and not credit.get("licence"):
            unlicensed.append(f"{p['id']} ({p['name']}): {first}")
        elif not credit.get("by") and not credit.get("licence"):
            uncredited.append(f"{p['id']} ({p['name']}): {first}")
    issues = []
    if uncredited:
        issues.append(Issue("error", "photo-uncredited",
                            f"{len(uncredited)} portraits do not say whose photograph they are",
                            uncredited))
    if unlicensed:
        issues.append(Issue("error", "photo-licence-missing",
                            f"{len(unlicensed)} Wikimedia Commons portraits have no recorded "
                            "licence; run 'portraits' to read their files' descriptions",
                            unlicensed))
    return issues


def check_guessed_photos(profiles):
    """No portrait is reached by a name (rule 24), on any profile.

    ``Special:FilePath/<Name>.jpg`` serves whoever uploaded under the name:
    the New Jersey and Oregon Republican Senate nominees showed a rugby
    player and an Olympic kayaker, and every member's chain ended in the same
    guess. A portrait found by searching a name is the same guess one step
    removed ("wikipedia-search" in the portrait cache).
    """
    from .photos import is_guessed

    found = []
    for p in profiles:
        guesses = [u for u in p.get("photos") or [] if is_guessed(u)]
        if guesses:
            found.append(f"{p['id']} ({p['name']}): {guesses[0]}")
        elif p.get("photoSource") == "wikipedia-search":
            found.append(f"{p['id']} ({p['name']}): found by a search")
    if not found:
        return []
    return [Issue("error", "photo-guessed",
                  f"{len(found)} profiles carry a portrait reached by a name, not an id "
                  "or a ballot-linked article", found)]


# Every profile field that holds an address the page links or loads.
URL_FIELDS = ("website", "contactForm", "campaignSite", "electionPageSite",
              "disclosureUrl", "campaignIssuesUrl", "photo_url")


def bad_url(url):
    """True unless *url* is an http(s) address with a host. Rep. Randy
    Fine's contact form arrived from congress-legislators as "hhttps://...":
    the browser treats that as an unknown scheme and the link goes nowhere."""
    import urllib.parse

    text = str(url or "")
    if not text or any(c.isspace() for c in text):
        return True
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return True
    return parts.scheme not in ("http", "https") or "." not in (parts.hostname or "")


def check_outbound_urls(profiles):
    """Every outbound address on a profile is one a browser can open."""
    from .photos import PLACEHOLDER

    found = []
    for p in profiles:
        urls = [(field, p.get(field)) for field in URL_FIELDS
                if p.get(field) and p.get(field) != PLACEHOLDER]
        urls += [("photos", u) for u in p.get("photos") or [] if u != PLACEHOLDER]
        urls += [("photoSet", size[1]) for size in p.get("photoSet") or []
                 if isinstance(size, (list, tuple)) and len(size) > 1]
        for field, url in urls:
            if bad_url(url):
                found.append(f"{p['id']} ({p['name']}) {field}: {url!r}")
    if not found:
        return []
    return [Issue("error", "url-malformed",
                  f"{len(found)} outbound addresses are not http(s) with a host; correct "
                  "the source or record the fix in overrides with evidence", found)]


def check_member_link_overrides(snapshot):
    """The dated corrections to members' links still match what they correct.

    ``MEMBER_CONTACT_FORMS``, ``YOUTUBE_LEGACY_NAMES``,
    ``YOUTUBE_HANDLE_CORRECTIONS`` and ``DEAD_X_HANDLES`` each apply only while congress-legislators holds exactly the value they
    were checked against; an entry the source has moved past is stale, and a
    YouTube legacy name nobody has checked is linked at /user/ unverified.
    """
    from . import overrides
    from .profiles import _CHANNEL_ID

    people = {p.get("bioguide"): p for p in (snapshot or {}).get("legislators") or []}
    if not people:
        return []
    stale, unchecked = [], []
    for bioguide, (value, _fixed, _why) in overrides.MEMBER_CONTACT_FORMS.items():
        if (people.get(bioguide) or {}).get("contactForm") != value:
            stale.append(f"MEMBER_CONTACT_FORMS {bioguide}: the source no longer holds {value!r}")
    for bioguide, (value, _shape, _why) in overrides.YOUTUBE_LEGACY_NAMES.items():
        if ((people.get(bioguide) or {}).get("social") or {}).get("youtube") != value:
            stale.append(f"YOUTUBE_LEGACY_NAMES {bioguide}: the source no longer holds {value!r}")
    for bioguide, (value, _fixed, _date, _why) in overrides.YOUTUBE_HANDLE_CORRECTIONS.items():
        if ((people.get(bioguide) or {}).get("social") or {}).get("youtube") != value:
            stale.append(f"YOUTUBE_HANDLE_CORRECTIONS {bioguide}: the source no longer "
                         f"holds {value!r}")
    for bioguide, (handle, _date, _why) in overrides.DEAD_X_HANDLES.items():
        social = (people.get(bioguide) or {}).get("social") or {}
        if social.get("twitter") != handle or social.get("twitter_id"):
            stale.append(f"DEAD_X_HANDLES {bioguide}: the source no longer holds {handle!r} "
                         "without an id")
    for bioguide, person in sorted(people.items()):
        social = person.get("social") or {}
        value = social.get("youtube")
        if (value and not social.get("youtube_id") and not value.startswith("@")
                and not _CHANNEL_ID.match(value)
                and (overrides.YOUTUBE_LEGACY_NAMES.get(bioguide) or (None,))[0] != value):
            unchecked.append(f"{bioguide} ({person.get('name')}): youtube {value!r}")
    issues = []
    if stale:
        issues.append(Issue("warn", "stale-link-override",
                            f"{len(stale)} member link corrections no longer match the source",
                            stale))
    if unchecked:
        issues.append(Issue("warn", "youtube-unchecked",
                            f"{len(unchecked)} YouTube legacy names are linked at /user/ "
                            "unchecked; check each and record it in YOUTUBE_LEGACY_NAMES",
                            unchecked))
    return issues


def check_wikipedia_withheld(profiles):
    """Ballot-page links that lead somewhere other than the person's article.

    "Brian McGinnis" redirects to a protest, "Elijah Manley" to a party's
    primaries, one link was a party's own article. enrich withholds each
    (rule 33); listed so a person can see what the page linked.
    """
    found = sorted(
        f"{p['id']} ({p['name']}): {w.get('title')!r} -> "
        f"{w.get('landsOn') or 'no article'}"
        for p in profiles for w in [p.get("wikipediaWithheld")] if w)
    if not found:
        return []
    return [Issue("warn", "wikipedia-not-about",
                  f"{len(found)} Wikipedia links from election pages lead to an article "
                  "not about the person; withheld", found)]


def check_future_coverage(profiles, today=None):
    """A profile's money reported through a date after the build.

    Copied from the filer's report (a committee files "through December 31"
    in October); the page shows it as filed, and this lists it.
    """
    import datetime

    if today is None:
        from .emit import build_timestamp
        today = datetime.date.fromisoformat(build_timestamp()[:10])
    found = sorted(f"{p['id']} ({p['name']}): through {p['financeAsOf']}"
                   for p in profiles
                   if (p.get("financeAsOf") or "") > today.isoformat())
    if not found:
        return []
    return [Issue("warn", "finance-future-coverage",
                  f"{len(found)} profiles' FEC figures report coverage ending after "
                  f"{today.isoformat()}; shown as filed", found)]


def check_photo_evidence(profiles, portraits=None, enrichment=None):
    """A photograph reached through a page - a campaign's (rule 38), a
    legislature's or a Wikidata item (``nominee_photos``) - carries in its
    cache the page that ties it to the person, the words that name them
    beside it, the day it was read and its bytes and pixel size, and a note
    where it is over the caps and shown at full size (rule 87). One shown
    without them fails: the cache cannot say why it is this person's."""
    from . import nominee_photos
    from .photos import too_heavy
    from .portraits import profile_key

    portraits, enrichment = portraits or {}, enrichment or {}
    people = enrichment.get("people") or {}
    found = []
    for p in profiles:
        source, shown = p.get("photoSource"), (p.get("photos") or [None])[0]
        if source in nominee_photos.ROUTES:
            record = portraits.get(profile_key(p)) or {}
            found += nominee_photos.problems({profile_key(p): record})
        elif source == "campaign-site":
            entry = people.get(p.get("id")) or {}
            record = next((r for r in (entry.get("site"), entry.get("listed"),
                                       entry.get("drawn"))
                           if r and r.get("portrait") == shown), {})
            weight = record.get("portraitWeight") or {}
            missing = [f for f in ("portraitPage", "portraitEvidence", "portraitRead")
                       if not record.get(f)]
            if not all(weight.get(k) for k in ("bytes", "width", "height")):
                missing.append("weight")
            elif too_heavy(weight) and not (record.get("portraitHeavy") or [{}])[0].get("kept"):
                missing.append("note that it is over the caps")
            if missing:
                found.append(f"{p['name']} (campaign-site): no {', '.join(missing)}")
    if not found:
        return []
    return [Issue("error", "photo-unevidenced",
                  f"{len(found)} photographs are shown without the page, the words naming the "
                  "person, the day read or the size their cache must record; run 'enrich' or "
                  "'portraits' to read them again", sorted(found))]


# Where a profile's photograph may be a picture not made in a studio: a
# campaign's site, a Commons file by an article, a cross-link or Wikidata.
_NOT_A_STUDIO = ("campaign-site", "wikipedia", "cross-link", "wikidata-fec")


def check_refusal_fallbacks(profiles, portraits=None):
    """A photograph shown because a person refused the one before it must
    itself have been looked at (the PR #139 review). Refusing James
    Talarico's Commons crop for someone at its edge promoted his campaign's
    photograph of him helping a child in a classroom, which nobody had
    seen. A profile whose portrait record a person refused (``photos.refused``),
    or whose record replaced one they refused (``nominee_photos.replacing``),
    and which now shows a photograph from a route that can take a picture
    not made in a studio, is named until that photograph is in
    ``overrides.SEEN_AFTER_A_REFUSAL`` (looked at: the person alone) or
    ``NOT_A_PORTRAIT``."""
    from . import nominee_photos
    from .portraits import profile_key

    seen = getattr(overrides, "SEEN_AFTER_A_REFUSAL", {})
    found = []
    for p in profiles:
        shown = (p.get("photos") or ["placeholder"])[0]
        if shown in (None, "placeholder") or p.get("photoSource") not in _NOT_A_STUDIO:
            continue
        record = (portraits or {}).get(profile_key(p)) or {}
        refused = nominee_photos.replaced(record)
        if not refused:
            continue
        if any(u in seen for u in (shown, record.get("original")) if u):
            continue
        found.append(f"{p['name']} ({p.get('officeLabel') or p.get('state')}): shows {shown} "
                     f"({p.get('photoSource')}) since {refused[0]} was refused")
    if not found:
        return []
    return [Issue("warn", "portrait-fallback-unseen",
                  f"{len(found)} profiles show a photograph that came forward when a person "
                  "refused the one before it; look at each, and record it in "
                  "overrides.SEEN_AFTER_A_REFUSAL or NOT_A_PORTRAIT", sorted(found))]


def check_portrait_overrides(enrichment, elsewhere=()):
    """Every ``NOT_A_PORTRAIT`` entry must still be an image some site offers.

    Once the site drops the image, the entry guards nothing; once its URL is
    mistyped, it never did. *elsewhere* is what the other routes that ask
    the list reached (a court's page, a statewide candidate's guide or
    Commons file: ``court_photos.refused_offered``,
    ``statewide_photos.doubted``).
    """
    if not enrichment:
        return []
    offered = set(elsewhere or ())
    for entry in (enrichment.get("people") or {}).values():
        for key in ("site", "listed", "drawn"):
            record = entry.get(key) or {}
            offered.update([record.get("portrait")] + list(record.get("notPortraits") or [])
                           + [h.get("url") for h in record.get("portraitHeavy") or []])
    stale = sorted(u for u in overrides.NOT_A_PORTRAIT if u not in offered)
    issues = []
    if stale:
        issues.append(Issue("warn", "stale-portrait-override",
                            f"{len(stale)} NOT_A_PORTRAIT entries match no image a cached "
                            "site offers", stale))
    unused = sorted(f"{pid}: {entry['url']}" for pid, entry in overrides.CAMPAIGN_PORTRAITS.items()
                    if entry["url"] not in offered)
    if unused:
        issues.append(Issue("warn", "stale-campaign-portrait",
                            f"{len(unused)} CAMPAIGN_PORTRAITS entries name no portrait a cached "
                            "site gives: the page no longer draws it, or the site no longer "
                            "reads as the campaign's", unused))
    return issues


def check_odds(races, odds, today=None):
    """Market prices and polling averages: attributed, current, coherent.

    A market's outcome label that names nobody in its race is shown as the
    party the market resolves on and listed here: on 2026-10-03 Kalshi's
    Louisiana ticker held Kentucky's race, labelled "Andy Barr" and "Charles
    Booker". A Senate race no market covers, prices that do not add up to
    about a dollar, and a cache older than a week are reported too. House
    races without a market are many and expected; only their count is shown
    by the build.
    """
    if not odds or races is None:
        return []
    import datetime

    from .odds import SOURCES, STALE_DAYS

    issues, mismatched, incoherent = [], [], []
    entries = odds.get("races") or {}
    for rid, entry in sorted(entries.items()):
        for market in entry.get("markets") or []:
            source = SOURCES.get(market.get("source"), market.get("source"))
            for outcome in market.get("outcomes") or []:
                # Under a cent is an eliminated candidate's market nobody
                # closed (Alaska's, after its August primary), not an error;
                # a nominee too small to have a profile here is a gap in our
                # data, counted by the build, not a conflict in theirs.
                if (outcome.get("mismatch") and outcome.get("conflict")
                        and (outcome.get("price") or 0) >= 0.01):
                    mismatched.append(f"{rid} {source}: \"{outcome.get('marketLabel')}\" "
                                      f"names nobody in the race; shown as {outcome.get('label')}")
            total = sum(o.get("price") or 0 for o in market.get("outcomes") or [])
            if not 0.85 <= total <= 1.2:
                incoherent.append(f"{rid} {source}: prices add up to {total:.2f}")
    if mismatched:
        issues.append(Issue("warn", "odds-label-mismatch",
                            f"{len(mismatched)} market label(s) name someone other than "
                            "this site's candidate of that party",
                            mismatched))
    if incoherent:
        issues.append(Issue("warn", "odds-incoherent",
                            f"{len(incoherent)} market(s) whose prices do not add up", incoherent))
    uncovered = [r["id"] for r in races if r.get("chamber") == "Senate"
                 and not (entries.get(r["id"]) or {}).get("markets")]
    if uncovered:
        issues.append(Issue("warn", "odds-uncovered",
                            f"{len(uncovered)} Senate race(s) with no market from either source",
                            uncovered))
    unknown = sorted(set(entries) - {r["id"] for r in races})
    if unknown:
        issues.append(Issue("warn", "odds-unknown-race",
                            f"{len(unknown)} race id(s) in the odds cache are not on the ballot "
                            "any more; run 'odds'", unknown))
    fetched = str(odds.get("fetched") or "")[:10]
    if today is None:
        from .emit import build_timestamp
        today = datetime.date.fromisoformat(build_timestamp()[:10])
    try:
        age = (today - datetime.date.fromisoformat(fetched)).days
    except ValueError:
        age = None
    if age is not None and age > STALE_DAYS:
        issues.append(Issue("warn", "odds-stale",
                            f"market prices are {age} days old; run 'odds'", [fetched]))
    return issues


def check_field_screen(field, today=None):
    """List every FEC filing the build set aside, and coverage from the future.

    :func:`kyc.candidates.screen` removes stale registrations (no report
    since the cycle began - Jim Inhofe's 2022 committee) and filings for races
    that do not exist this year (a Senate filing from a state with no seat
    up, GA-23 in a state with 14 districts). Dropping data is exactly the
    kind of change that must never be silent, so each one is named here.

    A coverage end date after today is a filing error at the FEC or a
    misread field here; either way the totals beside it are not what they
    claim to be.
    """
    if not field:
        return []
    import datetime

    if today is None:
        from .emit import build_timestamp
        today = datetime.date.fromisoformat(build_timestamp()[:10])
    from .candidates import race_id

    def line(row):
        return (f"{row.get('name')} ({row.get('candidate_id')}, {race_id(row)}, "
                f"reported through {row.get('coverage_end_date') or 'nothing'})")

    issues = []
    screened = field.get("screened") or {}
    stale = screened.get("stale") or []
    if stale:
        issues.append(Issue(
            "warn", "field-stale",
            f"{len(stale)} FEC registrations listing 2026 have reported nothing since "
            f"{screened.get('cycleStart')}; not shown as candidates or counted as filed",
            sorted(line(r) for r in stale)))
    phantom = screened.get("phantom") or []
    if phantom:
        issues.append(Issue(
            "warn", "field-phantom-race",
            f"{len(phantom)} FEC filings are for seats not on the 2026 ballot "
            f"(no Senate seat up, or a district the state does not have); dropped",
            sorted(line(r) for r in phantom)))
    future = [
        r for r in field.get("candidates", [])
        if (r.get("coverage_end_date") or "")[:10] > today.isoformat()
    ]
    if future:
        issues.append(Issue(
            "warn", "field-future-coverage",
            f"{len(future)} FEC filings report coverage ending after {today.isoformat()}",
            sorted(line(r) for r in future)))
    return issues


def check_senate_classes(profiles, snapshot=None):
    """Every sitting senator has a class, and a state's two seats differ.

    The Senate view groups seats by class and by the year each is next on
    the ballot. A senator with no class would silently drop out of it, and
    two senators from one state in the same class means one of the terms
    was read wrongly - the Constitution never puts both of a state's seats
    on the same ballot except through a special election, which is still
    a seat of the other class. ``nextElection`` must also agree with
    ``seatUp2026``, which comes from the same term dates by another route.
    """
    senators = [p for p in _members(profiles)
                if "Senate" in p["chamber"] and p.get("party") != "Vacant"]
    if not senators:
        return []
    if not snapshot:
        return [Issue("warn", "senate-class-unchecked",
                      "No congress_snapshot.json; senators carry no class, so the "
                      "Senate view cannot group them. Run 'congress'.")]

    issues = []
    missing = sorted(f"{p['name']} ({p['state']})" for p in senators
                     if p.get("senateClass") not in (1, 2, 3))
    if missing:
        issues.append(Issue(
            "error", "senate-class-missing",
            f"{len(missing)} sitting senator(s) have no Senate class", missing,
        ))

    by_state = collections.defaultdict(list)
    for p in senators:
        if p.get("senateClass") in (1, 2, 3):
            by_state[p["state"]].append(p)
    clashes = sorted(
        f"{st}: " + ", ".join(f"{p['name']} (Class {p['senateClass']})" for p in people)
        for st, people in by_state.items()
        if len({p["senateClass"] for p in people}) != len(people)
    )
    if clashes:
        issues.append(Issue(
            "error", "senate-class-clash",
            f"{len(clashes)} state(s) have two senators in the same class", clashes,
        ))

    # A record incumbent re-seated since Election Day - a special election's
    # winner in December - keeps the 2026 race and is next on the ballot in
    # their new term's year.
    from . import cycle, legislators

    election = cycle.general_election_day(cycle.CYCLE).isoformat()
    people = legislators.by_bioguide(snapshot)
    disagree = sorted(
        f"{p['name']} ({p['state']}): nextElection {p.get('nextElection')}, "
        f"seatUp2026 {bool(p.get('seatUp2026'))}"
        for p in senators
        if (p.get("nextElection") == 2026) != bool(p.get("seatUp2026"))
        and not (p.get("seatUp2026")
                 and (people.get(p["id"]) or {}).get("termStart", "") > election)
    )
    if disagree:
        issues.append(Issue(
            "warn", "senate-next-election",
            f"{len(disagree)} senator(s) whose next election disagrees with seatUp2026",
            disagree,
        ))
    return issues


def check_finance_periods(profiles):
    """Money still measured over the old two-year cycle, after a refresh.

    Every figure is meant to be an election-period total (fec.ELECTION_FULL).
    A record that never got the election-period lookup - a refresh that
    stopped part-way, or a pinned record skipped by older code - still shows
    the 2025-26 cycle beside challengers' whole election periods. The page
    labels it honestly, but it should not survive a full refresh unnoticed.
    """
    stale = sorted(
        f"{p['name']} ({p['officeLabel']})" for p in profiles
        if p.get("financePeriod") == "cycle"
    )
    if not stale:
        return []
    return [Issue("warn", "finance-cycle-period",
                  f"{len(stale)} profiles still show a two-year cycle total rather than "
                  f"their election period; run 'finance --refresh'", stale)]


def check_registrations(profiles, field):
    """One person's several FEC registrations, folded into one profile.

    The kept registration is the one with the latest statement of candidacy;
    when the folded ones name a different seat, that choice is worth a human
    look (Daniel Franzese filed for FL-22 and FL-25; the results page confirms
    FL-25). A curated pair that no longer matches two filings is stale.
    """
    if not field:
        return []
    from .candidates import race_id

    rows = {r.get("candidate_id"): r for r in field.get("candidates", [])}
    issues = []
    split = []
    for p in profiles:
        others = p.get("otherFecIds") or []
        kept = rows.get(p.get("fecCandidateId"))
        if not others or not kept:
            continue
        seats = sorted({race_id(rows[o]) for o in others if o in rows} - {race_id(kept)})
        if seats:
            split.append(f"{p['name']}: kept {p['fecCandidateId']} ({race_id(kept)}); "
                         f"also registered for {', '.join(str(s) for s in seats)}")
    if split:
        issues.append(Issue("warn", "registrations-disagree",
                            f"{len(split)} people registered for more than one seat; "
                            f"shown in the one their latest statement names", sorted(split)))
    stale = sorted(f"{other} -> {target}" for other, (target, _w)
                   in overrides.SAME_PERSON_FILINGS.items()
                   if other not in rows or target not in rows)
    if stale:
        issues.append(Issue("warn", "stale-same-person",
                            f"{len(stale)} curated same-person pairs match no filing", stale))
    return issues


def check_voting_links(cache):
    """Every state and D.C. has its four official voting pages.

    The state page tells a reader where to check their registration, find
    their polling place, vote absentee or early, and register - each the
    state's own page, as NASS lists it. A state left out would read as if it
    had none.
    """
    from . import voting
    if not cache:
        return [Issue("warn", "voting-links-missing",
                      f"no {voting.CACHE_PATH}; run 'voting' - state pages say nothing "
                      f"about how to vote")]
    states = cache.get("states") or {}
    gaps = [f"{code}: no {kind} page" for code in sorted(voting.JURISDICTIONS)
            for kind in voting.PAGES
            if not str((states.get(code) or {}).get(kind) or "").startswith(("http://", "https://"))]
    extra = sorted(set(states) - voting.JURISDICTIONS)
    foreign = sorted(f"{code} {kind}: {link['url']}"
                     for code, links in voting.effective(cache).items()
                     for kind, link in links.items() if not voting.official(link["url"], code))
    issues = []
    if foreign:
        issues.append(Issue("error", "voting-links-not-official",
                            f"{len(foreign)} voting links are not on their state's own "
                            f"election domain", foreign))
    dead = voting.dead_links(cache)
    if dead:
        # Not shown (voting.for_page), but a reader of that state is missing one.
        issues.append(Issue("warn", "voting-links-dead",
                            f"{len(dead)} official voting links answered 404 twice and are "
                            f"not shown; add an overrides.VOTING_LINKS entry", dead))
    stale = voting.stale_overrides(cache)
    if stale:
        issues.append(Issue("warn", "voting-override-stale",
                            f"{len(stale)} overrides.VOTING_LINKS entries no longer match "
                            f"what NASS lists; each may be unneeded", stale))
    # Where to read the count and the deadlines, for every state and D.C.
    # (audit 2026-10-17, RACES-20, STATEGOV-11): curated in kyc/voting.py.
    gaps += [f"{code}: no {kind} page" for code in sorted(voting.JURISDICTIONS)
             for kind, table in (("results", voting.RESULTS), ("deadlines", voting.DEADLINES))
             if code not in table]
    # A link never opened, or opened and not found live (a 403, a timeout:
    # rule 8 concludes nothing from either): the page says it could not be
    # reached, and this lists it, so "unknown" is never counted as checked.
    checked = cache.get("links") or {}
    unchecked = sorted(f"{code} {kind}: {link['url']} "
                       f"({checked.get(link['url'], 'never opened')})"
                       for code, links in voting.effective(cache).items()
                       for kind, link in links.items()
                       if checked.get(link["url"]) not in (voting.LIVE, voting.DEAD))
    if unchecked:
        issues.append(Issue("warn", "voting-links-unchecked",
                            f"{len(unchecked)} voting links were not found live when last "
                            f"opened, or never opened; run 'voting', and have a person open "
                            f"any that stay unknown", unchecked))
    if gaps:
        issues.append(Issue("error", "voting-links-incomplete",
                            f"{len(gaps)} official voting pages are missing", gaps))
    if extra:
        issues.append(Issue("error", "voting-links-unknown",
                            f"voting pages for jurisdictions NASS does not list: {', '.join(extra)}"))
    return issues


def run(profiles, raw, races=None, geo=None, snapshot=None, finance=None, campaigns=None,
        results=None, field=None, enrichment=None, odds=None, district_maps=None,
        district_error=None, voting=None, federal=None, judiciary=None, vacancies=None,
        history=None, voting_dates=None, statewide=None, measures=None, portraits=None,
        photo_routes=()):
    """Run every check. Returns a list of :class:`Issue`."""
    issues = []
    issues += check_district_maps(races, district_maps, district_error)
    issues += check_identity(profiles)
    issues += check_chamber_sizes(profiles)
    issues += check_seats(profiles)
    issues += check_fields(profiles)
    issues += check_placeholders(profiles)
    issues += check_photo_sets(profiles)
    issues += check_photo_credits(profiles)
    issues += check_guessed_photos(profiles)
    issues += check_outbound_urls(profiles)
    issues += check_wikipedia_withheld(profiles)
    issues += check_member_link_overrides(snapshot)
    issues += check_future_coverage(profiles)
    issues += check_overrides(profiles, raw)
    issues += check_committee_titles(profiles)
    issues += check_pay(profiles, snapshot)
    issues += check_campaign_blocklist(campaigns)
    issues += check_campaign_sites(profiles, enrichment)
    issues += check_portrait_overrides(enrichment, photo_routes)
    if portraits is not None:
        issues += check_photo_evidence(profiles, portraits, enrichment)
        issues += check_refusal_fallbacks(profiles, portraits)
    issues += check_odds(races, odds)
    issues += check_races(profiles, races)
    issues += check_markup(profiles)
    issues += check_geometry(profiles, geo)
    issues += check_snapshot(profiles, raw, snapshot)
    issues += check_record(profiles, (raw or {}).get("record"), snapshot)
    issues += check_senate_classes(profiles, snapshot)
    issues += check_finance(profiles, finance)
    issues += check_curated_candidates(profiles)
    issues += check_bio_sources(profiles)
    issues += check_finance_periods(profiles)
    issues += check_field_screen(field)
    issues += check_registrations(profiles, field)
    issues += check_duplicate_people(profiles)
    issues += check_results(profiles, races)
    issues += check_winners(profiles, races)
    issues += check_member_filings(profiles, snapshot)
    issues += check_seat_vacancies(profiles, snapshot)
    issues += check_former_wins((raw or {}).get("former"), (raw or {}).get("record"))
    issues += check_results_pages(results)
    issues += check_seats_contested(profiles)
    issues += check_guide()
    issues += check_ballot2026()
    issues += check_federal(federal)
    issues += check_succession(federal, snapshot)
    issues += check_judiciary(judiciary)
    issues += check_vacancies(vacancies, judiciary)
    issues += check_history(history, profiles)
    if voting is not None:                 # None: the caller did not supply it
        issues += check_voting_links(voting)
    if voting_dates is not None:
        issues += check_voting_dates(voting_dates)
    if statewide is not None:
        issues += check_statewide_candidates(statewide, snapshot)
    if measures is not None:
        issues += check_ballot_measures(measures)
    return issues


def check_ballot_measures(data):
    """The statewide questions (kyc/ballot_measures.py, rule 95): every
    measure and every list an official page's, quoted, never a compiled
    table, news or an advocate's (rule 50); a "none" only with the official
    words or ballots it rests on, quoted; a jurisdiction no official source
    speaks for sent to its election office, never told "none" (rule 19);
    every date in the cycle. An error: the page quotes these to voters, and
    the build refuses to write them."""
    from . import ballot_measures
    if not data:
        return [Issue("error", "ballot-measures-missing",
                      f"no {ballot_measures.CACHE_PATH}; no page lists the statewide questions")]
    found = ballot_measures.problems(data)
    if found:
        return [Issue("error", "ballot-measures", f"{len(found)} problems in the ballot measures "
                      "(kyc/ballot_measures.py)", found)]
    return []


def check_statewide_candidates(data, snapshot=None):
    """The statewide candidates (kyc/statewide.py, rule 91): every list the
    election office's own, quoted and dated, never a compiled table (rule
    50); exactly the offices kyc/ballot2026.py puts on the 2026 ballot; the
    list's words only - no portrait, money or platform; and the holder read
    consistently. An error: the page names real people as on a ballot.

    A warning, not a join, for a sitting member whose name and state a
    list carries and whose profile does not say so (rule 25): the lead is
    for a person to confirm and record in overrides.OTHER_OFFICE_NOMINEES."""
    from . import statewide
    if not data:
        return [Issue("error", "statewide-candidates-missing",
                      f"no {statewide.CACHE_PATH}; no statewide office lists its candidates")]
    found = statewide.problems(data)
    if found:
        return [Issue("error", "statewide-candidates", f"{len(found)} problems in the statewide "
                      "candidates (kyc/statewide.py)", found)]
    leads = statewide.member_leads(data, (snapshot or {}).get("legislators"),
                                   set(overrides.OTHER_OFFICE_NOMINEES))
    if leads:
        return [Issue("warning", "statewide-member-unnoted",
                      f"{len(leads)} sitting member(s) of Congress share a name with a statewide "
                      "candidate in their state and have no OTHER_OFFICE_NOMINEES entry", leads)]
    return []


def check_voting_dates(data):
    """Each jurisdiction's key dates (kyc/voting_dates.py): every value the
    page shows sourced to the jurisdiction's own official page, never to a
    compiled table (rule 50), every date in the cycle and in order, and the
    December dates the same as the results reader's (rule 53). An error: a
    wrong deadline sends a reader to the polls too late. A jurisdiction whose
    record breaks a rule is left off the page until it is fixed."""
    from . import voting_dates
    if not data:
        return [Issue("error", "voting-dates-missing",
                      f"no {voting_dates.CACHE_PATH}; state pages give no voting dates")]
    found = voting_dates.problems(data)
    if found:
        return [Issue("error", "voting-dates", f"{len(found)} problems in the voting dates "
                      f"(kyc/voting_dates.py)", found)]
    return []


def check_winners(profiles, races):
    """A member seated since Election Day in a seat they won (``winnerId``)
    whose filing's profile is also in that race: one person shown twice.

    Their filing is folded into the member only through an FEC id Congress's
    own record lists for them (rule 25); until congress-legislators adds the
    id, both profiles stay, and this says so."""
    by_id = {p["id"]: p for p in profiles}
    twice = []
    for race in races or []:
        winner = by_id.get(race.get("winnerId"))
        if not winner:
            continue
        for pid in race["candidateIds"]:
            other = by_id.get(pid)
            if (other and other is not winner and other.get("isCandidate")
                    and other.get("raceStatus") == "elected"):
                twice.append(f"{race['id']}: {winner['name']} ({winner['id']}) is seated; "
                             f"{other['name']} ({other['id']}) is the filing marked elected")
    issues = []
    if twice:
        issues.append(Issue(
            "warn", "seated-unlinked",
            f"{len(twice)} seated winners are not yet linked to their filing by an FEC "
            f"id in congress-legislators; both profiles are shown", sorted(twice)))
    # A winner with no filing at all: their money and their result reach no
    # profile until congress-legislators lists the id, or an evidenced entry
    # in overrides.MEMBER_FEC_IDS does.
    unfiled = sorted(f"{p['name']} ({p['id']}): {p.get('raceId')}" for p in profiles
                     if p.get("raceRole") == "winner" and not p.get("fecCandidateId"))
    if unfiled:
        issues.append(Issue("warn", "winner-no-filing",
                            f"{len(unfiled)} seated winners have no FEC filing linked",
                            unfiled))
    return issues


def check_member_filings(profiles, snapshot):
    """A sitting member's own candidacy for another seat whose FEC id is not
    among the ids congress-legislators lists for them (``fecAll``). Once they
    sit in that chamber, their money and their win are linked through that
    id or not at all; add it to ``overrides.MEMBER_FEC_IDS`` with evidence."""
    from . import overrides

    if not snapshot:
        return []
    known = {p["bioguide"]: set(p.get("fecAll") or []) for p in snapshot.get("legislators", [])}
    for bioguide, (filing, _why) in overrides.MEMBER_FEC_IDS.items():
        known.setdefault(bioguide, set()).add(filing)
    by_id = {p["id"]: p for p in profiles}
    missing = []
    for member in profiles:
        other = by_id.get(member.get("alsoRunningId") or "")
        if member.get("isCandidate") or not other or member["id"] not in known:
            continue
        if other.get("raceId") and other.get("raceId") == member.get("raceId"):
            continue            # a filing for the seat they sit in
        filing = other.get("rosterFecId") or other.get("fecCandidateId")
        if filing and filing not in known[member["id"]]:
            missing.append(f"{member['name']} ({member['id']}): {filing} for "
                           f"{other.get('officeLabel')}")
    if not missing:
        return []
    return [Issue("warn", "member-candidacy-id-missing",
                  f"{len(missing)} members' own candidacies for another seat are not among "
                  f"their FEC ids in congress-legislators", sorted(missing))]


def check_seat_vacancies(profiles, snapshot=None):
    """``overrides.SEAT_VACANCIES`` against the membership: an entry for a
    seat someone sits in is stale (the page stops showing it, and the entry
    should go), and one whose departed member the snapshot still seats is
    wrong."""
    from . import overrides
    from .record import seated

    sitting = {(p.get("state"), p.get("districtNum")) for p in profiles
               if seated(p) and "House" in str(p.get("chamber") or "")}
    seated_ids = {p.get("bioguide") for p in (snapshot or {}).get("legislators", [])}
    stale, wrong = [], []
    for (code, district), entry in sorted(overrides.SEAT_VACANCIES.items()):
        if (code, district) in sitting:
            stale.append(f"{code}-{district}: someone now sits in the seat {entry['name']} left")
        if entry.get("bioguide") in seated_ids:
            wrong.append(f"{code}-{district}: {entry['name']} ({entry['bioguide']}) is still "
                         f"in the membership snapshot")
    issues = []
    if stale:
        issues.append(Issue("warn", "seat-vacancy-filled",
                            f"{len(stale)} overrides.SEAT_VACANCIES entries are for seats now "
                            f"filled; remove them", stale))
    if wrong:
        issues.append(Issue("error", "seat-vacancy-seated",
                            f"{len(wrong)} overrides.SEAT_VACANCIES entries name a member who "
                            f"still sits", wrong))
    return issues


def check_former_wins(rows, record):
    """A member who won a record seat they did not hold and has since left:
    their archived row's seat is that race's, from after Election Day. The
    race keeps no winner for them yet - shown rather than silent."""
    from .normalize import parse_district

    if not rows or not record:
        return []
    held = {inc["bioguide"] for inc in (record.get("incumbents") or {}).values() if inc}
    seats = {}
    for rid, race in (record.get("races") or {}).items():
        key = (race["chamber"], race["state"],
               None if race["chamber"] == "Senate" else race.get("district"))
        seats[key] = rid
    day = record.get("electionDay") or ""
    lost = []
    for row in rows:
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        chamber, state = clean_str(row.get("Chamber"), ""), clean_str(row.get("State"), "")
        district = None if chamber == "Senate" else parse_district(row.get("District"), state)[0]
        rid = seats.get((chamber, state, district))
        if clean_str(row.get("Race Role"), "") == "winner" and clean_str(row.get("Race ID"), ""):
            continue            # archived with the race they won (winners_leaving)
        if (rid and bioguide not in held
                and clean_str(row.get("Term Start"), "")[:10] >= day):
            lost.append(f"{clean_str(row.get('Name'), bioguide)} ({bioguide}): {rid}")
    if not lost:
        return []
    return [Issue("warn", "former-winner-unplaced",
                  f"{len(lost)} archived members won a 2026 seat they did not hold; their "
                  f"race shows no winner for them", sorted(lost))]


def check_federal(cache):
    """The federal executive cache (kyc/federal.py), when the caller supplies
    one: a term that has ended is an error, so a stale file never shows a
    past President."""
    if cache is None:
        return []
    from . import federal

    return [Issue(level, code, message, detail)
            for level, code, message, detail in federal.problems(cache)]


def check_succession(cache, snapshot):
    """The Speaker and the President pro tempore in the line of succession
    (kyc/federal_build.py): an office the federal page cannot fill - none
    recorded, a holder chosen before the sitting Congress began, or one not
    seated - is a warning, so the page's "Nobody listed" is never silent."""
    if cache is None or snapshot is None:
        return []
    from . import federal_build

    _officers, problems = federal_build.congressional_officers(cache, snapshot)
    return [Issue("warn", "succession-unnamed",
                  f"the federal page names nobody for {len(problems)} congressional office(s) "
                  f"in the line of succession", problems)] if problems else []


def check_judiciary(cache):
    """The federal judiciary cache (kyc/judiciary.py), when the caller
    supplies one: every court present, nine justices and no retired one
    among them, and no judge with a party; and each court's own website on
    a host of the judiciary's own (kyc/court_info.py)."""
    from . import court_info, federal_courts, judiciary

    issues = [Issue("error", "federal-courts", f"the court table: {p}")
              for p in federal_courts.check()]
    issues += [Issue("error", "court-sites", f"the courts' websites: {p}")
               for p in court_info.check()]
    if cache is not None:
        issues += [Issue(level, code, message, detail)
                   for level, code, message, detail in judiciary.problems(cache)]
    return issues


def check_vacancies(cache, judiciary=None):
    """The courts' vacancy lists (kyc/vacancies.py), when the caller supplies
    them: a court code the table does not know, an emergency that matches no
    vacancy, a stale read, and a vacancy the FJC's directory disagrees with."""
    if cache is None:
        return []
    from . import vacancies

    return [Issue(level, code, message, detail)
            for level, code, message, detail in vacancies.problems(cache, judiciary=judiciary)]


def check_history(cache, profiles=None):
    """The public offices each person has held (kyc/history.py), when the
    caller supplies them: offices Wikidata lists that the person's own
    article does not corroborate, articles that resolved to no person, and
    offices read from an article a profile no longer links."""
    if cache is None:
        return []
    from . import history

    return [Issue(level, code, message, detail)
            for level, code, message, detail in history.problems(cache, profiles)]


def check_guide(today=None):
    """The guide's text (kyc/government_text.py): every link leads to a page,
    section or state that exists, and every source is cited by a section.

    An error, not a warning: the guide is static text, so nothing later in
    the build would notice a link that goes nowhere. Text about a dated event
    whose date has passed since the page was checked is a warning
    (``guide-revisit``): static prose about November 3 reads as still to
    come long after it, and nothing else would say so (rule 48)."""
    import datetime

    from . import government, government_maps
    problems = government.check() + government_maps.check()
    issues = []
    if problems:
        issues.append(Issue("error", "guide",
                            f"{len(problems)} problem(s) in the guide's text "
                            f"(kyc/government_text.py)", problems))
    due = government.revisits(today or datetime.date.today().isoformat())
    if due:
        issues.append(Issue("warn", "guide-revisit",
                             f"{len(due)} passage(s) of the guide describe dates that have passed "
                             f"since the page was checked; re-check them and move its 'reviewed'",
                             [f"{slug} (since {day}): {what}" for slug, day, what in due]))
    return issues


def check_ballot2026():
    """Which state offices and seats are on the 2026 ballot (kyc/ballot2026.py):
    every state, a sourced value each, chamber sizes that agree with the seat
    table. An error: the table is curated text nothing else checks."""
    from . import ballot2026
    try:
        ballot2026.check()
    except ballot2026.Ballot2026Error as exc:
        return [Issue("error", "ballot2026", "the 2026 ballot table breaks its rules",
                      str(exc).split("; "))]
    return []


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
