"""The home search's index of places and bodies (``data/search.js``, rule 97).

The grid's search found people by name, a state or a district, and an
office typed into it ("Texas AG", "Travis County", "Armed Services") found
nobody, or someone whose text mentioned the word. ``assets/kyc-search.js``
answers such a query with a link to the page about the thing named. The
offices it reads from the files their own pages read (``stategov.js``,
``federal.js``, the profiles); what no file a page loads holds, this index
holds, each in the words the page it links to uses:

- ``legislatures``: each state's legislature by the name its constitution
  gives it (rule 75) and its two chambers, as the legislature page names
  them (``government_maps.legislature_title``).
- ``counties``: each state's counties as its county page names them
  (``county_areas.local_name``), by their Census code, which is how that
  page is addressed (``counties/tx.html#/?county=48453``).
- ``committees``: the committees the Congress guide's table lists, with
  who leads each, from the same rosters by the same rule
  (``pages.committee_leads``: by the seat's side, rule 48).
- ``tribes``: each tribal government, band and community as the BIA's
  Tribal Leaders Directory lists them, under the state the guide's map
  lists them in (``tribes.placed``), with the leader it names.

It is generated, signature-stamped (rule 76) and compared by ``verify``
(rule 18). Nothing in it is typed by hand.
"""

from .government_maps import LOWER_CHAMBER, STATES, legislature_title


def _legislatures():
    out = {}
    for code in STATES:
        if code == "NE":
            # One chamber, and no "Senate" of it to find (its members are
            # called senators; the body is the Legislature).
            out[code] = [legislature_title(code), None, None]
        else:
            out[code] = [legislature_title(code), "Senate",
                         LOWER_CHAMBER.get(code, "House of Representatives")]
    return out


def _counties(local_maps):
    out = {}
    for code in sorted(local_maps or {}):
        counties = local_maps[code].get("counties") or {}
        out[code] = [[fips, counties[fips]["name"]] for fips in sorted(counties)]
    return out


def _committees(profiles, committees):
    from .pages import _committee_group, committee_leads
    leads = committee_leads(profiles, committees)
    rows = []
    for code in sorted(leads):
        row = leads[code]
        info = row["info"]

        def people(seats):
            return [[p["id"], p["name"], title] for p, title, _rank in seats]
        rows.append([code, info.get("name") or code, _committee_group(info),
                     people(row["majority"]), people(row["minority"])])
    return rows


def _tribes(cache):
    from . import tribes
    found, _ = tribes.placed(cache or {})
    out = {}
    for code in STATES:
        here = sorted(found.get(code) or [], key=lambda e: e["name"].lower())
        rows = []
        for e in here:
            rows.append([e["name"], e.get("leader") or "", e.get("title") or "",
                         1 if e.get("disputed") else 0, ""])
            for a in e.get("affiliates") or []:
                rows.append([a["name"], a.get("leader") or "", a.get("title") or "",
                             1 if a.get("disputed") else 0, e["name"]])
        if rows:
            out[code] = rows
    return out


def build(local_maps, profiles, committees, tribes_cache):
    """The index's payload. *local_maps* is ``counties.build``'s, *committees*
    the summary's committee table (``summary["committees"]``), *tribes_cache*
    ``tribes.load_cache``'s."""
    return {
        "legislatures": _legislatures(),
        "counties": _counties(local_maps),
        "committees": _committees(profiles, committees),
        "tribes": _tribes(tribes_cache),
    }


def problems(payload):
    """What would make the index answer wrongly, as strings: a state with
    no counties (its page would be linked with nothing to pick), a county
    code that is not its state's, a name given twice in one state."""
    from .geo import FIPS_TO_STATE
    from .normalize import US_STATES
    fips_of = {code: fips for fips, code in FIPS_TO_STATE.items()}
    out = []
    for code, rows in sorted((payload.get("counties") or {}).items()):
        if not rows:
            out.append(f"{code}: no counties")
        names = [name for _f, name in rows]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            out.append(f"{code}: county name listed twice: {', '.join(twice)}")
        prefix = fips_of.get(code)
        if prefix:
            wrong = [f for f, _n in rows if not f.startswith(prefix)]
            if wrong:
                out.append(f"{code}: county codes of another state: {', '.join(wrong[:5])}")
    codes = set(US_STATES.values())
    for code in payload.get("legislatures") or {}:
        if code not in codes:
            out.append(f"legislature of an unknown state {code}")
    return out
