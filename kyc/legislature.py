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

from . import ballot2026, geo, statelegs
from . import districts as D
from .government_maps import LOWER_CHAMBER, SEATS, STATES
from .pages import state_name

FOLDER = "legislature"

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
    "AL": ("alison.legislature.state.al.us", "legislature.state.al.us"),
    "AR": ("arkleg.state.ar.us", "arkansashouse.org", "senate.arkansas.gov"),
    "AZ": ("azleg.gov",),
    "CA": ("assembly.ca.gov", "senate.ca.gov"),
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

# A file, a download or a page about something other than the member.
_NOT_A_PAGE = re.compile(r"\.(pdf|txt|csv|docx?|xlsx?|jpe?g|png|gif)$|ftpdocument|/downloads?/"
                         r"|/documents/|[?&]sh=email|billsintro|/subscribe", re.I)
# Words a member's own page carries in its path ("/senators/574",
# "/Legislators/Detail", "/mem/Phil-Steck", "/rep/PETERVL").
_MEMBER_WORDS = {"member", "members", "membership", "legislator", "legislators", "rep", "reps",
                 "representative", "representatives", "senator", "senators", "sen", "profile",
                 "detail", "details", "bio", "mem", "legislatorpage", "memberinfo", "district"}
# A session a link is for: Illinois's General Assembly (GA=103), a year in
# a query or as a path segment (".../membership/2024/", "?yr=2022"), a
# biennium ("b2021_22", "li_2022", "ddBienniumSession=2019/2020F").
_SESSION_YEAR = re.compile(r"(?:(?<=[/_=-])|(?<=[/_=]b))((?:199|20[0-4])\d)(?!\d)")
# A member's page about part of their work, after the page about them
# (North Carolina links Biography, Committees, IntroducedBills and Votes).
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
# A numbered General Assembly or Legislature in a query: Illinois's GA=103
# pages return 404 now that the 104th sits, and Arizona links its 56th's
# pages beside its 57th's.
_ASSEMBLY = re.compile(r"[?&](GA|legislature)=(\d+)", re.I)
# Words of an address that are no one's surname here.
_URL_WORDS = {"http", "https", "www", "gov", "state", "aspx", "html", "default", "index",
              "page", "pages", "biography", "landing", "apps", "current", "upper", "lower",
              "general", "delegate", "search", "sponsor", "person", "home", "about", "legis",
              "single", "people", "lawmaker", "senators", "assemblymember", "assemblyman",
              "assemblywoman", "roster", "legislative"}
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


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
    return host + parts.path.rstrip("/").lower() + ("?" + parts.query.lower() if parts.query else "")


def _sessions(url):
    parts = urllib.parse.urlsplit(url)
    text = parts.path + ("?" + urllib.parse.unquote(parts.query) if parts.query else "")
    return [int(y) for y in _SESSION_YEAR.findall(text)]


def official_page(code, links, year, assembly=None, name="", others=()):
    """The member's page on their legislature's own site, or ``None``: one
    link for the card, never the dump of every page Open States read.

    Kept only: a host in ``LEGISLATURE_HOSTS``; a page about one member,
    not a file or the chamber's list ("/members/house"); a numbered
    General Assembly's or Legislature's page only for the latest any member
    of the state is linked for (*assembly*, ``latest_assembly``); and never
    a page whose address names another member (*others*, their surnames)
    and not this one (*name*): Open States lists Rhode Island's Bob
    Phillips with Lauren Carson's page (rule 3). Of what is left: the
    current session's page before a past one's (a session older than the
    year before *year*, the roster's, is past, and of past pages the
    latest), then a member page ("/members/...") before any other, then
    one whose address names them, then the host's place in the table, then
    the shorter address. A party caucus's pages are not the legislature's,
    even on its host (Maine's "/housedems/kuhn")."""
    hosts = LEGISLATURE_HOSTS.get(code, ())
    assembly = assembly or {}
    if not isinstance(assembly, dict):
        assembly = {"ga": assembly}
    own = surname(name)
    others = set(others) - own
    seen, ranked = set(), []
    for url in links or ():
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        if parts.scheme not in ("http", "https") or host not in hosts:
            continue
        key = _canonical(url)
        address = parts.path + "?" + parts.query
        if key in seen or _NOT_A_PAGE.search(address) or _CAUCUS.search(parts.path):
            continue
        seen.add(key)
        # A page drawn by script names the member after "#" ("/#/legislator/1840").
        segments = [w for w in (parts.path + "/" + parts.fragment).lower().split("/") if w]
        if segments and _INDEX_FILE.match(segments[-1]):
            segments.pop()
        if not parts.query and (not segments or segments[-1] in _GENERIC):
            continue
        numbered = [(k.lower(), int(n)) for k, n in _ASSEMBLY.findall(url)]
        if any(n < assembly.get(k, 0) for k, n in numbered):
            continue
        words = {w for w in _words(urllib.parse.unquote(parts.path + " " + parts.query + " "
                                                        + parts.fragment))
                 if len(w) >= 4 and w not in _URL_WORDS}
        if words & others and not words & own:
            continue
        sessions = _sessions(url)
        behind = max(0, year - 1 - sessions[0]) if sessions else 0
        stems = {re.sub(r"[.]" + chr(92) + "w+$", "", w) for w in segments}
        kind = (2 if not stems & _MEMBER_WORDS else 1 if stems & _ABOUT_ITS_WORK else 0)
        ranked.append((behind, kind, 0 if words & own else 1, hosts.index(host),
                       len(parts.query.split("&")) if parts.query else 0, len(url), url))
    if not ranked:
        return None
    return min(ranked)[-1]


def latest_assembly(records):
    """``{"ga": 104, "legislature": 57}``: the latest numbered General
    Assembly (Illinois's ``GA=``) and Legislature (Arizona's
    ``legislature=``) among *records*' links."""
    found = {}
    for r in records:
        for link in r.get("links", ()):
            for k, n in _ASSEMBLY.findall(link):
                found[k.lower()] = max(found.get(k.lower(), 0), int(n))
    return found


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


def _person(record, code="", year=0, assembly=None, dropped=None, others=()):
    """What the page shows of one legislator: their party and the other
    ballot lines they were elected on, the district office's phone labelled
    as such, one official page, and a portrait that is neither a search
    engine's thumbnail nor a file the source confirmed missing."""
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
    page = official_page(code, record.get("links"), year, assembly, record.get("name", ""), others)
    if page:
        out["page"] = page
    image = record.get("image")
    if image and search_thumbnail(image):
        if dropped is not None:
            dropped["thumbnail"] = dropped.get("thumbnail", 0) + 1
    elif image and record.get("imageStatus") == "broken":
        if dropped is not None:
            dropped["broken"] = dropped.get("broken", 0) + 1
    elif image:
        # Loaded over https, as the page is; 'statelegs' checked that copy.
        out["image"] = statelegs.secure(image)
    return out


def build_state(code, root=".", places=None, roster=None, control=None, fetched="",
                dropped=None):
    """One state's legislature page data. *control* is the state's entry in
    ``stategov.build``'s payload: its chambers' counts and who runs them;
    *fetched* the roster's date; *dropped* counts the portraits left off."""
    year = int(fetched[:4]) if fetched[:4].isdigit() else 0
    assembly = latest_assembly(roster or [])
    others = surnames(roster or [])

    def person(record):
        return _person(record, code, year, assembly, dropped, others)

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
    out = {}
    for code in codes or STATES:
        roster = cache["states"].get(code) or []
        topo = statelegs.load_map(code, root)
        if topo:
            statelegs.match(code, roster, topo)
        counts = {} if dropped is None else dropped.setdefault(code, {})
        out[code] = build_state(code, root, places, roster, control.get(code),
                                cache.get("fetched", ""), counts)
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
    name: reported by ``statelegs``)."""
    if record.get("tribalSeat"):
        return "tribal"
    if code == "NH" and record["chamber"] == "lower":
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
    nothing is marked: West Virginia elects "one of the two seats in each
    of the 17 districts" and Montana "25 of 50", which no district list
    shows. A special election is not a regular one and is never marked;
    the chamber's line quotes the record, specials and all."""
    entry = (ballot2026.STATES.get(code) or {}).get(chamber)
    if not entry or not districts:
        return {}
    _name, total, up, basis, _source = entry
    if up == 0:
        return {i: False for i in districts}
    if up == total:
        return {i: True for i in districts}
    per = total / len(districts)
    if per != int(per):
        return {}
    head = re.split(r"[(;]", basis)[0]
    rule = re.search(r"\bthe (\d+) (even|odd)-numbered districts\b", head)
    if rule:
        parity = 0 if rule.group(2) == "even" else 1
        chosen = {i for i, d in districts.items()
                  if d["name"].isdigit() and int(d["name"]) % 2 == parity}
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


def stats(maps):
    districts = sum(len(c["districts"]) for m in maps.values() for c in m["chambers"].values())
    people = sum(len(v) for m in maps.values() for c in m["chambers"].values()
                 for v in c["members"].values())
    unplaced = sum(len(m["unplaced"]) for m in maps.values())
    return {"states": len(maps), "districts": districts, "placed": people, "unplaced": unplaced}
