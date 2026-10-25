"""Build-time portrait resolution.

The site used to guess portrait URLs in the browser and hope one of five
patterns happened to exist. A live probe of all 594 profiles found only one
working tier: 82% of members resolved, 7% of candidates, and every curated
Wikimedia URL returned HTTP 400.

Resolution happens here instead, at build time, against authoritative sources,
and each URL is checked before it is written. The result is cached in
``candidate_profiles_site/data/portraits.json`` - committed, human-readable and
hand-correctable. The page then ships one known-good URL per profile and the
silhouette becomes a genuine last resort.

    python build_profile_site.py portraits            # fill in what is missing
    python build_profile_site.py portraits --refresh  # re-resolve everything

Two lessons are baked into this module:

* **Never discard on an inconclusive check.** Rate limiting made
  :func:`verify_image` return "failed", which threw away hundreds of perfectly
  good URLs. It now distinguishes "definitely broken" from "could not tell".
* **Never search with a topical hint.** Searching "Dan Osborn NE politician"
  pushes his actual article out of the results; "Dan Osborn" returns it first.

And two about size, measured on 2026-10-03:

* **A srcset lists sizes of one photograph.** congress.gov's portrait is
  175px wide; the House Clerk's and the unitedstates project's are larger,
  but for seven of ten members sampled each was a *different* photograph -
  the Clerk's newer, the project's often a Congress or two older. A srcset
  lets the screen choose, so mixing sources would let pixel density decide
  which photograph a reader sees. Only Wikimedia serves one photograph at
  several sizes; everything else ships a single URL.
* **Wikimedia serves only its standard thumbnail widths** and refuses any
  other with HTTP 400; a burst of thumbnail requests gets 429 for everything
  from that address. :func:`size_all` builds the sizes from the measured
  original and fetches only the smallest, slowly. The page falls back to the
  plain URL when a size fails.
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "portraits.json")

LEGISLATORS_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
WIKI_API = "https://en.wikipedia.org/w/api.php"
CONGRESS_IMG = "https://www.congress.gov/img/member/{bioguide_lower}_200.jpg"
# A House member's current official portrait, 335px wide. congress.gov's is
# 175px - soft on a high-density screen - and often a Congress or two older.
CLERK_IMG = "https://clerk.house.gov/images/members/{bioguide_upper}.jpg"

# Wikimedia renders a hotlinked thumbnail only at its standard widths
# (https://w.wiki/GHai). The largest the page needs is a ~165px card on a 3x
# screen, so 500 is the top step.
THUMB_STEPS = (120, 250, 330, 500)

# Wikimedia asks for a descriptive User-Agent identifying the client.
_UA = {"User-Agent": "know-your-candidate/2.1 (open-source civic data project)"}
_TIMEOUT = 25
# The article's lead image at a width Wikimedia serves as standard: one it
# does not is rendered on demand and refused under load (TECH-13).
_THUMB_SIZE = 960
_BATCH = 50

# Serialise API calls and keep a courteous gap between them: one a second,
# since Wikimedia answers a burst with 429 for everything (rule 42). The
# API is batched 50 titles at a time, so this costs very little wall clock.
_api_lock = threading.Lock()
_api_gap = 1.0
_last_call = [0.0]

_BAD_TITLE = re.compile(r"\(disambiguation\)|^List of |^\d{4} United States", re.I)


class PortraitError(RuntimeError):
    pass


# ---------------------------------------------------------------- http utils

def _get(url, timeout=_TIMEOUT, retries=6):
    """GET with backoff on the status codes that mean "slow down".

    Wikipedia returns 429 readily when a build resolves several hundred
    portraits. A shallow retry made whole batches fail and silently cost ~26
    profiles their photo, so back off generously and honour Retry-After.
    """
    delay = 2.0
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if retry_after:
                try:
                    delay = max(delay, min(float(retry_after), 30.0))
                except ValueError:
                    pass
        except Exception as exc:  # timeouts, connection resets
            last = exc
        if attempt < retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise PortraitError(f"GET failed after {retries} attempts: {url} ({last})")


def _api(params, endpoint=WIKI_API):
    """Rate-limited call to a MediaWiki API (English Wikipedia's by default)."""
    params = dict(params, action="query", format="json", formatversion="2")
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    with _api_lock:
        wait = _api_gap - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            body = _get(url)
        finally:
            _last_call[0] = time.monotonic()
    return json.loads(body.decode("utf-8"))


def check_image(url, timeout=_TIMEOUT):
    """Tristate check: ``True`` valid, ``False`` broken, ``None`` unknown.

    Returning ``None`` on a throttled or timed-out request matters: an earlier
    version treated "could not tell" as "broken" and silently discarded ~160
    working portraits.
    """
    if not url:
        return False
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=_UA, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    return False
                ctype = response.headers.get("Content-Type", "")
                if not ctype.startswith("image"):
                    return False
                length = response.headers.get("Content-Length")
                return length is None or int(length) > 1000
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 405) and method == "HEAD":
                continue  # some CDNs reject HEAD; retry as GET
            if exc.code in (429, 500, 502, 503, 504):
                return None
            return False
        except Exception:
            return None
    return None


# -------------------------------------------------------------------- sizes

_WIKIMEDIA = re.compile(
    r"^https://(?P<host>upload|thumb)\.wikimedia\.org/(?P<project>wikipedia/[a-z-]+)/"
    r"(?:thumb/)?(?P<hash>[0-9a-f]/[0-9a-f]{2})/(?P<file>[^/]+?)(?:/\d+px-[^/]+)?$")
_THUMBABLE = re.compile(r"\.(jpe?g|png|webp)$", re.I)
_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"RIFF")
_render_gap = 1.0
# Consecutive could-not-tell answers after which a run stops checking sizes.
_render_trip = 5


def wikimedia_file(url):
    """``(host, project, hash path, file)`` behind a Wikimedia image URL - the
    original or any thumbnail of it - or ``None`` for anything else."""
    match = _WIKIMEDIA.match(url or "")
    if not match or not _THUMBABLE.search(match.group("file")):
        return None
    return match.group("host"), match.group("project"), match.group("hash"), match.group("file")


def thumb_set(url, width):
    """``[[width, url], ...]`` - sizes of one Wikimedia photograph, smallest
    first, for a srcset.

    Each is a standard thumbnail narrower than the original, which Wikimedia
    will not enlarge; an original no wider than the top step is itself the
    largest. A comma or space would end a srcset entry early, so both are
    percent-encoded.
    """
    parts = wikimedia_file(url)
    if not parts or not width:
        return []
    host, project, hashed, name = parts
    name = name.replace(" ", "%20").replace(",", "%2C")
    base = f"https://{host}.wikimedia.org/{project}/thumb/{hashed}/{name}"
    out = [[step, f"{base}/{step}px-{name}"] for step in THUMB_STEPS if step < width]
    if width <= THUMB_STEPS[-1]:
        out.append([width, f"https://upload.wikimedia.org/{project}/{hashed}/{name}"])
    return out


def _api_endpoint(project):
    """The MediaWiki API that describes the files under *project*."""
    wiki = project.split("/", 1)[1]
    if wiki == "commons":
        return "https://commons.wikimedia.org/w/api.php"
    return f"https://{wiki}.wikipedia.org/w/api.php"


def file_info(urls, log=None):
    """``{url: imageinfo}`` for the file behind each Wikimedia URL: its
    measured ``width`` and ``height``, its ``descriptionurl`` and the
    licence fields of its ``extmetadata``. One request a batch of fifty,
    through :func:`_api`'s one-a-second gap."""
    wanted = {}
    for url in urls:
        parts = wikimedia_file(url)
        if parts:
            title = "File:" + urllib.parse.unquote(parts[3])
            wanted.setdefault(parts[1], {}).setdefault(title, []).append(url)

    out = {}
    for project, by_title in wanted.items():
        titles = list(by_title)
        for i in range(0, len(titles), _BATCH):
            try:
                payload = _api({"prop": "imageinfo", "iiprop": "size|url|extmetadata",
                                "iiextmetadatafilter": _CREDIT_FIELDS,
                                "titles": "|".join(titles[i:i + _BATCH])},
                               endpoint=_api_endpoint(project))
            except Exception as exc:
                if log:
                    log(f"    [warn] imageinfo batch failed: {exc}")
                continue
            query = payload.get("query", {})
            alias = {item["to"]: item["from"] for item in query.get("normalized", [])}
            for page in query.get("pages", []):
                info = (page.get("imageinfo") or [{}])[0]
                title = alias.get(page.get("title"), page.get("title"))
                if info.get("width"):
                    for url in by_title.get(title, []):
                        out[url] = info
    return out


def image_sizes(urls, log=None):
    """``{url: (width, height)}`` of the original behind each Wikimedia URL."""
    return {url: (info["width"], info["height"])
            for url, info in file_info(urls, log=log).items()}


# ------------------------------------------------------------------ credits
#
# A Commons file is free to use on the terms of its licence, and 148 of the
# 381 Wikimedia portraits on the site in October 2026 were CC BY or CC BY-SA:
# their licences require the author's name, the licence and a link to it
# beside the photograph. None was shown (TRUST-08). The file's own
# description page is the record of who made it and on what terms, so the
# credit is read from it - never typed in - and stored with the portrait.

_CREDIT_FIELDS = "Artist|LicenseShortName|LicenseUrl|AttributionRequired|NonFree"

# Which reading of a file's description page a stored credit is. A credit
# read by an earlier form is read again: the first printed Commons' hidden
# duplicate spans, uploaders' sentences and file names as authors.
CREDIT_FORM = 2

# Licence codes Commons gives where the licence has a name.
LICENCE_NAMES = {
    "PDM-owner": "Public Domain Mark",
    "PDM": "Public Domain Mark",
    "FAL": "Free Art License",
}

_HIDDEN = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b[^>]*\bstyle\s*=\s*\"[^\"]*display\s*:\s*none[^\"]*\"[^>]*>"
    r".*?</(?P=tag)\s*>", re.I | re.S)
_FILE_NAME = re.compile(r"[^\s:/]+\.(?:jpe?g|png|gif|tiff?|svg|webp)\b", re.I)
# What Commons' templates say where no author is known: {{Unknown|author}},
# "unidentified photographer", a sentence about not knowing.
_NO_AUTHOR = re.compile(
    r"^(?:unknown|unidentified|anonymous|not known|author unknown|no author|"
    r"photographer unknown|unnamed|n/?a\b|i do not know|i don't know)", re.I)
# What an uploader adds to the author's line about themselves.
_UPLOADER = re.compile(
    r"\s*(?:\(\s*talk\s*\)|(?:the )?original uploader was\b.*$|"
    r"later versions?(?:\(s\))? (?:were|was) uploaded by\b.*$|"
    r"(?<=\.)\s*\S+ at [A-Z][a-z]+ Wikipedia\b\s*\.?)", re.I | re.S)


def plain_text(fragment):
    """Text with its HTML gone, and what Commons hides from readers gone
    with it: an author given as ``Unknown author<span style="display:
    none;">Unknown author</span>`` read "Unknown author Unknown author"
    under five profiles' and six judges' photographs."""
    import html as html_mod

    text = _HIDDEN.sub(" ", str(fragment or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html_mod.unescape(text).split())


def author_of(fragment):
    """The author a Commons file's ``Artist`` field names, as a reader should
    see it, or ``None`` where it names no one.

    Each line of a list is read alone, without a leading file name (Judge
    Keenan's photograph is cut from another file: "Warner_Keenan_Webb.jpg:
    Mark Warner" and "derivative work: Athenchen"), an uploader's note
    about themselves or "(talk)". What is left is no author when it is a
    form of "unknown", a sentence about not knowing ("I do not know the
    name of the photographer ..."), a bare address or a file name; a phrase
    said twice is said once."""
    raw = _HIDDEN.sub(" ", str(fragment or ""))
    # A link whose words are only "source" or a footnote says of no one who
    # made the file: Sotomayor's official portrait's author read
    # "Collection of the Supreme Court of the United States, Steve Petteway
    # source", the last word a link to a newspaper. A link to a user's page
    # is a person, whatever their name ("User:Link"), and stays (the PR
    # #133 review). CREDIT_FORM is not moved for it: no cached credit
    # carries such a word (every "by" read 2026-10-25).
    raw = re.sub(r"<a\b(?![^>]*href=\"[^\"]*(?:User|Benutzer|Utilisateur)(?::|%3A))[^>]*>"
                 r"\s*(?:source|link|here|\[\d+\])\s*</a>", " ", raw, flags=re.I)
    items = re.findall(r"<li\b[^>]*>(.*?)</li>", raw, re.I | re.S) or [raw]
    out = []
    for item in items:
        text = plain_text(item)
        text = re.sub(rf"^{_FILE_NAME.pattern}\s*:\s*", "", text, flags=re.I)
        # An interwiki link's prefix: "en:United States District Court ...".
        text = re.sub(r"^[a-z]{2,3}:(?=[A-Z])", "", text)
        cleaned = _UPLOADER.sub("", text).strip(" ;,")
        text = " ".join((cleaned or text).split())
        # A sentence's full stop, not an initial's ("S.D.N.Y.").
        text = re.sub(r"(?:(?<=[a-z]{2})|(?<=\)))\s*\.$", "", text)
        half = len(text) // 2
        if len(text) % 2 == 1 and text[:half] == text[half + 1:]:
            text = text[:half]
        if (not text or _NO_AUTHOR.search(text) or re.search(r"(?:^|\s)I\s", text)
                or re.fullmatch(r"(?:https?:)?//\S+|https?://\S+", text)
                or _FILE_NAME.fullmatch(text)):
            continue
        if text not in out:
            out.append(text)
    return "; ".join(out) or None


def licence_name(code):
    """A licence as a reader can read it: Commons' code where it is a name
    ("CC BY-SA 4.0", "Public domain"), the name where it is only a code."""
    code = plain_text(code) or None
    return LICENCE_NAMES.get(code, code) if code else None


def credit_of(info):
    """The credit a Commons file's own description page gives it:
    ``{"by", "licence", "licenceUrl", "file", "attribution", "nonFree",
    "form"}``. ``by`` is ``None`` where the page names no author
    (:func:`author_of`); ``licence`` is ``None`` when the page records
    none, which ``validate`` refuses (rule 87)."""
    meta = info.get("extmetadata") or {}

    def field(name):
        return plain_text((meta.get(name) or {}).get("value")) or None

    return {
        "by": author_of((meta.get("Artist") or {}).get("value")),
        "licence": licence_name((meta.get("LicenseShortName") or {}).get("value")),
        "licenceUrl": field("LicenseUrl"),
        "file": info.get("descriptionurl") or None,
        "attribution": (field("AttributionRequired") or "").lower() == "true",
        "nonFree": (field("NonFree") or "").lower() == "true",
        "form": CREDIT_FORM,
    }


def credit_all(cache, log=print):
    """Give each Wikimedia portrait in *cache* its file's ``credit``.

    Only records that have none, or one read by an earlier form
    (:data:`CREDIT_FORM`), are asked about, fifty to a request, one request
    a second. A file the API does not describe keeps what it had, and one
    that never had a credit is not shown until it has one
    (:func:`apply_cache`); it is asked about again next run."""
    todo = {key: record for key, record in cache.items()
            if record.get("url") and wikimedia_file(record["url"])
            and (record.get("credit") or {}).get("form") != CREDIT_FORM}
    if not todo:
        return 0
    log(f"    credits: reading {len(todo)} Wikimedia file description(s) ...")
    infos = file_info([record["url"] for record in todo.values()], log=log)
    done = 0
    for record in todo.values():
        info = infos.get(record["url"])
        if info:
            record["credit"] = credit_of(info)
            done += 1
    log(f"    credits: {done} read, {len(todo) - done} could not be")
    return done


# ----------------------------------------------------------------- weights
#
# A portrait not on Wikimedia is one file at one size. Its weight is
# measured when it is found - the House Clerk's run 50-100 KB; one campaign
# site's original was a 1.3 MB PNG for a 165px card (TECH-13) - so a heavy
# one can be refused before a reader downloads it.

def measure(url, timeout=_TIMEOUT):
    """``{"bytes", "width", "height"}`` of the image at *url*, from its
    first 64 KB and the size the server reports, or ``None`` when it could
    not be told (rule 8: unknown is not too big). A JPEG whose metadata
    runs past 64 KB before its dimensions (the NGA's 7.6 MB headshot of
    Ohio's governor carries 100 KB of it) is read again to 512 KB."""
    for span_end in (65535, 524287):
        found = _measure_head(url, span_end, timeout)
        if found is None:
            return None
        total, size = found
        if size:
            return {"bytes": total, "width": size[0], "height": size[1]} if total else None
        if not total or total <= span_end + 1:
            return None
    return None


def _measure_head(url, span_end, timeout):
    """``(total bytes or None, (width, height) or None)`` from the first
    *span_end* + 1 bytes of *url*, or ``None`` when it is not an image."""
    headers = dict(_UA, Range=f"bytes=0-{span_end}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if not (response.headers.get("Content-Type") or "").startswith("image/"):
                return None
            head = response.read(span_end + 1)
            total = None
            span = response.headers.get("Content-Range") or ""
            if "/" in span and span.rsplit("/", 1)[1].isdigit():
                total = int(span.rsplit("/", 1)[1])
            elif response.status == 200 and response.headers.get("Content-Length", "").isdigit():
                total = int(response.headers["Content-Length"])
    except Exception:
        return None
    return total, image_size(head)


_measure_gap = 1.0


def measure_all(cache, log=print):
    """Record the weight of each non-Wikimedia portrait in *cache* that has
    none, one request a second."""
    todo = [record for record in cache.values()
            if record.get("url") and not wikimedia_file(record["url"]) and "bytes" not in record]
    if not todo:
        return 0
    log(f"    weights: measuring {len(todo)} portrait(s) ...")
    done = 0
    for record in todo:
        time.sleep(_measure_gap)
        found = measure(record["url"])
        if found:
            record.update(found)
            done += 1
    log(f"    weights: {done} measured, {len(todo) - done} could not be")
    return done


def _render(url):
    """Fetch one size: ``True`` an image, ``False`` refused, ``None`` could
    not tell.

    Wikimedia answers a burst of thumbnail requests with 429 for everything
    from that address. The first full run fetched every size and retried each
    429 with a backoff, which spent a minute a size and kept the burst going,
    so a 429 here waits out the window once and then gives up.
    """
    for attempt in range(2):
        time.sleep(_render_gap)
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
                body = response.read()
            return len(body) > 1000 and body.startswith(_IMAGE_MAGIC)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                return False
            if attempt == 0:
                wait = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    time.sleep(min(float(wait or 60), 120.0))
                except ValueError:
                    time.sleep(60.0)
        except Exception:
            return None
    return None


def size_all(cache, log=print):
    """Give each Wikimedia portrait in *cache* a ``set`` of sizes.

    The sizes are Wikimedia's standard widths narrower than the measured
    original, so they are valid by construction; one fetch of the smallest
    confirms the file can be thumbnailed at all, and a file that cannot gets
    an empty set. A check that could not tell keeps the set (rule 8) - the
    page falls back to the plain URL when a size fails - and after
    ``_render_trip`` of those in a row the run stops checking rather than
    wait on a closed window. An original that could not be measured gets no
    ``set`` and is tried again on the next run.
    """
    todo = {key: record for key, record in cache.items()
            if record.get("url") and "set" not in record and wikimedia_file(record["url"])}
    if not todo:
        return 0
    log(f"    sizes: measuring {len(todo)} Wikimedia portrait(s) ...")
    dims = image_sizes([record["url"] for record in todo.values()], log=log)
    sized = unclear = refused = 0
    for record in todo.values():
        measured = dims.get(record["url"])
        if not measured:
            continue
        record["width"], record["height"] = measured
        entries = thumb_set(record["url"], measured[0])
        verdict = None
        if entries and unclear < _render_trip:
            verdict = _render(entries[0][1])
            unclear = unclear + 1 if verdict is None else 0
        refused += verdict is False
        record["set"] = [] if verdict is False else entries
        sized += 1
    if unclear >= _render_trip:
        log("    sizes: Wikimedia stopped answering; the rest are kept unchecked (rule 8)")
    log(f"    sizes: {sized} measured ({refused} refused), {len(todo) - sized} could not be")
    return sized


def image_size(data):
    """``(width, height)`` of a PNG, JPEG, GIF or WebP from its bytes, or None."""
    import struct

    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8 " and len(data) >= 30:
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8X" and len(data) >= 30:
            return (int.from_bytes(data[24:27], "little") + 1,
                    int.from_bytes(data[27:30], "little") + 1)
        return None
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


# ------------------------------------------------------------------ sources

def fetch_legislator_titles():
    """``{bioguide_id: wikipedia_title}`` for sitting members."""
    try:
        payload = json.loads(_get(LEGISLATORS_URL, timeout=60).decode("utf-8"))
    except Exception as exc:
        raise PortraitError(f"Could not fetch {LEGISLATORS_URL}: {exc}") from exc

    titles = {}
    for entry in payload:
        ids = entry.get("id", {})
        bioguide, wikipedia = ids.get("bioguide"), ids.get("wikipedia")
        if bioguide and wikipedia:
            titles[bioguide.strip().upper()] = wikipedia
    return titles


def _clean_thumb(url):
    return url.split("?")[0] if url else url


def wiki_page_images(titles, log=None):
    """Resolve Wikipedia titles to thumbnails.

    Returns ``{requested_title: (resolved_title, thumb_url)}``.
    """
    out = {}
    titles = [t for t in dict.fromkeys(titles) if t]

    for i in range(0, len(titles), _BATCH):
        batch = titles[i:i + _BATCH]
        try:
            payload = _api({
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": _THUMB_SIZE,
                "redirects": "1",
                "titles": "|".join(batch),
            })
        except Exception as exc:
            if log:
                log(f"    [warn] pageimages batch failed: {exc}")
            continue

        result = payload.get("query", {})
        alias = {}
        for key in ("normalized", "redirects"):
            for item in result.get(key, []):
                alias[item["to"]] = alias.get(item["from"], item["from"])

        for page in result.get("pages", []):
            title = page.get("title", "")
            if page.get("missing") or _BAD_TITLE.search(title):
                continue
            thumb = _clean_thumb((page.get("thumbnail") or {}).get("source"))
            if thumb:
                out[alias.get(title, title)] = (title, thumb)
    return out


# ------------------------------------------------------------------- cache

def profile_key(profile):
    """Bioguide for members, name+state+chamber for candidates.

    The chamber is part of the key because ``(name, state)`` alone is not an
    identity. Colin Allred appears in Texas as both a former House member and
    a Senate candidate, and Brian McGinnis appears in North Carolina twice for
    two different offices - so one cache entry was being served to two
    profiles. Rule 3 in CLAUDE.md is about exactly this, and the fix is the
    same: key on enough to tell people apart.
    """
    if not profile["isCandidate"] and not profile["id"].startswith("CURR_"):
        return f"bioguide:{profile['id']}"
    chamber = "S" if "Senate" in profile.get("chamber", "") else "H"
    return f"person:{profile['name'].lower()}|{profile['state']}|{chamber}"


_GENERATIONAL = {"jr", "sr", "ii", "iii", "iv", "v"}


def surname_of(name):
    """Last name word, accents folded, for matching article titles.

    A generational suffix is skipped: "Briscoe Rowell Cain III" is about
    "Briscoe Cain", and treating "III" as the surname rejected twelve
    correct titles.
    """
    import unicodedata

    parts = [p for p in str(name).replace(".", "").split() if p]
    while parts and parts[-1].lower() in _GENERATIONAL:
        parts.pop()
    if not parts:
        return ""
    word = parts[-1]
    folded = unicodedata.normalize("NFD", word)
    return "".join(c for c in folded if unicodedata.category(c) != "Mn").lower()


def title_is_about(title, name):
    """True when a Wikipedia title plausibly names this person.

    Wikipedia redirects a person's name to whatever article mentions them, so
    a bare title guess can land on a topic page: "Brian McGinnis" redirected
    to "Protests against the 2026 Iran war", and his profile carried a
    photograph of a demonstration. Nothing about that looks wrong on the page,
    which is the whole problem.

    Requiring the person's surname to appear in the resolved title is a crude
    test, but it is the one that would have caught it.
    """
    surname = surname_of(name)
    if not surname:
        return False
    import unicodedata

    folded = unicodedata.normalize("NFD", str(title))
    clean = "".join(c for c in folded if unicodedata.category(c) != "Mn").lower()
    if surname in clean:
        return True
    # A double surname on the filing and one of them in the title:
    # "Valentina Gomez Noriega" is the article "Valentina Gomez".
    words = [w for w in str(name).replace(".", "").split() if w.lower() not in _GENERATIONAL]
    return len(words) >= 3 and surname_of(" ".join(words[:-1])) in clean


def article_is_theirs(title, profile):
    """:func:`title_is_about`, or the title an evidenced
    ``overrides.ARTICLE_UNDER_ANOTHER_NAME`` entry gives this profile - one
    answer for the link check, the portrait, the infobox and the offices
    held, so no two of them disagree about one article."""
    from . import overrides

    alias = overrides.article_alias(profile.get("id"))
    return (title_is_about(title, profile.get("name") or "")
            or (alias is not None and title == alias))


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (ValueError, OSError):
        return {}


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- resolution

def resolve_all(profiles, root=".", refresh=False, workers=8, log=print):
    """Resolve a checked portrait URL for every profile.

    Cached entries are kept unless *refresh* is set, so routine builds make no
    network calls. Entries with ``"pinned": true`` are never overwritten - the
    escape hatch for hand-corrections.
    """
    cache = load_cache(root)

    # Nobody's portrait is guessed (rule 24). A member's goes through the
    # official photographs and the authoritative bioguide -> Wikipedia
    # mapping, which cannot pick the wrong person. Anyone else has a title
    # only where the state's election page links one: an editor's assertion
    # about this person on this ballot, resolved through that title alone and
    # checked after redirects. A title guessed from a name or found by a
    # search is somebody else often enough - "Michael Smith", "Adam Hamilton
    # (politician)" - and a silhouette says "we have no portrait", which is
    # true. A stranger's face on a profile is the failure rule 3 exists for,
    # and nothing on the page would look wrong.
    profiles = [p for p in profiles
                if p.get("source") != "fec-field" or p.get("wikipedia")]

    # A cached portrait that came by a route no longer allowed - a search, a
    # guessed title, an article the profile no longer links - is resolved
    # again rather than kept (see :func:`route_ok`).
    todo = [p for p in profiles if refresh or profile_key(p) not in cache
            or not route_ok(p, cache[profile_key(p)])]
    todo = [p for p in todo if not cache.get(profile_key(p), {}).get("pinned")]

    if not todo:
        log(f"  portraits: {len(cache)} cached, nothing to resolve")
        changed = size_all(cache, log=log)
        changed += credit_all(cache, log=log)
        changed += measure_all(cache, log=log)
        if changed:
            save_cache(cache, root)
        return cache, {"resolved": 0, "cached": len(cache)}

    log(f"  portraits: resolving {len(todo)} profile(s) ...")

    # --- Stage 1: a House member's official portrait - the Clerk's current
    # one, then congress.gov's. A senator goes to Wikipedia first (stage 2):
    # the Senate publishes no portrait by Bioguide id, congress.gov's is
    # 175px, and for most senators sampled it was older than the article's.
    def official(profile):
        if (profile["isCandidate"] or profile["id"].startswith("CURR_")
                or not profile.get("chamber", "").startswith("House")):
            return profile, None, None
        for template, via in ((CLERK_IMG, "clerk.house.gov"), (CONGRESS_IMG, "congress.gov")):
            url = template.format(bioguide_upper=profile["id"].upper(),
                                  bioguide_lower=profile["id"].lower())
            if check_image(url):
                return profile, url, via
        return profile, None, None

    resolved = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for profile, url, via in pool.map(official, todo):
            if url:
                resolved[profile_key(profile)] = {
                    "url": url, "via": via, "name": profile["name"],
                }
    clerk = sum(1 for r in resolved.values() if r["via"] == "clerk.house.gov")
    log(f"    clerk.house.gov: {clerk}, congress.gov: {len(resolved) - clerk}")

    remaining = [p for p in todo if profile_key(p) not in resolved]

    # --- Stage 2: Wikipedia, via the authoritative bioguide -> title mapping.
    titles_by_bioguide = {}
    try:
        titles_by_bioguide = fetch_legislator_titles()
        log(f"    congress-legislators: {len(titles_by_bioguide)} titles")
    except PortraitError as exc:
        log(f"    [warn] {exc}")

    # The ballot page's own link is the only other route, for anyone it
    # names - a curated row as much as a filer (rule 33). There is no third:
    # titles guessed from a name ("Adam Hamilton (politician)", a 1930s
    # photograph on the Kansas Senate candidate, who is the pastor) and a
    # search for whoever was left are the guesses rule 24 forbids.
    wanted = {}
    by_bioguide = set()
    for profile in remaining:
        title = titles_by_bioguide.get(profile["id"].upper())
        if title:
            by_bioguide.add(profile_key(profile))
        elif profile.get("wikipediaVia") == "election-page" or profile.get("source") == "fec-field":
            title = profile.get("wikipedia")
        if title:
            wanted[profile_key(profile)] = title

    lookup = list(wanted.values())
    thumbs = wiki_page_images(lookup, log=log)
    log(f"    wikipedia pageimages: {len(thumbs)} thumbnails for {len(set(lookup))} titles")

    still = []
    for profile in remaining:
        key = profile_key(profile)
        found = thumbs.get(wanted.get(key, ""))
        # The bioguide -> Wikipedia mapping is authoritative and its title
        # need not contain the surname (married names, pen names). A ballot
        # page's link is trusted for the title but still checked after
        # redirects, the way McGinnis's protest photo taught.
        if found and (key in by_bioguide or article_is_theirs(found[0], profile)):
            resolved[key] = {
                "url": found[1], "via": "wikipedia",
                "title": found[0], "name": profile["name"],
            }
            # The title asked for, before redirects - the bioguide
            # mapping's or the ballot page's link: what route_ok compares
            # with the profile's own link.
            resolved[key]["linked"] = wanted[key]
        else:
            if found:
                log(f"    [skip] {profile['name']} -> {found[0]!r} (not about them)")
            still.append(profile)

    # --- Stage 3b: a senator with no portrait on Wikipedia gets the official
    # one, small as it is.
    def senate_official(profile):
        if (profile["isCandidate"] or profile["id"].startswith("CURR_")
                or not profile.get("chamber", "").startswith("Senate")):
            return profile, None
        url = CONGRESS_IMG.format(bioguide_lower=profile["id"].lower())
        return profile, (url if check_image(url) else None)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for profile, url in pool.map(senate_official, still):
            if url:
                resolved[profile_key(profile)] = {
                    "url": url, "via": "congress.gov", "name": profile["name"],
                }
    still = [p for p in still if profile_key(p) not in resolved]

    # --- Stage 5: check what we found, keeping anything not proven broken.
    def confirm(item):
        key, record = item
        if record["via"] in ("clerk.house.gov", "congress.gov"):
            return key, record  # already checked when it was found
        verdict = check_image(record["url"])
        if verdict is False:
            return key, {"url": None, "via": "broken", "name": record["name"]}
        if verdict is None:
            record["unverified"] = True
        return key, record

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key, record in pool.map(confirm, list(resolved.items())):
            resolved[key] = record

    for profile in todo:
        key = profile_key(profile)
        cache[key] = resolved.get(key) or {
            "url": None, "via": "unresolved", "name": profile["name"],
        }

    size_all(cache, log=log)
    credit_all(cache, log=log)
    measure_all(cache, log=log)
    shared = inherit_cross_links(profiles, cache)
    if shared:
        log(f"    cross-link inheritance: {shared}")

    save_cache(cache, root)

    hits = sum(1 for r in cache.values() if r.get("url"))
    log(f"  portraits: {hits}/{len(cache)} resolved "
        f"({100 * hits / max(len(cache), 1):.0f}% coverage)")
    return cache, {"resolved": hits, "cached": len(cache)}


def inherit_cross_links(profiles, cache):
    """Share a portrait between a member and their own 2026 candidacy.

    The same person filed twice is still the same face, so a resolved member
    portrait covers their candidate profile and vice versa.
    """
    by_id = {p["id"]: p for p in profiles}
    shared = 0
    for profile in profiles:
        key = profile_key(profile)
        if (cache.get(key) or {}).get("url"):
            continue
        partner_id = profile.get("alsoRunningId") or profile.get("incumbentId")
        partner = by_id.get(partner_id) if partner_id else None
        if not partner:
            continue
        source = cache.get(profile_key(partner)) or {}
        if source.get("url"):
            cache[key] = {
                "url": source["url"], "via": "cross-link",
                "name": profile["name"], "title": source.get("title"),
            }
            for field in ("width", "height", "set", "credit", "bytes"):
                if field in source:
                    cache[key][field] = source[field]
            shared += 1
    return shared


# Routes that reach a photograph through an id: the House Clerk's and
# congress.gov's official portraits (by bioguide id), and a member's own
# portrait shared with their other candidacy (by profile id).
_ID_ROUTES = ("clerk.house.gov", "congress.gov", "cross-link")


def route_ok(profile, record, legislators=None, legislator_photos=None):
    """True when a cached portrait reached this profile by an allowed route.

    Rule 24 for every profile: a member's portrait comes through their
    bioguide id; anyone else's only through the article their ballot page
    links (rule 33), checked after redirects to be about them. The cache
    held portraits found earlier by guessing "<Name> (politician)" and by
    searching a name - the Kansas Senate nominee, a pastor, carried a 1930s
    photograph of another Adam Hamilton - and those are refused here, not
    merely no longer looked for. A hand-pinned record stands on its own
    evidence. The two routes ``nominee_photos`` adds - Wikidata by the
    person's FEC id, and their state legislature's own page - are taught
    here by name and checked there (*legislators*: the roster, which a
    legislature's photograph must still seat them in; *legislator_photos*:
    the ``legphotos`` cache, so the card must still show that file).
    """
    from . import nominee_photos

    if record.get("pinned"):
        return True
    via = record.get("via")
    if via in _ID_ROUTES:
        return True
    if via in nominee_photos.ROUTES:
        return nominee_photos.route_ok(profile, record, legislators, legislator_photos)
    if via != "wikipedia":
        return not record.get("url")
    linked = record.get("linked") or record.get("title")
    if not linked or linked != profile.get("wikipedia"):
        return False
    if profile_key(profile).startswith("bioguide:"):
        # The bioguide -> Wikipedia mapping is authoritative, and its title
        # need not contain the surname (married names, pen names).
        return True
    return ((profile.get("wikipediaVia") == "election-page"
             or profile.get("source") == "fec-field")
            and article_is_theirs(record.get("title") or "", profile))


def apply_cache(profiles, cache, legislators=None, legislator_photos=None):
    """Put the resolved URL at the head of each profile's fallback chain.

    Only a portrait whose route :func:`route_ok` accepts; anything else
    leaves the chain as :mod:`kyc.photos` built it, ending at the silhouette.
    *legislators* is the state legislators' roster and *legislator_photos*
    the ``legphotos`` cache, for a portrait from a legislature
    (``nominee_photos``).
    """
    hits = 0
    for profile in profiles:
        record = cache.get(profile_key(profile)) or {}
        url = record.get("url")
        if not url or not route_ok(profile, record, legislators, legislator_photos):
            profile["photoSource"] = None
            continue
        if (record.get("credit") or {}).get("nonFree"):
            # A file Wikipedia holds under fair use is licensed to no one
            # else: it is not shown here.
            profile["photoSource"] = None
            continue
        if wikimedia_file(url) and not (record.get("credit") or {}).get("licence"):
            # Its credit has not been read yet (Commons did not answer): it
            # waits for the next run rather than show uncredited or hold the
            # build (rule 8), and the next photograph or the silhouette shows.
            profile["photoSource"] = None
            continue
        profile["photos"] = [url] + [u for u in profile["photos"] if u != url]
        profile["photo_url"] = url
        profile["photoSource"] = record.get("via")
        # Sizes of this same photograph, for the page's srcset.
        if record.get("set"):
            profile["photoSet"] = record["set"]
        if wikimedia_file(url):
            profile["photoCredit"] = commons_credit(record.get("credit"))
        elif record.get("via") == "state-legislature" and record.get("credit"):
            profile["photoCredit"] = dict(record["credit"])
        hits += 1
    return hits


def commons_credit(credit):
    """What the page prints for a Commons file: its author, its licence and
    the file's page, as the file's description page records them - or, with
    no recorded licence, ``licence`` ``None``, which ``validate`` fails."""
    credit = credit or {}
    out = {"by": credit.get("by"), "licence": credit.get("licence"),
           "licenceUrl": credit.get("licenceUrl"), "page": credit.get("file"),
           "via": "Wikimedia Commons"}
    if credit.get("attribution") and not credit.get("by"):
        # The licence asks for the author and the page names none: the line
        # says so, and links the file's page (rule 87).
        out["authorUnrecorded"] = True
    return out
