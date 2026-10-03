"""Rebuild ``ca_places.json``: California's cities and towns, for map labels.

The redistricting page labels towns in its close-ups so a reader can find
where they live. A hand-typed list of coordinates is exactly the kind of
plausible, unverifiable data this project avoids, so the places come from
official files instead, joined on codes rather than names:

* the Census Bureau's 2020 Gazetteer, for each place's internal point - a
  point the Bureau guarantees lies inside the place;
* the Census Bureau's Vintage 2024 population estimates, joined on the
  place code, used only to decide which labels win when two would overlap;
* the USGS Geographic Names Information System, joined on the Gazetteer's
  ANSI code (which is the GNIS feature id), for a second, independent point.

An internal point is inside the place, but not always inside the part of it
anyone means: San Francisco's is on the Farallon Islands, 52 km out to sea,
because the city and county includes them. So a place whose internal point
is more than ``OUTLYING`` "radii" (the radius of a circle of its land area)
from the USGS point is labelled at the USGS point instead, and the file
records which places that happened to. Only incorporated places are listed
(the estimates file has no CDPs). Run it from the repository root:

    python tools/fetch_ca_places.py
"""

import csv
import io
import json
import math
import os
import sys
import urllib.request
import zipfile

GAZETTEER_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                 "2020_Gazetteer/2020_Gaz_place_national.zip")
ESTIMATES_URL = ("https://www2.census.gov/programs-surveys/popest/datasets/"
                 "2020-2024/cities/totals/sub-est2024.csv")
GNIS_URL = ("https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/"
            "DomesticNames/DomesticNames_CA_Text.zip")
STATE_FIPS = "06"
STATE_USPS = "CA"
OUT_FILE = "ca_places.json"

# Three radii flags only San Francisco (8.4). Sprawling or elongated cities
# sit well inside it: Los Angeles 1.0, Anaheim 2.5, Brisbane 2.6.
OUTLYING = 3.0


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "know-your-candidate"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _short_name(name):
    """``"Truckee town"`` -> ``"Truckee"``. The legal suffix is not a label."""
    for suffix in (" city", " town"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _km(lat1, lon1, lat2, lon2):
    p = math.radians
    cos = (math.sin(p(lat1)) * math.sin(p(lat2)) +
           math.cos(p(lat1)) * math.cos(p(lat2)) * math.cos(p(lon2 - lon1)))
    return 6371.0088 * math.acos(max(-1.0, min(1.0, cos)))


def _gnis_civil(gnis_zip):
    """``{feature id: (lat, lon)}`` for every civil feature in the file."""
    archive = zipfile.ZipFile(io.BytesIO(gnis_zip))
    name = [n for n in archive.namelist() if n.lower().endswith(".txt")][0]
    text = archive.read(name).decode("utf-8-sig", errors="replace")
    return {
        row["feature_id"].lstrip("0"): (float(row["prim_lat_dec"]), float(row["prim_long_dec"]))
        for row in csv.DictReader(io.StringIO(text), delimiter="|")
        if row["feature_class"] == "Civil"
    }


def build(gazetteer_zip, estimates_csv, gnis_zip):
    archive = zipfile.ZipFile(io.BytesIO(gazetteer_zip))
    lines = archive.read(archive.namelist()[0]).decode("latin-1").splitlines()
    header = [h.strip() for h in lines[0].split("\t")]
    points = {}
    for line in lines[1:]:
        row = dict(zip(header, (f.strip() for f in line.split("\t"))))
        if row.get("USPS") == STATE_USPS:
            points[row["GEOID"][2:]] = row
    civil = _gnis_civil(gnis_zip)

    places, unmatched, moved, unchecked = [], [], [], []
    for row in csv.DictReader(io.StringIO(estimates_csv.decode("latin-1"))):
        if row["STATE"] != STATE_FIPS or row["SUMLEV"] != "162":
            continue
        point = points.get(row["PLACE"])
        if point is None:
            unmatched.append(row["NAME"])
            continue
        name = _short_name(row["NAME"])
        lat, lon = float(point["INTPTLAT"]), float(point["INTPTLONG"])
        usgs = civil.get(point["ANSICODE"].lstrip("0"))
        if usgs is None:
            unchecked.append(name)
        else:
            radius = math.sqrt(int(point["ALAND"]) / 1e6 / math.pi)
            gap = _km(lat, lon, *usgs)
            if gap > OUTLYING * radius:
                moved.append([name, lon, lat, round(gap, 1)])
                lat, lon = usgs
        places.append([name, lon, lat, int(row["POPESTIMATE2024"])])
    if unmatched:
        # Loud: a city that silently drops out of the label set is a city a
        # reader cannot find on the map.
        raise SystemExit("No Gazetteer point for: " + ", ".join(sorted(unmatched)))
    places.sort(key=lambda p: (-p[3], p[0]))
    return {
        "source": ("U.S. Census Bureau: 2020 Gazetteer place internal points and Vintage "
                   "2024 population estimates (SUB-EST2024); USGS GNIS civil feature points"),
        "urls": [GAZETTEER_URL, ESTIMATES_URL, GNIS_URL],
        "fields": ["name", "lon", "lat", "population2024"],
        # Internal points on an outlying piece of the place, replaced by the
        # USGS point: [name, internal lon, internal lat, km apart].
        "moved": sorted(moved),
        "unchecked": sorted(unchecked),
        "places": places,
    }


def dumps(payload):
    """JSON with one place per line, so a refresh diffs place by place."""
    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    head = [f"{compact(key)}:{compact(value)}"
            for key, value in payload.items() if key != "places"]
    rows = [compact(place) for place in payload["places"]]
    return ("{\n" + ",\n".join(head) + ',\n"places":[\n' + ",\n".join(rows) + "\n]}\n")


def main():
    payload = build(_get(GAZETTEER_URL), _get(ESTIMATES_URL), _get(GNIS_URL))
    text = dumps(payload)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, OUT_FILE)
    print(f"wrote {OUT_FILE}: {len(payload['places'])} places; "
          f"{len(payload['moved'])} labelled at the USGS point instead of an outlying "
          f"internal point ({', '.join(m[0] for m in payload['moved']) or 'none'}); "
          f"{len(payload['unchecked'])} with no USGS record to check against")
    return 0


if __name__ == "__main__":
    sys.exit(main())
