"""Rehearse what the turn of the Congress does to the site, on a copy.

    python tools/rehearse_changeover.py --out DIR [--scenario NAME ...]

Three scenarios, each on its own copy of the repository under DIR:

- ``december-loses``: Florida's special election is won by a fictional
  senator (Z900001), seated on 2026-12-08; the appointee leaves; Ohio's
  appointee is re-seated for the term to 2029.
- ``december-wins``: the same with the two states' outcomes swapped.
- ``january``: the 120th Congress, read on 2027-01-04. Each record race gets
  one holder: its incumbent if renominated for it, else a member who won it
  from another seat, else a fictional newcomer (Z9xxxxx), most carrying the
  FEC id of the race's leading filer so the link by id is exercised and
  every fifth carrying none (``seated-unlinked``). Members left without a
  seat leave on January 3.

On each copy it runs what the refresh would: ``congress --apply`` with the
fictional membership, the build, ``build --check --strict`` and ``verify``.
CI then runs the unit tests and the page checks on the copy.

The outcomes are fiction about real people. They exist only in DIR, which
may not be inside the repository, and nothing here is published. Once the
data is past the moment a scenario describes - the specials' winners
seated, or the new Congress sitting - the committed data is the case, and
the scenario is skipped.
"""

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = ("december-loses", "december-wins", "january")


class RehearsalError(RuntimeError):
    pass


def check_out(out, repo=REPO):
    """Refuse an output directory inside the repository: the fiction must
    never sit where a commit could pick it up."""
    out, repo = os.path.realpath(out), os.path.realpath(repo)
    if out == repo or out.startswith(repo + os.sep):
        raise RehearsalError(f"{out} is inside the repository; use a directory outside it")
    return out


def copy_repo(dest):
    shutil.copytree(REPO, dest, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", "*.tmp"))


def _kyc():
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from kyc import candidates, cycle, fec, legislators, overrides, results, sources
    from kyc.profiles import build_profiles
    return candidates, cycle, fec, legislators, overrides, results, sources, build_profiles


# ------------------------------------------------------------- December

def december(label, root=REPO):
    """``(snapshot, historical)`` for one outcome of the specials, or None
    once their winners are seated."""
    _c, _cy, _f, legislators, _o, _r, sources, _b = _kyc()
    raw = sources.load_all(root)
    snap = legislators.load_snapshot(root)
    held = raw["record"]["incumbents"]
    fl, oh = held["S-FL-2026"], held["S-OH-2026"]
    sitting = legislators.by_bioguide(snap)
    if any((sitting.get(a["bioguide"]) or {}).get("termEnd") != a["termEnd"] for a in (fl, oh)):
        return None
    loser, kept, new = {
        "december-loses": (fl["bioguide"], oh["bioguide"], ("Z900001", "FL", "Zora Example")),
        "december-wins": (oh["bioguide"], fl["bioguide"], ("Z900002", "OH", "Quinn Example")),
    }[label]
    first, last = new[2].split()
    winner = {"bioguide": new[0], "name": new[2], "last": last,
              "nameParts": {"first": first, "last": last}, "chamber": "Senate",
              "state": new[1], "district": None, "party": "Independent",
              "termStart": "2026-12-08", "termEnd": "2029-01-03", "senateClass": 3,
              "fec": [], "fecAll": [], "how": None, "endType": None}
    after = copy.deepcopy(snap)
    gone = next(p for p in after["legislators"] if p["bioguide"] == loser)
    people = [p for p in after["legislators"] if p["bioguide"] != loser] + [winner]
    for p in people:
        if p["bioguide"] == kept:
            p.update(termStart="2026-12-08", termEnd="2029-01-03", how=None, endType=None)
    after["legislators"] = sorted(people, key=lambda p: p["bioguide"])
    after["count"] = len(people)
    after["fetched"] = "2026-12-09T07:20:00+00:00"
    historical = [{"id": {"bioguide": loser},
                   "name": {"first": gone["nameParts"].get("first"), "last": gone["last"]},
                   "terms": [{"type": "sen", "start": gone["termStart"], "end": "2026-12-08",
                              "state": gone["state"]}]}]
    return after, historical


# -------------------------------------------------------------- January

NEW_TERM = "2027-01-03"
HOUSE_END, SENATE_END, SPECIAL_END = "2029-01-03", "2033-01-03", "2029-01-03"
WINS = ("nominee", "advanced", "qualified")


def january(root=REPO):
    """``(snapshot, historical, log)`` for 2027-01-04, or None once the new
    Congress is sitting."""
    candidates, cycle, fec, legislators, overrides, results, sources, build_profiles = _kyc()
    raw = sources.load_all(root)
    snap = legislators.load_snapshot(root)
    if cycle.phase(snap) == "record":
        return None
    record = raw["record"]
    field = candidates.load_cache(root)
    profiles, _ = build_profiles(raw, snapshot=snap, field=field, finance=fec.load_cache(root))
    members = {p["id"]: p for p in profiles if not p["isCandidate"]}
    people = {p["bioguide"]: copy.deepcopy(p) for p in snap["legislators"]}
    member_fec = {i for p in snap["legislators"] for i in p.get("fecAll") or []}
    status_of = {}
    for rid, race in ((results.load_cache(root) or {}).get("races") or {}).items():
        for cid, status in (race.get("status") or {}).items():
            status_of[(rid, cid)] = status
    filers = {}
    for row in field["candidates"]:
        rid = candidates.race_id(row)
        if rid and row["candidate_id"] not in member_fec and row.get("incumbent_challenge") != "I":
            filers.setdefault(rid, []).append(row)
    for rid, rows in filers.items():
        # A nominee first: only someone on the November ballot can have won.
        rows.sort(key=lambda r: (status_of.get((rid, r["candidate_id"])) not in WINS,
                                 -(r.get("receipts") or 0), r["candidate_id"]))

    held = {rid: (inc or {}).get("bioguide") for rid, inc in record["incumbents"].items()}
    holder, log = {}, []

    def nominee(p, rid):
        ids = set(people.get(p["id"], {}).get("fecAll") or [])
        other = next((q for q in profiles if q["id"] == p.get("alsoRunningId")), None)
        if other:
            ids |= {other.get("fecCandidateId"), other.get("rosterFecId")}
        return any(status_of.get((rid, i)) in WINS for i in ids if i)

    # 1. A member running for another record seat whose incumbent is not
    #    running for it again, and who is that race's nominee, takes it.
    for p in sorted((p for p in members.values() if p.get("contestRaceId") in record["races"]
                     and p["contestRaceId"] != p.get("raceId")), key=lambda p: p["id"]):
        rid = p["contestRaceId"]
        inc = members.get(held.get(rid) or "")
        if rid in holder or (inc and inc.get("seekingReelection2026")) or not nominee(p, rid):
            continue
        holder[rid] = ("mover", p["id"])
    # 2. An incumbent running again for their own seat keeps it.
    taken = {v[1] for v in holder.values()}
    for rid, bid in held.items():
        if rid not in holder and bid in members and bid not in taken \
                and members[bid].get("seekingReelection2026"):
            holder[rid] = ("incumbent", bid)
    # The specials: while they are open, Florida's appointee is re-seated and
    # Ohio's replaced. Once their winners are seated (December, in the data
    # or in a December rehearsal's copy), whoever sits in those seats keeps
    # them.
    oh = held["S-OH-2026"]
    sitting = legislators.by_bioguide(snap)
    specials = ("S-FL-2026", "S-OH-2026")
    still_open = all(
        (sitting.get(record["incumbents"][rid]["bioguide"]) or {}).get("termEnd")
        == record["incumbents"][rid]["termEnd"] for rid in specials)
    if still_open:
        holder["S-FL-2026"] = ("incumbent", held["S-FL-2026"])
        holder.pop("S-OH-2026", None)
    else:
        for rid in specials:
            race = record["races"][rid]
            holder.pop(rid, None)
            sitter = next((p for p in people.values() if p["chamber"] == "Senate"
                           and p["state"] == race["state"]
                           and p.get("senateClass") == race.get("senateClass")
                           and (p.get("termStart") or "") >= "2026-11-03"), None)
            if sitter:
                holder[rid] = ("seated", sitter["bioguide"])

    # 3. Every other seat to a newcomer; every fifth with no FEC id.
    count = 0
    for index, rid in enumerate(sorted(record["races"])):
        if rid in holder:
            continue
        race = record["races"][rid]
        rows = filers.get(rid) or []
        row = rows[0] if rows else None
        count += 1
        while f"Z9{count:05d}" in people:
            count += 1          # an id already seated: a December winner
        bid = f"Z9{count:05d}"
        name = candidates.display_name(row.get("name")) if row else f"Newcomer {bid}"
        party = {"DEM": "Democrat", "REP": "Republican"}.get((row or {}).get("party"),
                                                            "Independent")
        first, *rest = name.split()
        senate = race["chamber"] == "Senate"
        special = senate and race.get("special")
        linked = bool(row) and index % 5 != 0
        people[bid] = {
            "bioguide": bid, "name": name, "last": rest[-1] if rest else first,
            "nameParts": {"first": first, "last": rest[-1] if rest else first},
            "chamber": race["chamber"], "state": race["state"],
            "district": None if senate else race["district"], "party": party,
            "termStart": "2026-12-08" if special else NEW_TERM,
            "termEnd": SPECIAL_END if special else (SENATE_END if senate else HOUSE_END),
            "senateClass": race.get("senateClass") if senate else None,
            "fec": [row["candidate_id"]] if linked else [],
            "fecAll": [row["candidate_id"]] if linked else [],
            "how": "special-election" if special else None, "endType": None,
            "birthday": None, "wikipedia": None,
        }
        holder[rid] = ("newcomer", bid)
        log.append(["newcomer", rid, bid])

    # 4. Re-seat the holders; anyone holding a seat on the ballot who won
    #    none leaves on January 3 (Ohio's appointee when the winner is seated).
    seated_in = {bid: rid for rid, (_kind, bid) in holder.items()}
    gone = []
    for bid, p in list(people.items()):
        if bid.startswith("Z9") and holder.get(seated_in.get(bid), ("",))[0] != "seated":
            continue
        rid = seated_in.get(bid)
        if rid:
            race = record["races"][rid]
            senate = race["chamber"] == "Senate"
            p.update(chamber=race["chamber"], state=race["state"],
                     district=None if senate else race["district"],
                     senateClass=race.get("senateClass") if senate else None,
                     termStart="2026-12-08" if race.get("special") else NEW_TERM,
                     termEnd=SPECIAL_END if race.get("special")
                     else (SENATE_END if senate else HOUSE_END),
                     how=None, endType=None)
            # As legislators.trim builds them: this chamber's ids.
            extra = overrides.MEMBER_FEC_IDS.get(bid)
            every = sorted(set(p.get("fecAll") or []) | ({extra[0]} if extra else set()))
            p["fecAll"] = every
            p["fec"] = [i for i in every if i.startswith("S" if senate else "H")]
            log.append([holder[rid][0], rid, bid])
        elif bid in held.values() or (p["chamber"] == "House" and p["state"] != "PR"):
            left = "2026-12-08" if bid == oh else NEW_TERM
            gone.append({"id": {"bioguide": bid}, "name": {"last": p.get("last")},
                         "terms": [{"type": "sen" if p["chamber"] == "Senate" else "rep",
                                    "start": p.get("termStart"), "end": left,
                                    "state": p["state"]}]})
            del people[bid]
            log.append(["departed", bid])
        elif p["state"] == "PR" and p["chamber"] == "House":
            # Puerto Rico's four-year term continues.
            p.update(termStart=NEW_TERM, termEnd=HOUSE_END)

    snapshot = dict(snap, legislators=sorted(people.values(), key=lambda p: p["bioguide"]),
                    fetched="2027-01-04T07:20:00+00:00")
    snapshot["count"] = len(snapshot["legislators"])
    seats = {}
    for p in snapshot["legislators"]:
        key = (p["chamber"], p["state"],
               p.get("district") if p["chamber"] == "House" else p.get("senateClass"))
        seats[key] = seats.get(key, 0) + 1
    twice = sorted(str(k) for k, n in seats.items() if n > 1)
    if twice:
        raise RehearsalError(f"the fictional membership seats two people in: {twice}")
    return snapshot, gone, log


# ------------------------------------------------------------------ run

def run(scenario, out):
    """Write the scenario's copy and run the refresh's steps on it."""
    made = january() if scenario == "january" else december(scenario)
    if made is None:
        print(f"[skip] {scenario}: the committed data is past it")
        return 0
    snapshot, historical = made[0], made[1]
    dest = os.path.join(out, scenario)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    copy_repo(dest)
    inputs = os.path.join(out, f"{scenario}-inputs")
    os.makedirs(inputs, exist_ok=True)
    snap_path = os.path.join(inputs, "snapshot.json")
    hist_path = os.path.join(inputs, "historical.json")
    with open(snap_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=1, sort_keys=True)
    with open(hist_path, "w", encoding="utf-8") as handle:
        json.dump(historical, handle)
    steps = [
        ["congress", "--apply", "--snapshot", snap_path, "--historical", hist_path],
        [],
        ["build", "--check", "--strict"],
        ["verify"],
    ]
    for step in steps:
        cmd = [sys.executable, "build_profile_site.py", *step]
        print(f"[{scenario}] {' '.join(step) or 'build'}", flush=True)
        done = subprocess.run(cmd, cwd=dest, capture_output=True, text=True)
        tail = (done.stdout + done.stderr).strip().splitlines()[-12:]
        if done.returncode != 0:
            print("\n".join(tail))
            print(f"[error] {scenario}: '{' '.join(step) or 'build'}' exited {done.returncode}")
            return 1
    print(f"[ok] {scenario}: congress --apply, build, strict check and verify pass in {dest}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True,
                        help="a directory outside the repository for the copies")
    parser.add_argument("--scenario", action="append", choices=SCENARIOS,
                        help="which to run (default: all)")
    args = parser.parse_args(argv)
    try:
        out = check_out(args.out)
    except RehearsalError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    os.makedirs(out, exist_ok=True)
    failed = 0
    for scenario in args.scenario or SCENARIOS:
        try:
            failed += run(scenario, out)
        except RehearsalError as exc:
            print(f"[error] {scenario}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
