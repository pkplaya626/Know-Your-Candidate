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
        if profile.get("photoSource") in ("wikipedia", "cross-link", "campaign-site") \
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
