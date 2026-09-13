"""Campaign websites, from each candidate's principal committee at the FEC.

A voter who has found the person running for their seat wants to read what
that person says for themselves. A sitting member has an official site in
``congress-legislators``; a challenger has nothing on their profile but a
name and a dollar figure. The FEC's committee register carries a ``website``
for most principal campaign committees - filed by the treasurer on Form 1, so
it is the campaign's own statement of where it lives - and that is the only
source that covers the whole field without guessing.

One request per candidate, against ``/candidate/{id}/committees/``. The key
allows 1,000 an hour, so a full pass over everyone on a ballot takes about an
hour and resumes from the cache when interrupted. Off-ballot filers are not
looked up: a site for someone the primary eliminated is not what the page is
for, and the request budget is better spent on the people still running.
"""

import datetime
import json
import os
import re
import time

from . import fec
from .results import OFF_BALLOT

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "campaigns.json")

# Stay under the documented 1,000 requests an hour with room for retries.
_GAP = 3.7

_NOT_A_SITE = re.compile(r"^(n/?a|none|null|no website|tbd|-+)$", re.I)


class CampaignsError(RuntimeError):
    pass


# ------------------------------------------------------------------- shaping

def normalise_url(raw):
    """``"WWW.KENPAXTON.COM"`` -> ``"https://www.kenpaxton.com"``, or ``None``.

    Treasurers type the field by hand: upper case, no scheme, sometimes an
    email address or "N/A". Only something with a dotted host survives, and
    the host is lower-cased while any path keeps its case.
    """
    text = str(raw or "").strip().strip('"').strip()
    if not text or _NOT_A_SITE.match(text) or "@" in text or " " in text:
        return None
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    match = re.match(r"^(https?)://([^/?#]+)(.*)$", text, re.I)
    if not match:
        return None
    scheme, host, rest = match.groups()
    host = host.lower().rstrip(".")
    if "." not in host or re.search(r"[^a-z0-9.-]", host):
        return None
    return f"{scheme.lower()}://{host}{rest}"


def principal_committee(candidate_id, cycle=fec.CYCLE):
    """The candidate's principal campaign committee for *cycle*, or ``None``."""
    payload = fec._get(f"/candidate/{candidate_id}/committees/",
                       {"cycle": cycle, "designation": "P", "per_page": 5})
    rows = payload.get("results") or []
    if not rows:
        return None
    # Several principal committees is rare; the most recently filed wins.
    rows.sort(key=lambda r: r.get("last_file_date") or "", reverse=True)
    row = rows[0]
    return {
        "committee_id": row.get("committee_id"),
        "name": row.get("name"),
        "website": row.get("website"),
        "last_file_date": row.get("last_file_date"),
    }


# --------------------------------------------------------------------- cache

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


def wanted(profiles):
    """Who to look up, most useful first: nominees, then sitting members,
    then everyone else still on a ballot. Off-ballot filers are skipped."""
    def rank(profile):
        status = profile.get("raceStatus")
        if status in ("nominee", "advanced"):
            return 0
        if not profile.get("isCandidate"):
            return 1
        return 2

    people = [p for p in profiles
              if p.get("fecCandidateId") and p.get("raceStatus") not in OFF_BALLOT]
    people.sort(key=lambda p: (rank(p), p.get("name", "")))
    return people


def resolve_all(profiles, root=".", limit=None, refresh=False, log=print):
    """Look up the principal committee for everyone on a ballot, resuming
    from the cache. Returns ``(cache, stats)``."""
    cache = load_cache(root)
    todo = [p for p in wanted(profiles)
            if refresh or p["fecCandidateId"] not in cache]
    if limit:
        todo = todo[:limit]
    if not todo:
        log(f"  campaigns: {len(cache)} cached, nothing to look up")
        return cache, {"cached": len(cache), "looked_up": 0, "stopped": 0}

    if fec.using_demo_key(root):
        log("  [warn] using DEMO_KEY - the FEC will throttle after a few requests.")

    log(f"  campaigns: looking up {len(todo)} committee(s), about "
        f"{len(todo) * _GAP / 60:.0f} minutes ...")
    looked_up = stopped = with_site = 0
    fetched = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        for done, profile in enumerate(todo, start=1):
            cid = profile["fecCandidateId"]
            try:
                committee = principal_committee(cid)
            except fec.FecError as exc:
                log(f"  [stop] {exc}")
                stopped = 1
                break
            record = {"person": profile["name"], "fetched": fetched, "found": committee is not None}
            if committee:
                record.update(committee)
                record["url"] = normalise_url(committee.get("website"))
                if record["url"]:
                    with_site += 1
            cache[cid] = record
            looked_up += 1
            if done % 25 == 0:
                save_cache(cache, root)
                log(f"    {done}/{len(todo)} looked up ({with_site} with a site)")
            time.sleep(_GAP)
    except KeyboardInterrupt:
        log(f"  [stop] interrupted after {looked_up} of {len(todo)}")
        stopped = 1

    save_cache(cache, root)
    total_sites = sum(1 for r in cache.values() if r.get("url"))
    log(f"  campaigns: {total_sites}/{len(cache)} cached committees have a website")
    return cache, {"cached": len(cache), "looked_up": looked_up, "stopped": stopped,
                   "with_site": with_site}


def apply_cache(profiles, cache):
    """Attach ``campaignSite`` (and the committee's name) to every profile
    whose candidate id the cache knows. Returns how many got a site."""
    if not cache:
        return 0
    applied = 0
    for profile in profiles:
        record = cache.get(profile.get("fecCandidateId"))
        if not record or not record.get("found"):
            continue
        if record.get("name") and record.get("committee_id"):
            profile["campaignCommittee"] = record["name"]
            profile["campaignCommitteeId"] = record["committee_id"]
        if record.get("url"):
            profile["campaignSite"] = record["url"]
            applied += 1
    return applied
