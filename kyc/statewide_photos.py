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

   The official guides whose photographs have no address of their own -
   Alaska's statements (PDFs) and Oregon's pamphlet (JPEG 2000 in PDFs) -
   are kept here as copies by the owner's decision of 2026-10-25
   (kyc/guide_photos.py): one is shown for a candidate none of these
   routes pictures, by :func:`attach`.
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
   or an event ("addresses the United Nations"). A lead taken because the
   infobox's image was refused that way waits off the page until a person
   has looked at it (``overrides.SEEN_ARTICLE_LEADS``,
   :func:`awaiting_look`). Its licence is held to
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
from .photos import keep_refusals, refused_urls, withheld_files

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


class OutOfTime(StatewidePhotoError):
    """Nothing new is asked once the read's budget is spent."""


class Budget:
    """A read's time budget (``ballotphotos --max-minutes``, rule 78): once
    it is spent no new race is begun, and every race not reached keeps its
    last read (rule 8). ``Budget(None)`` never runs out."""

    def __init__(self, seconds=None, clock=time.monotonic):
        self.clock = clock
        self.seconds = seconds
        self.end = None if seconds is None else clock() + seconds

    def spent(self):
        return self.end is not None and self.clock() >= self.end


def race_key(code, office):
    """``"MN|sos"``: a race, as the head of each of its candidates' keys."""
    return f"{code}|{office}"


def race_order(lists, races_read=None, offices=OFFICES):
    """``[(code, office)]``: every race with a list, the one read longest
    ago first and a race never read before them all (``racesRead``), so a
    read its budget stops reaches next time what it did not reach this
    time, never the same alphabet's tail left unread week after week."""
    races = [(code, office) for code in sorted(lists) for office in offices
             if (lists[code] or {}).get(office)]
    return sorted(races, key=lambda r: ((races_read or {}).get(race_key(*r)) or "", r))


def once(reader):
    """*reader* asked once per argument for the whole run, its answer or its
    failure remembered: the photographs' read and the candidates' articles'
    read ask for the same race articles and the same linked articles, and
    the second asking cost the Monday read a quarter of its time."""
    answers = {}

    def read(arg):
        if arg not in answers:
            try:
                answers[arg] = (True, reader(arg))
            except Exception as exc:           # remembered, and raised again
                answers[arg] = (False, exc)
        ok, value = answers[arg]
        if not ok:
            raise value
        return value
    read.answered = answers
    return read


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
    200), so it is no one's photograph. A list with no statewide item this
    reader reads - an empty challenge (coag.gov answered a script HTTP 202
    with no body, 2026-11-01), a bot wall, a page drawn by script, a
    redesign - raises: it concludes nothing (rules 8 and 24), never "the
    guide pictures no one", and the last photographs read are kept."""
    out = []
    read = 0
    for item in re.findall(r"<li>(.*?)</li>", page or "", re.S):
        pic = re.search(r'<img class="pic" src="(/Custom/Picture/(\d+))"', item)
        name = re.search(r"<b>(.*?)</b>", item, re.S)
        office = re.search(r'<span class="office">(.*?)</span>', item, re.S)
        if not (pic and name and office):
            continue
        office_text = " ".join(html.unescape(office.group(1)).split())
        if office_text not in AZ_OFFICES:
            continue
        read += 1
        if pic.group(2) == "0":
            continue
        raw = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", name.group(1))).split())
        ticket = re.search(r"\(([^)]+)\)\s*$", raw)
        party = re.search(r'<span class="party">(.*?)</span>', item, re.S)
        words = (f"the list pairs Picture/{pic.group(2)} with '{raw}', '{office_text}'"
                 + (f", '{' '.join(party.group(1).split())}'" if party else ""))
        out.append((AZ_OFFICES[office_text], _plain_name(raw), ticket.group(1) if ticket else None,
                    urllib.parse.urljoin(AZ_LIST, pic.group(1)), words))
    if not read:
        raise StatewidePhotoError(f"{AZ_LIST} holds no statewide candidate this reader reads")
    return out


def parse_california(page, office):
    """``[(office, name, None, image url, words)]`` from one of the guide's
    statement pages: each candidate's block holds one image and one
    heading, "Name | PARTY"; the image is taken only where its alt text is
    the heading's name. "No Photo Submitted" is no photograph, but a block
    read. A page with no block this reader reads raises, as Arizona's list
    does (:func:`parse_arizona`)."""
    out = []
    read = 0
    blocks = re.split(r'<div class="grid-parent clearfix">', page or "")[1:]
    for block in blocks:
        heads = re.findall(r"<h2>(.*?)</h2>", block, re.S)
        imgs = re.findall(r"<img\b[^>]*>", block, re.I)
        if len(heads) != 1 or len(imgs) != 1:
            continue
        read += 1
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
    if not read:
        raise StatewidePhotoError(f"{CA_GUIDE.format(CA_PAGES[office])} holds no candidate's "
                                  "statement this reader reads")
    return out


def read_guides(lists, measure=None, pause=1.0, get=None, refused=None, passed_over=None):
    """``(records, problems, unknown)`` for Arizona's and California's
    guides: ``{key: record}`` for each candidate a guide pictures and the
    list names, ``unknown`` the keys a read concluded nothing about. A file
    a person refused (``photos.not_a_portrait``; *refused* stands in for
    ``overrides.NOT_A_PORTRAIT`` in a test) is appended to *passed_over*."""
    from .photos import not_a_portrait
    get = get or _get
    measure = measure or official_photos.weigh
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
            if not_a_portrait(url, passed_over=_bucket(passed_over, k), table=refused):
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


def _bucket(passed_over, k):
    """Where a refusal for the race key *k* is recorded: its own list in a
    ``{key: [url]}`` (what :func:`fetch` keeps, so a read that concludes
    nothing can keep it), or *passed_over* itself when it is a list."""
    return passed_over.setdefault(k, []) if isinstance(passed_over, dict) else passed_over


# ------------------------------------------------------- members by id

def read_members(lists, snapshot, measure=None, pause=1.0):
    """``(records, problems, unknown)`` for members of Congress an
    ``overrides.OTHER_OFFICE_NOMINEES`` entry puts on a statewide ballot:
    their congress.gov portrait, by bioguide id, where the list's name for
    that office is theirs."""
    from .overrides import OTHER_OFFICE_NOMINEES
    from .pages import short_name
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
        if _fold(short_name(code)).replace("u.s. ", "").replace("united states ", "") != \
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
    from .results import title_name
    place = title_name(code)             # the name a title gives the place: one helper (rule 12)
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


def _page_of(data, title):
    """The one page of an API reply about *title*. A reply that holds none
    - an error body sent with HTTP 200, a maintenance notice - is a failed
    read (rule 8), never "there is no such article": read as a finding, it
    dropped a race's photographs and dated the race as read whole (the
    PR #213 review)."""
    pages = ((data or {}).get("query") or {}).get("pages") if isinstance(data, dict) else None
    if not pages or not isinstance(pages[0], dict):
        raise StatewidePhotoError(f"the API's reply about '{title}' holds no page")
    return pages[0]


def _wikitext(title):
    data = _wiki({"prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": title,
                  "redirects": "1"})
    page = _page_of(data, title)
    if page.get("missing"):
        return None, None
    if not page.get("title") or not page.get("revisions"):
        # Neither missing nor an article with its text: nothing was said.
        raise StatewidePhotoError(f"the API's reply about '{title}' holds no text and does "
                                  "not say the article is missing")
    return page["title"], page["revisions"][0]["slots"]["main"]["content"]


def _resolve(title):
    data = _wiki({"titles": title, "redirects": "1", "prop": "pageimages|pageprops",
                  "piprop": "name"})
    page = _page_of(data, title)
    if not page.get("title") and not page.get("missing"):
        raise StatewidePhotoError(f"the API's reply about '{title}' names no article and does "
                                  "not say it is missing")
    query = data.get("query") or {}
    redirects = query.get("redirects") or []
    return {"title": page.get("title"), "missing": bool(page.get("missing")),
            "fragment": (redirects[-1].get("tofragment") if redirects else None),
            "image": page.get("pageimage"),
            "disambiguation": "disambiguation" in (page.get("pageprops") or {})}


def _commons(file_name):
    """``{"info", "categories"}`` of a file, from Commons' API."""
    from .portraits import _CREDIT_FIELDS, IIPROP, _api
    data = _api({"titles": "File:" + file_name, "prop": "imageinfo|categories",
                 "iiprop": IIPROP, "cllimit": "max",
                 "iiextmetadatafilter": _CREDIT_FIELDS},
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


def name_forms(code, office, name):
    """The short forms an evidenced ``overrides.STATEWIDE_NAME_FORMS`` entry
    records for this very list name ("Joe Lombardo" for "Lombardo,
    Joseph"; rule 91), never one guessed."""
    from . import overrides
    return [holder for (where, key, holder), (form, _evidence)
            in sorted(overrides.STATEWIDE_NAME_FORMS.items())
            if where == code and key == office and form == name]


def linked_article(office, candidate, links, resolve=None, code=None):
    """``((target, infobox image, resolved article), "")`` for the one
    article the race's article links for *candidate*, checked as rule 33
    checks a ballot page's link (it resolves, is no section, list or
    disambiguation, and its title carries their name); else ``(None, why)``:
    "not-linked" (the race's article links none for them), "ambiguous", or
    "article-not-theirs"."""
    from .portraits import title_is_about
    from .statewide import display_name
    resolve = resolve or _resolve
    name = candidate["name"]
    # The list's name, and a short form an evidenced entry records for it:
    # Nevada's article links [[Joe Lombardo]] for the list's "Lombardo,
    # Joseph" (PR #195's second review).
    names = [name] + (name_forms(code, office, name) if code else [])
    hits = {}
    for target, shown, image, _mate in ticket_links(office, candidate, links):
        if any(same_person(n, shown) or same_person(n, target.split(" (")[0]) for n in names):
            hits.setdefault(target, image)
            hits[target] = hits[target] or image
    if len(hits) != 1:
        return None, ("ambiguous" if hits else "not-linked")
    target, infobox_image = next(iter(hits.items()))
    article = resolve(target)
    resolved = article.get("title") or ""
    if article["missing"] or article["fragment"] or article["disambiguation"] \
            or not title_is_about(resolved, _plain_name(display_name(name))) \
            or not any(same_person(n, resolved.split(" (")[0]) for n in names):
        return None, "article-not-theirs"
    return (target, infobox_image, article), ""


# The offices whose candidates' own articles the overlay shows (rule 91):
# the governor's, whatever route pictures them.
ARTICLE_OFFICES = ("governor",)


def within(resolve, budget):
    """*resolve*, asking nothing new once *budget* is spent: an article this
    run has already read (:func:`once`) costs nothing and is given; any
    other raises, so its candidate concludes nothing and keeps their last
    read (rule 8). A race begun inside the budget once ran to its end
    whatever it cost (the PR #213 review)."""
    if budget is None:
        return resolve

    def ask(target):
        if budget.spent() and target not in getattr(resolve, "answered", {}):
            raise OutOfTime("the time budget is spent")
        return resolve(target)
    return ask


def article_days(cache, lists, offices=ARTICLE_OFFICES):
    """``{race key: day}``: the oldest day any of a race's candidates'
    article records was read (a kept record carries its own day, the rest
    the read's), for :func:`race_order`. A race with a candidate no record
    is held for has no day, and is read first."""
    cache = cache or {}
    held, out = cache.get("articles") or {}, {}
    for code, office in race_order(lists, offices=offices):
        days = [(held.get(key(code, office, p["name"])) or {}).get("read")
                or (cache.get("articlesRead")
                    if key(code, office, p["name"]) in held else None)
                for p in (lists[code] or {}).get(office) or () if not p.get("writeIn")]
        if days and all(days):
            out[race_key(code, office)] = min(days)
    return out


def read_articles(lists, offices=ARTICLE_OFFICES, wikitext=None, resolve=None, log=print,
                  budget=None, unreached=None, races_read=None):
    """``(articles, unknown)``: for every printed candidate for *offices*,
    what the race's own article links for them, recorded whether or not it
    gives a photograph: ``{"article": title, "page": race article}`` where
    it links one that is theirs (:func:`linked_article`), else ``{"none":
    why, "page": ...}``. A race whose article could not be read, or has
    none, records nothing: this site did not look (rule 19), and the last
    read is kept by the caller (rule 8). Once *budget* is spent no race is
    begun, and no article asked for inside one (:func:`within`): its
    candidates are *unknown* too, and the race is added to *unreached*.
    The race read longest ago comes first (*races_read*,
    :func:`article_days`), so a budget that runs out never leaves the same
    tail unread each time."""
    wikitext = wikitext or _wikitext
    resolve = within(resolve or _resolve, budget)
    log = log or (lambda line: None)
    articles, unknown = {}, set()
    asked = getattr(wikitext, "answered", {})
    for code, office in race_order(lists, races_read, offices=offices):
        people = (lists[code] or {}).get(office) or []
        # A race whose article this run has already read costs nothing more.
        if budget is not None and budget.spent() and race_titles(code, office)[0] not in asked:
            unknown.update(key(code, office, p["name"]) for p in people)
            if unreached is not None and race_key(code, office) not in unreached:
                unreached.append(race_key(code, office))
            continue
        text = title = None
        try:
            for candidate_title in race_titles(code, office):
                title, text = wikitext(candidate_title)
                if text:
                    break
        except Exception as exc:
            log(f"  {code} {office}: the race's article could not be read ({exc})")
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
                found, why = linked_article(office, person, links, resolve=resolve,
                                            code=code)
            except OutOfTime:
                unknown.add(k)
                if unreached is not None and race_key(code, office) not in unreached:
                    unreached.append(race_key(code, office))
                continue
            except Exception:
                unknown.add(k)
                continue
            articles[k] = ({"article": found[2]["title"], "page": title} if found
                           else {"none": why, "page": title})
    return articles, unknown


def kept_articles(now, before, unknown, before_read=None):
    """This read's articles, and the last read's for every candidate it
    concluded nothing about (rule 8), sorted. A kept one carries the day it
    was read (*before_read*, the last read's ``articlesRead``), so a read
    that reached only some races dates none it did not reach as today's."""
    out = dict(now)
    for k, rec in (before or {}).items():
        if k not in out and k in unknown:
            out[k] = dict(rec, read=rec.get("read") or before_read) if before_read else rec
    return {k: out[k] for k in sorted(out)}


def with_articles(cache, lists, previous=None, log=print, **readers):
    """*cache* with the candidates' own articles read again
    (:func:`read_articles`), the last read's kept where this one concluded
    nothing. The whole of ``ballotphotos --articles-only``."""
    readers.setdefault("races_read", article_days(previous, lists))
    now, unknown = read_articles(lists, log=log, **readers)
    out = dict(cache)
    out["articles"] = kept_articles(now, (previous or {}).get("articles"), unknown,
                                    (previous or {}).get("articlesRead") if now else None)
    out["articlesRead"] = (datetime.date.today().isoformat() if now
                           else (previous or {}).get("articlesRead"))
    return out


def article_of(cache, code, office, name):
    """What the cache records of the race's article's link to *name*:
    ``{"article": title, ...}``, ``{"none": why, ...}``, or ``None`` where
    nothing was read (rule 19). The photograph's own record stands in for
    a cache read before articles were recorded."""
    k = key(code, office, name)
    rec = ((cache or {}).get("articles") or {}).get(k)
    if rec:
        return dict(rec, read=rec.get("read") or (cache or {}).get("articlesRead"))
    photo = ((cache or {}).get("photos") or {}).get(k) or {}
    if photo.get("route") == "wikipedia" and photo.get("article"):
        return {"article": photo["article"], "read": photo.get("read") or (cache or {}).get("read")}
    return None


# Why a file a person's list withholds was not taken: no other file of the
# race's article is asked in its place.
LISTED_DOUBT = "licence-doubt-listed"
PERSONS_REFUSALS = ("not-a-portrait", LISTED_DOUBT)


def upload_of(file_name):
    """The Commons upload address of a file by its name alone, as a
    person's lists key it ("(cropped)", never "%28cropped%29"): no request
    is made."""
    page = "https://commons.wikimedia.org/wiki/File:" + str(file_name or "").replace(" ", "_")
    return official_photos.commons_upload({"credit": {"page": page}})


def listed(forms, refused=None, passed_over=None, doubted=None):
    """Why a person's lists withhold the file at *forms* (its upload
    address, in every form it is written), or ``""``: ``"not-a-portrait"``
    (``overrides.NOT_A_PORTRAIT``; *refused* stands in for it in a test) or
    ``LISTED_DOUBT`` (``PORTRAIT_LICENCE_DOUBTS``), the refusal recorded in
    *passed_over* or *doubted* for validate's staleness check."""
    from .photos import not_a_portrait, withheld_files
    forms = [u for u in forms if u]
    if not_a_portrait(*forms, passed_over=passed_over, table=refused):
        return "not-a-portrait"
    if withheld_files(forms, passed_over, doubted):
        return LISTED_DOUBT
    return ""


def wiki_photo(code, office, candidate, links, race_title, refused=None, measure=None,
               passed_over=None, resolve=None, doubted=None, last=None):
    """``(record, why)`` for one candidate through the race's article
    (*links*, :func:`race_links`). *refused* is ``overrides.NOT_A_PORTRAIT``,
    keyed on the Commons upload address; a file a person's lists withhold
    is appended to *passed_over* (``NOT_A_PORTRAIT``) or *doubted*
    (``PORTRAIT_LICENCE_DOUBTS``). *last* is the candidate's record from
    the last read, which a size that could not be read never moves to
    another width of the same file (:func:`_commons_photo`).

    The race's infobox image beside the nominee comes before the article's
    lead (rule 91); a file refused for what it is - its name says a scene
    or lacks the surname, its licence, its shape - gives way to the other.
    Ned Lamont's race article set a bridge visit with a Cabinet secretary
    beside him on 2026-11-09, over his own article's official portrait. A
    lead that comes forward this way says what it stands in place of
    (``inPlaceOf``) and waits off the page for a person's look
    (:func:`awaiting_look`): nobody has seen it, and the refresh publishes
    without a person (the PR #213 review). A file a person's list withholds
    gives way to nothing (rule 38) - the lists are asked before the file's
    name is, by the upload address its name gives, so a refused file whose
    name also says a scene still promotes nothing and is still recorded as
    refused - and nor does one that concludes nothing (Commons did not
    answer, a size could not be weighed): the last photograph read is kept
    (rule 8)."""
    from .statewide import display_name
    name = candidate["name"]
    found, why = linked_article(office, candidate, links, resolve=resolve, code=code)
    if not found:
        return None, why
    target, infobox_image, article = found
    resolved = article.get("title") or ""
    files = []
    for raw, from_infobox in ((infobox_image, True), (article.get("image"), False)):
        if raw:
            file_name = urllib.parse.unquote(raw).replace("_", " ")
            if file_name not in [f for f, _ in files]:
                files.append((file_name, from_infobox))
    if not files:
        return None, "no-image"
    passed = []                               # [(file, why)] refused for what it is
    for file_name, from_infobox in files:
        # A person's refusal promotes nothing unseen (rule 38: refusing
        # James Talarico's crop brought forward its uncropped file): Mayes
        # Middleton's refused crop would have given way to the uncropped
        # Gage Skidmore photograph it was cut from.
        why = listed([upload_of(file_name)], refused, passed_over, doubted)
        if why:
            return None, why
        if not file_ok(file_name, display_name(name)):
            passed.append((file_name, "file-name"))
            continue
        rec, why = _commons_photo(file_name, refused, measure, passed_over, doubted, last)
        if why == official_photos.UNKNOWN or why in PERSONS_REFUSALS:
            return None, why
        if not rec:
            passed.append((file_name, why))
            continue
        page = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(race_title.replace(" ", "_"))
        words = (f"The race's article '{race_title}' links [[{target}]] for the list's '{name}'; "
                 f"the article '{resolved}' "
                 + ("is the nominee's, and the race's infobox sets File:" + file_name
                    + " beside them" if from_infobox else "leads with File:" + file_name))
        chosen, weight, credit, heavy, size = rec
        stands_for = None
        if passed:
            words += (f"; taken in place of File:{passed[0][0]}, which the race's infobox sets "
                      f"beside them and this reader refused ({passed[0][1]})")
            stands_for = dict(size, file=passed[0][0], why=passed[0][1])
        return official_photos.record(
            chosen, page, words, weight, by=credit.get("by"), route="wikipedia",
            credit=credit, article=resolved, portraitHeavy=heavy, inPlaceOf=stands_for), ""
    return None, passed[0][1] if passed else ""


def _commons_photo(file_name, refused=None, measure=None, passed_over=None, doubted=None,
                   last=None):
    """``((url, weight, credit, heavy, size), "")`` for one Commons file
    named by a race's article, *size* the file's own pixel size, else
    ``(None, why)``."""
    from .portraits import commons_credit, credit_of, thumb_set
    measure = measure or official_photos.weigh
    meta = _commons(file_name)
    info = meta["info"]
    if not info or not info.get("width"):
        return None, official_photos.UNKNOWN
    upload = (info.get("url") or "").split("?", 1)[0]
    # The API writes the upload address percent-encoded ("%28cropped%29");
    # a person's lists, and the build's test of a record (``held_back``),
    # key it as its file page reads ("(cropped)"). Asked by the API's form
    # alone, Mayes Middleton's and JoCasta Zamarripa's refused files, and
    # three files whose licence a person doubts, were taken on every
    # Monday's read and dropped again on Tuesday's (2026-11-09).
    canonical = official_photos.commons_upload(
        {"credit": {"page": info.get("descriptionurl") or ""}})
    forms = [u for u in (upload, canonical) if u]
    why = listed(forms, refused, passed_over, doubted)
    if why:
        return None, why
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
    # A size Wikimedia did not answer for (a 429) is not passed over for
    # the next while the candidate's last record is of this very file: the
    # read of 2026-11-09 moved eleven photographs to another width of the
    # same file, Lisa Demuth's to 120px, on transient refusals. A file new
    # to the candidate has no width to keep, and a width guards no fact
    # about a person (rule 87): it is taken at whichever size answers, or
    # Brett Lindstrom's new lead image waited a week behind the crop his
    # article no longer shows (the PR #213 review).
    same_file = bool(last) and official_photos.commons_upload(last) in forms
    chosen, weight, why, heavy = official_photos.choose(sizes, measure, strict=same_file)
    if not chosen:
        return None, why
    shown = dated_credit(dict(commons_credit(credit), basis=basis) if basis
                         else commons_credit(credit), credit)
    return (chosen, weight, shown, heavy,
            {"width": info["width"], "height": info["height"]}), ""


def dated_credit(shown, credit):
    """*shown*, a Commons credit as the page prints it, with the year the
    file's own page dates it to (``portraits.year_of``), or
    ``yearUnstated`` where it gives no single one plainly, and the reading
    that dated it (``yearForm``, ``portraits.CREDIT_FORM``) - so it is not
    asked again until the reading changes, and no year is guessed."""
    from .portraits import CREDIT_FORM
    shown = {k: v for k, v in shown.items() if k not in ("year", "yearUnstated", "yearForm")}
    if (credit or {}).get("year"):
        shown["year"] = credit["year"]
    else:
        shown["yearUnstated"] = True
    shown["yearForm"] = CREDIT_FORM
    return shown


def date_credits(cache, info_of=None, log=print):
    """Give each Commons record in *cache* whose credit has not been dated
    by the current reading (``portraits.CREDIT_FORM``: the third took
    upload dates and estimates as years) the year its file's page gives,
    in place; returns how many were read. A file the read does not answer
    for is asked again next run (rule 8)."""
    from .portraits import CREDIT_FORM, credit_of, file_info
    info_of = info_of or file_info
    todo = {k: rec for k, rec in ((cache or {}).get("photos") or {}).items()
            if rec.get("route") == "wikipedia" and official_photos.commons_upload(rec)
            and (rec.get("credit") or {}).get("yearForm") != CREDIT_FORM}
    if not todo:
        return 0
    infos = info_of([official_photos.commons_upload(rec) for rec in todo.values()])
    done = 0
    for rec in todo.values():
        info = infos.get(official_photos.commons_upload(rec))
        if info:
            rec["credit"] = dated_credit(rec["credit"], credit_of(info))
            done += 1
    if log:
        log(f"  statewide photographs: {done} of {len(todo)} Commons credits dated")
    return done


def read_wikipedia(lists, refused=None, measure=None, log=print, passed_over=None,
                   budget=None, races_read=None, progress=None, wikitext=None, resolve=None,
                   doubted=None, before=None):
    """``(records, problems, unknown, misses)`` through each race's own
    article, for every printed candidate of every office listed, the race
    read longest ago first (:func:`race_order`). Once *budget* is spent no
    race is begun, and no candidate inside one: a race begun inside the
    budget once ran to its end whatever it cost, fifteen candidates of
    Tennessee's at six tries a request (the PR #213 review). *progress*, a
    dict, is given ``"read"`` (``{race key: day}`` for each race this read
    concluded about whole), ``"unreached"`` (the race keys it did not
    begin), ``"cut"`` (the candidates of a race begun whom the budget did
    not reach, who keep their last read and leave the race undated, so it
    comes first next time) and ``"inconclusive"`` (the candidates a read
    concluded nothing about). *before* is the last read's ``{key: record}``
    (:func:`wiki_photo`'s *last*)."""
    wikitext = wikitext or _wikitext
    log = log or (lambda line: None)
    records, problems, unknown, misses = {}, [], set(), {}
    progress = {} if progress is None else progress
    done, unreached = progress.setdefault("read", {}), progress.setdefault("unreached", [])
    cut, inconclusive = progress.setdefault("cut", []), progress.setdefault("inconclusive", [])
    today = datetime.date.today().isoformat()
    for code, office in race_order(lists, races_read):
        people = (lists[code] or {}).get(office) or []
        if budget is not None and budget.spent():
            unreached.append(race_key(code, office))
            continue
        text = title = None
        try:
            for candidate_title in race_titles(code, office):
                title, text = wikitext(candidate_title)
                if text:
                    break
        except Exception as exc:
            problems.append(f"{code} {office}: the race's article could not be read ({exc})")
            unknown.update(key(code, office, p["name"]) for p in people)
            continue
        if not text:
            done[race_key(code, office)] = today
            continue
        links = race_links(text)
        whole = True
        for person in people:
            if person.get("writeIn"):
                continue
            k = key(code, office, person["name"])
            if budget is not None and budget.spent():
                cut.append(k)
                unknown.add(k)
                whole = False
                continue
            try:
                found, why = wiki_photo(code, office, person, links, title, refused, measure,
                                        passed_over=_bucket(passed_over, k), resolve=resolve,
                                        doubted=_bucket(doubted, k), last=(before or {}).get(k))
            except Exception as exc:
                found, why = None, official_photos.UNKNOWN
                problems.append(f"{k}: {exc}")
            if found:
                records[k] = found
            elif why == official_photos.UNKNOWN:
                unknown.add(k)
                inconclusive.append(k)
                whole = False
            else:
                misses[k] = why
        if whole:
            done[race_key(code, office)] = today
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


def fetch(statewide_cache, snapshot, previous=None, wikipedia=True, log=print, budget=None):
    """``(cache, problems)``: every route read again. A photograph a read
    concluded nothing about keeps the last one read for the same
    candidate (rule 8), and so does every race the races' articles' read
    did not reach before *budget* (:class:`Budget`) was spent: the
    Monday read once ran past its step's limit and its output, buffered,
    was lost with it (2026-11-09)."""
    lists = lists_of(statewide_cache)
    problems = []
    # One asking per article for the whole run: the candidates' articles'
    # read asks for the governors' race articles the photographs' read has
    # just read.
    wikitext, resolve = once(_wikitext), once(_resolve)
    progress = {}
    records, more, unknown = read_members(lists, snapshot)
    problems += more
    # What a person refused (photos.not_a_portrait), kept in the cache by
    # race so validate can tell a NOT_A_PORTRAIT entry still means
    # something, and a race this run concluded nothing about keeps it.
    passed_over, doubts = {}, {}
    guides, more, unknown_g = read_guides(lists, passed_over=passed_over)
    problems += more
    unknown |= unknown_g
    for k, rec in guides.items():
        records.setdefault(k, rec)
    misses = {}
    before = (previous or {}).get("photos") or {}
    if wikipedia:
        wiki, more, unknown_w, misses = read_wikipedia(
            lists, log=log, passed_over=passed_over, doubted=doubts, budget=budget,
            races_read=(previous or {}).get("racesRead"), progress=progress,
            wikitext=wikitext, resolve=resolve, before=before)
        problems += more
        unknown |= unknown_w
        for k, rec in wiki.items():
            records.setdefault(k, rec)
    unreached = set(progress.get("unreached") or ())
    if unreached:
        problems.append(f"the races' articles: {len(unreached)} race(s) not reached within the "
                        f"time budget, their last read kept: {', '.join(sorted(unreached))}")
    cut = set(progress.get("cut") or ())
    if cut:
        problems.append(f"the races' articles: the time budget ran out inside "
                        f"{len({k.rsplit('|', 1)[0] for k in cut})} race(s); {len(cut)} "
                        f"candidate(s) keep their last read, and the race is read first next "
                        f"time: {', '.join(sorted(cut))}")

    def concluded_nothing(k):
        return k in unknown or k.rsplit("|", 1)[0] in unknown or k.split("|", 1)[0] in unknown

    def skipped(k):
        # The races' articles were not read for this candidate: not read
        # at all (--no-wikipedia), or not reached before the budget ran out.
        return not wikipedia or k.rsplit("|", 1)[0] in unreached

    for k, rec in before.items():
        held = concluded_nothing(k)
        kept = k not in records and "photo" in rec and (
            held or (skipped(k) and rec.get("route") == "wikipedia"))
        if not kept:
            continue
        # Kept from the last read (rule 8), but asked again of the lists a
        # person keeps and of the licence test: a doubt added since
        # withholds it, whatever this run could read. A file a person's list
        # withholds is recorded as passed over, as a read refusing it would
        # (the refresh of 2026-10-27 dropped Mayes Middleton's and JoCasta
        # Zamarripa's, and their entries read as stale).
        # (A lead that waits for a person's look is not refused: it is
        # kept, and waits.)
        why_held = withheld_why(k, rec, looks=False)
        if why_held:
            withheld_files(official_photos.addresses(rec), passed_over.setdefault(k, []),
                           doubts.setdefault(k, []))
            problems.append(f"{k}: the last photograph read is withheld: {why_held}")
            continue
        records[k] = rec
        if held and k not in cut:
            problems.append(f"{k}: could not be read; the last photograph read is kept")
    # Everyone a read concluded nothing about is said, kept or not: a
    # candidate with no earlier photograph who read unknown was named
    # nowhere (the PR #213 review).
    for k in sorted(set(progress.get("inconclusive") or ())):
        if k not in records:
            problems.append(f"{k}: could not be read, and no photograph is kept from an "
                            "earlier read; asked again next run")
    for k in sorted(records):
        heavy = official_photos.heavy_of(records[k])
        if heavy:
            problems.append(f"{k}: offered only at {heavy['why']} ({heavy['url']}); "
                            + ("shown at full size and said" if heavy["kept"]
                               else "shown smaller from the same file"))
    for k in sorted(set(records) | set(before)):
        was, now = (before.get(k) or {}).get("photo"), (records.get(k) or {}).get("photo")
        if now and was != now:
            waits = awaiting_look(k, records[k])
            problems.append(f"{k}: photograph {'changed' if was else 'added'}: {now} (from "
                            f"{records[k]['page']}); look at it"
                            + (f". Not shown yet: {waits}" if waits else ""))
    # A photograph that lacks what ties it to the person is never kept: one
    # bad record does not cost the run the rest (rule 8).
    for k in sorted(records):
        unfit = _problems_of({"photos": {k: records[k]}})
        if unfit:
            problems.append(f"{unfit[0]}; not kept")
            del records[k]
    # A record kept from a read before credits carried a year is dated.
    date_credits({"photos": records}, log=log)
    # A race this run concluded nothing about - its read failed, or the
    # races' articles were not read (--no-wikipedia) - keeps what its last
    # good read refused and why it found none (rule 8): Heather Baxter's
    # refused Commons file left the cache on a day the articles went unread.
    def unread(k):
        return concluded_nothing(k) or skipped(k)

    for k, why in ((previous or {}).get("misses") or {}).items():
        if unread(k) and k not in records and k not in misses:
            misses[k] = why
    cache = {"read": datetime.date.today().isoformat(),
             "photos": {k: records[k] for k in sorted(records)},
             "misses": {k: misses[k] for k in sorted(misses)}}
    # When each race's article was last read whole, so the next read whose
    # budget runs out begins with the races this one did not reach.
    races_read = dict((previous or {}).get("racesRead") or {})
    races_read.update(progress.get("read") or {})
    if races_read:
        cache["racesRead"] = {k: races_read[k] for k in sorted(races_read)}
    # The candidates' own articles, whatever route pictures them.
    if wikipedia:
        late = []
        cache = with_articles(cache, lists, previous, log=log, wikitext=wikitext,
                              resolve=resolve, budget=budget, unreached=late)
        if late:
            problems.append(f"the candidates' own articles: {len(late)} race(s) not reached "
                            f"within the time budget, their last read kept: {', '.join(late)}")
    elif (previous or {}).get("articles"):
        cache["articles"] = previous["articles"]
        cache["articlesRead"] = previous.get("articlesRead")
    whole = wikipedia and not unknown and not unreached
    for field, now in (("notPortraits", passed_over), ("licenceDoubts", doubts)):
        kept = keep_refusals(now, (previous or {}).get(field), unread, whole)
        if kept:
            cache[field] = kept
    return cache, problems


def counts(cache):
    """``{"shown", "heavy", "withheld", "waiting", "routes": {route: n}}``
    over the cache: *heavy* the photographs shown at full size though
    offered only above the caps (rule 87), *withheld* those a person's list
    or the licence test keeps off the page, *waiting* those that wait for a
    person's look (:func:`awaiting_look`)."""
    out = {"shown": 0, "heavy": 0, "withheld": 0, "waiting": 0, "routes": {}}
    for k, rec in ((cache or {}).get("photos") or {}).items():
        if "photo" not in rec:
            continue
        if withheld_why(k, rec, looks=False):
            out["withheld"] += 1
            continue
        if awaiting_look(k, rec):
            out["waiting"] += 1
            continue
        out["shown"] += 1
        out["heavy"] += bool((official_photos.heavy_of(rec) or {}).get("kept"))
        out["routes"][rec.get("route") or "?"] = out["routes"].get(rec.get("route") or "?", 0) + 1
    return out


def awaiting_look(k, rec):
    """Why a record waits off the page for a person's look, or ``""``: it
    is an article's lead image that came forward when this reader refused
    the image the race's infobox sets beside the nominee (``inPlaceOf``),
    and no ``overrides.SEEN_ARTICLE_LEADS`` entry records a look at this
    very file for this very candidate. The refresh publishes without a
    person, and nobody had seen Wes Moore's or Bruce Blakeman's when the
    first read with this fallback would have shown them (the PR #213
    review); a first-name campaign portrait waits the same way (rule 38).
    The look is at a picture, not an address: an entry made for a file of
    another pixel size is not this file's."""
    from . import overrides
    stands_for = (rec or {}).get("inPlaceOf")
    if not stands_for:
        return ""
    upload = official_photos.commons_upload(rec)
    look = getattr(overrides, "SEEN_ARTICLE_LEADS", {}).get(upload)
    size = {"width": stands_for.get("width"), "height": stands_for.get("height")}
    if look and look[1] == k and look[3] == size:
        return ""
    return (f"the article's lead image, taken in place of File:{stands_for.get('file')} "
            f"({stands_for.get('why')}), waits for a person's look: record {upload} in "
            "overrides.SEEN_ARTICLE_LEADS (the candidate alone, the face measured) or "
            "NOT_A_PORTRAIT")


def stale_looks(cache):
    """``[sentence]``: every ``overrides.SEEN_ARTICLE_LEADS`` entry whose
    race the cache has read again since the look and whose candidate it no
    longer pictures with that file in another's place - an entry that
    guards nothing. An entry made before the read that brings the file is
    not stale: the race has not been read since."""
    from . import overrides
    cache = cache or {}
    out = []
    for upload, look in sorted(getattr(overrides, "SEEN_ARTICLE_LEADS", {}).items()):
        day, k = look[0], look[1]
        read = (cache.get("racesRead") or {}).get(k.rsplit("|", 1)[0]) or ""
        rec = (cache.get("photos") or {}).get(k) or {}
        if read > day and not (rec.get("inPlaceOf")
                               and official_photos.commons_upload(rec) == upload):
            out.append(f"statewide_photos {k}: overrides.SEEN_ARTICLE_LEADS records a look at "
                       f"{upload}, which the race's article, read again on {read}, no longer "
                       "brings forward in another file's place")
    return out


def withheld_why(k, rec, looks=True):
    """Why a cached record must not reach the page, or ``""``: a list a
    person keeps (``official_photos.held_back``), and for a Commons file
    the licence test (:func:`licence_doubt`) and the file-name test
    (:func:`file_ok`), asked of the cache at build time as at the read;
    and, with *looks*, a lead image that came forward in a refused file's
    place and waits for a person's look (:func:`awaiting_look`) - which is
    no refusal, so the read keeps such a record while it waits."""
    return _refused_why(k, rec) or (awaiting_look(k, rec) if looks else "")


def _refused_why(k, rec):
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
    stale to the judges' and the campaign sites' checks. The refusals are
    ``{race key: [url]}``, or the flat list a cache wrote before."""
    cache = cache or {}
    out = refused_urls(cache.get("notPortraits")) | refused_urls(cache.get("licenceDoubts"))
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


def attach(code, office, rows, listed, holder, status, cache, guides=None, manifest=None):
    """Give each of the page's candidate *rows* (``statewide.for_page``)
    its photograph, in place, by the routes in order: ``photo`` and
    ``photoCredit`` (``KYC.photoCreditHtml``'s shape: whose it is, and the
    page it was read on or the Commons file's licence). *listed* is the
    cache's office entry (its candidates, by the list's own names);
    *holder* the office's holder as the card shows them; *status* the
    holder line ``statewide.holder_status`` settled. A photograph offered
    only above the caps is shown all the same (rule 87); one a person's
    list or the licence test withholds is not (:func:`withheld_why`).
    A candidate none of these routes pictures is given the election
    office's own guide's photograph, hosted here unmodified, where *guides*
    (``kyc/guide_photos.py``'s cache) joins one to them (the owner's
    decision of 2026-10-25). Returns how many of those shown are at full
    size though heavy."""
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
            if guides:
                from . import guide_photos
                found = guide_photos.for_row(guides, code, office, dict(row, printed=name),
                                             manifest)
                if found:
                    row["photo"], row["photoCredit"] = found["photo"], guide_photos.credit(found)
            continue
        heavy += bool((official_photos.heavy_of(rec) or {}).get("kept"))
        row["photo"] = rec["photo"]
        if rec.get("route") == "wikipedia":
            row["photoCredit"] = rec.get("credit")
        else:
            row["photoCredit"] = {"by": rec["by"], "page": rec["page"]}
    return heavy
