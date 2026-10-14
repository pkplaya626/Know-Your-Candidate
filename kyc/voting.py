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
value the state's URL). The links are the states' own; NASS is the directory,
and NASS's directory is not always current: on 2026-10-14 Iowa's and
Indiana's absentee links answered 404 and Hawaii's carried a stale session
id that ended on an error page. So:

- a link must be on its state's own election domain (``official``), or the
  page is refused;
- every link is opened (``check_links``), and only a 404, a 410 or a name
  that does not resolve, seen twice, counts as dead - a bot wall, a 403 or a
  timeout concludes nothing (rule 8);
- what NASS lists wrongly is replaced through ``overrides.VOTING_LINKS``, with
  the state's own page and the evidence, at read time, so the weekly re-read
  cannot put a dead link back; and a dead link with no override is not shown.

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
import socket
import time
import urllib.error
import urllib.parse
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

# Election domains that are neither .gov nor state.<xx>.us, each the state's
# own as NASS lists it (checked 2026-10-14), and valid for that state only:
# a lapsed or resold domain under another state's name is refused.
OFFICIAL_HOSTS = {
    "akelections.maps.arcgis.com": "AK",   # the Division of Elections' map service
    "voterview.ar-nova.org": "AR",         # Arkansas's VoterView
    "arizona.vote": "AZ",                  # the Secretary of State's voter portal
    "dcboe.org": "DC",                     # the D.C. Board of Elections
    "myflorida.com": "FL",                 # Florida's state domain
    "voteks.org": "KS",                    # the Secretary of State's voter site
    "msegov.com": "MS",                    # the Secretary of State's portal
    "okelections.us": "OK",                # the State Election Board
}


class VotingError(RuntimeError):
    """A NASS page could not be read, or does not list every state once."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise VotingError(f"could not fetch {url}: {exc}") from exc


def official(url, code):
    """Is *url* on *code*'s own election domain?"""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if host.endswith(".gov") or re.search(r"\.state\.[a-z]{2}\.us$", host):
        return True
    return any(OFFICIAL_HOSTS[suffix] == code and (host == suffix or host.endswith("." + suffix))
               for suffix in OFFICIAL_HOSTS)


# An ASP.NET cookieless session id in the path, "(S(vb2rc...))" raw or
# percent-encoded: Hawaii's, frozen into NASS's link, ended on an error page.
_SESSION = re.compile(r"/(?:\(|%28)S(?:\(|%28)[A-Za-z0-9]+(?:\)|%29)(?:\)|%29)", re.I)
# The value attribute itself, never a data-value after it.
_OPTION = re.compile(r'<option\b[^>]*?\svalue="([^"]*)"[^>]*>([^<]+)</option>', re.I)
_URL = re.compile(r"^https?://[^\s/]+\.[^\s/]+\S*$")


def parse(page):
    """``{state code: url}`` from one NASS page's state picker.

    Refused unless every one of the 50 states and D.C. appears exactly once,
    with a web address on its own election domain, and nothing else does.
    """
    found, problems = {}, []
    for url, label in _OPTION.findall(page):
        name = html.unescape(label).strip()
        url = _SESSION.sub("", html.unescape(url).strip())
        if not url and name.lower().startswith("select"):
            continue                       # the picker's own placeholder
        code = US_STATES.get(name.upper())
        if code is None:
            problems.append(f"an option that is not a state: {name!r}")
            continue
        if not _URL.match(url):
            problems.append(f"{code}: not a web address: {url!r}")
            continue
        if not official(url, code):
            problems.append(f"{code}: not on {name}'s own election domain: {url}")
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


# ------------------------------------------------------------------ liveness

DEAD = "dead"
LIVE = "live"
UNKNOWN = "unknown"


def _status(url, timeout=25):
    """One request: ``(HTTP status, the URL it ended on)``, ``("nxdomain",
    url)``, or ``(None, url)`` for inconclusive."""
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.geturl() or url
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, socket.gaierror):
            # The name that failed may be a redirect's, not the link's own:
            # Minnesota sends a script to a bot check whose host does not
            # resolve here. Only the link's own host failing is "nxdomain".
            try:
                socket.getaddrinfo(_host(url), 443)
            except OSError:
                return "nxdomain", url
        return None, url
    except (OSError, ValueError):
        return None, url


def _host(url):
    return (urllib.parse.urlsplit(url or "").hostname or "").lower()


def check_links(urls, status=_status, pause=1.0, sleep=time.sleep):
    """``{url: "live" | "dead" | "unknown"}``, one paced request per URL.

    Dead only on a 404, a 410 or a name that does not resolve, from the
    link's own host, seen again on a second request. Everything else that
    is not a success concludes nothing (rule 8): a 403, a 429, a 5xx, a
    timeout, and a 404 from somewhere else. Minnesota's every page,
    its home page included, redirects to a Radware bot check
    (validate.perfdrive.com) that answers a script with 404, and the first
    pass called three of them dead.
    """
    def gone(code, final):
        return code == "nxdomain" or (code in (404, 410) and _host(final) == _host(url))

    out = {}
    for url in sorted(set(urls)):
        code, final = status(url)
        sleep(pause)
        if isinstance(code, int) and 200 <= code < 400:
            out[url] = LIVE
        elif gone(code, final):
            again, final = status(url)
            sleep(pause)
            out[url] = DEAD if gone(again, final) else UNKNOWN
        else:
            out[url] = UNKNOWN
    return out


def fetch(get=_get, status=_status, check=True, pause=1.0, sleep=time.sleep):
    """Every state's four official voting pages, as NASS lists them, each
    opened once (unless *check* is false)."""
    pages = {}
    for kind, url in PAGES.items():
        try:
            pages[kind] = parse(get(url))
        except VotingError as exc:
            raise VotingError(f"{url}: {exc}") from exc
    states = {code: {kind: pages[kind][code] for kind in PAGES} for code in sorted(JURISDICTIONS)}
    cache = {"source": SOURCE, "pages": dict(PAGES), "states": states}
    if check:
        shown = [link["url"] for links in effective(cache).values() for link in links.values()]
        cache["links"] = check_links(shown, status=status, pause=pause, sleep=sleep)
        cache["linksChecked"] = datetime.date.today().isoformat()
    return cache


# ------------------------------------------------------------- what is shown

def effective(cache):
    """``{code: {kind: {"url", "label"?}}}``: NASS's links with the evidenced
    replacements applied, and nothing a replacement drops.

    An override applies only while NASS still lists the URL it replaces;
    once NASS changes its entry, NASS's is shown and validate says so.
    """
    from . import overrides

    out = {}
    for code, links in ((cache or {}).get("states") or {}).items():
        shown = {}
        for kind, url in links.items():
            fix = overrides.VOTING_LINKS.get((code, kind))
            if fix and fix[0] == url:
                if fix[1]:
                    shown[kind] = {"url": fix[1], **({"label": fix[2]} if fix[2] else {})}
                continue
            shown[kind] = {"url": url}
        out[code] = shown
    return out


def stale_overrides(cache):
    """Overrides whose NASS entry has changed: each may now be unneeded."""
    from . import overrides

    states = (cache or {}).get("states") or {}
    return sorted(f"{code} {kind}: NASS now lists {(states.get(code) or {}).get(kind)}"
                  for (code, kind), fix in overrides.VOTING_LINKS.items()
                  if (states.get(code) or {}).get(kind) != fix[0])


def dead_links(cache):
    """Links shown that were found dead, for a person to replace."""
    status = (cache or {}).get("links") or {}
    return sorted(f"{code} {kind}: {link['url']}"
                  for code, links in effective(cache).items()
                  for kind, link in links.items() if status.get(link["url"]) == DEAD)


def for_page(cache):
    """The build meta's ``voting``: ``{code: {kind: url}}``, labels apart.

    A link found dead is left out rather than sent to a reader, until an
    override replaces it.
    """
    if not cache:
        return {}
    status = cache.get("links") or {}
    out, labels = {}, {}
    for code, links in effective(cache).items():
        out[code] = {kind: link["url"] for kind, link in links.items()
                     if status.get(link["url"]) != DEAD}
        named = {kind: link["label"] for kind, link in links.items() if link.get("label")}
        if named:
            labels[code] = named
    out["_labels"] = labels
    out["_source"] = cache.get("source") or SOURCE
    out["_listed"] = (cache.get("fetched") or "")[:10]
    out["_opened"] = cache.get("linksChecked") or ""
    return out


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
