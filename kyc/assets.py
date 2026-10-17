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
``verify`` fails on a stale stamp.

The data files the code reads are stamped too, or a reload could pair fresh
code with data cached from before the deploy - and code and data ship
together. A data file's stamp is its content signature (the one ``verify``
reads, which leaves out the build time), so a rebuild of the same data
restamps nothing (rule 18). Except ``data/odds.js``: the odds job commits it
twice a day and may change no other file (rule 41), so no page names its
version.
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
# src="../data/districts/ca.js": a data file, by its path under data/.
_DATA = re.compile(r'(src=")((?:\.\./)*data/([A-Za-z0-9_./-]+\.js))(?:\?v=[0-9a-f]*)?(")')
UNSTAMPED_DATA = frozenset({"odds.js"})       # rule 41

_signatures = {}


def version(name, root="."):
    """The stamp for ``assets/<name>``: its content hash, line endings folded.
    A root with no such file raises (``verify`` on a copy without its code
    must not pass against another tree's)."""
    with open(os.path.join(root, ASSETS_DIR, name), "rb") as handle:
        data = handle.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:10]


def data_version(name, root="."):
    """The stamp for ``data/<name>``: the start of its content signature.
    A data file with none raises: it is not one the build wrote."""
    from .emit import read_signature

    path = os.path.join(root, SITE_DIR, "data", *name.split("/"))
    info = os.stat(path)
    key = (os.path.abspath(path), info.st_mtime_ns, info.st_size)
    if key not in _signatures:
        _signatures[key] = read_signature(path=path)
    if not _signatures[key]:
        raise ValueError(f"{path} carries no content signature to stamp it with")
    return _signatures[key][:10]


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

    def data(match):
        name = match.group(3)
        if name in UNSTAMPED_DATA:
            return f"{match.group(1)}{match.group(2)}{match.group(4)}"
        key = "data:" + name
        if key not in seen:
            seen[key] = data_version(name, root)
        return f"{match.group(1)}{match.group(2)}?v={seen[key]}{match.group(4)}"

    return _DATA.sub(data, _REF.sub(one, html))


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
    """The local script, stylesheet and data URLs in *html* with no stamp
    (``data/odds.js`` is meant to have none)."""
    code = re.findall(r'(?:src|href)="((?:\.\./)*assets/[A-Za-z0-9_.-]+\.(?:js|css))"', html)
    data = [ref for ref in re.findall(r'src="((?:\.\./)*data/[A-Za-z0-9_./-]+\.js)"', html)
            if ref.split("data/", 1)[1] not in UNSTAMPED_DATA]
    return code + data
