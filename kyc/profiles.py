"""Turn roster rows into the unified profile records the site renders.

All election derivation lives here. It used to run in the browser, duplicated
verbatim in both index.html and map.html, which meant the two pages could drift
apart and the same logic had to be maintained twice.
"""

import re
import unicodedata

from . import overrides
from .normalize import (
    GENERIC,
    NOT_DISCLOSED,
    OK,
    TERRITORIES,
    UNKNOWN,
    classify,
    clean_str,
    is_missing,
    looks_like_date,
    office_label,
    parse_age,
    parse_district,
    parse_state_abbrev,
)
from .photos import assign_credits, candidate_photos, member_photos

ELECTION_YEAR = 2026
NEXT_CONGRESS_START = "2027-01-03"


def age_as_of(snapshot=None):
    """The date ages are computed at: when the membership data was fetched.

    The CSVs' Age column is a number typed on the day the row was written,
    and 70 of them were already wrong when the site was built. Ages are
    computed from the birthdate instead - but not at the wall-clock moment of
    the build. ``verify`` asks whether the committed data matches its sources
    (rule 18); an age that ticked over at midnight would make it fail on
    every birthday, and CI's ``SOURCE_DATE_EPOCH`` build (2001) would make
    everyone 25 years younger. The snapshot's fetch date is part of the data,
    moves forward on every weekly refresh, and is reproducible. Without a
    snapshot the build timestamp is used, which honours SOURCE_DATE_EPOCH.
    """
    import datetime

    stamp = (snapshot or {}).get("fetched")
    if not stamp:
        from .emit import build_timestamp
        stamp = build_timestamp()
    return datetime.date.fromisoformat(str(stamp)[:10])


def _age(row, as_of):
    """Age from the birthdate at *as_of*; the CSV's Age only without a usable one."""
    from .legislators import age_on

    birthdate = clean_str(row.get("Birthdate"), "")
    if as_of is not None and looks_like_date(birthdate):
        years = age_on(birthdate[:10], as_of)
        if years:
            return int(years)
    return parse_age(row.get("Age"))


def _fold(text):
    """Strip accents so surname matching works on "Lujan" vs "Lujan"."""
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _chamber_kind(chamber):
    """Reduce a chamber string to ``"Senate"``, ``"House"`` or ``""``."""
    if "Senate" in chamber:
        return "Senate"
    if "House" in chamber:
        return "House"
    return ""


def _is_candidate(chamber, status):
    return "Candidate" in chamber or "candidate" in str(status).lower()


def _term_string(start, end_year):
    """Render a term as ``"<start> - <end>"``, tolerating a missing start."""
    start = clean_str(start, "N/A")
    base = start.split(" - ")[0].strip()
    if base in ("", "N/A"):
        return "N/A"
    return f"{base} - {end_year}-01-03" if end_year else base


def _senate_term_end(term_start):
    """Next odd-numbered year in which this Senate term expires.

    Senate terms run six years and end in January of an odd year, so we step
    forward from the start year in six-year hops until we pass the current
    Congress.
    """
    match = re.match(r"\s*(\d{4})", str(term_start or ""))
    if not match:
        return None
    end = int(match.group(1)) + 6
    while end < ELECTION_YEAR + 1:
        end += 6
    if end % 2 == 0:
        end += 1
    return end


# Fields whose provenance the page surfaces. Finance absences are "we have no
# filing on hand" rather than "they disclosed nothing", so they map to UNKNOWN.
_QUALITY_FIELDS = (
    "funding_sources", "platforms", "committees",
    "education", "previous_professions", "voting_alignment",
    "receipts", "disbursements", "birthdate",
)
_FINANCE_FIELDS = {"receipts", "disbursements"}


def apply_quality(profile):
    """Classify each surfaced field and record anything that is not real data.

    Rewrites long placeholder sentences down to a short label and stores the
    non-OK statuses in ``profile["quality"]`` so the page can render them as
    an explicit absence instead of as a finding.
    """
    quality = {}
    for field in _QUALITY_FIELDS:
        value, status = classify(profile.get(field))

        if field in _FINANCE_FIELDS and status == NOT_DISCLOSED:
            # Before the FEC lookup existed, an absent finance figure only
            # ever meant "we have no filing on hand", never "they disclosed
            # nothing" - so it was demoted to UNKNOWN. fec.apply_cache
            # promotes it again to NO_FILING for anyone the FEC was actually
            # queried about.
            value, status = "No data", UNKNOWN
        elif field == "birthdate" and status == OK and not looks_like_date(value):
            # "2026 Primary" is a race marker parked in a date column.
            value, status = "No data", UNKNOWN

        profile[field] = value
        if status != OK:
            quality[field] = status

    profile["quality"] = quality
    profile["hasRealFinance"] = "receipts" not in quality
    return profile


def _dedup_members(rows):
    """One record per person: their bioguide id, or for a row without one
    (a "Vacant" placeholder) its seat. Later rows win.

    Keyed on the seat alone, a member whose row still carried an old
    district number and a newcomer seated at that number would have shared a
    key, and one of them would have vanished with nothing said. Two people in
    one seat is a ``duplicate-district`` error; one person on two rows is a
    ``member-twice`` error."""
    seats = {}
    for row in rows:
        chamber = clean_str(row.get("Chamber"), "")
        state = clean_str(row.get("State"), "")
        name = clean_str(row.get("Name"), "")
        district_raw = clean_str(row.get("District"), "")
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()

        if bioguide and bioguide != "N/A":
            key = ("Member", bioguide)
        elif "House" in chamber:
            num, _ = parse_district(district_raw, state)
            key = ("House", state, num if num is not None else district_raw.lower())
        elif "Vacant" in name:
            key = ("Vacant", state, district_raw)
        else:
            key = ("Senate", state, name)
        seats[key] = row
    return list(seats.values())


def _dedup_candidates(rows):
    """One record per (person, state, chamber).

    Keying on the bare name alone would merge two different people who happen
    to share a name and are running in different states.
    """
    people = {}
    for row in rows:
        name = clean_str(row.get("Name"), "")
        if not name or name == "N/A":
            continue
        office = clean_str(row.get("Office / District"), "")
        state = parse_state_abbrev(office)
        kind = _chamber_kind(clean_str(row.get("Chamber"), ""))
        people[(name.lower(), state, kind)] = row
    return list(people.values())


def _contact(person):
    """Contact details and reference ids from the member's own term record.

    Only fields the dataset holds are written (rule 28): an absent Twitter
    handle is an absence, never an empty string the page has to guess at.
    """
    out = {}
    for src, dst in (("url", "website"), ("phone", "phone"), ("office", "office"),
                     ("contactForm", "contactForm"), ("wikipedia", "wikipedia")):
        if person.get(src):
            out[dst] = person[src]
    fixed = overrides.MEMBER_CONTACT_FORMS.get(person.get("bioguide"))
    if fixed and person.get("contactForm") == fixed[0]:
        # Only while the source still holds the value the entry corrects.
        out["contactForm"] = fixed[1]
    refs = {k: person[k] for k in ("govtrack", "opensecrets", "votesmart", "ballotpedia")
            if person.get(k)}
    if refs:
        out["refs"] = refs
    social = social_handles(person.get("social"), person.get("bioguide"))
    if social:
        out["social"] = social
    return out


_CHANNEL_ID = re.compile(r"^UC[\w-]{22}$")


def social_handles(social, bioguide=None):
    """The member's accounts, each in the shape the page links it by.

    congress-legislators' ``youtube`` holds three kinds of value, and the
    page built one URL for all of them, youtube.com/user/<value>, which
    answered 404 for 88 of 90 members whose record has no channel id
    (2026-10-17). A channel id (UC + 22 characters) is a ``youtube_id``,
    linked as /channel/<id>; an @handle stays one, linked as /@handle; a
    legacy username is linked as the dated check in
    ``overrides.YOUTUBE_LEGACY_NAMES`` found it, or as /user/ until one is
    made (validate's ``youtube-unchecked`` lists it). ``twitter_id`` is kept:
    the page links the account by it, which follows a renamed handle.
    """
    out = dict(social or {})
    value = out.get("youtube")
    if value and _CHANNEL_ID.match(value):
        out.setdefault("youtube_id", value)
        out.pop("youtube")
    elif value and value.startswith("@"):
        # A handle YouTube answers 404 for, as the member's office links it
        # instead (or dropped), while the source still holds exactly it.
        fixed = overrides.YOUTUBE_HANDLE_CORRECTIONS.get(bioguide)
        if fixed and fixed[0] == value:
            if fixed[1]:
                out["youtube"] = fixed[1]
            else:
                out.pop("youtube")
    elif value:
        checked = overrides.YOUTUBE_LEGACY_NAMES.get(bioguide)
        if checked and checked[0] == value:
            if checked[1] == "handle":
                out["youtube"] = "@" + value
            elif checked[1] is None:
                out.pop("youtube")
    # A handle X answers "not found" for, with no id to follow a rename by:
    # dropped, because an abandoned handle can be registered by anyone.
    dead = overrides.DEAD_X_HANDLES.get(bioguide)
    if dead and out.get("twitter") == dead[0] and not out.get("twitter_id"):
        out.pop("twitter")
    return out


def _committee_text(assignments):
    """``"House Committee on Agriculture (Chair); ..."`` - the roster column's
    shape, from the authoritative rosters, so every reader of the field keeps
    working. Full committees only; subcommittees travel in ``committeeList``."""
    parts = []
    for seat in assignments:
        if seat["sub"]:
            continue
        parts.append(f"{seat['name']} ({seat['title']})" if seat.get("title") else seat["name"])
    return "; ".join(parts)


def _build_member(row, index, seats_up=None, term_ends=None, person=None, assignments=None,
                  as_of=None):
    from . import legislators

    name = clean_str(row.get("Name"), "")
    bioguide = row.get("Bioguide ID")
    profile_id = clean_str(bioguide, "") or f"CURR_{index}"

    # The roster holds legal names: "John Reed" is Jack Reed, "Garland Barr"
    # Andy Barr, and five open with a bare initial ("C. Franklin" is Scott
    # Franklin). Each is shown by the name the member's own
    # congress-legislators record - matched on bioguide id, never on a name
    # (rules 3, 17) - says they go by (legislators.display_name). The roster
    # spelling stays searchable and keeps keying the name-keyed caches
    # (``rosterName``). The same person's curated Senate-run row already
    # read "Andy Barr" beside "Garland Barr".
    display = legislators.display_name(name, person) or name

    chamber = clean_str(row.get("Chamber"), "")
    kind = _chamber_kind(chamber)
    state = clean_str(row.get("State"), "N/A")

    district_num, district_label = (None, None)
    if kind == "House":
        district_num, district_label = parse_district(row.get("District"), state)

    # A curated status note is about the 2026 race; a member serving a term
    # that began since Election Day has moved past it (a re-elected member,
    # a winner), and their roster row says "Active Member".
    status = clean_str(row.get("Status"), "Active Member")
    from .cycle import CYCLE, general_election_day

    new_term = bool(person) and (person.get("termStart") or "") >= \
        general_election_day(CYCLE).isoformat()
    other_office = None
    if not new_term:
        status = overrides.status_override(profile_id, status)
        other_office = overrides.OTHER_OFFICE_NOMINEES.get(profile_id)
    not_seeking = overrides.is_not_seeking(status)

    # --- 2026 election derivation -------------------------------------
    from .races import FOUR_YEAR_HOUSE_SEATS

    seat_up = False
    end_year = None
    statutory = kind == "House" and state in FOUR_YEAR_HOUSE_SEATS
    if kind == "House":
        # Every House seat is a two-year term, so all of them are on the
        # 2026 ballot regardless of whether the incumbent is running - except
        # Puerto Rico's Resident Commissioner, who serves four (48 U.S.C. 891).
        from .races import house_seat_up, house_term_end_year

        seat_up = house_seat_up(state, ELECTION_YEAR)
        # The term the member is serving, as the snapshot states it: a
        # representative re-elected in 2026 serves to 2029 from January 3.
        # Except a four-year seat, which congress-legislators records one
        # Congress at a time (Puerto Rico's 2025-2029 term is listed as
        # 2025-2027), so there the statute decides.
        end_year = house_term_end_year(state, ELECTION_YEAR)
        if not statutory:
            end_year = (term_ends or {}).get(profile_id) or end_year
    elif kind == "Senate":
        # Prefer the authoritative snapshot, keyed on bioguide id. The
        # fallback matches a hand-typed surname against the member's name,
        # which is only ever approximately right: the table said "Graham" for
        # South Carolina meaning Lindsey Graham, and kept matching after the
        # seat changed hands purely because the new senator shares the name.
        # With neither a record nor a snapshot, no seat is called up: the
        # surname table this used to fall back on matched Darline Graham to
        # Lindsey Graham's seat (rule 17).
        seat_up = seats_up is not None and profile_id in seats_up

        snapshot_end = (term_ends or {}).get(profile_id)
        if seat_up and snapshot_end and snapshot_end > ELECTION_YEAR + 1:
            # A record incumbent re-seated for a new term - Ohio's special
            # election's winner in December, every re-elected senator on
            # January 3 - serves to the term the snapshot states.
            end_year = snapshot_end
        elif seat_up:
            end_year = ELECTION_YEAR + 1
        else:
            # The snapshot knows when the term actually ends. The fallback
            # steps forward from Term Start in six-year hops, which is wrong
            # for anyone appointed mid-term.
            end_year = (term_ends or {}).get(profile_id) or _senate_term_end(
                row.get("Term Start")
            )

    # The dates of the term being served come from the snapshot, which is
    # read from Congress's own record: the roster's Term Start is the day a
    # row was written, and on January 3 it still says 2025 for everyone
    # re-elected. A House member would have read "2025-01-03 - 2029-01-03",
    # a four-year House term. The roster's date is for a build without one.
    term = _term_string(row.get("Term Start"), end_year)
    if person and person.get("termStart") and person.get("termEnd") and not statutory:
        term = f"{person['termStart']} - {person['termEnd']}"
        if person.get("endType") == "special-election":
            # An appointee serves until the special election's winner is
            # sworn in - in December, not on Election Day. "2025-01-21 -
            # 2026-11-03 (special election)" read as a term that ends with
            # the vote (rule 65: the winners are seated in December).
            term = (f"{person['termStart']} - until the winner of the "
                    f"{person['termEnd']} special election is sworn in")

    profile = {
        "id": profile_id,
        "name": display,
        "chamber": chamber,
        "party": clean_str(row.get("Party"), "Independent"),
        "state": state,
        "district": district_label or "N/A",
        "districtNum": district_num,
        "officeLabel": office_label(chamber, state, district_label),
        "status": status,
        "term_start": term,
        "termEndYear": end_year,
        "electionYear": (end_year - 1) if end_year else None,
        "isCandidate": False,
        "seatUp2026": seat_up,
        # Retained under the original name for the page's existing filters.
        "isUpIn2026": seat_up,
        "seekingReelection2026": seat_up and not not_seeking,
        "age": _age(row, as_of),
        "birthdate": clean_str(row.get("Birthdate"), "Unknown"),
        "education": clean_str(row.get("Education"), "N/A"),
        "previous_professions": clean_str(row.get("Previous Professions"), "N/A"),
        # Money comes from the FEC alone (fec.apply_cache; validate's
        # finance-not-fec). The roster's totals and its "Individual/PAC
        # contributions" line are never read: a member the FEC lookup missed
        # reads "No data", not a figure nobody can trace.
        "receipts": "",
        "disbursements": "",
        "funding_sources": "",
        "platforms": clean_str(row.get("Policy Focus & Platforms"), "N/A"),
        "voting_alignment": clean_str(row.get("Projected/Historical Voting Alignment"), "N/A"),
        "committees": clean_str(row.get("Committee Assignments"), "None"),
        "photos": member_photos(name, bioguide),
    }
    if display != name:
        profile["rosterName"] = name
    if other_office:
        # On another office's November ballot, as the results page marks its
        # winner (overrides.OTHER_OFFICE_NOMINEES): the page says where a
        # member who is leaving the seat is going, with its source.
        profile["otherOffice"] = {"text": other_office[0], "source": other_office[1],
                                  "checked": other_office[2]}
    if person:
        profile.update(_contact(person))
        # Names a voter may type instead: "Jim Clyburn" for James Clyburn.
        # Taken from the record matched on bioguide id, never from a name.
        extra = ((name,) if display != name else ()) + tuple(
            alias for alias, _evidence in overrides.SEARCH_ALIASES.get(bioguide, ()))
        found = legislators.aliases(person, display, extra=extra)
        if found:
            profile["aliases"] = found
    if kind == "Senate":
        profile.update(_senate_cycle(person, profile))
    if assignments:
        # The roster column was typed by hand and is what "No data" would
        # replace; the committee rosters are maintained with each Congress
        # and carry rank and title, so they win when present.
        profile["committees"] = _committee_text(assignments) or profile["committees"]
        # Codes and titles only; the names, URLs and parents travel once in
        # the build metadata rather than 539 times in the profiles.
        # A titled seat also says which side holds it, so the guide's
        # Congress page can tell a committee's chair from its minority lead.
        profile["committeeList"] = [
            dict({"code": seat["code"]},
                 **({"title": seat["title"]} if seat.get("title") else {}),
                 **({"side": seat["side"]} if seat.get("title") and seat.get("side") else {}))
            for seat in assignments
        ]
        profile["committeesSource"] = "congress-legislators"
    return profile


def _former_members(rows, record, profiles, seats_up, as_of=None):
    """A profile for each record incumbent who has left Congress, and each
    2026 winner who has, from the row ``congress --apply`` archived for them
    (``Former_Members.csv``). A winner's row names the race and role
    (``Race Role``, ``Race ID``) and their FEC ids (``fecIds``), so the race
    keeps its winner and their filing stays theirs.

    The member shape and the bioguide id are kept, so their race, money,
    portrait, disclosures and every link already shared still find them;
    ``formerMember`` says they no longer sit, and every "who represents me"
    view counts with ``record.seated`` (rule 27). Nothing is said that the
    archive does not know: the term ends on the day they left, the roster's
    status line and committee seats - about the term that ended - are not
    shown, and no office or phone is attached.

    A record incumbent still on the roster is built from the roster (an
    interrupted archive leaves a row in both files). One with no archived
    row has no profile; the race still names them (``race.incumbent``).
    """
    from .record import held_races

    on_roster = {p["id"] for p in profiles}
    archived = {}
    for row in rows:
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        if bioguide and clean_str(row.get("Left Office"), ""):
            archived.setdefault(bioguide, []).append(row)
    races = record.get("races") or {}
    incumbents = record.get("incumbents") or {}
    held_by = held_races(record)
    won = {}
    for bioguide, rows_of in archived.items():
        for row in rows_of:
            rid = clean_str(row.get("Race ID"), "")
            if (clean_str(row.get("Race Role"), "") == "winner" and rid in races
                    and bioguide not in held_by):
                won[bioguide] = (rid, row)
    out = []
    for bioguide, (rid, row) in sorted(won.items()):
        if bioguide in on_roster:
            continue
        race = races[rid]
        district = race.get("district")
        seat = {"Chamber": race.get("chamber"), "State": race.get("state"),
                "District": "" if race.get("chamber") == "Senate" else (
                    "At-Large" if district == 0 else f"District {district}")}
        row = dict(row, **seat)
        left = clean_str(row.get("Left Office"), "")
        profile = _build_member(row, 0, seats_up, None, person=None, as_of=as_of)
        profile.update(
            formerMember={"left": left, "via": clean_str(row.get("Left Via"), ""),
                          "congress": int(clean_str(row.get("Last Congress"), "0") or 0) or None},
            status=f"Former member: left office {left}",
            term_start=f"{clean_str(row.get('Term Start'), 'N/A')[:10]} - {left}",
            termEndYear=int(left[:4]), committees="",
            raceRole="winner", raceId=rid,
            fecIds=[i for i in clean_str(row.get("FEC IDs"), "").split(";") if i],
            seatUp2026=False, isUpIn2026=False, seekingReelection2026=False)
        if "Senate" in profile["chamber"]:
            profile.update(senateClass=race.get("senateClass"), nextElection=None,
                           senateSpecial=bool(race.get("special")))
        out.append(profile)
    for bioguide, rid in sorted(held_by.items()):
        if bioguide in on_roster or bioguide not in archived:
            continue
        # The seat they held on the ballot, whatever they sat in last: a
        # member who won another seat and later left is archived from it.
        race = races.get(rid) or {}
        district = race.get("district")
        seat = {"Chamber": race.get("chamber"), "State": race.get("state"),
                "District": "" if race.get("chamber") == "Senate" else (
                    "At-Large" if district == 0 else f"District {district}")}
        rows_of = sorted(archived[bioguide], key=lambda r: clean_str(r.get("Left Office"), ""))
        same = [r for r in rows_of if clean_str(r.get("Chamber"), "") == seat["Chamber"]
                and clean_str(r.get("State"), "") == seat["State"]]
        row = dict(same[-1] if same else rows_of[-1], **seat)
        held = incumbents[rid]
        left = clean_str(row.get("Left Office"), "")
        profile = _build_member(row, 0, seats_up, None, person=None, as_of=as_of)
        profile["formerMember"] = {
            "left": left,
            "via": clean_str(row.get("Left Via"), ""),
            "congress": int(clean_str(row.get("Last Congress"), "0") or 0) or None,
        }
        profile["status"] = f"Former member: left office {left}"
        profile["term_start"] = f"{held.get('termStart') or 'N/A'} - {left}"
        profile["termEndYear"] = int(left[:4])
        # The committee seats were the term's that ended.
        profile["committees"] = ""
        if "Senate" in profile["chamber"]:
            race = races.get(rid) or {}
            profile.update(senateClass=race.get("senateClass"), nextElection=None,
                           senateSpecial=bool(race.get("special")))
        # A record incumbent who won another record seat and then left: still
        # this race's incumbent (heldRaceId), and that race's winner.
        elsewhere = next((r for r in rows_of if clean_str(r.get("Race Role"), "") == "winner"
                          and clean_str(r.get("Race ID"), "") in races
                          and clean_str(r.get("Race ID"), "") != rid), None)
        if elsewhere is not None:
            profile.update(raceRole="winner", raceId=clean_str(elsewhere.get("Race ID"), ""),
                           fecIds=[i for i in clean_str(elsewhere.get("FEC IDs"), "").split(";")
                                   if i],
                           seekingReelection2026=False)
        out.append(profile)
    return out


def _mark_record_roles(profiles, record, snapshot, field):
    """What the record says about each member: an appointee who held a seat
    on the ballot (``appointed``, never "re-elected"); a member seated since
    Election Day for the term a race decided, in a seat they did not hold
    (``raceRole`` "winner": that race's, never its incumbent); and anyone
    else seated in such a seat since then (``raceRole`` "successor": in the
    race only if they ran in it). Neither is "up" for the seat they now sit
    in, and neither is ever called re-elected (``record.seat_changes``).

    A winner who held another record seat - Andy Barr, KY-6 to the Senate;
    Greg Casar, TX-35 to TX-37 - is still that race's incumbent
    (``heldRaceId``), and sits in the seat they won: never "running for"
    it."""
    from . import candidates as field_mod
    from .record import held_races, seat_changes

    incumbents = record.get("incumbents") or {}
    appointed = {inc["bioguide"] for inc in incumbents.values() if inc and inc.get("appointed")}
    changes = seat_changes(record, snapshot) if snapshot else {"winners": {}, "successors": {}}
    held = held_races(record)
    people = {p["bioguide"]: p for p in (snapshot or {}).get("legislators", [])}
    filed = {}
    for row in (field or {}).get("candidates", []):
        filed.setdefault(field_mod.race_id(row), set()).add(row.get("candidate_id"))
    for profile in profiles:
        if profile.get("isCandidate"):
            continue
        if profile["id"] in appointed:
            profile["appointed"] = True
        if profile["id"] in held:
            # The seat they held on the ballot, whatever they sit in now:
            # what counts them among a chamber's seats up (rule 1).
            profile["heldRaceId"] = held[profile["id"]]
        if profile.get("formerMember") and profile.get("raceRole") == "winner":
            # A winner who has left: their race and role are their archived
            # row's, and their filing is found by the ids it kept.
            mine = [i for i in profile.get("fecIds") or []
                    if i in filed.get(profile["raceId"], ())]
            if mine and not profile.get("fecCandidateId"):
                profile["fecCandidateId"] = mine[0]
            continue
        role, rid = "winner", changes["winners"].get(profile["id"])
        if not rid:
            role, rid = "successor", changes["successors"].get(profile["id"])
        if not rid:
            continue
        # Their filing for that race, by the id Congress's record lists for
        # them: how their result reaches this profile.
        mine = [i for i in (people.get(profile["id"]) or {}).get("fec") or []
                if i in filed.get(rid, ())]
        if mine and not profile.get("fecCandidateId"):
            profile["fecCandidateId"] = mine[0]
        profile["raceRole"] = role
        mine_held = held.get(profile["id"])
        if role == "successor" and not mine:
            # Seated after the election for another term, and never ran in
            # it: not part of the 2026 race at all.
            profile["raceId"] = None
        else:
            profile["raceId"] = rid
        if mine_held and mine_held != rid:
            profile["seekingReelection2026"] = False
            profile["seatUp2026"] = profile["isUpIn2026"] = True
        elif not mine_held:
            profile.update(seatUp2026=False, isUpIn2026=False, seekingReelection2026=False)


def _seated_in_race(candidate, profiles):
    """The member seated since Election Day in the race a curated row is for
    (``raceRole``), when their first and last names are exactly the row's."""
    from .candidates import _fold
    from .races import race_id
    from .record import seated

    rid = race_id(candidate["chamber"], candidate["state"], candidate.get("districtNum"))
    words = _fold(candidate["name"]).split()
    if len(words) < 2:
        return None
    for profile in profiles:
        if not (seated(profile) and profile.get("raceRole") and profile.get("raceId") == rid):
            continue
        mine = _fold(profile["name"]).split()
        if len(mine) >= 2 and (mine[0], mine[-1]) == (words[0], words[-1]):
            return profile
    return None


def _claimed_ids(profiles, people, record):
    """FEC ids that already belong to a member profile, by Congress's own
    record: a seated member's ids for the chamber they sit in (the snapshot's
    ``fec``), and a former member's for the chamber of the seat they held."""
    from .record import held_races, seated

    held = held_races(record)
    incumbents = (record or {}).get("incumbents") or {}
    out = set()
    for profile in profiles:
        if profile.get("isCandidate"):
            continue
        if seated(profile):
            out |= set((people.get(profile["id"]) or {}).get("fec") or [])
            continue
        if profile.get("raceRole") == "winner" and profile.get("fecIds"):
            # A 2026 winner who has left: the ids their archived row kept,
            # for the chamber of the seat they won.
            out |= {i for i in profile["fecIds"] if i[:1] == profile["raceId"][:1]}
        if profile["id"] in held:
            rid = held[profile["id"]]
            out |= {i for i in (incumbents[rid] or {}).get("fec") or [] if i[:1] == rid[:1]}
    return out


def _senate_cycle(person, profile):
    """A sitting senator's class and next election, keyed on bioguide id
    through the snapshot (rule 17).

    Without a snapshot there is no class to report - the roster does not
    carry one, and guessing it from a term-start date is the six-year-hop
    heuristic that is wrong for every appointee - so ``senateClass`` stays
    ``None`` and validation says so; ``nextElection`` falls back to the
    election year the profile already derived.
    """
    from . import legislators

    if not person:
        return {"senateClass": None, "nextElection": profile.get("electionYear"),
                "senateSpecial": False}
    return legislators.senate_cycle(person)


def _build_candidate(row, index, as_of=None):
    """A curated candidate: who they are and which seat, keyed on two ids.

    ``ID`` is the profile id, written into the row so that removing a row
    never renumbers the people after it - odds.json and the enrichment cache
    hold these ids, and a positional ``CAND_<n>`` once meant deleting three
    rows would have moved everyone below them onto someone else's markets.
    ``FEC Candidate ID`` is the person's own filing (rule 17).

    Money, biography, platform, committees and voting alignment are not
    read from the row. The roster carried a $22,000,000 total for a governor who never ran,
    "Projected ~96% Republican" for people with no voting record, and
    birthdates that disagreed with the person's own article in 17 of 20
    checked. The FEC supplies the money (fec.apply_cache) and the article the
    election page links supplies the biography (enrich.apply_cache, rule 38);
    what neither knows is "No data", which is true.
    """
    name = clean_str(row.get("Name"), "")
    chamber_raw = clean_str(row.get("Chamber"), "Senate (Candidate)")
    kind = _chamber_kind(chamber_raw)
    office = clean_str(row.get("Office / District"), "")
    state = parse_state_abbrev(office)

    district_num, district_label = (None, None)
    if kind == "House":
        district_num, district_label = parse_district(office, state)

    # The chamber is a chamber: the roster typed "House (Primary Winner)" on
    # eight rows, a status that read as part of the office beside everyone
    # else's "House (Candidate)" and outlived the results (PROFILES-26).
    chamber = f"{kind} (Candidate)" if kind else chamber_raw

    profile = {
        # No positional fallback: CAND_3 was Andy Beshear's, and a new row
        # numbered by position could take it. A row without an ID has none,
        # and validate fails it.
        "id": clean_str(row.get("ID"), ""),
        "name": name,
        "chamber": chamber,
        "party": clean_str(row.get("Party"), "Independent"),
        "state": state,
        "district": district_label or "N/A",
        "districtNum": district_num,
        "officeLabel": office_label(chamber, state, district_label),
        "status": clean_str(row.get("Status"), "Candidate"),
        # One wording for every challenger's term, the FEC field's included.
        "term_start": clean_str(row.get("Projected Start"), "Jan. 3, 2027 (if elected)")
        .replace("(If elected)", "(if elected)"),
        "termEndYear": None,
        "electionYear": ELECTION_YEAR,
        "isCandidate": True,
        "seatUp2026": True,
        "isUpIn2026": False,
        "seekingReelection2026": False,
        "age": "Unknown",
        "birthdate": "",
        "education": "",
        "previous_professions": "",
        "receipts": "",
        "disbursements": "",
        "funding_sources": "",
        # The curator's platform and committee summaries went too: unsourced
        # paraphrase that also blocked the campaign's own issue headings
        # (enrich fills only an empty field, rule 38).
        "platforms": "",
        "voting_alignment": "",
        "committees": "",
        "photos": candidate_photos(name, state),
    }
    fec_id = clean_str(row.get("FEC Candidate ID"), "").upper()
    if fec_id:
        profile["fecCandidateId"] = fec_id
        profile["rosterFecId"] = fec_id
    return profile


def _link_key(profile, name=None):
    """First and last name, folded, plus the state.

    Middle names and suffixes are dropped: the FEC files Buddy Carter's
    Senate run as "Earl Leroy Carter" and the roster seats him as "Earl
    Carter", and they are one person. Two different people sharing a first
    and last name, a state and a cycle - but not a chamber - is the risk
    accepted here, and ``validate`` reports any member linked to a candidate
    of another party so it would be seen.
    """
    from .results import _tokens

    words = _tokens(name or profile["name"])
    if len(words) < 2:
        return None
    return (words[0], words[-1], profile["state"])


def _link_keys(profile):
    """The candidate's own key, and the key of the name its filing's
    evidenced entry in ``overrides.RESULT_NAMES`` gives. The FEC files Raja
    Krishnamoorthi's Senate run as "KRISHNAMOORTHI, S", so his member card
    never pointed at it; the entry is keyed on the filing's id and evidenced
    by his own committee (RAJA FOR ILLINOIS), not a guess (rule 17)."""
    from .overrides import RESULT_NAMES

    keys = [_link_key(profile)]
    entry = RESULT_NAMES.get(profile.get("fecCandidateId") or "")
    if entry:
        keys.append(_link_key(profile, entry[0]))
    return [k for k in keys if k]


def _cross_link(profiles, people=None):
    """Link a sitting member to their own 2026 candidacy for another seat.

    First by id: a filing whose candidate id Congress's record (*people*,
    the snapshot by bioguide) lists for a sitting member is theirs. Then
    matched on name *and* state, so Rep. Mike Rogers (AL) is never linked to
    Senate candidate Mike Rogers (MI). A member with a candidacy elsewhere is
    not seeking re-election to the seat they hold - no state lets a person
    run for two federal offices at once - so the seat is open. Seven House
    members running for the Senate read as "seeking re-election" before this
    was derived.
    """
    from . import races
    from .record import seated

    members = {}
    by_fec = {}
    for profile in profiles:
        if not profile["isCandidate"]:
            # The name shown and the roster's legal one: the FEC files a
            # member's other run under either ("Earl Leroy Carter").
            for name in (profile["name"], profile.get("rosterName")):
                key = _link_key(profile, name) if name else None
                if key:
                    members.setdefault(key, profile)
            # Every FEC id Congress's own record lists for a sitting member,
            # either chamber (rule 17): Andy Barr's Kentucky Senate filing
            # (S6KY00286) never met his member card, which the roster names
            # "Garland Barr", so the Republican nominee read only "Not
            # running for this seat".
            if seated(profile):
                for fec_id in (people or {}).get(profile["id"], {}).get("fecAll") or []:
                    by_fec[fec_id] = profile

    links = 0
    for profile in profiles:
        if not profile["isCandidate"]:
            continue
        ids = [profile.get("fecCandidateId")] + list(profile.get("otherFecIds") or [])
        held = next((by_fec[i] for i in ids if i in by_fec), None)
        if held is None:
            held = next((members[k] for k in _link_keys(profile) if k in members), None)
        if held is None or held["chamber"] == profile["chamber"]:
            continue
        contest = races.race_id(profile["chamber"], profile["state"], profile.get("districtNum"))
        if contest == races.race_id(held["chamber"], held["state"], held.get("districtNum")):
            # A filing for the seat they sit in - a winner seated since -
            # is not a run for another one.
            continue
        profile["incumbentId"] = held["id"]
        profile["incumbentSeat"] = held["officeLabel"]
        held["alsoRunningId"] = profile["id"]
        held["alsoRunningSeat"] = profile["officeLabel"]
        held["contestRaceId"] = contest
        held["contestLabel"] = profile["officeLabel"]
        if held.get("seatUp2026"):
            held["seekingReelection2026"] = False
        links += 1
    return links


def _apply_filings(profiles, field, finance):
    """Take the seat each person is contesting from their FEC filing.

    The roster seats a member at the district they hold and a curated
    challenger at the district the editor typed. The 2025 redistricting in
    Texas, Florida, California and Utah moved thirteen sitting members into
    new district numbers, and Colin Allred's roster row still said TX-32
    after his filing moved to TX-33. The filing is what a person has sworn
    they are running for, so it wins: a member gets ``contestRaceId`` (and
    stops "seeking re-election" to a seat they are not contesting), a roster
    challenger is re-seated, and ``validate`` reports both.

    Returns ``(moved, reseated)`` - lists of ``(name, from, to)``.
    """
    from . import fec as fec_mod, races
    from .candidates import district_number, race_id

    rows = {r["candidate_id"]: r for r in (field or {}).get("candidates", [])}
    moved, reseated = [], []
    for profile in profiles:
        if not profile.get("fecCandidateId"):
            record = (finance or {}).get(fec_mod.profile_key(profile)) or {}
            if record.get("candidate_id"):
                profile["fecCandidateId"] = record["candidate_id"]
        row = rows.get(profile.get("fecCandidateId"))
        if not row:
            continue
        contest = race_id(row)
        if not contest:
            continue
        seat = races.race_id(profile["chamber"], profile["state"], profile.get("districtNum"))
        if contest == seat:
            continue
        if profile["isCandidate"]:
            before = profile["officeLabel"]
            district = district_number(row)
            profile["state"] = row["state"]
            profile["districtNum"] = district
            profile["district"] = (
                "N/A" if district is None else "AL" if district == 0 else str(district)
            )
            profile["officeLabel"] = races.seat_label(contest)
            profile["rosterSeat"] = before
            reseated.append((profile["name"], before, profile["officeLabel"]))
        else:
            profile["contestRaceId"] = contest
            profile["contestLabel"] = races.seat_label(contest)
            if profile.get("seatUp2026"):
                profile["seekingReelection2026"] = False
            moved.append((profile["name"], profile["officeLabel"], profile["contestLabel"]))
    return moved, reseated


def screen_field(field, profiles, record=None):
    """The FEC field without stale registrations or filings for absent races.

    The races are the frozen *record*'s when there is one (kyc/record.py);
    otherwise only the sitting members in *profiles* are read, so this gives
    the same answer before and after candidate profiles are appended.
    """
    if not field:
        return field
    from . import candidates as field_mod, races as races_mod

    return field_mod.screen(field, races_mod.contestable(profiles, ELECTION_YEAR, record))


# The roster CSV's "Committee Assignments" column was typed for the 119th
# Congress. It is shown only while that Congress sits: on January 3 it would
# put every re-elected member on their old committees.
CURATED_COMMITTEES_CONGRESS = 119


def build_profiles(data, snapshot=None, field=None, finance=None, committees=None):
    """Build the unified profile list from loaded roster rows.

    *snapshot* is the authoritative ``congress-legislators`` extract from
    :mod:`kyc.legislators`. When present, the 2026 Senate class and every
    senator's term-end year come from it instead of from the hand-typed
    override table and a six-year-hop heuristic. It is optional so that
    ``build`` still works from the CSVs alone.

    *field* is the FEC's register of who has filed for the cycle
    (:mod:`kyc.candidates`). The roster carried 57 hand-curated challengers,
    which made the site report 436 races as having no declared challenger when
    only four of them actually did.

    The field is first passed through :func:`kyc.candidates.screen` against
    the races that exist this year (:func:`kyc.races.contestable`, derived
    from the sitting members built here), so stale registrations and filings
    for seats that are not on the ballot never become profiles or races.
    Callers that count ``filedCount`` must count the same screened field:
    :func:`screen_field` reproduces it from the finished profiles.

    Returns ``(profiles, stats)``.
    """
    as_of = age_as_of(snapshot)
    seats_up = term_ends = None
    people = {}
    record = (data or {}).get("record")
    sitting = None
    if snapshot:
        from . import cycle as cycle_mod, legislators as legislators_mod

        try:
            sitting = cycle_mod.snapshot_congress(snapshot)
        except cycle_mod.CycleError:
            sitting = None
        # A previous Congress's committee rosters are none at all.
        committees = legislators_mod.committees_current(committees, snapshot)
    curated_committees = sitting in (None, CURATED_COMMITTEES_CONGRESS)
    from . import legislators as legislators_mod

    # A chamber's rosters are used only once they are whole: a member on one
    # of the three committees a partial roster lists would read as sitting
    # on one.
    published = legislators_mod.committee_chambers(committees, snapshot)
    if snapshot:
        from . import legislators

        seats_up = legislators.seats_up_ids(snapshot, ELECTION_YEAR)
        term_ends = {
            person["bioguide"]: int(person["termEnd"][:4])
            for person in snapshot.get("legislators", [])
            if (person.get("termEnd") or "")[:4].isdigit()
        }
        people = legislators.by_bioguide(snapshot)
    if record:
        # The senators whose seats were on the 2026 ballot when the record was
        # frozen - not whoever's term happens to end now, which stops being
        # true for Florida and Ohio once their special elections' winners are
        # seated, and for everyone on January 3.
        from .record import senate_incumbents
        seats_up = senate_incumbents(record)

    members = _dedup_members(data["members"])
    candidates = _dedup_candidates(data["candidates"])

    profiles = []
    for index, row in enumerate(members):
        bioguide = clean_str(row.get("Bioguide ID"), "").upper()
        kind = (people.get(bioguide) or {}).get("chamber") or clean_str(row.get("Chamber"), "")
        chamber = "senate" if "Senate" in kind else "house"
        seats = None
        if committees and bioguide and chamber in published:
            seats = legislators_mod.assignments(committees, bioguide)
        member = _build_member(row, index, seats_up, term_ends,
                               person=people.get(bioguide), assignments=seats, as_of=as_of)
        # Speaker, floor leader, whip: the posts congress-legislators lists
        # for this bioguide id in the Congress the snapshot is of, never
        # typed, and never the previous Congress's (legislators.held_posts).
        posts = legislators_mod.held_posts(people.get(bioguide), sitting)
        if posts:
            member["leadership"] = posts
        if not curated_committees and not seats:
            # Never the previous Congress's seats from the roster column. A
            # member of a chamber whose rosters are out holds none; anyone
            # else's are not published yet, and the profile says so (rule 19).
            member["committees"] = ""
            if chamber not in published:
                member["committeesPending"] = sitting
        profiles.append(member)

    if record:
        profiles.extend(_former_members(data.get("former") or [], record, profiles,
                                        seats_up, as_of))
        _mark_record_roles(profiles, record, snapshot, field)

    from .record import seated

    member_count = sum(1 for p in profiles if seated(p))
    former_count = sum(1 for p in profiles if p.get("formerMember"))
    field = screen_field(field, profiles, record)

    # A curated candidate who has since been seated - a special election's
    # winner - is the member, by the FEC id Congress's record lists for them
    # (rule 25), never by name. Their curated id answers for the member
    # (``otherIds``), so a link or a market label saved under it still opens
    # the same person.
    owned = {}
    for profile in profiles:
        if seated(profile):
            for filing in (people.get(profile["id"]) or {}).get("fec") or []:
                owned[filing] = profile
        elif profile.get("raceRole") == "winner":
            # A 2026 winner who has left: the ids their archived row kept.
            for filing in profile.get("fecIds") or []:
                owned[filing] = profile
    for index, row in enumerate(candidates):
        filing = clean_str(row.get("FEC Candidate ID"), "")
        member = owned.get(filing)
        built = None
        if not member:
            # Or, until Congress's record lists that id, the member seated
            # in the row's own race since it was decided, by exactly the
            # row's first and last name (rule 25's same-seat signal).
            built = _build_candidate(row, index, as_of=as_of)
            member = _seated_in_race(built, profiles)
            if member and filing and not member.get("fecCandidateId"):
                member["fecCandidateId"] = filing
        if member and clean_str(row.get("ID"), ""):
            member.setdefault("otherIds", []).append(clean_str(row.get("ID"), ""))
            continue
        profiles.append(built or _build_candidate(row, index, as_of=as_of))

    roster_count = len(profiles)
    if field:
        from . import candidates as field_mod, fec as fec_mod

        # The FEC candidate id is the only exact identity we have, and it
        # reaches a roster profile through the finance cache - which is
        # applied *after* assembly. Without seeding it here the dedup falls
        # back to names, and the FEC's filed name is often not the one the
        # roster uses: "TUREK, JOSHUA" against "Josh Turek", "ARENHOLZ,
        # ASHLEY HINSON" against "Ashley Hinson". Both appeared twice in the
        # same race, once with a portrait and once without.
        claimed = set()
        for profile in profiles:
            cached = (finance or {}).get(fec_mod.profile_key(profile)) or {}
            if cached.get("candidate_id"):
                claimed.add(cached["candidate_id"])
        # And through the ids Congress's own records hold, with no name in
        # between (rule 25's exact signal): a sitting member's filings for
        # the chamber they sit in, and a record incumbent's for the chamber
        # of the seat they held. A special election's winner, seated in
        # December, would otherwise appear twice - their member profile and
        # their filing's - or, where the names agree, lose the filing and with
        # it their place in the race.
        claimed |= _claimed_ids(profiles, people, record)

        extra, _skipped = field_mod.to_profiles(field, profiles, claimed=claimed)
        profiles.extend(extra)

    for profile in profiles:
        apply_quality(profile)

    moved, reseated = _apply_filings(profiles, field, finance)
    links = _cross_link(profiles, people)

    # The page reads photo_url for the initial <img src>; keep it in step
    # with the head of the fallback chain.
    for profile in profiles:
        profile["photo_url"] = profile["photos"][0]

    voting_house = [
        p for p in profiles
        if p["chamber"] == "House" and p["state"] not in TERRITORIES and seated(p)
    ]
    stats = {
        "ageAsOf": as_of.isoformat(),
        "former": former_count,
        "field_stale": len(((field or {}).get("screened") or {}).get("stale", [])),
        "field_phantom": len(((field or {}).get("screened") or {}).get("phantom", [])),
        "members": member_count,
        "candidates": len(profiles) - member_count - former_count,
        "roster_candidates": roster_count - member_count,
        "filed_candidates": len(profiles) - roster_count,
        "total": len(profiles),
        "cross_linked": links,
        "contesting_elsewhere": moved,
        "reseated": reseated,
        # The Senate races, from the record when there is one: a seat stays a
        # 2026 race after its holder has left and its winner is seated.
        "senate_seats_up": (
            sum(1 for rid in record["races"] if rid.startswith("S-")) if record
            else sum(1 for p in profiles
                     if p["seatUp2026"] and not p["isCandidate"] and "Senate" in p["chamber"])
        ),
        "voting_house": len(voting_house),
        "generic_fields": sum(
            1 for p in profiles for st in p["quality"].values() if st == GENERIC
        ),
        "undisclosed_fields": sum(
            1 for p in profiles for st in p["quality"].values()
            if st in (NOT_DISCLOSED, UNKNOWN)
        ),
        "not_seeking": sum(
            1 for p in profiles
            if p["seatUp2026"] and not p["isCandidate"] and not p["seekingReelection2026"]
        ),
    }
    # Whose photograph each chain starts with; the portrait and enrichment
    # caches replace the first photograph later, and the build credits again.
    assign_credits(profiles)
    return profiles, stats
