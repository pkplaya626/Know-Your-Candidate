"""Group profiles into the 2026 contests they belong to.

A flat grid of 594 cards answers "who is in Congress". It does not answer the
question a voter actually has, which is "who is running for my seat". A race
is the natural unit: one seat, the incumbent, and everyone challenging them.
"""

from .normalize import TERRITORIES

ELECTION_YEAR = 2026


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


def build(profiles, filed_counts=None, results=None, dates=None):
    """Return the race list, most contested first.

    ``contested`` means we hold a profile for at least one challenger.
    ``filedCount`` is how many people have filed with the FEC for the seat at
    any funding level, which is a fact about the race rather than about our
    coverage - the two used to be conflated, and a race with eight filers and
    no profile read as "No declared challenger".
    """
    assign(profiles)
    by_id = {p["id"]: p for p in profiles}

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
                still = [pid for pid in race["candidateIds"] if on_ballot(by_id[pid])]
                race["candidateCount"] = len(still)
                race["contested"] = bool(still)
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
