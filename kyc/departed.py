"""Members who left the sitting Congress, so a reader can still find them.

A reader following the news about Marjorie Taylor Greene typed her name and
read "No profiles found": she resigned on 2026-01-05, before the roster was
built, so she was in no file the page read, and nothing said why (audit
2026-10-17, GRID-08). Former_Members.csv holds only members ``congress
--apply`` archived from the roster, and she was never on it.

So the ``congress`` refresh also keeps, from congress-legislators'
``legislators-historical``, everyone whose last term ended while the sitting
Congress sat: the day the record gives, and nothing it does not (it records
no reason - resignation, death, appointment elsewhere - so none is shown;
rule 28). The cache is matched to the membership by bioguide id only
(rules 3 and 17). Who holds the seat now is the membership snapshot's to
say, at build time, by seat: never stored, so it cannot go stale.

They are search-only rows on the grid, never profiles, and so never counted
in any "who represents me" figure (rules 27 and 67).
"""

import datetime
import json
import os

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "departed_members.json")


def build(historical, snapshot, sitting=None):
    """The cache: who in *historical* left during the *sitting* Congress
    (the snapshot's, by default) on or before the day *snapshot* was read.

    A person the snapshot still seats is not departed, whatever the
    historical file says (a member who moved chamber is in the current file
    only). Raises ValueError on a snapshot with no read date.
    """
    from . import cycle, legislators

    read = str((snapshot or {}).get("fetched") or "")[:10]
    if not read:
        raise ValueError("the snapshot has no read date")
    number = sitting or cycle.snapshot_congress(snapshot)
    began = cycle.congress_start(number).isoformat()
    seated = set(legislators.by_bioguide(snapshot))
    members = []
    for entry in historical or []:
        terms = entry.get("terms") or []
        if not terms:
            continue
        last = terms[-1]
        left = str(last.get("end") or "")[:10]
        # Ended after this Congress's first day: a term that ended on it
        # was the previous Congress's.
        if not (began < left <= read):
            continue
        person = legislators.trim(entry)
        if not person or person["bioguide"] in seated:
            continue
        name = legislators.display_name(person["name"], person)
        row = {
            "bioguide": person["bioguide"],
            "name": name,
            "chamber": person["chamber"],
            "state": person["state"],
            "party": person["party"],
            "termStart": str(last.get("start") or "")[:10],
            "left": left,
        }
        if person["chamber"] == "House":
            row["district"] = person["district"]
        else:
            row["senateClass"] = person["senateClass"]
        found = legislators.aliases(person, name)
        if found:
            row["aliases"] = found
        members.append(row)
    members.sort(key=lambda r: (r["left"], r["bioguide"]))
    return {
        "source": legislators.HISTORICAL_URL,
        "congress": number,
        "membershipRead": read,
        "members": members,
    }


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


def _seat_key(row):
    if row.get("chamber") == "Senate":
        return ("Senate", row.get("state"), row.get("senateClass"))
    return ("House", row.get("state"), row.get("district"))


def for_page(cache, snapshot, profiles):
    """``[{id, name, aliases, chamber, state, district, left, holder}]`` for
    the page's search, and ``problems``: ``[(level, code, message, detail)]``.

    Kept only while the cache is of the snapshot's Congress (a new Congress
    starts its own list, rule 68). Left out: anyone the snapshot seats (the
    cache is older than the membership - reported), and anyone with a profile
    here, which already says they left (a record incumbent, rule 67).
    ``holder`` is whoever the snapshot seats in that seat now, by bioguide
    id, or None when it seats nobody there.
    """
    from . import cycle, legislators, overrides

    problems = []
    if not cache or not snapshot:
        return [], problems
    try:
        number = cycle.snapshot_congress(snapshot)
    except cycle.CycleError:
        return [], problems
    if cache.get("congress") != number:
        return [], problems
    people = legislators.by_bioguide(snapshot)
    profiled = {p.get("id") for p in profiles or []}
    names = {p.get("id"): p.get("name") for p in profiles or []}
    holders = {}
    for bioguide, person in people.items():
        holders.setdefault(_seat_key(person), []).append(bioguide)
    out = []
    seated = []
    for row in cache.get("members") or []:
        bioguide = str(row.get("bioguide") or "").upper()
        if not bioguide:
            continue
        if bioguide in people:
            seated.append(f"{row.get('name')} ({bioguide})")
            continue
        if bioguide in profiled:
            continue
        now = holders.get(_seat_key(row)) or []
        holder = None
        if len(now) == 1:
            sitting = people[now[0]]
            holder = {"id": now[0], "name": names.get(now[0]) or sitting.get("name"),
                      "since": sitting.get("termStart")}
        aliases = list(row.get("aliases") or [])
        for alias, _evidence in overrides.SEARCH_ALIASES.get(bioguide, ()):
            if alias not in aliases:
                aliases.append(alias)
        item = {"id": bioguide, "name": row.get("name"), "chamber": row.get("chamber"),
                "state": row.get("state"), "party": row.get("party"),
                "left": row.get("left"), "holder": holder}
        if row.get("chamber") == "House":
            item["district"] = row.get("district")
        if aliases:
            item["aliases"] = aliases
        out.append(item)
    shown = {item["id"] for item in out}
    stale = sorted(b for b in overrides.SEARCH_ALIASES if b not in profiled and b not in shown)
    if stale:
        problems.append(("warn", "search-alias-unmatched",
                         f"{len(stale)} overrides.SEARCH_ALIASES keys are neither a profile nor "
                         "a departed member the page lists", ", ".join(stale)))
    if seated:
        problems.append(("warn", "departed-seated",
                         f"{len(seated)} people {CACHE_PATH} lists as having left are seated in "
                         "the membership snapshot; they are not shown as former members. "
                         "Refresh with: python build_profile_site.py congress",
                         ", ".join(seated)))
    return out, problems
