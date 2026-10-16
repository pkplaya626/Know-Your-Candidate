"""Who has held each Cabinet office since the President's term began: who
was confirmed, who left, who served in between.

Three sources, each for what it can say:

- **Confirmed**: the Senate's own roll calls (kyc/federal.py reads the vote
  menus), matched to the office on the Senate's wording of it. The date and
  the tally are the Senate's; so is the name of everyone it confirmed.
- **Who held the office**: Wikidata's "position held" (P39) statements on
  the office's own item, people only (P31 = human), dated. Joined to a
  confirmation by the office and the surname within this term; the
  holder's name is then the Senate's. A holder with no confirmation for the
  office (an acting officer) is named by their Wikipedia article's title,
  the item's own sitelink - never by a Wikidata label, which anyone can
  change and which has been vandalised on officials' items.
- **When**: in office from and to are shown only to the precision on which
  Wikidata and the person's own Wikipedia infobox agree - the day, the
  month, or the year. Wikidata has given Pete Hegseth's start as 2025-09-05
  (the infobox, January 25, 2025, the day after his confirmation) and Jay
  Clayton's as the day of his confirmation; where the two agree on nothing,
  the page says the sources differ and shows no date.

A partial list is said to be one: an acting officer Wikidata does not
record is not listed, and the page names its sources. A read that fails
keeps the last history (rule 8).
"""

import datetime
import html
import json
import re
import time
import urllib.parse
import urllib.request

from . import federal_offices

SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "KnowYourCandidate/1.0 (https://github.com/pkplaya626/Know-Your-Candidate; civic data)"
PAUSE = 1.0


class CabinetError(RuntimeError):
    """A source could not be read, or is not what the pipeline knows."""


def _get(url, data=None, timeout=60):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/sparql-results+json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (OSError, ValueError) as exc:
        raise CabinetError(f"could not read {url.split('?')[0]}: {exc}") from exc


def sparql(query, read=None):
    read = read or _get
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    return read(SPARQL_URL, data)["results"]["bindings"]


# ------------------------------------------------------------- Wikidata

_HOLDERS = """SELECT ?office ?officeTitle ?person ?title ?start ?startPrec ?end ?endPrec WHERE {
  VALUES ?office { %s }
  ?person p:P39 ?st . ?st ps:P39 ?office ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?person wdt:P31 wd:Q5 .
  ?st pqv:P580 ?sv . ?sv wikibase:timeValue ?start ; wikibase:timePrecision ?startPrec .
  OPTIONAL { ?st pqv:P582 ?ev . ?ev wikibase:timeValue ?end ; wikibase:timePrecision ?endPrec }
  OPTIONAL { ?title schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?officeTitle schema:about ?office ; schema:isPartOf <https://en.wikipedia.org/> }
  FILTER(!BOUND(?end) || ?end > "%sT00:00:00Z"^^xsd:dateTime)
}"""

_PRECISION = {"11": "day", "10": "month", "9": "year"}


def _when(value, precision):
    """A Wikidata time as ``{date, precision}``: ``"2025-02-05"``, day."""
    if not value:
        return None
    kind = _PRECISION.get(str(precision))
    if kind is None:
        return None
    day = value[:10]
    return {"date": day if kind == "day" else day[:7] if kind == "month" else day[:4],
            "precision": kind}


def _title(url):
    return urllib.parse.unquote(url.rsplit("/", 1)[1]).replace("_", " ") if url else None


def wikidata_holders(items, since, read=None):
    """``{office item: {"title": article, "holders": {person: {...}}}}``:
    everyone Wikidata records in each office, dated, since *since*. A
    person's several statements for one office become one span: the
    earliest start, and the latest end unless one is open."""
    values = " ".join("wd:" + q for q in items)
    out = {}
    for row in sparql(_HOLDERS % (values, since), read):
        office = row["office"]["value"].rsplit("/", 1)[1]
        person = row["person"]["value"].rsplit("/", 1)[1]
        slot = out.setdefault(office, {"title": _title((row.get("officeTitle") or {}).get("value")),
                                       "holders": {}})
        start = _when(row["start"]["value"], row["startPrec"]["value"])
        end = _when((row.get("end") or {}).get("value"), (row.get("endPrec") or {}).get("value"))
        if start is None:
            continue
        held = slot["holders"].setdefault(person, {
            "wikidata": person, "title": _title((row.get("title") or {}).get("value")),
            "start": start, "end": end, "open": end is None})
        if start["date"] < held["start"]["date"]:
            held["start"] = start
        if end is None:
            held["open"], held["end"] = True, None
        elif not held["open"] and (held["end"] is None or end["date"] > held["end"]["date"]):
            held["end"] = end
    return out


# ------------------------------------------------------------ Wikipedia

_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june",
                                       "july", "august", "september", "october", "november",
                                       "december"], 1)}


def _clean(value):
    """An infobox value without references, notes, comments or markup."""
    value = re.sub(r"<!--.*?-->", "", value, flags=re.S)
    value = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", value, flags=re.S)
    value = re.sub(r"\{\{\s*efn[^{}]*\}\}", "", value, flags=re.I)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", value)
    return " ".join(html.unescape(value).replace("'''", "").replace("''", "").split())


def parse_date(value):
    """An infobox date as ``{date, precision}``: "February 5, 2025",
    "June 2025", "2025", or {{start date|2025|2|5}}; None otherwise."""
    value = _clean(value or "")
    template = re.search(r"\{\{\s*(?:start|end) date(?: and age)?\s*\|\s*(\d{4})"
                         r"(?:\s*\|\s*(\d{1,2}))?(?:\s*\|\s*(\d{1,2}))?", value, re.I)
    if template:
        y, m, d = template.groups()
        if d:
            return {"date": f"{y}-{int(m):02d}-{int(d):02d}", "precision": "day"}
        if m:
            return {"date": f"{y}-{int(m):02d}", "precision": "month"}
        return {"date": y, "precision": "year"}
    value = re.sub(r"\{\{.*?\}\}", "", value)
    match = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b", value)
    if match and match.group(1).lower() in _MONTHS:
        return {"date": f"{match.group(3)}-{_MONTHS[match.group(1).lower()]:02d}-"
                        f"{int(match.group(2)):02d}", "precision": "day"}
    match = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", value)
    if match and match.group(2).lower() in _MONTHS:
        return {"date": f"{match.group(3)}-{_MONTHS[match.group(2).lower()]:02d}-"
                        f"{int(match.group(1)):02d}", "precision": "day"}
    match = re.match(r"^([A-Za-z]+)\s+(\d{4})\b", value)
    if match and match.group(1).lower() in _MONTHS:
        return {"date": f"{match.group(2)}-{_MONTHS[match.group(1).lower()]:02d}",
                "precision": "month"}
    match = re.match(r"^(\d{4})\b", value)
    return {"date": match.group(1), "precision": "year"} if match else None


_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _template_end(text, start):
    """The index just past the template that opens at *start*."""
    depth, i = 0, start
    while i < len(text):
        if text.startswith("{{", i):
            depth, i = depth + 1, i + 2
        elif text.startswith("}}", i):
            depth, i = depth - 1, i + 2
            if depth == 0:
                return i
        else:
            i += 1
    return len(text)


def infoboxes(text):
    """``[{field: value}]``: the article's first infobox, then each infobox
    embedded in it, each block on its own. A long career keeps its earlier
    offices in ``{{Infobox officeholder | embed = yes ...}}`` blocks inside
    collapsed sections (Marco Rubio's Florida House seat), and each block
    numbers its fields afresh, so Jeanne Shaheen's ``office5`` (a committee)
    and ``state_senate5`` are different entries. An article may write
    ``{{infobox officeholder`` (Donald Trump's). A comment is not the page's
    text, and may hold a field the editors switched off."""
    text = _COMMENT.sub("", text or "")
    start = text.lower().find("{{infobox")
    if start < 0:
        return []
    body = text[start + 2:_template_end(text, start) - 2]
    blocks = [_fields(body)]
    lower = body.lower()
    at = lower.find("{{infobox")
    while at >= 0:
        stop = _template_end(body, at)
        blocks.append(_fields(body[at + 2:stop - 2]))
        at = lower.find("{{infobox", stop)
    return blocks


def infobox(text):
    """The first infobox's own ``{field: value}``, or {}."""
    return (infoboxes(text) or [{}])[0]


def _fields(body):
    """``{field: value}`` of one template's body, split on its own pipes."""
    fields, depth, current, key = {}, 0, "", None
    for chunk in re.split(r"(\{\{|\}\}|\[\[|\]\]|\|)", body):
        if chunk in ("{{", "[["):
            depth += 1
        elif chunk in ("}}", "]]"):
            depth -= 1
        if chunk == "|" and depth == 0:
            if key is not None:
                fields[key] = current.strip()
            key, current = None, ""
            continue
        if key is None and "=" in chunk and depth == 0:
            name, _, rest = chunk.partition("=")
            key, current = name.strip().lower(), rest
            continue
        current += chunk
    if key is not None:
        fields[key] = current.strip()
    return fields


_ORDINALS = re.compile(r"^(?:\d+(?:st|nd|rd|th)(?:\s*(?:,|and|&)\s*\d+(?:st|nd|rd|th))*\s+)")


def _strip_templates(value):
    """Every template removed, the innermost first: a footnote can hold
    links and templates of its own ("{{efn|Also known as ... {{lang|...}}}}"),
    and one non-greedy pass leaves half of it behind."""
    previous = None
    while previous != value:
        previous, value = value, re.sub(r"\{\{[^{}]*\}\}", "", value)
    return value


def _office_text(value):
    """``(name, acting)`` of an infobox office field: "87th [[United States
    Attorney General]]" -> ("united states attorney general", False);
    "Acting [[United States Secretary of Energy]]" -> (..., True)."""
    text = _clean(_strip_templates(value)).lower()
    text = _ORDINALS.sub("", text)
    acting = text.startswith("acting ")
    return (text[7:] if acting else text).strip(), acting


def office_terms(fields, names):
    """The infobox's entries for the office: ``[{start, end, acting,
    actingNote}]``. An entry is an office (or order) field that is exactly
    one of the office's *names*, past an ordinal and "Acting" - never one
    that merely contains it ("Deputy Director of the Office of Management
    and Budget" is not its Director) - with the term fields of its number."""
    wanted = {_clean(n).lower() for n in names if n}
    out, seen = [], set()
    for name, value in fields.items():
        match = re.fullmatch(r"(office|order)(\d*)", name)
        if not match or not wanted:
            continue
        text, acting = _office_text(value)
        if text not in wanted:
            continue
        n = match.group(2)
        if n in seen:
            continue            # "order" and "office" of one entry both name it
        seen.add(n)
        start_raw = fields.get(f"term_start{n}", "")
        note = re.search(r"\{\{\s*efn\s*\|\s*(Acting:[^{}]*)\}\}", start_raw, re.I)
        marks = {_clean(fields.get(f"{label}{n}", "")).lower() for label in ("status", "term_label")}
        acting_note = _clean(note.group(1)) if note else None
        out.append({
            "start": parse_date(start_raw), "end": parse_date(fields.get(f"term_end{n}", "")),
            "acting": acting or "acting" in marks,
            "actingNote": acting_note,
            # "Acting: April 2, 2026 - August 10, 2026": when the acting
            # service began, the note's own first date.
            "actingStart": parse_date(acting_note.split(":", 1)[1]) if acting_note else None,
        })
    return out


def wikipedia_texts(titles, read=None):
    """``{title: wikitext}`` for each article, following redirects."""
    read = read or _get
    out = {}
    titles = sorted(set(t for t in titles if t))
    for i in range(0, len(titles), 50):
        query = urllib.parse.urlencode({
            "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "titles": "|".join(titles[i:i + 50]), "redirects": 1, "format": "json",
            "formatversion": 2})
        data = read(f"{WIKIPEDIA_API}?{query}")
        query_part = data.get("query") or {}
        # The API reports each title it normalised and each redirect it
        # followed; the text is keyed back to the title asked for.
        normal = {n["to"]: n["from"] for n in query_part.get("normalized", [])}
        back = {r["to"]: normal.get(r["from"], r["from"]) for r in query_part.get("redirects", [])}
        back.update({k: v for k, v in normal.items() if k not in back})
        for page in (data.get("query") or {}).get("pages", []):
            revisions = page.get("revisions") or []
            if revisions:
                out[back.get(page["title"], page["title"])] = \
                    revisions[0]["slots"]["main"]["content"]
    return out


# --------------------------------------------------------- agreement

def agree(a, b):
    """The date both sources give, at the finest precision on which they
    agree: ``{date, precision}`` or None."""
    if not a or not b:
        return None
    for precision, size in (("day", 10), ("month", 7), ("year", 4)):
        if len(a["date"]) >= size and len(b["date"]) >= size and a["date"][:size] == b["date"][:size]:
            return {"date": a["date"][:size], "precision": precision}
    return None


def _held_from(person, vote_date, slack_days=7):
    """True when the holder still held the office on or after the vote that
    would have confirmed them: someone acting before a confirmation is the
    nominee only if they served on past it (Keith Sonderling, acting from
    April and confirmed in September); an acting officer who left before the
    vote is never handed the nominee's confirmation. A week's slack for a
    date recorded a day off."""
    end = person.get("end")
    if person.get("open") or not end:
        return True
    last = end["date"] + ("-12-31" if len(end["date"]) == 4 else
                          "-28" if len(end["date"]) == 7 else "")
    vote = datetime.date.fromisoformat(vote_date)
    return datetime.date.fromisoformat(last) >= vote - datetime.timedelta(days=slack_days)


def _surname(name):
    from .federal import _words
    words = _words(name or "")
    return words[-1] if words else ""


def reading_title(title):
    """An article title as a name: "Doug Collins (politician)" -> "Doug
    Collins"."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title or "").strip()


# ---------------------------------------------------------------- build

def build(executive, votes, holders, texts):
    """``{office key: {"holders": [...], "problems": [...]}}`` from the
    executive cache, the Senate's votes, Wikidata's holders and the
    holders' articles. Pure: every read happens in :func:`fetch`."""
    from .federal import _CONFIRMATION, VOTE_URL

    since = executive["president"]["termStart"]
    out = {}
    for office in federal_offices.OFFICES:
        item = office.get("wikidata")
        slot = holders.get(item) or {"title": None, "holders": {}}
        current = next((o.get("holder") for o in executive["offices"]
                        if o["key"] == office["key"]), None)
        confirmations = []
        for vote in votes or []:
            if vote["question"] != "On the Nomination" or vote["result"] != "Confirmed":
                continue
            match = _CONFIRMATION.match(vote["title"])
            if match and match.group(2) in office["senate"] and vote["date"] >= since:
                confirmations.append({
                    "nominee": match.group(1), "date": vote["date"],
                    "yeas": int(vote["yeas"] or 0), "nays": int(vote["nays"] or 0),
                    "vote": f"{vote['congress']}-{vote['session']}-{int(vote['number'])}",
                    "url": VOTE_URL.format(congress=vote["congress"], session=vote["session"],
                                           number=vote["number"])})
        rows, problems, used = [], [], set()
        ordered = sorted(slot["holders"].values(), key=lambda h: h["start"]["date"])
        surnames = [_surname(reading_title(p["title"])) for p in ordered]
        for person in ordered:
            surname = _surname(reading_title(person["title"]))
            mine = [c for c in confirmations if _surname(c["nominee"]) == surname
                    and id(c) not in used and _held_from(person, c["date"])]
            if surnames.count(surname) > 1 and mine:
                problems.append(f"{person['title']}: two holders of one surname; their "
                                f"confirmation is not attached to either")
                mine = []
            if len(mine) > 1:
                problems.append(f"{person['title']}: {len(mine)} confirmations of one surname")
                mine = []
            used.update(id(c) for c in mine)
            names = [slot["title"], office["office"], *office["titles"]]
            terms = [term for fields in infoboxes(texts.get(person["title"]) or "")
                     for term in office_terms(fields, names)]
            # A person who held the office before, in another term: the
            # entry for this one is the one still open or ending after it
            # began.
            if len(terms) > 1:
                terms = [m for m in terms if m["end"] is None or m["end"]["date"] >= since[:len(m["end"]["date"])]]
            term = terms[0] if len(terms) == 1 else None
            if len(terms) > 1:
                problems.append(f"{person['title']}: the infobox lists this office {len(terms)} times")
            rows.append({
                "wikidata": person["wikidata"], "wikipedia": person["title"],
                # The common name: the article's title, the item's own
                # sitelink. The Senate's legal name rides with the
                # confirmation ("Walter Clayton" is Jay Clayton).
                "name": reading_title(person["title"]) if person["title"]
                        else (mine[0]["nominee"] if mine else None),
                "nameFrom": "wikipedia" if person["title"] else "senate",
                "confirmed": mine[0] if mine else None,
                "acting": bool(term and term["acting"]) or None,
                "actingNote": term["actingNote"] if term else None,
                "actingStart": term["actingStart"] if term else None,
                "start": {"wikidata": person["start"], "wikipedia": term and term["start"],
                          "shown": agree(person["start"], term and term["start"])},
                "end": None if person["open"] else {
                    "wikidata": person["end"], "wikipedia": term and term["end"],
                    "shown": agree(person["end"], term and term["end"])},
                "infobox": term is not None,
            })
        # Someone the Senate confirmed whom Wikidata does not record in the
        # office: listed from the Senate's record alone.
        for c in confirmations:
            if id(c) not in used:
                rows.append({"wikidata": None, "wikipedia": None, "name": c["nominee"],
                             "nameFrom": "senate", "confirmed": c, "acting": None,
                             "actingNote": None, "start": None, "end": None, "infobox": False})
                problems.append(f"{c['nominee']}: confirmed {c['date']}, not in Wikidata's holders")
        rows.sort(key=lambda r: ((r["start"] or {}).get("wikidata") or {}).get("date")
                  or (r["confirmed"] or {}).get("date") or "")
        # The holder the White House lists is the open one, by surname.
        open_rows = [r for r in rows if r["end"] is None and r["start"] is not None]
        if current and open_rows and _surname(open_rows[-1]["name"]) != _surname(current["name"]):
            problems.append(f"Wikidata's open holder is {open_rows[-1]['name']}, the White "
                            f"House lists {current['name']}")
        for row in rows:
            row["current"] = bool(current) and row["end"] is None and row["start"] is not None \
                and _surname(row["name"]) == _surname(current["name"])
            if row["current"]:
                row["name"], row["nameFrom"] = current["name"], "white-house"
        out[office["key"]] = {"office": office["office"], "wikidata": item,
                              "article": slot["title"], "holders": rows, "problems": problems}
    return out


def fetch(executive, votes, read=None, wiki_read=None):
    """The history for every office, read from Wikidata and Wikipedia."""
    since = executive["president"]["termStart"]
    items = [o["wikidata"] for o in federal_offices.OFFICES if o.get("wikidata")]
    holders = wikidata_holders(items, since, read)
    titles = [h["title"] for slot in holders.values() for h in slot["holders"].values()]
    time.sleep(PAUSE if read is None else 0)
    texts = wikipedia_texts(titles, wiki_read or read)
    return {
        "since": since,
        "read": datetime.date.today().isoformat(),
        "sources": {"wikidata": "https://www.wikidata.org/", "wikipedia": "https://en.wikipedia.org/",
                    "senate": "https://www.senate.gov/legislative/votes_new.htm"},
        "offices": build(executive, votes, holders, texts),
    }
