"""The election offices' own guides' photographs, kept here as unmodified
copies (rules 24, 87, 91 and 101).

Each election office below prints the photograph a candidate gave it beside
the candidate's name for that office, which ties it to the person (rule 24),
but offers no image address to link:

* **Washington's online voters' guide** (VoteWA, election 899) serves each
  photograph only base64-encoded inside its ``candidate.ashx`` answer, in
  the same statement record as the candidate's ballot name, party and race.
* **Alaska's Official Election Pamphlet** has each candidate's statement as
  a PDF, linked beside the candidate's name on the Division of Elections'
  candidate list; the statement's heading names the office and the
  candidate, and the page draws one photograph.
* **Oregon's State Voters' Pamphlet** is one PDF book per county, each page
  two candidates in two columns, the photograph at the head of each under
  the office's heading, the name beside it in large type. Its images are
  JPEG 2000, which no browser draws: each is decoded losslessly here
  (:mod:`kyc.jpx`, standard library only - the reversible coding gives back
  every pixel as coded, and on 2026-10-25 they matched Chrome's own PDF
  renderer one for one) and kept as a PNG (method "decoded").

On 2026-10-25 the owner allowed this site to host such official photographs
as unmodified copies, credited and sourced ("more content is better than
strict rules"), and to show one over the caps as a smaller copy made the way
rule 101 makes them. Nothing else is relaxed: the photograph is joined to a
person only where the guide's own page names them beside it, for that
office, in the words of their filing, their profile or the election office's
list - any order, never a surname alone, a short form only through an
evidenced ``overrides.GUIDE_NAME_FORMS`` entry - and only where that name
fits exactly one person in the race and the person exactly one name in the
guide (rules 25 and 62: Alaska's Senate race holds Dan S. Sullivan and
Daniel J. Sullivan Jr., each with a statement of his own, told apart only by
the middle initial and the suffix). It passes the likeness test every route
does (a head-and-shoulders frame, nothing in ``overrides.NOT_A_PORTRAIT`` or
``PORTRAIT_LICENCE_DOUBTS``: ``photos.refused``); a PDF page that draws two
photographs, or none, gives none; and an image the browser would not draw as
the guide does gives none: Bill Hill's statement holds a CMYK JPEG with an
Adobe marker, which Chrome draws inverted, and re-encoding it would be a
picture this site made, not the guide's.

``python build_profile_site.py guidephotos`` reads the guides for whoever the
last build showed with no photograph (the November ballot's people in these
states, and the statewide candidates), writes each joined photograph's bytes
to ``photos/`` named by their hash and lists it in rule 101's manifest
(``data/photo_copies.json``, ``hosted``: its method, the guide's page and the
JSON or PDF address, sha256, bytes, pixel size, the day read and whom it
shows; for a decoded one, the codestream's hash and the decoder), and keeps the join here, in ``data/guide_photos.json``, with
the guide's words and the day read. The build shows it only where no other
route gives the person a photograph, and only while the join still holds.
A guide that cannot be read keeps its last photographs (rule 8).
"""

import base64
import datetime
import hashlib
import html
import json
import os
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

from . import pdfread, tls

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "guide_photos.json")
ROUTE = "election-guide"
PAUSE = 1.0
TIMEOUT = 60
MAX_JSON = 32 * 1024 * 1024
MAX_PDF = 32 * 1024 * 1024
UA = {"User-Agent": "Mozilla/5.0 (compatible; know-your-candidate/2.1; civic data project)"}

WA_INDEX = "https://voter.votewa.gov/elections/voterguide.ashx?e=899&la=en&c=99&p=XX"
WA_RECORD = "https://voter.votewa.gov/elections/candidate.ashx?e=899&r={race}&b=0&la=en&c=XX"
WA_PAGE = "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99#/candidates/{race}/{ballot}"
AK_LIST = "https://www.elections.alaska.gov/candidates/?election=26genr"

# Each guide: who publishes it, the words its credit prints, and its terms
# as the research of 2026-10-19 read them (research/photos/nominees.checked.json).
# The credit says where the photograph was found, not whose it is: the
# candidates submit them ("Candidates submit their statements", Washington's
# guide; Oregon's pamphlet the same), and "Photo: Washington Secretary of
# State" read as the office's own photograph (the review of PR #138, as rule
# 101's "Photo: from" a host). A decoded file says this site made it.
GUIDES = {
    "WA": {
        "by": "Washington Secretary of State",
        "credit": "from the Washington Secretary of State's voters' guide",
        "title": "Online voters' guide, November 3, 2026 General Election",
        "url": "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99",
        "terms": "The guide's footer reads 'Copyright (c) 2026 Washington Secretary of State'; "
                 "the office's web policy says third-party photographs are 'copyrighted by "
                 "others' and used with their holders' permission. Hosted unmodified, "
                 "credited and linked, by the owner's decision of 2026-10-25.",
    },
    "AK": {
        "by": "Alaska Division of Elections",
        "credit": "from the Alaska Division of Elections' Official Election Pamphlet",
        "title": "Candidates - Division of Elections: 2026 General Election (Official "
                 "Candidate Statements)",
        "url": AK_LIST,
        "terms": "The elections site carries 'Copyright (c) 2026 Alaska Division of "
                 "Elections'; its disclaimer grants no reuse. Hosted unmodified, credited "
                 "and linked, by the owner's decision of 2026-10-25.",
    },
    "OR": {
        "by": "Oregon Secretary of State",
        "credit": "from the Oregon Secretary of State's State Voters' Pamphlet",
        "converted": "converted by this site to PNG from the pamphlet's JPEG 2000 image, "
                     "pixel for pixel",
        "title": "State Voters' Pamphlet, General Election November 3, 2026 (one book per "
                 "county)",
        "url": "https://sos.oregon.gov/elections/Voters-Pamphlet/Pages/Voters-Pamphlet-English.aspx",
        "terms": "Oregon's general terms grant no reuse; the photographs are the "
                 "candidates' own submissions. The pamphlet holds each as JPEG 2000, which "
                 "no browser draws: decoded losslessly here (kyc/jpx.py, the reversible "
                 "5/3 wavelet, every pixel as coded) and hosted as PNG, credited and linked "
                 "to its page, by the owner's decision of 2026-10-25.",
    },
}

OR_INDEX = GUIDES["OR"]["url"]
OR_BOOK = re.compile(r"^/elections/Voters-Pamphlet/Documents/VP_G\d{2}-Book\w+_web\.pdf$")

# Guides read and not used, and why: what a later version may take up.
ELSEWHERE = {}

# The offices a guide prints, as this site keys them: a profile's race
# (``H-WA-04-2026``, ``S-AK-2026``) or a statewide office (rule 91).
OFFICE_WORDS = {
    "house": "United States Representative",
    "senate": "United States Senator",
    "governor": "Governor",
    "lt": "Lieutenant Governor",
}

_SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
_TITLES = {"dr", "mr", "mrs", "ms", "hon", "honorable", "dvm", "md", "phd", "esq", "rev"}


class GuidePhotoError(RuntimeError):
    """A guide that cannot be read: concludes nothing (rule 8)."""


def today():
    return datetime.date.today().isoformat()


def is_hosted(url):
    """Whether *url* is a file this site hosts under ``photos/``."""
    from .photocopies import is_hosted as hosted
    return hosted(url)


# ------------------------------------------------------------------ names

def name_words(name, filed=False):
    """A name's folded words, sorted, so any order is the same name: a list's
    "Sullivan, Daniel J. Jr." and a page's "Daniel J. Sullivan Jr." are
    ``("daniel", "j", "sullivan")``. A quoted nickname, a closing suffix and
    a title or credential are not words of it; an initial is (it is what
    tells the two Alaska Sullivans apart). *filed* reads an FEC filed form
    ("KAHL, BARBARA J DR DVM")."""
    from .statewide import display_name, tokens
    text = str(name or "")
    if filed:
        from .candidates import display_name as filed_name
        text = filed_name(text)
    elif "," in text:
        text = display_name(text)
    words = [w for w in tokens(text) if w not in _TITLES]
    while len(words) > 2 and words[-1] in _SUFFIX:
        words.pop()
    return tuple(sorted(words))


def person_words(profile):
    """Every form of a profile's name a guide's name may be: the name the
    site shows (the results page's or the certified list's, rules 62 and
    77) and the filing's."""
    out = {name_words(profile.get("name"))}
    if profile.get("filedName"):
        out.add(name_words(profile["filedName"], filed=True))
    return {w for w in out if len(w) >= 2}


def evidenced_form(code, printed):
    """The person a guide's printed name stands for by an evidenced
    ``overrides.GUIDE_NAME_FORMS`` entry, or None."""
    from . import overrides
    entry = getattr(overrides, "GUIDE_NAME_FORMS", {}).get((code, printed))
    return entry[0] if entry else None


def join(code, entries, people, key_of, words_of):
    """``({entry index: person key}, problems)``: each guide entry of one race
    or office joined to the one person whose name it is.

    *entries* are the guide's ``{"name"}`` dicts for one race; *people* the
    site's people in it; *key_of(person)* the key a photograph is kept for;
    *words_of(person)* the name forms (:func:`person_words`). A name joins
    only where its words are one of the person's forms, or an evidenced
    ``GUIDE_NAME_FORMS`` entry names the person's key - and only where it
    fits one person, and that person one name (rules 25, 62)."""
    out, problems = {}, []
    fits = {}
    for i, entry in enumerate(entries):
        mine = name_words(entry["name"])
        named = evidenced_form(code, entry["name"])
        hits = [p for p in people
                if (len(mine) >= 2 and mine in words_of(p)) or (named and named == key_of(p))]
        if len(hits) > 1:
            problems.append(f"{code}: the guide's '{entry['name']}' fits "
                            f"{len(hits)} people in the race; not joined (rule 25)")
            continue
        if hits:
            fits.setdefault(key_of(hits[0]), []).append(i)
        else:
            # Said where someone in the race carries its surname: a short
            # form a person may record, with evidence, or a namesake.
            from .statewide import fold, surname
            family = fold(surname(entry["name"]))
            alike = [key_of(p) for p in people if any(family in w for w in words_of(p))]
            if family and alike:
                problems.append(f"{code}: the guide's '{entry['name']}' shares a surname with "
                                f"{', '.join(alike)} but is not their name (a short form needs "
                                "an evidenced overrides.GUIDE_NAME_FORMS entry); not joined")
    for key, found in fits.items():
        if len(found) > 1:
            problems.append(f"{code}: {len(found)} of the guide's names fit {key}; "
                            "not joined (rule 25)")
            continue
        out[found[0]] = key
    return out, problems


# ------------------------------------------------------------------ images

def jpeg_info(data):
    """``{"components", "adobe", "progressive"}`` from a JPEG's markers, or
    None when *data* is no JPEG. *adobe* is the APP14 colour transform, or
    None where there is no Adobe marker."""
    if data[:3] != b"\xff\xd8\xff":
        return None
    out = {"components": None, "adobe": None, "progressive": False}
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            return None
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        length = int.from_bytes(data[pos + 2:pos + 4], "big")
        body = data[pos + 4:pos + 2 + length]
        if marker == 0xEE and body[:5] == b"Adobe" and len(body) >= 12:
            out["adobe"] = body[11]
        if marker in (0xC0, 0xC1, 0xC2) and len(body) >= 6:
            out["components"] = body[5]
            out["progressive"] = marker == 0xC2
        if marker == 0xDA:
            break
        pos += 2 + length
    return out if out["components"] else None


def drawable(data, colour_space=None):
    """Why a browser would not draw *data* as its guide does, or ``""``: one
    the reader's browser draws as it is - a JPEG of one component (grey) or
    three (colour), with no CMYK or Adobe CMYK marker, or a PNG. A PDF's
    image must also be in DeviceGray or DeviceRGB (*colour_space*): an
    ICC-based or CMYK one is drawn by the PDF's own colour management, which
    the bytes alone do not carry."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "" if colour_space in (None, "DeviceGray", "DeviceRGB") else \
            f"a PNG in {colour_space}"
    info = jpeg_info(data)
    if not info:
        return "not a JPEG or PNG"
    if info["components"] == 4 or colour_space == "DeviceCMYK":
        return ("a CMYK JPEG" + (" with an Adobe marker (transform "
                                 f"{info['adobe']})" if info["adobe"] is not None else "")
                + ": a browser draws it inverted or off-colour, not as the guide prints it")
    if info["components"] not in (1, 3):
        return f"a JPEG of {info['components']} components"
    if colour_space not in (None, "DeviceGray", "DeviceRGB"):
        return f"an image in {colour_space}, which the bytes alone do not carry"
    if colour_space == "DeviceGray" and info["components"] != 1:
        return "a DeviceGray image whose JPEG has colour components"
    return ""


def measure(data):
    """``{"bytes", "width", "height", "type", "sha256"}`` of an image's bytes."""
    from .portraits import image_size
    size = image_size(data) or (None, None)
    kind = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
    return {"bytes": len(data), "width": size[0], "height": size[1], "type": kind,
            "sha256": hashlib.sha256(data).hexdigest()}


def unfit(weight, *addresses):
    """Why a photograph fails the likeness test every route asks, or ``""``:
    a frame wider than tall or too small to be a head and shoulders
    (rule 38), or one a person refused (``photos.refused``)."""
    from .official_photos import portrait_shaped
    from .photos import refused
    if not portrait_shaped(weight):
        return (f"a {weight.get('width')}x{weight.get('height')} frame is not a "
                "head-and-shoulders portrait (rule 38)")
    return refused(*addresses)


def own_addresses(code, page, photo):
    """The addresses a person's refusal of this photograph is keyed on
    (``photos.refused``): the hosted file, and the guide's page where that
    page is one candidate's - Washington's candidate page, Alaska's statement
    PDF. Never an address several candidates share: Washington's
    ``candidate.ashx`` answers for the whole race, and an Oregon page
    (``book#page=N``) holds two columns and its book every county's
    candidates, so an entry keyed on either would withdraw someone else's
    photograph (the review of PR #138)."""
    return (photo,) if code == "OR" else (page, photo)


def hosted_name(weight):
    ext = "png" if weight["type"] == "image/png" else "jpg"
    return f"{weight['sha256'][:20]}.{ext}"


# ------------------------------------------------------------------ network

_LAST = {}


def _pace(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    wait = _LAST.get(host, 0) + PAUSE - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _LAST[host] = time.monotonic()


def get(url, limit=MAX_JSON):
    """The bytes at *url*; ``GuidePhotoError`` when it cannot be read. A name
    this machine's resolver cannot look up is looked up again at dns.google
    before the read is given up (rule 78: this machine's resolver failed for
    oregon.gov on 2026-10-25 while dns.google answered), and the server is
    then asked at that address, its certificate checked for the name.
    Alaska's server sends the wrong intermediate certificate; the context
    completes its chain from the certificate's own issuer (kyc/tls.py)."""
    _pace(url)
    try:
        request = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(request, timeout=TIMEOUT,
                                    context=tls.context()) as response:
            data = response.read(limit + 1)
    except urllib.error.URLError as exc:
        import socket
        if not isinstance(getattr(exc, "reason", None), socket.gaierror):
            raise GuidePhotoError(f"could not read {url}: {exc}") from exc
        data = _get_resolved(url, limit)
    except (OSError, ValueError) as exc:
        raise GuidePhotoError(f"could not read {url}: {exc}") from exc
    if len(data) > limit:
        raise GuidePhotoError(f"{url} is over {limit} bytes")
    return data


def _address(host):
    """*host*'s IPv4 address as dns.google gives it, or None."""
    query = "https://dns.google/resolve?name=" + urllib.parse.quote(host) + "&type=A"
    try:
        with urllib.request.urlopen(urllib.request.Request(query, headers=UA),
                                    timeout=15, context=tls.context()) as response:
            answer = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for record in answer.get("Answer") or ():
        if record.get("type") == 1:
            return record.get("data")
    return None


def _get_resolved(url, limit, hops=5):
    import http.client
    import socket

    for _ in range(hops):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise GuidePhotoError(f"could not read {url}: not an https address")
        address = _address(parts.hostname)
        if not address:
            raise GuidePhotoError(f"could not read {url}: {parts.hostname} does not resolve "
                                  "here or at dns.google")

        class Pinned(http.client.HTTPSConnection):
            def connect(self):
                sock = socket.create_connection((address, self.port or 443), self.timeout)
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

        conn = Pinned(parts.hostname, parts.port or 443, timeout=TIMEOUT,
                      context=tls.context())
        try:
            conn.request("GET", parts.path + ("?" + parts.query if parts.query else ""),
                         headers=dict(UA, Host=parts.hostname))
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308) and response.getheader("Location"):
                url = urllib.parse.urljoin(url, response.getheader("Location"))
                continue
            if response.status != 200:
                raise GuidePhotoError(f"could not read {url}: HTTP {response.status}")
            return response.read(limit + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise GuidePhotoError(f"could not read {url}: {exc}") from exc
        finally:
            conn.close()
    raise GuidePhotoError(f"could not read {url}: too many redirects")


# --------------------------------------------------------------- Washington

def wa_races(index):
    """``{race id (H-WA-04-2026): (guide race id, [{"name", "ballot", "party"}])}``
    for the guide's U.S. House races, from its index."""
    out = {}
    for category in index.get("Categories") or ():
        if category.get("CategoryCode") != "FED":
            continue
        for race in category.get("Races") or ():
            found = re.fullmatch(r"Congressional District (\d+)", str(race.get("Jurisdiction")))
            if not found or race.get("Name") != "U.S. Representative":
                continue
            rid = f"H-WA-{int(found.group(1)):02d}-2026"
            out[rid] = (str(race["RaceID"]), [
                {"name": c.get("BallotName"), "ballot": str(c.get("BallotID")),
                 "party": c.get("PartyName") or ""}
                for c in race.get("Candidates") or ()])
    return out


def wa_statements(answer, race_id):
    """``{ballot id: (name, party, photo bytes or None)}`` from one race's
    ``candidate.ashx`` answer: each statement record carries the name, the
    race and the photograph together. A record of another race is refused."""
    out = {}
    if not answer:
        raise GuidePhotoError(f"race {race_id}: the guide's answer holds no statement")
    if not any("Photo" in ((item or {}).get("statement") or {}) for item in answer):
        # No record carries the field at all: the answer's shape has changed,
        # which says nothing about anyone's photograph (rule 8).
        raise GuidePhotoError(f"race {race_id}: no statement carries a Photo field")
    for item in answer:
        statement = (item or {}).get("statement") or {}
        if not statement.get("BallotID") or not statement.get("BallotName"):
            raise GuidePhotoError(f"race {race_id}: a statement with no ballot id or name")
        if str(statement.get("RaceID")) != race_id:
            raise GuidePhotoError(f"race {race_id}: a statement for race {statement.get('RaceID')}")
        photo = statement.get("Photo")
        data = None
        if photo:
            try:
                data = base64.b64decode(photo, validate=True)
            except ValueError as exc:
                raise GuidePhotoError(f"race {race_id}: a photograph that is not base64") from exc
        out[str(statement.get("BallotID"))] = (statement.get("BallotName"),
                                               statement.get("PartyName") or "", data)
    return out


def read_washington(wanted, getter=get, log=print):
    """``(photos, problems, unread)``: for each race in *wanted* (``{race id:
    [profile]}``), the guide's photograph of each person it joins, as
    ``{person key: record}``; *unread* the races a read concluded nothing
    about."""
    photos, problems, unread = {}, [], set()
    races = [r for r in sorted(wanted) if r.startswith("H-WA-")]
    if not races:
        return photos, problems, unread
    try:
        index = wa_races(json.loads(getter(WA_INDEX)))
    except (GuidePhotoError, ValueError) as exc:
        problems.append(f"WA: {exc}; the last photographs read are kept")
        return photos, problems, set(races)
    for rid in races:
        # A readable index that lists a race the general election holds
        # without it, or without its people's names, has changed its layout:
        # that concludes nothing (rules 8 and 36), so the last photographs
        # read are kept.
        if rid not in index:
            problems.append(f"WA: the guide's index has no race for {rid}; the last "
                            "photographs read are kept")
            unread.add(rid)
            continue
        guide_race, entries = index[rid]
        if not entries or not all(e["name"] and e["ballot"] not in ("", "None")
                                  for e in entries):
            problems.append(f"WA {rid}: the guide's index lists no candidates, or one with no "
                            "name; the last photographs read are kept")
            unread.add(rid)
            continue
        people = wanted[rid]
        joined, more = join("WA", entries, people, profile_key_of, person_words)
        problems += more
        if not joined:
            continue
        address = WA_RECORD.format(race=guide_race)
        try:
            statements = wa_statements(json.loads(getter(address)), guide_race)
        except (GuidePhotoError, ValueError) as exc:
            problems.append(f"WA {rid}: {exc}; the last photographs read are kept")
            unread.add(rid)
            continue
        for i, key in sorted(joined.items()):
            entry = entries[i]
            name, party, data = statements.get(entry["ballot"], (None, None, None))
            if name != entry["name"]:
                problems.append(f"WA {rid}: the statement for ballot {entry['ballot']} names "
                                f"{name!r}, the guide's index {entry['name']!r}; not used")
                continue
            if not data:
                problems.append(f"WA {rid}: the guide prints no photograph for {name}")
                continue
            page = WA_PAGE.format(race=guide_race, ballot=entry["ballot"])
            words = (f"the voters' guide's statement for '{name}' {party}, U.S. Representative, "
                     f"Congressional District {int(rid[5:7])} (ballot {entry['ballot']}), "
                     "carries this photograph")
            record, why = photo_record("WA", rid, "house", name, page, address, words, data)
            if why:
                problems.append(f"WA {rid}: {name}'s photograph: {why}; not used")
                continue
            record["for"] = key
            photos[key] = record
    return photos, problems, unread


def profile_key_of(profile):
    from .photocopies import key_of
    return key_of("person", profile)


def photo_record(code, race, office, name, page, source, words, data, colour_space=None,
                 extra=None):
    """``(record, "")`` for a guide's photograph, or ``(None, why)`` when it
    fails a test every route asks (:func:`drawable`, :func:`unfit`)."""
    why = drawable(data, colour_space)
    if why:
        return None, why
    weight = measure(data)
    if not weight["width"]:
        return None, "its size cannot be read"
    photo = "photos/" + hosted_name(weight)
    refusal = unfit(weight, *own_addresses(code, page, photo))
    if refusal:
        return None, refusal
    record = {"state": code, "race": race, "office": office, "name": name, "page": page,
              "from": source, "evidence": words, "read": today(), "photo": photo,
              "by": GUIDES[code]["credit"]}
    record.update({k: weight[k] for k in ("sha256", "bytes", "width", "height", "type")})
    record.update(extra or {})
    record["_data"] = data
    return record, ""


# ------------------------------------------------------------------ Alaska

_AK_SECTIONS = {
    "GOVERNOR / LIEUTENANT GOVERNOR": ("governor", "lt"),
    "UNITED STATES SENATOR": ("senate",),
    "UNITED STATES REPRESENTATIVE": ("house",),
}
_AK_LABELS = {"Governor Statement": 0, "Running Mate Statement": 1, "Candidate Statement": 0}


def ak_rows(page):
    """``[{"offices", "names", "statements": {0 or 1: pdf url}, "anchor"}]``:
    each row of the candidate list's sections for governor and lieutenant
    governor, the U.S. Senate and the U.S. House. A ticket's row names the
    governor first and the running mate second; each statement is linked
    under its own label ("Governor Statement", "Running Mate Statement",
    "Candidate Statement")."""
    out = []
    heads = list(re.finditer(r"<h4>(.*?)</h4>", page or "", re.S))
    for n, head in enumerate(heads):
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", head.group(1))).split())
        if title not in _AK_SECTIONS:
            continue
        end = heads[n + 1].start() if n + 1 < len(heads) else len(page)
        section = page[head.end():end]
        for row in re.findall(r"<tr>(.*?)</tr>", section, re.S):
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 4:
                continue
            strong = re.search(r"<strong>(.*?)</strong>", cells[0], re.S)
            anchor = re.search(r'<a id="([^"]+)"', cells[0])
            if not strong:
                continue
            ticket = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", strong.group(1))).split())
            names = [part.strip() for part in re.split(r"\s*/\s*", ticket) if part.strip()]
            statements = {}
            for label, link in re.findall(
                    r"<strong>\s*([^<]*?Statement)\s*</strong>\s*<br>\s*<a\b[^>]*href=\"([^\"]+\.pdf)\"",
                    cells[3], re.S):
                label = " ".join(label.split())
                if label in _AK_LABELS:
                    statements[_AK_LABELS[label]] = html.unescape(link)
            out.append({"offices": _AK_SECTIONS[title], "names": names,
                        "statements": statements,
                        "anchor": html.unescape(anchor.group(1)) if anchor else ""})
    return out


UNREADABLE_PDF = "the PDF cannot be read"


def ak_statement(data, office, name):
    """``(jpeg bytes, colour space, words, "")`` from one candidate statement
    PDF, or ``(None, None, None, why)``. The page's heading must name the
    office (its first line) and the candidate (the next, "Name, Party"), and
    the page must draw one photograph."""
    try:
        doc = pdfread.Document(data)
        pages = doc.pages()
        if len(pages) != 1:
            return None, None, None, f"{len(pages)} pages, not one statement"
        read = pdfread.read_page(doc, pages[0])
    except pdfread.PDFError as exc:
        return None, None, None, f"{UNREADABLE_PDF} ({exc})"
    lines = pdfread.page_text(read).split("\n")
    if len(lines) < 2 or " ".join(lines[0].split()) != OFFICE_WORDS[office]:
        return None, None, None, (f"the statement's heading is {lines[:1]!r}, not "
                                  f"'{OFFICE_WORDS[office]}'")
    heading = lines[1]
    printed = heading.split(",", 1)[0].strip()
    if name_words(printed) != name_words(name):
        return None, None, None, (f"the statement names {printed!r}, the list "
                                  f"{name!r}")
    images = {}
    for drawn in read["images"]:
        images.setdefault(drawn["ref"] or id(drawn["stream"]), drawn)
    if len(images) != 1:
        return None, None, None, (f"the page draws {len(images)} images, not one "
                                  "photograph")
    drawn = next(iter(images.values()))
    info = drawn["stream"].info
    for key in ("SMask", "Mask", "Decode", "ImageMask"):
        if info.get(key):
            return None, None, None, f"the image carries /{key}"
    try:
        raw, image_filter = pdfread.decode(drawn["stream"])
    except pdfread.PDFError as exc:
        return None, None, None, f"the image cannot be read ({exc})"
    if image_filter != "DCTDecode":
        return None, None, None, f"the image is {image_filter or 'raw samples'}, not a JPEG"
    space = doc.resolve(info.get("ColorSpace"))
    space = str(space) if isinstance(space, str) else "ICCBased" if isinstance(space, list) \
        else str(space)
    box = drawn["box"]
    words = (f"the statement's heading reads '{lines[0]}' and '{heading}', and the page "
             f"draws one photograph ({info.get('Width')}x{info.get('Height')}, at "
             f"{box[0]:.0f},{box[1]:.0f}-{box[2]:.0f},{box[3]:.0f} pt) beside it")
    return raw, space, words, ""


def read_alaska(wanted, getter=get, log=print):
    """``(photos, problems, unread)`` as :func:`read_washington`, for the
    candidate list's statements: *wanted* is ``{race id or "AK|office":
    [people]}`` (profiles for ``S-AK-2026`` and ``H-AK-00-2026``, statewide
    candidates for ``AK|governor`` and ``AK|lt``)."""
    photos, problems, unread = {}, [], set()
    keys = [k for k in sorted(wanted) if k.startswith(("S-AK-", "H-AK-", "AK|"))]
    if not keys:
        return photos, problems, unread
    try:
        rows = ak_rows(getter(AK_LIST).decode("utf-8", "replace"))
    except GuidePhotoError as exc:
        problems.append(f"AK: {exc}; the last photographs read are kept")
        return photos, problems, set(keys)
    targets = {"senate": "S-AK-2026", "house": "H-AK-00-2026", "governor": "AK|governor",
               "lt": "AK|lt"}
    for office, target in targets.items():
        if target not in wanted:
            continue
        entries = []
        for row in rows:
            if office not in row["offices"]:
                continue
            slot = row["offices"].index(office)
            if slot >= len(row["names"]):
                continue
            entries.append({"name": row["names"][slot], "pdf": row["statements"].get(slot),
                            "anchor": row["anchor"]})
        # A readable list with no row for an office on the ballot, or whose
        # rows link no statement, has changed its layout: it concludes
        # nothing (rules 8 and 36), and the last photographs read are kept.
        if not entries or not any(e["pdf"] for e in entries):
            problems.append(f"AK {office}: the candidate list "
                            + ("has no row for the office" if not entries
                               else "links no statement for the office")
                            + "; the last photographs read are kept")
            unread.add(target)
            continue
        people = wanted[target]
        if target.startswith("AK|"):
            joined, more = join("AK", entries, people, lambda p: p["key"],
                                lambda p: {name_words(p["name"])})
        else:
            joined, more = join("AK", entries, people, profile_key_of, person_words)
        problems += more
        for i, key in sorted(joined.items()):
            entry = entries[i]
            if not entry["pdf"]:
                problems.append(f"AK {office}: the list links no statement for {entry['name']}")
                continue
            try:
                data = getter(entry["pdf"], limit=MAX_PDF)
            except GuidePhotoError as exc:
                problems.append(f"AK {office}: {exc}; the last photograph read is kept")
                unread.add(key)
                continue
            raw, space, words, why = ak_statement(data, office, entry["name"])
            if why.startswith(UNREADABLE_PDF):
                # A file this reader cannot parse says nothing about the
                # photograph in it (rule 8).
                problems.append(f"AK {office}: {entry['name']}'s statement: {why}; the last "
                                "photograph read is kept")
                unread.add(key)
                continue
            if why:
                problems.append(f"AK {office}: {entry['name']}'s statement: {why}; not used")
                continue
            words = (f"the Division of Elections' candidate list links '{entry['name']}''s "
                     f"official candidate statement, whose " + words[len("the statement's "):])
            race = target if not target.startswith("AK|") else ""
            record, why = photo_record("AK", race, office, entry["name"], entry["pdf"],
                                       entry["pdf"], words, raw, space,
                                       {"list": AK_LIST + ("#" + urllib.parse.quote(
                                           entry["anchor"], safe="%+") if entry["anchor"] else "")})
            if why:
                problems.append(f"AK {office}: {entry['name']}'s photograph: {why}; not used")
                continue
            record["for"] = key
            photos[key] = record
    return photos, problems, unread


# ------------------------------------------------------------------ Oregon

_OR_HOUSE = re.compile(r"^US Representative, (\d+)(?:st|nd|rd|th) District$")
_OR_STATEWIDE = {"Governor": "governor", "Secretary of State": "sos",
                 "Attorney General": "ag"}


def or_books(page):
    """``[(book address, [county])]`` from the pamphlet's page of books, in
    its order, each book once."""
    out = {}
    for href, words in re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page or "", re.S):
        href = html.unescape(href)
        if not OR_BOOK.match(href):
            continue
        county = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", words)).split())
        out.setdefault(urllib.parse.urljoin(OR_INDEX, href), []).append(county)
    return list(out.items())


def or_target(office):
    """The race id or ``OR|office`` a pamphlet heading names, or None."""
    found = _OR_HOUSE.match(office)
    if found:
        return f"H-OR-{int(found.group(1)):02d}-2026"
    if office == "US Senator":
        return "S-OR-2026"
    if office in _OR_STATEWIDE:
        return f"OR|{_OR_STATEWIDE[office]}"
    return None


def or_columns(doc):
    """``[{"page", "office", "name", "party", "image"}]``: each candidate the
    pamphlet's pages show with a photograph. A page sets each candidate in a
    column under the office's heading, the photograph at its head and the
    name in large type beside it, then the party in smaller type. A column
    whose photograph is not the only image beside its name, or whose name or
    heading cannot be read, gives nothing."""
    out = []
    for number, page in enumerate(doc.pages(), 1):
        read = pdfread.read_page(doc, page)
        photos = [i for i in read["images"] if i["stream"].info.get("Filter") in
                  ("JPXDecode", ["JPXDecode"])]
        if not photos:
            continue
        for image in photos:
            x0, y0, x1, y1 = image["box"]
            heads = [t.strip() for x, y, t, _s in read["text"]
                     if abs(x - x0) < 4 and y1 < y < y1 + 25 and t.strip()]
            beside = sorted(((y, x, t.strip(), s) for x, y, t, s in read["text"]
                             if x1 < x < x1 + 20 and y0 <= y <= y1 and t.strip()),
                            key=lambda r: (-r[0], r[1]))
            near = [i for i in read["images"] if i is not image and
                    i["box"][0] < x1 + 20 and i["box"][2] > x0 and
                    i["box"][1] < y1 and i["box"][3] > y0]
            if len(heads) != 1 or not beside or near:
                continue
            size = beside[0][3]
            name = []
            for _y, _x, words, s in beside:
                if s != size:
                    break
                name.append(words)
            # The party: the lines straight after the name in the next size.
            party = []
            rest = beside[len(name):]
            for _y, _x, words, s in rest:
                if s != rest[0][3] or s >= size or len(party) == 3:
                    break
                party.append(words)
            out.append({"page": number, "office": heads[0], "name": " ".join(" ".join(name).split()),
                        "party": ", ".join(party), "image": image})
    return out


def or_photo(image, doc):
    """``(png bytes, codestream sha256, "")`` for a pamphlet photograph, or
    ``(None, None, why)``: a grey JPEG 2000 image with no mask, decoded
    losslessly (:mod:`kyc.jpx`)."""
    from . import jpx
    info = image["stream"].info
    space = doc.resolve(info.get("ColorSpace"))
    if space != "DeviceGray":
        return None, None, f"an image in {space}, not grey"
    for key in ("SMask", "Mask", "Decode", "ImageMask"):
        if info.get(key):
            return None, None, f"the image carries /{key}"
    try:
        data, image_filter = pdfread.decode(image["stream"])
    except pdfread.PDFError as exc:
        return None, None, f"the image cannot be read ({exc})"
    if image_filter != "JPXDecode":
        return None, None, f"the image is {image_filter}, not JPEG 2000"
    try:
        width, height, rows = jpx.decode(data)
    except jpx.JPXError as exc:
        return None, None, f"the JPEG 2000 cannot be decoded faithfully ({exc})"
    if (width, height) != (info.get("Width"), info.get("Height")):
        return None, None, "the decoded image is not the size the PDF gives"
    return jpx.png(width, height, rows), hashlib.sha256(data).hexdigest(), ""


def read_oregon(wanted, getter=get, log=print):
    """``(photos, problems, unread)`` as :func:`read_washington`, from the
    county books of the State Voters' Pamphlet: each book is read in the
    order the pamphlet's page lists them until every race and office wanted
    has been found on a page (a race's page is in each book for a county in
    it)."""
    photos, problems, unread = {}, [], set()
    targets = {k for k in wanted if k.startswith(("H-OR-", "S-OR-", "OR|"))}
    if not targets:
        return photos, problems, unread
    try:
        books = or_books(getter(OR_INDEX).decode("utf-8", "replace"))
    except GuidePhotoError as exc:
        problems.append(f"OR: {exc}; the last photographs read are kept")
        return photos, problems, set(targets)
    if not books:
        problems.append("OR: the pamphlet's page lists no county books; the last photographs "
                        "read are kept")
        return photos, problems, set(targets)
    found = {}
    remaining = set(targets)
    for book, counties in books:
        if not remaining:
            break
        try:
            doc = pdfread.Document(getter(book, limit=MAX_PDF))
            columns = or_columns(doc)
        except (GuidePhotoError, pdfread.PDFError) as exc:
            problems.append(f"OR: {exc}")
            continue
        here = {}
        for column in columns:
            target = or_target(column["office"])
            if target in remaining:
                here.setdefault(target, []).append(column)
        for target, entries in here.items():
            found[target] = (book, counties, doc, entries)
            remaining.discard(target)
    unread |= remaining
    for target in sorted(found):
        book, counties, doc, entries = found[target]
        people = wanted[target]
        if target.startswith("OR|"):
            joined, more = join("OR", entries, people, lambda p: p["key"],
                                lambda p: {name_words(p["name"])})
        else:
            joined, more = join("OR", entries, people, profile_key_of, person_words)
        problems += more
        for i, key in sorted(joined.items()):
            entry = entries[i]
            png, source_sha, why = or_photo(entry["image"], doc)
            if why:
                problems.append(f"OR {target}: {entry['name']}'s photograph: {why}; not used")
                continue
            page = f"{book}#page={entry['page']}"
            words = (f"page {entry['page']} of the State Voters' Pamphlet (the book for "
                     f"{', '.join(counties)}) heads a column '{entry['office']}' and prints "
                     f"'{entry['name']}'" + (f", '{entry['party']}'" if entry["party"] else "")
                     + " beside its one photograph")
            office = target.split("|", 1)[1] if target.startswith("OR|") else \
                ("senate" if target.startswith("S-") else "house")
            race = "" if target.startswith("OR|") else target
            record, why = photo_record("OR", race, office, entry["name"], page, book, words, png,
                                       extra={"method": "decoded", "sourceSha256": source_sha,
                                              "decoder": DECODER})
            if why:
                problems.append(f"OR {target}: {entry['name']}'s photograph: {why}; not used")
                continue
            record["for"] = key
            photos[key] = record
    return photos, problems, unread


DECODER = ("kyc/jpx.py: JPEG 2000, reversible 5/3 wavelet, no quantization, every coding "
           "pass - lossless, written as PNG")


# ------------------------------------------------------------------ who

def race_of(profile):
    """The race a profile is contesting: the seat its filing names
    (``contestRaceId``, rule 30), else its race, else - before the build
    has assigned races - the seat its chamber, state and district give."""
    found = profile.get("contestRaceId") or profile.get("raceId")
    if found:
        return found
    if profile.get("state") in (None, "", "N/A") or not profile.get("chamber"):
        return ""
    from .races import race_id
    return race_id(profile["chamber"], profile["state"], profile.get("districtNum"))


def wanted_people(profiles, cache=None):
    """``{race id: [profile]}``: everyone on the ballot in a guide's state
    whom the last build showed with no photograph, or with this route's."""
    from .enrich import running
    from .photos import PLACEHOLDER
    out = {}
    for profile in profiles:
        if profile.get("state") not in GUIDES or not running(profile):
            continue
        first = (profile.get("photos") or [PLACEHOLDER])[0]
        if first != PLACEHOLDER and profile.get("photoSource") != ROUTE:
            continue
        out.setdefault(race_of(profile), []).append(profile)
    # Everyone in those races, pictured or not: a name is joined only where
    # it fits one person among all of them (rule 25).
    races = set(out)
    everyone = {}
    for profile in profiles:
        if race_of(profile) in races:
            everyone.setdefault(race_of(profile), []).append(profile)
    return {rid: everyone[rid] for rid in sorted(races)}, {
        rid: {profile_key_of(p) for p in out[rid]} for rid in out}


def wanted_statewide(stategov):
    """``{"AK|office": [{"key", "name"}]}`` for each office a guide covers,
    every non-write-in candidate the list names, and the keys of those the
    last build showed with no photograph or with this route's."""
    from .photocopies import key_of
    people, keys = {}, {}
    for code, entry in sorted(((stategov or {}).get("states") or {}).items()):
        if code not in GUIDES:
            continue
        for office, item in sorted((((entry.get("ballot2026") or {}).get("offices")) or {}).items()):
            rows = ((item.get("candidates") or {}).get("candidates") or ())
            listed = [r for r in rows if not r.get("writeIn")]
            if not listed:
                continue
            target = f"{code}|{office}"
            people[target] = [{"key": key_of("candidate", r, code, office),
                               "name": r.get("printed") or r["name"], "shown": r["name"]}
                              for r in listed]
            keys[target] = {key_of("candidate", r, code, office) for r in listed
                            if not r.get("photo") or is_hosted(r["photo"])}
    return people, keys


# ------------------------------------------------------------------ the run

def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {"photos": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def same_decode(rec, previous, root="."):
    """*rec* as the file already hosted for it, where *rec* is a decode
    (Oregon's) of the very codestream, by the same decoder, that a
    previous record's file was made from, and that file is on disk as its
    name gives it and holds the same pixels; else None. The PNG's pixels
    are the decode's, but its compressed bytes are zlib's, and zlib's
    output differs between builds of it (zlib-ng here, the runner's
    system zlib): named by those bytes' hash, every Oregon photograph read
    on the other machine was a new file and "changed" (the refresh of
    2026-10-26), with nothing about the photograph changed."""
    from . import jpx, photocopies
    from .photos import refused
    data = rec.get("_data")
    if rec.get("method") != "decoded" or data is None:
        return None
    for was in sorted(((previous or {}).get("photos") or {}).values(),
                      key=lambda r: r.get("photo") or ""):
        if (was.get("method") != "decoded" or was.get("sourceSha256") != rec.get("sourceSha256")
                or was.get("decoder") != rec.get("decoder") or not was.get("photo")):
            continue
        if was["photo"] == rec["photo"]:
            return None
        name = was["photo"][len("photos/"):]
        path = os.path.join(root, photocopies.PHOTOS_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as handle:
            old = handle.read()
        if hashlib.sha256(old).hexdigest() != was.get("sha256"):
            continue
        try:
            if jpx.png_pixels(old) != jpx.png_pixels(data):
                continue
        except (jpx.JPXError, ValueError, zlib.error, struct.error):
            continue
        if refused(was["photo"]):
            continue
        out = dict(rec)
        out.update(measure(old))
        out["photo"] = was["photo"]
        out["_data"] = old
        return out
    return None


def fetch(root=".", profiles=None, stategov=None, getter=get, log=print):
    """Read each guide for whoever lacks a photograph; host what joins and
    update the manifest and the cache. Returns ``(cache, problems)``."""
    from . import photocopies
    if profiles is None:
        profiles = photocopies.read_people(root)
    if stategov is None:
        stategov = read_stategov(root)
    previous = load_cache(root)
    races, want = wanted_people(profiles)
    offices, want_sw = wanted_statewide(stategov)
    wanted = dict(races)
    wanted.update(offices)
    want.update(want_sw)
    log(f"  guide photographs: {sum(len(v) for v in want.values())} people in "
        f"{len(want)} races or offices without one ({', '.join(sorted(GUIDES))})")
    photos, problems, unread = {}, [], set()
    for reader in (read_washington, read_alaska, read_oregon):
        found, more, gone_unread = reader(wanted, getter=getter, log=log)
        problems += more
        unread |= gone_unread
        for key, rec in found.items():
            if key in want.get(rec["race"] or f"{rec['state']}|{rec['office']}", set()):
                photos[key] = rec
    # Kept from the last read where this read concluded nothing (rule 8).
    for key, rec in sorted(((previous or {}).get("photos") or {}).items()):
        target = rec.get("race") or f"{rec.get('state')}|{rec.get('office')}"
        if key in photos or (target not in unread and key not in unread):
            continue
        problems.append(f"{key}: the guide could not be read; the last photograph is kept")
        photos[key] = rec
    for key, rec in sorted(photos.items()):
        same = same_decode(rec, previous, root)
        if same:
            photos[key] = same
    cache = {"about": ABOUT, "read": today(),
             "guides": {code: dict(GUIDES[code]) for code in sorted(GUIDES)},
             "elsewhere": dict(ELSEWHERE),
             "photos": {}}
    manifest = photocopies.load(root)
    hosted = manifest.setdefault("hosted", {})
    # A file hosted by a person's choice (overrides.CANDIDATE_PHOTOS) is not
    # this reader's to rewrite or remove.
    chosen = {name for name in photocopies.curated_names() if name in hosted}
    keep = {name: hosted[name] for name in chosen}
    for key, rec in sorted(photos.items()):
        data = rec.pop("_data", None)
        name = rec["photo"][len("photos/"):]
        if data is not None:
            path = os.path.join(root, photocopies.PHOTOS_DIR, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                with open(path + ".tmp", "wb") as handle:
                    handle.write(data)
                os.replace(path + ".tmp", path)
        entry = keep.setdefault(name, dict(hosted.get(name) or {}))
        if entry.get("sha256") not in (None, rec["sha256"]):
            entry = keep[name] = {}
        entry.update({"method": rec.get("method") or "unmodified", "page": rec["page"],
                      "from": rec["from"], "sha256": rec["sha256"], "bytes": rec["bytes"],
                      "width": rec["width"], "height": rec["height"], "type": rec["type"],
                      "read": rec["read"], "by": rec["by"]})
        # A JPEG 2000 decoded losslessly (Oregon's): the codestream it was
        # decoded from, and how.
        for field in ("sourceSha256", "decoder"):
            if rec.get(field):
                entry[field] = rec[field]
            else:
                entry.pop(field, None)
        cache["photos"][key] = rec
        was = ((previous or {}).get("photos") or {}).get(key) or {}
        if was.get("photo") != rec["photo"]:
            problems.append(f"{key}: photograph {'changed' if was.get('photo') else 'added'}: "
                            f"{rec['photo']} (from {rec['page']}); look at it")
    for name, entry in keep.items():
        if name in chosen:
            continue
        entry["for"] = sorted({k for k, rec in cache["photos"].items()
                               if rec["photo"] == "photos/" + name})
        # A copy made for someone this file no longer shows is not theirs.
        if entry.get("copy"):
            entry["copy"]["for"] = sorted(set(entry["copy"].get("for") or ()) & set(entry["for"]))
    manifest["hosted"] = {k: keep[k] for k in sorted(keep)}
    photocopies.save(manifest, root)
    photocopies._sweep(manifest, root, log)
    return cache, problems


ABOUT = ("Photographs the election offices' own guides print beside a candidate's name, "
         "with no image address to link: each joined to the person by the guide's page "
         "naming them beside it, for that office (kyc/guide_photos.py; rules 24, 87, 91, "
         "101). The file is hosted unmodified under photos/ and listed in "
         "data/photo_copies.json ('hosted'). Hand-editable.")


def read_stategov(root="."):
    """The last build's ``data/stategov.js`` payload."""
    path = os.path.join(root, "candidate_profiles_site", "data", "stategov.js")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("window.kycStateGov = ") + len("window.kycStateGov = ")
    return json.JSONDecoder().raw_decode(text[start:].replace("<\\!--", "<!--"))[0]


# ------------------------------------------------------------------ the page

RECORD_KEYS = ("state", "office", "name", "page", "from", "evidence", "read", "photo",
               "sha256", "bytes", "width", "height", "by", "for")


def record_problems(key, rec, manifest=None):
    """What a cached record lacks or gets wrong, as sentences."""
    out = []
    for field in RECORD_KEYS:
        if rec.get(field) in (None, ""):
            out.append(f"guide_photos {key}: no {field}")
    for field in ("page", "from"):
        if rec.get(field) and not str(rec[field]).startswith("https://"):
            out.append(f"guide_photos {key}: its {field} is not an https address")
    if rec.get("state") and rec["state"] not in GUIDES:
        out.append(f"guide_photos {key}: {rec['state']} is no guide this site reads")
    if rec.get("photo") and not is_hosted(rec["photo"]):
        out.append(f"guide_photos {key}: {rec['photo']} is not a file under photos/")
    if rec.get("for") and rec["for"] != key:
        out.append(f"guide_photos {key}: kept for {rec['for']}")
    if rec.get("method", "unmodified") not in ("unmodified", "decoded"):
        out.append(f"guide_photos {key}: method {rec.get('method')!r}")
    if rec.get("method") == "decoded" and not (rec.get("sourceSha256") and rec.get("decoder")
                                               and rec.get("type") == "image/png"):
        out.append(f"guide_photos {key}: a decoded photograph without its source's hash, "
                   "its decoder, or as anything but a PNG")
    try:
        datetime.date.fromisoformat(str(rec.get("read") or ""))
    except ValueError:
        out.append(f"guide_photos {key}: the day read is not a date")
    if manifest is not None and is_hosted(rec.get("photo")):
        entry = (manifest.get("hosted") or {}).get(rec["photo"][len("photos/"):])
        if not entry:
            out.append(f"guide_photos {key}: {rec['photo']} is not in the manifest's hosted files")
        else:
            if entry.get("sha256") != rec.get("sha256"):
                out.append(f"guide_photos {key}: the manifest's {rec['photo']} is another file")
            if key not in (entry.get("for") or ()):
                out.append(f"guide_photos {key}: the manifest does not list it for {key}")
    return out


def problems(cache, manifest=None):
    out = []
    for key, rec in sorted(((cache or {}).get("photos") or {}).items()):
        out += record_problems(key, rec, manifest)
    return out


def shown_record(cache, key, words, race=None, office=None, manifest=None):
    """The cached record the page may show for *key*, or None: sound
    (:func:`record_problems`), not refused since it was read, of the same
    race or office, and still the name of the person it is shown for -
    *words*, that person's name forms, still holding the guide's name (or an
    evidenced form naming *key*)."""
    rec = ((cache or {}).get("photos") or {}).get(key)
    if not rec or record_problems(key, rec, manifest):
        return None
    if race is not None and rec.get("race") != race:
        return None
    if office is not None and rec.get("office") != office:
        return None
    if unfit({"width": rec["width"], "height": rec["height"]},
             *own_addresses(rec["state"], rec["page"], rec["photo"])):
        return None
    mine = name_words(rec["name"])
    if mine not in words and evidenced_form(rec["state"], rec["name"]) != key:
        return None
    return rec


def credit(rec):
    """The credit the page prints: the guide, linked to the candidate's page
    in it (rule 87), in the guide's words as they now stand; and for a file
    this site decoded, that it did (``converted``), as a smaller copy says
    it is one (rule 101)."""
    guide = GUIDES.get(rec.get("state")) or {}
    out = {"by": guide.get("credit") or rec["by"], "page": rec["page"]}
    if rec.get("method") == "decoded":
        out["converted"] = guide.get("converted") or "converted by this site"
    return out


def apply_people(profiles, cache, manifest=None):
    """Give each profile the build left with no photograph its guide's,
    where one is shown (:func:`shown_record`); returns how many."""
    from .photos import PLACEHOLDER
    if manifest is None:
        from .photocopies import load
        manifest = load()
    n = 0
    for profile in profiles:
        first = (profile.get("photos") or [PLACEHOLDER])[0]
        if first != PLACEHOLDER:
            continue
        key = profile_key_of(profile)
        rec = shown_record(cache, key, person_words(profile), race=race_of(profile),
                           manifest=manifest)
        if not rec:
            continue
        profile["photos"] = [rec["photo"]] + [u for u in profile.get("photos") or []
                                              if u != rec["photo"]]
        profile["photo_url"] = rec["photo"]
        profile["photoSource"] = ROUTE
        profile["photoCredit"] = credit(rec)
        n += 1
    return n


def reapply_people(profiles, cache, manifest=None):
    """Give each profile, as the last build wrote it, the guide's photograph
    the next build will give it: the one this route gave it taken off, then
    :func:`apply_people` from the cache as it stands. ``guidephotos`` runs
    between two builds and may host a new file for someone (a read whose
    bytes differ, a photograph the guide changed) and drop the one the last
    build showed, so a reader of the last build's people files
    (``photocopies``) must not take that build's file as still shown (the
    refresh of 2026-10-26: four Oregon nominees "showed" files the manifest
    had just let go). Returns how many profiles show one."""
    from .photos import PLACEHOLDER
    for profile in profiles:
        if profile.get("photoSource") != ROUTE:
            continue
        old = (profile.get("photos") or [PLACEHOLDER])[0]
        rest = [u for u in profile.get("photos") or [] if u != old] or [PLACEHOLDER]
        profile["photos"] = rest
        profile["photo_url"] = rest[0]
        for field in ("photoSource", "photoCredit", "photoCopy"):
            profile.pop(field, None)
    return apply_people(profiles, cache, manifest)


def for_row(cache, code, office, row, manifest=None):
    """The record a statewide candidate's row may show, or None."""
    from .photocopies import key_of
    key = key_of("candidate", row, code, office)
    return shown_record(cache, key, {name_words(row.get("printed") or row["name"]),
                                     name_words(row["name"])},
                        office=office, manifest=manifest)


def copy_heavy(cache, root=".", maker=None, log=print):
    """The smaller copies of the heavy photographs just hosted (rule 101),
    made at once: a profile's drawn as a card ("person"), a statewide
    candidate's in the election office's list ("candidate")."""
    from . import photocopies
    shown = photocopies.Shown()
    for key, rec in sorted(((cache or {}).get("photos") or {}).items()):
        kind = "person" if key.startswith("person:") else "candidate"
        shown.add(rec["photo"], kind, key, {}, True)
    return photocopies.copy_hosted(root, shown, maker=maker, log=log)


def counts(cache):
    out = {}
    for rec in ((cache or {}).get("photos") or {}).values():
        out[rec.get("state")] = out.get(rec.get("state"), 0) + 1
    return out
