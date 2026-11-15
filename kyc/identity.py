"""Who appears on this site in more than one role, joined by ids (rule 104).

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


def names_agree(a, b):
    """Whether two records an id ties name one person: the same surname and
    the same first initial ("Janet Trafton Mills" and "Janet Mills", "J.D.
    Vance" and "JD Vance"). A check on a join by id, never a join itself."""
    x, y = _words(a), _words(b)
    if not x or not y:
        return False
    if x[-1] != y[-1]:
        # A hyphenated or two-word surname written one way and the other.
        if not (x[-1] in y or y[-1] in x):
            return False
    return x[0][0] == y[0][0]


def look_alike(a, b):
    """The same first and last name, folded: two records a reader would take
    for one person, which only an id or a second source may join."""
    x, y = _words(a), _words(b)
    x = [w for w in x if len(w) > 1]
    y = [w for w in y if len(w) > 1]
    return bool(x and y) and x[0] == y[0] and x[-1] == y[-1]


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
                 "place", "history")

    def __init__(self, key, kind, name, state, record, role, photo=False, history=None):
        self.key, self.kind, self.name, self.state = key, kind, name, state
        self.record, self.role, self.photo = record, role, bool(photo)
        self.ids = {"bioguide": set(), "wikidata": set(), "fec": set()}
        self.history = history or {}

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

    def say(when):
        lead = _cap(share._role(person, when))
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


def departed_role(row):
    from .pages import date_words, short_name

    chamber = row.get("chamber") or "House"
    if chamber == "Senate":
        seat = short_name(row.get("state"))
    else:
        district = row.get("district")
        seat = f"{row.get('state')}-{district if district not in (None, '', 0, '0') else 'AL'}"
    words = f"Left the U.S. {chamber} on {date_words(row.get('left'))}, as the member for {seat}"
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


def judge_role(judge, court_id, court_name):
    first = (judge.get("seats") or [{}])[0]
    title = (judge.get("justice") or {}).get("role") or first.get("title") or "Judge"
    where = "the Supreme Court of the United States" if court_id == "scotus" else (
        court_name if str(court_name or "").startswith("the ") else f"the {court_name}")
    jid = judge["id"]
    href = (f"federal/index.html#/official/{jid}" if court_id == "scotus"
            else f"courts/{court_id}.html#/official/{jid}")
    return {"kind": "judge", "id": jid, "words": f"{title} of {where}", "href": href,
            "view": f"#/official/{jid}", "court": court_id, "share": f"o/{jid}.html"}


def governor_role(code, gov):
    from .pages import governor_of

    words = governor_of(code) + (f", in office since {gov['since']}" if gov.get("since") else "")
    gid = gov["id"]
    return {"kind": "governor", "id": gid, "state": code, "words": words,
            "href": f"states/{code.lower()}.html#/official/{gid}", "view": f"#/official/{gid}",
            "share": f"o/{gid}.html"}


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


def officer_role(code, key, off):
    from .voting_dates import place

    title = off.get("title") or {"lt": "Lieutenant Governor", "ag": "Attorney General",
                                 "sos": "Secretary of State"}[key]
    return {"kind": "officer", "id": f"{code}-{key}", "state": code,
            "words": f"{title} of {place(code)}",
            "href": f"states/{code.lower()}.html#state-government",
            "share": f"states/{code.lower()}.html"}


def legislator_role(code, member, title):
    """"Member of the Texas House of Representatives, district 49": the
    legislature page's chamber, named with its state, and the district the
    roster gives."""
    from .pages import short_name

    district = member.get("district")
    words = f"Member of the {short_name(code)} {title}" + (f", district {district}" if district else "")
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


def _join_by_ids(links):
    """Join every two nodes that hold one id, where their names agree."""
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
                if names_agree(first.name, other.name):
                    links._union(first.key, other.key, f"{scheme} {value}")
                else:
                    links.problems.append((
                        "warn", "identity-names-disagree",
                        f"{first.kind} {first.name} and {other.kind} {other.name} share the "
                        f"{scheme} id {value} but their names disagree; neither card names the "
                        "other (rule 104)", [first.key, other.key]))


def _join_officers(links, officers):
    """Each officer card to the people whose corroborated record holds that
    office open in that state, where the card's name names them (rule 56)."""
    from .pages import short_name

    people = [n for n in links.nodes.values() if n.kind in ("profile", "candidate", "governor")]
    for node in officers:
        code, key = node.state, node.key.rsplit(":", 1)[-1]
        for person in people:
            if person.state != code:
                continue
            held = [r for r in _history_rows(person.record if person.kind != "profile"
                                             else person.record)
                    if r.get("current") and OFFICE_WORDS[key].search(r.get("office") or "")
                    and not _NOT_THE_OFFICE.search(r.get("office") or "")
                    and (r.get("where") or short_name(code)) == short_name(code)]
            named = office_names(person.name, node.name)
            if held and named:
                links._union(node.key, person.key,
                             f"{held[0]['office']} in the record; the officer card names them")
            elif look_alike(person.name, node.name):
                links.problems.append((
                    "warn", "identity-look-alike",
                    f"{node.name} ({node.role['words']}) and {person.kind} {person.name} share a "
                    "name, but " + ("no corroborated record of theirs holds the office"
                                    if not held else "the card's name does not name them by "
                                    "rule 56's test") + "; neither card names the other (rule 104)",
                    [node.key, person.key]))


def _join_legislators(links, legislators, chamber_titles):
    """Each candidate for Congress or governor who sits in their state's
    legislature, by rule 24's join (``nominee_photos.legislator_for``)."""
    from .nominee_photos import legislator_for

    history = links.history_cache or {}
    for node in list(links.nodes.values()):
        if node.kind not in ("profile", "candidate"):
            continue
        record = node.record
        if node.kind == "profile" and not record.get("isCandidate"):
            continue
        person = {"id": record.get("id"), "name": node.name, "state": node.state,
                  "wikipedia": record.get("wikipedia")}
        member, _why = legislator_for(person, history, legislators)
        if not member:
            continue
        code = node.state
        title = chamber_titles.get((code, member.get("chamber"))) or "Legislature"
        key = f"legislator:{code}:{member.get('id')}"
        leg = links.nodes.get(key) or links.add(Node(
            key, "legislator", member.get("name"), code, member,
            legislator_role(code, member, title), photo=_photo(member, "image")))
        links._union(key, node.key, "legislature join (rule 24)")


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

    def from_history(node, key):
        entry = hist.get(key) or {}
        node.add("bioguide", entry.get("bioguide"))

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
        from_history(node, person["id"])

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
        from_history(node, person["id"])
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
        from_history(node, person["id"])
    for person in fed.get("former") or []:
        if not person.get("id") or f"official:{person['id']}" in links.nodes:
            continue
        held = (person.get("held") or [{}])[-1]
        words = f"Former, this term: {_us(('Acting ' if held.get('acting') else '') + (held.get('office') or ''))}"
        node = links.add(Node(f"official:{person['id']}", "official", person.get("name"), None,
                              person, official_role(person["id"], words)))
        node.add("wikidata", (person.get("links") or {}).get("wikidata") or held.get("wikidata"))
        from_history(node, person["id"])

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
    for judge, cid, cname in judges:
        if not judge.get("id") or f"judge:{judge['id']}" in links.nodes:
            continue
        item = judge_items.get(judge["id"])
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
        if gov.get("id"):
            node = links.add(Node(f"governor:{gov['id']}", "governor", gov.get("name"), code, gov,
                                  governor_role(code, gov), photo=_photo(gov, "headshot")))
            node.add("wikidata", gov.get("wikidata") or _wikidata(gov))
            from_history(node, gov["id"])
        office = ((entry.get("ballot2026") or {}).get("offices") or {}).get("governor") or {}
        if office.get("up"):
            for person in ((office.get("candidates") or {}).get("candidates") or []):
                if not person.get("id"):
                    continue
                node = links.add(Node(f"candidate:{person['id']}", "candidate", person.get("name"),
                                      code, person, candidate_role(code, person),
                                      photo=_photo(person, "photo")))
                node.add("bioguide", person.get("member"))
                node.add("wikidata", _wikidata(person))
                from_history(node, person["id"])
        for key in OFFICER_KEYS:
            off = entry.get(key)
            if _named_officer(off):
                officers.append(links.add(Node(f"officer:{code}:{key}", "officer", off.get("name"),
                                               code, off, officer_role(code, key, off),
                                               photo=_photo(off, "photo"))))

    _join_by_ids(links)
    _join_officers(links, officers)
    titles = {}
    for code, payload in (legislatures or {}).items():
        for chamber, info in ((payload or {}).get("chambers") or {}).items():
            titles[(code, chamber)] = info.get("title")
    if legislators:
        _join_legislators(links, legislators, titles)
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
                        or _same_card(a, b)):
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
                    "source; neither card names the other (rule 104)", [a.key, b.key]))


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
                    "naming the others (rule 104)",
                    [f"{name}: " + ", ".join(k for _kind, k in keys) + " (" + "; ".join(why) + ")"
                     for name, keys, why in rows]))
    pictured = photo_differences(links)
    if pictured:
        out.append(("info", "identity-photo-differs",
                    f"{len(pictured)} joined people have a photograph on one card and none on "
                    "another; no photograph is borrowed (rule 104)", pictured))
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
