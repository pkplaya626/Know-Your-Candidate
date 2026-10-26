"""Portraits of the people on the November ballot, by two more routes tied to
the person (rule 24).

417 of the 585 people on the November ballot for Congress had no portrait
on 2026-10-19: most challengers have no official photograph anywhere, and
they stay without one. The photo research of that day found two routes,
besides the campaign's own site (``enrich``), that reach a photograph
through something the person is already tied to here, never a name:

* **Wikidata, by FEC candidate id** (``wikidata-fec``). An item carrying the
  person's own FEC candidate id (P1839) and an image (P18). An id on
  Wikidata is not proof on its own (rule 82: Judge Whaley's FJC id sat on a
  basketball player's item), so the item must also be a human, the only
  item any of the person's ids is on, and its English label must carry
  their surname *and* one of their given names as the profile or their
  filing writes it ("John \"Drew\" Williams" for "John Andrew Williams",
  "WILLIAMS, JOHN ANDREW"; never "Robert Williams", and never a nickname
  - "Drew Williams" - but through an evidenced
  ``overrides.PORTRAIT_NAME_FORMS`` entry). And it must carry a second tie
  of its own: a year of birth the profile's agrees with, else a 2026
  candidacy in the person's state (P3602), an office held for that state
  (P39, by its label or its electoral district, P768), an official
  website (P856) that is their campaign's site, or an English article that
  is the one their ballot page links (rule 33). A year that disagrees
  refuses it. The file is shown at Wikimedia's standard width (rule 42),
  credited from its own description page (rule 87), and never reached
  through ``Special:FilePath`` (a name).
* **The state legislature, for a sitting legislator** (``state-legislature``).
  A nominee whose own article - the one their ballot page links (rule 33) -
  gives a current seat in their state's legislature, corroborated by
  Wikidata (``history``, rule 69), and whom the legislature's roster
  (``statelegs``) lists in that chamber under the same first and last name,
  alone, is that member. Their photograph is the one the site's own
  legislature page shows on that member's card (``legislature.card_photo``,
  one implementation, rule 12): Open States's file where the legislature
  serves it and no other member shares it, else the legislature's own
  (``legphotos``), and only on the legislature's own host, credited to it
  (rule 87). It is withheld once the roster lists someone else in that
  seat, or the card shows another file: a file keyed by seat ("Sen22.jpg")
  shows whoever holds it.

Not a route yet: a statewide officer's office photograph for an officer on
the ballot for Congress. Ken Paxton (TX Senate) shows the silhouette since
his Commons portrait was refused (someone else in the frame), while the
state page shows his office's photograph as Attorney General. The officers'
cards are matched to an office by state and title, never to a profile, so
the tie would be a third route - their corroborated record of offices
(``history``) naming that office, as ``legislator_for`` does for a seat -
with its own review; it waits for one (the PR #139 review).

Either route refuses a frame wider than tall unless its file is named a
headshot or portrait (rule 38), and a file a person refused in
``overrides.NOT_A_PORTRAIT`` or ``PORTRAIT_LICENCE_DOUBTS``.

A photograph over the caps (300 KB, 1,200 px) is shown smaller from the same
file where Wikimedia's standard widths, its host's resizer or Photon serve it
(rule 87), else at full size, and said either way (``heavy``): the owner's
decision of 2026-10-25 ("more content is better than strict rules") put
coverage before weight, and its weight is never a reason for the
silhouette. Washington's online voters' guide serves its photographs only
base64-encoded inside a JSON answer, and Alaska's and Oregon's pamphlets
only inside PDFs: there is no file to link, so they are kept here as
copies, by the owner's decision of 2026-10-25 (kyc/guide_photos.py, a route
of its own that fills in only where these leave the silhouette).

Every record keeps the page that ties the photograph to the person, the
words that name them (``evidence``), the day it was read, and its bytes and
pixel size; ``validate`` fails a shown one without them. Network reads pace
one request a second per host; a read that fails keeps the last good record
(rule 8), and only a definite answer - the file is gone (404, 410), the page
or item names someone else - takes one away.
"""

import datetime
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from .photos import host_of, lighter_rendition, too_heavy

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


_FEC_ID = re.compile(r"^[HSP]\d[A-Z0-9]{2}\d{5}$")
_GENERATIONAL = {"jr", "sr", "ii", "iii", "iv", "v"}
# A file named for what it is may be wider than tall (rule 38).
_NAMED_LIKENESS = re.compile(r"headshot|portrait|profile", re.I)


def _words(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in _GENERATIONAL]


def fec_ids(profile):
    """The FEC candidate ids a profile holds: its own and any merged in."""
    ids = [profile.get("fecCandidateId")] + list(profile.get("otherFecIds") or [])
    return [i for i in dict.fromkeys(ids) if i and _FEC_ID.match(str(i))]


def today():
    return datetime.date.today().isoformat()


def given_names(profile):
    """The given names the profile and the person's own filing write for
    them (``filedName``, "WILLIAMS, JOHN ANDREW"), folded, without initials:
    ``{"john", "andrew"}``. The surname is not among them."""
    from .candidates import display_name
    from .results import _tokens

    out = set()
    for name in (profile.get("name"), display_name(profile.get("filedName"))):
        words = _tokens(name or "")
        out.update(w for w in words[:-1] if len(w) > 1)
    return out


def given_fits(label, profile):
    """The item's *label* carries one of the person's own given names
    (:func:`given_names`), exactly: its first given name is one of theirs,
    or their first is among its given names. "John \"Drew\" Williams" fits
    "John Andrew Williams"; "Robert Williams", "Robert Andrew Williams" and
    the nickname "Drew Williams" do not. No nickname table and no prefix
    (``results._given_fits`` allows both, for a ballot's spelling of a
    filing already tied to the race): here the label is all that ties a
    Wikidata item to the person besides the id, so a nickname counts only
    through an evidenced ``overrides.PORTRAIT_NAME_FORMS`` entry naming
    that very label for this profile."""
    from . import overrides
    from .results import _tokens

    entry = getattr(overrides, "PORTRAIT_NAME_FORMS", {}).get(profile.get("id")) or {}
    if entry.get("label") and entry["label"] == label and entry.get("evidence"):
        return True
    theirs = [w for w in _tokens(label or "")[:-1] if len(w) > 1]
    mine = given_names(profile)
    first = [w for w in _tokens(profile.get("name") or "")[:-1] if len(w) > 1][:1]
    if not theirs or not mine:
        return False
    return theirs[0] in mine or bool(first and first[0] in theirs)


def surnames(profile):
    """The surname words the profile and the filing write: the profile
    name's last word, and every word of the filing's surname ("GOMEZ
    NORIEGA, VALENTINA" gives both), hyphens parting words."""
    from .results import _tokens

    out = set()
    words = _tokens(str(profile.get("name") or "").replace("-", " "))
    if len(words) > 1:
        out.add(words[-1])
    filed = str(profile.get("filedName") or "")
    if "," in filed:
        out.update(w for w in _tokens(filed.split(",", 1)[0].replace("-", " ") + " x")[:-1]
                   if len(w) > 1)
    return out


def label_names(label, profile):
    """``""`` when the item's *label* ends in the person's surname (as the
    profile or the filing writes it: "John Andrews" is not "John Andrew
    Williams", though "andrew" is in it) and carries a given name of theirs
    (:func:`given_fits`), else why not."""
    from .results import _tokens

    words = _tokens(str(label or "").replace("-", " "))
    if len(words) < 2 or words[-1] not in surnames(profile):
        return f"the item's label {label!r} does not end in their surname"
    if not given_fits(label, profile):
        return f"the item's label {label!r} carries no given name of theirs"
    return ""


def refused_file(*urls):
    """Why a person refused one of *urls* (``NOT_A_PORTRAIT``,
    ``PORTRAIT_LICENCE_DOUBTS``), or ``""``: ``photos.refused``, the one
    test every route asks."""
    from .photos import refused

    return refused(*urls)


def wide_frame(url, weight):
    """A frame wider than it is tall that its file name does not call a
    headshot or portrait (rule 38): a scene, not a likeness."""
    from .legphotos import landscape

    if not weight or not weight.get("width") or not weight.get("height"):
        return False
    name = urllib.parse.unquote(urllib.parse.urlsplit(url or "").path.rsplit("/", 1)[-1])
    return landscape(weight) and not _NAMED_LIKENESS.search(name)


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
    "birth", "human", "election", "website", "office", "district",
    "article"}`` (an item with several of a statement gives a row for
    each; ``article`` is its English Wikipedia title). One query a hundred
    ids."""
    import json

    out = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 100):
        values = " ".join(f'"{x}"' for x in ids[i:i + 100])
        query = ("SELECT ?item ?fec ?label ?img ?birth ?human ?election ?site ?office "
                 "?district ?article WHERE { "
                 "VALUES ?fec { %s } "
                 "?item wdt:P1839 ?fec . OPTIONAL { ?item wdt:P18 ?img } "
                 "OPTIONAL { ?item wdt:P569 ?birth } "
                 "OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label) = \"en\") } "
                 "OPTIONAL { ?item wdt:P31 ?human FILTER(?human = wd:Q5) } "
                 "OPTIONAL { ?item wdt:P3602 ?el . ?el rdfs:label ?election "
                 "FILTER(LANG(?election) = \"en\") } "
                 "OPTIONAL { ?item wdt:P856 ?site } "
                 "OPTIONAL { ?item p:P39 ?held . ?held ps:P39 ?pos . ?pos rdfs:label ?office "
                 "FILTER(LANG(?office) = \"en\") OPTIONAL { ?held pq:P768 ?dist . "
                 "?dist rdfs:label ?district FILTER(LANG(?district) = \"en\") } } "
                 "OPTIONAL { ?article schema:about ?item ; "
                 "schema:isPartOf <https://en.wikipedia.org/> } }" % values)
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
                "human": bool(row.get("human")), "election": row.get("election"),
                "website": row.get("site"), "office": row.get("office"),
                "district": row.get("district"), "article": _article_title(row.get("article"))})
    return out


def _article_title(url):
    """"Fred Wellman" from ``https://en.wikipedia.org/wiki/Fred_Wellman``."""
    if not url or "/wiki/" not in url:
        return None
    return urllib.parse.unquote(url.split("/wiki/", 1)[1]).replace("_", " ")


def states_named(text):
    """The state names *text* carries, the longest first so "West Virginia"
    is never also Virginia (rule 5)."""
    from .pages import STATE_NAMES

    text = f" {text or ''} "
    found = set()
    for name in sorted(STATE_NAMES.values(), key=len, reverse=True):
        pattern = re.compile(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])")
        if pattern.search(text):
            found.add(name)
            text = pattern.sub(" ", text)
    return found


# A tie to a state is a label of one of these whole shapes, with the state's
# name in its slot and no other state named - never the state's name found
# anywhere in it: "Mayor of Kansas City, Missouri" is not an office for
# Kansas, "United States Ambassador to Georgia" is the country's, a district
# "Washington, D.C." is not Washington's, "Mayor of Indiana, Pennsylvania"
# is not Indiana's, and the "2026 New York City Council election" is no race
# for Congress (rule 5; the verifier of PR #134).
_ORDINAL = r"(?:\d+(?:st|nd|rd|th)|at-large)"
_ELECTIONS = (
    r"2026 United States (?:House of Representatives|Senate)(?: special)? elections? in {s}",
    r"2026 {s}'s " + _ORDINAL + r" congressional district(?: special)? election",
)
_CHAMBERS = (r"(?:House of Representatives|House of Delegates|House|Senate|State Senate|"
             r"Assembly|State Assembly|General Assembly|Legislature)")
_STATEWIDE = (r"(?:Governor|Lieutenant Governor|Attorney General|Secretary of State|"
              r"State Treasurer|Treasurer|State Auditor|Auditor|Comptroller|Controller)")
_OFFICES = (
    r"(?:[Mm]ember of the )?{s} " + _CHAMBERS,
    _STATEWIDE + r" of {s}",
    r"{s} " + _STATEWIDE,
)
_US_SENATOR = re.compile(r"(?i)United States senator|member of the United States Senate")
_CONGRESSIONAL = r"{s}'s " + _ORDINAL + r" congressional district"


def _shaped(text, state, shapes):
    """*text* is wholly one of *shapes* with *state* in its slot, and names
    no other state."""
    text = (text or "").strip()
    if not text or not state or states_named(text) != {state}:
        return False
    return any(re.fullmatch(shape.replace("{s}", re.escape(state)), text) for shape in shapes)


def candidacy_for(election, state):
    """*election* is a 2026 election for Congress in *state*."""
    return _shaped(election, state, _ELECTIONS)


def office_for(office, district, state):
    """An office held (P39) for *state*: its electoral district (P768) is
    one of the state's congressional districts, or the state itself for a
    United States senator; else its own label is the state's legislature
    or one of its statewide offices. A district that names another state
    or another place ("Washington, D.C.") refuses whatever the office
    says."""
    office, district = (office or "").strip(), (district or "").strip()
    if district:
        if _shaped(district, state, (_CONGRESSIONAL,)):
            return True
        if district == state and _US_SENATOR.fullmatch(office):
            return True
        if district != state and (states_named(district) != {state} or "," in district):
            return False
    return _shaped(office, state, _OFFICES)


def _site_host(url):
    return host_of(url or "").removeprefix("www.")


def second_tie(profile, rows):
    """``(tie, why)``: what on the item, besides the FEC id, ties it to this
    person - a year of birth the profile's agrees with, a 2026 candidacy in
    their state (P3602, ``candidacy_for``), an office held for their state
    (P39 with its electoral district, P768, ``office_for``), an official website
    (P856) that is their campaign's site, or an English article that is the
    one their ballot page links (rule 33) - or ``None`` and why not. A year
    that disagrees is a refusal whatever else the item says."""
    from .pages import state_name

    births = {(r.get("birth") or "")[:4] for r in rows if r.get("birth")}
    born = str(profile.get("birthdate") or "")[:4]
    if births and born.isdigit():
        if born not in births:
            return None, f"the item's year of birth {sorted(births)} is not the profile's {born}"
        return f"its year of birth, {born}, is the profile's", ""
    state = state_name(profile.get("state"))
    for election in sorted({r.get("election") for r in rows if r.get("election")}):
        if candidacy_for(election, state):
            return f"its candidacy in election (P3602) is \"{election}\"", ""
    offices = sorted({(r.get("office") or "", r.get("district") or "") for r in rows
                      if r.get("office")})
    for office, district in offices:
        if office_for(office, district, state):
            held = f"{office} ({district})" if district else office
            return f"it holds an office for {state} (P39): \"{held}\"", ""
    campaign = _site_host(profile.get("campaignSite"))
    for site in sorted({r.get("website") for r in rows if r.get("website")}):
        if campaign and _site_host(site) == campaign:
            return f"its official website (P856) is the campaign's, {site}", ""
    linked = profile.get("wikipedia")
    for article in sorted({r.get("article") for r in rows if r.get("article")}):
        if linked and profile.get("wikipediaVia") == "election-page" and article == linked:
            return f"its English article is the one their ballot page links, \"{article}\"", ""
    return None, ("nothing on the item but the id ties it to them: no year of birth to "
                  f"compare, no 2026 candidacy or office for {state}, no official website "
                  "that is their campaign's, no article their ballot page links")


def wikidata_choice(profile, rows):
    """``(choice, why)``: the one item and image *rows* give this profile,
    or ``None`` and why not. *rows* are every row of every one of the
    person's FEC ids: ids on two items are refused (rule 25)."""
    items = {r["item"] for r in rows}
    if len(items) != 1:
        return None, f"the person's FEC ids are on {len(items)} Wikidata items"
    if not any(r["human"] for r in rows):
        return None, "the item is not a human"
    images = {r["image"] for r in rows if r.get("image")}
    if len(images) != 1:
        return None, ("the item has no image" if not images else "the item has two images")
    label = next((r["label"] for r in rows if r.get("label")), "")
    why = label_names(label, profile)
    if why:
        return None, why
    tie, why = second_tie(profile, rows)
    if not tie:
        return None, why
    image = images.pop()
    if "Special:FilePath/" not in image:
        return None, "the image is not a Commons file"
    name = urllib.parse.unquote(image.split("Special:FilePath/", 1)[1]).replace("_", " ")
    return {"item": rows[0]["item"], "label": label, "file": name, "tie": tie}, ""


def commons_file(name, api=None):
    """``imageinfo`` for File:*name* on Commons, with a thumbnail at
    :data:`SHOWN_WIDTH` and the licence fields (rule 87), or ``None``."""
    from .portraits import _CREDIT_FIELDS, IIPROP, _api

    try:
        payload = (api or _api)({"prop": "imageinfo", "titles": "File:" + name,
                                 "iiprop": IIPROP, "iiurlwidth": SHOWN_WIDTH,
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


def wikidata_record(profile, fec, choice, info, weight, largest=None):
    """The portrait cache record for a Wikidata route, from the item chosen,
    the file's ``imageinfo`` and the weight of what is shown. *largest* is
    the weight of the widest standard size the srcset would offer above
    it: that size is offered only once weighed within the caps."""
    from .portraits import credit_of, thumb_set

    shown = shown_form(info)
    record = {
        "via": WIKIDATA, "name": profile["name"], "item": choice["item"], "fec": fec,
        "label": choice["label"], "file": "File:" + choice["file"],
        "original": (info.get("url") or "").split("?", 1)[0] or None,
        "page": f"https://www.wikidata.org/wiki/{choice['item']}",
        "tie": choice["tie"],
        "evidence": (f"Wikidata {choice['item']} (\"{choice['label']}\") carries FEC candidate "
                     f"id {fec} (P1839) and the image File:{choice['file']} (P18); "
                     f"{choice['tie']}"),
        "read": today(), "width": info["width"], "height": info["height"],
        "credit": credit_of(info)}
    sizes = thumb_set(shown, info["width"])
    if sizes and sizes[-1][0] > SHOWN_WIDTH and not (largest and not too_heavy(largest)):
        sizes = [s for s in sizes if s[0] <= SHOWN_WIDTH]
    record.update(url=shown, set=sizes)
    if weight:
        record.update(bytes=weight["bytes"], shownWidth=weight["width"],
                      shownHeight=weight["height"])
        if too_heavy(weight):
            record["heavy"] = too_heavy(weight)
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


def card_photo(member, code, page=None, photos=None):
    """``(image, credit, evidence)``: the photograph the site's legislature
    page shows on *member*'s card (``legislature.card_photo``), when the
    legislature serves it and credits it, or the member's own party caucus
    in that chamber does (``legislature.caucus_photo``), or ``(None, None,
    why)``."""
    from . import legphotos
    from .legislature import card_photo as shown_on_card

    shown = shown_on_card(member, code, page, photos)
    image, credit = shown.get("image"), shown.get("imageCredit")
    if not image:
        # An "oversized" entry is not shown here for a reason that is not
        # its weight: legphotos.settle stops at the first sign a file is
        # over the caps, before the checks a seat-keyed file needs (dated
        # on or after the member's arrival, not the file a predecessor
        # showed), so its "offered" file is unchecked as theirs - Nebraska's
        # "dist13.jpg" is named by the seat. It waits for those checks,
        # which legphotos now makes before it takes a heavy file and rule
        # 101's copies show it smaller (rule 100); no nominee on the
        # ballot was affected on 2026-10-25.
        return None, None, f"the legislature page shows no photograph of them ({shown['kind']})"
    caucus = bool(credit and credit.get("caucus"))
    if not credit or not (legphotos.official_host(code, image) or caucus):
        # Only the legislature's file, or the member's own party caucus's
        # credited to it (``legislature.caucus_photo``; the owner,
        # 2026-10-25: "we can credit caucus"): never a file Open States
        # found on a news site, a campaign's or a county party's.
        return None, None, ("the photograph the card shows is on neither the legislature's own "
                            "host nor their caucus's")
    if caucus:
        evidence = (f"the file Open States lists for {member['name']} ({member['id']}), "
                    f"served by the {credit['by']}, their own party's caucus in that chamber")
    elif shown["kind"] == "legislature":
        entry = legphotos.entry_for(member, photos) or {}
        evidence = (f"{entry.get('evidence')} (the legislature's record of {member['name']}, "
                    f"read {entry.get('read')})")
    else:
        evidence = (f"the file Open States lists for {member['name']} ({member['id']}), "
                    f"served by the {credit['by']}")
    return image, credit, evidence


def legislature_record(profile, member, page, image, credit, evidence, weight, lighter=None):
    """The portrait cache record for a legislature route. *image* is the
    file the card shows (``original``); *lighter* is ``(form, its weight)``
    where the file is over the caps and a resizer serves it smaller
    (``photos.lighter_rendition``), and it is then the address shown."""
    shown, shown_weight = lighter or (image, weight)
    record = {
        "via": LEGISLATURE, "name": profile["name"], "page": page, "evidence": evidence,
        "read": today(), "state": member.get("state") or profile["state"],
        "chamber": member.get("chamber"), "district": member.get("district"),
        "legislator": member.get("id"), "legislatorName": member.get("name"),
        "credit": dict(credit), "url": shown, "original": image,
        "bytes": shown_weight["bytes"], "width": shown_weight["width"],
        "height": shown_weight["height"]}
    if too_heavy(weight):
        # Said either way (rule 87): shown smaller, or at full size.
        record["heavy"] = too_heavy(weight) + ("; shown smaller from the same file"
                                               if lighter else "")
        if lighter:
            record["originalWeight"] = dict(weight)
    return record


def roster_member(record, legislators):
    """The roster's entry for this record's member while it still lists
    them in that seat, else ``None``: a file keyed by seat shows whoever
    holds it."""
    roster = ((legislators or {}).get("states") or {}).get(record.get("state")) or []
    for r in roster:
        if (r.get("id") == record.get("legislator") and r.get("chamber") == record.get("chamber")
                and str(r.get("district")) == str(record.get("district"))
                and same_name(record.get("name"), r.get("name"))):
            return r
    return None


def seated(record, legislators):
    """True while the legislature's roster still lists this record's member
    in its seat."""
    return roster_member(record, legislators) is not None


# ------------------------------------------------------------------- routes

def route_ok(profile, record, legislators=None, legislator_photos=None):
    """True when a cached record of one of these routes may stand for this
    profile now; ``portraits.route_ok`` asks here for these routes by name.
    *legislators* (the roster) and *legislator_photos* (the ``legphotos``
    cache) are checked where given: the card must still show this file."""
    if not record.get("url"):
        return True
    if not (record.get("page") and record.get("evidence") and record.get("read")):
        return False
    if refused_file(record.get("url"), record.get("original")):
        return False
    if wide_frame(record["url"], {"width": record.get("shownWidth") or record.get("width"),
                                  "height": record.get("shownHeight") or record.get("height")}):
        return False
    if record.get("via") == WIKIDATA:
        return (record.get("fec") in fec_ids(profile) and bool(record.get("tie"))
                and not label_names(record.get("label") or "", profile))
    if record.get("via") == LEGISLATURE:
        if record.get("state") != profile.get("state"):
            return False
        if legislators is None:
            return True
        member = roster_member(record, legislators)
        if member is None:
            return False
        if legislator_photos is None:
            return True
        image, _credit, _why = card_photo(member, record["state"], None, legislator_photos)
        return image == (record.get("original") or record["url"])
    return False


def wanted(profiles, cache):
    """The people still on the ballot with no portrait by another route.

    A portrait a person refused (``photos.refused``: ``NOT_A_PORTRAIT``,
    ``PORTRAIT_LICENCE_DOUBTS``) is no portrait: withheld at build time, it
    left Jeremy Moss, La Shawn Ford, Adrian Boafo and J.D. Ford with the
    silhouette on their profiles while their legislature's or caucus's
    photograph stood on the legislature page (the PR #139 review), so they
    are asked for by these routes as if they had none."""
    from .enrich import running
    from .portraits import held_back, profile_key

    out = []
    for profile in profiles:
        if not running(profile):
            continue
        record = cache.get(profile_key(profile)) or {}
        if record.get("pinned") or (record.get("url") and record.get("via") not in ROUTES
                                    and not held_back(record)):
            continue
        out.append(profile)
    return out


def _unresolved(profile):
    return {"url": None, "via": "unresolved", "name": profile["name"]}


def resolve_all(profiles, cache, history=None, legislators=None, log=print,
                sparql=None, api=None, getter=None, legislator_photos=None):
    """Look for a portrait by each route for everyone :func:`wanted`, in
    place in the portrait *cache*; returns counts. A route whose source
    cannot be read keeps every record it made before (rule 8)."""
    from .portraits import profile_key, thumb_set

    getter = getter or get
    counts = {"wikidata": 0, "legislature": 0, "heavy": 0, "kept": 0}
    people = wanted(profiles, cache)
    log(f"  nominee portraits: {len(people)} on the ballot with none by another route")
    # What a person refused among what each one's routes offer: the record
    # held before, and any file a route meets now (``replaced``).
    passed = {}

    def passed_over(key, *urls):
        for url in urls:
            if url and url not in passed.setdefault(key, []):
                passed[key].append(url)

    for profile in people:
        key = profile_key(profile)
        record = cache.get(key) or {}
        passed_over(key, *replaced(record))

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
            # Every one of the person's ids together: one first id with no
            # usable item never hides another's, and ids on two items are
            # refused (rule 25).
            hits = [(fec, items[fec]) for fec in fec_ids(profile) if fec in items]
            if not hits:
                if record.get("via") == WIKIDATA:
                    cache[key] = _unresolved(profile)
                continue
            rows = [r for _fec, found in hits for r in found]
            choice, why = wikidata_choice(profile, rows)
            if not choice:
                log(f"    [skip] {profile['name']}: {why}")
                if record.get("via") == WIKIDATA:
                    cache[key] = _unresolved(profile)
                continue
            fec = next(f for f, found in hits if any(r["item"] == choice["item"] for r in found))
            info = commons_file(choice["file"], api=api)
            if not info:
                counts["kept"] += record.get("via") == WIKIDATA
                continue
            shown = shown_form(info)
            weight = weigh(shown, getter) if shown else None
            if weight is False:
                # The file is gone, or is no image: a definite answer.
                if record.get("via") == WIKIDATA:
                    cache[key] = _unresolved(profile)
                continue
            if not weight:
                counts["kept"] += record.get("via") == WIKIDATA
                continue                     # unmeasured: tried again next run
            refused = refused_file(shown, (info.get("url") or "").split("?", 1)[0])
            if refused:
                passed_over(key, (info.get("url") or "").split("?", 1)[0])
            if refused or wide_frame(shown, weight):
                log(f"    [skip] {profile['name']}: "
                    f"{refused or 'a frame wider than tall, not named a headshot (rule 38)'}")
                if record.get("via") == WIKIDATA:
                    cache[key] = _unresolved(profile)
                continue
            # The widest size the srcset would offer is weighed too.
            sizes = thumb_set(shown, info["width"])
            largest = (weigh(sizes[-1][1], getter) or None
                       if sizes and sizes[-1][0] > SHOWN_WIDTH else None)
            new = wikidata_record(profile, fec, choice, info, weight, largest)
            cache[key] = new
            counts["wikidata"] += 1
            counts["heavy"] += bool(new.get("heavy"))

    # The legislature's own photograph, for a sitting member of it: the
    # one its card on this site's legislature page shows.
    if legislators:
        from .legislature import pages_for

        fetched = str(legislators.get("fetched") or "")
        year = int(fetched[:4]) if fetched[:4].isdigit() else datetime.date.today().year
        pages = {}
        for profile in people:
            key = profile_key(profile)
            record = cache.get(key) or {}
            if record.get("url") and record.get("via") == WIKIDATA:
                continue
            member, why = legislator_for(profile, history, legislators)
            if not member:
                if record.get("via") == LEGISLATURE and why.startswith("no corroborated"):
                    cache[key] = _unresolved(profile)
                continue
            code = profile["state"]
            if code not in pages:
                roster = (legislators.get("states") or {}).get(code) or []
                pages[code] = pages_for(code, roster, year)[0]
            page = pages[code].get(member["id"])
            if not page or page.get("kind") not in ("member", "caucus"):
                log(f"    [skip] {profile['name']}: no page of theirs on the legislature's site "
                    "or their caucus's")
                continue
            image, credit, evidence = card_photo(member, code, page, legislator_photos)
            if image and page["kind"] == "caucus" and credit.get("page") != page["url"]:
                # Their page on a caucus's site ties only that caucus's file
                # to them (Sean McCann's senatedems.com page and photograph).
                image, evidence = None, "their caucus page is not the caucus that serves the file"
            if not image:
                log(f"    [skip] {profile['name']}: {evidence}")
                if record.get("via") == LEGISLATURE:
                    cache[key] = _unresolved(profile)
                continue
            weight = weigh(image, getter)
            if weight is False:
                if record.get("via") == LEGISLATURE:
                    cache[key] = _unresolved(profile)
                continue
            if not weight:
                counts["kept"] += record.get("via") == LEGISLATURE
                continue
            refused = refused_file(image)
            if refused:
                passed_over(key, image)
            if refused or wide_frame(image, weight):
                log(f"    [skip] {profile['name']}: "
                    f"{refused or 'a frame wider than tall, not named a headshot (rule 38)'}")
                if record.get("via") == LEGISLATURE:
                    cache[key] = _unresolved(profile)
                continue
            if not credit.get("page"):
                # Credited, and linked to their own page on the legislature's
                # site (rule 87), or not shown.
                log(f"    [skip] {profile['name']}: the card links no page of theirs on the "
                    "legislature's own site")
                continue
            # Over the caps: its host's resizer or Photon, the same file
            # scaled (rule 87); else shown at full size and said.
            lighter = (lighter_rendition(image, weight, lambda u: weigh(u, getter) or None)
                       if too_heavy(weight) else None)
            new = legislature_record(profile, member, credit["page"], image, credit, evidence,
                                     weight, lighter)
            cache[key] = new
            counts["legislature"] += 1
            counts["heavy"] += bool(new.get("heavy"))
    # Each record keeps what a person refused of what that person's routes
    # offered (``replaces``): what it stands in for, which validate's
    # staleness check counts as still offered.
    for key, urls in passed.items():
        if key in cache and cache[key].get("url") not in urls:
            cache[key]["replaces"] = sorted(urls)
    log(f"  nominee portraits: {counts['wikidata']} from Wikidata, {counts['legislature']} "
        f"from a legislature ({counts['heavy']} over the caps, shown all the same), "
        f"{counts['kept']} kept from an earlier read")
    return counts


def replaced(record):
    """The photographs a person refused that a portrait cache *record*
    stands in for: its own address where a person refused it
    (``photos.refused``), and what it says it ``replaces``. A route asked
    again after a refusal can offer a photograph nobody has looked at -
    James Talarico's Wikidata item carried the uncut file of the crop
    refused for someone at its edge - so ``validate`` names any such one
    shown until a person has (``portrait-fallback-unseen``)."""
    from .portraits import held_back

    record = record or {}
    out = list(record.get("replaces") or [])
    if record.get("url") and held_back(record) and record["url"] not in out:
        out.insert(0, record["url"])
    return out


def heavy_shown(profiles, cache):
    """How many people these routes show a photograph of that is over the
    caps and that no resizer served smaller (``heavy`` with no
    ``originalWeight``): shown at full size."""
    from .portraits import profile_key

    return sum(1 for p in profiles if p.get("photoSource") in ROUTES
               and (cache.get(profile_key(p)) or {}).get("heavy")
               and not (cache.get(profile_key(p)) or {}).get("originalWeight"))


def problems(cache):
    """Records of these routes that show a photograph without what ties it
    to the person: its page, the words naming them, the day read, its bytes
    and pixel size, and a note where it is over the caps (validate fails
    each)."""
    out = []
    for key, record in sorted(cache.items()):
        if record.get("via") not in ROUTES or not record.get("url"):
            continue
        missing = [f for f in ("page", "evidence", "read", "bytes") if not record.get(f)]
        if record.get("via") == WIKIDATA:
            missing += [f for f in ("shownWidth", "shownHeight", "tie") if not record.get(f)]
            if not (record.get("credit") or {}).get("licence"):
                missing.append("licence")
        else:
            missing += [f for f in ("width", "height") if not record.get(f)]
        weight = {"bytes": record.get("bytes"),
                  "width": record.get("shownWidth") or record.get("width"),
                  "height": record.get("shownHeight") or record.get("height")}
        if too_heavy(weight) and not record.get("heavy"):
            missing.append("note that it is over the caps")
        if missing:
            out.append(f"{record.get('name')} ({record['via']}): no {', '.join(missing)}")
    return out
