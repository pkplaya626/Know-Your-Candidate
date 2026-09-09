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


def _api(params):
    """Rate-limited call to the MediaWiki API."""
    params = dict(params, action="query", format="json", formatversion="2")
    url = f"{WIKI_API}?{urllib.parse.urlencode(params)}"
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


def surname_of(name):
    """Last word of a name, accents folded, for matching article titles."""
    import unicodedata

    parts = [p for p in str(name).split() if p]
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
    return surname in clean


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
    profiles = [p for p in profiles if p.get("source") != "fec-field"]

    todo = [p for p in profiles if refresh or profile_key(p) not in cache]
    todo = [p for p in todo if not cache.get(profile_key(p), {}).get("pinned")]

    if not todo:
        log(f"  portraits: {len(cache)} cached, nothing to resolve")
        return cache, {"resolved": 0, "cached": len(cache)}

    log(f"  portraits: resolving {len(todo)} profile(s) ...")

    # --- Stage 1: Congress.gov, the official portrait for sitting members.
    def official(profile):
        if profile["isCandidate"] or profile["id"].startswith("CURR_"):
            return profile, None
        url = CONGRESS_IMG.format(bioguide_lower=profile["id"].lower())
        return profile, (url if check_image(url) else None)

    resolved = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for profile, url in pool.map(official, todo):
            if url:
                resolved[profile_key(profile)] = {
                    "url": url, "via": "congress.gov", "name": profile["name"],
                }
    log(f"    congress.gov: {len(resolved)}")

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
        title = titles_by_bioguide.get(profile["id"].upper())
        if title:
            wanted[profile_key(profile)] = title

    # --- Stage 3: guess the obvious article titles for everyone else.
    guesses = {}
    for profile in remaining:
        key = profile_key(profile)
        if key not in wanted:
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
            # guess is not, and a redirect can land it on a topic page.
            if not from_mapping and not title_is_about(found[0], profile["name"]):
                log(f"    [skip] {profile['name']} -> {found[0]!r} (not about them)")
                continue
            resolved[key] = {
                "url": found[1], "via": "wikipedia",
                "title": found[0], "name": profile["name"],
            }
            break
        else:
            still.append(profile)

    # --- Stage 4: search Wikipedia for whoever is left.
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
        if record["via"] == "congress.gov":
            return key, record  # already checked in stage 1
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
        hits += 1
    return hits
