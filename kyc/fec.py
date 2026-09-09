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


ENV_FILE = ".env"


def _key_from_env_file(root="."):
    """Read ``FEC_API_KEY`` from a local ``.env``, if there is one.

    A convenience so the key can live in one gitignored file instead of a
    shell profile. ``.gitignore`` already covers ``*.env``; there is a test
    that asserts it, because committing an API key is the kind of mistake
    that is trivial to make once and permanent afterwards.
    """
    path = os.path.join(root, ENV_FILE)
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "FEC_API_KEY":
                    return value.strip().strip("'\"")
    except OSError:
        return ""
    return ""


def api_key(root="."):
    """The FEC key: the environment first, then ``.env``, then ``DEMO_KEY``."""
    return (
        os.environ.get("FEC_API_KEY", "").strip()
        or _key_from_env_file(root)
        or "DEMO_KEY"
    )


def using_demo_key(root="."):
    return api_key(root) == "DEMO_KEY"


def _get(path, params, retries=4):
    params = dict(params, api_key=api_key())
    # doseq: several OpenFEC parameters are repeatable (office=H&office=S).
    # Without it a list is encoded as its Python repr and the API returns 422.
    url = f"{API_ROOT}{path}?{urllib.parse.urlencode(params, doseq=True)}"
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


def known_ids(snapshot, active_ids=None):
    """``{bioguide: fec_candidate_id}`` from the authoritative membership.

    ``congress-legislators`` records the FEC candidate id for 537 of the 539
    sitting members, already scoped to the seat they currently hold. Using it
    removes the name search for every incumbent, which is where the risk
    lives: the FEC files people under their legal name - Ashley Hinson appears
    as "ARENHOLZ, ASHLEY HINSON" - so matching is fuzzy by necessity, and a
    fuzzy match that lands on the wrong person puts someone else's money on a
    profile without anything looking wrong.

    *active_ids* is the set of candidate ids the FEC lists for the current
    cycle. Fifteen members carry more than one id, and simply taking the first
    was wrong for four of them: Glenn Ivey's committee for this cycle is his
    second id, so the lookup asked about a committee with no 2026 activity and
    the profile reported "No filing this cycle" while $674,406 sat under the
    other one. An old committee id looks exactly as authoritative as a current
    one, which is why the cycle has to be the tie-breaker.
    """
    ids = {}
    for person in (snapshot or {}).get("legislators", []):
        candidate_ids = person.get("fec") or []
        if not candidate_ids:
            continue
        if active_ids:
            live = [i for i in candidate_ids if i in active_ids]
            if live:
                ids[person["bioguide"]] = live[0]
                continue
        ids[person["bioguide"]] = candidate_ids[0]
    return ids


def resolve_all(profiles, root=".", limit=None, refresh=False, snapshot=None,
                active_ids=None, log=print):
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

    authoritative = known_ids(snapshot, active_ids)
    if authoritative:
        covered = sum(1 for p in todo if p["id"] in authoritative)
        log(f"  finance: {covered} of {len(todo)} have an authoritative FEC id")

    log(f"  finance: looking up {len(todo)} profile(s) ...")
    found = stopped = by_id = 0

    # A full run is several hundred requests over several minutes. The cache
    # used to be written once at the end, so the documented promise that a run
    # "resumes exactly where the previous one stopped" only held for a clean
    # rate-limit stop - a Ctrl-C or a dropped connection threw the whole run
    # away. Checkpointing costs one small write per 25 lookups.
    CHECKPOINT = 25

    for done, profile in enumerate(todo, start=1):
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
        except KeyboardInterrupt:
            log(f"  [stop] interrupted after {done} of {len(todo)}")
            stopped = 1
            break

        if done % CHECKPOINT == 0:
            save_cache(cache, root)
            log(f"    {done}/{len(todo)} looked up ({found} with totals)")

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
    from .normalize import NO_FILING, STATUS_LABELS

    applied = checked = 0
    for profile in profiles:
        record = cache.get(profile_key(profile)) or {}

        if record.get("receipts") is None:
            # We identified this person at the FEC and it holds nothing for
            # this cycle. That is a different fact from "nobody has looked",
            # and the reader is entitled to the difference: several sitting
            # members here are running for a *different* seat, so their money
            # is in another committee entirely.
            if record.get("candidate_id") and not record.get("found"):
                # Record the id even with no totals: it is how the FEC field
                # import recognises that this person already has a profile.
                # Omitting it duplicated four sitting members.
                profile["fecCandidateId"] = record["candidate_id"]
                quality = profile.setdefault("quality", {})
                for field in ("receipts", "disbursements"):
                    quality[field] = NO_FILING
                    profile[field] = STATUS_LABELS[NO_FILING]
                profile["financeCycle"] = CYCLE
                checked += 1
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
