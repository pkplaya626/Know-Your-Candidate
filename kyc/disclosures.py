"""Official financial disclosures, from the Clerk of the House.

The site shows an "Estimated Net Worth" for 144 of 539 sitting members and
nothing for the rest, and the figures it does show carry no source at all. A
number about a named person's private wealth, with no filing behind it, is the
weakest thing on the page.

No free service publishes a computed net worth for members of Congress, and
inventing one from a disclosure is not a small step: the forms report assets in
broad value *bands*, so any single figure derived from them is an estimate
dressed as a fact. **This module therefore does not fill in net worth.** It
attaches the primary document instead, so a reader can see what was actually
filed.

    python build_profile_site.py disclosures          # refresh
    python build_profile_site.py disclosures --check  # report from the cache

The Clerk publishes one ZIP per year containing an XML index of every filing,
which is clean, complete and free. The Senate's equivalent sits behind a
session-based search that has to be agreed to before it returns anything;
scraping it would be fragile and against the spirit of that gate, so senators
have no disclosure link and the README says so.
"""

import io
import json
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "disclosures.json")

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}/{doc}.pdf"

_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 60

# The annual report is the filing that covers a member's whole financial
# position. "O" is the original and "A" an amendment to it; everything else in
# the index is a periodic transaction report, an extension request, a
# withdrawal or a candidate filing, none of which is what a reader following a
# link from "net worth" is looking for.
ANNUAL_TYPES = ("O", "A")


class DisclosureError(RuntimeError):
    pass


def fetch_year(year):
    """Every filing the Clerk indexed for *year*."""
    url = INDEX_URL.format(year=year)
    try:
        request = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            blob = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise DisclosureError(f"Could not download {url}: {exc}") from exc

    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
        name = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
        # The Clerk's XML carries a byte-order mark.
        root = ET.fromstring(archive.read(name).decode("utf-8-sig"))
    except (zipfile.BadZipFile, StopIteration, ET.ParseError, UnicodeDecodeError) as exc:
        raise DisclosureError(f"{url} is not the expected ZIP of XML: {exc}") from exc

    return [
        {
            "last": (row.findtext("Last") or "").strip(),
            "first": (row.findtext("First") or "").strip(),
            "seat": (row.findtext("StateDst") or "").strip().upper(),
            "type": (row.findtext("FilingType") or "").strip(),
            "year": (row.findtext("Year") or "").strip(),
            "filed": (row.findtext("FilingDate") or "").strip(),
            "doc": (row.findtext("DocID") or "").strip(),
        }
        for row in root
    ]


def _filed_key(filing):
    """Sort key putting the most recently filed report last."""
    parts = filing["filed"].split("/")
    if len(parts) == 3:
        month, day, year = parts
        return (year.zfill(4), month.zfill(2), day.zfill(2))
    return ("", "", "")


def seat_code(profile):
    """``"AL04"`` - the Clerk's state+district form, or ``None``."""
    if profile.get("chamber") != "House":
        return None
    district = profile.get("districtNum")
    return f"{profile['state']}{0 if district is None else district:02d}"


def match(profiles, filings):
    """``{bioguide: disclosure}`` for members with an annual report on file.

    Matched on surname *and* seat *and* first initial. Surname and seat alone
    would be enough almost always, which is exactly the sort of "almost" that
    puts one person's finances under another person's name - a district can
    hold a sitting member and a same-surname candidate in the same year.
    """
    index = {}
    for filing in filings:
        if filing["type"] not in ANNUAL_TYPES or not filing["doc"]:
            continue
        key = (filing["last"].lower(), filing["seat"],
               filing["first"][:1].lower())
        index.setdefault(key, []).append(filing)

    found = {}
    for profile in profiles:
        seat = seat_code(profile)
        if not seat or profile.get("isCandidate"):
            continue
        words = profile["name"].split()
        if not words:
            continue
        key = (words[-1].lower(), seat, words[0][:1].lower())
        candidates = index.get(key)
        if not candidates:
            continue
        latest = sorted(candidates, key=_filed_key)[-1]
        found[profile["id"]] = {
            "name": profile["name"],
            "year": latest["year"],
            "filed": latest["filed"],
            "doc": latest["doc"],
            "url": PDF_URL.format(year=latest["year"], doc=latest["doc"]),
        }
    return found


# --------------------------------------------------------------------- cache

def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return {}


def apply_cache(profiles, cache):
    """Attach the disclosure link to each member who has one."""
    applied = 0
    for profile in profiles:
        record = cache.get(profile["id"])
        if not record or not record.get("url"):
            continue
        profile["disclosureUrl"] = record["url"]
        profile["disclosureYear"] = record.get("year")
        profile["disclosureFiled"] = record.get("filed")
        applied += 1
    return applied
