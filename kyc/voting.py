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
    # Texas's election-night results, linked as "Election Results" from the
    # Secretary of State's votetexas.gov (checked 2026-10-17).
    "txelections.civixapps.com": "TX",
    # The Commonwealth Election Commission of the Northern Mariana Islands,
    # and Puerto Rico's State Elections Commission (CEE); vote.gov lists both.
    "votecnmi.gov.mp": "MP",
    "ceepur.org": "PR",
}

# Pages NASS does not list, each the state's own and each opened on
# 2026-10-17 from the link the election office's home page gives it (audit
# 2026-10-17: RACES-16, RACES-20, STATEGOV-14). Checked like NASS's links
# (``check_links``) and held to the same domains (``official``).
#
# "results": where the state publishes its returns. Nothing else on the
# site pointed a reader to an official count on election night, and this
# site's own results come from Wikipedia, read twice a week. Every
# jurisdiction has one (validate fails a gap).
RESULTS = {
    "AK": "https://www.elections.alaska.gov/election-results/",
    "AL": "https://www2.alabamavotes.gov/electionnight/statewideresultsbycontest.aspx",
    "AR": "https://www.sos.arkansas.gov/elections/research/election-results",
    "AZ": "https://results.arizona.vote/",
    "CA": "https://electionresults.sos.ca.gov/",
    "CO": "https://www.coloradosos.gov/pubs/elections/resultsData.html",
    "CT": "https://portal.ct.gov/sots/election-services/election-results/election-results",
    "DC": "https://electionresults.dcboe.org/",
    "DE": "https://elections.delaware.gov/results/index.html",
    "FL": "https://results.elections.myflorida.com/",
    "GA": "https://results.sos.ga.gov/results/public/Georgia",
    "HI": "https://elections.hawaii.gov/election-results/",
    "IA": "https://electionresults.iowa.gov/IA/",
    "ID": "https://voteidaho.gov/election-results/",
    "IL": "https://www.elections.il.gov/electionoperations/ElectionVoteTotals.aspx",
    "IN": "https://enr.indianavoters.in.gov/site/index.html",
    "KS": "https://sos.ks.gov/elections/election-results.html",
    "KY": "https://elect.ky.gov/results/Pages/default.aspx",
    "LA": "https://voterportal.sos.la.gov/Graphical",
    "MA": "https://electionstats.state.ma.us/",
    "MD": "https://elections.maryland.gov/elections/2026/index.html",
    "ME": "https://www.maine.gov/sos/elections-voting/election-results-data",
    "MI": "https://www.michigan.gov/sos/elections/election-results-and-data",
    "MN": "https://www.sos.mn.gov/elections-voting/election-results",
    "MO": "https://www.sos.mo.gov/elections/results",
    "MS": "https://www.sos.ms.gov/elections-voting/election-results",
    "MT": "https://sosmt.gov/elections/results/",
    "NC": "https://www.ncsbe.gov/results-data/election-results",
    "ND": "https://www.sos.nd.gov/elections/election-results",
    "NE": "https://electionresults.nebraska.gov/",
    "NH": "https://www.sos.nh.gov/elections/elections/election-results",
    "NJ": "https://www.nj.gov/state/elections/election-information-results.shtml",
    "NM": "https://www.sos.nm.gov/voting-and-elections/election-results/",
    "NV": "https://silverstateelection.nv.gov/",
    "NY": "https://nyenr.elections.ny.gov/",
    "OH": "https://www.ohiosos.gov/elections/election-results-and-data/",
    "OK": "https://results.okelections.us/",
    "OR": "https://sos.oregon.gov/elections/pages/historical-data.aspx",
    "PA": "https://www.electionreturns.pa.gov/",
    "RI": "https://electionresults.ri.gov/results/public/rhodeisland",
    "SC": "https://scvotes.gov/elections-statistics/election-results/",
    "SD": "https://electionresults.sd.gov/Default.aspx",
    "TN": "https://sos.tn.gov/elections/results",
    "TX": "https://goelect.txelections.civixapps.com/ivis-enr-ui/races",
    "UT": "https://vote.utah.gov/election-results-data-historical-information/",
    "VA": "https://www.elections.virginia.gov/resultsreports/election-results/",
    "VT": "https://sos.vermont.gov/elections/election-info-resources/elections-results-data/",
    "WA": "https://www.sos.wa.gov/elections/data-research/election-data-and-maps/election-results-and-voters-pamphlets",
    "WI": "https://elections.wi.gov/elections/election-results",
    "WV": "https://sos.wv.gov/elections/election-data/historical-election-results-and-turnout",
    "WY": "https://sos.wyo.gov/Elections/ElectionResults.aspx",
}

# "sample": a statewide page where a voter sees the ballot they will get,
# only where the election office links one ("Get My Sample Ballot",
# "What's on the ballot?"). Elsewhere sample ballots are the counties' and
# no link is shown rather than a guess.
SAMPLE_BALLOTS = {
    "AK": "https://www.elections.alaska.gov/sample-ballots/",
    "AL": "https://www.sos.alabama.gov/alabama-votes/2026-general-election-sample-ballots",
    "DC": "https://www.dcboe.org/elections/2026-elections",
    "LA": "https://www.sos.la.gov/elections-voting/sample-ballots",
    "MI": "https://mvic.sos.state.mi.us/PublicBallot/Index",
    "MN": "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot",
    "ND": "https://vip.sos.nd.gov/WhereToVote.aspx?tab=AddressandVotingTimes",
    "NM": "https://voterportal.servis.sos.state.nm.us/WhereToVote.aspx",
    "SC": "https://vrems.scvotes.sc.gov/Voter/Login?PageMode=Sampleballot",
    "SD": "https://vip.sdsos.gov/VIPLogin.aspx",
    "WI": "https://myvote.wi.gov/en-us/Whats-On-My-Ballot",
}

# "deadlines": vote.gov's page for the jurisdiction, from vote.gov/register's
# own list (read 2026-10-17). Each lists the online, mail and in-person
# registration deadlines as the state sets them ("29 days before Election
# Day"), and says where a state registers on Election Day. vote.gov is the
# General Services Administration's site, run with the Election Assistance
# Commission; the page calls it the federal government's voting site. No date is typed here: a deadline that
# changes is vote.gov's and the state's to say, and this site never calls
# one passed (STATEGOV-11, PERSONA-03).
VOTE_GOV = "https://vote.gov/register"
DEADLINES = {code: f"{VOTE_GOV}/{slug}" for code, slug in {
    "AK": "alaska", "AL": "alabama", "AR": "arkansas", "AS": "american-samoa", "AZ": "arizona",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DC": "district-of-columbia",
    "DE": "delaware", "FL": "florida", "GA": "georgia", "GU": "guam", "HI": "hawaii",
    "IA": "iowa", "ID": "idaho", "IL": "illinois", "IN": "indiana", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "MA": "massachusetts", "MD": "maryland", "ME": "maine",
    "MI": "michigan", "MN": "minnesota", "MO": "missouri", "MP": "northern-mariana-islands",
    "MS": "mississippi", "MT": "montana", "NC": "north-carolina", "ND": "north-dakota",
    "NE": "nebraska", "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico",
    "NV": "nevada", "NY": "new-york", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "PR": "puerto-rico", "RI": "rhode-island", "SC": "south-carolina",
    "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah", "VA": "virginia",
    "VI": "us-virgin-islands", "VT": "vermont", "WA": "washington", "WI": "wisconsin",
    "WV": "west-virginia", "WY": "wyoming"}.items()}
# vote.gov's own words where "Registration deadlines" would say what its page
# does not: North Dakota's reads "Voter registration is not required in North
# Dakota" (opened 2026-10-17).
DEADLINE_LABELS = {"ND": "No registration needed (vote.gov)"}

# NASS lists no territory, so a territory's page said nothing about voting
# (audit 2026-10-17, RACES-07, STATEGOV-15). Each link is the territory's
# election office's own, from its home page (checked 2026-10-17), with the
# office's own words where a kind's usual label would say more than the page
# does: the CNMI's lookup needs an account, and its registration form is a
# PDF. {code: {kind: (url, label or None)}}. Guam's Election Commission
# refused connections on 2026-10-17; its 2026 page was read that morning.
TERRITORY_LINKS = {
    "GU": {"info": ("https://gec.guam.gov/2026-general-election-info/",
                    "2026 general election: early voting and sample ballots")},
    "VI": {"status": ("https://app.vivote.gov/lookup", None),
           "polling": ("https://vivote.gov/elections/polling-places/", "Find your voting center"),
           "absentee": ("https://vivote.gov/voters/absentee-ballot/", "Vote absentee"),
           "register": ("https://vivote.gov/voters/register-to-vote/", None)},
    "MP": {"status": ("https://www.votecnmi.gov.mp/voter/are-you-a-registered-voter.php",
                      "Check your registration (account needed)"),
           "polling": ("https://www.votecnmi.gov.mp/polling-places.php", None),
           "sample": ("https://www.votecnmi.gov.mp/downloads/2026/2026_GE_BALLOT_SPECIMEN.pdf",
                      "Specimen ballot (PDF)"),
           "register": ("https://www.votecnmi.gov.mp/downloads/registration_package-f.pdf",
                        "Registration package (PDF)"),
           "info": ("https://www.votecnmi.gov.mp/voter/2026-ge-important-dates",
                    "2026 general election: important dates")},
    "AS": {"absentee": ("https://www.aselectionoffice.gov/absentee-voting", "Vote absentee"),
           "register": ("https://www.aselectionoffice.gov/registration", None)},
    "PR": {"register": ("https://ww2.ceepur.org/Home/ServiciosElector",
                        "Voter services (in Spanish)")},
}
# A second round in December, on the page of the state that holds one
# (audit 2026-10-17, PERSONA-06, FRESHNESS-11): Georgia's page never
# mentioned its December 1 runoff, Louisiana's never its December 12 House
# round. The dates are the overrides' (GENERAL_RUNOFFS, OPEN_PRIMARY_SEATS),
# where the results reader uses them; this names the state's own page that
# gives each, and validate fails a date with none.
KEY_DATE_SOURCES = {
    "GA": ("Georgia.gov, General election runoff, December 1, 2026",
           "https://georgia.gov/events/2026-12-01/election-day-general-election-runoff"),
    "LA": ("Louisiana Secretary of State, release of May 14, 2026 on the fall House races",
           "https://www.sos.la.gov/media/dcvl5ojl/051426-fall-house-races.pdf"),
}


def key_dates():
    """``{code: [{"date", "text", "source", "cite"}]}`` from the overrides'
    December dates. A state with no KEY_DATE_SOURCES entry is left out here
    and reported by ``unsourced_key_dates``."""
    from .overrides import GENERAL_RUNOFFS, OPEN_PRIMARY_SEATS

    out = {}
    for code, (date, _evidence) in sorted(GENERAL_RUNOFFS.items()):
        if code in KEY_DATE_SOURCES:
            label, url = KEY_DATE_SOURCES[code]
            out.setdefault(code, []).append({
                "date": date, "source": url, "cite": label,
                "text": "If no candidate for an office wins a majority of the votes on "
                        "November 3, the top two meet in a runoff",
                # Said once the date has passed (rule 63): what the date
                # was, never what will happen on it.
                "past": "The date set for a runoff in any race no candidate won with a "
                        "majority of the votes on November 3"})
    for (code, office, _cycle), seat in sorted(OPEN_PRIMARY_SEATS.items()):
        if code in KEY_DATE_SOURCES and seat.get("runoff"):
            label, url = KEY_DATE_SOURCES[code]
            chamber = "U.S. House" if office == "H" else "U.S. Senate"
            out.setdefault(code, []).append({
                "date": seat["runoff"], "source": url, "cite": label,
                "text": f"The {chamber} vote on November 3 is an open primary; a seat no "
                        f"candidate wins with a majority is decided at a general election",
                "past": f"The date set for a general election for any {chamber} seat no "
                        f"candidate won with a majority in the November 3 open primary"})
    return out


def unsourced_key_dates():
    from .overrides import GENERAL_RUNOFFS, OPEN_PRIMARY_SEATS
    codes = set(GENERAL_RUNOFFS) | {code for (code, _o, _c), seat in OPEN_PRIMARY_SEATS.items()
                                    if seat.get("runoff")}
    return sorted(codes - set(KEY_DATE_SOURCES))


# Each territory's election office, by the name its own site gives it
# (checked 2026-10-17), so the page names the office it credits (rule 75).
TERRITORY_SOURCES = {
    "GU": ("https://gec.guam.gov/", "Guam Election Commission"),
    "VI": ("https://vivote.gov/", "Election System of the Virgin Islands"),
    "MP": ("https://www.votecnmi.gov.mp/", "Commonwealth Election Commission"),
    "AS": ("https://www.aselectionoffice.gov/", "American Samoa Election Office"),
    "PR": ("https://ww2.ceepur.org/", "Comisi\u00f3n Estatal de Elecciones"),
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

# Where each link shown comes from, for the page to say link by link: the
# sentence "the first four from NASS" credited NASS with a curated sample
# ballot page, Wyoming's results page and D.C.'s override (PR #94 review).
# An override's replacement is the office's own page, not NASS's.
NASS = "nass"
OFFICE = "office"
VOTE_GOV_FROM = "vote.gov"


def effective(cache):
    """``{code: {kind: {"url", "from", "label"?}}}``: NASS's links with the
    evidenced replacements applied, nothing a replacement drops, and the
    curated pages beside them; ``from`` is NASS, OFFICE or VOTE_GOV_FROM.

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
                    shown[kind] = {"url": fix[1], "from": OFFICE,
                                   **({"label": fix[2]} if fix[2] else {})}
                continue
            shown[kind] = {"url": url, "from": NASS}
        for kind, table in (("sample", SAMPLE_BALLOTS), ("results", RESULTS),
                            ("deadlines", DEADLINES)):
            if code in table:
                shown[kind] = {"url": table[code],
                               "from": VOTE_GOV_FROM if kind == "deadlines" else OFFICE}
        if code in DEADLINE_LABELS and "deadlines" in shown:
            shown["deadlines"]["label"] = DEADLINE_LABELS[code]
        out[code] = shown
    if out:
        # The territories, which NASS does not list: their election offices'
        # own pages, and vote.gov's.
        for code, links in TERRITORY_LINKS.items():
            shown = {kind: {"url": url, "from": OFFICE, **({"label": label} if label else {})}
                     for kind, (url, label) in links.items()}
            shown["deadlines"] = {"url": DEADLINES[code], "from": VOTE_GOV_FROM}
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
    out, labels, nass, unreached = {}, {}, {}, {}
    for code, links in effective(cache).items():
        out[code] = {kind: link["url"] for kind, link in links.items()
                     if status.get(link["url"]) != DEAD}
        named = {kind: link["label"] for kind, link in links.items() if link.get("label")}
        if named:
            labels[code] = named
        # Which links NASS lists, so the page credits NASS with those and no
        # others; and which were not found live when the links were opened,
        # so the page never says "each link opened" over one that could not
        # be reached (Guam's only link, on 2026-10-17).
        nass[code] = sorted(kind for kind in out[code] if links[kind]["from"] == NASS)
        missed = sorted(kind for kind in out[code] if status.get(links[kind]["url"]) != LIVE)
        if missed:
            unreached[code] = missed
    out["_labels"] = labels
    out["_nass"] = nass
    out["_unreached"] = unreached
    out["_keyDates"] = key_dates()
    out["_territories"] = {code: {"url": url, "name": name}
                           for code, (url, name) in TERRITORY_SOURCES.items()}
    out["_voteGov"] = VOTE_GOV
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
