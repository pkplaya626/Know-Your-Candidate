"""Each state justice's photograph, from their own court's pages (rule 87).

No justice had one: 307 sat on the state pages as names only (research of
2026-10-19). A justice's photograph is taken only from the roster page the
court's recipe reads (``courts.COURTS``) or from the one page that roster
links from that justice's own name - or, where the roster lists a row per
justice, from the "Bio" link in that justice's row (West Virginia, Montana).
Never from a search, never from an address built from a name (rule 24):
Montana's ``/bios/Rice`` is not linked from its roster, and is not read.

An image is that justice's when every word the page gives it - its alt
text, its title, its caption and its file name - says so:

- the justice's surname is one of them, or run together with the others
  ("justiceBunn", "JRivera-sml");
- none names anyone else: another member's surname ("hargrave-and-combs"
  on Justice Combs's page), or "Justice <a name not theirs>" - two of
  Connecticut's justices' own pages carry a former justice's alt text,
  "Justice Christine E. Keller";
- none says a scene: a swearing-in, a staff photograph, "pinned by his
  brother" (Oklahoma's Edmondson);
- nothing is left over but the name, a title, a word for a likeness, a
  size or a shoot number;
- the file is portrait-shaped or square and at least 80px on its short side.

What the strict words refuse that is plainly the official portrait - a
misspelt alt text, a nickname, a file named by initials - is an evidenced
``overrides.JUSTICE_PHOTOS`` entry: the page's own words, the day read and
the file's weight, held to the same record as a read one.

Only a size the page itself offers is taken (the owner's decision of
2026-10-19: no image service, no resizing), the narrowest at least 160px
wide that is within the caps; one offered only above them is left out and
counted. A photograph that could not be read keeps the last one read of the
same justice (rule 8). The page credits each court's photographs to the
court.
"""

import html
import re
import time
import unicodedata
import urllib.parse

from . import official_photos

# Words an image may carry beside a name: titles, likeness words, sizes and
# a photographer's or a content system's counters. Anything else is a word
# about something else, and refuses the image.
FILLER = {
    "chief", "vice", "associate", "presiding", "deputy", "senior", "justice", "justices",
    "judge", "honorable", "hon", "the", "of", "and", "official", "officialportrait",
    "portrait", "photo", "photograph", "headshot", "head", "shot", "pic", "picture", "image",
    "img", "mug", "bio", "biography", "profile", "court", "courts", "supreme", "appeals",
    "criminal", "state", "web", "website", "edit", "edited", "small", "sm", "sml", "lg",
    "large", "med", "medium", "tmb", "thumb", "thumbnail", "hires", "highres", "high", "res",
    "new", "final", "color", "colour", "scaled", "approved", "crop", "cropped", "copy", "file",
    "formal", "informal", "preferred", "bench", "robe", "robes", "professional", "sq",
    "square", "jpg", "jpeg", "png", "webp", "gif", "avif", "jr", "sr", "ii", "iii", "iv",
    "mr", "ms", "mrs", "dr", "cj", "jus", "in", "his", "her", "a", "v", "updated", "update",
    "original", "secondary", "position", "seat", "district", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "webjpg", "webpng", "webready", "hs", "dsc", "img", "photo", "sel", "view",
}
# Words that say a scene, a group or a mark, not a likeness.
SCENE = re.compile(r"\b(?:group|staff|swearing|sworn|oath|award|awards|medal|desk|standing|"
                   r"investiture|members|left to right|l-r|townhall|ceremony|logo|seal|banner|"
                   r"building|with|pinned|brother|sister|wife|husband|family|conference|speaks|"
                   r"speaking|event|retirement|retired|former|students|visit|visits)\b")
_TITLED = re.compile(r"(?:Justice|Judge)\s+((?:[A-Z][\w.'’-]*\s*){1,4})")
_HASH = re.compile(r"(?<![A-Za-z0-9])(?=[A-Fa-f0-9]*\d)(?=[A-Fa-f0-9]*[A-Fa-f])[A-Fa-f0-9]{10,}"
                   r"(?![A-Za-z0-9])")
_LABEL = re.compile(r"^(?:bio|biography|full biography|read more|\[read more\]|more|view bio|"
                    r"view biography|learn more)$")


def fold(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).replace("’", "'").lower()


def _split(text):
    """An image's words: camel case and letters against digits apart
    ("BunnApproved", "Bethel0945"), folded, apostrophes dropped."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", str(text or ""))
    text = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", text)
    return [t.replace("'", "") for t in re.split(r"[^a-z0-9']+", fold(text)) if t.replace("'", "")]


_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def name_words(name):
    """A name's words, folded, without suffixes; a hyphenated name's parts
    as well as the whole."""
    words = []
    for w in re.split(r"[\s,]+", fold(name).replace(".", " ")):
        w = w.strip("'\"()")
        if not w or w in _SUFFIX:
            continue
        words.append(w.replace("'", ""))
        if "-" in w:
            words.extend(p for p in w.split("-") if p)
    return [w.replace("-", "") for w in words]


def surname(name):
    words = [w for w in re.split(r"[\s,]+", fold(name).replace(".", " ")) if w and w not in _SUFFIX]
    return words[-1].replace("-", "").replace("'", "") if words else ""


def _cased(text):
    """A field's words as written, case kept, letters and digits apart."""
    text = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", str(text or ""))
    return [t for t in re.split(r"[^A-Za-z0-9'’À-ÿ]+", text) if t.strip("'’")]


def _plain(text):
    """:func:`_split` without parting a change of case."""
    return [t for t in (fold(w).replace("'", "") for w in _cased(text)) if t]


def _made_of(word, pieces):
    """Whether *word* is *pieces* end to end ("justiceapproved")."""
    best = {0}
    for end in range(1, len(word) + 1):
        if any(start in best and word[start:end] in pieces for start in range(end)):
            best.add(end)
    return len(word) in best


def _compound(word, pieces, wanted):
    """Whether *word* is made of *pieces* end to end with *wanted* among
    them ("justicebunn", "jrivera")."""
    best = {0: False}
    for end in range(1, len(word) + 1):
        for start in range(end):
            if start in best and word[start:end] in pieces:
                best[end] = best.get(end, False) or best[start] or word[start:end] == wanted
    return best.get(len(word), False)


def _filler(token):
    return (token in FILLER or token.isdigit() or len(token) == 1
            or re.fullmatch(r"\d+x\d+|[a-z]?\d+[a-z0-9]*|[a-z]{1,4}\d+[a-z0-9]*|[a-f0-9]{12,}", token))


def judge(name, members, image, place_words=()):
    """``(ok, why)``: whether *image* (``official_photos.images``'s record)
    is *name*'s likeness by its words alone; *members* are the court's
    other members; *place_words* the state's and court's names, which may
    stand in a file name ("FloridaSupremeCourt")."""
    mine = set(name_words(name))
    family = surname(name)
    if len(family) < 2:
        return False, "no surname"
    words = name_words(name)
    # Initials: of the given names ("jrivera") and of the whole name
    # ("rah042921" is Rebeca Aizpuru Huddle's).
    initials = {"".join(w[0] for w in words[:-1] if w), "".join(w[0] for w in words if w)}
    pieces = mine | FILLER | set(place_words) | initials | {family} | {w[0] for w in mine}
    fields = [image.get("alt"), image.get("title"), image.get("caption"),
              official_photos.file_name(image.get("src") or "").rsplit(".", 1)[0]]
    # A content system's hash is no word ("Justice_Dana_Oxley_web_
    # 3CF35263E46B0"): split at its digits it would leave "cf" as one.
    fields = [_HASH.sub(" ", str(f or "")) for f in fields]
    # Each field's words as written ("McMillian2472" is "mcmillian") and
    # apart at a change of case ("BunnApproved" is "bunn approved").
    raw = [_plain(f) for f in fields]
    split = [_split(f) for f in fields]
    flat = [t for field in raw for t in field] + [t for field in split for t in field]
    found = family in flat or any(_compound(t, pieces, family) for t in flat if len(t) > len(family))
    if not found:
        return False, "no surname in its words"
    for other in members:
        theirs = surname(other)
        if other == name or not theirs or theirs in mine:
            continue
        if theirs in flat:
            return False, f"names another member ({other})"
    for field in fields[:3]:
        for titled in _TITLED.finditer(str(field or "")):
            said = [t for t in _split(titled.group(1)) if t not in FILLER and len(t) > 1]
            if said and not any(t in mine for t in said):
                return False, f"names someone else: {titled.group(0).strip()!r}"
    scene = SCENE.search(" ".join(" ".join(field) for field in raw + split))
    if scene:
        return False, f"says a scene: {scene.group(0)!r}"

    def plain(token):
        return (token in pieces or _filler(token) or _made_of(token, pieces)
                or any(m in token for m in mine if len(m) > 3))
    extra = []
    for field in fields:
        for token in _cased(field):
            # A possessive is the name's ("View David May's profile").
            token = re.sub(r"['’]s$", "", token)
            if not plain(fold(token).replace("'", "")) and not all(plain(t) for t in _split(token)):
                extra.append(fold(token))
    if extra:
        return False, f"words beyond the name and a title: {' '.join(extra[:6])}"
    return True, ""


def _host(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def same_site(a, b):
    """The court's own site: the same host, or one under the other
    ("supreme.courts.ca.gov" under "courts.ca.gov")."""
    x, y = _host(a), _host(b)
    return bool(x) and (x == y or x.endswith("." + y) or y.endswith("." + x))


def _anchors(page):
    for match in re.finditer(r'<a\b[^>]*?href\s*=\s*"([^"#]+)"[^>]*>(.*?)</a>', page or "", re.S | re.I):
        yield match.start(), match.group(1), official_photos._text(match.group(2))


def bio_pages(roster_url, page, members):
    """``{name: url}``: the page the roster links from each member's own
    name (the link's words carry their surname and their given name, and no
    other member's surname), or, failing that, the one "Bio" or "Read more"
    link in that member's part of the roster - between their name and the
    next member's. Only the court's own site; never a PDF."""
    found = {}
    anchors = list(_anchors(page))

    def usable(href):
        url = urllib.parse.urljoin(roster_url, html.unescape(href))
        if not url.startswith("https://") or not same_site(url, roster_url):
            return None
        if re.search(r"\.pdf(?:$|[?#])", url, re.I) or url.rstrip("/") == roster_url.rstrip("/"):
            return None
        return url

    for name in members:
        mine = name_words(name)
        family = surname(name)
        others = {surname(m) for m in members if m != name} - set(mine)
        hits = set()
        for _at, href, label in anchors:
            said = _split(label)
            if family in said and mine and mine[0] in said and not (set(said) & others):
                url = usable(href)
                if url:
                    hits.add(url)
        if len(hits) == 1:
            found[name] = hits.pop()
    # A row per member with a "Bio" link in it.
    text = page or ""
    spots = []
    for name in members:
        family = surname(name)
        hit = re.search(rf"\b{re.escape(family)}\b", fold(text)) if family else None
        if hit:
            spots.append((hit.start(), name))
    spots.sort()
    for i, (start, name) in enumerate(spots):
        if name in found:
            continue
        end = spots[i + 1][0] if i + 1 < len(spots) else len(text)
        links = {usable(href) for at, href, label in anchors
                 if start <= at < end and _LABEL.match(fold(label).strip())}
        links.discard(None)
        if len(links) == 1:
            found[name] = links.pop()
    return found


def photo_for(name, members, pages, place_words=(), measure=None):
    """``(record, why)`` for one member: the first image on *pages*
    (``[(url, html)]``, the roster first) whose words are theirs
    (:func:`judge`) at a size the page offers within the caps
    (``official_photos.choose``); or ``None`` and why not."""
    measure = measure or official_photos.weigh
    why_not = official_photos.NONE
    tried = set()
    for page_url, page in pages:
        for image in official_photos.images(page_url, page):
            if image["src"] in tried:
                continue
            tried.add(image["src"])
            ok, _ = judge(name, members, image, place_words)
            if not ok:
                continue
            url, weight, why = official_photos.choose(image["offered"], measure)
            if url:
                said = "; ".join(f"{k} {image[k]!r}" for k in ("alt", "title", "caption")
                                 if image.get(k))
                evidence = (f"On the court's page {page_url}: "
                            + (said + "; " if said else "")
                            + f"file {official_photos.file_name(image['src'])!r}")
                return official_photos.record(url, page_url, evidence, weight), ""
            if why in (official_photos.UNKNOWN, official_photos.OVERSIZED):
                why_not = why
    return None, why_not


def add_justice_photos(courts, pages, previous=None, get=None, pause=1.0, measure=None):
    """Give each court in *courts* (``{code: read}``) its members'
    photographs, in place: ``read["photos"] = {name: record}`` and
    ``read["photoMisses"] = {name: why}``. *pages* is ``{code: html}``,
    the roster each was read from; *previous* the last cache's courts,
    whose photograph of the same member a read that concludes nothing keeps
    (rule 8). Returns the problems to report."""
    from . import courts as court_module
    from .government_maps import HIGH_COURTS
    from .pages import state_name

    get = get or court_module._get
    problems = []
    for code, read in sorted(courts.items()):
        roster = pages.get(code)
        recipe = court_module.COURTS.get(code) or {}
        before = ((previous or {}).get(code) or {}).get("photos") or {}
        if roster is None or recipe.get("format") == "pdf":
            # Not read this time, or a roster file with no images: what was
            # read before of the same members stands.
            kept = {n: r for n, r in before.items() if n in read.get("members", [])}
            if kept:
                read["photos"] = kept
            continue
        url = recipe["url"]
        place = set(_split(state_name(code[:2]))) | set(_split((HIGH_COURTS.get(code[:2]) or ("",))[0]))
        links = bio_pages(url, roster, read["members"]) if not recipe.get("browser") else {}
        photos, misses = {}, {}
        for name in read["members"]:
            read_pages = [(url, roster)]
            if name in links:
                time.sleep(pause)
                try:
                    read_pages.append((links[name], get(links[name])))
                except court_module.CourtsError:
                    misses[name] = official_photos.UNKNOWN
            found, why = photo_for(name, read["members"], read_pages, place, measure)
            if found:
                photos[name] = found
                continue
            why = misses.get(name) or why
            if why == official_photos.UNKNOWN and name in before:
                photos[name] = before[name]
                problems.append(f"{code}: {name}'s photograph could not be read; the last one "
                                "read is kept")
                continue
            misses[name] = why
        for name in sorted(set(photos) | set(before)):
            was, now = (before.get(name) or {}).get("photo"), (photos.get(name) or {}).get("photo")
            if was != now and now:
                problems.append(f"{code}: photograph {'changed' if was else 'added'} for {name}: "
                                f"{now} (from {photos[name]['page']}); look at it")
            elif was and not now and name in read["members"]:
                problems.append(f"{code}: photograph dropped for {name} (was {was})")
        read.pop("photos", None)
        read.pop("photoMisses", None)
        if photos:
            read["photos"] = photos
        if misses:
            read["photoMisses"] = misses
    return problems


def curated():
    """``{(court, name): record}`` from ``overrides.JUSTICE_PHOTOS``."""
    from .overrides import JUSTICE_PHOTOS
    return dict(JUSTICE_PHOTOS)


def curated_problems(members_of):
    """Every ``overrides.JUSTICE_PHOTOS`` entry that lacks what a read
    photograph carries (an error), or whose justice the court no longer
    lists (a warning: it is not shown). *members_of* is ``{court: [names]}``.
    Returns ``(errors, warnings)``."""
    errors, warnings = [], []
    for (code, name), rec in sorted(curated().items()):
        errors.extend(official_photos.record_problems(rec, f"JUSTICE_PHOTOS {code} {name}"))
        if name not in (members_of.get(code) or ()):
            warnings.append(f"JUSTICE_PHOTOS {code} {name}: the court no longer lists them; "
                            "not shown")
    return errors, warnings


def for_page(code, read):
    """``{name: {"photo", "page"}}``: what the page shows of a court's
    photographs - the read ones, and an evidenced override's for a member
    the read found none of."""
    shown = {}
    members = (read or {}).get("members") or []
    for name, rec in ((read or {}).get("photos") or {}).items():
        if name in members and not official_photos.record_problems(rec, name):
            shown[name] = {"photo": rec["photo"], "page": rec["page"]}
    for (court, name), rec in curated().items():
        if court == code and name in members and name not in shown \
                and not official_photos.record_problems(rec, name):
            shown[name] = {"photo": rec["photo"], "page": rec["page"]}
    return shown


def counts(cache):
    """``{"shown", "oversized", "none", "unknown", "members"}`` over every
    read court, for the build's report."""
    out = {"members": 0, "shown": 0, "oversized": 0, "none": 0, "unknown": 0, "shape": 0}
    for code, read in ((cache or {}).get("courts") or {}).items():
        out["members"] += len(read.get("members") or ())
        out["shown"] += len(for_page(code, read))
        for why in (read.get("photoMisses") or {}).values():
            if why in out:
                out[why] += 1
    return out
