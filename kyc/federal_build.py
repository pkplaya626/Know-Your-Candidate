"""What the federal pages load, built from the two caches.

- ``data/federal.js`` (``window.kycFederal``): the President and Vice
  President, every Cabinet office in the order of succession, the Supreme
  Court's members (and its retired justices, apart), and an index of the
  courts with their counts - everything the hub draws.
- ``data/judiciary/<court>.js`` (``window.kycCourt[<court>]``): one court's
  judges, for that court's page; 1,463 judges in one file would load on
  every page.
- ``data/judiciary/index.js`` (``window.kycJudgesIndex``): every sitting
  judge's id, name and court, for the hub's search, which links to the
  judge on their court's page.

An official's id is never a profile's: ``fjc-<nid>`` for a judge (the
FJC's own id), ``x-<name>`` for an executive officer. The latter is an
address, keyed on the person, never on the office, so a link shared to one
Secretary never opens the next one; it is never matched against anything.
Nobody here is in ``profiles.js``: these people are not members of Congress
and are never counted as such (rules 16 and 27).
"""

import re

from . import federal, federal_courts, federal_offices, judiciary, vacancies


class FederalBuildError(RuntimeError):
    pass


def slug(name):
    """``x-`` and the name's letters: "Robert F. Kennedy, Jr." ->
    ``x-robert-f-kennedy-jr``."""
    from .officers import _fold
    return "x-" + "-".join(_fold(name).split())


def _leader(person, office):
    out = {
        "id": slug(person["name"]), "name": person["name"], "office": office,
        "party": person.get("party"),
        "since": person.get("termStart"), "until": person.get("termEnd"),
        "photo": person.get("photo"),
        "photoSet": person.get("photoSet") or [],
        "links": {k: v for k, v in (
            ("whitehouse", person.get("page")),
            ("wikipedia", person["ids"].get("wikipedia")),
            ("ballotpedia", person["ids"].get("ballotpedia")),
            ("bioguide", person["ids"].get("bioguide"))) if v},
    }
    return out


def _holder(office):
    holder = office.get("holder")
    if not holder:
        return None
    page = holder.get("page") or {}
    return {
        "id": slug(holder["name"]), "name": holder["name"], "title": holder["title"],
        "photo": holder.get("photo"),
        "photoSet": holder.get("photoSet") or [],
        "page": {k: page[k] for k in ("status", "url", "acting") if page.get(k)},
        "senate": holder.get("senate"),
        "senateUnread": bool(holder.get("senateUnread")),
    }


def _when(value):
    """A date as the pages show it: the agreed ``{date, precision}``, and
    whether the sources gave one and disagreed."""
    if not value:
        return None
    wikidata, wikipedia = value.get("wikidata"), value.get("wikipedia")
    return {"shown": value.get("shown"),
            # Disagreement needs two dates; one source alone is "not in both".
            "differs": value.get("shown") is None and bool(wikidata) and bool(wikipedia),
            "sort": (wikidata or wikipedia or {}).get("date")}


def _change(row):
    """One holder of an office this term, as the pages show it."""
    confirmed = row.get("confirmed")
    out = {
        # The person's address: a former officer this term opens at it.
        "id": slug(row["name"]),
        "name": row["name"], "current": row.get("current"), "acting": row.get("acting"),
        "actingNote": row.get("actingNote"), "actingStart": row.get("actingStart"),
        "confirmed": {k: confirmed[k] for k in ("date", "yeas", "nays", "url", "vote", "nominee")}
        if confirmed else None,
        "start": _when(row.get("start")), "end": _when(row.get("end")),
        "wikidata": row.get("wikidata"), "wikipedia": row.get("wikipedia"),
    }
    return {k: v for k, v in out.items() if v not in (None, False, "")}


def _judge(record, links=None):
    """A judge as the pages show them: nothing a source did not state.
    *links* is the judge-links cache (kyc/judge_links.py): a Wikipedia
    article and a portrait joined through the FJC id, never a name."""
    keep = ("id", "name", "sortName", "status", "seats", "prior", "born", "education",
            "career", "otherNominations", "fjc", "justice", "retiredJustice", "courtService",
            "portrait")
    out = {k: record[k] for k in keep if record.get(k) not in (None, [], "")}
    from . import judge_links
    joined = judge_links.for_judge(links, record["id"].replace("fjc-", ""))
    if joined.get("wikidata"):
        out["wikidata"] = joined["wikidata"]
    if joined.get("wikipedia"):
        out["wikipedia"] = joined["wikipedia"]
    # The Court's own portrait of a justice stands; the Commons one is for
    # everyone the Court does not photograph.
    if joined.get("portrait") and not out.get("portrait"):
        out["portrait"] = joined["portrait"]
    # The name they go by; the directory's bracketed given name read out
    # beside it (kyc/judiciary.py).
    full = judiciary.full_name(out.get("name"))
    if full:
        out["name"], out["fullName"] = judiciary.display_name(out["name"]), full
    return out


def _opening(row):
    """A vacancy as the pages show it: the list's words and dates, no code."""
    keep = ("vacatedBy", "reason", "since", "announced", "vacancyDate", "nominee",
            "nominated", "emergency")
    return {k: row[k] for k in keep if row.get(k) not in (None, "", False)}


def build(root="."):
    """``(federal_payload, {court id: payload}, judges index, problems)``."""
    executive = federal.load_cache(root)
    courts = judiciary.load_cache(root)
    openings = vacancies.load_cache(root)
    if openings is None:
        raise FederalBuildError(f"no {vacancies.CACHE_PATH}; run 'vacancies'")
    if executive is None:
        raise FederalBuildError(f"no {federal.CACHE_PATH}; run 'federal'")
    if courts is None:
        raise FederalBuildError(f"no {judiciary.CACHE_PATH}; run 'judiciary'")
    from . import judge_links
    links = judge_links.load_cache(root)
    problems = [message for level, _code, message, _d in federal.problems(executive)
                if level == "error"]
    problems += [message for level, _code, message, _d in judiciary.problems(courts)
                 if level == "error"]
    problems += [message for level, _code, message, _d in vacancies.problems(openings)
                 if level == "error"]
    judges = courts["judges"]
    # Each court's vacancies, as the courts list them, by the list's own
    # court code (kyc/vacancies.py); a code no court has stays unplaced.
    # A judge the list implies still serves, whom the directory does not
    # list on that court at all, is marked so on the row (vacancies.py).
    vacant, coming = {}, {}

    def placed(row, future):
        out = _opening(row)
        if courts["courts"].get(row["court"], {}).get("listed") and \
                vacancies.judge_unlisted(row, judges, future=future):
            out["notInDirectory"] = True
        if future:
            # Announced, not yet happened: a judge "elevated" on this list is
            # a nominee to the other court, named where the lists name one.
            out["future"] = True
            to = vacancies.nominated_to(row, openings)
            if to:
                out["nominatedTo"] = {"id": to, "name": federal_courts.COURTS[to]["name"]}
        return out

    # A judge the courts' list has on senior status by its own date, whom
    # the directory still lists as active: not counted active, and the row
    # says which source says what (vacancies.listed_senior).
    disagree = vacancies.listed_senior(openings, judges)
    elevations = vacancies.pending_elevations(openings, judges)
    # Confirmed and not yet commissioned: listed apart on their court's
    # page, never among its judges or in its counts.
    pending = {}
    for row in courts.get("pending") or []:
        if isinstance(row, dict) and row.get("court"):
            pending.setdefault(row["court"], []).append(
                {k: row[k] for k in ("name", "appointedBy", "nominated", "confirmed", "vote", "fjc")
                 if row.get(k)})

    for row in openings["current"]:
        if row.get("court"):
            vacant.setdefault(row["court"], []).append(placed(row, False))
    for row in openings["future"]:
        if row.get("court"):
            coming.setdefault(row["court"], []).append(placed(row, True))
    offices = []
    # Who has held each office since the term began (kyc/cabinet.py).
    changes = executive.get("changes") or {}
    for office in executive["offices"]:
        table = next(o for o in federal_offices.OFFICES if o["key"] == office["key"])
        entry = {"key": office["key"], "office": office["office"], "body": office["body"],
                 "kind": office["kind"], "order": office.get("order"),
                 "pages": list(table["pages"]), "holder": _holder(office)}
        # The agency's own website, as USA.gov's directory lists it: shown
        # whatever the head-name check concluded (rule 8).
        site = (executive.get("sites") or {}).get(office["key"])
        if site:
            entry["site"] = site
        held = ((changes.get("offices") or {}).get(office["key"]) or {}).get("holders")
        if held:
            entry["history"] = [_change(row) for row in held]
            # An acting end the sources put after the successor's start is
            # not shown, and says why (kyc/cabinet.py overlaps).
            from . import cabinet
            for i in cabinet.overlaps(held):
                end = entry["history"][i]["end"]
                end["shown"], end["overlap"] = None, True
        offices.append(entry)
    # The circuit map's colours: the guide's, from one table (rule 12).
    from . import court_districts, court_info, geo
    colours = federal_courts.circuit_colours(geo.neighbours())
    # Which counties each district court covers, and its divisions, from
    # 28 U.S.C. 81-131 (kyc/court_districts.py): a county no district
    # places, in a state of several, stops the build.
    placed, trouble = court_districts.table(court_districts.load_cache(root), root)
    if trouble:
        raise FederalBuildError("28 U.S.C. 81-131 against the Census counties: " + "; ".join(trouble[:5]))
    divisions = court_districts.for_courts(placed)
    covered = court_districts.covers(placed)
    index = []
    for cid, court in federal_courts.COURTS.items():
        held = courts["courts"][cid]
        chief = held.get("chief")
        moving = sum(1 for (c, _jid) in disagree if c == cid)
        index.append({
            "id": cid, "name": court["name"], "kind": court["kind"],
            "circuit": court.get("circuit"), "states": list(court.get("states") or ()),
            "site": court_info.SITES[cid],
            "listed": held["listed"], "active": held["active"] - moving,
            "senior": held["senior"] + moving,
            **({"listedSenior": moving} if moving else {}),
            "chief": {"id": chief, "name": judiciary.display_name(judges[chief]["name"])}
            if chief else None,
            "chiefUnsettled": bool(held.get("chiefUnsettled")),
            **({"token": colours[court["circuit"]]}
               if court["kind"] == "appeals" and court.get("states") else {}),
            "vacancies": len(vacant.get(cid, [])),
            "nominees": sum(1 for r in vacant.get(cid, []) if r.get("nominee")),
            "future": len(coming.get(cid, [])),
            "futureNominees": sum(1 for r in coming.get(cid, []) if r.get("nominee")),
            "pending": len(pending.get(cid, [])),
            "appointers": appointers(cid, held, judges, {j for (c, j) in disagree if c == cid}),
            **_court_listed_chief(cid, held, courts),
        })
    scotus = courts["courts"]["scotus"]
    payload = {
        "asOf": {"executive": executive["asOf"], "judiciary": courts["asOf"]},
        "sources": {"executive": executive["sources"], "judiciary": courts["sources"]},
        "president": _leader(executive["president"], "President of the United States"),
        "vicePresident": _leader(executive["vicePresident"], "Vice President of the United States"),
        "offices": offices,
        "courts": index,
        # The national courts outside the directory, each linked to its own
        # list of judges (kyc/court_info.py).
        "otherCourts": [dict(c) for c in court_info.OTHER_COURTS],
        "courtSites": {"source": court_info.SOURCE, "reviewed": court_info.REVIEWED},
        "statute": (court_districts.load_cache(root) or {}).get("source"),
        "supremeCourt": {"members": [_judge(judges[i], links) for i in scotus["judges"]],
                         "retired": [_judge(judges[i], links) for i in scotus.get("retired") or []]},
        # Sitting judges: a retired justice is listed apart, never counted.
        "judges": sum(1 for j in judges.values() if not j.get("retiredJustice")),
        "changes": {k: changes[k] for k in ("since", "read", "sources") if changes.get(k)} or None,
        "vacancies": {
            "asOf": openings["asOf"], "sources": openings["sources"],
            "totals": openings["totals"], "future": len(openings["future"]),
            "emergencies": sum(1 for r in openings["current"] if r.get("emergency")),
            "futureNominees": sum(1 for r in openings["future"] if r.get("nominee")),
            # Every vacancy, now and announced, with its court: the hub's
            # one table of vacancies and nominees.
            "rows": [dict(row, court=cid) for cid in federal_courts.COURTS
                     for row in vacant.get(cid, []) + coming.get(cid, [])],
        },
    }
    per_court = {}
    for cid, held in courts["courts"].items():
        # A territorial court's file says only that its judges are not in
        # the directory, so every court page loads the same scripts.
        rows = []
        for i in held["judges"]:
            row = _judge(judges[i], links)
            listed = disagree.get((cid, i))
            if listed:
                row["listedSenior"] = {"since": listed["since"]}
            # Nominated to another court, as the announced list has it: said
            # on the judge's own record too, not only on the court's table.
            if i in elevations:
                to = elevations[i]
                row["nominatedTo"] = {"id": to["court"], "name": federal_courts.COURTS[to["court"]]["name"],
                                      "nominated": to.get("nominated"), "asOf": openings["asOf"]}
            rows.append(row)
        per_court[cid] = {"id": cid, "listed": held["listed"], "judges": rows,
                          "vacancies": vacant.get(cid, []), "future": coming.get(cid, [])}
        if divisions.get(cid):
            per_court[cid]["divisions"] = divisions[cid]
            per_court[cid]["covers"] = covered[cid]
        if pending.get(cid):
            per_court[cid]["pending"] = pending[cid]
        # A territorial court's judges, as its own site lists them
        # (kyc/territorial_courts.py): never in the FJC's directory.
        listed_by_court = (courts.get("territorial") or {}).get(cid)
        if not held["listed"] and listed_by_court:
            per_court[cid]["courtList"] = listed_by_court
        if held.get("retired"):
            per_court[cid]["retired"] = [_judge(judges[i], links) for i in held["retired"]]
    # One row per judge, with every court they sit on: a judge on several
    # courts (a roving judgeship) is one person.
    sitting_on = {}
    for cid, held in courts["courts"].items():
        for jid in held["judges"]:
            sitting_on.setdefault(jid, []).append(cid)
    # A name the directory brackets is found by either form: the row carries
    # the full name fifth, for the search only.
    moved = {jid for (_c, jid) in disagree}
    search = sorted(([jid, judiciary.display_name(judges[jid]["name"]), sitting_on[jid],
                      "listed-senior" if jid in moved else judges[jid]["status"]] +
                     ([judiciary.full_name(judges[jid]["name"])]
                      if judiciary.full_name(judges[jid]["name"]) else [])
                     for jid in sitting_on), key=lambda row: (row[1], row[0]))
    # Each officer's financial disclosures (kyc/oge.py), by office, while the
    # index was read for the officer who holds it now.
    from . import oge
    filed = (oge.load_cache(root) or {}).get("people") or {}
    listed = (oge.load_cache(root) or {}).get("positions") or {}
    for key, person, names in [("president", payload["president"], ("President",)),
                               ("vicePresident", payload["vicePresident"], ("Vice President",))] + [
            (o["key"], o["holder"], (o["office"], o["holder"].get("title")))
            for o in offices if o.get("holder")]:
        found = filed.get(key)
        # Not read for this holder is not "nothing filed" (rule 19).
        person["disclosures"] = (oge.for_page(found, listed, names)
                                 if found and found["holder"] == person["name"]
                                 else {"notRead": True})
    if filed:
        payload["disclosuresRead"] = (oge.load_cache(root) or {}).get("read")
    # The offices each officer has held (kyc/history.py), by the same id.
    from . import history, legislators
    people = (history.load_cache(root) or {}).get("people") or {}
    as_of, _sitting = history.membership(legislators.load_snapshot(root))
    for person in [payload["president"], payload["vicePresident"]] + [
            o["holder"] for o in offices if o.get("holder")]:
        if person["id"] in people:
            # An officer does not sit in Congress (Art. I, sec. 6).
            person["politicalHistory"] = history.for_page(people[person["id"]], as_of, False)
    payload["former"] = former_officers(payload, people, as_of)
    payload["succession"], trouble = succession(payload, executive,
                                                legislators.load_snapshot(root))
    problems += trouble
    _check_ids(payload, per_court)
    return payload, per_court, search, problems


def _court_listed_chief(cid, held, courts):
    """For a territorial court, the chief and the count its own site lists
    (kyc/territorial_courts.py), for the hub's row; nothing otherwise."""
    entry = (courts.get("territorial") or {}).get(cid)
    if held["listed"] or not entry or entry.get("unread"):
        return {}
    chief = next((j["name"] for j in entry["judges"] if j["chief"]), None)
    return {"courtListed": {"judges": len(entry["judges"]), "seats": entry["seats"],
                            "chief": chief, "read": entry["read"], "source": entry["source"]}}


def appointers(cid, held, judges, moving=()):
    """``[[President, count], ...]`` for a court's active judges, by the
    President who appointed each to this court, earliest appointment first
    (FEDERAL-22). Counted over the same judges as the court's ``active``
    figure: a judge the courts' list has on senior status (*moving*) is not
    active here either. A judge is shown without a party, and so is this:
    it is a count of Presidents, never of parties."""
    counts, first = {}, {}
    for jid in held["judges"]:
        if jid in moving:
            continue
        judge = judges[jid]
        if judge.get("retiredJustice"):
            continue
        seat = next((s for s in judge.get("seats") or [] if s.get("court") == cid), None)
        if seat is None or seat.get("seniorSince"):
            continue
        who = seat.get("appointedBy") or "Not recorded"
        counts[who] = counts.get(who, 0) + 1
        when = seat.get("commissioned") or "9999"
        first[who] = min(first.get(who, when), when)
    return [[who, counts[who]] for who in sorted(counts, key=lambda w: (first[w], w))]


def former_officers(payload, people=None, as_of=None):
    """Everyone who held a Cabinet office this term and has left it, by the
    id the changes list links: a former-this-term record, as a former
    member's profile is (rule 67), so a link to them never reads "nobody
    here". Someone who holds another office now opens as that office's
    holder instead; one person who left two offices is one record."""
    from . import history

    current = {payload["president"]["id"], payload["vicePresident"]["id"]} | {
        o["holder"]["id"] for o in payload["offices"] if o.get("holder")}
    out = {}
    for office in payload["offices"]:
        for row in office.get("history") or []:
            if row.get("current") or not row.get("end") or row["id"] in current:
                continue
            record = out.setdefault(row["id"], {
                "id": row["id"], "name": row["name"], "held": [],
                "links": {k: row[k] for k in ("wikipedia", "wikidata") if row.get(k)}})
            record["held"].append(dict(row, key=office["key"], office=office["office"],
                                       body=office["body"]))
            for k in ("wikipedia", "wikidata"):
                if row.get(k) and not record["links"].get(k):
                    record["links"][k] = row[k]
    for record in out.values():
        if people and record["id"] in people:
            record["politicalHistory"] = history.for_page(people[record["id"]], as_of, False)
    return sorted(out.values(), key=lambda r: r["name"])


SUCCESSION_OFFICERS = (("speaker", "Speaker of the House"),
                       ("presidentProTempore", "President pro tempore of the Senate"))


def congressional_officers(executive, snapshot):
    """``({key: {"member": snapshot row} | {"missing": reason}}, problems)``
    for the Speaker and the President pro tempore.

    Each chamber chooses its officer anew in each Congress, and
    congress-legislators records each choice as a role starting that day,
    with no end until it ends. So a role that began before the snapshot's
    Congress did is the last Congress's: on January 3 its Speaker would
    otherwise stay second in line until the file is updated, which can take
    two weeks (rule 68), and name the wrong person if the House changed
    hands. Nobody is named then, and the build says so. The holder must
    also be seated in the snapshot, by bioguide id (rule 17)."""
    from . import cycle

    seated = {m["bioguide"]: m for m in (snapshot or {}).get("legislators") or []}
    try:
        number = cycle.snapshot_congress(snapshot)
    except cycle.CycleError:
        number = None
    began = cycle.congress_start(number).isoformat() if number else None
    out, problems = {}, []
    for key, role in SUCCESSION_OFFICERS:
        held = (executive.get("succession") or {}).get(key)
        member = seated.get((held or {}).get("bioguide"))
        if not held:
            out[key] = {"missing": "congress-legislators lists nobody in this office"}
            problems.append(f"the line of succession names no {role}: congress-legislators lists none")
        elif began and (held.get("since") or "") < began:
            out[key] = {"missing": f"congress-legislators has not yet recorded the "
                                   f"{cycle.ordinal(number)} Congress's {role.split(' of ')[0]}"}
            problems.append(f"the line of succession names no {role}: congress-legislators' "
                            f"holder {held['bioguide']} took the office {held.get('since')}, before the "
                            f"{cycle.ordinal(number)} Congress began on {began}; run 'federal' once "
                            f"it records the new Congress's choice")
        elif not member:
            out[key] = {"missing": "the holder congress-legislators lists is not a sitting member"}
            problems.append(f"the line of succession names no {role}: {held['bioguide']} is not "
                            f"in the membership snapshot")
        else:
            out[key] = {"member": member}
    return out, problems


def succession(payload, executive, snapshot):
    """``(line, problems)``: who stands in the line of presidential
    succession now - the Vice President; the Speaker and the President pro
    tempore (3 U.S.C. 19(a), (b)) from congress-legislators' leadership
    roles, each checked as seated in the membership snapshot by bioguide id
    (rule 17); then the department heads in the order of 3 U.S.C. 19(d)(1).
    A congressional officer the snapshot does not seat is left out and
    reported, never guessed."""
    line = [{"role": "Vice President", "id": payload["vicePresident"]["id"],
             "name": payload["vicePresident"]["name"], "kind": "official"}]
    officers, problems = congressional_officers(executive, snapshot)
    for key, role in SUCCESSION_OFFICERS:
        found = officers[key]
        if "missing" in found:
            line.append({"role": role, "kind": "missing", "reason": found["missing"]})
            continue
        member = found["member"]
        line.append({"role": role, "id": member["bioguide"], "name": member["name"],
                     "state": member["state"], "kind": "member"})
    departments = sorted((o for o in payload["offices"] if o["kind"] == "department"),
                         key=lambda o: o["order"])
    for office in departments:
        holder = office.get("holder")
        line.append({"role": office["office"], "kind": "official" if holder else "missing",
                     **({"id": holder["id"], "name": holder["name"],
                         "acting": bool((holder.get("page") or {}).get("acting")
                                        or re.match(r"(?i)acting\b", holder.get("title") or ""))}
                        if holder else {})})
    return line, problems


_PROFILE_ID = re.compile(r"^(?:[A-Z]\d{6}|FEC_|CAND_|CURR_)")


def _check_ids(payload, per_court):
    """Official ids are disjoint from profile ids, and unique."""
    ids = [payload["president"]["id"], payload["vicePresident"]["id"]]
    ids += [o["holder"]["id"] for o in payload["offices"] if o["holder"]]
    for court in per_court.values():
        ids += [j["id"] for j in court["judges"]] + [j["id"] for j in court.get("retired", [])]
    clash = sorted({i for i in ids if _PROFILE_ID.match(i)})
    if clash:
        raise FederalBuildError(f"official ids that look like profile ids: {clash}")
    executive = ids[:2] + [o["holder"]["id"] for o in payload["offices"] if o["holder"]]
    if len(executive) != len(set(executive)):
        raise FederalBuildError("two executive officers share an id")
