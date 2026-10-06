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


def fetch():
    """``{"sos": {...}, "lt": {...}}`` from the live rosters."""
    return {"sos": parse_nass(_get(NASS_URL)), "lt": parse_nlga(_get(NLGA_URL))}


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
    sos = cache["sos"].get(code)
    if (code, "Secretary of State") in named:
        out["sos"] = {"disputed": list(named[(code, "Secretary of State")])}
    elif sos and office_of(sos["title"]) == "Lieutenant Governor":
        out["sos"] = {"none": True, "electionChief": "lieutenant governor" if sos["electionChief"] else ""}
    elif sos:
        person = _person(sos)
        if person.get("photo") and not _surname_in(sos["name"], person["photo"]):
            del person["photo"]
        if sos.get("member") is False:
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
