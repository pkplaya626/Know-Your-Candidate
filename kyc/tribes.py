"""Tribal governments and who leads them, from the BIA's Tribal Leaders Directory.

The guide's tribal page explained sovereignty and jurisdiction and named no
nation and no leader (audit 2026-10-17, GUIDE-18). The Bureau of Indian
Affairs keeps the Tribal Leaders Directory (bia.gov/service/tribal-leaders-
directory), updated weekly, as an ArcGIS feature service whose rows are the
Federal Register's list of recognized entities, one row a name - 577 names
on 2026-10-18, where the Register counts 575 entities and four of its names
send the reader to another ("Arctic Village (See Native Village of Venetie
Tribal Government)") - plus 25 bands and communities of a tribe
("affiliates"), each with its leader and the state of its office. So the
page never totals the rows as a count of nations (rule 53).

What is kept, and what is not:

- the entry's name, BIA's id for it (``GlobalID``), whether it is a tribe or
  an affiliate, the leader's name and title, and the state of its office -
  its physical address's state, or where that is blank the mailing
  address's (``stateFrom``). Never phones, emails or street addresses, and
  never the website: a lapsed domain in a directory looks like the tribe's
  own (rule 35), and BIA's page is linked instead.
- an affiliate is placed under its tribe only by the directory's own name
  for it, "Te-Moak Tribe of Western Shoshone Indians of Nevada (Elko Band)"
  under the row named "Te-Moak Tribe of Western Shoshone Indians of
  Nevada"; one whose tribe is not a row is listed on its own, and one with
  no state of its own and no tribe to sit under is reported, never placed.
- the state is where the office is. A nation whose lands reach into
  several states is listed in one (the guide's map says so); no state is
  inferred from a name.

BIA warns that tribal elections change leaders faster than it can record,
so the page names the directory and the day it was last edited beside
every name. The query pages on OBJECTID, a unique key, and the rows must
number what the service's own count says, or nothing is written (rule 36).

    python build_profile_site.py tribes            # refresh (network)
    python build_profile_site.py tribes --check    # report from the cache
"""

import datetime
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .normalize import US_STATES

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "tribal_leaders.json")
SOURCE = "https://www.bia.gov/service/tribal-leaders-directory"
SERVICE = ("https://services1.arcgis.com/UxqqIfhng71wUT9x/arcgis/rest/services/"
           "TribalLeadership_Directory/FeatureServer/0")
FIELDS = ("OBJECTID", "GlobalID", "tribefullname", "tribalcomponent", "salutation",
          "firstname", "middlename", "lastname", "suffix", "jobtitle", "state",
          "mailingaddressstate", "biaregion")
PAGE = 500
USER_AGENT = "KnowYourCandidate/1.0 (+https://candidates.radicalrelay.us)"
TRIBE, AFFILIATE = "tribe", "affiliate"
# The directory's two components, as its service lists them (distinct values
# of ``tribalcomponent``, read 2026-10-18). Anything else is a change in the
# source, refused rather than filed as a band (rule 53).
COMPONENTS = {"Tribe": TRIBE, "Affiliate (band, community, village, island, etc...)": AFFILIATE}
# The directory marks a disputed leadership with an asterisk on the leader's
# name and title and this note after the title ("*Chief (Subject to Tribal
# Leadership Dispute)"). The page says "leadership disputed" in words; the
# asterisks and the note are not shown as part of a name.
_DISPUTE = re.compile(r"\s*\(\s*subject to tribal leadership dispute\s*\)", re.I)
_STATE_CODES = {name.title(): code for name, code in US_STATES.items()}
_INVISIBLE = re.compile("[​‌‍⁠﻿]")


class TribesError(RuntimeError):
    pass


def _get_json(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise TribesError(f"could not read {url}: {exc}") from exc
    if isinstance(data, dict) and data.get("error"):
        raise TribesError(f"{url}: the service answered {data['error']}")
    return data


def clean(text):
    """Whitespace collapsed, invisible characters gone; None for nothing."""
    text = _INVISIBLE.sub("", str(text or "")).strip()
    return re.sub(r"\s+", " ", text) or None


def state_code(name):
    """``"AK"`` for ``"Alaska"``; None for a blank; an error for anything
    else, which is a change in the source to look at, not to guess past."""
    name = clean(name)
    if not name:
        return None
    code = _STATE_CODES.get(name.title())
    if not code:
        raise TribesError(f"unknown state {name!r} in the directory")
    return code


def leader(row):
    """The leader's name as the directory writes it, without salutation."""
    parts = [clean(row.get(k)) for k in ("firstname", "middlename", "lastname")]
    name = " ".join(p for p in parts if p)
    suffix = clean(row.get("suffix"))
    if name and suffix:
        name += (" " if suffix.lower().rstrip(".") in ("ii", "iii", "iv") else ", ") + suffix
    return name or None


def _undisputed(text):
    """*text* without the directory's dispute marks, and whether it had them."""
    if not text:
        return text, False
    disputed = bool(_DISPUTE.search(text))
    text = _DISPUTE.sub("", text)
    starred = "*" in text
    text = clean(text.strip("* ")) if starred else text
    return text, disputed or starred


def parse(rows):
    """The directory's rows as the cache's entries, in name order."""
    entries, seen = [], set()
    for row in rows:
        ident = clean(row.get("GlobalID"))
        name = clean(row.get("tribefullname"))
        if not ident or not name:
            raise TribesError(f"a row with no id or no name: {row.get('OBJECTID')}")
        ident = ident.lower().strip("{}")
        if ident in seen:
            raise TribesError(f"id {ident} twice")
        seen.add(ident)
        component = clean(row.get("tribalcomponent")) or ""
        if component not in COMPONENTS:
            raise TribesError(f"{name}: unknown component {component!r} in the directory")
        who, disputed_who = _undisputed(leader(row))
        title, disputed_title = _undisputed(clean(row.get("jobtitle")))
        if "*" in (who or "") + (title or ""):
            raise TribesError(f"{name}: an asterisk inside a leader's name or title")
        state, came = state_code(row.get("state")), "office"
        if not state:
            state, came = state_code(row.get("mailingaddressstate")), "mailing"
        entry = {
            "id": ident,
            "name": name,
            "kind": COMPONENTS[component],
            "leader": who,
            "title": title,
            "state": state,
            "region": clean(row.get("biaregion")),
        }
        if state and came == "mailing":
            entry["stateFrom"] = "mailing"
        if disputed_who or disputed_title:
            entry["disputed"] = True
        entries.append(entry)
    for e in entries:
        if e["kind"] == AFFILIATE:
            parent = _parent(e, entries)
            if parent:
                e["parent"] = parent["id"]
    return sorted(entries, key=lambda e: (e["name"].lower(), e["id"]))


def _split(name, separators):
    """*name* split at the first of *separators* to occur in it: "Capitan
    Grande Band ... of California: Viejas (Baron Long) Group ..." splits at
    the colon, not at the parenthesis inside the group's own name."""
    found = [(name.index(sep), sep) for sep in separators if sep in name]
    if not found:
        return name, ""
    at, sep = min(found)
    base, rest = name[:at], name[at + len(sep):]
    return base, rest[:-1] if sep == " (" and rest.endswith(")") else rest


def _parent(affiliate, entries):
    """The one tribe row the directory names an affiliate under: the same
    name before its parenthesis ("Te-Moak Tribe of Western Shoshone Indians
    of Nevada (Elko Band)"), dash ("Passamaquoddy Tribe - Pleasant
    Point") or colon ("Capitan Grande Band of Diegueno Mission Indians of
    California: Barona Group of ..."), whose own parenthesis, where it has one, names the affiliate
    ("(Four constituent bands: Battle Mountain Band; Elko Band; ...)").
    None unless exactly one row fits."""
    base, part = _split(affiliate["name"], (" (", " - ", ": "))
    if not part:
        return None
    fits = []
    for e in entries:
        if e["kind"] != TRIBE:
            continue
        name, listed = _split(e["name"], (" (",))
        if name == base and (not listed or part in listed):
            fits.append(e)
    return fits[0] if len(fits) == 1 else None


def fetch(get=_get_json, pause=1.0, sleep=time.sleep):
    """Every row of the directory, paged on OBJECTID and counted."""
    count = get(SERVICE + "/query?" + urllib.parse.urlencode(
        {"where": "1=1", "returnCountOnly": "true", "f": "json"}))["count"]
    rows, offset = [], 0
    while True:
        page = get(SERVICE + "/query?" + urllib.parse.urlencode({
            "where": "1=1", "outFields": ",".join(FIELDS), "returnGeometry": "false",
            "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": PAGE,
            "f": "json"}))
        got = [f["attributes"] for f in page.get("features") or []]
        rows += got
        offset += len(got)
        if not got or (len(got) < PAGE and not page.get("exceededTransferLimit")):
            break
        sleep(pause)
    ids = [r.get("OBJECTID") for r in rows]
    if len(rows) != count or len(set(ids)) != len(ids):
        raise TribesError(f"the directory counts {count} rows and {len(rows)} came back "
                          f"({len(set(ids))} distinct); nothing written")
    layer = get(SERVICE + "?f=json")
    edited = ((layer.get("editingInfo") or {}).get("dataLastEditDate"))
    out = {"source": SOURCE, "service": SERVICE, "count": count, "entries": parse(rows)}
    if edited:
        out["edited"] = datetime.datetime.fromtimestamp(
            edited / 1000, datetime.timezone.utc).date().isoformat()
    return out


def placed(cache):
    """``{state: [tribe entry, with "affiliates": [...]]}`` and the entries
    no state can be given: an affiliate goes under its tribe, in the tribe's
    state; one with no tribe row stands on its own where it has a state."""
    entries = (cache or {}).get("entries") or []
    by_id = {e["id"]: dict(e, affiliates=[]) for e in entries if e["kind"] == TRIBE}
    out, unplaced = {}, []
    for e in entries:
        if e["kind"] == AFFILIATE and e.get("parent") in by_id:
            by_id[e["parent"]]["affiliates"].append(e)
    for e in entries:
        if e["kind"] == TRIBE:
            item = by_id[e["id"]]
        elif e.get("parent") in by_id:
            continue
        else:
            item = dict(e, affiliates=[])
        if item.get("state"):
            out.setdefault(item["state"], []).append(item)
        else:
            unplaced.append(item["name"])
    return out, unplaced


def problems(cache):
    """What the build reports about the cache, as strings."""
    if not cache:
        return []
    out = []
    _, unplaced = placed(cache)
    out += [f"no state for {name}" for name in unplaced]
    return out


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
