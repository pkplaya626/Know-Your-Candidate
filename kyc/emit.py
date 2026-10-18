"""Write the generated data files out for the site to load."""

import datetime
import hashlib
import json
import os
import re

SITE_DIR = "candidate_profiles_site"
DATA_DIR = os.path.join(SITE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "profiles.js")
GEO_FILE = os.path.join(DATA_DIR, "geo.js")
ODDS_FILE = os.path.join(DATA_DIR, "odds.js")
# What the guide's maps say about each state (kyc/government_maps.py).
GOVERNMENT_FILE = os.path.join(DATA_DIR, "government.js")
# Each state's governor and which party holds each chamber (kyc/stategov.py).
STATEGOV_FILE = os.path.join(DATA_DIR, "stategov.js")
# One file per state: its legislative districts and who sits for them.
LEGISLATURE_DIR = os.path.join(DATA_DIR, "legislature")
# The federal executive and courts: one file for the hub, one per court.
FEDERAL_FILE = os.path.join(DATA_DIR, "federal.js")
JUDICIARY_DIR = os.path.join(DATA_DIR, "judiciary")
JUDGES_INDEX_FILE = os.path.join(JUDICIARY_DIR, "index.js")
# One file per state: its counties and every local government in each.
LOCAL_DIR = os.path.join(DATA_DIR, "local")
# Which federal district court, and division, covers each county
# (kyc/court_districts.py, 28 U.S.C. 81-131), for the county pages.
COURT_COUNTIES_FILE = os.path.join(DATA_DIR, "courtcounties.js")
# One file per state, each loaded only by that state's district page.
DISTRICTS_DIR = os.path.join(DATA_DIR, "districts")
# Each chamber's roll calls and how every member voted in them
# (kyc/rollcalls.py), loaded by the profile dialog the first time a member of
# that chamber is opened, so profiles.js does not carry them.
VOTES_DIR = os.path.join(DATA_DIR, "votes")
# The global each chamber's file assigns, and its path under data/.
VOTES_GLOBALS = {"house": "kycVotesHouse", "senate": "kycVotesSenate"}
VOTES_FILES = {chamber: f"votes/{chamber}.js" for chamber in VOTES_GLOBALS}

# The scripts each page must load, in the order it must load them. The build
# never rewrites a page; it only reports when one has drifted out of step with
# the data it depends on.
#
# Order is the substantive part. Every generated file assigns a global, and
# the page modules read those globals as they initialise, so a page that
# loads its own module before the data renders an empty site with no error.
PAGE_REQUIREMENTS = {
    "index.html": (
        "assets/kyc.js",
        "data/profiles.js",
        "data/odds.js",
        "assets/kyc-odds.js",
        "assets/kyc-cards.js",
        "assets/kyc-profile.js",
        "assets/kyc-senate.js",
        "assets/kyc-directory.js",
    ),
    "map.html": (
        "assets/kyc.js",
        "data/profiles.js",
        "data/geo.js",
        "data/odds.js",
        "data/stategov.js",
        "assets/kyc-odds.js",
        "assets/kyc-cards.js",
        "assets/kyc-profile.js",
        "assets/kyc-stategov.js",
        "assets/kyc-usmap.js",
        "assets/kyc-map.js",
    ),
}

# The generated state pages sit one directory down and load the same data.
STATE_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/profiles.js",
    "../data/odds.js",
    "../data/stategov.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-stategov.js",
    "../assets/kyc-state.js",
)

# A state's district page. It reads the profiles for every claim about a
# person and its own state's map file for the lines, so both load first.
# "{code}" is the page's own postal code, lower case.
DISTRICT_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/profiles.js",
    "../data/odds.js",
    "../data/districts/{code}.js",
    "../assets/kyc-odds.js",
    "../assets/kyc-cards.js",
    "../assets/kyc-profile.js",
    "../assets/kyc-districts.js",
)

# A state's legislature page: the districts and people, then the map, then
# the page module that reads both.
LEGISLATURE_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/legislature/{code}.js",
    "../assets/kyc-regionmap.js",
    "../assets/kyc-legislature.js",
)

# The federal government's hub: the offices and courts, every judge's name
# for its search, the shared official dialog, then the page module.
FEDERAL_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/federal.js",
    "../data/judiciary/index.js",
    "../data/geo.js",
    "../assets/kyc-official.js",
    "../assets/kyc-usmap.js",
    "../assets/kyc-federal.js",
)

# One federal court's page: the hub's data, that court's judges, the dialog,
# the page module. "{code}" is the court's id.
COURT_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/federal.js",
    "../data/judiciary/{code}.js",
    "../assets/kyc-official.js",
    "../assets/kyc-federal.js",
)

# A state's counties page: its counties and governments, the map, the page.
COUNTIES_PAGE_REQUIREMENTS = (
    "../assets/kyc.js",
    "../data/local/{code}.js",
    "../data/courtcounties.js",
    "../assets/kyc-regionmap.js",
    "../assets/kyc-local.js",
)

PAGES = tuple(PAGE_REQUIREMENTS)
STATES_DIR = os.path.join(SITE_DIR, "states")
DISTRICT_PAGES_DIR = os.path.join(SITE_DIR, "districts")
LEGISLATURE_PAGES_DIR = os.path.join(SITE_DIR, "legislature")
COUNTIES_PAGES_DIR = os.path.join(SITE_DIR, "counties")
FEDERAL_PAGES_DIR = os.path.join(SITE_DIR, "federal")
COURT_PAGES_DIR = os.path.join(SITE_DIR, "courts")
# Know Your Government, the guide: generated pages, one folder down. What
# each loads depends on the page (kyc.government.scripts).
GOVERNMENT_DIR = os.path.join(SITE_DIR, "government")
# The site's frame, at its root: about.html, the page GitHub Pages serves for
# any missing address (its URLs are from the root, as it is served at any
# depth), and the manifest a phone reads to add the site to its home screen.
ABOUT_FILE = os.path.join(SITE_DIR, "about.html")
NOT_FOUND_FILE = os.path.join(SITE_DIR, "404.html")
MANIFEST_FILE = os.path.join(SITE_DIR, "site.webmanifest")
# The first district page lived here for a day; the address still answers.
REDIRECTS = {os.path.join(SITE_DIR, "redistricting", "ca.html"): "../districts/ca.html"}
SITEMAP_FILE = os.path.join(SITE_DIR, "sitemap.xml")

_BANNER = """\
// Generated by build_profile_site.py - do not edit by hand.
// Source: {source}
// Built: {built}
"""


def _atomic_write(path, text):
    """Write *text* to *path* via a temp file so a crash cannot truncate it."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, path)
    return len(text.encode("utf-8"))


def build_timestamp():
    """Build time, honouring ``SOURCE_DATE_EPOCH``.

    A fixed epoch makes the output byte-for-byte reproducible, which is what
    lets CI assert that a rebuild changes nothing.
    """
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    now = (
        datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
        if epoch and epoch.isdigit()
        else datetime.datetime.now(datetime.timezone.utc)
    )
    return now.isoformat(timespec="seconds")


def _json(value):
    """Compact JSON that is safe to embed in a ``<script>`` element.

    A profile field containing ``</script>`` would otherwise close the tag
    early and break the page; ``<!--`` can start an HTML comment inside a
    classic script and swallow the rest of the file.
    """
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/").replace("<!--", "<\\!--")


def data_signature(profiles, races=None, summary=None):
    """A content hash of everything the build derives from the sources.

    Deliberately excludes the build timestamp. "Is the committed data still in
    sync with the CSVs?" and "when was this built?" are different questions,
    and answering the first by diffing whole files forced the second to be a
    lie: CI rebuilt with a fixed SOURCE_DATE_EPOCH, so keeping `git diff`
    quiet would have meant committing a 2001 timestamp and showing it to
    readers in the page footer as the freshness stamp.
    """
    # sort_keys, unlike the emitted file. json.dumps preserves insertion
    # order, so two builds that attach the same enrichments in a different
    # sequence produced different signatures for identical data - which is
    # exactly what happened when `verify` applied the disclosure cache after
    # portraits and `build` applied it before. A signature has to describe
    # content, not the order the dict happened to be filled in.
    payload = json.dumps(
        [profiles, races or [], summary or {}],
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SIGNATURE_RE = re.compile(r'"signature":"([0-9a-f]{64})"')


def read_signature(root=".", path=None):
    """The signature recorded in a generated file, or ``None``."""
    target = path or os.path.join(root, DATA_FILE)
    if not os.path.exists(target):
        return None
    with open(target, "r", encoding="utf-8") as handle:
        # The signature lives in the metadata line at the end of the file;
        # reading the whole 1 MB payload to find it would be wasteful.
        for line in handle:
            match = _SIGNATURE_RE.search(line)
            if match:
                return match.group(1)
    return None


def write_profiles(profiles, stats, root=".", races=None, summary=None):
    """Emit ``candidate_profiles_site/data/profiles.js``.

    A plain script assignment rather than JSON + ``fetch`` so the pages keep
    working when opened straight off disk - ``file://`` requests are blocked
    by CORS, but ``<script src>`` is not.
    """
    path = os.path.join(root, DATA_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    built = build_timestamp()
    meta = {"built": built, "counts": stats,
            "signature": data_signature(profiles, races, summary)}
    if summary:
        meta.update(summary)

    text = (
        _BANNER.format(source="the roster CSVs at the repository root", built=built)
        + f"// Profiles: {len(profiles)}\n"
        + f"window.legislatorsData = {_json(profiles)};\n"
        + f"window.kycRaces = {_json(races or [])};\n"
        + f"window.kycBuildMeta = {_json(meta)};\n"
    )
    return path, _atomic_write(path, text)


def state_codes(profiles):
    """Every state or territory a sitting member represents."""
    from .record import seated

    return sorted({p["state"] for p in profiles
                   if seated(p) and p.get("state") not in (None, "", "N/A")})


def render_state_pages(profiles, root=".", summary=None, stamp_from=None):
    """``{relative path: html}`` for every generated page: one per state, the
    index of states, one district map per state, the old address of the
    first one, the directories of legislatures and counties, and the guide,
    Know Your Government."""
    from . import districts, government, pages

    host = canonical_host(root)
    # When each source was read, for the footers that name it (rule 19:
    # a page says when it looked, never only that it did).
    dates = pages.data_dates(root)
    codes = state_codes(profiles)
    out = {os.path.join(STATES_DIR, "index.html"): pages.render_states_index(host)}
    for code in state_codes(profiles):
        out[os.path.join(SITE_DIR, *pages.page_path(code).split("/"))] = (
            pages.render_state(code, host, summary))
    for code in districts.all_codes():
        out[os.path.join(SITE_DIR, *districts.page_path(code).split("/"))] = (
            pages.render_district_page(code, host, summary))
    out[os.path.join(DISTRICT_PAGES_DIR, "index.html")] = pages.render_districts_index(
        host, summary, codes)
    for path, target in REDIRECTS.items():
        out[path] = pages.render_redirect(target, host)
    # The site's frame: who runs it and where its data comes from, the page
    # GitHub Pages serves for any missing address, and the home-screen
    # manifest.
    out[ABOUT_FILE] = pages.render_about(host, dates, codes)
    out[NOT_FOUND_FILE] = pages.render_404(host, codes)
    out[MANIFEST_FILE] = pages.webmanifest()
    for relative, text in government.render_all(host, state_codes(profiles)).items():
        out[os.path.join(SITE_DIR, *relative.split("/"))] = text
    from . import census
    from .government_maps import STATES
    out[os.path.join(LEGISLATURE_PAGES_DIR, "index.html")] = pages.render_legislatures_index(
        host, dates)
    out[os.path.join(COUNTIES_PAGES_DIR, "index.html")] = pages.render_counties_index(
        host, census.load_cache(root), dates)
    for code in STATES:
        out[os.path.join(LEGISLATURE_PAGES_DIR, f"{code.lower()}.html")] = (
            pages.render_legislature_page(code, host, summary, dates))
        out[os.path.join(COUNTIES_PAGES_DIR, f"{code.lower()}.html")] = (
            pages.render_counties_page(code, host, pages.listing_date(code, root)))
    from . import federal_build, federal_courts
    # The names, written into the federal pages too (FEDERAL-12): from the
    # same payload as data/federal.js, so verify sees a page that disagrees.
    try:
        fed, fed_courts, _search, _problems = federal_build.build(root)
    except federal_build.FederalBuildError:
        fed, fed_courts = None, {}
    out[os.path.join(FEDERAL_PAGES_DIR, "index.html")] = pages.render_federal_page(
        host, codes, dates, fed)
    out[os.path.join(COURT_PAGES_DIR, "index.html")] = pages.render_courts_index(
        host, codes, dates)
    for cid in federal_courts.COURTS:
        out[os.path.join(COURT_PAGES_DIR, f"{cid}.html")] = pages.render_court_page(
            cid, host, codes, dates, fed, fed_courts.get(cid))
    # Each page's own code and data, at the versions it was built with
    # (kyc/assets.py), read from *stamp_from* - the root, unless a test
    # renders into a folder without them and says where they are.
    from . import assets
    return {path: assets.stamp(text, stamp_from or root) for path, text in out.items()}


def write_state_pages(profiles, root=".", summary=None, stamp_from=None):
    """Write one page per state plus the directory. Returns the paths."""
    written = []
    for relative, text in render_state_pages(profiles, root, summary, stamp_from).items():
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _atomic_write(path, text)
        written.append(path)
    return written


def check_state_pages(profiles, root=".", summary=None, stamp_from=None):
    """State pages that differ from what the build would write now.

    They are generated, so ``verify`` regenerates them in memory and compares:
    a template edit that was never followed by a build is otherwise invisible.
    """
    stale = []
    for relative, text in render_state_pages(profiles, root, summary, stamp_from).items():
        path = os.path.join(root, relative)
        if not os.path.exists(path):
            stale.append((relative, "missing"))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() != text:
                stale.append((relative, "stale"))
    return stale


def write_sitemap(profiles, root="."):
    """Write ``sitemap.xml`` listing the pages and every state. Returns the
    path, or ``None`` when no custom domain is configured."""
    from . import districts, government, pages

    host = canonical_host(root)
    if not host:
        return None
    path = os.path.join(root, SITEMAP_FILE)
    from .government_maps import STATES
    from .federal_courts import COURTS
    _atomic_write(path, pages.sitemap(host, state_codes(profiles),
                                      district_maps=districts.all_codes(),
                                      guide=government.slugs(),
                                      legislatures=STATES, courts=tuple(COURTS)))
    return path


def write_geo(geo, root="."):
    """Emit ``candidate_profiles_site/data/geo.js``.

    Pre-rendered SVG path data for the map, so the page needs no mapping
    library at runtime. Same ``<script src>`` reasoning as the profiles file.
    """
    path = os.path.join(root, GEO_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    text = (
        _BANNER.format(source="us_atlas_states_topo.json", built=build_timestamp())
        + f"// States: {len(geo.get('states', {}))}\n"
        + f"window.kycGeo = {_json(geo)};\n"
        + 'window.kycGeoMeta = {"signature":"' + geo_signature(geo) + '"};\n'
    )
    return path, _atomic_write(path, text)


def geo_signature(geo):
    """Content hash of the map geometry, excluding the build timestamp."""
    return hashlib.sha256(_json(geo).encode("utf-8")).hexdigest()


def district_file(code, root="."):
    """``candidate_profiles_site/data/districts/tx.js``."""
    return os.path.join(root, DISTRICTS_DIR, f"{code.lower()}.js")


def write_districts(maps, root="."):
    """Emit one ``data/districts/<st>.js`` per state. Returns ``[(path, size)]``.

    Each state's districts, projected at build time like the national map,
    in a file of its own so a page loads one state's lines, not 56. A pure
    function of the vendored boundaries and places: nothing about a person
    is in it, so a roster refresh never changes it.
    """
    from . import districts

    os.makedirs(os.path.join(root, DISTRICTS_DIR), exist_ok=True)
    written = []
    for code, payload in sorted(maps.items()):
        path = district_file(code, root)
        source = f"{districts.MAPS_DIR}/{code.lower()}.json, {districts.PLACES_FILE}"
        text = (
            _BANNER.format(source=source.replace(os.sep, "/"), built=build_timestamp())
            + f"window.kycDistricts = {_json({code: payload})};\n"
            + 'window.kycDistrictsMeta = {"signature":"' + districts_signature(payload)
            + '"};\n'
        )
        written.append((path, _atomic_write(path, text)))
    return written


def districts_signature(payload):
    """Content hash of one state's maps, excluding the build timestamp."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def check_districts(maps, root="."):
    """``[(path, problem)]`` for state map files missing or out of date."""
    problems = []
    for code, payload in sorted(maps.items()):
        path = district_file(code, root)
        committed = read_signature(path=path)
        if committed is None:
            problems.append((path, "missing or carries no signature"))
        elif committed != districts_signature(payload):
            problems.append((path, "stale"))
    return problems


def write_odds(payload, root="."):
    """Emit ``candidate_profiles_site/data/odds.js``.

    Market prices and polling averages, keyed by race id, in a file of their
    own: the twelve-hourly odds refresh writes this and odds.json and nothing
    else, so it never collides with the weekly roster refresh's profiles.js.
    """
    path = os.path.join(root, ODDS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = (
        _BANNER.format(source="candidate_profiles_site/data/odds.json (Kalshi, Polymarket, "
                              "Wikipedia)", built=build_timestamp())
        + f"// Races: {len(payload.get('races', {}))}\n"
        + f"window.kycOdds = {_json(payload)};\n"
        + 'window.kycOddsMeta = {"signature":"' + odds_signature(payload) + '"};\n'
    )
    return path, _atomic_write(path, text)


def odds_signature(payload):
    """Content hash of the odds payload, excluding the build timestamp."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def write_government(payload, root="."):
    """Emit ``candidate_profiles_site/data/government.js``: the guide's maps.

    A pure function of ``kyc/government_maps.py`` and the atlas - nothing
    about a person is in it - so a roster refresh never changes it, and the
    build rewrites it only when its signature changes.
    """
    path = os.path.join(root, GOVERNMENT_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = (
        _BANNER.format(source="kyc/government_maps.py", built=build_timestamp())
        + f"window.kycGovernment = {_json(payload)};\n"
        + 'window.kycGovernmentMeta = {"signature":"' + government_signature(payload) + '"};\n'
    )
    return path, _atomic_write(path, text)


def write_stategov(payload, root="."):
    """Emit ``candidate_profiles_site/data/stategov.js``: each state's
    governor and the parties in its legislature, rewritten only when its
    signature changes."""
    path = os.path.join(root, STATEGOV_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = (
        _BANNER.format(source="kyc/stategov.py", built=build_timestamp())
        + f"window.kycStateGov = {_json(payload)};\n"
        + 'window.kycStateGovMeta = {"signature":"' + stategov_signature(payload) + '"};\n'
    )
    return path, _atomic_write(path, text)


def stategov_signature(payload):
    """Content hash of the state government data, excluding the build time."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def federal_signature(payload):
    """Content hash of a federal data file's payload, excluding the build time."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def write_federal(payload, per_court, search, root="."):
    """Emit ``data/federal.js``, ``data/judiciary/<court>.js`` and
    ``data/judiciary/index.js``, each only when its signature changed.
    Returns ``[(path, size)]`` for the files written."""
    os.makedirs(os.path.join(root, JUDICIARY_DIR), exist_ok=True)
    source = ("data/federal_executive.json, data/judiciary.json, data/judicial_vacancies.json, "
              "data/judge_links.json, data/court_districts.json, data/political_history.json, "
              "data/oge_disclosures.json (kyc/federal_build.py)")
    files = [(os.path.join(root, FEDERAL_FILE), "kycFederal", payload)]
    files += [(os.path.join(root, JUDICIARY_DIR, f"{cid}.js"), None, court)
              for cid, court in sorted(per_court.items())]
    files.append((os.path.join(root, JUDGES_INDEX_FILE), "kycJudgesIndex", search))
    written = []
    for path, name, data in files:
        signature = federal_signature(data)
        if read_signature(path=path) == signature:
            continue
        if name is None:
            # A court file adds itself to the courts the page has loaded.
            body = ("window.kycCourt = window.kycCourt || {};\n"
                    f"window.kycCourt[{_json(data['id'])}] = {_json(data)};\n"
                    'window.kycCourtMeta = {"signature":"' + signature + '"};\n')
        else:
            body = (f"window.{name} = {_json(data)};\n"
                    f'window.{name}Meta = {{"signature":"{signature}"}};\n')
        text = _BANNER.format(source=source, built=build_timestamp()) + body
        written.append((path, _atomic_write(path, text)))
    return written


def votes_file(chamber, root="."):
    return os.path.join(root, DATA_DIR, *VOTES_FILES[chamber].split("/"))


def write_votes(payloads, root="."):
    """Emit ``data/votes/<chamber>.js`` for each chamber, each only when its
    signature changed. Returns ``[(path, size)]`` for the files written."""
    written = []
    for chamber, name in sorted(VOTES_GLOBALS.items()):
        data = payloads[chamber]
        path = votes_file(chamber, root)
        signature = federal_signature(data)
        if read_signature(path=path) == signature:
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = (_BANNER.format(source="data/roll_calls.json (kyc/rollcalls.py)",
                               built=build_timestamp())
                + f"window.{name} = {_json(data)};\n"
                + f'window.{name}Meta = {{"signature":"{signature}"}};\n')
        written.append((path, _atomic_write(path, text)))
    return written


def check_votes(payloads, root="."):
    """Vote files that are missing or carry another signature."""
    stale = []
    for chamber in sorted(VOTES_GLOBALS):
        path = votes_file(chamber, root)
        committed = read_signature(path=path)
        if committed is None:
            stale.append((path, "missing"))
        elif committed != federal_signature(payloads[chamber]):
            stale.append((path, "stale"))
    return stale


def check_federal(payload, per_court, search, root="."):
    """Federal data files that are missing or carry another signature."""
    stale = []
    files = [(os.path.join(root, FEDERAL_FILE), payload)]
    files += [(os.path.join(root, JUDICIARY_DIR, f"{cid}.js"), court)
              for cid, court in sorted(per_court.items())]
    files.append((os.path.join(root, JUDGES_INDEX_FILE), search))
    for path, data in files:
        committed = read_signature(path=path)
        if committed is None:
            stale.append((path, "missing"))
        elif committed != federal_signature(data):
            stale.append((path, "stale"))
    return stale


def legislature_file(code, root="."):
    """``candidate_profiles_site/data/legislature/tx.js``."""
    return os.path.join(root, LEGISLATURE_DIR, f"{code.lower()}.js")


def legislature_signature(payload):
    """Content hash of one state's legislature data, excluding the build time."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def write_legislature(maps, root="."):
    """Emit one ``data/legislature/<st>.js`` per state whose content changed.
    Returns ``[(path, size)]`` for the files written."""
    os.makedirs(os.path.join(root, LEGISLATURE_DIR), exist_ok=True)
    written = []
    for code, payload in sorted(maps.items()):
        path = legislature_file(code, root)
        signature = legislature_signature(payload)
        if read_signature(path=path) == signature:
            continue
        text = (
            _BANNER.format(source=f"legislative_maps/{code.lower()}.json, "
                                  "data/state_legislators.json (Open States)",
                           built=build_timestamp())
            + f"window.kycLegislature = {_json({code: payload})};\n"
            + 'window.kycLegislatureMeta = {"signature":"' + signature + '"};\n'
        )
        written.append((path, _atomic_write(path, text)))
    return written


def write_court_counties(payload, root="."):
    """Emit ``data/courtcounties.js``: each county's federal district court
    and division, rewritten only when its signature changes."""
    path = os.path.join(root, COURT_COUNTIES_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = (
        _BANNER.format(source="data/court_districts.json, 28 U.S.C. 81-131 "
                              "(kyc/court_districts.py)", built=build_timestamp())
        + f"window.kycCourtCounties = {_json(payload)};\n"
        + 'window.kycCourtCountiesMeta = {"signature":"' + federal_signature(payload) + '"};\n'
    )
    return path, _atomic_write(path, text)


def local_file(code, root="."):
    """``candidate_profiles_site/data/local/tx.js``."""
    return os.path.join(root, LOCAL_DIR, f"{code.lower()}.js")


def write_local(maps, root="."):
    """Emit one ``data/local/<st>.js`` per state whose content changed."""
    os.makedirs(os.path.join(root, LOCAL_DIR), exist_ok=True)
    written = []
    for code, payload in sorted(maps.items()):
        path = local_file(code, root)
        signature = legislature_signature(payload)
        if read_signature(path=path) == signature:
            continue
        text = (
            _BANNER.format(source=f"legislative_maps/{code.lower()}.json (counties), "
                                  f"local_maps/{code.lower()}.json (places), "
                                  f"local_governments/{code.lower()}.json (Census listing)",
                           built=build_timestamp())
            + f"window.kycLocal = {_json({code: payload})};\n"
            + 'window.kycLocalMeta = {"signature":"' + signature + '"};\n'
        )
        written.append((path, _atomic_write(path, text)))
    return written


def check_local(maps, root="."):
    problems = []
    for code, payload in sorted(maps.items()):
        path = local_file(code, root)
        committed = read_signature(path=path)
        if committed is None:
            problems.append((path, "missing or carries no signature"))
        elif committed != legislature_signature(payload):
            problems.append((path, "stale"))
    return problems


def check_legislature(maps, root="."):
    """``[(path, problem)]`` for legislature files missing or out of date."""
    problems = []
    for code, payload in sorted(maps.items()):
        path = legislature_file(code, root)
        committed = read_signature(path=path)
        if committed is None:
            problems.append((path, "missing or carries no signature"))
        elif committed != legislature_signature(payload):
            problems.append((path, "stale"))
    return problems


def government_signature(payload):
    """Content hash of the guide's map data, excluding the build timestamp."""
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def inline_script_problems(html):
    """What is wrong with *html*'s inline ``<script>`` blocks: a page runs
    no inline code (CLAUDE.md), and the one inline block allowed is
    structured data, ``type="application/ld+json"``, which must parse as
    JSON. An inline block with any other type, or none, is code."""
    import json

    problems = []
    for attrs, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
        if re.search(r"\bsrc=", attrs):
            continue
        kind = re.search(r'\btype="([^"]*)"', attrs)
        if not kind or kind.group(1).strip().lower() != "application/ld+json":
            problems.append("an inline <script> that is not application/ld+json")
            continue
        try:
            json.loads(body)
        except ValueError:
            problems.append("an application/ld+json block that is not JSON")
    return problems


def script_sources(html):
    """Every ``<script src="...">`` in *html*, in document order, without the
    version stamp a local asset's URL carries (kyc/assets.py). Not those
    named inert in a ``<template>``, which the page never runs as it loads
    (:func:`on_demand_sources`)."""
    html = re.sub(r"<template\b.*?</template>", "", html, flags=re.S)
    return [src.split("?v=")[0] for src in re.findall(r'<script[^>]*\bsrc="([^"]+)"', html)]


def on_demand_sources(html):
    """The data files *html* names in its ``<template id="onDemandData">``,
    loaded only when wanted (``KYC.loadData``), without their stamps."""
    block = re.search(r'<template id="onDemandData">(.*?)</template>', html, re.S)
    return script_sources(block.group(1)) if block else []


# ------------------------------------------------------------------ hostname

CNAME_FILE = os.path.join(SITE_DIR, "CNAME")

# Files that name the public hostname, and how to find it in each. GitHub
# Pages takes it from CNAME; everything else has to agree with that file or
# the site tells search engines and social networks it lives somewhere it
# does not. Six copies of a hostname across five files is precisely the kind
# of thing that drifts silently after a rename.
#
# A page's every own address is matched, not only its canonical link: the
# home page's structured data names the site and its search, and the share
# card's source prints the host into the image (regenerate the PNG after a
# rename). Outbound links to other sites are not the site's own and are not
# matched: only canonical, og: and the JSON-LD's url fields.
_OWN_URL = (r'(?:rel="canonical" href="|property="og:(?:url|image)" content="|'
            r'"(?:url|urlTemplate|item)":")https://([^/"]+)')
_HOST_REFERENCES = {
    os.path.join(SITE_DIR, "index.html"): _OWN_URL,
    os.path.join(SITE_DIR, "map.html"): _OWN_URL,
    os.path.join(SITE_DIR, "robots.txt"): r"Sitemap:\s*https://([^/\s]+)",
    os.path.join(SITE_DIR, "sitemap.xml"): r"<loc>https://([^/<]+)",
    os.path.join("tools", "social-card.html"): r'<div class="host">([^<]+)</div>',
}


def canonical_host(root="."):
    """The hostname GitHub Pages will serve from, or ``None``."""
    path = os.path.join(root, CNAME_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip() or None


def check_hostname(root="."):
    """Report files whose hostname disagrees with CNAME.

    Returns a list of ``(file, ok, note)``.
    """
    expected = canonical_host(root)
    if expected is None:
        return [(CNAME_FILE, True, "no custom domain configured")]

    results = [(CNAME_FILE, True, expected)]
    for relative, pattern in _HOST_REFERENCES.items():
        path = os.path.join(root, relative)
        if not os.path.exists(path):
            results.append((relative, False, "missing"))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            found = set(re.findall(pattern, handle.read()))
        if not found:
            results.append((relative, False, f"names no host; expected {expected}"))
        elif found != {expected}:
            results.append(
                (relative, False, f"names {', '.join(sorted(found))}; CNAME says {expected}")
            )
        else:
            results.append((relative, True, "ok"))
    return results


def check_pages(root="."):
    """Report which pages are wired up to the scripts they need.

    Returns a list of ``(page, ok, note)``.
    """
    results = []
    checks = dict(PAGE_REQUIREMENTS)
    for folder, required in ((STATES_DIR, STATE_PAGE_REQUIREMENTS),
                             (DISTRICT_PAGES_DIR, DISTRICT_PAGE_REQUIREMENTS),
                             (LEGISLATURE_PAGES_DIR, LEGISLATURE_PAGE_REQUIREMENTS),
                             (COUNTIES_PAGES_DIR, COUNTIES_PAGE_REQUIREMENTS),
                             (COURT_PAGES_DIR, COURT_PAGE_REQUIREMENTS)):
        directory = os.path.join(root, folder)
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                # A folder's directory page is checked on its own, below.
                if name.endswith(".html") and not (name == "index.html" and folder != STATES_DIR):
                    code = name[:-len(".html")]
                    checks[f"{os.path.basename(folder)}/{name}"] = tuple(
                        src.replace("{code}", code) for src in required)

    checks["federal/index.html"] = FEDERAL_PAGE_REQUIREMENTS
    # The directories and the frame load nothing but the shared module.
    checks["districts/index.html"] = ("../assets/kyc.js",)
    checks["courts/index.html"] = ("../assets/kyc.js",)
    checks["about.html"] = ("assets/kyc.js",)
    checks["404.html"] = ("/assets/kyc.js",)
    checks["legislature/index.html"] = ("../assets/kyc.js", "../data/stategov.js",
                                        "../assets/kyc-stategov.js")
    checks["counties/index.html"] = ("../assets/kyc.js",)

    from . import government
    for slug in government.slugs():
        checks[government.page_path(slug)] = ("../assets/kyc.js",) + tuple(
            government.scripts(slug))

    for page, required in checks.items():
        path = os.path.join(root, SITE_DIR, page)
        if not os.path.exists(path):
            results.append((page, False, "missing"))
            continue
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        loaded = script_sources(text)

        problems = inline_script_problems(text)
        # The profile dialog loads a member's votes on demand, from the files
        # the page names in its inert template (KYC.loadData): a page that
        # opens profiles and names none would say the votes failed to load.
        dialog = [src for src in loaded if src.endswith("assets/kyc-profile.js")]
        if dialog:
            prefix = dialog[0][:-len("assets/kyc-profile.js")]
            lazy = on_demand_sources(text)
            absent = [prefix + "data/" + VOTES_FILES[c] for c in sorted(VOTES_FILES)
                      if prefix + "data/" + VOTES_FILES[c] not in lazy]
            if absent:
                problems.append("opens profiles but its onDemandData template does not name "
                                + ", ".join(absent))
            for src in lazy:
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path),
                                                                    *src.split("/")))):
                    problems.append(f"{src} is named on demand but does not exist")
        missing = [src for src in required if src not in loaded]
        if missing:
            problems.append("does not load " + ", ".join(missing))

        present = [src for src in required if src in loaded]
        order = [loaded.index(src) for src in present]
        if order != sorted(order):
            problems.append(
                "scripts load out of order; expected " + " -> ".join(required)
            )

        page_dir = os.path.dirname(path)
        for src in required:
            # A URL from the root ("/assets/kyc.js", the 404 page's) is the
            # site directory's, wherever the page is served.
            base = os.path.join(root, SITE_DIR) if src.startswith("/") else page_dir
            if src in loaded and not os.path.exists(
                os.path.normpath(os.path.join(base, *src.lstrip("/").split("/")))
            ):
                problems.append(f"{src} is referenced but does not exist")

        results.append((page, not problems, "; ".join(problems) if problems else "ok"))
    results += check_nav(root)
    return results


# The hand-maintained pages and the navigation entry each is.
NAV_PAGES = {"index.html": "candidates", "map.html": "races"}


def check_nav(root="."):
    """``[(page, ok, note)]``: whether index.html and map.html carry the
    navigation the generated pages render (pages.nav_groups). They are
    edited by hand, and a sidebar that disagrees with the rest of the site
    looks entirely normal on the page it is on."""
    from . import pages

    out = []
    for page, current in NAV_PAGES.items():
        path = os.path.join(root, SITE_DIR, page)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        want = pages.nav_html("", current)
        start = text.find('        <nav class="sidebar-section site-nav"')
        found = text[start:text.find("</nav>", start) + len("</nav>")] if start >= 0 else ""
        out.append((f"{page} (navigation)", found == want,
                    "ok" if found == want else
                    "its navigation is not pages.nav_html(\"\", %r): copy it from there" % current))
        # The frame every generated page has: the footer's last line (About,
        # Report a problem) and the sidebar's freshness line. The home page
        # also carries the site's structured data, with its search.
        frame = [("footer", pages.footer_meta("", pages.BUILD_STAMP)),
                 ("sidebar's freshness line", pages.built_line("", "stamp"))]
        host = canonical_host(root)
        if page == "index.html" and host:
            frame.append(("structured data", pages.website_jsonld(host).strip()))
        for what, line in frame:
            out.append((f"{page} ({what})", line in text, "ok" if line in text else
                        f"it does not carry the {what} kyc/pages.py writes: copy it from there"))
    return out
