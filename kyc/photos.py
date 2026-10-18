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
