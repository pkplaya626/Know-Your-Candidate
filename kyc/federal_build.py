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
        "name": row["name"], "current": row.get("current"), "acting": row.get("acting"),
        "actingNote": row.get("actingNote"), "actingStart": row.get("actingStart"),
        "confirmed": {k: confirmed[k] for k in ("date", "yeas", "nays", "url", "vote", "nominee")}
        if confirmed else None,
        "start": _when(row.get("start")), "end": _when(row.get("end")),
        "wikidata": row.get("wikidata"), "wikipedia": row.get("wikipedia"),
    }
    return {k: v for k, v in out.items() if v not in (None, False, "")}


def _judge(record):
    """A judge as the pages show them: nothing a source did not state."""
    keep = ("id", "name", "sortName", "status", "seats", "prior", "born", "education",
            "career", "otherNominations", "fjc", "justice", "retiredJustice", "portrait")
    return {k: record[k] for k in keep if record.get(k) not in (None, [], "")}


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
    problems = [message for level, _code, message, _d in federal.problems(executive)
                if level == "error"]
    problems += [message for level, _code, message, _d in judiciary.problems(courts)
                 if level == "error"]
    problems += [message for level, _code, message, _d in vacancies.problems(openings)
                 if level == "error"]
    judges = courts["judges"]
    # Each court's vacancies, as the courts list them, by the list's own
    # court code (kyc/vacancies.py); a code no court has stays unplaced.
    vacant, coming = {}, {}
    for row in openings["current"]:
        if row.get("court"):
            vacant.setdefault(row["court"], []).append(_opening(row))
    for row in openings["future"]:
        if row.get("court"):
            coming.setdefault(row["court"], []).append(_opening(row))
    offices = []
    # Who has held each office since the term began (kyc/cabinet.py).
    changes = executive.get("changes") or {}
    for office in executive["offices"]:
        table = next(o for o in federal_offices.OFFICES if o["key"] == office["key"])
        entry = {"key": office["key"], "office": office["office"], "body": office["body"],
                 "kind": office["kind"], "order": office.get("order"),
                 "pages": list(table["pages"]), "holder": _holder(office)}
        held = ((changes.get("offices") or {}).get(office["key"]) or {}).get("holders")
        if held:
            entry["history"] = [_change(row) for row in held]
        offices.append(entry)
    # The circuit map's colours: the guide's, from one table (rule 12).
    from . import geo
    colours = federal_courts.circuit_colours(geo.neighbours())
    index = []
    for cid, court in federal_courts.COURTS.items():
        held = courts["courts"][cid]
        chief = held.get("chief")
        index.append({
            "id": cid, "name": court["name"], "kind": court["kind"],
            "circuit": court.get("circuit"), "states": list(court.get("states") or ()),
            "listed": held["listed"], "active": held["active"], "senior": held["senior"],
            "chief": {"id": chief, "name": judges[chief]["name"]} if chief else None,
            "chiefUnsettled": bool(held.get("chiefUnsettled")),
            **({"token": colours[court["circuit"]]}
               if court["kind"] == "appeals" and court.get("states") else {}),
            "vacancies": len(vacant.get(cid, [])),
            "nominees": sum(1 for r in vacant.get(cid, []) if r.get("nominee")),
            "future": len(coming.get(cid, [])),
        })
    scotus = courts["courts"]["scotus"]
    payload = {
        "asOf": {"executive": executive["asOf"], "judiciary": courts["asOf"]},
        "sources": {"executive": executive["sources"], "judiciary": courts["sources"]},
        "president": _leader(executive["president"], "President of the United States"),
        "vicePresident": _leader(executive["vicePresident"], "Vice President of the United States"),
        "offices": offices,
        "courts": index,
        "supremeCourt": {"members": [_judge(judges[i]) for i in scotus["judges"]],
                         "retired": [_judge(judges[i]) for i in scotus.get("retired") or []]},
        # Sitting judges: a retired justice is listed apart, never counted.
        "judges": sum(1 for j in judges.values() if not j.get("retiredJustice")),
        "changes": {k: changes[k] for k in ("since", "read", "sources") if changes.get(k)} or None,
        "vacancies": {
            "asOf": openings["asOf"], "sources": openings["sources"],
            "totals": openings["totals"], "future": len(openings["future"]),
            "emergencies": sum(1 for r in openings["current"] if r.get("emergency")),
        },
    }
    per_court = {}
    for cid, held in courts["courts"].items():
        # A territorial court's file says only that its judges are not in
        # the directory, so every court page loads the same scripts.
        per_court[cid] = {"id": cid, "listed": held["listed"],
                          "judges": [_judge(judges[i]) for i in held["judges"]],
                          "vacancies": vacant.get(cid, []), "future": coming.get(cid, [])}
        if held.get("retired"):
            per_court[cid]["retired"] = [_judge(judges[i]) for i in held["retired"]]
    # One row per judge, with every court they sit on: a judge on several
    # courts (a roving judgeship) is one person.
    sitting_on = {}
    for cid, held in courts["courts"].items():
        for jid in held["judges"]:
            sitting_on.setdefault(jid, []).append(cid)
    search = sorted(([jid, judges[jid]["name"], sitting_on[jid], judges[jid]["status"]]
                     for jid in sitting_on), key=lambda row: (row[1], row[0]))
    # Each officer's financial disclosures (kyc/oge.py), by office, while the
    # index was read for the officer who holds it now.
    from . import oge
    filed = (oge.load_cache(root) or {}).get("people") or {}
    for key, person in [("president", payload["president"]),
                        ("vicePresident", payload["vicePresident"])] + [
            (o["key"], o["holder"]) for o in offices if o.get("holder")]:
        found = filed.get(key)
        if found and found["holder"] == person["name"]:
            person["disclosures"] = oge.for_page(found)
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
    _check_ids(payload, per_court)
    return payload, per_court, search, problems


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
