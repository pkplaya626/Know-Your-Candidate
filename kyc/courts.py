"""Each state's court of last resort and who sits on it, from the court itself.

``python build_profile_site.py courts`` reads each court's own roster page
and writes ``data/courts.json``: the justices (judges, on New York's Court of
Appeals and the two courts of criminal appeals), who is chief, and where it
was read. No national source lists sitting state justices - the Conference
of Chief Justices publishes only its board, and the National Center for
State Courts has no directory - so every roster is the court's own, read
with the recipe in ``COURTS``.

A recipe is data, not code: the page, an optional slice of it, a pattern
whose ``name`` group is one member (and whose ``title`` group, when there is
one, says whether they are chief), or for the few courts whose page draws
itself with JavaScript, the JSON the page itself loads. What comes back is
checked against the court's seats (``government_maps.HIGH_COURTS``): fewer
names than seats is "nobody listed" for the rest, never "vacant" unless the
court says so (rule 19), and more is an error, not a court.

Where a court's site cannot be read by a script - a bot wall, a page with no
content until JavaScript runs - the court is listed without its members and
the page says why. Nothing comes from Wikipedia or Ballotpedia.
"""

import datetime
import html
import json
import os
import re
import time
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "courts.json")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")

CHIEF = r"\b(?:chief justice|chief judge|presiding judge)\b"
# Titles and honorifics before a name, and ordinals or seat labels after it.
_LEAD = re.compile(r"^(?:(?:the\s+)?hon(?:ou?rable|\.)?|(?:vice[- ]|associate\s+|deputy\s+)?chief\s+"
                   r"justice|(?:vice\s+)?presiding\s+(?:justice|judge)|(?:associate\s+|senior\s+)?"
                   r"justice|chief\s+judge|judge)\s+", re.I)
_TRAIL = re.compile(r"\s*(?:,\s*(?:chief justice|position\s+\d+|associate justice)|\(\d+\)|"
                    r"[-–—]\s*(?:vice\s+)?presiding judge)\s*$", re.I)

# Names a court prints in capitals, in the case the person's own biography
# page uses. Title-casing "MCMILLIAN" or "LAGRUA" gets them wrong.
CASED = {
    "CARLA WONG MCMILLIAN": "Carla Wong McMillian",
    "SHAWN ELLEN LAGRUA": "Shawn Ellen LaGrua",
    "SHERYL GORDON MCCLOUD": "Sheryl Gordon McCloud",
}

# The recipes. Each was checked against the court's page on 2026-10-05; the
# note says what the page does that the recipe has to allow for.
COURTS = {
    "AK": {
        "url": "https://courts.alaska.gov/judges/index.htm",
        # The page lists every court; the first table is the Supreme Court's.
        "section": [r"Alaska Supreme Court Justices", r"</table>"],
        # A row's first cell is the name, then "<br>Chief Justice" for the
        # chief only. Oravec's cell is bare text beside a commented-out link
        # (comments are stripped first).
        "item": r"<tr>\s*<td[^>]*>(?P<name>(?:(?!<br|</td>).)+)(?:<br>\s*(?P<title>[^<]*))?</td>",
    },
    "TX": {
        "url": "https://www.txcourts.gov/supreme/about-the-court/justices/",
        "section": [r'class="fluid-container bioSummaries"', r"</main>|<footer"],
        "item": r"<h2><a[^>]*>(?P<title>(?:Chief\s+)?Justice)\s+(?P<name>[^<]+)</a></h2>",
    },
    "WI": {
        "url": "https://www.wicourts.gov/courts/supreme/justices/index.htm",
        "section": [r'class="team"', r"Former justices|</main>"],
        "item": r'<p class="team-title-heading"><a[^>]*>(?P<title>(?:Chief )?Justice)<br\s*/?>'
                r"\s*(?P<name>[^<]+)</a>",
    },
}


class CourtsError(RuntimeError):
    """A roster could not be read, or does not fit its court."""


def _get(url, headers=None, timeout=60):
    request = urllib.request.Request(url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise CourtsError(f"could not fetch {url}: {exc}") from exc


def _text(fragment):
    no_comments = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", no_comments)).replace(" ", " ").split())


def clean_name(raw):
    """A member's name as a reader should see it: no title, honorific, seat
    or ordinal; one space; and capitals put into ordinary case."""
    name = _text(raw)
    for _ in range(3):
        name = _LEAD.sub("", name).strip()
        name = _TRAIL.sub("", name).strip()
    name = name.strip(" ,")
    if "," in name and re.fullmatch(r"[^,]+,\s*[^,]+", name) and not re.search(
            r",\s*(?:jr|sr|ii|iii|iv)\.?$", name, re.I):
        last, first = (p.strip() for p in name.split(",", 1))
        name = f"{first} {last}"                 # "Rabner, Stuart" -> "Stuart Rabner"
    if name.isupper() and len(name) > 3:
        from .localgov import display_name
        name = CASED.get(name, display_name(name))
    return name


def _json_path(data, path):
    for key in path.split("."):
        if isinstance(data, list):
            data = data[int(key)]
        else:
            data = data.get(key, {})
    return data


def extract(page, recipe):
    """``[(name, chief)]`` from a court's page by its recipe."""
    if recipe.get("format") == "json":
        data = json.loads(page)
        if recipe.get("script"):
            match = re.search(recipe["script"], page, re.S)
            data = json.loads(match.group(1)) if match else {}
        items = _json_path(data, recipe["items"])
        out = []
        for item in items or []:
            if recipe.get("keep") and not re.search(recipe["keep"], json.dumps(item)):
                continue
            title = _text(str(_json_path(item, recipe["title"]))) if recipe.get("title") else ""
            name = _text(str(_json_path(item, recipe["name"])))
            out.append((clean_name(name), bool(re.search(CHIEF, f"{title} {name}", re.I))))
        return out
    if recipe.get("script"):
        match = re.search(recipe["script"], page, re.S)
        if not match:
            raise CourtsError("the page no longer carries the data its recipe reads")
        return extract(match.group(1), dict(recipe, format="json", script=None))
    if recipe.get("section"):
        start, end = recipe["section"]
        found = re.search(start, page)
        if not found:
            raise CourtsError("the page no longer has the section its recipe reads")
        rest = page[found.end():]
        stop = re.search(end, rest)
        page = rest[:stop.start()] if stop else rest
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    out, seen = [], set()
    for match in re.finditer(recipe["item"], page, re.S | re.I):
        groups = {k: v for k, v in match.groupdict().items() if v}
        raw = groups.get("name") or groups.get("name2") or ""
        title = groups.get("title") or groups.get("title2") or ""
        name = clean_name(raw)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        chief = bool(re.search(CHIEF, f"{title} {_text(raw)}", re.I))
        out.append((name, chief))
    return out


def read_court(code, recipe, seats):
    """``{"members": [...], "chief": name, "listed", "seats", "url"}``, or
    raises when the page does not fit the court: no names, more names than
    seats, or more than one chief."""
    page = _get(recipe["url"], recipe.get("headers"))
    members = extract(page, recipe)
    if not members:
        raise CourtsError(f"{code}: no members read from {recipe['url']}")
    if len(members) > seats:
        raise CourtsError(f"{code}: {len(members)} members read for {seats} seats")
    chiefs = [n for n, chief in members if chief]
    if len(chiefs) > 1:
        raise CourtsError(f"{code}: more than one chief read: {', '.join(chiefs)}")
    return {"members": [n for n, _ in members], "chief": chiefs[0] if chiefs else "",
            "listed": len(members), "seats": seats, "url": recipe.get("link", recipe["url"])}


def fetch(codes=None, pause=1.0):
    """``(courts, problems)`` for every court with a recipe."""
    from .government_maps import HIGH_COURTS
    courts, problems = {}, []
    for code in sorted(codes or COURTS):
        recipe = COURTS[code]
        seats = recipe.get("seats", HIGH_COURTS.get(code[:2], ("", 0))[1])
        try:
            courts[code] = read_court(code, recipe, seats)
        except CourtsError as exc:
            problems.append(str(exc))
        time.sleep(pause)
    return courts, problems


def save_cache(courts, root="."):
    payload = {"fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "courts": {c: courts[c] for c in sorted(courts)}}
    path = os.path.join(root, CACHE_PATH)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":                       # python -m kyc.courts TX WI ...
    import sys
    found, issues = fetch(sys.argv[1:] or None, pause=0.5)
    for code, court in found.items():
        print(code, f"{court['listed']}/{court['seats']}", "chief:", court["chief"] or "-",
              "|", "; ".join(court["members"]))
    for issue in issues:
        print("PROBLEM", issue)
