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
        parts = share._seat_parts(person.get("officeLabel"))
        if parts and person.get("isCandidate"):
            body, where = parts
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


def legislator_role(code, member, title):
    """"Member of the Texas House of Representatives, district 49": the
    legislature page's chamber, named with its state, and the district the
    roster gives - a number as "district 49", a district a legislature
    names as a place in its own words, "for the 18th Essex district" and
    "for the Strafford 4 district" (the first read "district 18th
    Essex")."""
    from .pages import short_name

    district = str(member.get("district") or "").strip()
    where = ""
    if district:
        where = (f", district {district}" if _DISTRICT_NUMBER.match(district)
                 else f", for the {district} district")
    words = f"Member of the {short_name(code)} {title}{where}"
    d = member.get("districtId") or ""
    chamber = member.get("chamber")
    query = ("chamber=lower&" if chamber == "lower" else "") + f"d={d}"
    return {"kind": "legislator", "id": member.get("id"), "state": code, "words": words,
            "href": f"legislature/{code.lower()}.html#/?{query}",
            "share": f"legislature/{code.lower()}.html"}


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


def _same_card(a, b):
    kinds = {a.kind, b.kind}
    if kinds == {"profile"}:
        return True
    if kinds == {"governor", "candidate"} and a.state == b.state:
        return True                 # the holder on their own office's list
    return False


# The kinds whose card is a state's: one person on two states' (a
# candidate on two states' lists for governor, Minnesota's governor on
# Wisconsin's list) is a record to report, not a role to link.
STATE_KINDS = ("governor", "candidate", "officer", "legislator")


def _join_by_ids(links):
    """Join every two nodes that hold one id, where their names agree and,
    for two of a state's cards, their states do."""
    for scheme in ("bioguide", "wikidata", "fec"):
        holders = {}
        for node in links.nodes.values():
            for value in node.ids[scheme]:
                holders.setdefault(value, []).append(node)
        for value, nodes in sorted(holders.items()):
            if len(nodes) < 2:
                continue
            first = nodes[0]
            for other in nodes[1:]:
                if (first.kind in STATE_KINDS and other.kind in STATE_KINDS and first.state
                        and other.state and first.state != other.state):
                    links.problems.append((
                        "warn", "identity-states-disagree",
                        f"{first.kind} {first.name} ({first.state}) and {other.kind} {other.name} "
                        f"({other.state}) share the {scheme} id {value}, but one person is not on "
                        "two states' cards: neither card names the other (rule 105)",
                        [first.key, other.key]))
                elif names_agree(first.forms, other.forms):
                    links._union(first.key, other.key, f"{scheme} {value}")
                else:
                    links.problems.append((
                        "warn", "identity-names-disagree",
                        f"{first.kind} {first.name} and {other.kind} {other.name} share the "
                        f"{scheme} id {value} but their names disagree; neither card names the "
                        "other (rule 105)", [first.key, other.key]))


def office_in_state(row, key, code):
    """Whether a corroborated row of offices (rule 69) is the officer card's
    office in *code*: open, the office's words and none of another office's
    (a deputy's, an assistant's, an acting one's, the U.S. one), and the
    state in its place - the row's ``where``, or with none, the label itself
    naming the state in the office's slot ("Texas Attorney General",
    "Attorney General of Texas"), never a label naming no state: Arizona's
    rows carry no ``where``, and "Oklahoma Attorney General" was read as
    Texas's (the review of PR #267)."""
    from .pages import short_name

    office = row.get("office") or ""
    if not row.get("current") or not OFFICE_WORDS[key].search(office) \
            or _NOT_THE_OFFICE.search(office):
        return False
    state = short_name(code)
    if row.get("where"):
        return row["where"] == state
    title = OFFICE_WORDS[key].pattern
    st = re.escape(state)
    shape = re.compile(rf"(?:(?:the\s+)?(?:state\s+of\s+)?{st}\s+{title}|{title}\s+of\s+(?:the\s+)?"
                       rf"(?:state\s+of\s+|commonwealth\s+of\s+)?{st})", re.I)
    return bool(shape.fullmatch(office.strip()))


def _join_officers(links, officers):
    """Each officer card to the people whose corroborated record holds that
    office open in that state, where the card's name names them (rule 56)."""
    people = [n for n in links.nodes.values() if n.kind in ("profile", "candidate", "governor")]
    for node in officers:
        code, key = node.state, node.key.rsplit(":", 1)[-1]
        for person in people:
            if person.state != code:
                continue
            held = [r for r in _history_rows(person.record) if office_in_state(r, key, code)]
            named = office_names(person.name, node.name)
            if held and named:
                links._union(node.key, person.key,
                             f"{held[0]['office']} in the record; the officer card names them")
            elif look_alike(person.name, node.name) and not links.settled(node.key, person.key):
                links.problems.append((
                    "warn", "identity-look-alike",
                    f"{node.name} ({node.role['words']}) and {person.kind} {person.name} share a "
                    "name, but " + ("no corroborated record of theirs holds the office"
                                    if not held else "the card's name does not name them by "
                                    "rule 56's test") + "; neither card names the other (rule 105)",
                    [node.key, person.key]))


def _legislator_node(links, code, member, chamber_titles):
    key = f"legislator:{code}:{member.get('id')}"
    if key in links.nodes:
        return links.nodes[key]
    title = chamber_titles.get((code, member.get("chamber"))) or "Legislature"
    return links.add(Node(key, "legislator", member.get("name"), code, member,
                          legislator_role(code, member, title), photo=_photo(member, "image")))


def _join_legislators(links, legislators, chamber_titles):
    """Each candidate for Congress or governor who sits in their state's
    legislature, by rule 24's join (``nominee_photos.legislator_for``); and
    each who shares their first and last name with a member of their own
    state's legislature that the join did not tie, reported in one line
    (``identity-legislator-look-alike``) and linked to nobody (rule 25)."""
    from .nominee_photos import held_seats, legislator_for, same_name

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
        roster = ((legislators or {}).get("states") or {}).get(node.state) or []
        # A corroborated seat whose member the roster writes another way
        # ("Shev Jones" for "Shevrin \"Shev\" Jones"): the same surname in
        # that very chamber is reported too, for a person to settle.
        seats = held_seats(person, history) if joinable else set()
        surname = (_words(node.name) or [""])[-1]
        for seat in roster:
            alike = same_name(node.name, seat.get("name"))
            if not alike and not ((node.state, seat.get("chamber")) in seats and surname
                                  and surname in _words(seat.get("name"))):
                continue
            key = f"legislator:{node.state}:{seat.get('id')}"
            if links.settled(key, node.key):
                continue
            unsettled.append(f"{node.kind} {node.name} ({record.get('id')}) and "
                             f"{seat.get('name')} ({node.state} {seat.get('chamber')} "
                             f"{seat.get('district')}, {seat.get('id')}): "
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


def _apply_settled(links):
    """Read ``overrides.IDENTITY_JOINS``: a person's evidenced word that two
    cards are one person (``same``) or two (a namesake), keyed on both
    cards' keys as the build's report names them. An entry with no
    evidence or day is an error and settles nothing (rule 105)."""
    from . import overrides

    for pair, entry in sorted(getattr(overrides, "IDENTITY_JOINS", {}).items()):
        entry = entry or {}
        if (not isinstance(pair, tuple) or len(pair) != 2 or "same" not in entry
                or not entry.get("evidence") or not re.match(r"^\d{4}-\d{2}-\d{2}$",
                                                              str(entry.get("read") or ""))):
            links.problems.append((
                "error", "identity-join-unevidenced",
                f"overrides.IDENTITY_JOINS {pair!r} needs both cards' keys, \"same\", the "
                "evidence and the day it was read; it settles nothing (rule 105)", [str(pair)]))
            continue
        links.settled_pairs[frozenset(pair)] = dict(entry, pair=pair)


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
                f"overrides.IDENTITY_JOINS {entry['pair']!r}: "
                + ", ".join(k for k, n in ((a_key, a), (b_key, b)) if not n)
                + " is no card this build makes; the entry settles nothing", list(entry["pair"])))
            continue
        together = links._find(a.key) == links._find(b.key)
        if entry["same"]:
            if together:
                links.problems.append((
                    "warn", "stale-identity-join",
                    f"overrides.IDENTITY_JOINS {entry['pair']!r}: the two cards are joined by "
                    f"ids or a second source already ({links.joined_by.get(pair) or 'joined'}); "
                    "the entry is no longer needed", list(entry["pair"])))
            else:
                links._union(a.key, b.key, "an evidenced overrides.IDENTITY_JOINS entry")
        elif together:
            links.problems.append((
                "warn", "identity-join-contradicted",
                f"overrides.IDENTITY_JOINS {entry['pair']!r} says two people, but the build joins "
                f"the two cards ({links.joined_by.get(pair) or 'through another card'}): a person "
                "must look again", list(entry["pair"])))
        elif not look_alike(a.name, b.name):
            links.problems.append((
                "warn", "stale-identity-join",
                f"overrides.IDENTITY_JOINS {entry['pair']!r}: {a.name} and {b.name} no longer "
                "share a name, so there is no look-alike to settle", list(entry["pair"])))


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
        from_history(node, person["id"], _wikidata(person), article=person.get("wikipedia"))

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
    links.legislators = legislators or {}
    links.titles = titles
    _apply_settled(links)
    _join_by_ids(links)
    _join_officers(links, officers)
    if legislators:
        _join_legislators(links, legislators, titles)
    _join_settled(links)
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
