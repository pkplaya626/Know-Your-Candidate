"""Outside spending: independent expenditures for and against each 2026
candidate, from the FEC.

A reader deciding how much a race is being fought over saw only what the
campaigns themselves raised (PERSONA-12). Groups that are not the campaign -
party committees, super PACs, other PACs - report what they spend for or
against a candidate on Schedule E, and the FEC totals it by candidate and
committee (``/schedules/schedule_e/by_candidate/``). This reads those totals
for the 2026 cycle by each profile's own FEC candidate id, at the pace the
key reports (rule 37), and keeps them in a hand-editable cache.

Attribution is by id and is checked (rule 20). A row counts for a profile
only when its candidate id is one the profile carries and the id's own
office and state are the profile's; a row the FEC filed under no candidate
id is never attributed by name. Totals are shown per side, as filed: what
was spent supporting and what was spent opposing, never one figure netted
from the two. Each side lists the committees that spent it.

The totals are the 2025-26 two-year cycle's, not a senator's six-year
election period: read over the election period, Jon Ossoff's rows held
spending from Georgia's January 2021 runoff, about another election
entirely, and came back once per cycle. They are the FEC's processed
filings, which trail the 24- and 48-hour reports by days; the page dates
them by the day they were read.

    python build_profile_site.py outside            # refresh (network)
    python build_profile_site.py outside --check    # report from the cache
"""

import datetime
import json
import os
import re

from . import fec

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "outside_spending.json")
ENDPOINT = "/schedules/schedule_e/by_candidate/"
CYCLE = fec.CYCLE
BATCH = 40              # candidate ids per request
PER_PAGE = 100
# What the page lists by name on each side; the FEC's table has the rest.
LISTED = 3
FEC_ID = re.compile(r"^([HSP])\d([A-Z]{2})")


class OutsideError(RuntimeError):
    pass


def fec_url(candidate_id, cycle=CYCLE):
    """The FEC's table of the independent expenditures naming a candidate."""
    return ("https://www.fec.gov/data/independent-expenditures/?data_type=processed"
            f"&candidate_id={candidate_id}&cycle={cycle}&is_notice=false")


def _key(row):
    return (row.get("candidate_id"), row.get("committee_id"), row.get("cycle"),
            row.get("support_oppose_indicator"))


def _fetch_batch(ids, get):
    """Every by-candidate row for *ids*, in one page where they fit; a
    batch that does not fit is split, and one candidate's rows over a page
    are paged on a unique sort and counted (rule 36)."""
    params = {"cycle": CYCLE, "election_full": "false", "candidate_id": list(ids),
              "per_page": PER_PAGE}
    payload = get(ENDPOINT, dict(params, page=1))
    count = (payload.get("pagination") or {}).get("count", 0)
    rows = payload.get("results") or []
    if count <= PER_PAGE:
        if len(rows) != count:
            raise OutsideError(f"{len(rows)} rows where the FEC counted {count}")
        return rows
    if len(ids) > 1:
        half = len(ids) // 2
        return _fetch_batch(ids[:half], get) + _fetch_batch(ids[half:], get)
    # One candidate's rows over a page: each side on its own, where the
    # committee is unique, sorted on it. Sorted on committee and side
    # together, the API ignored the second key and Senate candidate
    # S8GA00180's 101 rows came back as 89 distinct.
    rows = []
    for side in ("S", "O"):
        found, page, expected = [], 1, None
        while True:
            payload = get(ENDPOINT, dict(params, page=page, support_oppose_indicator=side,
                                         sort="committee_id"))
            results = payload.get("results") or []
            found += results
            pagination = payload.get("pagination") or {}
            if expected is None:
                expected = pagination.get("count", 0)
            if not results or page >= pagination.get("pages", 1):
                break
            page += 1
        distinct = {_key(r) for r in found}
        if len(distinct) != len(found) or len(found) != expected:
            raise OutsideError(f"{ids[0]} ({side}): {len(found)} rows ({len(distinct)} distinct) "
                               f"where the FEC counted {expected}")
        rows += found
    if len(rows) != count:
        raise OutsideError(f"{ids[0]}: {len(rows)} rows where the FEC counted {count}")
    return rows


def fetch(candidate_ids, get=None, log=print, today=None):
    """The cache: every row for *candidate_ids*, by candidate id."""
    get = get or fec._get
    ids = sorted({i for i in candidate_ids if i and FEC_ID.match(i)})
    by_id = {}
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        try:
            rows = _fetch_batch(batch, get)
        except OutsideError:
            rows = _fetch_batch(batch, get)          # once more, then refuse
        for row in rows:
            cid = row.get("candidate_id")
            if cid not in batch:
                raise OutsideError(f"a row for {cid!r}, which was not asked for")
            side = {"S": "support", "O": "oppose"}.get(row.get("support_oppose_indicator"))
            if not side:
                continue
            entry = by_id.setdefault(cid, {"support": [], "oppose": []})
            entry[side].append({
                "committeeId": row.get("committee_id"),
                "committee": row.get("committee_name") or row.get("committee_id"),
                "total": round(float(row.get("total") or 0), 2),
                "count": row.get("count"),
            })
        if start and start % (BATCH * 10) == 0:
            log(f"  {start} of {len(ids)} candidate ids read")
    for entry in by_id.values():
        for side in entry.values():
            side.sort(key=lambda r: (-r["total"], r["committeeId"] or ""))
    return {"read": today or datetime.date.today().isoformat(), "cycle": CYCLE,
            "asked": len(ids), "candidates": by_id}


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def profile_ids(profile):
    return [i for i in [profile.get("fecCandidateId")] + list(profile.get("otherFecIds") or [])
            if i]


def office_of(profile):
    return "S" if "Senate" in (profile.get("chamber") or "") else "H"


def apply(profiles, cache):
    """Attach ``outsideSpending`` to each profile with a row, checked
    against the profile's office and state; returns ``(applied, refused)``,
    *refused* naming each row that was filed for another seat."""
    refused = []
    applied = 0
    rows = (cache or {}).get("candidates") or {}
    for profile in profiles:
        profile.pop("outsideSpending", None)
        sides = {"support": [], "oppose": []}
        ids = []
        for cid in profile_ids(profile):
            entry = rows.get(cid)
            if not entry:
                continue
            match = FEC_ID.match(cid)
            if not match or match.group(1) != office_of(profile) or match.group(2) != profile["state"]:
                refused.append(f"{profile['name']} ({profile.get('officeLabel')}): {cid}")
                continue
            ids.append(cid)
            for side in sides:
                sides[side] += entry.get(side) or []
        if not ids:
            continue
        out = {"asOf": cache["read"], "cycle": cache.get("cycle", CYCLE),
               "url": fec_url(ids[0], cache.get("cycle", CYCLE))}
        for side, items in sides.items():
            items = sorted(items, key=lambda r: (-r["total"], r["committeeId"] or ""))
            out[side] = round(sum(r["total"] for r in items), 2)
            out[side + "Committees"] = len(items)
            out[side + "Top"] = [{"committee": r["committee"], "total": round(r["total"])}
                                 for r in items[:LISTED]]
        if not out["support"] and not out["oppose"]:
            continue
        profile["outsideSpending"] = out
        applied += 1
    return applied, refused


def problems(cache, refused):
    out = []
    if not cache:
        return [("warn", "outside-missing",
                 f"no {CACHE_PATH}; run: python build_profile_site.py outside", [])]
    if refused:
        out.append(("error", "outside-attribution",
                    f"{len(refused)} outside-spending rows filed for another seat than the "
                    "profile's", refused))
    return out
