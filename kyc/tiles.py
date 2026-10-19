"""Tile layouts: the states as a grid of equal squares, and the House as one
square per district (audit 2026-10-17, VISUALS-27 and VISUALS-35).

The partisan map's House view is a choropleth: Wyoming's one seat and
California's fifty-two were the same weight of colour, and a delegation's
split could be read only by clicking it. A tile map gives every seat the same
square. The layout is computed here, once, from the district maps' own label
points, so the page only places what it is given.

Two layouts, one table of where each state sits:

* ``STATE_GRID`` places each state, D.C. and territory on a 12-column grid
  that keeps rough geography (the familiar tile-grid map). The States &
  territories page draws it as a picker of links.
* :func:`house` lays each state's districts out as a block of squares, the
  blocks placed row by row in ``STATE_GRID``'s order, and each district
  placed inside its block by where its label point lies: north to south by
  rows, then west to east. A district is a square at a fixed place, never
  coloured here: the page colours it by who sits for it.

Standard library only, like the rest of ``kyc/``.
"""

import math

from . import districts
from .normalize import TERRITORIES

# (row, column) on a 12-column grid. Rows 0-7 are the fifty states and D.C.;
# row 8 holds the territories, apart from the states.
STATE_GRID = {
    "AK": (0, 0), "ME": (0, 11),
    "WI": (1, 6), "VT": (1, 10), "NH": (1, 11),
    "WA": (2, 1), "ID": (2, 2), "MT": (2, 3), "ND": (2, 4), "MN": (2, 5),
    "IL": (2, 6), "MI": (2, 7), "NY": (2, 9), "MA": (2, 10),
    "OR": (3, 1), "NV": (3, 2), "WY": (3, 3), "SD": (3, 4), "IA": (3, 5),
    "IN": (3, 6), "OH": (3, 7), "PA": (3, 8), "NJ": (3, 9), "CT": (3, 10), "RI": (3, 11),
    "CA": (4, 1), "UT": (4, 2), "CO": (4, 3), "NE": (4, 4), "MO": (4, 5),
    "KY": (4, 6), "WV": (4, 7), "VA": (4, 8), "MD": (4, 9), "DE": (4, 10),
    "AZ": (5, 2), "NM": (5, 3), "KS": (5, 4), "AR": (5, 5), "TN": (5, 6),
    "NC": (5, 7), "SC": (5, 8), "DC": (5, 9),
    "OK": (6, 4), "LA": (6, 5), "MS": (6, 6), "AL": (6, 7), "GA": (6, 8),
    "HI": (7, 0), "TX": (7, 4), "FL": (7, 9),
    "GU": (8, 0), "MP": (8, 1), "AS": (8, 2), "PR": (8, 9), "VI": (8, 10),
}

# The House layout, in squares. A block is at most MAX_ROWS squares tall; a
# block's slot is at least LABEL_COLS wide, so the state's code above it has
# room; COLUMN is how far apart neighbouring grid columns start, so a row
# keeps its states roughly where they are on a map; GAP separates blocks.
MAX_ROWS = 4
LABEL_COLS = 2
COLUMN = 2.6
GAP = 0.6
# Each row of blocks has a band above it for the states' codes.
LABEL_BAND = 1.6
ROW_GAP = 0.5


class TileError(ValueError):
    """A district map that cannot be laid out: a data error, never skipped."""


def block_shape(seats):
    """``(columns, rows)`` of a state's block of *seats* squares: nearly
    square for a small delegation, never taller than ``MAX_ROWS``."""
    if seats < 1:
        raise TileError(f"a block of {seats} seats")
    rows = min(MAX_ROWS, max(1, round(math.sqrt(seats))))
    return math.ceil(seats / rows), rows


def place(points, cols, rows):
    """``{district: [column, row]}``: *points* (``{district: (lon, lat)}``)
    in a block of *cols* x *rows*, north to south by row and west to east
    within it. A short last row spreads its squares across the block's
    width, so a southern district stays under the part of the state it is
    in rather than at the block's west edge."""
    order = sorted(points, key=lambda n: (-points[n][1], points[n][0], n))
    out = {}
    for r in range(rows):
        chunk = sorted(order[r * cols:(r + 1) * cols], key=lambda n: (points[n][0], n))
        if not chunk:
            break
        if len(chunk) < cols and len(chunk) > 1:
            span = cols - 1
            spots = [round(i * span / (len(chunk) - 1)) for i in range(len(chunk))]
        elif len(chunk) < cols:
            spots = [cols // 2]
        else:
            spots = list(range(cols))
        for n, c in zip(chunk, spots):
            out[n] = [c, r]
    if len(out) != len(points):
        raise TileError(f"placed {len(out)} of {len(points)} districts")
    return out


def _label_points(code, root, key):
    """``{district: (lon, lat)}`` of one plan's label points."""
    topo = districts._read_json(districts.map_file(code, root), "District map")
    found = districts._numbered(topo, f"{key}_pts", "label point")
    return {number: districts._decode_point(topo, g["coordinates"])
            for number, g in found.items()}


def house(root="."):
    """The House as one square per voting seat.

    ``{"width", "height", "states": {code: {x, y, cols, rows, cells,
    cells2026?}}}``, in squares. ``cells`` places each district of the
    plan members now sit for (``{"7": [column, row]}``, "0" for a seat
    elected at large); ``cells2026`` is the 2026 plan's, only in a state
    whose map was redrawn for 2026 (``districts.REDRAWN``). D.C. and the
    territories elect delegates with no floor vote, so they have no block.
    """
    blocks = {}
    for code in sorted(STATE_GRID):
        if code in TERRITORIES:
            continue
        current = _label_points(code, root, "current")
        cols, rows = block_shape(len(current))
        entry = {"cols": cols, "rows": rows,
                 "cells": {str(n): at for n, at in sorted(place(current, cols, rows).items())}}
        if code in districts.REDRAWN:
            after = _label_points(code, root, "next")
            if len(after) != len(current):
                raise TileError(f"{code}: the 2026 plan has {len(after)} districts, "
                                f"the current one {len(current)}")
            entry["cells2026"] = {str(n): at for n, at in sorted(place(after, cols, rows).items())}
        blocks[code] = entry

    y = 0.0
    width = 0.0
    for row in sorted({STATE_GRID[c][0] for c in blocks}):
        codes = sorted((c for c in blocks if STATE_GRID[c][0] == row), key=lambda c: STATE_GRID[c][1])
        x_end = -GAP
        tallest = 0
        for code in codes:
            block = blocks[code]
            slot = max(block["cols"], LABEL_COLS)
            x = max(STATE_GRID[code][1] * COLUMN, x_end + GAP)
            # The block centred in its slot, under its code.
            block["x"] = round(x + (slot - block["cols"]) / 2, 2)
            block["y"] = round(y + LABEL_BAND, 2)
            x_end = x + slot
            tallest = max(tallest, block["rows"])
        width = max(width, x_end)
        y += LABEL_BAND + tallest + ROW_GAP
    return {"width": round(width, 2), "height": round(y - ROW_GAP, 2),
            # The band above each block that holds its code, and the
            # narrowest a block's slot is: the page places each state's
            # button over both.
            "band": LABEL_BAND, "slot": LABEL_COLS, "gap": GAP,
            "states": {c: blocks[c] for c in sorted(blocks)}}


def check(layout, seats_by_state=None):
    """Problems with a layout, as strings: blocks that overlap, a square
    outside its block or two on one square, and - given the House's seats
    by state - a block whose square count is not the state's seats."""
    problems = []
    states = layout["states"]
    for code, b in states.items():
        cells = [tuple(v) for v in b["cells"].values()]
        for key in ("cells", "cells2026"):
            at = [tuple(v) for v in (b.get(key) or {}).values()]
            if len(set(at)) != len(at):
                problems.append(f"{code}: two districts on one square ({key})")
            if any(not (0 <= c < b["cols"] and 0 <= r < b["rows"]) for c, r in at):
                problems.append(f"{code}: a square outside its block ({key})")
        if seats_by_state is not None and len(cells) != seats_by_state.get(code):
            problems.append(f"{code}: {len(cells)} squares for {seats_by_state.get(code)} seats")
    codes = sorted(states)
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            (pl, pr), (ql, qr) = slot_span(states[a]), slot_span(states[b])
            p, q = states[a], states[b]
            # Each block's slot, its code's band above it included.
            if (pl < qr and ql < pr
                    and p["y"] - LABEL_BAND < q["y"] + q["rows"] and q["y"] - LABEL_BAND < p["y"] + p["rows"]):
                problems.append(f"{a} and {b} overlap")
    return problems


def slot_span(block):
    """``(left, right)`` of the slot a block is centred in, as the page
    draws its button: a block narrower than ``LABEL_COLS`` sits in the
    middle of its slot, so its own ``x`` is not the slot's left edge."""
    slot = max(block["cols"], LABEL_COLS)
    left = block["x"] - (slot - block["cols"]) / 2
    return left, left + slot
