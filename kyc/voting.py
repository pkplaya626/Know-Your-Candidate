"""How to vote in each state: the official pages, from the secretaries of state.

Nothing on the site told a reader how, when or where to vote (audit
2026-10-13, CG-5), three weeks before the election. The National Association
of Secretaries of State keeps "Can I Vote" (nass.org/can-I-vote), whose four
pages each list one official page per state and D.C.:

    registration status    https://www.nass.org/can-i-vote/voter-registration-status
    polling place          https://www.nass.org/can-i-vote/find-your-polling-place
    absentee and early     https://www.nass.org/can-i-vote/absentee-early-voting
    registering            https://www.nass.org/can-i-vote/register-to-vote

Each is read from the page's own state picker (an <option> per state, its
value the state's URL). The links are the states' own; NASS is the directory.
No date or deadline is typed in anywhere: those change, and the state's page
is where a reader should read them. A page that lists anything but the 50
states and D.C. once each is refused, never written half.

    python build_profile_site.py voting            # refresh (network)
    python build_profile_site.py voting --check    # report from the cache
"""

import datetime
import html
import json
import os
import re
import urllib.request

from .normalize import US_STATES

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "voting_links.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")

# The kind of page, and the NASS page that lists it for every state.
PAGES = {
    "status": "https://www.nass.org/can-i-vote/voter-registration-status",
    "polling": "https://www.nass.org/can-i-vote/find-your-polling-place",
    "absentee": "https://www.nass.org/can-i-vote/absentee-early-voting",
    "register": "https://www.nass.org/can-i-vote/register-to-vote",
}
SOURCE = "https://www.nass.org/can-I-vote"

# The 50 states and D.C.: NASS lists no territory.
JURISDICTIONS = frozenset(code for code in US_STATES.values()
                          if code not in ("PR", "GU", "VI", "AS", "MP"))


class VotingError(RuntimeError):
    """A NASS page could not be read, or does not list every state once."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise VotingError(f"could not fetch {url}: {exc}") from exc


_OPTION = re.compile(r'<option[^>]*\bvalue="([^"]+)"[^>]*>([^<]+)</option>', re.I)


def parse(page):
    """``{state code: url}`` from one NASS page's state picker.

    Refused unless every one of the 50 states and D.C. appears exactly once,
    with an http(s) link, and nothing else does.
    """
    found, problems = {}, []
    for url, label in _OPTION.findall(page):
        name = html.unescape(label).strip().upper()
        code = US_STATES.get(name)
        url = html.unescape(url).strip()
        if code is None:
            problems.append(f"an option that is not a state: {label.strip()!r}")
            continue
        if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url):
            problems.append(f"{code}: not a web address: {url!r}")
            continue
        if code in found:
            problems.append(f"{code} is listed twice")
            continue
        found[code] = url
    missing = sorted(JURISDICTIONS - set(found))
    extra = sorted(set(found) - JURISDICTIONS)
    if missing:
        problems.append("no link for " + ", ".join(missing))
    if extra:
        problems.append("a link for " + ", ".join(extra) + ", which NASS does not cover")
    if problems:
        raise VotingError("; ".join(problems))
    return found


def fetch(get=_get):
    """Every state's four official voting pages, as NASS lists them."""
    pages = {}
    for kind, url in PAGES.items():
        try:
            pages[kind] = parse(get(url))
        except VotingError as exc:
            raise VotingError(f"{url}: {exc}") from exc
    states = {code: {kind: pages[kind][code] for kind in PAGES} for code in sorted(JURISDICTIONS)}
    return {"source": SOURCE, "pages": dict(PAGES), "states": states}


def save_cache(payload, root="."):
    payload = dict(payload, fetched=datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"))
    path = os.path.join(root, CACHE_PATH)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def for_page(cache):
    """``{code: {kind: url}, "_source": ..., "_checked": ...}`` for the build meta."""
    if not cache:
        return {}
    out = {code: dict(links) for code, links in (cache.get("states") or {}).items()}
    out["_source"] = cache.get("source") or SOURCE
    out["_checked"] = (cache.get("fetched") or "")[:10]
    return out
