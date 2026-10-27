"""Each state's other statewide officers, from the associations of the offices.

``python build_profile_site.py officers`` reads the rosters each association
publishes of its own members:

- the National Association of Secretaries of State (https://www.nass.org/
  membership): every secretary of state - or, where a state has none, the
  officer who is NASS's member, its lieutenant governor - with how they hold
  the office (elected, appointed, chosen by the legislature), whether they
  are the state's chief election official, and the office's address, phone
  and email;
- the National Lieutenant Governors Association (https://nlga.us/our-
  members/): every lieutenant governor, and where a state has none, the
  officer first in line to succeed the governor.

The two overlap: NASS's member in Alaska, Hawaii and Utah is the lieutenant
governor, and NLGA's in Arizona, Oregon and Wyoming is the secretary of
state. Where both name the holder of one office they must name the same
person of the same party, or neither is shown (``overlaps``; rule 53). An
entry NASS marks as not a member is not NASS speaking for its own member:
its Hawaii entry named Sylvia Luke, whom Keith Regan, NLGA's member, had
replaced as (acting) lieutenant governor, so NLGA's stands. A secretary of
state NASS lists for a non-member state is shown as NASS's listing, not as
fact.
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

NASS_URL = "https://www.nass.org/membership"
NLGA_URL = "https://nlga.us/our-members/"
RAGA_URL = "https://www.republicanags.com/attorneys-general"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "statewide_officers.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")

# How the rosters abbreviate a jurisdiction's name.
ABBREVIATED = {
    "Amer. Samoa": "AS",
    "American Samoa": "AS",
    "Dist. of Columbia": "DC",
    "N. Mariana Islands": "MP",
    "Northern Mariana Islands": "MP",
    "U.S. Virgin Islands": "VI",
    "US Virgin Islands": "VI",
}

PARTY_NAME = {"D": "Democratic", "R": "Republican", "I": "Independent"}


class OfficersError(RuntimeError):
    """A roster could not be read, or is not what the pipeline expects."""


def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise OfficersError(f"could not fetch {url}: {exc}") from exc


_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def _text(fragment):
    """Visible text: tags and invisible characters gone (one of RAGA's two
    West Virginia cards carries a zero-width space after the name)."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).translate(_INVISIBLE).split())


def jurisdiction(label):
    """A roster's name for a state or territory -> its postal code."""
    from .normalize import US_STATES
    clean = re.sub(r"\s*\(CEO\)|\*", "", _text(label)).strip()
    if clean in ABBREVIATED:
        return ABBREVIATED[clean]
    code = {name.title(): c for name, c in US_STATES.items()}.get(clean.title())
    if not code:
        raise OfficersError(f"a roster names a jurisdiction the site does not know: {label!r}")
    return code


def name_and_party(text):
    """``"Wes Allen (R)"`` -> ``("Wes Allen", "R")``. A party in brackets is
    required: a roster entry without one is not read as a person."""
    match = re.fullmatch(r"(.+?)\s*\(([A-Z]{1,4})\)", _text(text))
    if not match:
        return None, None
    return re.sub(r"^(Hon\.|The Honorable)\s+", "", match.group(1)), match.group(2)


# Titles that come before a name and are not part of it, for comparing two
# renderings of one person. "High Chief" is a Samoan matai title: shown as
# published, set aside only to compare.
_TITLES = re.compile(r"^(High Chief|Chief|Dr\.|Rev\.|Judge)\s+")


def same_person(a, b):
    from .executives import same_person as same
    return same(_TITLES.sub("", a), _TITLES.sub("", b))


def party_key(letter):
    return letter if letter in ("D", "R") else "I"


def _record(rows, code, entry, source):
    if code in rows:
        raise OfficersError(f"{source} lists {code} twice")
    rows[code] = entry


# --------------------------------------------------------------------- NASS

_NASS_ITEM = re.compile(r'<article class="secretary[^"]*" id="[^"]*">(.*?)</article>', re.S)


def parse_nass(page):
    """``{code: officer}`` from NASS's membership roster."""
    rows = {}
    for body in _NASS_ITEM.findall(page):
        head = re.search(r'<h2><a href="([^"]*)">(.*?)</a></h2>', body, re.S)
        lines = re.findall(r"<p>(.*?)</p>", body, re.S)
        if not head or len(lines) < 2:
            raise OfficersError("a NASS roster entry has no heading or no title line")
        code = jurisdiction(head.group(2))
        name, party = name_and_party(lines[0])
        if not name:
            raise OfficersError(f"NASS {code}: no name and party in {_text(lines[0])!r}")
        title, _, selection = _text(lines[1]).partition(" - ")
        entry = {
            "name": name, "party": party, "partyKey": party_key(party),
            "title": title.replace("Sec. of the", "Secretary of the").replace("Lt.", "Lieutenant"),
            "selection": {"Legislature": "Chosen by the legislature"}.get(selection, selection),
            "electionChief": "(CEO)" in head.group(2),
            "website": head.group(1),
        }
        # "* Currently Not a NASS Member": the entry is not NASS speaking
        # for its own member (rule 55). Hawaii's named a lieutenant
        # governor NLGA's member had replaced.
        if "*" in head.group(2):
            entry["member"] = False
        img = re.search(r'<img src="([^"]+)"', body)
        if img:
            entry["photo"] = urllib.parse.urljoin(NASS_URL, html.unescape(img.group(1)))
        bio = re.search(r'<strong><a href="([^"]+)"', lines[0])
        if bio:
            entry["bio"] = bio.group(1)
        rest = [_text(line) for line in lines[2:]]
        for value in rest:
            if re.fullmatch(r"\(?\d{3}\)?[\s.-]?\d{3}-\d{4}.*", value):
                entry.setdefault("phone", value)
            elif "@" in value:
                entry.setdefault("email", value)
            elif value and "address" not in entry:
                entry["address"] = value
        _record(rows, code, entry, "NASS")
    if len(rows) < 50:
        raise OfficersError(f"NASS's roster lists only {len(rows)} members")
    return rows


# --------------------------------------------------------------------- NLGA

_NLGA_ITEM = re.compile(
    r'<h2 class="elementor-heading-title[^"]*">([^<]+)</h2>(.*?)'
    r'<h3 class="elementor-heading-title[^"]*">([^<]+)</h3>(.*?)(?=<h2 class="elementor-heading-title|\Z)',
    re.S)


def _smallest(srcset):
    """The smallest size a srcset offers of its one photograph."""
    best = None
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w") and bits[1][:-1].isdigit():
            width = int(bits[1][:-1])
            if best is None or width < best[0]:
                best = (width, html.unescape(bits[0]))
    return best[1] if best else ""


def _card_photo(fragment):
    """The photograph on an NLGA card: the smallest size its srcset offers,
    or - for a card that has only a ``src`` - that file at 300px from the
    host's own resizer. Virginia's lieutenant governor's card carried a
    plain ``src`` and lost its photograph because only a srcset was read
    (STATEGOV-13)."""
    from .photos import host_resized

    img = re.search(r'<img[^>]*\bsrcset="([^"]+)"', fragment)
    if img:
        return _smallest(img.group(1))
    img = re.search(r'<img[^>]*\bsrc="(https://[^"]+)"', fragment)
    if not img:
        return ""
    src = html.unescape(img.group(1))
    return host_resized(src, 300) or src


def parse_nlga(page):
    """``{code: officer}`` from NLGA's member list: the lieutenant governor,
    or the officer first in line where a state has none."""
    rows = {}
    for state, before, heading, after in _NLGA_ITEM.findall(page):
        code = jurisdiction(state)
        who, _, title = _text(heading).partition(", ")
        entry = {"title": title.replace("Lt.", "Lieutenant").strip()}
        if who.strip().lower() == "vacant":
            entry["vacant"] = True
        else:
            name, party = name_and_party(who)
            if not name:
                raise OfficersError(f"NLGA {code}: no name and party in {who!r}")
            entry.update(name=name, party=party, partyKey=party_key(party))
            photo = _card_photo(before)
            if photo and _surname_in(name, photo):
                entry["photo"] = photo
        site = re.search(r'<a href="([^"]+)"[^>]*>\s*<span class="elementor-icon-list-text">\s*'
                         r'Website', after)
        if site:
            entry["website"] = html.unescape(site.group(1))
        _record(rows, code, entry, "NLGA")
    if len(rows) < 50:
        raise OfficersError(f"NLGA's list holds only {len(rows)} members")
    return rows


def office_of(title):
    """"Lieutenant Governor", "Secretary of State" or ``None`` for a roster
    title, acting or not: "Acting Lt. Governor", "Lieutenant Governor/Senate
    President", "Secretary of the Commonwealth"."""
    base = re.sub(r"^acting\s+", "", title.strip().lower()).replace("lt.", "lieutenant")
    if base.startswith("lieutenant governor"):
        return "Lieutenant Governor"
    if base.startswith(("secretary of state", "secretary of the commonwealth")):
        return "Secretary of State"
    return None


def lieutenant(entry):
    """Whether an NLGA entry is the state's lieutenant governor, rather than
    the officer first in line in a state that has none."""
    return office_of(entry["title"]) == "Lieutenant Governor"


# --------------------------------------------------------------------- RAGA

_RAGA_ITEM = re.compile(
    r'<h2 class="entry-title[^"]*">\s*<a href="([^"]+)">([^<]+)</a>\s*</h2>\s*'
    r'<p class="state[^"]*">([^<]+)</p>', re.S)


def parse_raga(page):
    """``{code: {"name", "profile"}}`` for the association's members. The page
    repeats its officers' cards; a state named twice must name one person."""
    rows = {}
    for profile, name, state in _RAGA_ITEM.findall(page):
        code = jurisdiction(state)
        if _text(name).lower() == _text(state).lower():
            continue                     # a placeholder card: "Maryland", not a person
        entry = {"name": _text(name), "profile": profile}
        if code in rows and rows[code]["name"] != entry["name"]:
            raise OfficersError(f"RAGA lists two people for {code}: "
                                f"{rows[code]['name']!r} and {entry['name']!r}")
        rows[code] = entry
    if len(rows) < 20:
        raise OfficersError(f"RAGA's roster lists only {len(rows)} members")
    return rows


# ------------------------------------------------------------- cross-check

def overlaps(nass, nlga):
    """Where both rosters name the holder of one office - a lieutenant
    governor who is NASS's member, a secretary of state first in line for
    NLGA - ``(code, office, nass name, nlga name)`` for every pair that
    does not name the same person of the same party."""
    out = []
    for code in sorted(set(nass) & set(nlga)):
        a, b = nass[code], nlga[code]
        office = office_of(a["title"])
        if not office or office != office_of(b["title"]):
            continue
        if a.get("member") is False:
            continue                    # not NASS's member: NLGA's member stands
        theirs = "" if b.get("vacant") else b["name"]
        if not theirs or not same_person(a["name"], theirs) or a["party"] != b.get("party"):
            out.append((code, office, f"{a['name']} ({a['party']})",
                        f"{theirs} ({b.get('party')})" if theirs else "vacant"))
    return out


# ------------------------------------------------------- attorneys general
#
# No association lists every attorney general in a form a script can read:
# NAAG's site is behind a Cloudflare challenge. Each party's association
# lists its own members - RAGA's Republicans, DAGA's Democrats, which
# together have covered all fifty - and those give the party. Neither is
# trusted for the name: on 2026-10-05 RAGA listed for North Carolina the
# Republican Jeff Jackson beat in 2024, and printed "Maryland" and
# "Vermont" as members' names. So a name is shown only when the attorney
# general's own office, linked from USA.gov's page for the state, names
# that person beside the title.

DAGA_URL = "https://dems.ag/meet-the-attorneys-general/"
USAGOV_URL = "https://www.usa.gov/states/{slug}"

# The office's page where USA.gov's link is wrong, or another official page
# where the office's own site names nobody or refuses a script. Each with
# what was seen on 2026-10-05.
OFFICE_PAGES = {
    # USA.gov links ago.wv.gov/Pages/default.aspx, which is a 404.
    "WV": ["https://ago.wv.gov/"],
    # The homepage names nobody; the office's staff page names the AG.
    "WY": ["https://attorneygeneral.wyo.gov/law-office-division/administrative-division/"
           "administrative-division-staff"],
    # ag.ks.gov answers Akamai "Access Denied"; the state portal's Elected
    # Officials block names the attorney general.
    "KS": ["https://portal.kansas.gov/"],
}

# The office's form of a name an association prints differently.
NAME_FORMS = {
    # DAGA's card; ag.ny.gov: "Office of the New York Attorney General
    # Letitia James".
    "Tish James": "Letitia James",
}

# The office's front door, where USA.gov links a contact page, a page that
# is gone, or a domain named for the officeholder (rules 35 and 39:
# ago.ms.gov redirects to attorneygenerallynnfitch.com, which will lapse).
OFFICE_LINK = {
    "AK": "https://law.alaska.gov/",
    "HI": "https://ag.hawaii.gov/",
    "MS": "https://ago.ms.gov/",
    "WV": "https://ago.wv.gov/",
}

# How the office is filled where it is not elected statewide. Checked on
# 2026-10-05 against each office's own site (Wyoming's quotes Wyo. Stat.
# 9-1-601; Tennessee's, its appointment by the Supreme Court).
AG_SELECTION = {
    "AK": "Appointed by the governor",
    "HI": "Appointed by the governor",
    "ME": "Chosen by the legislature",
    "NH": "Appointed by the governor and Executive Council",
    "NJ": "Appointed by the governor",
    "TN": "Appointed by the state Supreme Court",
    "WY": "Appointed by the governor",
}

_DAGA_ITEM = re.compile(r'<a class="profile-card"\s+href="([^"]+)"\s+title="([^"]+)">.*?'
                        r'<p class="profile-card__copy">(.*?)</p>', re.S)


def parse_daga(page):
    """``{code: {"name", "profile"}}`` for DAGA's members (D.C.'s included)."""
    rows = {}
    for profile, name, state in _DAGA_ITEM.findall(page):
        code = jurisdiction(state)
        if code in rows:
            raise OfficersError(f"DAGA lists {code} twice")
        rows[code] = {"name": _text(name), "profile": profile}
    if len(rows) < 15:
        raise OfficersError(f"DAGA's roster lists only {len(rows)} members")
    return rows


def usagov_office(page):
    """The attorney general's office link on a USA.gov state page."""
    links = re.findall(r'field--name-field-state-attorney-general[^>]*>\s*<a href="([^"]+)"', page)
    if len(links) != 1:
        raise OfficersError(f"USA.gov's page has {len(links)} attorney general links, not one")
    return html.unescape(links[0])


def _fold(text):
    """Lower case, accents off, periods and quotes gone, one space - letter
    for letter, so a match's position is its position in the original."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch)[:1] or ch
        out.append(base.lower() if base.isalnum() else (" " if not base.isspace() else " "))
    return re.sub(r" +", " ", "".join(out))


def visible_text(page):
    """A page's readable text: no head, script, style or title, and nothing
    inside an HTML comment - North Carolina's page keeps a commented-out
    "Attorney General Josh Stein", its previous holder."""
    body = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    body = re.sub(r"<(head|script|style|title|noscript)\b[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    return _text(body)


_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


TITLES = {
    "ag": r"(?:attorney general|(?<!of )\bag\b)",
    "sos": r"(?:secretary of state|secretary of the commonwealth)",
}
# The title as it stands directly before a surname: "Attorney General
# Sunday", "Secretary Godlewski" (Wisconsin's own page).
ADJACENT = {
    "ag": r"(?:attorney general|(?<!of )\bag\b)",
    "sos": r"(?:secretary of state|secretary of the commonwealth|\bsecretary)",
}


def names_attorney_general(name, text, code=None):
    return names_holder(name, text, "ag", code)


# Before a title, a word that makes it someone's past: "former attorney
# general Treg Taylor" is on Alaska's page about its acting attorney general.
_PAST = r"(?<!former )(?<!then )(?<!past )(?<!previous )(?<!late )"
# Words that may stand between a name and its title, after it: the state's
# own name, "Office of the", an ordinal ("South Carolina's 51st").
_BETWEEN = {"office", "of", "the", "state", "s", "department", "justice"}


def names_holder(name, text, office="ag", code=None):
    """Whether *text* names *name* as the holder of *office* - the name
    directly beside its title, nothing else:

    - the title, then the name ("Attorney General Jeff Jackson"), unless the
      title is someone's past ("former attorney general ...");
    - the name, then the title, with only the state's name, "Office of the"
      or an ordinal between ("Phil Weiser Colorado Attorney General",
      "Alan Wilson was elected ..." is not);
    - the title, then the surname alone ("Attorney General Sunday").

    Middle initials or names may stand between first and last. A different
    first name is not a match: that is a person to look at, and NAME_FORMS
    to fill in. An 80-character window confirmed predecessors and governors
    standing beside the attorney general."""
    from .pages import state_name
    words = [w for w in _fold(re.sub(r'"[^"]*"', " ", name)).split() if w not in _SUFFIX]
    if len(words) < 2:
        return False
    first, last = re.escape(words[0]), re.escape(words[-1])
    folded = _fold(text)
    title = TITLES[office]
    full = rf"\b{first}(?: [a-z]+){{0,2}} {last}\b"
    if re.search(rf"{_PAST}{title} {full}", folded):
        return True
    if re.search(rf"{_PAST}{ADJACENT[office]} {last}\b", folded):
        return True
    allowed = _BETWEEN | ({code.lower()} | set(_fold(state_name(code)).split()) if code else set())
    for match in re.finditer(rf"{full}((?: [a-z0-9]+){{0,5}}?) {title}", folded):
        between = match.group(1).split()
        if all(w in allowed or re.fullmatch(r"\d+(st|nd|rd|th)", w) for w in between):
            return True
    return False


def acting(name, text):
    """Whether the office's page calls the person acting attorney general:
    the title directly before their name. "A bill enacting Attorney General
    Jackson's proposals", or another official called acting nearby, is not."""
    last = re.escape(_fold(name).split()[-1])
    return bool(re.search(rf"\bacting attorney general (?:[a-z]+ ){{0,2}}{last}\b", _fold(text)))


# How long to wait after each failed request for an office's page before it
# is tried again (tests set these to nothing).
_RETRY_WAITS = (2, 10)
_BOT_WALL = re.compile(r"<title>\s*(Access Denied|Just a moment|Not allowed)", re.I)


def _get_answered(url):
    """*url*'s page, or ``None`` when it did not answer after the retries:
    one timeout on Tennessee's site made it read as unconfirmed (rule 8)."""
    for wait in (*_RETRY_WAITS, None):
        try:
            return _get(url)
        except OfficersError:
            if wait is not None:
                time.sleep(wait)
    return None


class OfficeRead(list):
    """``[(url, html)]``, the pages of an office's site that answered, with
    ``unread``: ``[(what, url)]`` for each page the read set out to read that
    did not (a whole read's is empty, and it is the plain list it was)."""

    def __init__(self, pages=(), unread=()):
        super().__init__(pages)
        self.unread = list(unread)


def _unread_words(unread):
    """'the attorney general's page https://... could not be read'."""
    return " and ".join(f"{what} {url}" for what, url in unread) + " could not be read"


def _office_pages(url, pause):
    """An :class:`OfficeRead` of an office page and any page it links as its
    attorney general's own ("Attorney General", "About the Attorney
    General"), or ``None`` when the front page concludes nothing (no answer,
    a refusal, a bot wall, a page drawn by script). Each request
    is tried again before it counts as unanswered. A linked page that does
    not answer makes the read partial (``unread``), never a whole read of
    the front page alone: a front page that leaves the name to that page
    would read as an office that does not name its attorney general."""
    page = _get_answered(url)
    if page is None:
        return None
    if _BOT_WALL.search(page):
        return None
    # A page that draws itself with JavaScript (Nevada's secretary of state)
    # says nothing either way: unreadable, not "does not name them".
    if len(visible_text(page)) < 300:
        return None
    pages = OfficeRead([(url, page)])
    for href, label in re.findall(r'<a\s+href="([^"]+)"[^>]*>\s*([^<]{0,40})</a>', page):
        if re.fullmatch(r"(About|Meet)?\s*(the\s+)?Attorney General", _text(label), re.I):
            target = urllib.parse.urljoin(url, html.unescape(href))
            if urllib.parse.urlparse(target).netloc == urllib.parse.urlparse(url).netloc:
                time.sleep(pause)
                linked = _get_answered(target)
                # A bot wall, or a page that draws itself with JavaScript,
                # says nothing either way, as the front page's would.
                if (linked is None or _BOT_WALL.search(linked)
                        or len(visible_text(linked)) < 300):
                    pages.unread.append(("the attorney general's page", target))
                else:
                    pages.append((target, linked))
                break
    return pages


def _read_offices(urls, pause):
    """One :class:`OfficeRead` of every page in *urls* (an ``OFFICE_PAGES``
    entry, or the office's one front page) and the pages each links, or
    ``None`` when none of them answered. One that does not answer while
    another does makes the read partial: its words are not in the text."""
    read = OfficeRead()
    for url in urls:
        found = _office_pages(url, pause)
        if found is None:
            read.unread.append(("the office's page", url))
            continue
        read.extend(found)
        read.unread.extend(found.unread)
    return read if read else None


def office_read(urls, link, pause):
    """``(pages, (link, text, unread))`` for :func:`attorneys_general`: the
    pages of *urls* that answered (:func:`_read_offices`), and their visible
    text (``None`` when none did) with the pages that did not."""
    found = _read_offices(urls, pause)
    if not found:
        return OfficeRead(), (link, None, [])
    # The pages stay an OfficeRead, so add_ag_photos knows a photograph may
    # be on a page that did not answer.
    return found, (link, " ".join(visible_text(page) for _, page in found), found.unread)


def _office_text(url, pause):
    """``(text, unread)``: the visible text of :func:`_office_pages` (``None``
    when the site refused or drew nothing) and the pages it set out to read
    that did not answer (:class:`OfficeRead`)."""
    pages = _office_pages(url, pause)
    if not pages:
        return None, []
    return " ".join(visible_text(page) for _, page in pages), pages.unread


# ------------------------------------------- attorneys general's photographs
#
# No attorney general had a photograph (STATEGOV-13). NAAG's member pages
# hold one each, but answer a script - and a headless browser - with a
# Cloudflare challenge, and a party association's photograph is the
# party's. So the photograph is the office's own, from the very pages that
# confirmed the name (``names_holder``): never a search, and only for a
# holder the office confirmed. An image is taken when
#
# - its file name or alt text carries the holder's surname;
# - it says it is a likeness ("headshot", "portrait", "official photo",
#   "photo of") or its alt text is nothing but the name, the title and the
#   state: "Attorney General Rob Bonta", not "AG Mayes talking to a
#   townhall crowd" or "Attorney General Neronha discusses health care";
# - nothing in its file name, alt text or class says logo, banner, seal,
#   header, slider or background: Arkansas's "AG-Griffin-Logo.png" carries
#   the alt text "Tim Griffin Attorney General of Arkansas";
# - it is head-and-shoulders shaped (``enrich.portrait_check``) and no
#   heavier than a campaign's may be (``photos.too_heavy``), or a size of
#   the same file the page itself offers (its ``srcset``, a ``<picture>``'s
#   ``<source>``) is, or its host's resizer or Photon serves the same file
#   smaller (``photos.lighter_form``, weighed and checked to be the same
#   shape). Where none is, the office's file is kept all the same and said
#   (``photoHeavy``, rule 87; the owner's decision of 2026-10-25 that
#   nothing a route ties to the person is left out for its weight):
#   California's is a 6 MB original, West Virginia's 3.2 MB. The state page
#   then shows NAAG's lighter card where one is recorded (both are tied to
#   the person: ``stategov.officer_photos``), else the office's own, heavy.
#
# A size that could not be read concludes nothing (rule 8): the last
# photograph read of the same person is kept.
#
# Where the office's front page links no biography the reader can find,
# ``BIO_PAGES`` names the office's own page about its attorney general, as
# found by hand: (the page, the day it was found, the holder it was found
# for, what the page shows). The page's address is all that is typed in:
# the image on it is taken by the same words test as any other. Several
# addresses carry the holder's name, so an entry goes stale with a change of
# holder; :func:`bio_page_problems` says so when the cache's confirmed
# holder is not the entry's, or the page gave them no photograph.
_BIO_FOUND = "2026-10-19"
BIO_PAGES = {
    "AZ": ("https://www.azag.gov/kris-mayes", _BIO_FOUND, "Kris Mayes",
           "the office's page about Attorney General Kris Mayes"),
    "CA": ("https://www.oag.ca.gov/about", _BIO_FOUND, "Rob Bonta",
           "the office's 'About' page, on Attorney General Rob Bonta"),
    "HI": ("https://ag.hawaii.gov/about-us/", _BIO_FOUND, "Anne Lopez",
           "the department's 'About us' page, on Attorney General Anne Lopez"),
    "MD": ("https://oag.maryland.gov/our-office/Pages/about-the-attorney-general.aspx",
           _BIO_FOUND, "Anthony Brown", "the office's 'About the Attorney General' page"),
    "MI": ("https://www.michigan.gov/ag/team-listing-page/attorney-general-dana-nessel",
           _BIO_FOUND, "Dana Nessel", "the department's team page for Attorney General Dana Nessel"),
    "PA": ("https://www.attorneygeneral.gov/the-office/meet-the-attorney-general/", _BIO_FOUND,
           "Dave Sunday", "the office's 'Meet the Attorney General' page"),
    "SD": ("https://atg.sd.gov/OurOffice/bio.aspx", _BIO_FOUND, "Marty Jackley",
           "the office's biography of Attorney General Marty Jackley"),
    "TX": ("https://www.texasattorneygeneral.gov/about-office", _BIO_FOUND, "Ken Paxton",
           "the office's 'About the office' page, on Attorney General Ken Paxton"),
    "WA": ("https://www.atg.wa.gov/about-nick-brown", _BIO_FOUND, "Nick Brown",
           "the office's 'About Nick Brown' page"),
    "WV": ("https://ago.wv.gov/about-us/meet-attorney-general-jb-mccuskey", _BIO_FOUND,
           "J.B. McCuskey", "the office's 'Meet Attorney General JB McCuskey' page"),
}


def bio_page_problems(rows):
    """One line per ``BIO_PAGES`` entry gone stale: the confirmed holder is
    no longer the one it was found for, or the read gave that holder no
    photograph of the office's own (the page may have moved). A person reads
    the office's site again and moves or drops the entry."""
    out = []
    for code, (url, found, holder, _what) in sorted(BIO_PAGES.items()):
        row = (rows or {}).get(code) or {}
        if row.get("unconfirmed") or row.get("disputed") or not row.get("name"):
            continue
        if row["name"] != holder:
            out.append(f"{code}: officers.BIO_PAGES names {url} for {holder} (found {found}); "
                       f"the office now confirms {row['name']}: read its site again")
        elif not row.get("photo"):
            out.append(f"{code}: officers.BIO_PAGES's {url} (found {found}) gave {holder} no "
                       "photograph of the office's own: read its site again")
    return out

_LIKENESS = re.compile(r"\b(?:headshot|head shot|portrait|official photo|official headshot|"
                       r"photo of|photograph of|picture of|image of)\b")
# The same said in a file name, whose words often run together
# ("AgLizMurrillHeadshot.jpg").
_LIKENESS_FILE = ("headshot", "portrait")
_NOT_LIKENESS = re.compile(r"\b(?:logo|logos|banner|seal|hero|header|hdr|background|bg|slider|"
                           r"slide|carousel|cta|icon|signature|flag|crowd|podium|"
                           r"conference|swearing|sworn|event|events|townhall|town hall|award|"
                           r"meeting|group|with|speaks|speaking|talking|discusses|"
                           r"announces|video|map|graphic|cover|book|report)\b")
_NOT_LIKENESS_FILE = ("logo", "banner", "header", "slider", "background", "cobrand", "signature")
# Words an alt text may carry beside the name and still be only the name.
_TITLE_WORDS = {"attorney", "general", "ag", "the", "of", "office", "state", "s", "honorable",
                "hon", "official", "mr", "ms", "mrs", "dr", "jr", "sr", "ii", "iii", "iv",
                "photo", "photograph", "portrait", "headshot", "head", "shot", "picture",
                "image", "pic", "and", "reporter"}
# What a file name carries that is no word of anyone's: WordPress's
# "-scaled" on a large upload ("AG-Anne-Lopez-scaled.jpg").
_FILE_COUNTERS = {"scaled"}


def _attr(tag, name):
    found = re.search(rf'\b{name}\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', tag, re.I)
    return html.unescape((found.group(1) if found.group(1) is not None
                          else found.group(2)) if found else "")


def _img_tags(page):
    """``[(src, srcset, alt, class)]`` of every ``<img>`` on *page*, a lazy
    one's real address (``data-src``) in place of its placeholder. An image
    inside a ``<picture>`` carries the sizes its ``<source>`` elements offer
    too: Michigan's page offers its attorney general's portrait at 320px
    only there."""
    out = []
    for block in re.findall(r"<picture\b.*?</picture>|<img\b[^>]*>", page, re.I | re.S):
        if block[:8].lower() == "<picture":
            tags = re.findall(r"<img\b[^>]*>", block, re.I)
            if not tags:
                continue
            tag = tags[0]
            sources = [_attr(s, "data-srcset") or _attr(s, "srcset")
                       for s in re.findall(r"<source\b[^>]*>", block, re.I)]
        else:
            tag, sources = block, []
        src = _attr(tag, "data-src") or _attr(tag, "data-lazy-src") or _attr(tag, "src")
        if not src or src.startswith("data:"):
            continue
        srcset = ", ".join(s for s in sources + [_attr(tag, "data-srcset") or _attr(tag, "srcset")]
                           if s)
        out.append((src, srcset, _attr(tag, "alt"), _attr(tag, "class")))
    return out


def _file_words(url):
    """The words of an image's file name: split at separators, at a change
    of case ("AgLizMurrillHeadshot") and between letters and digits."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", stem)
    stem = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", stem)
    return _fold(stem.replace("_", " ").replace("-", " "))


def _compound_of(word, pieces, wanted):
    """Whether *word* is made of *pieces* end to end with *wanted* among
    them: "agmurrillheadshot" is ag + murrill + headshot. "carrie" is not
    carr + anything, nor "stanford" stan + ford unless "stan" is a piece."""
    best = {0: False}
    for end in range(1, len(word) + 1):
        for start in range(end):
            if start in best and word[start:end] in pieces:
                best[end] = best.get(end, False) or best[start] or word[start:end] == wanted
    return best.get(len(word), False)


def _names_someone_else(words, surname, firsts, middles):
    """Whether *words* put a first name other than the holder's before
    their surname: "Solicitor General Jessica Ford" on Aaron Ford's
    pages. Initials and the holder's middle names are passed over; a title
    word or nothing before the surname is no one else (rule 56)."""
    for at, word in enumerate(words):
        if word != surname:
            continue
        before = at - 1
        while before >= 0 and (len(words[before]) == 1 or words[before] in middles):
            before -= 1
        if before < 0:
            continue
        word = words[before]
        if word in firsts or word in _TITLE_WORDS or any(c.isdigit() for c in word):
            continue
        return True
    return False


def likeness_candidates(name, code, pages):
    """The images on the office's *pages* that may be *name*'s likeness,
    best first: ``[(urls, page, hinted)]``, *urls* the sizes of one file to
    try, smallest useful first. Only what the words around an image say is
    read here; whether it is head-and-shoulders shaped is the fetch's.

    The surname must be a word of the alt text or of the file name, or
    the file name's run-together words must break into the holder's name,
    title and likeness words with the surname among them
    ("AgLizMurrillHeadshot"): "Carrie-Smith-Headshot" is not Chris Carr's,
    nor "jane-stanford-portrait" Aaron Ford's. And neither may put another
    first name before the surname (rule 56): "Solicitor General Jessica
    Ford headshot" is not the attorney general's face. An evidenced
    ``NAME_FORMS`` short form counts as the holder's first name."""
    from .pages import state_name

    words = [w for w in _fold(name).split() if w not in _SUFFIX]
    if len(words) < 2:
        return []
    surname = words[-1]
    firsts = {words[0]} | {_fold(form).split()[0] for form, office_form in NAME_FORMS.items()
                           if office_form == name and _fold(form).split()}
    # Initials written together: "J.B. McCuskey" is "JB McCuskey" on his
    # office's page ("Attorney General JB McCuskey").
    initials = "".join(w for w in words[:-1] if len(w) == 1)
    if len(initials) > 1:
        firsts.add(initials)
    middles = set(words[1:-1])
    plain = set(words) | firsts | _TITLE_WORDS | set(_fold(state_name(code)).split()) \
        | {code.lower()}
    pieces = plain | firsts | set(_LIKENESS_FILE) | {"official", "photo", "pic", "img"}
    found, seen = [], set()
    for page_url, page in pages:
        for src, srcset, alt, klass in _img_tags(page):
            url = urllib.parse.urljoin(page_url, src)
            if not url.startswith("https://") or url in seen:
                continue
            seen.add(url)
            said = _fold(alt)
            file = _file_words(url)
            flat = file.replace(" ", "")
            in_alt = surname in said.split()
            in_file = surname in file.split() or any(
                _compound_of(word, pieces, surname) for word in file.split())
            if not (in_alt or in_file):
                continue
            if _names_someone_else(said.split(), surname, firsts, middles) \
                    or _names_someone_else(file.split(), surname, firsts, middles):
                continue
            if _NOT_LIKENESS.search(" ".join((said, file, _fold(klass)))) \
                    or any(word in flat for word in _NOT_LIKENESS_FILE):
                continue
            hinted = bool(_LIKENESS.search(said + " " + file)) \
                or any(word in flat for word in _LIKENESS_FILE)
            # Nothing but the name and the title, in the alt text (a middle
            # initial passed over: "Attorney General Dave W. Sunday") or,
            # with its counters set aside, the file name
            # ("AG_Marty_Jackley_0007a", "AG-Anne-Lopez-scaled").
            named = [w for w in file.split()
                     if len(w) > 1 and not any(c.isdigit() for c in w)
                     and w not in _FILE_COUNTERS]
            alt_words = {w for w in said.split() if len(w) > 1}
            if not hinted and not (alt_words and alt_words <= plain) \
                    and not (surname in named and set(named) <= plain):
                continue
            sizes = []
            for part in (srcset or "").split(","):
                bits = part.split()
                if len(bits) == 2 and bits[1].endswith("w") and bits[1][:-1].isdigit():
                    sizes.append((int(bits[1][:-1]), urllib.parse.urljoin(page_url, bits[0])))
            urls = [u for w, u in sorted(sizes) if w >= 200 and u.startswith("https://")]
            urls += [u for u in [url] if u not in urls]
            found.append((urls, page_url, hinted))
    found.sort(key=lambda item: not item[2])
    return found


def ag_photo(name, code, pages, check=None, refused=None, lighter=None, passed_over=None):
    """``(photo, why)``: ``{"photo", "photoPage", "photoWeight"}`` from the
    office's own *pages* (``[(url, html)]``), or ``None`` and why not -
    ``"none"`` when no image passed, ``"unknown"`` when one could not be
    read (rule 8). Of the sizes the page offers the first within the caps
    (``photos.too_heavy``) is taken; where every size is over them, the
    same file smaller from its host's resizer or Photon (*lighter*,
    ``photos.lighter_form``), else the file itself - never left out for its
    weight (rule 87) - with ``photoHeavy``: ``[{"url", "why", "kept"}]``.
    *check* is ``enrich.portrait_check``. An image a person refused
    (``photos.not_a_portrait``; *refused* stands in for
    ``overrides.NOT_A_PORTRAIT`` in a test) is passed over and appended to
    *passed_over*."""
    from .photos import not_a_portrait, too_heavy
    if check is None:
        from .enrich import portrait_check as check
    if lighter is None:
        from .photos import lighter_form as lighter

    unknown = False
    for urls, page_url, hinted in likeness_candidates(name, code, pages):
        heavy = []
        for url in urls:
            if not_a_portrait(url, passed_over=passed_over, table=refused):
                heavy = []
                break
            shape, weight = check(url, hinted)
            if not weight:
                if shape is None:
                    unknown = True
                    continue
                break                         # not an image
            # Head-and-shoulders: drawn in a 40px circle, so 120px is
            # enough, and a square headshot is common.
            width, height = weight["width"], weight["height"]
            if not (min(width, height) >= 120
                    and 0.5 <= width / height <= (1.35 if hinted else 1.0)):
                heavy = []
                break                         # the file's shape is every size's
            if too_heavy(weight):
                heavy.append((url, weight))
                continue
            return {"photo": url, "photoPage": page_url, "photoWeight": weight}, ""
        if heavy:
            url, weight = min(heavy, key=lambda s: (s[1].get("bytes") or 0))
            found = lighter(url, weight, lambda u: check(u, hinted)[1])
            said = [{"url": url, "why": too_heavy(weight), "kept": not found}]
            if found:
                return {"photo": found[0], "photoPage": page_url, "photoWeight": found[1],
                        "photoHeavy": said}, ""
            return {"photo": url, "photoPage": page_url, "photoWeight": weight,
                    "photoHeavy": said}, ""
    return None, "unknown" if unknown else "none"


_BIO_LABEL = re.compile(r"^(?:about|meet|biography of)(?: the)? (?:attorney general|ag)\b|"
                        r"\b(?:bio|biography)\b")


def bio_links(name, pages, limit=2):
    """The office's own pages about its attorney general that *pages* link
    and did not read: a link on the same host labelled with the holder's
    surname ("Meet AG Brown", "About Nick Brown") or as the attorney
    general's biography ("Meet the Attorney General", "Bio"). Most offices
    keep the official photograph there, not on the front page."""
    words = [w for w in _fold(name).split() if w not in _SUFFIX]
    if len(words) < 2:
        return []
    surname = words[-1]
    read = {url for url, _ in pages}
    ranked = []
    for page_url, page in pages:
        host = urllib.parse.urlsplit(page_url).hostname
        for href, label in re.findall(r'<a\b[^>]*?href="([^"#]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
            said = _fold(_text(label)).strip()
            if not said or len(said.split()) > 8:
                continue
            target = urllib.parse.urljoin(page_url, html.unescape(href))
            if urllib.parse.urlsplit(target).hostname != host or target in read:
                continue
            named = set(said.split()) & set(words)
            about = re.match(r"(?:about|meet) ", said)
            if surname in said.split() or _BIO_LABEL.search(said) or (about and named):
                rank = 0 if named and (about or _BIO_LABEL.search(said)) else 1
                ranked.append((rank, len(ranked), target))
    out = []
    for _, _, target in sorted(ranked):
        if target not in out:
            out.append(target)
    return out[:limit]


def add_ag_photos(rows, pages, previous=None, check=None, pause=1.0, get=None):
    """Give each confirmed attorney general in *rows* their office's
    photograph (:func:`ag_photo`), in place. *pages* is ``{code: [(url,
    html)]}``, the pages that were read for the name; where those show
    none, the attorney general's own page they link (:func:`bio_links`) is
    read too. *previous* is the last cache's rows. Returns the problems to
    report."""
    from .photos import not_a_portrait, withheld_files

    get = get or _get
    problems = []
    for code, row in sorted(rows.items()):
        old = (previous or {}).get(code) or {}
        if row.get("unconfirmed") and row.get("unreadable") and old.get("name") == row.get("name"):
            # The office's site concluded nothing: what its last good read
            # of the same holder refused stays recorded (rule 8), with the
            # photograph it took if a person has refused that since.
            refused_then = list(old.get("notPortraits") or [])
            withheld_files([old.get("photo")] + [h.get("url") for h in old.get("photoHeavy") or []],
                           refused_then)
            row.pop("notPortraits", None)
            if refused_then:
                row["notPortraits"] = refused_then
        if not row.get("name") or row.get("unconfirmed") or row.get("disputed"):
            continue
        if row.get("confirmationKept"):
            # The office's site concluded nothing this run: its photograph
            # stands as the confirming read left it (kept_confirmation), not
            # dropped, re-read or reported as changed.
            continue
        # A partial read (OfficeRead.unread): the page that did not answer
        # may be the one with the photograph, so finding none there
        # concludes nothing and the last one read of this holder is kept.
        unread = getattr(pages.get(code), "unread", None)
        read = list(pages.get(code) or [])
        # What a person refused is kept on the row (``notPortraits``) so
        # validate can tell a NOT_A_PORTRAIT entry still means something.
        passed_over = []
        found, why = ag_photo(row["name"], code, read, check=check, passed_over=passed_over)
        if not found and unread:
            why = "unknown"
        if not found:
            more = []
            seen = {url for url, _ in read}
            bio = BIO_PAGES[code][0] if code in BIO_PAGES else None
            wanted = [bio] if bio and bio not in seen else []
            for url in wanted + [u for u in bio_links(row["name"], read) if u not in wanted]:
                time.sleep(pause)
                try:
                    more.append((url, get(url)))
                except OfficersError:
                    why = "unknown"
            if more:
                again, why_again = ag_photo(row["name"], code, more, check=check,
                                            passed_over=passed_over)
                found = again
                why = "unknown" if "unknown" in (why, why_again) else why_again
        time.sleep(pause)
        row.pop("photoOversized", None)
        row.pop("photoHeavy", None)
        row.pop("notPortraits", None)
        if not found and why == "unknown" and old.get("name") == row["name"]:
            # A read that concludes nothing keeps the refusals its last good
            # read recorded (rule 8), the photograph it kept or not.
            passed_over.extend(u for u in old.get("notPortraits") or () if u not in passed_over)
        if not found and why == "unknown" and old.get("photo") and old.get("name") == row["name"] \
                and not not_a_portrait(old["photo"], passed_over=passed_over):
            found = {k: old[k] for k in ("photo", "photoPage", "photoWeight", "photoHeavy")
                     if old.get(k)}
            problems.append(f"{code}: {row['name']}'s photograph could not be read; "
                            "the last one read is kept")
        if passed_over:
            row["notPortraits"] = passed_over
        if found:
            row.update(found)
            heavy = (found.get("photoHeavy") or [None])[0]
            if heavy:
                problems.append(f"{code}: the office offers {row['name']}'s photograph only at "
                                f"{heavy['why']} ({heavy['url']}); "
                                + ("kept at full size and said" if heavy["kept"]
                                   else "taken smaller from the same file"))
        else:
            problems.append(f"{code}: the office's own pages show no photograph of "
                            f"{row['name']} that passes the checks")
        problems.extend(photo_changes(code, old, row))
    return problems


def photo_changes(code, old, row):
    """What changed in an attorney general's photograph since the last
    read, said so a person looks at it: a photograph added, changed or
    dropped beside a named official is a claim about their face, and a
    40px circle is not looked at by anyone else (rule 87, like courts'
    ``changed``)."""
    was, now = (old or {}).get("photo"), row.get("photo")
    if was == now:
        return []
    who = row.get("name") or (old or {}).get("name") or "the attorney general"
    if not was:
        return [f"{code}: photograph added for {who}: {now} (from {row.get('photoPage')}); "
                "look at it"]
    if not now:
        return [f"{code}: photograph dropped for {who} (was {was})"]
    return [f"{code}: photograph changed for {who}: {was} -> {now} "
            f"(from {row.get('photoPage')}); look at it"]


# A confirmation is the office's word on the day its page was read
# (``confirmedOn``), with the other association listings that page did not
# name (``alsoListed``, "Name (P)"). Where the office's site later concludes
# nothing (a timeout, a refusal, a page drawn by script: rule 8), that
# confirmation is kept - shown as the confirmed holder, as a court's last
# good read is (rule 57) - only while nothing read since contradicts it: the
# same association lists the same holder with the same party, and every
# other listing is one the confirming read saw and did not name. On
# 2026-10-20, -21 and -22 ncdoj.gov did not answer, and North Carolina's
# page called its attorney general disputed between Jeff Jackson, whom the
# office names, and Dan Bishop, whom RAGA still lists after he lost the
# 2024 election. Past ``KEPT_STALE_DAYS`` the build says a person should
# read the office's page by hand (overrides.OFFICERS_READ_BY_HAND).
KEPT_STALE_DAYS = 14


def _utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def _listing(r, party):
    return f"{r['name']} ({party})"


def _as_shown(name):
    """An association's spelling as the office writes it (``NAME_FORMS``)."""
    return " ".join(NAME_FORMS.get(name, name).split())


def kept_confirmation(old, listed, previous_day=None):
    """The previous cache's confirmed row *old*, kept where the office's site
    concluded nothing this run, or ``None``. *listed* is this run's
    ``[(listing, party, association)]``; *previous_day* the previous cache's
    ``fetched`` day, the day a row written before ``confirmedOn`` existed was
    confirmed (every run reads every office). Kept only when the same
    association lists the same holder with the same party and every other
    listing this run is one the confirming read did not name
    (``alsoListed``). A row written before this was recorded has no
    ``alsoListed``, so a state two associations list is kept only once a
    read has recorded what else it saw; a one-listing state needs nothing
    more."""
    old = old or {}
    if not old.get("name") or old.get("unconfirmed") or old.get("disputed") or old.get("unlisted"):
        return None
    day = old.get("confirmedOn") or previous_day
    if not day:
        return None
    holder = [(r, p) for r, p, source in listed if source == old.get("listedBy")
              and p == old.get("party") and _as_shown(r["name"]) == old["name"]]
    if len(holder) != 1:
        return None
    seen = old.get("alsoListed")
    others = [_listing(r, p) for r, p, _ in listed if r is not holder[0][0]]
    if others and (seen is None or any(o not in seen for o in others)):
        return None
    return dict(old, confirmedOn=day, confirmationKept=True)


def attorneys_general(raga, daga, office_texts, previous=None, previous_day=None, today=None):
    """``(rows, problems)``. *office_texts* is ``{code: (url, text or None,
    unread)}``, *unread* (which may be left off) the pages the read set out
    to read that did not answer (:class:`OfficeRead`). A row is the
    confirmed holder, an unconfirmed association listing, or a dispute;
    *problems* says what a person should look at. *previous* is the last
    cache's rows and *previous_day* its ``fetched`` day: where an office's
    site concludes nothing, its last confirmation is kept while nothing
    read contradicts it (:func:`kept_confirmation`). A partial read
    concludes only what it says: where one association lists someone, one
    that names them beside the title confirms them; one that names nobody,
    or a state two associations list (the page that did not answer may name
    the other), concludes nothing, as a site that did not answer - never
    "does not name them", never a dispute on its silence, and an earlier
    confirmation is not kept where it names another listing. *today* dates
    each confirmation (``confirmedOn``)."""
    from .government_maps import STATES
    today = today or _utc_today()
    rows, problems = {}, []
    for code in STATES:
        url, text, *rest = office_texts.get(code, ("", None))
        unread = (rest[0] if rest else None) or []
        listed = [(r, "R", "Republican Attorneys General Association") for r in [raga.get(code)] if r]
        listed += [(r, "D", "Democratic Attorneys General Association") for r in [daga.get(code)] if r]
        base = {"office": url} if url else {}
        if code in AG_SELECTION:
            base["selection"] = AG_SELECTION[code]
        if not listed:
            rows[code] = dict(base, unlisted=True)
            problems.append(f"{code}: neither association lists an attorney general")
            continue
        unreadable = "the office's site could not be read"
        named = []
        if text is not None and unread:
            unreadable = _unread_words(unread)
            named = [(r, p, s) for r, p, s in listed
                     if names_attorney_general(_as_shown(r["name"]), text, code)]
            if not named:
                text = None                     # what did not answer may name them
            elif len(listed) > 1:
                # Two associations list someone. A whole read of a site that
                # names both is a dispute (rule 55), and the page that did
                # not answer may name the other listing - a predecessor's
                # name left beside the title on the front page is enough -
                # so a partial read is never more sure than the whole read
                # would be: it concludes nothing. An earlier confirmation is
                # kept only where what answered names its holder and no one
                # else (below).
                text = None
                problems.append(f"{code}: {unreadable}; the pages that answered name "
                                + " and ".join(_as_shown(r["name"]) for r, _, _ in named)
                                + " as attorney general; with two associations' listings "
                                "a partial read confirms no one")
            else:
                problems.append(f"{code}: {unreadable}; the pages that answered name "
                                f"{_as_shown(named[0][0]['name'])} as attorney general")
        if text is None:
            kept = kept_confirmation((previous or {}).get(code), listed, previous_day)
            other = [r["name"] for r, p, s in named if kept and not (
                s == kept.get("listedBy") and p == kept.get("party")
                and _as_shown(r["name"]) == kept["name"])]
            if other:
                # Naming another listing beside the title contradicts the
                # earlier confirmation, which stood only while every other
                # listing went unnamed (kept_confirmation).
                problems.append(f"{code}: its confirmation of {kept['name']} on "
                                f"{kept['confirmedOn']} is not kept: the pages that answered "
                                f"name {' and '.join(other)} as attorney general")
                kept = None
            if kept:
                rows[code] = dict({k: v for k, v in kept.items()
                                   if k not in ("office", "selection")}, **base)
                problems.append(f"{code}: {unreadable}; its confirmation "
                                f"of {kept['name']} on {kept['confirmedOn']} is kept"
                                + (f" ({', '.join(kept['alsoListed'])} also listed, and not "
                                   "named on that read)" if kept.get("alsoListed") else ""))
            elif len(listed) > 1:
                rows[code] = dict(base, disputed=[f"{r['name']} ({p})" for r, p, _ in listed])
                problems.append(f"{code}: both associations list someone and {unreadable}")
            else:
                r, party, source = listed[0]
                rows[code] = dict(base, unconfirmed=True, unreadable=True, name=r["name"],
                                  party=party, partyKey=party, listedBy=source)
                problems.append(f"{code}: {unreadable}; {r['name']} is "
                                f"shown as {source}'s listing, unconfirmed")
            continue
        confirmed = []
        for r, party, source in listed:
            name = NAME_FORMS.get(r["name"], r["name"])
            name = " ".join(name.split())
            if names_attorney_general(name, text, code):
                confirmed.append((name, party, source, r))
            else:
                problems.append(f"{code}: {source} lists {r['name']}, whom the office's page "
                                f"does not name as attorney general")
        if len(confirmed) == 1:
            name, party, source, r = confirmed[0]
            # A partial read reaches here only where one association lists
            # someone and what answered names them (above), so ``alsoListed``
            # is a whole read's: the listings the office did not name.
            rows[code] = dict(base, name=name, party=party, partyKey=party, listedBy=source,
                              title="Acting Attorney General" if acting(name, text)
                              else "Attorney General", confirmedOn=today,
                              alsoListed=[_listing(o, p) for o, p, _ in listed if o is not r])
        elif not confirmed and len(listed) > 1:
            # Both associations list someone and the office names neither:
            # neither listing stands for the office (RAGA's alone would be
            # the man who lost North Carolina's race).
            rows[code] = dict(base, disputed=[f"{r['name']} ({p})" for r, p, _ in listed])
        elif not confirmed:
            r, party, source = listed[0]
            rows[code] = dict(base, unconfirmed=True, name=r["name"], party=party,
                              partyKey=party, listedBy=source)
        else:
            rows[code] = dict(base, disputed=[f"{n} ({p})" for n, p, _, _ in confirmed])
            problems.append(f"{code}: the office's page names both associations' members")
    return rows, problems


def ag_problems(rows):
    """What the committed attorney-general rows leave for a person to look
    at (the build re-reports these; the fetch reports more)."""
    out = []
    for code, row in sorted(rows.items()):
        if row.get("unconfirmed") and row.get("unreadable") and hand_confirms(code, "ag", row["name"]):
            continue                             # the office's page, read by hand
        if row.get("unconfirmed"):
            out.append(f"{code}: {row['name']} is shown as {row['listedBy']}'s listing; the "
                       f"office's own page did not confirm it")
        elif row.get("disputed"):
            out.append(f"{code}: the attorney general is disputed: {', '.join(row['disputed'])}")
        elif row.get("unlisted"):
            out.append(f"{code}: neither association lists an attorney general")
    return out


def fetch_attorneys_general(pause=0.5, previous=None, previous_day=None):
    """``(rows, problems)`` from the live rosters, USA.gov and every office,
    each confirmed holder with their office's photograph (``add_ag_photos``;
    *previous* is the last cache's rows, whose photograph a read that
    concludes nothing keeps, and whose confirmation an office's site that
    concludes nothing keeps: :func:`kept_confirmation`; *previous_day* is
    that cache's ``fetched`` day)."""
    from .government_maps import STATES
    from .pages import state_name
    raga, daga = parse_raga(_get(RAGA_URL)), parse_daga(_get(DAGA_URL))
    texts, read = {}, {}
    for code in STATES:
        slug = re.sub(r"[^a-z]+", "-", state_name(code).lower()).strip("-")
        url = usagov_office(_get(USAGOV_URL.format(slug=slug)))
        read[code], texts[code] = office_read(OFFICE_PAGES.get(code, [url]),
                                              OFFICE_LINK.get(code, url), pause)
        time.sleep(pause)
    rows, problems = attorneys_general(raga, daga, texts, previous, previous_day)
    problems += add_ag_photos(rows, read, previous)
    return rows, problems


def confirm_non_members(sos, pause=0.5, previous=None, previous_day=None, today=None,
                        problems=None):
    """A secretary of state NASS lists for a state that is not a member is
    not NASS speaking for its member; the office's own site, which NASS
    links, can still confirm it. Marks ``officeConfirms`` on each it does,
    with the day (``confirmedOn``), and ``officeRead`` on each it does not:
    ``"unreadable"`` where the read concluded nothing (a refusal, a timeout,
    a page drawn by script: rule 8; the page never says which), or a
    page it links as the office's own did not answer and the rest does not
    name them, ``"not-named"`` only where every page it set out to read
    answered and none names them, so the page can say why. Where the site
    concludes nothing, *previous* (the last
    cache's ``sos``) keeps an ``officeConfirms`` of the very same name, with
    its ``confirmedOn`` (else *previous_day*, the last cache's ``fetched``
    day), as ``confirmationKept``; a site read that does not name them keeps
    nothing. What was kept is appended to *problems*."""
    today = today or _utc_today()
    for code, entry in sorted(sos.items()):
        if entry.get("member") is False and office_of(entry["title"]) == "Secretary of State":
            text, unread = (_office_text(entry["website"], pause) if entry.get("website")
                            else (None, []))
            old = (previous or {}).get(code) or {}
            # A read is whole only when every page it set out to read
            # answered: a partial one confirms what it names, and its
            # silence concludes nothing (as a site that did not answer).
            unreadable = (_unread_words(unread) if text and unread
                          else "the secretary of state's site could not be read")
            if text and names_holder(entry["name"], text, "sos", code):
                entry["officeConfirms"] = True
                entry["confirmedOn"] = today
                if unread and problems is not None:
                    problems.append(f"{code}: {unreadable}; the pages that answered name "
                                    f"{entry['name']} as secretary of state")
            elif (entry.get("website") and (not text or unread) and old.get("officeConfirms")
                    and old.get("name") == entry["name"]
                    and office_of(old.get("title", "")) == "Secretary of State"
                    and (old.get("confirmedOn") or previous_day)):
                entry.update(officeConfirms=True, confirmationKept=True,
                             confirmedOn=old.get("confirmedOn") or previous_day)
                if problems is not None:
                    problems.append(f"{code}: {unreadable}; "
                                    f"its confirmation of {entry['name']} on "
                                    f"{entry['confirmedOn']} is kept")
            elif entry.get("website"):
                entry["officeRead"] = "not-named" if text and not unread else "unreadable"
                if text and unread and problems is not None:
                    problems.append(f"{code}: {unreadable}; {entry['name']} is not confirmed "
                                    "by the office")
            time.sleep(pause)
    return sos


# --------------------------------------------- officers confirmed by hand
#
# Where a script's read of the office's own site concludes nothing (rule 8),
# or the association's roster does not speak for the office, a person reads
# the office's page in their own browser (overrides.OFFICERS_READ_BY_HAND,
# rule 57's way). An entry confirms only the holder the roster names, and
# only where its quoted words pass the same test as a read page's
# (names_holder). Past this many days since the reading, the build says the
# page must be read again, as a court roster read by hand does
# (courts.STALE_DAYS).
BY_HAND_STALE_DAYS = 45
BY_HAND_OFFICES = ("ag", "sos")


def by_hand():
    """``{(code, office): {"holder", "page", "read", "words"}}``."""
    from .overrides import OFFICERS_READ_BY_HAND
    return {key: dict(zip(("holder", "page", "read", "words"), entry))
            for key, entry in OFFICERS_READ_BY_HAND.items()}


def hand_confirms(code, office, name):
    """``(name as shown, entry)`` where a reading by hand confirms *name*
    as the holder of *office* in *code*, else ``None``. Never anyone but the
    entry's own holder: a roster that names someone else is confirmed by
    nothing here (rule 3), and the entry is reported (``by_hand_unused``)."""
    entry = by_hand().get((code, office))
    if not entry or not name:
        return None
    form = " ".join(NAME_FORMS.get(name, name).split())
    if entry["holder"] not in (name, form):
        return None
    if not any(names_holder(form, piece, office, code) for piece in entry["words"]):
        return None
    return form, entry


def by_hand_errors():
    """Every entry that could not confirm anyone as it stands: an office
    this does not cover, no page or no day, no words quoted, or words that
    do not name the holder beside the title (rule 56). An error that stops
    the build (``stategov.build``), as a court roster read by hand that
    does not fit its court does."""
    out = []
    for (code, office), entry in sorted(by_hand().items()):
        where = f"{code} {office}"
        if office not in BY_HAND_OFFICES:
            out.append(f"{where}: an office the readings by hand do not cover")
            continue
        if not str(entry["page"]).startswith("https://"):
            out.append(f"{where}: a reading by hand needs the office's own page")
        try:
            datetime.date.fromisoformat(entry["read"])
        except (TypeError, ValueError):
            out.append(f"{where}: a reading by hand needs the day it was read, as YYYY-MM-DD")
        words = entry["words"]
        if isinstance(words, str) or not words:
            out.append(f"{where}: a reading by hand needs the page's words, quoted piece by piece")
        elif not any(names_holder(" ".join(NAME_FORMS.get(entry["holder"], entry["holder"]).split()),
                                  piece, office, code) for piece in words):
            out.append(f"{where}: the words quoted do not name {entry['holder']} beside the title")
    return out


def by_hand_stale(today=None):
    """Every reading by hand more than ``BY_HAND_STALE_DAYS`` old: a warning
    for a person to read the office's page again."""
    today = today or datetime.date.today()
    out = []
    for (code, office), entry in sorted(by_hand().items()):
        try:
            age = (today - datetime.date.fromisoformat(entry["read"])).days
        except (TypeError, ValueError):
            continue                             # by_hand_errors says so
        if age > BY_HAND_STALE_DAYS:
            out.append(f"{code} {office}: {entry['holder']} was confirmed by hand {age} days ago "
                       f"({entry['read']}); read {entry['page']} again and update "
                       "overrides.OFFICERS_READ_BY_HAND")
    return out


def by_hand_unused(cache):
    """Every reading by hand that confirms nobody on the page: the roster now
    names someone else (the entry is stale, and confirms nobody), names
    nobody, or the office's own site now confirms the holder itself (the
    entry may go). For validate (``officers-by-hand``)."""
    out = []
    for (code, office), entry in sorted(by_hand().items()):
        row = ((cache or {}).get(office) or {}).get(code) or {}
        name = row.get("name")
        where = f"{code} {office}"
        if not name:
            out.append(f"{where}: the roster names nobody; the entry for {entry['holder']} "
                       "confirms nobody")
        elif entry["holder"] not in (name, " ".join(NAME_FORMS.get(name, name).split())):
            out.append(f"{where}: the roster now names {name}; the entry for {entry['holder']} "
                       "confirms nobody and should go")
        elif row.get("confirmationKept"):
            # The office's site did not answer this run; its last
            # confirmation was only kept (kept_confirmation), so the site
            # does not "now answer", and the reading by hand still stands.
            continue
        elif office == "ag" and not (row.get("unconfirmed") and row.get("unreadable")):
            out.append(f"{where}: the office's own site now answers for {name}; the entry may go")
        elif office == "sos" and (row.get("member") is not False or row.get("officeConfirms")):
            out.append(f"{where}: NASS or the office's own site now answers for {name}; the "
                       "entry may go")
    return out


def kept_stale(cache, today=None):
    """Every confirmation kept from an earlier read (``confirmationKept``)
    more than ``KEPT_STALE_DAYS`` old and not since read by hand: the
    office's site has not answered since, and a person should read its page
    (overrides.OFFICERS_READ_BY_HAND). For validate
    (``officer-confirmation-kept``). Aged on the UTC day, as ``confirmedOn``
    is stamped."""
    today = today or datetime.date.fromisoformat(_utc_today())
    out = []
    for office, label in (("ag", "attorney general"), ("sos", "secretary of state")):
        for code, row in sorted(((cache or {}).get(office) or {}).items()):
            if not row.get("confirmationKept"):
                continue
            hand = hand_confirms(code, office, row.get("name"))
            if hand and str(hand[1]["read"]) >= str(row.get("confirmedOn") or "~"):
                # Read by hand on or after the kept confirmation's day:
                # by_hand_stale ages it. A reading older than the kept
                # confirmation does not stand for the read since.
                continue
            try:
                age = (today - datetime.date.fromisoformat(row.get("confirmedOn") or "")).days
            except (TypeError, ValueError):
                out.append(f"{code} {label}: {row.get('name')}'s kept confirmation carries no "
                           f"day ({row.get('confirmedOn')!r})")
                continue
            if age > KEPT_STALE_DAYS:
                out.append(f"{code} {label}: {row['name']}, confirmed by the office's site on "
                           f"{row['confirmedOn']} ({age} days ago) and kept since, as the site "
                           "has not answered; read the office's page by hand and record it in "
                           "overrides.OFFICERS_READ_BY_HAND")
    return out


def _by_hand_record(entry):
    """What the page says of a reading by hand: the office's page and the
    day (rule 57: "read by hand on")."""
    return {"url": entry["page"], "read": entry["read"]}


def fetch(previous=None):
    """``{"sos": {...}, "lt": {...}, "ag": {...}}`` from the live rosters,
    with the attorney-general problems to report. *previous* is the cache
    being replaced."""
    previous = previous or {}
    # The day the previous cache was read: a confirmed row it holds that
    # predates ``confirmedOn`` was confirmed that day (kept_confirmation).
    day = (previous.get("fetched") or "")[:10] or None
    ag, problems = fetch_attorneys_general(previous=previous.get("ag"), previous_day=day)
    sos_problems = []
    sos = confirm_non_members(parse_nass(_get(NASS_URL)), previous=previous.get("sos"),
                              previous_day=day, problems=sos_problems)
    return {"sos": sos, "lt": parse_nlga(_get(NLGA_URL)), "ag": ag, "agProblems": problems,
            "sosProblems": sos_problems}


# ------------------------------------------------------------- for a state

_PERSON = ("name", "party", "partyKey", "title", "website", "photo", "bio", "selection",
           "electionChief", "address", "phone", "email")


def _person(entry):
    return {k: entry[k] for k in _PERSON if entry.get(k) not in (None, "")}


def _surname_in(name, url):
    """Whether a photo's file name carries the person's surname - NASS's
    alt text calls every one of them a state seal."""
    surname = re.sub(r"[^a-z]", "", (name.split() or [""])[-1].lower().replace("jr.", ""))
    if surname in ("jr", "sr", "ii", "iii", "") and len(name.split()) > 1:
        surname = re.sub(r"[^a-z]", "", name.split()[-2].lower())
    file = re.sub(r"[^a-z]", "", url.rsplit("/", 1)[-1].split("?")[0].lower())
    return bool(surname) and surname in file


NASS_BY = "National Association of Secretaries of State"
NLGA_BY = "National Lieutenant Governors Association"


def _credited(person, by):
    """*person* with whose photograph it is, when it has one (rule 87) and
    no person has refused it (``photos.refused``: Massachusetts's NASS card
    of William Galvin shows people walking behind him)."""
    from .photos import refused
    if person.get("photo") and refused(person["photo"]):
        del person["photo"]
    if person.get("photo"):
        person["photoBy"] = by
    return person


def for_state(code, cache, disputes):
    """``{"lt": ..., "sos": ...}`` for one state, as the page shows them.
    *disputes* is ``overlaps(...)``: an office the rosters disagree about
    shows both names and neither as the holder."""
    out = {}
    named = {(c, office): (a, b) for c, office, a, b in disputes}
    lt = cache["lt"].get(code)
    if (code, "Lieutenant Governor") in named:
        out["lt"] = {"disputed": list(named[(code, "Lieutenant Governor")])}
    elif lt and lieutenant(lt):
        out["lt"] = ({"vacant": True, "title": lt["title"]} if lt.get("vacant")
                     else _credited(_person(lt), NLGA_BY))
    elif lt:
        # No lieutenant governor. The officer first in line is named only
        # when that office is neither vacant nor in dispute.
        out["lt"] = {"none": True}
        if not lt.get("vacant") and (code, office_of(lt["title"])) not in named:
            out["lt"]["successor"] = _credited(_person(lt), NLGA_BY)
    if code in cache.get("ag", {}):
        out["ag"] = dict(cache["ag"][code])
        # A kept confirmation is shown as the confirmed holder, in the same
        # words (kept_confirmation; validate says when it grows old).
        kept = out["ag"].pop("confirmationKept", None)
        for field in ("photoWeight", "photoOversized", "notPortraits", "confirmedOn",
                      "alsoListed"):
            out["ag"].pop(field, None)
        from .photos import refused
        if out["ag"].get("photo") and refused(out["ag"]["photo"]):
            # A file a person refused since it was read (rule 38: someone
            # else in the frame) is not shown, whatever the cache holds.
            for field in ("photo", "photoPage", "photoHeavy"):
                out["ag"].pop(field, None)
        if out["ag"].get("photo"):
            # The office's own photograph, from the page it was read on.
            host = urllib.parse.urlsplit(out["ag"].get("photoPage") or "").hostname or ""
            out["ag"]["photoBy"] = ("the office's website (" + host.removeprefix("www.") + ")"
                                    if host else "the office's website")
        hand = (((out["ag"].get("unconfirmed") and out["ag"].get("unreadable")) or kept)
                and hand_confirms(code, "ag", out["ag"].get("name")))
        if hand:
            # A script's read of the office's site concluded nothing; its
            # page, read by hand, names them beside the title
            # (overrides.OFFICERS_READ_BY_HAND).
            # Where the site's last confirmation is kept, the reading by hand
            # is what a person read since (KEPT_STALE_DAYS asks for one).
            name, entry = hand
            for field in ("unconfirmed", "unreadable"):
                out["ag"].pop(field, None)
            out["ag"]["name"] = name
            out["ag"]["title"] = ("Acting Attorney General" if any(acting(name, w) for w in entry["words"])
                                  else "Attorney General")
            out["ag"]["readByHand"] = _by_hand_record(entry)
    sos = cache["sos"].get(code)
    if (code, "Secretary of State") in named:
        out["sos"] = {"disputed": list(named[(code, "Secretary of State")])}
    elif sos and office_of(sos["title"]) == "Lieutenant Governor":
        out["sos"] = {"none": True, "electionChief": "lieutenant governor" if sos["electionChief"] else ""}
    elif sos:
        person = _person(sos)
        if person.get("photo") and not _surname_in(sos["name"], person["photo"]):
            del person["photo"]
        if sos.get("member") is False and (not sos.get("officeConfirms")
                                           or sos.get("confirmationKept")):
            hand = hand_confirms(code, "sos", sos["name"])
            if hand:
                # NASS does not speak for a non-member; the office's own
                # page, read by hand, names them (OFFICERS_READ_BY_HAND).
                person["name"] = hand[0]
                person["readByHand"] = _by_hand_record(hand[1])
                # The page read by hand names the holder, not their party:
                # that is still the non-member listing's, and said so.
                person["partyFrom"] = NASS_BY
            elif sos.get("officeConfirms"):
                pass                             # the site's last confirmation, kept
            else:
                person["notMember"] = True
                if sos.get("officeRead"):
                    # Why the office's own site did not confirm them.
                    person["officeRead"] = sos["officeRead"]
        out["sos"] = _credited(person, NASS_BY)
    return out


# ------------------------------------------------------------------- cache

def save_cache(payload, root="."):
    payload = dict(payload, fetched=datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"))
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
