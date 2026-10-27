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

No date or deadline is typed in here. The dates are each jurisdiction's own,
read from its election office's pages with the words that give each one,
in ``kyc/voting_dates.py`` (audit 2026-10-17, STATEGOV-11, PERSONA-03). A
page that lists anything but the 50 states and D.C. once each is refused,
never written half.

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

from . import tls
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
# Commission; the page calls it the federal government's voting site. It is
# a compiled table (rule 50), so it is shown only where the jurisdiction's
# own record (kyc/voting_dates.py) does not say when registration closes:
# two sources of one deadline beside each other may disagree (rule 53).
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

# The pages this module lists itself, by kind: an evidenced
# overrides.VOTING_LINKS entry replaces one as it replaces NASS's.
CURATED = (("sample", SAMPLE_BALLOTS), ("results", RESULTS), ("deadlines", DEADLINES))

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
# The dates themselves - registration, early voting, mail ballots, and a
# second round in December (Georgia's December 1 runoff, Louisiana's
# December 12 House round: PERSONA-06, FRESHNESS-11) - are each
# jurisdiction's own, in kyc/voting_dates.py, which also holds the
# December dates to the overrides the results reader uses.


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
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=tls.context()) as response:
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
        # Alaska's server sends the wrong intermediate certificate: the
        # context completes its chain from the certificate's own issuer
        # (kyc/tls.py), never by checking less.
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=tls.context()) as response:
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
    once NASS changes its entry, NASS's is shown and validate says so. The
    same holds for a page this module curates (``CURATED``): an override
    replaces it only while the table still gives the address it names.
    """
    from . import overrides

    def link(code, kind, url, source):
        fix = overrides.VOTING_LINKS.get((code, kind))
        if fix and fix[0] == url:
            return ({"url": fix[1], "from": OFFICE, **({"label": fix[2]} if fix[2] else {})}
                    if fix[1] else None)
        return {"url": url, "from": source}

    out = {}
    for code, links in ((cache or {}).get("states") or {}).items():
        shown = {}
        for kind, url in links.items():
            found = link(code, kind, url, NASS)
            if found:
                shown[kind] = found
        for kind, table in CURATED:
            if code in table:
                found = link(code, kind, table[code],
                             VOTE_GOV_FROM if kind == "deadlines" else OFFICE)
                if found:
                    shown[kind] = found
                else:
                    shown.pop(kind, None)
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


# An override's evidence records the office's site linking its replacement
# when it says a page "links" it or it was "linked from" one: never NASS's
# listing, and never a redirect. Oklahoma's results address was shown as
# the office's own page "as its site links it" when the record said only
# that an old address redirected there (NOTES.md, "Oklahoma's results link").
_SITE_LINKS = re.compile(r"(?<!NASS )\blinks\b|\blinked from\b")


def site_linked(code, kind, url):
    """Does the record show *code*'s election office's site linking *url*,
    the page shown for *kind*? A curated page at the table's own address
    does (each was opened from the link the office's home page gives it);
    an override's replacement only where its evidence names the page that
    links it. NASS's listing is NASS's word, not the office's site's."""
    from . import overrides

    fix = overrides.VOTING_LINKS.get((code, kind))
    if fix and fix[1] == url and _SITE_LINKS.search(fix[3]):
        return True
    table = dict(CURATED).get(kind)
    return kind != "deadlines" and table is not None and table.get(code) == url


def stale_overrides(cache):
    """Overrides whose NASS entry, or curated page, has changed: each may
    now be unneeded."""
    from . import overrides

    states = (cache or {}).get("states") or {}
    curated = dict(CURATED)
    out = []
    for (code, kind), fix in overrides.VOTING_LINKS.items():
        if kind in curated:
            listed, who = curated[kind].get(code), "kyc/voting.py"
        else:
            listed, who = (states.get(code) or {}).get(kind), "NASS"
        if listed != fix[0]:
            out.append(f"{code} {kind}: {who} now lists {listed}")
    return sorted(out)


# Links opened by hand in a person's browser where the weekly check could not
# open them (overrides.VOTING_LINKS_BY_HAND). The page counts such a link as
# opened, or says its portal asks visitors to show they are people, for this
# many days from the day on the reader's calendar, and then no longer: a
# later failure is seen again (rule 84's way: the pipeline writes the day,
# the page decides on the reader's own day).
BY_HAND_DAYS = 30
OPENED_BY_HAND = "opened"
HUMAN_CHECK = "human-check"


def by_hand(cache):
    """``{code: {kind: [day, what]}}``: each link shown that a person opened
    by hand (``OPENED_BY_HAND``) or found behind a check for people
    (``HUMAN_CHECK``). An entry counts only while its address is the one
    shown and the weekly check has found that link neither live nor dead:
    a live link needs nothing, and a dead one is not shown."""
    from . import overrides

    status = (cache or {}).get("links") or {}
    shown = effective(cache)
    out = {}
    for (code, kind), (url, day, what, *_seen) in sorted(overrides.VOTING_LINKS_BY_HAND.items()):
        if what not in (OPENED_BY_HAND, HUMAN_CHECK):
            continue  # a mistyped word counts for nothing (by_hand_problems says so)
        link = (shown.get(code) or {}).get(kind)
        if link and link["url"] == url and status.get(url) not in (LIVE, DEAD):
            out.setdefault(code, {})[kind] = [day, what]
    return out


def by_hand_problems(cache, today=None):
    """Every entry the page no longer counts, for a person: the link shown
    is another, the weekly check now opens it (or found it dead), or it was
    read more than ``BY_HAND_DAYS`` ago. And an entry that is not a day, or
    says neither opened nor a check for people, which counts for nothing."""
    from . import overrides

    today = today or datetime.date.today()
    status = (cache or {}).get("links") or {}
    shown = effective(cache)
    out = []
    for (code, kind), (url, day, what, *_seen) in sorted(overrides.VOTING_LINKS_BY_HAND.items()):
        link = (shown.get(code) or {}).get(kind)
        where = f"{code} {kind}"
        if what not in (OPENED_BY_HAND, HUMAN_CHECK):
            out.append(f"{where}: '{what}' is neither {OPENED_BY_HAND!r} nor {HUMAN_CHECK!r}")
        if not link or link["url"] != url:
            out.append(f"{where}: the page now shows {link['url'] if link else 'no link'}, not "
                       f"{url}; the entry may go")
        elif status.get(url) in (LIVE, DEAD):
            out.append(f"{where}: the weekly check found {url} {status[url]}; the entry may go")
        try:
            age = (today - datetime.date.fromisoformat(day)).days
        except (TypeError, ValueError):
            out.append(f"{where}: the day {day!r} is not YYYY-MM-DD")
            continue
        if age > BY_HAND_DAYS:
            out.append(f"{where}: opened by hand {age} days ago ({day}); the page no longer "
                       f"counts it - open {url} again")
    return out


def dead_links(cache):
    """Links shown that were found dead, for a person to replace."""
    status = (cache or {}).get("links") or {}
    return sorted(f"{code} {kind}: {link['url']}"
                  for code, links in effective(cache).items()
                  for kind, link in links.items() if status.get(link["url"]) == DEAD)


def for_page(cache, dates=None):
    """The build meta's ``voting``: ``{code: {kind: url}}``, labels apart,
    with each jurisdiction's own dates (``voting_dates``) under ``_dates``.

    A link found dead is left out rather than sent to a reader, until an
    override replaces it. vote.gov's deadlines page is left out wherever the
    jurisdiction's own record gives its deadlines: a compiled table beside
    the state's own dates is a second source that may disagree (rules 50
    and 53).
    """
    from . import voting_dates

    if not cache:
        return {}
    status = cache.get("links") or {}
    out, labels, nass, linked, unreached = {}, {}, {}, {}, {}
    for code, links in effective(cache).items():
        if voting_dates.deadlines_known(dates, code):
            links = {kind: link for kind, link in links.items() if kind != "deadlines"}
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
        # Which of the office's own pages the record shows its site linking:
        # the page says "as its site links it" of those and no others.
        linked[code] = sorted(kind for kind, url in out[code].items()
                              if links[kind]["from"] == OFFICE and site_linked(code, kind, url))
        missed = sorted(kind for kind in out[code] if status.get(links[kind]["url"]) != LIVE)
        if missed:
            unreached[code] = missed
    out["_labels"] = labels
    out["_nass"] = nass
    out["_siteLinked"] = linked
    out["_unreached"] = unreached
    # Links a person opened by hand, or found behind a check for people,
    # with the day: the page counts them for BY_HAND_DAYS from that day.
    out["_byHand"] = {code: {kind: entry for kind, entry in kinds.items()
                             if kind in unreached.get(code, ())}
                      for code, kinds in by_hand(cache).items()
                      if any(kind in unreached.get(code, ()) for kind in kinds)}
    out["_byHandDays"] = BY_HAND_DAYS
    out["_dates"] = voting_dates.for_page(dates)
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
