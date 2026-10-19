"""Generate the per-state pages.

``index.html`` and ``map.html`` are hand-maintained templates. The state pages
are not: fifty-six near-identical documents would drift the moment one of
them was edited by hand, so they are written by the build from one template
here, and every state's page is identical except for the facts about that
state. The content itself is rendered on the client by ``assets/kyc-state.js``
from the same ``profiles.js`` the other pages load, so a state page can never
disagree with the grid about who represents a district.

The pages live one directory down (``states/tx.html``), so every asset and
data reference is relative to that: a page that works when opened straight
off disk also works when served, and the render tests exercise both.
"""

import html
import string

from .courts import STALE_DAYS as COURT_STALE_DAYS
from .normalize import TERRITORIES, US_STATES

STATE_NAMES = {}
for _name, _code in US_STATES.items():
    _words = [w.lower() if w.lower() == "of" else w.capitalize() for w in _name.split()]
    STATE_NAMES[_code] = " ".join(_words)


def state_name(code):
    """``"TX"`` -> ``"Texas"``."""
    return STATE_NAMES.get(code, code)


def page_path(code):
    """The page's path inside the site directory: ``states/tx.html``."""
    return f"states/{code.lower()}.html"


_PAGE = string.Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<meta name="description" content="$description">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0d0f12" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f5f7fa" media="(prefers-color-scheme: light)">
<link rel="canonical" href="$canonical">
<meta property="og:url" content="$canonical">
<meta property="og:type" content="website">
<meta property="og:title" content="$og_title">
<meta property="og:description" content="$description">
<meta property="og:image" content="https://$host/assets/social-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Know Your Candidate">
<meta property="og:site_name" content="Know Your Candidate">
<meta name="twitter:card" content="summary_large_image">
<meta name="referrer" content="no-referrer">
<link rel="icon" href="${root}assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="${root}assets/apple-touch-icon.png">
<link rel="manifest" href="${root}site.webmanifest">
<link rel="stylesheet" href="${root}assets/kyc.css">
<script src="${root}assets/kyc.js"></script>
$jsonld</head>
<body data-root="$root" data-state="$code" data-page="$page_kind">

<a href="#stateMain" class="skip-link">Skip to content</a>
<button type="button" class="sidebar-scrim" tabindex="-1" aria-hidden="true"></button>

<header class="app-header">
    <button type="button" class="btn-icon sidebar-toggle" aria-expanded="false"
            aria-controls="sidebar" aria-label="Show navigation">
        <svg class="icon" aria-hidden="true"><use href="#i-menu"/></svg>
    </button>

    <a class="brand" href="${root}index.html">
        <svg class="icon" aria-hidden="true"><use href="#i-vote"/></svg>
        <span class="brand-name">Know Your Candidate</span>
        $brand_sub
    </a>

$search
    <div class="header-actions">
        <div class="menu">
            <button type="button" class="btn-icon" id="themeButton"
                    aria-haspopup="true" aria-label="Change theme">
                <svg class="icon" aria-hidden="true"><use href="#i-palette"/></svg>
            </button>
            <div class="menu-panel" id="themePanel" role="menu" hidden>
                <button type="button" class="menu-item" role="menuitemradio"
                        data-theme-option="system" aria-checked="true">
                    <svg class="icon check" aria-hidden="true"><use href="#i-check"/></svg>
                    Match system
                </button>
                <button type="button" class="menu-item" role="menuitemradio"
                        data-theme-option="dark" aria-checked="false">
                    <svg class="icon check" aria-hidden="true"><use href="#i-check"/></svg>
                    Dark
                </button>
                <button type="button" class="menu-item" role="menuitemradio"
                        data-theme-option="amoled" aria-checked="false">
                    <svg class="icon check" aria-hidden="true"><use href="#i-check"/></svg>
                    AMOLED black
                </button>
                <button type="button" class="menu-item" role="menuitemradio"
                        data-theme-option="light" aria-checked="false">
                    <svg class="icon check" aria-hidden="true"><use href="#i-check"/></svg>
                    Light
                </button>
            </div>
        </div>
    </div>
</header>

<div class="app-body">
    <aside class="sidebar scroll-y" id="sidebar" aria-label="Navigation and summary">
$nav
$sidebar
        <nav class="sidebar-section push" aria-label="Jump to a state">
            <h2 class="sidebar-heading">Jump to</h2>
            <label class="sr-only" for="stateJump">$jump_label</label>
            <select id="stateJump" class="select"$jump_attrs>
                <option value="">Choose a state&hellip;</option>$jump_options
            </select>
        </nav>
$built
    </aside>

$main_block
</div>

$scripts
</body>
</html>
""")

# The site's navigation, by level of government. One table: every generated
# page renders it, and emit.check_nav holds the two hand-maintained pages,
# index.html and map.html, to it. Each entry is (key, path from the site's
# root, icon, label). The election's year is the cycle's (kyc/cycle.py),
# never typed (rule 65).
def nav_groups():
    from .cycle import CYCLE

    return (
        (f"Elections {CYCLE}", (
            ("candidates", "index.html", "user", "Candidates"),
            ("races", "map.html", "map", "Races & partisan map"),
        )),
        ("Federal", (
            ("congress", "index.html#/?role=member", "landmark", "Congress"),
            ("executive", "federal/index.html#executive", "flag", "President & Cabinet"),
            ("courts", "courts/index.html", "scale", "Federal courts"),
        )),
        ("State", (
            ("states", "states/index.html", "pin", "States & territories"),
            ("legislatures", "legislature/index.html", "columns", "State legislatures"),
        )),
        ("Local", (
            ("local", "counties/index.html", "layers", "Counties & local governments"),
        )),
        ("Learn", (
            ("guide", "government/index.html", "scroll", "Know Your Government"),
            ("about", "about.html", "info", "About & sources"),
        )),
    )


def section_name(key):
    """The navigation's name for the entry *key*: the one name a section
    has in the sidebar, the header's tag and the breadcrumbs (rule 75)."""
    for _heading, entries in nav_groups():
        for entry_key, _path, _icon, label in entries:
            if entry_key == key:
                return label
    raise KeyError(f"no navigation entry {key!r}")


def nav_html(prefix="../", current=None, how="page"):
    """The sidebar's navigation, its links *prefix*-ed from the page. The
    entry *current* is marked ``aria-current``: "page" where its link is
    this page, "true" where this page belongs to it (a court's page, under
    Federal courts)."""
    lines = ['        <nav class="sidebar-section site-nav" aria-label="Site">']
    for heading, entries in nav_groups():
        lines.append(f'            <h2 class="nav-group">{_e(heading)}</h2>')
        for key, path, icon, label in entries:
            mark = f' aria-current="{how}"' if key == current else ""
            lines += [f'            <a class="nav-link" href="{_e(prefix + path)}" data-nav="{key}"{mark}>',
                      f'                <svg class="icon" aria-hidden="true"><use href="#i-{icon}"/></svg>',
                      f"                {_e(label)}",
                      "            </a>"]
        if heading == "State":
            # The reader's own state, remembered (KYC.renderRememberedState).
            lines.append('            <div id="yourState" hidden></div>')
    lines.append("        </nav>")
    return "\n".join(lines)


# The search box in the header. A state's pages search its profiles; every
# other page's box searches the grid's, on index.html (kyc.js sends the
# words there), so the site's search does not vanish when a reader leaves
# the Congress pages.
_SEARCH = """\
    <div class="search">
        <svg class="icon" aria-hidden="true"><use href="#i-search"/></svg>
        <label class="sr-only" for="stateSearch">Search this page</label>
        <input type="search" id="stateSearch" autocomplete="off" spellcheck="false"
               placeholder="$search_placeholder">
    </div>
"""

_SITE_SEARCH = """\
    <form class="search" role="search" action="${root}index.html" data-site-search>
        <svg class="icon" aria-hidden="true"><use href="#i-search"/></svg>
        <label class="sr-only" for="siteSearch">Search candidates and members of Congress</label>
        <input type="search" id="siteSearch" name="q" autocomplete="off" spellcheck="false"
               placeholder="Search candidates and members&hellip;" data-placeholder-short="Search&hellip;">
    </form>
"""

# The sidebar of every page that loads profiles.js: the chambers' balance,
# the state's own delegation on its pages, and the election.
_CONGRESS_SIDEBAR = """
        <div class="sidebar-section">
            <h2 class="sidebar-heading" data-congress>U.S. Congress</h2>
            <div class="balance-label">Senate</div>
            <div class="balance" id="senateBalance"></div>
            <div class="balance-label">House</div>
            <div class="balance" id="houseBalance"></div>
            <a class="sidebar-link learn-link" href="../government/congress.html">How Congress works</a>
        </div>

        <div class="sidebar-section" id="stateBalance" hidden></div>

        <div class="sidebar-section">
            <h2 class="sidebar-heading">
                <svg class="icon icon-sm" aria-hidden="true"><use href="#i-flag"/></svg>
                2026 midterms
            </h2>
            <time id="electionCountdown" class="badge badge-warn countdown"></time>
            <div class="stat-row"><span>Senate seats up</span>
                <span class="value" id="senateSeatsUp"></span></div>
            <div class="stat-row"><span>House seats up</span>
                <span class="value" id="houseSeatsUp"></span></div>
            <div class="stat-row"><span>Challengers on the ballot</span>
                <span class="value" id="challengerCount"></span></div>
            <div class="stat-row"><span>Candidates for open seats</span>
                <span class="value" id="openCandidateCount"></span></div>
            <a class="sidebar-link learn-link" href="../government/elections.html">How elections work</a>
        </div>
"""

_CONGRESS_SOURCES = """\
                <p><strong>Sources:</strong>
                    membership, contact details and committee rosters from the
                    <code>congress-legislators</code> dataset; the candidate field and
                    campaign finance from the Federal Election Commission; primary results
                    from each state's Wikipedia election page<span data-results-read hidden>,
                    as last read on <time data-results-as-of></time></span>; the November
                    ballot, where this site reads one, from the certified list of candidates
                    its election office publishes, credited on each race it sets; portraits
                    from the House of Representatives, Congress.gov, Wikimedia Commons and
                    candidates' campaign websites, each credited under the photograph on the
                    profile, a Wikimedia Commons file with its author and licence.</p>
                <p><strong>Who counts as a candidate:</strong> everyone the FEC records
                    as having raised or spent more than $5,000 for the 2026 cycle
                    (52&nbsp;U.S.C.&nbsp;&sect;30101(2)). People no longer in a race - beaten
                    in a primary, withdrawn, or left off a certified list - stay on record
                    and are shown under each race.</p>"""


# ------------------------------------------------------- the site's frame

# The public repository: where the code and data live and where a reader
# reports an error. kyc.js holds the same address (KYC.REPO_URL), and a test
# holds the two together.
REPO = "https://github.com/pkplaya626/Know-Your-Candidate"
ISSUE_FORM = REPO + "/issues/new?template=correction.yml"

_MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.",
           "Oct.", "Nov.", "Dec.")


def date_words(iso):
    """``"2026-10-15T13:14:00+00:00"`` -> ``"Oct. 15, 2026"``, as the profile
    writes a term ("Jan. 3, 2027"); anything that is not an ISO date -> ``""``."""
    import re

    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    if not match or not 1 <= int(match.group(2)) <= 12:
        return ""
    year, month, day = match.groups()
    return f"{_MONTHS[int(month) - 1]} {int(day)}, {year}"


def time_html(iso):
    """A ``<time>`` for *iso*, in words; ``""`` for no date."""
    words = date_words(iso)
    return f'<time datetime="{_e(str(iso)[:10])}">{_e(words)}</time>' if words else ""


def report_url(page=None, profile=None):
    """The issue form for a correction, filled in with the page and the
    profile it is about (GitHub fills a form field from the query parameter
    of its id: .github/ISSUE_TEMPLATE/correction.yml)."""
    from urllib.parse import quote

    url = ISSUE_FORM
    if page:
        url += "&page=" + quote(page, safe="")
    if profile:
        url += "&profile=" + quote(profile, safe="")
    return url


# The tag beside the site's name, for a page that is not about Congress: the
# section it belongs to. The federal hub's entry in the navigation is
# "President & Cabinet", but the page holds the courts too, so its tag is
# the whole branch's name, as its own kicker and sidebar call it.
_SECTION_TAGS = {"executive": "Federal government"}


def brand_sub(nav_current=None, congress=False):
    """The tag beside the site's name: which part of the site this is. A
    page that loads profiles.js names the Congress its data is of
    (``data-congress``, filled by kyc.js); every other page names its
    section as the navigation does (rule 75), never "U.S. Congress" over a
    county, a court or the guide."""
    if congress:
        return '<span class="brand-sub" data-congress>U.S. Congress</span>'
    name = _SECTION_TAGS.get(nav_current) or (section_name(nav_current) if nav_current else "")
    return f'<span class="brand-sub">{_e(name)}</span>' if name else ""


# The build's date in a footer, filled from profiles.js by kyc.js.
BUILD_STAMP = 'Data built <time id="buildStamp">&mdash;</time>. '


def footer_html(sources, root="../", built=None, page=None):
    """A page's footer, the same on every page (rule 12): its own sources
    (*sources*, markup, each with the date it was read), then one line - the
    build stamp where the page loads it (*built* "stamp"), else the date
    given - with links to About and to report a problem with this page."""
    if built == "stamp":
        when = BUILD_STAMP
    else:
        when = f"{read_words(built)}. " if built else ""
    return "\n".join([sources, "                " + footer_meta(root, when, page)])


def footer_meta(root="", when="", page=None):
    """The last line of every page's footer: what the site is, how fresh
    the page is (*when*, markup), and the links to About and to report a
    problem. The two hand-maintained pages carry it too, written by this
    (emit.check_nav holds them to it)."""
    report = report_url(page)
    return (f'<p class="footer-meta">Non-partisan and independent. {when}'
            f'<a href="{_e(root)}about.html">{_e(section_name("about"))}</a> &middot; '
            f'<a href="{_e(report)}" data-report target="_blank" rel="noopener noreferrer">'
            "Report a problem</a></p>")


def built_line(root="../", built=None):
    """The sidebar's line saying how fresh the page's data is, with the way
    to its sources: a grid of a thousand cards pushes the footer out of
    reach (TRUST-04). *built* is "stamp" where the page loads profiles.js
    (kyc.js fills it), a date, or None for a page with no data."""
    if built == "stamp":
        when = 'Data built <time data-built>&mdash;</time> &middot; '
    else:
        when = f"{read_words(built)} &middot; " if built else ""
    return (f'        <p class="sidebar-section sidebar-built">{when}'
            f'<a href="{_e(root)}about.html">{_e(section_name("about"))}</a></p>')


def jsonld(data):
    """A ``<script type="application/ld+json">`` block: data for search
    engines, not code (emit.inline_script_problems allows this type
    alone, and only as JSON)."""
    import json

    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return ('<script type="application/ld+json">'
            + text.replace("</", "<\\/") + "</script>\n")


def website_jsonld(host):
    """The home page's WebSite block, with the grid's search as its
    SearchAction (kyc.js reads ``index.html?q=``). index.html is edited by
    hand and carries exactly this (emit.check_nav)."""
    root = f"https://{host}/"
    return jsonld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Know Your Candidate",
        "url": root,
        "description": "A non-partisan directory of the U.S. Congress, the 2026 midterm "
                       "races, and every state's government.",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint",
                       "urlTemplate": root + "index.html?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    })


def breadcrumbs(host, trail):
    """BreadcrumbList for *trail*, ``[(name, path from the site's root)]``,
    the site first. Names are the navigation's (section_name)."""
    if not host:
        return ""
    items = [{"@type": "ListItem", "position": i + 1, "name": name,
              "item": f"https://{host}/{path}"} for i, (name, path) in enumerate(trail)]
    return jsonld({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "itemListElement": items})


# A reading page: one scrolling column, its footer at the end. A map page
# (the guide's) passes its own main block instead: the map and its panel.
_CONTENT_MAIN = string.Template("""    <main class="app-main" id="stateMain">
        <div class="content scroll-y">
$main

            <footer class="site-footer">
$footer
            </footer>
        </div>
    </main>""")


def render_page(**fields):
    """Fill the shared template. Each page kind passes what differs; the
    profile pages share the Congress sidebar, footer and search box.

    *root* is the way from the page to the site's root ("../" one folder
    down, "" at the root, "/" for the 404 page GitHub serves at any depth);
    *crumbs* the page's place in the site for search engines; *built* the
    data's date for the sidebar and footer ("stamp" for the build's own)."""
    root = fields.setdefault("root", "../")
    congress = "sidebar" not in fields
    built = fields.pop("built", "stamp" if congress else None)
    # A footer whose sources each carry their date does not repeat it in
    # its last line: a court's said "as read on Oct. 17, 2026" three times.
    footer_built = None if fields.pop("footer_dated", False) else built
    page = fields.pop("page_url", None)
    if page is None and fields.get("canonical", "").startswith("https:"):
        page = html.unescape(fields["canonical"])
    if "main_block" not in fields:
        fields["main_block"] = _CONTENT_MAIN.substitute(
            main=fields.pop("main"),
            footer=footer_html(fields.pop("footer", _CONGRESS_SOURCES), root, footer_built, page))
    search = fields.pop("search", None)
    if search is None:
        search = string.Template(_SEARCH).substitute(
            search_placeholder=fields.pop("search_placeholder"))
    elif search == "":
        search = string.Template(_SITE_SEARCH).substitute(root=root)
    fields.setdefault("sidebar", _CONGRESS_SIDEBAR)
    current = fields.pop("nav_current", None)
    fields["brand_sub"] = brand_sub(current, congress)
    fields["nav"] = nav_html(root, current, fields.pop("nav_how", "page"))
    fields["built"] = built_line(root, built)
    host = html.unescape(fields.get("host") or "")
    crumbs = fields.pop("crumbs", None)
    fields["jsonld"] = breadcrumbs(host, crumbs) if crumbs else fields.get("jsonld", "")
    fields.setdefault("jump_options", "")
    fields.setdefault("jump_attrs", "")
    # An empty list is filled on the page with every state and territory; a
    # list written here (the legislature and county pages) may hold only
    # the fifty states, and its label says what it holds.
    options = fields["jump_options"]
    whole = not options or any(f'value="{c}"' in options for c in TERRITORIES)
    fields["jump_label"] = "Jump to a state or territory" if whole else "Jump to a state"
    return _PAGE.substitute(search=search, **fields)

# The state pages render everything from profiles.js on the client. The
# guide page's name rides on the container, so the button the page draws to
# it is called what the guide calls itself (rule 75), never retyped.
_STATE_MAIN = string.Template("""\
            <div id="stateContent" class="state-page" data-guide-name="$guide">
                <p class="results-bar" role="status">Loading&hellip;</p>
            </div>""")


def _state_main():
    return _STATE_MAIN.substitute(guide=_e(_guide_name("states")))

_STATE_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../data/stategov.js",
    "../data/lookup/index.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-stategov.js",
    "../assets/kyc-findrep.js",
    "../assets/kyc-state.js",
)

_DISTRICT_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../data/districts/{code}.js",
    "../data/lookup/index.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-findrep.js",
    "../assets/kyc-districts.js",
)

# "Find who represents me" on a state's legislature and county pages: the
# panel (kyc-findrep.js) is written into this slot, first on the page.
# *view* is the id of the page's map: a district picked in the answer is
# selected on this page, and the panel scrolls the map into view.
def _findrep_slot(code, view):
    return (f'                <section class="state-section findrep" id="findrep" data-findrep '
            f'data-findrep-state="{_e(code)}" data-findrep-view="{_e(view)}"></section>')


def _e(text):
    return html.escape(str(text), quote=True)


def _scripts(sources):
    return "\n".join(f'<script src="{_e(src)}"></script>' for src in sources)


# The caches whose dates the footers print: (key, file under data/, the
# fields that hold when it was read, first found wins). Each is the date the
# source was read, so a rebuild of the same data writes the same page
# (rule 18). Never odds.json: the odds job may change no page (rule 41).
DATED_CACHES = (
    ("congress", "../../congress_snapshot.json", ("fetched",)),
    ("committees", "committees.json", ("fetched",)),
    ("results", "primary_results.json", ("asOf",)),
    ("openstates", "state_legislators.json", ("fetched",)),
    ("ncsl", "partisan_composition.json", ("fetched",)),
    ("governors", "executives.json", ("fetched",)),
    ("officers", "statewide_officers.json", ("fetched",)),
    ("statecourts", "courts.json", ("fetched",)),
    ("voting", "voting_links.json", ("linksChecked", "fetched")),
    ("census", "census_governments.json", ("fetched",)),
    ("tribes", "tribal_leaders.json", ("fetched",)),
    ("executive", "federal_executive.json", ("asOf", "fetched")),
    ("judiciary", "judiciary.json", ("asOf", "fetched")),
    ("vacancies", "judicial_vacancies.json", ("asOf", "read", "fetched")),
    ("history", "political_history.json", ("read",)),
    ("oge", "oge_disclosures.json", ("read",)),
    ("enrichment", "enrichment.json", ("checked",)),
)


def data_dates(root="."):
    """``{key: ISO date}``: when each dated cache was read, by its own
    record. A cache that is missing or carries no date is left out, and the
    page then names its source without a date rather than a wrong one."""
    import json
    import os

    out = {}
    base = os.path.join(root, "candidate_profiles_site", "data")
    for key, name, fields in DATED_CACHES:
        try:
            with open(os.path.normpath(os.path.join(base, name)), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for field in fields:
            if date_words((data or {}).get(field)):
                out[key] = str(data[field])[:10]
                break
    return out


def listing_date(code, root="."):
    """When the Census listing of *code*'s local governments was read."""
    import json
    import os

    try:
        with open(os.path.join(root, "local_governments", f"{code.lower()}.json"),
                  encoding="utf-8") as handle:
            fetched = (json.load(handle) or {}).get("fetched")
    except (OSError, ValueError):
        return None
    return str(fetched)[:10] if date_words(fetched) else None


def _when(dates, key, before=", as read on "):
    """", as read on <time>Oct. 15, 2026</time>" for a dated cache, else ""."""
    iso = (dates or {}).get(key)
    return f"{before}{time_html(iso)}" if iso else ""


def _read_span(dates, *keys):
    """``(earliest, latest)`` of the dates *keys* name, for the line saying
    when the page's sources were read; ``None`` when none is dated. A page
    of several sources never claims the latest read for all of them."""
    found = [dates[k] for k in keys if (dates or {}).get(k)]
    return (min(found), max(found)) if found else None


def read_words(span):
    """"Sources read on Oct. 15, 2026", or "... read Oct. 5 to Oct. 17,
    2026" for a page of several; markup. Never "data as of": the Census of
    Governments counted in 2022 and was read in 2026."""
    first, last = span
    if first == last:
        return f"Sources read on {time_html(first)}"
    return f"Sources read between {time_html(first)} and {time_html(last)}"


# The first step of every page's breadcrumbs: the site.
_HOME = ("Know Your Candidate", "")


def render_state(code, host, summary=None):
    """The HTML for one state's page."""
    name = state_name(code)
    info = ((summary or {}).get("states") or {}).get(code) or {}
    if code in TERRITORIES and info.get("houseTerm"):
        # Puerto Rico: a four-year seat with no 2026 race (summary._delegate_seats).
        title = info.get("delegateTitle", "Delegate")
        description = (f"{name}'s {title} in the U.S. House, elected for a "
                       f"{info['houseTerm']['years']}-year term and next on the ballot in "
                       f"{info['houseTerm']['next']}, and who governs {name}.")
    elif code in TERRITORIES:
        what = "delegate to the U.S. House" if info.get("house", 0) <= 1 else "delegates"
        description = (f"{name}'s {what}, the 2026 race for the seat, and every "
                       f"candidate who has filed - who is on the ballot and who is out.")
    else:
        description = (
            f"{name}'s U.S. senators and representatives, the 2026 midterm races for "
            f"{info.get('seatsUp', 'its')} seats, and every candidate who has filed: "
            f"who is on the November ballot, who is out, and how to reach them."
        )
    canonical = f"https://{host}/{page_path(code)}" if host else page_path(code)
    return render_page(
        title=_e(f"{name} — Know Your Candidate"),
        og_title=_e(f"{name}: Congress and the 2026 midterms"),
        description=_e(description),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="state",
        nav_current="states",
        nav_how="true",
        search_placeholder=_e(f"Search {name} profiles…"),
        main=_state_main(),
        scripts=_scripts(_STATE_SCRIPTS),
        crumbs=[_HOME, (section_name("states"), "states/index.html"), (name, page_path(code))],
    )


def render_states_index(host):
    """The directory of every state and territory page."""
    canonical = f"https://{host}/states/index.html" if host else "states/index.html"
    return render_page(
        title=_e("States & territories — Know Your Candidate"),
        og_title=_e("Every state's Congress and 2026 midterm races"),
        description=_e("One page per state and territory: its senators and representatives, "
                       "the 2026 races, and everyone who has filed to run."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="states",
        search_placeholder=_e("Search states…"),
        nav_current="states",
        main=_state_main(),
        crumbs=[_HOME, (section_name("states"), "states/index.html")],
        scripts=_scripts(_STATE_SCRIPTS),
    )


def render_legislatures_index(host, dates=None):
    """Every state legislature, each linked to its page, with each chamber's
    seats by party and who holds a majority - drawn by
    ``assets/kyc-stategov.js`` from ``data/stategov.js``, the words of the
    state pages. The list itself is plain links, there without the script."""
    from .government import jump_options
    from .government_maps import STATES

    path = "legislature/index.html"
    canonical = f"https://{host}/{path}" if host else path
    rows = "\n".join(
        f'                    <li class="directory-row" data-state="{_e(code)}">'
        f'<a class="directory-name" href="{_e(code.lower())}.html">{_e(state_name(code))}</a>'
        f'<div class="directory-facts" data-facts="{_e(code)}"></div></li>'
        for code in sorted(STATES, key=state_name))
    main = "\n".join([
        '            <div id="legislatureDirectory" class="state-page directory-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">State legislatures</p>',
        '                    <h1 class="state-title">Every state legislature</h1>',
        '                    <p class="districts-lede">Each state\'s two chambers - one in Nebraska -',
        '                        with the seats each party holds and who has a majority. Pick a state',
        '                        for its districts on a map and the members who sit for them.</p>',
        '                    <p class="state-links">',
        f'                        <a class="btn" href="{_e(_learn("states#legislatures"))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> How state legislatures work</a>',
        '                        <a class="btn" href="../states/index.html"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> States &amp; territories</a>',
        "                    </p>",
        "                </header>",
        '                <ul class="directory-list">',
        rows,
        "                </ul>",
        '                <p class="faint directory-outside">The fifty state legislatures. The District of',
        '                    Columbia has <a href="../states/dc.html">a mayor and a council</a>, not a',
        "                    legislature, and the territories&#8217; legislatures are not covered here.</p>",
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Sources:</strong> members and their parties from Open States, as",
        f"                    each legislature publishes them{_when(dates, 'openstates')}. Which party",
        "                    holds each chamber is checked against the National Conference of State",
        f"                    Legislatures' figures{_when(dates, 'ncsl')} and shown only where the two",
        "                    agree. A seat with nobody listed counts for no one.</p>",
    ])
    return render_page(
        title=_e("State legislatures — Know Your Candidate"),
        og_title=_e("Every state legislature: who holds each chamber"),
        description=_e("Every state legislature: each chamber's seats by party and who holds a "
                       "majority, with a map of each state's districts and members."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="legislatures",
        search="",
        sidebar="",
        nav_current="legislatures",
        jump_options=jump_options(STATES),
        jump_attrs=' data-jump-to="legislature/{code}.html"',
        main=main,
        footer=footer,
        built=_read_span(dates, "openstates", "ncsl"),
        crumbs=[_HOME, (section_name("legislatures"), path)],
        scripts=_scripts(("../data/stategov.js", "../assets/kyc-stategov.js")),
    )


def _local_kinds():
    """The Census of Governments' kinds, as the guide's map words them
    (government_maps.LOCAL_KINDS, one table): ``[(key, column, none)]``,
    the total first - the figure a reader came for, which as the last of
    seven columns sat off a 1280px screen. A count of school districts is
    of *independent* ones; a state with none runs its schools as dependent
    systems."""
    from .government_maps import LOCAL_KINDS, NONE_OF_KIND

    kinds = [k for k in LOCAL_KINDS if k[0] == "total"] + [k for k in LOCAL_KINDS if k[0] != "total"]
    return [(key, "All local governments" if key == "total" else title.split(":")[0],
             NONE_OF_KIND.get(key, f"No {plural}."))
            for key, _short, title, _one, plural in kinds]


# Each kind of local government's tone on the directory's bars: category
# colours, never a party's (rule 49), in the table's order of kinds.
LOCAL_TONES = {"county": "lg-county", "municipal": "lg-municipal", "township": "lg-township",
               "school": "lg-school", "special": "lg-special"}


def local_bar(name, counts, kinds):
    """One state's local governments as one bar, a part per kind as wide as
    its share of the total (VISUALS-32). A kind the Census marks "X" - the
    state has none - is no part of the bar but a word under it, "none":
    never a zero-length part a reader cannot see (rule 49). *kinds* is
    ``[(key, words, none)]`` without the total. "" with no total."""
    total = (counts or {}).get("total")
    if not total:
        return ""
    present = [(k, w, counts[k]) for k, w, _n in kinds if counts.get(k)]
    absent = [w.lower() for k, w, _n in kinds if counts.get(k) is None]
    spoken = (f"{name}: {total:,} local governments: "
              + ", ".join(f"{n:,} {w.lower()}" for _k, w, n in present)
              + (f"; none of: {', '.join(absent)}" if absent else "") + ".")
    parts = "".join(
        f'<span class="lg-seg {LOCAL_TONES[k]}" style="width:{100 * n / total:.3f}%"></span>'
        for k, _w, n in present)
    return (f'<span class="lg-bar" role="img" aria-label="{_e(spoken)}" title="{_e(spoken)}">{parts}</span>'
            + (f'<span class="lg-none">None: {_e(", ".join(absent))}</span>' if absent else ""))


def render_counties_index(host, census=None, dates=None):
    """Every state's local governments, counted by kind as the Census of
    Governments counts them, each state linked to its counties page. A
    state with none of a kind (an "X" in the Census table) reads "none",
    with what that means, never 0 (rule 49)."""
    from . import county_areas
    from .government import jump_options
    from .government_maps import COUNT_NOTES, STATES

    path = "counties/index.html"
    canonical = f"https://{host}/{path}" if host else path
    counts = (census or {}).get("states") or {}
    kinds = _local_kinds()
    # A state whose county areas are not all governed by a county says why,
    # in a numbered note under the table: "none" for Rhode Island, and 5 for
    # Massachusetts's fourteen counties, are otherwise a puzzle (rule 71).
    notes = [(code, county_areas.directory_note(code)) for code in sorted(STATES, key=state_name)]
    notes = [(code, text) for code, text in notes if text]
    number = {code: i + 1 for i, (code, _text) in enumerate(notes)}

    def cell(code, kind, none):
        value = (counts.get(code) or {}).get(kind)
        mark = (f'<sup><a class="note-ref" href="#county-note-{_e(code.lower())}" '
                f'aria-label="Note {number[code]}">{number[code]}</a></sup>'
                if kind == "county" and code in number else "")
        if value is None:
            return (f'<td class="faint" title="{_e(none)}">none{mark}</td>' if code in counts
                    else "<td>&ndash;</td>")
        if (code, kind) in COUNT_NOTES:
            mark += (f'<sup><a class="note-ref" href="#count-note-{_e(code.lower())}-{_e(kind)}" '
                     f'aria-label="What this count is">*</a></sup>')
        return f"<td>{value:,}{mark}</td>"

    parts = [k for k in kinds if k[0] != "total"]
    rows = "\n".join(
        f'                        <tr><th scope="row"><a href="{_e(code.lower())}.html">'
        f'{_e(state_name(code))}</a>{local_bar(state_name(code), counts.get(code), parts)}</th>'
        + "".join(cell(code, k, n) for k, _w, n in kinds) + "</tr>"
        for code in sorted(STATES, key=state_name))
    # What the bars' tones are, once, above the table.
    key = ('                <p class="lg-key">' + "".join(
        f'<span class="lg-key-item"><span class="lg-seg {LOCAL_TONES[k]}" aria-hidden="true"></span>'
        f"{_e(w)}</span>" for k, w, _n in parts)
        + '<span class="lg-key-item">Each bar is a state&#8217;s governments, by kind; '
        "&#8220;None&#8221; names a kind the state does not have.</span></p>")
    year = (census or {}).get("year")
    # D.C. and the territories are not in the table, and it says why. D.C.'s
    # count is the same table's, as the guide's map shows it; the scope is
    # the guide's (government_maps: "the Census of Governments covers the
    # states and D.C.").
    dc = counts.get("DC") or {}
    dc_kinds = [(dc.get(k), w) for k, w in (("municipal", "municipal government"),
                                             ("special", "special district")) if dc.get(k)]
    outside = ("The District of Columbia has no counties, so it is not in this table" +
               (f"; the Census Bureau counted {dc['total']:,} local governments there"
                f"{' in ' + _e(year) if year else ''}: " +
                " and ".join(f"{n:,} {w}{'' if n == 1 else 's'}" for n, w in dc_kinds)
                if dc.get("total") else "") +
               ". The five territories are outside the Census of Governments, which covers the "
               "states and D.C.")
    main = "\n".join([
        '            <div id="countiesDirectory" class="state-page directory-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">Counties &amp; local governments</p>',
        '                    <h1 class="state-title">Every state&#8217;s local governments</h1>',
        '                    <p class="districts-lede">Counties, cities and towns, townships, school',
        '                        districts and special districts, as the Census Bureau counted them'
        + (f" in {_e(year)}" if year else "") + '. Pick a state for its counties on a map and every',
        '                        government in each.</p>',
        '                    <p class="state-links">',
        f'                        <a class="btn" href="{_e(_learn("local"))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> {_e(_guide_name("local"))}</a>',
        '                        <a class="btn" href="../states/index.html"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> States &amp; territories</a>',
        "                    </p>",
        "                </header>",
        key,
        '                <div class="directory-scroll" tabindex="0" role="region" aria-label="Local governments by state">',
        '                    <table class="directory-table directory-wrap">',
        '                        <thead><tr><th scope="col">State</th>' +
        "".join(f'<th scope="col">{_e(words)}</th>' for _k, words, _n in kinds) + "</tr></thead>",
        "                        <tbody>",
        rows,
        "                        </tbody>",
        "                    </table>",
        "                </div>",
        *[f'                <p class="faint" id="count-note-{_e(code.lower())}-{_e(kind)}">* '
          f'{_e(state_name(code))}, {_e(dict((k, w) for k, w, _n in kinds)[kind].lower())}: '
          f"{_e(text)}</p>" for (code, kind), text in sorted(COUNT_NOTES.items())],
        f'                <p class="faint directory-outside">{_e(outside)}</p>',
        '                <h2 class="state-heading" id="countyNotes">Where a county area has no county government</h2>',
        '                <p class="faint">A state can have fewer county governments than counties. '
        "These are the places the Census Bureau lists as county areas without one, and what governs "
        "them instead.</p>",
        '                <ol class="directory-notes">',
        *[f'                    <li id="county-note-{_e(code.lower())}"><a href="{_e(code.lower())}.html">'
          f"{_e(state_name(code))}</a>: {_e(text)}</li>" for code, text in notes],
        "                </ol>",
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Source:</strong> the U.S. Census Bureau's Census of Governments"
        + (f" ({_e(year)})" if year else "") + ", which counts every",
        f"                    local government by state and kind{_when(dates, 'census', '; its table read on ')}."
        ' "None" is a state with no',
        "                    government of that kind: one with no county governments has none, and",
        "                    one with no independent school districts runs its schools as dependent",
        "                    systems of the state, a county or a city. County areas without a county",
        "                    government, and what governs them: "
        f'<a href="{_e(county_areas.SOURCES["isd"][1])}" rel="noopener">{_e(county_areas.SOURCES["isd"][0])}</a>.</p>',
    ])
    return render_page(
        title=_e("Counties & local governments — Know Your Candidate"),
        og_title=_e("Every state's local governments, counted"),
        description=_e("Every state's counties, cities and towns, townships, school districts and "
                       "special districts, as the Census counts them, with a map of each state."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="local",
        search="",
        sidebar="",
        nav_current="local",
        jump_options=jump_options(STATES),
        jump_attrs=' data-jump-to="counties/{code}.html"',
        main=main,
        footer=footer,
        built=_read_span(dates, "census"),
        crumbs=[_HOME, (section_name("local"), path)],
        scripts="",
    )


def _possessive(name):
    return name + ("'" if name.endswith("Islands") else "'s")


# States whose map is unchanged but nearly was, where a reader may have read
# otherwise. Each clause is on the record of the court that decided it.
UNCHANGED_NOTES = {
    "MO": ("A map passed in 2025 was suspended by a referendum petition, and the courts "
           "have kept these districts in place for 2026."),
    # Voters approved the amendment on April 21, 2026 (51.7% to 48.3%); the
    # Supreme Court of Virginia struck it down 4-3 on May 8, 2026, for want
    # of an intervening general election between the legislature's two
    # passages (Va. Const. art. XII, sec. 1); the U.S. Supreme Court denied
    # an emergency application on May 15, 2026. Virginia Mercury, 2026-05-08
    # and 2026-05-18; NPR, 2026-05-15; CNN, 2026-05-15.
    "VA": ("Voters approved a redistricting amendment on April 21, 2026, but the Supreme "
           "Court of Virginia struck it down on May 8 and the U.S. Supreme Court declined to "
           "intervene, leaving these districts in place."),
}


def district_page_text(code, seats=None):
    """``(headline, introduction)`` for a state's district page."""
    from .districts import REDRAWN

    if code in REDRAWN:
        return REDRAWN[code]["headline"], REDRAWN[code]["intro"]
    name = state_name(code)
    if code == "PR":
        return (f"{_possessive(name)} seat in the House",
                "Puerto Rico elects a non-voting resident commissioner to the House, at "
                "large, for a four-year term. The seat is not on the ballot in 2026.")
    if code in TERRITORIES:
        return (f"{_possessive(name)} seat in the House",
                f"{name} elects a non-voting delegate to the House, at large.")
    if seats == 1:
        return (f"{_possessive(name)} seat in the House",
                f"{name} elects one member of the House, at large: the whole state is "
                f"one district.")
    intro = (f"{name} elects {seats} members of the House, one from each district below. "
             f"These are the districts of the 2024 election, and they are used again in "
             f"2026." if seats else
             f"{name}'s House districts, as used in 2024 and again in 2026.")
    if code in UNCHANGED_NOTES:
        intro += " " + UNCHANGED_NOTES[code]
    return f"{_possessive(name)} House districts", intro


def render_district_page(code, host, summary=None):
    """A state's House districts - and, where the map was redrawn, both maps.

    The introduction is static, so the page says what it is without
    JavaScript; the maps and every claim about a person are rendered by
    ``assets/kyc-districts.js`` from the state's map file and profiles.js.
    """
    from .districts import REDRAWN, page_path as district_path
    from .government_maps import STATES

    name = state_name(code)
    info = ((summary or {}).get("states") or {}).get(code) or {}
    seats = info.get("house") or info.get("delegates") or None
    headline, intro = district_page_text(code, seats)
    path = district_path(code)
    canonical = f"https://{host}/{path}" if host else path
    if code in REDRAWN:
        description = (f"{name}'s House districts under the 2024 map and the map for 2026, "
                       f"side by side: who holds each seat, who is running where, and how "
                       f"much of each new district came from each old one.")
    else:
        description = (f"{name}'s House districts on a map: who holds each seat and who is "
                       f"on the November 2026 ballot.")
    main = "\n".join([
        '            <div id="districtsContent" class="state-page districts-page">',
        '                <header class="state-hero">',
        f'                    <p class="state-kicker">{"Redistricting" if code in REDRAWN else "District map"}</p>',
        f'                    <h1 class="state-title">{_e(headline)}</h1>',
        f'                    <p class="districts-lede">{_e(intro)}</p>',
        '                    <p class="state-links">',
        f'                        <a class="btn" href="../{_e(page_path(code))}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> '
        f'{_e(name)} page</a>',
        '                        <a class="btn" href="index.html">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-map"/></svg> {DISTRICTS_INDEX_NAME}</a>',
        f'                        <a class="btn" href="{_e(_learn("congress#house"))}">'
        '<svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> How the House works</a>',
    ] + ([
        # Every state - not D.C. or a territory - has a legislature and a
        # counties page.
        f'                        <a class="btn" href="../legislature/{_e(code.lower())}.html">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> State legislature</a>',
        f'                        <a class="btn" href="../counties/{_e(code.lower())}.html">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-layers"/></svg> Counties &amp; local governments</a>',
    ] if code in STATES else []) + [
        '                    </p>',
        '                </header>',
        '                <div id="districtsApp">',
        '                    <p class="results-bar" role="status">Loading the map&hellip;</p>',
        '                </div>',
        '            </div>',
    ])
    scripts = [s.replace("{code}", code.lower()) for s in _DISTRICT_SCRIPTS]
    return render_page(
        title=_e(f"{headline} — Know Your Candidate"),
        og_title=_e(headline),
        description=_e(description),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="districts",
        nav_current="states",
        nav_how="true",
        search_placeholder=_e(f"Search {name} profiles…"),
        main=main,
        scripts=_scripts(scripts),
        crumbs=[_HOME, (section_name("states"), "states/index.html"), (name, page_path(code)),
                (headline, path)],
    )


_LEGISLATURE_SIDEBAR = """
        <div class="sidebar-section">
            <h2 class="sidebar-heading">State legislatures</h2>
            <p class="sidebar-note">Every state's districts and the members who sit for
                them, from Open States and the Census Bureau.</p>
        </div>
"""


def render_legislature_page(code, host, summary=None, dates=None):
    """A state's legislature: its Senate and House districts on a map, and
    the members who sit for them. The page carries the state code only;
    ``assets/kyc-legislature.js`` draws it from ``data/legislature/<st>.js``."""
    from .government_maps import LEGISLATURE_NAME, LOWER_CHAMBER, SEATS, STATES
    from .government import jump_options

    name = state_name(code)
    path = f"legislature/{code.lower()}.html"
    canonical = f"https://{host}/{path}" if host else path
    senate, house = SEATS[code]
    lower = LOWER_CHAMBER.get(code, "House of Representatives")
    if code == "NE":
        title = "Nebraska Legislature"
        lede = (f"Nebraska's Legislature has one chamber of {senate} members, called "
                f"senators, each elected from a district on a nonpartisan ballot.")
        chambers = ""
    else:
        title = f"{name} {LEGISLATURE_NAME.get(code, 'Legislature')}"
        lede = (f"The {name} Senate has {senate} members and the {lower} {house}. Pick a "
                f"district on the map to see who sits for it.")
        chambers = "\n".join([
            '                    <div class="segmented" role="group" aria-label="Chamber">',
            '                        <button type="button" data-chamber="upper" aria-pressed="true">Senate</button>',
            f'                        <button type="button" data-chamber="lower" aria-pressed="false">{_e(lower)}</button>',
            "                    </div>",
        ])
    from .legislature import STATE_NOTES
    note = STATE_NOTES.get(code)
    # Each colour the map can draw, keyed so the page hides the ones a
    # chamber does not use. Nebraska elects its Legislature without party
    # labels: its map is one neutral, said in one line, and a seat with
    # nobody listed is its own entry everywhere (audit 2026-10-17,
    # STATEGOV-06).
    keys = ([("n", "Nonpartisan: senators are elected without party labels")] if code == "NE" else
            [("r", "Republican"), ("d", "Democratic"), ("i", "Independent or other"),
             ("split", "Members of more than one party"), ("n", "Nonpartisan")])
    keys.append(("none", "Nobody listed"))
    legend = "\n".join(
        f'                        <span class="key" data-key="{key}"><span class="swatch party-fill-{key}">'
        f"</span>{_e(text)}</span>" for key, text in keys)
    main = "\n".join(line for line in [
        '            <div id="legislatureContent" class="state-page legislature-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">State legislature</p>',
        f'                    <h1 class="state-title">{_e(title)}</h1>',
        f'                    <p class="districts-lede">{_e(lede)}</p>',
        # A state whose lines changed after the Census captured them says so.
        (f'                    <p class="guide-note">{_e(note[0])} <a href="{_e(note[1])}" '
         f'target="_blank" rel="noopener noreferrer">Source</a></p>') if note else None,
        '                    <p class="state-links">',
        f'                        <a class="btn" href="../{_e(page_path(code))}"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> {_e(name)} page</a>',
        f'                        <a class="btn" href="../districts/{_e(code.lower())}.html"><svg class="icon" aria-hidden="true"><use href="#i-map"/></svg> Congressional districts</a>',
        f'                        <a class="btn" href="../counties/{_e(code.lower())}.html"><svg class="icon" aria-hidden="true"><use href="#i-layers"/></svg> Counties &amp; local governments</a>',
        f'                        <a class="btn" href="{_e(_learn("states"))}"><svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> {_e(_guide_name("states"))}</a>',
        "                    </p>",
        "                </header>",
        _findrep_slot(code, "legMap"),
        '                <div class="toolbar legislature-toolbar">',
        chambers,
        '                    <div class="party-legend" aria-label="Colours">',
        legend,
        "                    </div>",
        "                </div>",
        '                <div class="leg-layout">',
        '                    <div class="leg-map-card">',
        # One square per seat, above the map (kyc-legislature.js seats()).
        '                    <div id="legSeats" class="leg-seats"></div>',
        '                    <div id="legMap" class="leg-map">',
        '                        <p class="results-bar" role="status">Loading the map&hellip;</p>',
        "                    </div></div>",
        '                    <aside class="leg-panel" aria-live="polite">',
        '                        <h2 class="leg-panel-title" id="legPanelTitle"></h2>',
        '                        <div id="legPanelBody"></div>',
        "                    </aside>",
        "                </div>",
        '                <section class="leg-roster-section" aria-labelledby="legRosterTitle">',
        '                    <h2 class="state-heading" id="legRosterTitle">Every district</h2>',
        '                    <div id="legRoster" class="leg-roster"></div>',
        "                </section>",
        "            </div>",
    ] if line is not None)
    footer = "\n".join([
        "                <p><strong>Sources:</strong> members, their parties, districts and contact",
        "                    details from Open States (its data is CC0), as each legislature publishes",
        f"                    them{_when(dates, 'openstates')}; portraits as each legislature publishes",
        "                    them, on its own site; district boundaries from the U.S. Census Bureau's",
        "                    cartographic boundary files, as set for the 2024 elections. A seat with",
        "                    nobody listed may be vacant, or Open States may be behind a special",
        "                    election. The legislature is called by the name its state constitution",
        "                    gives it.</p>",
    ])
    scripts = [s.replace("{code}", code.lower()) for s in (
        "../data/legislature/{code}.js", "../data/lookup/index.js", "../assets/kyc-regionmap.js",
        "../assets/kyc-findrep.js", "../assets/kyc-legislature.js")]
    return render_page(
        title=_e(f"{title} — Know Your Candidate"),
        og_title=_e(f"{title}: every district and member"),
        description=_e(f"Every {name} state legislative district on a map, and the members "
                       f"who sit for them: party, contact details and links."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="legislature",
        nav_current="legislatures",
        nav_how="true",
        search="",
        sidebar=_LEGISLATURE_SIDEBAR,
        jump_options=jump_options(STATES),
        jump_attrs=' data-jump-to="legislature/{code}.html"',
        main=main,
        footer=footer,
        built=_read_span(dates, "openstates"),
        crumbs=[_HOME, (section_name("legislatures"), "legislature/index.html"), (title, path)],
        scripts=_scripts(scripts),
    )


_FEDERAL_SIDEBAR = """
        <nav class="sidebar-section" aria-label="Federal government">
            <h2 class="sidebar-heading">Federal government</h2>
            <p class="sidebar-note">Who holds the federal government's offices now, each from the
                office's own record: the President, the Vice President and the Cabinet, the
                Supreme Court, and every sitting Article III judge.</p>
            <a class="nav-link nav-sub" href="../federal/index.html#executive">The President and Vice President</a>
            <a class="nav-link nav-sub" href="../federal/index.html#cabinet">The Cabinet</a>
            <a class="nav-link nav-sub" href="../federal/index.html#changes">Changes since the term began</a>
            <a class="nav-link nav-sub" href="../federal/index.html#supreme-court">The Supreme Court</a>
            <a class="nav-link nav-sub" href="../federal/index.html#courts">The federal courts</a>
        </nav>
"""

def _federal_footer(dates=None):
    """The federal hub's sources, each dated as its cache records it."""
    return "\n".join([
        "                <p><strong>Sources:</strong> the President and Vice President from",
        "                    congress-legislators' record of their terms; the Cabinet as the White House",
        "                    lists it, each officer checked on their office's own page and against the",
        f"                    Senate's roll-call vote confirming them{_when(dates, 'executive')}; every",
        "                    Article III judge from the Federal Judicial Center's Biographical Directory,",
        "                    and the Supreme Court's members as the Court lists them"
        f"{_when(dates, 'judiciary')}; vacancies as the courts list them on",
        f"                    uscourts.gov{_when(dates, 'vacancies')}. Judges are shown with the",
        "                    president who appointed them, never with a party.</p>",
    ])


def _court_footer(court, dates=None, own=None):
    """A court page's own sources: the judges' directory and the vacancy
    lists, never the President's and the Cabinet's, which it does not show
    (FEDERAL-14). A territorial court's judges are not in the directory:
    they are listed as the court's own website names them (*own*, the
    court's ``courtList``), and that site is the source."""
    read = _when(dates, "judiciary")
    if court["kind"] == "territorial" and (own or {}).get("judges"):
        judges = (f'                    the judges as <a href="{_e(own["source"])}">the court&#8217;s own '
                  f"website</a> lists them, read {_e(date_words(own['read']))} (the Federal Judicial",
                  "                    Center's Biographical Directory lists Article III judges only)")
    elif court["kind"] == "supreme":
        judges = ("                    the justices as the Supreme Court lists its members, with each",
                  "                    one's record from the Federal Judicial Center's Biographical Directory"
                  + read)
    elif court["kind"] == "territorial":
        # The date belongs to the directory, not to the absence it
        # explains; and a page that lists no judges says nothing of how
        # judges are shown.
        judges = ("                    the Federal Judicial Center's Biographical Directory" + read
                  + ", which lists",
                  "                    Article III judges only, so this court's judges are not listed")
    else:
        judges = ("                    every sitting judge from the Federal Judicial Center's Biographical",
                  "                    Directory" + read)
    shown = ("" if court["kind"] == "territorial" else
             " Judges are shown with the president who appointed them, never with a party.")
    if court["kind"] == "territorial" and (own or {}).get("judges"):
        shown = " Judges are shown with the title the court gives them, never with a party."
    return "\n".join([
        "                <p><strong>Sources:</strong>",
        *judges[:-1],
        judges[-1] + "; vacancies, announced vacancies and",
        "                    judicial emergencies as the courts list them on uscourts.gov"
        f"{_when(dates, 'vacancies')}.{shown}</p>",
    ])


def _jump(codes):
    """The "Jump to" list, written into the page: these pages load no build
    metadata to fill it."""
    from .government import jump_options
    return jump_options(codes)


_FEDERAL_SCRIPTS = (
    "../data/federal.js",
    "../data/judiciary/index.js",
    "../data/geo.js",
    "../assets/kyc-official.js",
    "../assets/kyc-usmap.js",
    "../assets/kyc-federal.js",
)


def _prerendered(rows, note):
    """The page's first contents, written into its HTML so a reader without
    script, and a crawler, see the names (FEDERAL-12); the page's own module
    draws the full view over them from the same data."""
    return "\n".join(['                <div class="fed-prerendered">'] + rows + [
        f'                    <p class="faint">{note}</p>', "                </div>"])


def _federal_static(federal):
    """The hub's names, as plain lists, from the payload ``data/federal.js``
    holds (kyc/federal_build.py)."""
    if not federal:
        return '                    <p class="results-bar" role="status">Loading&hellip;</p>'
    rows = ['                    <h2 class="guide-subheading">The President and Vice President</h2>',
            '                    <ul class="fed-static">']
    for key in ("president", "vicePresident"):
        person = federal[key]
        rows.append(f"                        <li>{_e(person['office'])}: {_e(person['name'])}</li>")
    rows += ["                    </ul>",
             '                    <h2 class="guide-subheading">The Cabinet</h2>',
             '                    <ul class="fed-static">']
    for office in federal["offices"]:
        holder = office.get("holder")
        rows.append(f"                        <li>{_e(office['office'])}: "
                    + (_e(holder["name"]) if holder else "nobody listed by the White House") + "</li>")
    rows += ["                    </ul>",
             '                    <h2 class="guide-subheading">The Supreme Court</h2>',
             '                    <ul class="fed-static">']
    for justice in federal["supremeCourt"]["members"]:
        role = (justice.get("justice") or {}).get("role") or "Justice"
        rows.append(f"                        <li>{_e(role)}: {_e(justice['name'])}</li>")
    rows += ["                    </ul>",
             '                    <h2 class="guide-subheading">The federal courts</h2>',
             '                    <ul class="fed-static">']
    for court in federal["courts"]:
        if court["kind"] == "supreme":
            continue
        chief = f" (chief judge: {_e(court['chief']['name'])})" if court.get("chief") else ""
        rows.append(f'                        <li><a href="../courts/{_e(court["id"])}.html">'
                    f"{_e(court['name'])}</a>{chief}</li>")
    rows.append("                    </ul>")
    return _prerendered(rows, f"Names as of {_e(date_words(federal['asOf']['executive']))}. "
                              f"This is a plain list: the full page could not be shown.")


def _court_static(court_id, federal, court):
    """One court's judges, as a plain table, from its data file's payload."""
    if not federal or not court:
        return '                    <p class="results-bar" role="status">Loading&hellip;</p>'
    if not court["listed"]:
        own = court.get("courtList") or {}
        rows = ['                    <p>This court&#8217;s judges serve ten-year terms under '
                "Article IV and are not in the Federal Judicial Center&#8217;s directory of "
                "Article III judges"
                + (", so they are named as the court&#8217;s own website lists them.</p>"
                   if own.get("judges") else ".</p>")]
        if own.get("judges"):
            rows.append('                    <ul class="fed-static">')
            rows += [f"                        <li>{_e(j['title'])}: {_e(j['name'])}</li>"
                     for j in own["judges"]]
            rows.append("                    </ul>")
    else:
        rows = ['                    <table class="guide-table fed-table">',
                '                        <thead><tr><th scope="col">Judge</th><th scope="col">Title</th>'
                '<th scope="col">Appointed by</th><th scope="col">Status</th></tr></thead>',
                "                        <tbody>"]
        for judge in court["judges"] + court.get("retired", []):
            seat = next((s for s in judge.get("seats") or [] if s.get("court") == court_id),
                        (judge.get("seats") or [{}])[0])
            title = (judge.get("justice") or {}).get("role") or seat.get("title") or "Judge"
            # Senior by the courts' list and active by the directory: both
            # said, as the full page says them (kyc/vacancies.py).
            status = ("Retired justice" if judge.get("retiredJustice")
                      else "Senior status" if judge.get("status") == "senior"
                      else ("Senior status by the courts&#8217; list (the FJC directory still "
                            "lists active service)") if judge.get("listedSenior")
                      else "Active")
            name = (f'<a href="{_e(judge["fjc"])}">{_e(judge["name"])}</a>' if judge.get("fjc")
                    else _e(judge["name"]))
            rows.append(f"                            <tr><th scope=\"row\">{name}</th>"
                        f'<td data-label="Title">{_e(title)}</td>'
                        f'<td data-label="Appointed by">{_e(seat.get("appointedBy") or "")}</td>'
                        f'<td data-label="Status">{status}</td></tr>')
        rows += ["                        </tbody>", "                    </table>"]
    site = next((c.get("site") for c in federal["courts"] if c["id"] == court_id), None)
    if site:
        rows.append(f'                    <p>The court&#8217;s website: <a href="{_e(site)}">{_e(site)}</a></p>')
    if court["listed"]:
        note = (f"From the Federal Judicial Center&#8217;s directory as of "
                f"{_e(date_words(federal['asOf']['judiciary']))}")
    elif (court.get("courtList") or {}).get("judges"):
        note = f"From the court&#8217;s own website, read {_e(date_words(court['courtList']['read']))}"
    else:
        note = "The court&#8217;s own list of its judges could not be read"
    return _prerendered(rows, note + ". This is a plain list: the full page could not be shown.")


def render_federal_page(host, codes=(), dates=None, federal=None):
    """The federal government's hub: the President, the Vice President, the
    Cabinet, the Supreme Court and every federal court.
    ``assets/kyc-federal.js`` draws it from ``data/federal.js``; with that
    payload (*federal*), the names are written into the HTML too, for a
    reader without script and for a crawler (FEDERAL-12)."""
    path = "federal/index.html"
    canonical = f"https://{host}/{path}" if host else path
    main = "\n".join([
        '            <div id="federalContent" class="state-page federal-page" data-federal="hub">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">Federal government</p>',
        '                    <h1 class="state-title">Who holds the federal government&#8217;s offices</h1>',
        '                    <p class="districts-lede">The President and Vice President, the Cabinet, the',
        '                        Supreme Court and every sitting Article III judge, each from the',
        '                        office&#8217;s own record. Pick a name for the person&#8217;s record.</p>',
        '                    <p class="state-links">',
        f'                        <a class="btn" href="{_e(_learn("executive"))}"><svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> {_e(_guide_name("executive"))}</a>',
        f'                        <a class="btn" href="{_e(_learn("courts"))}"><svg class="icon" aria-hidden="true"><use href="#i-scale"/></svg> {_e(_guide_name("courts"))}</a>',
        "                    </p>",
        "                </header>",
        '                <div id="federalBody">',
        _federal_static(federal),
        "                </div>",
        "            </div>",
    ])
    return render_page(
        title=_e("Federal government — Know Your Candidate"),
        og_title=_e("The federal government: who holds each office"),
        description=_e("The President, the Vice President, the Cabinet, the Supreme Court and "
                       "every sitting Article III judge, each from the office's own record."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="federal",
        search="",
        sidebar=_FEDERAL_SIDEBAR,
        nav_current="executive",
        jump_options=_jump(codes),
        main=main,
        footer=_federal_footer(dates),
        footer_dated=True,
        built=_read_span(dates, "executive", "judiciary", "vacancies"),
        crumbs=[_HOME, ("Federal government", path)],
        scripts=_scripts(_FEDERAL_SCRIPTS),
    )


def _learn(target):
    """The address, from a page one folder down, of a section of the guide:
    ``"courts#appeals"`` -> ``"../government/courts.html#appeals"``. Raises
    for a page or section the guide does not have, so a "how this works"
    link cannot lead nowhere (rule 47)."""
    from . import government

    url, _external = government.href("guide:" + target, "index")
    return "../government/" + url


def _guide_name(slug):
    """A guide page's one name, for a link to the whole page (rule 75):
    the federal page called the executive's "How the executive works", the
    page itself "The president and the executive branch"."""
    from . import government

    return government.name(slug)


# Where the guide explains each kind of federal court, and what to call it.
_COURT_SECTIONS = {"supreme": "supreme-court", "appeals": "appeals", "district": "district",
                   "territorial": "other-courts", "trade": "district"}
_COURT_WORDS = {"supreme": "How the Supreme Court works",
                "appeals": "How the courts of appeals work",
                "district": "How the district courts work",
                "territorial": "How the territorial courts work",
                "trade": "How the federal trial courts work"}


def _court_og_title(court, own=None):
    """A court page's share title: a territorial court's page lists judges
    only when the court's own website was read (*own*)."""
    if court["kind"] == "territorial" and (own or {}).get("judges"):
        return f"{court['name']}: its judges, as the court lists them"
    if court["kind"] == "territorial":
        return f"{court['name']}: its vacancies"
    if court["kind"] == "supreme":
        return f"{court['name']}: its justices"
    return f"{court['name']}: its judges"


def _court_description(court, own=None):
    """What a court page holds, said for its kind: a territorial court's
    judges are not in the directory the pages are built from - they are
    named as the court's own website lists them (*own*) - and a justice
    does not take senior status. The territorial courts' ten-year terms are
    the guide's checked text (``government_text``, "other-courts")."""
    name = court["name"]
    if court["kind"] == "territorial" and (own or {}).get("judges"):
        chief = next((j["name"] for j in own["judges"] if j.get("chief")), None)
        return (f"The {name}: an Article IV court whose judges serve ten-year terms, named as "
                f"the court's own website lists them (read {date_words(own['read'])})."
                + (f" Chief judge: {chief}." if chief else "")
                + " Its vacancies, as the courts list them.")
    if court["kind"] == "territorial":
        return (f"The {name}: an Article IV court whose judges serve ten-year terms. The Federal "
                f"Judicial Center's directory lists Article III judges only, so its judges are "
                f"not listed; its vacancies are, as the courts list them.")
    if court["kind"] == "supreme":
        return (f"Every justice of the {name}, as the Court lists them: who appointed them, "
                f"when they were commissioned, and their background. Retired justices listed apart.")
    return (f"Every sitting judge of the {name}: who appointed them, when they were "
            f"commissioned, their senior status, and their background.")


def _court_counts(court_id, federal):
    """The chief and the counts, for a court page's description, as the
    hub's index gives them; nothing without the payload."""
    found = next((c for c in (federal or {}).get("courts") or [] if c["id"] == court_id), None)
    if not found or not found["listed"] or found["kind"] == "supreme":
        return ""
    chief = f" Chief judge: {found['chief']['name']}." if found.get("chief") else ""
    return (f"{chief} {found['active']} active and {found['senior']} senior judges as of "
            f"{date_words(federal['asOf']['judiciary'])}.")


def render_court_page(court_id, host, codes=(), dates=None, federal=None,
                      court_data=None):
    """One federal court: its judges, the chief first, then active and senior
    judges. ``assets/kyc-federal.js`` draws it from the court's data file;
    with the hub's payload and the court's (*federal*, *court_data*), its
    judges are written into the HTML too (FEDERAL-12)."""
    from .federal_courts import COURTS, KINDS

    court = COURTS[court_id]
    path = f"courts/{court_id}.html"
    canonical = f"https://{host}/{path}" if host else path
    main = "\n".join([
        f'            <div id="federalContent" class="state-page federal-page" data-federal="court" data-court="{_e(court_id)}">',
        '                <header class="state-hero">',
        f'                    <p class="state-kicker">{_e(KINDS[court["kind"]])}</p>',
        f'                    <h1 class="state-title">{_e(court["name"])}</h1>',
        '                    <p class="state-links">',
        '                        <a class="btn" href="../federal/index.html#courts"><svg class="icon" aria-hidden="true"><use href="#i-scale"/></svg> The federal courts</a>',
        f'                        <a class="btn" href="{_e(_learn("courts#" + _COURT_SECTIONS[court["kind"]]))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> {_e(_COURT_WORDS[court["kind"]])}</a>',
        "                    </p>",
        "                </header>",
        '                <div id="federalBody">',
        _court_static(court_id, federal, court_data),
        "                </div>",
        "            </div>",
    ])
    scripts = ("../data/federal.js", f"../data/judiciary/{court_id}.js",
               "../assets/kyc-official.js", "../assets/kyc-federal.js")
    return render_page(
        title=_e(f"{court['name']} — Know Your Candidate"),
        og_title=_e(_court_og_title(court, (court_data or {}).get("courtList"))),
        description=_e(_court_description(court, (court_data or {}).get("courtList"))
                       + _court_counts(court_id, federal)),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="court",
        search="",
        sidebar=_FEDERAL_SIDEBAR,
        nav_current="courts",
        nav_how="true",
        jump_options=_jump(codes),
        main=main,
        footer=_court_footer(court, dates, (court_data or {}).get("courtList")),
        footer_dated=True,
        built=_read_span(dates, "judiciary", "vacancies"),
        crumbs=[_HOME, (section_name("courts"), "courts/index.html"), (court["name"], path)],
        scripts=_scripts(scripts),
    )


_COUNTIES_SIDEBAR = """
        <div class="sidebar-section">
            <h2 class="sidebar-heading">Counties &amp; local governments</h2>
            <p class="sidebar-note">Every county, city, township, school district and special
                district, from the Census Bureau's 2022 Census of Governments.</p>
        </div>
"""


def render_counties_page(code, host, listed=None):
    """A state's counties and every local government in each. The page
    carries the state code only; ``assets/kyc-local.js`` draws it from
    ``data/local/<st>.js``."""
    from . import county_areas
    from .government import jump_options
    from .government_maps import STATES

    name = state_name(code)
    path = f"counties/{code.lower()}.html"
    canonical = f"https://{host}/{path}" if host else path
    title = f"{name}: counties and local governments"
    # What the state's map areas are called: parishes, boroughs and census
    # areas, planning regions (kyc/county_areas.py).
    one, many, button = county_areas.words(code)
    a_one = ("an " if one[0] in "aeiou" else "a ") + one
    why = [county_areas.SOURCES["isd"]] + ([county_areas.SOURCES["ct-fr"]] if code == "CT" else [])
    main = "\n".join([
        '            <div id="localContent" class="state-page local-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">Counties &amp; local governments</p>',
        f'                    <h1 class="state-title">{_e(name)}</h1>',
        f'                    <p class="districts-lede">Every {_e(one)}, city and town, township, school '
        f'district and special district, as the Census Bureau counted them in 2022. Pick {_e(a_one)} to '
        'see every government in it, or switch to cities and towns to find one place and its '
        'government, with a link to its own site where the Census lists one.</p>',
        '                    <p class="state-links">',
        f'                        <a class="btn" href="../{_e(page_path(code))}"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> {_e(name)} page</a>',
        f'                        <a class="btn" href="../legislature/{_e(code.lower())}.html"><svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> State legislature</a>',
        f'                        <a class="btn" href="../districts/{_e(code.lower())}.html"><svg class="icon" aria-hidden="true"><use href="#i-map"/></svg> Congressional districts</a>',
        f'                        <a class="btn" href="{_e(_learn("local"))}"><svg class="icon" aria-hidden="true"><use href="#i-layers"/></svg> {_e(_guide_name("local"))}</a>',
        "                    </p>",
        "                </header>",
        _findrep_slot(code, "localMap"),
        '                <div class="segmented" role="group" aria-label="Map view">',
        f'                    <button type="button" data-view="counties" aria-pressed="true">{_e(button)}</button>',
        '                    <button type="button" data-view="cities" aria-pressed="false">Cities &amp; towns</button>',
        "                </div>",
        f'                <div class="party-legend" id="countyLegend" aria-label="Local governments per {_e(one)}">',
        f'                    <span class="party-legend-title">Local governments in each {_e(one)}</span>',
        '                    <span class="key"><span class="swatch region-fill-scale-1"></span>Fewer than 10</span>',
        '                    <span class="key"><span class="swatch region-fill-scale-2"></span>10&ndash;24</span>',
        '                    <span class="key"><span class="swatch region-fill-scale-3"></span>25&ndash;49</span>',
        '                    <span class="key"><span class="swatch region-fill-scale-4"></span>50&ndash;99</span>',
        '                    <span class="key"><span class="swatch region-fill-scale-5"></span>100 or more</span>',
        "                </div>",
        '                <div class="party-legend" id="cityLegend" aria-label="Incorporated places by legal form" hidden></div>',
        '                <div class="leg-layout">',
        '                    <div class="leg-map-card"><div id="localMap" class="leg-map">',
        '                        <p class="results-bar" role="status">Loading the map&hellip;</p>',
        "                    </div></div>",
        '                    <aside class="leg-panel local-panel" aria-live="polite">',
        '                        <h2 class="leg-panel-title" id="localPanelTitle"></h2>',
        '                        <div id="localPanelBody"></div>',
        "                    </aside>",
        "                </div>",
        '                <section class="leg-roster-section" aria-labelledby="localRosterTitle">',
        f'                    <h2 class="state-heading" id="localRosterTitle">Every {_e(one)}</h2>',
        '                    <div id="localRoster"></div>',
        "                </section>",
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Sources:</strong> every government, its county, website, city,",
        "                    population or enrollment, from the U.S. Census Bureau's 2022 Census of",
        "                    Governments: Government Units listing"
        + (f", read on {time_html(listed)}" if listed else "") + ", checked against the Bureau's",
        "                    published counts for every state; county lines from its cartographic",
        "                    boundary file; every incorporated place and its legal form from its 2025",
        "                    place boundaries, joined to its government by name only where the join is",
        "                    one to one. Names are shown in title case; the listing prints them in",
        "                    capitals.</p>",
        "                <p><strong>Where there is no county government:</strong> "
        + "; ".join(f'<a href="{_e(url)}" rel="noopener">{_e(label)}</a>' for label, url in why)
        + ".</p>",
    ])
    scripts = [s.replace("{code}", code.lower()) for s in (
        "../data/local/{code}.js", "../data/courtcounties.js", "../data/lookup/index.js",
        "../assets/kyc-regionmap.js", "../assets/kyc-findrep.js", "../assets/kyc-local.js")]
    return render_page(
        title=_e(f"{title} — Know Your Candidate"),
        og_title=_e(title),
        description=_e(f"Every {one} in {name} and every local government in each: cities, "
                       f"townships, school districts and special districts, with links."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="counties",
        nav_current="local",
        nav_how="true",
        search="",
        sidebar=_COUNTIES_SIDEBAR,
        jump_options=jump_options(STATES),
        jump_attrs=' data-jump-to="counties/{code}.html"',
        main=main,
        footer=footer,
        built=(listed, listed) if listed else None,
        crumbs=[_HOME, (section_name("local"), "counties/index.html"), (name, path)],
        scripts=_scripts(scripts),
    )


# ------------------------------------------------------ about, 404, folders

# When the roster refresh runs (.github/workflows/refresh.yml's gate job):
# every day in these spans, inclusive; before Election Day otherwise on
# Mondays and Thursdays, after it on Mondays. test_about holds the two
# together, so the About page cannot promise a schedule the workflow left.
REFRESH_DAILY = (("2026-10-15", "2026-11-02"), ("2026-11-04", "2026-12-15"),
                 ("2027-01-03", "2027-01-14"))
# odds.yml's cron, in words (rule 41: it stops at the first poll closing).
ODDS_TIMES = ("00:47", "12:47")

# What each part of the site is built from: (what, source, what it covers,
# when it is read again, the DATED_CACHES key of when it was last read).
# "refresh" is the scheduled refresh above; README.md's field tables go
# into each field.
DATASETS = (
    ("Members of Congress",
     '<a href="https://github.com/unitedstates/congress-legislators">congress-legislators</a>',
     "Every member: seat, party, term, contact details, ids for outbound links", "refresh",
     "congress"),
    # The rosters' biography columns are not read by a script: they are the
    # editorial source of truth, kept by hand (CLAUDE.md), and the page must
    # not say every fact is read from a source.
    ("Members' biographies",
     "The member rosters in this site's repository, kept by hand",
     "Education, earlier careers and stated priorities, where the rosters hold them",
     "curated", None),
    ("Editorial decisions",
     "This site's repository: each decision recorded with its evidence and date",
     "What no source can settle alone: a lapsed campaign site, one person filed under two names",
     "curated", None),
    ("Committee seats",
     '<a href="https://github.com/unitedstates/congress-legislators">congress-legislators</a>',
     "Each committee's members, with their rank and title", "refresh", "committees"),
    ("Who is running, and their money",
     '<a href="https://www.fec.gov/data/">Federal Election Commission</a>',
     "Everyone registered for 2026; receipts, spending and cash on hand", "refresh", None),
    ("Primary results and who is on the ballot",
     "Each state's results page on Wikipedia; Louisiana's Secretary of State for its "
     "qualified candidates",
     "Who won, lost or withdrew; who is on the November ballot", "refresh", "results"),
    ("Financial disclosures",
     '<a href="https://disclosures-clerk.house.gov/">House Clerk</a> and '
     '<a href="https://efdsearch.senate.gov/">Senate eFD</a>',
     "A link to each member's latest annual report", "refresh", None),
    ("Voting record", '<a href="https://voteview.com/">Voteview</a>',
     "A left-to-right score from each member's roll-call votes", "manual", None),
    ("Campaign websites and candidates' own words",
     "Each committee's FEC filing; the article a race page links; the campaign's own site",
     "Websites, and what a campaign says about itself, quoted", "refresh", "enrichment"),
    ("Public offices held",
     "congress-legislators; Wikidata, where the person's own Wikipedia article agrees",
     "Offices each person has held, with years", "refresh", "history"),
    ("Market prices and polling averages",
     "Kalshi, Polymarket; each race's Wikipedia page for polling averages",
     "Published prices and averages, never a forecast of this site's", "odds", None),
    ("Governors and party control",
     '<a href="https://www.nga.org/governors/">National Governors Association</a>; '
     "Open States and the National Conference of State Legislatures",
     "Every governor; which party holds each chamber, where the two agree", "refresh",
     "governors"),
    ("Statewide officers",
     "NLGA, NASS, the attorneys general's associations, and each office's own site",
     "Lieutenant governors, secretaries of state, attorneys general", "refresh", "officers"),
    ("State legislators", '<a href="https://openstates.org/">Open States</a>',
     "Every state legislator and their district", "refresh", "openstates"),
    ("State supreme courts",
     "Each court's own page or roster file. Where a court's site refuses automated reading, "
     "a person reads its page; each state's page says how and on which day",
     "Each state's highest court", "courts", "statecourts"),
    ("Voting information", '<a href="https://www.nass.org/can-I-vote">NASS Can I Vote</a>',
     "Each state's official pages to register, find a polling place and vote", "refresh",
     "voting"),
    ("President, Vice President and Cabinet",
     "The White House, each office's own page, the Senate's roll calls",
     "Who holds each office, and since when", "refresh", "executive"),
    ("Executive financial reports",
     '<a href="https://www.oge.gov/">Office of Government Ethics</a>',
     "Reports filed by the President, Vice President and Cabinet", "refresh", "oge"),
    ("Federal judges",
     '<a href="https://www.fjc.gov/history/judges">Federal Judicial Center</a>; the Supreme Court',
     "Every sitting Article III judge", "refresh", "judiciary"),
    ("Judicial vacancies", '<a href="https://www.uscourts.gov/judges-judgeships/judicial-vacancies">uscourts.gov</a>',
     "Vacancies, announced vacancies and judicial emergencies", "refresh", "vacancies"),
    ("Local governments",
     '<a href="https://www.census.gov/programs-surveys/cog.html">Census of Governments</a> (2022)',
     "Every county, city, town, township, school district and special district", "fixed",
     "census"),
    ("Tribal governments",
     '<a href="https://www.bia.gov/service/tribal-leaders-directory">BIA Tribal Leaders '
     'Directory</a>',
     "Each tribal government, the state of its office, and its leader", "refresh", "tribes"),
    ("Maps", "U.S. Census Bureau boundary files; each redrawn state's enacted plan",
     "States, congressional and legislative districts, counties, places", "maps", None),
    ("Know Your Government", "The primary sources each section cites",
     "How government is organized, in plain words", "guide", None),
)

_WHEN_READ = {
    "refresh": "Each scheduled refresh",
    # The build warns once a roster read by hand is older than that.
    "courts": "Each scheduled refresh; a roster read by hand, by a person within "
              f"{COURT_STALE_DAYS} days",
    "odds": "Every 12 hours, until polls close",
    "fixed": "Fixed: counted in 2022",
    "maps": "When a map changes",
    # Voteview's scores are read into the rosters by hand (`fetch`); the
    # scheduled refresh does not run it.
    "manual": "By hand, from time to time",
    "guide": "Checked by hand; each page gives its date",
    "curated": "When a change is needed; each change is a public commit",
}

# What the "Last read" column says for a dataset with no single read date:
# where the reader finds the date instead, never a dash that reads as "never".
_NO_READ_DATE = {
    "Who is running, and their money": "Each profile gives the date its figures run through",
    "Financial disclosures": "Each profile names its report's year",
    "Market prices and polling averages": "Each price gives the day it was read",
    "Members' biographies": "In the repository's history",
    "Editorial decisions": "Each decision gives its date",
}


def _span_words(first, last):
    """"Oct. 15 to Nov. 2, 2026"; across a year, both years."""
    a, b = date_words(first), date_words(last)
    if first[:4] == last[:4]:
        return f"{a.rsplit(',', 1)[0]} to {b}"
    return f"{a} to {b}"


def schedule_words():
    """The refresh schedule, in a sentence, from REFRESH_DAILY."""
    spans = [_span_words(a, b) for a, b in REFRESH_DAILY]
    return (f"The scheduled refresh runs every day from {spans[0]} and from {spans[1]}, the "
            f"weeks before the election and the six weeks after it, and from {spans[2]}, as the new "
            "Congress is sworn in. On other days it runs on Mondays and Thursdays before "
            "Election Day and on Mondays after it. Each run is published only once every "
            "check passes. Market prices and polling averages are read every 12 hours, at "
            f"{ODDS_TIMES[0]} and {ODDS_TIMES[1]} UTC, and stop when the first polls close on "
            "Election Day: prices that move on early returns would read as results.")


def _about_main(dates):
    rows = []
    for what, source, covers, when, key in DATASETS:
        if key and dates.get(key):
            last = time_html(dates.get(key))
        else:
            last = _e(_NO_READ_DATE.get(what, "")) or "&ndash;"
        rows.append("                        <tr>"
                    f'<th scope="row">{_e(what)}</th><td data-label="Source">{source}</td>'
                    f'<td data-label="Covers">{_e(covers)}</td>'
                    f'<td data-label="Read again">{_e(_WHEN_READ[when])}</td>'
                    f'<td data-label="Last read">{last}</td></tr>')
    report = report_url()
    repo = _e(REPO)
    return "\n".join([
        '            <article id="aboutContent" class="state-page guide-page about-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">About</p>',
        f'                    <h1 class="state-title">{_e(section_name("about"))}</h1>',
        '                    <p class="districts-lede">Whose site this is, where the facts on it come',
        "                        from, how often they are read again, and how to tell us when something",
        "                        is wrong.</p>",
        "                </header>",
        '                <section class="guide-section" id="who">',
        # Named for what the section can answer: it names no maintainer and
        # no funder, so it does not ask "who runs this site" (TRUST-02).
        '                    <h2 class="state-heading">An independent project</h2>',
        "                    <p>Know Your Candidate is an independent, non-partisan project. Its code",
        f'                        and data are public, at <a href="{repo}">{repo}</a>, so anyone can',
        "                        see how each fact was reached, and every change to them is recorded",
        "                        there.</p>",
        "                    <p>It is not affiliated with any campaign, party, candidate or government",
        "                        office, takes no money from any of them, and carries no",
        "                        advertising. It is served by GitHub Pages.</p>",
        "                </section>",
        '                <section class="guide-section" id="not-official">',
        '                    <h2 class="state-heading">What this site is not</h2>',
        "                    <p>It is not an official election source, and nothing on it is legal",
        "                        advice. Before you register, request a ballot or vote, check with your",
        "                        state's election office: each state's page here links its official",
        '                        voting pages, and <a href="https://www.nass.org/can-I-vote">NASS Can',
        "                        I Vote</a> lists every state's.</p>",
        "                </section>",
        '                <section class="guide-section" id="report">',
        '                    <h2 class="state-heading">Report a problem</h2>',
        "                    <p>This site makes claims about real, named people, and a wrong one",
        "                        matters. If something is wrong, out of date or missing, or a page does",
        f'                        not work for you, <a href="{_e(report)}" data-report target="_blank"',
        '                        rel="noopener noreferrer">open a report on GitHub</a> (it needs a free',
        "                        GitHub account). Every profile and page has the same link, which fills",
        "                        in where you were. Please say what is wrong and, if you can, where the",
        "                        right answer is published.</p>",
        "                    <p>Reports and the corrections made from them are public: each is an",
        "                        issue in the repository, and each fix a change anyone can read.</p>",
        "                </section>",
        '                <section class="guide-section" id="data">',
        '                    <h2 class="state-heading">Where the data comes from</h2>',
        "                    <p>Most facts are read from a named source by a script and checked before",
        "                        they are published. The member rosters' biographies, and the decisions",
        "                        no source can settle alone, are kept by hand in the repository, where",
        "                        each change is public. Where a source says nothing, the site says so,",
        "                        rather than guessing. The repository's",
        f'                        <a href="{repo}#readme">README</a> lists every field and where it comes',
        "                        from.</p>",
        '                    <div class="directory-scroll" tabindex="0" role="region" aria-label="Data sources">',
        '                        <table class="directory-table about-table">',
        '                            <thead><tr><th scope="col">Data</th><th scope="col">Source</th>'
        '<th scope="col">Covers</th><th scope="col">Read again</th><th scope="col">Last read</th>'
        "</tr></thead>",
        "                            <tbody>",
        *rows,
        "                            </tbody>",
        "                        </table>",
        "                    </div>",
        '                    <p id="schedule">' + _e(schedule_words()) + "</p>",
        "                    <p><strong>Who counts as a candidate:</strong> everyone the FEC records as",
        "                        having raised or spent more than $5,000 for the 2026 cycle",
        "                        (52&nbsp;U.S.C.&nbsp;&sect;30101(2)). Everyone who has registered is",
        "                        counted in each race, whatever they raised.</p>",
        "                </section>",
        '                <section class="guide-section" id="privacy">',
        '                    <h2 class="state-heading">Privacy</h2>',
        "                    <ul>",
        "                        <li>No cookies, no analytics, no advertising trackers and no accounts.",
        "                            The site does not know who you are.</li>",
        "                        <li>Your browser keeps two settings for this site, on your device only:",
        "                            the theme you picked and the last state you looked at, so the",
        "                            navigation can offer it again. To clear them, clear this site's data",
        "                            in your browser's settings.</li>",
        "                        <li>Portraits and some images load from the sites that publish them:",
        "                            Wikimedia Commons, the House Clerk, Congress.gov, state legislatures,",
        "                            state officers' offices and their associations, and campaign sites,",
        "                            some of them through WordPress.com's image service (i0.wp.com), which",
        "                            serves a heavy photograph at a smaller size. Those sites see your IP",
        "                            address when your browser",
        "                            fetches an image, as any website would; this site asks your browser",
        "                            not to tell them which page you were reading.</li>",
        "                        <li>&#8220;Find my district&#8221; and &#8220;Find who represents you&#8221;",
        "                            ask your browser for your location, or take a ZIP code you type, and",
        "                            look it up on your device, in this site&#8217;s own file for your",
        "                            state. Neither is ever sent anywhere; the host sees only which",
        "                            state&#8217;s file was fetched, as it would for that state&#8217;s",
        "                            page.</li>",
        "                        <li>The site is served by GitHub Pages, which receives your IP address",
        "                            with each request, as any web host does; see",
        '                            <a href="https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement">GitHub&#8217;s',
        "                            privacy statement</a>. Links out lead to other sites, whose own",
        "                            policies apply.</li>",
        "                    </ul>",
        "                </section>",
        '                <section class="guide-section" id="accessibility">',
        '                    <h2 class="state-heading">Accessibility</h2>',
        "                    <p>The site aims to meet the Web Content Accessibility Guidelines (WCAG)",
        "                        2.2 at level AA. Every page is built and checked by automated tests on",
        "                        each change: pages can be zoomed; every control works from a keyboard,",
        "                        with a visible focus; dialogs hold the focus and return it when they",
        "                        close; each page has a link to skip to its content; fields are large",
        "                        enough on a phone that it does not zoom on its own; and the words on",
        "                        the maps are page text, so they stay readable in forced dark modes.</p>",
        "                    <p>Known limits: the maps are visual. On a map of the states, each state",
        "                        is a button that names it, and picking one shows its facts as text,",
        "                        but no view lists every state's value at once. Documents this site",
        "                        links, such",
        "                        as disclosure PDFs and the Senate's disclosure site, are their",
        "                        publishers' and may not be accessible. If anything here is hard to use,",
        f'                        <a href="{_e(report)}" target="_blank" rel="noopener noreferrer">tell us',
        "                        with the same form</a>.</p>",
        "                </section>",
        '                <section class="guide-section" id="licence">',
        '                    <h2 class="state-heading">Licence</h2>',
        f'                    <p>The code is under the <a href="{repo}/blob/main/LICENSE">MIT',
        "                        licence</a>. The data this project compiles is under",
        f'                        <a href="{repo}/blob/main/LICENSE-DATA.md">Creative Commons Attribution',
        "                        4.0</a> (CC BY 4.0): you may reuse it, with credit to Know Your",
        "                        Candidate and the dates the data carries. Photographs, and the",
        "                        datasets this project reads, keep their own owners' terms: each",
        "                        photograph on a profile or an official's record is credited under",
        "                        it, a Wikimedia Commons file with its author and licence as the",
        "                        file's own page records them; a state officer's in the sources line",
        "                        of their state's card.</p>",
        "                </section>",
        "            </article>",
    ])


def render_about(host, dates=None, codes=()):
    """about.html: who runs the site, where its data comes from, how to
    report an error, privacy, accessibility and the licence (TRUST-02)."""
    dates = dates or {}
    path = "about.html"
    canonical = f"https://{host}/{path}" if host else path
    keys = sorted({key for *_rest, key in DATASETS if key and dates.get(key)})
    name = section_name("about")
    return render_page(
        title=_e(f"{name} — Know Your Candidate"),
        og_title=_e("About Know Your Candidate"),
        description=_e("An independent, non-partisan project: who runs it, where every fact "
                       "comes from and how often it is read, how to report an error, privacy, "
                       "accessibility and the licence."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="about",
        root="",
        search="",
        sidebar="",
        nav_current="about",
        jump_options=_jump(codes),
        main=_about_main(dates),
        footer="",
        built=_read_span(dates, *keys),
        crumbs=[_HOME, (name, path)],
        scripts="",
    )


def render_404(host, codes=()):
    """404.html: GitHub Pages serves it for any missing address, at any
    depth, so every URL in it is from the site's root (TECH-06)."""
    report = report_url()
    main = "\n".join([
        '            <div id="notFound" class="state-page directory-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">Know Your Candidate</p>',
        '                    <h1 class="state-title">Page not found</h1>',
        '                    <p class="districts-lede">There is no page at this address. It may have',
        "                        moved, or the link may be mistyped. Search for a candidate or member",
        "                        of Congress, or pick a section.</p>",
        "                </header>",
        '                <form class="search-page" role="search" action="/index.html" data-site-search>',
        '                    <label class="sr-only" for="notFoundSearch">Search candidates and members of Congress</label>',
        '                    <input type="search" id="notFoundSearch" name="q" autocomplete="off"',
        '                           spellcheck="false" placeholder="Search candidates and members&hellip;">',
        '                    <button type="submit" class="btn">Search</button>',
        "                </form>",
        '                <ul class="directory-list">',
        *[f'                    <li class="directory-row"><a class="directory-name" href="/{_e(p)}">'
          f"{_e(label)}</a></li>"
          for _heading, entries in nav_groups() for _k, p, _i, label in entries],
        "                </ul>",
        f'                <p class="faint">If a link on this site brought you here, <a href="{_e(report)}"',
        '                    target="_blank" rel="noopener noreferrer">please report it</a>.</p>',
        "            </div>",
    ])
    return render_page(
        title=_e("Page not found — Know Your Candidate"),
        og_title=_e("Page not found"),
        description=_e("There is no page at this address."),
        canonical=_e(f"https://{host}/404.html" if host else "404.html"),
        host=_e(host or ""),
        code="",
        page_kind="not-found",
        root="/",
        search="",
        sidebar="",
        jump_options=_jump(codes),
        main=main,
        footer="",
        built=None,
        page_url="",
        jsonld='<meta name="robots" content="noindex">\n',
        scripts="",
    )


# The name of districts/index.html, wherever it is shown or linked.
DISTRICTS_INDEX_NAME = "District maps"


def district_directory_facts(code, seats=None):
    """What a state's district page holds, in a few words for the
    directory: never the state's name, which the row already shows."""
    from .districts import REDRAWN

    if code in REDRAWN:
        return "Redrawn for 2026: the old and new lines side by side"
    if code == "PR":
        return "One resident commissioner, at large"
    if code in TERRITORIES:
        return "One delegate, at large"
    if seats == 1:
        return "One seat, at large"
    return f"{seats} districts: the 2024 lines, used again" if seats else "The 2024 lines, used again"


def render_districts_index(host, summary=None, codes=()):
    """districts/index.html: every state's district map, so the folder's
    own address answers (TECH-06). Plain links; nothing to load."""
    from .districts import REDRAWN, all_codes

    path = "districts/index.html"
    canonical = f"https://{host}/{path}" if host else path
    states = ((summary or {}).get("states") or {})
    rows = []
    for code in sorted(all_codes(), key=state_name):
        info = states.get(code) or {}
        facts = district_directory_facts(code, info.get("house") or info.get("delegates"))
        rows.append(f'                    <li class="directory-row"><a class="directory-name" '
                    f'href="{_e(code.lower())}.html">{_e(state_name(code))}</a>'
                    f'<div class="directory-facts">{_e(facts)}</div></li>')
    main = "\n".join([
        '            <div id="districtsDirectory" class="state-page directory-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">The U.S. House</p>',
        # One name in its title, heading, breadcrumb and the links to it
        # (rule 75).
        f'                    <h1 class="state-title">{DISTRICTS_INDEX_NAME}</h1>',
        '                    <p class="districts-lede">Each state&#8217;s congressional districts on a',
        "                        map: who holds each seat and who is on the November ballot. Where a",
        "                        state redrew its map for 2026, the old and new lines side by side.</p>",
        '                    <p class="state-links">',
        f'                        <a class="btn" href="{_e(_learn("congress#house"))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> How the House works</a>',
        '                        <a class="btn" href="../states/index.html"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> States &amp; territories</a>',
        "                    </p>",
        "                </header>",
        '                <ul class="directory-list">',
        *rows,
        "                </ul>",
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Sources:</strong> district lines from the U.S. Census Bureau's",
        "                    boundary files and, for each redrawn state, the plan its legislature or",
        "                    court enacted.</p>",
    ])
    return render_page(
        title=_e(f"{DISTRICTS_INDEX_NAME} — Know Your Candidate"),
        og_title=_e(DISTRICTS_INDEX_NAME),
        description=_e("Every state's congressional districts on a map, with the old and new "
                       "lines side by side where a state redrew them for 2026."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="districts-index",
        search="",
        sidebar="",
        nav_current="states",
        nav_how="true",
        jump_options=_jump(codes),
        main=main,
        footer=footer,
        built=None,
        crumbs=[_HOME, (section_name("states"), "states/index.html"), (DISTRICTS_INDEX_NAME, path)],
        scripts="",
    )


def render_courts_index(host, codes=(), dates=None):
    """courts/index.html: every federal court, by kind, so the folder's own
    address answers (TECH-06). Plain links; the hub holds the rest."""
    from .federal_courts import COURTS, KIND_PLURALS, KINDS

    path = "courts/index.html"
    canonical = f"https://{host}/{path}" if host else path
    groups = []
    for kind in ("supreme", "appeals", "trade", "district", "territorial"):
        ids = [cid for cid, court in COURTS.items() if court["kind"] == kind]
        if not ids:
            continue
        heading = KINDS[kind] if len(ids) == 1 else KIND_PLURALS[kind]
        groups += [f'                <h2 class="state-heading">{_e(heading)}</h2>',
                   '                <ul class="directory-list">',
                   *[f'                    <li class="directory-row"><a class="directory-name" '
                     f'href="{_e(cid)}.html">{_e(COURTS[cid]["name"])}</a></li>' for cid in ids],
                   "                </ul>"]
    main = "\n".join([
        '            <div id="courtsDirectory" class="state-page directory-page">',
        '                <header class="state-hero">',
        '                    <p class="state-kicker">The judicial branch</p>',
        # One name in the navigation, the title, the heading and the
        # breadcrumbs (rule 75): the navigation's.
        f'                    <h1 class="state-title">{_e(section_name("courts"))}</h1>',
        '                    <p class="districts-lede">The Supreme Court, the courts of appeals and the',
        "                        district courts, each with its sitting judges and its vacancies.</p>",
        '                    <p class="state-links">',
        '                        <a class="btn" href="../federal/index.html#courts"><svg class="icon" aria-hidden="true"><use href="#i-scale"/></svg> The federal courts</a>',
        f'                        <a class="btn" href="{_e(_learn("courts"))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> How the federal courts work</a>',
        "                    </p>",
        "                </header>",
        *groups,
        "            </div>",
    ])
    return render_page(
        title=_e(f"{section_name('courts')} — Know Your Candidate"),
        og_title=_e(section_name("courts")),
        description=_e("Every federal court: the Supreme Court, the courts of appeals and the "
                       "district courts, each with its judges and vacancies."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="courts-index",
        search="",
        sidebar=_FEDERAL_SIDEBAR,
        nav_current="courts",
        jump_options=_jump(codes),
        main=main,
        footer=_court_footer({"kind": "appeals"}, dates),
        footer_dated=True,
        built=_read_span(dates, "judiciary", "vacancies"),
        crumbs=[_HOME, (section_name("courts"), path)],
        scripts="",
    )


def webmanifest():
    """site.webmanifest: the name and icons a phone uses when the site is
    added to its home screen. Relative URLs only: no hostname (rule 21)."""
    import json

    return json.dumps({
        "name": "Know Your Candidate",
        "short_name": "Know Your Candidate",
        "description": "A non-partisan directory of the U.S. Congress, the 2026 midterm "
                       "races, and every state's government.",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "background_color": "#0d0f12",
        "theme_color": "#0d0f12",
        "icons": [
            {"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            {"src": "assets/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
            {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }, indent=2) + "\n"


def render_redirect(target, host):
    """A page that moved: a stub that sends the reader on, and tells search
    engines where the page lives now."""
    canonical = f"https://{host}/{target.replace('../', '')}" if host else target
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Moved — Know Your Candidate</title>",
        f'<meta http-equiv="refresh" content="0; url={_e(target)}">',
        f'<link rel="canonical" href="{_e(canonical)}">',
        '<meta name="robots" content="noindex">',
        "</head>",
        "<body>",
        f'<p>This page has moved to <a href="{_e(target)}">{_e(target)}</a>.</p>',
        "</body>",
        "</html>",
        "",
    ])


def sitemap(host, codes, built=None, district_maps=(), guide=(), legislatures=(), courts=()):
    """``sitemap.xml`` listing the two hand-maintained pages and every state.

    Individual profiles live behind hash fragments, which crawlers do not
    treat as separate URLs, so they are not listed.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    stamp = f"\n    <lastmod>{_e(built[:10])}</lastmod>" if built else ""

    def url(path, priority, freq="weekly"):
        lines.extend([
            "  <url>",
            f"    <loc>https://{_e(host)}/{_e(path)}</loc>{stamp}",
            f"    <changefreq>{freq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ])

    url("", "1.0")
    url("map.html", "0.8")
    url("about.html", "0.4", "monthly")
    url("states/index.html", "0.8")
    for code in sorted(codes):
        url(page_path(code), "0.7")
    if district_maps:
        url("districts/index.html", "0.5", "monthly")
    for code in sorted(district_maps):
        url(f"districts/{code.lower()}.html", "0.6", "monthly")
    # The guide, in reading order.
    for slug in guide:
        url(f"government/{slug}.html", "0.5", "monthly")
    if legislatures:
        url("legislature/index.html", "0.6", "weekly")
    for code in sorted(legislatures):
        url(f"legislature/{code.lower()}.html", "0.6", "weekly")
    if legislatures:
        url("counties/index.html", "0.5", "monthly")
    for code in sorted(legislatures):
        url(f"counties/{code.lower()}.html", "0.5", "monthly")
    if courts:
        url("federal/index.html", "0.7")
        url("courts/index.html", "0.5")
    for court in courts:
        url(f"courts/{court}.html", "0.5")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
