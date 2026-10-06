"""Every state's governor, from the National Governors Association.

``python build_profile_site.py executives`` reads the NGA's roster of current
governors (https://www.nga.org/governors/) and each governor's NGA page, and
writes ``data/executives.json``: name, party, terms, birth date, the office's
address and phone, the governor's official website and NGA headshot.

Only the labelled facts are kept. The NGA page's "About" text is written by
each governor's office and reads as advocacy; a non-partisan site does not
republish it.

The roster is cross-checked against Wikidata's record of who holds each
state's governorship. Wikidata is a lead, not a source (rule 50): it lacks
some governors entirely, so a missing record is no finding, but a different
name is reported for a person to settle.
"""

import datetime
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

ROSTER_URL = "https://www.nga.org/governors/"
SOURCE = "National Governors Association, current governors"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "executives.json")
USER_AGENT = ("Mozilla/5.0 (compatible; know-your-candidate/1.0; "
              "+https://github.com/pkplaya626/Know-Your-Candidate)")
WIKIDATA_URL = "https://query.wikidata.org/sparql"


class ExecutivesError(RuntimeError):
    """The roster could not be read, or is not what the pipeline expects."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise ExecutivesError(f"could not fetch {url}: {exc}") from exc


def _text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# ------------------------------------------------------------------ roster

_ITEM = re.compile(
    r'<a\s+href="(https://www\.nga\.org/governors/[^"]+)"[^>]*>.*?'
    r'<img[^>]*src="([^"]+)"[^>]*>.*?<small class="state">([^<]+)</small>\s*'
    r'Gov\.\s*([^<]+?)\s*</div>', re.S)


def parse_roster(page):
    """``[{state, name, profile, headshot}]`` from the roster page. Only the
    list items are read: the page's own links come before them."""
    from .normalize import US_STATES
    by_name = {name.title(): code for name, code in US_STATES.items()}
    by_name.update({"U.S. Virgin Islands": "VI", "Northern Mariana Islands": "MP",
                    "American Samoa": "AS", "Puerto Rico": "PR", "Guam": "GU"})
    out = []
    items = re.split(r'<li class="current-governors__item">', page)[1:]
    found = [m.groups() for m in (_ITEM.search(item.split("</li>")[0]) for item in items) if m]
    if len(found) != len(items):
        raise ExecutivesError(f"read {len(found)} of the roster's {len(items)} entries")
    for profile, headshot, state, name in found:
        state = _text(state)
        code = by_name.get(state) or by_name.get(state.title())
        if not code:
            raise ExecutivesError(f"the roster names a jurisdiction the site does not know: {state!r}")
        out.append({"state": code, "name": _text(name), "profile": profile,
                    "headshot": headshot if headshot.startswith("https://") else ""})
    if len({r["state"] for r in out}) != len(out):
        raise ExecutivesError("the roster lists a jurisdiction twice")
    return out


_FIELD = re.compile(r'<label class="label">([^<]+)</label>(.*?)</li>', re.S)


def parse_profile(page):
    """The labelled facts on a governor's NGA page."""
    facts = {}
    for label, value in _FIELD.findall(page):
        facts[_text(label)] = value
    out = {}
    terms = [t.strip() for t in re.split(r"<br\s*/?>", facts.get("Terms", "")) if _text(t)]
    if terms:
        out["terms"] = [_text(t) for t in terms]
    for key, label in (("party", "Party"), ("born", "Born")):
        if facts.get(label):
            out[key] = _text(facts[label])
    if out.get("party") == "Democrat":
        out["party"] = "Democratic"
    # The office's own site: "Governor's Website" (Florida's page spells it
    # "Governer's"), or just "Website" on a territory's page. "State Website"
    # is the state's portal, not the office.
    for href, label in _LINK.findall(page):
        if re.fullmatch(r"(Gover[a-z]+.s )?Website", _text(label)):
            out["website"] = html.unescape(href)
            break
    # Contact labels vary by page: "Phone" or "Office Phone"; "Address", or an
    # address block headed by the building ("Office of the Governor",
    # "Government House"), which leads the address. Anything else is
    # reported, not dropped in silence.
    for label, value in _CONTACT.findall(page):
        label = _text(label)
        text = re.sub(r"\s+,", ",", _text(re.sub(r"<br\s*/?>", ", ", value)))
        if "phone" in label.lower():
            out.setdefault("phone", text)
        elif label == "Address":
            out.setdefault("address", text)
        elif re.search(r"\b\d{5}(-\d{4})?$", text):
            out.setdefault("address", f"{label}, {text}")
        else:
            out.setdefault("unread", []).append(label)
    return out


_LINK = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>([^<]*Website)</a>')
_CONTACT = re.compile(r'<small class="content-block__item__description">\s*([^<]+?)\s*</small>'
                      r'(.*?)</li>', re.S)


def party_key(label):
    first = (label or "").lower()
    if first.startswith("democrat"):
        return "D"
    if first.startswith("republican"):
        return "R"
    return "I"


def _size(url):
    """The headshot's size in bytes, or ``None`` when the server does not say."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            length = response.headers.get("Content-Length")
    except OSError:
        return None
    return int(length) if length and length.isdigit() else None


def fetch(pause=1.0, previous=None):
    """``{code: governor}`` for every state and territory on the roster.
    *previous* is the cache being replaced: when a headshot's size cannot be
    measured now, its earlier measurement of the same URL stands (rule 8)."""
    roster = parse_roster(_get(ROSTER_URL))
    if len(roster) < 50:
        raise ExecutivesError(f"the roster lists only {len(roster)} governors")
    before = (previous or {}).get("governors", {})
    out = {}
    for entry in roster:
        facts = parse_profile(_get(entry["profile"]))
        if "party" not in facts or "terms" not in facts:
            raise ExecutivesError(f"{entry['state']}: the NGA page has no party or terms")
        out[entry["state"]] = dict(entry, **facts, partyKey=party_key(facts["party"]))
        if entry["headshot"]:
            size = _size(entry["headshot"]) or _size(entry["headshot"])
            old = before.get(entry["state"], {})
            if size is None and old.get("headshot") == entry["headshot"]:
                size = old.get("headshotBytes")
            out[entry["state"]]["headshotBytes"] = size
        time.sleep(pause)
    return out


# --------------------------------------------------------------- wikidata

# Every open-ended term with a start date. Old records often lack the end
# date, so a state can have several; the latest start is the incumbent.
# ?anyStart is every start date Wikidata records for that person in that
# office - one statement for continuous service, or one per term - against
# which the NGA's first day in office is checked.
_WIKIDATA_QUERY = """
SELECT ?person ?personLabel ?state ?start ?anyStart WHERE {
  ?office wdt:P31 wd:Q889821 ; wdt:P1001 ?st .
  ?st wdt:P31 wd:Q35657 ; wdt:P300 ?state .
  ?person p:P39 ?held . ?held ps:P39 ?office ; pq:P580 ?start .
  FILTER NOT EXISTS { ?held pq:P582 ?end }
  OPTIONAL { ?person p:P39 ?other . ?other ps:P39 ?office ; pq:P580 ?anyStart . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def _fold(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", plain).split()


def same_person(a, b):
    """Whether two renderings name the same person: the same surname and the
    same first initial ("Mike Dunleavy", "Mike J. Dunleavy")."""
    x, y = _fold(a), _fold(b)
    return bool(x and y) and x[-1] == y[-1] and x[0][:1] == y[0][:1]


def wikidata_governors():
    """``{code: (name, qid, starts)}`` from Wikidata, *starts* being every
    first day it records for that person in that office (ISO dates); empty
    if it cannot be reached (a cross-check that cannot run reports nothing,
    rule 8)."""
    url = WIKIDATA_URL + "?" + urllib.parse.urlencode({"query": _WIKIDATA_QUERY,
                                                       "format": "json"})
    try:
        data = json.loads(_get(url, timeout=120))
    except (ExecutivesError, ValueError):
        return {}
    latest, starts = {}, {}
    for row in data.get("results", {}).get("bindings", []):
        code = row["state"]["value"].split("-")[-1]
        start = row["start"]["value"]
        qid = row["person"]["value"].rsplit("/", 1)[-1]
        if code not in latest or start > latest[code][0]:
            latest[code] = (start, row["personLabel"]["value"], qid)
        if "anyStart" in row:
            starts.setdefault((code, qid), set()).add(row["anyStart"]["value"][:10])
    return {code: (name, qid, sorted(starts.get((code, qid), ())))
            for code, (_, name, qid) in latest.items()}


def carry_over(governors, previous):
    """Copy the last run's Wikidata id and start dates onto each governor
    who is the same person as before; returns how many were kept."""
    kept = 0
    before = (previous or {}).get("governors", {})
    for code, gov in governors.items():
        old = before.get(code, {})
        if old.get("wikidata") and old.get("name") == gov["name"]:
            gov["wikidata"] = old["wikidata"]
            gov["wikidataStarts"] = list(old.get("wikidataStarts", ()))
            kept += 1
    return kept


def cross_check(governors, wikidata):
    """``(agree, disagree)``: names Wikidata confirms, and names it disputes.
    A confirmed governor keeps Wikidata's id and start dates, against which
    the build checks the NGA's first day in office."""
    agree, disagree = [], []
    for code, gov in sorted(governors.items()):
        if code not in wikidata:
            continue
        name, qid, starts = (wikidata[code] + ((),))[:3]
        if same_person(gov["name"], name):
            gov["wikidata"] = qid
            gov["wikidataStarts"] = list(starts)
            agree.append(code)
        else:
            disagree.append((code, gov["name"], name))
    return agree, disagree


# ------------------------------------------------------------------ cache

def save_cache(governors, root="."):
    payload = {
        "source": SOURCE,
        "url": ROSTER_URL,
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "governors": {code: governors[code] for code in sorted(governors)},
    }
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
