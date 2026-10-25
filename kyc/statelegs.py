"""Every sitting state legislator, from Open States.

The site covers Congress through the ``congress-legislators`` dataset; this
is its state-level counterpart. ``python build_profile_site.py statelegs``
downloads Open States' per-state file of current legislators (public domain,
https://data.openstates.org/people/current/<st>.csv) for all fifty states,
keeps what the site shows, and writes ``data/state_legislators.json``.

Each legislator keeps Open States' own id (``ocd-person/...``), so a record
is never matched on a name (rules 3 and 17), and the links, portrait and
contact details come from that record (rule 32).

A legislator is placed on the map by matching their district to a Census
boundary (``legislative_maps/<st>.json``). Names differ in form - Open States
writes "Hampshire, Franklin and Worcester", the Census "Hampshire-Franklin-
Worcester"; Idaho's "10A" is seat A of district 10 - so both are normalised
the same way, and anyone who still does not match is reported, never
guessed (rule 16). New Hampshire's floterial representatives sit for an
overlay of several districts that a map of non-overlapping districts cannot
draw; they are listed, not placed.
"""

import csv
import datetime
import io
import json
import os
import re
import time
import urllib.request

OPENSTATES_URL = "https://data.openstates.org/people/current/{st}.csv"
SOURCE = "Open States (Plural Policy), current legislators"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "state_legislators.json")
MAPS_DIR = "legislative_maps"

# How tools/fetch_legislative_maps.py simplifies a state's districts, here so
# the build can say how far the drawn lines may stray (kyc/legislature.py
# ``lineErrorKm``, which "Find who represents me" widens its margin by). The
# districts are far smaller than congressional ones - a Boston house district
# is a few kilometres across - so they keep more detail: Douglas-Peucker at
# 120 m, rising with the state's size (an eight-thousandth of its diagonal),
# so Alaska's coast does not cost what Massachusetts's districts need.
MAP_TOLERANCE_M = 120.0
MAP_MAX_TOLERANCE_M = 300.0


def map_tolerance_m(points):
    """The simplification tolerance, in metres, for a state whose upper
    chamber's districts have these ``(lon, lat)`` *points*."""
    import math
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    mid = math.radians((min(lats) + max(lats)) / 2)
    width = (max(lons) - min(lons)) * 111320.0 * math.cos(mid)
    height = (max(lats) - min(lats)) * 110574.0
    # Capped: Alaska's Aleutians cross the 180th meridian, so its "width"
    # spans the globe, and Anchorage's districts are a few kilometres across.
    return min(MAP_MAX_TOLERANCE_M, max(MAP_TOLERANCE_M, math.hypot(width, height) / 8000.0))

REQUIRED = ("id", "name", "current_party", "current_district", "current_chamber")


class StateLegislatorsError(RuntimeError):
    """The data could not be fetched, or is not what the pipeline expects."""


# ------------------------------------------------------------------ parties

def party_key(label):
    """"D", "R", "I" or "N" (nonpartisan) for a party label as Open States
    writes it. Fusion lines name the party first ("Democratic/Working
    Families"); Minnesota's Democrats are the Democratic-Farmer-Labor Party."""
    first = (label or "").split("/")[0].strip().lower()
    if first.startswith("democratic"):
        return "D"
    if first.startswith("republican"):
        return "R"
    if first == "nonpartisan":
        return "N"
    return "I"


# ---------------------------------------------------------------- districts

_WORDS = ("state legislative subdistrict", "state legislative district", "state senate district",
          "state house district", "senatorial district", "state house", "district")


def norm(name):
    """A district name reduced to what both sources agree on: "10th Bristol
    District" and "10th Bristol"; "Hampshire-Franklin-Worcester" and
    "Hampshire, Franklin and Worcester"; "Chittenden South East" and
    "Chittenden Southeast"; "Merrimack 08" and "Merrimack 8"."""
    text = (name or "").lower()
    for word in _WORDS:
        text = text.replace(word, " ")
    text = re.sub(r"[-,.]", " ", text)
    tokens = [str(int(t)) if t.isdigit() else t for t in text.split() if t != "and"]
    return "".join(tokens)


def seat_district(code, chamber, district):
    """The Census district a seat belongs to, where a state numbers seats
    within a district: Idaho elects representatives to seats A and B of each
    legislative district."""
    if code == "ID" and chamber == "lower":
        return re.sub(r"^(\d+)\s*[AB]$", r"\1", district.strip(), flags=re.I)
    return district


def load_map(code, root="."):
    path = os.path.join(root, MAPS_DIR, f"{code.lower()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def boundary_index(topo):
    """``{chamber: {normalised name: Census code}}`` from a state's map."""
    out = {}
    for chamber in ("upper", "lower"):
        obj = (topo.get("objects") or {}).get(chamber)
        if not obj:
            continue
        index = {}
        for geometry in obj["geometries"]:
            props = geometry["properties"]
            index[norm(props["name"])] = props["id"]
        out[chamber] = index
    return out


def match(code, records, topo):
    """Give each record the Census code of its district (``districtId``).

    Returns the records that could not be placed, with the reason."""
    index = boundary_index(topo)
    unplaced = []
    for record in records:
        chamber = record["chamber"]
        names = index.get(chamber) or {}
        key = norm(seat_district(code, chamber, record["district"]))
        found = names.get(key)
        if found:
            record["districtId"] = found
        elif record.get("tribalSeat"):
            record.pop("districtId", None)          # elected by a nation, not a district
        else:
            record.pop("districtId", None)
            why = ("a floterial district, which overlays others and is not drawn"
                   if code == "NH" and chamber == "lower" else
                   "no boundary of that name")
            unplaced.append((record, why))
    return unplaced


# ------------------------------------------------------------------- record

def _split(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def record(row, code):
    """What the site keeps of one Open States row."""
    chamber = row["current_chamber"].strip()
    out = {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "party": row["current_party"].strip(),
        "partyKey": party_key(row["current_party"]),
        # Nebraska's one chamber is its upper house in the Census files.
        "chamber": "upper" if chamber == "legislature" else chamber,
        "district": row["current_district"].strip(),
        "state": code,
    }
    if chamber == "legislature":
        out["unicameral"] = True
    # Maine's House seats non-voting representatives of tribal nations,
    # elected by the nation, not a district (Open States names the nation).
    if code == "ME" and re.search(r"\b(tribe|band|nation)\b", out["district"], re.I):
        out["tribalSeat"] = True
    for key, field in (("email", "email"), ("image", "image"), ("phone", "capitol_voice"),
                       ("address", "capitol_address"), ("districtPhone", "district_voice"),
                       ("wikidata", "wikidata")):
        value = (row.get(field) or "").strip()
        if value:
            out[key] = value
    links = [u for u in _split(row.get("links")) if u.startswith("https://") or u.startswith("http://")]
    if links:
        out["links"] = links
    social = {k: row[k].strip() for k in ("twitter", "facebook", "instagram", "youtube")
              if (row.get(k) or "").strip()}
    if social:
        out["social"] = social
    return out


# -------------------------------------------------------------------- fetch

def parse(text, code):
    reader = csv.DictReader(io.StringIO(text))
    missing = [f for f in REQUIRED if f not in (reader.fieldnames or [])]
    if missing:
        raise StateLegislatorsError(f"{code}: the file has no {', '.join(missing)} column")
    rows = [record(row, code) for row in reader if (row.get("id") or "").strip()]
    if not rows:
        raise StateLegislatorsError(f"{code}: the file lists nobody")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise StateLegislatorsError(f"{code}: a legislator is listed twice")
    for r in rows:
        if r["chamber"] not in ("upper", "lower"):
            raise StateLegislatorsError(f"{code}: {r['name']} is in an unknown chamber")
    return rows


def fetch(codes, pause=0.5, timeout=60):
    """``{code: [records]}`` for each state."""
    out = {}
    for code in codes:
        url = OPENSTATES_URL.format(st=code.lower())
        request = urllib.request.Request(url, headers={"User-Agent": "know-your-candidate"})
        # A failed lookup is tried again before it fails the refresh: one
        # missed DNS answer is not a missing file (rule 8).
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    text = response.read().decode("utf-8")
                break
            except OSError as exc:
                if attempt == 2:
                    raise StateLegislatorsError(f"{code}: could not fetch {url}: {exc}") from exc
                time.sleep(5 * (attempt + 1))
        out[code] = parse(text, code)
        time.sleep(pause)
    return out


# ------------------------------------------------------------------ images

# How long an answer about a portrait stands before it is asked again. The
# refresh runs daily near the election; about 6,500 images at a polite pace
# take ten minutes, so each is re-read about once a fortnight.
IMAGE_RECHECK_DAYS = 14


def secure(url):
    """The address a page served over https loads *url* from: browsers
    upgrade an http:// image on such a page, and block it if the upgrade
    fails, so an http:// portrait is only as good as its https:// copy."""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def check_portrait(url, timeout=25):
    """``True`` the address serves an image, ``False`` it definitely does
    not, ``None`` could not tell - ``portraits.check_image``'s tristate, made
    stricter for hosts this project does not know: only a 404 or 410 (how
    Kansas answers for its missing portraits) is ``False``. A 200 that is
    not an image, a refusal (401, 403: a bot wall), a throttle, a server
    error or a failed connection concludes nothing (rule 8):
    Texas's host refused every connection from one machine and served the
    same files to another.

    It asks with GET, never HEAD: Massachusetts answers HEAD for every
    member's portrait with 404 and GET with the image, and South Dakota
    answers HEAD with an HTML page where GET redirects to the photograph.
    The first run asked HEAD first and called 211 working portraits
    missing. Only the headers are read."""
    import urllib.error

    from .portraits import _UA
    try:
        req = urllib.request.Request(url, headers=_UA, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                return None
            ctype = (response.headers.get("Content-Type") or "").lower()
            # A page where an image should be may be a soft 404 or a bot
            # wall's "Request Rejected" with status 200 (rule 52): it
            # concludes nothing.
            return True if ctype.startswith("image") else None
    except urllib.error.HTTPError as exc:
        return False if exc.code in (404, 410) else None
    except Exception:
        return None


def check_images(by_state, previous=None, today=None, check=None, pause=0.5, workers=8):
    """Mark each record's portrait ``imageStatus`` "ok" or "broken", the
    tristate way (``check_portrait``, rule 8): only a definite answer - a
    404 or 410 - is "broken", and a throttled,
    refused or timed-out request leaves the last answer standing, or none.

    Kansas's member pages name portraits the legislature no longer serves
    (123 of 165 failed to load, audit 2026-10-17, STATEGOV-03); the page
    drops a "broken" one rather than drawing nothing in its place. An answer
    younger than ``IMAGE_RECHECK_DAYS`` is carried over from *previous* (the
    last cache) for the same person and address. Requests are spread over
    hosts, one at a time to each, *pause* seconds apart.

    Returns ``{code: {"ok": n, "broken": n, "unknown": n}}``."""
    import concurrent.futures
    import urllib.parse

    from .legislature import search_thumbnail
    check = check or check_portrait
    today = today or datetime.date.today()
    before = {}
    for records in ((previous or {}).get("states") or {}).values():
        for r in records:
            if r.get("imageStatus") and r.get("imageChecked"):
                before[(r["id"], r.get("image"))] = (r["imageStatus"], r["imageChecked"])
    todo = {}
    for records in by_state.values():
        for r in records:
            url = r.get("image")
            if not url or search_thumbnail(url):
                continue
            status, checked = before.get((r["id"], url), (None, None))
            if status:
                r["imageStatus"], r["imageChecked"] = status, checked
                age = (today - datetime.date.fromisoformat(checked)).days
                if age < IMAGE_RECHECK_DAYS:
                    continue
            todo.setdefault(secure(url), []).append(r)
    by_host = {}
    for url in todo:
        by_host.setdefault(urllib.parse.urlsplit(url).hostname or "", []).append(url)

    def run(urls):
        out = {}
        for i, url in enumerate(urls):
            if i and pause:
                time.sleep(pause)
            out[url] = check(url)
        return out

    answers = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(run, [by_host[h] for h in sorted(by_host)]):
            answers.update(result)
    for url, records in todo.items():
        verdict = answers.get(url)
        if verdict is None:
            continue                    # could not tell: the last answer stands
        for r in records:
            r["imageStatus"] = "ok" if verdict else "broken"
            r["imageChecked"] = today.isoformat()
    counts = {}
    for code, records in by_state.items():
        c = counts.setdefault(code, {"ok": 0, "broken": 0, "unknown": 0})
        for r in records:
            if r.get("image") and not search_thumbnail(r["image"]):
                c[r.get("imageStatus") or "unknown"] += 1
    return counts


def save_cache(by_state, root=".", fetched=None):
    """Write the cache. *fetched* keeps the date the roster was read when
    only its portraits were checked again (``statelegs --images-only``)."""
    payload = {
        "source": SOURCE,
        "url": OPENSTATES_URL.format(st="<st>"),
        "fetched": fetched or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "states": {code: sorted(({k: v for k, v in r.items() if k != "imageShared"}
                                 for r in by_state[code]),
                                key=lambda r: (r["chamber"], r["district"], r["name"]))
                   for code in sorted(by_state)},
    }
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        cache = json.load(handle)
    mark_shared_images(cache.get("states") or {})
    return cache


def mark_shared_images(by_state):
    """Mark ``imageShared`` (in memory only; ``save_cache`` drops it) on
    every record whose Open States portrait is the same file as another
    member's of that legislature. One file offered as two members'
    photograph is neither's, as ``legphotos.problems`` already holds for
    the legislature's own: on 2026-10-25 Open States gave Arkansas
    Representative Ashley Hudson (House 75) the file the legislature
    serves for Andrew Collins (House 73), a man's portrait, and the card
    credited it to the Arkansas General Assembly (the PR #133 review)."""
    for records in by_state.values():
        seen = {}
        for r in records:
            r.pop("imageShared", None)
            if r.get("image"):
                seen.setdefault(secure(r["image"]).strip().lower(), []).append(r)
        for group in seen.values():
            if len(group) > 1:
                for r in group:
                    r["imageShared"] = True
    return by_state


# ------------------------------------------------------------------- report

def seats_report(by_state):
    """``{code: {chamber: (listed, seats)}}`` against NCSL's seat counts. A
    seat with nobody listed is "not listed": Open States may be behind a
    special election, so the site does not call it vacant."""
    from .government_maps import SEATS
    out = {}
    for code, records in by_state.items():
        senate, house = SEATS[code]
        counts = {"upper": 0, "lower": 0}
        for r in records:
            if not r.get("tribalSeat"):         # not among NCSL's voting seats
                counts[r["chamber"]] += 1
        out[code] = {"upper": (counts["upper"], senate), "lower": (counts["lower"], house)}
    return out
