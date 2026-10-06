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

# The chief, but not an associate, vice or deputy chief, nor a vice
# presiding judge: Arizona has a Vice Chief Justice, Utah and Washington an
# Associate Chief Justice, Kentucky a Deputy Chief Justice.
CHIEF = (r"(?<!vice )(?<!vice-)(?<!associate )(?<!deputy )\bchief (?:justice|judge)\b|"
         r"(?<!vice )(?<!vice-)\bpresiding judge\b")
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
    "AZ": {
        "url": "https://www.azcourts.gov/meetthejustices",
        "item": r"<p><strong><span[^>]*>(?P<name>(?P<title>(?:Vice\s+)?(?:Chief\s+)?Justice)\s+[^<]+)</span>",
    },
    "AR": {
        "url": "https://www.arcourts.gov/courts/supreme-court/justices",
        # "Associate Justice Cody Hiland, Position 3"; the position is read from
        # the text, never the link (Hiland's link says position-2).
        "item": r'views-field-title-1"><a [^>]*>(?P<name>(?P<title>[^<]*?Justice)[^<]*)</a>',
    },
    "CA": {
        "url": "https://supreme.courts.ca.gov/about-court/justices-court",
        # The chief is named only in the side navigation; the associate
        # justices are cards, one of which is a "Vacant Seat" card.
        "item": r'href="/about-court/justices-court/chief-justice-[^"]*">(?P<name>(?P<title>Chief Justice)'
                r'[^<]*)</a>|<div class="usa-card__brow-color">\s*<div>(?P<name2>(?!Vacant)[^<]+)</div>',
    },
    "CO": {
        "url": "https://www.coloradojudicial.gov/supreme-court/supreme-court-judges-and-staff",
        # One contact card per person; justices only (the Clerk is a card too),
        # and never the site-alert banner that reuses the title class.
        "item": r'node--type-contact(?:(?!node--type-contact).)*?field--name-title[^>]*>(?P<name>[^<]+)</span>'
                r'(?:(?!node--type-contact).)*?<div class="field__item">(?P<title>[^<]*Justice[^<]*)</div>',
    },
    "DE": {
        "url": "https://courts.delaware.gov/supreme/justices.aspx",
        "item": r"<h3>(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</h3>",
    },
    "HI": {
        "url": "https://www.courts.state.hi.us/courts/supreme/justices/justices",
        "item": r'<td[^>]*><a href="[^"]*">(?P<name>[^<]+)</a></td>\s*<td[^>]*>(?P<title>[^<]*Justice[^<]*)</td>',
    },
    "FL": {
        "url": "https://supremecourt.flcourts.gov/Justices",
        # A Next.js page: the names are in its own embedded JSON.
        "script": r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        "items": "props.pageProps.extraData.subnavigation.items",
        "keep": r"/justices/",
        "name": "name",
        "title": "name",
    },
    "GA": {
        "url": "https://www.gasupreme.us/court-information/biographies/",
        # Names in capitals: "NELS S.D. PETERSON, Chief Justice".
        "section": [r"<h1>Justice Biographies</h1>", r"</div>"],
        "item": r'<a href="[^"]*/biographies/justice-[^"]*">(?P<name>[^<]+)</a>(?P<title>,\s*[^<]*)?',
    },
    "ID": {
        "url": "https://isc.idaho.gov/about-the-courts/sc-justices",
        "item": r'<h2 class="text-h3"[^>]*>(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</h2>',
    },
    "IL": {
        "url": "https://www.illinoiscourts.gov/courts/supreme-court/meet-the-justices/",
        # The chief's heading ends ", Chief Justice".
        "item": r'<h2 class="accordion-title[^"]*">\s*(?P<name>[^<]+?)\s*</h2>',
    },
    "IN": {
        "url": "https://www.in.gov/courts/supreme/justices/",
        "section": [r"Current Justices", r"Former Justices|</main>"],
        "item": r"<h6>\s*<a[^>]*>\s*(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+?)\s*</a>\s*</h6>",
    },
    "KS": {
        "url": "https://www.kscourts.gov/About-the-Courts/Supreme-Court/Supreme-Court-Justices",
        # The page's own class name is misspelled "desination".
        "item": r'<strong class="name">\s*(?P<name>[^<]+?)\s*</strong>.*?<strong class="desination">\s*'
                r"(?P<title>[^<]+?)\s*</strong>",
    },
    "KY": {
        "url": "https://www.kycourts.gov/Courts/Supreme-Court/Pages/default.aspx",
        "item": r'<h3>\s*(?P<name>[^<]+?)\s*</h3>\s*<h4>\s*(?P<title>[^<]*?)<span class="court-name">Supreme Court</span>',
    },
    "ME": {
        "url": "https://www.courts.maine.gov/courts/sjc/justices.html",
        "item": r"<h3>\s*<strong>(?P<name>Hon\.[^<]+)</strong>\s*<br>\s*(?:<strong>)?\s*(?P<title>[^<]+?)\s*"
                r"(?:</strong>)?\s*</h3>",
    },
    "MD": {
        "url": "https://www.mdcourts.gov/scm/justices",
        "item": r'views-field-title[^"]*"><a [^>]*>(?P<name>Honorable[^<]+)</a>',
    },
    "MI": {
        "url": "https://www.courts.michigan.gov/courts/supreme-court/justices/",
        # The page draws itself; asked for JSON, it returns its own content.
        "headers": {"Accept": "application/json"},
        "format": "json",
        "items": "pageContent.0.linkCardItems",
        "name": "title",
        "title": "title",
    },
    "MN": {
        "url": "https://dxp-us-search.funnelback.squiz.cloud/s/search.json?collection=mjb~sp-search&profile="
               "judicial-officers&f.Appellate%7Cappellate=supreme+court&num_ranks=600&query=!padrenull",
        "link": "https://mncourts.gov/supremecourt/supreme-court-justices",
        # The court's page fills its list from this search index.
        "format": "json",
        "items": "response.resultPacket.results",
        "name": "title",
        "title": "listMetadata.rank",
    },
    "MS": {
        "url": "https://courts.ms.gov/appellatecourts/sc/scjustices.php",
        # The <strong> text; alt and aria-label carry nicknames.
        "item": r"<span><strong>(?P<name>(?P<title>(?:Chief|Presiding|Associate)\s+Justice)\s+[^<]+)</strong>",
    },
    "MT": {
        "url": "https://courts.mt.gov/Courts/Supreme/About/bios/",
        # Names appear only as the first words of each biography: "Justice
        # Beth Baker was raised ...". Take the capitalised words after the title.
        # (Case-sensitive inside: the extractor otherwise matches "is" and
        # "was" as capitalised words.)
        "item": r"<img alt=\"[^\"]*\"[^>]*/>\s*</a>\s*(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+"
                r"(?-i:[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*){1,3}))",
    },
    "NE": {
        "url": "https://nebraskajudicial.gov/courts/supreme-court/supreme-court-justices",
        # The chief's name ends ", Chief Justice".
        "item": r'views-field-title"><span class="field-content"><a [^>]*>(?P<name>Hon\.[^<]+)</a>',
    },
    "NJ": {
        "url": "https://www.njcourts.gov/public/museum/meet-the-justices",
        # "Rabner, Stuart"; stop before the former justices.
        "section": [r"Current Justices", r"Former Justices"],
        "item": r"<article about=\"[^\"]*\"(?:(?!</article>).)*?<small>(?P<title>[^<]*)</small>"
                r"(?:(?!</article>).)*?class=\"text-underline-hover\"[^>]*>(?P<name>[^<]+)</a>",
    },
    "NM": {
        "url": "https://supremecourt.nmcourts.gov/about-this-court/supreme-court-justices/",
        "item": r'<h2 class="wp-block-heading"[^>]*>(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</h2>',
    },
    "NC": {
        "url": "https://www.nccourts.gov/courts/supreme-court/meet-the-justices",
        "item": r'<span class="judge__title">\s*(?P<title>[^<]+?)\s*</span>\s*<span class="judge__full-name">'
                r"\s*(?P<name>[^<]+?)\s*</span>",
    },
    "ND": {
        "url": "https://www.ndcourts.gov/supreme-court/justices",
        "item": r'<h5 class="card-title">(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</h5>',
    },
    "OH": {
        "url": "https://www.supremecourt.ohio.gov/courts/judicial-system/supreme-court-of-ohio/justices-overview/",
        "section": [r"Supreme Court Justices</h2>", r"</ul>"],
        "item": r"<a href=\"[^\"]*justices-overview/[^\"]+\">(?:<span[^>]*>.*?</span>)?\s*"
                r"(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</a>",
    },
    "OK": {
        "url": "https://oksc.oscn.net/justices/",
        "section": [r'<ul id="list-justices"', r"</ul>"],
        "item": r'<a href="[^"]*"[^>]*>(?P<name>[^<]+)</a>(?:\s*&#8211;\s*<em>(?P<title>[^<]+)</em>)?',
    },
    "OK-CCA": {
        "url": "https://www.okcca.net/judges/",
        "seats": 5,
        # The site's Judges menu: one link per judge, then pages that are not
        # judges (retention, past judges).
        "section": [r"Judges</a>\s*<ul class=\"sub-menu\">", r"</ul>"],
        "item": r'<a href="https://www\.okcca\.net/judges/(?!judges-for-retention|past-judges)[a-z-]+/">'
                r"(?P<name>[^<]+)</a>",
    },
    "PA": {
        "url": "https://www.pacourts.us/courts/supreme-court/supreme-court-justices",
        "item": r"<span>(?P<title>(?:Chief\s+)?Justice)<br\s*/?>\s*(?P<name>[^<]+)</span>",
    },
    "SC": {
        "url": "https://www.sccourts.org/courts/supreme-court/justices/",
        "item": r'<h3 class="small-title"><span class="d-block">(?P<title>[^<]+)</span>\s*(?P<name>[^<]+)</h3>',
    },
    "SD": {
        "url": "https://ujs.sd.gov/supreme-court/",
        # Every page's menu repeats the names; read the profile grid.
        "section": [r"<h2>South Dakota Supreme Court Justices</h2>", r"</section>|<footer"],
        "item": r'<h3 class="profilepage__subhead">\s*<a [^>]*>(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</a>',
    },
    "TX-CCA": {
        "url": "https://www.txcourts.gov/cca/about-the-court/judges/",
        "seats": 9,
        "section": [r'class="fluid-container bioSummaries"', r"</main>|<footer"],
        "item": r"<h2><a[^>]*>(?P<name>(?P<title>(?:Presiding\s+)?Judge)\s+[^<]+)</a></h2>",
    },
    "OR": {
        "url": "https://www.courts.oregon.gov/courts/_api/web/GetList('%2Fcourts%2FLists%2FJudges')/items"
               "?$filter=Category%20eq%20'Supreme'&$top=50",
        "link": "https://www.courts.oregon.gov/courts/appellate/supreme/Pages/justices.aspx",
        # The page's table reads this list; its names drop the initials' periods.
        "headers": {"Accept": "application/json;odata=nometadata"},
        "format": "json",
        "items": "value",
        "name": "FullName",
        "title": "Job_x0020_Title",
        "initials": True,
    },
    "UT": {
        "url": "https://www.utcourts.gov/en/courts/other-court-info/judges-bios/appellate-courts/supreme-court.html",
        # Capitals, each card twice. An Associate Chief Justice is not the chief.
        "item": r'<a class="cmp-teaser__title-link[^"]*" href="[^"]*/supreme-court/[^"]+\.html"[^>]*>(?P<name>[^<]+)</a>',
    },
    "VT": {
        "url": "https://www.vtcourts.gov/supreme-court",
        # Exactly the justices' titles: a later table lists law clerks as
        # "Law Clerk (Justice Eaton)".
        "item": r'<tr><td><a href="/people/[^"]*">(?P<name>[^<]+)</a></td><td>(?P<title>(?:Chief|Associate) Justice)</td>',
    },
    "VA": {
        "url": "https://www.vacourts.gov/courts/scv/home",
        # "Chief Justice" heads one accordion item, then "Justices"; the
        # retired "Senior Justices" come after.
        "section": [r"Justices of the Supreme Court of Virginia", r"Senior Justices"],
        "item": r'acc-title-no-link">\s*(?P<title>Chief Justice)\s*</div>(?:(?!acc-title-no-link).)*?'
                r"<strong>(?P<name>[^<]+)</strong>|<strong>(?P<name2>The Honorable[^<]+)</strong>",
    },
    "WA": {
        "url": "https://www.courts.wa.gov/appellate_trial_courts/SupremeCourt/?fa=supremecourt.justices",
        # Hand-written: the line break falls after the title, inside the name
        # or nowhere, so take the whole link text that is not the photo. An
        # Associate Chief Justice is not the chief.
        "item": r'fileID=[^"]*">(?P<name>(?!\s*<img)(?:(?!</a>).)+)</a>',
    },
    "WV": {
        "url": "https://www.courtswv.gov/appellate-courts/supreme-court-of-appeals/justices-staff",
        "item": r"<tr><td>(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+?)<br>",
    },
    "WY": {
        "url": "https://www.wyocourts.gov/supreme-court/",
        "item": r'<h4 id="team-member-name-\d+" class="title">(?P<name>[^<]+?)\s*</h4>',
    },
    "IA": {
        "url": "https://www.iowacourts.gov/iowa-courts/supreme-court/justices/",
        "item": r'<h2 class="title_header">\s*(?P<name>[^<]+?)\s*</h2>\s*<div class="cms_metadata2 cms_title"'
                r"[^>]*>\s*(?P<title>[^<]+?)\s*</div>",
    },
}


# Courts whose roster a script cannot read, with what was seen on
# 2026-10-05. Listed on the page without members, and why: never guessed
# from another source (rule 50).
UNREADABLE = {
    "AL": ("https://judicial.alabama.gov/appellate/supremecourt",
           "The court's site reset every connection"),
    "LA": ("https://www.lasc.org/Justices",
           "The court's page shows its justices only once JavaScript runs"),
    "MA": ("https://www.mass.gov/orgs/supreme-judicial-court",
           "The state's site refuses automated requests"),
    "MO": ("https://www.courts.mo.gov/",
           "The court's site answers automated requests with a challenge page"),
    "NH": ("https://www.courts.nh.gov/our-courts/supreme-court",
           "The court's site refuses automated requests"),
    "RI": ("https://www.courts.ri.gov/Public-Resources/Documents/JudicialRoster.pdf",
           "The court publishes its roster only as a PDF"),
    "TN": ("https://www.tncourts.gov/courts/supreme-court/judges",
           "The court's site answers automated requests with a challenge page"),
    # These three answer a browser but refuse this pipeline's requests (a
    # reset connection, or 403), which is not to be worked around.
    "CT": ("https://www.jud.ct.gov/external/supapp/supjustices.htm",
           "The court's site refuses automated requests"),
    "NV": ("https://nvcourts.gov/supreme/court_information/the_supreme_court_of_nevada_justices",
           "The court's site refuses automated requests"),
    "NY": ("https://www.nycourts.gov/ctapps/",
           "The court's site refuses automated requests"),
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
    letters = [ch for ch in name if ch.isalpha()]
    # Capitals, or nearly ("SHERYL GORDON McCLOUD"): ordinary case, with
    # the person's own form where title case would get it wrong.
    if len(letters) > 3 and sum(ch.isupper() for ch in letters) / len(letters) > 0.8:
        from .localgov import display_name
        name = CASED.get(name.upper(), display_name(name))
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
            chief = bool(re.search(CHIEF, f"{title} {name}", re.I))
            name = clean_name(name)
            if recipe.get("initials"):
                # "Stephen K Bushong" -> "Stephen K. Bushong"
                name = re.sub(r"\b([A-Z])\b(?!\.)", r"\1.", name)
            out.append((name, chief))
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
    seats, or more than one chief. A failed request is tried again before
    the court counts as unread: one dropped connection lost Mississippi."""
    page = None
    for wait in (3, 10, 0):
        try:
            page = _get(recipe["url"], recipe.get("headers"))
            break
        except CourtsError:
            if not wait:
                raise
            time.sleep(wait)
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


# The second court of last resort two states have, for criminal cases.
CRIMINAL = {"TX-CCA": ("TX", "Court of Criminal Appeals", "judges"),
            "OK-CCA": ("OK", "Court of Criminal Appeals", "judges")}


def for_state(code, cache):
    """``{"court": {...}}`` (and ``"criminalCourt"`` in Texas and Oklahoma)
    as the page shows it: the court from HIGH_COURTS, and its members from
    the cache, or why they could not be read."""
    from .government_maps import HIGH_COURTS, METHOD_PHRASE
    if code not in HIGH_COURTS:
        return {}
    name, seats, term, method, note = HIGH_COURTS[code]
    out = {}
    for key, entry_code, title in (("court", code, name),) + tuple(
            ("criminalCourt", k, v[1]) for k, v in CRIMINAL.items() if v[0] == code):
        court = {"name": title, "chosen": METHOD_PHRASE.get(method, ""), "term": term,
                 "word": "judges" if entry_code in CRIMINAL or code == "NY" else "justices"}
        read = (cache or {}).get("courts", {}).get(entry_code)
        if read:
            court.update(members=read["members"], chief=read["chief"], seats=read["seats"],
                         url=read["url"])
        elif entry_code in UNREADABLE:
            court.update(unreadable=UNREADABLE[entry_code][1], url=UNREADABLE[entry_code][0],
                         seats=seats if key == "court" else CRIMINAL_SEATS.get(entry_code, 0))
        else:
            continue
        if key == "court":
            court["seats"] = court.get("seats") or seats
            if note:
                court["note"] = note
        out[key] = court
    return out


CRIMINAL_SEATS = {"TX-CCA": 9, "OK-CCA": 5}


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
