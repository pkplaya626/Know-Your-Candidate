"""Turn the TopoJSON state atlas into plain SVG path data at build time.

The map page used to pull d3 and topojson-client off two different CDNs, ship
an 82 KB TopoJSON blob inline, and decode it in the browser on every page load
- roughly 300 KB of third-party JavaScript to draw 51 static shapes that never
change between builds.

The shapes are decoded here instead, once, and emitted as ready-to-render
``<path d="...">`` strings. The page then needs no mapping library at all.

The atlas is *already projected* (Albers USA, fitted to a 975x610 viewBox), so
this module does no cartography: it only reverses TopoJSON's quantised
delta encoding. Nothing here is a judgement call about geography.
"""

import heapq
import json
import math
import os

# us-atlas 10m, states + nation, pre-projected to the 975x610 Albers USA box.
ATLAS_FILE = "us_atlas_states_topo.json"

# The viewBox the atlas was fitted to. Kept next to the data it describes so
# the page and the geometry can never disagree about the coordinate space.
VIEWBOX_WIDTH = 975
VIEWBOX_HEIGHT = 610

# One decimal is ~0.1 px in a 975-wide box: below anything a screen can show,
# and it keeps the emitted file about a third the size of full precision.
_PRECISION = 1

# Census FIPS -> postal code. The atlas identifies states by FIPS only.
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "72": "PR", "78": "VI",
}

# Territories are not in the atlas - they are too small to project usefully at
# national scale, and three of them are thousands of miles outside the frame.
# They render as a labelled strip beneath the map, so the page still offers a
# way to reach every delegation. The shapes are schematic, not cartographic,
# and the page labels them as such.
TERRITORY_ORDER = ("DC", "PR", "VI", "GU", "MP", "AS")

TERRITORY_SHAPES = {
    "DC": "M 20 2 L 34 16 L 20 30 C 15 28 10 25 8 18 L 20 2 Z",
    "PR": "M 4 10 L 10 9 L 20 9 L 30 10 L 36 12 L 36 18 L 30 20 L 20 21 L 10 20 L 4 17 Z",
    "GU": "M 20 2 C 25 2 25 7 22 10 C 19 12 21 15 24 18 C 26 21 21 23 17 20 "
          "C 14 17 16 14 18 10 C 20 7 15 4 20 2 Z",
    "VI": "M 10 6 C 14 4 18 6 16 10 C 12 10 8 8 10 6 Z "
          "M 22 6 C 26 6 28 10 24 12 C 20 12 20 8 22 6 Z "
          "M 16 18 C 22 16 30 16 28 20 C 22 22 14 20 16 18 Z",
    "AS": "M 6 14 C 14 10 26 12 30 14 C 22 18 12 18 6 14 Z "
          "M 34 16 A 1.5 1.5 0 1 0 34 19 A 1.5 1.5 0 1 0 34 16",
    "MP": "M 24 4 C 26 4 26 8 24 10 C 22 8 22 4 24 4 Z "
          "M 22 12 C 24 12 24 16 22 18 C 20 16 20 12 22 12 Z "
          "M 16 20 C 19 20 19 24 16 26 C 13 24 13 20 16 20 Z",
}

TERRITORY_NAMES = {
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "VI": "U.S. Virgin Islands",
    "GU": "Guam",
    "MP": "Northern Mariana Islands",
    "AS": "American Samoa",
}


class AtlasError(RuntimeError):
    """Raised when the atlas file is missing or not the shape we expect."""


# ------------------------------------------------------------------ decoding

def load_atlas(root="."):
    """Read and sanity-check the TopoJSON atlas."""
    path = os.path.join(root, ATLAS_FILE)
    if not os.path.exists(path):
        raise AtlasError(f"Atlas not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            topo = json.load(handle)
    except ValueError as exc:
        raise AtlasError(f"{path} is not valid JSON: {exc}") from exc

    if topo.get("type") != "Topology":
        raise AtlasError(f"{path} is not a TopoJSON Topology")
    if "states" not in topo.get("objects", {}):
        raise AtlasError(f"{path} has no 'states' object")
    return topo


def decode_arcs(topo):
    """Return every arc as a list of absolute ``(x, y)`` pairs.

    TopoJSON stores arcs as quantised integer deltas against a shared
    transform; the first point is absolute and each later point is an offset
    from the one before it.
    """
    transform = topo.get("transform")
    raw = topo.get("arcs") or []
    if not transform:
        # An unquantised topology stores real coordinates directly.
        return [[(float(x), float(y)) for x, y in arc] for arc in raw]

    (sx, sy) = transform["scale"]
    (tx, ty) = transform["translate"]

    arcs = []
    for arc in raw:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * sx + tx, y * sy + ty))
        arcs.append(points)
    return arcs


def _ring(arc_indices, arcs):
    """Stitch a ring together from its arc indices.

    A negative index means "arc ``~i`` traversed backwards"; the shared
    endpoint between consecutive arcs is dropped so it is not emitted twice.
    """
    points = []
    for index in arc_indices:
        if index < 0:
            segment = list(reversed(arcs[~index]))
        else:
            segment = arcs[index]
        if points and segment and points[-1] == segment[0]:
            segment = segment[1:]
        points.extend(segment)
    return points


def geometry_rings(geometry, arcs):
    """Every ring of a Polygon or MultiPolygon, as point lists."""
    kind = geometry.get("type")
    if kind == "Polygon":
        return [_ring(ring, arcs) for ring in geometry.get("arcs", [])]
    if kind == "MultiPolygon":
        return [
            _ring(ring, arcs)
            for polygon in geometry.get("arcs", [])
            for ring in polygon
        ]
    # Points and lines have no area; a state atlas should not contain them.
    return []


# ------------------------------------------------------------------ geometry

def _round(value):
    # ``+ 0.0`` normalises -0.0 to 0.0 so the output is stable across
    # platforms and a rebuild is byte-for-byte identical.
    return round(value, _PRECISION) + 0.0


def _num(value):
    """Shortest exact spelling of a rounded coordinate: ``12.0`` -> ``12``."""
    text = f"{value:.{_PRECISION}f}"
    if text.endswith(".0"):
        text = text[:-2]
    return "-0" if text == "-0" else text


def rings_to_path(rings):
    """Render rings as one SVG path string.

    Coordinates are emitted as relative moves. Every delta is the difference
    between two already-rounded absolute points, so replaying them reproduces
    those points exactly - relative encoding here is a compression choice, not
    a loss of precision. It roughly halves the emitted geometry.

    Points that collapse onto each other once rounded are dropped: they draw
    nothing and only cost bytes.
    """
    parts = []
    for ring in rings:
        if len(ring) < 3:
            continue
        drawn = []
        for x, y in ring:
            point = (_round(x), _round(y))
            if not drawn or drawn[-1] != point:
                drawn.append(point)
        # A closed ring repeats its first point; "Z" already does that.
        if len(drawn) > 1 and drawn[0] == drawn[-1]:
            drawn.pop()
        if len(drawn) < 3:
            continue

        px, py = drawn[0]
        body = []
        for x, y in drawn[1:]:
            dx, dy = _round(x - px), _round(y - py)
            # "l -3,4" needs no separator before a negative number.
            sep = "" if dy < 0 else ","
            body.append(f"{_num(dx)}{sep}{_num(dy)}")
            px, py = x, y
        parts.append(f"M{_num(drawn[0][0])},{_num(drawn[0][1])}l" + " ".join(body) + "Z")
    return "".join(parts)


def signed_distance(x, y, rings):
    """Distance from ``(x, y)`` to the nearest edge of *rings*: positive
    inside (even-odd, so holes are outside), negative outside."""
    inside, best = False, float("inf")
    for ring in rings:
        n = len(ring)
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                inside = not inside
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) /
                                                      (dx * dx + dy * dy)))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best if inside else -best


def _crosses(ax, ay, bx, by, box):
    """Whether segment a-b touches the inside of *box* (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def box_room(x, y, rings, aspect=1.6):
    """The half-height of the largest box, *aspect* times as wide as it is
    tall, centred on ``(x, y)`` and inside *rings* - how big a label can be
    written there. A circle's radius is the wrong test for a two-letter code:
    Tennessee is thin and long, and "TN" is long and thin too."""
    if signed_distance(x, y, rings) <= 0:
        return 0.0
    edges = [(ring[i], ring[(i + 1) % len(ring)]) for ring in rings for i in range(len(ring))]

    def fits(k):
        box = (x - aspect * k, y - k, x + aspect * k, y + k)
        return not any(_crosses(a[0], a[1], b[0], b[1], box) for a, b in edges)

    low, high = 0.0, 1.0
    while fits(high):
        low, high = high, high * 2
    for _ in range(24):
        middle = (low + high) / 2
        low, high = (middle, high) if fits(middle) else (low, middle)
    return low


def outline_distance(rings):
    """A signed distance function for the land a tiling of *rings* covers.

    The rings are a whole map's districts. Inside is by the even-odd rule
    over all of them; distance is measured only to edges no two rings share
    - the coast and the state line - so the lines between the districts are
    not treated as edges of the land. A shared edge is recognised by its
    exact coordinates, which a topology's shared arcs guarantee.
    """
    count = {}
    for ring in rings:
        for i in range(len(ring)):
            a, b = tuple(ring[i]), tuple(ring[(i + 1) % len(ring)])
            if a != b:
                key = (a, b) if a <= b else (b, a)
                count[key] = count.get(key, 0) + 1
    edges = [key for key, seen in count.items() if seen == 1]

    def distance(x, y):
        inside = False
        for ring in rings:
            n = len(ring)
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                    inside = not inside
        best = float("inf")
        for (ax, ay), (bx, by) in edges:
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return best if inside else -best

    return distance


def polylabel(rings, cells=8, within=None):
    """The interior point farthest from any edge - the pole of
    inaccessibility, after Mapbox's polylabel.

    A label at the area-weighted centroid drifted to wherever a shape's
    mass happened to balance: 4 px from Florida's coast, onto Louisiana's
    coastal marsh, between Michigan's peninsulas, and into the Pacific
    between Hawaii's islands. This point is inside the shape, as far from
    its edges as the shape allows.

    *within*, a signed distance function for a second region, asks for the
    point of the overlap instead: a new district that runs out to sea is
    labelled on its land. Inside both, the distance to the overlap's edge is
    the smaller of the two distances, so the search is the same.
    """
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    size = max(x1 - x0, y1 - y0)
    precision = size / 400
    cell = size / cells
    heap, counter = [], 0

    def distance(x, y):
        d = signed_distance(x, y, rings)
        return d if within is None else min(d, within(x, y))

    def push(x, y, half):
        nonlocal counter
        d = distance(x, y)
        heapq.heappush(heap, (-(d + half * math.sqrt(2)), counter, x, y, half, d))
        counter += 1

    y = y0
    while y < y1:
        x = x0
        while x < x1:
            push(x + cell / 2, y + cell / 2, cell / 2)
            x += cell
        y += cell
    middle = ((x0 + x1) / 2, (y0 + y1) / 2)
    best = (distance(*middle), middle[0], middle[1])
    while heap:
        bound, _, x, y, half, d = heapq.heappop(heap)
        if d > best[0]:
            best = (d, x, y)
        if -bound - best[0] <= precision:
            continue
        half /= 2
        for sx in (-half, half):
            for sy in (-half, half):
                push(x + sx, y + sy, half)
    if best[0] <= 0:
        raise AtlasError("no interior point found for a shape")
    return best[1], best[2]


def label_point(rings):
    """Where to write a shape's name: its pole of inaccessibility, rounded."""
    if not rings:
        return None
    x, y = polylabel(rings)
    return (_round(x), _round(y))


def bounds(rings):
    """``(minX, minY, maxX, maxY)`` over every point, or ``None``."""
    points = [p for ring in rings for p in ring]
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (_round(min(xs)), _round(min(ys)), _round(max(xs)), _round(max(ys)))


# --------------------------------------------------------------------- build

def build(root="."):
    """Decode the atlas into the structure the map page renders.

    Returns a dict with a ``states`` map keyed by postal code, a ``nation``
    outline, the territory strip, and the viewBox the coordinates live in.
    """
    topo = load_atlas(root)
    arcs = decode_arcs(topo)

    states = {}
    unknown_fips = []
    for geometry in topo["objects"]["states"].get("geometries", []):
        fips = str(geometry.get("id", "")).zfill(2)
        code = FIPS_TO_STATE.get(fips)
        if not code:
            unknown_fips.append(fips)
            continue
        rings = geometry_rings(geometry, arcs)
        path = rings_to_path(rings)
        if not path:
            continue
        label = label_point(rings)
        states[code] = {
            "name": (geometry.get("properties") or {}).get("name", code),
            "d": path,
            "label": label,
            # How big a label fits at the label point: the half-height, in
            # map units, of the largest box the shape of a two-letter code
            # (1.75 times as wide as its capitals are tall).
            "labelRoom": _round(box_room(label[0], label[1], rings, 1.75)),
            "bounds": bounds(rings),
        }

    if unknown_fips:
        # Loud rather than silent: an unmapped FIPS code means a state would
        # quietly vanish from the map.
        raise AtlasError(
            "Atlas contains FIPS codes with no postal mapping: "
            + ", ".join(sorted(set(unknown_fips)))
        )

    # The atlas also carries a "nation" outline. It costs 50 KB and draws the
    # same edge the outermost state borders already draw, so it is skipped.

    return {
        "viewBox": [0, 0, VIEWBOX_WIDTH, VIEWBOX_HEIGHT],
        "states": states,
        "territories": [
            {
                "code": code,
                "name": TERRITORY_NAMES[code],
                "d": TERRITORY_SHAPES[code],
                "box": [40, 35],
            }
            for code in TERRITORY_ORDER
        ],
    }


def stats(geo):
    return {
        "geo_states": len(geo["states"]),
        "geo_territories": len(geo["territories"]),
        "geo_bytes": sum(len(s["d"]) for s in geo["states"].values()),
    }
