"""How many local governments each state has: the Census of Governments.

``python build_profile_site.py census`` downloads the Census Bureau's own
table of local governments by type and state (2022 Census of Governments,
table CG2200ORG02), reads it with the standard library - an .xlsx is a zip
of XML - and writes ``data/census_governments.json``. The guide's local map
reads that cache; nothing is typed in.

The table marks a type of government a state does not have with "X" - "not
applicable" - which is not the same claim as zero (rule 19), so it is kept
as ``None``: Texas has no township governments, which is a fact about Texas,
not a count of them. Every column must add up to the table's own national
row, or the fetch is refused.
"""

import datetime
import io
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from .geo import FIPS_TO_STATE

TABLE_URL = "https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org02.zip"
TABLE_FILE = "COG2022_CG2200ORG02_Data.xlsx"
TABLE_TITLE = "2022 Census of Governments, Table CG2200ORG02: Local Governments by Type and State"
CACHE_PATH = os.path.join("candidate_profiles_site", "data", "census_governments.json")

# The table's codes for the counts the guide shows.
KINDS = {
    "GO0002": "total",
    "GO0005": "county",
    "GO0007": "municipal",
    "GO0008": "township",
    "GO0009": "special",
    "GO0010": "school",
}

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class CensusError(RuntimeError):
    """The table could not be fetched, or does not add up."""


def _column(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sheet_rows(xlsx_bytes, sheet=1):
    """Rows of cell strings from one sheet of an .xlsx file."""
    book = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    shared = []
    if "xl/sharedStrings.xml" in book.namelist():
        for si in ET.fromstring(book.read("xl/sharedStrings.xml")).findall(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
    root = ET.fromstring(book.read(f"xl/worksheets/sheet{sheet}.xml"))
    for row in root.iter(f"{_NS}row"):
        cells = {}
        for c in row.findall(f"{_NS}c"):
            v = c.find(f"{_NS}v")
            if v is None:
                inline = c.find(f"{_NS}is")
                text = "".join(t.text or "" for t in inline.iter(f"{_NS}t")) if inline is not None else ""
            elif c.get("t") == "s":
                text = shared[int(v.text)]
            else:
                text = v.text or ""
            cells[_column(c.get("r"))] = text
        if cells:
            yield [cells.get(i, "") for i in range(max(cells) + 1)]


def parse(xlsx_bytes):
    """``(national, {code: counts})`` from the table; raises if it does not
    add up. A count is an int, or ``None`` where the table says "X"."""
    rows = list(sheet_rows(xlsx_bytes))
    if not rows:
        raise CensusError("the table is empty")
    head = {name: i for i, name in enumerate(rows[0])}
    for need in ("AMOUNT", "AGG_DESC", "ST"):
        if need not in head:
            raise CensusError(f"the table has no {need} column")
    by_fips = {}
    for row in rows[1:]:
        kind = KINDS.get(row[head["AGG_DESC"]])
        if not kind:
            continue
        amount = row[head["AMOUNT"]].strip()
        if amount == "X":
            value = None
        elif amount.isdigit():
            value = int(amount)
        else:
            raise CensusError(f"unreadable count {amount!r} for {row[head['ST']]} {kind}")
        by_fips.setdefault(row[head["ST"]], {})[kind] = value
    national = by_fips.pop("00", None)
    if not national:
        raise CensusError("the table has no national row")
    states = {}
    for fips, counts in by_fips.items():
        code = FIPS_TO_STATE.get(fips)
        if not code:
            raise CensusError(f"unknown state FIPS {fips!r}")
        states[code] = {kind: counts.get(kind) for kind in KINDS.values()}
    for kind in KINDS.values():
        total = sum(counts[kind] or 0 for counts in states.values())
        if total != national[kind]:
            raise CensusError(f"{kind}: the states add up to {total}, the table says {national[kind]}")
    return national, states


def fetch(timeout=120):
    """Download and read the table."""
    request = urllib.request.Request(TABLE_URL, headers={"User-Agent": "know-your-candidate"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            archive = response.read()
        data = zipfile.ZipFile(io.BytesIO(archive)).read(TABLE_FILE)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise CensusError(f"could not fetch {TABLE_URL}: {exc}") from exc
    return parse(data)


def save_cache(national, states, root="."):
    payload = {
        "source": TABLE_TITLE,
        "url": TABLE_URL,
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "year": 2022,
        "national": national,
        "states": {code: states[code] for code in sorted(states)},
    }
    path = os.path.join(root, CACHE_PATH)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
