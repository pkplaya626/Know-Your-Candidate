"""Every state's House districts, and where a map was redrawn, both maps.

Each state and territory gets a page that draws its congressional districts
with who holds each seat and who is on the November ballot. Where the map for
2026 is not the one members were elected under in 2024, the page draws both:
California's Proposition 50, Texas's 2025 map and the rest of REDRAWN. The
roster seats people where they sit and the filings say where they run (rule
30); these maps are what those numbers refer to, so a reader can see what
"TX-9" meant in 2024 and means now.

Like ``geo.py``, the work happens here, once, at build time: the page gets
ready-to-render ``<path d="...">`` strings and needs no mapping library. The
boundaries arrive as longitude and latitude, so each state is projected here
with an equal-area conic fitted to it - which is also what makes the overlap
figures honest: on an equal-area map, a share of the drawing is a share of
the ground.

Sources, vendored under ``district_maps/`` by ``tools/fetch_district_maps.py``
and never edited by hand:

* ``<st>.json`` - the districts members were elected in (the 119th Congress,
  the Census Bureau's 1:5,000,000 cartographic boundaries), the county lines
  (the same series), and for a redrawn state the new map, from the Wikimedia
  Commons map data pages that cite the official shapefile (CC0).
* ``places.json`` - incorporated places from the Census Gazetteer, ranked by
  population, each placed on its own largest piece of land.

Everything a reader is told about *people* comes from ``profiles.js``; the
emitted files are a pure function of the geometry, and their signatures say so.
"""

import json
import math
import os

from . import geo
from .pages import STATE_NAMES, state_name


class DistrictsError(RuntimeError):
    """Raised when a district map is missing or not the shape we expect."""


MAPS_DIR = "district_maps"
PLACES_FILE = os.path.join(MAPS_DIR, "places.json")
PAGE_DIR = "districts"

EARTH_RADIUS_KM = 6371.0088

# The emitted coordinate space: 1,000 units across, which keeps the
# one-decimal rounding in geo.py below a pixel even in a close-up drawn at
# five times the statewide scale.
WIDTH = 1000
PAD = 10

# Scanline spacing, in emitted units, for measuring areas and overlaps.
SCAN_STEP = 0.5

# Overlaps smaller than this share of both districts are not shipped. Two
# plans simplified separately do not trace a shared county line identically,
# so the slivers between them are drawing artefacts, not territory.
MIN_FLOW = 0.005

# Every district of one plan must be accounted for by the other plan to
# within this share. Anything less means a district is missing or
# mis-numbered, not merely simplified.
MIN_COVERAGE = 0.97

# The page lays a map out at this many pixels across. A district smaller
# than LABEL_PX square pixels at that size is numbered in an inset instead.
DESIGN_PX = 620
LABEL_PX = 380
INSET_LABEL_PX = 30
MAX_INSETS = 4
# Two numbers in an inset are drawn at least this far apart, in page pixels;
# an inset is never narrower than INSET_MIN_PX.
INSET_GAP_PX = 18
INSET_MIN_PX = 240

# California's own projection, EPSG:3310. Every other state gets an Albers
# conic with standard parallels at a sixth and five-sixths of its latitude.
PROJECTIONS = {"CA": (34.0, 40.5, -120.0)}

# The 2024 map, where nothing more specific is on record for a state.
CURRENT = {
    "label": "District map",
    "title": "The map for 2026",
    "used": "the 2024 election, and again in 2026",
    "drawnBy": "",
}

# States whose House map for the 2026 election is not the one used in 2024.
# Every clause here is checked against the enacting body's own record; the
# "before" map is the 119th Congress's, as the Census Bureau publishes it.
REDRAWN = {
    "CA": {
        "commons": "California",
        # The Senate demographics office links it as the "AB 604 District Shapefile".
        "shapefile": {
            "url": "https://selc.senate.ca.gov/media/603",
            "field": "DISTRICT",
            "cite": "the California Senate's AB 604 district shapefile (https://sdmg.senate.ca.gov/committeehome/2025-congressional-districts)",
        },
        "headline": "California's House districts, before and after Proposition 50",
        "intro": (
            "Proposition 50, approved by voters on November 4, 2025, replaced the "
            "congressional map that the California Citizens Redistricting Commission drew "
            "after the 2020 census with one the Legislature passed as AB 604. The new map "
            "is used for the 2026, 2028 and 2030 elections; after the 2030 census the "
            "commission draws the next one. Every district changed shape, and some members "
            "are running in a district with a different number from the one they hold."
        ),
        "before": {
            "title": "2021 commission map",
            "used": "the 2022 and 2024 elections",
            "drawnBy": "the California Citizens Redistricting Commission, after the 2020 census",
        },
        "after": {
            "title": "Proposition 50 map",
            "used": "the 2026, 2028 and 2030 elections",
            "drawnBy": "the Legislature as AB 604, approved by voters as Proposition 50 "
                       "on November 4, 2025",
        },
    },
    # Plan C2333: the plan page at data.capitol.texas.gov reads "ENACTED BY
    # 89TH LEGISLATURE, 2ND C.S., 2025"; used for the March 2026 primaries.
    "TX": {
        "commons": "Texas",
        # The Legislative Council's own file for the enacted plan.
        "shapefile": {
            "url": "https://data.capitol.texas.gov/dataset/748c952b-e926-4f44-8d01-a738884b3ec8/"
                   "resource/5712ebe1-d777-4d4a-b836-0534e17bca01/download/planc2333.zip",
            "field": "District",
            "cite": "the Texas Legislative Council (Plan C2333, https://data.capitol.texas.gov/dataset/planc2333)",
        },
        "headline": "Texas's House districts, before and after the 2025 map",
        "intro": (
            "In 2025 the Legislature replaced the congressional map drawn after the 2020 "
            "census with a new one, Plan C2333 (HB 4, second called session). It is the map "
            "for the 2026 election, and some members are running in a district with a "
            "different number from the one they hold."
        ),
        "after": {"title": "2025 map (Plan C2333)", "used": "the 2026 election",
                  "drawnBy": "the Legislature as HB 4 in its second called session of 2025"},
    },
    # Chapter 2026-229, Laws of Florida: flsenate.gov shows HB 1-D approved by
    # the Governor on May 4, 2026.
    "FL": {
        "commons": "Florida",
        # Commons has no page for districts 2-7, so the state's own file:
        # EDR's "2026 Congressional Districts - Revised May 4, 2026".
        "shapefile": {
            "url": "https://edr.state.fl.us/content/redistricting/2026redistricting/"
                   "EOGPCRP2026.zip",
            "field": "DISTRICT",
            "cite": "the Florida Legislature's Office of Economic and Demographic Research "
                    "(plan EOGPCRP2026, https://edr.state.fl.us/content/redistricting/"
                    "2026redistricting/index.cfm)",
        },
        "headline": "Florida's House districts, before and after the 2026 map",
        "intro": (
            "In May 2026 Florida enacted a new congressional map, HB 1-D of Special Session "
            "D (Chapter 2026-229, Laws of Florida). It is the map for the 2026 election, and "
            "some members are running in a district with a different number from the one "
            "they hold."
        ),
        "after": {"title": "2026 map (HB 1-D)", "used": "the 2026 election",
                  "drawnBy": "the Legislature as HB 1-D in Special Session D, approved by "
                             "the Governor on May 4, 2026"},
    },
    # League of Women Voters of Utah v. Utah State Legislature: on November
    # 10, 2025 the Third District Court enjoined the Legislature's plans and
    # selected a plan for the 2026 elections; a federal panel declined to
    # block it in February 2026.
    "UT": {
        "commons": "Utah",
        # UGRC: the court's "Map 1" with the clarifications it ordered ("Map 1A").
        "shapefile": {
            "url": "https://opendata.gis.utah.gov/api/download/v1/items/"
                   "d3388c1f7d894ab789247f6442855d66/shapefile?layers=0",
            "field": "DISTRICT",
            "cite": "the Utah Geospatial Resource Center and the Lieutenant Governor's Office (Utah US Congress Districts 2026 to 2032, https://gis.utah.gov/products/sgid/political/us-congressional-districts/)",
        },
        "headline": "Utah's House districts, before and after the court-ordered map",
        "intro": (
            "In November 2025 a state court, ruling in League of Women Voters of Utah v. "
            "Utah State Legislature, set aside the Legislature's congressional map and "
            "adopted one submitted by the plaintiffs for the 2026 election. Every member "
            "is running in a district with a different number from the one they hold."
        ),
        "after": {"title": "Court-ordered map", "used": "the 2026 election",
                  "drawnBy": "the Third District Court of Utah, on November 10, 2025"},
    },
    # Session Law 2025-95 (SB 249), ratified October 22, 2025, redefines
    # Districts 1 and 3 only; used for the March 2026 primary.
    "NC": {
        "commons": "North Carolina",
        # ncleg.gov, under "Congressional (To be used for the 2026 Election)".
        "shapefile": {
            "url": "https://webservices.ncleg.gov/ViewBillDocument/2025/7667/0/"
                   "SL%202025-95%20-%20Shapefile",
            "field": "DISTRICT",
            "cite": "the North Carolina General Assembly (S.L. 2025-95 shapefile, https://www.ncleg.gov/Redistricting)",
        },
        "headline": "North Carolina's House districts, before and after the 2025 change",
        "intro": (
            "In October 2025 the General Assembly redrew two districts, the 1st and the "
            "3rd, in Session Law 2025-95 (SB 249). The other twelve are unchanged. The new "
            "lines are used for the 2026 election."
        ),
        "after": {"title": "2025 map (S.L. 2025-95)", "used": "the 2026 election",
                  "drawnBy": "the General Assembly as Session Law 2025-95, ratified "
                             "October 22, 2025"},
    },
    # The Ohio Redistricting Commission adopted the plan unanimously on
    # October 31, 2025; used for the May 2026 primary.
    "OH": {
        "commons": "Ohio",
        "headline": "Ohio's House districts, before and after the 2025 map",
        "intro": (
            "On October 31, 2025 the Ohio Redistricting Commission adopted a new "
            "congressional map, replacing the one used in 2022 and 2024. It is the map for "
            "the 2026 election."
        ),
        "after": {"title": "2025 commission map", "used": "the 2026 election",
                  "drawnBy": "the Ohio Redistricting Commission, on October 31, 2025"},
    },
    # Public Chapter 3 (HB 7003, Second Extraordinary Session of the 114th
    # General Assembly), effective May 7, 2026 per the legislature's page.
    "TN": {
        "commons": "Tennessee",
        # The Comptroller's "U.S. Congressional District Maps" page.
        "shapefile": {
            "url": "https://comptroller.tn.gov/content/dam/cot/pa/documents/district-maps/"
                   "congress-districts/NewCongressional26.zip",
            "field": "DISTRICT",
            "cite": "the Tennessee Comptroller of the Treasury (https://comptroller.tn.gov/maps/u-s--congress-districts.html)",
        },
        "headline": "Tennessee's House districts, before and after the 2026 map",
        "intro": (
            "In May 2026 the General Assembly enacted a new congressional map, HB 7003 of "
            "its second extraordinary session (Public Chapter 3). It is the map for the "
            "2026 election."
        ),
        "after": {"title": "2026 map (Public Chapter 3)", "used": "the 2026 election",
                  "drawnBy": "the General Assembly as HB 7003, in May 2026"},
    },
    # Act No. 2 (SB 121, 2026 Regular Session), signed May 29, 2026, after
    # Louisiana v. Callais struck down the 2024 map.
    "LA": {
        "commons": "Louisiana",
        # Listed under "Enacted Plans From the 2026 Regular Session".
        "shapefile": {
            "url": "https://redist.legis.la.gov/2026_Files/Act2Congress/Shapefile/"
                   "Shapefile%20-%20Act_2_(2026_RS).zip",
            "field": "DISTRICT_I",
            "cite": "the Louisiana Legislature (Act 2, 2026 Regular Session, https://redist.legis.la.gov/)",
        },
        "headline": "Louisiana's House districts, before and after the 2026 map",
        "intro": (
            "In May 2026 the Legislature enacted a new congressional map, Act 2 (SB 121), "
            "after the U.S. Supreme Court struck down the 2024 map in Louisiana v. Callais. "
            "Louisiana's House races are open primaries on November 3; where no one wins a "
            "majority, the top two meet in a runoff on December 12."
        ),
        "after": {"title": "2026 map (Act 2)", "used": "the 2026 election",
                  "drawnBy": "the Legislature as SB 121, signed May 29, 2026"},
    },
    # Allen v. Milligan, No. 25A1314: on June 2, 2026 the U.S. Supreme Court
    # stayed the district court's May 26 order, which put the Legislature's
    # 2023 plan (Act 2023-563) in place of the court-drawn map used in 2024.
    "AL": {
        "commons": "Alabama",
        # Posted on June 3, 2026, the day after the stay.
        "shapefile": {
            "url": "https://www.sos.alabama.gov/sites/default/files/06-03-2026/"
                   "2023_CONGRESSIONAL_PLAN.zip",
            "field": "DISTRICT",
            "cite": "the Alabama Secretary of State (2023 Congressional Plan, https://www.sos.alabama.gov/alabama-votes/state-district-maps)",
        },
        "headline": "Alabama's House districts, before and after the 2026 change",
        "intro": (
            "No new map was drawn for 2026. The 2024 election used districts drawn by a "
            "federal court; on June 2, 2026 the U.S. Supreme Court stayed that court's "
            "latest order, which put the Legislature's 2023 plan into effect for the 2026 "
            "election."
        ),
        "before": {"title": "Court-drawn map", "used": "the 2024 election"},
        "after": {"title": "2023 legislative plan", "used": "the 2026 election",
                  "drawnBy": "the Legislature in 2023 (Act 2023-563)"},
    },
}


def all_codes():
    """Every state, D.C. and territory with a seat in the House."""
    return sorted(STATE_NAMES)


def index():
    """``{code: {page, name, redrawn}}`` for the build metadata: every state
    page and profile dialog links to its state's map."""
    return {code: {"page": page_path(code), "name": state_name(code),
                   "redrawn": code in REDRAWN}
            for code in all_codes()}


def page_path(code):
    return f"{PAGE_DIR}/{code.lower()}.html"


def map_file(code, root="."):
    return os.path.join(root, MAPS_DIR, f"{code.lower()}.json")


# --------------------------------------------------------------- projection

class _Albers:
    """Spherical Albers equal-area conic, fitted to a box later."""

    def __init__(self, parallels, meridian):
        phi0, phi1 = (math.radians(p) for p in parallels)
        self.n = (math.sin(phi0) + math.sin(phi1)) / 2
        self.c = 1 + math.sin(phi0) * (2 * self.n - math.sin(phi0))
        self.r0 = math.sqrt(self.c) / self.n
        self.meridian = meridian

    def raw(self, lon, lat):
        """Unscaled ``(x, y)`` with y pointing north, on the unit sphere."""
        lam = math.radians(_wrap(lon - self.meridian)) * self.n
        r = math.sqrt(self.c - 2 * self.n * math.sin(math.radians(lat))) / self.n
        return (r * math.sin(lam), self.r0 - r * math.cos(lam))


def _wrap(degrees):
    """Longitude difference into [-180, 180): the Aleutians are west of
    Alaska's meridian, not 330 degrees east of it."""
    return (degrees + 180.0) % 360.0 - 180.0


def projection_for(code, points):
    """The state's own projection, from its longitude/latitude points."""
    if code in PROJECTIONS:
        south, north, meridian = PROJECTIONS[code]
        return _Albers((south, north), meridian)
    lats = [p[1] for p in points]
    lo, hi = min(lats), max(lats)
    # The mean of the longitudes as unit vectors, so a state that crosses
    # the antimeridian is centred on itself.
    sx = sum(math.cos(math.radians(p[0])) for p in points)
    sy = sum(math.sin(math.radians(p[0])) for p in points)
    meridian = math.degrees(math.atan2(sy, sx))
    span = max(hi - lo, 1.0)
    return _Albers((lo + span / 6, hi - span / 6), meridian)


class _Fit:
    """Scale and flip raw coordinates into the emitted ``WIDTH``-wide box."""

    def __init__(self, raw_points):
        xs = [p[0] for p in raw_points]
        ys = [p[1] for p in raw_points]
        self.min_x, self.max_y = min(xs), max(ys)
        self.k = (WIDTH - 2 * PAD) / (max(xs) - self.min_x)
        self.height = int(math.ceil(self.k * (self.max_y - min(ys)) + 2 * PAD))

    def __call__(self, point):
        return (PAD + self.k * (point[0] - self.min_x),
                PAD + self.k * (self.max_y - point[1]))


# ------------------------------------------------------------------ loading

def _read_json(path, what):
    if not os.path.exists(path):
        raise DistrictsError(f"{what} not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError as exc:
        raise DistrictsError(f"{path} is not valid JSON: {exc}") from exc


def _decode_point(topo, coordinates):
    """A Point's position. Quantised topologies store points as integers on
    the same grid as the arcs, but absolute rather than delta-encoded."""
    transform = topo.get("transform")
    if not transform:
        return (float(coordinates[0]), float(coordinates[1]))
    (sx, sy), (tx, ty) = transform["scale"], transform["translate"]
    return (coordinates[0] * sx + tx, coordinates[1] * sy + ty)


def _numbered(topo, name, kind, expected=None):
    """``{district number: geometry}`` for one object, numbered 1..N, or 0
    for a single at-large seat, and matching *expected* when given."""
    obj = (topo.get("objects") or {}).get(name)
    if not obj:
        raise DistrictsError(f"map has no '{name}' object")
    found = {}
    for geometry in obj.get("geometries", []):
        number = (geometry.get("properties") or {}).get("d")
        if not isinstance(number, int) or isinstance(number, bool):
            raise DistrictsError(f"'{name}' has a {kind} with no district number")
        if number in found:
            raise DistrictsError(f"'{name}' numbers district {number} twice")
        found[number] = geometry
    if expected is None:
        expected = {0} if set(found) == {0} else set(range(1, len(found) + 1))
    if set(found) != set(expected):
        missing = sorted(set(expected) - set(found))
        extra = sorted(set(found) - set(expected))
        raise DistrictsError(
            f"'{name}' should number districts {sorted(expected)[0]}-{sorted(expected)[-1]}"
            + (f"; missing {missing}" if missing else "")
            + (f"; unexpected {extra}" if extra else ""))
    return found


# ----------------------------------------------------------------- geometry

def _contains(rings, x, y):
    """Even-odd point-in-polygon over every ring, so holes count as outside."""
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, y0 = ring[i]
            x1, y1 = ring[(i + 1) % n]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


def _spans(rings, y):
    """The intervals of the horizontal line at *y* that lie inside *rings*."""
    xs = []
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x0, y0 = ring[i]
            x1, y1 = ring[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def interior_point(rings):
    """A point well inside *rings*, for a label.

    A centroid can fall outside a crescent-shaped county; the middle of the
    widest horizontal span through the shape cannot.
    """
    box = geo.bounds(rings)
    if box is None:
        return None
    best = None
    for step in range(1, 20):
        y = box[1] + (box[3] - box[1]) * step / 20
        for x0, x1 in _spans(rings, y):
            if best is None or x1 - x0 > best[0]:
                best = (x1 - x0, (x0 + x1) / 2, y)
    if best is None:
        return None
    return (geo._round(best[1]), geo._round(best[2]))


def lines_to_path(lines):
    """Open polylines as one SVG path, encoded as ``geo.rings_to_path`` is."""
    parts = []
    for line in lines:
        drawn = []
        for x, y in line:
            point = (geo._round(x), geo._round(y))
            if not drawn or drawn[-1] != point:
                drawn.append(point)
        if len(drawn) < 2:
            continue
        px, py = drawn[0]
        body = []
        for x, y in drawn[1:]:
            dx, dy = geo._round(x - px), geo._round(y - py)
            body.append(f"{geo._num(dx)}{'' if dy < 0 else ','}{geo._num(dy)}")
            px, py = x, y
        parts.append(f"M{geo._num(drawn[0][0])},{geo._num(drawn[0][1])}l" + " ".join(body))
    return "".join(parts)


def measure(plans, height, step=SCAN_STEP):
    """Area of every district, and with two plans every overlap between them.

    *plans* is one or two ``{district: rings}`` maps in emitted coordinates.
    Each horizontal scanline is cut where any district boundary crosses it,
    and every piece is credited to the districts that contain it - the
    even-odd rule per district, so holes and islands come out right. Returns
    ``(areas, overlaps)``: ``areas[p][d]`` and ``overlaps[(first, second)]``,
    in square emitted units.
    """
    rows = int(math.ceil(height / step))
    crossings = [[] for _ in range(rows)]
    for p, districts in enumerate(plans):
        for number, rings in districts.items():
            for ring in rings:
                n = len(ring)
                for i in range(n):
                    x0, y0 = ring[i]
                    x1, y1 = ring[(i + 1) % n]
                    if y0 == y1:
                        continue
                    lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
                    # Rows sit at (r + 0.5) * step; an edge owns the rows in
                    # [lo, hi), so a shared vertex is never counted twice.
                    first = max(0, int(math.ceil(lo / step - 0.5)))
                    last = min(rows, int(math.ceil(hi / step - 0.5)))
                    slope = (x1 - x0) / (y1 - y0)
                    for r in range(first, last):
                        crossings[r].append((x0 + ((r + 0.5) * step - y0) * slope, p, number))

    areas = [dict.fromkeys(districts, 0.0) for districts in plans]
    overlaps = {}
    for row in crossings:
        if not row:
            continue
        row.sort()
        inside = [set() for _ in plans]
        last_x = row[0][0]
        for x, p, number in row:
            length = x - last_x
            if length > 0:
                for plan_areas, members in zip(areas, inside):
                    for a in members:
                        plan_areas[a] += length
                if len(plans) == 2:
                    for a in inside[0]:
                        for b in inside[1]:
                            overlaps[(a, b)] = overlaps.get((a, b), 0.0) + length
            inside[p] ^= {number}
            last_x = x
    for plan_areas in areas:
        for number in plan_areas:
            plan_areas[number] *= step
    return areas, {key: value * step for key, value in overlaps.items()}


def land_areas(areas, overlaps):
    """Each new district's area on the old map's land.

    The Census map stops at the shore; the new maps' districts run out over
    water, and the page clips them to the land. So a new district's size -
    for its label, and as the whole its shares are shares of - is the part
    of it the old map also covers.
    """
    land = dict.fromkeys(areas[1], 0.0)
    for (_, new), area in overlaps.items():
        land[new] += area
    return land


def flows(areas, overlaps):
    """``[[old, new, share of new, share of old], ...]`` for real overlaps.

    A share of a new district is a share of its land. Raises when an old
    district is not covered by the new plan, or a new district has no land:
    two maps of the same state must account for each other's every district.
    """
    land = land_areas(areas, overlaps)
    out = []
    covered = dict.fromkeys(areas[0], 0.0)
    for (old, new), area in sorted(overlaps.items()):
        of_new = area / land[new] if land[new] else 0.0
        of_old = area / areas[0][old] if areas[0][old] else 0.0
        covered[old] += of_old
        if max(of_new, of_old) >= MIN_FLOW:
            out.append([old, new, round(of_new, 3), round(of_old, 3)])
    short = [f"old {n} ({share:.0%})" for n, share in sorted(covered.items())
             if share < MIN_COVERAGE]
    short += [f"new {n} (no land)" for n, area in sorted(land.items()) if area <= 0]
    if short:
        raise DistrictsError("districts the other plan does not cover: " + ", ".join(short))
    return out


def insets(plan, places, viewbox, also=()):
    """Boxes around districts too small to number on the statewide map.

    The small districts are grouped by how close their numbers would sit,
    each group gets a box, and boxes that overlap merge - at most
    MAX_INSETS. Each is named for the biggest towns inside it. Every small
    district's label point is inside some box, which is what lets the page
    number every district somewhere.
    """
    px = DESIGN_PX / viewbox[2]
    small = [n for n, d in plan.items() if d["area"] * px * px < LABEL_PX]
    if not small:
        return []
    parent = {n: n for n in small}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    reach = 70 / px
    for i, a in enumerate(small):
        for b in small[i + 1:]:
            (ax, ay), (bx, by) = plan[a]["at"], plan[b]["at"]
            if math.hypot(ax - bx, ay - by) < reach:
                parent[find(a)] = find(b)
    groups = {}
    for n in small:
        groups.setdefault(find(n), []).append(n)
    boxes = sorted(_group_box(plan, members) for members in groups.values())
    while len(boxes) > 1:
        pair = next(((i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes))
                     if _overlap(boxes[i], boxes[j])), None)
        if pair is None and len(boxes) > MAX_INSETS:
            pair = _closest(boxes)
        if pair is None:
            break
        i, j = pair
        boxes[i] = _union(boxes[i], boxes[j])
        del boxes[j]
        boxes.sort()
    out = []
    for box in sorted(boxes, key=lambda b: (b[0], b[1])):
        x0, y0, x1, y1 = box
        inside = [p for p in places if x0 <= p[1] <= x1 and y0 <= p[2] <= y1]
        names = [p[0] for p in inside[:2] if p[3] >= 0.4 * inside[0][3]] if inside else []
        out.append({"title": " & ".join(names) if names else "Close-up",
                    "box": [geo._round(x0), geo._round(y0),
                            geo._round(x1 - x0), geo._round(y1 - y0)],
                    "width": max(inset_width(p, box) for p in (plan,) + tuple(also))})
    return out


def inset_width(plan, box):
    """How wide, in page pixels, to draw an inset so the closest two numbers
    in it sit INSET_GAP_PX apart - a fixed size squeezed Los Angeles until
    its numbers collided and dropped - within the card's width."""
    x0, y0, x1, y1 = box
    points = [d["at"] for d in plan.values()
              if x0 <= d["at"][0] <= x1 and y0 <= d["at"][1] <= y1]
    closest = min((math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1:]),
                  default=None)
    width = INSET_MIN_PX if not closest else INSET_GAP_PX / closest * (x1 - x0)
    return int(round(min(DESIGN_PX, max(INSET_MIN_PX, width))))


def _group_box(plan, members):
    xs, ys = [], []
    for n in members:
        b = plan[n]["box"]
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0, y1 - y0
    pad = 0.08 * max(w, h) + 4
    # A box no squarer than 2:1 either way, so an inset is never a sliver.
    if w < h / 2:
        x0, x1 = (x0 + x1) / 2 - h / 4, (x0 + x1) / 2 + h / 4
    if h < w / 2:
        y0, y1 = (y0 + y1) / 2 - w / 4, (y0 + y1) / 2 + w / 4
    return [x0 - pad, y0 - pad, x1 + pad, y1 + pad]


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _closest(boxes):
    best = None
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            gap = math.hypot(max(0, max(a[0], b[0]) - min(a[2], b[2])),
                             max(0, max(a[1], b[1]) - min(a[3], b[3])))
            if best is None or gap < best[0]:
                best = (gap, i, j)
    return best[1], best[2]


# --------------------------------------------------------------------- build

def _plan_text(code, key):
    """Title, years used and who drew it, for one plan of one state."""
    spec = REDRAWN.get(code)
    if spec is None:
        return dict(CURRENT)
    if key == "current":
        return dict({"label": "Before", "title": "2024 map", "used": "the 2024 election",
                     "drawnBy": ""}, **spec.get("before", {}))
    return dict({"label": "After", "title": "2026 map", "used": "the 2026 election",
                 "drawnBy": ""}, **spec.get("after", {}))


def build_state(code, root=".", places=None):
    """Project one state's plans into the structure its page renders."""
    topo = _read_json(map_file(code, root), "District map")
    if topo.get("type") != "Topology":
        raise DistrictsError(f"{map_file(code, root)} is not a TopoJSON Topology")
    keys = ["current"] + (["next"] if code in REDRAWN else [])
    if code not in REDRAWN and "next" in topo.get("objects", {}):
        raise DistrictsError(f"{code}'s map file has a new plan but REDRAWN has no entry")

    arcs = geo.decode_arcs(topo)
    shapes, points = [], []
    for key in keys:
        expected = set(shapes[0]) if shapes else None
        shapes.append(_numbered(topo, key, "shape", expected))
        points.append(_numbered(topo, f"{key}_pts", "label point", expected or set(shapes[0])))

    lonlat = [p for plan in shapes for g in plan.values()
              for ring in geo.geometry_rings(g, arcs) for p in ring]
    albers = projection_for(code, lonlat)
    raw_arcs = [[albers.raw(lon, lat) for lon, lat in arc] for arc in arcs]
    raw_rings = [{n: geo.geometry_rings(g, raw_arcs) for n, g in sorted(plan.items())}
                 for plan in shapes]
    fit = _Fit([p for plan in raw_rings for rings in plan.values()
                for ring in rings for p in ring])
    rings = [{n: [[fit(p) for p in ring] for ring in plan_rings]
              for n, plan_rings in plan.items()} for plan in raw_rings]

    areas, overlaps = measure(rings, fit.height)
    if len(keys) == 2:
        # The new map is drawn clipped to the old map's land; size it so.
        areas[1] = land_areas(areas, overlaps)
    viewbox = [0, 0, WIDTH, fit.height]
    land = [r for district_rings in rings[0].values() for r in district_rings]
    out_plans = []
    for key, plan_rings, plan_points, plan_areas in zip(keys, rings, points, areas):
        districts = {}
        for number, district_rings in plan_rings.items():
            path = geo.rings_to_path(district_rings)
            if not path:
                raise DistrictsError(f"{code} {key} plan has no shape for {number}")
            at = fit(albers.raw(*_decode_point(topo, plan_points[number]["coordinates"])))
            if not _contains(district_rings, *at):
                # A number drawn over the wrong shape is a silent error.
                raise DistrictsError(
                    f"{code} {key} plan: district {number}'s label point is outside it")
            if key == "next" and not _contains(land, *at):
                # ... and so is one drawn over water the page clips away.
                raise DistrictsError(
                    f"{code} {key} plan: district {number}'s label point is off the land")
            districts[str(number)] = {
                "d": path,
                "at": [geo._round(at[0]), geo._round(at[1])],
                "box": list(geo.bounds(district_rings)),
                "area": int(round(plan_areas[number])),
            }
        out_plans.append(dict(_plan_text(code, key), key=key, districts=districts))

    town_list = _places((places or {}).get(code, []), albers, fit)
    return {
        "name": state_name(code),
        "seats": len(rings[0]),
        "atLarge": set(rings[0]) == {0},
        "page": page_path(code),
        "viewBox": viewbox,
        # Kilometres per map unit, so every "area" here has a stated unit.
        "unitKm": round(EARTH_RADIUS_KM / fit.k, 6),
        "plans": out_plans,
        "flows": flows(areas, overlaps) if len(keys) == 2 else [],
        "counties": _counties(topo, raw_arcs, fit),
        "places": town_list,
        # Sized for every map drawn in them: the old map's numbers too.
        "insets": insets(out_plans[-1]["districts"], town_list, viewbox,
                         [p["districts"] for p in out_plans[:-1]]),
        "sources": _sources(code, topo),
    }


def _sources(code, topo):
    lines = ["District boundaries: U.S. Census Bureau, 119th Congress cartographic "
             "boundaries (1:5,000,000)."]
    if code in REDRAWN:
        source = (topo.get("sources") or {}).get("next") or {}
        if source.get("via") == "official":
            lines.append("The 2026 map: " + _plain(source.get("cite", "")) +
                         " Simplified for display, keeping shared boundaries shared.")
        else:
            lines.append("The 2026 map: Wikimedia Commons map data (CC0), converted from "
                         + _plain(source.get("cite", "")) +
                         " Simplified for display, keeping shared boundaries shared.")
    lines.append("County lines: U.S. Census Bureau. Town locations: U.S. Census Bureau "
                 "2020 Gazetteer, checked against its 2024 place boundaries; populations, "
                 "used only to choose which towns to label: Census Vintage 2024 estimates.")
    if code in REDRAWN:
        lines.append("Shares of area are measured on an equal-area projection of the "
                     "simplified boundaries. They describe land, not people.")
    return lines


def _plain(wikitext):
    """``"Shapefile from [https://x the Texas Legislative Council], ..."`` ->
    ``"the Texas Legislative Council (https://x)"``: the cited body in words,
    its address in brackets, and nothing that renders as markup."""
    import re

    text = re.sub(r"\[(https?://\S+)\s+([^\]]+)\]", r"\2 (\1)", wikitext)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = text.replace("Shapefile from ", "").replace("\n", " ").strip()
    return text.rstrip(".") + "."


def _counties(topo, raw_arcs, fit):
    """County lines - inner borders and the state's edge - and name points."""
    obj = (topo.get("objects") or {}).get("counties")
    if not obj:
        raise DistrictsError("map has no 'counties' object")
    users = {}
    names = []
    for index_, geometry in enumerate(obj.get("geometries", [])):
        for arc in _arc_indices(geometry.get("arcs", [])):
            users.setdefault(arc if arc >= 0 else ~arc, set()).add(index_)
        county = (geometry.get("properties") or {}).get("name")
        rings = [[fit(p) for p in ring] for ring in geo.geometry_rings(geometry, raw_arcs)]
        at = interior_point(rings) if county else None
        if at:
            # The area decides which names win when two would collide.
            names.append([county, at[0], at[1], int(round(_rough_area(rings)))])
    inner = [[fit(p) for p in raw_arcs[a]] for a, who in sorted(users.items()) if len(who) > 1]
    edge = [[fit(p) for p in raw_arcs[a]] for a, who in sorted(users.items()) if len(who) == 1]
    names.sort(key=lambda n: (-n[3], n[0]))
    return {"mesh": lines_to_path(inner), "outline": lines_to_path(edge), "names": names}


def _rough_area(rings, step=2.0):
    """Area by coarse scanlines - enough to rank labels, nothing more."""
    box = geo.bounds(rings)
    if box is None:
        return 0.0
    total, y = 0.0, box[1] + step / 2
    while y < box[3]:
        total += sum(x1 - x0 for x0, x1 in _spans(rings, y)) * step
        y += step
    return total


def _arc_indices(nested):
    for item in nested:
        if isinstance(item, list):
            yield from _arc_indices(item)
        else:
            yield item


def _places(rows, albers, fit):
    out = []
    for name, lon, lat, population in rows:
        x, y = fit(albers.raw(lon, lat))
        if 0 <= x <= WIDTH and 0 <= y <= fit.height:
            out.append([name, geo._round(x), geo._round(y), population])
    out.sort(key=lambda p: (-p[3], p[0]))
    return out


def load_places(root="."):
    return _read_json(os.path.join(root, PLACES_FILE), "Place list").get("places", {})


def build(root=".", codes=None):
    """Every state's maps, keyed by postal code."""
    places = load_places(root)
    return {code: build_state(code, root, places) for code in (codes or all_codes())}


def stats(maps):
    return {
        "district_maps": len(maps),
        "district_maps_redrawn": sum(1 for s in maps.values() if len(s["plans"]) == 2),
        "district_bytes": sum(
            len(d["d"]) for state in maps.values()
            for plan in state["plans"] for d in plan["districts"].values()),
    }
