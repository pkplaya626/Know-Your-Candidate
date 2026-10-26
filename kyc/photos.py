"""Portrait URL resolution.

Each profile carries an ordered list of candidate image URLs. The page tries
them in order and falls back to the next on load error, ending at the literal
sentinel ``"placeholder"`` which the page renders as an inline silhouette.

Every URL in a chain is resolved from an id the source holds (a bioguide id)
or chosen by hand (``overrides.CANDIDATE_PHOTOS``). Nothing is built from a
name. The chains used to end in Wikipedia ``Special:FilePath/<Name>.jpg``
guesses, and the files those names reach are whoever uploaded under them:
"Justin_Murphy.jpg" is a French-Australian rugby league player and
"David_Smith.jpg" an Australian Olympic kayaker, and both were the first
photograph on the profiles of the New Jersey and Oregon Republican Senate
nominees. Behind every member's official sources sat the same guess -
"Al_Green.jpg" is the singer - one outage away from the page (rule 24).
"""

import re

from .normalize import is_missing
from .overrides import CANDIDATE_PHOTOS

PLACEHOLDER = "placeholder"

# What no chain may hold: a file reached by a name rather than an id.
GUESSED_PHOTO_MARKERS = ("Special:FilePath", "Special:Redirect")


def member_photos(name, bioguide_id):
    """Portrait chain for a sitting member, best source first.

    Order: Congress.gov, the unitedstates project's copy of the GPO photo
    (often a Congress or two older, so a last resort), then the Biographical
    Directory's own photograph, all by Bioguide id. A member without a
    Bioguide id has the silhouette; *name* is not used to look for one.

    The project's images used to be linked at theunitedstates.io. That domain
    lapsed: on 2026-10-03 it resolved to a domain-parking network and its TLS
    handshake failed, so every member's chain pointed twice at a host anyone
    could buy (rule 35). The project serves the same files from GitHub Pages.
    The Directory's old image host, bioguideretro.congress.gov, answered 404
    for every member on 2026-10-17; ``bioguide.congress.gov/photo/<ID>.jpg``
    serves the same Directory's photographs (HTTP 200, image/jpeg).
    """
    urls = []

    if not is_missing(bioguide_id):
        bg = str(bioguide_id).strip()
        upper, lower = bg.upper(), bg.lower()
        urls += [
            f"https://www.congress.gov/img/member/{lower}_200.jpg",
            f"https://unitedstates.github.io/images/congress/450x550/{upper}.jpg",
            f"https://bioguide.congress.gov/photo/{upper}.jpg",
        ]

    urls.append(PLACEHOLDER)
    return urls


def candidate_photos(name, state):
    """Portrait chain for a 2026 candidate.

    The curated override is keyed on ``(name, state)`` so that two different
    people who share a name never share a portrait. Anything else reaches the
    chain through ``portraits`` - an article the person's ballot page links,
    checked to be about them (rules 24 and 33) - or not at all.
    """
    urls = []

    override = CANDIDATE_PHOTOS.get((str(name).strip(), state))
    if override:
        urls.append(override[0])  # (url, date checked, evidence)

    urls.append(PLACEHOLDER)
    return urls


def is_guessed(url):
    """True for a URL that reaches a file by a name, not an id."""
    return any(marker in str(url or "") for marker in GUESSED_PHOTO_MARKERS)


# Whose photograph a government portrait is, by the host that serves it. A
# profile's credit names the source of the photograph it shows (TRUST-08):
# the House's official portrait is the House's, not "Congress.gov", which is
# what the footer said of every portrait before.
HOST_CREDITS = {
    "clerk.house.gov": "U.S. House of Representatives",
    "www.congress.gov": "Congress.gov",
    "unitedstates.github.io": "U.S. Government Publishing Office",
    "bioguide.congress.gov": "Biographical Directory of the U.S. Congress",
}

# The heaviest single-file portrait taken from a campaign's site, and the
# widest. The largest the page draws is a 165px card, 330px on a 2x screen;
# one site's 1.3 MB, 876px PNG was downloaded for that card (TECH-13).
MAX_PORTRAIT_BYTES = 300_000
MAX_PORTRAIT_PX = 1200


def too_heavy(weight):
    """Why a measured portrait is too heavy to show, or ``""``. An unmeasured
    one (``None``) is not: unknown is not too big (rule 8)."""
    if not weight:
        return ""
    if (weight.get("bytes") or 0) > MAX_PORTRAIT_BYTES:
        return f"{weight['bytes'] // 1000} KB, over {MAX_PORTRAIT_BYTES // 1000} KB"
    if max(weight.get("width") or 0, weight.get("height") or 0) > MAX_PORTRAIT_PX:
        return (f"{weight.get('width')}x{weight.get('height')}px, over "
                f"{MAX_PORTRAIT_PX}px")
    return ""


def others_only(entry):
    """Is a ``NOT_A_PORTRAIT`` entry's only finding other people in the
    frame - behind, beside, in part - marked ``overrides.OTHERS_IN_FRAME``?
    A picture of a person (a framed photograph on a shelf, a poster, a book
    jacket) is not a person in the frame, and is never such an entry."""
    from .overrides import OTHERS_IN_FRAME
    return len(entry) > 2 and entry[2] == OTHERS_IN_FRAME


def applies(entry, judge=False):
    """Does a ``NOT_A_PORTRAIT`` entry refuse its file for this route? For
    everyone, except that the owner's background-people rule ("probably
    better to leave out background people", 2026-10-25) is for candidates'
    and officials' photographs: of a judge's portrait - a federal judge's
    Senate Judiciary hearing still, a state justice's from the court's own
    roster - he said "keep" the same day, since the judge is plainly the
    subject. So for a judge (*judge*) an entry whose only finding is other
    people in the frame (:func:`others_only`) does not apply; one that
    finds another person the subject, no likeness, a drawing or a scene
    does, as do the licence doubts."""
    return not (judge and others_only(entry))


def refused(*urls, judge=False):
    """Why the lists a person keeps withhold one of *urls*, or ``""``:
    ``overrides.NOT_A_PORTRAIT`` (rule 38: someone looked, and it is not a
    likeness) or ``overrides.PORTRAIT_LICENCE_DOUBTS`` (rule 82: its licence
    waits for a person). One test for every route that asks both - a
    nominee's (``nominee_photos``), an official's or a statewide
    candidate's (``official_photos.held_back``) and a judge's
    (``judge_links.held_back``, *judge*: :func:`applies`) - asked of a
    record read now and of one kept from an earlier read (rule 8)."""
    from . import overrides

    doubts = getattr(overrides, "PORTRAIT_LICENCE_DOUBTS", {})
    for url in urls:
        if not url:
            continue
        if url in overrides.NOT_A_PORTRAIT and applies(overrides.NOT_A_PORTRAIT[url], judge):
            return f"{url} is in overrides.NOT_A_PORTRAIT ({overrides.NOT_A_PORTRAIT[url][1]})"
        if url in doubts:
            return f"{url} is in overrides.PORTRAIT_LICENCE_DOUBTS ({doubts[url][1]})"
    return ""


def not_a_portrait(*urls, passed_over=None, table=None, judge=False):
    """The first of *urls* a person looked at and found no likeness of the
    person alone in (``overrides.NOT_A_PORTRAIT``, rule 38), or ``""``. The
    one test every reader asks of an image it meets on a page - a campaign
    site's (``enrich``), a court's (``court_photos``, *judge*), an attorney
    general's office's (``officers.add_ag_photos``), a statewide
    candidate's guide or article (``statewide_photos``), a federal judge's
    Commons file (``judge_links``, *judge*) - where ``refused`` asks both
    lists of a record already made (rule 12). For a judge an entry whose
    only finding is other people in the frame does not apply
    (:func:`applies`, the owner's decision of 2026-10-25).
    What it refuses is appended to *passed_over*, the list the reader keeps
    in its cache as ``notPortraits``, so ``validate``'s staleness check
    knows the entry still names an image a route offers. *table* stands in
    for the overrides in a test."""
    if table is None:
        from .overrides import NOT_A_PORTRAIT as table
    for url in urls:
        if url and url in table and applies(table[url], judge):
            if passed_over is not None and url not in passed_over:
                passed_over.append(url)
            return url
    return ""


def host_of(url):
    import urllib.parse
    try:
        return (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def host_credit(url):
    """The credit for a government portrait at *url*, or ``None``."""
    by = HOST_CREDITS.get(host_of(url))
    return {"by": by} if by else None


def campaign_credit(site):
    """The credit for a photograph taken from the campaign's own site."""
    host = host_of(site)
    if host.startswith("www."):
        host = host[4:]
    return {"by": f"the campaign's website ({host})" if host else "the campaign's website",
            "page": site or None}


def assign_credits(profiles):
    """Give every profile whose chain starts with a photograph the credit
    for that photograph; returns how many have one.

    A Wikimedia portrait's credit comes with it from the portrait cache
    (``portraits.apply_cache``) and a campaign's from the enrichment cache
    (``enrich.apply_cache``); a government portrait's is its host's. A
    profile that shows the silhouette carries none."""
    credited = 0
    for profile in profiles:
        first = (profile.get("photos") or [PLACEHOLDER])[0]
        if first == PLACEHOLDER:
            profile.pop("photoCredit", None)
            continue
        if profile.get("photoSource") in ("wikipedia", "cross-link", "campaign-site",
                                          "wikidata-fec", "state-legislature",
                                          "election-guide") \
                and profile.get("photoCredit"):
            credited += 1
            continue
        credit = host_credit(first)
        if credit:
            profile["photoCredit"] = credit
            credited += 1
        else:
            profile.pop("photoCredit", None)
    return credited


SMALLER_WIDTH = 500
# The widths a heavy file is asked for, widest first: 500px is sharp in any
# box the pages draw, 330px is a 165px card on a 2x screen, and a PNG that
# is still too heavy at 500 usually is not at 330.
SMALLER_WIDTHS = (500, 330)
PHOTON_HOSTS = ("i0.wp.com", "i1.wp.com", "i2.wp.com", "i3.wp.com")
SQUARESPACE_WIDTHS = (100, 300, 500, 750, 1000, 1500, 2500)


def host_resized(url, width=SMALLER_WIDTH):
    """*url* at *width* pixels wide from its host's own resizing service, or
    ``None``. Squarespace's image CDN (``format=500w``), imgix and
    WordPress.com's Photon (``w=500``, on ``i0.wp.com`` and its siblings)
    serve any upload at a width asked for: the same file, so the same
    photograph (rule 42), checked again for shape and weight before it is
    taken."""
    import urllib.parse

    try:
        parts = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    if host == "images.squarespace-cdn.com":
        # Squarespace serves a fixed set of widths and the original for any
        # other: the widest of its set no wider than asked.
        width = max((w for w in SQUARESPACE_WIDTHS if w <= width), default=SQUARESPACE_WIDTHS[0])
        query = [(k, v) for k, v in query if k != "format"] + [("format", f"{width}w")]
    elif host.endswith(".imgix.net") or host in PHOTON_HOSTS:
        query = [(k, v) for k, v in query if k not in ("w", "resize", "fit")] + [("w", str(width))]
    else:
        return None
    smaller = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    return smaller if smaller != url else None


def photon_form(url, width=SMALLER_WIDTH):
    """*url* at *width* pixels wide through WordPress.com's public image
    resizer (Photon, ``i0.wp.com/<host>/<path>?w=``), or ``None``.

    Photon fetches the very file at that address and scales it, so what it
    serves is the same photograph (rule 42), and it answers 404 for a file
    that is not there, never another image. It is used for a file whose own
    host has no resizer: eleven November nominees' only portraits were
    campaign uploads of 1-2.6 MB or 2,048px, and 27 governors' NGA
    headshots ran 320 KB to 7.6 MB for a 40px circle (TECH-13). Only a plain
    https address of an image file is asked for: Photon drops a query
    string, which could name another file."""
    import urllib.parse

    try:
        parts = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if (parts.scheme != "https" or not host or parts.query or parts.port
            or host in PHOTON_HOSTS or host.endswith(".imgix.net")
            or host == "images.squarespace-cdn.com"
            or not re.search(r"\.(?:jpe?g|png|gif|webp)$", parts.path, re.I)):
        return None
    return f"https://i0.wp.com/{host}{parts.path}?w={int(width)}&ssl=1"


def smaller_form(url, width=SMALLER_WIDTH):
    """*url* at *width* pixels wide: from its host's own resizer
    (:func:`host_resized`), or else through Photon (:func:`photon_form`);
    ``None`` when neither serves it. Nothing is guessed - no size suffix a
    host might have generated - and whatever comes back is weighed and
    checked for shape before it is used."""
    return host_resized(url, width) or photon_form(url, width)


def smaller_forms(url):
    """:func:`smaller_form` at each of :data:`SMALLER_WIDTHS`, widest first."""
    out = []
    for width in SMALLER_WIDTHS:
        form = smaller_form(url, width)
        if form and form not in out:
            out.append(form)
    return out


def same_shape(original, smaller):
    """Whether *smaller* (a weight: ``{"bytes", "width", "height"}``) is
    *original* scaled down: narrower, at the same proportions to within 2%
    (a resizer rounds a pixel). A resizer that answered with some other
    image - a placeholder, an error picture - has some other shape."""
    try:
        ratio = original["width"] / original["height"]
        scaled = smaller["width"] / smaller["height"]
    except (KeyError, TypeError, ZeroDivisionError):
        return False
    return smaller["width"] < original["width"] and abs(scaled - ratio) <= 0.02 * ratio


def lighter_form(url, weight, weigh):
    """``(form, its weight)``: the widest of :func:`smaller_forms` of *url*
    within the caps and the same picture scaled, or ``None``
    (:func:`lighter_rendition` with no page to offer renditions: a
    governor's headshot)."""
    return lighter_rendition(url, weight, weigh)


# The widest a card needs: a 165px card on a 2x screen.
CARD_WIDTH = 330


def parse_srcset(srcset, base=""):
    """``[(url, width)]`` from an ``<img srcset>``, each address resolved
    against *base*; a candidate with no width descriptor has width 0.

    Parsed the way the HTML standard does, not by splitting on commas: an
    address is a run of characters up to whitespace, and Wix's carry
    commas of their own ("/v1/fill/w_432,h_681,al_c/...")."""
    import urllib.parse

    out, text, i = [], str(srcset or ""), 0
    while i < len(text):
        while i < len(text) and (text[i].isspace() or text[i] == ","):
            i += 1
        start = i
        while i < len(text) and not text[i].isspace():
            i += 1
        url = text[start:i]
        descriptors = ""
        if url.endswith(","):
            url = url.rstrip(",")
        else:
            start = i
            while i < len(text) and text[i] != ",":
                i += 1
            descriptors = text[start:i]
        if not url:
            continue
        width = 0
        for descriptor in descriptors.split():
            if descriptor.endswith("w") and descriptor[:-1].isdigit():
                width = int(descriptor[:-1])
        out.append((urllib.parse.urljoin(base, url), width))
    return out


def offered_forms(offered):
    """The renditions a page's own srcset offers of one image, in the order
    they are tried: the narrowest at least :data:`CARD_WIDTH` wide first,
    then the narrower ones, widest first. A rendition that declares itself
    wider than :data:`MAX_PORTRAIT_PX` is over the caps whatever it weighs,
    and is not tried: Mark Nair's Squarespace page lists 100w to 2500w, and
    the five tries went to 500w, 750w, 1000w, 1500w and 2500w, never
    reaching 300w, the one within the caps, so his 479 KB original was
    shown."""
    sized = sorted({(int(width), url) for url, width in offered or ()
                    if width and int(width) <= MAX_PORTRAIT_PX})
    wide = [url for width, url in sized if width >= CARD_WIDTH]
    narrow = [url for width, url in reversed(sized) if width < CARD_WIDTH]
    return wide + narrow


def lighter_rendition(url, weight, weigh, offered=(), tries=5):
    """``(form, its weight)``: the first rendition of *url* within the caps
    that is the same picture scaled (:func:`same_shape` against *weight*,
    the original's), or ``None``. *weigh* reads a URL's weight, ``None``
    when it cannot.

    Tried in this order: a rendition the image's own page lists (*offered*,
    its ``srcset``: WordPress's "-683x1024" files, Wix's "w_432,h_681"
    ones), then its host's own resizer or Photon (:func:`smaller_forms`),
    as rule 87 had it before the brief of 2026-10-19 ruled the resizers
    out. The owner's decision of 2026-10-25 ("more content is better than
    strict rules") put them back: Photon fetches that very file and scales
    it, so it is the same photograph (rule 42), and what comes back is
    weighed and checked for shape before it is used. Where none serves it
    the caller shows the original all the same and says so (rule 87)."""
    forms = [form for form in offered_forms(offered) if form != url]
    for form in smaller_forms(url):
        if form not in forms:
            forms.append(form)
    for form in forms[:tries]:
        found = weigh(form)
        if found and not too_heavy(found) and same_shape(weight, found):
            return form, found
    return None
