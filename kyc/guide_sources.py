"""Whether each source the guide cites still opens (rule 48).

Know Your Government, its maps and the 2026 ballot table cite some 350
addresses, and the page code links a few statutes of its own. About eighty
are the Office of the Law Revision Counsel's ``uscode.house.gov/us/usc/tN/sM/``
pages, which that site says it serves in a "temporary format"; its previous
``view.xhtml`` addresses already answer 404 (read 2026-11-14). A change of
scheme there would break every one of those links, and nothing opened an
external link: the gates check that a source is cited and on its
publisher's host, never that it still answers (PR #255's review).

``python build_profile_site.py guidesources`` opens each address, one
request at a time per host and paced (``HOST_INTERVAL``), as this project
(``agent.USER_AGENT``, rule 103), with a GET - HEAD lies (rule 51) - reading
only the first bytes of a large file, and writes what each answered to
``data/guide_sources.json``: per address, the day and the answer. The cache
is hand-editable, one address a line, and a stopped run resumes.

What one read answers (``assess``):

* ``open`` - a page: 2xx, not a bot wall's or an empty answer, and for a
  section of the U.S. Code on uscode.house.gov a page whose title names
  that section ("2 U.S.C. § 8: Vacancies");
* ``notfound`` - HTTP 404 or 410 (never one a bot wall's own host gives
  after a redirect: ``agent.wall_host``);
* ``elsewhere`` - a page that is not the source: one titled "Page Not
  Found", a deep address sent to its site's front page, or a Code section's
  address opening a page whose title names another section or none;
* ``dead`` - its host does not resolve here, and dns.google and Cloudflare
  both answer NXDOMAIN or no address for it (rule 35's second resolver);
* ``nothing`` - nothing concluded (rule 8): a 403, a 429, a 5xx, a timeout,
  a certificate or connection failure, a bot wall or a challenge
  (constitution.congress.gov answers this project with Cloudflare's "Just a
  moment..."), a name a public resolver finds or cannot answer for, a
  sign-in page, a page where its address names a PDF.

What the cache keeps (``merge``):

* ``ok`` - it opened on the read of ``checked``;
* ``missing`` - a 404, a 410 or another page, on one day only: read again on
  a later day before anything is said;
* ``gone`` - 404 or 410 on two reads on different days, or a dead host;
* ``elsewhere`` - not the source on two reads on different days, not both
  a 404 or 410;
* ``unread`` - no read of it has concluded anything.

A read that concludes nothing never undoes a verdict: the verdict and its
day stay and the try is dated beside them (``tried``), as
``kyc/localsites.py`` does. The build (``problems``, through
``validate.check_guide_sources``) warns - never an error: the refresh must
not fail on someone else's site - on each gone or elsewhere source by its
name and every section that cites it, on a source never opened, and on one
not looked at in ``WARN_DAYS``.
"""

import datetime
import glob
import http.client
import http.cookiejar
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

from . import agent, tls
from .localsites import _Gate, bare, doh, resolves_here

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "guide_sources.json")
SOURCE = ("Each address the guide's sections, its maps and the 2026 ballot table cite, and each "
          "statute the page code links, opened by 'guidesources'")
ASSETS = os.path.join("candidate_profiles_site", "assets")

# One read's answer.
OPEN, NOTFOUND, ELSEWHERE_ANSWER, DEAD, NOTHING = "open", "notfound", "elsewhere", "dead", "nothing"
# What the cache keeps.
OK, MISSING, GONE, ELSEWHERE, UNREAD = "ok", "missing", "gone", "elsewhere", "unread"
VERDICTS = (OK, MISSING, GONE, ELSEWHERE, UNREAD)
WARNED = (GONE, ELSEWHERE)

# Opened again once a week: the refresh runs at least every Monday, and an
# address looked at six days ago is due on the next. A missing or unread
# one is due on any later day.
RECHECK_DAYS = 6
# The build warns once a cited address was last looked at longer ago than
# this: the weekly refresh reaches every one, so an old one means it is not
# running.
WARN_DAYS = 30
TIMEOUT = 30
HOPS = 8
HOST_INTERVAL = 2.0          # seconds between two requests to one host
# A host that answers nothing this many times running is not asked again
# this run; its addresses keep their last read (legphotos' way, rule 100).
HOST_FAILURES = 3
# Only the first bytes: a page's title is in its head, a file says what it
# is in its first bytes, and the bound volume of 567 U.S. is a 40 MB PDF.
PAGE_BYTES = 300_000
FILE_BYTES = 8_192
# The hosts of the statutes the page code links, read from assets/*.js.
STATUTE_HOSTS = ("uscode.house.gov", "constitution.congress.gov", "govinfo.gov")
_STATUTE_LINK = re.compile(
    r"https://(?:www\.)?(?:" + "|".join(re.escape(h) for h in STATUTE_HOSTS) + r")"
    r"/[^\s\"'<>`)\\]*")

_HEADERS = dict(agent.HEADERS, **{
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    # A body read only in part is undone more surely when it was not packed.
    "Accept-Encoding": "identity",
})
# A sign-in page says nothing of the source (rule 8).
_SIGN_IN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "login.live.com",
                  "login.yahoo.com")
# Bot walls a redirect lands on, beside ``agent.WALL_HOSTS``: eCFR sends a
# script to unblock.federalregister.gov's "Federal Register :: Request
# Access" (HTTP 200, read 2026-11-14), which says nothing of the section.
WALL_HOSTS = ("unblock.federalregister.gov",)
# A title that says the page asked for is not there: "Page Not Found - US
# Code", the Law Revision Counsel's own 404 page's.
_NOT_FOUND_TITLE = re.compile(
    r"\b(?:page|file|document|resource|content)\b(?:\s+(?:you|was|is|has|been|requested|"
    r"looking|for|are|were|the))*\s+(?:not\s+found|(?:could\s+not|cannot|can't)\s+be\s+found|"
    r"no\s+longer\s+(?:exists|available))\b|"
    r"^\s*(?:error\s+)?404\b|\b404\s*(?:error|[-–—:|])|\berror\s*404\b|^\s*not\s+found\s*$",
    re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)(?:</title|$)", re.I | re.S)
_BODY_OR_SVG = re.compile(r"<(?:body|svg)\b", re.I)
_FRONT = re.compile(r"^/(?:(?:index|default|home)(?:\.[a-z]{2,5})?)?/?$", re.I)
_CODE_SECTION = re.compile(r"^https?://uscode\.house\.gov/us/usc/t(\w+)/s([^/?#]+)/?$", re.I)
_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


# ---------------------------------------------------------------- citations

def address(url):
    """The address a citation opens: the URL without its fragment, which a
    browser never sends ("567BV.pdf#page=555" is "567BV.pdf")."""
    return urllib.parse.urldefrag(str(url or "").strip())[0]


def _links(value):
    """Every ``[label](https://...)`` target in a block's words, at any
    depth (a Tense's words, a table's cells)."""
    if isinstance(value, str):
        return _LINK.findall(value)
    if isinstance(value, dict):
        return [u for v in value.values() for u in _links(v)]
    if isinstance(value, (list, tuple)):
        return [u for v in value for u in _links(v)]
    return []


def _guide_text():
    from . import government_text as text
    out = []
    for page in text.PAGES:
        slug = page["slug"]
        for field in ("lede", "description", "card"):
            out += [(u, f"guide {slug}", "a link in its words") for u in _links(page.get(field))]
        for section in page.get("sections", ()):
            where = f"guide {slug}#{section['id']}"
            for key in section.get("sources") or ():
                title, url = text.SOURCES[key]
                out.append((url, where, f"{key}: {title}"))
            out += [(u, where, "a link in its words") for u in _links(section.get("blocks"))]
    return out


def _guide_maps(root):
    from . import government_maps as maps
    out = []
    for page, items in maps.modes(root=root).items():
        for mode in items:
            where = f"guide map {page}/{mode['id']}"
            for key in mode["sources"]:
                title, url = maps.SOURCES[key]
                out.append((url, where, title if key.startswith("ballot-") else f"{key}: {title}"))
    return out


def _ballot_table():
    from . import ballot2026 as ballot
    out = []
    for code, entry in sorted(ballot.every_jurisdiction().items()):
        for key in ballot.OFFICES + ("upper", "lower"):
            item = ballot._item(entry, key)
            if not item:
                continue
            url = item[3] if key in ballot.OFFICES else item[4]
            what = ballot.TITLES[key].lower() if key in ballot.OFFICES else item[0]
            out.append((url, f"2026 ballot table {code} {key}", f"{code}'s record of the {what}"))
    for (code, key), value in sorted(ballot.NEXT.items()):
        out.append((value[1], f"2026 ballot table {code} {key}", "its next election"))
    for (code, key), (url, cite, _words) in sorted(ballot.TERMS.items()):
        out.append((url, f"2026 ballot table {code} {key}", f"its term: {cite}"))
    for (code, key), value in sorted(ballot.OPEN_SEATS.items()):
        out.append((value[3], f"2026 ballot table {code} {key}", f"its open seat: {value[4]}"))
    return out


def _page_code(root):
    out = []
    for path in sorted(glob.glob(os.path.join(root, ASSETS, "*.js"))):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        name = os.path.basename(path)
        out += [(url, f"page code {name}", "a statute it links")
                for url in sorted(set(_STATUTE_LINK.findall(text)))]
    return out


def citations(root="."):
    """``{address: [(where, name), ...]}``: every address the guide's
    sections (their sources and the links in their words), its maps, the
    2026 ballot table and the page code's statute links cite, each with where
    it is cited and under what name."""
    out = {}
    for url, where, name in (_guide_text() + _guide_maps(root) + _ballot_table()
                             + _page_code(root)):
        cite = (where, name)
        found = out.setdefault(address(url), [])
        if cite not in found:
            found.append(cite)
    return {url: sorted(cites) for url, cites in sorted(out.items()) if url}


# ------------------------------------------------------------------ network

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _body(response, kind):
    """The first bytes of a body: a page's head, a file's first block."""
    wanted = PAGE_BYTES if _is_page(kind) else FILE_BYTES
    raw = response.read(wanted)
    encoding = (response.headers.get("Content-Encoding") or "identity").lower().strip()
    if encoding in ("gzip", "x-gzip", "deflate"):
        for wbits in ((16 + zlib.MAX_WBITS,) if "gzip" in encoding
                      else (zlib.MAX_WBITS, -zlib.MAX_WBITS)):
            try:
                # A decompressor object takes the cut-off end of a part read.
                return zlib.decompressobj(wbits).decompress(raw)
            except zlib.error:
                continue
        return b""
    return raw


def _is_page(kind):
    kind = (kind or "").lower()
    return not kind or "html" in kind or "xml" in kind or kind.startswith("text/")


def _request(url, jar, timeout=TIMEOUT):
    """``(status, content type, first bytes, location)``; raises
    URLError/OSError. Certificates are verified, with the vendored
    intermediates (``kyc/tls.py``): never trusted less."""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), _NoRedirect(),
                                         urllib.request.HTTPSHandler(context=tls.context()))
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with opener.open(req, timeout=timeout) as response:
            kind = response.headers.get("Content-Type") or ""
            return response.status, kind, _body(response, kind), None
    except urllib.error.HTTPError as exc:
        kind = (exc.headers.get("Content-Type") if exc.headers else "") or ""
        where = exc.headers.get("Location") if exc.headers else None
        try:
            body = exc.read(PAGE_BYTES) if 400 <= exc.code < 500 else b""
        except Exception:                     # noqa: BLE001 - an error page's body is extra
            body = b""
        return exc.code, kind, body, where


def visit(url, gate, request=_request):
    """Follow *url* by hand, one hop at a time through the gate: ``{"chain",
    "status", "type", "body", "error", "dnsHost"}``; never raises."""
    jar = http.cookiejar.CookieJar()
    out = {"chain": [url], "status": None, "type": "", "body": b"", "error": "", "dnsHost": ""}
    current = url
    for _hop in range(HOPS):
        host = urllib.parse.urlsplit(current).hostname or ""
        try:
            with gate.hold(host):
                status, kind, body, where = request(current, jar)
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, socket.gaierror):
                out["dnsHost"] = host
                out["error"] = f"{host} does not resolve here"
            elif isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
                out["error"] = _words(f"its certificate could not be verified: {reason}", 120)
            else:
                out["error"] = _words(str(reason), 120) or "connection failed"
            return out
        except (OSError, ValueError, http.client.HTTPException) as exc:
            out["error"] = _words(f"{type(exc).__name__} {exc}", 120) or "connection failed"
            return out
        out["status"], out["type"], out["body"] = status, kind, body
        if 300 <= status < 400 and where:
            nxt = urllib.parse.urljoin(current, where.strip())
            if not nxt.lower().startswith(("http://", "https://")) or nxt in out["chain"][-3:]:
                return out
            out["chain"].append(nxt)
            current = nxt
            continue
        return out
    out["status"] = None
    out["error"] = "too many redirects"
    return out


# ---------------------------------------------------------------- one read

def _words(text, limit=90):
    """ASCII words for the evidence: a page can carry anything."""
    text = " ".join(str(text or "").split())
    text = text.replace("§", "s.").replace("–", "-").replace("—", "-")
    return "".join(ch for ch in text if 32 <= ord(ch) < 127)[:limit].strip()


def page_title(markup):
    """A page's own title: the first ``<title>`` before its body, never an
    inline SVG's."""
    import html
    cut = _BODY_OR_SVG.search(markup or "")
    match = _TITLE.search(markup[:cut.start()] if cut else (markup or ""))
    return " ".join(html.unescape(match.group(1)).split()) if match else ""


def code_section(url):
    """``(title, section)`` for a section of the U.S. Code at the Law
    Revision Counsel's present addresses, ``uscode.house.gov/us/usc/tN/sM/``;
    None for any other address."""
    match = _CODE_SECTION.match(address(url))
    return (match.group(1), urllib.parse.unquote(match.group(2))) if match else None


def names_section(title, section):
    """Whether a page's *title* names the Code section *section*, as the Law
    Revision Counsel titles its pages: "42 U.S.C. § 300aa–12: Court
    jurisdiction" names ``("42", "300aa-12")``."""
    number, part = section
    folded = re.sub(r"[‐-―−]", "-", title or "")
    part = re.escape(part).replace(r"\-", "-")
    return bool(re.search(rf"(?<![\w.]){re.escape(number)}\s*U\.?\s*S\.?\s*C\.?\s*(?:§+|sec\.?|section)"
                          rf"\s*{part}(?![\w-])", folded, re.I))


def _on(host, hosts):
    host = bare(host)
    return any(host == h or host.endswith("." + h) for h in hosts)


def _same_site(a, b):
    """One site: the same host but for "www.", or one a subdomain of the
    other."""
    a, b = bare(a), bare(b)
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def shown(url, final):
    """*final* as the cache may keep it: whole on *url*'s own site, and with
    no query anywhere else. A bot wall's redirect carries the reader's own
    address in its query (Radware's validate.perfdrive.com wrote the
    machine's IP address, base64-encoded, into "ssr=" on 2026-11-14), and
    no other host's query is the source's to say."""
    asked, ended = urllib.parse.urlsplit(url), urllib.parse.urlsplit(final or "")
    if (_same_site(asked.hostname or "", ended.hostname or "")
            and not agent.wall_host(final) and not _on(ended.hostname or "", WALL_HOSTS)):
        return (final or "")[:300]
    return urllib.parse.urlunsplit((ended.scheme, ended.hostname or "", ended.path, "", ""))[:300]


def _front_page(url, final):
    """Whether *final* is the front page of *url*'s own site and *url*, the
    cited address, is not: a deep link a site sends home is the classic
    answer of a page that has gone where the server will not say 404.
    Another host's front page is not the site's (eCFR sends a script to a
    bot wall's)."""
    asked, ended = urllib.parse.urlsplit(url), urllib.parse.urlsplit(final)
    if not _same_site(asked.hostname or "", ended.hostname or ""):
        return False
    deep = bool(asked.query) or not _FRONT.match(asked.path or "/")
    return deep and not ended.query and bool(_FRONT.match(ended.path or "/"))


def _decode(body, kind):
    charset = re.search(r"charset=([\w-]+)", kind or "", re.I)
    try:
        return body.decode(charset.group(1) if charset else "utf-8", "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def assess(url, seen):
    """``(answer, evidence, final address)`` for what :func:`visit` saw:
    ``open``, ``notfound``, ``elsewhere`` or ``nothing`` (the caller asks
    the public resolvers before a name that does not resolve is ``dead``)."""
    chain = seen["chain"]
    final = shown(url, chain[-1])
    moved = f" at {final}" if chain[-1] != url else ""
    status = seen["status"]
    end = urllib.parse.urlsplit(final).hostname or ""
    if status is None:
        return NOTHING, seen["error"] or "could not be reached", final
    if chain[-1] != url and _on(end, _SIGN_IN_HOSTS):
        return NOTHING, f"redirects to {bare(end)}, which asks visitors to sign in", final
    if chain[-1] != url and (agent.wall_host(chain[-1]) or _on(end, WALL_HOSTS)):
        # A bot wall's page, its redirect or its own 404 says nothing of the
        # page asked for.
        return NOTHING, f"HTTP {status} from a bot wall's host{moved}", final
    if 300 <= status < 400:
        return NOTHING, f"HTTP {status} without a usable redirect{moved}", final
    if status in (404, 410):
        return NOTFOUND, f"HTTP {status}{moved}", final
    body, kind = seen.get("body") or b"", seen.get("type") or ""
    if not 200 <= status < 300:
        # Said as what it is where the page says: constitution.congress.gov
        # answers this project 403 with Cloudflare's "Just a moment...".
        markup = _decode(body, kind) if body.strip() and _is_page(kind) else ""
        wall = (f", a bot wall's or a challenge's page ('{_words(page_title(markup), 60)}')"
                if markup and agent.walled(markup) else "")
        return NOTHING, f"HTTP {status}{wall}{moved}", final
    if not body.strip():
        return NOTHING, f"HTTP {status} with an empty body{moved}", final
    title = ""
    if _is_page(kind) and not body.lstrip().startswith(b"%PDF"):
        markup = _decode(body, kind)
        if agent.walled(markup):
            return NOTHING, f"a bot wall's or a challenge's page ('{_words(page_title(markup), 60)}'){moved}", final
        title = page_title(markup)
        if address(url).lower().endswith(".pdf"):
            # A page where a file was asked for may be a rejection page
            # (rule 52): it says nothing of the file.
            return NOTHING, f"HTTP {status}, a page where its address names a PDF ('{_words(title, 60)}'){moved}", final
        if _NOT_FOUND_TITLE.search(title):
            return ELSEWHERE_ANSWER, f"HTTP {status}, a page titled '{_words(title, 60)}'{moved}", final
    if _front_page(address(url), final):
        return ELSEWHERE_ANSWER, f"redirects to its site's front page, {final}", final
    section = code_section(url)
    if section and not names_section(title, section):
        return (ELSEWHERE_ANSWER, f"HTTP {status}, a page whose title ('{_words(title, 60)}') does not "
                                  f"name {section[0]} U.S.C. {section[1]}{moved}", final)
    what = f", titled '{_words(title, 60)}'" if title else (
        f", {_words(kind.split(';')[0], 40)}" if kind else "")
    return OPEN, f"HTTP {status}{what}{moved}", final


def read_one(url, gate, visit_fn=visit, doh_fn=doh, resolves=resolves_here):
    """One address read once: ``(answer, evidence, final address, answered)``;
    *answered* is False where nothing answered at all (a timeout, a refused
    connection), which counts against its host for this run."""
    seen = visit_fn(url, gate)
    answer, evidence, final = assess(url, seen)
    host = seen.get("dnsHost")
    if host and answer == NOTHING and resolves(host):
        # A lookup that failed while others ran can be this machine's
        # resolver's, not the host's: read once more.
        seen = visit_fn(url, gate)
        answer, evidence, final = assess(url, seen)
        host = seen.get("dnsHost")
    answered = seen.get("status") is not None
    if host and answer == NOTHING:
        answered = True                   # the name, not the host, failed
        if resolves(host):
            evidence = f"{host} did not resolve here on two tries, then did; not read"
        else:
            answers = doh_fn(host, gate)
            if len(answers) == 2 and all(a in ("nxdomain", "noaddress") for a in answers):
                what = "NXDOMAIN" if all(a == "nxdomain" for a in answers) else "no address record"
                lead = f"redirects to {host}: " if len(seen["chain"]) > 1 else f"{host}: "
                return DEAD, f"{lead}{what} here, at dns.google and at Cloudflare", final, answered
            if "servfail" in answers:
                evidence = (f"{host} did not resolve here, and a public resolver's lookup failed "
                            f"(its name servers do not answer); not confirmed gone")
            else:
                evidence = f"{host} did not resolve here; a public resolver did not confirm it gone"
    return answer, evidence, final, answered


# -------------------------------------------------------------------- cache

def _miss_words(misses):
    """"HTTP 404 on 2026-11-14 and 2026-11-21": each answer with its days."""
    days = {}
    for miss in misses:
        found = days.setdefault(miss["evidence"], [])
        if miss["day"] not in found:
            found.append(miss["day"])
    return "; ".join(f"{said} on {' and '.join(sorted(on))}" for said, on in days.items())


def settle(misses):
    """The verdict a run of answers that were not the source gives: ``gone``
    with 404 or 410 on two days, ``elsewhere`` on two days of which not both
    were 404 or 410, ``missing`` on one day only."""
    if len({m["day"] for m in misses if m["answer"] == NOTFOUND}) >= 2:
        return GONE
    if len({m["day"] for m in misses}) >= 2:
        return ELSEWHERE
    return MISSING


def merge(old, read, today, url=None):
    """What the cache keeps when *read*, ``(answer, evidence, final)``, is
    today's read of *url*, whose entry was *old*. A run of answers that are
    not the source is kept (``misses``) until the source opens again; a read
    that concludes nothing leaves the verdict as it was (rule 8)."""
    answer, evidence, final = read
    old = old or {}
    extra = {"final": final[:300]} if final and url and final != url else {}
    if answer == OPEN:
        return dict({"checked": today, "verdict": OK, "evidence": evidence}, **extra)
    if answer == DEAD:
        return {"checked": today, "verdict": GONE, "evidence": evidence}
    if answer in (NOTFOUND, ELSEWHERE_ANSWER):
        misses = (list(old.get("misses") or []) if old.get("verdict") in (MISSING, GONE, ELSEWHERE)
                  else [])
        # Read twice in a day, it is still one day's answer.
        misses = [m for m in misses if not (m["day"] == today and m["answer"] == answer)]
        misses.append({"day": today, "answer": answer, "evidence": evidence})
        # The run's first answer and its latest few: enough to say since when.
        if len(misses) > 4:
            misses = misses[:1] + misses[-3:]
        verdict = settle(misses)
        said = [m for m in misses if m["answer"] == NOTFOUND] if verdict == GONE else misses
        return dict({"checked": today, "verdict": verdict, "evidence": _miss_words(said),
                     "misses": misses}, **extra)
    if old.get("verdict") in VERDICTS and old.get("verdict") != UNREAD:
        return dict(old, tried=today, triedEvidence=evidence)
    return {"checked": today, "verdict": UNREAD, "evidence": evidence}


def last_look(entry):
    """The day an address was last looked at: its verdict's day, or a later
    try that concluded nothing and so left the verdict as it was."""
    return max((entry or {}).get("checked", ""), (entry or {}).get("tried", ""))


def due(entry, today, refresh=False):
    """Whether an address is to be opened today: never read, or read
    ``RECHECK_DAYS`` ago; a missing or unread one on any later day."""
    if not entry or refresh:
        return True
    look = last_look(entry)
    if entry.get("verdict") in (MISSING, UNREAD):
        return look < today
    try:
        then = datetime.date.fromisoformat(look)
    except ValueError:
        return True
    return (datetime.date.fromisoformat(today) - then).days >= RECHECK_DAYS


def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {"source": SOURCE, "sources": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    """One address a line, so a person can find and edit one."""
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sources = cache.get("sources", {})
    lines = [json.dumps(url, ensure_ascii=True) + ": " +
             json.dumps(sources[url], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
             for url in sorted(sources)]
    head = {k: v for k, v in cache.items() if k != "sources"}
    text = ("{\n" + "".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=True)},\n"
                            for k, v in sorted(head.items()))
            + ' "sources": {\n  ' + ",\n  ".join(lines) + "\n }\n}\n")
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(path + ".tmp", path)
    return path


# ---------------------------------------------------------------------- run

def check_all(root=".", workers=8, limit=None, refresh=False, max_seconds=None, log=print,
              read=read_one, gate=None, clock=time.monotonic, today=None):
    """Open every cited address that is due, several hosts at once and one
    request at a time per host, oldest first; saves the cache once at the
    end, keeping only the addresses something still cites.

    *max_seconds* is a time budget: once it is spent no new address is
    opened, the ones already open finish, and the run saves and ends
    cleanly, the rest waiting for the next (rule 78)."""
    cache = load_cache(root)
    cache["source"] = SOURCE
    cited = citations(root)
    entries = {url: entry for url, entry in (cache.get("sources") or {}).items() if url in cited}
    cache["sources"] = entries
    today = today or datetime.date.today().isoformat()
    todo = [u for u in cited if due(entries.get(u), today, refresh)]
    rank, per_host = {}, {}
    for url in todo:
        host = bare(urllib.parse.urlsplit(url).hostname or "")
        rank[url] = per_host.get(host, 0)
        per_host[host] = rank[url] + 1
    # Each host's addresses spread apart, round by round, so the workers are
    # not all waiting on one host's gate; the oldest looks first.
    todo.sort(key=lambda u: (last_look(entries.get(u)), rank[u], u))
    if limit:
        todo = todo[:limit]
    log(f"[..] {len(todo)} of {len(cited)} cited addresses to open, {workers} hosts at a time")
    gate = gate or _Gate(interval=HOST_INTERVAL)
    started = clock()
    lock = threading.Lock()
    failures, counts = {}, {"opened": 0, "late": 0, "skipped": 0}

    def one(url):
        host = bare(urllib.parse.urlsplit(url).hostname or "")
        if max_seconds is not None and clock() - started >= max_seconds:
            with lock:
                counts["late"] += 1
            return
        with lock:
            if failures.get(host, 0) >= HOST_FAILURES:
                counts["skipped"] += 1
                return
        try:
            answer, evidence, final, answered = read(url, gate)
        except Exception as exc:          # noqa: BLE001 - one address never stops the run
            answer, evidence, final, answered = (NOTHING, _words(f"read failed: {type(exc).__name__} "
                                                                f"{exc}", 120), url, True)
        with lock:
            failures[host] = 0 if answered else failures.get(host, 0) + 1
            entries[url] = merge(entries.get(url), (answer, evidence, final), today, url)
            counts["opened"] += 1
            if entries[url]["verdict"] != OK or answer != OPEN:
                log(f"    {entries[url]['verdict']:9} {url}: {evidence}")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(one, todo))
    save_cache(cache, root)
    if counts["late"]:
        log(f"[..] the time budget ({max_seconds / 60:,.0f} min) is spent: {counts['opened']} opened, "
            f"{counts['late']} left for the next run")
    if counts["skipped"]:
        log(f"[..] {counts['skipped']} left for the next run: their host answered nothing "
            f"{HOST_FAILURES} times running")
    return cache


# ----------------------------------------------------------------- the build

def summary(cache, cited=None):
    """``{verdict: count}`` over the cited addresses the cache holds."""
    counts = {}
    for url, entry in ((cache or {}).get("sources") or {}).items():
        if cited is not None and url not in cited:
            continue
        counts[entry.get("verdict")] = counts.get(entry.get("verdict"), 0) + 1
    return counts


def _cited_as(cites):
    return [f"{where} ({name})" for where, name in cites]


def problems(cache, cited, today=None):
    """``[(level, code, message, detail)]`` for the build: every one a
    warning, never an error - a site that is someone else's must not fail the
    refresh. A gone or elsewhere source by its address, its names and every
    section that cites it; the addresses never opened; those not looked at in
    ``WARN_DAYS``."""
    sources = (cache or {}).get("sources") or {}
    today = datetime.date.fromisoformat(today or datetime.date.today().isoformat())
    out = []
    for url in sorted(cited):
        entry = sources.get(url) or {}
        verdict = entry.get("verdict")
        if verdict not in WARNED:
            continue
        cites = cited[url]
        names = "; ".join(sorted({name for _where, name in cites}))
        where = ", ".join(sorted({w for w, _name in cites}))
        said = ("is gone" if verdict == GONE else "opens a page that is not it")
        out.append(("warn", f"guide-source-{verdict}",
                    f"{url} ({names}) {said}: {entry.get('evidence', '')}; cited in {where}. "
                    f"Find where it now is, cite that, and run 'guidesources'",
                    _cited_as(cites)))
    never = [url for url in sorted(cited) if not sources.get(url)]
    if never:
        out.append(("warn", "guide-source-unopened",
                    f"{len(never)} address(es) the guide cites have never been opened by "
                    f"'guidesources' ({CACHE_PATH})",
                    [f"{url}: {'; '.join(_cited_as(cited[url]))}" for url in never]))
    old = []
    for url in sorted(cited):
        try:
            then = datetime.date.fromisoformat(last_look(sources.get(url)))
        except ValueError:
            continue
        if (today - then).days > WARN_DAYS:
            old.append(f"{url}: last looked at {last_look(sources.get(url))}")
    if old:
        out.append(("warn", "guide-source-stale",
                    f"{len(old)} address(es) the guide cites were last looked at more than "
                    f"{WARN_DAYS} days ago; the weekly refresh runs 'guidesources' - is it running?",
                    old))
    return out


def unread_hosts(cache, cited):
    """``{host: count}`` of the cited addresses no read has opened: what the
    build says it could not confirm (never a warning: rule 8)."""
    counts = {}
    for url, entry in ((cache or {}).get("sources") or {}).items():
        if url in cited and entry.get("verdict") == UNREAD:
            host = bare(urllib.parse.urlsplit(url).hostname or "")
            counts[host] = counts.get(host, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
