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


def describe(dim1):
    """Render a DW-NOMINATE first-dimension score as a display string.

    The first dimension runs roughly -1 (left) to +1 (right). The loyalty
    figure is an explicit heuristic derived from distance off centre, not a
    published statistic, and is labelled as approximate for that reason.
    """
    distance = abs(dim1)

    if dim1 < -0.4:
        label = "Solidly Progressive"
    elif dim1 < -0.1:
        label = "Moderate Democrat"
    elif dim1 <= 0.1:
        label = "Centrist / Swing Voter"
    elif dim1 <= 0.4:
        label = "Moderate Republican"
    else:
        label = "Solidly Conservative"

    if -0.1 <= dim1 <= 0.1:
        loyalty = "Highly Independent"
    else:
        loyalty = f"~{min(99, int(80 + distance * 30))}% Party Loyalty"

    return f"DW-NOMINATE: {dim1:+.2f} ({label}) • {loyalty}"


def build_alignment_map(rows=None):
    """``{bioguide_id: alignment string}`` for every scored member."""
    rows = fetch_members() if rows is None else rows
    return {bg: describe(dim1) for bg, (_, dim1) in latest_scores(rows).items()}


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
