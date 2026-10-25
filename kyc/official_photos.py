"""What every photograph taken from an official page shares (rule 87): the
images a page offers and the words beside each, a photograph's weight read
from the file, the size chosen from what the page itself offers, and the
record each cached photograph must carry.

Weight is rule 87's, as for every other portrait (the owner's decision of
2026-10-25, "more content is better than strict rules", which replaced the
brief of 2026-10-19 that left out anything offered only above the caps): of
the sizes a source offers, the narrowest within the caps
(``photos.MAX_PORTRAIT_BYTES`` and ``MAX_PORTRAIT_PX``, about 300 KB and
1,200px) is taken; where every size is over them, the same file smaller
from its host's own resizer or Photon (``photos.lighter_form``, weighed and
checked to be the same shape); and where neither serves it, the file itself
is shown all the same and said (``portraitHeavy``). A photograph a route ties
to the person is never left out for its weight. Smaller copies made here of
what is shown heavy are rule 101's (feature/photo-copies), keyed by the
photograph's address, which the record keeps.

A record names the photograph's address, the page it was read on, the words
on that page that name the person beside it (``evidence``), the day it was
read and its bytes and pixel size. ``record_problems`` says what one lacks;
the build fails a shown photograph that lacks any of it. ``held_back`` asks
the lists a person keeps - ``overrides.NOT_A_PORTRAIT`` (rule 38) and
``overrides.PORTRAIT_LICENCE_DOUBTS`` (rule 82) - of every record, read or
kept from an earlier read.
"""

import datetime
import html
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .photos import MAX_PORTRAIT_BYTES, MAX_PORTRAIT_PX, too_heavy

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")

WIKIMEDIA_AGENT = "know-your-candidate/2.1 (open-source civic data project)"
# One request a second to any one host.
PACE = 1.0
_LAST = {}
_PACE_LOCK = threading.Lock()

# Why a photograph was not taken, as the build counts them. Weight is
# never one (rule 87): a heavy photograph is shown and said.
UNKNOWN = "unknown"         # could not be read (rule 8): the last one is kept
NONE = "none"               # nothing on the page passed

# The narrowest size worth taking when a page offers several: the pages
# draw these photographs in 32-72px circles, so 160px is sharp on any screen.
PREFERRED_WIDTH = 160
# The smallest side a portrait may have at all.
MIN_SIDE = 80

RECORD_KEYS = ("photo", "page", "evidence", "read", "bytes", "width", "height")


# ------------------------------------------------------------------ a page

def _attr(tag, name):
    found = re.search(rf'\b{name}\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', tag, re.I)
    if not found:
        return ""
    return html.unescape(found.group(1) if found.group(1) is not None else found.group(2))


def _text(fragment):
    no_comments = re.sub(r"<!--.*?-->", " ", fragment or "", flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", no_comments)).split())


def offered(page_url, srcset, src=""):
    """``[(width or 0, url)]``: every size *srcset* (and *src*) offers, as
    absolute addresses, narrowest first; *src*'s width is unknown (0) and
    it comes last."""
    sizes = []
    for part in (srcset or "").split(","):
        bits = part.split()
        if len(bits) == 2 and re.fullmatch(r"\d+w", bits[1]):
            sizes.append((int(bits[1][:-1]), urllib.parse.urljoin(page_url, bits[0])))
    sizes.sort()
    out = [s for s in sizes]
    if src:
        url = urllib.parse.urljoin(page_url, src)
        if url not in [u for _, u in out]:
            out.append((0, url))
    return out


def unwrap(url):
    """The file behind a page's own image proxy: Next.js serves
    ``/_next/image?url=<file>&w=...`` with a build id that changes every
    deploy, so the file itself is what is kept (Florida's justices)."""
    parts = urllib.parse.urlsplit(url)
    if parts.path.endswith("/_next/image"):
        inner = urllib.parse.parse_qs(parts.query).get("url", [""])[0]
        if inner:
            return urllib.parse.urljoin(url, inner)
    return url


def images(page_url, page):
    """Every image on *page*: ``{"src", "offered", "alt", "title", "caption",
    "klass", "at"}``. A lazy image's real address (``data-src``) stands in
    for its placeholder; an image inside a ``<picture>`` carries the sizes
    its ``<source>`` elements offer; an image inside a ``<figure>`` carries
    its ``<figcaption>``. ``at`` is where it stands in *page*."""
    out = []
    pattern = re.compile(r"<figure\b.*?</figure>|<picture\b.*?</picture>|<img\b[^>]*>", re.I | re.S)
    for match in pattern.finditer(page or ""):
        block = match.group(0)
        caption = ""
        if block[:7].lower() == "<figure":
            found = re.search(r"<figcaption\b[^>]*>(.*?)</figcaption>", block, re.I | re.S)
            caption = _text(found.group(1)) if found else ""
        for inner in re.finditer(r"<picture\b.*?</picture>|<img\b[^>]*>", block, re.I | re.S):
            piece = inner.group(0)
            tags = re.findall(r"<img\b[^>]*>", piece, re.I)
            if not tags:
                continue
            tag = tags[0]
            sources = [_attr(s, "data-srcset") or _attr(s, "srcset")
                       for s in re.findall(r"<source\b[^>]*>", piece, re.I)]
            src = _attr(tag, "data-src") or _attr(tag, "data-lazy-src") or _attr(tag, "src")
            if not src or src.startswith("data:"):
                continue
            srcset = ", ".join(s for s in sources + [_attr(tag, "data-srcset") or _attr(tag, "srcset")]
                               if s)
            sizes = [(w, unwrap(u)) for w, u in offered(page_url, srcset, src)]
            seen, kept = set(), []
            for w, u in sizes:
                if u not in seen and u.startswith("https://"):
                    seen.add(u)
                    kept.append((w, u))
            if not kept:
                continue
            out.append({"src": unwrap(urllib.parse.urljoin(page_url, src)), "offered": kept, "alt": _attr(tag, "alt"), "title": _attr(tag, "title"),
                        "caption": caption, "klass": _attr(tag, "class"),
                        "at": match.start() + inner.start()})
    return out


def file_name(url):
    """An image's file name, without its folder or query, decoded. A page's
    own resizing script names the file it serves in its query: Ohio's
    ``timthumb.php?w=350&src=/docs/images/justices/kennedy_highres.jpg`` is
    "kennedy_highres.jpg", not "timthumb.php"."""
    parts = urllib.parse.urlsplit(unwrap(url))
    name = urllib.parse.unquote(parts.path).rstrip("/").rsplit("/", 1)[-1]
    if re.search(r"\.(?:php|aspx?|ashx|cfm)$", name, re.I):
        query = urllib.parse.parse_qs(parts.query)
        for field in ("src", "file", "image", "img"):
            inner = (query.get(field) or [""])[0]
            if inner and not re.search(r"\.(?:php|aspx?|ashx|cfm)(?:$|\?)", inner, re.I):
                return file_name(urllib.parse.urljoin(url, inner))
    return name


# ---------------------------------------------------------------- weights

def _image_size(data):
    from .portraits import image_size
    size = image_size(data)
    if size:
        return size
    # AVIF: the 'ispe' box carries the size.
    k = data.find(b"ispe")
    if data[4:8] == b"ftyp" and k > 0 and len(data) >= k + 16:
        return int.from_bytes(data[k + 8:k + 12], "big"), int.from_bytes(data[k + 12:k + 16], "big")
    return None


def weigh(url, timeout=30, headers=None):
    """``(verdict, weight)``: ``{"bytes", "width", "height"}`` of the image
    at *url* as its server sends it, read from the file. *verdict* is True
    for an image, False for an answer that is not one (a 404, a page of
    HTML: rule 52), None when nothing could be told (a refusal, a timeout:
    rule 8). Only GET: a HEAD's answer is not believed (rule 51). One
    request a second to any one host (rule 42: Wikimedia answers a burst
    with 429 for everything); Wikimedia is sent the descriptive agent it
    asks for."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    with _PACE_LOCK:
        wait = _LAST.get(host, 0) + PACE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST[host] = time.monotonic()
    agent = WIKIMEDIA_AGENT if host.endswith("wikimedia.org") else USER_AGENT
    request = urllib.request.Request(url, headers=dict({
        "User-Agent": agent, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        "Range": "bytes=0-524287"}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            kind = (response.headers.get("Content-Type") or "").lower()
            head = response.read(524288)
            total = None
            span = response.headers.get("Content-Range") or ""
            if "/" in span and span.rsplit("/", 1)[1].strip().isdigit():
                total = int(span.rsplit("/", 1)[1])
            elif response.headers.get("Content-Length", "").isdigit() and response.status == 200:
                total = int(response.headers["Content-Length"])
            if total is None:
                # No length given: count it, up to a size that is over the
                # cap anyway.
                rest = response.read(MAX_PORTRAIT_BYTES * 20)
                total = len(head) + len(rest)
    except urllib.error.HTTPError as exc:
        return (False if exc.code in (404, 410) else None), None
    except Exception:
        return None, None
    size = _image_size(head)
    if not size:
        # A wall's page of HTML answers 200: it concludes nothing about the
        # file (rule 8), unless the server says outright it is no image.
        return (None if "html" in kind or not kind else False), None
    return True, {"bytes": total, "width": size[0], "height": size[1]}


def within_caps(weight):
    return bool(weight) and not too_heavy(weight)


def portrait_shaped(weight, widest=1.0):
    """Head-and-shoulders: taller than wide, or square, and big enough."""
    try:
        width, height = weight["width"], weight["height"]
        return min(width, height) >= MIN_SIDE and 0.5 <= width / height <= widest
    except (KeyError, TypeError, ZeroDivisionError):
        return False


def _weight_of(measure):
    """*measure* (``(verdict, weight)``) as ``photos.lighter_form`` asks:
    the weight of an image, else ``None``."""
    def weight_of(url):
        verdict, weight = measure(url)
        return weight if verdict else None
    return weight_of


def choose(sizes, measure=weigh, widest=1.0, lighter=None):
    """``(url, weight, why, heavy)``: of the sizes a page offers
    (``[(width, url)]``), the narrowest at least ``PREFERRED_WIDTH`` wide
    that is within the caps, else the widest narrower one that is. Where
    every size read is over the caps, the lightest of them is taken (rule
    87): smaller from its host's resizer or Photon where one serves the same
    picture (*lighter*, ``photos.lighter_form``), else as it is; *heavy* is
    then ``[{"url": the file, "why": its weight, "kept": shown at full
    size}]`` (``portraitHeavy``), and ``None`` otherwise. Why there is none
    - ``UNKNOWN`` when a size could not be read, ``"shape"`` when the file
    is not portrait-shaped, ``NONE`` when none is an image. Each size is
    read, never assumed from its label."""
    if lighter is None:
        from .photos import lighter_form as lighter
    order = [s for s in sizes if s[0] >= PREFERRED_WIDTH] + \
        sorted((s for s in sizes if 0 < s[0] < PREFERRED_WIDTH), reverse=True) + \
        [s for s in sizes if not s[0]]
    unknown, heavy = False, []
    for _width, url in order:
        verdict, weight = measure(url)
        if verdict is None:
            unknown = True
            continue
        if not verdict or not weight:
            continue
        if not portrait_shaped(weight, widest):
            return None, weight, "shape", None
        if too_heavy(weight):
            heavy.append((url, weight))
            continue
        return url, weight, "", None
    if heavy:
        # Never left out for its weight (the owner's decision of
        # 2026-10-25): the lightest size offered, smaller where the same
        # picture is served smaller, else shown as it is and said.
        url, weight = min(heavy, key=lambda s: ((s[1].get("bytes") or 0),
                                                max(s[1]["width"], s[1]["height"])))
        found = lighter(url, weight, _weight_of(measure))
        said = [{"url": url, "why": too_heavy(weight), "kept": not found}]
        if found:
            return found[0], found[1], "", said
        return url, weight, "", said
    return None, None, UNKNOWN if unknown else NONE, None


# ---------------------------------------------------------------- records

def record(photo, page, evidence, weight, read=None, **more):
    """A cached photograph: where it is, where it was read, the page's words
    naming the person beside it, the day and its weight."""
    out = {"photo": photo, "page": page, "evidence": evidence,
           "read": read or datetime.date.today().isoformat(),
           "bytes": weight["bytes"], "width": weight["width"], "height": weight["height"]}
    out.update({k: v for k, v in more.items() if v not in (None, "", [], {})})
    return out


def record_problems(rec, where):
    """What a cached photograph lacks, as sentences; [] when it has it all.
    A photograph without the words that tie it to the person, or without
    its weight, is never shown (rule 87)."""
    out = []
    if not isinstance(rec, dict):
        return [f"{where}: not a record"]
    for key in RECORD_KEYS:
        if rec.get(key) in (None, ""):
            out.append(f"{where}: the photograph has no {key}")
    for key in ("photo", "page"):
        if rec.get(key) and not str(rec[key]).startswith("https://"):
            out.append(f"{where}: the photograph's {key} is not an https address")
    try:
        datetime.date.fromisoformat(str(rec.get("read") or ""))
    except ValueError:
        out.append(f"{where}: the day it was read is not a date")
    # Weight never disqualifies (rule 87, the owner's decision of
    # 2026-10-25), but a heavy photograph is said: one over the caps that
    # does not say so would be shown with nothing to tell a copy to make.
    weight = {k: rec.get(k) for k in ("bytes", "width", "height")}
    if all(isinstance(v, int) for v in weight.values()) and too_heavy(weight) \
            and not heavy_of(rec):
        out.append(f"{where}: the photograph is {too_heavy(weight)} and does not say so "
                   "(portraitHeavy)")
    for said in rec.get("portraitHeavy") or ():
        if not (isinstance(said, dict) and str(said.get("url") or "").startswith("https://")):
            out.append(f"{where}: portraitHeavy does not name the heavy file's https address")
    return out


def heavy_of(rec):
    """The heavy file *rec* says it stands for (``portraitHeavy``), or
    ``None``: ``{"url", "why", "kept"}``."""
    said = (rec or {}).get("portraitHeavy") or []
    return said[0] if said and isinstance(said[0], dict) else None


def commons_upload(rec):
    """The Commons upload address of a record taken from Wikimedia Commons
    (its credit's file page), or ``None``: what the overrides key a Commons
    file on."""
    page = ((rec or {}).get("credit") or {}).get("page") or ""
    if "/wiki/File:" not in page:
        return None
    from .judge_links import source_url
    return source_url(page)


def addresses(rec):
    """Every address *rec* stands for: the photograph shown, the heavy file
    it was made smaller from, and its Commons upload."""
    out = [(rec or {}).get("photo"), (heavy_of(rec) or {}).get("url"), commons_upload(rec)]
    return [u for u in out if u]


def held_back(rec):
    """Why a person's lists withhold *rec*, or ``None``: a file in
    ``overrides.NOT_A_PORTRAIT`` (rule 38: someone looked, and it is not a
    likeness) or ``overrides.PORTRAIT_LICENCE_DOUBTS`` (rule 82: its licence
    waits for a person). One test for every route, asked of a record read
    now and of one kept from an earlier read (rule 8), as
    ``judge_links.held_back`` asks it of a judge's."""
    from . import overrides
    doubts = getattr(overrides, "PORTRAIT_LICENCE_DOUBTS", {})
    for url in addresses(rec):
        if url in overrides.NOT_A_PORTRAIT:
            return f"{url} is in overrides.NOT_A_PORTRAIT"
        if url in doubts:
            return f"{url} is in overrides.PORTRAIT_LICENCE_DOUBTS ({doubts[url][1]})"
    return None


CAPS_WORDS = f"{MAX_PORTRAIT_BYTES // 1000} KB or {MAX_PORTRAIT_PX:,}px"
