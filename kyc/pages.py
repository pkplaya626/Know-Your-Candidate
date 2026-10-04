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
        <span class="brand-sub">119th Congress</span>
    </a>

    <div class="search">
        <svg class="icon" aria-hidden="true"><use href="#i-search"/></svg>
        <label class="sr-only" for="stateSearch">Search this page</label>
        <input type="search" id="stateSearch" autocomplete="off" spellcheck="false"
               placeholder="$search_placeholder">
    </div>

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
        <nav class="sidebar-section" aria-label="Views">
            <a class="nav-link" href="../index.html">
                <svg class="icon" aria-hidden="true"><use href="#i-grid"/></svg>
                Profile grid
            </a>
            <a class="nav-link" href="../map.html">
                <svg class="icon" aria-hidden="true"><use href="#i-map"/></svg>
                Partisan map
            </a>
            <a class="nav-link" href="index.html"$states_current>
                <svg class="icon" aria-hidden="true"><use href="#i-pin"/></svg>
                States &amp; territories
            </a>
            <div id="yourState" hidden></div>
        </nav>

        <div class="sidebar-section">
            <h2 class="sidebar-heading">119th Congress</h2>
            <div class="balance-label">Senate</div>
            <div class="balance" id="senateBalance"></div>
            <div class="balance-label">House</div>
            <div class="balance" id="houseBalance"></div>
        </div>

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
        </div>

        <nav class="sidebar-section push" aria-label="Jump to a state">
            <h2 class="sidebar-heading">Jump to</h2>
            <label class="sr-only" for="stateJump">Jump to a state or territory</label>
            <select id="stateJump" class="select">
                <option value="">Choose a state&hellip;</option>
            </select>
        </nav>
    </aside>

    <main class="app-main" id="stateMain">
        <div class="content scroll-y">
$main

            <footer class="site-footer">
                <p><strong>Sources:</strong>
                    membership, contact details and committee rosters from the
                    <code>congress-legislators</code> dataset; the candidate field and
                    campaign finance from the Federal Election Commission; primary results
                    from each state's Wikipedia election page; portraits from Congress.gov
                    and Wikipedia.</p>$more_sources
                <p><strong>Who counts as a candidate:</strong> everyone the FEC records
                    as having raised or spent more than $$5,000 for the 2026 cycle
                    (52&nbsp;U.S.C.&nbsp;&sect;30101(2)). People the primary removed stay on
                    record and are shown under each race.</p>
                <p>Non-partisan and independent. Data built
                    <time id="buildStamp">&mdash;</time>.</p>
            </footer>
        </div>
    </main>
</div>

$scripts
</body>
</html>
""")

# The state pages render everything from profiles.js on the client.
_STATE_MAIN = """\
            <div id="stateContent" class="state-page">
                <p class="results-bar" role="status">Loading&hellip;</p>
            </div>"""

_STATE_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
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
    return _PAGE.substitute(
        title=_e(f"{name} — Know Your Candidate"),
        og_title=_e(f"{name}: Congress and the 2026 midterms"),
        description=_e(description),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="state",
        search_placeholder=_e(f"Search {name} profiles…"),
        states_current="",
        main=_STATE_MAIN,
        more_sources="",
        scripts=_scripts(_STATE_SCRIPTS),
    )


def render_states_index(host):
    """The directory of every state and territory page."""
    canonical = f"https://{host}/states/index.html" if host else "states/index.html"
    return _PAGE.substitute(
        title=_e("States & territories — Know Your Candidate"),
        og_title=_e("Every state's Congress and 2026 midterm races"),
        description=_e("One page per state and territory: its senators and representatives, "
                       "the 2026 races, and everyone who has filed to run."),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="states",
        search_placeholder=_e("Search states…"),
        states_current=' aria-current="page"',
        main=_STATE_MAIN,
        more_sources="",
        scripts=_scripts(_STATE_SCRIPTS),
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
        '                    </p>',
        '                </header>',
        '                <div id="districtsApp">',
        '                    <p class="results-bar" role="status">Loading the map&hellip;</p>',
        '                </div>',
        '            </div>',
    ])
    scripts = [s.replace("{code}", code.lower()) for s in _DISTRICT_SCRIPTS]
    return _PAGE.substitute(
        title=_e(f"{headline} — Know Your Candidate"),
        og_title=_e(headline),
        description=_e(description),
        canonical=_e(canonical),
        host=_e(host or ""),
        code=_e(code),
        page_kind="districts",
        search_placeholder=_e(f"Search {name} profiles…"),
        states_current="",
        main=main,
        more_sources="",
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


def sitemap(host, codes, built=None, district_maps=()):
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
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
