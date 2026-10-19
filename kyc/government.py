"""Know Your Government: the guide's pages.

The site is about the people who hold one set of offices. The guide is about
the offices themselves, and the governments around Congress: the executive
and the courts, the states, local governments and tribal nations. Its pages
are generated like the state pages, from the one template in ``pages``, with
their words in ``government_text``.

The words are static and say so: every section cites the sources it was
checked against, and the footer gives the date they were checked. Anything
that is a fact about the people the site covers - who chairs a committee -
is not typed here; the page renders it from profiles.js (``assets/kyc-guide.js``).

The build refuses a guide with a link to a page, section or state that does
not exist, or a section citing a source the guide does not list: a primer
that says "see the Senate" and goes nowhere looks entirely normal.
"""

import html
import os
import re

from . import pages
from .government_text import HOLDERS, PAGES, REVIEWED, SEE, SOURCES

FOLDER = "government"
# The site's own pages, which a "site:" link must name.
SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "candidate_profiles_site")

# What each guide page loads. Most need only the shared module; a page that
# shows people loads them the way a state page does, so a name opens the
# same profile dialog.
_PLAIN_SCRIPTS = ("../assets/kyc-guide.js",)
_PEOPLE_SCRIPTS = (
    "../data/profiles.js",
    "../data/odds.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-guide.js",
)
# A page with a map draws it the way the partisan map is drawn: the state
# shapes, then what the guide says about each state, then the shared map.
_MAP_SCRIPTS = (
    "../data/geo.js",
    "../data/government.js",
    "../assets/kyc-usmap.js",
    "../assets/kyc-guide.js",
)


def _map_modes(slug):
    from . import government_maps
    return government_maps.modes().get(slug) or []


def page_path(slug):
    """``government/congress.html``."""
    return f"{FOLDER}/{slug}.html"


def slugs():
    return [page["slug"] for page in PAGES]


def _page(slug):
    for page in PAGES:
        if page["slug"] == slug:
            return page
    raise KeyError(slug)


def name(slug):
    """A guide page's one name: its title, its <h1>, its entry in the
    guide's navigation, its card on the overview, the pager's link to it
    and every other page's link to it (rule 75). The navigation said "How
    the federal courts work" over a page titled "The federal courts", and
    "Elections" over "How elections work"."""
    return _page(slug)["title"]


# ----------------------------------------------------------------- figures

# A count the text states that a table elsewhere in the build determines,
# written {{key}}: "In {{ltgov-presides}} states". The text said "about 26"
# lieutenant governors preside while the map, from the same table, coloured
# 24 (rule 73).
_FIGURE = re.compile(r"\{\{([a-z0-9-]+)\}\}")


def figures():
    from . import government_maps
    return government_maps.figures()


def _figures(text, here):
    if "{{" not in text:
        return text
    table = figures()

    def put(match):
        key = match.group(1)
        if key not in table:
            raise ValueError(f"{here}: no figure {key!r}")
        return str(table[key])
    return _FIGURE.sub(put, text)


def scripts(slug):
    """The scripts a guide page loads after ``kyc.js``, in order. A page
    that lists who holds an office (:data:`HOLDERS`) loads the federal
    government's data before the guide's module."""
    base = (_MAP_SCRIPTS if _map_modes(slug) else
            _PEOPLE_SCRIPTS if _page(slug).get("people") else _PLAIN_SCRIPTS)
    if any(page == slug for page, _sid in HOLDERS):
        base = base[:-1] + ("../data/federal.js",) + base[-1:]
    return base


def _after(here, sid, pad, level=3):
    """What follows a section's text: who holds its offices now, and where
    on the site its subject can be seen (:data:`SEE`)."""
    lines = []
    live = HOLDERS.get((here, sid))
    if live:
        # Its own heading: in a section that ends with a subheading
        # ("Changes since 2025") the list would otherwise read as part of it.
        lines.append(f'{pad}<h{level} class="guide-subheading">{html.escape(live[1], quote=False)}</h{level}>')
        lines += _block(("live", live[0], live[2]), here, pad)
    see = SEE.get((here, sid))
    if see:
        links = []
        for words, target in see:
            url, external = href(target, here)
            extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
            links.append(f'<a href="{_e(url)}"{extra}>{html.escape(words, quote=False)}</a>')
        lines.append(f'{pad}<p class="guide-see"><span>See it on this site:</span> '
                     + '<span class="sep" aria-hidden="true"> · </span>'.join(links) + "</p>")
    return lines


def _e(text):
    return html.escape(str(text), quote=True)


# ------------------------------------------------------------------- links

# [label](target). Targets:
#   #section               a section of this page
#   guide:congress#senate  another guide page, or a section of one
#   site:map.html          a page of the site, from its root
#   state:TX               a state's page
#   https://...            somewhere else, opened in a new tab
_LINK = re.compile(r"\[([^\[\]]+)\]\(([^()\s]+)\)")


def _section_ids(slug):
    page = _page(slug)
    ids = set()
    for section in page["sections"]:
        ids.add(section["id"])
        for block in section["blocks"]:
            if block[0] == "h3" and len(block) > 2:
                ids.add(block[2])
    return ids


# Pages the same build writes, which a fresh checkout has before its first
# build: the directories the guide links.
_GENERATED = {"legislature/index.html", "counties/index.html"}
# The sections a site page's script draws, which a link may name: the
# federal hub's (assets/kyc-federal.js; tests/test_guide.py holds the two
# to each other).
SITE_ANCHORS = {"federal/index.html": ("executive", "cabinet", "changes", "supreme-court", "courts")}


#   voting:                the reader's state's voting section (VOTING)
# The elections page sent "your state's official voting pages" to the
# states' index, two clicks from the registration and polling-place links.
VOTING = "voting:"


def href(target, here):
    """``(href, external)`` for a link target written on page *here*.

    Raises ``ValueError`` for a target that leads nowhere."""
    if target == VOTING:
        return "../states/index.html", False
    if target.startswith("https://"):
        return target, True
    if target.startswith("#"):
        if target[1:] not in _section_ids(here):
            raise ValueError(f"{here}: no section {target!r} on this page")
        return target, False
    kind, _, rest = target.partition(":")
    if kind == "guide":
        slug, _, anchor = rest.partition("#")
        if slug not in slugs():
            raise ValueError(f"{here}: no guide page {slug!r}")
        if anchor and anchor not in _section_ids(slug):
            raise ValueError(f"{here}: no section {anchor!r} on guide page {slug!r}")
        return f"{slug}.html" + (f"#{anchor}" if anchor else ""), False
    if kind == "site":
        if not rest or rest.startswith(("/", ".")):
            raise ValueError(f"{here}: site link {rest!r} must be relative to the root")
        page = rest.split("#")[0].split("?")[0]
        if not os.path.isfile(os.path.join(SITE, *page.split("/"))) and page not in _GENERATED:
            raise ValueError(f"{here}: no site page {page!r}")
        anchor = rest.partition("#")[2]
        if anchor and not anchor.startswith("/") and anchor not in SITE_ANCHORS.get(page, ()):
            raise ValueError(f"{here}: no section {anchor!r} on site page {page!r}")
        return "../" + rest, False
    if kind == "state":
        if rest not in pages.STATE_NAMES:
            raise ValueError(f"{here}: no state {rest!r}")
        return "../" + pages.page_path(rest), False
    raise ValueError(f"{here}: unknown link target {target!r}")


# What is left of a link the pattern could not read: "[label](" with a
# parenthesis in its target, say. It would reach the page as raw markup.
_UNREAD = re.compile(r"\]\(|\[[^\]]*\]\s*\(")


def _text(segment, here):
    if _UNREAD.search(segment):
        raise ValueError(f"{here}: link markup the build cannot read: {segment.strip()[:80]!r}")
    return html.escape(segment, quote=False)


def inline(text, here):
    """Escape *text* for HTML, turning ``[label](target)`` into links and
    ``{{key}}`` into the figure the build counts (:func:`figures`)."""
    text = _figures(text, here)
    out = []
    last = 0
    for match in _LINK.finditer(text):
        out.append(_text(text[last:match.start()], here))
        target = match.group(2)
        url, external = href(target, here)
        extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
        if target == VOTING:
            # The reader's own state's voting section, once the page knows
            # their state (kyc-guide.js); the states' index until then.
            extra += " data-voting-link"
        out.append(f'<a href="{_e(url)}"{extra}>'
                   f'{html.escape(match.group(1), quote=False)}</a>')
        last = match.end()
    out.append(_text(text[last:], here))
    return "".join(out)


# ------------------------------------------------------------------ blocks

def _table(spec, here, pad):
    head = spec["head"]
    lines = [f'{pad}<div class="guide-table-wrap">',
             f'{pad}    <table class="guide-table">']
    if spec.get("caption"):
        lines.append(f'{pad}        <caption>{inline(spec["caption"], here)}</caption>')
    lines.append(f'{pad}        <thead><tr>' + "".join(
        f'<th scope="col">{inline(h, here)}</th>' for h in head) + "</tr></thead>")
    lines.append(f"{pad}        <tbody>")
    for row in spec["rows"]:
        if len(row) != len(head):
            raise ValueError(f"{here}: a table row has {len(row)} cells for {len(head)} columns")
        cells = [f'<th scope="row">{inline(row[0], here)}</th>'] + [
            f'<td data-label="{_e(head[i])}">{inline(cell, here)}</td>'
            for i, cell in enumerate(row) if i]
        lines.append(f"{pad}            <tr>{''.join(cells)}</tr>")
    lines.append(f"{pad}        </tbody>")
    lines.append(f"{pad}    </table>")
    lines.append(f"{pad}</div>")
    return lines


def _flow(spec, here, pad):
    """A process drawn as boxes joined by a line (kyc.css .guide-flow): page
    text in HTML, never SVG text (rule 46). A step's options are the ways
    it can end, side by side."""
    lines = [f'{pad}<figure class="guide-flow">',
             f'{pad}    <ol class="guide-flow-steps">']
    for step in spec["steps"]:
        lines.append(f'{pad}        <li class="guide-flow-step"><strong>{inline(step[0], here)}</strong>'
                     f'<span>{inline(step[1], here)}</span>')
        if len(step) > 2 and step[2]:
            lines.append(f'{pad}            <ul class="guide-flow-options">')
            for title, text in step[2]:
                lines.append(f'{pad}                <li><strong>{inline(title, here)}</strong>'
                             f'<span>{inline(text, here)}</span></li>')
            lines.append(f"{pad}            </ul>")
        lines.append(f"{pad}        </li>")
    lines.append(f"{pad}    </ol>")
    if spec.get("caption"):
        lines.append(f'{pad}    <figcaption>{inline(spec["caption"], here)}</figcaption>')
    return lines + [f"{pad}</figure>"]


def _checks(spec, here, pad):
    """Who checks whom: a box per branch, each listing its checks on the
    others, an arrow and the branch it acts on before each."""
    lines = [f'{pad}<figure class="guide-checks">',
             f'{pad}    <ul class="guide-checks-row">']
    for branch, checks in spec["branches"]:
        lines.append(f'{pad}        <li class="guide-checks-branch"><strong>{inline(branch, here)}</strong>')
        lines.append(f'{pad}            <ul>')
        for target, how in checks:
            lines.append(f'{pad}                <li><span class="guide-checks-on">'
                         f'<span aria-hidden="true">→ </span>{inline(target, here)}:</span> '
                         f'{inline(how, here)}</li>')
        lines.append(f"{pad}            </ul>")
        lines.append(f"{pad}        </li>")
    lines.append(f"{pad}    </ul>")
    if spec.get("caption"):
        lines.append(f'{pad}    <figcaption>{inline(spec["caption"], here)}</figcaption>')
    return lines + [f"{pad}</figure>"]


def _ladder(spec, here, pad):
    """Court systems side by side, highest court first, with the paths a
    case takes between them below."""
    lines = [f'{pad}<figure class="guide-ladder">',
             f'{pad}    <div class="guide-ladder-row">']
    for heading, rungs in spec["columns"]:
        lines.append(f'{pad}        <div class="guide-ladder-col">')
        lines.append(f'{pad}            <p class="guide-ladder-head">{inline(heading, here)}</p>')
        lines.append(f'{pad}            <ol class="guide-ladder-rungs">')
        for court, text in rungs:
            lines.append(f'{pad}                <li><strong>{inline(court, here)}</strong>'
                         f'<span>{inline(text, here)}</span></li>')
        lines.append(f"{pad}            </ol>")
        lines.append(f"{pad}        </div>")
    lines.append(f"{pad}    </div>")
    if spec.get("paths"):
        lines.append(f'{pad}    <ul class="guide-ladder-paths">')
        for title, text in spec["paths"]:
            lines.append(f'{pad}        <li><strong>{inline(title, here)}</strong> {inline(text, here)}</li>')
        lines.append(f"{pad}    </ul>")
    if spec.get("caption"):
        lines.append(f'{pad}    <figcaption>{inline(spec["caption"], here)}</figcaption>')
    return lines + [f"{pad}</figure>"]


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")

# The statuses a timeline step may name: keys of KYC.raceStatus's table
# (assets/kyc.js RACE_STATUS), and "awaiting", a nominee after Election Day.
TIMELINE_STATUSES = ("nominee", "awaiting", "elected", "defeated", "runoff")


def _timeline(spec, here, pad):
    """Dated steps in order. Each may name the result statuses this site
    shows at that step: their words are the site's one status table's
    (KYC.raceStatus), filled in by kyc-guide.js; the words written here are
    what a page without the script shows."""
    lines = [f'{pad}<figure class="guide-timeline">',
             f'{pad}    <ol class="guide-timeline-steps">']
    last = ""
    for day, label, title, parts in spec["items"]:
        if not _DATE.match(day) or day < last:
            raise ValueError(f"{here}: timeline dates must be ISO dates in order: {day!r}")
        last = day
        words = []
        for part in parts:
            if isinstance(part, str):
                # Punctuation closes up on the status before it.
                words.append(("" if part[:1] in ".,;:" or not words else " ") + inline(part, here))
            else:
                key, text = part
                if key not in TIMELINE_STATUSES:
                    raise ValueError(f"{here}: no status {key!r} in the site's table")
                words.append(f' <span class="badge guide-status" data-status="{_e(key)}">'
                             f'{html.escape(text, quote=False)}</span>')
        lines.append(f'{pad}        <li data-date="{_e(day)}"><time datetime="{_e(day)}">'
                     f'{html.escape(label, quote=False)}</time><strong>{inline(title, here)}</strong>'
                     f'<span>{"".join(words)}</span></li>')
    lines.append(f"{pad}    </ol>")
    if spec.get("caption"):
        lines.append(f'{pad}    <figcaption>{inline(spec["caption"], here)}</figcaption>')
    return lines + [f"{pad}</figure>"]


def _redrawn(here, pad):
    """The states whose 2026 House map is not 2024's, as kyc/districts.REDRAWN
    records each from the enacting body's own record, each linking its
    before-and-after district page. Read from the table, never retyped, so
    a state added there is listed here."""
    from . import districts
    lines = [f'{pad}<ul class="guide-list guide-redrawn">']
    for code in sorted(districts.REDRAWN, key=pages.state_name):
        after = districts.REDRAWN[code].get("after") or {}
        words = [f'<a href="../{_e(districts.PAGE_DIR)}/{_e(code.lower())}.html">'
                 f'{html.escape(pages.state_name(code), quote=False)}</a>:']
        if after.get("title"):
            words.append(html.escape(after["title"], quote=False))
        if after.get("drawnBy"):
            words.append("— drawn by " + html.escape(after["drawnBy"], quote=False))
        lines.append(f"{pad}    <li>{' '.join(words)}.</li>")
    return lines + [f"{pad}</ul>"]


def _voting_picker(here, pad):
    """A state picker that opens that state's voting section."""
    options = "".join(
        f'<option value="{_e(code)}">{_e(pages.state_name(code))}</option>'
        for code in sorted(pages.STATE_NAMES, key=pages.state_name))
    return [f'{pad}<form class="guide-voting" action="../states/index.html" data-voting-picker>',
            f'{pad}    <label for="votingState">Your state or territory</label>',
            f'{pad}    <select id="votingState" class="select"><option value="">Choose…</option>'
            f"{options}</select>",
            f'{pad}    <button type="submit" class="btn">Open its voting pages</button>',
            f"{pad}</form>"]


def _cards(here, pad):
    """A card for every page of the guide after this one, each with its
    one name (:func:`name`) and its own summary."""
    lines = [f'{pad}<ul class="guide-cards">']
    for page in PAGES:
        if page["slug"] == here:
            continue
        lines.append(f'{pad}    <li><a class="guide-card" href="{_e(page["slug"])}.html">'
                     f'<strong>{html.escape(name(page["slug"]), quote=False)}</strong>'
                     f'<span>{html.escape(page["card"], quote=False)}</span></a></li>')
    return lines + [f"{pad}</ul>"]


def _block(block, here, pad, level=3):
    """One block of a section's text. *level* is the level of the section's
    subheadings: h3 on a page of sections, h4 inside a map page's folded
    sections, whose own titles are h3."""
    kind = block[0]
    if kind == "p":
        return [f"{pad}<p>{inline(block[1], here)}</p>"]
    if kind == "note":
        return [f'{pad}<p class="guide-note">{inline(block[1], here)}</p>']
    if kind == "h3":
        anchor = f' id="{_e(block[2])}"' if len(block) > 2 else ""
        return [f'{pad}<h{level} class="guide-subheading"{anchor}>{inline(block[1], here)}</h{level}>']
    if kind == "flow":
        return _flow(block[1], here, pad)
    if kind == "checks":
        return _checks(block[1], here, pad)
    if kind == "ladder":
        return _ladder(block[1], here, pad)
    if kind == "timeline":
        return _timeline(block[1], here, pad)
    if kind == "redrawn":
        return _redrawn(here, pad)
    if kind == "voting-picker":
        return _voting_picker(here, pad)
    if kind == "guide-cards":
        return _cards(here, pad)
    if kind == "ul":
        return ([f'{pad}<ul class="guide-list">'] +
                [f"{pad}    <li>{inline(item, here)}</li>" for item in block[1]] +
                [f"{pad}</ul>"])
    if kind == "roles":
        lines = [f'{pad}<dl class="guide-roles">']
        for term, text in block[1]:
            lines.append(f'{pad}    <div class="guide-role"><dt>{inline(term, here)}</dt>'
                         f'<dd>{inline(text, here)}</dd></div>')
        return lines + [f"{pad}</dl>"]
    if kind == "table":
        return _table(block[1], here, pad)
    if kind == "chart":
        spec = block[1]
        lines = [f'{pad}<figure class="guide-chart">',
                 f'{pad}    <p class="guide-chart-top">{inline(spec["top"], here)}</p>',
                 f'{pad}    <ul class="guide-chart-row">']
        for title, text in spec["items"]:
            lines.append(f'{pad}        <li><strong>{inline(title, here)}</strong>'
                         f'<span>{inline(text, here)}</span></li>')
        lines.append(f"{pad}    </ul>")
        if spec.get("caption"):
            lines.append(f'{pad}    <figcaption>{inline(spec["caption"], here)}</figcaption>')
        return lines + [f"{pad}</figure>"]
    if kind == "cards":
        lines = [f'{pad}<ul class="guide-cards">']
        for title, target, text in block[1]:
            url, external = href(target, here)
            extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
            lines.append(f'{pad}    <li><a class="guide-card" href="{_e(url)}"{extra}>'
                         f'<strong>{html.escape(title, quote=False)}</strong>'
                         f'<span>{html.escape(text, quote=False)}</span></a></li>')
        return lines + [f"{pad}</ul>"]
    if kind == "live":
        # Filled by assets/kyc-guide.js from the site's data; what it says
        # without JavaScript is the fallback, not an empty box.
        return [f'{pad}<div class="guide-live" data-live="{_e(block[1])}">',
                f'{pad}    <p class="results-bar" role="status">{inline(block[2], here)}</p>',
                f"{pad}</div>"]
    raise ValueError(f"{here}: unknown block {kind!r}")


def _sources(keys, here):
    links = []
    for key in keys:
        if key not in SOURCES:
            raise ValueError(f"{here}: unknown source {key!r}")
        title, url = SOURCES[key]
        links.append(f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">'
                     f"{html.escape(title, quote=False)}</a>")
    return "; ".join(links)


def _main(page):
    here = page["slug"]
    pad = " " * 16
    lines = [
        '            <article id="guideContent" class="state-page guide-page">',
        '                <header class="state-hero">',
        # The guide's own front page is named Know Your Government already.
        '                    <p class="state-kicker">'
        + ("A guide to American government" if here == "index" else "Know Your Government")
        + "</p>",
        f'                    <h1 class="state-title">{html.escape(name(here), quote=False)}</h1>',
        f'                    <p class="guide-lede">{inline(page["lede"], here)}</p>',
        "                </header>",
    ]
    if len(page["sections"]) > 2:
        lines.append('                <nav class="guide-toc" aria-labelledby="guideTocTitle">')
        lines.append('                    <h2 class="guide-toc-title" id="guideTocTitle">'
                     "On this page</h2>")
        lines.append("                    <ol>")
        for section in page["sections"]:
            lines.append(f'                        <li><a href="#{_e(section["id"])}">'
                         f'{html.escape(section["heading"], quote=False)}</a></li>')
        lines.append("                    </ol>")
        lines.append("                </nav>")
    for section in page["sections"]:
        sid = section["id"]
        lines.append(f'{pad}<section class="guide-section" id="{_e(sid)}" '
                     f'aria-labelledby="{_e(sid)}-title">')
        lines.append(f'{pad}    <h2 class="guide-heading" id="{_e(sid)}-title">'
                     f'{html.escape(section["heading"], quote=False)}</h2>')
        for block in section["blocks"]:
            lines.extend(_block(block, here, pad + "    "))
        lines.extend(_after(here, sid, pad + "    "))
        if not section.get("sources"):
            raise ValueError(f"{here}#{sid}: a section with no sources")
        lines.append(f'{pad}    <p class="guide-sources"><span>Sources:</span> '
                     f'{_sources(section["sources"], here)}</p>')
        lines.append(f"{pad}</section>")
    lines.extend(_pager(here))
    lines.append("            </article>")
    return "\n".join(lines)


def _pager(here):
    order = slugs()
    at = order.index(here)
    links = []
    if at > 0:
        prev = _page(order[at - 1])
        links.append(f'<a class="guide-pager-link" rel="prev" href="{_e(order[at - 1])}.html">'
                     f'<span>Previous</span> {html.escape(name(prev["slug"]), quote=False)}</a>')
    if at + 1 < len(order):
        nxt = _page(order[at + 1])
        links.append(f'<a class="guide-pager-link next" rel="next" href="{_e(order[at + 1])}.html">'
                     f'<span>Next</span> {html.escape(name(nxt["slug"]), quote=False)}</a>')
    return (['                <nav class="guide-pager" aria-label="Guide pages">'] +
            [f"                    {link}" for link in links] +
            ["                </nav>"])


def _sidebar(here, people):
    lines = ["",
             '        <nav class="sidebar-section" aria-label="In this guide">',
             '            <h2 class="sidebar-heading">In this guide</h2>']
    for page in PAGES:
        current = ' aria-current="page"' if page["slug"] == here else ""
        lines.append(f'            <a class="nav-link nav-sub" href="{_e(page["slug"])}.html"'
                     f'{current}>{html.escape(name(page["slug"]), quote=False)}</a>')
    lines.append("        </nav>")
    sidebar = "\n".join(lines) + "\n"
    # A page that loads the profiles can show the chambers' balance too.
    return sidebar + (pages._CONGRESS_SIDEBAR if people else "")


def _section_lines(section, here, pad, collapsed, first=False):
    """One of the page's text sections; folded into a <details> on a map
    page, where it reads below the panel's facts.

    Its title is a heading inside the <summary>, so a screen reader's list
    of headings and a search engine find the page's sections (they were
    bare <summary> text), and the first section is open: a reader landing
    on the federal courts' page saw a map and five closed rows."""
    sid = section["id"]
    lines = []
    if collapsed:
        lines.append(f'{pad}<details class="guide-more-section" id="{_e(sid)}"{" open" if first else ""}>')
        lines.append(f'{pad}    <summary><h3 class="guide-more-heading">'
                     f'{html.escape(section["heading"], quote=False)}</h3></summary>')
    for block in section["blocks"]:
        lines.extend(_block(block, here, pad + "    ", level=4 if collapsed else 3))
    lines.extend(_after(here, sid, pad + "    ", level=4 if collapsed else 3))
    lines.append(f'{pad}    <p class="guide-sources"><span>Sources:</span> '
                 f'{_sources(section["sources"], here)}</p>')
    if collapsed:
        lines.append(f"{pad}</details>")
    return lines


def _map_main(page, modes, footer):
    """The map layout of map.html: a toolbar of views over the map, and a
    panel that shows the picked state's facts, what the current view means,
    and the page's text below them."""
    from . import government_maps
    here = page["slug"]
    first = modes[0]
    pad = " " * 12
    lines = [
        '    <main class="app-main" id="stateMain">',
        '        <header class="guide-map-head">',
        '            <p class="state-kicker">Know Your Government</p>',
        f'            <h1 class="guide-map-title">{html.escape(name(here), quote=False)}</h1>',
        '        </header>',
        '        <div class="toolbar">',
        '            <div class="map-legend" id="mapLegend" aria-live="polite"></div>',
    ]
    if len(modes) > 1:
        lines.append('            <div class="segmented push-right" role="group" aria-label="Map view">')
        for i, mode in enumerate(modes):
            lines.append(f'                <button type="button" data-mode="{_e(mode["id"])}" '
                         f'aria-pressed="{"true" if i == 0 else "false"}">'
                         f'{html.escape(mode["label"], quote=False)}</button>')
        lines.append("            </div>")
    lines += [
        "        </div>",
        '        <div class="map-stage" id="mapStage">',
        '            <svg id="usMap" viewBox="0 0 975 652" preserveAspectRatio="xMidYMid meet"',
        '                 role="group" aria-label="Map of U.S. states and territories.',
        '                 Each state is a button that shows what this page says about it."></svg>',
        "        </div>",
        "    </main>",
        "",
        f'    <aside class="detail-panel" aria-label="{_e(name(here))}, state by state">',
        '        <div class="detail-head">',
        '            <div class="detail-title">',
        '                <h2>',
        '                    <svg class="icon icon-sm" aria-hidden="true"><use href="#i-pin"/></svg>',
        '                    <span id="panelState">Select a state</span>',
        "                </h2>",
        "            </div>",
        f'            <p class="detail-sub" id="panelMode">{html.escape(first["title"], quote=False)}</p>',
        '            <a class="sidebar-link" id="panelStateLink" href="../states/index.html" hidden></a>',
        "        </div>",
        '        <div class="delegation scroll-y guide-panel" id="guideContent">',
        '            <div id="guideFacts" aria-live="polite"></div>',
    ]
    for i, mode in enumerate(modes):
        hidden = "" if i == 0 else " hidden"
        lines.append(f'{pad}<section class="guide-about" data-mode="{_e(mode["id"])}"{hidden}>')
        lines.append(f'{pad}    <h3 class="guide-about-title">{html.escape(mode["title"], quote=False)}</h3>')
        lines.append(f'{pad}    <p>{inline(mode["about"], here)}</p>')
        links = []
        # A view whose sources are each state's own cites them on the state
        # (government_maps "aboutSources", "aboutNote"), not all at once here.
        for key in mode.get("aboutSources", mode["sources"]):
            title, url = government_maps.SOURCES[key]
            links.append(f'<a href="{_e(url)}" target="_blank" rel="noopener noreferrer">'
                         f"{html.escape(title, quote=False)}</a>")
        if mode.get("aboutNote"):
            links.append(html.escape(mode["aboutNote"], quote=False))
        lines.append(f'{pad}    <p class="guide-sources"><span>Sources:</span> {"; ".join(links)}</p>')
        lines.append(f"{pad}</section>")
    lines.append(f'{pad}<div class="guide-more">')
    # The page's text: an h2, like the panel's own heading, over the
    # sections' h3s.
    lines.append(f'{pad}    <h2 class="guide-more-title">Sections of this page</h2>')
    for i, section in enumerate(page["sections"]):
        lines.extend(_section_lines(section, here, pad + "    ", collapsed=True, first=i == 0))
    lines.append(f"{pad}</div>")
    lines.extend(_pager(here))
    lines.append(f'{pad}<footer class="site-footer">')
    lines.append(footer)
    lines.append(f"{pad}</footer>")
    lines += ["        </div>", "    </aside>"]
    return "\n".join(lines)


def _footer(page):
    # A page checked on another day than the rest of the guide says so.
    reviewed = page.get("reviewed", REVIEWED)
    return "\n".join([
        "                <p><strong>About this guide:</strong> a plain-language summary of how",
        "                    American government is organized. Each section lists the sources",
        f"                    it was checked against, on {pages.time_html(reviewed)}.",
        "                    It describes offices and institutions; where it names who holds",
        "                    one today, that comes from the same data as the rest of the site.",
        "                    It is not legal advice.</p>",
    ])


def jump_options(codes):
    """The "Jump to" list, written into the page: the guide's pages do not
    load the build metadata that fills it elsewhere."""
    named = sorted(codes, key=lambda c: pages.state_name(c))
    return "".join(f'\n                <option value="{_e(c)}">{_e(pages.state_name(c))} '
                   f"({_e(c)})</option>" for c in named)


def render(slug, host, codes=()):
    """The HTML for one guide page."""
    page = _page(slug)
    path = page_path(slug)
    canonical = f"https://{host}/{path}" if host else path
    people = bool(page.get("people"))
    modes = _map_modes(slug)
    # A map page writes its footer into its own panel, through the same
    # helper that ends every other page (rule 12).
    layout = ({"main_block": _map_main(page, modes, pages.footer_html(
                  _footer(page), "../", None, f"https://{host}/{path}" if host else None))}
              if modes else {"main": _main(page), "footer": _footer(page)})
    crumbs = [pages._HOME, (pages.section_name("guide"), page_path("index"))]
    if slug != "index":
        crumbs.append((name(slug), path))
    return pages.render_page(
        title=_e(f"{name(slug)} — Know Your Candidate"),
        og_title=_e(name(slug)),
        description=_e(page["description"]),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind=f"guide-{slug}" if modes else "guide",
        search="",
        nav_current="guide",
        nav_how="page" if slug == "index" else "true",
        sidebar=_sidebar(slug, people),
        jump_options="" if people else jump_options(codes),
        # On a map page the list picks the state on the map (kyc-guide.js);
        # on the elections page it opens the state's voting section.
        jump_attrs=(' data-jump="map"' if modes else
                    ' data-jump-to="states/{code}.html#voting"' if slug == "elections" else ""),
        crumbs=crumbs,
        scripts=pages._scripts(scripts(slug)),
        **layout,
    )


def render_all(host, codes=()):
    """``{path inside the site: html}`` for every guide page."""
    return {page_path(slug): render(slug, host, codes) for slug in slugs()}


# -------------------------------------------------------------- validation

def revisits(today):
    """``[(slug, date, what)]``: each page's dated text whose date has passed
    since the page was last checked (``reviewed``)."""
    out = []
    for page in PAGES:
        reviewed = page.get("reviewed", REVIEWED)
        for day, what in page.get("revisit") or ():
            if reviewed < day <= today:
                out.append((page["slug"], day, what))
    return out


def check():
    """Problems with the guide's text, as strings. Empty when it is sound.

    Rendering already raises on a broken link or an unknown source; this also
    finds sources nobody cites and pages missing what the template needs."""
    problems = []
    cited = set()
    seen_ids = {}
    for page in PAGES:
        for key in ("slug", "title", "card", "lede", "description", "sections"):
            if not page.get(key):
                problems.append(f"{page.get('slug', '?')}: missing {key}")
        for entry in page.get("revisit") or ():
            if (len(entry) != 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry[0]))
                    or not str(entry[1]).strip()):
                problems.append(f"{page['slug']}: a revisit entry is not (date, what): {entry!r}")
        for section in page.get("sections", ()):
            cited.update(section.get("sources") or ())
            ids = seen_ids.setdefault(page.get("slug"), set())
            if section["id"] in ids:
                problems.append(f"{page['slug']}: section id {section['id']!r} used twice")
            ids.add(section["id"])
        try:
            _main(page)
        except (ValueError, KeyError) as error:
            problems.append(str(error))
    for key, (title, url) in SOURCES.items():
        if key not in cited:
            problems.append(f"source {key!r} is listed but no section cites it")
        if not url.startswith("https://"):
            problems.append(f"source {key!r} is not an https URL: {url}")
    if slugs()[0] != "index":
        problems.append("the guide's first page must be its index")
    # Every "see it" and "who holds it" entry belongs to a section there is.
    for table, name in ((SEE, "SEE"), (HOLDERS, "HOLDERS")):
        for page, sid in table:
            if page not in slugs() or sid not in _section_ids(page):
                problems.append(f"{name} names a section the guide does not have: {page}#{sid}")
    return problems
