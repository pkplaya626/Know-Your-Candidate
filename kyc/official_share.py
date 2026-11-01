"""Share pages for the federal officials and judges (rule 96, TECH-09).

The President, the Vice President, the Cabinet and every federal judge open
in the officials' dialog (``assets/kyc-official.js``) behind a fragment
(``federal/index.html#/official/<id>``, ``courts/<court>.html#/official/<id>``),
which every crawler drops: a shared official unfurled as the home page's
card, whose image says "who is running in 2026". So the build writes one
small page per official, ``o/<id>.html``, as it does per profile and race
(kyc/share.py): its own title, description, canonical address and image,
the facts in plain text, and a link to the view that
``assets/kyc-share.js`` follows at once for a reader with scripts.

No official is a profile (rule 27): these pages are their own folder, never
counted among anyone who sits in Congress or runs for it.

The words are the dialog's own, from one table (``shareWords`` in
kyc-official.js; :func:`share_words` here). The render suite compares the
two for every official on every build, and asks every case in
``tests/fixtures/official_share_words.json`` of the page code; a judge's
service is said as the dialog says it, the FJC directory's and the courts'
list of vacancies side by side where they differ (rule 82), with the
President who appointed them and never a party.

The image is a photograph only by a route the dialog already shows it by:
the White House's photograph of the President, the Vice President or a
Cabinet officer (one of the sizes it serves of that one file, rule 42, or
the smaller copy made here of a heavy one, at its absolute address on the
site's one hostname, rules 21 and 101), and a judge's or a justice's
portrait as ``judge_links`` records it, a Commons file with its licence
(rules 82 and 87). The credit the dialog prints is written under it. A
portrait without a recorded licence (the Court's own) is not unfurled: the
site's card stands.

Nothing here is dated by the build, and an unchanged page is not rewritten
(``emit.write_state_pages``).
"""

import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal

from .share import _e, _https, _page

OFFICIAL_DIR = "o"

# The dialog's "Where this comes from" words, by kind (``SOURCES`` in
# kyc-official.js). One table on each side; the render suite compares them.
SOURCES = {
    "leader": ("The term’s dates and party are from congress-legislators’ record of executive "
               "terms; the portrait is the White House’s."),
    "officer": ("Listed by the White House among the President’s Cabinet; checked on the "
                "office’s own page and against the Senate’s roll-call votes. A Cabinet officer is "
                "shown without a party."),
    "former": ("The Cabinet’s changes since the term began: who held each office from Wikidata, "
               "checked against the person’s Wikipedia article, and the Senate’s roll-call votes. A "
               "Cabinet officer is shown without a party."),
    "judge": "Federal Judicial Center, Biographical Directory of Article III Federal Judges",
}

WORDS_TABLE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                           "official_share_words.json")

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")
_SHORT_MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.",
                 "Oct.", "Nov.", "Dec.")
# The largest size a share image is taken at: an unfurl draws a "summary"
# card's image at a few hundred pixels.
SHARE_IMAGE_MAX = 640


def official_path(oid):
    """``o/<id>.html``, relative to the site's root."""
    return f"{OFFICIAL_DIR}/{oid}.html"


# ----------------------------------------------------------------- words

def date_words(iso):
    """``KYC.dateWords``: "2026-10-15" -> "Oct. 15, 2026", anything that is
    not an ISO date as it was."""
    text = "" if iso is None else str(iso)
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:$|T)", text)
    if not match or not 1 <= int(match.group(2)) <= 12 or not 1 <= int(match.group(3)) <= 31:
        return text
    return f"{_SHORT_MONTHS[int(match.group(2)) - 1]} {int(match.group(3))}, {match.group(1)}"


def when_text(when):
    """``whenText``: an agreed date at its precision."""
    if not when or not when.get("date"):
        return ""
    if when.get("precision") == "month":
        return f"{_MONTHS[int(when['date'][5:7]) - 1]} {when['date'][:4]}"
    return date_words(when["date"])


def left_text(row):
    """``leftText``: "Left office Feb. 13, 2025", or why no day is given."""
    verb = "Acting service ended" if row.get("acting") else "Left office"
    end = row.get("end") or {}
    if end.get("shown"):
        return f"{verb} {when_text(end['shown'])}"
    if end.get("overlap"):
        return f"{verb}; the date is not shown: both sources put it after the successor took office"
    return verb + "; " + ("the sources differ on the date" if end.get("differs")
                          else "the date is not in both sources")


def judge_status(judge):
    """``judgeStatus``: senior by the courts' list and active by the
    directory are both said (rule 82)."""
    if judge.get("retiredJustice"):
        return "Retired justice, not a member of the Court"
    if judge.get("status") == "senior":
        return "Senior status"
    if judge.get("listedSenior"):
        return (f"Senior status from {date_words(judge['listedSenior'].get('since'))} by the "
                "courts’ list of vacancies; the FJC directory still lists active service")
    return "Active service"


def nominated_parts(to):
    """``nominatedParts``: a nomination to another court, in the future
    tense, the court's name between so a page can link it."""
    return ["Nominated to the ", re.sub(r"^U\.S\. ", "", str(to.get("name"))),
            (f" on {date_words(to['nominated'])}" if to.get("nominated") else "")
            + ", pending in the Senate, as the courts’ list of announced vacancies has it"]


# Leaving the seat, as the courts' list of announced vacancies has it
# (``LEAVING`` in kyc-official.js; vacancies.announced_departures).
LEAVING = {"Senior": "Will take senior status", "Retired": "Will retire",
           "Resigned": "Will resign"}


def leaving_text(leaving):
    """``leavingText``: the future tense, or "" for none."""
    said = LEAVING.get((leaving or {}).get("reason"))
    return f"{said}, as the courts’ list of announced vacancies has it" if said else ""


def court_names():
    from .federal_courts import COURTS
    return {cid: court["name"] for cid, court in COURTS.items()}


def share_words(found, courts=None):
    """``shareWords``: every word the dialog's head gives *found*
    (``{"kind", "person", "office"}``), each "" where it says none."""
    courts = court_names() if courts is None else courts
    person = found["person"]
    kind = found["kind"]
    out = {"kind": "", "office": "", "inLaw": "", "status": "", "party": "", "appointedBy": "",
           "nominated": "", "leaving": "", "source": SOURCES.get(kind, "")}
    if kind == "leader":
        out["kind"] = person.get("office") or ""
        out["party"] = person.get("party") or ""
        out["status"] = (f"In office since {date_words(person.get('since') or '')}; term ends "
                         f"{date_words(person.get('until') or '')}")
    elif kind == "officer":
        office = found.get("office") or {}
        out["kind"] = office.get("body") or ""
        out["office"] = person.get("title") or office.get("office") or ""
        if person.get("title") and person["title"] != office.get("office"):
            out["inLaw"] = f"The office in law: {office.get('office')}"
        if (person.get("page") or {}).get("acting"):
            out["status"] = "Acting"
    elif kind == "former":
        held = person.get("held") or []
        last = held[-1] if held else {}
        out["kind"] = "Former, this term"
        out["office"] = ("Acting " if last.get("acting") else "") + (last.get("office") or "")
        out["status"] = left_text(last)
    else:
        first = (person.get("seats") or [{}])[0]
        name = courts.get(first.get("court"))
        out["source"] = SOURCES["judge"]
        out["kind"] = "Supreme Court" if person.get("justice") else (name or "Federal judge")
        out["office"] = (person["justice"].get("role") if person.get("justice")
                         else first.get("title") or "Judge")
        out["status"] = judge_status(person)
        out["appointedBy"] = first.get("appointedBy") or ""
        if person.get("nominatedTo"):
            out["nominated"] = "".join(nominated_parts(person["nominatedTo"]))
        out["leaving"] = leaving_text(person.get("leaving"))
    return out


# --------------------------------------------------------- who is shared

def officials(fed, per_court):
    """``{id: {"kind", "person", "office", "court"}}``: everyone the
    officials' dialog answers to (``officials()`` in kyc-official.js), in
    the page's order. *court* is the court whose page shows them (its file
    holds their record); None for the federal government's page, which
    holds the President, the Vice President, the Cabinet, who left it this
    term, and the Supreme Court."""
    out = {}
    for key in ("president", "vicePresident"):
        if fed.get(key):
            out[fed[key]["id"]] = {"kind": "leader", "person": fed[key], "office": None, "court": None}
    for office in fed.get("offices") or []:
        if office.get("holder"):
            out[office["holder"]["id"]] = {"kind": "officer", "person": office["holder"],
                                           "office": office, "court": None}
    for person in fed.get("former") or []:
        out.setdefault(person["id"], {"kind": "former", "person": person, "office": None,
                                      "court": None})
    scotus = fed.get("supremeCourt") or {}
    for judge in (scotus.get("members") or []) + (scotus.get("retired") or []):
        out[judge["id"]] = {"kind": "judge", "person": judge, "office": None, "court": None}
    # A judge of the other courts, on the page of the court their first
    # seat is on where its file lists them, else the first that does (a
    # judge on several courts is one person).
    listing = {}
    for cid, court in (per_court or {}).items():
        for judge in (court.get("judges") or []) + (court.get("retired") or []):
            listing.setdefault(judge["id"], {})[cid] = judge
    for jid, held in listing.items():
        if jid in out:
            continue
        first = next(iter(held.values()))
        seat = ((first.get("seats") or [{}])[0]).get("court")
        cid = seat if seat in held else next(iter(held))
        out[jid] = {"kind": "judge", "person": held[cid], "office": None, "court": cid}
    return out


# --------------------------------------------------------------- picture

def weight_words(n):
    """``weightWords``: "12.4 MB", "820 KB". Rounded as ``toFixed`` rounds,
    the exact value of the double half up: Python's own format rounds a tie
    to even, and 2,250,000 bytes would read "2.2 MB" here and "2.3 MB" in
    the dialog."""
    n = float(n or 0)
    if n >= 1e6:
        tenths = Decimal(n / 1e6).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return re.sub(r"\.0$", "", str(tenths)) + " MB"
    return f"{max(1, int(n / 1e3 + 0.5))} KB"


def credit_html(credit):
    """``KYC.photoCreditHtml``: one line crediting a photograph, escaped,
    linked where the credit holds the address; "" for none."""
    if not credit or not (credit.get("by") or credit.get("licence") or credit.get("host")):
        return ""

    def anchor(href, text):
        if re.match(r"https?://", str(href or "")):
            return (f'<a href="{_e(href)}" target="_blank" rel="noopener noreferrer">'
                    f"{_e(text)}</a>")
        return _e(text)

    parts = []
    if credit.get("by"):
        parts.append(_e(credit["by"]) if credit.get("via") else anchor(credit.get("page"), credit["by"]))
    elif credit.get("authorUnrecorded"):
        parts.append("author not recorded on Commons")
    elif credit.get("host"):
        parts.append("from " + _e(credit["host"]))
    if credit.get("licence"):
        parts.append(anchor(credit.get("licenceUrl"), credit["licence"]))
    year = (f" ({credit['year']})" if not credit.get("dated")
            and re.fullmatch(r"\d{4}", str(credit.get("year") or "")) else "")
    line = f"Photo{year}: " + ", ".join(parts) if parts else f"Photo{year}"
    if credit.get("via"):
        line += (", via " if parts else " via ") + anchor(credit.get("page"), credit["via"])
    if credit.get("dated"):
        line = _e(credit["dated"]) + ". " + line
    if credit.get("copyOf"):
        original = "the original file" + (f" ({weight_words(credit['copyOfBytes'])})"
                                          if credit.get("copyOfBytes") else "")
        line += (f'<span class="photo-copy-note" data-copy-of="{_e(credit["copyOf"])}">; a smaller '
                 f"copy made by this site of {anchor(credit['copyOf'], original)}</span>")
    return line


def _largest(sizes):
    """The largest of ``[(width, url)]`` an unfurl needs, else the smallest."""
    sizes = [(w, u) for w, u in sizes if isinstance(w, (int, float)) and _https(u)]
    if not sizes:
        return None
    fits = [s for s in sizes if s[0] <= SHARE_IMAGE_MAX]
    return (max(fits) if fits else min(sizes))[1]


def picture(found, host=None):
    """``(image URL, credit)`` for *found*'s share page, or ``(None, None)``
    for the site's card. Only what the dialog shows, by its route: the White
    House's photograph (its sizes of that one file, or the smaller copy
    made here at its absolute address on *host*), or a judge's Commons
    portrait with its licence recorded (``judge_links``)."""
    person = found["person"]
    photo = person.get("photo")
    if photo:
        copy = person.get("photoCopy") or {}
        if copy.get("src") and copy.get("of") == photo:
            if not host:
                return None, None
            credit = {"by": "The White House", "copyOf": photo}
            if copy.get("ofBytes"):
                credit["copyOfBytes"] = copy["ofBytes"]
            return f"https://{host}/{copy['src']}", credit
        sizes = [(s[1], s[0]) for s in person.get("photoSet") or []
                 if isinstance(s, (list, tuple)) and len(s) == 2]
        url = _largest(sizes) or (photo if _https(photo) else None)
        return (url, {"by": "The White House"}) if url else (None, None)
    portrait = person.get("portrait") or {}
    if found["kind"] != "judge" or not portrait.get("licence") or not portrait.get("url"):
        return None, None
    sizes = [(s[0], s[1]) for s in portrait.get("set") or []
             if isinstance(s, (list, tuple)) and len(s) == 2]
    url = _largest(sizes) or (portrait["url"] if _https(portrait["url"]) else None)
    if not url or "Special:" in url or not url.startswith("https://upload.wikimedia.org/"):
        return None, None
    year = portrait.get("year") or ""
    return url, {"by": portrait.get("by"), "licence": portrait["licence"],
                 "licenceUrl": portrait.get("licenceUrl"), "page": portrait.get("source"),
                 "via": "Wikimedia Commons", "authorUnrecorded": bool(portrait.get("authorUnrecorded")),
                 "year": year,
                 "dated": f"Official portrait, {year}" if year and portrait.get("route") == "official"
                 else ""}


# ----------------------------------------------------------------- pages

def describe(found, words):
    """``(og title, description)`` for *found*'s share page: the name and
    the words of the dialog's head (:func:`share_words`), and nothing of
    its own - a description cut short by an unfurler must not read as more
    than the dialog says. A former officer's leads with "Former, this
    term", or "Pam Bondi: Attorney General" would unfurl as though she
    still held the office."""
    name = found["person"].get("name") or ""
    kind = found["kind"]

    def sentence(*parts):
        return " ".join(f"{p}." for p in parts if p)

    if kind == "leader":
        lead = f"{name} ({words['party']})" if words["party"] else name
        return lead, f"{lead}, {words['kind']}: {words['status']}."
    if kind == "officer":
        return name, sentence(f"{name}: {words['office']}, {words['kind']}", words["status"])
    if kind == "former":
        return name, sentence(f"{name} — {words['kind']}: {words['office']}", words["status"])
    said = words["status"] + (f"; appointed by {words['appointedBy']}" if words["appointedBy"] else "")
    return name, sentence(f"{name}: {words['office']}, {words['kind']}", said, words["leaving"],
                          words["nominated"])


def _view(found, oid, courts):
    """``(the view's address, its link's words, what a reader without
    scripts can read instead)``. The court's page lists its judges, retired
    ones too, in plain text; the federal page lists who serves now, so a
    page about someone who left the Cabinet, or a retired justice, says it
    does not list them."""
    if found.get("court"):
        cid = found["court"]
        name = courts.get(cid) or cid
        return (f"../courts/{cid}.html#/official/{oid}",
                f"Open their record on the {name}’s page",
                f'<a href="../courts/{_e(cid)}.html">the {_e(name)}’s page</a> lists its '
                "judges in plain text.")
    gone = ("those who have left the Cabinet this term" if found["kind"] == "former"
            else "the retired justices" if found["person"].get("retiredJustice") else "")
    return (f"../federal/index.html#/official/{oid}",
            "Open their record on the federal government’s page",
            '<a href="../federal/index.html">the federal government’s page</a> lists the '
            "President, the Vice President, the Cabinet and the Supreme Court in plain text"
            + (f", though not {gone}." if gone else "."))


def render_official(oid, found, host, courts=None):
    """``o/<id>.html``."""
    courts = court_names() if courts is None else courts
    words = share_words(found, courts)
    name = found["person"].get("name") or ""
    og_title, description = describe(found, words)
    image, credit = picture(found, host)
    body = [f'<p class="share-kind">{_e(words["kind"])}</p>']
    if words["office"]:
        body.append(f'<p class="share-office"><strong>{_e(words["office"])}</strong></p>')
    if words["inLaw"]:
        body.append(f'<p class="share-in-law faint">{_e(words["inLaw"])}</p>')
    if words["party"]:
        body.append(f'<p class="share-party">{_e(words["party"])}</p>')
    if words["status"]:
        body.append(f'<p class="share-status"><strong>{_e(words["status"])}</strong></p>')
    if words["appointedBy"]:
        body.append(f'<p class="share-appointed">Appointed by {_e(words["appointedBy"])}</p>')
    if words["nominated"]:
        body.append(f'<p class="share-nominated">{_e(words["nominated"])}.</p>')
    if words["leaving"]:
        body.append(f'<p class="share-leaving">{_e(words["leaving"])}.</p>')
    if image:
        body.append(f'<p class="share-photo-credit faint">{credit_html(credit)}</p>')
    source = words["source"]
    body.append(f'<p class="share-source faint">Source: {_e(source)}'
                + ("" if source.endswith(".") else ".") + "</p>")
    view, view_words, fallback = _view(found, oid, courts)
    return _page(
        host, official_path(oid),
        title=_e(f"{name} — Know Your Candidate"),
        description=_e(description),
        og_type="profile",
        og_title=_e(og_title),
        image=image,
        image_alt=f"Portrait of {name}",
        kind="official",
        heading=_e(name),
        body="\n".join(body),
        view=_e(view),
        view_words=_e(view_words),
        fallback=fallback,
    )


def render_all(fed, per_court, host):
    """``{path relative to the site: html}`` for every official, or ``{}``
    without the federal build."""
    if not fed:
        return {}
    courts = court_names()
    return {official_path(oid): render_official(oid, found, host, courts)
            for oid, found in officials(fed, per_court).items()}


def ids(fed, per_court):
    """Every official's id, for the sitemap."""
    return list(officials(fed, per_court)) if fed else []


# ------------------------------------------------- every case, both sides

def _when(date, precision="day"):
    return {"shown": {"date": date, "precision": precision}}


def words_table():
    """Every case of :func:`share_words`, with its answer: what the render
    suite asks ``KYC.official.shareWords`` about, row by row
    (``[kind, person, office, words]``)."""
    cases = []
    leader = {"id": "x-a", "name": "A", "office": "President of the United States",
              "party": "Republican", "since": "2025-01-20", "until": "2029-01-20"}
    cases.append(("leader", leader, None))
    cases.append(("leader", dict(leader, party=None, until=None), None))
    office = {"office": "Secretary of the Treasury", "body": "Department of the Treasury"}
    for title in ("Secretary of the Treasury", "Treasury Secretary", None):
        for acting in (False, True):
            holder = {"id": "x-b", "name": "B", "title": title,
                      "page": {"acting": True} if acting else {}}
            cases.append(("officer", holder, office))
    ends = [_when("2025-02-13"), _when("2025-03-01", "month"), _when("2025", "year"),
            {"shown": None, "overlap": True}, {"shown": None, "differs": True}, {"shown": None}, None]
    for acting in (False, True):
        for end in ends:
            row = {"office": "Secretary of Labor", "acting": acting, "end": end}
            cases.append(("former", {"id": "x-c", "name": "C", "held": [row]}, None))
    cases.append(("former", {"id": "x-c", "name": "C", "held": []}, None))
    seat = {"court": "ak", "title": "Judge", "appointedBy": "Barack Obama"}
    judges = [
        {"status": "active", "seats": [seat]},
        {"status": "senior", "seats": [seat]},
        {"status": "active", "listedSenior": {"since": "2026-10-05"}, "seats": [seat]},
        {"status": "active", "seats": [dict(seat, court="ca5", title="Chief Judge")],
         "nominatedTo": {"id": "scotus", "name": "U.S. Court of Appeals for the Fifth Circuit",
                         "nominated": "2026-09-30", "asOf": "2026-10-05"}},
        {"status": "active", "seats": [seat],
         "nominatedTo": {"id": "ca9", "name": "Court of Appeals for the Ninth Circuit",
                         "asOf": "2026-10-05"}},
        {"status": "active", "seats": [dict(seat, court="scotus", title="Chief Justice")],
         "justice": {"role": "Chief Justice"}},
        {"status": "senior", "retiredJustice": True,
         "seats": [dict(seat, court="scotus", title="Associate Justice")],
         "justice": {"role": "Associate Justice"}},
        {"status": "active", "seats": [seat], "leaving": {"reason": "Senior"}},
        {"status": "senior", "seats": [seat], "leaving": {"reason": "Retired"}},
        {"status": "active", "seats": [seat], "leaving": {"reason": "Resigned"}},
        {"status": "active", "seats": [seat], "leaving": {"reason": "Deceased"}},
        {"status": "active", "seats": [{"court": "zz-unknown"}]},
        {"status": "active", "seats": []},
    ]
    for judge in judges:
        cases.append(("judge", dict(judge, id="fjc-1", name="D"), None))
    courts = court_names()
    # A copy's credit gives its original's weight: the ties round alike on
    # both sides (2,250,000 bytes is "2.3 MB" in the dialog).
    weights = (0, 1, 499, 500, 820_400, 999_499, 999_500, 1_000_000, 1_050_000, 2_250_000,
               2_350_000, 2_750_000, 12_400_000, 12_449_999, 12_450_000)
    return {"cases": [[kind, person, office, share_words({"kind": kind, "person": person,
                                                           "office": office}, courts)]
                      for kind, person, office in cases],
            "weights": [[n, weight_words(n)] for n in weights]}


def words_table_text():
    return json.dumps(words_table(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write_words_table(path=WORDS_TABLE):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(words_table_text())
    return path
