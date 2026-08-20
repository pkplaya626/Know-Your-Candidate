"""Locating and reading the roster CSVs."""

import csv
import os

# Sitting members of the 119th Congress.
MEMBER_ROSTERS = (
    "Cleaned_House_119th.csv",
    "Cleaned_Senate_119th.csv",
)

# 2026 candidates, in ascending order of precedence: later files win when the
# same person appears more than once, so freshly resolved primaries override
# the broad roster.
CANDIDATE_ROSTERS = (
    "Congressional_Candidates_2026.csv",
    "Completed_Primary_Candidates_2026.csv",
    "Late_Primary_Candidates_2026.csv",
)


class MissingRosterError(FileNotFoundError):
    """Raised when none of the expected roster CSVs are present."""


def read_csv(path):
    """Read a CSV into a list of dicts, tolerating mixed encodings."""
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def load_rosters(names, root="."):
    """Read every roster in *names* that exists under *root*.

    Returns ``(rows, found, missing)`` where each row carries a
    ``_source`` key naming the file it came from.
    """
    rows, found, missing = [], [], []
    for name in names:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        chunk = read_csv(path)
        for row in chunk:
            row["_source"] = name
        rows.extend(chunk)
        found.append((name, len(chunk)))
    return rows, found, missing


def load_all(root="."):
    """Load member and candidate rosters.

    Raises :class:`MissingRosterError` if no member roster is found at all -
    building a congressional directory with zero members is never the intent,
    and silently emitting an empty site would hide the real problem.
    """
    members, m_found, m_missing = load_rosters(MEMBER_ROSTERS, root)
    candidates, c_found, c_missing = load_rosters(CANDIDATE_ROSTERS, root)

    if not m_found:
        raise MissingRosterError(
            "No member roster CSVs found in {!r}. Expected one of: {}".format(
                os.path.abspath(root), ", ".join(MEMBER_ROSTERS)
            )
        )

    return {
        "members": members,
        "candidates": candidates,
        "found": m_found + c_found,
        "missing": m_missing + c_missing,
    }
