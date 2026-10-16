"""Which election this site is about, and which Congress is sitting.

Two facts, one place each (audit CG-7, the January 3, 2027 changeover):

* the cycle - the election the site covers - is an editorial decision, set
  here by hand (``CYCLE``) and nowhere else;
* the sitting Congress is a fact the data states: the Congress most House
  members' terms in the committed snapshot began in
  (:func:`snapshot_congress`). It never reads the clock, so a build is
  reproducible (rule 18).

Everything else is date arithmetic.
"""

import collections
import datetime
import hashlib
import json
import os

CYCLE = 2026

# The races of a cycle, frozen once from the sitting Congress before the
# election (kyc/record.py). Its content signature is pinned here, so a change
# to the set of races is a code change somebody reviews (rules 18 and 41).
RECORD_PATH = os.path.join("candidate_profiles_site", "data", "record_{cycle}.json")
RECORD_SIGNATURES = {
    2026: "1fd61033531d9a5cea3451b4b074819a780a81150556faf8bf8a8f4d1eae2503",
}

# A new Congress's terms begin at noon on January 3 (Twentieth Amendment):
# 17:00 UTC.
NOON_UTC = datetime.time(17, 0)


class CycleError(RuntimeError):
    pass


def general_election_day(year):
    """The Tuesday after the first Monday in November (2 U.S.C. 7)."""
    day = datetime.date(year, 11, 1)
    while day.weekday() != 0:
        day += datetime.timedelta(days=1)
    return day + datetime.timedelta(days=1)


def congress_for_date(day):
    """The Congress sitting on *day*: the 119th from 2025-01-03 to 2027-01-02.

    Terms change on January 3, so a date before it belongs to the previous
    year's Congress."""
    if isinstance(day, str):
        day = datetime.date.fromisoformat(day[:10])
    year = (day - datetime.timedelta(days=2)).year
    return (year - 1789) // 2 + 1


def congress_start(number):
    """The day the *number*th Congress's terms begin."""
    return datetime.date(1789 + 2 * (number - 1), 1, 3)


def electing_congress(cycle=CYCLE):
    """The Congress a November election in *cycle* elects: 2026 elects the 120th."""
    return congress_for_date(general_election_day(cycle)) + 1


def ordinal(number):
    """120 -> "120th"."""
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def snapshot_congress(snapshot):
    """The Congress the committed membership is of.

    The Congress most House terms began in: 432 terms starting 2025-01-03
    is the 119th. A House member seated in a special election mid-Congress
    counts for the Congress they joined. Fewer than four in five agreeing is
    a malformed snapshot, and fails loudly rather than guessing.
    """
    starts = [p.get("termStart") for p in (snapshot or {}).get("legislators", [])
              if p.get("chamber") == "House" and p.get("termStart")]
    if not starts:
        raise CycleError("the snapshot lists no House terms")
    counts = collections.Counter(congress_for_date(s) for s in starts)
    number, n = counts.most_common(1)[0]
    if n < 0.8 * len(starts):
        raise CycleError(f"House terms in the snapshot span several Congresses: "
                         f"{dict(counts)}")
    return number


def phase(snapshot, cycle=CYCLE):
    """``"campaign"`` until the Congress the cycle elects is sitting, then
    ``"record"``.

    Both must hold for the record: the snapshot is of that Congress, and it
    was read after noon on the day its terms began - so an early or partial
    upstream file cannot turn the site over before the swearing-in.
    """
    electing = electing_congress(cycle)
    if snapshot_congress(snapshot) < electing:
        return "campaign"
    fetched = (snapshot or {}).get("fetched") or ""
    try:
        read = datetime.datetime.fromisoformat(fetched.replace("Z", "+00:00"))
    except ValueError:
        return "campaign"
    if read.tzinfo is None:
        read = read.replace(tzinfo=datetime.timezone.utc)
    sworn = datetime.datetime.combine(congress_start(electing), NOON_UTC,
                                      tzinfo=datetime.timezone.utc)
    return "record" if read >= sworn else "campaign"


# ------------------------------------------------------------------- record

def record_path(root=".", cycle=CYCLE):
    return os.path.join(root, RECORD_PATH.format(cycle=cycle))


def load_record(root=".", cycle=CYCLE):
    """The frozen race record for *cycle*, or ``None`` when there is none."""
    path = record_path(root, cycle)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def record_signature(record):
    """Content hash of the record's race set, the part that is frozen."""
    races = (record or {}).get("races") or {}
    text = json.dumps(races, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
