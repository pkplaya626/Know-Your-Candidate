"""Portrait URL resolution.

Each profile carries an ordered list of candidate image URLs. The page tries
them in order and falls back to the next on load error, ending at the literal
sentinel ``"placeholder"`` which the page renders as an inline silhouette.
"""

from .normalize import is_missing
from .overrides import CANDIDATE_PHOTOS

PLACEHOLDER = "placeholder"


def _wiki_slugs(name):
    """Wikipedia ``Special:FilePath`` slugs to try for *name*.

    Yields the full name first (correct for people with middle names, e.g.
    "Ben Ray Lujan") before the first+last contraction.
    """
    parts = [p for p in str(name).split() if p]
    if not parts:
        return []

    slugs = ["_".join(parts)]
    if len(parts) > 2:
        slugs.append(f"{parts[0]}_{parts[-1]}")
    return slugs


def _wiki_urls(name, suffixes=("", "_official_portrait")):
    urls = []
    for slug in _wiki_slugs(name):
        for suffix in suffixes:
            urls.append(f"https://en.wikipedia.org/wiki/Special:FilePath/{slug}{suffix}.jpg")
    return urls


def member_photos(name, bioguide_id):
    """Portrait chain for a sitting member, best source first.

    Order: Congress.gov, theunitedstates.io (two sizes), Bioguide Retro, then
    Wikipedia. Members without a Bioguide ID skip straight to Wikipedia.
    """
    urls = []

    if not is_missing(bioguide_id):
        bg = str(bioguide_id).strip()
        upper, lower = bg.upper(), bg.lower()
        initial = upper[0] if upper else "A"
        urls += [
            f"https://www.congress.gov/img/member/{lower}_200.jpg",
            f"https://theunitedstates.io/images/congress/450x550/{upper}.jpg",
            f"https://theunitedstates.io/images/congress/225x275/{upper}.jpg",
            f"https://bioguideretro.congress.gov/Static_Files/images/bioguide/{initial}/{upper}.jpg",
        ]

    urls += _wiki_urls(name)
    urls.append(PLACEHOLDER)
    return urls


def candidate_photos(name, state):
    """Portrait chain for a 2026 candidate.

    The curated override is keyed on ``(name, state)`` so that two different
    people who share a name never share a portrait.
    """
    urls = []

    override = CANDIDATE_PHOTOS.get((str(name).strip(), state))
    if override:
        urls.append(override)

    urls += _wiki_urls(name, suffixes=("", "_portrait"))
    urls.append(PLACEHOLDER)
    return urls
