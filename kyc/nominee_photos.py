"""Portraits of the people on the November ballot, by two more routes tied to
the person (rule 24).

417 of the 585 people on the November ballot for Congress had no portrait
on 2026-10-19: most challengers have no official photograph anywhere, and
they stay without one. The photo research of that day found two routes,
besides the campaign's own site (``enrich``), that reach a photograph
through something the person is already tied to here, never a name:

* **Wikidata, by FEC candidate id** (``wikidata-fec``). An item carrying the
  person's own FEC candidate id (P1839) and an image (P18). The id is the
  tie; the item's English label must still carry the surname, the item must
  be a human, and where the item gives a birth year and the profile one, they
  agree (rule 82). One id on two items is refused. The file is shown at
  Wikimedia's standard width (rule 42), credited from its own description
  page (rule 87), and never reached through ``Special:FilePath`` (a name).
* **The state legislature, for a sitting legislator** (``state-legislature``).
  A nominee whose own article - the one their ballot page links (rule 33) -
  gives a current seat in their state's legislature, corroborated by
  Wikidata (``history``, rule 69), and whom the legislature's roster
  (``statelegs``) lists in that chamber under the same first and last name,
  alone, is that member. Their photograph is the image the legislature's own
  page for them draws (``legislature.pages_for``, never a caucus's page,
  rule 51), found on that page either as the file the roster names or by an
  alt text or file name carrying the surname; the page must name them. It is
  withheld once the roster lists someone else in that seat, since a file
  keyed by seat ("Sen22.jpg") shows whoever holds it.

The owner's decision of 2026-10-19: a photograph is used only where its
source itself offers a version within 300 KB and 1,200 px - no resizing, no
image service, no copy of our own. One offered only oversized is left out
(``leftOut``) and the build counts it. Three routes the research found
cannot meet that: Washington's online voters' guide serves its photographs
only base64-encoded inside a JSON answer, and Alaska's and Oregon's pamphlets
only inside PDFs, so none offers an image file to link (``ELECTION_OFFICES``).

Every record keeps the page that ties the photograph to the person, the
words that name them beside it (``evidence``), the day it was read, and its
bytes and pixel size; ``validate`` fails a shown one without them. Network
reads pace one request a second per host; a read that fails keeps the last
good record (rule 8), and only a definite answer - the file is gone (404,
410), the page or item names someone else - takes one away.
"""

import datetime
import html.parser
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from .photos import host_of, too_heavy

WIKIDATA = "wikidata-fec"
LEGISLATURE = "state-legislature"
ROUTES = (WIKIDATA, LEGISLATURE)

SPARQL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia's standard thumbnail width a card needs on a 2x screen (rule 42).
SHOWN_WIDTH = 330
PAUSE = 1.0
TIMEOUT = 30
MAX_IMAGE = 8_000_000
# Wikidata's query service asks for a way to reach whoever sends a query.
UA = {"User-Agent": "know-your-candidate/2.1 (https://candidates.radicalrelay.us; "
                    "open-source civic data project)"}

# What each state's election office offers, and why it is not a route here:
# the research of 2026-10-19 (research/photos/nominees.json) and its check.
ELECTION_OFFICES = {
    "WA": "the online voters' guide (election 899) serves each photograph only "
          "base64-encoded inside candidate.ashx's JSON, never as a file",
    "AK": "the Official Election Pamphlet's candidate statements hold the "
          "photograph only inside each PDF",
    "OR": "the State Voters' Pamphlet holds the photograph only inside the "
          "county PDFs, as JPEG 2000",
}

_FEC_ID = re.compile(r"^[HSP]\d[A-Z0-9]{2}\d{5}$")
_GENERATIONAL = {"jr", "sr", "ii", "iii", "iv", "v"}


def _words(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in _GENERATIONAL]


def fec_ids(profile):
    """The FEC candidate ids a profile holds: its own and any merged in."""
    ids = [profile.get("fecCandidateId")] + list(profile.get("otherFecIds") or [])
    return [i for i in dict.fromkeys(ids) if i and _FEC_ID.match(str(i))]


def today():
    return datetime.date.today().isoformat()


# ------------------------------------------------------------------ network

_last = {}


def _pace(url):
    host = host_of(url)
    wait = PAUSE - (time.monotonic() - _last.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()


def get(url, accept="*/*", limit=MAX_IMAGE):
    """``(status, final url, headers, body)``; status ``None`` when nothing
    answered. One request a second to each host."""
    for attempt in range(2):
        _pace(url)
        try:
            req = urllib.request.Request(url, headers=dict(UA, Accept=accept))
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                return (response.status, response.geturl(), response.headers,
                        response.read(limit + 1))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and not attempt:
                # Asked to slow down: the window it names, once (rule 37).
                wait = (exc.headers.get("Retry-After") if exc.headers else None) or "30"
                time.sleep(min(float(wait) if wait.isdigit() else 30.0, 120.0))
                continue
            return exc.code, url, exc.headers, b""
        except Exception:
            return None, url, {}, b""
    return None, url, {}, b""


def weigh(url, getter=None):
    """``{"bytes", "width", "height"}`` of the image at *url* read whole by
    GET, ``False`` when it is definitely gone (404, 410) or not an image,
    ``None`` when nothing could be told (rule 8; HEAD is not asked, rule 51)."""
    from .portraits import image_size

    status, _final, headers, body = (getter or get)(url, accept="image/*")
    if status in (404, 410):
        return False
    if status != 200:
        return None
    if not str((headers or {}).get("Content-Type") or "").startswith("image/"):
        return False
    size = image_size(body[:600_000])
    if not size or not all(size):
        return None
    length = str((headers or {}).get("Content-Length") or "")
    return {"bytes": int(length) if length.isdigit() else len(body),
            "width": size[0], "height": size[1]}


# ------------------------------------------------------------------ wikidata

def wikidata_items(ids, sparql=None):
    """``{fec id: [row]}`` for every Wikidata item carrying one of *ids* as
    its FEC candidate id (P1839); each row ``{"item", "label", "image",
    "birth", "human"}``. One query a hundred ids."""
    import json

    out = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 100):
        values = " ".join(f'"{x}"' for x in ids[i:i + 100])
        query = ("SELECT ?item ?fec ?label ?img ?birth ?human WHERE { VALUES ?fec { %s } "
                 "?item wdt:P1839 ?fec . OPTIONAL { ?item wdt:P18 ?img } "
                 "OPTIONAL { ?item wdt:P569 ?birth } "
                 "OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label) = \"en\") } "
                 "OPTIONAL { ?item wdt:P31 ?human FILTER(?human = wd:Q5) } }" % values)
        if sparql:
            bindings = sparql(query)
        else:
            url = SPARQL + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
            status, _final, _headers, body = get(url, accept="application/sparql-results+json")
            if status != 200:
                raise RuntimeError(f"Wikidata query answered {status}")
            bindings = json.loads(body.decode("utf-8"))["results"]["bindings"]
        for b in bindings:
            row = {k: v.get("value") for k, v in b.items()}
            out.setdefault(row["fec"], []).append({
                "item": row["item"].rsplit("/", 1)[-1], "label": row.get("label"),
                "image": row.get("img"), "birth": row.get("birth"),
                "human": bool(row.get("human"))})
    return out


def wikidata_choice(profile, rows):
    """``(choice, why)``: the one item and image *rows* give this profile,
    or ``None`` and why not."""
    from .portraits import title_is_about

    items = {r["item"] for r in rows}
    if len(items) != 1:
        return None, f"the FEC id is on {len(items)} Wikidata items"
    if not any(r["human"] for r in rows):
        return None, "the item is not a human"
    images = {r["image"] for r in rows if r.get("image")}
    if len(images) != 1:
        return None, ("the item has no image" if not images else "the item has two images")
    label = next((r["label"] for r in rows if r.get("label")), "")
    if not label or not title_is_about(label, profile["name"]):
        return None, f"the item's label {label!r} does not carry the surname"
    births = {(r.get("birth") or "")[:4] for r in rows if r.get("birth")}
    born = str(profile.get("birthdate") or "")[:4]
    if births and born.isdigit() and born not in births:
        return None, f"the item's year of birth {sorted(births)} is not the profile's {born}"
    image = images.pop()
    if "Special:FilePath/" not in image:
        return None, "the image is not a Commons file"
    name = urllib.parse.unquote(image.split("Special:FilePath/", 1)[1]).replace("_", " ")
    return {"item": rows[0]["item"], "label": label, "file": name}, ""


def commons_file(name, api=None):
    """``imageinfo`` for File:*name* on Commons, with a thumbnail at
    :data:`SHOWN_WIDTH` and the licence fields (rule 87), or ``None``."""
    from .portraits import _CREDIT_FIELDS, _api

    try:
        payload = (api or _api)({"prop": "imageinfo", "titles": "File:" + name,
                                 "iiprop": "size|url|extmetadata", "iiurlwidth": SHOWN_WIDTH,
                                 "iiextmetadatafilter": _CREDIT_FIELDS},
                                endpoint=COMMONS_API)
    except Exception:
        return None
    for page in (payload.get("query") or {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("width"):
            return info
    return None


def shown_form(info):
    """The address shown for a Commons file: its standard thumbnail at
    :data:`SHOWN_WIDTH`, or the original where it is no wider - without
    the tracking query the API appends, which no srcset entry carries."""
    url = info.get("thumburl") if info.get("width", 0) > SHOWN_WIDTH else info.get("url")
    return url.split("?", 1)[0] if url else None


def wikidata_record(profile, fec, choice, info, weight):
    """The portrait cache record for a Wikidata route, from the item chosen,
    the file's ``imageinfo`` and the weight of what is shown."""
    from .portraits import credit_of, thumb_set

    shown = shown_form(info)
    record = {
        "via": WIKIDATA, "name": profile["name"], "item": choice["item"], "fec": fec,
        "label": choice["label"], "file": "File:" + choice["file"],
        "page": f"https://www.wikidata.org/wiki/{choice['item']}",
        "evidence": (f"Wikidata {choice['item']} (\"{choice['label']}\") carries FEC candidate "
                     f"id {fec} (P1839) and the image File:{choice['file']} (P18)"),
        "read": today(), "width": info["width"], "height": info["height"],
        "credit": credit_of(info)}
    if weight and too_heavy(weight):
        record.update(url=None, leftOut={"url": shown, "why": too_heavy(weight)})
        return record
    record.update(url=shown, set=thumb_set(shown, info["width"]))
    if weight:
        record.update(bytes=weight["bytes"], shownWidth=weight["width"],
                      shownHeight=weight["height"])
    return record


# ---------------------------------------------------------------- legislature

def chamber_of(office):
    """``"upper"`` / ``"lower"`` for a state legislative office's label, or
    ``None``: Nebraska's one-chamber Legislature, and any label that does not
    say, are not guessed at (rule 69)."""
    text = str(office or "").lower()
    if "senate" in text:
        return "upper"
    if re.search(r"\bhouse\b|\bassembly\b|\bdelegates\b", text):
        return "lower"
    return None


def held_seats(profile, history):
    """``{(state, chamber)}`` the person's corroborated record of offices
    (``history``, rule 69) says they hold now in their own state's
    legislature."""
    from .pages import state_name

    entry = ((history or {}).get("people") or {}).get(profile.get("id")) or {}
    linked = entry.get("asked") or entry.get("wikipedia")
    if not linked or linked != profile.get("wikipedia"):
        return set()                 # read from an article the profile no longer links
    state = profile.get("state")
    out = set()
    for office in entry.get("offices") or []:
        label = office.get("office") or ""
        if (office.get("open") and office.get("where") == state_name(state)
                and office.get("agree") in ("exact", "year-off")
                and re.search(r"legislat|senate|house|assembly|delegates", label, re.I)
                and "United States" not in label):
            chamber = chamber_of(label)
            if chamber:
                out.add((state, chamber))
    return out


def same_name(name, other):
    """First and last name the same, after folding accents, initials and
    suffixes: "Martin R Zamora" and "Martin Zamora"."""
    a, b = _words(name), _words(other)
    a = [w for w in a if len(w) > 1]
    b = [w for w in b if len(w) > 1]
    return bool(a and b) and a[0] == b[0] and a[-1] == b[-1]


def legislator_for(profile, history, legislators):
    """``(record, why)``: the one sitting member of the profile's state
    legislature who is this person - the chamber their corroborated record
    gives, the same first and last name, nobody else of that name in the
    chamber - or ``None`` and why not. Never a name across states (rule 3)."""
    seats = held_seats(profile, history)
    if not seats:
        return None, "no corroborated seat in the state legislature"
    roster = ((legislators or {}).get("states") or {}).get(profile.get("state")) or []
    found = [r for r in roster if (r.get("state") or profile["state"], r.get("chamber")) in seats
             and same_name(profile["name"], r.get("name"))]
    if len(found) != 1:
        return None, f"{len(found)} members of that chamber carry the name"
    return found[0], ""


class _Images(html.parser.HTMLParser):
    """Every image on a page, with its alt text, and the page's words."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images, self.text, self._skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "img":
            self.images.append((a.get("src") or a.get("data-src") or "",
                                a.get("alt") or a.get("title") or ""))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


_NOT_A_LIKENESS = re.compile(r"seal|logo|icon|banner|map|district|flag|social|facebook|twitter|"
                             r"instagram|youtube|email|newsletter|widget|arrow|button", re.I)


def _same_file(a, b):
    """Two addresses of one file: the same path on the same host, whatever
    the scheme or "www."."""
    pa, pb = urllib.parse.urlsplit(a or ""), urllib.parse.urlsplit(b or "")
    return host_of(a).removeprefix("www.") == host_of(b).removeprefix("www.") \
        and pa.path.lower() == pb.path.lower() and bool(pa.path)


def image_on_page(markup, base, member, listed=None):
    """``(image url, evidence)``: the member's photograph on their page, or
    ``(None, why)``.

    The page must name them (the surname, as a word). The image is the file
    the roster lists for them, or one the page names them beside - their
    surname in its alt text or file name - that is no seal, logo or map.
    Only an address on the legislature's host page itself is considered."""
    from .portraits import surname_of

    parser = _Images()
    try:
        parser.feed(markup or "")
        parser.close()
    except Exception:
        pass
    surname = surname_of(member)
    text = " ".join(" ".join(parser.text).split())
    if not surname or surname not in _words(text):
        return None, "the page does not name them"
    for src, alt in parser.images:
        if not src or src.startswith("data:"):
            continue
        url = urllib.parse.urljoin(base, src.strip())
        name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        if _NOT_A_LIKENESS.search(name) or _NOT_A_LIKENESS.search(alt):
            continue
        if listed and (_same_file(url, listed)
                       or name.lower() == urllib.parse.unquote(listed.rsplit("/", 1)[-1]).lower()):
            said = f'alt text "{" ".join(alt.split())}"' if alt.strip() else "no alt text"
            return url, (f"the file the roster lists for them, on their page ({said}), "
                         f"which names {member}")
        if surname in _words(alt):
            return url, f'alt text "{" ".join(alt.split())}" on their page'
        if surname in _words(re.sub(r"\.\w+$", "", name)):
            return url, f'file name "{name}" on their page'
    return None, "no image on the page is named for them"


def secure(url):
    """An http:// image as https://; a page served over https draws it so
    (rule 51), and one that answers only over http is not taken."""
    return "https://" + url[len("http://"):] if str(url).startswith("http://") else url


def legislature_record(profile, member, page, image, evidence, weight):
    """The portrait cache record for a legislature route."""
    from .government_maps import legislature_title

    record = {
        "via": LEGISLATURE, "name": profile["name"], "page": page, "evidence": evidence,
        "read": today(), "state": member.get("state") or profile["state"],
        "chamber": member.get("chamber"), "district": member.get("district"),
        "legislator": member.get("id"), "legislatorName": member.get("name"),
        "credit": {"by": legislature_title(profile["state"]), "page": page}}
    if too_heavy(weight):
        record.update(url=None, leftOut={"url": image, "why": too_heavy(weight)})
        return record
    record.update(url=image, bytes=weight["bytes"], width=weight["width"],
                  height=weight["height"])
    return record


def seated(record, legislators):
    """True while the legislature's roster still lists this record's member
    in its seat: a file keyed by seat shows whoever holds it."""
    roster = ((legislators or {}).get("states") or {}).get(record.get("state")) or []
    return any(r.get("id") == record.get("legislator") and r.get("chamber") == record.get("chamber")
               and str(r.get("district")) == str(record.get("district"))
               and same_name(record.get("name"), r.get("name")) for r in roster)


# ------------------------------------------------------------------- routes

def route_ok(profile, record, legislators=None):
    """True when a cached record of one of these routes may stand for this
    profile now; ``portraits.route_ok`` asks here for these routes by name."""
    from .portraits import title_is_about

    if not record.get("url"):
        return True
    if not (record.get("page") and record.get("evidence") and record.get("read")):
        return False
    if record.get("via") == WIKIDATA:
        return (record.get("fec") in fec_ids(profile)
                and title_is_about(record.get("label") or "", profile["name"]))
    if record.get("via") == LEGISLATURE:
        if record.get("state") != profile.get("state"):
            return False
        return legislators is None or seated(record, legislators)
    return False


def wanted(profiles, cache):
    """The people still on the ballot with no portrait by another route."""
    from .enrich import running
    from .portraits import profile_key

    out = []
    for profile in profiles:
        if not running(profile):
            continue
        record = cache.get(profile_key(profile)) or {}
        if record.get("pinned") or (record.get("url") and record.get("via") not in ROUTES):
            continue
        out.append(profile)
    return out


def resolve_all(profiles, cache, history=None, legislators=None, log=print,
                sparql=None, api=None, getter=None):
    """Look for a portrait by each route for everyone :func:`wanted`, in
    place in the portrait *cache*; returns counts. A route whose source
    cannot be read keeps every record it made before (rule 8)."""
    from .legislature import pages_for
    from .portraits import profile_key

    getter = getter or get
    counts = {"wikidata": 0, "legislature": 0, "leftOut": 0, "kept": 0}
    people = wanted(profiles, cache)
    log(f"  nominee portraits: {len(people)} on the ballot with none by another route")

    # Wikidata, by the person's own FEC id.
    by_fec = {fec: p for p in people for fec in fec_ids(p)}
    try:
        items = wikidata_items(list(by_fec), sparql=sparql)
    except Exception as exc:
        log(f"    [warn] Wikidata could not be read ({exc}); its records are kept")
        items = None
    if items is not None:
        for profile in people:
            key = profile_key(profile)
            record = cache.get(key) or {}
            hits = [(fec, items[fec]) for fec in fec_ids(profile) if fec in items]
            if not hits:
                if record.get("via") == WIKIDATA:
                    cache[key] = {"url": None, "via": "unresolved", "name": profile["name"]}
                continue
            fec, rows = hits[0]
            choice, why = wikidata_choice(profile, rows)
            if not choice:
                log(f"    [skip] {profile['name']}: {why}")
                if record.get("via") == WIKIDATA:
                    cache[key] = {"url": None, "via": "unresolved", "name": profile["name"]}
                continue
            info = commons_file(choice["file"], api=api)
            if not info:
                counts["kept"] += record.get("via") == WIKIDATA
                continue
            shown = shown_form(info)
            weight = weigh(shown, getter) if shown else None
            if weight is False:
                continue
            new = wikidata_record(profile, fec, choice, info, weight or None)
            if new.get("url") and not weight:
                counts["kept"] += record.get("via") == WIKIDATA
                continue                     # unmeasured: tried again next run
            cache[key] = new
            counts["wikidata" if new.get("url") else "leftOut"] += 1

    # The legislature's own photograph, for a sitting member of it.
    if legislators:
        pages = {}
        for code, roster in (legislators.get("states") or {}).items():
            pages[code] = pages_for(code, roster, datetime.date.today().year)[0]
        for profile in people:
            key = profile_key(profile)
            record = cache.get(key) or {}
            if record.get("url") and record.get("via") == WIKIDATA:
                continue
            member, why = legislator_for(profile, history, legislators)
            if not member:
                if record.get("via") == LEGISLATURE and why.startswith("no corroborated"):
                    cache[key] = {"url": None, "via": "unresolved", "name": profile["name"]}
                continue
            page = (pages.get(profile["state"]) or {}).get(member["id"])
            if not page or page.get("kind") != "member":
                log(f"    [skip] {profile['name']}: no page of theirs on the legislature's site")
                continue
            status, final, _headers, body = getter(page["url"], accept="text/html",
                                                   limit=2_000_000)
            if status != 200:
                counts["kept"] += record.get("via") == LEGISLATURE
                continue
            image, evidence = image_on_page(body.decode("utf-8", "replace"), final,
                                            member["name"], member.get("image"))
            if not image:
                log(f"    [skip] {profile['name']}: {evidence}")
                continue
            image = secure(image)
            weight = weigh(image, getter)
            if weight is False:
                if record.get("via") == LEGISLATURE:
                    cache[key] = {"url": None, "via": "unresolved", "name": profile["name"]}
                continue
            if not weight:
                counts["kept"] += record.get("via") == LEGISLATURE
                continue
            new = legislature_record(profile, member, page["url"], image, evidence, weight)
            cache[key] = new
            counts["legislature" if new.get("url") else "leftOut"] += 1
    log(f"  nominee portraits: {counts['wikidata']} from Wikidata, {counts['legislature']} "
        f"from a legislature, {counts['leftOut']} left out (offered only oversized), "
        f"{counts['kept']} kept from an earlier read")
    return counts


def left_out(profiles, cache):
    """How many people on the ballot these routes found a photograph of and
    left out because its source offers it only oversized."""
    from .portraits import profile_key

    return sum(1 for p in profiles if not p.get("photoSource")
               and (cache.get(profile_key(p)) or {}).get("via") in ROUTES
               and (cache.get(profile_key(p)) or {}).get("leftOut"))


def problems(cache):
    """Records of these routes that show a photograph without what ties it
    to the person: its page, the words naming them, the day read, its bytes
    and pixel size (validate fails each)."""
    out = []
    for key, record in sorted(cache.items()):
        if record.get("via") not in ROUTES or not record.get("url"):
            continue
        missing = [f for f in ("page", "evidence", "read", "bytes") if not record.get(f)]
        if record.get("via") == WIKIDATA:
            missing += [f for f in ("shownWidth", "shownHeight") if not record.get(f)]
            if not (record.get("credit") or {}).get("licence"):
                missing.append("licence")
        else:
            missing += [f for f in ("width", "height") if not record.get(f)]
        weight = {"bytes": record.get("bytes"),
                  "width": record.get("shownWidth") or record.get("width"),
                  "height": record.get("shownHeight") or record.get("height")}
        if too_heavy(weight):
            missing.append("within the caps")
        if missing:
            out.append(f"{record.get('name')} ({record['via']}): no {', '.join(missing)}")
    return out
