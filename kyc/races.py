"""Group profiles into the 2026 contests they belong to.

A flat grid of 594 cards answers "who is in Congress". It does not answer the
question a voter actually has, which is "who is running for my seat". A race
is the natural unit: one seat, the incumbent, and everyone challenging them.
"""

from .normalize import AT_LARGE, TERRITORIES

ELECTION_YEAR = 2026

# House seats that are not two-year terms. Puerto Rico's Resident Commissioner
# serves four years (48 U.S.C. 891), elected with the President: 2024, then
# 2028. The FEC's 2026 calendar has no PR-H primary and Wikipedia's "2026
# United States House of Representatives elections" lists delegate races for
# AS, DC, GU, MP and VI only - yet the site showed H-PR-00-2026 with the
# Resident Commissioner "seeking re-election". congress-legislators records
# his term as ending 2027-01-03, so the term date cannot be trusted here and
# the statute is encoded instead: {state: election years are multiples of}.
FOUR_YEAR_HOUSE_SEATS = {"PR": 4}


def house_seat_up(state, year=ELECTION_YEAR):
    """Is *state*'s House seat on the *year* ballot? True for every two-year seat."""
    period = FOUR_YEAR_HOUSE_SEATS.get(state)
    return True if period is None else year % period == 0


def house_term_end_year(state, year=ELECTION_YEAR):
    """The year the current House term for *state* ends (Jan. 3)."""
    election = year
    while not house_seat_up(state, election):
        election += 1
    return election + 1


def contestable(profiles, year=ELECTION_YEAR, record=None):
    """Every race id that genuinely exists in *year*.

    With a frozen *record* (kyc/record.py), its race set: the seats that were
    on the ballot, whoever sits in them now. Without one, derived from the
    sitting members, as the record itself was frozen:

    The FEC accepts a Senate filing from a state with no Senate seat on the
    ballot, and a House filing for a district the state does not have
    (Georgia has 14 seats; filings arrived for GA-23, and New Mexico, with 3,
    for NM-66). Taken at face value each became a race with a "pending
    primary". So a race exists only if:

    * Senate - a sitting senator's seat is up this year (``seatUp2026``,
      which comes from the snapshot's real term dates, rule 17);
    * House - the district is one the state actually has: 1 to the highest
      district any sitting member holds (so a vacant seat still counts), or
      the at-large seat; and the seat is up this year (not Puerto Rico in
      2026).

    Seat counts come from the roster, never from a hard-coded total.
    """
    if record:
        from .record import race_ids
        return race_ids(record)
    senate, house = set(), {}
    for profile in profiles:
        if profile.get("isCandidate"):
            continue
        state = profile.get("state")
        chamber = profile.get("chamber") or ""
        if "Senate" in chamber:
            if profile.get("seatUp2026"):
                senate.add(race_id("Senate", state, None))
        elif "House" in chamber and profile.get("districtNum") is not None:
            house.setdefault(state, set()).add(profile["districtNum"])

    contests = set(senate)
    for state, districts in house.items():
        if not house_seat_up(state, year):
            continue
        if state in AT_LARGE:
            numbers = {0}
        else:
            numbers = set(range(1, max(districts) + 1)) if max(districts) > 0 else {0}
        contests |= {race_id("House", state, n) for n in numbers}
    return contests


def race_id(chamber, state, district_num):
    """Stable identifier for a seat on the 2026 ballot."""
    if "Senate" in chamber:
        return f"S-{state}-{ELECTION_YEAR}"
    return f"H-{state}-{district_num or 0:02d}-{ELECTION_YEAR}"


def race_label(chamber, state, district_num):
    if "Senate" in chamber:
        return f"{state} — U.S. Senate"
    if not district_num:
        return f"{state} — At-Large"
    return f"{state}-{district_num} — U.S. House"


def parse_race_id(rid):
    """``"H-TX-37-2026"`` -> ``("House", "TX", 37)``; ``"S-MT-2026"`` ->
    ``("Senate", "MT", None)``."""
    parts = rid.split("-")
    if parts[0] == "S":
        return "Senate", parts[1], None
    return "House", parts[1], int(parts[2])


def seat_label(rid):
    """The office label the profiles use, for a race id: ``"House • TX-37"``."""
    from .normalize import office_label

    chamber, state, district = parse_race_id(rid)
    if chamber == "Senate":
        return office_label("Senate", state, None)
    return office_label("House", state, "AL" if not district else str(district))


def assign(profiles):
    """Attach a ``raceId`` to every profile contesting a 2026 seat.

    A sitting member gets the race for the seat they *hold*; their separate
    candidate profile gets the race for the seat they are *running for*, which
    is how a House member seeking a Senate seat ends up in two races.
    """
    for profile in profiles:
        chamber, state = profile["chamber"], profile["state"]
        if state in ("N/A", "") or not profile.get("seatUp2026"):
            profile["raceId"] = None
            continue
        profile["raceId"] = race_id(chamber, state, profile.get("districtNum"))
    return profiles


def build(profiles, filed_counts=None, results=None, dates=None, filed=None):
    """Return the race list, most contested first.

    ``contested`` means somebody besides the incumbent is running: a
    challenger we hold a profile for, or, once the primary is decided, any
    nominee the results page names. ``candidateCount`` counts the profiles.
    ``filedCount`` is how many people have filed with the FEC for the seat at
    any funding level, which is a fact about the race rather than about our
    coverage - the two used to be conflated, and a race with eight filers and
    no profile read as "No declared challenger".

    *filed* is the FEC field by candidate id, every filer at any funding
    level. It names the nominees whose filings are under the $5,000
    threshold, so have no profile (rule 22).
    """
    assign(profiles)
    by_id = {p["id"]: p for p in profiles}
    profiled = set()
    for p in profiles:
        profiled.update([p.get("fecCandidateId")] + list(p.get("otherFecIds") or []))

    races = {}

    def race_for(rid):
        if rid not in races:
            chamber, state, district = parse_race_id(rid)
            races[rid] = {
                "id": rid,
                "chamber": chamber,
                "state": state,
                "district": district,
                "label": race_label(chamber, state, district),
                "year": ELECTION_YEAR,
                "incumbentIds": [],
                "candidateIds": [],
                "parties": [],
                "openSeat": False,
            }
        return races[rid]

    for profile in profiles:
        rid = profile.get("raceId")
        if not rid:
            continue
        race = race_for(rid)
        if profile["isCandidate"]:
            race["candidateIds"].append(profile["id"])
        else:
            race["incumbentIds"].append(profile["id"])
            race["openSeat"] = not profile.get("seekingReelection2026", False)
            # A member contesting a different seat - a redrawn district, the
            # other chamber - is a candidate in *that* race as well as the
            # incumbent of this one. Without this, TX-37 had no Greg Casar
            # and TX-35 reported two Democratic nominees.
            contest = profile.get("contestRaceId")
            if contest and contest != rid and profile.get("alsoRunningId") is None:
                other = race_for(contest)
                other["candidateIds"].append(profile["id"])
                if profile["party"] not in other["parties"]:
                    other["parties"].append(profile["party"])
        if profile["party"] not in race["parties"]:
            race["parties"].append(profile["party"])

    for race in races.values():
        race["candidateCount"] = len(race["candidateIds"])
        race["contested"] = race["candidateCount"] > 0
        race["isTerritory"] = race["state"] in TERRITORIES
        # A seat nobody holds - a district the state has just drawn - is
        # open by definition.
        if not race["incumbentIds"]:
            race["openSeat"] = True
        if filed_counts is not None:
            race["filedCount"] = filed_counts.get(race["id"], 0)
        if dates:
            slot = dates.get((race["state"], "S" if race["chamber"] == "Senate" else "H")) or {}
            race["primaryDate"] = slot.get("primary")
            race["runoffDate"] = slot.get("runoff")
        if results is not None:
            from .results import race_summary
            summary = race_summary(results, race["id"])
            race["results"] = summary
            race["settled"] = summary is not None
            if summary:
                # Only people still on the ballot count as challengers once
                # the primary has decided who that is.
                from .results import on_ballot
                below = _below_threshold(results, race["id"], filed, profiled,
                                         [by_id[pid] for pid in race["candidateIds"] +
                                          race["incumbentIds"]])
                if below:
                    # TX-12 read "No challenger on the ballot" over a
                    # Democratic nominee who filed and raised nothing, and 53
                    # races like it. Named from their filing, by its id.
                    summary["belowThreshold"] = below
                    summary["otherNominees"] = sorted(
                        set(summary["otherNominees"]) | {b["name"] for b in below})
                    for key, wanted in (("otherElected", "elected"), ("otherRunoff", "runoff")):
                        summary[key] = sorted(set(summary.get(key) or ()) | {
                            b["name"] for b in below if b["status"] == wanted})
                # One person, counted once: an undecided profile whose name
                # the page may give another spelling of is counted as that
                # page name, not beside it ("Sarah Zabel" and the page's
                # "Sarah Zabel Peterson" were two challengers).
                from .results import _maybe_named
                named = {"unmatched": {n: "nominee" for n in summary["otherNominees"]}}
                still = [pid for pid in race["candidateIds"] if on_ballot(by_id[pid]) and not (
                    not by_id[pid].get("raceStatus") and _maybe_named(by_id[pid], named))]
                race["candidateCount"] = len(still)
                race["contested"] = bool(still) or bool(summary["otherNominees"])
                race["results"]["unlisted"] = sum(
                    1 for pid in race["candidateIds"]
                    if by_id[pid].get("raceStatus") == "unlisted"
                )

    ordered = sorted(
        races.values(),
        key=lambda r: (-r["candidateCount"], r["chamber"] != "Senate",
                       r["state"], r["district"] if r["district"] is not None else -1),
    )
    return ordered


def _below_threshold(results, rid, filed, profiled, people=()):
    """Nominees the results page matched to an FEC filing with no profile.

    The filing is under $5,000, so it never became a profile, but its owner
    is on the November ballot. Not counted: an incumbent's own registration,
    whatever the id (the FEC's incumbent flag); a second registration of
    someone with a profile in the race, which the page's one name matched
    to both ids (Jeremy Ryan Todd, KY-4); and a name already counted.
    """
    from .candidates import display_name
    from .results import NOVEMBER, _sequence

    race = ((results or {}).get("races") or {}).get(rid) or {}
    seen = set()
    for person in people:
        for name in (person.get("name"), person.get("filedName")):
            if name:
                seen.add(tuple(sorted(_sequence(display_name(name) if "," in name else name))))
    out = []
    for cid, status in sorted((race.get("status") or {}).items()):
        row = (filed or {}).get(cid)
        if status not in NOVEMBER or cid in profiled or not row:
            continue
        if row.get("incumbent_challenge") == "I":
            continue
        name = display_name(row.get("name"))
        key = tuple(sorted(_sequence(name)))
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": cid, "name": name, "status": status})
    return sorted(out, key=lambda b: b["name"])


def stats(races):
    contested = [r for r in races if r["contested"]]
    return {
        "filed_total": sum(r.get("filedCount", 0) for r in races),
        "races_with_filings": sum(1 for r in races if r.get("filedCount")),
        "races": len(races),
        "contested": len(contested),
        "open_seats": sum(1 for r in races if r["openSeat"]),
        "senate_races": sum(1 for r in races if r["chamber"] == "Senate"),
        "house_races": sum(1 for r in races if r["chamber"] == "House"),
    }
