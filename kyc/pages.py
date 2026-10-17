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
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../assets/kyc.css">
<script src="../assets/kyc.js"></script>
</head>
<body data-root="../" data-state="$code" data-page="$page_kind">

<a href="#stateMain" class="skip-link">Skip to content</a>
<button type="button" class="sidebar-scrim" tabindex="-1" aria-hidden="true"></button>

<header class="app-header">
    <button type="button" class="btn-icon sidebar-toggle" aria-expanded="false"
            aria-controls="sidebar" aria-label="Show navigation">
        <svg class="icon" aria-hidden="true"><use href="#i-menu"/></svg>
    </button>

    <a class="brand" href="../index.html">
        <svg class="icon" aria-hidden="true"><use href="#i-vote"/></svg>
        <span class="brand-name">Know Your Candidate</span>
        <span class="brand-sub" data-congress>U.S. Congress</span>
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
            <label class="sr-only" for="stateJump">Jump to a state or territory</label>
            <select id="stateJump" class="select"$jump_attrs>
                <option value="">Choose a state&hellip;</option>$jump_options
            </select>
        </nav>
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
            ("courts", "federal/index.html#supreme-court", "scale", "Federal courts"),
        )),
        ("State", (
            ("states", "states/index.html", "pin", "States & territories"),
            ("legislatures", "legislature/index.html", "columns", "State legislatures"),
        )),
        ("Local", (
            ("local", "counties/index.html", "layers", "Counties & cities"),
        )),
        ("Learn", (
            ("guide", "government/index.html", "scroll", "Know Your Government"),
        )),
    )


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


# The search box in the header. A state's pages search its profiles; the
# guide's pages carry no profiles to search, so they have none (as the map).
_SEARCH = """\
    <div class="search">
        <svg class="icon" aria-hidden="true"><use href="#i-search"/></svg>
        <label class="sr-only" for="stateSearch">Search this page</label>
        <input type="search" id="stateSearch" autocomplete="off" spellcheck="false"
               placeholder="$search_placeholder">
    </div>
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
            <a class="sidebar-link learn-link" href="../government/elections.html">How elections work</a>
        </div>
"""

_CONGRESS_FOOTER = """\
                <p><strong>Sources:</strong>
                    membership, contact details and committee rosters from the
                    <code>congress-legislators</code> dataset; the candidate field and
                    campaign finance from the Federal Election Commission; primary results
                    from each state's Wikipedia election page; portraits from Congress.gov
                    and Wikipedia.</p>
                <p><strong>Who counts as a candidate:</strong> everyone the FEC records
                    as having raised or spent more than $5,000 for the 2026 cycle
                    (52&nbsp;U.S.C.&nbsp;&sect;30101(2)). People the primary removed stay on
                    record and are shown under each race.</p>
                <p>Non-partisan and independent. Data built
                    <time id="buildStamp">&mdash;</time>.</p>"""


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
    profile pages share the Congress sidebar, footer and search box."""
    if "main_block" not in fields:
        fields["main_block"] = _CONTENT_MAIN.substitute(
            main=fields.pop("main"), footer=fields.pop("footer", _CONGRESS_FOOTER))
    search = fields.pop("search", None)
    if search is None:
        search = string.Template(_SEARCH).substitute(
            search_placeholder=fields.pop("search_placeholder"))
    fields.setdefault("sidebar", _CONGRESS_SIDEBAR)
    fields["nav"] = nav_html("../", fields.pop("nav_current", None), fields.pop("nav_how", "page"))
    fields.setdefault("jump_options", "")
    fields.setdefault("jump_attrs", "")
    return _PAGE.substitute(search=search, **fields)

# The state pages render everything from profiles.js on the client.
_STATE_MAIN = """\
            <div id="stateContent" class="state-page">
                <p class="results-bar" role="status">Loading&hellip;</p>
            </div>"""

_STATE_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../data/stategov.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-stategov.js",
    "../assets/kyc-state.js",
)

_DISTRICT_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../data/districts/{code}.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-districts.js",
)


def _e(text):
    return html.escape(str(text), quote=True)


def _scripts(sources):
    return "\n".join(f'<script src="{_e(src)}"></script>' for src in sources)


def render_state(code, host, summary=None):
    """The HTML for one state's page."""
    name = state_name(code)
    info = ((summary or {}).get("states") or {}).get(code) or {}
    if code in TERRITORIES:
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
        main=_STATE_MAIN,
        scripts=_scripts(_STATE_SCRIPTS),
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
        main=_STATE_MAIN,
        scripts=_scripts(_STATE_SCRIPTS),
    )


def render_legislatures_index(host):
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
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Sources:</strong> members and their parties from Open States, as",
        "                    each legislature publishes them, counted against the National Conference",
        "                    of State Legislatures' figures; a chamber's control is shown only where",
        "                    the two agree. A seat with nobody listed counts for no one.</p>",
        "                <p>Non-partisan and independent.</p>",
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
        scripts=_scripts(("../data/stategov.js", "../assets/kyc-stategov.js")),
    )


def _local_kinds():
    """The Census of Governments' kinds, as the guide's map words them
    (government_maps.LOCAL_KINDS, one table): ``[(key, column, none)]``,
    the total last. A count of school districts is of *independent* ones;
    a state with none runs its schools as dependent systems."""
    from .government_maps import LOCAL_KINDS, NONE_OF_KIND

    kinds = [k for k in LOCAL_KINDS if k[0] != "total"] + [k for k in LOCAL_KINDS if k[0] == "total"]
    return [(key, title.split(":")[0], NONE_OF_KIND.get(key, f"No {plural}."))
            for key, _short, title, _one, plural in kinds]


def render_counties_index(host, census=None):
    """Every state's local governments, counted by kind as the Census of
    Governments counts them, each state linked to its counties page. A
    state with none of a kind (an "X" in the Census table) reads "none",
    with what that means, never 0 (rule 49)."""
    from . import county_areas
    from .government import jump_options
    from .government_maps import STATES

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
        return f"<td>{value:,}{mark}</td>"

    rows = "\n".join(
        f'                        <tr><th scope="row"><a href="{_e(code.lower())}.html">'
        f'{_e(state_name(code))}</a></th>' + "".join(cell(code, k, n) for k, _w, n in kinds) + "</tr>"
        for code in sorted(STATES, key=state_name))
    year = (census or {}).get("year")
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
        f'                        <a class="btn" href="{_e(_learn("local"))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> How local governments work</a>',
        '                        <a class="btn" href="../states/index.html"><svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg> States &amp; territories</a>',
        "                    </p>",
        "                </header>",
        '                <div class="directory-scroll" tabindex="0" role="region" aria-label="Local governments by state">',
        '                    <table class="directory-table">',
        '                        <thead><tr><th scope="col">State</th>' +
        "".join(f'<th scope="col">{_e(words)}</th>' for _k, words, _n in kinds) + "</tr></thead>",
        "                        <tbody>",
        rows,
        "                        </tbody>",
        "                    </table>",
        "                </div>",
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
        '                    local government by state and kind. "None" is a state with no',
        "                    government of that kind: one with no county governments has none, and",
        "                    one with no independent school districts runs its schools as dependent",
        "                    systems of the state, a county or a city. County areas without a county",
        "                    government, and what governs them: "
        f'<a href="{_e(county_areas.SOURCES["isd"][1])}" rel="noopener">{_e(county_areas.SOURCES["isd"][0])}</a>.</p>',
        "                <p>Non-partisan and independent.</p>",
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
        scripts="",
    )


def _possessive(name):
    return name + ("'" if name.endswith("Islands") else "'s")


# States whose map is unchanged but nearly was, where a reader may have read
# otherwise. Each clause is on the record of the court that decided it.
UNCHANGED_NOTES = {
    "MO": ("A map passed in 2025 was suspended by a referendum petition, and the courts "
           "have kept these districts in place for 2026."),
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
    )


_LEGISLATURE_SIDEBAR = """
        <div class="sidebar-section">
            <h2 class="sidebar-heading">State legislatures</h2>
            <p class="sidebar-note">Every state's districts and the members who sit for
                them, from Open States and the Census Bureau.</p>
        </div>
"""


def render_legislature_page(code, host, summary=None):
    """A state's legislature: its Senate and House districts on a map, and
    the members who sit for them. The page carries the state code only;
    ``assets/kyc-legislature.js`` draws it from ``data/legislature/<st>.js``."""
    from .government_maps import LOWER_CHAMBER, SEATS, STATES
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
        title = f"{name} Legislature"
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
        '                        <a class="btn" href="../government/states.html"><svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> How states are governed</a>',
        "                    </p>",
        "                </header>",
        '                <div class="toolbar legislature-toolbar">',
        chambers,
        '                    <div class="party-legend" aria-label="Colours">',
        '                        <span class="key"><span class="swatch party-fill-r"></span>Republican</span>',
        '                        <span class="key"><span class="swatch party-fill-d"></span>Democratic</span>',
        '                        <span class="key"><span class="swatch party-fill-i"></span>Independent or other</span>',
        '                        <span class="key"><span class="swatch party-fill-split"></span>Members of more than one party</span>',
        '                        <span class="key"><span class="swatch party-fill-none"></span>Nobody listed, or nonpartisan</span>',
        "                    </div>",
        "                </div>",
        '                <div class="leg-layout">',
        '                    <div class="leg-map-card"><div id="legMap" class="leg-map">',
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
        "                <p><strong>Sources:</strong> members, their parties, districts, contact",
        "                    details and portraits from Open States (public domain), as each",
        "                    legislature publishes them; district boundaries from the U.S. Census",
        "                    Bureau's cartographic boundary files, as set for the 2024 elections.",
        "                    A seat with nobody listed may be vacant, or Open States may be behind",
        "                    a special election.</p>",
        "                <p>Non-partisan and independent.</p>",
    ])
    scripts = [s.replace("{code}", code.lower()) for s in (
        "../data/legislature/{code}.js", "../assets/kyc-regionmap.js", "../assets/kyc-legislature.js")]
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
            <a class="nav-link nav-sub" href="../federal/index.html#courts">The Article III courts</a>
        </nav>
"""

_FEDERAL_FOOTER = "\n".join([
    "                <p><strong>Sources:</strong> the President and Vice President from",
    "                    congress-legislators' record of their terms; the Cabinet as the White House",
    "                    lists it, each officer checked on their office's own page and against the",
    "                    Senate's roll-call vote confirming them; every Article III judge from the",
    "                    Federal Judicial Center's Biographical Directory, and the Supreme Court's",
    "                    members as the Court lists them; vacancies as the courts list them on",
    "                    uscourts.gov. Judges are shown with the president who appointed them,",
    "                    never with a party.</p>",
    "                <p>Non-partisan and independent.</p>",
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


def render_federal_page(host, codes=()):
    """The federal government's hub: the President, the Vice President, the
    Cabinet, the Supreme Court and every federal court. The page carries no
    names; ``assets/kyc-federal.js`` draws it from ``data/federal.js``."""
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
        '                        <a class="btn" href="../government/executive.html"><svg class="icon" aria-hidden="true"><use href="#i-landmark"/></svg> How the executive works</a>',
        '                        <a class="btn" href="../government/courts.html"><svg class="icon" aria-hidden="true"><use href="#i-scale"/></svg> How the federal courts work</a>',
        "                    </p>",
        "                </header>",
        '                <div id="federalBody">',
        '                    <p class="results-bar" role="status">Loading&hellip;</p>',
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
        footer=_FEDERAL_FOOTER,
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


# Where the guide explains each kind of federal court, and what to call it.
_COURT_SECTIONS = {"supreme": "supreme-court", "appeals": "appeals", "district": "district",
                   "territorial": "other-courts", "trade": "district"}
_COURT_WORDS = {"supreme": "How the Supreme Court works",
                "appeals": "How the courts of appeals work",
                "district": "How the district courts work",
                "territorial": "How the territorial courts work",
                "trade": "How the federal trial courts work"}


def render_court_page(court_id, host, codes=()):
    """One federal court: its judges, the chief first, then active and senior
    judges. ``assets/kyc-federal.js`` draws it from the court's data file."""
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
        '                        <a class="btn" href="../federal/index.html#courts"><svg class="icon" aria-hidden="true"><use href="#i-scale"/></svg> The Article III courts</a>',
        f'                        <a class="btn" href="{_e(_learn("courts#" + _COURT_SECTIONS[court["kind"]]))}"><svg class="icon" aria-hidden="true"><use href="#i-scroll"/></svg> {_e(_COURT_WORDS[court["kind"]])}</a>',
        "                    </p>",
        "                </header>",
        '                <div id="federalBody">',
        '                    <p class="results-bar" role="status">Loading&hellip;</p>',
        "                </div>",
        "            </div>",
    ])
    scripts = ("../data/federal.js", f"../data/judiciary/{court_id}.js",
               "../assets/kyc-official.js", "../assets/kyc-federal.js")
    return render_page(
        title=_e(f"{court['name']} — Know Your Candidate"),
        og_title=_e(f"{court['name']}: its judges"),
        description=_e(f"Every sitting judge of the {court['name']}: who appointed them, when "
                       f"they were confirmed, their senior status, and their background."),
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
        footer=_FEDERAL_FOOTER,
        scripts=_scripts(scripts),
    )


_COUNTIES_SIDEBAR = """
        <div class="sidebar-section">
            <h2 class="sidebar-heading">Counties &amp; local governments</h2>
            <p class="sidebar-note">Every county, city, township, school district and special
                district, from the Census Bureau's 2022 Census of Governments.</p>
        </div>
"""


def render_counties_page(code, host):
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
        '                        <a class="btn" href="../government/local.html"><svg class="icon" aria-hidden="true"><use href="#i-layers"/></svg> How local government works</a>',
        "                    </p>",
        "                </header>",
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
        '                    <div id="localRoster" class="leg-roster"></div>',
        "                </section>",
        "            </div>",
    ])
    footer = "\n".join([
        "                <p><strong>Sources:</strong> every government, its county, website, city,",
        "                    population or enrollment, from the U.S. Census Bureau's 2022 Census of",
        "                    Governments: Government Units listing, checked against the Bureau's",
        "                    published counts for every state; county lines from its cartographic",
        "                    boundary file; every incorporated place and its legal form from its 2025",
        "                    place boundaries, joined to its government by name only where the join is",
        "                    one to one. Names are shown in title case; the listing prints them in",
        "                    capitals.</p>",
        "                <p><strong>Where there is no county government:</strong> "
        + "; ".join(f'<a href="{_e(url)}" rel="noopener">{_e(label)}</a>' for label, url in why)
        + ".</p>",
        "                <p>Non-partisan and independent.</p>",
    ])
    scripts = [s.replace("{code}", code.lower()) for s in (
        "../data/local/{code}.js", "../assets/kyc-regionmap.js", "../assets/kyc-local.js")]
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
        scripts=_scripts(scripts),
    )


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
    url("states/index.html", "0.8")
    for code in sorted(codes):
        url(page_path(code), "0.7")
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
    for court in courts:
        url(f"courts/{court}.html", "0.5")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
