"""State legislators' portraits, from each legislature's own records.

Open States has no usable portrait for about a thousand of the 7,300
sitting state legislators (audit 2026-10-17, STATEGOV-13; the photo
research of 2026-10-19): it stored none, or a search engine's thumbnail, or
an address the legislature no longer serves. Most legislatures publish one
all the same, on a page or in a record of their own. ``python
build_profile_site.py legphotos`` reads them, state by state, and writes
``data/legislator_photos.json``; the legislature pages show one only where
Open States has nothing usable (``legislature._person``).

What reaches a page (rules 24, 51 and 87, and the owner's decision of
2026-10-19):

- A photograph is taken only from a page or record the legislature serves
  for this member, reached by the legislature's own key for them (Montana's
  roster id, New Jersey's roster id, Indiana's lpid, a member page Open
  States links) or by chamber and district with their surname agreeing.
  Never a search, never an address built from a name.
- The source names the member beside the image: the record that names the
  file, the image's alt text, its file name or the page's heading. That
  wording is kept as ``evidence`` and ``validate`` fails an entry without
  it, or whose evidence does not carry the member's surname.
- A file keyed by seat (Louisiana's ``rep<n>.jpg``, Connecticut's
  ``legpics/<code>.png``) may still be a predecessor's photograph the first
  time it is read. It is taken only when the server dates it on or after
  the member's arrival (``SEAT_MARGIN_DAYS`` before it: new members are
  photographed between the election and the swearing-in), and never again
  once the seat's holder changes while the file does not (``seatFiles``).
- Only a rendition the source itself offers, within 300 KB and 1,200 px
  (``photos.MAX_PORTRAIT_BYTES`` / ``MAX_PORTRAIT_PX``): no resizing and no
  image service. A member whose legislature offers only heavier files is
  left without one and counted (``oversized``). Of the renditions offered,
  the smallest at least ``TARGET_WIDTH`` wide, what the card needs on a 2x
  screen.
- A landscape frame is not a portrait (rule 38).
- Each photograph is credited to the legislature, linked to the page it
  was read from (rule 87).

Network reads pace one request a second to each host. A read that fails,
or concludes nothing, keeps the last good entry (rule 8); only a definite
answer - the file is gone (404, 410), the page names someone else - takes
one away.
"""

import concurrent.futures
import datetime
import gzip
import hashlib
import html
import html.parser
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "legislator_photos.json")
SOURCE = "each state legislature's own member pages and records"

# The card draws a portrait 56 CSS px wide (kyc.css .leg-photo): 112 on a
# 2x screen. Of the renditions a source offers, the smallest this wide.
TARGET_WIDTH = 112
# An entry younger than this is not read again.
RECHECK_DAYS = 14
# An entry not confirmed for this long is reported by the build.
STALE_DAYS = 60
# A seat-keyed file dated this long before the member's arrival is still
# theirs: Connecticut and Louisiana photograph members-elect.
SEAT_MARGIN_DAYS = 90
PAUSE = 1.0
TIMEOUT = 30
# A host that gave no answer this many times running is not asked again in
# the same run.
DOWN_AFTER = 3
UA = {"User-Agent": "Mozilla/5.0 (compatible; know-your-candidate/2.1; civic data project)",
      "Accept-Encoding": "gzip"}
# A browser's user agent, for the hosts that answer a script with an empty
# shell (Indiana's IGA, rule 57's "answers only a browser").
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
              "Accept-Encoding": "gzip"}

# Hosts that serve a legislature's files without being its pages' host:
# Oklahoma's House keeps its uploads on a CloudFront distribution its own
# pages name (read 2026-10-19).
EXTRA_PHOTO_HOSTS = {
    "OK": ("dgbf0g52sf9l0.cloudfront.net",),
}

# Hosts that are a party's or a campaign's, never the legislature's (rule
# 87): refused even where a page on the legislature's site links them.
PARTY_HOSTS = re.compile(r"(gop|dems|democrats|republicans|caucus|asmdc|asmrc)", re.I)


class LegPhotoError(RuntimeError):
    """The cache cannot be read or written."""


# ------------------------------------------------------------------ names

def fold(text):
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def words(text):
    return re.findall(r"[a-z]+", fold(text))


def surname_words(name):
    from .legislature import surname
    return surname(name)


def given_words(name):
    """The first name's words, run together as well ("T.J." is also "TJ"),
    and a nickname in quotes ("Allen \"Penny\" Demar" is also Penny)."""
    parts = (name or "").split()
    out = set(words(parts[0])) if parts else set()
    if parts and len(words(parts[0])) > 1:
        out.add("".join(words(parts[0])))
    out |= set(words(" ".join(re.findall(r"[\"“]([^\"”]+)[\"”]", name or ""))))
    return out


def _same_given(mine, theirs):
    """One given name written two ways: the same word, or a short form of
    three letters or more that the longer one starts with and outruns by
    four at most ("Dan" and "Daniel", "Pat" and "Patrick"; never "Dan" and
    "Danielle", who may be another member of the family)."""
    if mine == theirs:
        return True
    short, long_ = sorted((mine, theirs), key=len)
    return len(short) >= 3 and long_.startswith(short) and len(long_) - len(short) <= 4


def names_surname(text, name):
    """Every word of the member's surname is a word of *text* (a hyphenated
    or two-word surname is matched by its words), or the surname's letters
    run together are one ("OLaughlin18.jpg" for Cindy O'Laughlin)."""
    sur = surname_words(name)
    have = set(words(text))
    if not sur:
        return False
    return sur <= have or (len(sur) > 1 and surname_joined(name) in have)


def surname_joined(name):
    """The surname's letters, run together: "O'Laughlin" -> "olaughlin"."""
    from .legislature import _SUFFIXES
    parts = [p for p in (name or "").split() if p]
    while parts and set(words(parts[-1])) <= _SUFFIXES:
        parts.pop()
    return "".join(words(parts[-1])) if parts else ""


def names_member(text, name):
    """*text* carries the member's surname and a given name or initial."""
    if not names_surname(text, name):
        return False
    have = set(words(text))
    given = given_words(name)
    return (any(_same_given(g, w) for g in given for w in have)
            or any(g[:1] in have for g in given if g))


def names_in_full(text, name):
    """*text* writes the member's name as a phrase: a given name, up to two
    words, then the surname ("David Nelson", "Representative David R.
    Nelson"). Looser than a heading, so used only beside a file the page's
    own key names (``pick_member_image``)."""
    sur = surname_joined(name)
    if not sur:
        return False
    toks = words(text)
    given = given_words(name)
    for i, tok in enumerate(toks):
        if tok == sur and any(_same_given(g, t) for g in given for t in toks[max(0, i - 3):i]):
            return True
    return False


def legislature_name(code):
    """"Montana Legislature", "Connecticut General Assembly" (rule 75)."""
    from .government_maps import LEGISLATURE_NAME
    from .pages import state_name
    return f"{state_name(code)} {LEGISLATURE_NAME.get(code, 'Legislature')}"


def official_host(code, url):
    """*url* is served by the legislature (``legislature.LEGISLATURE_HOSTS``
    or a host its pages name, ``EXTRA_PHOTO_HOSTS``), never a party's."""
    from .legislature import LEGISLATURE_HOSTS
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    if not host or PARTY_HOSTS.search(host):
        return False
    for h in LEGISLATURE_HOSTS.get(code, ()) + EXTRA_PHOTO_HOSTS.get(code, ()):
        h = h.lstrip(".")
        if host == h or host.endswith("." + h):
            return True
    return False


# ------------------------------------------------------------------- http

class Answer:
    __slots__ = ("status", "headers", "body", "url", "truncated")

    def __init__(self, status, headers=None, body=b"", url="", truncated=False):
        self.status = status
        self.headers = headers or {}
        self.body = body
        self.url = url
        self.truncated = truncated

    def text(self):
        ctype = self.headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", ctype)
        try:
            return self.body.decode(m.group(1) if m else "utf-8", "replace")
        except LookupError:
            return self.body.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text())


class Http:
    """GET, one request at a time to each host, *pause* seconds apart.
    Network failures answer ``status=None`` (concludes nothing)."""

    def __init__(self, pause=PAUSE, timeout=TIMEOUT):
        self.pause = pause
        self.timeout = timeout
        self._locks = {}
        self._last = {}
        self._guard = threading.Lock()
        self._down = {}
        self.requests = 0

    def _lock(self, host):
        with self._guard:
            return self._locks.setdefault(host, threading.Lock())

    def get(self, url, limit=None, browser=False):
        host = urllib.parse.urlsplit(url).hostname or ""
        with self._lock(host):
            if self._down.get(host, 0) >= DOWN_AFTER:
                # A host that has answered nothing several times running
                # (Maine's, which resets every connection) is not asked
                # again in this run: each try costs two timeouts, and its
                # silence concludes nothing either way (rule 8).
                return Answer(None, {}, b"", url)
            wait = self._last.get(host, 0) + self.pause - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                answer = self._get(url, limit, browser)
                if answer.status is None:
                    # One dropped connection is not an answer (rule 8): once more.
                    time.sleep(self.pause * 3)
                    answer = self._get(url, limit, browser)
                self._down[host] = self._down.get(host, 0) + 1 if answer.status is None else 0
                return answer
            finally:
                self._last[host] = time.monotonic()
                self.requests += 1

    def _get(self, url, limit, browser):
        headers = BROWSER_UA if browser else UA
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                info = {k.lower(): v for k, v in response.headers.items()}
                gz = info.get("content-encoding") == "gzip"
                body = response.read() if (limit is None or gz) else response.read(limit + 1)
                if gz:
                    body = gzip.decompress(body)
                truncated = limit is not None and len(body) > limit
                return Answer(response.status, info, body, response.url, truncated)
        except urllib.error.HTTPError as exc:
            return Answer(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, b"", url)
        except Exception:
            return Answer(None, {}, b"", url)


# ------------------------------------------------------------------ weigh

def weigh(http, url):
    """``{"bytes", "width", "height", "sha", "lastModified"}`` of the image
    at *url*; ``{"gone": True}`` for a 404 or 410; ``None`` when it could
    not be told (rule 8). A file over the byte cap is read only that far:
    its size is the server's, or "over the cap"."""
    from .photos import MAX_PORTRAIT_BYTES
    from .portraits import image_size
    ans = http.get(url, limit=MAX_PORTRAIT_BYTES)
    if ans.status in (404, 410):
        return {"gone": True}
    if ans.status != 200 or not ans.headers.get("content-type", "").lower().startswith("image"):
        return None
    size = image_size(ans.body)
    if not size:
        return None
    if ans.truncated:
        length = ans.headers.get("content-length", "")
        total = int(length) if length.isdigit() else MAX_PORTRAIT_BYTES + 1
    else:
        total = len(ans.body)
    out = {"bytes": total, "width": size[0], "height": size[1]}
    if not ans.truncated:
        out["sha"] = hashlib.sha256(ans.body).hexdigest()[:16]
    modified = _http_date(ans.headers.get("last-modified"))
    if modified:
        out["lastModified"] = modified
    return out


def _http_date(value):
    import email.utils
    try:
        return email.utils.parsedate_to_datetime(value).date().isoformat() if value else None
    except (TypeError, ValueError):
        return None


def over_caps(weight):
    from .photos import too_heavy
    return too_heavy(weight)


def landscape(weight):
    """A frame wider than it is tall (a square is a headshot): rule 38."""
    return weight["width"] > weight["height"] * 1.05


# ------------------------------------------------------------------- html

class _Page(html.parser.HTMLParser):
    """The images, title and headings of a page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.title = ""
        self.headings = []
        self.text = ""
        self._in = None
        self._depth = 0
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "img":
            self.images.append(a)
        elif tag in ("br", "div", "p") and self._in:
            self._buf.append(" ")         # "HOUSE<br />DAVID NELSON"
        elif tag in ("title", "h1", "h2"):
            if self._in == tag:
                # A heading inside a heading (Alaska's member page nests
                # an empty <h1> in the one naming the member) is one.
                self._depth += 1
            elif not self._in:
                self._in, self._buf, self._depth = tag, [], 1

    def handle_endtag(self, tag):
        if tag == self._in:
            self._depth -= 1
            if self._depth > 0:
                return
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if tag == "title":
                self.title = self.title or text
            else:
                self.headings.append(text)
            self._in = None

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)


def parse_page(text):
    page = _Page()
    try:
        page.feed(re.sub(r"<!--.*?-->", "", text, flags=re.S))
    except Exception:
        pass
    page.text = strip_text(text)
    return page


def file_words(url):
    """The words of an image address's file name ("Black12.jpg" -> black)."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return words(re.sub(r"\.\w+$", "", path.rsplit("/", 1)[-1]))


def strip_text(markup):
    markup = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", markup, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


# --------------------------------------------------------------- recipes
#
# A recipe reads one state for the *records* given (Open States rows with
# no usable portrait) and returns ``{person id: outcome}``, where an
# outcome is one of:
#   {"candidate": {...}}  an image the legislature names beside the member:
#                         "page", "evidence", "renditions" (smallest
#                         first), "key", and for a seat-keyed file
#                         "seatKeyed" with "holderSince";
#   {"refused": why}      a definite answer that the source shows someone
#                         else, or nothing for this member;
#   absent                nothing could be concluded (rule 8).

def _record_district(record):
    return re.sub(r"^0+(?=\d)", "", (record.get("district") or "").strip())


def _digits(text):
    m = re.search(r"\d+", text or "")
    return str(int(m.group(0))) if m else ""


def read_montana(http, code, records, roster=None, year=0):
    """Montana's roster API, joined on the legislature's own ids from the
    Open States links: the www.legmt.gov/legislators/<id>/ WordPress id
    first, then the lawsId of legislators.legmt.gov/#/legislator/<n> (the
    checker of 2026-10-19 found Tony Tezak's Open States lawsId is not the
    API's, while his WordPress id is)."""
    url = "https://www.legmt.gov/wp-json/legmt/v1/people/legislators"
    ans = http.get(url)
    if ans.status != 200:
        return {}
    try:
        people = ans.json().get("content") or []
    except ValueError:
        return {}
    by_id = {str(p.get("id")): p for p in people}
    by_laws = {str(p.get("lawsId")): p for p in people if p.get("lawsId") is not None}
    out = {}
    for r in records:
        links = r.get("links") or []
        wp = [m.group(1) for l in links for m in [re.search(r"legmt\.gov/legislators/(\d+)", l)] if m]
        laws = [m.group(1) for l in links for m in [re.search(r"#/legislator/(\d+)", l)] if m]
        found = next((by_id[i] for i in wp if i in by_id), None) or \
            next((by_laws[i] for i in laws if i in by_laws), None)
        if not found:
            continue
        chamber = "upper" if (found.get("chamber") or "").lower() == "senate" else "lower"
        theirs = f"{found.get('firstName') or ''} {found.get('lastName') or ''}".strip()
        if (chamber != r["chamber"] or _digits(found.get("district")) != _record_district(r)
                or not names_surname(found.get("lastName"), r["name"]) or not found.get("isActive")):
            out[r["id"]] = {"refused": f"the roster's id {found.get('id')} is {theirs}, "
                                       f"{found.get('district')}"}
            continue
        sizes = ((found.get("photo") or {}).get("sizes") or {})
        renditions = [sizes[k] for k in ("avatar", "lowres") if sizes.get(k)]
        if not renditions:
            out[r["id"]] = {"refused": "the roster names no photograph"}
            continue
        out[r["id"]] = {"candidate": {
            "page": (found.get("links") or {}).get("profileUrl") or f"https://www.legmt.gov/legislators/{found['id']}/",
            "record": url,
            "evidence": f"the roster record {found['id']}: \"{found.get('jobTitle') or ''} {theirs}, "
                        f"{found.get('district')}\" with its photo",
            "renditions": renditions,
            "key": f"legmt.gov id {found['id']}",
        }}
    return out


def read_new_jersey(http, code, records, roster=None, year=0):
    """The Office of Legislative Services' bio record for the roster id in
    the member's Open States links (a member who moved chambers has a
    second); its ``PictureText`` names the member beside its ``Picture``."""
    out = {}
    for r in records:
        ids = []
        for link in r.get("links") or []:
            m = re.search(r"njleg\.state\.nj\.us/legislative-roster/(\d+)", link)
            if m and m.group(1) not in ids:
                ids.append(m.group(1))
        for rid in reversed(ids):          # the newest id is listed last
            api = f"https://www.njleg.state.nj.us/api/legislatorData/legislatorBio/{rid}"
            ans = http.get(api)
            if ans.status != 200:
                continue
            try:
                bio = ans.json()[0][0]
            except (ValueError, IndexError, KeyError, TypeError):
                continue
            house = (bio.get("Roster_House") or [""])[0]
            chamber = "upper" if house == "S" else "lower" if house == "A" else ""
            if (chamber != r["chamber"] or str(bio.get("Roster_District")) != _record_district(r)
                    or not names_surname(bio.get("Last_Name"), r["name"])
                    or bio.get("Legislator_Status") != "A"):
                continue
            text = (bio.get("PictureText") or "").strip()
            picture = (bio.get("Picture") or "").strip()
            if not picture or not names_surname(text, r["name"]):
                out[r["id"]] = {"refused": "the bio record names no photograph of the member"}
                break
            out[r["id"]] = {"candidate": {
                "page": "https://www.njleg.state.nj.us" + (bio.get("BioLink") or f"/legislative-roster/{rid}"),
                "record": api,
                "evidence": f"the bio record {rid}: PictureText \"{text}\"",
                "renditions": ["https://pub.njleg.state.nj.us" + picture],
                "key": f"roster id {rid}",
            }}
            break
    return out


def _strapi_portrait(text):
    """The ``"portrait"`` upload of an Oklahoma House member page."""
    i = text.find('"portrait":{')
    if i < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[i + len('"portrait":'):])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def read_oklahoma(http, code, records, roster=None, year=0):
    """The House member page Open States links: the page's own record of
    the member's ``portrait`` upload lists the renditions Strapi made of it
    (``formats``), and the page's heading names the member. Only that slot:
    a page also serves press photographs with the member's name in the file
    (the checker's Dempsey). The Senate's list answers a script with a
    redirect loop and is not read."""
    out = {}
    for r in records:
        if r["chamber"] != "lower":
            continue
        # Open States may list a past page first (Chris Banning's
        # "59th-chris-banning" is empty): the first that has a heading.
        heading = ""
        for page in [l for l in r.get("links") or []
                     if re.search(r"okhouse\.gov/representatives/[\w-]+/?$", l)]:
            ans = http.get(page)
            if ans.status != 200:
                continue
            text = ans.text()
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.S)
            heading = strip_text(h1.group(1)) if h1 else ""
            if heading:
                break
        if not heading:
            continue
        if not names_surname(heading, r["name"]):
            out[r["id"]] = {"refused": f"the page is \"{heading}\""}
            continue
        district = re.search(r'href="/district/(\d+)"', text)
        if not district or district.group(1) != _record_district(r):
            out[r["id"]] = {"refused": "the page is another district's"}
            continue
        portrait = _strapi_portrait(text)
        if not portrait or not portrait.get("url"):
            continue
        formats = sorted(((f.get("width") or 0, f["url"]) for f in (portrait.get("formats") or {}).values()
                          if f.get("url")), key=lambda x: x[0])
        renditions = [u for w, u in formats if w >= TARGET_WIDTH] + [portrait["url"]]
        out[r["id"]] = {"candidate": {
            "page": page,
            "evidence": f"heading \"{heading}\"; portrait \"{portrait.get('name') or ''}\"",
            "renditions": renditions,
            "key": f"member page {page.rsplit('/', 1)[-1] or page}",
        }}
    return out


def read_louisiana(http, code, records, roster=None, year=0):
    """Each seat's page on the chamber's site names its member
    (``FULLNAME1Label``) beside a file keyed by the seat
    (``RepPics/rep<n>.jpg``, ``SenPics/Sen<n>.jpg``): seat-keyed."""
    out = {}
    for r in records:
        d = _record_district(r)
        if not d.isdigit():
            continue
        if r["chamber"] == "lower":
            page = f"https://house.louisiana.gov/H_Reps/members?ID={d}"
            pattern = rf"RepPics/rep{d}\.jpg"
        else:
            page = f"https://senate.la.gov/smembers?ID={d}"
            pattern = rf"SenPics/Sen{d}\.jpg"
        ans = http.get(page)
        if ans.status != 200:
            continue
        text = ans.text()
        m = re.search(r'id="body_FormView1111_FULLNAME1Label">([^<]+)<', text)
        img = next((i.get("src") for i in parse_page(text).images
                    if re.search(pattern + "$", i.get("src") or "", re.I)), None)
        if not m or not img:
            continue
        theirs = html.unescape(m.group(1)).strip()
        if not names_surname(theirs, r["name"]):
            out[r["id"]] = {"refused": f"the seat's page names {theirs}"}
            continue
        out[r["id"]] = {"candidate": {
            "page": page,
            "evidence": f"the seat's page names \"{theirs}\" beside {img.rsplit('/', 1)[-1]}",
            "renditions": [urllib.parse.urljoin(ans.url or page, img)],
            "key": f"{'House' if r['chamber'] == 'lower' else 'Senate'} seat {d}",
            "seatKeyed": True,
        }}
    return out


def read_connecticut(http, code, records, roster=None, year=0):
    """The CGA's member lists name each member beside their district code;
    the member's bills page for that code shows ``legpics/<code>.png``
    under the heading "Representative Matthew Ritter of the 1st": seat-keyed."""
    lists = {}
    for chamber, path in (("lower", "hlist.asp"), ("upper", "slist.asp")):
        ans = http.get(f"https://www.cga.ct.gov/asp/menu/{path}")
        if ans.status != 200:
            continue
        for m in re.finditer(r"<td>\s*(S?\d+)\s*</td>\s*<td>\s*<a[^>]*>([^<]+)</a>", ans.text()):
            lists[(chamber, _digits(m.group(1)))] = (m.group(1).strip(), html.unescape(m.group(2)).strip())
    out = {}
    for r in records:
        listed = lists.get((r["chamber"], _record_district(r)))
        if not listed:
            continue
        dist_code, listed_name = listed
        if not names_surname(listed_name, r["name"]):
            out[r["id"]] = {"refused": f"the CGA list names {listed_name} for {dist_code}"}
            continue
        page = f"https://www.cga.ct.gov/asp/CGABillStatus/CGAMemberBills.asp?dist_code=%27{dist_code}%27"
        ans = http.get(page)
        if ans.status != 200:
            continue
        doc = parse_page(ans.text())
        heading = next((h for h in doc.headings if re.match(r"(Representative|Senator)\b", h)), "")
        img = next((i.get("src") for i in doc.images
                    if re.search(rf"/legpics/{re.escape(dist_code)}\.(png|jpg)(\?|$)", i.get("src") or "", re.I)),
                   None)
        if not heading or not img:
            continue
        if not names_surname(heading, r["name"]):
            out[r["id"]] = {"refused": f"the page is \"{heading}\""}
            continue
        out[r["id"]] = {"candidate": {
            "page": page,
            "evidence": f"the CGA list \"{listed_name}\" ({dist_code}); heading \"{heading}\" "
                        f"beside legpics/{dist_code}",
            "renditions": [urllib.parse.urljoin(page, img.split("?")[0])],
            "key": f"district code {dist_code}",
            "seatKeyed": True,
        }}
    return out


def read_indiana(http, code, records, roster=None, year=0):
    """The IGA's record of the member (``getLegislatorDetails``, by the
    lpid in their Open States links) names them; the IGA app shows their
    photograph at ``images/legislators/<assembly>/<year>/<chamber>/<lpid>
    .jpg``, built from its own key - read from the app's code each run,
    never assumed (the checker of 2026-10-19)."""
    ans = http.get("https://iga.in.gov/api/getSessionYears", browser=True)
    try:
        active = next(y for y in ans.json()["years"] if y.get("active") and not y.get("special"))
    except Exception:
        return {}
    shell = http.get("https://iga.in.gov/", browser=True)
    script = re.search(r'src="(/static/js/main\.[0-9a-f]+\.js)"', shell.text() if shell.status == 200 else "")
    if not script:
        return {}
    app = http.get("https://iga.in.gov" + script.group(1), browser=True)
    if app.status != 200 or '"/images/legislators/").concat(' not in app.text():
        return {}
    out = {}
    session = active["lpid"]
    for r in records:
        lpid = next((m.group(1) for l in r.get("links") or []
                     for m in [re.search(r"/legislators/(legislator_[a-z0-9_]+)", l)] if m), None)
        if not lpid:
            continue
        api = (f"https://iga.in.gov/api/getLegislatorDetails?session_lpid={session}"
               f"&legislator_lpid={lpid}")
        ans = http.get(api, browser=True)
        if ans.status != 200:
            continue
        try:
            rec = ans.json()
        except ValueError:
            continue
        honorific = rec.get("honorific") or ""
        chamber = "lower" if honorific == "Representative" else "upper" if honorific == "Senator" else ""
        theirs = f"{honorific} {rec.get('firstname') or ''} {rec.get('lastname') or ''}".strip()
        if (chamber != r["chamber"] or str(rec.get("district_id")) != _record_district(r)
                or not names_surname(rec.get("lastname"), r["name"])):
            out[r["id"]] = {"refused": f"the IGA's {lpid} is {theirs}, district {rec.get('district_id')}"}
            continue
        folder = "house" if chamber == "lower" else "senate"
        out[r["id"]] = {"candidate": {
            "page": f"https://iga.in.gov/legislative/{active['year']}/legislators/{lpid}",
            "record": api,
            "evidence": f"the IGA record {lpid}: \"{theirs}\", district {rec.get('district_id')}",
            "renditions": [f"https://iga.in.gov/images/legislators/{active['assembly_id']}/"
                           f"{active['year']}/{folder}/{lpid}.jpg"],
            "key": f"lpid {lpid}",
        }}
    return out


def read_ohio(http, code, records, roster=None, year=0):
    """Each chamber's member directory: a card per member gives the name,
    "District N" and the headshot as its background. The directory's
    ``medium`` file runs 233-466 KB; the host's own ``small`` rendition of
    the same file is taken, after its shape is checked against it."""
    cards = {}
    for chamber, host in (("lower", "https://ohiohouse.gov"), ("upper", "https://ohiosenate.gov")):
        ans = http.get(host + "/members/directory")
        if ans.status != 200:
            continue
        for m in re.finditer(r'caption-text-line-1">([^<]+)</div>.*?District (\d+).*?'
                             r'background-image:url\(([^)]+)\)', ans.text(), re.S):
            cards[(chamber, m.group(2))] = (html.unescape(m.group(1)).strip(), host,
                                            host + m.group(3).strip("'\""))
    out = {}
    for r in records:
        card = cards.get((r["chamber"], _record_district(r)))
        if not card:
            continue
        theirs, host, medium = card
        if theirs.lower() == "vacant":
            out[r["id"]] = {"refused": "the chamber's directory lists the seat as vacant"}
            continue
        if not names_surname(theirs, r["name"]):
            out[r["id"]] = {"refused": f"the directory names {theirs} for the district"}
            continue
        small = re.sub(r"/medium/", "/small/", medium)
        small = re.sub(r"_medium(\.\w+)$", r"_small\1", small)
        out[r["id"]] = {"candidate": {
            "page": host + "/members/directory",
            "evidence": f"the directory's card \"{theirs}, District {_record_district(r)}\"",
            "renditions": ([small] if small != medium else []) + [medium],
            "sameShapeAs": medium,
            "key": f"{'House' if r['chamber'] == 'lower' else 'Senate'} district {_record_district(r)}",
        }}
    return out


def read_colorado(http, code, records, roster=None, year=0):
    """The General Assembly's list of legislators offers its own smaller
    rendition (an Active Storage variant) of each listed member's
    photograph, alt-texted with their name; anyone it does not list is read
    from their own page (``read_member_pages``)."""
    ans = http.get("https://leg.colorado.gov/legislators")
    found = {}
    if ans.status == 200:
        for img in parse_page(ans.text()).images:
            src = img.get("src") or ""
            if "leg-mem-picture" in (img.get("class") or "") and "/representations/" in src:
                found.setdefault(fold(img.get("alt")).strip(), []).append(src)
    out, rest = {}, []
    for r in records:
        srcs = found.get(fold(r["name"]).strip()) or []
        if len(srcs) == 1 and names_surname(" ".join(file_words(srcs[0])), r["name"]):
            out[r["id"]] = {"candidate": {
                "page": "https://leg.colorado.gov/legislators",
                "evidence": f"alt \"{r['name']}\"; file \"{urllib.parse.unquote(srcs[0].rsplit('/', 1)[-1])}\"",
                "renditions": [srcs[0]],
                "key": "the legislators list",
            }}
        else:
            rest.append(r)
    out.update(read_member_pages(http, code, rest, roster=roster, year=year))
    return out


def read_member_pages(http, code, records, roster=None, year=0):
    """Any other state: the member's own page on the legislature's site
    (``legislature.page_for``: never a caucus's, a past session's or another
    member's), and on it the photograph the legislature names as theirs
    (``pick_member_image``)."""
    from . import legislature
    roster = roster if roster is not None else records
    pages, _ = legislature.pages_for(code, roster, year)
    others = {w for r in roster for w in surname_words(r.get("name"))}
    out = {}
    for r in records:
        page = pages.get(r["id"])
        if not page or page["kind"] != "member" or page.get("session"):
            continue
        url = page["url"]
        ans = http.get(url)
        if ans.status != 200:
            continue
        doc = parse_page(ans.text())
        picked = pick_member_image(code, r, doc, ans.url or url, others)
        if not picked:
            continue
        images, why, seat_keyed = picked
        title = doc.title if names_surname(doc.title, r["name"]) else next(
            (h for h in doc.headings if names_surname(h, r["name"])), "")
        candidate = {
            "page": url,
            "evidence": why + (f"; page \"{title}\"" if title else ""),
            "renditions": images,
            "key": "member page",
        }
        if seat_keyed:
            candidate["seatKeyed"] = True
        out[r["id"]] = {"candidate": candidate}
    # One file offered as two members' photograph is neither's: the
    # Florida House alt-texts one album photograph with each page's member
    # (the checker of 2026-10-19).
    claimed = {}
    for pid, outcome in out.items():
        for image in outcome["candidate"]["renditions"]:
            claimed.setdefault(image, []).append(pid)
    for image, pids in claimed.items():
        if len(pids) > 1:
            for pid in pids:
                out[pid] = {"refused": f"{image} is offered on {len(pids)} members' pages"}
    return out


_LIKENESS_ALT = re.compile(r"\b(photo|picture|headshot|portrait|image)\b", re.I)
# A page's album or gallery holds photographs of events, not the member's
# portrait, whatever its alt text says (the Florida House's PhotoAlbums and
# member-uploaded photographs, 2026-10-19).
_ALBUM = re.compile(r"album|gallery|uploaded", re.I)


def page_keys(url):
    """The keys a member page's address carries for its member: query
    values of three or more letters and digits ("HHABI" in ?SponCode=HHABI,
    "ned" in Alaska's ?code=ned) and path segments of three or more
    carrying a digit or in capitals ("1003" in /Biography/H/1003)."""
    parts = urllib.parse.urlsplit(url)
    keys = [v for _, v in urllib.parse.parse_qsl(parts.query) if re.fullmatch(r"[A-Za-z0-9]{3,}", v)]
    keys += [s for s in parts.path.split("/")
             if re.fullmatch(r"[A-Za-z0-9]{3,}", s) and not s.isalpha() or re.fullmatch(r"[A-Z]{4,}\d*", s)]
    return {k.lower() for k in keys if not re.fullmatch(r"(19|20)\d\d", k)}


def _file_keys(url):
    """The file name's stem and its parts: never a folder's name, which can
    be the member's key over photographs that are not their portrait
    (Florida's ``get-member-uploaded-photo/5064/...``)."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).lower()
    segments = [s for s in path.split("/") if s]
    stem = re.sub(r"\.\w+$", "", segments[-1]) if segments else ""
    return {stem} | set(re.split(r"[^a-z0-9]+", stem)) - {""}


def seat_and_surname(url, name, district):
    """The file is named by the member's surname and their district's
    number together (Missouri's Senate ``Mosley13.jpg``): still keyed by the
    seat, since a successor of the same surname would get the same name."""
    stem = re.sub(r"[^a-z0-9]", "", fold(file_words_raw(url)))
    sur = surname_joined(name)
    return bool(sur and district and (re.fullmatch(rf"{re.escape(sur)}0*{district}", stem)
                                      or re.fullmatch(rf"0*{district}{re.escape(sur)}", stem)))


def pick_member_image(code, record, doc, page_url, others=()):
    """``([image urls], evidence, seat-keyed)`` for the one photograph a
    member page names as *record*'s, or ``None``.

    First choice, any image the legislature ties to the member:
    - alt text carrying their given name and surname;
    - a file name carrying their surname, on a page whose title or heading
      names them;
    - a file named by the member's own key in the page's address (New
      Mexico's ``HHABI.jpg`` on ``?SponCode=HHABI``, Florida's
      ``cutout/5063.png`` on ``?MemberId=5063``, Alaska's ``NED.jpg`` on
      ``?code=ned``) - the file's own name, never a folder's - with their
      surname in its alt, the page's title or heading, or their name
      written in full in the page's text;
    - a file named by the seat on a page whose title or heading names them
      in full (Nebraska's ``dist01.jpg`` under "Sen. Bob Hallstrom").
    Several such images are the member's alternatives (New York's headshot
    and header headshot); none of another member's surname is taken, and
    nothing from an album or a gallery.
    Only where there is none: a single image whose alt is a likeness of a
    member of their surname ("Photo of Representative Torres") on a page
    naming them in full. Florida's album photograph carries such an alt on
    every page; it is never taken while the page has a first choice.
    A file named by the member's district number and not their name is
    keyed by the seat (California's ``assembly_member_02.jpg``, New York's
    ``115.jpg``), and so is one named by surname and district together
    (Missouri's Senate ``Mosley13.jpg``): each is dated like any seat-keyed
    file."""
    name = record["name"]
    mine = surname_words(name)
    named_page = any(names_member(t, name) for t in [doc.title] + doc.headings)
    in_text = named_page or names_in_full(getattr(doc, "text", ""), name)
    district = _digits(record.get("district"))
    keys = {k for k in page_keys(page_url) if not seat_key(k, district)}
    first, second = {}, {}
    seat_files = set()
    for img in doc.images:
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        absolute = urllib.parse.urljoin(page_url, src).split("#")[0]
        # A cache-buster stamped at each request ("?20261019095335", the
        # Pennsylvania House) is not part of the file's address.
        absolute = re.sub(r"\?\d{8,}$", "", absolute)
        if not absolute.startswith("http") or not official_host(code, absolute):
            continue
        if _ALBUM.search(urllib.parse.unquote(urllib.parse.urlsplit(absolute).path)):
            continue                  # an album's photograph, not the portrait
        alt = (img.get("alt") or img.get("title") or "").strip()
        # The file name's words, apart: "sd29_logo_white.png" is a logo
        # (an underscore is a word character, so no word boundary falls there).
        if _NOT_A_LIKENESS.search(alt) or _NOT_A_LIKENESS.search(" ".join(file_words(absolute))):
            continue                  # a district map, a seal, a banner
        fwords = set(file_words(absolute))
        fkeys = _file_keys(absolute)
        mentions = names_surname(alt, name) or named_page
        if not names_member(alt, name) and (fwords & (set(others) - mine)):
            continue                  # another member's surname and not theirs
        filename = urllib.parse.unquote(absolute.rsplit("/", 1)[-1])
        in_file = names_surname(" ".join(fwords), name)
        by_seat = ((not in_file and any(seat_key(k, district) for k in fkeys))
                   or seat_and_surname(absolute, name, district))
        if names_member(alt, name):
            first.setdefault(absolute, f"alt \"{alt}\"")
        elif in_file and mentions:
            first.setdefault(absolute, f"file \"{filename}\" on a page naming them")
        elif keys & fkeys and (mentions or in_text):
            key = sorted(keys & fkeys)[0]
            first.setdefault(absolute, f"file \"{filename}\" named by the page's own key for "
                                       f"the member ({key})" + (f", alt \"{alt}\"" if alt else "")
                                       + ("" if mentions else ", on a page naming them in full"))
        elif by_seat and names_surname(alt, name):
            first.setdefault(absolute, f"file \"{filename}\" named by the seat, alt \"{alt}\"")
        elif by_seat and named_page:
            first.setdefault(absolute, f"file \"{filename}\" named by the seat, on a page "
                                       f"whose heading names them")
        elif named_page and names_surname(alt, name) and _LIKENESS_ALT.search(alt):
            second.setdefault(absolute, f"alt \"{alt}\" on a page naming them")
        else:
            continue
        if by_seat:
            seat_files.add(absolute)
    chosen = first or (second if len(second) == 1 else {})
    if not chosen:
        return None
    images = list(chosen)
    return images, "; ".join(dict.fromkeys(chosen.values())), bool(seat_files & set(images))


_NOT_A_LIKENESS = re.compile(r"\b(map|maps|logo|seal|banner|flag|icon|chart|signature|capitol|"
                             r"building|district\s+\d+\s+map)\b", re.I)


def seat_key(key, district):
    """*key* names the seat, not the member: the district's number, bare or
    after a chamber's letters or the word for a district ("02", "s14",
    "hd105", Nebraska's "dist01")."""
    m = re.fullmatch(r"(?:[a-z]{0,2}|dist|district|seat)0*(\d+)", (key or "").lower())
    return bool(m and district and m.group(1) == district)


def file_words_raw(url):
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    return re.sub(r"\.\w+$", "", path.rsplit("/", 1)[-1])


RECIPES = {
    "MT": read_montana,
    "NJ": read_new_jersey,
    "OK": read_oklahoma,
    "LA": read_louisiana,
    "CT": read_connecticut,
    "IN": read_indiana,
    "OH": read_ohio,
    "CO": read_colorado,
}

# States read by no recipe, with why (reported by the command):
#
# Kansas is read like any other state: its new site names
# /static/li_pics/<key>.jpg for every member, alt-texted with their name,
# and answers 404 for 123 of 165 (read 2026-10-19; the old /li/s/images/pics
# path redirects to another 404). Its pages carry no other photograph, and
# the Internet Archive's copies of the old files are not the legislature
# serving them (owner, 2026-10-19), so those members read "the file the
# source names is gone" until the legislature restores them.
NOT_READ = {
    # Michigan's only portraits are the party caucuses' (rule 87): the
    # House's own pages show none, and its media folder serves Republicans'
    # files at addresses no page names (research, 2026-10-19).
    "MI": "only the party caucuses publish Michigan legislators' photographs",
}

# Pages a script cannot read, said by the command so nobody takes their
# members' missing portraits for an absence (rule 8). Each was opened on
# 2026-10-19.
SCRIPT_DRAWN = {
    "GA": "legis.ga.gov draws its member pages with script",
    "SD": "sdlegislature.gov draws its member pages with script",
    "UT": "house.utleg.gov draws its member pages with script",
    "OK": "oksenate.gov answers a script with a JavaScript challenge (the Senate's 4)",
    "AL": "Open States links only the chamber's searchable list",
    "ME": "legislature.maine.gov resets every connection from here",
}


# --------------------------------------------------------------- settling

def holder_since(http, code, person_id, chamber, cache):
    """The day the member began in their seat, from Open States' own record
    of them (its people repository, found by the person's id): used only to
    date a seat-keyed file. ``None`` when it cannot be read."""
    listing = cache.get(code)
    if listing is None:
        ans = http.get(f"https://api.github.com/repos/openstates/people/contents/data/{code.lower()}/legislature")
        try:
            listing = {e["name"][-40:-4]: e["download_url"] for e in ans.json()
                       if e.get("name", "").endswith(".yml")} if ans.status == 200 else {}
        except (ValueError, TypeError, KeyError):
            listing = {}
        cache[code] = listing
    uuid = person_id.rsplit("/", 1)[-1]
    url = listing.get(uuid)
    if not url:
        return None
    ans = http.get(url)
    if ans.status != 200:
        return None
    return role_start(ans.text(), chamber)


def role_start(yaml_text, chamber):
    """The start date of the open role in *chamber* in an Open States person
    file (a role with no end date)."""
    block = re.search(r"^roles:\n((?:[ -].*\n?)+)", yaml_text, re.M)
    if not block:
        return None
    for role in re.split(r"\n(?=- )", block.group(1)):
        kind = re.search(r"type: (\w+)", role)
        start = re.search(r"start_date: '?(\d{4}-\d{2}-\d{2})", role)
        if kind and start and "end_date" not in role and kind.group(1) in (chamber, "legislature"):
            return start.group(1)
    return None


def settle(http, code, record, candidate, previous_files, today, starts):
    """An entry for *candidate* (weighed), or ``None`` when nothing could be
    concluded. The entry is one of: a photograph to show; ``oversized``
    (every rendition the source offers is over the caps); ``withheld`` with
    why (a landscape frame, a seat-keyed file that may be the predecessor's,
    a file gone)."""
    base = {"name": record["name"], "chamber": record["chamber"], "district": record["district"],
            "page": candidate["page"], "evidence": candidate["evidence"], "key": candidate["key"],
            "credit": legislature_name(code), "read": today}
    if candidate.get("record"):
        base["record"] = candidate["record"]
    smallest = None
    chosen = None
    for url in candidate["renditions"]:
        if not official_host(code, url):
            return dict(base, withheld=f"{url} is not on the legislature's host")
        weight = weigh(http, url)
        if weight is None:
            return None
        if weight.get("gone"):
            continue
        weight["image"] = url
        if over_caps(weight):
            smallest = smallest or weight
            continue
        chosen = weight
        if weight["width"] >= TARGET_WIDTH:
            break
    if not chosen:
        if smallest:
            return dict(base, oversized=True, offered=smallest["image"],
                        **{k: smallest[k] for k in ("bytes", "width", "height")})
        return dict(base, withheld="the file the source names is gone")
    if landscape(chosen):
        return dict(base, withheld=f"a landscape frame ({chosen['width']}x{chosen['height']})")
    same = candidate.get("sameShapeAs")
    if same and same != chosen["image"]:
        from .portraits import measure
        original = measure(same)
        if not original:
            return None
        if abs(original["width"] / original["height"] - chosen["width"] / chosen["height"]) > 0.02:
            return dict(base, withheld="the smaller rendition is not the same shape as the page's file")
    entry = dict(base, image=chosen["image"],
                 **{k: chosen[k] for k in ("bytes", "width", "height", "sha", "lastModified") if k in chosen})
    if candidate.get("seatKeyed"):
        entry["seatKeyed"] = True
        since = holder_since(http, code, record["id"], record["chamber"], starts)
        if since:
            entry["holderSince"] = since
        why = seat_problem(entry, record["id"], previous_files)
        if why:
            return dict(entry, withheld=why, image=None)
    return entry


def seat_problem(entry, person_id, seat_files):
    """Why a seat-keyed file may not be this member's, or ``""``."""
    shown = (seat_files or {}).get(entry["image"])
    if shown and shown.get("holder") != person_id and shown.get("sha") == entry.get("sha"):
        return f"the seat's file has not changed since it showed {shown.get('name')}"
    since, modified = entry.get("holderSince"), entry.get("lastModified")
    if not since or not modified:
        return "the file is keyed by seat and cannot be dated against the member's arrival"
    arrived = datetime.date.fromisoformat(since) - datetime.timedelta(days=SEAT_MARGIN_DAYS)
    if datetime.date.fromisoformat(modified) < arrived:
        return f"the seat's file dates from {modified}, before the member arrived ({since})"
    return ""


# ------------------------------------------------------------------ cache

def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {"people": {}, "seatFiles": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    path = os.path.join(root, CACHE_PATH)
    payload = {
        "source": SOURCE,
        "fetched": cache.get("fetched") or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "people": {k: cache["people"][k] for k in sorted(cache.get("people") or {})},
        "seatFiles": {k: cache["seatFiles"][k] for k in sorted(cache.get("seatFiles") or {})},
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return path


def open_states_image_ok(record):
    """Open States' own portrait for *record* is shown (legislature._person)."""
    from .legislature import search_thumbnail
    image = record.get("image")
    return bool(image) and not search_thumbnail(image) and record.get("imageStatus") != "broken"


def needing(by_state, codes=None, unread=False):
    """``{code: [records]}`` of members with no usable Open States portrait,
    in the states a recipe reads (and in ``NOT_READ`` too, with *unread*)."""
    return {code: [r for r in records if not open_states_image_ok(r)]
            for code, records in by_state.items()
            if (codes is None or code in codes) and (unread or code not in NOT_READ)}


def refresh(by_state, previous, codes=None, http=None, today=None, force=False, log=print,
            workers=6, year=0):
    """Read every state's members who need a portrait; returns the new cache
    and ``{code: {"shown", "oversized", "withheld", "kept", "none"}}``."""
    http = http or Http()
    today = today or datetime.date.today().isoformat()
    people = dict((previous or {}).get("people") or {})
    seat_files = dict((previous or {}).get("seatFiles") or {})
    todo = needing(by_state, codes)
    starts = {}

    def fresh(pid):
        entry = people.get(pid)
        if force or not entry or not entry.get("read"):
            return False
        age = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(entry["read"])).days
        return age < RECHECK_DAYS

    def run(code):
        records = [r for r in todo[code] if not fresh(r["id"])]
        if not records:
            return code, {}, {}
        recipe = RECIPES.get(code)
        try:
            outcomes = (recipe or read_member_pages)(http, code, records, roster=by_state[code], year=year)
        except Exception as exc:                 # a recipe's surprise concludes nothing
            log(f"  [warn] {code}: the read failed ({exc.__class__.__name__}: {exc}); "
                f"the last entries stand")
            return code, {}, {}
        settled = {}
        for r in records:
            outcome = outcomes.get(r["id"])
            if not outcome:
                continue
            if "refused" in outcome:
                settled[r["id"]] = {"name": r["name"], "chamber": r["chamber"], "district": r["district"],
                                    "withheld": outcome["refused"], "read": today,
                                    "credit": legislature_name(code)}
                continue
            entry = settle(http, code, r, outcome["candidate"], seat_files, today, starts)
            if entry is not None:
                settled[r["id"]] = entry
        return code, settled, records

    report = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for code, settled, records in pool.map(run, sorted(todo)):
            counts = report.setdefault(code, {"shown": 0, "oversized": 0, "withheld": 0, "kept": 0, "none": 0})
            for r in records or ():
                entry = settled.get(r["id"])
                if entry is None:
                    counts["kept" if r["id"] in people else "none"] += 1
                    continue
                people[r["id"]] = dict(entry, state=code)
                if entry.get("image"):
                    counts["shown"] += 1
                    if entry.get("seatKeyed") and entry.get("sha"):
                        seat_files[entry["image"]] = {"holder": r["id"], "name": r["name"],
                                                      "sha": entry["sha"], "read": today}
                elif entry.get("oversized"):
                    counts["oversized"] += 1
                else:
                    counts["withheld"] += 1
    # Members no longer on the roster leave the cache; the seat files they
    # were shown with stay, so a successor is never shown their photograph.
    current = {r["id"] for records in by_state.values() for r in records}
    people = {pid: e for pid, e in people.items() if pid in current}
    return {"people": people, "seatFiles": seat_files}, report


# ------------------------------------------------------------------- build

def entry_for(record, cache):
    """The cache's entry for *record* when it is shown: a photograph that
    passed every check, for the same member, else ``None``."""
    entry = ((cache or {}).get("people") or {}).get(record["id"])
    if not entry or not entry.get("image") or entry.get("withheld") or entry.get("oversized"):
        return None
    if not names_surname(entry.get("evidence"), record["name"]):
        return None
    return entry


def problems(cache, by_state):
    """``[(level, code, message)]`` for ``build``: an entry shown without
    the evidence, the weight or the credit this module requires is an
    error; one not confirmed for ``STALE_DAYS`` a warning."""
    out = []
    from .photos import MAX_PORTRAIT_BYTES, MAX_PORTRAIT_PX
    records = {r["id"]: (code, r) for code, rows in (by_state or {}).items() for r in rows}
    today = datetime.date.today()
    stale = []
    for pid, entry in sorted(((cache or {}).get("people") or {}).items()):
        if pid not in records or not entry.get("image") or entry.get("withheld") or entry.get("oversized"):
            continue
        code, record = records[pid]
        if open_states_image_ok(record):
            continue
        who = f"{code} {record['name']}"
        missing = [k for k in ("page", "evidence", "read", "bytes", "width", "height", "credit", "key")
                   if not entry.get(k)]
        if missing:
            out.append(("error", "legislator-photo-unsourced",
                        f"{who}: the cached photograph has no {', '.join(missing)}"))
            continue
        if not names_surname(entry["evidence"], record["name"]):
            out.append(("error", "legislator-photo-unnamed",
                        f"{who}: the evidence for the photograph does not name them: {entry['evidence']}"))
        if not official_host(code, entry["image"]) or not official_host(code, entry["page"]):
            out.append(("error", "legislator-photo-host",
                        f"{who}: {entry['image']} is not on the legislature's own host"))
        if entry["bytes"] > MAX_PORTRAIT_BYTES or max(entry["width"], entry["height"]) > MAX_PORTRAIT_PX:
            out.append(("error", "legislator-photo-heavy",
                        f"{who}: {entry['bytes']:,} bytes, {entry['width']}x{entry['height']}, over the caps"))
        if entry.get("seatKeyed") and not entry.get("holderSince"):
            out.append(("error", "legislator-photo-seat",
                        f"{who}: a seat-keyed file shown without the member's arrival date"))
        try:
            age = (today - datetime.date.fromisoformat(entry["read"])).days
        except ValueError:
            age = STALE_DAYS + 1
        if age > STALE_DAYS:
            stale.append(who)
    if stale:
        out.append(("warn", "legislator-photo-stale",
                    f"{len(stale)} legislator photograph(s) not confirmed for {STALE_DAYS} days "
                    f"(run 'legphotos'): " + ", ".join(stale[:8])))
    return out


def report(cache, by_state):
    """``{what: {code: n}}`` over members with no usable Open States
    portrait: shown from the legislature's records ("legislature"), left out
    because only heavier files are offered ("oversized"), and withheld
    ("withheld")."""
    out = {}
    people = (cache or {}).get("people") or {}
    for code, records in (by_state or {}).items():
        for r in records:
            if open_states_image_ok(r):
                continue
            entry = people.get(r["id"])
            if not entry:
                continue
            kind = ("legislature" if entry_for(r, cache) else "oversized" if entry.get("oversized")
                    else "withheld" if entry.get("withheld") else None)
            if kind:
                out.setdefault(kind, {})[code] = out.get(kind, {}).get(code, 0) + 1
    return out
