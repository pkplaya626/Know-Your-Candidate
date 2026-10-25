"""Each state's legislature on a map: its districts, and who sits for them.

The build projects ``legislative_maps/<st>.json`` (Census boundaries, from
``tools/fetch_legislative_maps.py``) the way ``districts`` projects the
congressional maps - the state's own Albers projection, label points at each
district's pole, close-up insets wherever a district is too small to find on
a phone - and attaches the legislators from ``data/state_legislators.json``
(Open States, ``statelegs``), matched to districts by name there.

Nothing about a person is typed here. A district whose seat Open States lists
nobody for is drawn as "nobody listed", never as vacant: Open States may be
behind a special election (rule 19). A legislator who could not be placed on
a district (New Hampshire's floterial seats, Maine's tribal representatives)
is listed on the page, never dropped.
"""

import math
import os
import re
import unicodedata
import urllib.parse

from . import ballot2026, geo, legphotos, photocopies, statelegs
from . import districts as D
from .government_maps import LOWER_CHAMBER, SEATS, STATES
from .pages import state_name

FOLDER = "legislature"


def line_error_km(tolerance_m, unit_km):
    """How far a legislature page's drawn line may lie from the Census
    Bureau's, in kilometres, rounded up to 10 m: the Douglas-Peucker
    *tolerance_m* the tool simplified at, plus the path data's rounding to
    half of ``10 ** -geo._PRECISION`` map units on each axis."""
    rounding = math.hypot(0.5, 0.5) * 10 ** -geo._PRECISION * unit_km
    return math.ceil((tolerance_m / 1000.0 + rounding) * 100 - 1e-9) / 100

# States whose lines changed after the Census captured them (it holds the
# districts set for the 2024 elections), checked on 2026-10-05. A map that
# silently drew the wrong lines would look entirely normal, so the page says
# what it draws and why.
STATE_NOTES = {
    "MI": ("Michigan's Senate districts in the Detroit area were redrawn by court order "
           "(Agee v. Benson, approved July 26, 2024). The new lines take effect with the "
           "November 3, 2026 election; this map shows the districts the sitting senators "
           "were elected in.",
           # The plan's own page now redirects to /micrc/404 (audit
           # 2026-10-17, LINKS-08); the Commission's mapping-process page
           # holds the "2024 State Senate remedial plan" documents.
           "https://www.michigan.gov/micrc/mapping-process"),
    "MS": ("After a court-ordered redraw, Mississippi held special elections in November 2025 "
           "under new lines in Senate districts 1, 2, 11, 19, 34, 41, 42, 44 and 45 and House "
           "districts 16, 22, 36, 39 and 41. In May 2026 the Supreme Court vacated that order, "
           "and which lines apply is unsettled. This map draws those districts as they were "
           "before the redraw.",
           "https://redistricting.lls.edu/states-MS.php"),
}


class LegislatureError(RuntimeError):
    """A state's map or roster is not what the page needs."""


def page_path(code):
    """``legislature/tx.html``."""
    return f"{FOLDER}/{code.lower()}.html"


def chamber_title(code, chamber):
    if code == "NE":
        return "Legislature"
    if chamber == "upper":
        return "Senate"
    return LOWER_CHAMBER.get(code) or "House of Representatives"


def label_text(name):
    """What is written on a district: its number or short code ("12",
    "10A", "B"). A district known by a name ("10th Bristol", "Belknap 1") is
    not written on the map - the name would not fit - and is found by
    pointing at it or in the list."""
    short = name.replace(" ", "")
    return short if len(short) <= 4 and short.isalnum() else ""


# --------------------------------------------------------------- the person

# Each legislature's own web hosts, in the order a member's page is looked
# for. Open States lists every page it read a member from: up to eighteen,
# among them past sessions' pages, bill lists, conflict-of-interest PDFs and
# the party caucus's page (audit 2026-10-17, LINKS-04, STATEGOV-16). A
# caucus's site is not the legislature's, even on a .gov host
# (housedems.ct.gov, maine.gov/housedems), so a host is the legislature's
# only where it is listed here; each was read from the hosts Open States
# links for that state on 2026-10-17. Michigan's members are linked from
# no legislature host at all, only from their caucuses', so they get no
# "Official page" rather than a party's.
LEGISLATURE_HOSTS = {
    "AK": ("akleg.gov",),
    # Not the old ALIS pages (legislature.state.al.us/aliswww/), which
    # Open States still links for 42 members: on 2026-10-17 http answered
    # 301 to https, and https completed its handshake and then answered
    # 504 Gateway Timeout after 60 seconds (and timed out twice for the
    # PR #96 reviewer); the Internet Archive holds no capture of them that
    # loaded since June 2018. The Legislature's members are on ALISON.
    "AL": ("alison.legislature.state.al.us",),
    "AR": ("arkleg.state.ar.us", "arkansashouse.org", "senate.arkansas.gov"),
    "AZ": ("azleg.gov",),
    # A senator's own site is a subdomain of the Senate's, by district
    # and party ("sd14.senate.ca.gov", "sr01.senate.ca.gov").
    "CA": ("assembly.ca.gov", "senate.ca.gov", ".senate.ca.gov"),
    "CO": ("leg.colorado.gov",),
    "CT": ("cga.ct.gov",),
    "DE": ("legis.delaware.gov",),
    "FL": ("myfloridahouse.gov", "flhouse.gov", "flsenate.gov"),
    "GA": ("legis.ga.gov", "house.ga.gov", "senate.ga.gov"),
    "HI": ("capitol.hawaii.gov",),
    "IA": ("legis.iowa.gov",),
    "ID": ("legislature.idaho.gov",),
    "IL": ("ilga.gov",),
    "IN": ("iga.in.gov",),
    "KS": ("kslegislature.gov",),
    "KY": ("legislature.ky.gov", "lrc.ky.gov"),
    "LA": ("house.louisiana.gov", "senate.la.gov"),
    "MA": ("malegislature.gov",),
    "MD": ("mgaleg.maryland.gov",),
    "ME": ("legislature.maine.gov",),
    "MI": (),
    "MN": ("house.mn.gov", "senate.mn", "house.leg.state.mn.us", "lrl.mn.gov"),
    "MO": ("house.mo.gov", "senate.mo.gov"),
    "MS": ("billstatus.ls.state.ms.us",),
    "MT": ("legislators.legmt.gov", "legmt.gov", "leg.mt.gov"),
    "NC": ("ncleg.gov",),
    "ND": ("ndlegis.gov", "legis.nd.gov"),
    "NE": ("nebraskalegislature.gov",),
    "NH": ("gc.nh.gov", "gencourt.state.nh.us"),
    "NJ": ("njleg.state.nj.us",),
    "NM": ("nmlegis.gov",),
    "NV": ("leg.state.nv.us",),
    "NY": ("nyassembly.gov", "assembly.state.ny.us", "nysenate.gov"),
    "OH": ("ohiohouse.gov", "ohiosenate.gov"),
    "OK": ("okhouse.gov", "oksenate.gov"),
    "OR": ("oregonlegislature.gov",),
    "PA": ("palegis.us", "legis.state.pa.us"),
    "RI": ("rilegislature.gov", "rilin.state.ri.us"),
    "SC": ("scstatehouse.gov",),
    "SD": ("sdlegislature.gov",),
    "TN": ("wapp.capitol.tn.gov", "capitol.tn.gov"),
    "TX": ("house.texas.gov", "senate.texas.gov", "legdir.capitol.texas.gov"),
    "UT": ("house.utah.gov", "house.utleg.gov", "senate.utah.gov", "le.utah.gov"),
    "VA": ("house.vga.virginia.gov", "apps.senate.virginia.gov", "lis.virginia.gov",
           "virginiageneralassembly.gov"),
    "VT": ("legislature.vermont.gov",),
    "WA": ("leg.wa.gov",),
    "WI": ("legis.wisconsin.gov", "docs.legis.wisconsin.gov"),
    "WV": ("wvlegislature.gov", "legis.state.wv.us"),
    "WY": ("wyoleg.gov",),
}

# A party caucus's site, which is not the legislature's but is where some
# legislatures' members have their only page: every Michigan legislator,
# and 1 in 4 of California's, Connecticut's and Indiana's members, are
# linked from no page on the legislature's host (audit 2026-10-17,
# reviewer of PR #96). Shown only where no page on the legislature's own
# site is linked, labelled with the caucus's name, and only for a page
# whose address names the member or carries their district; each host
# was read on 2026-10-17 and its own title names the caucus (gophouse.org,
# asmrc.org and the Delaware sites refused a script, and are the caucuses'
# addresses on the legislatures' own member lists).
# ``(host, path prefix, chamber, the caucus's name)``; a host beginning
# with "." is every subdomain of it (California's "a14.asmdc.org").
CAUCUS_SITES = {
    "AL": (("alsenaterepublicans.org", "/", "upper", "Alabama Senate Republican Caucus"),),
    "CA": ((".asmdc.org", "/", "lower", "Assembly Democratic Caucus"),
           (".asmrc.org", "/", "lower", "Assembly Republican Caucus")),
    "CT": (("housedems.ct.gov", "/", "lower", "Connecticut House Democrats"),
           ("cthousegop.com", "/", "lower", "Connecticut House Republicans"),
           ("senatedems.ct.gov", "/", "upper", "Connecticut Senate Democrats"),
           ("ctsenaterepublicans.com", "/", "upper", "Connecticut Senate Republicans")),
    "DE": (("housedems.delaware.gov", "/members/", "lower", "Delaware House Democrats"),
           ("senatedems.delaware.gov", "/members/", "upper", "Delaware Senate Democrats")),
    "IN": (("indianahouserepublicans.com", "/members/", "lower", "Indiana House Republicans"),
           ("indianasenaterepublicans.com", "/", "upper", "Indiana Senate Republicans"),
           ("indianasenatedemocrats.org", "/", "upper", "Indiana Senate Democrats")),
    "MI": (("housedems.com", "/", "lower", "Michigan House Democrats"),
           ("gophouse.org", "/", "lower", "Michigan House Republicans"),
           ("senatedems.com", "/", "upper", "Michigan Senate Democrats")),
}

# A file, a download or a page about something other than the member.
_NOT_A_PAGE = re.compile(r"\.(pdf|txt|csv|docx?|xlsx?|jpe?g|png|gif)$|ftpdocument|/downloads?/"
                         r"|/documents/|[?&]sh=email|billsintro|/subscribe", re.I)
# Words a member's own page carries in its path ("/senators/574",
# "/Legislators/Detail", "/mem/Phil-Steck", "/rep/PETERVL").
_MEMBER_WORDS = {"member", "members", "membership", "legislator", "legislators", "rep", "reps",
                 "representative", "representatives", "senator", "senators", "sen", "profile",
                 "detail", "details", "bio", "mem", "legislatorpage", "memberinfo", "district"}
# The session a link is for, read only where an address is known to name
# one: a query key ("?yr=2022", "&year=2024", "ddBienniumSession=2019/2020F")
# or a path segment after a word that takes a session ("/membership/2024/",
# "/Legislators/2023/", "/legislative/2021/"), the
# first segment ("docs.legis.wisconsin.gov/2023/"), or a biennium's own form
# ("b2025_26", "69-2025", "li_2026", "/Senators/2022-2024/"). Any other four digits are an id:
# Pennsylvania's "/bio/2009/sen-miller" is member 2009, not the 2009 session.
_SESSION_KEYS = {"yr", "year", "session", "ddbienniumsession", "sessionyear"}
_SESSION_AFTER = {"", "membership", "legislators", "legislative", "single"}
_YEAR = r"(?:19[89]|20[0-4])\d"
_SESSION_SEGMENT = re.compile(rf"({_YEAR})(?:[-_/]({_YEAR}|\d\d))?f?")
_BIENNIUM = re.compile(rf"(?:b|li_|\d{{2,3}}-)({_YEAR})(?:[-_](\d\d|{_YEAR}))?|({_YEAR})-({_YEAR})")
# A member's page about part of their work, after the page about them
# (North Carolina links Biography, Committees, IntroducedBills and Votes;
# Connecticut links only its list of a member's bills, CGAMemberBills).
_ABOUT_ITS_WORK = {"votes", "committees", "introducedbills", "bills", "sponsoredbills",
                   "legislation", "news", "press", "cgamemberbills"}
# The last part of a chamber's list of members, not one member's page.
_GENERIC = {"house", "senate", "assembly", "members", "member", "legislators", "representatives",
            "senators", "house-leaders-members", "senate-leaders-members", "legislature",
            "default.aspx", "index.html", "index.php"}
# A page's own file name, which says nothing about whom it is for: Rhode
# Island's ".../representatives/phillips/default.aspx" is his page.
_CAUCUS = re.compile(r"/(house|senate)(dems|democrats|gop|republicans)\b|caucus", re.I)
_INDEX_FILE = re.compile(r"^(default|index)\.\w+$")
# A numbered General Assembly or Legislature: Illinois's GA=103 pages return
# 404 now that the 104th sits, Arizona links its 56th's pages beside its
# 57th's, and Delaware its 150th's (/AssemblyMember/150/...) beside its
# 153rd's.
_ASSEMBLY = re.compile(r"[?&](GA|legislature)=(\d+)|/(AssemblyMember)/(\d+)/", re.I)
# Words of an address that are no one's surname here.
_URL_WORDS = {"http", "https", "www", "gov", "state", "aspx", "html", "default", "index",
              "page", "pages", "biography", "landing", "apps", "current", "upper", "lower",
              "general", "delegate", "search", "sponsor", "person", "home", "about", "legis",
              "single", "people", "lawmaker", "senators", "assemblymember", "assemblyman",
              "assemblywoman", "roster", "legislative", "members", "member", "house", "senate"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# The chamber an address is for. Legislatures key pages by chamber, and
# Open States keeps a senator's old House pages beside their Senate one:
# Texas's Phil King (Senate District 10) was linked to house.texas.gov's
# District 61 page, which shows whoever holds that House seat now; West
# Virginia's Sen. Joey Garcia to "Delegate Garcia", another man (reviewer
# of PR #96, 2026-10-17). Read from host labels ("house.texas.gov",
# "flsenate.gov", "sd14.senate.ca.gov"), path words ("/house/Rep.asp",
# "/H_Reps/", North Carolina's "/Biography/S/449", Wyoming's
# "/Legislators/2025/H/") and the title in a query ("member=Delegate+Garcia",
# "Chamber=H"). "Assembly" is a chamber only where the lower one is called
# that: Delaware's /AssemblyMember/ and North Dakota's /assembly/69-2025/
# are the whole legislature's.
_LOWER_WORDS = {"house", "representative", "representatives", "rep", "reps", "h", "delegate",
                "delegates", "alrepresentative", "hse"}
_UPPER_WORDS = {"senate", "senator", "senators", "sen", "s", "smembers", "alsenator"}
_QUERY_TITLES = {"delegate": "lower", "representative": "lower", "senator": "upper"}

# Addresses keyed by district number, which show whoever holds that seat
# now: Kentucky's Sen. Steve Rawlings (District 11) was linked to House
# District 66's page, Louisiana's Sen. Brach Myers to House District 45's,
# California's Sen. Anna Caballero (14) to Senate District 12's, Florida's
# Sen. Ed Hooper (21) to District 16's. Each pattern was measured against
# the members Open States lists (2026-10-17): it names the member's own
# district on almost every link, and every miss was a past or other seat.
# ``(pattern on host+path?query, lower-cased, the chamber when the pattern
# carries none)``; a pattern's "c" group, an "h" or "s", is the chamber.
_DISTRICT_IN_ADDRESS = tuple((re.compile(p), ch) for p, ch in (
    # Missouri's House links one page as "MemberDetails.aspx?\district=103".
    (r"[?&]\\?(?:district|districtnumber)=(?P<c>[hs])?0*(?P<n>\d+)(?:&|$)", None),
    (r"^senate\.texas\.gov/member\.php\?d=0*(?P<n>\d+)", "upper"),
    (r"^legis\.delaware\.gov/legislature\.nsf/bydistrict/(?:representative|senator)0*(?P<n>\d+)$",
     None),
    (r"^arkansashouse\.org/district/0*(?P<n>\d+)", "lower"),
    (r"^assembly\.ca\.gov/assemblymembers/0*(?P<n>\d+)", "lower"),
    (r"^senate\.ca\.gov/sd0*(?P<n>\d+)\b", "upper"),
    (r"^s[dr]0*(?P<n>\d+)\.senate\.ca\.gov", "upper"),
    (r"^a0*(?P<n>\d+)\.asmdc\.org", "lower"),
    (r"^ad0*(?P<n>\d+)\.asmrc\.org", "lower"),
    (r"^cga\.ct\.gov/.*[?&]dist_code='?(?P<c>s)?0*(?P<n>\d+)", "lower"),
    (r"^flsenate\.gov/senators/(?:\d{4}-\d{4}/)?s0*(?P<n>\d+)(?:\?|$)", "upper"),
    (r"^legislature\.maine\.gov/district0*(?P<n>\d+)$", "upper"),
    (r"^(?:gc\.nh\.gov|gencourt\.state\.nh\.us)/senate/members/webpages/district0*(?P<n>\d+)\.aspx$",
     "upper"),
    (r"^leg\.state\.nv\.us/app/legislator/a/(?:assembly|senate)/current/0*(?P<n>\d+)$", None),
    (r"^capitol\.tn\.gov/(?:house|senate)/members/(?P<c>[hs])0*(?P<n>\d+)\.html$", None),
    (r"^legis\.wisconsin\.gov/(?:assembly|senate)/0*(?P<n>\d+)/", None),
    (r"^house\.louisiana\.gov/h_reps/members(?:\.aspx)?\?id=0*(?P<n>\d+)", "lower"),
    (r"^senate\.la\.gov/smembers(?:\.aspx)?\?id=0*(?P<n>\d+)", "upper"),
    (r"^(?:house|senate)dems\.delaware\.gov/members/(?:house|senate)-district-0*(?P<n>\d+)", None),
))


def _words(text):
    """The lower-case letters-only words of *text*, accents folded."""
    folded = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.findall(r"[a-z]+", folded.lower())


def surname(name):
    """The words of a member's last name ("Gonzales Worthen" -> {"worthen"},
    "Robert Smith Jr." -> {"smith"}, "Brown-May" -> {"brown", "may"})."""
    parts = [w for w in re.split(r"\s+", (name or "").strip()) if w]
    while parts and _words(parts[-1]) and set(_words(parts[-1])) <= _SUFFIXES:
        parts.pop()
    return set(_words(parts[-1])) if parts else set()


def _canonical(url):
    """One key for a page however it was written: scheme, ``www.``, case of
    the host and a trailing slash do not make another page."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    # A page drawn by script is named after "#": Montana's
    # legislators.legmt.gov/#/legislator/134 is one member's.
    return (host + parts.path.rstrip("/").lower() + ("?" + parts.query.lower() if parts.query else "")
            + ("#" + parts.fragment.lower() if parts.fragment else ""))


def _year(text, century_of=None):
    if not text:
        return None
    if len(text) == 2 and century_of:
        return century_of // 100 * 100 + int(text)
    return int(text)


def sessions(url):
    """``[(first year, last year), ...]``: the sessions an address names,
    where it is known to name one (``_SESSION_KEYS``, ``_SESSION_AFTER``,
    ``_BIENNIUM``)."""
    parts = urllib.parse.urlsplit(url)
    found = []
    for key, value in urllib.parse.parse_qsl(parts.query):
        if key.lower() in _SESSION_KEYS:
            m = _SESSION_SEGMENT.search(value.lower())
            if m:
                first = int(m.group(1))
                found.append((first, _year(m.group(2), first) or first))
    segments = [s.lower() for s in parts.path.split("/")]
    for i, segment in enumerate(segments[1:], 1):
        m = _BIENNIUM.fullmatch(segment)
        if m:
            if m.group(3):
                found.append((int(m.group(3)), int(m.group(4))))
            else:
                first = int(m.group(1))
                found.append((first, _year(m.group(2), first) or first))
            continue
        if segments[i - 1] in _SESSION_AFTER and re.fullmatch(_YEAR, segment):
            found.append((int(segment), int(segment)))
    return found


def chamber_of(code, url, names=()):
    """``"upper"``, ``"lower"`` or ``None``: the chamber *url* is for, from
    its host, its path's words and a title in its query, never from the
    surnames in *names*. Both, or neither, is ``None``."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    assembly = LOWER_CHAMBER.get(code) == "Assembly"
    found = set()
    for label in host.split(".")[:-1]:
        # South Carolina's "scstatehouse.gov" is the building, both chambers.
        if label.endswith("house") and not label.endswith("statehouse"):
            found.add("lower")
        elif label.endswith("senate") or re.fullmatch(r"sd\d+", label):
            found.add("upper")
        elif assembly and label.endswith("assembly"):
            found.add("lower")
    # One letter is a chamber only as a segment of its own (North
    # Carolina's "/Biography/S/449"), never inside one: Massachusetts's
    # "/Profile/S_R1" is Rep. Sean Reid's.
    path = urllib.parse.unquote(parts.path)
    words = {w for w in _words(path) if len(w) > 1}
    words |= {s for s in path.lower().split("/") if s in ("h", "s")}
    for word in words - set(names):
        if word in _LOWER_WORDS or (assembly and word in ("assembly", "assemblymembers")):
            found.add("lower")
        elif word in _UPPER_WORDS:
            found.add("upper")
    for key, value in urllib.parse.parse_qsl(parts.query):
        if key.lower() == "chamber" and value.lower() in ("h", "s"):
            found.add("lower" if value.lower() == "h" else "upper")
        # New Mexico's sponsor code opens with its chamber: "HFIGU" is
        # Natalie Figueroa's House page, now headed "Former Representative",
        # "SFIGU" her Senate one (2026-10-19: five senators were linked to
        # their House pages, and their House photographs taken from them).
        if code == "NM" and key.lower() == "sponcode" and value[:1].lower() in ("h", "s"):
            found.add("lower" if value[:1].lower() == "h" else "upper")
        for word in set(_words(value)) - set(names):
            if word in _QUERY_TITLES:
                found.add(_QUERY_TITLES[word])
    return found.pop() if len(found) == 1 else None


def districts_in(url):
    """``[(chamber or None, district number), ...]`` that *url*'s address
    is keyed by (``_DISTRICT_IN_ADDRESS``)."""
    parts = urllib.parse.urlsplit(url)
    text = ((parts.hostname or "").lower().removeprefix("www.") + parts.path.lower()
            + ("?" + urllib.parse.unquote(parts.query).lower() if parts.query else ""))
    out = []
    for pattern, chamber in _DISTRICT_IN_ADDRESS:
        for m in pattern.finditer(text):
            letter = m.groupdict().get("c")
            out.append(({"h": "lower", "s": "upper"}[letter] if letter else chamber, int(m.group("n"))))
    return out


def _own_district(code, chamber, district):
    """The number a member's own district is written as in an address:
    Kentucky's Senate pages number District 11 as 111."""
    m = re.match(r"0*(\d+)", district or "")
    if not m:
        return None
    n = int(m.group(1))
    return n + 100 if code == "KY" and chamber == "upper" else n


def _someone_elses(code, url, chamber, district, names, by_words=True):
    """Whether *url* is keyed to another chamber or district than the
    member's (*chamber*, *district*): a district-keyed page shows whoever
    holds that seat now, never the member who once did. *by_words* false
    reads only the district an address carries, not its chamber words."""
    if code == "NE" or not chamber:
        return False
    if by_words and chamber_of(code, url, names) not in (None, chamber):
        return True
    own = _own_district(code, chamber, district)
    for theirs, n in districts_in(url):
        if theirs not in (None, chamber):
            return True
        if own is not None and n != own:
            return True
    return False


def member_page(code, links, year, assembly=None, name="", others=(), chamber=None,
                district=None, shared=()):
    """The member's one page for the card, or ``None``: ``{"url", "kind"}``
    with ``kind`` "member" (their page on the legislature's own site),
    "work" (the legislature's page of their bills, Connecticut's only one)
    or "caucus" (their page on their party caucus's site, with its
    ``"caucus"`` name, only where the legislature's site has none), and a
    past session's ``"session"`` ("2021", "2022-2024") where only a past
    session's page is linked.

    Never the dump of every page Open States read. Kept only: a host in
    ``LEGISLATURE_HOSTS``; a page about one member, not a file or the
    chamber's list ("/members/house"); a numbered General Assembly's or
    Legislature's page only for the latest any member of the state is
    linked for (*assembly*, ``latest_assembly``); never a page for the
    other chamber or another district than the member's (*chamber*,
    *district*), which shows whoever holds that seat now; never a page
    whose address names another member (*others*, their surnames) and not
    this one (*name*): Open States lists Rhode Island's Bob Phillips with
    Lauren Carson's page (rule 3). Of what is left: the current session's
    page before a past one's (a session ending before the year before
    *year*, the roster's, is past; of past pages the latest), a member page
    ("/members/...") before a page of their work and before any other,
    a page linked for this member alone before one linked for several
    (*shared*, canonical addresses), one whose address names them, then
    the host's place in the table, then the shorter address. A party
    caucus's pages are not the legislature's, even on its host (Maine's
    "/housedems/kuhn")."""
    hosts = LEGISLATURE_HOSTS.get(code, ())
    assembly = assembly or {}
    if not isinstance(assembly, dict):
        assembly = {"ga": assembly}
    own = surname(name)
    others = set(others) - own
    names = own | others
    seen, ranked, caucus, lists = set(), [], [], []
    for url in links or ():
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        if parts.scheme not in ("http", "https"):
            continue
        key = _canonical(url)
        address = parts.path + "?" + parts.query
        if key in seen or _NOT_A_PAGE.search(address):
            continue
        seen.add(key)
        every = set(_words(urllib.parse.unquote(parts.path + " " + parts.query + " "
                                                + parts.fragment)))
        words = {w for w in every if len(w) >= 4 and w not in _URL_WORDS}
        # Their own surname at any length ("/gee" is Rep. Fred Gee's).
        mine = bool(every & own - _URL_WORDS)
        if words & others and not mine:
            continue
        rank = _host_rank(hosts, host)
        site = None if rank is not None else _caucus_site(code, host, parts.path or "/", chamber)
        # A caucus's site is one chamber's (CAUCUS_SITES), whatever its
        # paths say: Alabama's Senate Republicans file their senators under
        # "/representatives/".
        if _someone_elses(code, url, chamber, district, names, by_words=not site):
            continue
        if rank is None:
            # A caucus's page must say whose it is: their name, or their
            # district's number, which _someone_elses has checked.
            named = mine or _run_together(parts.path, name)
            if site and (named or districts_in(url)):
                segments = [w for w in parts.path.lower().split("/") if w]
                if not segments or segments[-1] not in _GENERIC:
                    caucus.append((0 if named else 1, len(url), url, site))
            continue
        if _CAUCUS.search(parts.path):
            continue
        # A page drawn by script names the member after "#" ("/#/legislator/1840").
        segments = [w for w in (parts.path + "/" + parts.fragment).lower().split("/") if w]
        if segments and _INDEX_FILE.match(segments[-1]):
            segments.pop()
        # California's senators' own sites are a district on the Senate's
        # host ("sd14.senate.ca.gov/"), which says whose they are.
        # A query names one member ("/Senators/Member?id=3"), unless it is
        # a search of the list.
        searched = not parts.query or any(k.lower() == "search"
                                          for k, _v in urllib.parse.parse_qsl(parts.query))
        if searched and (not segments or segments[-1] in _GENERIC) and not districts_in(url):
            # The chamber's own member list, kept for a member the
            # legislature's site has no page for (Alabama's
            # "/senate-leaders-members", searched for them where Open
            # States links it so: "?tab=1&search=Pettus"); never a list of
            # no known chamber.
            if segments and chamber and chamber_of(code, url, names) == chamber:
                lists.append((0 if mine else 1, rank, len(url), url))
            continue
        if any(n < assembly.get(k, 0) for k, n in assembly_numbers(url)):
            continue
        held = sessions(url)
        last = max((b for _a, b in held), default=None)
        behind = max(0, year - 1 - last) if last else 0
        label = None
        if behind:
            first = min(a for a, b in held if b == last)
            label = str(first) if first == last else f"{first}-{last}"
        stems = {re.sub(r"[.]" + chr(92) + "w+$", "", w) for w in segments}
        kind = (1 if stems & _ABOUT_ITS_WORK else 0 if stems & _MEMBER_WORDS else 2)
        ranked.append((behind, kind, 1 if key in shared else 0, 0 if mine else 1,
                       rank, len(parts.query.split("&")) if parts.query else 0,
                       len(url), url, label))
    if ranked:
        best = min(ranked)
        out = {"url": best[7], "kind": "work" if best[1] == 1 else "member"}
        if best[8]:
            out["session"] = best[8]
        return out
    if caucus:
        best = min(caucus)
        return {"url": best[2], "kind": "caucus", "caucus": best[3]}
    if lists:
        return {"url": min(lists)[3], "kind": "list"}
    return None


def _run_together(path, name):
    """Whether one segment of *path* runs the member's first and last names
    together, the first before the last: Michigan House Republicans'
    "/member/RepTomKunse/posts" is Tom Kunse's."""
    words = _words(name)
    last = "".join(sorted(surname(name), key=words.index))
    if len(words) < 2 or len(last) < 3:
        return False
    for segment in urllib.parse.unquote(path).split("/"):
        letters = "".join(_words(segment))
        # Connecticut House Democrats' "/BrownM" is Marcus Brown's.
        if letters == last + words[0][0]:
            return True
        at = letters.find(last)
        # "RepJamesDeSana" is Jim DeSana's: a title, then a first name
        # with his first name's initial, then his whole surname.
        if at > 0 and re.fullmatch(r"(?:rep|sen|senator|representative)?" + words[0][0] + r"[a-z]*",
                                   letters[:at]):
            return True
    return False


def _host_rank(hosts, host):
    """*host*'s place in a state's ``LEGISLATURE_HOSTS``, or ``None``; an
    entry beginning with "." is every subdomain of it."""
    for i, entry in enumerate(hosts):
        if host == entry or (entry.startswith(".") and host.endswith(entry)):
            return i
    return None


def _caucus_site(code, host, path, chamber):
    for site, prefix, theirs, caucus_name in CAUCUS_SITES.get(code, ()):
        if (host == site or (site.startswith(".") and host.endswith(site))) \
                and path.lower().startswith(prefix) and (chamber in (None, theirs)):
            return caucus_name
    return None


def official_page(code, links, year, assembly=None, name="", others=(), chamber=None,
                  district=None, shared=()):
    """The address of the member's page on the legislature's own site, or
    ``None`` (``member_page``, without a caucus's)."""
    page = member_page(code, links, year, assembly, name, others, chamber, district, shared)
    return page["url"] if page and page["kind"] != "caucus" else None


def assembly_numbers(url):
    """``[("ga", 104), ...]``: the numbered General Assemblies and
    Legislatures an address names."""
    out = []
    for m in _ASSEMBLY.finditer(url):
        key = (m.group(1) or m.group(3)).lower()
        out.append((key, int(m.group(2) or m.group(4))))
    return out


def latest_assembly(records):
    """``{"ga": 104, "legislature": 57}``: the latest numbered General
    Assembly (Illinois's ``GA=``), Legislature (Arizona's
    ``legislature=``) and Delaware General Assembly
    (``/AssemblyMember/153/``) among *records*' links."""
    found = {}
    for r in records:
        for link in r.get("links", ()):
            for k, n in assembly_numbers(link):
                found[k] = max(found.get(k, 0), n)
    return found


def shared_links(records):
    """The canonical addresses Open States links for more than one member."""
    count = {}
    for r in records:
        for key in {_canonical(link) for link in r.get("links", ())}:
            count[key] = count.get(key, 0) + 1
    return {k for k, n in count.items() if n > 1}


def surnames(records):
    """Every member's surname words, for ``official_page``'s *others*."""
    out = set()
    for r in records:
        out |= {w for w in surname(r.get("name")) if len(w) >= 4 and w not in _URL_WORDS}
    return out


# Image hosts that are a search engine's copy of a picture, never a
# source's own: an image-search thumbnail carries no attribution to the
# person it shows (audit 2026-10-17, LINKS-05). News and civic sites'
# images are left alone; they are the page's, and Open States picked them
# for this person by id.
SEARCH_THUMBNAIL_HOSTS = re.compile(r"(^|\.)(gstatic\.com|googleusercontent\.com)$|^encrypted-tbn",
                                    re.I)


def search_thumbnail(url):
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    return bool(SEARCH_THUMBNAIL_HOSTS.search(host))


def fusion_lines(label):
    """The other ballot lines of a fusion label, after the party:
    "Republican/Conservative/Independence" -> ["Conservative", "Independence"]."""
    return [p.strip() for p in (label or "").split("/")[1:] if p.strip()]


def party_name(label):
    """The party a fusion label names first: "Democratic/Working Families"
    is a Democrat, counted as one (audit 2026-10-17, STATEGOV-21)."""
    return (label or "").split("/")[0].strip()


# ``member_page``'s kinds, as the page data names them.
PAGE_KINDS = {"member": "member", "work": "bills", "caucus": "caucus", "list": "list"}


def page_for(code, record, year=0, assembly=None, others=(), shared=()):
    """``member_page`` for one roster record, by its chamber and district."""
    return member_page(code, record.get("links"), year, assembly, record.get("name", ""), others,
                       record.get("chamber"), record.get("district"), shared)


def pages_for(code, roster, year):
    """``{record id: page}`` for a state's roster, where no page is any two
    members': a page chosen for two is neither's, since a page keyed by
    number shows one person (North Carolina's Biography/S/449 is Sen. Dana
    Jones's, and Open States lists it for Sen. Sophia Chitlik too). Returns
    the pages and how many members lost one that way."""
    assembly = latest_assembly(roster)
    others = surnames(roster)
    shared = shared_links(roster)
    pages = {r["id"]: page_for(code, r, year, assembly, others, shared) for r in roster}
    users = {}
    for rid, page in pages.items():
        # A chamber's member list is every member's, and says so.
        if page and page["kind"] != "list":
            users.setdefault(_canonical(page["url"]), []).append(rid)
    withheld = 0
    for ids in users.values():
        if len(ids) > 1:
            for rid in ids:
                pages[rid] = None
                withheld += 1
    return pages, withheld


def _person(record, code="", year=0, assembly=None, dropped=None, others=(), pages=None,
            photos=None):
    """What the page shows of one legislator: their party and the other
    ballot lines they were elected on, the district office's phone labelled
    as such, one page about them (``member_page``; *pages*, from
    ``pages_for``, where the state's roster has been read whole), and a
    portrait that is neither a search engine's thumbnail nor a file the
    source confirmed missing - or, where Open States has none of those, the
    one the legislature itself publishes for them (*photos*, the
    ``legphotos`` cache), credited to the legislature (rule 87)."""
    keep = ("id", "name", "partyKey", "district", "email", "tribalSeat", "unicameral")
    out = {k: record[k] for k in keep if k in record}
    out["party"] = party_name(record.get("party"))
    lines = fusion_lines(record.get("party"))
    if lines:
        out["lines"] = lines
    if record.get("phone"):
        out["phone"] = record["phone"]
    if record.get("address"):
        out["address"] = record["address"]
    if record.get("districtPhone"):
        out["districtPhone"] = record["districtPhone"]
    page = pages.get(record["id"]) if pages is not None else page_for(
        code, record, year, assembly, others)
    if page:
        # The card labels the link as what it is (PR #96 review): the
        # member's page on the legislature's site, the legislature's list of
        # their bills, their page on a party caucus's site, or the chamber's
        # member list - and a past session's page as one.
        out["page"] = page["url"]
        out["pageKind"] = PAGE_KINDS[page["kind"]]
        if page.get("caucus"):
            out["pageCaucus"] = page["caucus"]
        if page.get("session"):
            out["pageSession"] = page["session"]
    image = record.get("image")
    kind = photo_kind(record, photos)
    if kind == "openstates":
        # Loaded over https, as the page is; 'statelegs' checked that copy.
        out["image"] = statelegs.secure(image)
        # A portrait the legislature itself serves is credited to it like
        # the ones legphotos reads (rule 87): in a district of two, one
        # credited and one not read as coming from two places (the
        # reviewers of PR #125). Linked to the member's own page only.
        if legphotos.official_host(code, out["image"]):
            credit = {"by": legphotos.legislature_name(code)}
            if (page and page["kind"] == "member" and not page.get("session")
                    and legphotos.official_host(code, page["url"])):
                credit["page"] = page["url"]
            out["imageCredit"] = credit
    elif kind == "legislature":
        own = legphotos.entry_for(record, photos)
        out["image"] = own["image"]
        out["imageCredit"] = {"by": own["credit"], "page": own["page"]}
    if dropped is not None and kind not in ("openstates", "legislature", "none"):
        dropped[kind] = dropped.get(kind, 0) + 1
    return out


def photo_kind(record, photos=None):
    """Which portrait a card shows, or why none: "openstates" (Open States's
    own, checked by 'statelegs'), "legislature" (the legislature's, from
    the ``legphotos`` cache, where Open States has no usable one),
    "oversized" (the legislature offers only a file over the caps),
    "sharedImage" (Open States gives the same file to another member,
    ``statelegs.mark_shared_images``), "thumbnail" (Open States's is a
    search engine's), "broken" (confirmed
    missing) or "none"."""
    image = record.get("image")
    if legphotos.open_states_image_ok(record):
        return "openstates"
    if legphotos.entry_for(record, photos):
        return "legislature"
    entry = ((photos or {}).get("people") or {}).get(record["id"]) or {}
    if entry.get("oversized"):
        return "oversized"
    if image and record.get("imageShared"):
        return "sharedImage"
    if image and search_thumbnail(image):
        return "thumbnail"
    if image and record.get("imageStatus") == "broken":
        return "broken"
    return "none"


def build_state(code, root=".", places=None, roster=None, control=None, fetched="",
                dropped=None, photos=None):
    """One state's legislature page data. *control* is the state's entry in
    ``stategov.build``'s payload: its chambers' counts and who runs them;
    *fetched* the roster's date; *dropped* counts the portraits left off."""
    year = int(fetched[:4]) if fetched[:4].isdigit() else 0
    pages, withheld = pages_for(code, roster or [], year)
    if dropped is not None and withheld:
        dropped["sharedPage"] = withheld

    def person(record):
        return _person(record, code, year, dropped=dropped, pages=pages, photos=photos)

    topo = statelegs.load_map(code, root)
    if not topo:
        raise LegislatureError(f"no {statelegs.MAPS_DIR}/{code.lower()}.json; "
                               f"run tools/fetch_legislative_maps.py")
    arcs = geo.decode_arcs(topo)
    objects = topo.get("objects") or {}
    chambers = [c for c in ("upper", "lower") if c in objects]

    shapes, points = {}, {}
    for chamber in chambers:
        shapes[chamber] = {g["properties"]["id"]: g for g in objects[chamber]["geometries"]}
        points[chamber] = {g["properties"]["id"]: g for g in objects[f"{chamber}_pts"]["geometries"]}
        if set(points[chamber]) != set(shapes[chamber]):
            raise LegislatureError(f"{code} {chamber}: label points do not match the districts")

    lonlat = [p for chamber in chambers for g in shapes[chamber].values()
              for ring in geo.geometry_rings(g, arcs) for p in ring]
    # How far the drawn lines may stray from the Census Bureau's: the
    # simplification tools/fetch_legislative_maps.py applied (from the upper
    # chamber's extent, as it measured it) and the rounding of the path data
    # to geo._PRECISION, on both axes.
    tolerance_m = statelegs.map_tolerance_m(
        [p for g in shapes["upper"].values() for ring in geo.geometry_rings(g, arcs) for p in ring])
    albers = D.projection_for(code, lonlat)
    raw_arcs = [[albers.raw(lon, lat) for lon, lat in arc] for arc in arcs]
    raw = {chamber: {i: geo.geometry_rings(g, raw_arcs) for i, g in shapes[chamber].items()}
           for chamber in chambers}
    fit = D._Fit([p for chamber in chambers for rings in raw[chamber].values()
                  for ring in rings for p in ring])
    viewbox = [0, 0, D.WIDTH, fit.height]
    towns = D._places((places or {}).get(code, []), albers, fit)

    people = list(roster or [])
    out_chambers = {}
    for chamber in chambers:
        found = {}
        for district_id, rings in sorted(raw[chamber].items()):
            fitted = [[fit(p) for p in ring] for ring in rings]
            path = geo.rings_to_path(fitted)
            if not path:
                raise LegislatureError(f"{code} {chamber} district {district_id} has no shape")
            props = shapes[chamber][district_id]["properties"]
            at = fit(albers.raw(*D._decode_point(topo, points[chamber][district_id]["coordinates"])))
            if not D._contains(fitted, *at):
                # A label over the wrong district is a silent error.
                raise LegislatureError(f"{code} {chamber} {district_id}: label point outside it")
            found[district_id] = {
                "d": path,
                "name": props["name"],
                "label": label_text(props["name"]),
                "at": [geo._round(at[0]), geo._round(at[1])],
                "box": list(geo.bounds(fitted)),
                "room": geo._round(geo.signed_distance(at[0], at[1], fitted)),
            }
        members = {}
        for record in people:
            if record["chamber"] == chamber and record.get("districtId") in found:
                members.setdefault(record["districtId"], []).append(person(record))
        for listed in members.values():
            listed.sort(key=lambda p: (p["district"], p["name"]))
        seats = SEATS[code][0 if chamber == "upper" else 1]
        count = _count(code, chamber, people, seats, (control or {}).get(chamber))
        ballot = (ballot2026.for_state(code).get("chambers") or {}).get(chamber)
        for district_id, up in seats_up(code, chamber, found).items():
            found[district_id]["up"] = up
        on_special = specials(code, chamber, found)
        for district_id in on_special:
            found[district_id]["special"] = True
        out_chambers[chamber] = {
            "title": chamber_title(code, chamber),
            "seats": seats,
            "listed": count["listed"],
            # The same count as the state page's (stategov.chamber), and
            # each party under its own name, never a fusion line's
            # (rule 73).
            "count": count,
            "parties": parties(people, chamber),
            "districts": found,
            "members": members,
            "insets": D.insets([found], towns, viewbox) if len(found) > 1 else [],
            "lsy": (topo.get("sources") or {}).get(chamber, {}).get("lsy", []),
        }
        if ballot:
            out_chambers[chamber]["ballot"] = ballot
            each = district_seats(code, chamber, found)
            if each:
                out_chambers[chamber]["districtSeats"] = each
        if on_special:
            # In the record's order, which is the districts' own.
            out_chambers[chamber]["specials"] = [found[i]["name"] for i in on_special]
        years = term_years(code, chamber)
        if years:
            out_chambers[chamber]["termYears"] = years

    placed = {r["id"] for c in out_chambers.values() for listed in c["members"].values()
              for r in listed}
    unplaced = [dict(person(r), chamber=r["chamber"], why=unplaced_why(code, r))
                for r in people if r["id"] not in placed]
    unplaced.sort(key=lambda p: (p["chamber"], p["district"], p["name"]))
    out = {
        "name": state_name(code),
        "page": page_path(code),
        "viewBox": viewbox,
        "unitKm": round(D.EARTH_RADIUS_KM / fit.k, 6),
        # Added to the margin "Find who represents me" places a reader with
        # (kyc-findrep.js): these lines are coarser than the lookup files'.
        "lineErrorKm": line_error_km(tolerance_m, D.EARTH_RADIUS_KM / fit.k),
        # Where a reader's location falls on these districts, placed on the
        # device by "Find who represents me" (kyc-findrep.js).
        "projection": D.projection_payload(albers, fit),
        "counties": D._counties(topo, raw_arcs, fit),
        "places": towns,
        "chambers": out_chambers,
        "unplaced": unplaced,
        "sources": {"maps": "U.S. Census Bureau, 2025 cartographic boundary files (1:500,000)",
                    "people": statelegs.SOURCE, "peopleDate": fetched[:10],
                    "ballot2026": ballot2026.REVIEWED},
    }
    # Who runs the chambers, in the state page's words (stategov): the
    # coalition note where the majority of seats does not govern (rule 54).
    for key in ("legislature", "note", "noteSource"):
        if key in (control or {}):
            out[key] = control[key]
    return out


def build(root=".", codes=None, dropped=None):
    """``{code: payload}`` for every state with a map and a roster.
    *dropped*, a dict, collects ``{code: {"thumbnail": n, "broken": n}}``:
    the portraits left off each state's page."""
    from . import stategov
    cache = statelegs.load_cache(root)
    if not cache:
        raise LegislatureError(f"no {statelegs.CACHE_PATH}; run 'statelegs'")
    try:
        control = stategov.build(root)[0]["states"]
    except stategov.StateGovError as exc:
        raise LegislatureError(str(exc)) from exc
    places = D.load_places(root)
    photos = legphotos.load_cache(root)
    # The smaller copies this site made of the heavy ones (rule 101).
    copies = photocopies.load(root)
    out = {}
    for code in codes or STATES:
        roster = cache["states"].get(code) or []
        topo = statelegs.load_map(code, root)
        if topo:
            statelegs.match(code, roster, topo)
        counts = {} if dropped is None else dropped.setdefault(code, {})
        out[code] = build_state(code, root, places, roster, control.get(code),
                                cache.get("fetched", ""), counts, photos)
        photocopies.apply_legislature(out[code], copies, code)
    return out


def _count(code, chamber, records, seats, theirs):
    """The chamber's seats by party, as ``stategov.chamber`` counts them for
    the state page; a different answer from the state page's own payload
    is an error, never a second figure (rule 73)."""
    from . import stategov
    ours = stategov.chamber(records, chamber, seats)
    if theirs:
        shown = {k: theirs.get(k) for k in ours}
        if shown != ours:
            raise LegislatureError(f"{code} {chamber}: the state page counts {shown}, "
                                   f"this page {ours}")
        if "ncsl" in theirs:
            ours["ncsl"] = theirs["ncsl"]
    return ours


def parties(records, chamber):
    """``[[party, key, members], ...]``, most members first: each party
    under the name its members' labels give it first, so "Democratic" and
    "Democratic/Working Families" are one party of 40, not two of 21 and 19
    (audit 2026-10-17, STATEGOV-21). Independents and third parties keep
    their own names ("Progressive", "Independent")."""
    groups = {}
    for r in records:
        if r["chamber"] != chamber or r.get("tribalSeat"):
            continue
        key = r["partyKey"]
        name = party_name(r.get("party")) or "Unknown"
        group = (key, name) if key == "I" else (key,)
        names = groups.setdefault(group, {})
        names[name] = names.get(name, 0) + 1
    out = []
    for group, names in groups.items():
        # The name most of the party's members carry ("Democratic-Farmer-
        # Labor" in Minnesota), ties broken by the name itself.
        label = sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        out.append([label, group[0], sum(names.values())])
    out.sort(key=lambda p: (-p[2], p[0]))
    return out


def unplaced_why(code, record):
    """Why a member is not on the map: "tribal" (Maine's non-voting
    representatives of tribal nations), "floterial" (New Hampshire's
    districts that overlay others) or "unmatched" (no boundary of that
    name: reported by ``statelegs``). Floterial only where RSA 662:5 makes
    the district one (``NH_FLOTERIAL``)."""
    if record.get("tribalSeat"):
        return "tribal"
    if code == "NH" and record["chamber"] == "lower" and record.get("district") in NH_FLOTERIAL:
        return "floterial"
    return "unmatched"


def term_years(code, chamber):
    """A chamber's term in years where the state's own record in
    ``ballot2026`` states one ("all (2-year terms)", "4-year staggered
    terms"), or ``None``: no term is typed in from a compiled table (rule
    50), so a chamber whose record does not say has none shown."""
    entry = (ballot2026.STATES.get(code) or {}).get(chamber)
    # A 2-4-4 cycle's terms are not all one length (Minnesota's Senate).
    if not entry or re.search(r"\d-\d-\d", entry[3]):
        return None
    found = set(re.findall(r"\b(\d)-year (?:staggered )?terms?\b", entry[3]))
    return int(found.pop()) if len(found) == 1 else None


def seats_up(code, chamber, districts):
    """``{district id: on the 2026 regular ballot?}`` from the state's own
    record (``ballot2026``), or ``{}`` where that record names the seats in
    words that do not resolve to these districts exactly.

    "all" and "none" are every district and none. Otherwise the record's
    list ("districts A, C, E", "11 districts: 2, 8, 9") or rule ("the 20
    even-numbered districts") must name districts on this map, as many as
    the seats it says are up - a district of two seats counting twice - or
    nothing is marked: Montana's "25 of 50" and Arkansas's "17 seats"
    show no district. A special election is not a regular one and is never
    marked; the chamber's line quotes the record, specials and all.

    West Virginia's Senate elects "one of the two seats in each of the 17
    districts", so every district has a seat up, and North Dakota's House
    "2 seats in each of the 24 odd-numbered districts", whose map also
    holds the even District 4 as subdistricts 4A and 4B. Both once marked
    nothing, and the Your ballot page told a reader in North Dakota's
    House District 2 that whether their seat was up was not known, over
    the record that says (PR #115 review)."""
    entry = (ballot2026.STATES.get(code) or {}).get(chamber)
    if not entry or not districts:
        return {}
    _name, total, up, basis, _source = entry
    if up == 0:
        return {i: False for i in districts}
    if up == total:
        return {i: True for i in districts}
    head = re.split(r"[(;]", basis)[0]
    each = re.search(r"\bone of the (?:two|(\d+)) seats in each of the (\d+) districts\b", head)
    if each:
        n, seats = int(each.group(2)), int(each.group(1) or 2)
        if n != len(districts) or up != n or total != n * seats:
            return {}
        return {i: True for i in districts}
    stated = re.search(r"\b(\d+) seats in each of\b", head)
    per = int(stated.group(1)) if stated else total / len(districts)
    if per != int(per):
        return {}
    rule = re.search(r"\bthe (\d+) (even|odd)-numbered districts\b", head)
    if rule:
        parity = 0 if rule.group(2) == "even" else 1
        chosen = set()
        for i, d in districts.items():
            number = re.fullmatch(r"(\d+)([A-Z]?)", d["name"])
            if not number or int(number.group(1)) % 2 != parity:
                continue
            if number.group(2):
                # A subdistrict ("4A") holds some of its number's seats,
                # how many the record does not say.
                return {}
            chosen.add(i)
        if len(chosen) != int(rule.group(1)):
            return {}
    else:
        listed = re.search(r"\bdistricts\b:?(.*)$", head)
        tokens = [t.strip() for t in re.split(r",|\band\b", listed.group(1)) if t.strip()] \
            if listed else []
        if not tokens:
            return {}
        by_name = {statelegs.norm(d["name"]): i for i, d in districts.items()}
        chosen = set()
        for token in tokens:
            match = re.fullmatch(r"\d+|[A-Z]", token)
            found = by_name.get(statelegs.norm(token)) if match else None
            if found is None:
                return {}
            chosen.add(found)
    if len(chosen) * int(per) != up:
        return {}
    return {i: i in chosen for i in districts}


def district_seats(code, chamber, districts):
    """How a district's seats stand on the ballot, for the words a page
    says of one district: ``"one"`` (each district holds one seat),
    ``"several"`` (each holds more than one, and those up are all up),
    ``"one-of-several"`` (one of each district's seats is up: West
    Virginia's Senate), or None where the record and the map do not say.
    Arizona's House elects two members a district, and its page said
    "This seat is on the Nov 3, 2026 ballot" (PR #115 review)."""
    entry = (ballot2026.STATES.get(code) or {}).get(chamber)
    if not entry or not districts:
        return None
    total, basis = entry[1], entry[3]
    head = re.split(r"[(;]", basis)[0]
    if re.search(r"\bone of the (?:two|\d+) seats in each of\b", head):
        return "one-of-several"
    stated = re.search(r"\b(\d+) seats in each of\b", head)
    if stated:
        # North Dakota's "2 seats in each" is of its numbered districts;
        # its subdistricts 4A and 4B hold one each.
        if any(re.fullmatch(r"\d+[A-Z]", d["name"]) for d in districts.values()):
            return None
        return "one" if stated.group(1) == "1" else "several"
    per = total / len(districts)
    if per != int(per):
        return None
    return "one" if per == 1 else "several"


# Words in a ballot2026 record that speak of an election for the rest of a
# term, beside the regular ones: "plus 17,21,29,31 for 2-year vacancy
# remainders", "District 41 also has a 2-year special", "only districts 24
# and 25 are on the 2026 ballot" (Kansas's Senate, none of it regular).
_SPECIAL_WORDS = re.compile(r"special|vacanc|unexpired|remainder|\bonly districts?\b", re.I)


def specials(code, chamber, districts):
    """``[district id, ...]``: the districts the state's own record
    (``ballot2026``) names for an election to the rest of a term on the
    Nov 3, 2026 ballot, in the record's order. A district on the ballot for
    the rest of a term is on the ballot: reviewers of PR #96 found Kansas
    Senate 24, Nebraska 41, New Mexico Senate 33 and Oklahoma Senate 17
    reading "This seat is not up for regular election in 2026" over a seat
    on the ballot, the special mentioned only in faint text below (rule 74).

    Read from the record's clauses after its regular part (``seats_up``
    reads that), less its term lengths ("2-year", "for 2 years") and
    years. A clause that speaks of a special but names no district on this
    map is an error, never an unmarked district: a mark missing over a
    seat on the ballot looks entirely normal."""
    entry = (ballot2026.STATES.get(code) or {}).get(chamber)
    if not entry or not districts:
        return []
    basis = entry[3]
    clauses = re.split(r"[(;]", basis)[1:]
    by_name = {statelegs.norm(d["name"]): i for i, d in districts.items()}
    out = []
    for clause in clauses:
        if not _SPECIAL_WORDS.search(clause):
            continue
        text = re.sub(r"\b\d+-year\b|\b\d+ years?\b|\b(?:19|20)\d\d\b", " ", clause)
        numbers = re.findall(r"\b\d+\b", text)
        if not numbers:
            raise LegislatureError(f"{code} {chamber}: the 2026 record names a special election "
                                   f"but no district: {clause.strip()!r}")
        for number in numbers:
            found = by_name.get(statelegs.norm(number))
            if found is None:
                raise LegislatureError(f"{code} {chamber}: the 2026 record's special election in "
                                       f"district {number} is not a district on the map")
            if found not in out:
                out.append(found)
    return out


# New Hampshire's floterial House districts: each is the union of base
# districts it overlays, so no boundary of its own is drawn. Read from RSA
# 662:5, the apportionment as it stands (gc.nh.gov/rsa/html/LXIII/662/
# 662-5.htm, read 2026-10-18): every district whose towns and wards are
# exactly those of two or more other districts of its county. A member
# Open States places in a district not listed here is "unmatched" and
# reported, never called floterial (reviewer of PR #96): a misspelt or
# renamed base district would otherwise read as an overlay.
NH_FLOTERIAL = frozenset(
    ["Belknap 8", "Carroll 7", "Carroll 8", "Coos 7", "Grafton 17", "Grafton 18",
     "Sullivan 7", "Sullivan 8"]
    + [f"Cheshire {n}" for n in (15, 16, 17, 18)]
    + [f"Hillsborough {n}" for n in (37, 38, 39, 40, 41, 44, 45)]
    + [f"Merrimack {n}" for n in range(25, 31)]
    + [f"Rockingham {n}" for n in range(31, 41)]
    + [f"Strafford {n}" for n in range(18, 22)])


def stats(maps):
    districts = sum(len(c["districts"]) for m in maps.values() for c in m["chambers"].values())
    people = sum(len(v) for m in maps.values() for c in m["chambers"].values()
                 for v in c["members"].values())
    unplaced = sum(len(m["unplaced"]) for m in maps.values())
    return {"states": len(maps), "districts": districts, "placed": people, "unplaced": unplaced}


def link_report(root="."):
    """``{what: {code: n}}``: what the legislature pages leave off or label
    otherwise, counted from the roster alone so ``build --check`` can say
    it: portraits that are a search engine's thumbnail ("thumbnail") or
    confirmed missing ("broken") with none from the legislature in their
    place, portraits shown from the legislature's own records
    ("legislature") and left out because it offers only a file over the
    caps ("oversized"), members with no page ("noPage"), a page
    on a caucus's site only ("caucus"), and pages withheld because two
    members were given one ("sharedPage")."""
    cache = statelegs.load_cache(root)
    if not cache:
        return {}
    fetched = cache.get("fetched", "")
    year = int(fetched[:4]) if fetched[:4].isdigit() else 0
    out = {}
    photos = legphotos.load_cache(root)

    def add(what, code):
        out.setdefault(what, {})[code] = out.get(what, {}).get(code, 0) + 1

    for code, roster in sorted(cache["states"].items()):
        pages, withheld = pages_for(code, roster, year)
        if withheld:
            out.setdefault("sharedPage", {})[code] = withheld
        for r in roster:
            kind = photo_kind(r, photos)
            if kind not in ("openstates", "none"):
                add(kind, code)
            page = pages.get(r["id"])
            if not page:
                add("noPage", code)
            elif page["kind"] == "caucus":
                add("caucus", code)
    return out
