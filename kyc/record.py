"""The frozen record of a cycle's races: which seats were on the ballot, and
who held each one when it was.

Until now the 2026 races were re-derived on every build from whoever is
sitting - a Senate seat was "up" because its senator's term ends at the
election. That derivation dies twice: when the Ohio and Florida special
elections' winners are seated in December (their terms end in 2029, so the
seats stop looking "up" and two Senate races, with their results, would
vanish), and on January 3, when the whole membership changes. So the race
set is frozen once, from the 119th Congress, before the election
(``record --freeze``), and the site reads it from then on (audit CG-7).

``races`` is frozen: its signature is pinned in ``cycle.RECORD_SIGNATURES``
and ``verify`` fails when it changes. ``incumbents`` names who held each seat
on the ballot, with the ids the site links through (rule 32).
"""

import json
import os

from . import cycle as cycle_mod


class RecordError(RuntimeError):
    pass


# The person fields kept for an incumbent: who they are, the seat, the term,
# and the ids every outbound link is built from - never a name to match on.
_INCUMBENT_FIELDS = ("bioguide", "name", "party", "termStart", "termEnd", "govtrack",
                     "opensecrets", "votesmart", "ballotpedia", "wikipedia")


def _incumbent(person, seat):
    out = {key: person.get(key) for key in _INCUMBENT_FIELDS}
    out["seat"] = seat
    # Every FEC id the person has filed under, both chambers: a member's own
    # candidacy for the other one is linked through it.
    out["fec"] = sorted(set(person.get("fecAll") or person.get("fec") or []))
    out["appointed"] = person.get("how") == "appointment"
    return out


def freeze(profiles, snapshot, cycle=None):
    """The record dict for *cycle*, from the sitting members.

    *profiles* are the built member profiles (their ``raceId``s name the race
    set, :func:`kyc.races.contestable`); *snapshot* is the committed
    membership. Refuses a snapshot that is not of the Congress before the one
    the cycle elects, and a Senate race set that does not match the senators
    whose terms end at this election.
    """
    from . import legislators, races as races_mod

    cycle = cycle or cycle_mod.CYCLE
    electing = cycle_mod.electing_congress(cycle)
    sitting = cycle_mod.snapshot_congress(snapshot)
    if sitting != electing - 1:
        raise RecordError(f"the {cycle} record is frozen from the "
                          f"{cycle_mod.ordinal(electing - 1)} Congress; the snapshot is "
                          f"of the {cycle_mod.ordinal(sitting)}")
    regular_end = f"{cycle + 1}-01-03"

    contests = races_mod.contestable(profiles, cycle)
    up = legislators.senators_up(snapshot, cycle)
    senate_states = {p["state"] for p in up}
    listed = {rid.split("-")[1] for rid in contests if rid.startswith("S-")}
    if listed != senate_states:
        raise RecordError(f"Senate races {sorted(listed)} do not match the senators "
                          f"whose terms end at the {cycle} election {sorted(senate_states)}")

    races, incumbents = {}, {}
    by_state = {p["state"]: p for p in up}
    house = {}
    for person in (snapshot or {}).get("legislators", []):
        if person.get("chamber") == "House":
            rid = races_mod.race_id("House", person["state"], person.get("district") or 0)
            house[rid] = person

    for rid in sorted(contests):
        kind, state = rid.split("-")[0], rid.split("-")[1]
        if kind == "S":
            senator = by_state[state]
            special = senator.get("termEnd") != regular_end
            # The source says so too, for an appointee's seat: the two must
            # agree, or the record would call a regular race special.
            end_type = senator.get("endType")
            if end_type is not None and special != (end_type == "special-election"):
                raise RecordError(f"{rid}: the term end and the source's end-type "
                                  f"disagree about a special election")
            races[rid] = {"chamber": "Senate", "state": state,
                          "senateClass": senator.get("senateClass"), "special": special}
            incumbents[rid] = _incumbent(senator, races_mod.seat_label(rid))
        else:
            district = int(rid.split("-")[2])
            races[rid] = {"chamber": "House", "state": state, "district": district}
            person = house.get(rid)
            incumbents[rid] = _incumbent(person, races_mod.seat_label(rid)) if person else None

    return {
        "cycle": cycle,
        "sittingCongress": sitting,
        "electing": electing,
        "electionDay": cycle_mod.general_election_day(cycle).isoformat(),
        "frozenFrom": {"snapshotFetched": (snapshot or {}).get("fetched")},
        "races": races,
        "incumbents": incumbents,
    }


def save(record, root=".", cycle=None, force=False):
    """Write the record, atomically (rule 7). Refuses to overwrite one."""
    path = cycle_mod.record_path(root, cycle or record["cycle"])
    if os.path.exists(path) and not force:
        raise RecordError(f"{path} exists; the record is frozen (pass --force to replace it)")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def race_ids(record):
    return set((record or {}).get("races") or {})


def senate_incumbents(record):
    """Bioguide ids of the senators whose seats are the record's Senate races."""
    return {inc["bioguide"] for rid, inc in ((record or {}).get("incumbents") or {}).items()
            if rid.startswith("S-") and inc}


def drift(record, live, snapshot):
    """Race ids where the live race set and the record differ, and why.

    The only difference allowed is a race whose record incumbent's term has
    ended by the time the snapshot was read: a special election's seat once
    its winner is seated (Florida's and Ohio's Senate seats in December).
    Anything else - a district the record does not have, a seat that stopped
    being up for another reason - is reported.
    """
    fetched = ((snapshot or {}).get("fetched") or "")[:10]
    held = (record or {}).get("incumbents") or {}
    out = []
    for rid in sorted(race_ids(record) ^ set(live)):
        inc = held.get(rid)
        ended = bool(inc and fetched and (inc.get("termEnd") or "9999") <= fetched)
        if rid in race_ids(record) and ended:
            continue
        out.append(f"{rid}: " + ("in the record, not among today's seats"
                                 if rid in race_ids(record) else
                                 "a seat today that the record does not have"))
    return out
