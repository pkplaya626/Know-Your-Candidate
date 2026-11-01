"""The local questions on the November 3, 2026 ballot in the most populous
counties (rule 102).

The site listed each state's statewide questions (rule 95) and said that
local questions were "not listed here". By the owner's decision of
2026-11-01 ("largest places first"), they are now listed for the 50 most
populous counties, by the Census Bureau's Vintage 2024 estimates: the
county's own questions, those of districts that cover the whole county, and
those of each city of 250,000 people or more in it. Nothing keyed by an id
lists them, so they are a hand-edited cache, ``data/local_measures.json``,
researched county by county from the county election office's or the city
clerk's own sample ballot or list of measures, or the state election
office's list of local questions - never Ballotpedia, news or another
compilation, which were leads only (rule 50).

Each county record says, for the county and its countywide districts and for
each covered city, one of these:

- ``listed``: the questions, each with its jurisdiction, its designation and
  title as printed (null where the office prints none), its text as printed
  or the office's printed summary (``summary``), its kind, its source's
  address, title and words, and the day read. ``partial`` says in words what
  the list may be missing, where an office's own list could not be read;
- ``none``: no question, on a document's own words - a statement that there
  is none or a count of the questions (``statement``), or a ballot or list
  whose own words say it holds every contest (``complete``, quoted), or every
  ballot style read whole (``every``), or no county government to put one
  (``noGovernment``, which the page says of the county alone: it shows
  nothing about districts that cover the county, which it says were not
  looked for);
- ``unlisted``: a document that lists none, but whose words do not say it is
  complete: the page says what it lists and does not say there is none
  (rule 19);
- ``notFound``: no official list could be read, and why, in plain words;
- ``elsewhere`` (a city): listed under another covered county, which holds
  most of it; the page shows that county's entry;
- ``same`` (a county): one government with a city, listed under the city.

The page says a question only in its official words, and never what a yes or
a no vote does; no colour suggests a side. Questions decided at an earlier
2026 election, or taken off the ballot by a court, are not listed, nor one
the source marks withdrawn (Sacramento's list printed "WITHDRAWN -- Measure
F" over a question the first cache listed). ``check``
holds the cache to all of this; ``for_state`` and ``index`` write what
``data/localmeasures/`` holds, loaded only where a county's questions are
shown (rule 94).
"""

import json
import os
import re
from urllib.parse import urlparse

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "local_measures.json")
ELECTION = "2026-11-03"
READ_EARLIEST, READ_LATEST = "2026-01-01", "2026-12-31"
COUNTIES = 50
CITY_POPULATION = 250000

# A measure's kind, in the page's words.
KINDS = {
    "bond": "Bond",
    "tax": "Tax",
    "tax exemption": "Tax exemption",
    "charter amendment": "Charter amendment",
    "ordinance": "Ordinance",
    "franchise": "Franchise",
    "spending limit": "Spending limit",
    "lease": "Lease of city property",
    "advisory": "Advisory question",
    None: None,
}
JURISDICTIONS = ("county", "district", "city")
OWN_STATUSES = ("listed", "none", "unlisted", "notFound", "same")
CITY_STATUSES = ("listed", "none", "unlisted", "notFound", "elsewhere")
BASES = ("statement", "ballots", "list", "noGovernment")

COUNTY_KEYS = frozenset({"state", "name", "rank", "office", "read", "own", "cities", "measures",
                         "notes"})
MEASURE_KEYS = frozenset({"jurisdiction", "designation", "title", "text", "summary", "textNote",
                          "textMissing", "kind", "source", "read", "voters", "notes"})
BASIS_KEYS = frozenset({"from", "source", "found", "complete", "every"})

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FIPS = re.compile(r"^\d{5}$")
_PLACE = re.compile(r"^\d{7}$")
_NOT_A_TITLE = re.compile(r"https?:|www\.|\blinked\b|\bdescribed as\b|\bedition:|\bquery:", re.I)
_CUT = re.compile(r"\.\.\.|…")
_ONLY_A_LABEL = re.compile(r"^\W*(?:EN_\d+\W*)?(?:composite|facsimile|reference|sample|"
                           r"official)(?:\W+(?:ballot|page))*(?:\W+\d+)?\W*$", re.I)
_OFF_THE_BALLOT = re.compile(r"\bwithdrawn\b|\bremoved from the ballot\b|\bstricken from the "
                             r"ballot\b|\btaken off the ballot\b", re.I)


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ------------------------------------------------------------- sources

def _host(url):
    return (urlparse(str(url or "")).hostname or "").lower()


def listed_hosts(url):
    """Every ``(key, counties, publisher, evidence)`` of the
    ``overrides.LOCAL_MEASURE_SOURCES`` entries *url* falls under, an
    address's own entry (a key starting ``https://``) before its host's: a
    host is a source for its own county, and for another county only through
    the one document its evidence names."""
    from . import overrides
    url = str(url or "")
    host = _host(url)
    prefixed, hosts = [], []
    for key, (counties, label, evidence) in overrides.LOCAL_MEASURE_SOURCES.items():
        if key.startswith("https://"):
            if url.startswith(key):
                prefixed.append((key, counties, label, evidence))
        elif host == key or host.endswith("." + key):
            hosts.append((key, counties, label, evidence))
    return prefixed + hosts


def listed_host(url):
    """The first of ``listed_hosts(url)``, or None."""
    found = listed_hosts(url)
    return found[0] if found else None


def official(url, fips, state):
    """``(True, publisher)`` when *url* is the county's, a covered city's or
    the state election office's own page, else ``(False, why)``. A compiled
    table, a news site or an advocate's page is never one (rule 50)."""
    from . import voting_dates
    if not re.match(r"^https://", str(url or "")):
        return False, "not an https address"
    if voting_dates.compiled(str(url)):
        return False, "a compiled table, a lead and never a source (rule 50)"
    found = listed_hosts(url)
    if found:
        for _key, counties, label, _evidence in found:
            if fips in counties:
                return True, label
        counties = sorted({c for entry in found for c in entry[1]})
        return False, f"a source for {'/'.join(counties)}, not {fips}"
    ok, label = voting_dates.official_source(url, state)
    if ok:
        return True, label
    return False, f"{_host(url)} is not an official host recorded for {fips}"


def _source_problems(where, fips, state, source, *, quoted=True):
    if not isinstance(source, dict) or not source.get("url"):
        return [f"{where}: no source"]
    out = []
    ok, why = official(source["url"], fips, state)
    if not ok:
        out.append(f"{where}: {source['url']} is not an official source ({why})")
    if quoted and not str(source.get("quote") or "").strip():
        out.append(f"{where}: its source is not quoted")
    if not str(source.get("title") or "").strip():
        out.append(f"{where}: its source has no title")
    elif _NOT_A_TITLE.search(source["title"]):
        out.append(f"{where}: its title carries a note or an address, not the document's own "
                   f"name: {source['title']!r}")
    extra = set(source) - {"url", "title", "quote"}
    if extra:
        out.append(f"{where}: its source has unknown field(s) {', '.join(sorted(extra))}")
    return out


def _date_problems(where, day):
    day = str(day or "")
    if not _DATE.match(day):
        return [f"{where}: no day read"]
    if not READ_EARLIEST <= day <= READ_LATEST:
        return [f"{where}: read on {day}, outside the cycle"]
    return []


# ------------------------------------------------------------- checking

def problems(data):
    """Every way *data* breaks the cache's rules, as strings."""
    if not isinstance(data, dict):
        return ["no record"]
    out = []
    if data.get("election") != ELECTION:
        out.append(f"the election is {data.get('election')!r}, not {ELECTION}")
    cover = data.get("coverage") or {}
    if cover.get("counties") != COUNTIES or cover.get("cityPopulation") != CITY_POPULATION:
        out.append("the coverage is not the 50 most populous counties and their cities of 250,000")
    ranking = cover.get("ranking") or {}
    if not (ranking.get("url") and ranking.get("title") and ranking.get("by")):
        out.append("the coverage does not name the ranking it rests on")
    counties = data.get("counties")
    if not isinstance(counties, dict):
        return out + ["'counties' is not a record"]
    ranks = sorted(c.get("rank") for c in counties.values() if isinstance(c, dict)
                   and isinstance(c.get("rank"), int))
    if ranks != list(range(1, len(counties) + 1)) or len(counties) != COUNTIES:
        out.append(f"the counties are not ranked 1 to {COUNTIES} once each")
    for fips, record in sorted(counties.items()):
        out += county_problems(fips, record, counties)
    return out


def county_problems(fips, rec, counties):
    if not _FIPS.match(str(fips)):
        return [f"{fips}: not a county code"]
    if not isinstance(rec, dict):
        return [f"{fips}: not a record"]
    out = []
    extra = set(rec) - COUNTY_KEYS
    if extra:
        out.append(f"{fips}: unknown field(s) {', '.join(sorted(extra))}")
    from .normalize import US_STATES
    state = rec.get("state")
    if state not in set(US_STATES.values()):
        return out + [f"{fips}: no state"]
    if not str(rec.get("name") or "").strip():
        out.append(f"{fips}: no name")
    office = rec.get("office") or {}
    if not office.get("name"):
        out.append(f"{fips}: no election office named")
    else:
        ok, why = official(office.get("url"), fips, state)
        if not ok:
            out.append(f"{fips} office: {office.get('url')} is not official ({why})")
    out += _date_problems(fips, rec.get("read"))
    measures = rec.get("measures")
    if not isinstance(measures, list):
        return out + [f"{fips}: 'measures' is not a list"]
    for i, m in enumerate(measures):
        out += measure_problems(fips, state, i, m)
    good = [m for m in measures if isinstance(m, dict) and isinstance(m.get("jurisdiction"), dict)]
    own_measures = [m for m in good if m["jurisdiction"].get("kind") in ("county", "district")]
    places = {m["jurisdiction"].get("place") for m in good if m["jurisdiction"].get("kind") == "city"}
    cities = rec.get("cities")
    if not isinstance(cities, list):
        return out + [f"{fips}: 'cities' is not a list"]
    by_place = {}
    for c in cities:
        if isinstance(c, dict):
            by_place[c.get("place")] = c
    out += own_problems(fips, state, rec.get("own"), own_measures, by_place)
    for c in cities:
        out += city_problems(fips, state, c, good, counties)
    for place in sorted(p for p in places if p not in by_place):
        out.append(f"{fips}: a city measure for place {place}, which the record does not cover")
    return out


def basis_problems(where, fips, state, b):
    if not isinstance(b, dict):
        return [f"{where}: no basis"]
    out = []
    extra = set(b) - BASIS_KEYS
    if extra:
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))}")
    if b.get("from") not in BASES:
        out.append(f"{where}: rests on {b.get('from')!r}, not one of {', '.join(BASES)}")
    out += _source_problems(where, fips, state, b.get("source"))
    if not str(b.get("found") or "").strip():
        out.append(f"{where}: does not say what the document shows ('found')")
    complete = b.get("complete")
    quote = str((b.get("source") or {}).get("quote") or "")
    if complete is not None and str(complete) not in quote:
        out.append(f"{where}: its 'complete' words are not in its source's quote")
    elif complete is not None and str(complete).strip().lower() in \
            str((b.get("source") or {}).get("title") or "").lower():
        # Tarrant's "Districts in Election", quoted as showing the list was
        # whole, was only the document's name.
        out.append(f"{where}: its 'complete' words are only its source's title")
    elif complete is not None and _ONLY_A_LABEL.match(str(complete)):
        # San Diego's reference ballot is titled "Composite Ballot" and footed
        # "Composite Page 20", and prints no City of San Diego or Chula Vista
        # question: a label says what the document is called, not that it
        # holds every contest.
        out.append(f"{where}: its 'complete' words are only a label of the document "
                   f"({complete!r}), not words saying it holds every contest")
    if "every" in b and b["every"] is not True:
        out.append(f"{where}: 'every' is true or absent")
    return out


def _none_problems(where, b):
    """A "none" rests on a document's own words (rule 19): a statement or a
    count of the questions, or a ballot or list whose words say it is whole,
    or every ballot style read whole, or no county government at all."""
    basis = b.get("from")
    if basis == "noGovernment":
        return []
    if basis == "statement" and not b.get("complete"):
        return [f"{where}: a statement with no words quoted as saying it ('complete')"]
    if basis in ("ballots", "list") and not (b.get("complete") or b.get("every")):
        return [f"{where}: 'none' on a {basis} whose words do not say it holds every contest; "
                "it is 'unlisted'"]
    return []


def own_problems(fips, state, own, own_measures, by_place):
    where = f"{fips} county"
    if not isinstance(own, dict) or own.get("status") not in OWN_STATUSES:
        return [f"{where}: status is not one of {', '.join(OWN_STATUSES)}"]
    status = own["status"]
    out = []
    allowed = {"status", {"listed": "partial", "none": "basis", "unlisted": "basis",
                          "notFound": "why", "same": "city"}[status]}
    extra = set(own) - allowed
    if extra:
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))} for '{status}'")
    if status == "listed":
        if not own_measures:
            out.append(f"{where}: 'listed', and no county or countywide question is listed")
        if "partial" in own and not str(own["partial"] or "").strip():
            out.append(f"{where}: an empty 'partial'")
        return out
    if own_measures:
        out.append(f"{where}: '{status}', yet {len(own_measures)} county question(s) listed")
    if status in ("none", "unlisted"):
        out += basis_problems(where, fips, state, own.get("basis"))
        if status == "none" and isinstance(own.get("basis"), dict):
            out += _none_problems(where, own["basis"])
    elif status == "notFound":
        if not str(own.get("why") or "").strip():
            out.append(f"{where}: not found, and not said why")
    elif status == "same":
        city = by_place.get(own.get("city"))
        if not city or city.get("status") == "elsewhere":
            out.append(f"{where}: one government with a city the record does not list")
    return out


def city_problems(fips, state, c, measures, counties):
    if not isinstance(c, dict):
        return [f"{fips}: a city that is not a record"]
    where = f"{fips} {c.get('name') or 'city'}"
    out = []
    if not str(c.get("name") or "").startswith(("City of ", "Town of ")):
        out.append(f"{where}: a city is named as its government is ('City of ...')")
    if not _PLACE.match(str(c.get("place") or "")):
        out.append(f"{where}: no Census place code")
    status = c.get("status")
    if status not in CITY_STATUSES:
        return out + [f"{where}: status is not one of {', '.join(CITY_STATUSES)}"]
    allowed = {"name", "place", "status",
               {"listed": "partial", "none": "basis", "unlisted": "basis", "notFound": "why",
                "elsewhere": "listedIn"}[status]}
    extra = set(c) - allowed
    if extra:
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))} for '{status}'")
    mine = [m for m in measures if m["jurisdiction"].get("kind") == "city"
            and m["jurisdiction"].get("place") == c.get("place")]
    for m in mine:
        # A city's questions are the city's own. Los Angeles's Measure SC
        # amends the City Charter, but the Registrar prints it under the
        # school district's own heading, apart from the city's seven: listed
        # with them, it made the city's count eight against the document's
        # seven, and the district's voters outside the city never saw it.
        if m["jurisdiction"].get("name") != c.get("name"):
            out.append(f"{where}: a question of {m['jurisdiction'].get('name')!r} is listed as the "
                       "city's; a city's questions are its own")
    if status == "listed":
        if not mine:
            out.append(f"{where}: 'listed', and none of its questions is listed")
        return out
    if mine:
        out.append(f"{where}: '{status}', yet {len(mine)} of its question(s) listed")
    if status in ("none", "unlisted"):
        out += basis_problems(where, fips, state, c.get("basis"))
        if status == "none" and isinstance(c.get("basis"), dict):
            out += _none_problems(where, c["basis"])
        if (c.get("basis") or {}).get("from") == "noGovernment":
            out.append(f"{where}: 'noGovernment' speaks of a county with no government, "
                       "never of a city")
    elif status == "notFound":
        if not str(c.get("why") or "").strip():
            out.append(f"{where}: not found, and not said why")
    elif status == "elsewhere":
        other = counties.get(c.get("listedIn"))
        theirs = [x for x in (other or {}).get("cities") or []
                  if isinstance(x, dict) and x.get("place") == c.get("place")]
        if c.get("listedIn") == fips or not other:
            out.append(f"{where}: listed in {c.get('listedIn')!r}, which is not another covered county")
        elif not theirs or theirs[0].get("status") == "elsewhere":
            out.append(f"{where}: {c.get('listedIn')} does not list this city itself")
    return out


def measure_problems(fips, state, i, m):
    if not isinstance(m, dict):
        return [f"{fips} measure {i + 1}: not a record"]
    where = f"{fips} {m.get('designation') or m.get('title') or 'measure ' + str(i + 1)}"
    out = []
    extra = set(m) - MEASURE_KEYS
    if extra:
        # A "yes vote means", a forecast, a position: none is the office's
        # designation, title, text or kind, and none is shown.
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))}")
    j = m.get("jurisdiction")
    if not isinstance(j, dict) or j.get("kind") not in JURISDICTIONS or not j.get("name"):
        out.append(f"{where}: no jurisdiction (a county, a district or a city, named)")
    elif j["kind"] == "city" and not _PLACE.match(str(j.get("place") or "")):
        out.append(f"{where}: a city's question carries no Census place code")
    elif j["kind"] != "city" and "place" in j:
        out.append(f"{where}: a place code on a {j['kind']}'s question")
    elif set(j) - {"kind", "name", "place"}:
        out.append(f"{where}: unknown jurisdiction field(s)")
    for key in ("designation", "title"):
        if m.get(key) is not None and not str(m[key]).strip():
            out.append(f"{where}: an empty {key} (null where the office prints none)")
    if not (m.get("designation") or m.get("title")):
        out.append(f"{where}: neither a designation nor a title")
    text = m.get("text")
    if text is None:
        if not str(m.get("textMissing") or "").strip():
            out.append(f"{where}: no text, and not said why ('textMissing')")
    elif not str(text).strip():
        out.append(f"{where}: an empty text")
    elif m.get("textMissing"):
        out.append(f"{where}: 'textMissing' beside a text")
    if "summary" in m and m["summary"] is not True:
        out.append(f"{where}: 'summary' is true or absent")
    if m.get("kind") not in KINDS:
        out.append(f"{where}: unknown kind {m.get('kind')!r}")
    said = " ".join(str(x or "") for x in (m.get("text"), m.get("title"),
                                           (m.get("source") or {}).get("quote")))
    gone = _OFF_THE_BALLOT.search(said)
    if gone:
        # Sacramento's list printed "WITHDRAWN -- Measure F" over a question
        # the first cache listed as on the ballot, its quote cut after it.
        out.append(f"{where}: its source says {gone.group(0)!r}: a question taken off the "
                   "ballot is not listed")
    out += _source_problems(where, fips, state, m.get("source"))
    out += _date_problems(where, m.get("read"))
    return out


def check(data):
    """Raise ``ValueError`` listing every problem, or return *data*."""
    found = problems(data)
    if found:
        raise ValueError("; ".join(found))
    return data


def unused_hosts(data):
    """``overrides.LOCAL_MEASURE_SOURCES`` entries no address in *data*
    rests on - the entry that makes an address a source for its county: a
    stale entry is invisible and quietly wrong."""
    from . import overrides
    used = set()
    for fips, rec in ((data or {}).get("counties") or {}).items():
        urls = [rec.get("office", {}).get("url")]
        urls += [m.get("source", {}).get("url") for m in rec.get("measures") or []]
        for part in [rec.get("own") or {}] + list(rec.get("cities") or []):
            urls.append(((part.get("basis") or {}).get("source") or {}).get("url"))
        for url in urls:
            for entry in listed_hosts(url):
                if fips in entry[1]:
                    used.add(entry[0])
                    break
    return sorted(set(overrides.LOCAL_MEASURE_SOURCES) - used)


# ------------------------------------------------------------- the page

def _basis(b):
    out = {"from": b["from"], "url": b["source"]["url"], "title": b["source"]["title"],
           "found": b["found"]}
    if b.get("complete"):
        out["words"] = b["complete"]
    if b.get("every"):
        out["every"] = True
    return out


def _measure(m):
    j = m["jurisdiction"]
    out = {
        "j": j["name"],
        "jk": j["kind"],
        "designation": (m.get("designation") or "").strip() or None,
        "title": (m.get("title") or "").strip() or None,
        "kind": KINDS.get(m.get("kind")),
        "source": m["source"]["url"],
        "sourceTitle": m["source"]["title"],
        "read": m["read"],
    }
    if j.get("place"):
        out["place"] = j["place"]
    if m.get("text"):
        out["text"] = m["text"].strip()
        if _CUT.search(m["text"]):
            out["cut"] = True
    else:
        out["missing"] = m["textMissing"]
    if m.get("summary"):
        out["summary"] = True
    if m.get("textNote"):
        out["note"] = m["textNote"]
    if m.get("voters"):
        out["voters"] = m["voters"]
    return out


def _part(part, measures):
    out = {"status": part["status"]}
    if part.get("partial"):
        out["partial"] = part["partial"]
    if part.get("basis"):
        out["basis"] = _basis(part["basis"])
    if part.get("why"):
        out["why"] = part["why"]
    if measures:
        out["measures"] = [_measure(m) for m in measures]
    return out


def for_county(fips, rec, counties):
    """One county's record in the page's words, with a city listed under
    another county taken from that county's record."""
    measures = rec["measures"]
    own = [m for m in measures if m["jurisdiction"]["kind"] in ("county", "district")]
    out = {
        "state": rec["state"],
        "name": rec["name"],
        "read": rec["read"],
        "office": {"name": rec["office"]["name"], "url": rec["office"]["url"]},
        "own": _part(rec["own"], own),
        "cities": [],
    }
    if rec["own"]["status"] == "same":
        out["own"]["city"] = rec["own"]["city"]
    for c in rec["cities"]:
        home, where = c, rec
        if c["status"] == "elsewhere":
            where = counties[c["listedIn"]]
            home = next(x for x in where["cities"] if x["place"] == c["place"])
        mine = [m for m in where["measures"] if m["jurisdiction"]["kind"] == "city"
                and m["jurisdiction"].get("place") == c["place"]]
        entry = dict(_part(home, mine), name=c["name"], place=c["place"])
        if where is not rec:
            entry["from"] = {"fips": c["listedIn"], "name": where["name"],
                             "office": where["office"]["name"]}
            entry["read"] = where["read"]
        out["cities"].append(entry)
    return out


def for_state(data):
    """``{state: {fips: record}}``: what each ``data/localmeasures/<st>.js``
    holds. A cache that breaks its rules is refused, not shown."""
    check(data)
    counties = data["counties"]
    out = {}
    for fips, rec in sorted(counties.items()):
        out.setdefault(rec["state"], {})[fips] = for_county(fips, rec, counties)
    return out


def samples(voting):
    """``{state: {url, label?, linked}}``: each state's sample-ballot page as
    the build's voting record holds it (``voting.for_page``), for a county
    page to name beside "not listed here" - the county pages load no build
    figures, and Your ballot's words for the link are the same
    (``KYC.sampleBallotLine``)."""
    out = {}
    for code, links in sorted((voting or {}).items()):
        if code.startswith("_") or not isinstance(links, dict) or not links.get("sample"):
            continue
        entry = {"url": links["sample"],
                 "linked": "sample" in ((voting.get("_siteLinked") or {}).get(code) or [])}
        label = ((voting.get("_labels") or {}).get(code) or {}).get("sample")
        if label:
            entry["label"] = label
        out[code] = entry
    return out


def load_samples(root="."):
    """``samples`` of the committed voting record."""
    from . import voting, voting_dates
    return samples(voting.for_page(voting.load_cache(root), voting_dates.load(root)))


def index(data, sample_ballots=None):
    """What ``data/localmeasures/index.js`` holds: which counties are
    covered, on what ranking, and each state's sample-ballot page."""
    check(data)
    cover = data["coverage"]
    return {
        "election": data["election"],
        "counties": {fips: [rec["state"], rec["name"]]
                     for fips, rec in sorted(data["counties"].items())},
        "cityPopulation": cover["cityPopulation"],
        "ranking": cover["ranking"],
        "samples": sample_ballots or {},
    }


def stats(data):
    counties = (data or {}).get("counties") or {}
    measures = [m for r in counties.values() for m in r.get("measures") or []]
    parts = [r.get("own") or {} for r in counties.values()]
    parts += [c for r in counties.values() for c in r.get("cities") or []]
    return {
        "counties": len(counties),
        "measures": len(measures),
        "cities": sum(1 for r in counties.values() for c in r.get("cities") or []
                      if c.get("status") != "elsewhere"),
        "none": sum(1 for p in parts if p.get("status") == "none"),
        "unlisted": sum(1 for p in parts if p.get("status") == "unlisted"),
        "notFound": sum(1 for p in parts if p.get("status") == "notFound"),
    }
