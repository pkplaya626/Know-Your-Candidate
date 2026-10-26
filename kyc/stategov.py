"""Who runs each state: its governor, and which party holds each chamber.

The governor comes from the NGA's roster (kyc/executives.py). Chamber
control is counted from the legislators Open States lists
(``data/state_legislators.json``) against each chamber's seats as NCSL
counts them (kyc/government_maps.SEATS): a party holds a chamber when it has
more than half of *all* its seats, so a seat with nobody listed is never
counted for anyone, and never called vacant (rule 19).

NCSL's table of partisan composition is a second, independent count. It is
dated - NCSL updates it a few times a year - and where it and Open States
disagree about which party holds a chamber, the page shows neither and says
the sources disagree (rule 53). Neither is quietly preferred.

A majority of seats is not always a majority that governs. Alaska's two
chambers are run by coalitions across parties; COALITIONS records that,
with the evidence, and ``check`` reports the note once the seat counts no
longer fit it.
"""

import datetime
import html
import json
import os
import re
import urllib.request

from .government_maps import LOWER_CHAMBER, SEATS, STATES

NCSL_URL = "https://www.ncsl.org/about-state-legislatures/state-partisan-composition"
NCSL_SOURCE = "National Conference of State Legislatures, State Partisan Composition"
NCSL_CACHE = os.path.join("candidate_profiles_site", "data", "partisan_composition.json")
USER_AGENT = "Mozilla/5.0 (compatible; know-your-candidate/1.0)"

# Chambers whose majority of seats does not run them. The Legislature's own
# roster names a Republican as minority leader in both chambers although
# Republicans hold a majority of the seats in each: the majorities that elect
# the leaders are coalitions of members from both parties.
#
# A note holds for one legislature. *session* is read from the legislators'
# own links (Open States lists each Alaska member's akleg.gov page, whose
# address carries the legislature's number): once the members listed belong
# to a later legislature, or the seats stop fitting, the note is not shown
# and ``build`` reports it.
COALITIONS = {
    "AK": {
        "party": "R",
        "chambers": ("upper", "lower"),
        "session": 34,
        "sessionLink": r"akleg\.gov/basis/Member/Detail/(\d+)",
        "text": ("Republicans hold a majority of the seats in both chambers, but the "
                 "Legislature's roster lists a Republican as minority leader in each: both "
                 "chambers are run by coalitions of members from both parties."),
        "source": "https://www.akleg.gov/basis/mbr_info.asp?session=34",
        "checked": "2026-10-05",
    },
}


def coalition_holds(code, records, chambers):
    """``(holds, why)`` for a state's coalition note against the current
    records and seat counts."""
    note = COALITIONS[code]
    for which in note["chambers"]:
        if (chambers.get(which) or {}).get("majority") != note["party"]:
            return False, (f"the note says {note['party']} holds a majority of the {which} "
                           f"chamber's seats; it no longer does")
    sessions = [int(n) for r in records for link in r.get("links", ())
                for n in re.findall(note["sessionLink"], link)]
    if not sessions or max(sessions) != note["session"]:
        return False, (f"the note is about legislature {note['session']}; the members listed "
                       f"belong to {max(sessions) if sessions else 'an unknown one'}")
    return True, ""



class StateGovError(RuntimeError):
    """The NCSL table could not be read, or does not have the expected shape."""


# -------------------------------------------------------------------- NCSL

def _cells(row):
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


_HEAD = ["State", "Total House", "House Dem", "House Rep", "House Third Party",
         "House Vacancies", "Total Senate", "Senate Dem", "Senate Rep", "Senate Third Party",
         "Senate Vacancies", "Legislative Control", "Governor Party", "State Control"]


def parse_ncsl(page):
    """``{"updated", "states": {code: {...}}}`` from NCSL's composition page."""
    from .normalize import US_STATES
    start = page.find('<table id="partisanComp"')
    if start < 0:
        raise StateGovError("NCSL's page has no partisanComp table")
    table = page[start:page.find("</table>", start)]
    heads = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())
             for h in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
    if heads != _HEAD:
        raise StateGovError(f"NCSL's table changed its columns: {heads}")
    by_name = {name.title(): code for name, code in US_STATES.items()}
    states = {}

    def num(text):
        return int(text) if text.isdigit() else 0

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = _cells(row)
        if not cells or cells[0] not in by_name:
            continue
        lower = {"seats": num(cells[1]), "D": num(cells[2]), "R": num(cells[3]),
                 "other": num(cells[4]), "vacant": num(cells[5])}
        upper = {"seats": num(cells[6]), "D": num(cells[7]), "R": num(cells[8]),
                 "other": num(cells[9]), "vacant": num(cells[10])}
        states[by_name[cells[0]]] = {"upper": upper, "lower": lower, "legislature": cells[11],
                                     "governor": cells[12], "control": cells[13]}
    updated = re.search(r"Updated\s+([A-Z][a-z]+ \d{1,2}, \d{4})", page)
    missing = [c for c in STATES if c not in states]
    if missing:
        raise StateGovError(f"NCSL's table has no row for {', '.join(missing)}")
    return {"updated": updated.group(1) if updated else "", "states": states}


def fetch_ncsl():
    request = urllib.request.Request(NCSL_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            page = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise StateGovError(f"could not fetch {NCSL_URL}: {exc}") from exc
    return parse_ncsl(page)


def save_ncsl(table, root="."):
    payload = dict(table, source=NCSL_SOURCE, url=NCSL_URL, fetched=datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds"))
    path = os.path.join(root, NCSL_CACHE)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def load_ncsl(root="."):
    path = os.path.join(root, NCSL_CACHE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ----------------------------------------------------------------- counting

def majority(counts, seats):
    """The party holding more than half of *seats*, else ``None``."""
    for key in ("D", "R"):
        if counts.get(key, 0) * 2 > seats:
            return key
    return None


def chamber(records, which, seats):
    """Party counts for one chamber from the Open States records."""
    counts = {"D": 0, "R": 0, "I": 0, "N": 0}
    for record in records:
        if record["chamber"] == which and not record.get("tribalSeat"):
            counts[record["partyKey"]] += 1
    listed = sum(counts.values())
    return dict(counts, seats=seats, listed=listed, majority=majority(counts, seats))


def _date(text):
    try:
        return datetime.datetime.strptime(text.strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def in_office_since(terms):
    """The first day of the governor's current unbroken run of terms, and how
    many terms it spans. A gap of more than a month starts a new run."""
    spans = []
    for term in terms:
        start, _, end = term.partition(" - ")
        spans.append((_date(start), None if end.strip() == "Current" else _date(end), start.strip()))
    if not spans or spans[-1][0] is None:
        return "", 0
    run = [spans[-1]]
    for earlier in reversed(spans[:-1]):
        if earlier[1] is None or run[0][0] is None or (run[0][0] - earlier[1]).days > 31:
            break
        run.insert(0, earlier)
    return run[0][2], len(run)


def _governor(gov, problems=None):
    """What the page shows of a governor. The first day in office is shown
    only when Wikidata records the same date for them in that office: the
    NGA's pages give Kay Ivey April 19, 2017 and Kim Reynolds May 27, 2017,
    and they were sworn in on April 10 and May 24."""
    since, terms = in_office_since(gov.get("terms", []))
    first = _date(since) if since else None
    confirmed = first is not None and first.isoformat() in (gov.get("wikidataStarts") or ())
    if since and not confirmed and problems is not None and gov.get("wikidataStarts"):
        problems.append(f"{gov.get('state', '?')}: the NGA says {gov['name']} took office on "
                        f"{since}; Wikidata records {', '.join(gov['wikidataStarts'])}")
    out = {"name": gov["name"], "party": gov["party"], "partyKey": gov["partyKey"],
           "since": since if confirmed else "", "terms": terms, "profile": gov["profile"]}
    for key in ("website", "phone", "address"):
        if gov.get(key):
            out[key] = gov[key]
    shown = headshot(gov)
    if shown:
        out["headshot"] = shown
        out["headshotBy"] = "National Governors Association"
    return out


def headshot(gov):
    """The NGA headshot the card shows, or ``""``: the file itself when it is
    within the caps every portrait is held to (``photos.too_heavy``), else
    the same file smaller (``executives.weigh_headshot``), else none - the
    NGA's run to 7.6 MB, for a circle of 40-72px (TECH-13). A headshot
    never weighed is not shown: unknown is not small."""
    from .photos import too_heavy

    if not gov.get("headshot"):
        return ""
    weight = gov.get("headshotWeight") or (
        {"bytes": gov["headshotBytes"]} if gov.get("headshotBytes") else None)
    if not weight:
        return ""
    if not too_heavy(weight):
        return gov["headshot"]
    small = gov.get("headshotSmallWeight")
    if gov.get("headshotSmall") and small and not too_heavy(small):
        return gov["headshotSmall"]
    return ""


def officer_photos(code, entry):
    """Apply ``overrides.OFFICER_PHOTOS`` to one state's offices, in place:
    a photograph for a holder whose roster has none - or whose office offers
    its own only above the caps, the lighter card going first - while the
    roster names
    the person the entry was checked for. Returns a problem for each entry
    that no longer fits - the office changed hands, or the roster now has a
    photograph of its own - so a stale one is never shown (rule 87)."""
    from .overrides import OFFICER_PHOTOS
    from .photos import refused

    problems = []
    for (state, office), photo in sorted(OFFICER_PHOTOS.items()):
        if state != code:
            continue
        if refused(photo["photo"]):
            # One test for every route (rule 38): a curated card a person
            # has since refused is not shown.
            problems.append(f"{code} {office}: {refused(photo['photo'])}; not shown")
            continue
        holder = entry.get(office)
        field, by_field, page_field = (("headshot", "headshotBy", "headshotPage")
                                       if office == "governor"
                                       else ("photo", "photoBy", "photoPage"))
        name = " ".join(str((holder or {}).get("name") or "").split())
        if (not isinstance(holder, dict) or holder.get("unconfirmed") or holder.get("disputed")
                or holder.get("notMember") or name != photo["name"]):
            problems.append(f"{code} {office}: overrides.OFFICER_PHOTOS is for {photo['name']}; "
                            f"the roster names {name or 'no confirmed holder'}, so no "
                            "photograph is shown")
            continue
        heavy = (holder.get("photoHeavy") or [{}])[0].get("kept")
        if holder.get(field) and not heavy:
            problems.append(f"{code} {office}: the roster now has a photograph of {name}; "
                            "overrides.OFFICER_PHOTOS may be unneeded")
            continue
        # Both are tied to the person (rule 87): where the office offers its
        # own only above the caps and nothing serves it smaller, the
        # association's lighter card goes first.
        holder[field] = photo["photo"]
        holder[by_field] = photo["by"]
        holder[page_field] = photo["page"]
    # Whether the office's file is heavy is the build's to say, not the
    # page's: stategov.js carries the photograph and whose it is.
    for holder in entry.values():
        if isinstance(holder, dict):
            holder.pop("photoHeavy", None)
    return problems


def court_photo_problems(court_cache):
    """The justices' photographs: a read or an evidenced override's record
    that lacks what ties it to the justice stops the build (rule 87: never
    dropped from the page without a word); one a person's list withholds,
    one whose justice the court no longer lists, and the count shown though
    offered only above the caps, are said."""
    from . import court_photos
    members = {code: read.get("members") or []
               for code, read in ((court_cache or {}).get("courts") or {}).items()}
    errors, warnings = court_photos.curated_problems(members)
    if errors:
        raise StateGovError("overrides.JUSTICE_PHOTOS: " + "; ".join(errors))
    errors, withheld = court_photos.read_problems(court_cache)
    if errors:
        raise StateGovError("courts.json photographs: " + "; ".join(errors))
    warnings.extend(withheld)
    seen = court_photos.counts(court_cache)
    if seen["smaller"] or seen["heavy"]:
        # Shown all the same (rule 87; the owner's decision of 2026-10-25):
        # smaller from the same file where a resizer serves it, else at
        # full size until rule 101's copies serve it lighter.
        warnings.append(f"{seen['smaller'] + seen['heavy']} justices' photographs are offered "
                        f"by their court only above the caps: {seen['smaller']} shown smaller "
                        f"from the same file, {seen['heavy']} at full size")
    return warnings


def unpictured(states):
    """One line per office naming the confirmed holders the card shows
    without a photograph (STATEGOV-13): a person's to look for one from
    their office or its association, never a search."""
    out = []
    for office, label in (("governor", "governors"), ("lt", "lieutenant governors"),
                          ("sos", "secretaries of state"), ("ag", "attorneys general")):
        codes = []
        for code, entry in sorted(states.items()):
            holder = entry.get(office) or {}
            if not holder.get("name") or any(holder.get(k) for k in (
                    "unconfirmed", "disputed", "unlisted", "vacant", "none", "notMember")):
                continue
            if not holder.get("headshot" if office == "governor" else "photo"):
                codes.append(code)
        if codes:
            out.append(f"{len(codes)} {label} have no photograph from their office or its "
                       f"association: {', '.join(codes)}")
    return out


def office_links(code, entry):
    """Apply ``overrides.OFFICE_LINKS`` to one state's offices, in place.
    Returns a problem for each entry whose roster no longer lists what it
    replaces: the roster changed, and the entry may now be unneeded."""
    from .overrides import OFFICE_LINKS

    problems = []
    for (state, office, field), (listed, shown, _evidence) in sorted(OFFICE_LINKS.items()):
        if state != code:
            continue
        holder = entry.get(office)
        if not isinstance(holder, dict) or holder.get("none") or not holder.get("name"):
            problems.append(f"{code} {office} {field}: overrides.OFFICE_LINKS names no holder here")
            continue
        if holder.get(field) != listed:
            problems.append(f"{code} {office} {field}: the roster now lists "
                            f"{holder.get(field) or 'nothing'}, not {listed or 'nothing'}; "
                            f"overrides.OFFICE_LINKS may be unneeded")
            continue
        if shown:
            holder[field] = shown
        else:
            holder.pop(field, None)
    return problems


def stale_name_forms(states):
    """An ``overrides.STATEWIDE_NAME_FORMS`` entry whose holder the rosters
    no longer name, or whose list no longer prints that name, settles
    nothing: reported, so it is removed rather than left to match someone
    else."""
    from .overrides import STATEWIDE_NAME_FORMS

    out = []
    for (code, key, name), (form, _evidence) in sorted(STATEWIDE_NAME_FORMS.items()):
        entry = states.get(code) or {}
        holder = (entry.get(key) or {}).get("name")
        item = ((entry.get("ballot2026") or {}).get("offices") or {}).get(key) or {}
        # The list's own form: the page shows "Joseph Lombardo", printed as
        # "Lombardo, Joseph".
        names = [p.get("printed") or p["name"]
                 for p in (item.get("candidates") or {}).get("candidates", ())]
        if holder != name or form not in names:
            out.append(f"{code} {key}: overrides.STATEWIDE_NAME_FORMS is for {name} as "
                       f"'{form}'; the rosters name {holder or 'nobody'} and the list "
                       f"{'prints' if form in names else 'does not print'} that name")
    return out


def holder_line(code, key, holder, terms, listed):
    """``(record, problem)``: what an office on the ballot says about its
    holder. The election office's list of candidates answers wherever it is
    in hand (``statewide.holder_status``); a term limit in
    ``ballot2026.OPEN_SEATS`` stays as the reason, the list beside it. The
    two must agree: a term-limited holder the list names, or a list entry
    that does not settle the holder, is reported and the line says it was
    not checked. With no list, OPEN_SEATS alone answers, as before."""
    from . import ballot2026, statewide

    seat, seat_problem = ballot2026.open_seat(code, key, holder, terms)
    if not listed or not holder:
        return seat, seat_problem
    status, problem = statewide.holder_status(code, key, listed, holder)
    if status is None:
        return ballot2026.unchecked(holder), problem
    if seat and seat["why"] == "term-limit":
        if status["why"] == "listed":
            return ballot2026.unchecked(holder), (
                f"{code} {key}: OPEN_SEATS says {holder} is term-limited; "
                f"{status['cite']} names them; neither is shown")
        return dict(seat, then={"text": "is not among the candidates for this office",
                                "source": status["source"], "cite": status["cite"]}), problem
    if seat and seat["why"] in ("not-listed", "listed") and seat["why"] != status["why"]:
        return ballot2026.unchecked(holder), (
            f"{code} {key}: OPEN_SEATS says {seat['why']}; the list of candidates says "
            f"{status['why']}; neither is shown")
    return status, problem or seat_problem


# -------------------------------------------------------------------- build

def build(root="."):
    """``(payload, problems)``: what ``data/stategov.js`` holds, and every
    disagreement between the sources."""
    from . import ballot2026, courts, executives, officers, statelegs, statewide
    exec_cache, leg_cache, ncsl, officer_cache = (
        executives.load_cache(root), statelegs.load_cache(root), load_ncsl(root),
        officers.load_cache(root))
    # The statewide candidates are a hand-edited cache: one that breaks its
    # rules stops the build, as a hand-read court roster does (rule 91).
    lists = statewide.load(root)
    if lists is None:
        raise StateGovError(f"no {statewide.CACHE_PATH}")
    unfit = statewide.problems(lists)
    if unfit:
        raise StateGovError(f"{statewide.CACHE_PATH}: " + "; ".join(unfit))
    # The candidates' photographs (kyc/statewide_photos.py): optional, but a
    # cached one without what ties it to the person stops the build (rule 87).
    from . import statewide_photos
    photo_cache = statewide_photos.load_cache(root) or {}
    unfit = statewide_photos.problems(photo_cache)
    if unfit:
        raise StateGovError(f"{statewide_photos.CACHE_PATH}: " + "; ".join(unfit))
    # And the election offices' own guides' photographs, hosted here
    # unmodified, for a candidate no other route pictures (kyc/guide_photos.py).
    from . import guide_photos, photocopies
    guide_cache = guide_photos.load_cache(root)
    copies_manifest = photocopies.load(root)
    candidates_heavy = 0
    for cache, path, command in ((exec_cache, executives.CACHE_PATH, "executives"),
                                 (leg_cache, statelegs.CACHE_PATH, "statelegs"),
                                 (ncsl, NCSL_CACHE, "executives"),
                                 (officer_cache, officers.CACHE_PATH, "officers")):
        if not cache:
            raise StateGovError(f"no {path}; run '{command}'")
    governors = exec_cache["governors"]
    legislators = leg_cache["states"]
    problems = []
    disputes = officers.overlaps(officer_cache["sos"], officer_cache["lt"])
    # The courts' cache is optional: a state whose court was never read
    # simply has no court block, rather than the build failing.
    court_cache = courts.load_cache(root)
    for code, office, theirs, ours in disputes:
        problems.append(f"{code}: NASS lists {theirs} as {office}, NLGA {ours}; neither is shown")
    problems.extend(officers.ag_problems(officer_cache.get("ag", {})))
    problems.extend(officers.bio_page_problems(officer_cache.get("ag", {})))
    # A photograph the office offers only above the caps is kept, heavy
    # (rule 87; the owner's decision of 2026-10-25): shown where nothing
    # lighter ties to the person, the association's card first where there
    # is one (officer_photos). The build says how many.
    heavy = sorted(c for c, row in officer_cache.get("ag", {}).items()
                   if (row.get("photoHeavy") or [{}])[0].get("kept"))
    if heavy:
        problems.append(f"{len(heavy)} attorneys general's own office photographs are offered "
                        f"only above the caps ({', '.join(heavy)}); the association's card "
                        "goes first where one is recorded, else the office's is shown heavy")
    # A roster typed in from a court's page is held to what a read one is
    # (courts.read_court refuses it): one that does not fit its court stops
    # the build. Age is a warning: a person must read the page again.
    unfit = courts.curated_errors()
    if unfit:
        raise StateGovError("overrides.COURT_ROSTERS: " + "; ".join(unfit))
    problems.extend(courts.curated_stale())
    problems.extend(courts.stale(court_cache))
    states = {}
    for code in sorted(governors):
        entry = {"governor": _governor(dict(governors[code], state=code), problems)}
        if code not in STATES:
            # A territory: the page calls it one, and says its legislature
            # and courts are not covered rather than leaving them out silently.
            entry["territory"] = True
        entry.update(officers.for_state(code, officer_cache, disputes))
        problems.extend(office_links(code, entry))
        problems.extend(officer_photos(code, entry))
        entry.update(courts.for_state(code, court_cache))
        # Its federal courts: the district courts in it and its court of
        # appeals (kyc/federal_courts.py), each linked to its own page.
        from .federal_courts import federal_for_state
        if federal_for_state(code):
            entry["federalCourts"] = federal_for_state(code)
        if code in ballot2026.STATES or code in ballot2026.TERRITORIES:
            # Which of these offices and seats are elected on November 3, and
            # for each office on it, who the election office lists as its
            # candidates and whether its holder is among them - or, said in
            # words, that nothing here checked.
            entry["ballot2026"] = ballot2026.for_state(code)
            for key, item in entry["ballot2026"]["offices"].items():
                if not item["up"]:
                    continue
                holder = entry["governor"] if key == "governor" else entry.get(key) or {}
                listed = statewide.office(lists, code, key)
                status, problem = holder_line(code, key, holder.get("name"), holder.get("terms"),
                                              listed)
                if problem:
                    problems.append(problem)
                if status:
                    item["holderStatus"] = status
                if listed:
                    item["candidates"] = statewide.for_page(
                        code, listed, status.get("name") if status and status["why"] == "listed"
                        else None)
                    candidates_heavy += statewide_photos.attach(
                        code, key, item["candidates"]["candidates"], listed, holder, status,
                        photo_cache, guide_cache, copies_manifest)
        if code in STATES:
            entry.update(_legislature(code, legislators.get(code, []), ncsl["states"].get(code),
                                      entry["governor"]["partyKey"], problems))
            theirs = (ncsl["states"].get(code) or {}).get("governor", "")
            if theirs and theirs != entry["governor"]["partyKey"]:
                problems.append(f"{code}: the NGA lists a {entry['governor']['party']} governor; "
                                f"NCSL's table ({ncsl['updated']}) says {theirs}")
        states[code] = entry
    missing = [c for c in STATES if c not in states]
    if missing:
        problems.append(f"no governor for {', '.join(missing)}")
    problems.extend(unpictured(states))
    if candidates_heavy:
        # Shown all the same (rule 87; the owner's decision of 2026-10-25).
        problems.append(f"{candidates_heavy} statewide candidates' photographs shown at full "
                        "size: their source offers them only above the caps")
    problems.extend(statewide_photos.withheld(photo_cache))
    problems.extend(court_photo_problems(court_cache))
    problems.extend(stale_name_forms(states))
    payload = {
        "states": states,
        "sources": {
            "nga": [executives.SOURCE, executives.ROSTER_URL, exec_cache.get("fetched", "")[:10]],
            "openstates": [statelegs.SOURCE, "https://openstates.org/",
                           leg_cache.get("fetched", "")[:10]],
            "ncsl": [NCSL_SOURCE, NCSL_URL, ncsl.get("updated", "")],
            "nass": ["National Association of Secretaries of State, membership roster",
                     officers.NASS_URL, officer_cache.get("fetched", "")[:10]],
            "nlga": ["National Lieutenant Governors Association, members", officers.NLGA_URL,
                     officer_cache.get("fetched", "")[:10]],
            "raga": ["Republican Attorneys General Association, members", officers.RAGA_URL,
                     officer_cache.get("fetched", "")[:10]],
            "daga": ["Democratic Attorneys General Association, members", officers.DAGA_URL,
                     officer_cache.get("fetched", "")[:10]],
            # Each state's own record, linked per office and chamber.
            "ballot2026": ["Each state's constitution, statutes and election office",
                           "", ballot2026.REVIEWED],
        },
    }
    # The headshots and officers' photographs, as the smaller copies this
    # site made of the heavy ones (rule 101).
    from . import photocopies
    photocopies.apply_stategov(payload, photocopies.load(root))
    return payload, problems


def filled_where_vacant(code, which, ours, theirs):
    """Open States names more members for a chamber than NCSL counts seated:
    someone listed may have left. Only *which party holds* the chamber is
    compared on the page; the seat counts are Open States', so this is
    reported for a person to check against the chamber's own roster - never
    changed on NCSL's word alone, since NCSL can lag a special election too.
    A seat Open States lists nobody for and NCSL fills is the opposite lag,
    and is already said on the page ("nobody listed")."""
    seated = theirs.get("D", 0) + theirs.get("R", 0) + theirs.get("other", 0)
    if ours["listed"] > seated and theirs.get("vacant"):
        return [f"{code} {which}: Open States lists {ours['listed']} members, NCSL {seated} with "
                f"{theirs['vacant']} vacant; check the chamber's own roster for a member who has left"]
    return []


def _legislature(code, records, theirs, governor_key, problems):
    upper_seats, lower_seats = SEATS[code]
    out = {"upper": dict(chamber(records, "upper", upper_seats),
                         title="Legislature" if code == "NE" else "Senate")}
    if lower_seats:
        out["lower"] = dict(chamber(records, "lower", lower_seats),
                            title=LOWER_CHAMBER.get(code, "House of Representatives"))
    if code == "NE":
        out["legislature"] = "nonpartisan"
        out["trifecta"] = "nonpartisan"
        return out
    disputed = False
    for which in ("upper", "lower"):
        if not theirs:
            continue
        problems.extend(filled_where_vacant(code, which, out[which], theirs[which]))
        ncsl = majority(theirs[which], theirs[which]["seats"] or out[which]["seats"])
        if ncsl != out[which]["majority"]:
            disputed = True
            out[which]["ncsl"] = ncsl or "none"
            problems.append(f"{code} {which}: Open States gives "
                            f"{out[which]['majority'] or 'no majority'}, NCSL "
                            f"{ncsl or 'no majority'}")
    upper, lower = out["upper"]["majority"], out["lower"]["majority"]
    holds, why = coalition_holds(code, records, out) if code in COALITIONS else (False, "")
    if why:
        problems.append(f"{code}: coalition note not shown: {why}")
    if disputed:
        out["legislature"] = out["trifecta"] = "disputed"
    elif holds:
        out["legislature"] = "coalition"
        out["trifecta"] = "divided"
        out["note"] = COALITIONS[code]["text"]
        out["noteSource"] = COALITIONS[code]["source"]
    elif upper and upper == lower:
        out["legislature"] = upper
        out["trifecta"] = upper if governor_key == upper else "divided"
    else:
        out["legislature"] = "split"
        out["trifecta"] = "divided"
    return out


def stats(payload):
    states = [s for c, s in payload["states"].items() if c in STATES]
    count = {}
    for s in states:
        count[s["trifecta"]] = count.get(s["trifecta"], 0) + 1
    return {"governors": len(payload["states"]), "trifectas": count}
