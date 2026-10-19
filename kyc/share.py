"""Share pages, and the plain lists the state pages are written with (rule 96).

A profile or a race is a view behind a fragment (``index.html#/profile/<id>``),
and a crawler drops the fragment: every person or race anyone shared
unfurled as the home page's card. So the build writes one small page per
profile (``p/<id>.html``) and per race (``r/<raceId>.html``), each with its
own title, description, canonical address and image, and the facts in
plain text. A reader with scripts is sent on to the view at once
(``assets/kyc-share.js``, never an inline script); a reader without, and a
crawler, stay and read the facts.

Where someone stands in their race is said in the words the profile dialog
uses (``KYC.standing`` in ``assets/kyc.js``, the one table of rule 63). A
page written without JavaScript cannot call it, so :func:`status_words` is
that function's "long" form read the same way, and the render suite
compares the two for every profile on every build (``testSharePages``): a
word changed in one and not the other fails, as two copies of the table
once drifted unnoticed.

Nothing here is dated, and nothing here carries the build's time: a refresh
that changes nobody's status rewrites none of these 3,000 files (rule 18).
"""

import html
from urllib.parse import urlparse

PROFILE_DIR = "p"
RACE_DIR = "r"


def _e(text):
    return html.escape(str(text), quote=True)


def profile_path(pid):
    """``p/<id>.html``, relative to the site's root."""
    return f"{PROFILE_DIR}/{pid}.html"


def race_path(rid):
    """``r/<raceId>.html``, relative to the site's root."""
    return f"{RACE_DIR}/{rid}.html"


# ------------------------------------------------------------- the words

# KYC.raceStatus's "long" words, status by status, with the member's own
# wording (`member`) and whether the status takes someone out of the race
# (`off`). Only the "long" form: it is the one the profile dialog shows.
def _leaving():
    return {"long": "Not running for re-election in 2026"}


_RACE_STATUS = {
    "nominee": {"long": "On the November ballot", "member": {"long": "Renominated for 2026"}},
    "elected": {"long": "Elected in November", "member": {"long": "Re-elected in November"}},
    "runoff": {"long": "In the general election runoff"},
    "advanced": {"long": "In a primary runoff"},
    "qualified": {"long": "On the November 3 open-primary ballot"},
    "defeated": {"long": "Lost the November election",
                 "member": {"long": "Lost re-election in November"}},
    "eliminated": {"long": "Lost the 2026 primary", "off": True},
    "withdrawn": {"long": "Withdrew from the 2026 race", "off": True, "member": _leaving()},
    "unlisted": {"long": "Not on the 2026 primary ballot", "off": True, "member": _leaving()},
}
_APPOINTEE_LEAVING = {"long": "Not running in 2026"}
_UNCONFIRMED = {"long": "Not on the November ballot", "off": True}
_AWAITING = {"long": "On the November ballot: awaiting result"}
_MINOR_NOMINEE = {"long": "On the November ballot"}
_ALL_PARTY = {"long": "Advanced to the November ballot",
              "member": {"long": "Advanced to the November ballot"}}
_LISTED = {
    "unlisted": {"long": "Not on the November 3 open-primary ballot", "off": True,
                 "member": _leaving()},
    "withdrawn": {"long": "Withdrew from the 2026 race", "off": True, "member": _leaving()},
}
_CERTIFIED = {
    "nominee": {"member": {"long": "On the November ballot"}},
    "unlisted": {"long": "Not on the November ballot", "off": True, "member": _leaving()},
    "withdrawn": {},
    "eliminated": {},
}
NOVEMBER = frozenset({"nominee", "elected", "defeated", "runoff", "qualified"})
OFF_BALLOT = frozenset({"eliminated", "withdrawn", "unlisted"})


def party_key(person):
    """KYC.partyKey: "d", "r", "vacant" or "i"."""
    party = str((person or {}).get("party"))
    if party == "Vacant" or (person or {}).get("status") == "Vacant":
        return "vacant"
    if "Democrat" in party:
        return "d"
    if party == "Republican":
        return "r"
    return "i"


def _runs_elsewhere(item):
    return (not item.get("isCandidate") and bool(item.get("contestRaceId"))
            and item.get("contestRaceId") != item.get("raceId"))


def _own_record(item):
    return not _runs_elsewhere(item) or item.get("raceStatusRace") == item.get("contestRaceId")


def contest_status(item, by_id):
    """KYC.contestStatus: the result that describes what *item* does in 2026."""
    if _own_record(item):
        return item.get("raceStatus") or ""
    filing = by_id.get(item.get("alsoRunningId") or "")
    if filing and filing.get("raceId") == item.get("contestRaceId"):
        return filing.get("raceStatus") or ""
    return ""


def ballot_line(item, by_id):
    """KYC.ballotLine: a nominee's November line when it is not their party's."""
    if contest_status(item, by_id) not in NOVEMBER:
        return ""
    if _own_record(item):
        return str(item.get("ballotLine") or "")
    filing = by_id.get(item.get("alsoRunningId") or "")
    if filing and filing.get("raceId") == item.get("contestRaceId"):
        return str(filing.get("ballotLine") or "")
    return ""


def _race_status(status, own=False, unconfirmed=False, appointed=False, source=None,
                 all_party=None, minor=False, post_election=False):
    """KYC.raceStatus(status, "long", opts): ``(words, off)`` or None."""
    spec = _RACE_STATUS.get(status)
    if not spec:
        return None
    if status == "nominee" and all_party:
        spec = _ALL_PARTY
    if source == "qualified" and status in _LISTED:
        spec = _LISTED[status]
    certified = _CERTIFIED.get(status) if source == "certified" else None
    if certified is not None:
        merged = dict(spec)
        merged.update(certified)
        if "member" not in certified and spec.get("member"):
            merged["member"] = dict(spec["member"])
        spec = merged
    if status == "unlisted" and unconfirmed and certified is None:
        spec = _UNCONFIRMED
    mine = (own and spec.get("member")) or {}
    if own and appointed and spec.get("member") and spec.get("off"):
        mine = _APPOINTEE_LEAVING
    if status == "nominee" and spec is _RACE_STATUS["nominee"] and minor and not own:
        spec = _MINOR_NOMINEE
    if status in ("nominee", "qualified") and post_election:
        spec, mine = _AWAITING, {}
    return (mine.get("long") or spec.get("long"), bool(spec.get("off")))


def _no_primary_race(race_id, races_by_id):
    """KYC's noPrimaryRace: a race whose calendar names no primary (null,
    not absent) and for which no results were read."""
    race = races_by_id.get(race_id)
    return bool(race) and "primaryDate" in race and race["primaryDate"] is None \
        and race.get("results") is None


def _unsettled(item, races_by_id):
    """KYC's unsettled(): a filer the results do not settle."""
    if not item.get("isCandidate") or item.get("raceStatus"):
        return None
    if item.get("maybeNamed"):
        return "Result not matched"
    unprinted = item.get("unprinted") or {}
    if unprinted.get("kind"):
        return ("Unopposed in November, not printed" if unprinted["kind"] == "unopposed"
                else "Write-in candidate")
    no_primary = not item.get("ballotUnknown") and _no_primary_race(item.get("raceId"), races_by_id)
    if item.get("ballotUnknown") or no_primary:
        return "Ballot status not known"
    return None


def standing(item, by_id, races_by_id, post_election=False):
    """KYC.standing(item, "long"): ``(words, off)``, or None for no status."""
    if not item:
        return None
    record = item if _own_record(item) else (by_id.get(item.get("alsoRunningId") or "") or {})
    status = contest_status(item, by_id)
    spec = _race_status(
        status,
        own=(not item.get("isCandidate") and not item.get("contestLabel")
             and not item.get("raceRole") and not (item.get("appointed") and status != "unlisted")),
        unconfirmed=bool(item.get("raceStatusUnconfirmed")),
        appointed=bool(item.get("appointed")),
        source=record.get("raceStatusSource"),
        all_party=record.get("allPartyPrimary"),
        minor=party_key(item) == "i",
        post_election=post_election)
    if spec:
        return spec
    words = _unsettled(item, races_by_id)
    return (words, False) if words else None


def status_words(item, by_id, races_by_id, post_election=False):
    """Where *item* stands, as the profile dialog's badge says it: the
    standing, "for <seat>" when a member runs for another, and the ballot
    line when it is not their party's. None for someone with no 2026 race
    (a senator whose seat is not up)."""
    spec = standing(item, by_id, races_by_id, post_election)
    if not spec:
        return None
    words = spec[0]
    if not item.get("isCandidate") and item.get("contestLabel"):
        words += " for " + item["contestLabel"]
    line = ballot_line(item, by_id)
    if line:
        words += " – " + line + " line"
    return words


def post_election(summary):
    """Whether the results the build holds were read after Election Day:
    KYC.electionStatus's "post-election" on the day they were read. The
    page's own clock is the reader's; a page written once is the data's."""
    from . import cycle

    as_of = (((summary or {}).get("election") or {}).get("resultsAsOf") or "")[:10]
    if not as_of:
        return False
    return as_of > cycle.general_election_day(cycle.CYCLE).isoformat()


def ballot_source(race):
    """KYC.ballotSource: who named the people on a race's November ballot."""
    res = (race or {}).get("results") or {}
    if res.get("fromQualifiedList"):
        return "per the Secretary of State's list of qualified candidates"
    if res.get("certifiedBy"):
        return ("per the " + res["certifiedBy"] if res.get("certifiedComplete")
                else "per Wikipedia's results page and the " + res["certifiedBy"])
    return "per Wikipedia's results page"


# ------------------------------------------------------------ portraits

def og_photo(person):
    """The share image of *person*: a photograph that reached the profile
    by a sourced route (rule 24), or None for the site's card. Only the
    sizes of the article's own file (``photoSet``, rule 42), the House
    Clerk's portrait, or a campaign's own portrait with its credit - never
    a URL from a fallback chain."""
    sizes = [s for s in person.get("photoSet") or []
             if isinstance(s, (list, tuple)) and len(s) == 2 and _https(s[1])]
    if sizes:
        fits = [s for s in sizes if s[0] <= 640]
        width, url = max(fits) if fits else min(sizes)
        return url
    url = person.get("photo_url") or ""
    source = person.get("photoSource")
    if not _https(url) or "Special:" in url:
        return None
    if source in ("clerk.house.gov", "cross-link") and urlparse(url).hostname == "clerk.house.gov":
        return url
    if source == "campaign-site" and person.get("photoCredit"):
        return url
    return None


def _https(url):
    return isinstance(url, str) and url.startswith("https://") and bool(urlparse(url).hostname)


# ----------------------------------------------------------------- pages

_SHARE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="{canonical}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
{image_size}<meta property="og:image:alt" content="{image_alt}">
<meta property="og:site_name" content="Know Your Candidate">
<meta name="twitter:card" content="{card}">
<meta name="referrer" content="no-referrer">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
<style>
body {{ margin: 0 auto; max-width: 40rem; padding: 1.5rem 1rem; line-height: 1.5;
       font-family: system-ui, sans-serif; background: Canvas; color: CanvasText; }}
ul {{ padding-left: 1.25rem; }}
.faint {{ opacity: .75; font-size: .9em; }}
</style>
</head>
<body data-share="{kind}">
<p class="faint"><a href="../index.html">Know Your Candidate</a></p>
<main>
<h1>{heading}</h1>
{body}
<p><a id="shareView" href="{view}">{view_words}</a></p>
<p class="faint">That view needs JavaScript. Without it, {fallback}</p>
</main>
<script src="../assets/kyc-share.js"></script>
</body>
</html>
"""

_SITE_CARD = "assets/social-card.png"


def _page(host, path, **fields):
    canonical = f"https://{host}/{path}" if host else path
    image = fields.pop("image", None)
    if image:
        size, card, alt = "", "summary", fields.pop("image_alt")
    else:
        image = f"https://{host}/{_SITE_CARD}" if host else "../" + _SITE_CARD
        size = ('<meta property="og:image:width" content="1200">\n'
                '<meta property="og:image:height" content="630">\n')
        card, alt = "summary_large_image", "Know Your Candidate"
        fields.pop("image_alt", None)
    return _SHARE.format(canonical=_e(canonical), image=_e(image), image_size=size,
                         image_alt=_e(alt), card=card, **fields)


def _state_page(code):
    return f"../states/{str(code).lower()}.html"


def describe(person, by_id, races_by_id, post=False):
    """``(og title, description, status words)`` for a profile's share page:
    "<Name> (<party>), candidate for House • AK-AL: Not on the 2026 primary
    ballot." The office is the profile's own label (rule 4), never rebuilt."""
    from .record import seated

    name, party = person.get("name") or "", person.get("party") or ""
    role = ("candidate for" if person.get("isCandidate")
            else "member for" if seated(person) else "former member for")
    status = status_words(person, by_id, races_by_id, post)
    lead = f"{name} ({party})" if party else name
    office = person.get("officeLabel") or ""
    description = f"{lead}, {role} {office}" + (f": {status}." if status else ".")
    return lead, description, status


def render_profile(person, host, by_id, races_by_id, post=False):
    """``p/<id>.html``."""
    from .pages import _possessive, state_name

    pid = person["id"]
    lead, description, status = describe(person, by_id, races_by_id, post)
    body = [f"<p>{_e(person.get('party') or '')} &middot; {_e(person.get('officeLabel') or '')}</p>"]
    if status:
        body.append(f'<p class="share-status"><strong>{_e(status)}</strong></p>')
    race = races_by_id.get(person.get("contestRaceId") or person.get("raceId") or "")
    if race:
        body.append(f'<p>The race: <a href="../{_e(race_path(race["id"]))}">{_e(race["label"])}</a></p>')
    photo = og_photo(person)
    return _page(
        host, profile_path(pid),
        title=_e(f"{person.get('name')} — Know Your Candidate"),
        description=_e(description),
        og_type="profile",
        og_title=_e(lead),
        image=photo,
        image_alt=f"Portrait of {person.get('name')}",
        kind="profile",
        heading=_e(person.get("name") or ""),
        body="\n".join(body),
        view=_e(f"../index.html#/profile/{pid}"),
        view_words=_e(f"Open {person.get('name')}'s full profile"),
        fallback=(f'<a href="{_e(_state_page(person.get("state")))}">'
                  f'{_e(_possessive(state_name(person.get("state"))))} page</a> '
                  "lists its members and races in plain text."),
    )


def race_people(race, by_id):
    """The people a race lists, in its order (rule 63): the seat's holder,
    then everyone filed for it, as ``KYC.cards.raceSection`` takes them."""
    out, seen = [], set()
    for pid in list(race.get("incumbentIds") or []) + list(race.get("candidateIds") or []):
        if pid in seen or pid not in by_id:
            continue
        seen.add(pid)
        out.append(by_id[pid])
    return out


def _elsewhere(race, person):
    """KYC.cards' elsewhere(): the seat's holder, running for another."""
    return (not person.get("isCandidate") and person["id"] in (race.get("incumbentIds") or [])
            and bool(person.get("contestRaceId")) and person.get("contestRaceId") != race["id"]
            and bool(person.get("contestLabel")))


def split_people(race, by_id):
    """``(held elsewhere, still in the race, no longer in it)``, as
    ``KYC.cards.racePeople`` splits a race: the holder running for another
    seat apart, and anyone a result takes out of it (``offBallot`` of their
    own status) folded under the rest."""
    people = race_people(race, by_id)
    moved = [p for p in people if _elsewhere(race, p)]
    rest = [p for p in people if p not in moved]
    return (moved, [p for p in rest if p.get("raceStatus") not in OFF_BALLOT],
            [p for p in rest if p.get("raceStatus") in OFF_BALLOT])


def held_words(person, by_id):
    """KYC.cards' heldByLine, in words: "who is running for CA-6"."""
    seat = str(person.get("contestLabel")).replace(" • ", " ", 1)
    if seat.startswith("House "):
        seat = seat[len("House "):]
    status = contest_status(person, by_id)
    past = status in OFF_BALLOT or status == "defeated"
    if person.get("renumbered"):
        return (f"ran in {seat} under the state’s new district map, and is not on its "
                "November ballot" if past
                else f"is running in {seat} under the state’s new district map")
    return f"ran for {seat} and is not on its November ballot" if past else f"is running for {seat}"


def unprofiled(race):
    """``(names with no profile, [(name, profile id)] maybe a profile's)``,
    as KYC.cards.unprofiledNames splits the results' other nominees."""
    res = (race or {}).get("results") or {}
    maybe = res.get("maybeProfiled") or {}
    names = res.get("otherNominees") or []
    return [n for n in names if not maybe.get(n)], [(n, maybe[n]) for n in names if maybe.get(n)]


def _item(person, by_id, races_by_id, post, root, indent):
    status = status_words(person, by_id, races_by_id, post)
    party = f" ({_e(person['party'])})" if person.get("party") else ""
    return (f'{indent}<li data-id="{_e(person["id"])}"><a href="{root}'
            f'{_e(profile_path(person["id"]))}">{_e(person.get("name") or "")}</a>{party}'
            + (f': <span class="share-standing">{_e(status)}</span>' if status else "") + "</li>")


def race_list_html(race, by_id, races_by_id, post=False, root="../", indent=""):
    """A race's people as plain lists, each linked to their share page with
    where they stand, split as the race's section on a state page splits
    them: the holder running elsewhere, the people still in it, those no
    longer in it, and the November names with no profile here."""
    moved, running, out = split_people(race, by_id)
    rows = []
    for person in moved:
        rows.append(f'{indent}<p class="race-held">Held by <a href="{root}'
                    f'{_e(profile_path(person["id"]))}">{_e(person.get("name") or "")}</a>, who '
                    f"{_e(held_words(person, by_id))}.</p>")
    rows.append(f'{indent}<ul class="share-list" data-race="{_e(race["id"])}">')
    rows += [_item(p, by_id, races_by_id, post, root, indent + "    ") for p in running]
    rows.append(f"{indent}</ul>")
    none, maybe = unprofiled(race)
    parties = ((race.get("results") or {}).get("otherParties")) or {}
    notes = []
    if none:
        notes.append("Also on the November ballot, " + _e(ballot_source(race)) +
                     ", with no FEC filing over $5,000 and so no profile here: " +
                     ", ".join(_e(n) + (f" ({_e(parties[n])})" if parties.get(n) else "")
                               for n in none) + ".")
    for name, pid in maybe:
        who = (by_id.get(pid) or {}).get("name") or "a candidate with a profile here"
        notes.append(f"Also named, {_e(ballot_source(race))}: {_e(name)}, who may be {_e(who)} "
                     "under another spelling; this site has not confirmed it.")
    if notes:
        rows.append(f'{indent}<p class="share-note">' + " ".join(notes) + "</p>")
    if out:
        rows += [f"{indent}<p>{len(out)} no longer in this race &mdash; lost the primary, "
                 "withdrew, or were not on the primary ballot:</p>",
                 f'{indent}<ul class="share-list share-out" data-race-out="{_e(race["id"])}">']
        rows += [_item(p, by_id, races_by_id, post, root, indent + "    ") for p in out]
        rows.append(f"{indent}</ul>")
    return "\n".join(rows)


def describe_race(race, by_id, races_by_id, post=False):
    """A race's share description: the seat, who holds it, and who is still
    in it with where each stands."""
    label = race.get("label") or race["id"]
    moved, running, _out = split_people(race, by_id)
    held = ""
    # The seat's holder only while they sit in it (rule 67): a record
    # incumbent who has left holds nothing.
    for person in moved:
        held = f"Held by {person.get('name')}, who {held_words(person, by_id)}."
    inc = race.get("incumbent") or {}
    if not held and inc.get("seated") and inc.get("name"):
        held = f"Held by {inc['name']}" + (f" ({inc['party']})." if inc.get("party") else ".")
    people = []
    for person in running:
        status = status_words(person, by_id, races_by_id, post)
        people.append(f"{person.get('name')}" + (f" ({person['party']})" if person.get("party")
                                                  else "") + (f": {status}" if status else ""))
    return " ".join(filter(None, [f"The {race.get('year') or ''} race for {label}.", held,
                                  "; ".join(people) + "." if people else ""]))


def render_race(race, host, by_id, races_by_id, post=False):
    """``r/<raceId>.html``."""
    from .pages import _possessive, state_name

    label = race.get("label") or race["id"]
    year = race.get("year") or ""
    state = race.get("state") or ""
    whose = _possessive(state_name(state))
    return _page(
        host, race_path(race["id"]),
        title=_e(f"{label}, {year} — Know Your Candidate"),
        description=_e(describe_race(race, by_id, races_by_id, post)),
        og_type="website",
        og_title=_e(f"{label}: the {year} race"),
        image=None,
        kind="race",
        heading=_e(f"{label}: the {year} race"),
        body=race_list_html(race, by_id, races_by_id, post),
        view=_e(f"{_state_page(state)}#race-{race['id']}"),
        view_words=_e(f"Open this race on {whose} page"),
        fallback=(f'<a href="{_e(_state_page(state))}">{_e(whose)} page</a> '
                  "lists every race there in plain text."),
    )


def render_all(profiles, races, host, summary=None):
    """``{path relative to the site: html}`` for every profile and race."""
    by_id = {p["id"]: p for p in profiles}
    races = list(races or [])
    races_by_id = {r["id"]: r for r in races}
    post = post_election(summary)
    out = {}
    for person in profiles:
        out[profile_path(person["id"])] = render_profile(person, host, by_id, races_by_id, post)
    for race in races:
        out[race_path(race["id"])] = render_race(race, host, by_id, races_by_id, post)
    return out
