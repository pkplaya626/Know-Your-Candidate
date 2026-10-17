"""A page and the code it runs are one version.

A reload fetches the page again but keeps a script it cached minutes before
(GitHub Pages serves every file with ``max-age=600``). Minutes after the
deploy of 2026-10-17 the new index.html ran the previous kyc-directory.js,
which looked for the sort's old ``<select>``, threw, and left the grid on
"Loading profiles..." until a filter chip was clicked - and the new sort
menu, never wired, did nothing.

So every local script and stylesheet URL carries ``?v=`` and the first ten
hex digits of its file's content hash: a changed file is a new URL, and a
page never runs an older copy of its code. Line endings are folded first, so
a Windows checkout and CI stamp alike. The generated pages are stamped as
they are rendered; the two hand-maintained templates (index.html, map.html)
are restamped by the build, which changes nothing else in them, and
``verify`` fails on a stale stamp. Data files are not stamped: the odds job
commits ``data/odds.js`` twice a day and may change no other file (rule 41).
"""

import hashlib
import os
import re

SITE_DIR = "candidate_profiles_site"
ASSETS_DIR = os.path.join(SITE_DIR, "assets")
TEMPLATES = ("index.html", "map.html")

# src="assets/kyc.js", href="../assets/kyc.css?v=0123456789": the URL, the
# file's name, and any stamp it already carries (replaced).
_REF = re.compile(r'((?:src|href)=")((?:\.\./)*assets/([A-Za-z0-9_.-]+\.(?:js|css)))'
                  r'(?:\?v=[0-9a-f]*)?(")')


def version(name, root="."):
    """The stamp for ``assets/<name>``: its content hash, line endings folded.
    The assets are code, shipped with the repository: a build into a folder
    with no ``assets/`` of its own (a test's) stamps with the repository's."""
    folder = os.path.join(root, ASSETS_DIR)
    if not os.path.isdir(folder):
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              ASSETS_DIR)
    with open(os.path.join(folder, name), "rb") as handle:
        data = handle.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:10]


def stamp(html, root="."):
    """*html* with every local script and stylesheet URL stamped with the
    current version of its file. A reference to a file that does not exist
    raises: a page loading a missing script is a broken page (rule 14)."""
    seen = {}

    def one(match):
        name = match.group(3)
        if name not in seen:
            seen[name] = version(name, root)
        return f"{match.group(1)}{match.group(2)}?v={seen[name]}{match.group(4)}"

    return _REF.sub(one, html)


def stamp_templates(root=".", write=True):
    """Restamp the hand-maintained templates. Returns the names of those
    whose stamps were stale (and, with *write*, are no longer)."""
    stale = []
    for name in TEMPLATES:
        path = os.path.join(root, SITE_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", newline="") as handle:
            html = handle.read()
        stamped = stamp(html, root)
        if stamped != html:
            stale.append(name)
            if write:
                tmp = f"{path}.tmp"
                with open(tmp, "w", encoding="utf-8", newline="") as handle:
                    handle.write(stamped)
                os.replace(tmp, path)
    return stale


def unstamped(html):
    """The local script and stylesheet URLs in *html* with no stamp."""
    return re.findall(r'(?:src|href)="((?:\.\./)*assets/[A-Za-z0-9_.-]+\.(?:js|css))"', html)
