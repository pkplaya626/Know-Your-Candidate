"""Political history: the public offices a person has held, where, and when.

Two sources, each for what it does well, joined to the person by id only:

- **Congress** - congress-legislators, the same project as the membership
  snapshot: every term of every member, current and former, by bioguide id.
  Consecutive terms in one seat become one span ("U.S. Representative, CA-12,
  2013-2023, 5 terms"). Authoritative; shown as years.
- **Every other public office** - Wikidata's "position held" (P39) on the
  person's own item: the id congress-legislators records for a member, the
  item an election page's article belongs to for a challenger (rule 33), the
  Cabinet history's id for an officer (kyc/cabinet.py). Raw P39 is mostly
  noise, so a statement is kept only when:
    - it is not deprecated, and carries no qualifier that changes its
      meaning (Jerry Moran's "Kansas Attorney General, 1982-1985" is
      qualified "instance of: assistant");
    - it is not a seat in Congress (that is the first source's);
    - the position is a public office or a judgeship by its own class, with
      a jurisdiction that is a U.S. place (a "senator" or "mayor" with no
      place, a party chair, an intern are not);
    - a federal post (jurisdiction: the United States) is on the reviewed
      list of offices this site already knows (the Cabinet's, the
      presidency's);
    - it has a start.
  Per-session statements of one office are merged into spans.

  A span is shown only when the person's own Wikipedia infobox (the item's
  sitelink) has the same start and end years; within a year, it is shown
  and says the sources differ by a year; otherwise it is withheld and the
  build reports it. Years only: Wikidata often records the election year,
  the infobox the year sworn in. An office still open is "since" only when
  the infobox agrees it is ongoing; otherwise its end is "not recorded".

Names are never read from Wikidata: an office is shown by its own
Wikipedia article's title where it has one. A profile with no linked item
reads "no linked record of other public offices", never "none" (rule 19).
A read that fails keeps the last cache (rule 8).
"""

import datetime
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "political_history.json")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "KnowYourCandidate/1.0 (https://github.com/pkplaya626/Know-Your-Candidate; civic data)"
PAUSE = 0.5
BATCH = 50

HUMAN, USA = "Q5", "Q30"
PUBLIC_OFFICE, JUDGE, LEGISLATOR = "Q294414", "Q16533", "Q4175034"
ADMIN_ENTITY, COUNTRY, ELECTORAL_DISTRICT = "Q56061", "Q6256", "Q192611"
# Seats in Congress, and Congress's own posts: congress-legislators' to say.
CONGRESS = {"Q13218630", "Q4416090", "Q5253588", "Q139796506", "Q139796629", "Q1294433"}
# Qualifiers that change what a statement says ("instance of: assistant").
MEANING_QUALIFIERS = ("P31", "P2868", "P3831", "P642", "P1039", "P39")
# Federal posts (jurisdiction: the United States) shown when held: the
# presidency, the offices kyc/federal_offices.py tracks, a few more held by
# people on this site, and any post of these classes.
PRESIDENCY = {"Q11696", "Q11699"}
FEDERAL_POSTS = {
    "Q1364289",   # United States Deputy Attorney General
    "Q1414246",   # United States National Security Advisor
    "Q2094335",   # United States Attorney
    "Q22230876",  # Administrator of the United States Agency for International Development
    "Q2298067",   # Solicitor General of the United States
}
AMBASSADOR, FEDERAL_JUDGE = "Q15726790", "Q1006696"
FEDERAL_CLASSES = {AMBASSADOR, FEDERAL_JUDGE}

_PRECISION = {11: "day", 10: "month", 9: "year"}


class HistoryError(RuntimeError):
    """A source could not be read, or is not what the pipeline knows."""


def _get(url, data=None, timeout=90):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/sparql-results+json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except (OSError, ValueError) as exc:
        raise HistoryError(f"could not read {url.split('?')[0]}: {exc}") from exc
    # An API that answers with an error ("maxlag", a bad batch) has read
    # nothing; taken as an empty answer it would drop people silently.
    if isinstance(data, dict) and "error" in data:
        raise HistoryError(f"{url.split('?')[0]} answered with an error: "
                           f"{str(data['error'])[:200]}")
    return data


def federal_items():
    from . import federal_offices
    return PRESIDENCY | FEDERAL_POSTS | {o["wikidata"] for o in federal_offices.OFFICES
                                         if o.get("wikidata")}


# --------------------------------------------------------------- Congress

# The title of each non-voting House member's office; summary.by_state
# gives the state pages the same words.
DELEGATE_TITLES = {"PR": "Resident Commissioner", "DC": "Delegate", "GU": "Delegate", "VI": "Delegate",
                   "AS": "Delegate", "MP": "Delegate"}
_TERRITORIES = DELEGATE_TITLES


def _seat(term):
    if term["type"] == "sen":
        return ("Senate", term["state"], None)
    return ("House", term["state"], term.get("district"))


def congress_spans(terms, read_day):
    """Consecutive terms in one seat as one span: ``[{office, state,
    district, from, to, terms, current}]``, newest first. A term still
    running on *read_day* is current."""
    spans = []
    for term in sorted(terms, key=lambda t: t["start"]):
        seat = _seat(term)
        last = spans[-1] if spans else None
        gap = None
        if last and last["seat"] == seat:
            gap = (datetime.date.fromisoformat(term["start"]) -
                   datetime.date.fromisoformat(last["end"])).days
        if last is not None and gap is not None and gap <= 40:
            last["end"], last["terms"] = term["end"], last["terms"] + 1
        else:
            spans.append({"seat": seat, "start": term["start"], "end": term["end"], "terms": 1})
    out = []
    for span in reversed(spans):
        chamber, state, district = span["seat"]
        office = ("U.S. Senator" if chamber == "Senate" else
                  _TERRITORIES.get(state, "U.S. Representative"))
        current = span["end"] > read_day
        terms = span["terms"]
        if state == "PR":
            # A four-year term, listed one Congress at a time (as
            # kyc/profiles.py notes): counted by its length, not its rows.
            years = (datetime.date.fromisoformat(span["end"]) -
                     datetime.date.fromisoformat(span["start"])).days / 365.25
            terms = max(1, math.ceil(years / 4 - 0.05))
        out.append({"office": office, "state": state,
                    "district": None if chamber == "Senate" or state in _TERRITORIES else district,
                    "from": span["start"][:4], "to": None if current else span["end"][:4],
                    # The dates themselves, so the build decides what is
                    # current against the membership it builds from.
                    "start": span["start"], "end": span["end"],
                    "terms": terms, "current": current,
                    "source": "congress-legislators"})
    return out


# ---------------------------------------------------------------- Wikidata

def _claims(entity, prop):
    return [c for c in (entity.get("claims") or {}).get(prop, [])]


def _item(snak):
    value = ((snak or {}).get("datavalue") or {}).get("value")
    return value.get("id") if isinstance(value, dict) else None


def _time(snak):
    value = ((snak or {}).get("datavalue") or {}).get("value")
    if not isinstance(value, dict) or "time" not in value:
        return None
    precision = _PRECISION.get(value.get("precision"))
    match = re.match(r"^\+(\d{4})-(\d{2})-(\d{2})", value["time"])
    if not precision or not match:
        return None
    return {"year": match.group(1), "date": "-".join(match.groups()), "precision": precision}


def statements(entity):
    """The P39 statements of a person's item: ``[{position, start, end,
    district, rank, meaning}]``."""
    out = []
    for claim in _claims(entity, "P39"):
        position = _item(claim.get("mainsnak"))
        if not position:
            continue
        qualifiers = claim.get("qualifiers") or {}
        first = lambda prop: (qualifiers.get(prop) or [None])[0]  # noqa: E731
        out.append({
            "position": position, "rank": claim.get("rank"),
            "start": _time(first("P580")), "end": _time(first("P582")),
            "district": _item(first("P768")),
            "meaning": sorted(p for p in MEANING_QUALIFIERS if qualifiers.get(p)),
            "id": claim.get("id"),
        })
    return out


def entities(ids, read=None, props="claims|sitelinks", extra=None):
    """``{id: entity}`` for each id, in batches."""
    read = read or _get
    out = {}
    ids = sorted(set(i for i in ids if i))
    for i in range(0, len(ids), BATCH):
        params = {"action": "wbgetentities", "ids": "|".join(ids[i:i + BATCH]), "props": props,
                  "sitefilter": "enwiki", "languages": "en", "format": "json"}
        params.update(extra or {})
        data = read(f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}")
        for key, entity in (data.get("entities") or {}).items():
            if "missing" not in entity:
                out[key] = entity
        if read is _get:
            time.sleep(PAUSE)
    return out


def _results(data):
    """A SPARQL answer's rows; an answer without them read nothing."""
    try:
        return data["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise HistoryError("the Wikidata query service answered without results") from exc


def short(new, old, people=0.9, offices=0.8):
    """Why *new* reads short against the committed *old* cache, or None: a
    read that lost a tenth of its people, or a fifth of their offices, is a
    failed read, not a change in anyone's career."""
    if not old:
        return None
    count = lambda c: sum(len(p.get("offices") or []) for p in c["people"].values())  # noqa: E731
    if len(new["people"]) < people * len(old["people"]):
        return f"{len(new['people'])} people against {len(old['people'])} last read"
    if count(new) < offices * count(old):
        return f"{count(new)} offices against {count(old)} last read"
    return None


def sitelink(entity):
    return ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")


def classes(items, read=None):
    """``{item: {roots}}``: which of the classes this module tests each item
    reaches through instance-of and subclass-of."""
    read = read or _get
    roots = [PUBLIC_OFFICE, JUDGE, LEGISLATOR, ADMIN_ENTITY, COUNTRY, ELECTORAL_DISTRICT,
             *FEDERAL_CLASSES, *CONGRESS]
    out = {}
    items = sorted(set(i for i in items if i))
    for i in range(0, len(items), 150):
        query = ("SELECT ?item ?root WHERE { VALUES ?item {%s} VALUES ?root {%s} "
                 "?item (wdt:P31|wdt:P279)/wdt:P279* ?root . }") % (
            " ".join("wd:" + q for q in items[i:i + 150]), " ".join("wd:" + r for r in roots))
        data = _results(read(SPARQL_URL, urllib.parse.urlencode({"query": query, "format": "json"}).encode()))
        for row in data:
            out.setdefault(row["item"]["value"].rsplit("/", 1)[1], set()).add(
                row["root"]["value"].rsplit("/", 1)[1])
        if read is _get:
            time.sleep(PAUSE)
    return out


# ----------------------------------------------------------- the filter

def federal(position, reach, allowed):
    """True for a federal post this module shows: one on the reviewed list,
    or an ambassadorship or federal judgeship by its class. Their own
    classes often never reach "public office" (the CIA's directorship, the
    Trade Representative), which is why they are listed, not inferred."""
    return position in allowed or bool(reach.get(position, set()) & FEDERAL_CLASSES)


def keep(statement, positions, reach, allowed):
    """None to keep a statement, else why it is dropped."""
    position = statement["position"]
    info = positions.get(position) or {}
    if statement["rank"] == "deprecated":
        return "deprecated"
    if statement["meaning"]:
        return "qualified " + ",".join(statement["meaning"])
    up = set(info.get("superclasses") or ())
    if position in CONGRESS or up & CONGRESS or reach.get(position, set()) & CONGRESS:
        return "congress"
    if not statement["start"]:
        return "no start"
    if federal(position, reach, allowed):
        return None
    if info.get("jurisdiction") == USA and LEGISLATOR in reach.get(position, set()):
        return "congress"
    if not reach.get(position, set()) & {PUBLIC_OFFICE, JUDGE}:
        return "not a public office"
    where = info.get("jurisdiction")
    if not where:
        return "no place"
    if where == USA:
        return "federal, not on the reviewed list"
    if not (positions.get(where) or {}).get("us") or not reach.get(where, set()) & {ADMIN_ENTITY, COUNTRY}:
        return "not a U.S. place"
    return None


def merge(rows):
    """Statements of one position, sorted, joined where one starts within
    sixty days of the last one's end (per-session statements); never across
    an open-ended one."""
    spans = []
    for row in sorted(rows, key=lambda r: r["start"]["date"]):
        last = spans[-1] if spans else None
        if last and last["end"] and row["start"]:
            gap = (datetime.date.fromisoformat(_full(row["start"]["date"])) -
                   datetime.date.fromisoformat(_full(last["end"]["date"], end=True))).days
            if gap <= 60:
                if row["end"] is None or row["end"]["date"] > last["end"]["date"]:
                    last["end"] = row["end"]
                last["ids"].append(row["id"])
                last["districts"].add(row["district"])
                continue
        spans.append(dict(row, ids=[row["id"]], districts={row["district"]}))
    # A span that crosses a redistricting has no one district: Tim Kennedy
    # held New York's 58th Senate district, then another, in one span.
    for span in spans:
        named = span.pop("districts") - {None}
        span["district"] = named.pop() if len(named) == 1 else None
    return spans


def _full(date, end=False):
    if len(date) == 4:
        return date + ("-12-31" if end else "-01-01")
    if len(date) == 7:
        return date + ("-28" if end else "-01")
    return date.replace("-00", "-01")


# ------------------------------------------------------------ Wikipedia

# A legislative seat the infobox names by its state alone.
_SEAT_FIELDS = (("state_house", "{} House of Representatives"), ("state_senate", "{} Senate"),
                ("state_assembly", "{} Assembly"), ("state_delegate", "{} House of Delegates"),
                ("state_legislature", "{} Legislature"))
# Fields that name an entry's office; an entry with one of its own never
# continues the office before it.
_NAMING = re.compile(r"(office|title|state|state_[a-z_]+|jr/sr)(\d*)")


def _term_office(fields, n):
    """The office an infobox entry names: its office, title or order field;
    a seat named by its state (``state_house9 = Florida``); a senator
    (``jr/sr``), or a representative (``state`` and ``district``)."""
    from .cabinet import _clean, _strip_templates

    for name in ("office", "title", "order"):
        value = _clean(_strip_templates(fields.get(f"{name}{n}", "")))
        if _tokens(value):
            return value
    for name, form in _SEAT_FIELDS:
        value = _clean(_strip_templates(fields.get(f"{name}{n}", "")))
        if value:
            return form.format(value)
    if fields.get(f"jr/sr{n}"):
        return "United States Senator"
    if fields.get(f"state{n}"):
        return "United States Representative"
    return None


def _names_own_office(fields, n):
    return any(value.strip() for key, value in fields.items()
               if (m := _NAMING.fullmatch(key)) and m.group(2) == n)


def infobox_terms(text):
    """``[{from, to, office}]`` for every term in the article's infoboxes,
    each embedded block read on its own. An entry that names no office of
    its own continues the one before it in its block, as the infobox draws
    it ("42nd and 44th Director" over two numbered terms; Chris Murphy's
    ``state_house5`` over ``term_start6``); one that names an office this
    module cannot read has none, never its neighbour's."""
    from .cabinet import infoboxes, parse_date

    out = []
    for fields in infoboxes(text or ""):
        numbers = sorted({m.group(2) for m in map(_NUMBERED.fullmatch, fields) if m},
                         key=lambda n: -1 if n == "" else int(n))
        office = None
        for n in numbers:
            own = _term_office(fields, n)
            office = own if own or _names_own_office(fields, n) else office
            start = parse_date(fields.get(f"term_start{n}", ""))
            if not start:
                continue
            end = parse_date(fields.get(f"term_end{n}", ""))
            # Acting service, as the article says it: "Acting [[...]]" or a
            # term_label (Rubio's USAID, which Wikidata records plainly).
            acting = (bool(own) and re.match(r"(?:\d+\w*\s+)?acting\b", own.strip().lower())
                      is not None) or \
                fields.get(f"term_label{n}", "").strip().lower() == "acting"
            out.append({"from": start["date"][:4], "to": end["date"][:4] if end else None,
                        "office": office, "acting": acting})
    return out


_NUMBERED = re.compile(r"(term_start|term_end|office|title|order|state|state_[a-z_]+|jr/sr)(\d*)")


def runs(terms):
    """Consecutive terms of one office as one run ("Minnesota Senate
    1996-2013" and "2013-2018" are 1996-2018): the infobox splits a span at
    a redistricting or a new district number where Wikidata need not."""
    out = []
    for term in sorted(terms, key=lambda t: t["from"]):
        if not term["office"]:
            continue
        for run in out:
            if (run["to"] is not None and same_office(run["office"], term["office"]) and
                    0 <= int(term["from"]) - int(run["to"]) <= 1):
                run["to"], run["joined"] = term["to"], True
                run["acting"] = run.get("acting") and term.get("acting")
                break
        else:
            out.append(dict(term))
    return [r for r in out if r.get("joined")]


_STOP = {"of", "the", "a", "an", "and", "for", "from", "to", "in", "at", "on", "member", "members",
         "district", "large", "office", "st", "nd", "rd", "th", "house", "acting", "former", "interim"}
_CHAMBERS = {"senate", "representative", "assembly", "delegate"}
_SYNONYMS = {"representatives": "representative", "delegates": "delegate", "senator": "senate",
             "senators": "senate", "assemblyman": "assembly", "assemblywoman": "assembly",
             "assemblymember": "assembly", "councilman": "council", "councilwoman": "council",
             "councilmember": "council", "councillor": "council", "councilor": "council",
             "commissioners": "commissioner", "supervisors": "supervisor", "justices": "justice",
             "judges": "judge", "mayors": "mayor"}
# Words that make one office another: a lieutenant governor is not a
# governor, nor a speaker a member.
_MODIFIERS = {"lieutenant", "deputy", "assistant", "vice", "associate", "speaker", "pro", "tempore",
              "majority", "minority", "leader", "whip", "president", "chair", "chairman",
              "chairwoman", "chairperson", "chief", "presiding", "under", "principal"}


# Two-word state names as one word, longest first (rule 5): "Virginia" is
# not a part of "West Virginia".
_STATE_WORDS = sorted((n.lower() for n in (
    "West Virginia", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "South Carolina", "South Dakota", "Rhode Island", "District of Columbia",
    "Puerto Rico", "American Samoa", "Northern Mariana Islands", "Virgin Islands")),
    key=len, reverse=True)


def _tokens(text):
    text = re.sub(r"\([^)]*\)", " ", (text or "").lower())
    for name in _STATE_WORDS:
        text = text.replace(name, name.replace(" ", ""))
    # "United States" is a place, and a distinguishing one: a U.S. senator
    # is not a state senator.
    text = re.sub(r"\bunited states\b|\bu\.\s?s\.", " us ", text)
    # "state senate", "state representative": the state is the place.
    text = re.sub(r"\bstate (?=senat|house|represent|assembl|legislat|delegat)", "", text)
    out = set()
    for word in re.findall(r"[a-z]+", text):
        word = _SYNONYMS.get(word, word)
        if word not in _STOP:
            out.add(word)
    return out


def same_office(a, b):
    """True when two names plausibly name one office: the words of one are
    all among the other's ("Mayor of Richmond" and "Mayor of Richmond,
    Virginia"; "member of the State Senate of Idaho" and "Idaho Senate"),
    with the same rank-changing words ("Lieutenant", "Speaker")."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb or ta & _MODIFIERS != tb & _MODIFIERS:
        return False
    # "Nebraska Legislature" names the seat by the body, whose members are
    # senators ("Nebraska State Senator"); it never stands for another
    # chamber - Nebraska's House of Representatives ended in 1937.
    if "legislature" in ta and "senate" in tb:
        ta = (ta - {"legislature"}) | {"senate"}
    elif "legislature" in tb and "senate" in ta:
        tb = (tb - {"legislature"}) | {"senate"}
    return ta <= tb or tb <= ta


def corroborate(span, terms, names):
    """``(agreement, article end, term)`` against the infobox's terms of the same
    office (by any of *names*), each term and each run of consecutive ones:

    - ``"exact"``: the same start and end years (an open span: one still
      open there);
    - ``"year-off"``: within a year of both;
    - ``"start"``: the same start, where Wikidata records no end and the
      article does - the article's end is returned, and shown as its;
    - None: nothing agrees. Years of another office corroborate nothing."""
    start = span["start"]["year"]
    end = span["end"]["year"] if span["end"] else None
    mine = [t for t in terms if t["office"] and any(same_office(n, t["office"]) for n in names if n)]
    mine += runs(mine)
    for term in mine:
        if term["from"] == start and term["to"] == end:
            return "exact", None, term
    for term in mine:
        s, e = term["from"], term["to"]
        if abs(int(s) - int(start)) <= 1 and (
                (e is None and end is None) or
                (e is not None and end is not None and abs(int(e) - int(end)) <= 1)):
            return "year-off", None, term
    if end is None:
        closed = [t for t in mine if t["from"] == start and t["to"]]
        if closed:
            last = max(closed, key=lambda t: t["to"])
            return "start", last["to"], last
    return None, None, None


def wikitexts(titles, read=None):
    from .cabinet import wikipedia_texts
    return wikipedia_texts(titles, read)


# ----------------------------------------------------------------- build

def _display(name):
    """A title as a reader says it: "Georgia (U.S. state)" is "Georgia", and
    a label's lower-case first letter ("member of the ...") is raised."""
    name = re.sub(r"\s*\([^)]*\)$", "", name or "").strip()
    return name[:1].upper() + name[1:] if name else None


def offices_for(entity, positions, reach, allowed, terms, labels, home=()):
    """``(shown, withheld)`` spans of other public offices for one person.

    *home* is the states the person is tied to otherwise (their profile's,
    their seats in Congress). A place below a state is shown only when its
    state is one of those or of the person's statewide offices: Wikidata's
    "Jefferson County Judge/Executive" is in Jefferson County, Oklahoma, and
    Mitch McConnell held it in Kentucky. The office stays; the place goes,
    and is reported (``placeWithheld``)."""
    by_position = {}
    for statement in statements(entity):
        if keep(statement, positions, reach, allowed) is None:
            by_position.setdefault(statement["position"], []).append(statement)
    shown, withheld = [], []
    for position, rows in by_position.items():
        info = positions.get(position) or {}
        names = [info.get("title"), labels.get(position)]
        where = info.get("jurisdiction")
        for span in merge(rows):
            agreement, article_end, term = corroborate(span, terms, names)
            district = span["district"] if ELECTORAL_DISTRICT in reach.get(span["district"] or "", set()) \
                else None
            name = _display(info.get("title") or labels.get(position)) or position
            entry = {
                "office": "Acting " + name if term and term.get("acting") else name,
                "item": position,
                # A federal post's place is the country, which its title says.
                "where": None if federal(position, reach, allowed) or where == USA
                else _display((positions.get(where) or {}).get("title") or labels.get(where)),
                "district": _display((positions.get(district) or {}).get("title") or labels.get(district))
                if district else None,
                "from": span["start"]["year"],
                "to": article_end or (span["end"]["year"] if span["end"] else None),
                "open": span["end"] is None and not article_end,
                "agree": agreement, "source": "wikidata", "statements": span["ids"],
                "_state": (positions.get(where) or {}).get("state"),
                "_statewide": (positions.get(where) or {}).get("statewide", False),
            }
            (shown if agreement else withheld).append(entry)
    states = set(home) | {e.get("_state") for e in shown if e.get("_statewide")}
    for entry in shown + withheld:
        entry.pop("_statewide", None)
        state = entry.pop("_state", None)
        if entry["where"] and state is not None and state not in states:
            entry["placeWithheld"], entry["where"] = entry["where"], None
        elif entry["where"] and state is None and not federal(entry["item"], reach, allowed):
            # A place in no state Wikidata names cannot be checked.
            entry["placeWithheld"], entry["where"] = entry["where"], None
    shown.sort(key=lambda e: e["from"], reverse=True)
    return shown, withheld


def for_page(person, as_of=None, seated=False):
    """What the page draws for one person: Congress and every other office
    as one list, newest first, with the ids it links (rule 32).

    A seat in Congress is current only while its term runs past *as_of* -
    the membership snapshot's date - and the person is *seated* in it: a
    read made in October would otherwise go on saying "since 1985" of a
    senator who left on January 3."""
    from .pages import state_name

    rows = []
    for span in person.get("congress") or []:
        current = span["current"]
        if as_of and span.get("end"):
            current = bool(seated) and span["end"] > as_of
        # The state by name: the officials' page loads no state table.
        rows.append({"office": span["office"], "where": state_name(span["state"]),
                     "district": span["district"],
                     "from": span["from"], "to": None if current else (span.get("end") or "")[:4] or span["to"],
                     "terms": span["terms"], "current": current, "congress": True})
    for office in person.get("offices") or []:
        rows.append({"office": office["office"], "where": office["where"],
                     "district": office["district"], "from": office["from"], "to": office["to"],
                     "current": office["open"],
                     # Only a difference is said: "exact" is the rule.
                     "agree": office["agree"] if office["agree"] != "exact" else None})
    rows.sort(key=lambda r: (r["from"], r["to"] or "9999"), reverse=True)
    # An at-large district is 0, which is not an absence (0 == False).
    return {k: v for k, v in {
        "wikidata": person.get("wikidata"), "wikipedia": person.get("wikipedia"),
        "rows": [{k: v for k, v in row.items() if v is not None and v is not False}
                 for row in rows],
        "withheld": len(person.get("withheld") or []) or None,
    }.items() if v is not None}


def stale(profiles, cache):
    """``[(profile, detail)]``: people whose history was read from an article
    their profile no longer links. A challenger's item is the one their
    election page's article belongs to (rule 33); when the page links
    another article, the cached offices may be someone else's (rule 20)."""
    people = (cache or {}).get("people") or {}
    out = []
    for profile in profiles:
        found = people.get(profile["id"])
        if found and found.get("asked") and found["asked"] != profile.get("wikipedia"):
            out.append((profile, f"{profile['id']} ({profile['name']}): read from "
                                 f"{found['asked']}, the profile now links "
                                 f"{profile.get('wikipedia') or 'no article'}"))
    return out


def membership(snapshot):
    """``(as of, {bioguide})`` from the membership snapshot: the day it was
    read and who sits."""
    if not snapshot:
        return None, set()
    return ((snapshot.get("fetched") or "")[:10] or None,
            {m.get("bioguide") for m in snapshot.get("legislators") or [] if m.get("bioguide")})


def apply_cache(profiles, cache, snapshot=None):
    """Attach ``politicalHistory`` to each profile the cache knows, by id,
    unless it was read from an article the profile no longer links. What
    is current in Congress is the snapshot's to say: whether the person -
    by the bioguide id their seats were read under, whichever profile shows
    them - sits now."""
    as_of, sitting = membership(snapshot)
    people = (cache or {}).get("people") or {}
    refused = {id(p) for p, _detail in stale(profiles, cache)}
    attached = 0
    for profile in profiles:
        found = people.get(profile["id"])
        if found and id(profile) not in refused:
            profile["politicalHistory"] = for_page(
                found, as_of, not profile.get("formerMember") and found.get("bioguide") in sitting)
            attached += 1
    return attached


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=None, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def problems(cache, profiles=None):
    """What a build says about the cache: ``[(level, code, message, detail)]``."""
    if not cache:
        return []
    out = []
    people = cache.get("people") or {}
    # Every member's id is congress-legislators' own, which records each
    # member's Wikidata item: one with no record was not read.
    unread = [f"{p['id']} ({p['name']})" for p in profiles or []
              if not p.get("isCandidate") and p["id"] not in people]
    if unread:
        out.append(("warn", "history-missing",
                    f"{len(unread)} members have no record of offices held; run 'history'", unread))
    from .record import seated

    # A seated member whose record holds no current seat was read before
    # their present term began: the January 3 case.
    behind = [f"{p['id']} ({p['name']})" for p in profiles or []
              if seated(p) and p.get("politicalHistory") and not any(
                  r.get("congress") and r.get("current") for r in p["politicalHistory"].get("rows", []))]
    if behind:
        out.append(("warn", "history-behind",
                    f"{len(behind)} sitting members' records hold no current seat in Congress: "
                    "they were read before this term; run 'history'", behind))
    placed = [f"{key}: {w['office']} - {w['placeWithheld']}"
              for key, person in people.items() for w in person.get("offices") or []
              if w.get("placeWithheld")]
    if placed:
        out.append(("warn", "history-place",
                    f"{len(placed)} offices are shown without their place: Wikidata puts it in a "
                    "state the person is not otherwise tied to", placed))
    moved = [detail for _p, detail in stale(profiles or [], cache)]
    if moved:
        out.append(("warn", "history-stale",
                    f"{len(moved)} people's offices are not shown: they were read from an "
                    f"article their profile no longer links; run 'history'", moved))
    withheld = [f"{key}: {w['office']} {w['from']}-{w['to'] or ''}"
                for key, person in (cache.get("people") or {}).items()
                for w in person.get("withheld") or []]
    if withheld:
        out.append(("warn", "history-withheld",
                    f"{len(withheld)} offices from Wikidata are not shown: the person's own "
                    f"Wikipedia infobox does not give the same office the same years", withheld))
    if cache.get("unresolved"):
        out.append(("warn", "history-unresolved",
                    f"{len(cache['unresolved'])} articles an election page links resolved to no "
                    f"person's Wikidata item", cache["unresolved"]))
    return out


# ----------------------------------------------------------------- fetch

def resolve_titles(wanted, read=None, wiki_read=None):
    """``({key: qid}, unresolved)`` for ``{key: (title, name)}``: each
    article's own Wikidata item - the sitelink first, which honours a
    sitelink to a redirect, then an enwiki redirect - kept only when it is a
    person and the title it resolves to carries the person's surname
    (portraits.title_is_about, rule 33)."""
    from .portraits import article_is_theirs

    read = read or _get
    wiki_read = wiki_read or read
    out, unresolved = {}, []
    titles = sorted({title for title, _name in wanted.values()})
    found = {}
    for i in range(0, len(titles), BATCH):
        params = {"action": "wbgetentities", "sites": "enwiki", "titles": "|".join(titles[i:i + BATCH]),
                  "props": "claims|sitelinks", "sitefilter": "enwiki", "format": "json"}
        data = read(f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}")
        for qid, entity in (data.get("entities") or {}).items():
            if "missing" in entity:
                continue
            title = sitelink(entity)
            if title:
                found[title] = (qid, entity, title)
        if read is _get:
            time.sleep(PAUSE)
    missing = [t for t in titles if t not in found]
    for i in range(0, len(missing), BATCH):
        params = {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                  "titles": "|".join(missing[i:i + BATCH]), "redirects": 1, "format": "json",
                  "formatversion": 2}
        data = wiki_read(f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}")
        query = data.get("query") or {}
        normal = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redirect = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages = {p["title"]: (p.get("pageprops") or {}).get("wikibase_item")
                 for p in query.get("pages", [])}
        qids = {}
        for title in missing[i:i + BATCH]:
            name = normal.get(title, title)
            to = redirect.get(name, name)
            if pages.get(to):
                qids[title] = (pages[to], to)
        fetched = entities([q for q, _t in qids.values()], read)
        for title, (qid, to) in qids.items():
            if qid in fetched:
                found[title] = (qid, fetched[qid], to)
    for key, (title, name) in sorted(wanted.items()):
        hit = found.get(title)
        if not hit:
            unresolved.append(f"{key}: {title}")
            continue
        qid, entity, resolved = hit
        human = any(_item(c.get("mainsnak")) == HUMAN for c in _claims(entity, "P31"))
        if not human or not article_is_theirs(resolved, {"id": key, "name": name}):
            unresolved.append(f"{key}: {title} -> {resolved} ({qid}) is not this person")
            continue
        out[key] = qid
    return out, unresolved


def _title(entity):
    """An item's article title, unless the article is a list: "Governor of
    Colorado" sitelinks to "List of governors of Colorado"."""
    title = sitelink(entity)
    return None if (title or "").startswith("List of") else title


def _place_states(items, read=None):
    """``{place: (state code, statewide)}``: the U.S. state (or D.C., or a
    territory) each place lies in, by "located in" (P131), and whether the
    place is that state itself."""
    from .normalize import US_STATES

    read = read or _get
    codes = {name.lower(): code for name, code in US_STATES.items()}
    out = {}
    items = sorted(set(i for i in items if i))
    for i in range(0, len(items), 150):
        query = ("SELECT ?item ?state ?label WHERE { VALUES ?item {%s} "
                 "VALUES ?kind { wd:Q35657 wd:Q1352230 wd:Q3551781 } "
                 "?item wdt:P131* ?state . ?state wdt:P31 ?kind . "
                 "?state rdfs:label ?label . FILTER(LANG(?label) = 'en') }") % (
            " ".join("wd:" + q for q in items[i:i + 150]))
        data = _results(read(SPARQL_URL, urllib.parse.urlencode({"query": query, "format": "json"}).encode()))
        found = {}
        for row in data:
            item = row["item"]["value"].rsplit("/", 1)[1]
            state = row["state"]["value"].rsplit("/", 1)[1]
            code = codes.get(row["label"]["value"].lower())
            if code:
                found.setdefault(item, set()).add((code, state == item))
        # A place in two states (a border town's item gone wrong) is in none.
        for item, rows in found.items():
            if len({code for code, _own in rows}) == 1:
                out[item] = (next(iter(rows))[0], any(own for _code, own in rows))
        if read is _get:
            time.sleep(PAUSE)
    return out


def _us_places(items, read=None):
    """The items among *items* whose country (P17) is the United States."""
    read = read or _get
    out = set()
    items = sorted(set(i for i in items if i))
    for i in range(0, len(items), 150):
        query = "SELECT ?item WHERE { VALUES ?item {%s} ?item wdt:P17 wd:Q30 . }" % (
            " ".join("wd:" + q for q in items[i:i + 150]))
        data = _results(read(SPARQL_URL, urllib.parse.urlencode({"query": query, "format": "json"}).encode()))
        out |= {row["item"]["value"].rsplit("/", 1)[1] for row in data}
    return out


def fetch(profiles, executive=None, read=None, wiki_read=None, today=None):
    """The whole cache; :class:`HistoryError` when a source cannot be read."""
    from .federal_build import slug
    from .legislators import HISTORICAL_URL, SOURCE_URL

    read = read or _get
    wiki_read = wiki_read or read
    today = today or datetime.date.today().isoformat()
    roster = read(SOURCE_URL) + read(HISTORICAL_URL)
    by_bioguide = {p["id"]["bioguide"]: p for p in roster if p.get("id", {}).get("bioguide")}
    by_wikidata = {p["id"]["wikidata"]: p for p in roster if p.get("id", {}).get("wikidata")}

    # Each person's item, by an id: congress-legislators' for a member; the
    # article an election page links for a challenger; the executive cache's
    # ids for the President, the Vice President and the Cabinet.
    qids, wanted = {}, {}
    by_profile = {p["id"]: p for p in profiles}
    for profile in profiles:
        member = None if profile.get("isCandidate") else by_bioguide.get(profile["id"])
        if member and member["id"].get("wikidata"):
            qids[profile["id"]] = member["id"]["wikidata"]
        elif profile.get("wikipediaVia") == "election-page" and profile.get("wikipedia"):
            wanted[profile["id"]] = (profile["wikipedia"], profile["name"])
    if executive:
        for key in ("president", "vicePresident"):
            person = executive.get(key) or {}
            if (person.get("ids") or {}).get("wikidata"):
                qids[slug(person["name"])] = person["ids"]["wikidata"]
        for office in ((executive.get("changes") or {}).get("offices") or {}).values():
            for row in office.get("holders") or []:
                if row.get("current") and row.get("wikidata"):
                    qids[slug(row["name"])] = row["wikidata"]
    resolved, unresolved = resolve_titles(wanted, read, wiki_read)
    qids.update(resolved)

    people = entities(qids.values(), read)
    position_ids = {s["position"] for e in people.values() for s in statements(e)}
    positions = entities(position_ids, read, props="claims|labels|sitelinks")
    info, labels, places, districts = {}, {}, set(), set()
    # A post with no place of its own takes the place of the body it
    # directs: the Speaker of the Florida House directs the Florida House.
    bodies = {qid: next((_item(c.get("mainsnak")) for c in _claims(e, "P2389")), None)
              for qid, e in positions.items() if not _claims(e, "P1001")}
    directed = entities({b for b in bodies.values() if b}, read, props="claims")
    for qid, entity in positions.items():
        labels[qid] = ((entity.get("labels") or {}).get("en") or {}).get("value")
        jurisdiction = next((_item(c.get("mainsnak")) for c in _claims(entity, "P1001")), None)
        if not jurisdiction and bodies.get(qid) in directed:
            jurisdiction = next((_item(c.get("mainsnak"))
                                 for c in _claims(directed[bodies[qid]], "P1001")), None)
        info[qid] = {"title": _title(entity), "jurisdiction": jurisdiction,
                     "superclasses": [_item(c.get("mainsnak")) for c in _claims(entity, "P279")]}
        if jurisdiction:
            places.add(jurisdiction)
    for entity in people.values():
        districts |= {s["district"] for s in statements(entity) if s["district"]}
    extra = entities(places | districts, read, props="labels|sitelinks")
    us = _us_places(places, read)
    in_state = _place_states(places & us, read)
    for qid, entity in extra.items():
        info.setdefault(qid, {})
        info[qid].update(title=info[qid].get("title") or _title(entity), us=qid in us,
                         state=in_state.get(qid, (None, False))[0],
                         statewide=in_state.get(qid, (None, False))[1])
        labels[qid] = ((entity.get("labels") or {}).get("en") or {}).get("value")
    reach = classes(position_ids | places | districts, read)

    texts = wikitexts([sitelink(e) for e in people.values()], wiki_read)
    allowed = federal_items()
    out = {}
    for key, qid in sorted(qids.items()):
        entity = people.get(qid)
        if entity is None:
            unresolved.append(f"{key}: {qid} is not on Wikidata")
            continue
        title = sitelink(entity)
        member = by_bioguide.get(key) or by_wikidata.get(qid)
        home = {t["state"] for t in (member or {}).get("terms") or []}
        if by_profile.get(key, {}).get("state"):
            home.add(by_profile[key]["state"])
        shown, withheld = offices_for(entity, info, reach, allowed,
                                      infobox_terms(texts.get(title) or ""), labels, home)
        out[key] = {
            "wikidata": qid, "wikipedia": title,
            "congress": congress_spans(member["terms"], today) if member else [],
            "offices": shown, "withheld": withheld,
            "revision": entity.get("lastrevid"),
        }
        if member:
            # Whose seats these are: a member's candidacy profile (Ashley
            # Hinson's for the Senate) sits in the House all the same.
            out[key]["bioguide"] = member["id"]["bioguide"]
        if key in wanted:
            # The article the item was found through: the build attaches the
            # offices only while the profile links the same one.
            out[key]["asked"] = wanted[key][0]
    return {
        "read": today,
        "sources": {"congress": SOURCE_URL, "congressHistorical": HISTORICAL_URL,
                    "wikidata": "https://www.wikidata.org/", "wikipedia": "https://en.wikipedia.org/"},
        "people": out,
        "unresolved": sorted(unresolved),
    }
