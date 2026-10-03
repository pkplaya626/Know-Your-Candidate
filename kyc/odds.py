"""What prediction markets and polling averages say about each 2026 Senate race.

Three sources, each quoted as it publishes itself and never blended into a
number of our own:

* **Kalshi**, a CFTC-regulated exchange: its public market-data API, no key.
* **Polymarket**: its public Gamma API, no key.
* **Polling averages** as the race's Wikipedia page lists them - 270toWin,
  Decision Desk HQ, FiftyPlusOne, RealClearPolitics and others - each row
  linked to the aggregator that published it.

A market price is what a trader pays for a contract that pays $1 if the
outcome happens. It is not a poll and not a forecast by this site, and the
page says so beside every figure.

Attribution is checked, not trusted (rule 20). Kalshi's series ticker
``SENATELA`` holds *Kentucky's* race - its markets ask "Will Republicans win
the Senate race in Kentucky?" and resolve on "a Senator of Kentucky" - while
Louisiana's lives under ``KXSENATELA``. A market belongs to the state its own
question and its own resolution rules both name, never to the one a ticker
suggests. A market's outcome label that names nobody in the race ("Andy Barr"
on a Louisiana page) is shown as the party it resolves on, and reported.
"""

import datetime
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "odds.json")
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA_API = "https://gamma-api.polymarket.com"
_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)",
       "Accept": "application/json"}
_TIMEOUT = 30
STALE_DAYS = 8

KALSHI, POLYMARKET = "kalshi", "polymarket"
SOURCES = {KALSHI: "Kalshi", POLYMARKET: "Polymarket"}


class OddsError(RuntimeError):
    pass


def _get_json(url, retries=4):
    """GET a JSON document, backing off on the codes that mean "slow down"."""
    delay = 2.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise OddsError(f"{url}: HTTP {exc.code}") from exc
            wait = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = max(delay, min(float(wait), 30.0)) if wait else delay
            except ValueError:
                pass
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == retries - 1:
                raise OddsError(f"{url}: {exc}") from exc
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    raise OddsError(f"{url}: no answer")


def _price(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 1 else None


def state_codes(races):
    """``{"texas": "TX"}`` for every state with a 2026 Senate race."""
    from .results import state_name

    return {state_name(r["state"]).lower(): r["state"]
            for r in races if r.get("chamber") == "Senate"}


def _state_in(text, names):
    """The state *text* names, longest name first ("West Virginia" before
    "Virginia", rule 5), or ``None``."""
    lowered = (text or "").lower()
    for name in sorted(names, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", lowered):
            return names[name]
    return None


_PARTY_WORDS = (("democrat", "d"), ("republican", "r"), ("independent", "i"),
                ("libertarian", "i"), ("green", "i"))


def party_of(text):
    lowered = (text or "").lower()
    for word, key in _PARTY_WORDS:
        if word in lowered:
            return key
    return None


# --------------------------------------------------------------------- Kalshi

# A series about who wins a Senate seat, not a primary, a combination or a
# count: "Texas Senate race", "Who will win the Senate race in Louisiana?",
# "Special Senate election in Ohio".
_KALSHI_RACE = re.compile(r"senate race|senate winner|senate election|win the senate", re.I)
_KALSHI_NOT = re.compile(r"primary|nominee|combo|margin|turnout|count|endorse|advance|matchup|"
                         r"closer|split|call|leader|majority|governor|state senate|district|"
                         r"seats|ballot|sworn|runoff counties|parl", re.I)
_KALSHI_QUESTION = re.compile(r"win the senate race in ([A-Za-z .]+?)\?", re.I)
_KALSHI_RULE = re.compile(r"senator (?:of|from) ([A-Za-z .]+?)(?: for| following| in |,|\.|$)", re.I)


def kalshi_series():
    """Series that may hold a 2026 Senate race.

    Discovery only - Alabama's series is titled just "Alabama" - so a series
    is read when its title reads like a Senate race or its ticker starts with
    SENATE. Which state a market is about is decided by the market itself.
    """
    payload = _get_json(f"{KALSHI_API}/series?category=Elections")
    out = []
    for series in payload.get("series") or []:
        title = series.get("title") or ""
        if _KALSHI_NOT.search(title):
            continue
        if _KALSHI_RACE.search(title) or re.match(r"^(?:KX)?SENATE", series.get("ticker") or ""):
            out.append(series)
    return out


def kalshi_events(series_ticker):
    query = urllib.parse.urlencode({"series_ticker": series_ticker,
                                    "with_nested_markets": "true", "status": "open"})
    return _get_json(f"{KALSHI_API}/events?{query}").get("events") or []


def _is_2026(event):
    return "2026" in (event.get("sub_title") or "") or re.search(r"-26(?:[A-Z]*)$",
                                                                  event.get("event_ticker") or "")


def kalshi_market(event, series_ticker, names):
    """``(state, market record)`` from one Kalshi event, or ``(None, reason)``.

    Every market's question and its resolution rules must name the same state,
    and every market in the event must agree.
    """
    outcomes, states = [], set()
    for market in event.get("markets") or []:
        if market.get("status") not in ("active", "open"):
            continue
        question = market.get("title") or ""
        asked = _KALSHI_QUESTION.search(question)
        ruled = _KALSHI_RULE.search(market.get("rules_primary") or "")
        state = _state_in(asked.group(1), names) if asked else None
        rule_state = _state_in(ruled.group(1), names) if ruled else None
        if not state:
            return None, None          # not a "who wins this state's seat" market
        if state != rule_state:
            return None, (f"{market.get('ticker')}: asks about {state} but resolves on "
                          f"{rule_state or 'no state'}")
        states.add(state)
        price = _price(market.get("last_price_dollars"))
        bid, ask = _price(market.get("yes_bid_dollars")), _price(market.get("yes_ask_dollars"))
        if price is None and bid is not None and ask is not None:
            price = round((bid + ask) / 2, 4)
        if price is None:
            continue
        outcomes.append({
            "label": (market.get("yes_sub_title") or "").strip(),
            "party": party_of(market.get("subtitle")) or party_of(question),
            "question": question, "price": price, "bid": bid, "ask": ask,
            "volume": float(market.get("volume_fp") or market.get("volume") or 0),
        })
    if len(states) != 1 or len(outcomes) < 2:
        return None, f"{event.get('event_ticker')}: no single state with two priced outcomes"
    record = {"source": KALSHI, "event": event.get("event_ticker"),
              "title": event.get("title"),
              "url": f"https://kalshi.com/markets/{series_ticker.lower()}",
              "outcomes": sorted(outcomes, key=lambda o: -o["price"])}
    return states.pop(), record


def fetch_kalshi(names, log=print, pause=0.3):
    """``({state: record}, control record or None, notes)``."""
    found, notes = {}, []
    for series in kalshi_series():
        time.sleep(pause)
        try:
            events = kalshi_events(series["ticker"])
        except OddsError as exc:
            notes.append(str(exc))
            continue
        for event in events:
            if not _is_2026(event):
                continue
            state, record = kalshi_market(event, series["ticker"], names)
            if state is None:
                if record:
                    notes.append(record)
                continue
            if state in found:
                notes.append(f"{state}: two Kalshi events ({found[state]['event']}, "
                             f"{record['event']}); kept the busier")
                if sum(o["volume"] for o in record["outcomes"]) <= \
                        sum(o["volume"] for o in found[state]["outcomes"]):
                    continue
            found[state] = record
    control = None
    try:
        for event in kalshi_events("CONTROLS"):
            if not _is_2026(event):
                continue
            outcomes = []
            for market in event.get("markets") or []:
                price = _price(market.get("last_price_dollars"))
                if price is None or market.get("status") not in ("active", "open"):
                    continue
                outcomes.append({"label": (market.get("yes_sub_title") or "").strip(),
                                 "party": party_of(market.get("yes_sub_title")),
                                 "question": market.get("title"), "price": price})
            if len(outcomes) >= 2:
                control = {"source": KALSHI, "event": event.get("event_ticker"),
                           "title": event.get("title"),
                           "url": "https://kalshi.com/markets/controls",
                           "outcomes": sorted(outcomes, key=lambda o: -o["price"])}
    except OddsError as exc:
        notes.append(str(exc))
    log(f"  kalshi: {len(found)} Senate races{', and control of the Senate' if control else ''}")
    return found, control, notes


# ----------------------------------------------------------------- Polymarket

_PM_TITLE = re.compile(r"^\s*(?P<state>[A-Za-z .']+?)\s+(?:Special\s+)?Senate\s+Election\s+Winner\s*$",
                       re.I)
_PM_CONTROL = "which-party-will-win-the-senate-in-2026"


def polymarket_events(pause=0.3, pages=20):
    """Every open event Polymarket tags as part of the midterms."""
    out = []
    for page in range(pages):
        query = urllib.parse.urlencode({"tag_slug": "midterms", "closed": "false",
                                        "limit": 100, "offset": page * 100})
        batch = _get_json(f"{GAMMA_API}/events?{query}")
        if not batch:
            break
        out.extend(batch)
        time.sleep(pause)
    return out


def _pm_party(market):
    question = (market.get("question") or "").lower()
    if "will the democrats" in question:
        return "d"
    if "will the republicans" in question:
        return "r"
    if "will an independent" in question:
        return "i"
    suffix = re.search(r"\((D|R|I)\)\s*$", market.get("groupItemTitle") or "")
    if suffix:
        return suffix.group(1).lower()
    # "Democratic Party" on the control market; "Democrat" on Delaware's.
    label = market.get("groupItemTitle") or ""
    if re.fullmatch(r"\s*(?:the\s+)?(?:democrat(?:ic)?|republican)s?(?:\s+party)?\s*", label, re.I):
        return party_of(label)
    return None


def polymarket_market(event):
    """A market record from one Polymarket event: its live outcomes only -
    the "Person A" placeholders it lists for candidates not yet named are
    inactive and unpriced."""
    outcomes = []
    for market in event.get("markets") or []:
        if not market.get("active") or market.get("closed"):
            continue
        try:
            prices = json.loads(market.get("outcomePrices") or "null") or []
        except ValueError:
            prices = []
        price = _price(prices[0]) if prices else None
        if price is None:
            continue
        outcomes.append({
            "label": (market.get("groupItemTitle") or "").strip(),
            "party": _pm_party(market), "question": market.get("question"),
            "price": price, "bid": _price(market.get("bestBid")),
            "ask": _price(market.get("bestAsk")),
            "volume": float(market.get("volume") or 0),
        })
    if len(outcomes) < 2:
        return None
    return {"source": POLYMARKET, "event": event.get("slug"), "title": (event.get("title") or "").strip(),
            "url": f"https://polymarket.com/event/{event.get('slug')}",
            "outcomes": sorted(outcomes, key=lambda o: -o["price"])}


def fetch_polymarket(names, log=print):
    """``({state: record}, control record or None, notes)``."""
    found, notes, control = {}, [], None
    for event in polymarket_events():
        if event.get("slug") == _PM_CONTROL:
            control = polymarket_market(event)
            continue
        title = _PM_TITLE.match(event.get("title") or "")
        if not title:
            continue
        state = _state_in(title.group("state"), names)
        # The title says which state; the description must say the same.
        if not state or _state_in(event.get("description") or "", names) != state:
            notes.append(f"{event.get('slug')}: title and description do not name one state")
            continue
        record = polymarket_market(event)
        if record is None:
            continue
        if state in found:
            notes.append(f"{state}: two Polymarket events ({found[state]['event']}, "
                         f"{record['event']}); kept the busier")
            if sum(o["volume"] for o in record["outcomes"]) <= \
                    sum(o["volume"] for o in found[state]["outcomes"]):
                continue
        found[state] = record
    log(f"  polymarket: {len(found)} Senate races{', and control of the Senate' if control else ''}")
    return found, control, notes


# ---------------------------------------------------------------------- polls

_HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$", re.M)
_TABLE = re.compile(r"\{\|.*?\n\|\}", re.S)


def general_election(text):
    """The wikitext of the page's general-election section, or ``""``."""
    headings = list(_HEADING.finditer(text or ""))
    for n, heading in enumerate(headings):
        if re.fullmatch(r"general election", heading.group(2).strip(), re.I):
            level = len(heading.group(1))
            end = len(text)
            for later in headings[n + 1:]:
                if len(later.group(1)) <= level:
                    end = later.start()
                    break
            return text[heading.end():end]
    return ""


def _split_top(text, sep="|"):
    """*text* split on *sep* outside [[links]] and {{templates}}."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            i += 2
            continue
        if two in ("]]", "}}"):
            depth = max(depth - 1, 0)
            i += 2
            continue
        if text[i] == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def _cells(line, marker):
    """The cells of one table line: ``| a || b`` or ``! a !! b``."""
    body = line[1:]
    raw = re.split(r"\|\||!!", body) if marker == "!" else _split_double(body)
    cells = []
    for cell in raw:
        pieces = _split_top(cell)
        # "style=... | content": the attributes come before the first pipe.
        content = pieces[-1] if len(pieces) > 1 and "=" in pieces[0] or (
            len(pieces) > 1 and pieces[0].strip().startswith("{{")) else cell
        cells.append(content.strip())
    return cells


def _split_double(body):
    """Split a data line on "||" outside links and templates."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            i += 2
            continue
        if two in ("]]", "}}"):
            depth = max(depth - 1, 0)
            i += 2
            continue
        if two == "||" and depth == 0:
            out.append(body[start:i])
            start = i + 2
            i += 2
            continue
        i += 1
    out.append(body[start:])
    return out


def table_rows(table):
    """``(header cells, [data row cells])`` of one wikitext table."""
    header, rows, current = [], [], None
    for line in table.split("\n")[1:]:
        line = line.rstrip()
        if line.startswith("|}"):
            break
        if line.startswith("|-"):
            if current:
                rows.append(current)
            current = []
            continue
        if line.startswith("!"):
            header.extend(_cells(line, "!"))
        elif line.startswith("|") and not line.startswith("|+"):
            if current is None:
                current = []
            current.extend(_cells(line, "|"))
        elif current and line and not line.startswith(("{|", "|")):
            current[-1] += "\n" + line          # a cell continued on the next line
    if current:
        rows.append(current)
    return header, rows


def _plain(cell):
    from .results import plain_text

    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell or "", flags=re.S)
    # "Mary<br />Peltola" is two words, not "MaryPeltola".
    return plain_text(re.sub(r"<br\s*/?>", " ", text, flags=re.I))


def _percent(cell):
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", _plain(cell))
    return float(match.group(1)) if match else None


def aggregate_table(section):
    """The section's "Aggregate polls" table: the first whose header names a
    "Source of poll aggregation"."""
    for table in _TABLE.findall(section or ""):
        header, _ = table_rows(table)
        if header and re.search(r"aggregation", _plain(header[0]), re.I):
            return table
    return ""


def parse_aggregates(table, people):
    """Rows of an aggregate-polls table, or ``(None, reason)``.

    Every candidate column must name someone in the race - the people this
    page lists for it - or the table is a hypothetical matchup, not this
    race's November ballot, and is not shown.
    """
    header, rows = table_rows(table)
    names = [_plain(h) for h in header]
    try:
        updated = next(i for i, h in enumerate(names) if re.search(r"updated", h, re.I))
    except StopIteration:
        return None, "no 'Dates updated' column"
    administered = next((i for i, h in enumerate(names) if re.search(r"administered", h, re.I)),
                        None)
    tail = next((i for i, h in enumerate(names) if i > updated
                 and re.search(r"other|undecided|margin|lead", h, re.I)), len(names))
    candidates = list(range(updated + 1, tail))
    other = next((i for i, h in enumerate(names) if re.search(r"other|undecided", h, re.I)), None)
    margin = next((i for i, h in enumerate(names) if re.search(r"margin|lead", h, re.I)), None)
    if len(candidates) < 2:
        return None, "fewer than two candidate columns"
    columns = []
    for i in candidates:
        label = re.sub(r"\s+", " ", names[i]).strip()
        hits = named(label, people)
        if not hits:
            return None, f"column {label!r} names nobody in the race"
        columns.append((i, label, _label_party(label) or _shared_party(hits),
                        hits[0].get("id") if len(hits) == 1 else None))
    out = []
    for row in rows:
        if len(row) < len(names) - 1:
            continue
        cell = row[0]
        url = re.search(r"\|\s*url\s*=\s*(https?://[^\s|}]+)", cell)
        results = []
        for i, label, party, pid in columns:
            value = _percent(row[i]) if i < len(row) else None
            if value is None:
                break
            results.append({"label": label, "party": party, "pct": value, "id": pid})
        if len(results) != len(columns):
            continue
        out.append({
            "aggregator": _plain(cell).strip(),
            "url": url.group(1) if url else None,
            "administered": _plain(row[administered]) if administered is not None else "",
            "updated": _plain(row[updated]),
            "results": results,
            "other": _percent(row[other]) if other is not None and other < len(row) else None,
            "margin": _plain(row[margin]) if margin is not None and margin < len(row) else "",
        })
    return (out, None) if out else (None, "no rows with a figure for every candidate")


def _fold(text):
    import unicodedata

    normal = unicodedata.normalize("NFD", str(text or "").replace("’", "'"))
    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def _words(text):
    return re.findall(r"[a-z0-9']+", _fold(text))


_NOT_A_NAME = {"sen", "rep", "gov", "dr", "jr", "sr", "ii", "iii", "iv", "r", "d", "i"}


def named(label, people):
    """Everyone in the race *label* names, by surname.

    "Darline Graham" is Darline Graham Nordone: the label's last name may be
    any of a person's names after the first. Alaska's race holds two Sullivans
    (rule 25), so a label can name more than one person, and callers decide
    what that means.
    """
    words = [w for w in _words(re.sub(r"\([^)]*\)", " ", label)) if w not in _NOT_A_NAME]
    if not words:
        return []
    last = words[-1]
    hits = []
    for person in people:
        theirs = [w for w in _words(person.get("name")) if w not in _NOT_A_NAME]
        if theirs and (last == theirs[-1] or (len(theirs) > 2 and last in theirs[1:])):
            hits.append(person)
    return hits


def _party_key(person):
    party = str((person or {}).get("party") or "")
    return "d" if "Democrat" in party else "r" if party == "Republican" else "i"


def _shared_party(people):
    """The party everyone in *people* shares, or ``None``."""
    parties = {_party_key(p) for p in people}
    return parties.pop() if len(parties) == 1 else None


def _label_party(label):
    suffix = re.search(r"\((D|R|I)\)\s*$", label or "")
    return suffix.group(1).lower() if suffix else None


def fetch_polls(races, people_of, log=print, fetch=None):
    """``({race id: {page, url, rows}}, notes)`` from each race's Wikipedia page."""
    from .results import PageMissing, fetch_wikitext, page_titles

    fetch = fetch or fetch_wikitext
    found, notes = {}, []
    for race in races:
        if race.get("chamber") != "Senate":
            continue
        people = people_of(race)
        for title in page_titles(race["state"], "S"):
            try:
                text = fetch(title)
            except PageMissing:
                continue
            except Exception as exc:            # throttled or down: nothing concluded
                notes.append(f"{race['id']}: {title}: {exc}")
                continue
            table = aggregate_table(general_election(text))
            if not table:
                continue
            rows, reason = parse_aggregates(table, people)
            if rows is None:
                notes.append(f"{race['id']}: {title}: {reason}")
                continue
            found[race["id"]] = {
                "page": title, "rows": rows,
                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                       + "#Polling"}
            break
    log(f"  polls: aggregate polling for {len(found)} Senate races")
    return found, notes


# ---------------------------------------------------------------------- cache

def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def build(races, people_of, log=print, now=None):
    """Fetch all three sources into one cache document."""
    names = state_codes(races)
    by_state = {r["state"]: r["id"] for r in races if r.get("chamber") == "Senate"}
    kalshi, kalshi_control, kalshi_notes = fetch_kalshi(names, log=log)
    poly, poly_control, poly_notes = fetch_polymarket(names, log=log)
    polls, poll_notes = fetch_polls(races, people_of, log=log)
    entries = {}
    for state, rid in by_state.items():
        markets = [m for m in (kalshi.get(state), poly.get(state)) if m]
        entry = {}
        if markets:
            entry["markets"] = markets
        if rid in polls:
            entry["polls"] = polls[rid]
        if entry:
            entries[rid] = entry
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds")
    return {
        "fetched": stamp,
        "races": entries,
        "control": {"senate": [c for c in (kalshi_control, poly_control) if c]},
        "notes": sorted(kalshi_notes + poly_notes + poll_notes),
    }


# ---------------------------------------------------------------------- apply

def checked_outcomes(market, people):
    """The market's outcomes, each label checked against the race.

    A label that names a person must name someone in this race; one that does
    not is shown as the party the market resolves on, with ``mismatch`` set
    for validate to report. A party label ("Republican party", "Democrat")
    stands as it is.
    """
    out = []
    for outcome in market.get("outcomes") or []:
        row = dict(outcome)
        label = row.get("label") or ""
        words = [w for w in _words(label) if w not in _NOT_A_NAME]
        is_party = (not words) or set(words) <= {"democratic", "democrat", "democrats",
                                                 "republican", "republicans", "party",
                                                 "independent", "other", "libertarian",
                                                 "green", "an"}
        if not is_party:
            hits = named(label, people)
            if not hits:
                row["mismatch"] = True
                row["marketLabel"] = label
                row["label"] = {"d": "Democratic party", "r": "Republican party",
                                "i": "Independent"}.get(row.get("party"), "Other")
            elif not row.get("party"):
                row["party"] = _label_party(label) or _shared_party(hits)
        out.append(row)
    return out


def apply(races, cache, by_id):
    """Attach ``odds`` to every Senate race the cache covers; return the count."""
    entries = (cache or {}).get("races") or {}
    applied = 0
    for race in races:
        entry = entries.get(race["id"])
        if not entry or race.get("chamber") != "Senate":
            continue
        people = [by_id[i] for i in race.get("incumbentIds", []) + race.get("candidateIds", [])
                  if i in by_id]
        markets = []
        for market in entry.get("markets") or []:
            markets.append(dict(market, outcomes=checked_outcomes(market, people)))
        race["odds"] = {"asOf": cache.get("fetched"), "markets": markets}
        if entry.get("polls"):
            race["odds"]["polls"] = entry["polls"]
        applied += 1
    return applied


def control(cache):
    """The markets on which party wins the Senate, for the build meta."""
    senate = ((cache or {}).get("control") or {}).get("senate") or []
    return {"asOf": cache.get("fetched"), "markets": senate} if senate else None
