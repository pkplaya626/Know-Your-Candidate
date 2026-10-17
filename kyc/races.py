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
    from .record import race_ids, seated

    if record:
        return race_ids(record)
    senate, house = set(), {}
    for profile in profiles:
        if not seated(profile):
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
    is how a House member seeking a Senate seat ends up in two races. A
    member seated since Election Day in a record seat keeps the race the
    build gave them (``raceRole``, ``record.seat_changes``).
    """
    for profile in profiles:
        if profile.get("raceRole"):
            continue
        chamber, state = profile["chamber"], profile["state"]
        if state in ("N/A", "") or not profile.get("seatUp2026"):
            profile["raceId"] = None
            continue
        profile["raceId"] = race_id(chamber, state, profile.get("districtNum"))
    return profiles


def build(profiles, filed_counts=None, results=None, dates=None, filed=None, record=None):
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

    def join(race, profile, role):
        ids = race[role]
        if profile["id"] not in ids:
            ids.append(profile["id"])
        if profile["party"] not in race["parties"]:
            race["parties"].append(profile["party"])

    def holds(race, profile):
        join(race, profile, "incumbentIds")
        race["openSeat"] = not profile.get("seekingReelection2026", False)
        # A member contesting a different seat - a redrawn district, the
        # other chamber - is a candidate in *that* race as well as the
        # incumbent of this one. Without this, TX-37 had no Greg Casar
        # and TX-35 reported two Democratic nominees.
        contest = profile.get("contestRaceId")
        if contest and contest != race["id"] and profile.get("alsoRunningId") is None:
            join(race_for(contest), profile, "candidateIds")
        from .districts import REDRAWN
        from .results import OFF_BALLOT
        out = (profile.get("raceStatusRace") == contest
               and profile.get("raceStatus") in OFF_BALLOT)
        # Only where the state's map changed: in a state whose map did not,
        # a member running in a neighbouring district is running for
        # another seat, not under a new number.
        if (contest and contest != race["id"] and race["chamber"] == "House"
                and race["state"] in REDRAWN
                and contest.startswith(f"H-{race['state']}-") and not out):
            # Running for the House again under the state's new district
            # number: the seat they hold is open, but they are not leaving.
            # Utah read "4 open seats" with all four members running, and
            # the "Not seeking re-election" filter listed eleven nominees.
            profile["renumbered"] = True
            race["holderMoved"] = {"name": profile["name"], "to": seat_label(contest)}

    frozen = (record or {}).get("races") or {}
    held = (record or {}).get("incumbents") or {}
    if record:
        from .record import held_races

        held_by = held_races(record)
        # Every race of the cycle exists, whoever now points at it: a seat
        # whose holder has left and was never re-seated is still a race.
        for rid in frozen:
            race_for(rid)

    for profile in profiles:
        rid = profile.get("raceId")
        if profile["isCandidate"]:
            if rid:
                join(race_for(rid), profile, "candidateIds")
            continue
        if not record:
            if rid:
                holds(race_for(rid), profile)
            continue
        # With a record, who held a seat is the record's word, not whoever
        # sits in it now: on January 3 a newly elected member would
        # otherwise become a second incumbent of the race they won, and a
        # record incumbent who has left (``formerMember``) would vanish.
        mine = held_by.get(profile["id"])
        if mine:
            holds(race_for(mine), profile)
        if profile.get("raceRole") == "winner":
            race = race_for(rid)
            join(race, profile, "candidateIds")
            race["winnerId"] = profile["id"]
        elif profile.get("raceRole") == "successor":
            if rid:
                join(race_for(rid), profile, "candidateIds")
        elif not mine and rid and not (held.get(rid) or {}).get("bioguide"):
            # Sitting in a seat the record has no holder for - a vacancy
            # filled before Election Day - so its incumbent at the election.
            # Anyone else in a seat the record names a holder for is not its
            # incumbent, whatever the build could tell about them.
            holds(race_for(rid), profile)

    for race in races.values():
        # A special election (Florida's, Ohio's): from the frozen record, so it
        # stays one after the seat's winner is seated for the term to 2029.
        race["special"] = bool((frozen.get(race["id"]) or {}).get("special"))
        if race["chamber"] == "Senate" and (frozen.get(race["id"]) or {}).get("senateClass"):
            # The seat's class, from the record: the view groups a seat by
            # it whoever holds the seat now.
            race["senateClass"] = frozen[race["id"]]["senateClass"]
        race["candidateCount"] = len(race["candidateIds"])
        race["contested"] = race["candidateCount"] > 0
        race["isTerritory"] = race["state"] in TERRITORIES
        # A seat nobody holds - a district the state has just drawn - is
        # open by definition.
        if not race["incumbentIds"]:
            race["openSeat"] = True
        # Open means no sitting member is on this seat's ballot. A member
        # running here under the state's new district number is: UT-4 read
        # "Open seat" with Mike Kennedy its nominee, while UT-1, which no
        # member is running for, did not count as open.
        if any(by_id[pid].get("renumbered") and by_id[pid].get("contestRaceId") == race["id"]
               for pid in race["candidateIds"]):
            race["openSeat"] = False
        if record:
            # Who held the seat on the ballot, from the record: named even
            # when they have no profile here, and said to be seated only
            # while they still sit in this seat.
            inc = held.get(race["id"])
            holder = by_id.get((inc or {}).get("bioguide"))
            race["incumbent"] = inc and {
                "bioguide": inc["bioguide"],
                "name": inc["name"],
                "party": inc["party"],
                "profileId": holder["id"] if holder else None,
                "seated": bool(holder) and _sits_in(holder, race["id"]),
                "appointed": bool(inc.get("appointed")),
            }
        if filed_counts is not None:
            race["filedCount"] = filed_counts.get(race["id"], 0)
        if dates:
            from .results import seat_slot
            slot = seat_slot(dates, race["id"])
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
                    summary["otherParties"] = dict(sorted(
                        {**(summary.get("otherParties") or {}),
                         **{b["name"]: b["party"] for b in below if b["party"]}}.items()))
                    for key, wanted in (("otherElected", "elected"), ("otherRunoff", "runoff")):
                        summary[key] = sorted(set(summary.get(key) or ()) | {
                            b["name"] for b in below if b["status"] == wanted})
                # One person, counted once: an undecided profile whose name
                # the page may give another spelling of is counted as that
                # page name, not beside it ("Sarah Zabel" and the page's
                # "Sarah Zabel Peterson" were two challengers).
                from .results import _maybe_named
                named = {"unmatched": {n: "nominee" for n in summary["otherNominees"]}}
                # Nor is anyone whose place on the ballot is not known
                # (results.apply_cache: ``ballotUnknown``).
                still = [pid for pid in race["candidateIds"] if on_ballot(by_id[pid]) and not (
                    not by_id[pid].get("raceStatus") and _maybe_named(by_id[pid], named))
                    and not by_id[pid].get("ballotUnknown")]
                race["candidateCount"] = len(still)
                # A page name that may be a profile here under another
                # spelling is counted as the name; the page says whose it may
                # be, never "no profile here" (IN-6's "Cynthia Wirth" and the
                # profile "Cynthia (Cinde) Wirth").
                maybe = {}
                for pid in race["candidateIds"]:
                    person = by_id[pid]
                    if person.get("raceStatus"):
                        continue
                    for name in person.get("maybeNamed") or []:
                        if name in summary["otherNominees"]:
                            maybe[name] = pid
                if maybe:
                    summary["maybeProfiled"] = maybe
                # A filer whose place on the ballot is not known is not
                # counted as on it - nor is the race said to have nobody:
                # "No challenger on the ballot" would be a claim the site
                # cannot make (rule 19).
                race["ballotUnknown"] = sum(
                    1 for pid in race["candidateIds"] if by_id[pid].get("ballotUnknown"))
                race["contested"] = (bool(still) or bool(summary["otherNominees"])
                                     or bool(race["ballotUnknown"]))
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


def _sits_in(profile, rid):
    """True when *profile* is a member sitting in race *rid*'s seat now."""
    from .record import seated

    if not seated(profile):
        return False
    if profile.get("raceRole") == "winner":
        return profile.get("raceId") == rid
    return race_id(profile["chamber"], profile["state"], profile.get("districtNum")) == rid


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
        # The name the ballot or the results page gives them where one was
        # matched to this filing: Alaska's "Eric Hafner", whom the FEC
        # files as "ERIC, HAFNER".
        name = (race.get("names") or {}).get(cid) or display_name(row.get("name"))
        key = tuple(sorted(_sequence(name)))
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": cid, "name": name, "status": status,
                    "party": _party_shown(race, cid, row)})
    return sorted(out, key=lambda b: b["name"])


def _party_shown(race, cid, row):
    """The party to print beside a nominee with no profile: the ballot's
    line as the page or the state's list gives it, else the filing's."""
    from .results import LINE_LABELS, party_key

    line = (race.get("listParty") or {}).get(cid) or (race.get("label") or {}).get(cid)
    if line:
        return line
    key = (race.get("party") or {}).get(cid)
    if key in LINE_LABELS:
        return LINE_LABELS[key]
    # The filing's party only where it names one: "UNK", "NNE" and the like
    # say nothing, and are never shown as "Independent".
    if str(row.get("party") or "").upper() in _NAMED_FEC_PARTIES:
        return LINE_LABELS[party_key(row["party"])]
    return ""


_NAMED_FEC_PARTIES = ("DEM", "DFL", "REP", "LIB", "GRE", "GRN", "IND")


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
