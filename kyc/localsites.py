"""Whether each local government's website, as the Census listed it, still is one.

The 2022 Government Units listing (``localgov``) gives 39,452 governments a
website, and nothing checked them: a sample on 2026-10-17 found about one in
a hundred leading to a gambling, parked or for-sale domain under a public
body's name - Clinton, Connecticut's to a slot-machine demo, Vermilion
Parish's to SBOBET88, Bismarck's to a parked page - and about one in eight to
a host that no longer exists. A lapsed government domain is exactly the kind
that gets bought for gambling spam (rules 35 and 39).

``python build_profile_site.py localgov --check-sites`` opens every listed
address, one request at a time per host (redirect targets included) and many
hosts at once, and writes what it saw to ``data/local_sites.json``: per
address, the day it was checked, a verdict and the evidence. The cache is
hand-editable; a gambling verdict is never cleared by a later check, and a
host a person has confirmed goes in ``overrides.BLOCKED_LOCAL_HOSTS``.

The build (``kyc/counties.py``) withdraws an address whose verdict is in
``WITHDRAWN`` and labels the rest with the day they were checked:

* ``gambling`` - the page, or where it redirects, is gambling spam (one
  passage of a real page's text is withdrawn but waits for a person: see
  ``STICKY``);
* ``parked``, ``for-sale``, ``expired`` - a registrar's parking page (the
  ``window.location = "/lander"`` script of rule 39 included), a domain
  marketplace, an expired-domain notice;
* ``business`` - it redirects to a page whose title says it is a
  business's: Alma's address opens its chamber of commerce, Haverhill's an
  estate agent's listings, the Ringtown Borough Municipal Authority's a
  funeral home;
* ``elsewhere`` - it redirects to another site whose title and address
  carry no word of the government's name, whose text does not carry all
  of them, and which is not a government host. A page that names part of
  it - "City of Greenfield" for the listing's Town of Greenfield - is
  ``unread``: perhaps its own site under the name it uses, never claimed
  not to be. A page names it, and the move is kept (``moved``), with its
  distinctive words and a word for its kind in the title ("Pettisville
  Schools"), its whole name as a phrase, or a .gov host;
* ``dead`` - the host does not exist: it fails here and both dns.google and
  Cloudflare answer NXDOMAIN, or no address, for it (rule 35's second
  resolver);
* ``gone`` - the link's own host answers 404 or 410, twice.

Everything else that is not an answer concludes nothing (rule 8): a 403, a
429, a 5xx, a timeout, a certificate or connection failure, a bot wall, a
DNS server failure (SERVFAIL: a lame delegation), a page with too little
text to tell. A lookup that fails here but that a public resolver answers
is this machine's, under load, and the address is read again. Such an address is
``unread``: kept, and said to be unchecked.
"""

import datetime
import http.client
import http.cookiejar
import json
import os
import re
import socket
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import enrich, overrides

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "local_sites.json")
SOURCE = ("Each address as the Census Bureau's 2022 Government Units listing gives it, opened by "
          "'localgov --check-sites'")

OK = "ok"
MOVED = "moved"
UNREAD = "unread"
GAMBLING = "gambling"
PARKED = "parked"
FOR_SALE = "for-sale"
EXPIRED = "expired"
ELSEWHERE = "elsewhere"
BUSINESS = "business"
DEAD = "dead"
GONE = "gone"
VERDICTS = (OK, MOVED, UNREAD, GAMBLING, PARKED, FOR_SALE, EXPIRED, ELSEWHERE, BUSINESS, DEAD, GONE)
WITHDRAWN = (GAMBLING, PARKED, FOR_SALE, EXPIRED, ELSEWHERE, BUSINESS, DEAD, GONE)
# What a later check never clears: a domain once used for gambling spam
# under a government's name is not linked again without a person's look -
# where the spam was plain: in the page's title or headings, on the site a
# lapsed address now redirects to, or all over its text. One match in a
# real page's text is not plain: "Schedule your slot online" on the
# Keansburg schools' blood-drive notice read as gambling on 2026-10-17.
# Such a verdict is withdrawn, looked at again, and reported for a person
# to confirm in overrides.BLOCKED_LOCAL_HOSTS (``seen`` says which).
STICKY = (GAMBLING,)
PLAIN = ("head", "redirect", "text")
# A conclusive verdict is looked at again after this many days, so a site
# that comes back is linked again; an unread one on every run.
STALE_DAYS = 30
# The build warns once a listed address was last checked longer ago than
# this: the weekly refresh checks the oldest first, and an address it has
# not reached in two cycles says the refresh is not running.
WARN_DAYS = 60

TIMEOUT = 20
MAX_BODY = 600_000
HOPS = 8
HOST_INTERVAL = 1.0           # seconds between two requests to one host
DOH = (("dns.google", "https://dns.google/resolve?name={}&type={}", {}),
       ("cloudflare-dns.com", "https://cloudflare-dns.com/dns-query?name={}&type={}",
        {"Accept": "application/dns-json"}))


# --------------------------------------------------------------- signatures

# Gambling spam beyond enrich's campaign signatures: what the sample of
# 2026-10-17 found on lapsed government domains.
_SPAM_MORE = re.compile(
    r"\bslot\s*88\b|\bslot88|\bdemo\s+slot|\bslot\s+demo\b|\blink\s+slot|\bsitus\s+gacor|"
    r"\bgacor\b|\bkasino\s+online|\bsweepstakes\s+casinos?\b|\bagen\s+(?:slot|judi|togel)|"
    r"\btoto\s*(?:slot|macau|togel|gelap)|\bshio\s+togel|\bmawartoto|\bsbobet\d*|"
    r"\bjudi\s+(?:bola|online|slot)|\bcasino\s+sites?\b|\bonline\s+slots?\b|"
    # Brand names built on a betting word and a lucky number: "pgbet888",
    # "kartubet88", "laskar138" sites name themselves this way.
    r"\b[a-z]*(?:bet|slot|toto|win)(?:88|888|77|777|99|138|4d)\b|\bpgbet|"
    "nh\u00e0\\s+c\u00e1i|c\u00e1\\s+c\u01b0\u1ee3c|\\bqh88|"
    "\u30ab\u30b8\u30ce|\u535a\u5f69|\u767e\u5bb6\u4e50|\u5a31\u4e50\u57ce", re.I)
# "Slot online" is English too: "Schedule your slot online" (the Keansburg
# schools' blood drive), "Secure your 15-minute slot online" (the Landfill
# of North Iowa's Saturday drop-off). A slot someone books is not a slot
# machine; the phrase is taken out before the spam signatures are read.
_BOOKED_SLOT = re.compile(
    r"\b(?:your|a|an|the|my|our|their|this|that|one|time|appointment|delivery|pickup|pick-up)"
    r"\s+(?:[\w-]+\s+){0,2}slots?\s+online\b", re.I)
# A title that says what it is, and it is a business: the Alma address
# opens its chamber of commerce, Haverhill's an estate agent's listings,
# the Ringtown Borough Municipal Authority's a funeral home.
_BUSINESS = re.compile(
    r"chamber\s+of\s+commerce|homes?\s+for\s+sale|real\s+estate\s+(?:agents?|listings?|for\s+sale)|"
    r"\brealty\b|\brealtors?\b|\bfuneral\b|\bcremation\b|\bmortuary\b|"
    # The City of Phoenix, Oregon's address opens "Phoenix Best Hotels".
    r"\bbest\s+hotels\b", re.I)
_FOR_SALE = re.compile(
    r"domain\s+(?:name\s+)?(?:is|may\s+be)\s+for\s+sale|buy\s+this\s+domain|"
    r"this\s+domain\s+is\s+for\s+sale|make\s+an\s+offer\s+on\s+this\s+domain|"
    r"this\s+domain\s+(?:name\s+)?(?:is\s+)?available|hugedomains|afternic|"
    r"get\s+this\s+domain|inquire\s+about\s+this\s+domain|domain\s+broker", re.I)
_EXPIRED = re.compile(
    r"(?:this\s+)?domain\s+(?:name\s+)?(?:has\s+)?expired|domain\s+is\s+expired|"
    r"website\s+(?:has\s+)?expired|renew\s+(?:this|your)\s+domain|"
    r"expired\s+domain|expireddomains", re.I)
_PARKED_MORE = re.compile(
    r"this\s+domain\s+(?:is|has\s+been)\s+parked|parked\s+(?:free|domain)|"
    r"domain\s+parking|sedoparking|parkingcrew|bodis|above\.com|parklogic|"
    r"this\s+(?:web\s*page|site)\s+is\s+parked|most\s+relevant\s+links\s+on\s+all\s+topics|"
    r"related\s+searches|sponsored\s+listings", re.I)
# Where a domain marketplace or parking service lands a visitor.
_MARKET_HOSTS = (
    "forsale.godaddy.com", "afternic.com", "hugedomains.com", "dan.com", "sedo.com",
    "undeveloped.com", "buydomains.com", "domainmarket.com", "brandbucket.com",
    "squadhelp.com", "atom.com", "efty.com", "spaceship.com", "expireddomains.com",
    "namecheap.com", "domainnamesales.com", "domainagents.com", "sav.com", "epik.com",
)
_PARKING_HOSTS = ("sedoparking.com", "parkingcrew.net", "bodis.com", "above.com",
                  "parklogic.com", "park.godaddy.com", "ww1.", "ww25.", "searchvity.com")
# A private or deleted site on a hosting platform sends visitors to its
# sign-in page: not the government's site, and not anyone else's (rule 8).
_SIGN_IN_HOSTS = ("accounts.google.com", "login.microsoftonline.com", "login.live.com",
                  "login.yahoo.com")
# A web server's or a host's placeholder: the address answers, and says
# nothing of whose it is. Not a verdict - unread.
_PLACEHOLDER = re.compile(
    r"welcome\s+to\s+nginx|apache2?\s+(?:ubuntu\s+|debian\s+)?default\s+page|"
    r"iis\s+windows\s+server|test\s+page\s+for\s+the\s+(?:apache|nginx)|^index\s+of\s+/|"
    r"default\s+web\s+site\s+page|web\s+server'?s?\s+default\s+page", re.I)
_GENERATED = {"jr", "sr"}

# Words of a government's name that say what it is, not which one it is.
_GENERIC = set("""
    a an and at by for in of on or the to
    city town village borough township townships county counties parish municipality
    consolidated metropolitan metro unified government governments area areas
    school schools district districts unified union elementary high independent community
    public central joint regional special common free charter local vocational technical
    fire protection water sewer sewerage sanitary sanitation authority authorities housing
    library libraries park parks recreation cemetery cemeteries drainage levee irrigation
    conservation soil utility utilities municipal improvement development transit
    transportation hospital health services service board commission agency center port
    airport flood control road roads highway solid waste management mosquito abatement
    emergency ambulance rural north south east west northern southern eastern western
    new upper lower office education educational cooperative association department
    no number unit units corporation corp inc system systems supply resource resources
    natural industrial economic financing finance insurance risk pool benefits trust
    medical memorial district's valley lake river creek mount saint st mt ft fort
    admin administrative uni operated superintendent supervisory modified benefit
""".split())
# What a government is, by the head word of its name: "Town of Clinton" is
# a town, "Ringtown Borough Municipal Authority" an authority.
_HEADS = ("city", "town", "village", "borough", "township", "county", "parish", "municipality",
          "district", "authority", "board", "commission", "school", "schools", "library",
          "department", "agency", "corporation", "council", "system", "trust", "center",
          "college", "cemetery", "hospital", "port", "unit", "association", "cooperative",
          "zone", "area", "commissioners", "trustees", "government")


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def near(a, b):
    """Whether two words of six letters or more are one slip apart: a
    letter added, dropped, changed, or two letters swapped. The listing
    misspells names ("Las Virgenes Muncipal", "Kinneola", "Davenport
    Commmunity"); the bodies' own pages spell them right."""
    if a == b:
        return True
    if min(len(a), len(b)) < 6 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


_GENERIC_LONG = sorted(w for w in _GENERIC if len(w) >= 6)


def distinctive(name):
    """The words of a government's name that tell it from others of its
    kind: ``["covina"]`` for "Covina Valley Unified School District"."""
    # Read with the listing's abbreviations written out, or "Central Ind
    # Sch Dist" would ask a page for "ind", "sch" and "dist".
    from .localgov import expand_name
    words = re.findall(r"[a-z0-9]+", fold(expand_name(name)))
    return [w for w in words if w not in _GENERIC and w not in _GENERATED
            and len(w) >= 3 and not w.isdigit()
            # A misspelt generic word is still generic ("Muncipal").
            and not any(near(w, g) for g in _GENERIC_LONG)]


class _Words:
    """A text's words, for asking whether a name's words are among them -
    as words, one slip apart, or run together ("DesPlaines" for "Des
    Plaines", "Twentynine" for "Twenty-Nine", "O'Neill" for "Oneill")."""

    def __init__(self, text):
        tokens = re.findall(r"[a-z0-9]+", fold(text))
        self.words = set(tokens)
        self.pairs = {a + b for a, b in zip(tokens, tokens[1:])}
        self._long = [w for w in self.words if len(w) >= 5]

    def has(self, word):
        return (word in self.words or word in self.pairs
                or (len(word) >= 6 and any(near(word, w) for w in self._long)))

    def found(self, words):
        """Which of *words* (a name's distinctive words, in order) are here."""
        out = {w for w in words if self.has(w)}
        for a, b in zip(words, words[1:]):
            if a + b in self.words:
                out |= {a, b}
        return out


def names_government(names, text):
    """True when *text* names one of *names* - every distinctive word of it,
    as words - and ``None`` when no name has a distinctive word to look for."""
    seen = _Words(text)
    tried = False
    for name in names:
        words = distinctive(name)
        if not words:
            continue
        tried = True
        if seen.found(words) >= set(words):
            return True
    return False if tried else None


def names_part(names, text):
    """Whether *text* carries any distinctive word of one of *names*."""
    seen = _Words(text)
    return any(seen.found(distinctive(n)) for n in names)


def head_word(name):
    """The word that says what a government is: the form before "of" ("Town
    of Clinton"), else the last such word of its name ("... Authority")."""
    words = re.findall(r"[a-z]+", fold(name))
    if len(words) > 2 and words[1] == "of" and words[0] in _HEADS:
        return words[0]
    heads = [w for w in words if w in _HEADS]
    return heads[-1] if heads else ""


def _phrases(name):
    """The ways a page writes a government's name as a phrase: "town of
    clinton" and "clinton town"; a district without its number."""
    words = re.findall(r"[a-z0-9]+", fold(name))
    while words and (words[-1].isdigit() or re.fullmatch(r"[ivx]+|[a-z]?\d+[a-z]?", words[-1])):
        words = words[:-1]
    out = set()
    if words:
        out.add(" ".join(words))
    if len(words) > 2 and words[1] == "of" and words[0] in _HEADS:
        out.add(" ".join(words[2:] + words[:1]))
    # "Cabell County Public Library Board" writes itself "Cabell County
    # Public Library"; the shorter phrase still says what it is.
    if len(words) > 3 and words[-1] in ("board", "district", "commission", "trustees"):
        out.add(" ".join(words[:-1]))
    return {p for p in out if len(p.split()) >= 2}


def names_as_government(names, text):
    """Whether *text* names one of *names* as a government - the whole name
    as a phrase, "Town of Haverhill" or "Haverhill Town" - not merely the
    place: the chamber of commerce and the estate agent the Bennington and
    Haverhill addresses now open name the town too, and the funeral home
    the Ringtown Borough Municipal Authority's opens names Ringtown."""
    seen = " " + " ".join(re.findall(r"[a-z0-9]+", fold(text))) + " "
    return any(" " + p + " " in seen for n in names for p in _phrases(n))


# The words of a name that say what kind of body it is, and the words a
# site's own title uses for the same kind: "Pettisville Local School
# District" titles its new site "Pettisville Schools", the Chattanooga
# Metropolitan Airport Authority's is "Chattanooga Airport".
_OFFICIAL = "official-website"
_KIND_WORDS = {
    "city": {"city", _OFFICIAL}, "town": {"town", _OFFICIAL}, "village": {"village", _OFFICIAL},
    "borough": {"borough", _OFFICIAL}, "township": {"township", "twp", _OFFICIAL},
    "county": {"county", _OFFICIAL}, "parish": {"parish", _OFFICIAL},
    "municipality": {"municipality", _OFFICIAL},
    "school": {"school", "schools", "isd", "usd", "csd", "cusd", "sd", "academy", "education"},
    "schools": {"school", "schools", "isd", "usd", "csd", "cusd", "sd", "education"},
    "education": {"education", "school", "schools"},
    "library": {"library", "libraries", "librarys"}, "libraries": {"library", "libraries"},
    "fire": {"fire"}, "ambulance": {"ambulance", "ems"}, "water": {"water"},
    "sewer": {"sewer", "wastewater"}, "sewerage": {"sewer", "wastewater"},
    "sanitary": {"sanitary", "sanitation"}, "sanitation": {"sanitary", "sanitation"},
    "housing": {"housing"}, "park": {"park", "parks"}, "parks": {"park", "parks"},
    "recreation": {"recreation", "rec"}, "cemetery": {"cemetery", "cemeteries"},
    "drainage": {"drainage"}, "levee": {"levee"}, "irrigation": {"irrigation"},
    "conservation": {"conservation"}, "soil": {"soil"}, "utility": {"utility", "utilities", "pud"},
    "utilities": {"utility", "utilities"}, "transit": {"transit", "bus", "metro"},
    "transportation": {"transportation", "transit"}, "metro": {"metro", "transit"},
    "hospital": {"hospital", "health", "medical"}, "health": {"health"},
    "medical": {"medical", "health", "hospital"}, "airport": {"airport"}, "port": {"port"},
    "flood": {"flood"}, "mosquito": {"mosquito"}, "college": {"college"},
    "union": {"union"},
    "workforce": {"workforce"},
}
# A school district's own initials in the listing ("North Santiam SD 29 J")
# say what it is as well as the words do.
for _initials in ("sd", "isd", "usd", "csd", "cusd", "ufsd"):
    _KIND_WORDS[_initials] = _KIND_WORDS["school"]


def names_in_title(names, head):
    """Whether a page's title and headings (*head*) name one of *names*:
    every distinctive word of it and a word for its kind. "Pettisville
    Schools" names the Pettisville Local School District; "Alma Chamber of
    Commerce" does not name the City of Alma, nor "Haverhill, New
    Hampshire Real Estate" the Town of Haverhill. A municipality's title
    may call itself its official website instead ("Salisbury, MA |
    Official Website", on its web host's platform)."""
    seen = _Words(head)
    if re.search(r"\bofficial\s+(?:web\s*)?site\b", fold(head)):
        seen.words.add(_OFFICIAL)
    for name in names:
        words = distinctive(name)
        if not words or not seen.found(words) >= set(words):
            continue
        kinds = set()
        from .localgov import expand_name
        for word in re.findall(r"[a-z]+", fold(expand_name(name))):
            kinds |= _KIND_WORDS.get(word, set())
        if kinds & seen.words:
            return True
    return False


def in_host(names, host, every=True):
    """Whether a host's name spells out every distinctive word of one of
    *names* ("dewittcountyil.gov" for the County of De Witt) - or, with
    *every* false, any one of four letters or more ("29palmswater.com" for
    the Twenty-Nine Palms Water District)."""
    label = re.sub(r"[^a-z0-9]", "", bare(host).rsplit(".", 1)[0])
    for name in names:
        words = distinctive(name)
        if every and words and all(w in label for w in words):
            return True
        if not every and any(len(w) >= 4 and w in label for w in words):
            return True
    return False


def names_place(names, head):
    """Whether *head* carries any distinctive word of one of *names*."""
    return names_part(names, head)


def bare(host):
    host = (host or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _official(host):
    """A namespace only a government can hold: .gov, and a state's .us
    locality names (ci.groton.ma.us, k12.wi.us)."""
    host = bare(host)
    return host.endswith(".gov") or bool(re.search(r"\.[a-z]{2}\.us$", host))


def same_site(a, b):
    """One site: the same host but for "www.", or one a subdomain of the
    other (cityofx.org and portal.cityofx.org)."""
    a, b = bare(a), bare(b)
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def _on(host, hosts):
    host = bare(host)
    return any(host == h or host.endswith("." + h) or (h.endswith(".") and host.startswith(h))
               for h in hosts)


def _snippet(text, limit=90):
    """ASCII words for the evidence: page text can carry anything."""
    text = fold(" ".join((text or "").split()))
    text = "".join(ch for ch in text if 32 <= ord(ch) < 127)
    return text[:limit].strip()


# ------------------------------------------------------------------ network

class _Gate:
    """One request at a time to any one host, at least *interval* apart."""

    def __init__(self, interval=HOST_INTERVAL, sleep=time.sleep, clock=time.monotonic,
                 intervals=None):
        self.interval, self.sleep, self.clock = interval, sleep, clock
        self.intervals = dict(intervals or {})
        self._locks, self._last, self._guard = {}, {}, threading.Lock()

    def hold(self, host):
        host = bare(host)
        with self._guard:
            lock = self._locks.setdefault(host, threading.Lock())
        gate = self

        class _Held:
            def __enter__(self_inner):
                lock.acquire()
                wait = (gate._last.get(host, -1e9) + gate.intervals.get(host, gate.interval)
                        - gate.clock())
                if wait > 0:
                    gate.sleep(wait)
                return self_inner

            def __exit__(self_inner, *exc):
                gate._last[host] = gate.clock()
                lock.release()
                return False
        return _Held()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE


def _dns_failed(exc):
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, socket.gaierror)


def _tls_failed(exc):
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (ssl.SSLError, ssl.CertificateError))


def _request(url, jar, context, timeout=TIMEOUT):
    """``(status, headers, body bytes, location)``; raises URLError/OSError."""
    handlers = [urllib.request.HTTPCookieProcessor(jar), _NoRedirect()]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    # The listing writes a few addresses with spaces in their paths.
    url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    req = urllib.request.Request(url, headers=enrich._UA_WEB)
    try:
        with opener.open(req, timeout=timeout) as response:
            kind = response.headers.get("Content-Type") or "text/html"
            body = response.read(MAX_BODY) if ("html" in kind or "text" in kind) else b""
            return response.status, response.headers, body, None
    except urllib.error.HTTPError as exc:
        where = exc.headers.get("Location") if exc.headers else None
        try:
            body = exc.read(MAX_BODY) if 400 <= exc.code < 500 else b""
        except Exception:
            body = b""
        return exc.code, exc.headers, body, where


def _markup(headers, body):
    raw = enrich._decoded(body, headers.get("Content-Encoding") if headers else None)
    if raw is None:
        return None
    charset = (headers.get_content_charset() if headers else None) or "utf-8"
    try:
        return raw.decode(charset, "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


def visit(url, gate, request=_request):
    """Follow *url* to where it ends, by hand, one hop at a time through the
    gate. ``{"chain": [urls], "status", "markup", "error", "dnsHost",
    "insecure"}``; never raises."""
    jar = http.cookiejar.CookieJar()
    out = {"chain": [url], "status": None, "markup": "", "error": "", "dnsHost": "",
           "insecure": False}
    current, context = url, None
    for _hop in range(HOPS):
        host = urllib.parse.urlsplit(current).hostname or ""
        try:
            with gate.hold(host):
                try:
                    status, headers, body, where = request(current, jar, context)
                except urllib.error.URLError as exc:
                    if not _tls_failed(exc) or context is not None:
                        raise
                    # A government site with a lapsed certificate is still
                    # read for what it is; a browser would warn.
                    context = _UNVERIFIED
                    out["insecure"] = True
                    status, headers, body, where = request(current, jar, context)
        except urllib.error.URLError as exc:
            if _dns_failed(exc):
                out["dnsHost"] = host
                out["error"] = f"{host} does not resolve here"
            else:
                out["error"] = _snippet(str(getattr(exc, "reason", exc)), 80) or "connection failed"
            return out
        except (OSError, ValueError, http.client.HTTPException) as exc:
            out["error"] = _snippet(f"{type(exc).__name__} {exc}", 80) or "connection failed"
            return out
        out["status"] = status
        if 300 <= status < 400 and where:
            nxt = urllib.parse.urljoin(current, where.strip())
            if not nxt.lower().startswith(("http://", "https://")) or nxt in out["chain"][-3:]:
                return out
            out["chain"].append(nxt)
            current = nxt
            continue
        markup = _markup(headers, body) or ""
        out["markup"] = markup
        # A page that only sends the browser on, in script or a meta
        # refresh, is followed: a parked domain's page is one line of
        # script to "/lander" (rule 39).
        if status == 200 and len(markup) < 4000:
            jump = enrich._SCRIPT_REDIRECT.search(markup)
            if jump:
                nxt = urllib.parse.urljoin(current, (jump.group(1) or jump.group(2)).strip())
                if nxt.startswith("http") and nxt.rstrip("/") != current.rstrip("/") \
                        and nxt not in out["chain"]:
                    out["chain"].append(nxt)
                    current = nxt
                    continue
        return out
    out["error"] = "too many redirects"
    out["status"] = None
    return out


# Public resolvers are built for millions of queries a second: a few at a
# time from here, unpaced, is still nothing to them. Paced like a small
# town's web server, they were the whole run's bottleneck.
_DOH_SLOTS = threading.BoundedSemaphore(12)


def doh(name, gate, get=None):
    """``"nxdomain"``, ``"noaddress"``, ``"exists"``, ``"servfail"`` or
    ``None`` (could not ask) for *name* at each public resolver, as a
    tuple. Only NXDOMAIN or no address at both makes a host dead."""
    answers = []
    for host, template, headers in DOH:
        verdict = None
        for rtype in ("A", "AAAA"):
            try:
                with _DOH_SLOTS:
                    if get is not None:
                        data = get(template.format(urllib.parse.quote(name), rtype), headers)
                    else:
                        req = urllib.request.Request(
                            template.format(urllib.parse.quote(name), rtype),
                            headers=dict({"User-Agent": "know-your-candidate"}, **headers))
                        with urllib.request.urlopen(req, timeout=15) as response:
                            data = json.loads(response.read().decode("utf-8"))
            except Exception:
                verdict = None
                break
            status = data.get("Status")
            if status == 3:
                verdict = "nxdomain"
                break
            if status != 0:
                # SERVFAIL (2): the name's own servers refuse or do not
                # answer - not an absence (rule 8).
                verdict = "servfail" if status == 2 else None
                break
            if any(a.get("type") in (1, 28) for a in data.get("Answer") or []):
                verdict = "exists"
                break
            verdict = "noaddress"
        answers.append(verdict)
        if verdict not in ("nxdomain", "noaddress"):
            break                     # one resolver that finds it, or cannot say, is enough
    return tuple(answers)


def resolves_here(host):
    try:
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- the check

def gambling_at(head, body, moved):
    """Where a page shows gambling spam - ``"head"`` (its title, headings or
    description), ``"redirect"`` (anywhere on a site a lapsed address now
    sends visitors to), ``"text"`` (throughout its text) or ``"once"`` (once
    or twice in its text) - or ``""``. A slot someone books online is not a
    slot machine."""
    head, body = _BOOKED_SLOT.sub(" ", head), _BOOKED_SLOT.sub(" ", body)
    if enrich._SPAM.search(head) or _SPAM_MORE.search(head) or enrich._GAMBLING.search(head):
        return "head"
    spam, more, words = (len(enrich._SPAM.findall(body)), len(_SPAM_MORE.findall(body)),
                         len(enrich._GAMBLING.findall(body)))
    if not (spam or more >= 3 or words >= 5):
        return ""
    if moved:
        return "redirect"
    return "text" if spam + more + words >= 3 else "once"


def assess(names, url, seen):
    """``(verdict, evidence, final url)`` for what :func:`visit` saw, before
    any DNS or second-request confirmation (the caller does those)."""
    return _assess(names, url, seen)[:3]


def _assess(names, url, seen):
    """:func:`assess`, and where a gambling page showed its spam
    (:func:`gambling_at`; ``""`` for any other verdict)."""
    chain = seen["chain"]
    final = chain[-1]
    start, end = urllib.parse.urlsplit(url).hostname or "", urllib.parse.urlsplit(final).hostname or ""
    # A site that moved onto a host's platform under its own address -
    # sites.google.com/a/rollinsford.k12.nh.us/... - has not left it.
    moved = not same_site(start, end) and bare(start) not in final.lower()
    where = f"redirects to {bare(end)}: " if moved else ""
    if moved and _on(end, _SIGN_IN_HOSTS):
        return UNREAD, f"redirects to {bare(end)}, which asks visitors to sign in", final, ""
    if _on(end, _MARKET_HOSTS):
        return FOR_SALE, f"redirects to {bare(end)}, a domain marketplace", final, ""
    if _on(end, _PARKING_HOSTS):
        return PARKED, f"redirects to {bare(end)}, a parking service", final, ""
    if urllib.parse.urlsplit(final).path.rstrip("/").endswith("/lander"):
        return (PARKED, f"{where}a script sends visitors to a parking lander ({bare(end)}/lander)",
                final, "")
    status = seen["status"]
    if status is None:
        return UNREAD, seen["error"] or "could not be reached", final, ""
    if 300 <= status < 400:
        return UNREAD, f"HTTP {status} without a usable redirect", final, ""
    markup = seen["markup"]
    page = enrich.parse_page(markup)
    head = " ".join([page.title] + [page.meta.get(k, "") for k in
                     ("description", "og:description", "og:title")]
                    + [h for t, h in page.headings if t in ("h1", "h2")])
    body = page.body
    title = _snippet(page.title or (page.headings[0][1] if page.headings else ""), 60)
    quoted = f" ('{title}')" if title else ""
    spam = gambling_at(head, body, moved)
    if spam:
        once = " (one passage of its text)" if spam == "once" else ""
        return GAMBLING, f"{where}gambling page{quoted}{once}", final, spam
    if status != 200:
        if status in (404, 410):
            return (GONE if not moved else UNREAD), f"{where}HTTP {status}", final, ""
        return UNREAD, f"{where}HTTP {status}", final, ""
    small = len(body) < 2500
    if _FOR_SALE.search(head) or (small and _FOR_SALE.search(body)):
        return FOR_SALE, f"{where}domain for sale{quoted}", final, ""
    if _EXPIRED.search(head) or (small and _EXPIRED.search(body)):
        return EXPIRED, f"{where}expired domain{quoted}", final, ""
    if (enrich._PARKED.search(head) or (small and enrich._PARKED.search(body))
            or enrich._PARKING_CODE.search(page.small) or _PARKED_MORE.search(head)
            or (small and _PARKED_MORE.search(body))):
        return PARKED, f"{where}parked domain{quoted}", final, ""
    if _PLACEHOLDER.search(head) or (small and _PLACEHOLDER.search(body)):
        return UNREAD, f"{where}a web server's placeholder page{quoted}", final, ""
    if enrich._SPAM.search(page.hidden) or enrich._GAMBLING.search(page.hidden):
        return OK, f"{where}answers, and hides gambling links in its page{quoted}", final, ""
    if not moved:
        return OK, "", final, ""
    text = " ".join([head, body] + [h for _t, h in page.headings])
    named = names_government(names, text)
    # A move is kept where the new page names the government: in its title
    # and headings with a word for what it is, as a phrase anywhere, or on
    # a .gov host - which only a government can hold - by its distinctive
    # words; a government address (.gov, a state's .us names) that now
    # opens another .gov naming the place has moved within government.
    if (names_in_title(names, head) or names_as_government(names, text)
            or (named and _official(end))
            or (_official(start) and bare(end).endswith(".gov") and names_place(names, head))
            or (bare(end).endswith(".gov") and in_host(names, end))):
        return MOVED, f"redirects to {bare(end)}, which names it{quoted}", final, ""
    if len(body) < 200:
        return UNREAD, f"redirects to {bare(end)}, with too little text to tell{quoted}", final, ""
    if named is None:
        return UNREAD, f"redirects to {bare(end)}; its name has no word to look for{quoted}", final, ""
    # A title that says the page is a business's - a chamber of commerce,
    # an estate agent, a funeral home - is not the government's, whatever
    # place it names.
    if _BUSINESS.search(head):
        return BUSINESS, f"redirects to {bare(end)}, a business's page{quoted}", final, ""
    # Otherwise a page that names any part of it - a word of its name in
    # the title or the address, all of them in its text, or a host only a
    # government can hold - may well be its own, under the name it uses
    # itself: "City of Greenfield" for the listing's Town of Greenfield,
    # "Bartlett Fire District" on bartlettilfd.gov for the
    # Bartlett-Countryside Fire Protection District, "Welcome - Miamisburg,
    # OH". The first full run withdrew such pages as "elsewhere" and the
    # page said they did not name the body; a failed match concludes
    # nothing (rule 8).
    if names_part(names, head) or in_host(names, end, every=False) or named or _official(end):
        return (UNREAD, f"redirects to {bare(end)}, which names part of it; not confirmed as its "
                        f"site{quoted}", final, "")
    return ELSEWHERE, (f"redirects to {bare(end)}, whose page and address name none of "
                       f"it{quoted}"), final, ""


def sticky(entry):
    """Whether a verdict stays whatever a later check finds: gambling spam
    seen plainly (``PLAIN``). An entry from before ``seen`` was recorded
    stays too, until a person looks."""
    return bool(entry) and entry.get("verdict") in STICKY and entry.get("seen", "head") in PLAIN


def check_one(url, names, gate, visit_fn=visit, doh_fn=doh, resolves=resolves_here,
              sleep=time.sleep, today=None):
    """One address, start to finish: ``{"checked", "verdict", "evidence",
    "final"?}``."""
    today = today or datetime.date.today().isoformat()
    seen = visit_fn(url, gate)
    verdict, evidence, final, spam = _assess(names, url, seen)
    if seen.get("dnsHost") and verdict == UNREAD:
        host = seen["dnsHost"]
        # A local lookup that fails while many run at once can be this
        # machine's resolver, not the host: one that answers on a second
        # try, or that a public resolver finds, is read again.
        retried = False
        if resolves(host):
            retried = True
        else:
            answers = doh_fn(host, gate)
            if answers and answers[0] == "exists":
                sleep(5)
                retried = resolves(host)
        if retried:
            sleep(2)
            seen = visit_fn(url, gate)
            verdict, evidence, final, spam = _assess(names, url, seen)
    if seen.get("dnsHost") and verdict == UNREAD:
        host = seen["dnsHost"]
        own = len(seen["chain"]) == 1
        if not resolves(host):
            answers = doh_fn(host, gate)
            if len(answers) == 2 and all(a in ("nxdomain", "noaddress") for a in answers):
                what = ("NXDOMAIN" if all(a == "nxdomain" for a in answers)
                        else "no address record")
                if own:
                    verdict, evidence = DEAD, f"{host}: {what} here, at dns.google and at Cloudflare"
                else:
                    verdict, evidence = DEAD, (f"redirects to {host}: {what} here, at dns.google "
                                               f"and at Cloudflare")
            elif "servfail" in answers:
                evidence = (f"{host} did not resolve here, and a public resolver's lookup failed "
                            f"(its name servers do not answer); not confirmed gone")
            else:
                evidence = f"{host} did not resolve here; a public resolver did not confirm it gone"
    elif verdict == GONE:
        # A page not found is looked at once more before it is withdrawn.
        sleep(3)
        again = visit_fn(url, gate)
        second, _ev, _final = assess(names, url, again)
        if second != GONE:
            verdict, evidence = UNREAD, f"{evidence}, then {again.get('status') or again.get('error')}"
        else:
            evidence = f"{evidence}, twice"
    entry = {"checked": today, "verdict": verdict}
    if spam:
        entry["seen"] = spam
    if evidence:
        entry["evidence"] = evidence
    if seen.get("insecure"):
        entry["evidence"] = (entry.get("evidence", "") + "; its certificate is not valid").lstrip("; ")
    if final and not same_site(urllib.parse.urlsplit(url).hostname or "",
                               urllib.parse.urlsplit(final).hostname or ""):
        entry["final"] = final[:300]
    return entry


# ------------------------------------------------------------------- cache

def load_cache(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return {"source": SOURCE, "sites": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_cache(cache, root="."):
    """One address a line, so a person can find and edit one."""
    path = os.path.join(root, CACHE_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sites = cache.get("sites", {})
    lines = [json.dumps(url, ensure_ascii=True) + ": " +
             json.dumps(sites[url], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
             for url in sorted(sites)]
    head = {k: v for k, v in cache.items() if k != "sites"}
    text = ("{\n" + "".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=True)},\n"
                            for k, v in sorted(head.items()))
            + ' "sites": {\n  ' + ",\n  ".join(lines) + "\n }\n}\n")
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(path + ".tmp", path)
    return path


def targets(root=".", codes=None):
    """``{address: [government names]}`` for every listed website, the
    address as the county pages link it."""
    from . import counties, localgov
    from .government_maps import STATES
    out = {}
    for code in codes or STATES:
        listing = localgov.load(code, root)
        if not listing:
            continue
        govs = [g for e in listing["counties"].values() for g in e["governments"]]
        govs += listing.get("statewide", [])
        for gov in govs:
            url = counties.web_address(gov.get("web", ""))
            if url:
                names = out.setdefault(url, [])
                for name in (localgov.expand_name(gov["name"]), gov["name"]):
                    if name not in names:
                        names.append(name)
    return out


def last_look(entry):
    """The day an address was last looked at: its verdict's day, or a later
    try that concluded nothing and so left the verdict as it was."""
    return max((entry or {}).get("checked", ""), (entry or {}).get("tried", ""))


def due(entry, today, refresh=False, recheck=()):
    """Whether an address needs looking at today. *recheck* names verdicts
    to look at again whatever their date - after a change to how a verdict
    is reached (never a sticky one: that takes a person, rule 39)."""
    if not entry:
        return True
    if entry.get("verdict") in recheck and not sticky(entry):
        return True
    if sticky(entry) and not refresh:
        return False
    if refresh or entry.get("verdict") == UNREAD:
        return True
    try:
        then = datetime.date.fromisoformat(last_look(entry))
    except ValueError:
        return True
    return (datetime.date.fromisoformat(today) - then).days >= STALE_DAYS


def merge(old, new, today):
    """What the cache keeps when *new* is today's look at an address whose
    entry was *old*. Plain gambling stays whatever is seen later (rule 39),
    and a look that concludes nothing (``unread``) does not undo a
    withdrawal (rule 8): the verdict and its day stay, and the try is
    dated beside them."""
    if old and ((sticky(old) and new.get("verdict") != GAMBLING)
                or (old.get("verdict") in WITHDRAWN and new.get("verdict") == UNREAD)):
        return dict(old, tried=today)
    return new


def check_all(root=".", codes=None, workers=24, limit=None, refresh=False, retry_unread=True,
              log=print, save_every=500, check=check_one, recheck=(), max_seconds=None,
              clock=time.monotonic):
    """Open every address that is due, many hosts at once and one request at
    a time per host; saves the cache as it goes, so a stopped run resumes.
    The addresses looked at longest ago go first, so a run capped with
    *limit* each week (the refresh workflow) works through all of them.

    *max_seconds* is a time budget: once it is spent no new address is
    opened, the ones already open finish, and the cache is saved once, so
    the run ends cleanly and the rest wait for the next. A run killed at its
    step's time limit instead saved its cache from threads still finishing
    after the next step had read it, and verify found the county files
    stale (the refresh of 2026-10-19)."""
    cache = load_cache(root)
    cache["source"] = SOURCE
    sites = cache.setdefault("sites", {})
    today = datetime.date.today().isoformat()
    wanted = targets(root, codes)
    todo = [u for u in sorted(wanted)
            if due(sites.get(u), today, refresh, recheck) and (retry_unread or not sites.get(u)
                                                     or sites[u].get("verdict") != UNREAD)]
    # Each host's addresses spread apart, round by round, so the workers
    # are not all waiting on one host's gate.
    rank, seen_hosts = {}, {}
    for u in todo:
        host = bare(urllib.parse.urlsplit(u).hostname or "")
        rank[u] = seen_hosts.get(host, 0)
        seen_hosts[host] = rank[u] + 1
    todo.sort(key=lambda u: (last_look(sites.get(u)), rank[u], u))
    if limit:
        todo = todo[:limit]
    log(f"[..] {len(todo):,} of {len(wanted):,} addresses to check, {workers} at a time")
    gate = _Gate()
    started = clock()
    lock = threading.Lock()
    done = [0]
    late = [0]

    def one(url):
        if max_seconds is not None and clock() - started >= max_seconds:
            with lock:
                late[0] += 1
            return
        try:
            entry = check(url, wanted[url], gate, today=today)
        except Exception as exc:          # one address never stops the run
            entry = {"checked": today, "verdict": UNREAD,
                     "evidence": _snippet(f"check failed: {type(exc).__name__} {exc}", 100)}
        with lock:
            sites[url] = merge(sites.get(url), entry, today)
            done[0] += 1
            if done[0] % save_every == 0:
                save_cache(cache, root)
                log(f"    {done[0]:,} checked, {clock() - started:,.0f} s")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    save_cache(cache, root)
    if late[0]:
        log(f"[..] the time budget ({max_seconds / 60:,.0f} min) is spent: {done[0]:,} checked, "
            f"{late[0]:,} left for the next run")
    return cache


# ----------------------------------------------------------------- the build

def blocked(url):
    """The overrides.BLOCKED_LOCAL_HOSTS key that bars *url*, or None."""
    try:
        host = (urllib.parse.urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return None
    for key in (host, bare(host)):
        if key and key in overrides.BLOCKED_LOCAL_HOSTS:
            return key
    return None


def status(url, cache):
    """What the page shows for a listed address: ``(link or "", note)``,
    the note ``"<verdict> <date>"`` - "" when it was never checked."""
    if not url:
        return "", ""
    key = blocked(url)
    if key:
        kind, day, _seen = overrides.BLOCKED_LOCAL_HOSTS[key]
        return "", f"{kind} {day}"
    entry = ((cache or {}).get("sites") or {}).get(url)
    if not entry or entry.get("verdict") not in VERDICTS:
        return url, ""
    verdict, day = entry["verdict"], entry.get("checked", "")
    if verdict in WITHDRAWN:
        return "", f"{verdict} {day}"
    if verdict == MOVED:
        verdict = OK
    return url, f"{verdict} {day}"


def summary(cache, urls=None):
    """``{verdict: count}`` over the cache, or the addresses in *urls*."""
    counts = {}
    for url, entry in ((cache or {}).get("sites") or {}).items():
        if urls is not None and url not in urls:
            continue
        counts[entry.get("verdict")] = counts.get(entry.get("verdict"), 0) + 1
    return counts


def stale_blocks(addresses):
    """BLOCKED_LOCAL_HOSTS keys that no listed address uses any more."""
    used = {blocked(u) for u in addresses}
    return sorted(k for k in overrides.BLOCKED_LOCAL_HOSTS if k not in used)


def problems(cache, addresses, today=None):
    """What the build reports about the website check, as strings."""
    out = [f"overrides.BLOCKED_LOCAL_HOSTS[{k!r}] matches no listed website; remove it"
           for k in stale_blocks(addresses)]
    sites = (cache or {}).get("sites") or {}
    unchecked = [u for u in addresses if u not in sites and not blocked(u)]
    if unchecked:
        out.append(f"{len(unchecked):,} listed local-government websites have never been checked "
                   f"(run 'localgov --check-sites'); they are linked and marked unchecked")
    # A check is a day's finding, and domains keep lapsing (rule 39): the
    # weekly refresh looks at the oldest first, so an old one means it is
    # not running.
    today = datetime.date.fromisoformat(today or datetime.date.today().isoformat())
    old = []
    for url in addresses:
        try:
            then = datetime.date.fromisoformat(last_look(sites.get(url)))
        except ValueError:
            continue
        if (today - then).days > WARN_DAYS:
            old.append(url)
    if old:
        out.append(f"{len(old):,} listed local-government websites were last checked more than "
                   f"{WARN_DAYS} days ago; the weekly refresh runs 'localgov --check-sites "
                   f"--limit', oldest first - is it running?")
    # Gambling seen once in a page's text is withdrawn, and waits for a
    # person: a real page can say "slot" in a sentence the signatures read.
    for url in sorted(u for u, e in sites.items() if u in addresses and e.get("verdict") == GAMBLING
                      and not sticky(e) and not blocked(u)):
        out.append(f"{url}: gambling seen in one passage of its text ({sites[url].get('evidence', '')}); "
                   f"look, and record it in overrides.BLOCKED_LOCAL_HOSTS, or clear it in "
                   f"{CACHE_PATH}")
    hidden = sorted(u for u, e in sites.items() if u in addresses and e.get("verdict") == OK
                    and "hides gambling" in e.get("evidence", ""))
    for url in hidden:
        out.append(f"{url} hides gambling links in its page: a compromised site, still linked; "
                   f"look, and record it in overrides.BLOCKED_LOCAL_HOSTS if it should not be")
    return out
