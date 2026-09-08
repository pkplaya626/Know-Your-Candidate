"""Headline figures for the page chrome, derived once at build time.

Both pages used to print ``53 R | 47 D/I``, ``35`` Senate seats up and ``435``
House seats as literal text in their sidebars, and recomputed the House split
in a copy-pasted ``updateElectionWatchBadge`` function. Four numbers about real
people, hand-typed into two templates, with nothing tying them to the rosters
they claim to describe.

They are counted here instead, from the same profiles the grid renders, and
shipped in the build metadata. If the roster changes, the sidebar changes.
"""

from .normalize import TERRITORIES

ELECTION_YEAR = 2026

# Every House seat is a two-year term, so the whole chamber is on every
# ballot. This is the size of the chamber, not a count of our rows: a
# mid-term vacancy does not take the seat off the ballot.
HOUSE_SEATS = 435


def _party_bucket(profile):
    """Reduce a party label to the four buckets the site displays.

    Kept in one place because "Democrat", "Democratic" and
    "Democratic-Farmer Labor" all appear in the rosters, and every page that
    counted them re-derived the test slightly differently.
    """
    party = str(profile.get("party") or "")
    if party == "Vacant" or profile.get("status") == "Vacant":
        return "vacant"
    if "Democrat" in party:
        return "D"
    if party == "Republican":
        return "R"
    return "I"


def _split(profiles):
    counts = {"D": 0, "R": 0, "I": 0, "vacant": 0}
    for profile in profiles:
        counts[_party_bucket(profile)] += 1
    counts["total"] = len(profiles)
    return counts


def build(profiles, races=None):
    """Chamber balance and 2026 election headline figures."""
    members = [p for p in profiles if not p.get("isCandidate")]

    senate = [p for p in members if "Senate" in p["chamber"]]
    # Delegates from the territories sit in the House but cannot vote on
    # legislation, so they are excluded from the partisan balance.
    house_voting = [
        p for p in members
        if "House" in p["chamber"] and p["state"] not in TERRITORIES
    ]
    delegates = [
        p for p in members
        if "House" in p["chamber"] and p["state"] in TERRITORIES
    ]

    senate_up = [p for p in senate if p.get("seatUp2026")]

    summary = {
        "congress": 119,
        "senate": _split(senate),
        "house": dict(_split(house_voting), seats=HOUSE_SEATS),
        "delegates": len(delegates),
        "election": {
            "year": ELECTION_YEAR,
            "senateSeatsUp": len(senate_up),
            "senateDefending": _split(senate_up),
            "houseSeatsUp": HOUSE_SEATS,
            "notSeeking": sum(
                1 for p in senate_up + house_voting
                if not p.get("seekingReelection2026")
            ),
            "challengers": sum(1 for p in profiles if p.get("isCandidate")),
        },
    }

    if races is not None:
        summary["races"] = {
            "total": len(races),
            "contested": sum(1 for r in races if r.get("contested")),
            "open": sum(1 for r in races if r.get("openSeat")),
        }
    return summary
