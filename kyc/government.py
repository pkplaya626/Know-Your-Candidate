"""How government works: the guide's pages.

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
from .government_text import PAGES, REVIEWED, SOURCES

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


def scripts(slug):
    """The scripts a guide page loads after ``kyc.js``, in order."""
    return _PEOPLE_SCRIPTS if _page(slug).get("people") else _PLAIN_SCRIPTS


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


def href(target, here):
    """``(href, external)`` for a link target written on page *here*.

    Raises ``ValueError`` for a target that leads nowhere."""
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
        if not os.path.isfile(os.path.join(SITE, *page.split("/"))):
            raise ValueError(f"{here}: no site page {page!r}")
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
    """Escape *text* for HTML, turning ``[label](target)`` into links."""
    out = []
    last = 0
    for match in _LINK.finditer(text):
        out.append(_text(text[last:match.start()], here))
        url, external = href(match.group(2), here)
        extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
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


def _block(block, here, pad):
    kind = block[0]
    if kind == "p":
        return [f"{pad}<p>{inline(block[1], here)}</p>"]
    if kind == "note":
        return [f'{pad}<p class="guide-note">{inline(block[1], here)}</p>']
    if kind == "h3":
        anchor = f' id="{_e(block[2])}"' if len(block) > 2 else ""
        return [f'{pad}<h3 class="guide-subheading"{anchor}>{inline(block[1], here)}</h3>']
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
        '                    <p class="state-kicker">How government works</p>',
        f'                    <h1 class="state-title">{inline(page["title"], here)}</h1>',
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
                     f'<span>Previous</span> {html.escape(prev["nav"], quote=False)}</a>')
    if at + 1 < len(order):
        nxt = _page(order[at + 1])
        links.append(f'<a class="guide-pager-link next" rel="next" href="{_e(order[at + 1])}.html">'
                     f'<span>Next</span> {html.escape(nxt["nav"], quote=False)}</a>')
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
                     f'{current}>{html.escape(page["nav"], quote=False)}</a>')
    lines.append("        </nav>")
    sidebar = "\n".join(lines) + "\n"
    # A page that loads the profiles can show the chambers' balance too.
    return sidebar + (pages._CONGRESS_SIDEBAR if people else "")


def _footer(page):
    return "\n".join([
        "                <p><strong>About this guide:</strong> a plain-language summary of how",
        "                    American government is organized. Each section lists the sources",
        f'                    it was checked against, on <time datetime="{_e(REVIEWED)}">'
        f"{_e(REVIEWED)}</time>.",
        "                    It describes offices and institutions; where it names who holds",
        "                    one today, that comes from the same data as the rest of the site.",
        "                    It is not legal advice.</p>",
        "                <p>Non-partisan and independent.</p>",
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
    return pages.render_page(
        title=_e(f"{page['title']} — Know Your Candidate"),
        og_title=_e(page["title"]),
        description=_e(page["description"]),
        canonical=_e(canonical),
        host=_e(host or ""),
        code="",
        page_kind="guide",
        search="",
        government_current=' aria-current="page"' if slug == "index" else "",
        sidebar=_sidebar(slug, people),
        jump_options="" if people else jump_options(codes),
        main=_main(page),
        footer=_footer(page),
        scripts="\n".join(f'<script src="{_e(src)}"></script>' for src in scripts(slug)),
    )


def render_all(host, codes=()):
    """``{path inside the site: html}`` for every guide page."""
    return {page_path(slug): render(slug, host, codes) for slug in slugs()}


# -------------------------------------------------------------- validation

def check():
    """Problems with the guide's text, as strings. Empty when it is sound.

    Rendering already raises on a broken link or an unknown source; this also
    finds sources nobody cites and pages missing what the template needs."""
    problems = []
    cited = set()
    seen_ids = {}
    for page in PAGES:
        for key in ("slug", "nav", "title", "lede", "description", "sections"):
            if not page.get(key):
                problems.append(f"{page.get('slug', '?')}: missing {key}")
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
    return problems
