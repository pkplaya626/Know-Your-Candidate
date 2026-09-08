"""Campaign finance from the FEC's OpenFEC API.

Campaign finance is one of the project's four stated pillars, yet 67% of
sitting members had no receipts figure at all. This fills that gap from the
authoritative source and records where every number came from.

An API key is required. Get a free one at https://api.data.gov/signup/ and
export it::

    export FEC_API_KEY=...            # Linux/macOS
    $env:FEC_API_KEY = "..."          # PowerShell

Without a key the module falls back to ``DEMO_KEY``, which the FEC rate-limits
to a handful of requests per hour - enough to try it out, not enough to fill
594 profiles. Results are cached in ``candidate_profiles_site/data/finance.json``
so a run resumes exactly where the previous one stopped.

    python build_profile_site.py finance --limit 50
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.open.fec.gov/v1"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "finance.json")
CYCLE = 2026

_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 30
_GAP = 0.4  # be polite; the documented limit is 1000/hour on a real key


class FecError(RuntimeError):
    pass


def api_key():
    return os.environ.get("FEC_API_KEY", "").strip() or "DEMO_KEY"


def using_demo_key():
    return api_key() == "DEMO_KEY"


def _get(path, params, retries=4):
    params = dict(params, api_key=api_key())
    url = f"{API_ROOT}{path}?{urllib.parse.urlencode(params)}"
    delay = 1.5
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                if using_demo_key():
                    raise FecError(
                        "FEC rate limit hit on DEMO_KEY. Set FEC_API_KEY to a free "
                        "key from https://api.data.gov/signup/ to continue."
                    ) from exc
            elif exc.code not in (500, 502, 503, 504):
                raise FecError(f"FEC {exc.code} for {path}") from exc
        except Exception as exc:
            last = exc
        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 2
    raise FecError(f"FEC request failed: {path} ({last})")


def _surname(name):
    parts = [p for p in re.sub(r"[^\w\s-]", "", str(name)).split() if p]
    return parts[-1].lower() if parts else ""


def find_candidate(name, state, chamber, cycle=CYCLE):
    """Best FEC candidate record for a person, or ``None``.

    The FEC files people under their legal name - Ashley Hinson appears as
    "ARENHOLZ, ASHLEY HINSON" - so the surname must appear somewhere in the
    filed name rather than matching it exactly.
    """
    office = "S" if "Senate" in chamber else "H"
    params = {
        "q": name,
        "office": office,
        "election_year": cycle,
        "per_page": 10,
        "sort": "-first_file_date",
    }
    if state and state != "N/A":
        params["state"] = state

    payload = _get("/candidates/search/", params)
    surname = _surname(name)

    for result in payload.get("results", []):
        filed = str(result.get("name", "")).lower()
        if surname and surname in filed:
            return {
                "candidate_id": result.get("candidate_id"),
                "filed_name": result.get("name"),
                "office": result.get("office"),
                "state": result.get("state"),
                "party": result.get("party"),
            }
    return None


def totals(candidate_id, cycle=CYCLE):
    """Receipts/disbursements/cash for one candidate in *cycle*."""
    payload = _get(f"/candidate/{candidate_id}/totals/", {"cycle": cycle, "per_page": 1})
    results = payload.get("results") or []
    if not results:
        return None
    row = results[0]
    return {
        "receipts": row.get("receipts"),
        "disbursements": row.get("disbursements"),
        "cash_on_hand": row.get("last_cash_on_hand_end_period"),
        "individual_contributions": row.get("individual_contributions"),
        "pac_contributions": row.get("other_political_committee_contributions"),
        "party_contributions": row.get("political_party_committee_contributions"),
        "self_funding": row.get("candidate_contribution"),
        "coverage_end": (row.get("coverage_end_date") or "")[:10],
    }


# --------------------------------------------------------------------- cache

def profile_key(profile):
    return f"{profile['name'].lower()}|{profile['state']}|{'S' if 'Senate' in profile['chamber'] else 'H'}"


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return {}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def known_ids(snapshot):
    """``{bioguide: fec_candidate_id}`` from the authoritative membership.

    ``congress-legislators`` records the FEC candidate id for 537 of the 539
    sitting members, already scoped to the seat they currently hold. Using it
    removes the name search for every incumbent, which is where the risk
    lives: the FEC files people under their legal name - Ashley Hinson appears
    as "ARENHOLZ, ASHLEY HINSON" - so matching is fuzzy by necessity, and a
    fuzzy match that lands on the wrong person puts someone else's money on a
    profile without anything looking wrong.
    """
    ids = {}
    for person in (snapshot or {}).get("legislators", []):
        candidate_ids = person.get("fec") or []
        if candidate_ids:
            ids[person["bioguide"]] = candidate_ids[0]
    return ids


def resolve_all(profiles, root=".", limit=None, refresh=False, snapshot=None,
                log=print):
    """Look up finance totals, resuming from the cache.

    Requests are sequential and rate-limited on purpose; the FEC key allows
    1000 requests an hour. A profile with a known FEC id costs one request
    instead of two, so passing *snapshot* roughly halves a full run as well as
    making it exact.
    """
    cache = load_cache(root)
    todo = [p for p in profiles if refresh or profile_key(p) not in cache]
    todo = [p for p in todo if not (cache.get(profile_key(p)) or {}).get("pinned")]

    if limit:
        todo = todo[:limit]
    if not todo:
        log(f"  finance: {len(cache)} cached, nothing to look up")
        return cache, {"cached": len(cache)}

    if using_demo_key():
        log("  [warn] using DEMO_KEY - the FEC will throttle after a few requests.")
        log("         Set FEC_API_KEY from https://api.data.gov/signup/ for a full run.")

    authoritative = known_ids(snapshot)
    if authoritative:
        covered = sum(1 for p in todo if p["id"] in authoritative)
        log(f"  finance: {covered} of {len(todo)} have an authoritative FEC id")

    log(f"  finance: looking up {len(todo)} profile(s) ...")
    found = stopped = by_id = 0

    for profile in todo:
        key = profile_key(profile)
        try:
            candidate_id = authoritative.get(profile["id"])
            if candidate_id:
                match = {"candidate_id": candidate_id, "via": "congress-legislators"}
                by_id += 1
            else:
                match = find_candidate(
                    profile["name"], profile["state"], profile["chamber"]
                )
                time.sleep(_GAP)
                if match:
                    match["via"] = "fec-search"

            if not match:
                cache[key] = {"found": False, "name": profile["name"]}
                continue

            figures = totals(match["candidate_id"])
            time.sleep(_GAP)
            cache[key] = {
                "found": bool(figures),
                "name": profile["name"],
                **match,
                **(figures or {}),
            }
            if figures:
                found += 1
        except FecError as exc:
            log(f"  [stop] {exc}")
            stopped = 1
            break

    save_cache(cache, root)
    hits = sum(1 for r in cache.values() if r.get("receipts") is not None)
    log(f"  finance: {hits}/{len(cache)} cached profiles have FEC totals"
        + (f" ({by_id} matched by authoritative id)" if by_id else ""))
    return cache, {"cached": len(cache), "found": found, "stopped": stopped,
                   "by_id": by_id}


def _money(value):
    return f"${float(value):,.2f}" if value is not None else None


def apply_cache(profiles, cache):
    """Overlay FEC figures onto profiles, replacing roster estimates."""
    applied = 0
    for profile in profiles:
        record = cache.get(profile_key(profile)) or {}
        if record.get("receipts") is None:
            continue

        profile["receipts"] = _money(record["receipts"])
        profile["disbursements"] = _money(record.get("disbursements"))
        profile["cashOnHand"] = _money(record.get("cash_on_hand"))
        profile["financeSource"] = "FEC"
        profile["financeAsOf"] = record.get("coverage_end")
        profile["fecCandidateId"] = record.get("candidate_id")

        breakdown = {
            "Individual": record.get("individual_contributions"),
            "PACs": record.get("pac_contributions"),
            "Party": record.get("party_contributions"),
            "Self-funded": record.get("self_funding"),
        }
        profile["fundingBreakdown"] = {
            k: float(v) for k, v in breakdown.items() if v
        }

        quality = profile.setdefault("quality", {})
        quality.pop("receipts", None)
        quality.pop("disbursements", None)
        if profile["fundingBreakdown"]:
            quality.pop("funding_sources", None)
            profile["funding_sources"] = ", ".join(
                f"{k} {v / sum(profile['fundingBreakdown'].values()):.0%}"
                for k, v in sorted(
                    profile["fundingBreakdown"].items(), key=lambda kv: -kv[1]
                )
            )
        profile["hasRealFinance"] = True
        applied += 1
    return applied
