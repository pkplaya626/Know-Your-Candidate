"""A photograph beside each statewide candidate, where one reaches them by
a route tied to the person (rules 24, 33, 87 and 91).

The state pages and Your ballot listed every candidate for governor,
lieutenant governor, attorney general and secretary of state by name only
(rule 91: no portrait). The owner allowed photographs on 2026-10-19, through
these routes, in this order, and no other:

1. **The holder's office photograph** the site already shows, for the
   candidate the list marks as the office's holder - the same person by
   rule 91's holder test (``statewide.holder_status``: surname and given
   name). Built from the caches, at build time.
2. **A member of Congress's own photograph**, by bioguide id, for a member
   an evidenced ``overrides.OTHER_OFFICE_NOMINEES`` entry puts on that
   office's ballot, where the list's name carries the member's surname and
   given name.
3. **An official guide's photograph**: the Arizona Citizens Clean Elections
   Commission's candidate profiles (each ``<li>`` pairs the picture with the
   candidate's name and office) and California's Official Voter Information
   Guide statements (each block pairs an image whose alt text is the name
   with the heading naming them - paired by block, never by nearness: the
   image comes before the heading, and a parser that took the next image
   gave Rob Bonta Michael Gates's face).

   TODO (a follow-up to rule 101's copies, kyc/photocopies.py, which copy
   only a file with an address): the official guides whose photographs
   have no address of their own - Washington's VoteWA (base64 in the
   page), Alaska's statements (encrypted PDFs) and Oregon's pamphlet (JPEG
   2000) - can be shown only from an unmodified copy kept here, which the
   owner allowed on 2026-10-25. They wait for it; they are not ruled out.
4. **The race's own Wikipedia article** (``2026 Colorado gubernatorial
   election``, a title built from the race, never a person), the link it
   gives the candidate - matched on surname *and* given name within that
   one race, never a surname alone (Danielle Ford, Nevada, is not Aaron
   Ford, whose article the race page also links), and never a one-word
   name - and then, as rule 33 does for a ballot page's link, the article
   resolved without a section, a disambiguation or a title that is not
   theirs (``portraits.title_is_about``). The photograph is the race page's
   own infobox image beside the nominee, else the article's lead image,
   read with its Commons licence and author (rule 87); refused when it is
   non-free, landscape, or its file name lacks the surname or says a scene
   or an event ("addresses the United Nations"). Its licence is held to
   rule 82's one test (:func:`licence_doubt`): a file whose page names no
   author, a public-domain tag resting on nothing but an uploader's say-so
   (a "PD-author" or no PD category at all: the checker found Phillip
   Ensler's resting on an email relayed by Ballotpedia), or an uploader's
   own declaration (CC0, "Copyrighted free use", "Attribution") on a file
   that calls itself official, by an author who is not a government office,
   is a doubt, withheld and reported; what a person doubts goes in
   ``overrides.PORTRAIT_LICENCE_DOUBTS``, and what a person looked at and
   found no likeness in ``overrides.NOT_A_PORTRAIT`` - the lists every other
   route asks (``official_photos.held_back``), keyed on the Commons upload.

Weight is rule 87's (the owner's decision of 2026-10-25, which replaced the
brief of 2026-10-19): a size within the caps where the source offers one -
for Commons, one of Wikimedia's standard thumbnail widths (rule 42) - else
the same file smaller from its host's resizer or Photon, else the file as it
is, shown and said (``portraitHeavy``); never left out for its weight. Each
is cached with its page, the words naming the person beside it, the day
read, its bytes and pixel size (``official_photos.record``); a read that
concludes nothing keeps the last one (rule 8), asked again of the lists a
person keeps. A cached photograph reaches the page only while the list
still prints the same name for the same office.
"""

import datetime
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse

from . import official_photos

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "statewide_photos.json")
OFFICES = ("governor", "lt", "ag", "sos")

AZ_LIST = "https://www.azcleanelections.gov/Custom/CandidateList?location="
AZ_BY = "Arizona Citizens Clean Elections Commission"
AZ_OFFICES = {"Governor": "governor", "Lieutenant Governor": "lt",
              "Attorney General": "ag", "Secretary of State": "sos"}
CA_GUIDE = "https://voterguide.sos.ca.gov/candidates/{}-candidate-statements.htm"
CA_PAGES = {"governor": "governor", "lt": "lt-governor", "ag": "attorney-general", "sos": "sos"}
CA_BY = "California Secretary of State, Official Voter Information Guide"


class StatewidePhotoError(RuntimeError):
    pass


def key(code, office, name):
    return f"{code}|{office}|{name}"


# ---------------------------------------------------------------- names

def _fold(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _plain_name(text):
    """A name without a bracketed ticket or nickname: "Angela Harrolle Mohan
    (Hourihan)" is Angela Harrolle Mohan; "Donald P. (Don) Wagner" Donald
    P. Wagner."""
    return " ".join(re.sub(r"\([^)]*\)", " ", html.unescape(str(text or ""))).split())


def same_person(list_name, other):
    """Whether *other* names the list's candidate: their surname and their
    given name (or a short form of it), as rule 91 settles a holder. A
    one-word name settles nothing."""
    from . import statewide
    mine = statewide.display_name(list_name)
    if len(statewide.tokens(_plain_name(mine))) < 2 or len(statewide.tokens(_plain_name(other))) < 2:
        return False
    family = statewide.surname(_plain_name(mine))
    return (statewide.has_surname(family, _plain_name(other))
            and statewide.same_given_name(_plain_name(mine), _plain_name(other)))


def matches(candidates, found_name, ticket=None):
    """The one list candidate *found_name* names, or None: unique both ways.
    *ticket* is a running mate's governor the source names beside them
    ("(Hourihan)"), which must be the candidate's own ticket."""
    from . import statewide
    hits = [c for c in candidates if not c.get("writeIn") and same_person(c["name"], found_name)]
    if len(hits) != 1:
        return None
    hit = hits[0]
    if ticket:
        mate = hit.get("runningMate") or ""
        if not mate or not statewide.has_surname(statewide.surname(ticket), mate):
            return None
    return hit


# ------------------------------------------------------- official guides

def _get(url, timeout=40):
    from .courts import _get as get
    try:
        return get(url, timeout=timeout)
    except Exception as exc:                      # CourtsError or anything else
        raise StatewidePhotoError(f"could not read {url}: {exc}") from exc


def parse_arizona(page):
    """``[(office, name, ticket, picture url, words)]`` from the Clean
    Elections Commission's candidate list: each ``<li>`` of the state
    executive's sections pairs ``/Custom/Picture/<n>`` with ``<b>Name</b>``
    and the office. Picture 0 is the commission's silhouette (it answers
    200), so it is no one's photograph."""
    out = []
    for item in re.findall(r"<li>(.*?)</li>", page or "", re.S):
        pic = re.search(r'<img class="pic" src="(/Custom/Picture/(\d+))"', item)
        name = re.search(r"<b>(.*?)</b>", item, re.S)
        office = re.search(r'<span class="office">(.*?)</span>', item, re.S)
        if not (pic and name and office):
            continue
        office_text = " ".join(html.unescape(office.group(1)).split())
        if office_text not in AZ_OFFICES or pic.group(2) == "0":
            continue
        raw = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", name.group(1))).split())
        ticket = re.search(r"\(([^)]+)\)\s*$", raw)
        party = re.search(r'<span class="party">(.*?)</span>', item, re.S)
        words = (f"the list pairs Picture/{pic.group(2)} with '{raw}', '{office_text}'"
                 + (f", '{' '.join(party.group(1).split())}'" if party else ""))
        out.append((AZ_OFFICES[office_text], _plain_name(raw), ticket.group(1) if ticket else None,
                    urllib.parse.urljoin(AZ_LIST, pic.group(1)), words))
    return out


def parse_california(page, office):
    """``[(office, name, None, image url, words)]`` from one of the guide's
    statement pages: each candidate's block holds one image and one
    heading, "Name | PARTY"; the image is taken only where its alt text is
    the heading's name. "No Photo Submitted" is no photograph."""
    out = []
    blocks = re.split(r'<div class="grid-parent clearfix">', page or "")[1:]
    for block in blocks:
        heads = re.findall(r"<h2>(.*?)</h2>", block, re.S)
        imgs = re.findall(r"<img\b[^>]*>", block, re.I)
        if len(heads) != 1 or len(imgs) != 1:
            continue
        head = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", heads[0])).split())
        name = head.split("|", 1)[0].strip()
        alt = official_photos._attr(imgs[0], "alt")
        src = official_photos._attr(imgs[0], "src")
        if not src or "no-photo" in src or alt.strip().lower() == "no photo submitted":
            continue
        if " ".join(alt.split()) != name:
            continue
        url = urllib.parse.urljoin(CA_GUIDE.format(CA_PAGES[office]), src)
        out.append((office, _plain_name(name), None, url,
                    f"the statement's block pairs the image alt-texted '{alt}' with the heading "
                    f"'{head}'"))
    return out


def read_guides(lists, measure=None, pause=1.0, get=None, refused=None):
    """``(records, problems, unknown)`` for Arizona's and California's
    guides: ``{key: record}`` for each candidate a guide pictures and the
    list names, ``unknown`` the keys a read concluded nothing about."""
    get = get or _get
    measure = measure or official_photos.weigh
    if refused is None:
        from .overrides import NOT_A_PORTRAIT as refused
    records, problems, unknown = {}, [], set()
    sources = []
    if "AZ" in lists:
        try:
            sources.append(("AZ", AZ_LIST, AZ_BY, parse_arizona(get(AZ_LIST))))
        except StatewidePhotoError as exc:
            problems.append(f"AZ: {exc}; the last photographs read are kept")
            unknown.add("AZ")
    if "CA" in lists:
        for office in OFFICES:
            if office not in lists["CA"]:
                continue
            url = CA_GUIDE.format(CA_PAGES[office])
            time.sleep(pause)
            try:
                sources.append(("CA", url, CA_BY, parse_california(get(url), office)))
            except StatewidePhotoError as exc:
                problems.append(f"CA {office}: {exc}; the last photographs read are kept")
                unknown.add(f"CA|{office}")
    for code, page, by, found in sources:
        for office, name, ticket, url, words in found:
            people = (lists.get(code) or {}).get(office) or []
            hit = matches(people, name, ticket)
            if not hit:
                if people:
                    problems.append(f"{code} {office}: the guide pictures {name!r}, whom the list "
                                    "does not name once; not used")
                continue
            time.sleep(pause)
            k = key(code, office, hit["name"])
            if url in refused:
                problems.append(f"{k}: {url} is in overrides.NOT_A_PORTRAIT; not used")
                continue
            chosen, weight, why, heavy = official_photos.choose([(0, url)], measure, widest=1.0)
            if not chosen:
                if why == official_photos.UNKNOWN:
                    unknown.add(k)
                else:
                    problems.append(f"{code} {office}: {hit['name']}'s guide photograph: {why}")
                continue
            records[k] = official_photos.record(chosen, page, f"{by}: {words}", weight,
                                                by=by, route="guide", portraitHeavy=heavy)
    return records, problems, unknown


# ------------------------------------------------------- members by id

def read_members(lists, snapshot, measure=None, pause=1.0):
    """``(records, problems, unknown)`` for members of Congress an
    ``overrides.OTHER_OFFICE_NOMINEES`` entry puts on a statewide ballot:
    their congress.gov portrait, by bioguide id, where the list's name for
    that office is theirs."""
    from .overrides import OTHER_OFFICE_NOMINEES
    from .pages import state_name
    from .photos import HOST_CREDITS, member_photos
    measure = measure or official_photos.weigh
    by_id = {m.get("bioguide"): m for m in (snapshot or {}).get("legislators") or ()}
    records, problems, unknown = {}, [], set()
    titles = {"Governor": "governor", "Lieutenant Governor": "lt", "Attorney General": "ag",
              "Secretary of State": "sos"}
    for bioguide, (what, source, _checked) in sorted(OTHER_OFFICE_NOMINEES.items()):
        member = by_id.get(bioguide)
        found = re.search(r"nominee for (Governor|Lieutenant Governor|Attorney General|"
                          r"Secretary of State) of (?:the )?(.+)$", what)
        if not member or not found:
            continue
        office = titles[found.group(1)]
        code = member.get("state")
        if _fold(state_name(code)).replace("u.s. ", "").replace("united states ", "") != \
                _fold(found.group(2)).replace("u.s. ", "").replace("united states ", ""):
            continue
        people = (lists.get(code) or {}).get(office) or []
        names = [member.get("name") or ""] + [
            f"{member.get('nameParts', {}).get(k)} {member.get('last')}"
            for k in ("first", "nickname") if (member.get("nameParts") or {}).get(k)]
        hits = {c["name"] for c in people if not c.get("writeIn")
                and any(same_person(c["name"], n) for n in names)}
        if len(hits) != 1:
            if people:
                problems.append(f"{code} {office}: {member.get('name')} ({bioguide}) is not named "
                                "once on the list; no photograph")
            continue
        listed = hits.pop()
        url = member_photos(member.get("name"), bioguide)[0]
        time.sleep(pause)
        chosen, weight, why, heavy = official_photos.choose([(0, url)], measure, widest=1.0)
        k = key(code, office, listed)
        if not chosen:
            (unknown.add(k) if why == official_photos.UNKNOWN else
             problems.append(f"{code} {office}: {listed}'s portrait by id: {why}"))
            continue
        host = urllib.parse.urlsplit(url).hostname
        records[k] = official_photos.record(
            chosen, f"https://bioguide.congress.gov/search/bio/{bioguide}",
            f"{member.get('name')} ({bioguide}), whom overrides.OTHER_OFFICE_NOMINEES records as "
            f"{what} ({source}); the list prints '{listed}'. The portrait is the member's by "
            "bioguide id.", weight, by=HOST_CREDITS.get(host, host), route="member",
            bioguide=bioguide, portraitHeavy=heavy)
    return records, problems, unknown


# ---------------------------------------------------------- Wikipedia

def race_titles(code, office):
    """The race's own article titles, built from the race (as
    ``results.page_titles`` builds a House race's), never from a person."""
    from .pages import state_name
    place = state_name(code)
    if code == "VI":
        place = "United States Virgin Islands"
    if office == "governor":
        return [f"2026 {place} gubernatorial election"]
    if office == "lt":
        return [f"2026 {place} lieutenant gubernatorial election",
                f"2026 {place} gubernatorial election"]
    if office == "ag":
        return [f"2026 {place} Attorney General election", f"2026 {place} attorney general election"]
    return [f"2026 {place} Secretary of State election", f"2026 {place} secretary of state election"]


_LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")


def _section(text, heading):
    found = re.search(rf"^(=+)\s*{heading}\s*\1\s*$", text, re.M | re.I)
    if not found:
        return ""
    level = len(found.group(1))
    rest = text[found.end():]
    stop = re.search(r"^={1,%d}[^=].*?={1,%d}\s*$" % (level, level), rest, re.M)
    return rest[:stop.start()] if stop else rest


def templates(text, name):
    """The body of every ``{{name ...}}`` template in *text*, nested
    templates and links kept whole (rule 31: a candidate's piped link or a
    ``{{nowrap|...}}`` inside a row must not end it)."""
    out = []
    for match in re.finditer(r"\{\{\s*" + name, text or "", re.I):
        depth, i = 0, match.start()
        while i < len(text):
            two = text[i:i + 2]
            if two == "{{":
                depth += 1
                i += 2
                continue
            if two == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    out.append(text[match.start() + 2:i - 2])
                    break
                continue
            i += 1
    return out


def _link_of(value):
    link = _LINK.search(value or "")
    if not link:
        return None
    return link.group(1).strip(), (link.group(2) or link.group(1)).strip()


def race_links(text):
    """``[(target, shown, image or None, mate_of or None)]``: the race
    article's candidates as it links them - its infobox nominees with the
    image it sets beside each and their running mates (*mate_of* the
    nominee whose ticket names them), the general election's result rows,
    and the bullets under its nominee and candidate headings (never the
    withdrawn, declined or eliminated)."""
    from .results import template_fields
    out = []
    for body in templates(text, "Infobox election")[:1]:
        fields = template_fields(body)
        for name, value in fields.items():
            number = re.fullmatch(r"nominee(\d+)", name)
            if not number:
                continue
            link = _link_of(value)
            if not link:
                continue
            image = fields.get(f"image{number.group(1)}") or ""
            image = re.sub(r"^\[\[(?:File|Image):([^|\]]+).*$", r"\1", image, flags=re.I).strip()
            image = re.sub(r"^(?:File|Image):", "", image, flags=re.I).strip()
            out.append(link + (image or None, None))
            mate = _link_of(fields.get(f"running_mate{number.group(1)}"))
            if mate:
                out.append(mate + (None, link[1]))
    general = _section(text or "", "General election")
    for body in templates(general, "Election box (?:winning )?candidate"):
        link = _link_of(template_fields(body).get("candidate"))
        if link:
            out.append(link + (None, None))
    heads = list(re.finditer(r"^(=+)\s*([^=\n]+?)\s*\1\s*$", text or "", re.M))
    for i, head in enumerate(heads):
        title = head.group(2).lower()
        if not re.search(r"nominee|declared|qualified|on the ballot|^candidates$", title) \
                or re.search(r"withdr|declin|elimin|potential|publicly|lost", title):
            continue
        body = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        for line in re.findall(r"^\*+\s*(.*)$", body, re.M):
            link = _LINK.match(line.strip())
            if link:
                out.append((link.group(1).strip(), (link.group(2) or link.group(1)).strip(),
                            None, None))
    return out


_SCENE = re.compile(r"\b(?:and|with|at|meeting|rally|ceremony|oath|event|conference|protest|"
                    r"debate|signing|visit|visits|speaks|speaking|group|press|roundtable|hearing|"
                    r"summit|parade|swearing|sworn|inauguration|award|interview|town hall|"
                    r"festival|tour|panel|son|daughter|wife|husband|family|center|pamphlet|"
                    r"page|cup|address|addresses|addressing|remarks|testifies|testifying|"
                    r"delivers|delivering|attends|attending|greets|greeting)\b")
_UPLOADER_PD = re.compile(r"^PD[- ](?:author|user|self)", re.I)


def file_ok(file_title, name):
    """Whether a Commons file's own name may be this candidate's portrait:
    it carries their surname and says no scene ("Lt. Governor Susan
    Bysiewicz at Women's History Month panel ... (cropped)")."""
    from . import statewide
    stem = re.sub(r"^File:", "", file_title or "", flags=re.I).rsplit(".", 1)[0]
    if not statewide.has_surname(statewide.surname(_plain_name(name)), stem.replace("_", " ")):
        return False
    return not _SCENE.search(_fold(stem.replace("_", " ")))


# Licences that are the uploader's own declaration, with no statute or
# government's tag behind them.
_DECLARED = ("cc0", "copyrighted free use", "attribution")
# An author who is a government office or its staff ("Office of the
# Governor of South Carolina", "U.S. House Office of Photography").
_GOVERNMENT = re.compile(r"\b(?:office|government|department|dept|senate|house of|legislature|"
                         r"general assembly|assembly|state of|commonwealth|united states|u\.s\.|"
                         r"us government|ministry|agency|bureau|court|national guard|"
                         r"air force|army|navy|official)\b", re.I)
_CAMPAIGN = re.compile(r"\bfor (?:governor|congress|senate|attorney general|secretary|"
                       r"lieutenant)\b", re.I)


def licence_doubt(credit, file_title):
    """Why rule 82's one test doubts a Commons file's licence, or ``""``:
    its page names no author; it is public domain with no basis recorded
    (:func:`licence_basis`); or it is an uploader's own declaration (CC0,
    "Copyrighted free use", "Attribution") on a file that calls itself
    official, by an author who is not a government office - an official
    portrait claimed as someone's own work (Kris Kobach's "official
    portrait, 2024", CC0 by a user account). Asked at the read and again
    of every cached record at build time."""
    credit = credit or {}
    licence = (credit.get("licence") or "").lower()
    by = " ".join(str(credit.get("by") or "").split())
    if not by:
        return "the file's page names no author"
    if licence.startswith("public domain") and not credit.get("basis"):
        return "public domain on no basis but an uploader's word"
    stem = re.sub(r"^File:", "", urllib.parse.unquote(file_title or ""), flags=re.I)
    if licence in _DECLARED and re.search(r"\bofficial\b", stem.replace("_", " "), re.I) \
            and (not _GOVERNMENT.search(by) or _CAMPAIGN.search(by)):
        return (f"an official portrait under the uploader's own {credit.get('licence')} "
                f"declaration, by {by}")
    return ""


def licence_basis(categories):
    """Why a "Public domain" file is public domain, by its categories: a
    government's or a statute's ("PD US Congress", "PD California"), or
    ``None`` when it rests on an uploader's word ("PD-author") or nothing."""
    pd = [c for c in categories if re.match(r"^(?:Category:)?(?:PD|CC-PD)[- ]", c)]
    good = [c for c in pd if not _UPLOADER_PD.match(re.sub(r"^Category:", "", c))]
    return good[0].removeprefix("Category:") if good else None


def _wiki(params):
    from .portraits import _api
    return _api(params)


def _wikitext(title):
    data = _wiki({"prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": title,
                  "redirects": "1"})
    page = ((data.get("query") or {}).get("pages") or [{}])[0]
    if page.get("missing") or not page.get("revisions"):
        return None, None
    return page["title"], page["revisions"][0]["slots"]["main"]["content"]


def _resolve(title):
    data = _wiki({"titles": title, "redirects": "1", "prop": "pageimages|pageprops",
                  "piprop": "name"})
    query = data.get("query") or {}
    page = (query.get("pages") or [{}])[0]
    redirects = query.get("redirects") or []
    return {"title": page.get("title"), "missing": bool(page.get("missing")),
            "fragment": (redirects[-1].get("tofragment") if redirects else None),
            "image": page.get("pageimage"),
            "disambiguation": "disambiguation" in (page.get("pageprops") or {})}


def _commons(file_name):
    """``{"info", "categories"}`` of a file, from Commons' API."""
    from .portraits import _api
    data = _api({"titles": "File:" + file_name, "prop": "imageinfo|categories",
                 "iiprop": "size|url|extmetadata", "cllimit": "max",
                 "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|AttributionRequired|NonFree"},
                endpoint="https://commons.wikimedia.org/w/api.php")
    page = ((data.get("query") or {}).get("pages") or [{}])[0]
    info = (page.get("imageinfo") or [None])[0]
    return {"info": info, "categories": [c["title"] for c in page.get("categories") or []]}


def ticket_links(office, candidate, links):
    """The links a candidate may be matched among. A running mate is
    matched only where the ticket names them: a lieutenant governor on a
    governor's ticket only among the running mates the article sets beside
    that very governor (``running_mateN`` beside ``nomineeN``); a governor
    never among anyone's running mates."""
    mate = candidate.get("runningMate")
    if office == "lt" and mate:
        return [link for link in links if link[3] and same_person(mate, link[3])]
    return [link for link in links if not link[3]]


def wiki_photo(code, office, candidate, links, race_title, refused=None, measure=None):
    """``(record, why)`` for one candidate through the race's article
    (*links*, :func:`race_links`). *refused* is ``overrides.NOT_A_PORTRAIT``,
    keyed on the Commons upload address."""
    from .portraits import commons_credit, credit_of, thumb_set, title_is_about
    from .statewide import display_name
    measure = measure or official_photos.weigh
    name = candidate["name"]
    hits = {}
    for target, shown, image, _mate in ticket_links(office, candidate, links):
        if same_person(name, shown) or same_person(name, target.split(" (")[0]):
            hits.setdefault(target, image)
            hits[target] = hits[target] or image
    if len(hits) != 1:
        return None, ("ambiguous" if hits else "not-linked")
    target, infobox_image = next(iter(hits.items()))
    article = _resolve(target)
    resolved = article.get("title") or ""
    if article["missing"] or article["fragment"] or article["disambiguation"] \
            or not title_is_about(resolved, _plain_name(display_name(name))) \
            or not same_person(name, resolved.split(" (")[0]):
        return None, "article-not-theirs"
    file_name = infobox_image or article.get("image")
    if not file_name:
        return None, "no-image"
    file_name = urllib.parse.unquote(file_name).replace("_", " ")
    if not file_ok(file_name, display_name(name)):
        return None, "file-name"
    meta = _commons(file_name)
    info = meta["info"]
    if not info or not info.get("width"):
        return None, official_photos.UNKNOWN
    upload = (info.get("url") or "").split("?", 1)[0]
    if refused is None:
        from .overrides import NOT_A_PORTRAIT as refused
    if upload in refused:
        return None, "not-a-portrait"
    credit = credit_of(info)
    if credit.get("nonFree") or not credit.get("licence"):
        return None, "licence"
    basis = None
    if credit["licence"].lower().startswith("public domain"):
        basis = licence_basis(meta["categories"])
        if not basis:
            return None, "public-domain-unsupported"
    if licence_doubt(dict(credit, basis=basis), file_name):
        return None, "licence-doubt"
    if not official_photos.portrait_shaped({"width": info["width"], "height": info["height"]}):
        return None, "shape"
    sizes = [(w, u) for w, u in thumb_set(upload, info["width"])]
    chosen, weight, why, heavy = official_photos.choose(sizes, measure)
    if not chosen:
        return None, why
    page = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(race_title.replace(" ", "_"))
    words = (f"The race's article '{race_title}' links [[{target}]] for the list's '{name}'; "
             f"the article '{resolved}' "
             + ("is the nominee's, and the race's infobox sets File:" + file_name + " beside them"
                if infobox_image else "leads with File:" + file_name))
    return official_photos.record(
        chosen, page, words, weight, by=credit.get("by"), route="wikipedia",
        credit=dict(commons_credit(credit), basis=basis) if basis else commons_credit(credit),
        article=resolved, portraitHeavy=heavy), ""


def read_wikipedia(lists, refused=None, measure=None, log=print):
    """``(records, problems, unknown, misses)`` through each race's own
    article, for every printed candidate of every office listed."""
    records, problems, unknown, misses = {}, [], set(), {}
    for code in sorted(lists):
        for office in OFFICES:
            people = (lists[code] or {}).get(office) or []
            if not people:
                continue
            text = title = None
            try:
                for candidate_title in race_titles(code, office):
                    title, text = _wikitext(candidate_title)
                    if text:
                        break
            except Exception as exc:
                problems.append(f"{code} {office}: the race's article could not be read ({exc})")
                unknown.update(key(code, office, p["name"]) for p in people)
                continue
            if not text:
                continue
            links = race_links(text)
            for person in people:
                if person.get("writeIn"):
                    continue
                k = key(code, office, person["name"])
                try:
                    found, why = wiki_photo(code, office, person, links, title, refused, measure)
                except Exception as exc:
                    found, why = None, official_photos.UNKNOWN
                    problems.append(f"{k}: {exc}")
                if found:
                    records[k] = found
                elif why == official_photos.UNKNOWN:
                    unknown.add(k)
                else:
                    misses[k] = why
            log(f"  {code} {office}: {title}")
    return records, problems, unknown, misses


# -------------------------------------------------------------- the run

def lists_of(statewide_cache):
    """``{code: {office: [candidate]}}`` from the statewide cache."""
    out = {}
    for code, entry in ((statewide_cache or {}).get("states") or {}).items():
        for office, item in ((entry or {}).get("offices") or {}).items():
            out.setdefault(code, {})[office] = list(item.get("candidates") or [])
    return out


def fetch(statewide_cache, snapshot, previous=None, wikipedia=True, log=print):
    """``(cache, problems)``: every route read again. A photograph a read
    concluded nothing about keeps the last one read for the same
    candidate (rule 8)."""
    lists = lists_of(statewide_cache)
    problems = []
    records, more, unknown = read_members(lists, snapshot)
    problems += more
    guides, more, unknown_g = read_guides(lists)
    problems += more
    unknown |= unknown_g
    for k, rec in guides.items():
        records.setdefault(k, rec)
    misses = {}
    if wikipedia:
        wiki, more, unknown_w, misses = read_wikipedia(lists, log=log)
        problems += more
        unknown |= unknown_w
        for k, rec in wiki.items():
            records.setdefault(k, rec)
    before = (previous or {}).get("photos") or {}
    for k, rec in before.items():
        held = k in unknown or k.rsplit("|", 1)[0] in unknown or k.split("|", 1)[0] in unknown
        kept = k not in records and "photo" in rec and (
            held or (not wikipedia and rec.get("route") == "wikipedia"))
        if not kept:
            continue
        # Kept from the last read (rule 8), but asked again of the lists a
        # person keeps and of the licence test: a doubt added since
        # withholds it, whatever this run could read.
        why_held = withheld_why(k, rec)
        if why_held:
            problems.append(f"{k}: the last photograph read is withheld: {why_held}")
            continue
        records[k] = rec
        if held:
            problems.append(f"{k}: could not be read; the last photograph read is kept")
    for k in sorted(records):
        heavy = official_photos.heavy_of(records[k])
        if heavy:
            problems.append(f"{k}: offered only at {heavy['why']} ({heavy['url']}); "
                            + ("shown at full size and said" if heavy["kept"]
                               else "shown smaller from the same file"))
    for k in sorted(set(records) | set(before)):
        was, now = (before.get(k) or {}).get("photo"), (records.get(k) or {}).get("photo")
        if now and was != now:
            problems.append(f"{k}: photograph {'changed' if was else 'added'}: {now} (from "
                            f"{records[k]['page']}); look at it")
    # A photograph that lacks what ties it to the person is never kept: one
    # bad record does not cost the run the rest (rule 8).
    for k in sorted(records):
        unfit = _problems_of({"photos": {k: records[k]}})
        if unfit:
            problems.append(f"{unfit[0]}; not kept")
            del records[k]
    cache = {"read": datetime.date.today().isoformat(),
             "photos": {k: records[k] for k in sorted(records)},
             "misses": {k: misses[k] for k in sorted(misses)}}
    return cache, problems


def counts(cache):
    """``{"shown", "heavy", "withheld", "routes": {route: n}}`` over the
    cache: *heavy* the photographs shown at full size though offered only
    above the caps (rule 87), *withheld* those a person's list or the
    licence test keeps off the page."""
    out = {"shown": 0, "heavy": 0, "withheld": 0, "routes": {}}
    for k, rec in ((cache or {}).get("photos") or {}).items():
        if "photo" not in rec:
            continue
        if withheld_why(k, rec):
            out["withheld"] += 1
            continue
        out["shown"] += 1
        out["heavy"] += bool((official_photos.heavy_of(rec) or {}).get("kept"))
        out["routes"][rec.get("route") or "?"] = out["routes"].get(rec.get("route") or "?", 0) + 1
    return out


def withheld_why(k, rec):
    """Why a cached record must not reach the page, or ``""``: a list a
    person keeps (``official_photos.held_back``), and for a Commons file
    the licence test (:func:`licence_doubt`) and the file-name test
    (:func:`file_ok`), asked of the cache at build time as at the read."""
    held = official_photos.held_back(rec)
    if held:
        return held
    if rec.get("route") == "wikipedia":
        file_title = ((rec.get("credit") or {}).get("page") or "").split("/wiki/File:", 1)[-1]
        file_title = urllib.parse.unquote(file_title).replace("_", " ")
        doubt = licence_doubt(rec.get("credit"), file_title)
        if doubt:
            return f"licence in doubt: {doubt}"
        name = k.split("|", 2)[-1]
        from .statewide import display_name
        if not file_ok(file_title, display_name(name)):
            return f"the file's name ({file_title}) lacks the surname or says a scene"
    return ""


def withheld(cache):
    """``[sentence]``: every cached photograph :func:`withheld_why` keeps
    off the page, for the build to say."""
    return [f"statewide_photos {k}: {withheld_why(k, rec)}"
            for k, rec in sorted(((cache or {}).get("photos") or {}).items())
            if "photo" in rec and withheld_why(k, rec)]


def doubted(cache):
    """The ``PORTRAIT_LICENCE_DOUBTS`` and ``NOT_A_PORTRAIT`` entries a
    cached record stands for: what keeps those entries from reading as
    stale to the judges' and the campaign sites' checks."""
    out = set()
    for rec in ((cache or {}).get("photos") or {}).values():
        out.update(official_photos.addresses(rec))
    return out


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(path + ".tmp", path)
    return path


def problems(cache):
    """Every cached photograph that lacks what a read one carries: an error
    the build stops on (rule 87)."""
    out = []
    for k, rec in sorted(((cache or {}).get("photos") or {}).items()):
        out.extend(official_photos.record_problems(rec, f"statewide_photos {k}"))
        # A Commons file's credit is its licence, its author where the file
        # page names one, and "author not recorded on Commons" where it
        # does not (rule 87); anything else names whose it is in ``by``.
        if not (rec.get("by") or (rec.get("route") == "wikipedia"
                                  and (rec.get("credit") or {}).get("licence"))):
            out.append(f"statewide_photos {k}: the photograph does not say whose it is")
        if rec.get("route") == "wikipedia" and not (rec.get("credit") or {}).get("licence"):
            out.append(f"statewide_photos {k}: a Commons photograph with no recorded licence")
    return out


# The cache check, under a name ``fetch``'s own list of problems does not hide.
_problems_of = problems


# ------------------------------------------------------------- the page

# A holder row the card shows without its photograph: the page draws none
# for it (kyc-stategov.js officerRow), so no candidate row takes one either.
_UNPICTURED = ("unconfirmed", "disputed", "notMember", "unlisted", "vacant", "none")


def holder_photo(office, holder):
    """``(photo, credit)`` the state card shows for the office's holder, or
    ``(None, None)``."""
    if not holder or any(holder.get(k) for k in _UNPICTURED):
        return None, None
    field = "headshot" if office == "governor" else "photo"
    if not holder.get(field):
        return None, None
    by = holder.get(field + "By")
    if not by:
        return None, None
    return holder[field], {"by": by, "page": holder.get(field + "Page") or ""}


def attach(code, office, rows, listed, holder, status, cache):
    """Give each of the page's candidate *rows* (``statewide.for_page``)
    its photograph, in place, by the routes in order: ``photo`` and
    ``photoCredit`` (``KYC.photoCreditHtml``'s shape: whose it is, and the
    page it was read on or the Commons file's licence). *listed* is the
    cache's office entry (its candidates, by the list's own names);
    *holder* the office's holder as the card shows them; *status* the
    holder line ``statewide.holder_status`` settled. A photograph offered
    only above the caps is shown all the same (rule 87); one a person's
    list or the licence test withholds is not (:func:`withheld_why`).
    Returns how many of those shown are at full size though heavy."""
    from .statewide import display_name
    photos = (cache or {}).get("photos") or {}
    by_shown = {}
    for person in (listed or {}).get("candidates") or ():
        by_shown.setdefault(display_name(person["name"]), person["name"])
    heavy = 0
    for row in rows:
        if row.get("writeIn"):
            continue
        name = by_shown.get(row["name"])
        if not name:
            continue
        # 1. The holder's office photograph, for the one candidate the
        # holder line settled as the holder (surname and given name).
        if status and status.get("why") == "listed" and status.get("name") == name:
            photo, credit = holder_photo(office, holder)
            if photo:
                row["photo"], row["photoCredit"] = photo, credit
                continue
        k = key(code, office, name)
        rec = photos.get(k)
        if not rec or "photo" not in rec or _problems_of({"photos": {name: rec}}) \
                or withheld_why(k, rec):
            continue
        heavy += bool((official_photos.heavy_of(rec) or {}).get("kept"))
        row["photo"] = rec["photo"]
        if rec.get("route") == "wikipedia":
            row["photoCredit"] = rec.get("credit")
        else:
            row["photoCredit"] = {"by": rec["by"], "page": rec["page"]}
    return heavy
