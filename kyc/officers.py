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
            img = re.search(r'<img[^>]*\bsrcset="([^"]+)"', before)
            if img and _surname_in(name, _smallest(img.group(1))):
                entry["photo"] = _smallest(img.group(1))
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
    """A page's readable text: no head, script, style or title."""
    body = re.sub(r"<(head|script|style|title|noscript)\b[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    return _text(body)


_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


TITLES = {
    "ag": r"(?:attorney general|\bag\b)",
    "sos": r"(?:secretary of state|secretary of the commonwealth)",
}
# The title as it stands directly before a surname: "Attorney General
# Sunday", "Secretary Godlewski" (Wisconsin's own page).
ADJACENT = {
    "ag": r"(?:attorney general|\bag\b)",
    "sos": r"(?:secretary of state|secretary of the commonwealth|\bsecretary)",
}


def names_attorney_general(name, text):
    return names_holder(name, text, "ag")


def names_holder(name, text, office="ag"):
    """Whether *text* names *name* as the holder of *office*: its title
    ("Attorney General" or "AG"; "Secretary of State") within 80 characters
    of the full name, middle initials and nicknames in quotes allowed between
    first and last; or the title and the surname with nothing between. A
    different first name is not a match: that is a person to look at, and
    NAME_FORMS to fill in."""
    words = [w for w in _fold(re.sub(r'"[^"]*"', " ", name)).split() if w not in _SUFFIX]
    if len(words) < 2:
        return False
    first, last = re.escape(words[0]), re.escape(words[-1])
    folded = _fold(text)
    title = TITLES[office]
    # Up to two middle words: initials, or names ("Candi Mundon King").
    full = rf"\b{first}(?: [a-z]+){{0,2}} {last}\b"
    near = rf"{title}.{{0,80}}?{full}|{full}.{{0,80}}?{title}"
    adjacent = rf"{ADJACENT[office]} {last}\b"
    return bool(re.search(near, folded) or re.search(adjacent, folded))


def acting(name, text):
    """Whether the office's page calls the person acting attorney general."""
    last = re.escape(_fold(name).split()[-1])
    return bool(re.search(rf"acting attorney general.{{0,60}}?\b{last}\b|\b{last}\b.{{0,60}}?"
                          rf"acting attorney general", _fold(text)))


def _office_text(url, pause):
    """The visible text of an office page and of any page it links as its
    attorney general's own ("Attorney General", "About the Attorney
    General"), or ``None`` when the site refuses the request. A failed
    request is tried once more before the office counts as unreadable: one
    timeout on Tennessee's site made it read as unconfirmed (rule 8)."""
    page = None
    for wait in (2, 10, 0):
        try:
            page = _get(url)
            break
        except OfficersError:
            time.sleep(wait)
    if page is None:
        return None
    if re.search(r"<title>\s*(Access Denied|Just a moment|Not allowed)", page, re.I):
        return None
    texts = [visible_text(page)]
    # A page that draws itself with JavaScript (Nevada's secretary of state)
    # says nothing either way: unreadable, not "does not name them".
    if len(texts[0]) < 300:
        return None
    for href, label in re.findall(r'<a\s+href="([^"]+)"[^>]*>\s*([^<]{0,40})</a>', page):
        if re.fullmatch(r"(About|Meet)?\s*(the\s+)?Attorney General", _text(label), re.I):
            target = urllib.parse.urljoin(url, html.unescape(href))
            if urllib.parse.urlparse(target).netloc == urllib.parse.urlparse(url).netloc:
                time.sleep(pause)
                try:
                    texts.append(visible_text(_get(target)))
                except OfficersError:
                    pass
                break
    return " ".join(texts)


def attorneys_general(raga, daga, office_texts):
    """``(rows, problems)``. *office_texts* is ``{code: (url, text or None)}``.
    A row is the confirmed holder, an unconfirmed association listing, or a
    dispute; *problems* says what a person should look at."""
    from .government_maps import STATES
    rows, problems = {}, []
    for code in STATES:
        url, text = office_texts.get(code, ("", None))
        listed = [(r, "R", "Republican Attorneys General Association") for r in [raga.get(code)] if r]
        listed += [(r, "D", "Democratic Attorneys General Association") for r in [daga.get(code)] if r]
        base = {"office": url} if url else {}
        if code in AG_SELECTION:
            base["selection"] = AG_SELECTION[code]
        if not listed:
            rows[code] = dict(base, unlisted=True)
            problems.append(f"{code}: neither association lists an attorney general")
            continue
        if text is None:
            if len(listed) > 1:
                rows[code] = dict(base, disputed=[f"{r['name']} ({p})" for r, p, _ in listed])
                problems.append(f"{code}: both associations list someone and the office "
                                f"could not be read")
            else:
                r, party, source = listed[0]
                rows[code] = dict(base, unconfirmed=True, name=r["name"], party=party,
                                  partyKey=party, listedBy=source)
                problems.append(f"{code}: the office's site could not be read; {r['name']} is "
                                f"shown as {source}'s listing, unconfirmed")
            continue
        confirmed = []
        for r, party, source in listed:
            name = NAME_FORMS.get(r["name"], r["name"])
            name = " ".join(name.split())
            if names_attorney_general(name, text):
                confirmed.append((name, party, source, r))
            else:
                problems.append(f"{code}: {source} lists {r['name']}, whom the office's page "
                                f"does not name as attorney general")
        if len(confirmed) == 1:
            name, party, source, r = confirmed[0]
            rows[code] = dict(base, name=name, party=party, partyKey=party, listedBy=source,
                              title="Acting Attorney General" if acting(name, text)
                              else "Attorney General")
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
        if row.get("unconfirmed"):
            out.append(f"{code}: {row['name']} is shown as {row['listedBy']}'s listing; the "
                       f"office's own page did not confirm it")
        elif row.get("disputed"):
            out.append(f"{code}: the attorney general is disputed: {', '.join(row['disputed'])}")
        elif row.get("unlisted"):
            out.append(f"{code}: neither association lists an attorney general")
    return out


def fetch_attorneys_general(pause=0.5):
    """``(rows, problems)`` from the live rosters, USA.gov and every office."""
    from .government_maps import STATES
    from .pages import state_name
    raga, daga = parse_raga(_get(RAGA_URL)), parse_daga(_get(DAGA_URL))
    texts = {}
    for code in STATES:
        slug = re.sub(r"[^a-z]+", "-", state_name(code).lower()).strip("-")
        url = usagov_office(_get(USAGOV_URL.format(slug=slug)))
        pages = OFFICE_PAGES.get(code, [url])
        found = [t for t in (_office_text(p, pause) for p in pages) if t]
        texts[code] = (OFFICE_LINK.get(code, url), " ".join(found) if found else None)
        time.sleep(pause)
    return attorneys_general(raga, daga, texts)


def confirm_non_members(sos, pause=0.5):
    """A secretary of state NASS lists for a state that is not a member is
    not NASS speaking for its member; the office's own site, which NASS
    links, can still confirm it. Marks ``officeConfirms`` on each it does."""
    for code, entry in sorted(sos.items()):
        if entry.get("member") is False and office_of(entry["title"]) == "Secretary of State":
            text = _office_text(entry["website"], pause) if entry.get("website") else None
            if text and names_holder(entry["name"], text, "sos"):
                entry["officeConfirms"] = True
            time.sleep(pause)
    return sos


def fetch():
    """``{"sos": {...}, "lt": {...}, "ag": {...}}`` from the live rosters,
    with the attorney-general problems to report."""
    ag, problems = fetch_attorneys_general()
    return {"sos": confirm_non_members(parse_nass(_get(NASS_URL))),
            "lt": parse_nlga(_get(NLGA_URL)), "ag": ag, "agProblems": problems}


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
        out["lt"] = {"vacant": True, "title": lt["title"]} if lt.get("vacant") else _person(lt)
    elif lt:
        # No lieutenant governor. The officer first in line is named only
        # when that office is neither vacant nor in dispute.
        out["lt"] = {"none": True}
        if not lt.get("vacant") and (code, office_of(lt["title"])) not in named:
            out["lt"]["successor"] = _person(lt)
    if code in cache.get("ag", {}):
        out["ag"] = cache["ag"][code]
    sos = cache["sos"].get(code)
    if (code, "Secretary of State") in named:
        out["sos"] = {"disputed": list(named[(code, "Secretary of State")])}
    elif sos and office_of(sos["title"]) == "Lieutenant Governor":
        out["sos"] = {"none": True, "electionChief": "lieutenant governor" if sos["electionChief"] else ""}
    elif sos:
        person = _person(sos)
        if person.get("photo") and not _surname_in(sos["name"], person["photo"]):
            del person["photo"]
        if sos.get("member") is False and not sos.get("officeConfirms"):
            person["notMember"] = True
        out["sos"] = person
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
