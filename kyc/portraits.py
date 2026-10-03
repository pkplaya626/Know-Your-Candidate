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
_THUMB_SIZE = 800
_BATCH = 50

# Serialise API calls and keep a courteous gap between them. The Wikipedia
# API is batched 50 titles at a time, so this costs very little wall clock.
_api_lock = threading.Lock()
_api_gap = 0.9
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


def image_sizes(urls, log=None):
    """``{url: (width, height)}`` of the original behind each Wikimedia URL."""
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
                payload = _api({"prop": "imageinfo", "iiprop": "size",
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
                        out[url] = (info["width"], info["height"])
    return out


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


def wiki_search_title(name):
    """Best-guess article title for *name*.

    Searched bare. Adding a topical hint ("NE politician") reorders results so
    badly that the person's own article drops out of the top hits entirely.
    """
    try:
        payload = _api({
            "list": "search", "srsearch": name, "srlimit": "5", "srnamespace": "0",
        })
    except Exception:
        return None

    hits = [h.get("title", "") for h in payload.get("query", {}).get("search", [])]
    lowered = name.lower()
    surname = name.split()[-1].lower() if name.split() else ""

    for title in hits:
        if _BAD_TITLE.search(title):
            continue
        clean = title.lower()
        # Exact article, or the standard "Name (politician)" disambiguation.
        if clean == lowered or clean.startswith(f"{lowered} ("):
            return title

    # Fall back to a title that at least starts with the person's full name,
    # so a loose match cannot attach a stranger's portrait to a candidate.
    for title in hits:
        if not _BAD_TITLE.search(title) and title.lower().startswith(lowered) and surname:
            return title
    return None


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

    # Candidates imported from the FEC's filing register are deliberately not
    # resolved. Portrait resolution for a member goes through the
    # authoritative bioguide -> Wikipedia mapping, which cannot pick the wrong
    # person. For a filed candidate it is a bare title guess and a search, and
    # the field contains 1,979 largely unknown people with ordinary names -
    # "Michael Smith" resolves to an article about somebody else entirely.
    # A silhouette says "we have no portrait", which is true. A stranger's
    # face on a candidate's profile is the exact failure rule 3 exists for,
    # and nothing on the page would look wrong.
    # The one exception is a filing the state's election page links to an
    # article: that link is an editor's assertion about this person on this
    # ballot, the same kind of authority as the bioguide mapping. Those are
    # resolved through the title alone - never guessed, never searched.
    profiles = [p for p in profiles
                if p.get("source") != "fec-field" or p.get("wikipedia")]

    todo = [p for p in profiles if refresh or profile_key(p) not in cache]
    todo = [p for p in todo if not cache.get(profile_key(p), {}).get("pinned")]

    if not todo:
        log(f"  portraits: {len(cache)} cached, nothing to resolve")
        if size_all(cache, log=log):
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

    wanted = {}
    for profile in remaining:
        title = titles_by_bioguide.get(profile["id"].upper()) or (
            profile.get("wikipedia") if profile.get("source") == "fec-field" else None)
        if title:
            wanted[profile_key(profile)] = title

    # --- Stage 3: guess the obvious article titles for everyone else. Never
    # for a filed candidate: their only route is the ballot's own link.
    guesses = {}
    for profile in remaining:
        key = profile_key(profile)
        if key not in wanted and profile.get("source") != "fec-field":
            guesses[key] = [profile["name"], f"{profile['name']} (politician)"]

    lookup = list(wanted.values()) + [t for v in guesses.values() for t in v]
    thumbs = wiki_page_images(lookup, log=log)
    log(f"    wikipedia pageimages: {len(thumbs)} thumbnails for {len(set(lookup))} titles")

    still = []
    for profile in remaining:
        key = profile_key(profile)
        from_mapping = key in wanted
        for title in ([wanted[key]] if from_mapping else guesses.get(key, [])):
            found = thumbs.get(title)
            if not found:
                continue
            # The bioguide -> Wikipedia mapping is authoritative and its title
            # need not contain the surname (married names, pen names). A bare
            # guess is not, and a redirect can land it on a topic page. A
            # ballot page's link is trusted for the title but still checked
            # after redirects, the way McGinnis's protest photo taught.
            trusted = from_mapping and profile.get("source") != "fec-field"
            if not trusted and not title_is_about(found[0], profile["name"]):
                log(f"    [skip] {profile['name']} -> {found[0]!r} (not about them)")
                continue
            resolved[key] = {
                "url": found[1], "via": "wikipedia",
                "title": found[0], "name": profile["name"],
            }
            break
        else:
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

    # --- Stage 4: search Wikipedia for whoever is left - roster people only.
    still = [p for p in still if p.get("source") != "fec-field"]
    if still:
        log(f"    searching wikipedia for {len(still)} remaining ...")
        found_titles = {}
        for profile in still:
            title = wiki_search_title(profile["name"])
            if title:
                found_titles[profile_key(profile)] = title
        extra = wiki_page_images(list(found_titles.values()), log=log)
        for profile in still:
            key = profile_key(profile)
            hit = extra.get(found_titles.get(key, ""))
            if hit and title_is_about(hit[0], profile["name"]):
                resolved[key] = {
                    "url": hit[1], "via": "wikipedia-search",
                    "title": hit[0], "name": profile["name"],
                }

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
            for field in ("width", "height", "set"):
                if field in source:
                    cache[key][field] = source[field]
            shared += 1
    return shared


def apply_cache(profiles, cache):
    """Put the resolved URL at the head of each profile's fallback chain."""
    hits = 0
    for profile in profiles:
        record = cache.get(profile_key(profile)) or {}
        url = record.get("url")
        if not url:
            profile["photoSource"] = None
            continue
        profile["photos"] = [url] + [u for u in profile["photos"] if u != url]
        profile["photo_url"] = url
        profile["photoSource"] = record.get("via")
        # Sizes of this same photograph, for the page's srcset.
        if record.get("set"):
            profile["photoSet"] = record["set"]
        hits += 1
    return hits
