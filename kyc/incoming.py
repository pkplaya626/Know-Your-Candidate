"""The Congress the 2026 election is choosing, as far as it has been called.

From the day after Election Day until the Congress the cycle elects is
seated, a reader asks who won - "how many seats does each party have in the
120th Congress?" - and the site counted only who sits now (rule 104). This
module counts the seats elected so far, never a projection: the site makes
no forecast (rule 40), and a projection would mean guessing the races nobody
has called.

* A seat on the 2026 ballot counts for the party of its winner, only where
  the results read mark one (``raceStatus`` "elected", rule 63), or the
  results page names a winner with no profile here (``otherElected``, its
  party as the page gives it). Anything else is "not yet called as of" the
  day the results were last read - a claim about this site, not about the
  count (rule 19) - and a race the results send to a December round is
  counted among them and said apart, with its day.
* A Senate seat not on the 2026 ballot counts for the party of the senator
  who holds it now (``record.seated``), or as vacant.
* Seats not on the ballot and the Senate's races must be the Senate's 100,
  and the House's races for voting seats its 435, or the build stops: a
  count that does not add up reads exactly like one that does.
* An independent is never folded into a party, as nowhere on the site; the
  delegates are apart from the House's voting seats, as the House count
  keeps them, and Puerto Rico's Resident Commissioner, not up in 2026, is a
  seat not on the ballot.

Each state's figures are the same count, so the map, the House's squares,
its panel and the sidebar read one number (rules 1 and 73). A state's step
in the elected view - all Republican, a Democratic majority, split - is the
step its delegation will have *whatever* the uncalled seats decide, worked
out here over every way they could be decided; where they could change it,
the step is ``undecided``.

Standard library only, like the rest of ``kyc/``.
"""

from .normalize import TERRITORIES

SENATE_SEATS = 100
HOUSE_SEATS = 435
PARTIES = ("D", "R", "I")

ELECTED = "elected"
RUNOFF = "runoff"


class IncomingError(ValueError):
    """The elected Congress's figures do not add up: never shipped."""


def _bucket(party):
    """A party label in the four buckets the site counts by (summary.py's
    test): "Democratic-Farmer Labor" is Democratic, anything that is neither
    Democratic nor Republican is counted apart as independent."""
    party = str(party or "")
    if "Democrat" in party:
        return "D"
    if party == "Republican":
        return "R"
    return "I"


def _zero(vacant=False):
    out = {key: 0 for key in PARTIES}
    if vacant:
        out["vacant"] = 0
    return out


def _status_race(profile):
    """The race a profile's status is about: its own ``raceStatusRace``
    where the results gave one (a member running elsewhere, a renumbered
    member), else the seat's (validate's ``status_in``)."""
    return profile.get("raceStatusRace", profile.get("raceId"))


def outcomes(profiles, races):
    """``{race id: {"winner": {...}|None, "runoff": bool, "date": ...}}``.

    A winner is the one person in the race the results mark elected - a
    profile, or a name the results page gives with no profile here. Two are
    a contradiction and stop the build; none is "not yet called"."""
    elected, runoff = {}, {}
    for p in profiles:
        rid = _status_race(p)
        if not rid:
            continue
        if p.get("raceStatus") == ELECTED:
            elected.setdefault(rid, []).append({
                "id": p["id"], "name": p.get("name") or "", "party": _bucket(p.get("party")),
                "partyName": str(p.get("party") or "")})
        elif p.get("raceStatus") == RUNOFF:
            runoff.setdefault(rid, []).append(p["id"])
    out = {}
    for race in races:
        rid = race["id"]
        res = race.get("results") or {}
        parties = res.get("otherParties") or {}
        winners = list(elected.get(rid, []))
        for name in res.get("otherElected") or ():
            if name not in parties:
                raise IncomingError(f"{rid}: the results name {name!r} the winner and give no "
                                    "party, so the seat cannot be counted for one")
            winners.append({"name": name, "party": _bucket(parties[name]),
                            "partyName": str(parties[name])})
        if len(winners) > 1:
            raise IncomingError(f"{rid}: {len(winners)} people are marked elected "
                                f"({', '.join(w['name'] for w in winners)})")
        to_runoff = bool(runoff.get(rid) or res.get("otherRunoff"))
        entry = {"winner": winners[0] if winners else None}
        if not winners and to_runoff:
            entry["runoff"] = True
            entry["date"] = race.get("generalRunoff")
            entry["open"] = race.get("primaryKind") == "open"
        out[rid] = entry
    return out


def house_step(d, r, i, total):
    """A House delegation's step, as kyc-map.js's House view draws it."""
    if not total:
        return "none"
    if i == total or not (d + r):
        return "allI"
    if r == total:
        return "allR"
    if d == total:
        return "allD"
    return "majD" if d > r else "majR" if r > d else "even"


def senate_step(d, r, i, vacant):
    """A Senate delegation's step, as the map's Senate view draws it: the
    seats held, an empty one aside."""
    held = d + r + i
    if not held:
        return "vacant" if vacant else "none"
    if r == held:
        return "allR"
    if d == held:
        return "allD"
    if i == held:
        return "allI"
    return "split"


def completions(k):
    """Every way *k* uncalled seats could be decided, as (D, R, I) counts."""
    for d in range(k + 1):
        for r in range(k + 1 - d):
            yield d, r, k - d - r


def decided_step(known, uncalled, chamber):
    """The step a delegation has whatever its *uncalled* seats decide, over
    every completion; ``undecided`` where two completions differ. *known* is
    the decided seats by party (with "vacant" in the Senate)."""
    steps = set()
    vacant = known.get("vacant", 0)
    for d, r, i in completions(uncalled):
        D, R, I = known["D"] + d, known["R"] + r, known["I"] + i
        if chamber == "senate":
            steps.add(senate_step(D, R, I, vacant))
        else:
            steps.add(house_step(D, R, I, D + R + I + vacant))
    return steps.pop() if len(steps) == 1 else "undecided"


def _seat(race, outcome):
    """One seat on the ballot: its winner's party bucket and profile id, or
    - a winner with no profile here - their name and party as the results
    page gives them; else whether it is in a December round. A House seat
    is keyed by its district, so names its race only while undecided."""
    house = race.get("chamber") == "House"
    if outcome["winner"]:
        w = outcome["winner"]
        seat = {} if house else {"race": race["id"]}
        seat["party"] = w["party"]
        if w.get("id"):
            seat["id"] = w["id"]
        else:
            seat.update(name=w["name"], partyName=w["partyName"])
        return seat
    seat = {"race": race["id"], "status": RUNOFF if outcome.get("runoff") else "uncalled"}
    if outcome.get("runoff"):
        seat["date"] = outcome.get("date")
        seat["open"] = outcome.get("open")
    return seat


def _rounds(seats):
    """The December rounds the uncalled seats go to: one entry per day."""
    days = {}
    for seat in seats:
        if seat.get("status") == RUNOFF:
            key = (seat.get("date") or "", bool(seat.get("open")))
            days[key] = days.get(key, 0) + 1
    return [{"date": date or None, "open": open_, "seats": n}
            for (date, open_), n in sorted(days.items())]


def build(profiles, races, results=None, snapshot=None):
    """The elected Congress's figures for ``kycBuildMeta.incoming``, or None
    once the Congress the cycle elects sits (the record phase): nothing is
    incoming then, and the normal view is that Congress."""
    from . import cycle
    from .record import seated

    if snapshot:
        try:
            if cycle.phase(snapshot) == "record":
                return None
        except cycle.CycleError:
            pass
    races = list(races or ())
    told = outcomes(profiles, races)
    states = {}

    def state(code):
        return states.setdefault(code, {
            "senate": {"elected": _zero(), "notUp": _zero(True), "uncalled": 0, "runoff": 0,
                       "seats": [], "held": []},
            "house": {"elected": _zero(), "notUp": _zero(True), "uncalled": 0, "runoff": 0,
                      "seats": {}, "held": []},
        })

    senate_races = [r for r in races if r.get("chamber") == "Senate"]
    house_races = [r for r in races if r.get("chamber") == "House"]
    voting = [r for r in house_races if r["state"] not in TERRITORIES]
    if len(voting) != HOUSE_SEATS:
        raise IncomingError(f"{len(voting)} House races for voting seats, not {HOUSE_SEATS}")
    if any(r["state"] in TERRITORIES for r in senate_races):
        raise IncomingError("a Senate race in a place with no seat in the Senate")

    on_ballot = set()
    for race in senate_races:
        if not race.get("senateClass"):
            raise IncomingError(f"{race['id']}: a Senate race with no class, so the seats "
                                "not on the ballot cannot be told from it")
        on_ballot.add((race["state"], race["senateClass"]))
    for race in sorted(races, key=lambda r: r["id"]):
        code = race["state"]
        chamber = "senate" if race.get("chamber") == "Senate" else "house"
        entry = state(code)[chamber]
        seat = _seat(race, told[race["id"]])
        if "party" in seat:
            entry["elected"][seat["party"]] += 1
        else:
            entry["uncalled"] += 1
            if seat["status"] == RUNOFF:
                entry["runoff"] += 1
        if chamber == "senate":
            entry["seats"].append(seat)
        else:
            number = str(race.get("district") or 0)
            if number in entry["seats"]:
                raise IncomingError(f"{race['id']}: two House races for {code}-{number}")
            entry["seats"][number] = seat

    # The seats not on the 2026 ballot, by who holds them now.
    house_places = {r["state"] for r in house_races}
    for p in profiles:
        if not seated(p) or not p.get("state"):
            continue
        code = p["state"]
        if "Senate" in str(p.get("chamber") or ""):
            if not p.get("senateClass"):
                raise IncomingError(f"{p['id']}: a sitting senator with no class, so whether "
                                    "their seat is on the ballot cannot be told")
            if (code, p.get("senateClass")) in on_ballot:
                continue
            entry = state(code)["senate"]
        elif "House" in str(p.get("chamber") or ""):
            if code in house_places:
                continue
            entry = state(code)["house"]
        else:
            continue
        entry["notUp"][_bucket(p.get("party"))] += 1
        entry["held"].append({"id": p["id"], "party": _bucket(p.get("party")),
                              "name": p.get("name") or ""})

    # Every state has two senators: a seat not on the ballot that nobody
    # holds is vacant, and more holders than seats is a contradiction.
    from .normalize import STATE_CODES
    voting_states = sorted(STATE_CODES - TERRITORIES)
    for code in voting_states:
        entry = state(code)["senate"]
        not_up = 2 - sum(1 for r in senate_races if r["state"] == code)
        held = sum(entry["notUp"][k] for k in PARTIES)
        if held > not_up:
            raise IncomingError(f"{code}: {held} senators hold seats not on the ballot, "
                                f"of {not_up}")
        entry["notUp"]["vacant"] = not_up - held
    for code in TERRITORIES:
        entry = state(code)["house"]
        if not entry["seats"] and sum(entry["notUp"][k] for k in PARTIES) != 1:
            # One seat each: a place with no race has its member's seat not
            # on the ballot (Puerto Rico's four-year term), held or vacant.
            entry["notUp"]["vacant"] = 1 - sum(entry["notUp"][k] for k in PARTIES)
            if entry["notUp"]["vacant"] < 0:
                raise IncomingError(f"{code}: more than one member holds its House seat")

    def chamber_total(chamber, codes):
        out = {"elected": _zero(), "notUp": _zero(True), "uncalled": 0, "runoff": 0}
        seats = []
        for code in codes:
            if code not in states:
                continue
            entry = states[code][chamber]
            for key in PARTIES:
                out["elected"][key] += entry["elected"][key]
                out["notUp"][key] += entry["notUp"][key]
            out["notUp"]["vacant"] += entry["notUp"]["vacant"]
            out["uncalled"] += entry["uncalled"]
            out["runoff"] += entry["runoff"]
            seats.extend(entry["seats"].values() if isinstance(entry["seats"], dict)
                         else entry["seats"])
        out["rounds"] = _rounds(seats)
        out["races"] = len(seats)
        return out

    senate = chamber_total("senate", voting_states)
    senate["seats"] = SENATE_SEATS
    not_up = sum(senate["notUp"].values())
    if not_up + len(senate_races) != SENATE_SEATS:
        raise IncomingError(f"{not_up} Senate seats not on the ballot and {len(senate_races)} "
                            f"races make {not_up + len(senate_races)}, not {SENATE_SEATS}")
    house = chamber_total("house", voting_states)
    house["seats"] = HOUSE_SEATS
    if house["races"] != HOUSE_SEATS or sum(house["notUp"].values()):
        raise IncomingError(f"{house['races']} House races for voting seats and "
                            f"{sum(house['notUp'].values())} seats off the ballot, not {HOUSE_SEATS}")
    delegates = chamber_total("house", sorted(TERRITORIES))
    delegates["seats"] = len(TERRITORIES)
    if delegates["races"] + sum(delegates["notUp"].values()) != len(TERRITORIES):
        raise IncomingError("the delegates' seats are not one a place")

    for code, entry in states.items():
        for chamber in ("senate", "house"):
            part = entry[chamber]
            known = dict(part["elected"])
            for key in PARTIES:
                known[key] += part["notUp"][key]
            known["vacant"] = part["notUp"]["vacant"]
            part["step"] = decided_step(known, part["uncalled"], chamber)
            part["held"].sort(key=lambda h: h["name"])
            for h in part["held"]:
                del h["name"]
        if code in TERRITORIES:
            del entry["senate"]

    number = cycle.electing_congress()
    return {
        "congress": number,
        "termStart": cycle.congress_start(number).isoformat(),
        "resultsAsOf": (results or {}).get("asOf"),
        "senate": senate,
        "house": house,
        "delegates": delegates,
        "states": {code: states[code] for code in sorted(states)},
    }


def tile_problems(layout, elected):
    """The House's squares in the elected view are the 2026 map's districts
    (``cells2026``, else the map unchanged): a square per race, each one's
    own, or a winner is coloured on another district's square."""
    problems = []
    states = (elected or {}).get("states") or {}
    for code, block in sorted(((layout or {}).get("states") or {}).items()):
        cells = block.get("cells2026") or block.get("cells") or {}
        seats = ((states.get(code) or {}).get("house") or {}).get("seats") or {}
        if set(cells) != set(seats):
            problems.append(f"{code}: squares {sorted(cells)} for the 2026 races' districts "
                            f"{sorted(seats)}")
    return problems
