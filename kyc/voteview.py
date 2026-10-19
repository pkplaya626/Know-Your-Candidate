"""DW-NOMINATE ideology scores from Voteview.

Downloads the public ``HSall_members.csv`` roll-call dataset, keeps the most
recent Congress per member, and writes a human-readable alignment string back
into the member roster CSVs.

Uses only the standard library, so the pipeline has no third-party
dependencies (this previously required pandas).
"""

import csv
import io
import os
import re
import urllib.error
import urllib.request

VOTEVIEW_URL = "https://voteview.com/static/data/out/members/HSall_members.csv"
ALIGNMENT_COLUMN = "Projected/Historical Voting Alignment"
_USER_AGENT = "know-your-candidate/2.0 (+https://voteview.com)"


class VoteviewError(RuntimeError):
    """Raised when the Voteview dataset cannot be fetched or parsed."""


def fetch_members(url=VOTEVIEW_URL, timeout=60):
    """Download and parse the Voteview member-level dataset."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise VoteviewError(f"Could not download {url}: {exc}") from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise VoteviewError(f"{url} returned no rows")
    for column in ("bioguide_id", "congress", "nominate_dim1"):
        if column not in rows[0]:
            raise VoteviewError(f"{url} is missing the {column!r} column")
    return rows


def latest_scores(rows):
    """Keep the most recent Congress per Bioguide ID.

    Returns ``{bioguide_id: (congress, nominate_dim1)}``.
    """
    latest = {}
    for row in rows:
        bioguide = (row.get("bioguide_id") or "").strip()
        if not bioguide:
            continue
        try:
            congress = int(float(row["congress"]))
            dim1 = float(row["nominate_dim1"])
        except (TypeError, ValueError):
            continue
        known = latest.get(bioguide)
        if known is None or congress > known[0]:
            latest[bioguide] = (congress, dim1)
    return latest


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def describe(dim1, congress=None):
    """Render a DW-NOMINATE first-dimension score as a display string.

    The first dimension runs roughly -1 (left) to +1 (right), and the words
    say where on that scale, in the scale's own terms. They were party
    names ("Moderate Republican", "Moderate Democrat"), which put a party
    on independents - Kevin Kiley and Angus King - and on anyone whose
    score sat past their own party's. The Congress the score is from goes
    with it: a score is a record of votes in one Congress.

    Nothing else is derived from it. A "~92% Party Loyalty" figure used to
    follow, computed as 80 + 30 x distance from centre: a formula shown as a
    statistic, given even to independents with no party to be loyal to. A
    party-unity rate has to be counted from roll calls, not inferred from a
    score.
    """
    if dim1 < -0.4:
        label = "well left of centre"
    elif dim1 < -0.1:
        label = "left of centre"
    elif dim1 <= 0.1:
        label = "near the centre"
    elif dim1 <= 0.4:
        label = "right of centre"
    else:
        label = "well right of centre"
    tail = f"; {_ordinal(congress)} Congress" if congress else ""
    return f"DW-NOMINATE: {dim1:+.2f} ({label}{tail})"


_DESCRIBED = re.compile(r"DW-NOMINATE:\s*([+-]?\d+(?:\.\d+)?)", re.I)


def read_described(text):
    """``(score, "119th Congress")`` from a string :func:`describe` wrote,
    as the profile dialog reads it (assets/kyc-profile.js): the score, and
    the Congress the parenthesis names after its ";" ("" when none). None
    for a profile with no score."""
    found = _DESCRIBED.search(str(text or ""))
    if not found:
        return None
    inner = re.search(r"\(([^)]+)\)", str(text))
    congress = (inner.group(1).split(";") + [""])[1].strip() if inner else ""
    return float(found.group(1)), congress


def chamber_scores(profiles):
    """``{"House"|"Senate": {"119th Congress": [score, ...]}}``: every
    sitting member's score, by chamber and by the Congress it is of - the
    ticks the profile dialog draws beside a member's own. Counted here, from
    every profile, rather than on the page: a state page holds its own
    state's people only (rule 94), and its dialog would have placed a
    senator among their own delegation as though it were the chamber."""
    from .record import seated

    out = {}
    for p in profiles:
        chamber = str(p.get("chamber") or "")
        if not seated(p) or not re.search("Senate|House", chamber):
            continue
        read = read_described(p.get("voting_alignment"))
        if read is None:
            continue
        word = "Senate" if "Senate" in chamber else "House"
        out.setdefault(word, {}).setdefault(read[1], []).append(read[0])
    return {word: {congress: sorted(scores) for congress, scores in sorted(by.items())}
            for word, by in sorted(out.items())}


def build_alignment_map(rows=None):
    """``{bioguide_id: alignment string}`` for every scored member."""
    rows = fetch_members() if rows is None else rows
    return {bg: describe(dim1, congress)
            for bg, (congress, dim1) in latest_scores(rows).items()}


def apply_to_roster(path, alignment_map):
    """Write alignment strings into one roster CSV.

    Rows whose Bioguide ID has no score keep their existing value. Returns
    ``(updated, total)``.
    """
    if not os.path.exists(path):
        return 0, 0

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not fieldnames:
        return 0, 0
    if ALIGNMENT_COLUMN not in fieldnames:
        fieldnames.append(ALIGNMENT_COLUMN)

    updated = 0
    for row in rows:
        bioguide = (row.get("Bioguide ID") or "").strip()
        alignment = alignment_map.get(bioguide)
        if alignment and row.get(ALIGNMENT_COLUMN) != alignment:
            row[ALIGNMENT_COLUMN] = alignment
            updated += 1

    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)

    return updated, len(rows)
