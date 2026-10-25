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

A court whose page has no content until JavaScript runs, or that answers a
browser but not a plain request, is read in a headless Chrome
(``tools/read_court_pages.mjs``, Node with no dependencies); a run with no
Chrome keeps each such court's last good read and says so. A roster the
court publishes as a PDF is read from the file's own text (``pdf_lines``).
A court whose site refuses every automated reader (a bot wall) is read by
hand from its own page, with the day and the page's words, in
``overrides.COURT_ROSTERS``, and the page says so. A court nobody can read
is listed without its members and the page says why. Nothing comes from
Wikipedia or Ballotpedia.
"""

import datetime
import html
import json
import os
import re
import time
import urllib.request
import zlib

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
    # Read in a headless Chrome (tools/read_court_pages.mjs), checked
    # 2026-10-17. Each answers a plain request with a reset connection, a
    # 403 or a script challenge, or draws its roster only once JavaScript
    # runs; each answers the browser with its roster.
    "CT": {
        "url": "https://www.jud.ct.gov/external/supapp/supjustices.htm",
        "browser": True,
        # The list under "Biographies of Justices"; the retired are
        # commented out, and a Senior Justice would not be a member.
        "section": [r"Biographies of Justices", r"</section>"],
        "item": r'<li><a href="[^"]*">(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+)</a>',
    },
    "LA": {
        "url": "https://www.lasc.org/About/Biography",
        "browser": True,
        # A table drawn by the page's script: name, then title. The header's
        # "Hon. John L. Weimer, Chief Justice" is not in a table row. A name
        # may sit in <strong>, a bold <span> or neither, and a title cell's
        # <p> may carry a style: the first recipe, which took only the
        # first two, read five of seven.
        "item": r'<a [^>]*href="/Biography\?p=[^"]*"[^>]*>(?P<name>(?:(?!</a>).){1,200}?)</a>'
                r"</p></td><td><p[^>]*>(?P<title>[^<]+)",
    },
    "MA": {
        "url": "https://www.mass.gov/info-details/supreme-judicial-court-justices",
        "browser": True,
        # One heading per justice; the page's other headings are "Contact"
        # and "Related".
        "item": r'<h2 class="ma__comp-heading[^"]*"[^>]*>\s*(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+?)'
                r"\s*</h2>",
    },
    "TN": {
        "url": "https://www.tncourts.gov/courts/supreme-court",
        "browser": True,
        # The cards under "Supreme Court Justices", up to the next heading.
        # The photograph's caption above them is older (it names a justice
        # the cards do not). A card may link anywhere: Justice Kyle Hixson's
        # still links his Court of Criminal Appeals page (2026-10-18).
        "section": [r">\s*Supreme Court Justices\s*</div>", r"<h2"],
        "item": r'<a href="[^"]+" class="card-link\s*">\s*'
                r"(?P<name>(?P<title>(?:Chief\s+)?Justice)\s+[^<]+?)\s*</a>",
    },
    "RI": {
        "url": "https://www.courts.ri.gov/Public-Resources/Documents/JudicialRoster.pdf",
        # The judiciary's roster of every court, as a PDF: its text is read
        # from the file itself (pdf_lines), the Supreme Court's block only.
        # "Justice (Vacant)" is the court saying a seat is empty, not a name.
        "format": "pdf",
        "dated": r"Revised\s+([A-Z][a-z]+ \d{1,2}, \d{4})",
        "section": [r"(?m)^Supreme Court - ", r"(?m)^Superior Court - "],
        # A name, and nothing else: a line joins every run of text along its
        # baseline (pdf_lines), so a phone number or "Retired" set beside a
        # name would otherwise be read as part of it. Every justice's line
        # ("every") must be read as a name, or the read is refused.
        "item": r"(?m)^(?P<name>(?P<title>(?:Chief +)?Justice) +(?!\(Vacant\))"
                r"[A-Za-zÀ-ÖØ-öø-ÿ]"
                r"[A-Za-zÀ-ÖØ-öø-ÿ.'’ -]*(?:, *(?:Jr|Sr)\.?)?)$",
        "every": r"(?m)^(?:Chief +)?Justice +(?!\(Vacant\)$)[^\n]*$",
    },
}

# The browser reader: a Node script (no dependencies) that drives a headless
# Chrome and writes each page as drawn. A run without Node or Chrome reads
# none of these courts, and each keeps its last good read (rule 8).
BROWSER_TOOL = os.path.join("tools", "read_court_pages.mjs")


# Courts whose roster nobody here can read, with what was seen. Listed on
# the page without members, and why: never guessed from another source
# (rule 50). Alabama's site reset every connection on 2026-10-05, and on
# 2026-10-17 and 2026-10-18 from a plain request, a headless Chrome and a
# windowed Chrome alike (the plain http:// address answers only with a
# redirect to the https:// one that resets).
UNREADABLE = {
    "AL": ("https://judicial.alabama.gov/appellate/supremecourt",
           "The court's site reset every connection"),
}

# A roster grows stale without a sound: a court kept at its last good read
# week after week (a page the browser reader could not draw, a recipe the
# page outgrew), or a roster read by hand (overrides.COURT_ROSTERS). Past
# this many days since its read, the build says so.
STALE_DAYS = 45


class CourtsError(RuntimeError):
    """A roster could not be read, or does not fit its court."""


def _get_bytes(url, headers=None, timeout=60):
    request = urllib.request.Request(url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except OSError as exc:
        raise CourtsError(f"could not fetch {url}: {exc}") from exc


def _get(url, headers=None, timeout=60):
    return _get_bytes(url, headers, timeout).decode("utf-8", errors="replace")


# ------------------------------------------------------------- a PDF's text

_PDF_TOKEN = re.compile(rb"\((?:\\.|[^\\)])*\)|<<|>>|\[|\]|<[0-9A-Fa-f\s]*>|/[^\s/\[\]()<>]+|"
                        rb"[-+]?(?:\d+\.?\d*|\.\d+)|[A-Za-z'\"*]+")
_PDF_ESCAPES = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b", ord("f"): b"\f"}


def _pdf_string(token, decode=None):
    """A PDF literal string ``(...)`` as text (WinAnsi, as a simple
    TrueType font without its own encoding writes it), or as *decode* reads
    its bytes, for a font with an encoding of its own."""
    body, out, i = token[1:-1], bytearray(), 0
    while i < len(body):
        if body[i] == 0x5C and i + 1 < len(body):
            nxt = body[i + 1]
            octal = re.match(rb"[0-7]{1,3}", body[i + 1:i + 4])
            if octal:
                out.append(int(octal.group(), 8) & 0xFF)
                i += 1 + len(octal.group())
                continue
            out += _PDF_ESCAPES.get(nxt, bytes([nxt]))
            i += 2
            continue
        out.append(body[i])
        i += 1
    if decode:
        return decode(bytes(out))
    return bytes(out).decode("cp1252", errors="replace")


def pdf_lines(data, decode=None):
    """The lines of text a PDF draws, in the order its content streams draw
    them, with the standard library alone: each Flate-compressed (or plain)
    stream's text operators. A move to a new line (``Td``/``TD`` down,
    ``Tm``, ``T*``, ``'``, the end of a text block) ends a line; a wide gap
    inside a ``TJ`` array is a space. Enough for a roster typed in a word
    processor - not for a scan, which has no text to read."""
    lines = []
    for match in re.finditer(rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", data, re.S):
        head, body = match.groups()
        if b"/FlateDecode" in head:
            try:
                body = zlib.decompress(body)
            except zlib.error:
                continue
        elif b"/Filter" in head:
            continue
        # A page's content is operators in ASCII. A font or an image is
        # binary, and holds "BT" by chance: its bytes are not text.
        if not re.search(rb"(?:^|\s)BT\s", body) or sum(b > 0x7E for b in body[:4096]) > 400:
            continue
        current, operands = [], []

        def flush():
            text = " ".join("".join(current).split())
            if text:
                lines.append(text)
            current.clear()

        for token in _PDF_TOKEN.findall(body):
            if token.startswith(b"("):
                operands.append(_pdf_string(token, decode))
            elif re.fullmatch(rb"[-+]?(?:\d+\.?\d*|\.\d+)", token):
                operands.append(float(token))
            elif token in (b"[", b"]", b"<<", b">>") or token.startswith((b"/", b"<")):
                continue
            elif token == b"Tj":
                current.extend(o for o in operands if isinstance(o, str))
                operands = []
            elif token == b"TJ":
                for item in operands:
                    if isinstance(item, str):
                        current.append(item)
                    elif item < -250:            # a gap wider than a quarter of the font
                        current.append(" ")
                operands = []
            elif token in (b"'", b'"'):
                flush()
                current.extend(o for o in operands if isinstance(o, str))
                operands = []
            elif token in (b"Td", b"TD"):
                numbers = [o for o in operands if isinstance(o, float)]
                # Down a line ends it. A move along the line adds nothing: a
                # word processor writes its spaces as text and moves on to
                # the next run within a word ("Keou" then "gh" is Keough).
                if len(numbers) >= 2 and abs(numbers[-1]) > 0.01:
                    flush()
                operands = []
            elif token in (b"Tm", b"T*", b"ET"):
                flush()
                operands = []
            else:
                operands = []
        flush()
    return lines


# ------------------------------------------------------- a browser's page

def _host(url):
    """A URL's host without a leading "www.": the same site either way."""
    import urllib.parse
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def read_with_browser(pages, root=".", out_dir=None):
    """``({code: html}, problems)`` for ``{code: url}``, each page as a
    headless Chrome drew it (``BROWSER_TOOL``). A page the browser could not
    read, or that answered with an error status (a bot wall's 403), is left
    out and reported. No Node, no Chrome or no WebSocket reads nothing: the
    courts keep their last good read, and the run says why (rule 8)."""
    import subprocess
    import tempfile
    if not pages:
        return {}, []
    out_dir = out_dir or tempfile.mkdtemp(prefix="kyc-court-pages-")
    command = ["node", os.path.join(root, BROWSER_TOOL), "--out", out_dir] + [
        f"{code}={url}" for code, url in sorted(pages.items())]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, [f"the browser reader did not run ({exc}); "
                    f"{', '.join(sorted(pages))} keep their last read"]
    if done.returncode != 0:
        why = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
        return {}, [f"the browser reader did not run ({why}); {', '.join(sorted(pages))} keep their last read"]
    try:
        with open(os.path.join(out_dir, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)["pages"]
    except (OSError, ValueError, KeyError) as exc:
        return {}, [f"the browser reader wrote no manifest ({exc})"]
    found, problems = {}, []
    for code in sorted(pages):
        entry = manifest.get(code) or {}
        if entry.get("error") or not 200 <= int(entry.get("status") or 0) < 300:
            problems.append(f"{code}: the browser read {entry.get('status') or 'nothing'} "
                            f"{entry.get('error') or entry.get('title') or ''} from {pages[code]}".rstrip())
            continue
        # A redirect to another site answers 200 like the court would: the
        # page read is the court's only while it is still on the court's host.
        final = _host(entry.get("finalUrl") or "")
        if final != _host(pages[code]):
            problems.append(f"{code}: the browser was taken from {pages[code]} to "
                            f"{entry.get('finalUrl') or 'nowhere it named'}; not read")
            continue
        with open(os.path.join(out_dir, f"{code}.html"), encoding="utf-8") as handle:
            found[code] = handle.read()
    return found, problems


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
    if recipe.get("every"):
        # Each line the court writes for a member must read as a member: a
        # line the item refuses is a layout the recipe has not seen, not a
        # seat with nobody in it.
        for line in re.finditer(recipe["every"], page, re.I):
            if not re.search(recipe["item"], line.group(0), re.S | re.I):
                raise CourtsError(f"a member's line the recipe does not read as a name: "
                                  f"{line.group(0)!r}")
    out, seen = [], set()
    for match in re.finditer(recipe["item"], page, re.S | re.I):
        groups = {k: v for k, v in match.groupdict().items() if v}
        raw = groups.get("name") or groups.get("name2") or ""
        title = groups.get("title") or groups.get("title2") or ""
        name = clean_name(raw)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        # Whitespace normalised first: the lookbehinds in CHIEF need one
        # plain space, so "Associate<br>\n Chief Justice" or a non-breaking
        # space would otherwise read an associate chief as the chief.
        chief = bool(re.search(CHIEF, _text(f"{title} {raw}"), re.I))
        out.append((name, chief))
    return out


def read_court(code, recipe, seats, page=None, pages=None):
    """``{"members": [...], "chief": name, "listed", "seats", "url"}``, or
    raises when the page does not fit the court: no names, more names than
    seats, or more than one chief. A failed request is tried again before
    the court counts as unread: one dropped connection lost Mississippi.
    A ``browser`` recipe reads *page*, as the browser reader drew it.
    *pages*, when given, keeps the roster's HTML under *code*, for the
    justices' photographs (``court_photos``)."""
    if recipe.get("browser"):
        if page is None:
            raise CourtsError(f"{code}: the browser did not read {recipe['url']}")
    else:
        for wait in (3, 10, 0):
            try:
                data = _get_bytes(recipe["url"], recipe.get("headers"))
                break
            except CourtsError:
                if not wait:
                    raise
                time.sleep(wait)
        if recipe.get("format") == "pdf":
            if not data.startswith(b"%PDF"):
                raise CourtsError(f"{code}: {recipe['url']} did not answer with a PDF")
            page = "\n".join(pdf_lines(data))
            recipe = {k: v for k, v in recipe.items() if k != "format"}
        else:
            page = data.decode("utf-8", errors="replace")
    if pages is not None and recipe.get("format") != "pdf":
        pages[code] = page
    members = extract(page, recipe)
    if not members:
        raise CourtsError(f"{code}: no members read from {recipe['url']}")
    if len(members) > seats:
        raise CourtsError(f"{code}: {len(members)} members read for {seats} seats")
    chiefs = [n for n, chief in members if chief]
    if len(chiefs) > 1:
        raise CourtsError(f"{code}: more than one chief read: {', '.join(chiefs)}")
    out = {"members": [n for n, _ in members], "chief": chiefs[0] if chiefs else "",
           "listed": len(members), "seats": seats, "url": recipe.get("link", recipe["url"]),
           # The day it was read: a court that later keeps this read
           # (rule 8) carries the day, and stale() says when it is old.
           "read": datetime.date.today().isoformat()}
    if recipe.get("dated"):
        # The date the court's own document says it was revised: a roster
        # file can be months old, and the page says so.
        found = re.search(recipe["dated"], page)
        if not found:
            raise CourtsError(f"{code}: the roster no longer says when it was revised")
        out["revised"] = datetime.datetime.strptime(found.group(1), "%B %d, %Y").date().isoformat()
    return out


def fetch(codes=None, pause=1.0, root=".", pages=None):
    """``(courts, problems)`` for every court with a recipe. The courts a
    browser must read are read first, together, by the browser reader.
    *pages*, when given, collects each roster's HTML (``read_court``)."""
    from .government_maps import HIGH_COURTS
    courts, problems = {}, []
    codes = sorted(codes or COURTS)
    drawn, browser_problems = read_with_browser(
        {c: COURTS[c]["url"] for c in codes if COURTS[c].get("browser")}, root)
    problems.extend(browser_problems)
    for code in codes:
        recipe = COURTS[code]
        seats = recipe.get("seats", HIGH_COURTS.get(code[:2], ("", 0))[1])
        try:
            courts[code] = read_court(code, recipe, seats, drawn.get(code), pages)
        except CourtsError as exc:
            problems.append(str(exc))
        if not recipe.get("browser"):
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
            if read.get("read"):
                # The day the court's roster was read, for the page's list
                # of sources.
                court["read"] = read["read"]
            if read.get("revised"):
                court["revised"] = read["revised"]
        elif entry_code in curated():
            roster = curated()[entry_code]
            # Read by hand (overrides.COURT_ROSTERS): the page says so, and
            # on which day.
            court.update(members=list(roster["members"]), chief=roster["chief"], url=roster["url"],
                         readOn=roster["read"])
        elif entry_code in UNREADABLE:
            court.update(unreadable=UNREADABLE[entry_code][1], url=UNREADABLE[entry_code][0],
                         seats=seats if key == "court" else CRIMINAL_SEATS.get(entry_code, 0))
        else:
            continue
        if court.get("members"):
            # Each justice's photograph from the court's own pages, or an
            # evidenced override's (court_photos; rule 87), credited to the
            # court on the page.
            from .court_photos import for_page
            shown = for_page(entry_code, read or {"members": court["members"]})
            if shown:
                court["photos"] = shown
        if key == "court":
            court["seats"] = court.get("seats") or seats
            if note:
                court["note"] = note
        out[key] = court
    return out


CRIMINAL_SEATS = {"TX-CCA": 9, "OK-CCA": 5}


def curated():
    """``{code: {"url", "read", "members", "chief", "evidence"}}``: the
    rosters a person read from a court's own page, where the court's site
    refuses every automated reader (``overrides.COURT_ROSTERS``)."""
    from .overrides import COURT_ROSTERS
    return {code: dict(zip(("url", "read", "members", "chief", "evidence"), entry))
            for code, entry in COURT_ROSTERS.items()}


def curated_errors():
    """Every curated roster that does not fit its court, as a read roster
    would be refused: more names than seats, a name twice, a chief who is
    not a member, a court with a recipe or no seats, or no page and words
    quoted from it. Each is an error that stops the build
    (``stategov.build``), never a warning: a read roster that broke these
    would not reach the page, and nor may one typed in."""
    from .government_maps import HIGH_COURTS
    problems = []
    for code, roster in sorted(curated().items()):
        seats = HIGH_COURTS.get(code, ("", 0))[1]
        members = list(roster["members"])
        if code in COURTS or code in UNREADABLE:
            problems.append(f"{code}: a curated roster for a court the pipeline reads or calls unreadable")
        if not members or len(members) > seats or len(set(members)) != len(members):
            problems.append(f"{code}: the curated roster lists {len(members)} for {seats} seats")
        if roster["chief"] and roster["chief"] not in members:
            problems.append(f"{code}: the curated chief {roster['chief']} is not among its members")
        if not roster["url"].startswith("https://") or not roster["evidence"]:
            problems.append(f"{code}: a curated roster needs the court's page and what it says")
        try:
            datetime.date.fromisoformat(roster["read"])
        except (TypeError, ValueError):
            problems.append(f"{code}: a curated roster needs the day it was read, as YYYY-MM-DD")
    return problems


def curated_stale(today=None):
    """Every roster read by hand more than ``STALE_DAYS`` ago: a warning for
    a person to read the court's page again."""
    today = today or datetime.date.today()
    problems = []
    for code, roster in sorted(curated().items()):
        try:
            age = (today - datetime.date.fromisoformat(roster["read"])).days
        except (TypeError, ValueError):
            continue                             # curated_errors says so
        if age > STALE_DAYS:
            problems.append(f"{code}: the court's roster was read by hand {age} days ago "
                            f"({roster['read']}); read {roster['url']} again and update "
                            "overrides.COURT_ROSTERS")
    return problems


def stale(cache, today=None):
    """A court whose members come from a read more than ``STALE_DAYS`` old:
    the refresh kept its last good read (rule 8) every run since. Each read
    carries its own day, kept with it (kyc/cli.py): the cache's ``fetched``
    is rewritten by every run, so a court that stopped reading would never
    age by it, and a read with no day of its own is reported as such."""
    today = today or datetime.date.today()
    out = []
    for code, court in sorted(((cache or {}).get("courts") or {}).items()):
        day = str(court.get("read") or "")
        try:
            age = (today - datetime.date.fromisoformat(day)).days
        except ValueError:
            out.append(f"{code}: the cache does not say when the court's roster was read")
            continue
        if age > STALE_DAYS:
            out.append(f"{code}: the court's roster was last read {age} days ago ({day}); "
                       "'courts' has kept that read since - look at why it no longer reads")
    return out


def shrunk(before, after):
    """A court that now lists fewer members than its last read. The page
    says the missing seats have "nobody listed by the court", which is true
    only if the recipe still reads everyone the court lists - Oklahoma's
    once missed a justice whose link carried an extra attribute - so a drop
    is reported for a person to look at the court's page."""
    return [f"{code}: {after[code]['listed']} members read, {before[code]['listed']} last time "
            f"(gone: {', '.join(sorted(set(before[code]['members']) - set(after[code]['members']))) or '-'})"
            for code in sorted(set(before) & set(after))
            if after[code]["listed"] < before[code]["listed"]]


def changed(before, after):
    """A court whose members differ from its last read with no fewer of
    them (``shrunk`` reports the rest). A high court's roster changes a few
    times a year; a recipe that has begun to read a neighbouring word into a
    name ("Taft-CarterRetired" from a roster file's line) changes it too,
    and looks entirely normal on the page. Either is for a person to see."""
    out = []
    for code in sorted(set(before) & set(after)):
        gone = sorted(set(before[code]["members"]) - set(after[code]["members"]))
        new = sorted(set(after[code]["members"]) - set(before[code]["members"]))
        if (gone or new) and after[code]["listed"] >= before[code]["listed"]:
            out.append(f"{code}: the court's members changed since the last read (gone: "
                       f"{', '.join(gone) or '-'}; new: {', '.join(new) or '-'}); check the court's page")
    return out


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
