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
    if district_num is None:
        return f"H-{state}-AL-{ELECTION_YEAR}"
    return f"H-{state}-{district_num:02d}-{ELECTION_YEAR}"


def race_label(chamber, state, district_num):
    if "Senate" in chamber:
        return f"{state} — U.S. Senate"
    if district_num is None:
        return f"{state} — At-Large"
    return f"{state}-{district_num} — U.S. House"


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


def build(profiles):
    """Return the race list, most contested first.

    Only races with at least one declared challenger are marked ``contested``;
    the rest are seats where the roster has no opponent on file yet, which is
    a fact about our data as much as about the race.
    """
    assign(profiles)

    races = {}
    for profile in profiles:
        rid = profile.get("raceId")
        if not rid:
            continue
        race = races.setdefault(rid, {
            "id": rid,
            "chamber": "Senate" if rid.startswith("S-") else "House",
            "state": profile["state"],
            "district": profile.get("districtNum"),
            "label": race_label(profile["chamber"], profile["state"],
                                profile.get("districtNum")),
            "year": ELECTION_YEAR,
            "incumbentIds": [],
            "candidateIds": [],
            "parties": [],
            "openSeat": False,
        })
        if profile["isCandidate"]:
            race["candidateIds"].append(profile["id"])
        else:
            race["incumbentIds"].append(profile["id"])
            race["openSeat"] = not profile.get("seekingReelection2026", False)
        if profile["party"] not in race["parties"]:
            race["parties"].append(profile["party"])

    for race in races.values():
        race["candidateCount"] = len(race["candidateIds"])
        race["contested"] = race["candidateCount"] > 0
        race["isTerritory"] = race["state"] in TERRITORIES

    ordered = sorted(
        races.values(),
        key=lambda r: (-r["candidateCount"], r["chamber"] != "Senate",
                       r["state"], r["district"] if r["district"] is not None else -1),
    )
    return ordered


def stats(races):
    contested = [r for r in races if r["contested"]]
    return {
        "races": len(races),
        "contested": len(contested),
        "open_seats": sum(1 for r in races if r["openSeat"]),
        "senate_races": sum(1 for r in races if r["chamber"] == "Senate"),
        "house_races": sum(1 for r in races if r["chamber"] == "House"),
    }
