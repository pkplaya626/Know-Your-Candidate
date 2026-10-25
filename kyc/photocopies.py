"""Smaller copies of the heavy portraits the site already shows (rule 101).

The legislature pages drew 6,134 portraits straight from 343 hosts in a
56x70 box: the Oklahoma Senate's run 9 to 12.5 MB each, so one chamber's
list was about 300 MB on a phone; Connecticut's House Democrats' 4 to 8 MB,
the White House's up to 3.5 MB (measured 2026-10-25). On 2026-10-25 the
owner relaxed the policy that kept such files at full size (rule 87's
``portraitHeavy``) or off the page (rule 100's "no resizing"): "more
content is better than strict rules". The site may host a smaller copy,
made here, of a photograph it already shows by a route the rules allow.

What that relaxes, and what it does not:

- A copy is only ever of an address a record already shows (the
  legislature's or Open States's ``image``, the White House's ``photo``, an
  NGA headshot, a statewide officer's photograph, a profile's first
  portrait), never of a Wikimedia file (Wikimedia serves its own sizes,
  rule 42). No new route, no search, no address built from a name.
- It is that photograph, smaller: drawn once in headless Chrome
  (``tools/make_photo_copies.mjs``) with the browser's own decoder and EXIF
  orientation, white under any transparency, scaled down - never up - to
  just cover three times the largest CSS box any page draws that kind of
  portrait in (``BOXES``; phones are DPR 3), and saved as JPEG. Nothing is
  cropped or retouched.
- The credit stays the original's - whose photograph it is and its source
  page - and the page says it is a smaller copy made here, linking the
  original file (``KYC.photoCreditHtml``).
- Only an original over the caps every portrait is held to
  (``photos.MAX_PORTRAIT_BYTES``, ``MAX_PORTRAIT_PX``) is copied.

``python build_profile_site.py photocopies`` weighs each address (a ranged
GET: HEAD lies, rule 51), one request a second to each host, and keeps
what it read in ``data/photo_copies.json``, a hand-editable cache: for each
original, the records that show it, its bytes, pixels and sha256 as read,
its ETag and Last-Modified, the day read, and its copy - the file under
``photos/`` named by the copy's own hash, its hash, bytes and pixels, and
how it was made (Chrome's version, the quality). A copy is never made again
while the original's sha256 is unchanged: Chrome versions encode
differently, and the build must stay reproducible from committed files
(rule 18). An original that changes is read again and its copy remade; one
that answers 404 or 410 twice is gone, and its copy with it. A failure
concludes nothing (rule 8). A run takes a batch, oldest first, inside a
time budget that ends it cleanly (rule 78), and keeps what it did not
reach.
"""

import concurrent.futures
import datetime
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SITE_DIR = "candidate_profiles_site"
CACHE_PATH = os.path.join(SITE_DIR, "data", "photo_copies.json")
PHOTOS_DIR = os.path.join(SITE_DIR, "photos")
# The copy's address as a page names it, from the site's root.
PHOTOS_URL = "photos/"
TOOL = os.path.join("tools", "make_photo_copies.mjs")
SOURCE = "each portrait's own host, weighed and copied by this site (rule 101)"

# Phones are DPR 3: a copy covers three times the CSS box it is drawn in.
DPR = 3
# The largest CSS box (width, height) any page draws each kind of portrait
# in, from assets/kyc.css (test_photocopies reads them back from it).
BOXES = {
    # .leg-photo: the legislature pages' cards.
    "legislator": (56, 70),
    # .modal-portrait img (the official's dialog); .fed-photo is 72x90.
    "federal": (116, 145),
    # .gov-portrait: the governor's card on the state page.
    "governor": (72, 72),
    # .gov-officer-photo: a statewide officer's row.
    "officer": (40, 40),
    # .card-photo: a profile's card, 4:5, as wide as its column - the
    # Senate view's holder column at most 180px (.senate-holder
    # .card-grid); the dialog's .modal-portrait img is 116x145.
    "person": (180, 225),
}
QUALITY = 0.86
# A copy heavier than this is not what this mechanism is for.
COPY_MAX_BYTES = 150_000
# The most an original may weigh to be downloaded.
MAX_DOWNLOAD = 64 * 1024 * 1024
# How much of a file a weighing reads: its size and pixels are near the
# start (a JPEG's metadata can run past 64 KB, portraits.measure).
HEAD_BYTES = 512 * 1024
PAUSE = 1.0
TIMEOUT = 40
WORKERS = 12
# An entry read this recently is not read again unless forced.
RECHECK_DAYS = 7
# A host that gave no answer this many times running is not asked again in
# the same run.
DOWN_AFTER = 3
GONE_AFTER = 2
UA = {"User-Agent": "Mozilla/5.0 (compatible; know-your-candidate/2.1; civic data project)",
      "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
      "Accept-Encoding": "gzip"}
# The image is already drawn in every reader's browser; a host that refuses
# this script but serves a browser (Indiana's, legphotos.BROWSER_UA) is
# asked again as one.
BROWSER_UA = dict(UA, **{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 "
                                       "Safari/537.36"})

_WIKIMEDIA = re.compile(r"(^|\.)(wikimedia|wikipedia)\.org$", re.I)
_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF")


class PhotoCopyError(RuntimeError):
    """The cache or the copy maker cannot be read or run."""


# ------------------------------------------------------------------ cache

def today():
    return datetime.date.today().isoformat()


def host_of(url):
    try:
        return (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def is_wikimedia(url):
    """Wikimedia serves its own sizes of a file (rule 42): never copied."""
    return bool(_WIKIMEDIA.search(host_of(url)))


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {"originals": {}}
    with open(path, encoding="utf-8") as handle:
        cache = json.load(handle)
    if not isinstance(cache.get("originals"), dict):
        raise PhotoCopyError(f"{CACHE_PATH}: no 'originals' table")
    return cache


def save(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    payload = {
        "source": SOURCE,
        "boxes": {k: [w * DPR, h * DPR] for k, (w, h) in sorted(BOXES.items())},
        "originals": {k: cache["originals"][k] for k in sorted(cache.get("originals") or {})},
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def box_for(kinds):
    """The device-pixel box a copy must cover for every kind it is shown as."""
    boxes = [BOXES[k] for k in kinds if k in BOXES]
    if not boxes:
        return None
    return [max(b[0] for b in boxes) * DPR, max(b[1] for b in boxes) * DPR]


def covers(copy, box):
    """Whether *copy* is sharp for *box*: it was made for a box at least as
    large, or it is the original's own size (never scaled up)."""
    made = copy.get("box") or [0, 0]
    return made[0] >= box[0] and made[1] >= box[1]


def current(cache, url, kind=None):
    """The copy the pages show for *url*, or ``None``: one made, not gone,
    and made for a box that covers *kind*'s."""
    entry = ((cache or {}).get("originals") or {}).get(url)
    if not entry or not entry.get("copy") or (entry.get("gone") or 0) >= GONE_AFTER:
        return None
    copy = entry["copy"]
    if kind and not covers(copy, box_for([kind])):
        return None
    return copy


def src(copy):
    """The copy's address from the site's root, stamped with its hash (rule
    76: the edge caches a ``?v=`` address for a year)."""
    return f"{PHOTOS_URL}{copy['file']}?v={copy['sha256'][:10]}"


def attach(record, url, cache, kind):
    """Point *record* at the copy of *url*, its original, where one is
    current: ``photoCopy = {"src", "of"}``; the record keeps the original's
    address and credit, which the page names beside the copy. Returns
    whether a copy was attached."""
    copy = current(cache, url, kind) if url else None
    if copy:
        record["photoCopy"] = {"src": src(copy), "of": url}
        return True
    record.pop("photoCopy", None)
    return False


def apply_people(profiles, cache):
    """A profile's first portrait, copied, where it has a credit (rule 87:
    no copy without one); returns how many."""
    n = 0
    for profile in profiles:
        first = (profile.get("photos") or [""])[0]
        if (first and first != "placeholder" and profile.get("photoCredit")
                and not is_wikimedia(first)):
            n += attach(profile, first, cache, "person")
        else:
            profile.pop("photoCopy", None)
    return n


def apply_legislature(payload, cache, code=""):
    """Each member's portrait on one legislature page, copied; returns how
    many. A copy carries a credit (rule 87): where the card credits none -
    an Open States portrait the legislature's own host does not serve - the
    copy is credited to the host that serves the original, as Open States
    lists it, since the page no longer loads it from there."""
    n = 0
    for _code, member in _legislators({code: payload}):
        if attach(member, member["image"], cache, "legislator"):
            n += 1
            if not member.get("imageCredit"):
                member["imageCredit"] = {"by": host_of(member["image"]), "via": "Open States"}
    return n


def apply_federal(payload, cache):
    """The President's, the Vice President's and each Cabinet officer's
    White House photograph, copied; returns how many."""
    n = 0
    for person in federal_people(payload):
        if person.get("photo"):
            n += attach(person, person["photo"], cache, "federal")
    return n


def apply_stategov(payload, cache):
    """Each governor's NGA headshot and each statewide officer's photograph,
    copied; returns how many."""
    n = 0
    for _code, entry in sorted((payload.get("states") or {}).items()):
        gov = entry.get("governor") or {}
        if gov.get("headshot"):
            n += attach(gov, gov["headshot"], cache, "governor")
        for office in ("lt", "ag", "sos"):
            holder = entry.get(office)
            if isinstance(holder, dict) and holder.get("photo"):
                n += attach(holder, holder["photo"], cache, "officer")
    return n


# --------------------------------------------------------------- gathering

def federal_people(payload):
    out = [payload.get(k) for k in ("president", "vicePresident") if payload.get(k)]
    out += [o["holder"] for o in payload.get("offices") or [] if o.get("holder")]
    return out


def _legislators(payloads):
    """``(code, member record)`` for every member a legislature file shows."""
    def walk(code, node):
        if isinstance(node, dict):
            if isinstance(node.get("image"), str) and node.get("id"):
                yield code, node
                return
            for value in node.values():
                yield from walk(code, value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(code, value)
    for code, payload in sorted((payloads or {}).items()):
        yield from walk(code, payload)


class Shown:
    """Every portrait address the build shows outside Wikimedia: by address,
    the kinds it is drawn as and the records that show it; and what is
    wrong with any copy a record points at."""

    def __init__(self):
        self.urls = {}
        self.issues = []

    def add(self, url, kind, record_id, record=None, credited=True):
        if not url or not url.startswith(("https://", "http://")):
            return
        copy = (record or {}).get("photoCopy")
        if copy:
            if copy.get("of") != url:
                self.issues.append(("error", "photo-copy-misplaced",
                                    f"{record_id} shows the copy of {copy.get('of')} in place of "
                                    f"its own portrait, {url}"))
            if not credited:
                self.issues.append(("error", "photo-copy-uncredited",
                                    f"{record_id} shows a copy of {url} with no credit (rule 87)"))
            if is_wikimedia(url):
                self.issues.append(("error", "photo-copy-wikimedia",
                                    f"{record_id} shows a copy of a Wikimedia file, {url}"))
        if is_wikimedia(url):
            return
        slot = self.urls.setdefault(url, {"kinds": set(), "records": set()})
        slot["kinds"].add(kind)
        slot["records"].add(record_id)

    def add_legislatures(self, payloads):
        for code, member in _legislators(payloads):
            self.add(member["image"], "legislator", f"legislator:{code}:{member['id']}", member,
                     bool(member.get("imageCredit")))
        return self

    def add_federal(self, payload):
        for person in federal_people(payload or {}):
            # The page credits every White House photograph to it
            # (kyc-official.js picture).
            self.add(person.get("photo"), "federal", f"federal:{person.get('id')}", person, True)
        return self

    def add_stategov(self, payload):
        for code, entry in sorted(((payload or {}).get("states") or {}).items()):
            gov = entry.get("governor") or {}
            self.add(gov.get("headshot"), "governor", f"governor:{code}", gov,
                     bool(gov.get("headshotBy")))
            for office in ("lt", "ag", "sos"):
                holder = entry.get(office)
                if isinstance(holder, dict):
                    self.add(holder.get("photo"), "officer", f"officer:{code}:{office}", holder,
                             bool(holder.get("photoBy")))
        return self

    def add_people(self, people):
        for person in people or []:
            first = (person.get("photos") or [""])[0]
            if first and first != "placeholder":
                self.add(first, "person", f"person:{person.get('id')}", person,
                         bool(person.get("photoCredit")))
        return self


def read_people(root="."):
    """Everyone's whole record, as the last build wrote the state files
    (``data/people/<st>.js``; the index leaves out the credit)."""
    from . import emit
    directory = os.path.join(root, emit.PEOPLE_DIR)
    people = {}
    if not os.path.isdir(directory):
        return []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".js") or name in ("index.js", "meta.js"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("window.kycPeopleFile = "):
                    text = line[len("window.kycPeopleFile = "):].rstrip().rstrip(";")
                    for person in json.loads(text.replace("<\\!--", "<!--")).get("people") or []:
                        people.setdefault(person.get("id"), person)
    return [people[k] for k in sorted(people, key=str)]


def gather(root="."):
    """``Shown`` for what the build shows now: the legislatures, the federal
    executive and the state governments built from their caches, and the
    people as the last build wrote them."""
    from . import federal_build, legislature, stategov
    shown = Shown()
    shown.add_legislatures(legislature.build(root))
    shown.add_federal(federal_build.build(root)[0])
    shown.add_stategov(stategov.build(root)[0])
    shown.add_people(read_people(root))
    return shown


# ---------------------------------------------------------------- problems

def file_sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def heavy(entry):
    """Why a weighed original is over the caps, or ``""``."""
    from .photos import too_heavy
    if not entry or not entry.get("bytes"):
        return ""
    return too_heavy({"bytes": entry.get("bytes"), "width": entry.get("width"),
                      "height": entry.get("height")})


def stats(cache, shown):
    """One line of figures for the build's report."""
    originals = (cache or {}).get("originals") or {}
    over = [u for u in shown.urls if heavy(originals.get(u))]
    copied = [u for u in over if current(cache, u, sorted(shown.urls[u]["kinds"])[0])]
    weight = sum(e["copy"]["bytes"] for e in originals.values() if e.get("copy"))
    return (f"{len(copied):,} of {len(over):,} portraits over the caps shown as a copy made here "
            f"({weight / 1e6:.1f} MB under {PHOTOS_DIR}); "
            f"{sum(1 for u in shown.urls if (originals.get(u) or {}).get('read')):,} of "
            f"{len(shown.urls):,} addresses weighed")


def problems(cache, root=".", shown=None, files=True):
    """``[(level, code, message)]``: an error for anything that would put a
    wrong or unaccounted file on the page, a warning for what is left to do.
    *files* checks the manifest against ``photos/``; *shown* (a ``Shown``)
    checks the records that show the copies, and counts what is left."""
    out = []
    originals = (cache or {}).get("originals") or {}
    listed = {}
    for url, entry in sorted(originals.items() if files else ()):
        copy = entry.get("copy")
        if not copy:
            continue
        name = copy.get("file") or ""
        listed.setdefault(name, []).append(url)
        if is_wikimedia(url):
            out.append(("error", "photo-copy-wikimedia", f"a copy of a Wikimedia file: {url}"))
        if not re.fullmatch(r"[0-9a-f]{16,64}\.jpg", name):
            out.append(("error", "photo-copy-name", f"{url}: copy file {name!r} is not named by "
                                                     f"its hash"))
            continue
        path = os.path.join(root, PHOTOS_DIR, name)
        if not os.path.exists(path):
            out.append(("error", "photo-copy-missing", f"{url}: {PHOTOS_DIR}/{name} is not on disk"))
            continue
        sha = file_sha(path)
        if sha != copy.get("sha256") or not sha.startswith(name[:-4]):
            out.append(("error", "photo-copy-hash", f"{PHOTOS_DIR}/{name} does not have the hash "
                                                    f"its name and the manifest give"))
        size = os.path.getsize(path)
        if size != copy.get("bytes"):
            out.append(("error", "photo-copy-bytes", f"{PHOTOS_DIR}/{name} is {size} bytes, the "
                                                     f"manifest says {copy.get('bytes')}"))
        for key in ("chrome", "quality", "made", "box", "width", "height"):
            if not copy.get(key):
                out.append(("error", "photo-copy-unrecorded",
                            f"{url}: the copy does not record its {key}"))
        box = copy.get("box") or [0, 0]
        w, h = copy.get("width") or 0, copy.get("height") or 0
        # Just covering its box: one side at the box, never both past it.
        if min(w - box[0], h - box[1]) > 1:
            out.append(("error", "photo-copy-oversize",
                        f"{url}: the copy is {w}x{h}, more than its {box[0]}x{box[1]} box needs"))
        if w > (entry.get("width") or 0) + 1 and h > (entry.get("height") or 0) + 1 \
                and entry.get("width"):
            out.append(("error", "photo-copy-enlarged", f"{url}: the copy is larger than the "
                                                        f"original"))
        if (copy.get("bytes") or 0) > COPY_MAX_BYTES or \
                (copy.get("bytes") or 0) >= (entry.get("bytes") or 0):
            out.append(("error", "photo-copy-heavy", f"{url}: the copy is {copy.get('bytes')} "
                                                     f"bytes, the original {entry.get('bytes')}"))
        if not heavy(entry):
            out.append(("error", "photo-copy-unneeded",
                        f"{url}: copied, but the original as read is within the caps"))
        if not entry.get("sha256"):
            out.append(("error", "photo-copy-unrecorded", f"{url}: no hash of the original"))
    directory = os.path.join(root, PHOTOS_DIR)
    if files and os.path.isdir(directory):
        for name in sorted(os.listdir(directory)):
            if name not in listed:
                out.append(("error", "photo-copy-unlisted",
                            f"{PHOTOS_DIR}/{name} is not in {CACHE_PATH}"))
    if shown is None:
        return out
    out += shown.issues
    missing, unweighed, orphans = {}, {}, []
    for url, slot in sorted(shown.urls.items()):
        entry = originals.get(url)
        kind = sorted(slot["kinds"])[0]
        if not entry or not entry.get("read"):
            unweighed[kind] = unweighed.get(kind, 0) + 1
        elif heavy(entry) and not current(cache, url, kind) and (entry.get("gone") or 0) < GONE_AFTER:
            missing[kind] = missing.get(kind, 0) + 1
    for url, entry in sorted(originals.items()):
        if entry.get("copy") and url not in shown.urls:
            orphans.append(url)
    if missing:
        out.append(("warning", "photo-copies-missing",
                    f"{sum(missing.values())} portraits over 300 KB or 1,200 px have no smaller "
                    f"copy yet ({', '.join(f'{k} {n}' for k, n in sorted(missing.items()))}); "
                    f"run 'photocopies'"))
    if unweighed:
        out.append(("warning", "photo-copies-unweighed",
                    f"{sum(unweighed.values())} portraits not yet weighed "
                    f"({', '.join(f'{k} {n}' for k, n in sorted(unweighed.items()))}); "
                    f"run 'photocopies'"))
    if orphans:
        out.append(("warning", "photo-copy-orphan",
                    f"{len(orphans)} copies whose original no record shows any more (the "
                    f"'photocopies' command removes them): {', '.join(orphans[:3])}"))
    return out


# ----------------------------------------------------------------- network

def _open(url, headers, timeout=TIMEOUT):
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout)


def _status(exc):
    return exc.code if isinstance(exc, urllib.error.HTTPError) else 0


def _read(response, limit):
    data = response.read(limit + 1)
    if len(data) > limit:
        raise PhotoCopyError(f"over {limit} bytes")
    return data


def _decoded(response, data):
    if (response.headers.get("Content-Encoding") or "").lower() == "gzip":
        return gzip.decompress(data)
    return data


def _is_image(response, head):
    kind = (response.headers.get("Content-Type") or "").lower()
    if head[:4] == b"<svg" or "svg" in kind:
        return False
    return kind.startswith("image/") or head.startswith(_IMAGE_MAGIC)


def probe(url, entry=None, headers=UA):
    """One read of *url*: ``{"status": "unchanged"}`` (a 304 to the last
    read's validators), ``{"status": "gone", "code"}`` (404, 410),
    ``{"status": "error", "why"}`` (anything else that concludes nothing,
    rule 8), or ``{"status": "ok", "bytes", "width", "height", "etag",
    "lastModified", "type", "data"}`` where ``data`` is the whole file when
    the read took all of it."""
    from .portraits import image_size

    sent = dict(headers, Range=f"bytes=0-{HEAD_BYTES - 1}")
    entry = entry or {}
    if entry.get("etag"):
        sent["If-None-Match"] = entry["etag"]
    if entry.get("lastModified"):
        sent["If-Modified-Since"] = entry["lastModified"]
    try:
        with _open(url, sent) as response:
            gz = (response.headers.get("Content-Encoding") or "").lower() == "gzip"
            total = None
            span = response.headers.get("Content-Range") or ""
            if response.status == 206 and "/" in span and span.rsplit("/", 1)[1].isdigit():
                total = int(span.rsplit("/", 1)[1])
            elif response.status == 200 and (response.headers.get("Content-Length") or "").isdigit():
                total = int(response.headers["Content-Length"])
            if response.status == 206 and not gz:
                head = response.read(HEAD_BYTES)
                data = head if total is not None and len(head) >= total else None
            else:
                # The whole file came (no ranges), or it came compressed.
                data = _decoded(response, _read(response, MAX_DOWNLOAD))
                head, total = data, len(data)
            meta = {"etag": response.headers.get("ETag") or "",
                    "lastModified": response.headers.get("Last-Modified") or "",
                    "type": (response.headers.get("Content-Type") or "").split(";")[0].strip()}
            if not _is_image(response, head[:16]):
                return {"status": "error", "why": f"not an image ({meta['type'] or 'no type'})"}
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return {"status": "unchanged"}
        if exc.code in (404, 410):
            return {"status": "gone", "code": exc.code}
        if exc.code == 416:
            return probe_whole(url, headers)
        return {"status": "error", "why": f"HTTP {exc.code}", "code": exc.code}
    except Exception as exc:  # noqa: BLE001 - a failed read concludes nothing (rule 8)
        return {"status": "error", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    if total is None:
        return {"status": "error", "why": "the server gave no size"}
    size = image_size(head) or (None, None)
    return dict(meta, status="ok", bytes=total, width=size[0], height=size[1], data=data)


def probe_whole(url, headers=UA):
    """A whole-file read, for a host that refuses a range."""
    from .portraits import image_size
    try:
        data = download(url, headers)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return {"status": "gone", "code": exc.code}
        return {"status": "error", "why": f"HTTP {exc.code}", "code": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    size = image_size(data) or (None, None)
    return {"status": "ok", "bytes": len(data), "width": size[0], "height": size[1],
            "etag": "", "lastModified": "", "type": "", "data": data}


def download(url, headers=UA):
    with _open(url, headers) as response:
        data = _decoded(response, _read(response, MAX_DOWNLOAD))
        if not _is_image(response, data[:16]):
            raise PhotoCopyError("not an image")
        return data


def _unchanged(entry, read):
    """Whether a read that was not a 304 still shows the file last read: the
    same length, and the same validators where the server gives them (some
    ignore a conditional request that carries a range)."""
    if read["bytes"] != entry.get("bytes"):
        return False
    if not (read.get("etag") or read.get("lastModified")):
        return bool(entry.get("sha256")) and not (entry.get("etag") or entry.get("lastModified"))
    return (read.get("etag") or "") == (entry.get("etag") or "") and \
        (read.get("lastModified") or "") == (entry.get("lastModified") or "")


# --------------------------------------------------------------------- run

def _order(shown, cache, force=False, now=None):
    """The addresses to read, oldest first: never read, then by the day last
    read; those read in the last ``RECHECK_DAYS`` only when forced."""
    now = now or datetime.date.today()
    originals = cache.get("originals") or {}
    todo = []
    for url in shown.urls:
        entry = originals.get(url) or {}
        read = entry.get("read") or ""
        if read and not force:
            try:
                age = (now - datetime.date.fromisoformat(read)).days
            except ValueError:
                age = RECHECK_DAYS
            box = box_for(shown.urls[url]["kinds"])
            needs = heavy(entry) and (not entry.get("copy") or not covers(entry["copy"], box))
            if age < RECHECK_DAYS and not needs and not entry.get("error"):
                continue
        todo.append((read, url))
    todo.sort()
    return [url for _, url in todo]


def run(root=".", limit=None, max_minutes=None, force=False, log=print, workers=WORKERS,
        shown=None, maker=None, prober=None, fetcher=None):
    """Weigh a batch of what the build shows, copy what is over the caps,
    drop what no record shows; save the cache. Returns a report dict.
    *shown* (``gather``'s) and *maker*, *prober* and *fetcher* stand in for
    the build, Chrome and the network in tests."""
    deadline = time.monotonic() + max_minutes * 60 if max_minutes else None
    cache = load(root)
    shown = shown if shown is not None else gather(root)
    return _run(root, cache, shown, limit, deadline, force, log, workers,
                maker or make_copies, prober or probe, fetcher or download)


def _run(root, cache, shown, limit, deadline, force, log, workers, maker, prober, fetcher):
    originals = cache["originals"]
    report = {"weighed": 0, "heavy": 0, "copied": 0, "kept": 0, "unchanged": 0, "gone": 0,
              "removed": 0, "errors": 0, "skipped": 0, "orphans": 0, "copyFailed": 0}
    # What no record shows any more: its copy goes, as the photograph would.
    for url in sorted(set(originals) - set(shown.urls)):
        if originals[url].get("copy"):
            report["orphans"] += 1
            log(f"  removed the copy of {url}: no record shows it")
        del originals[url]
    for url, slot in shown.urls.items():
        entry = originals.setdefault(url, {})
        entry["kinds"] = sorted(slot["kinds"])
        entry["records"] = sorted(slot["records"])
    todo = _order(shown, cache, force)
    if limit is not None:
        report["skipped"] = max(0, len(todo) - limit)
        todo = todo[:limit]
    log(f"  {len(shown.urls):,} portrait addresses shown outside Wikimedia; reading "
        f"{len(todo):,} this run")
    by_host = {}
    for url in todo:
        by_host.setdefault(host_of(url), []).append(url)
    lock = threading.Lock()
    workdir = tempfile.mkdtemp(prefix="kyc-photocopies-")
    jobs = []

    def out_of_time():
        return deadline is not None and time.monotonic() > deadline

    def one(url, headers):
        entry = originals[url]
        # A conditional read only where a 304 would leave nothing to do: a
        # copy made for a box that covers every kind the original is shown as.
        known = entry if (entry.get("copy") and
                          covers(entry["copy"], box_for(entry.get("kinds") or []))) else None
        read = prober(url, known, headers)
        if read["status"] == "error" and read.get("code") in (401, 403, 406) and headers is UA:
            time.sleep(PAUSE)
            read = prober(url, known, BROWSER_UA)
            headers = BROWSER_UA
        return read, headers

    def host_worker(host, urls):
        down = 0
        last = 0.0
        for url in urls:
            if out_of_time():
                break
            if down >= DOWN_AFTER:
                break
            wait = last + PAUSE - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            last = time.monotonic()
            read, headers = one(url, UA)
            entry = originals[url]
            with lock:
                report["weighed"] += 1
            if read["status"] == "unchanged":
                with lock:
                    entry["read"] = today()
                    entry.pop("error", None)
                    entry["gone"] = 0
                    report["unchanged"] += 1
                down = 0
                continue
            if read["status"] == "error":
                down = down + 1 if not read.get("code") else 0
                with lock:
                    entry["error"] = read["why"]
                    report["errors"] += 1
                continue
            down = 0
            if read["status"] == "gone":
                with lock:
                    entry["gone"] = (entry.get("gone") or 0) + 1
                    entry["read"] = today()
                    entry.pop("error", None)
                    report["gone"] += 1
                    if entry["gone"] >= GONE_AFTER and entry.get("copy"):
                        entry.pop("copy")
                        report["removed"] += 1
                        log(f"  {url}: gone ({read['code']}) twice; its copy is removed")
                continue
            same = bool(entry.get("copy")) and _unchanged(entry, read)
            with lock:
                for key in ("bytes", "width", "height", "etag", "lastModified"):
                    if read.get(key):
                        entry[key] = read[key]
                    else:
                        entry.pop(key, None)
                entry["read"] = today()
                entry["gone"] = 0
                entry.pop("error", None)
            if not heavy(entry):
                with lock:
                    if entry.pop("copy", None):
                        report["removed"] += 1
                        log(f"  {url}: now within the caps; its copy is removed")
                    entry.pop("sha256", None)
                continue
            with lock:
                report["heavy"] += 1
            box = box_for(entry.get("kinds") or [])
            if same and covers(entry["copy"], box):
                with lock:
                    report["kept"] += 1
                continue
            data = read.get("data")
            if data is None:
                if out_of_time():
                    break
                time.sleep(PAUSE)
                last = time.monotonic()
                try:
                    data = fetcher(url, headers)
                except Exception as exc:  # noqa: BLE001 - concludes nothing (rule 8)
                    with lock:
                        entry["error"] = f"download: {type(exc).__name__}: {str(exc)[:100]}"
                        report["errors"] += 1
                    continue
            sha = hashlib.sha256(data).hexdigest()
            with lock:
                if (entry.get("copy") and entry.get("sha256") == sha
                        and covers(entry["copy"], box)):
                    report["kept"] += 1
                    continue
                # A copy of another file than the one the address serves now
                # is never shown, even until the new copy is made.
                if entry.pop("copy", None) and entry.get("sha256") not in (None, sha):
                    report["removed"] += 1
                entry["sha256"] = sha
                if len(data) != entry.get("bytes"):
                    entry["bytes"] = len(data)
                path = os.path.join(workdir, f"{len(jobs)}.img")
                with open(path, "wb") as handle:
                    handle.write(data)
                jobs.append({"id": url, "in": path,
                             "out": os.path.join(workdir, f"{len(jobs)}.jpg"), "box": box})

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for future in [pool.submit(host_worker, h, u) for h, u in sorted(by_host.items())]:
                future.result()
        if jobs:
            log(f"  making {len(jobs)} copies in headless Chrome")
            try:
                made = maker(jobs, root)
            except (PhotoCopyError, OSError, subprocess.SubprocessError) as exc:
                # No Chrome concludes nothing: what was weighed is kept, and
                # the next run makes the copies (rule 8).
                log(f"  [warn] no copies made: {exc}")
                report["copyFailed"] += len(jobs)
                made = None
            if made is not None:
                _take(made, jobs, originals, root, report, log)
        _sweep(cache, root, log)
        save(cache, root)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return report


def _take(made, jobs, originals, root, report, log):
    """Store each copy Chrome made under ``photos/``, by its own hash."""
    os.makedirs(os.path.join(root, PHOTOS_DIR), exist_ok=True)
    results = made.get("results") or {}
    for job in jobs:
        url = job["id"]
        entry = originals[url]
        result = results.get(url) or {}
        if not result.get("ok"):
            report["copyFailed"] += 1
            entry["error"] = f"copy: {result.get('error') or 'not made'}"
            log(f"  [warn] no copy of {url}: {entry['error']}")
            continue
        with open(job["out"], "rb") as handle:
            data = handle.read()
        if len(data) >= (entry.get("bytes") or 0) or len(data) > COPY_MAX_BYTES:
            report["copyFailed"] += 1
            entry["error"] = f"copy: {len(data)} bytes, no lighter than it should be"
            log(f"  [warn] no copy of {url}: {entry['error']}")
            continue
        sha = hashlib.sha256(data).hexdigest()
        name = f"{sha[:20]}.jpg"
        target = os.path.join(root, PHOTOS_DIR, name)
        if not os.path.exists(target):
            with open(target, "wb") as handle:
                handle.write(data)
        entry["copy"] = {
            "file": name, "sha256": sha, "bytes": len(data),
            "width": result["width"], "height": result["height"],
            "box": job["box"], "chrome": made.get("chrome") or "",
            "quality": made.get("quality"), "made": today(),
            "from": [result.get("srcWidth"), result.get("srcHeight")],
        }
        entry.pop("error", None)
        report["copied"] += 1


def _sweep(cache, root, log=print):
    """Remove every file under ``photos/`` no entry names."""
    names = {e["copy"]["file"] for e in cache["originals"].values() if e.get("copy")}
    directory = os.path.join(root, PHOTOS_DIR)
    if not os.path.isdir(directory):
        return 0
    removed = 0
    for name in sorted(os.listdir(directory)):
        if name not in names:
            os.remove(os.path.join(directory, name))
            removed += 1
    if removed:
        log(f"  removed {removed} file(s) under {PHOTOS_DIR} that no entry names")
    return removed


def make_copies(jobs, root="."):
    """Run ``tools/make_photo_copies.mjs`` over *jobs*; its report."""
    node = shutil.which("node")
    if not node:
        raise PhotoCopyError("no node to run the copy maker")
    with tempfile.TemporaryDirectory(prefix="kyc-photojobs-") as tmp:
        spec = os.path.join(tmp, "jobs.json")
        out = os.path.join(tmp, "report.json")
        with open(spec, "w", encoding="utf-8") as handle:
            json.dump({"quality": QUALITY, "jobs": jobs}, handle)
        done = subprocess.run([node, os.path.join(root, TOOL), "--jobs", spec, "--out", out],
                              capture_output=True, text=True, timeout=3600)
        if done.returncode or not os.path.exists(out):
            raise PhotoCopyError(f"the copy maker failed ({done.returncode}): "
                                 f"{(done.stderr or done.stdout).strip()[:300]}")
        with open(out, encoding="utf-8") as handle:
            return json.load(handle)
