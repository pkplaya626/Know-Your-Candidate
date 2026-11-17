"""Who appears on this site in more than one role, joined by ids (rule 105).

A person can be on several cards here: Amy Klobuchar's profile as a senator
and her card on Minnesota's list for governor; Janet Mills's card as
Maine's governor and her profile as a candidate for the Senate; J.D. Vance's
row among the members who left this Congress and his dialog as Vice
President; Peggy Flanagan's line as Minnesota's lieutenant governor and her
profile as the state's Senate nominee. Each card was drawn from its own
source and said nothing of the others, so a reader on one did not learn of
the rest (the owner's request of 2026-11-15).

So every card built here is a *node*, and two nodes are one person only by:

- an id both records hold - a bioguide id (a member's profile, a departed
  member's row, the ``member`` an evidenced ``overrides.OTHER_OFFICE_NOMINEES``
  entry puts on a candidate for governor, the id congress-legislators gives
  for the record's own Wikidata item in the history cache), a Wikidata item
  (the item a record's corroborated offices were read from, a governor's
  item the NGA cross-check holds, a departed member's from
  legislators-historical, a judge's from the FJC id it carries), or an FEC
  candidate id - and only where their names agree as well
  (:func:`names_agree`): an id whose two records name two people is withheld
  and warned (``identity-names-disagree``), never shown;
- two sources about an office no id ties: a state officer's card (its
  association's roster, checked against the office's own site, rule 56)
  and a person's corroborated record of offices (rule 69) holding that very
  office open in that state, with the card's name naming them by rule 56's
  test (:func:`office_names`);
- a state legislator found by rule 24's legislature join
  (``nominee_photos.legislator_for``: the chamber their article's
  corroborated record gives, the same first and last name, nobody else of
  that name in it), the one test (rule 12).

A name alone joins nobody (rules 3, 17, 25): two records of one name in one
state that no id or second source ties are reported
(``identity-look-alike``) and link nothing.

Each node's role is written in its own card's words (:func:`role_words`),
in both tenses where the card has two (``after``: from the day after
Election Day, read on the reader's clock by ``KYC.alsoHtml``), with the
address that opens that card (``href``, from the site's root), the view it
opens on a page that draws it (``view``) and its share page (``share``).
Nothing here makes anyone a profile (rule 27) or changes any count (rule
73): the roles are written onto records the pages already draw, as
``also``, and each card keeps its own sources, words and photograph.
"""

import re
import unicodedata

KINDS = ("profile", "departed", "official", "judge", "governor", "candidate",
         "officer", "legislator")
OFFICER_KEYS = ("lt", "ag", "sos")
# The words of the office in a record's corroborated offices (rule 69), by
# the officer card's key: "Lieutenant Governor of Illinois", "Texas
# Attorney General", "Secretary of State of Maine".
OFFICE_WORDS = {
    "lt": re.compile(r"\blieutenant governor\b", re.I),
    "ag": re.compile(r"\battorney general\b", re.I),
    "sos": re.compile(r"\bsecretary of (?:state|the commonwealth)\b", re.I),
}
_NOT_THE_OFFICE = re.compile(r"\b(?:deputy|assistant|acting|united states|u\.s\.)\b", re.I)
_SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
BIOGUIDE = re.compile(r"^[A-Z]\d{6}$")
BIOGUIDE_URL = "https://bioguide.congress.gov/search/bio/{}"
ELECTION = "Nov 3, 2026"


# --------------------------------------------------------------- names

def _words(name):
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    text = re.sub(r'"[^"]*"|\([^)]*\)', " ", text)
    text = re.sub(r"[.'’]", "", text.lower())
    return [w for w in re.findall(r"[a-z]+", text) if w not in _SUFFIX]


def _collapse(words):
    """Initials run together, one word: "J. D." is "jd", as "JD" is."""
    out = []
    for word in words:
        if len(word) == 1 and out and out[-1][1]:
            out[-1] = (out[-1][0] + word, True)
        else:
            out.append((word, len(word) == 1))
    return [w for w, _initials in out]


def _forms(names):
    """``(firsts, givens, surnames)`` of every form a record writes its
    person's name in (its name, its sourced aliases, the FEC's filed name):
    each form's first given name, every given name (initials run together
    count, a lone initial does not) and every surname word (a hyphenated
    surname's parts as well as the whole)."""
    from .candidates import display_name
    from .results import _tokens

    firsts, givens, surnames = set(), set(), set()
    for name in names:
        name = str(name or "")
        if not name.strip():
            continue
        if "," in name:
            # The FEC's "LAST, FIRST" and a list's "Lombardo, Joseph".
            last, first = name.split(",", 1)
            name = display_name(name) if name.upper() == name else f"{first.strip()} {last.strip()}"
        words = _tokens(name)
        if len(words) < 2:
            continue
        last = words[-1]
        surnames.add(last.replace("-", ""))
        surnames.update(p for p in last.split("-") if len(p) > 1)
        given = [w for w in _collapse(words[:-1]) if len(w) > 1]
        if given:
            firsts.add(given[0])
            givens.update(given)
    return firsts, givens, surnames


def names_agree(a, b):
    """Whether two records an id ties name one person (a check on a join by
    id, never a join itself; rule 82: an id is not proof on its own): a
    surname in common, and the first given name of one form among the given
    names of the other, as ``nominee_photos.given_fits`` asks of an item's
    label - "Janet Trafton Mills" and "Janet Mills", "J.D. Vance" and "JD
    Vance", "Tom Tiffany" and the member whose sourced aliases hold "Tom
    Tiffany". No nickname table and no initial alone: "John James" and
    "Jane James" sharing an item, a spouse's or a namesake's, name two
    people. *a* and *b* are a name or a list of the forms a record writes."""
    fa, ga, sa = _forms(a if isinstance(a, (list, tuple)) else [a])
    fb, gb, sb = _forms(b if isinstance(b, (list, tuple)) else [b])
    if not (sa & sb):
        return False
    return bool(fa & gb or fb & ga)


def look_alike(a, b):
    """The same first and last name, folded: two records a reader would take
    for one person, which only an id or a second source may join. Rule 24's
    test, the one (``nominee_photos.same_name``, rule 12)."""
    from .nominee_photos import same_name

    return same_name(a, b)


def office_names(person_name, officer_name):
    """Whether the officer card's name names *person_name* by rule 56's test
    (``officers.names_holder``): their first and last name, up to two middle
    words between, beside the office's title - the card's title and name
    are that text. A different first name is no match."""
    from .officers import names_holder

    return names_holder(person_name, "attorney general " + str(officer_name or ""), "ag")


# --------------------------------------------------------------- nodes

class Node:
    """One card: its *kind*, the record the page draws it from (*record*,
    where ``also`` is written), its ids and its role."""

    __slots__ = ("key", "kind", "name", "state", "record", "ids", "role", "photo",
                 "place", "history", "forms")

    def __init__(self, key, kind, name, state, record, role, photo=False, history=None):
        self.key, self.kind, self.name, self.state = key, kind, name, state
        self.record, self.role, self.photo = record, role, bool(photo)
        self.ids = {"bioguide": set(), "wikidata": set(), "fec": set()}
        self.history = history or {}
        # Every form the record's own sources write the name in: the card's
        # name, a member's aliases from congress-legislators' name block
        # (rule 66), the FEC's filed name.
        self.forms = [name] + [a for a in (record or {}).get("aliases") or [] if a] +             ([record["filedName"]] if (record or {}).get("filedName") else [])

    def add(self, scheme, value):
        if value:
            self.ids[scheme].add(str(value))


def _cap(text):
    return text[:1].upper() + text[1:] if text else text


def _history_rows(record):
    return ((record or {}).get("politicalHistory") or {}).get("rows") or []


def _wikidata(record):
    return ((record or {}).get("politicalHistory") or {}).get("wikidata")


def profile_role(person, by_id, races_by_id, post):
    """A profile's words, as its own card and dialog say them (rule 96): the
    seat in words and where they stand (``share``'s mirror of KYC.standing,
    held to it by the status table), in the campaign's tense and after
    Election Day (``post``, the results day)."""
    from . import share
    from .record import seated

    def lead_of(when):
        label = person.get("officeLabel")
        parts = share._seat_parts(label)
        if parts and person.get("isCandidate"):
            body, where = parts
            if str(label).endswith("-AL"):
                # An at-large seat in rule 96's seat words, as every sentence
                # writes it: "the U.S. House in WY-AL", and the District's or
                # a territory's one seat in the place's own words - never "in
                # Wyoming (at large)", an unfurl's form (the second review of
                # PR #267: Chuck Gray's line on Wyoming's officers' row).
                seat = share.seat_in_words(label)
                code = str(label).partition(" • ")[2]
                tail = f"the {body} in {seat}" if seat == code else seat
                return f"2026 race for {tail}" if when else f"Candidate for {tail}"
            # After Election Day the race is named, not the person's place in
            # it: "In the 2026 race for ...: Withdrew from the 2026 race" read
            # as though they were still in it (the review of PR #267).
            return (f"2026 race for the {body} in {where}" if when
                    else f"Candidate for the {body} in {where}")
        if parts:
            # The seat they hold in a sentence (rule 96: share's mirror of
            # KYC.heldSeatInWords): "a U.S. Senate seat from Minnesota", "the
            # U.S. Virgin Islands’ seat in the U.S. House".
            held = share.held_seat_in_words(person.get("officeLabel"))
            return ("Member of Congress, holding " if seated(person)
                    else "Former member of Congress, who held ") + held
        return _cap(share._role(person, when))

    def say(when):
        lead = lead_of(when)
        status = share.status_words(person, by_id, races_by_id, when)
        return f"{lead}: {status}" if status else lead

    words, after = say(False), say(post)
    pid = person["id"]
    role = {"kind": "profile", "id": pid, "state": person.get("state"),
            "words": words, "href": f"states/{str(person.get('state') or '').lower()}.html"
                                    f"#/profile/{pid}",
            "view": f"#/profile/{pid}", "share": f"p/{pid}.html"}
    if after != words:
        role["after"] = after
    return role


def departed_seat_words(row):
    """The seat a member who left held, as their own row says it
    (``kyc-directory.js`` seatWords, word for word): "U.S. Senator from
    Ohio", "Delegate from the U.S. Virgin Islands", "U.S. Representative,
    NJ-11"."""
    from .history import DELEGATE_TITLES
    from .pages import sentence_place, state_name

    state = row.get("state")
    if (row.get("chamber") or "House") == "Senate":
        return f"U.S. Senator from {state_name(state)}"
    if state in DELEGATE_TITLES:
        return f"{DELEGATE_TITLES[state]} from {sentence_place(state)}"
    district = row.get("district")
    return f"U.S. Representative, {state}-{district if district not in (None, '', 0, '0') else 'AL'}"


def departed_role(row):
    """A member who left this Congress, in their row's own words: the seat,
    and the day as congress-legislators' end of the term, said as theirs -
    never "Left the U.S. Senate on" that day as the fact. The row's reason:
    that end can be another day than the leaving (Doug LaMalfa's term ends
    there on January 5, 2026; the Clerk records his death on January 6), and
    the first words, "Left the U.S. Senate on Jan. 9, 2025", stated
    congress-legislators' day for J.D. Vance as the day he left (the review
    of PR #267)."""
    from .pages import date_words

    words = (f"Former {departed_seat_words(row)}; congress-legislators ends the term on "
             f"{date_words(row.get('left'))}")
    bioguide = row.get("id") or row.get("bioguide")
    return {"kind": "departed", "id": bioguide, "state": row.get("state"), "words": words,
            "href": BIOGUIDE_URL.format(bioguide), "share": BIOGUIDE_URL.format(bioguide),
            "link": "Congress biography"}


def _us(title):
    title = str(title or "")
    if re.search(r"United States|^President|^Vice President", title):
        return title
    if title.lower().startswith("acting "):
        return "Acting U.S. " + title[7:]
    return "U.S. " + title


def official_role(oid, words, after=None):
    role = {"kind": "official", "id": oid, "words": words,
            "href": f"federal/index.html#/official/{oid}", "view": f"#/official/{oid}",
            "share": f"o/{oid}.html"}
    if after and after != words:
        role["after"] = after
    return role


def judge_court(judge, entries):
    """Of the courts whose files list *judge* (``[(court id, name)]``), the
    one of their latest seat by commission: a judge sitting on two is shown
    where they sit now, never by which court's id sorts first."""
    seats = sorted((s for s in judge.get("seats") or [] if s.get("court")),
                   key=lambda s: s.get("commissioned") or "")
    courts = dict(entries)
    for seat in reversed(seats):
        if seat["court"] in courts:
            return seat["court"], courts[seat["court"]]
    return entries[0]


def judge_role(judge, court_id, court_name):
    """A judge as their dialog says it (rule 82): the title of the seat on
    the court whose file is read (their latest there), and their service -
    senior by the directory, or senior by the courts' list while the
    directory says active, both said."""
    from .pages import date_words

    seats = sorted((s for s in judge.get("seats") or [] if s.get("court") == court_id),
                   key=lambda s: s.get("commissioned") or "")
    seat = seats[-1] if seats else (judge.get("seats") or [{}])[-1]
    title = (judge.get("justice") or {}).get("role") or seat.get("title") or "Judge"
    where = "the Supreme Court of the United States" if court_id == "scotus" else (
        court_name if str(court_name or "").startswith("the ") else f"the {court_name}")
    words = f"{title} of {where}"
    listed = judge.get("listedSenior") or {}
    if judge.get("retiredJustice"):
        words = f"Retired justice of {where}, not a member of the Court"
    elif seat.get("seniorSince") or judge.get("status") == "senior":
        words += (f", senior status since {date_words(seat['seniorSince'])}"
                  if seat.get("seniorSince") else ", senior status")
    elif listed.get("since"):
        words += (f", senior status from {date_words(listed['since'])} by the courts’ list of "
                  "vacancies; the FJC directory still lists active service")
    jid = judge["id"]
    href = (f"federal/index.html#/official/{jid}" if court_id == "scotus"
            else f"courts/{court_id}.html#/official/{jid}")
    return {"kind": "judge", "id": jid, "words": words, "href": href,
            "view": f"#/official/{jid}", "court": court_id, "share": f"o/{jid}.html"}


def term_end(role, item, now_words):
    """A governor's or an officer's role ends on the clock its own card uses
    (``KYC.stategov.pastTermText``, kyc/terms_begin.py): where the term the
    2026 election chose has a day the state's law gives (``termBegins``)
    and the roster's holder was not on the ballot for it (``outgoing``),
    the role carries that day (``ends``, the first day the term had
    certainly begun), the roster's day read (``endsRead``) and the words
    from then (``ended``): "Was Attorney General of Texas, until the term
    the 2026 election chose began on Jan. 1, 2027". Read in January, the
    first line went on calling Ken Paxton "Attorney General of Texas" beside
    the officers' row saying the new term had begun (the review of PR
    #267)."""
    from .terms_begin import began_words

    term = (item or {}).get("termBegins")
    gone = (item or {}).get("outgoing")
    if not (item or {}).get("up") or not term or not gone or not term.get("from"):
        return role
    role["ends"] = term["from"]
    if gone.get("read"):
        role["endsRead"] = gone["read"]
    role["ended"] = f"Was {now_words}, until the term the 2026 election chose {began_words(term)}"
    return role


def governor_role(code, gov, item=None):
    from .pages import governor_of

    words = governor_of(code) + (f", in office since {gov['since']}" if gov.get("since") else "")
    gid = gov["id"]
    return term_end({"kind": "governor", "id": gid, "state": code, "words": words,
                     "href": f"states/{code.lower()}.html#/official/{gid}",
                     "view": f"#/official/{gid}", "share": f"o/{gid}.html"},
                    item, governor_of(code))


def candidate_role(code, person):
    """A candidate on the election office's list for governor, in their
    card's badge's words (``KYC.stategov.candidateBadge``) and the office:
    "On the Nov 3, 2026 ballot for Governor of Minnesota", and from the day
    after Election Day "Was on ...": never a winner (rule 91)."""
    from .pages import governor_of

    office = governor_of(code)
    if person.get("writeIn"):
        words, after = f"Write-in candidate for {office}", f"Was a write-in candidate for {office}"
    else:
        words, after = (f"On the {ELECTION} ballot for {office}",
                        f"Was on the {ELECTION} ballot for {office}")
    cid = person["id"]
    return {"kind": "candidate", "id": cid, "state": code, "words": words, "after": after,
            "href": f"states/{code.lower()}.html#/official/{cid}", "view": f"#/official/{cid}",
            "share": f"o/{cid}.html"}


def officer_role(code, key, off, item=None):
    from .voting_dates import place

    title = off.get("title") or {"lt": "Lieutenant Governor", "ag": "Attorney General",
                                 "sos": "Secretary of State"}[key]
    words = f"{title} of {place(code)}"
    return term_end({"kind": "officer", "id": f"{code}-{key}", "state": code, "words": words,
                     "href": f"states/{code.lower()}.html#state-government",
                     "share": f"states/{code.lower()}.html"}, item, words)


_DISTRICT_NUMBER = re.compile(r"^\d+[A-Z]?$")


def legislator_role(code, member, title, name=None):
    """"Member of the Texas House of Representatives, district 49": the
    legislature page's chamber, named with its state as that page's title
    names it - or by the chamber's own name where the legislature page
    carries one (*name*, ``legislature.chamber_name``: "New York State
    Assembly", never "New York Assembly", rule 75) - and the district the
    roster gives: a number as "district 49", a district a legislature
    names as a place in its own words, "for the 18th Essex district" and
    "for the Strafford 4 district" (the first read "district 18th
    Essex"). Its share page's link opens the member's district on the
    legislature page, as the card's does (the first led to the page's
    top)."""
    from .pages import short_name

    district = str(member.get("district") or "").strip()
    where = ""
    if district:
        where = (f", district {district}" if _DISTRICT_NUMBER.match(district)
                 else f", for the {district} district")
    words = f"Member of the {name or short_name(code) + ' ' + title}{where}"
    d = member.get("districtId") or ""
    chamber = member.get("chamber")
    query = ("chamber=lower&" if chamber == "lower" else "") + f"d={d}"
    href = f"legislature/{code.lower()}.html#/?{query}"
    return {"kind": "legislator", "id": member.get("id"), "state": code, "words": words,
            "href": href, "share": href}


def _named_officer(off):
    """An officer card that names its holder as the office's (rule 56): no
    dispute, no unconfirmed association listing, a name."""
    if not off or not off.get("name"):
        return False
    return not any(off.get(k) for k in ("none", "vacant", "disputed", "unlisted", "unconfirmed",
                                         "notMember"))


def _photo(record, *keys):
    for key in keys:
        value = (record or {}).get(key)
        if isinstance(value, list):
            value = next((v for v in value if v and v != "placeholder"), None)
        if value:
            return True
    return False


# --------------------------------------------------------------- the graph

class Links:
    """The joins of one build: ``components`` (lists of nodes that are one
    person), ``problems`` (``(level, code, message, detail)``) and the
    nodes by key."""

    def __init__(self):
        self.nodes = {}
        self.parent = {}
        self.problems = []
        self.joined_by = {}       # frozenset of two keys -> why
        self.settled_pairs = {}   # frozenset of two keys -> an IDENTITY_JOINS entry
        self.item_pairs = set()   # two profiles one Wikidata item is on, and no other id
        self.item_settled = set()  # those an entry says are one person
        self.chamber_names = {}   # (state, chamber) -> a chamber's own name, where recorded
        self.roster_behind = []   # legislator cards that are no current role, and why
        self.officer_behind = []  # officer cards naming a sitting member of Congress, and why
        self.history_cache = {}
        self.legislators = {}
        self.titles = {}

    def settled(self, a, b):
        """Whether a person's evidenced entry settles the pair either way."""
        return frozenset((a, b)) in self.settled_pairs

    # union-find
    def _find(self, key):
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def _union(self, a, b, why):
        ra, rb = self._find(a), self._find(b)
        self.joined_by.setdefault(frozenset((a, b)), why)
        if ra != rb:
            self.parent[rb] = ra

    def add(self, node):
        if node.key in self.nodes:
            return self.nodes[node.key]
        self.nodes[node.key] = node
        self.parent[node.key] = node.key
        return node

    def components(self):
        groups = {}
        for key in self.nodes:
            groups.setdefault(self._find(key), []).append(self.nodes[key])
        return [sorted(g, key=lambda n: (KINDS.index(n.kind), n.key))
                for g in groups.values() if len(g) > 1]

    def roles_for(self, node):
        """The other roles of *node*'s person, in the kinds' order, less
        those its own card already is (a governor's own entry on their
        office's list, rule 91; a member's own candidacy profile, which the
        profile cross-links itself, rule 30)."""
        root = self._find(node.key)
        out = []
        for other in sorted((n for n in self.nodes.values()
                             if n is not node and self._find(n.key) == root),
                            key=lambda n: (KINDS.index(n.kind), n.key)):
            if _same_card(node, other):
                continue
            out.append(dict(other.role))
        return out


def cross_linked(a, b):
    """Two profiles the profile dialog itself cross-links
    (``kyc-profile.js`` renderCrossLink): a member and their own candidacy
    for another seat, by the fields that dialog reads - the member's
    ``alsoRunningId`` and the filing's ``incumbentId`` (kyc/profiles.py,
    rules 30 and 68). *a* and *b* are the profiles' records."""
    a, b = a or {}, b or {}
    return bool(a.get("id") and b.get("id") and (
        b["id"] in (a.get("alsoRunningId"), a.get("incumbentId"))
        or a["id"] in (b.get("alsoRunningId"), b.get("incumbentId"))))


def _same_card(a, b):
    """Two nodes whose cards already say the other: a governor on their own
    office's list (rule 91), and the two profiles the profile dialog
    cross-links (:func:`cross_linked`) - only those. Any other two profiles
    of one person (two filings an id or a person's evidenced entry ties,
    which no dialog links) name each other like any two cards: "one card,
    no line" was said of every pair of profiles, so Colin Allred's race for
    the House said nothing of his Senate filing (the second review of PR
    #267)."""
    kinds = {a.kind, b.kind}
    if kinds == {"profile"}:
        return cross_linked(a.record, b.record)
    if kinds == {"governor", "candidate"} and a.state == b.state:
        return True                 # the holder on their own office's list
    return False


# The kinds whose card is a state's: one person on two states' (a
# candidate on two states' lists for governor, Minnesota's governor on
# Wisconsin's list) is a record to report, not a role to link.
STATE_KINDS = ("governor", "candidate", "officer", "legislator")


def states_disagree(a, b):
    """A state's card and a card of another state: another state's card, a
    profile or a departed member's row. Whatever id they share, one is not
    the other's role (two states' lists for governor, Minnesota's governor
    on Wisconsin's list, an Ohio legislator and a Texas filer): refused and
    warned, for a person to settle."""
    return bool(a.state and b.state and a.state != b.state
                and (a.kind in STATE_KINDS or b.kind in STATE_KINDS))


def _share_an_id(a, b):
    return bool(a.ids["bioguide"] & b.ids["bioguide"] or a.ids["fec"] & b.ids["fec"])


def _join_by_ids(links):
    """Join every two nodes that hold one id, where their names agree and,
    for a state's card, their states do. Every pair of an id's holders is
    asked: compared only with the first, a first holder whose name
    disagreed (a spouse's article on a challenger's ballot page) kept two
    true holders apart and pointed both warnings at itself.

    A Wikidata item two *profiles* hold is not enough for them: a
    challenger's item is their ballot page's article's (rule 33), a
    namesake's article passes that rule's surname test, and two filings
    that share an article are a look-alike to report (rule 25), never one
    person on the item's word - the namesake would take on every role the
    member's item is on. Two profiles are joined by an item only where
    they also share a bioguide or an FEC id; otherwise the pair is warned
    (``identity-item-shared``) and the item joins neither of them to
    anything until an evidenced ``overrides.IDENTITY_JOINS`` entry says
    they are one person."""
    for scheme in ("bioguide", "wikidata", "fec"):
        holders = {}
        for node in links.nodes.values():
            for value in node.ids[scheme]:
                holders.setdefault(value, []).append(node)
        for value, nodes in sorted(holders.items()):
            if len(nodes) < 2:
                continue
            barred = set()
            if scheme == "wikidata":
                profiles = [n for n in nodes if n.kind == "profile"]
                for i, a in enumerate(profiles):
                    for b in profiles[i + 1:]:
                        if _share_an_id(a, b):
                            continue
                        pair = frozenset((a.key, b.key))
                        entry = links.settled_pairs.get(pair)
                        if entry and entry["same"]:
                            # A person's word that the item is both filings'.
                            links.item_settled.add(pair)
                            continue
                        links.item_pairs.add(pair)
                        barred.update(pair)
                        if not entry:
                            links.problems.append((
                                "warn", "identity-item-shared",
                                f"profile {a.name} ({a.record.get('id')}, {a.state}) and profile "
                                f"{b.name} ({b.record.get('id')}, {b.state}) both carry the Wikidata "
                                f"item {value} and share no bioguide or FEC id: one article on two "
                                "filings' ballot pages, which a namesake's can be (rules 25, 33). The "
                                "item joins neither to any card until an evidenced "
                                "overrides.IDENTITY_JOINS entry settles the pair (rule 105)",
                                [a.key, b.key]))
            for i, first in enumerate(nodes):
                for other in nodes[i + 1:]:
                    if first.key in barred or other.key in barred:
                        continue
                    if states_disagree(first, other):
                        links.problems.append((
                            "warn", "identity-states-disagree",
                            f"{first.kind} {first.name} ({first.state}) and {other.kind} "
                            f"{other.name} ({other.state}) share the {scheme} id {value}, but a "
                            "state's card is not a role of someone on another state's card: "
                            "neither card names the other (rule 105)", [first.key, other.key]))
                    elif names_agree(first.forms, other.forms):
                        links._union(first.key, other.key, f"{scheme} {value}")
                    else:
                        links.problems.append((
                            "warn", "identity-names-disagree",
                            f"{first.kind} {first.name} and {other.kind} {other.name} share the "
                            f"{scheme} id {value} but their names disagree; neither card names the "
                            "other (rule 105)", [first.key, other.key]))


def office_in_state(row, key, code, when_read=False):
    """Whether a corroborated row of offices (rule 69) is the officer card's
    office in *code*: open (*when_read*: or found open when the record was
    read, ``openWhenRead``, as the record phase writes a candidate's and a
    seated winner's open offices - ``history.for_page``'s *before_seat*; the
    officer card is then the current source and the record the second), the
    office's words and none of another office's
    (a deputy's, an assistant's, an acting one's, the U.S. one), and the
    state in its place - the row's ``where``, or with none, the label itself
    naming the state in the office's slot ("Texas Attorney General",
    "Attorney General of Texas"), never a label naming no state: Arizona's
    rows carry no ``where``, and "Oklahoma Attorney General" was read as
    Texas's (the review of PR #267)."""
    from .pages import short_name

    office = row.get("office") or ""
    is_open = row.get("current") or (when_read and row.get("openWhenRead"))
    if not is_open or not OFFICE_WORDS[key].search(office) or _NOT_THE_OFFICE.search(office):
        return False
    state = short_name(code)
    if row.get("where"):
        return row["where"] == state
    title = OFFICE_WORDS[key].pattern
    st = re.escape(state)
    shape = re.compile(rf"(?:(?:the\s+)?(?:state\s+of\s+)?{st}\s+{title}|{title}\s+of\s+(?:the\s+)?"
                       rf"(?:state\s+of\s+|commonwealth\s+of\s+)?{st})", re.I)
    return bool(shape.fullmatch(office.strip()))


def _seat_day(record):
    """The day a sitting member's term began, from the profile's own term
    (``term_start``, "2027-01-03 - 2029-01-03"); "" where it gives none."""
    found = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str((record or {}).get("term_start") or ""))
    return found.group(1) if found else ""


def _officer_behind(links, officer, other):
    """The member of Congress sitting now (``record.seated``) among the
    cards *other* is one person with, whom the state officer's card still
    names as holding its office after they took their seat in Congress -
    its role carrying no end (``ends``, :func:`term_end`) or one after the
    day their term began - or None. Such a card is the roster's lag, never
    a current role: on the January rehearsal Marty Jackley, seated for
    SD-AL, read "Also on this site: Attorney General of South Dakota" with
    no end, while the legislator cards of seated winners were said apart
    and linked to nothing (rule 105). One day is enough: Wyoming's
    secretary of state's term ends on January 4, a day after Chuck Gray's
    seat in the House began."""
    from .record import seated

    root = links._find(other.key)
    ends = officer.role.get("ends") or ""
    for node in links.nodes.values():
        if node.kind != "profile" or links._find(node.key) != root or not seated(node.record):
            continue
        day = _seat_day(node.record)
        if not ends or not day or ends > day:
            return node
    return None


def _say_officer_behind(links, officer, member, why):
    day = _seat_day(member.record)
    ends = officer.role.get("ends")
    links.officer_behind.append(
        f"{member.kind} {member.name} ({member.record.get('id')}) and {officer.name} "
        f"({officer.role['words']}): seated in Congress"
        + (f" since {day}" if day else "") + ", but the officer card still names them, "
        + (f"its term ending on {ends}" if ends else "its term carrying no end this site reads")
        + f" (joined by {why})")


def _join_officers(links, officers):
    """Each officer card to the people whose corroborated record holds that
    office open in that state, where the card's name names them (rule 56).

    Once the Congress the cycle elects sits, a candidate's and a seated
    winner's record says an office was open *when it was read*
    (``openWhenRead``), no longer that it is current (rules 69 and 86). The
    officer card is read from the office's roster every day, so while it
    still names the person the two sources still agree: the join stands,
    and the role ends on its own card's clock (``ends``, :func:`term_end`).
    On the first January rehearsal Phil Weiser's, Aaron D. Ford's, Alan
    Wilson's, Juliana Stratton's and Chuck Gray's lines vanished on January
    3 and each pair was reported as a look-alike to settle, a day after the
    build had settled it. A pair whose record holds the office open when
    read is never a look-alike."""
    people = [n for n in links.nodes.values() if n.kind in ("profile", "candidate", "governor")]
    for node in officers:
        code, key = node.state, node.key.rsplit(":", 1)[-1]
        for person in people:
            if person.state != code:
                continue
            held = [r for r in _history_rows(person.record)
                    if office_in_state(r, key, code, when_read=True)]
            read_open = [r for r in held if not r.get("current")]
            # Any form of the name the record's own sources write (a member's
            # congress-legislators aliases, the FEC's filed name, the list's
            # printed form), each by rule 56's test, never a nickname table.
            named = any(office_names(form, node.name) for form in person.forms if form)
            if held and named:
                row = next((r for r in held if r.get("current")), held[0])
                why = (f"{row['office']} in the record"
                       + ("" if row.get("current")
                          else f", open when it was read on {row['openWhenRead']}")
                       + "; the officer card names them")
                behind = _officer_behind(links, node, person)
                if behind:
                    _say_officer_behind(links, node, behind, why)
                    continue
                links._union(node.key, person.key, why)
            elif (look_alike(person.name, node.name) and not read_open
                  and not links.settled(node.key, person.key)):
                links.problems.append((
                    "warn", "identity-look-alike",
                    f"{node.name} ({node.role['words']}) and {person.kind} {person.name} share a "
                    "name, but " + ("no corroborated record of theirs holds the office"
                                    if not held else "the card's name does not name them by "
                                    "rule 56's test") + "; neither card names the other (rule 105)",
                    [node.key, person.key]))
            elif (held and _forms([node.name])[2] & _forms(person.forms)[2]
                  and not links.settled(node.key, person.key)):
                # The record holds the very office and the card names someone
                # of that surname under another given name: one person under
                # a name the card does not write (the January rehearsal's
                # "Margaret Flanagan", Minnesota's Senate winner, beside the
                # card's "Peggy Flanagan"), or a stale record beside a
                # namesake holder. A person's evidenced entry settles it; it
                # was silent, the pair neither joined nor said.
                links.problems.append((
                    "warn", "identity-names-disagree",
                    f"{node.name} ({node.role['words']}) and {person.kind} {person.name} "
                    f"({person.record.get('id')}): their corroborated record holds the office, "
                    "but the card names a given name none of the record's forms of the name "
                    "writes (rule 56); neither card names the other until an evidenced "
                    "overrides.IDENTITY_JOINS entry settles the pair (rule 105)",
                    [node.key, person.key]))


def _legislator_node(links, code, member, chamber_titles):
    key = f"legislator:{code}:{member.get('id')}"
    if key in links.nodes:
        return links.nodes[key]
    title = chamber_titles.get((code, member.get("chamber"))) or "Legislature"
    name = (links.chamber_names or {}).get((code, member.get("chamber")))
    return links.add(Node(key, "legislator", member.get("name"), code, member,
                          legislator_role(code, member, title, name),
                          photo=_photo(member, "image")))


def _seat_while_a_candidate(record, person, history, legislators):
    """For a member seated since Election Day for a race they won (rule 67's
    ``record.seated_winner``), the legislator rule 24's own test ties to the
    filing folded into their profile (``record.filing_ids``, where the
    history cache still holds the record read while they ran, rule 86): the
    seat they held as a candidate, which the legislature's roster still
    lists. None for anyone else."""
    from .nominee_photos import legislator_for
    from .record import filing_ids, seated_winner

    if not seated_winner(record):
        return None
    for pid in [record.get("id")] + filing_ids(record):
        member, _why = legislator_for(dict(person, id=pid), history, legislators)
        if member:
            return member
    return None


def _join_legislators(links, legislators, chamber_titles):
    """Each candidate for Congress or governor who sits in their state's
    legislature, by rule 24's join (``nominee_photos.legislator_for``); and
    each who shares their first and last name with a member of their own
    state's legislature that the join did not tie, reported in one line
    (``identity-legislator-look-alike``) and linked to nobody (rule 25).

    A winner seated in Congress since Election Day whom the roster still
    lists in the seat the join tied them to as a candidate is neither: they
    are one person, and it is the roster that is behind (rules 16, 51 and
    100: Open States seats whom a legislature has replaced). They are said
    in a line of their own (``identity-legislator-roster-behind``) and
    linked to nothing - a member of Congress is not shown as sitting in a
    legislature on a roster's word. On the first January rehearsal fourteen
    of them were listed among the look-alikes for a person to settle."""
    from .nominee_photos import held_seats, legislator_for, same_name
    from .record import seated_winner

    history = links.history_cache or {}
    unsettled = []
    for node in list(links.nodes.values()):
        if node.kind not in ("profile", "candidate"):
            continue
        record = node.record
        person = {"id": record.get("id"), "name": node.name, "state": node.state,
                  "wikipedia": record.get("wikipedia")}
        # Only a candidate is asked of the join (a sitting member of Congress
        # holds no seat in a legislature); everyone is asked of the report:
        # the Speaker and Louisiana's Representative Mike Johnson are a pair
        # for a person to name as two.
        joinable = node.kind == "candidate" or record.get("isCandidate")
        member, why = (legislator_for(person, history, legislators) if joinable
                       else (None, "not a candidate, so not asked of the legislature join"))
        if member:
            leg = _legislator_node(links, node.state, member, chamber_titles)
            links._union(leg.key, node.key, "legislature join (rule 24)")
            continue
        was = (None if joinable or node.kind != "profile"
               else _seat_while_a_candidate(record, person, history, legislators))
        if not joinable and node.kind == "profile" and seated_winner(record):
            # A winner seated since Election Day is asked of the roster-behind
            # test, not the join: say why that test did not hold, never "not a
            # candidate" (the January rehearsal's Houston Gaines, Wes Climer).
            why = ("seated in Congress since Election Day, and no corroborated seat of theirs "
                   "while they ran is this one" if was is None else
                   "seated in Congress since Election Day; the seat rule 24's join tied them to "
                   "as a candidate is another")
        roster = ((legislators or {}).get("states") or {}).get(node.state) or []
        # A corroborated seat whose member the roster writes another way
        # ("Shev Jones" for "Shevrin \"Shev\" Jones"): the same surname in
        # that very chamber is reported too, for a person to settle.
        seats = held_seats(person, history) if joinable else set()
        surname = (_words(node.name) or [""])[-1]
        for seat in roster:
            # The very seat rule 24's join tied a seated winner to as a
            # candidate is the roster's lag whatever the names say: Congress's
            # record writes "Christopher M. Rabb" and "Joshua Turek", the
            # roster "Chris Rabb" and "Josh Turek", and the first version asked
            # the name first and said nothing of either.
            was_seat = was is not None and seat.get("id") == was.get("id")
            alike = same_name(node.name, seat.get("name"))
            if not was_seat and not alike and not (
                    (node.state, seat.get("chamber")) in seats and surname
                    and surname in _words(seat.get("name"))):
                continue
            key = f"legislator:{node.state}:{seat.get('id')}"
            if links.settled(key, node.key):
                continue
            pair = (f"{node.kind} {node.name} ({record.get('id')}) and "
                    f"{seat.get('name')} ({node.state} {seat.get('chamber')} "
                    f"{seat.get('district')}, {seat.get('id')})")
            if was_seat:
                links.roster_behind.append(
                    pair + ": seated in Congress since Election Day, in the seat rule 24's join "
                    "tied them to as a candidate")
                continue
            unsettled.append(pair + ": "
                             + (why if alike else "their corroborated record holds a seat in that "
                                "chamber, but the roster writes the name another way"))
    if unsettled:
        links.problems.append((
            "warn", "identity-legislator-look-alike",
            f"{len(unsettled)} people look like a member of their own state's legislature - the "
            "same first and last name, or their surname in a chamber their corroborated record "
            "holds a seat in - and rule 24's join does not tie them; neither card names the other "
            "until a corroborated record does, or an evidenced "
            "overrides.IDENTITY_JOINS entry settles the pair (rule 105)", sorted(unsettled)))


def _report_roster_behind(links):
    """One line for the legislator cards that are no current role though
    they are the person's (rules 16, 51, 100): a winner seated in Congress
    since Election Day whom the roster still lists in the seat rule 24's
    join tied them to as a candidate, and a pair an evidenced
    ``overrides.IDENTITY_JOINS`` entry says is one person whose legislature
    now seats someone else (``behind``: Florida's Senate gives Shevrin
    Jones's District 34 to Ashley Gantt for 2026-2028, its House Angie
    Nixon's District 13 to Audrey Gibson, while Open States still seats
    both). Neither card names the other: a roster's word is not shown as a
    seat the legislature has given away.

    And one line for the officer cards that still name a member of Congress
    sitting now after their seat began (:func:`_officer_behind`,
    ``identity-officer-roster-behind``): the office's roster is behind, or
    the term this site reads for it is, for a person to check."""
    if links.officer_behind:
        n = len(links.officer_behind)
        links.problems.append((
            "warn", "identity-officer-roster-behind",
            f"{n} state officer card{'' if n == 1 else 's'} still name{'s' if n == 1 else ''} "
            "someone who sits in Congress now as holding the office after their seat in Congress "
            "began: the office's roster, or the term this site reads for the office (termBegins, "
            "rule 84), is behind; neither card names the other until it is checked (rule 105)",
            sorted(links.officer_behind)))
    if not links.roster_behind:
        return
    fetched = str((links.legislators or {}).get("fetched") or "")[:10]
    n = len(links.roster_behind)
    links.problems.append((
        "warn", "identity-legislator-roster-behind",
        f"{n} state legislator card{'' if n == 1 else 's'} of someone on this site "
        f"{'is' if n == 1 else 'are'} no current role: their legislature's roster"
        + (f" (Open States, read {fetched})" if fetched else "")
        + " still seats them, but they sit in Congress now or the legislature's own pages "
        "give the seat to someone else. The roster is behind (rules 16, 51, 100), not a "
        "look-alike to settle; neither card names the other (rule 105)",
        sorted(links.roster_behind)))


def _profile_alias(links, key):
    """The node a profile's key answers to once its filing is folded into
    another profile: ``profile:FEC_<id>`` is the profile that holds that FEC
    candidate id (its own or a merged one, ``otherFecIds``; rule 96's
    ``share.aliases``), so an entry keyed on a winner's filing still settles
    their pair on January 3, when they are a member under their bioguide id
    (Marty Jackley's, elected in SD-AL). None where no one profile holds it."""
    if key in links.nodes or not key.startswith("profile:FEC_"):
        return None
    fec = key[len("profile:FEC_"):]
    held = [n for n in links.nodes.values() if n.kind == "profile" and fec in n.ids["fec"]]
    return held[0] if len(held) == 1 else None


def _apply_settled(links):
    """Read ``overrides.IDENTITY_JOINS``: a person's evidenced word that two
    cards are one person (``same``) or two (a namesake), keyed on both
    cards' keys as the build's report names them. An entry with no
    evidence or day is an error and settles nothing (rule 105)."""
    from . import overrides

    for pair, entry in sorted(getattr(overrides, "IDENTITY_JOINS", {}).items()):
        entry = entry or {}
        # "behind": one person, whose legislator card is no current role -
        # only of a pair one of whose keys is a legislator's, said "same".
        behind_ok = "behind" not in entry or (
            entry.get("same") is True and str(entry.get("behind") or "").strip()
            and isinstance(pair, tuple) and any(str(k).startswith("legislator:") for k in pair))
        if (not isinstance(pair, tuple) or len(pair) != 2 or "same" not in entry
                or not entry.get("evidence") or not behind_ok
                or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(entry.get("read") or ""))):
            links.problems.append((
                "error", "identity-join-unevidenced",
                f"overrides.IDENTITY_JOINS {pair!r} needs both cards' keys, \"same\", the "
                "evidence and the day it was read; it settles nothing (rule 105)", [str(pair)]))
            continue
        # The keys as this build's nodes carry them (a folded filing's
        # profile), and as the entry writes them, for what is said of it.
        now = tuple(getattr(_profile_alias(links, key), "key", key) for key in pair)
        links.settled_pairs[frozenset(now)] = dict(entry, pair=now, written=pair)


def _node_for(links, key):
    """The node a settled entry names, making a legislator's from the Open
    States cache (their node exists only once something joins them)."""
    if key in links.nodes:
        return links.nodes[key]
    if key.startswith("legislator:"):
        _kind, code, mid = key.split(":", 2)
        for member in ((links.legislators or {}).get("states") or {}).get(code) or []:
            if member.get("id") == mid:
                return _legislator_node(links, code, member, links.titles)
    return None


def _join_settled(links):
    """Apply the settled entries after every other join, and say which no
    longer settle anything (stale, rule 105 and CLAUDE.md, Curated data)."""
    for pair, entry in sorted(links.settled_pairs.items(), key=lambda kv: kv[1]["pair"]):
        a_key, b_key = entry["pair"]
        a, b = _node_for(links, a_key), _node_for(links, b_key)
        if not a or not b:
            links.problems.append((
                "warn", "stale-identity-join",
                f"overrides.IDENTITY_JOINS {entry['written']!r}: "
                + ", ".join(w for w, n in zip(entry["written"], (a, b)) if not n)
                + " is no card this build makes; the entry settles nothing", list(entry["written"])))
            continue
        together = links._find(a.key) == links._find(b.key)
        if entry.get("behind"):
            if together:
                links.problems.append((
                    "warn", "stale-identity-join",
                    f"overrides.IDENTITY_JOINS {entry['written']!r} says the legislator card is no "
                    "current role, but the records join the two cards "
                    f"({links.joined_by.get(pair) or 'through another card'}): a person must look "
                    "at the legislature's roster again", list(entry["written"])))
            else:
                leg, other = (a, b) if a.kind == "legislator" else (b, a)
                links.roster_behind.append(
                    f"{other.kind} {other.name} ({other.record.get('id')}) and {leg.name} "
                    f"({leg.state} {leg.record.get('chamber')} {leg.record.get('district')}, "
                    f"{leg.record.get('id')}): {entry['behind']} (overrides.IDENTITY_JOINS, read "
                    f"{entry['read']})")
            continue
        if entry["same"]:
            if together and pair in links.item_settled:
                # Joined by the item, on this entry's word.
                links.joined_by[pair] = "an evidenced overrides.IDENTITY_JOINS entry"
            elif together:
                links.problems.append((
                    "warn", "stale-identity-join",
                    f"overrides.IDENTITY_JOINS {entry['written']!r}: the two cards are joined by "
                    f"ids or a second source already ({links.joined_by.get(pair) or 'joined'}); "
                    "the entry is no longer needed", list(entry["written"])))
            else:
                why = "an evidenced overrides.IDENTITY_JOINS entry"
                officer, other = (a, b) if a.kind == "officer" else (b, a)
                behind = (_officer_behind(links, officer, other) if officer.kind == "officer"
                          else None)
                if behind:
                    _say_officer_behind(links, officer, behind, why)
                else:
                    links._union(a.key, b.key, why)
        elif together:
            links.problems.append((
                "warn", "identity-join-contradicted",
                f"overrides.IDENTITY_JOINS {entry['written']!r} says two people, but the build joins "
                f"the two cards ({links.joined_by.get(pair) or 'through another card'}): a person "
                "must look again", list(entry["written"])))
        elif not look_alike(a.name, b.name) and pair not in links.item_pairs:
            links.problems.append((
                "warn", "stale-identity-join",
                f"overrides.IDENTITY_JOINS {entry['written']!r}: {a.name} and {b.name} no longer "
                "share a name or a Wikidata item, so there is no look-alike to settle",
                list(entry["written"])))


def build(profiles, races=None, summary=None, stategov=None, federal=None, courts=None,
          history=None, judge_links=None, departed=None, departed_cache=None,
          legislators=None, legislatures=None):
    """The :class:`Links` of one build, from the records each card is drawn
    from: *profiles* and *races* (the people files), *summary* (its results
    day and ``departed`` rows), *stategov* (``stategov.build``'s payload),
    *federal* and *courts* (``federal_build.build``'s), *history* (the
    political history cache: the bioguide id congress-legislators gives for
    each record's own item), *judge_links* (the judges' Wikidata items),
    *departed_cache* (the departed members' items), *legislators* (the
    Open States cache) and *legislatures* (the legislature pages' payload,
    for their chambers' titles)."""
    from . import share

    links = Links()
    links.history_cache = history or {}
    hist = (history or {}).get("people") or {}
    races_by_id = {r["id"]: r for r in races or []}
    by_id = {p["id"]: p for p in profiles or []}
    post = share.post_election(summary) or share.ResultsDay("2026-11-04")

    def from_history(node, key, *own, article=None):
        """The bioguide id congress-legislators gives for the record's own
        Wikidata item, read from the history cache - only where the cache's
        entry is that item's (*own*, the items the record itself carries)
        and, for a profile, was read from the article it links (*article*,
        as ``nominee_photos.held_seats`` asks): a stale entry, read from a
        namesake's article or a predecessor's item, would have joined a
        challenger "Scott Turner" to the Secretary of Housing (the review of
        PR #267)."""
        entry = hist.get(key) or {}
        bioguide = entry.get("bioguide")
        if not bioguide or bioguide in node.ids["bioguide"]:
            return                       # a member's own id says no more
        mine = {i for i in own if i}
        # The article it was read from, as history.stale asks (``asked``).
        asked = entry.get("asked")
        if entry.get("wikidata") in mine and (article is None or not asked or asked == article):
            node.add("bioguide", bioguide)
        elif mine:
            links.problems.append((
                "warn", "identity-history-stale",
                f"{node.kind} {node.name}: the history cache's entry under {key} gives the "
                f"bioguide id {bioguide} for {entry.get('wikidata') or 'no item'}"
                + (f", read from {asked}" if asked else "") + ", not the record's own "
                + ", ".join(sorted(mine)) + "; no card is joined by it (rule 105)", [node.key]))

    for person in profiles or []:
        node = links.add(Node(f"profile:{person['id']}", "profile", person.get("name"),
                              person.get("state"), person,
                              profile_role(person, by_id, races_by_id, post),
                              photo=_photo(person, "photos")))
        if BIOGUIDE.match(str(person["id"])):
            node.add("bioguide", person["id"])
        node.add("wikidata", _wikidata(person))
        for fec in [person.get("fecCandidateId")] + list(person.get("otherFecIds") or []):
            node.add("fec", fec)
        # A seated winner's record was read under the filing folded into
        # their profile (record.filing_ids, history.folded): on January 3
        # Colin Allred's TX-33 profile lost the bioguide id his item gives,
        # and his Senate filing, sharing only the item, became a pair to warn.
        from .record import filing_ids, seated_winner
        keys = [person["id"]] + (filing_ids(person) if seated_winner(person) else [])
        from_history(node, next((k for k in keys if hist.get(k)), person["id"]), _wikidata(person),
                     article=person.get("wikipedia"))

    items = {}
    for row in ((departed_cache or {}).get("members") or []) + \
            ((departed_cache or {}).get("previous") or []):
        if row.get("bioguide") and row.get("wikidata"):
            items[row["bioguide"]] = row["wikidata"]
    for row in departed if departed is not None else (summary or {}).get("departed") or []:
        node = links.add(Node(f"departed:{row['id']}", "departed", row.get("name"),
                              row.get("state"), row, departed_role(row)))
        node.add("bioguide", row["id"])
        node.add("wikidata", items.get(row["id"]))

    fed = federal or {}
    for key in ("president", "vicePresident"):
        person = fed.get(key)
        if not person or not person.get("id"):
            continue
        node = links.add(Node(f"official:{person['id']}", "official", person.get("name"), None,
                              person, official_role(person["id"], person.get("office") or ""),
                              photo=_photo(person, "photo")))
        node.add("bioguide", (person.get("links") or {}).get("bioguide"))
        node.add("wikidata", _wikidata(person))
        from_history(node, person["id"], _wikidata(person), (person.get("links") or {}).get("wikidata"))
    for office in fed.get("offices") or []:
        person = office.get("holder")
        if not person or not person.get("id"):
            continue
        title = person.get("title") or office.get("office") or ""
        if (person.get("page") or {}).get("acting") and not title.lower().startswith("acting"):
            title = "Acting " + title
        node = links.add(Node(f"official:{person['id']}", "official", person.get("name"), None,
                              person, official_role(person["id"], _us(title)),
                              photo=_photo(person, "photo")))
        node.add("bioguide", (person.get("links") or {}).get("bioguide"))
        node.add("wikidata", _wikidata(person))
        from_history(node, person["id"], _wikidata(person), (person.get("links") or {}).get("wikidata"))
    for person in fed.get("former") or []:
        if not person.get("id") or f"official:{person['id']}" in links.nodes:
            continue
        held = (person.get("held") or [{}])[-1]
        words = f"Former, this term: {_us(('Acting ' if held.get('acting') else '') + (held.get('office') or ''))}"
        node = links.add(Node(f"official:{person['id']}", "official", person.get("name"), None,
                              person, official_role(person["id"], words)))
        node.add("wikidata", (person.get("links") or {}).get("wikidata") or held.get("wikidata"))
        from_history(node, person["id"], _wikidata(person), (person.get("links") or {}).get("wikidata"),
                     held.get("wikidata"))

    # The federal judges, by the Wikidata item that carries their FJC id
    # (kyc/judge_links.py, rule 82): the Supreme Court's and every court's.
    judge_items = {f"fjc-{nid}": (row or {}).get("wikidata")
                   for nid, row in ((judge_links or {}).get("judges") or {}).items()}
    judges = []
    for judge in ((fed.get("supremeCourt") or {}).get("members") or []):
        judges.append((judge, "scotus", "Supreme Court of the United States"))
    for cid, court in sorted((courts or {}).items()):
        for judge in court.get("judges") or []:
            judges.append((judge, cid, court.get("name") or cid))
    # A judge in two courts' files is noded under the court of their latest
    # seat (judge_court), never whichever court's id sorts first.
    listed = {}
    for judge, cid, cname in judges:
        if judge.get("id"):
            listed.setdefault(judge["id"], (judge, []))[1].append((cid, cname))
    for jid, (judge, entries) in listed.items():
        cid, cname = judge_court(judge, entries)
        item = judge_items.get(jid)
        if not item:
            continue
        node = links.add(Node(f"judge:{judge['id']}", "judge", judge.get("name"), None, judge,
                              judge_role(judge, cid, cname),
                              photo=bool(((judge_links or {}).get("judges") or {})
                                         .get(judge["id"][4:], {}).get("portrait"))))
        node.add("wikidata", item)

    officers = []
    for code, entry in sorted(((stategov or {}).get("states") or {}).items()):
        gov = entry.get("governor") or {}
        offices = (entry.get("ballot2026") or {}).get("offices") or {}
        office = offices.get("governor") or {}
        if gov.get("id"):
            node = links.add(Node(f"governor:{gov['id']}", "governor", gov.get("name"), code, gov,
                                  governor_role(code, gov, office), photo=_photo(gov, "headshot")))
            node.add("wikidata", gov.get("wikidata") or _wikidata(gov))
            from_history(node, gov["id"], gov.get("wikidata"), _wikidata(gov))
        if office.get("up"):
            for person in ((office.get("candidates") or {}).get("candidates") or []):
                if not person.get("id"):
                    continue
                node = links.add(Node(f"candidate:{person['id']}", "candidate", person.get("name"),
                                      code, person, candidate_role(code, person),
                                      photo=_photo(person, "photo")))
                node.add("bioguide", person.get("member"))
                node.add("wikidata", _wikidata(person))
                # The list's own form of the name and the short form an
                # evidenced STATEWIDE_NAME_FORMS entry gives it ("Joe
                # Lombardo" for "Lombardo, Joseph", rule 91).
                if person.get("printed"):
                    from .statewide_photos import name_forms
                    node.forms += [person["printed"]] + name_forms(code, "governor",
                                                                    person["printed"])
                from_history(node, person["id"], _wikidata(person))
        for key in OFFICER_KEYS:
            off = entry.get(key)
            if _named_officer(off):
                officers.append(links.add(Node(f"officer:{code}:{key}", "officer", off.get("name"),
                                               code, off, officer_role(code, key, off, offices.get(key)),
                                               photo=_photo(off, "photo"))))

    titles = {}
    for code, payload in (legislatures or {}).items():
        for chamber, info in ((payload or {}).get("chambers") or {}).items():
            titles[(code, chamber)] = info.get("title")
            if info.get("name"):
                links.chamber_names[(code, chamber)] = info["name"]
    links.legislators = legislators or {}
    links.titles = titles
    _apply_settled(links)
    _join_by_ids(links)
    _join_officers(links, officers)
    if legislators:
        _join_legislators(links, legislators, titles)
    _join_settled(links)
    _report_roster_behind(links)
    _look_alikes(links)
    return links


def _look_alikes(links):
    """Two cards of one name in one state, of different kinds, that nothing
    joined: reported, never joined (rule 25)."""
    seen = set()
    by_name = {}
    for node in links.nodes.values():
        if node.kind in ("legislator", "judge", "officer"):
            continue                     # officers are asked in _join_officers
        words = [w for w in _words(node.name) if len(w) > 1]
        if len(words) < 2:
            continue
        by_name.setdefault((words[0], words[-1]), []).append(node)
    for _name, nodes in sorted(by_name.items()):
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if (a.kind == b.kind or links._find(a.key) == links._find(b.key)
                        or _same_card(a, b) or links.settled(a.key, b.key)):
                    continue
                if a.state and b.state and a.state != b.state:
                    continue
                pair = frozenset((a.key, b.key))
                if pair in seen:
                    continue
                seen.add(pair)
                links.problems.append((
                    "warn", "identity-look-alike",
                    f"{a.kind} {a.name} and {b.kind} {b.name} share a name but no id or second "
                    "source; neither card names the other (rule 105)", [a.key, b.key]))


# --------------------------------------------------------------- writing

def attach(links):
    """Write each node's other roles onto the record its card is drawn from,
    as ``also``; remove a stale one. Returns how many records carry one."""
    count = 0
    for node in links.nodes.values():
        roles = links.roles_for(node)
        if roles:
            node.record["also"] = roles
            count += 1
        else:
            node.record.pop("also", None)
    return count


def attach_legislatures(links, legislatures):
    """The legislature pages' members carry their other roles too: the
    payload's records are not the Open States cache's the join read."""
    by_id = {n.record.get("id"): n for n in links.nodes.values() if n.kind == "legislator"}
    count = 0
    for code, payload in (legislatures or {}).items():
        for chamber in ((payload or {}).get("chambers") or {}).values():
            for members in (chamber.get("members") or {}).values():
                for member in members if isinstance(members, list) else [members]:
                    node = by_id.get(member.get("id"))
                    roles = links.roles_for(node) if node else []
                    if roles:
                        member["also"] = roles
                        count += 1
                    else:
                        member.pop("also", None)
        for member in (payload or {}).get("unplaced") or []:
            if isinstance(member, dict):
                node = by_id.get(member.get("id"))
                roles = links.roles_for(node) if node else []
                if roles:
                    member["also"] = roles
                else:
                    member.pop("also", None)
    return count


def attach_courts(links, courts):
    """A judge's record in their court's file (``data/judiciary/<id>.js``),
    which the court's page and its dialog read; the hub's justices are in
    the federal payload :func:`attach` writes."""
    by_id = {n.record.get("id"): n for n in links.nodes.values() if n.kind == "judge"}
    for court in (courts or {}).values():
        for judge in (court.get("judges") or []) + (court.get("retired") or []):
            node = by_id.get(judge.get("id"))
            roles = links.roles_for(node) if node else []
            if roles:
                judge["also"] = roles
            else:
                judge.pop("also", None)


def congress_bios(links, stategov=None, federal=None, history=None):
    """(h) An official or a governor whose service in Congress has no card
    here (no profile, no departed row): the Congress biography by the
    bioguide id congress-legislators gives for the record's own Wikidata
    item (the history cache's ``bioguide``), never a name. Written as
    ``congressBio`` on the record; returns how many."""
    hist = (history or {}).get("people") or {}
    carded = {v for n in links.nodes.values() if n.kind in ("profile", "departed")
              for v in n.ids["bioguide"]}
    count = 0
    for node in links.nodes.values():
        if node.kind not in ("official", "governor", "candidate"):
            continue
        entry = hist.get(node.record.get("id")) or {}
        bioguide = entry.get("bioguide")
        congress = any(r.get("congress") for r in _history_rows(node.record))
        if (bioguide and congress and bioguide not in carded
                and entry.get("wikidata") == _wikidata(node.record)):
            node.record["congressBio"] = bioguide
            count += 1
        else:
            node.record.pop("congressBio", None)
    return count


def joined(links):
    """``[(names, [(kind, key), ...], [why, ...])]``: every person joined,
    for the build's report."""
    out = []
    for group in links.components():
        # Only the cards that name another: a governor's own entry on their
        # office's list and a member's own candidacy are one card (_same_card).
        group = [n for n in group if links.roles_for(n)]
        if len(group) < 2:
            continue
        keys = {n.key for n in group}
        whys = sorted({why for pair, why in links.joined_by.items() if pair <= keys})
        out.append((group[0].name, [(n.kind, n.key) for n in group], whys))
    return sorted(out, key=lambda row: row[0] or "")


def photo_differences(links):
    """The joined people one of whose cards has a photograph another lacks:
    an info line, for a later decision (no photograph is borrowed)."""
    rows = []
    for group in links.components():
        cards = [n for n in group if n.kind != "departed" and links.roles_for(n)]
        with_photo = [n for n in cards if n.photo]
        without = [n for n in cards if not n.photo]
        if with_photo and without:
            rows.append(f"{group[0].name}: " + ", ".join(n.kind for n in with_photo) +
                        " pictured, " + ", ".join(n.kind for n in without) + " not")
    return sorted(rows)


def problems(links):
    """What the joins refused, and what they found, for validate's report."""
    out = list(links.problems)
    rows = joined(links)
    if rows:
        out.append(("info", "identity-joined",
                    f"{len(rows)} people appear on this site in more than one role, each card "
                    "naming the others (rule 105)",
                    [f"{name}: " + ", ".join(k for _kind, k in keys) + " (" + "; ".join(why) + ")"
                     for name, keys, why in rows]))
    pictured = photo_differences(links)
    if pictured:
        out.append(("info", "identity-photo-differs",
                    f"{len(pictured)} joined people have a photograph on one card and none on "
                    "another; no photograph is borrowed (rule 105)", pictured))
    return out


def share_html(record, post=False, root="../"):
    """The share pages' plain text of :func:`attach`'s roles (rule 96): the
    same words ``KYC.alsoHtml`` draws, in the tense of the day the results
    were read (*post*), each linked to that role's own share page (or its
    page, where it has none) from *root*. "" where there are none."""
    import html

    roles = (record or {}).get("also") or []
    if not roles:
        return ""
    parts = []
    for role in roles:
        words = role.get("after") if post and role.get("after") else role.get("words")
        # A role's end (term_end) on the page's day: the day the results
        # were read, or a later day the roster itself was read, as the
        # governor's share page decides its "In office since" (never the
        # build's clock, rule 96).
        day = post if isinstance(post, str) else ""
        if day and (role.get("endsRead") or "") > day:
            day = role["endsRead"]
        if role.get("ends") and role.get("ended") and day and day >= role["ends"]:
            words = role["ended"]
        words += f" ({role['link']})" if role.get("link") else ""
        target = role.get("share") or role.get("href") or ""
        href = target if re.match(r"https?:", target) else root + target
        parts.append(f'<a href="{html.escape(href, quote=True)}">{html.escape(words, quote=False)}</a>')
    return ('<p class="share-also"><strong>Also on this site:</strong> ' + "; ".join(parts)
            + "</p>")


def congress_bio_html(record):
    """The share pages' line for ``congressBio`` (:func:`congress_bios`)."""
    import html

    bioguide = (record or {}).get("congressBio")
    if not bioguide:
        return ""
    return (f'<p class="share-also"><a href="{html.escape(BIOGUIDE_URL.format(bioguide), quote=True)}">'
            "Biography in the Biographical Directory of the U.S. Congress</a></p>")
