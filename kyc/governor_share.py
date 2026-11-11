"""Share pages for the governors and the candidates for governor (rule 96).

The governor cards open an overlay (``assets/kyc-governor.js``) behind a
fragment - ``states/<st>.html#/official/gov-<ST>`` for the sitting
governor, ``#/official/gov-<ST>-<name>`` for a candidate on the election
office's list - which every crawler drops: a shared governor unfurled as the
home page's card. So the build writes one small page for each, beside the
federal officials' (kyc/official_share.py): ``o/gov-<ST>.html`` and
``o/gov-<ST>-<name>.html``, with its own title, description, canonical
address and image, the facts in plain text, and a link to the overlay, which
``assets/kyc-share.js`` follows at once for a reader with scripts.

A governor is never a profile (rule 27): these pages carry no profile id and
count nobody in Congress.

The words are the overlay's own, from one table (``shareWords`` in
kyc-governor.js; :func:`share_words` here): the render suite compares the two
for every governor and every candidate (``testGovernorSharePages``) and asks
every case in ``tests/fixtures/governor_share_words.json`` of the page code.
A candidate's page holds the list's words alone - name, party, running mate,
the name the ballot prints - with the list cited and dated, and from the day
after Election Day it is in the past tense beside the state's results, naming
no winner (rule 91).

The image is a photograph only by a route the overlay shows it by: the
NGA's headshot of the governor with its credit, or a candidate's photograph
by the routes rule 91 names (``kyc/statewide_photos.py``) with its credit -
the smaller copy made here of a heavy one, and a file an election office's
guide gives no address of its own (rule 101), at its absolute address on the
site's one hostname (rule 21). A write-in's card shows none, and nor does
their page.

Nothing here is dated by the build, and an unchanged page is not rewritten
(``emit.write_state_pages``).
"""

import json
import os
import re

from .official_share import OFFICIAL_DIR, credit_html, date_words, official_path
from .share import _e, _https, _page

ID = re.compile(r"^gov-([A-Z]{2})(?:-(.+))?$")

WORDS_TABLE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                           "governor_share_words.json")

# The keys of the words table, every one "" where the overlay says none.
KEYS = ("kind", "office", "seeking", "party", "since", "mark", "holder", "status", "printed",
        "ballotName", "surnameOnly", "runningMate", "term", "record", "past", "results",
        "source")

# The overlay's words for what this site does not read after the election
# (rule 91: names no winner).
PAST = "This site does not read the state’s results and names no winner"
RECORD = {"holder": "The sitting governor: see their record ›",
          "member": "A member of Congress: see their profile ›",
          # stategov's memberFormer: the membership snapshot no longer seats them.
          "former": "A former member of Congress: see their profile ›"}


def is_governor_id(oid):
    """Whether *oid* is a governor's or a candidate's for governor."""
    return bool(ID.match(str(oid or "")))


# ----------------------------------------------------------------- words

def governor_of(code):
    """``KYC.stategov.governorOf``: "Governor of Georgia"."""
    from .pages import governor_of as words

    return words(code)


def office_item(state):
    """The ballot table's entry for the governor (``ballotOf(code).offices
    .governor``), or None."""
    return (((state or {}).get("ballot2026") or {}).get("offices") or {}).get("governor")


def mark_words(item, post):
    """``textOf(KYC.stategov.officeMark(code, "governor"))``: the office's
    ballot mark, and when it is next elected where it is not on this one."""
    if not item:
        return ""
    if item.get("up"):
        return "This office " + ("was" if post else "is") + " on the Nov 3, 2026 ballot"
    selection = item.get("selection")
    elected = selection in ("elected", "elected-jointly-with-governor")
    text = ("Not elected in 2026" if elected
            else "Appointed, not elected" if selection == "appointed"
            else "Chosen by the legislature, not elected" if selection == "chosen-by-legislature"
            else "No such office")
    nxt = item.get("next")
    if elected and nxt:
        text += " " + (f"Next election: {nxt['month']}" if nxt.get("month")
                       else "Next elected: November") + f" {nxt.get('year')}"
    return text


def mark_html(item, post):
    """The mark as markup, linked to the record that says so, as the
    overlay links it (``ballotMark``, ``nextMark``)."""
    if not item:
        return ""
    words = mark_words(item, post)
    nxt = item.get("next") if not item.get("up") else None
    head = words
    tail = ""
    if nxt and item.get("selection") in ("elected", "elected-jointly-with-governor"):
        head, _, rest = words.partition(" Next ")
        rest = "Next " + rest
        tail = (f' <a href="{_e(nxt.get("source"))}" target="_blank" rel="noopener noreferrer">'
                f"{_e(rest)}</a>") if _https(nxt.get("source")) else " " + _e(rest)
    first = (f'<a href="{_e(item.get("source"))}" target="_blank" rel="noopener noreferrer">'
             f"{_e(head)}</a>") if _https(item.get("source")) else _e(head)
    return first + tail


def holder_words(item, post):
    """``textOf(KYC.stategov.openSeat(code, "governor"))``: whether the
    holder is on the list, as a cited source says (rule 79); "" after the
    election, when the office has a winner."""
    status = (item or {}).get("holderStatus") if (item or {}).get("up") else None
    if not status or post:
        return ""
    text = status.get("text") or ""
    if status.get("why") == "unchecked":
        return text + "."
    lead = "" if status.get("why") == "listed" else "Open seat: "
    then = status.get("then")
    more = f" and {then.get('text')} ({then.get('cite')})" if then else ""
    return f"{lead}{text} ({status.get('cite')}){more}."


def holder_html(item, post):
    """The holder line as markup (``pages._holder_line``)."""
    if not holder_words(item, post):
        return ""
    from .pages import _holder_line

    return _holder_line(item.get("holderStatus"))


def term_words(item, post):
    """``termLength``: "Term 4 years (if elected)" where the ballot
    table's note opens with a term's length ("4-year term"), else "": the
    label and a value repeating it read "Term 4-year term"."""
    if not item or not item.get("up"):
        return ""
    match = re.match(r"^(\d+)-year term(?=[;,.]|$)", str(item.get("note") or ""))
    if not match:
        return ""
    years = match.group(1) + (" year" if match.group(1) == "1" else " years")
    return f"Term {years}" + ("" if post else " (if elected)")


def badge_words(person, post):
    """``textOf(KYC.stategov.candidateBadge(person))``."""
    if person.get("writeIn"):
        return "Was a write-in candidate" if post else "Write-in candidate"
    return "Was on the Nov 3, 2026 ballot" if post else "On the Nov 3, 2026 ballot"


def share_words(found, post=False, sources=None, results=None):
    """``shareWords``: every word the overlay's head and footer give
    *found* (``{"kind": "governor"|"candidate", "code", "person", "state"}``),
    each "" where it says none. *post*: the day after Election Day or later;
    *sources*: data/stategov.js's ``sources``; *results*: the state's
    results page (``KYC.meta().voting[code].results``)."""
    code = found["code"]
    person = found["person"]
    item = office_item(found.get("state"))
    out = dict.fromkeys(KEYS, "")
    if post and item and item.get("up"):
        out["past"] = PAST
        out["results"] = results or ""
    if found["kind"] == "governor":
        out["kind"] = "Governor"
        out["office"] = governor_of(code)
        out["party"] = person.get("party") or ""
        out["since"] = f"In office since {person['since']}" if person.get("since") else ""
        out["mark"] = mark_words(item, post)
        out["holder"] = holder_words(item, post)
        nga = (sources or {}).get("nga") or []
        out["source"] = ("Governor: " + (nga[0] if nga else "National Governors Association")
                         + (f", read {date_words(nga[2])}" if len(nga) > 2 and nga[2] else "") + ".")
        return out
    listed = (item or {}).get("candidates") or {}
    out["kind"] = "Governor (Candidate)"
    out["seeking"] = "Ran for" if post else "Running for"
    out["office"] = f"Governor • {code}"
    out["party"] = person.get("party") or ""
    out["status"] = badge_words(person, post)
    out["printed"] = f"The list prints: {person['printed']}" if person.get("printed") else ""
    out["ballotName"] = (f"Printed on the ballot as “{person['ballotName']}”"
                         if person.get("ballotName") else "")
    out["surnameOnly"] = "The list gives a surname only." if person.get("surnameOnly") else ""
    out["runningMate"] = (f"{person['runningMate']} for lieutenant governor"
                          if person.get("runningMate") else "")
    out["term"] = term_words(item, post)
    out["record"] = RECORD["holder"] if person.get("holder") else (
        (RECORD["former"] if person.get("memberFormer") else RECORD["member"])
        if person.get("member") else "")
    named = list_for(listed, person)
    out["source"] = f"Source: {named.get('source')} (read {date_words(named.get('read'))})."
    return out


def list_for(listed, person):
    """``listFor``: the document that names *person*. A write-in's is the
    office's list of write-ins where it keeps one apart (``writeIns``,
    statewide.py), never the printed list that does not hold their name
    (rules 19, 91; PR #180 review); everyone else's is the list."""
    listed = listed or {}
    more = listed.get("writeIns") or {}
    return more if (person or {}).get("writeIn") and more.get("source") else listed


# --------------------------------------------------------- who is shared

def governors(stategov):
    """``{id: {"kind", "code", "person", "state"}}``: everyone the overlay
    answers to (``find`` in kyc-governor.js): each sitting governor, and
    each candidate on the election office's list for an office on the
    ballot, write-ins with them. A state with no governor listed answers
    for none."""
    out = {}
    for code, state in sorted(((stategov or {}).get("states") or {}).items()):
        gov = (state or {}).get("governor")
        if not gov or gov.get("id") != f"gov-{code}":
            continue
        out[gov["id"]] = {"kind": "governor", "code": code, "person": gov, "state": state}
        item = office_item(state) or {}
        if not item.get("up"):
            continue
        for person in ((item.get("candidates") or {}).get("candidates") or []):
            pid = person.get("id")
            match = ID.match(str(pid or ""))
            if match and match.group(1) == code and match.group(2):
                out.setdefault(pid, {"kind": "candidate", "code": code, "person": person,
                                     "state": state})
    return out


def ids(stategov):
    """Every governor's and candidate's share page id, for the sitemap."""
    return list(governors(stategov))


# --------------------------------------------------------------- picture

def picture(found, host=None):
    """``(image URL, credit)`` for *found*'s share page, or ``(None, None)``
    for the site's card. Only what the overlay shows (``setPortrait``, which
    asks ``KYC.stategov.cardPhoto``): a photograph with its credit, as the
    smaller copy made here where there is one (``KYC.copyCredit``), and a
    file hosted here at its absolute address on *host* (rules 21, 101)."""
    from .photocopies import is_hosted

    person = found["person"]
    if found["kind"] == "governor":
        url = person.get("headshot") or ""
        credit = ({"by": person["headshotBy"], "page": person.get("headshotPage")}
                  if person.get("headshotBy") else None)
    else:
        url = "" if person.get("writeIn") else person.get("photo") or ""
        credit = person.get("photoCredit")
    if not url or not credit or not (credit.get("by") or credit.get("licence") or credit.get("host")):
        return None, None
    credit = dict(credit)
    copy = person.get("photoCopy") or {}
    if copy.get("src") and copy.get("of") == url:
        if not host:
            return None, None
        credit["copyOf"] = url
        if copy.get("ofBytes"):
            credit["copyOfBytes"] = copy["ofBytes"]
        return f"https://{host}/{copy['src']}", credit
    if is_hosted(url):
        return (f"https://{host}/{url}", credit) if host else (None, None)
    if not _https(url) or "Special:" in url:
        return None, None
    return url, credit


# ----------------------------------------------------------------- pages

def describe(found, words):
    """``(og title, description)``: the name and the words of the overlay's
    head (:func:`share_words`), and nothing of its own but the office in
    words where the overlay writes "Governor • GA" (a bullet read as a
    glitch in an unfurl, as ``share.seat_phrase`` says)."""
    name = found["person"].get("name") or ""
    party = f" ({words['party']})" if words["party"] else ""

    def sentence(*parts):
        return " ".join(f"{p}" if p.endswith(".") else f"{p}." for p in parts if p)

    if found["kind"] == "governor":
        # The mark's two parts ("Not elected in 2026", "Next elected:
        # November 2029") are two sentences here: run together they read as
        # a glitch in an unfurl (PR #180 review). The overlay keeps its words.
        mark, _, nxt = words["mark"].partition(" Next ")
        # After Election Day an office that was on the ballot says, as the
        # overlay does, that this site names no winner: without it the
        # unfurl's "This office was on the Nov 3, 2026 ballot" beside a
        # sitting governor's name left the result to be guessed (the
        # integration of PR #180 on results-day data).
        return name, sentence(f"{name}{party}, {words['office']}", words["since"], mark,
                              "Next " + nxt if nxt else "", words["past"])
    office = governor_of(found["code"])
    seat = office[0].lower() + office[1:]
    mate = f", with {found['person']['runningMate']} for lieutenant governor" if words["runningMate"] else ""
    return name, sentence(f"{name}{party}: {words['seeking'].lower()} {seat}{mate}", words["status"],
                          words["past"])


def _link(href, text):
    if not _https(href):
        return _e(text)
    return f'<a href="{_e(href)}" target="_blank" rel="noopener noreferrer">{_e(text)}</a>'


def _view(found, oid):
    """``(the overlay's address, its link's words, what a reader without
    scripts can read instead)``: the state page, whose plain text names the
    governor and lists the race's candidates (``pages.governor_static``)."""
    from .pages import state_name

    code = found["code"]
    page = f"../states/{code.lower()}.html"
    place = state_name(code)
    if found["kind"] == "governor":
        return (f"{page}#/official/{oid}", f"Open the governor’s record on {place}’s page",
                f'<a href="{_e(page)}#governor">{_e(place)}’s page</a> names the governor in plain text.')
    return (f"{page}#/official/{oid}", f"Open their record on {place}’s page",
            f'<a href="{_e(page)}#governor-race">{_e(place)}’s page</a> lists the election office’s '
            "candidates for governor in plain text.")


def render_governor(oid, found, host, post=False, sources=None, results=None):
    """``o/<id>.html`` for a governor or a candidate for governor."""
    words = share_words(found, post, sources, results)
    person = found["person"]
    name = person.get("name") or ""
    og_title, description = describe(found, words)
    image, credit = picture(found, host)
    item = office_item(found.get("state"))
    body = [f'<p class="share-kind">{_e(words["kind"])}</p>']
    if found["kind"] == "governor":
        body.append(f'<p class="share-office"><strong>{_e(words["office"])}</strong></p>')
    else:
        body.append(f'<p class="share-office">{_e(words["seeking"])} '
                    f'<strong>{_e(words["office"])}</strong></p>')
    if words["party"]:
        body.append(f'<p class="share-party">{_e(words["party"])}</p>')
    if words["since"]:
        body.append(f'<p class="share-since">{_e(words["since"])}</p>')
    if words["mark"]:
        body.append(f'<p class="share-mark">{mark_html(item, post)}</p>')
    if words["holder"]:
        body.append(f'<p class="share-holder">{holder_html(item, post)}</p>')
    if words["status"]:
        body.append(f'<p class="share-status"><strong>{_e(words["status"])}</strong></p>')
    for key, cls in (("printed", "share-printed"), ("ballotName", "share-ballot-name"),
                     ("surnameOnly", "share-surname-only"), ("term", "share-term")):
        if words[key]:
            body.append(f'<p class="{cls}">{_e(words[key])}</p>')
    if words["runningMate"]:
        body.append(f'<p class="share-mate">Running mate: {_e(words["runningMate"])}</p>')
    if words["record"]:
        target = (official_path(f"gov-{found['code']}") if person.get("holder")
                  else f"p/{person.get('member')}.html")
        body.append(f'<p class="share-record"><a href="../{_e(target)}">{_e(words["record"])}</a></p>')
    if words["past"]:
        body.append(f'<p class="share-past">{_e(words["past"])}'
                    + (f": {_link(words['results'], 'the official results')}" if words["results"] else "")
                    + ".</p>")
    if image:
        body.append(f'<p class="share-photo-credit faint">{credit_html(credit, host)}</p>')
    if found["kind"] == "governor":
        nga = (sources or {}).get("nga") or []
        source = _e(words["source"])
        if len(nga) > 1 and nga[0] and _https(nga[1]):
            source = source.replace(_e(nga[0]), _link(nga[1], nga[0]), 1)
    else:
        listed = list_for((item or {}).get("candidates"), person)
        source = _e(words["source"])
        if listed.get("source") and _https(listed.get("url")):
            source = source.replace(_e(listed["source"]), _link(listed["url"], listed["source"]), 1)
    body.append(f'<p class="share-source faint">{source}</p>')
    view, view_words, fallback = _view(found, oid)
    return _page(
        host, official_path(oid),
        title=_e(f"{name} — Know Your Candidate"),
        description=_e(description),
        og_type="profile",
        og_title=_e(og_title),
        image=image,
        image_alt=f"Portrait of {name}",
        kind="governor",
        heading=_e(name),
        body="\n".join(body),
        view=_e(view),
        view_words=_e(view_words),
        fallback=fallback,
    )


def render_all(stategov, host, summary=None):
    """``{path relative to the site: html}`` for every governor and
    candidate, or ``{}`` without data/stategov.js. Written for the day the
    results were read (``share.post_election``), as the profiles' are."""
    if not stategov:
        return {}
    from .share import post_election

    post = bool(post_election(summary))
    sources = stategov.get("sources") or {}
    voting = (summary or {}).get("voting") or {}
    return {official_path(oid): render_governor(oid, found, host, post, sources,
                                                (voting.get(found["code"]) or {}).get("results"))
            for oid, found in governors(stategov).items()}


# ------------------------------------------------- every case, both sides

def words_table():
    """Every case of :func:`share_words`, with its answer, on both sides of
    Election Day: what the render suite asks ``KYC.governor.shareWords``
    about, row by row (``[post, code, kind, person, state, sources, results,
    words]``), each case's state laid into the page's data for the asking."""
    sources = {"nga": ["National Governors Association, current governors",
                       "https://www.nga.org/governors/", "2026-11-02"]}
    listed = {"url": "https://sos.example.gov/list.pdf", "source": "the Secretary of State’s list",
              "read": "2026-10-18", "certified": False}
    governor = {"id": "gov-GA", "name": "A B", "party": "Republican", "partyKey": "R",
                "since": "January 14, 2019", "profile": "https://www.nga.org/governors/georgia/"}
    status = {"holder": "A B", "source": "https://sos.example.gov/list.pdf", "cite": "the list",
              "why": "not-listed", "text": "A B is not among the candidates for this office"}
    items = [
        {"selection": "elected", "up": True, "note": "4-year term; term begins 01/2027",
         "source": "https://sos.example.gov/offices", "holderStatus": status},
        {"selection": "elected", "up": True, "note": "open seat (term-limited)",
         "source": "https://sos.example.gov/offices",
         "holderStatus": dict(status, why="listed", text="A B is among the candidates for this office")},
        {"selection": "elected", "up": True, "note": "4-year term",
         "source": "https://sos.example.gov/offices",
         "holderStatus": dict(status, why="unchecked", text="Whether A B is running was not checked")},
        {"selection": "elected", "up": True, "note": "2-year term.",
         "source": "https://sos.example.gov/offices",
         "holderStatus": dict(status, then={"text": "the constitution limits the governor to two terms",
                                            "source": "https://law.example.gov/", "cite": "Art. V"})},
        {"selection": "elected", "up": False, "source": "https://sos.example.gov/offices",
         "next": {"year": 2029, "source": "https://law.example.gov/"}},
        {"selection": "elected", "up": False, "source": "https://sos.example.gov/offices",
         "next": {"year": 2027, "month": "October", "source": "https://law.example.gov/"}},
        {"selection": "elected", "up": False, "source": "https://sos.example.gov/offices"},
        None,
    ]
    people = [
        {"id": "gov-GA-c-d", "name": "C D", "party": "Democratic"},
        {"id": "gov-GA-e-f", "name": "E F", "writeIn": True},
        {"id": "gov-GA-g", "name": "G", "surnameOnly": True, "party": "Libertarian",
         "printed": "G"},
        {"id": "gov-GA-h-i", "name": "H I", "party": "Republican; Conservative",
         "printed": "I, H", "ballotName": "Hank I", "runningMate": "J K"},
        {"id": "gov-GA-a-b", "name": "A B", "party": "Republican", "holder": True},
        {"id": "gov-GA-l-m", "name": "L M", "party": "Democratic", "member": "M000001"},
        # One the membership snapshot no longer seats (stategov's memberFormer).
        {"id": "gov-GA-n-o", "name": "N O", "party": "Republican", "member": "O000001",
         "memberFormer": True},
    ]
    cases = []
    for post in (False, True):
        for results in ("https://results.example.gov/", None):
            for item in items:
                state = {"governor": governor}
                if item:
                    state["ballot2026"] = {"offices": {"governor": dict(item, candidates=dict(
                        listed, candidates=people)) if item.get("up") else item}}
                for g_sources in (sources, {}):
                    cases.append((post, "GA", "governor", governor, state, g_sources, results))
                if item and item.get("up"):
                    for person in people:
                        cases.append((post, "GA", "candidate", person, state, sources, results))
            # A list that keeps its write-ins in a document of their own
            # (Georgia's, Maine's): a write-in cites that one (PR #180 review).
            apart = dict(listed, candidates=people, writeIns={
                "url": "https://sos.example.gov/writeins.pdf", "by": "the Secretary of State",
                "read": "2026-10-28", "source": "the Secretary of State’s list of certified write-in candidates"})
            state = {"governor": governor,
                     "ballot2026": {"offices": {"governor": dict(items[0], candidates=apart)}}}
            for person in people[:2]:
                cases.append((post, "GA", "candidate", person, state, sources, results))
            # A governor without a date of office or a party.
            bare = dict(governor, since=None, party=None)
            cases.append((post, "GA", "governor", bare, {"governor": bare}, sources, results))
    out = []
    for post, code, kind, person, state, src, results in cases:
        found = {"kind": kind, "code": code, "person": person, "state": state}
        out.append([post, code, kind, person, state, src, results,
                    share_words(found, post, src, results)])
    return {"cases": out}


def words_table_text():
    return json.dumps(words_table(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write_words_table(path=WORDS_TABLE):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(words_table_text())
    return path


__all__ = ["OFFICIAL_DIR", "governors", "ids", "is_governor_id", "picture", "render_all",
           "render_governor", "share_words", "words_table"]
