"""The statewide questions on each jurisdiction's November 3, 2026 ballot
(rule 95).

A reader asked "what is on my ballot" and every state page said the ballot
also held "ballot measures, which this site does not list" (audit
2026-10-17, RACES-16, STATEGOV-14, PERSONA-08). No source keyed by an id
lists them, so they are a hand-edited cache, ``data/ballot_measures.json``,
researched jurisdiction by jurisdiction from each election office's own
list - a Secretary of State's qualified or certified measures, a board's
voter guide, the official sample ballots - and every list re-opened by a
second reader (``verified``). Ballotpedia, NCSL, news and advocacy sites
were leads, never sources (rule 50).

Each jurisdiction says one of three things:

- ``hasMeasures`` true: its measures, each with its official designation,
  title (where the state prints one: Alabama, Missouri and Tennessee print
  none), the official text quoted, what kind of measure it is and who put
  it on the ballot, its source's address and words, and the official voter
  guide's page for it where there is one;
- false: no statewide question, credited to the document that shows it -
  an office's sentence saying so, an office's list of its ballots'
  questions, or the official ballots, which print none - quoted
  (``noneFrom``, ``noneWords``). A proclamation calling the election for
  offices is not one: it would not name a constitutional amendment
  election, which that election's own resolution sets (Texas, PR #120);
- null: no official source says either way (American Samoa, Maine,
  Pennsylvania, Puerto Rico), and the page says this site has not found an
  official list, with the election office's own site (``office``), never
  "none" (rule 19).

The page describes a measure only in its official words and kind, and
never says what a yes or a no vote does in its own; no colour suggests a
side. Measures already decided at an earlier 2026 election, and those a
court took off the ballot, are not in the list; the research notes name
them. ``check`` holds the cache to all of this, and ``for_page`` writes
what ``data/measures.js`` holds.
"""

import json
import os
import re

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "ballot_measures.json")
ELECTION = "2026-11-03"
# A list is read in the cycle's year; a page it cites may have been
# published from the day after the last general election (a measure the
# legislature referred in 2025).
READ_EARLIEST, READ_LATEST = "2026-01-01", "2026-12-31"
PUBLISHED_EARLIEST = "2024-11-06"

# The kinds of measure, in the page's words. "other" says its own, from the
# measure's official designation (``kindWords``).
KINDS = {
    "constitutional amendment": "Constitutional amendment",
    "statute": "Statute",
    "bond": "Bond",
    "referendum": "Referendum on a law",
    "advisory": "Advisory question",
    "constitutional convention": "Constitutional convention question",
    "other": None,
}
# Who put it on the ballot. "constitution" and "commission" say which in
# their own words (``originWords``); None is "not recorded here".
ORIGINS = ("legislature", "citizens", "constitution", "commission", None)
# What a "none" rests on: an office's sentence that there is none, the
# official ballots (which would print a statewide question on every one), or
# an office's list of the questions on its ballots.
NONE_FROM = ("statement", "ballots", "list")

RECORD_KEYS = frozenset({"hasMeasures", "by", "read", "listSource", "voterGuide", "office",
                         "noneFrom", "noneWords", "textNote", "measures", "notes", "verified"})
MEASURE_KEYS = frozenset({"designation", "title", "question", "kind", "origin", "voterGuide",
                          "source", "kindWords", "originWords", "textNote", "local"})

# A shown title is the document's own name. The researchers' asides ("linked
# as ... from https://...", "Spanish edition: ...", "described as ...") were
# rendered as link text (PR #120 review); they belong in ``notes``.
_NOT_A_TITLE = re.compile(r"https?:|www\.|\blinked\b|\bdescribed as\b|\bedition:|\bquery:|"
                          r"\bpages?\s+\d", re.I)

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_IN_TEXT = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_CUT = re.compile(r"\.\.\.|…")

# A legislature's own name (rule 75), for "put on the ballot by the General
# Assembly"; D.C.'s legislature is its Council.
_LEGISLATURE_OTHER = {"DC": "Council of the District of Columbia"}


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def jurisdictions():
    from .normalize import US_STATES
    return frozenset(US_STATES.values())


# ------------------------------------------------------------- sources

def elsewhere(url):
    """``(prefix, codes, label, evidence)`` when *url* is under an evidenced
    official page off the jurisdiction's own domains, else None."""
    from . import overrides
    for prefix, (codes, label, evidence) in overrides.MEASURE_SOURCES_ELSEWHERE.items():
        if str(url or "").startswith(prefix):
            return prefix, codes, label, evidence
    return None


def official(url, code):
    """``(True, label)`` when *url* is *code*'s own official page or an
    evidenced one elsewhere (``overrides.MEASURE_SOURCES_ELSEWHERE``), else
    ``(False, why)``. A compiled table, a news site or an advocate's page is
    never one (rule 50): only a jurisdiction's own domains count."""
    from . import voting_dates
    if voting_dates.compiled(str(url or "")):
        return False, "a compiled table, a lead and never a source (rule 50)"
    found = elsewhere(url)
    if found:
        _prefix, owners, label, _evidence = found
        return (code in owners), (label if code in owners
                                  else f"{'/'.join(owners)}'s page, not {code}'s")
    return voting_dates.official_source(url, code)


def _source_problems(where, code, source, *, quoted=True, titled=False):
    if not isinstance(source, dict) or not source.get("url"):
        return [f"{where}: no source"]
    out = []
    ok, why = official(source["url"], code)
    if not ok:
        out.append(f"{where}: {source['url']} is not an official source ({why})")
    if quoted and not str(source.get("quote") or "").strip():
        out.append(f"{where}: its source is not quoted")
    if titled and not str(source.get("title") or "").strip():
        out.append(f"{where}: its source has no title")
    for key in ("title", "name"):
        if _NOT_A_TITLE.search(str(source.get(key) or "")):
            out.append(f"{where}: its {key} carries a note or an address, not the document's "
                       f"own name: {source[key]!r}")
    for day in _ISO_IN_TEXT.findall(str(source.get("pageUpdated") or "")):
        if not PUBLISHED_EARLIEST <= day <= READ_LATEST:
            out.append(f"{where}: its page's date {day} is outside the cycle")
    return out


# ------------------------------------------------------------- checking

def problems(data):
    """Every way *data* breaks the cache's rules, as strings."""
    if not isinstance(data, dict):
        return ["no record"]
    out = []
    if data.get("election") != ELECTION:
        out.append(f"the election is {data.get('election')!r}, not {ELECTION}")
    records = data.get("jurisdictions") or {}
    every = jurisdictions()
    out += [f"{code}: no record" for code in sorted(every - set(records))]
    out += [f"{code}: not a jurisdiction" for code in sorted(set(records) - every)]
    for code, record in sorted(records.items()):
        if code in every:
            out += record_problems(code, record)
    return out


def record_problems(code, record):
    out = []
    extra = set(record) - RECORD_KEYS
    if extra:
        out.append(f"{code}: unknown field(s) {', '.join(sorted(extra))}")
    has = record.get("hasMeasures", "absent")
    if has not in (True, False, None):
        return out + [f"{code}: hasMeasures must be true, false or null, not {has!r}"]
    if not str(record.get("by") or "").strip():
        out.append(f"{code}: no office named ('by')")
    read = str(record.get("read") or "")
    if not _DATE.match(read):
        out.append(f"{code}: no day read ('read')")
    elif not READ_EARLIEST <= read <= READ_LATEST:
        out.append(f"{code}: read on {read}, outside the cycle")
    measures = record.get("measures")
    if not isinstance(measures, list):
        return out + [f"{code}: 'measures' is not a list"]
    guide = record.get("voterGuide")
    if guide is not None:
        out += _source_problems(f"{code} voter guide", code, guide, quoted=False, titled=True)
    if has is None:
        if measures:
            out.append(f"{code}: no official list, yet {len(measures)} measure(s) listed")
        office = record.get("office")
        if not isinstance(office, dict) or not office.get("name"):
            out.append(f"{code}: no official list and no election office to send a reader to")
        else:
            out += _source_problems(f"{code} election office", code, office, quoted=False)
        for key in ("noneFrom", "noneWords"):
            if key in record:
                out.append(f"{code}: '{key}' is for a jurisdiction with no measures")
        return out
    out += _source_problems(f"{code} list", code, record.get("listSource"), titled=True)
    if has is False:
        if measures:
            out.append(f"{code}: hasMeasures is false, yet {len(measures)} measure(s) listed")
        basis = record.get("noneFrom")
        if basis not in NONE_FROM:
            out.append(f"{code}: no statewide question, but not said on what ('noneFrom' is "
                       f"{basis!r})")
        words = record.get("noneWords")
        if basis == "statement":
            quote = str((record.get("listSource") or {}).get("quote") or "")
            if not words:
                out.append(f"{code}: a {basis} with no words quoted ('noneWords')")
            elif str(words) not in quote:
                out.append(f"{code}: 'noneWords' is not in its source's quote")
        elif words:
            out.append(f"{code}: 'noneWords' is shown only for a statement")
        return out
    if not measures:
        out.append(f"{code}: hasMeasures is true, and no measure is listed")
    elif all(isinstance(m, dict) and m.get("local") for m in measures):
        # A question each municipality decides for itself is not a statewide
        # one; with no other, the jurisdiction has none (``hasMeasures``
        # false, with what shows it).
        out.append(f"{code}: hasMeasures is true, and every measure listed is decided locally")
    for key in ("noneFrom", "noneWords", "office"):
        if key in record:
            out.append(f"{code}: '{key}' is for a jurisdiction without measures")
    seen = set()
    for i, measure in enumerate(measures):
        out += measure_problems(code, i, measure, guide)
        name = str((measure or {}).get("designation") or "")
        if name in seen:
            out.append(f"{code}: '{name}' is listed twice")
        seen.add(name)
    return out


def measure_problems(code, i, m, guide):
    if not isinstance(m, dict):
        return [f"{code} measure {i + 1}: not a record"]
    where = f"{code} {m.get('designation') or 'measure ' + str(i + 1)}"
    out = []
    extra = set(m) - MEASURE_KEYS
    if extra:
        # A "yes vote means", a forecast, a position: none is the office's
        # designation, title, question or kind, and none is shown.
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))}")
    if not str(m.get("designation") or "").strip():
        out.append(f"{where}: no designation")
    if not str(m.get("question") or "").strip():
        out.append(f"{where}: no official text ('question')")
    if "local" in m:
        # On every ballot, decided by each municipality for itself (New
        # Hampshire's HB 1300 question): its text names the place, the page
        # lists it apart from the statewide questions, and says how each
        # ballot words it.
        if m["local"] is not True:
            out.append(f"{where}: 'local' is true or absent, not {m['local']!r}")
        elif not str(m.get("textNote") or "").strip():
            out.append(f"{where}: a locally decided question says how each ballot words it "
                       "('textNote')")
    if m.get("title") is not None and not str(m["title"]).strip():
        out.append(f"{where}: an empty title (null where the state prints none)")
    kind = m.get("kind")
    if kind not in KINDS:
        out.append(f"{where}: unknown kind {kind!r}")
    elif KINDS[kind] is None and not str(m.get("kindWords") or "").strip():
        out.append(f"{where}: kind 'other' says what it is in 'kindWords'")
    origin = m.get("origin")
    if origin not in ORIGINS:
        out.append(f"{where}: unknown origin {origin!r}")
    elif origin in ("constitution", "commission") and not str(m.get("originWords") or "").strip():
        out.append(f"{where}: origin {origin!r} says which in 'originWords'")
    out += _source_problems(where, code, m.get("source"))
    if m.get("voterGuide"):
        ok, why = official(m["voterGuide"], code)
        if not ok:
            out.append(f"{where}: its voter guide {m['voterGuide']} is not official ({why})")
    return out


def check(data):
    """Raise ``ValueError`` listing every problem, or return *data*."""
    found = problems(data)
    if found:
        raise ValueError("; ".join(found))
    return data


# ------------------------------------------------------------- the page

def legislature(code):
    from .government_maps import LEGISLATURE_NAME
    return _LEGISLATURE_OTHER.get(code) or LEGISLATURE_NAME.get(code, "Legislature")


def origin_words(code, m):
    origin = m.get("origin")
    if m.get("originWords"):
        return m["originWords"]
    if origin == "legislature":
        return "the " + legislature(code)
    if origin == "citizens":
        return "a citizens' petition"
    return None


def kind_words(m):
    return m.get("kindWords") or KINDS.get(m.get("kind"))


def _measure(code, m):
    title = m.get("title")
    designation = m["designation"].strip()
    # A title the designation already holds ("Question 2 (Statutory
    # Question required by HB 1300 ...)") is said once.
    if title and title.strip() in designation:
        title = None
    out = {
        "designation": designation,
        "title": title.strip() if title else None,
        "text": m["question"].strip(),
        "kind": kind_words(m),
        "origin": origin_words(code, m),
        "source": m["source"]["url"],
    }
    if _CUT.search(m["question"]):
        out["cut"] = True
    if m.get("voterGuide"):
        out["guide"] = m["voterGuide"]
    if m.get("textNote"):
        out["note"] = m["textNote"]
    if m.get("local"):
        out["local"] = True
    return out


def for_jurisdiction(code, record):
    has = record.get("hasMeasures")
    out = {"has": has, "by": record["by"], "read": record["read"]}
    if record.get("listSource"):
        out["list"] = {"url": record["listSource"]["url"], "title": record["listSource"]["title"]}
    if record.get("voterGuide"):
        out["guide"] = {"url": record["voterGuide"]["url"], "title": record["voterGuide"]["title"]}
    if has is None:
        out["office"] = {"url": record["office"]["url"], "name": record["office"]["name"]}
        out.pop("list", None)
    elif has is False:
        out["none"] = {"from": record["noneFrom"]}
        if record.get("noneWords"):
            out["none"]["words"] = record["noneWords"]
    else:
        out["measures"] = [_measure(code, m) for m in record["measures"]]
    if record.get("textNote"):
        out["textNote"] = record["textNote"]
    return out


def for_page(data):
    """What ``data/measures.js`` holds: each jurisdiction's measures in the
    page's words, its list and guide, or what its "none" or "not found"
    rests on. A cache that breaks its rules is refused, not shown."""
    check(data)
    return {code: for_jurisdiction(code, record)
            for code, record in sorted(data["jurisdictions"].items())}


def stats(data):
    records = (data or {}).get("jurisdictions") or {}
    return {
        "measures": sum(1 for r in records.values() for m in r.get("measures") or []
                        if not m.get("local")),
        "local": sum(1 for r in records.values() for m in r.get("measures") or []
                     if m.get("local")),
        "with": sum(1 for r in records.values() if r.get("hasMeasures") is True),
        "none": sum(1 for r in records.values() if r.get("hasMeasures") is False),
        "unknown": sum(1 for r in records.values() if r.get("hasMeasures") is None),
    }
