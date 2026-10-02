"""Hand-curated corrections layered on top of the CSV rosters.

Everything here is an editorial judgement rather than pipeline logic, so it
lives apart from the loaders. Keep entries sourced and minimal - the CSVs are
the source of truth wherever they are correct.
"""

from urllib.parse import urlsplit

# Photo overrides for people the automated Bioguide/Wikipedia chain misses or
# resolves to the wrong image.
#
# Keyed on (name, state) and applied ONLY to candidate rows. A bare-name key
# is unsafe: Rep. Mike Rogers (AL-3) and 2026 Senate candidate Mike Rogers (MI)
# are different people, and a name-keyed override put the Michigan candidate's
# portrait on the Alabama congressman's profile.
CANDIDATE_PHOTOS = {
    ("James Talarico", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/James_Talarico.jpg/800px-James_Talarico.jpg",
    ("Ken Paxton", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ken_Paxton_official_photo_%28cropped%29.jpg/800px-Ken_Paxton_official_photo_%28cropped%29.jpg",
    ("Mike Rogers", "MI"): "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Mike_Rogers_official_portrait.jpg/800px-Mike_Rogers_official_portrait.jpg",
    ("Abdul El-Sayed", "MI"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Abdul_El-Sayed_by_Gage_Skidmore.jpg/800px-Abdul_El-Sayed_by_Gage_Skidmore.jpg",
    ("Roy Cooper", "NC"): "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Roy_Cooper_official_photo.jpg/800px-Roy_Cooper_official_photo.jpg",
    ("Dan Osborn", "NE"): "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Dan_Osborn_for_Senate_%28cropped%29.jpg/800px-Dan_Osborn_for_Senate_%28cropped%29.jpg",
    ("Michael Whatley", "NC"): "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Michael_Whatley_in_2024.jpg/800px-Michael_Whatley_in_2024.jpg",
    ("Charles Booker", "KY"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Charles_Booker.jpg/800px-Charles_Booker.jpg",
    ("Andy Barr", "KY"): "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Andy_Barr_official_photo.jpg/800px-Andy_Barr_official_photo.jpg",
    ("Juliana Stratton", "IL"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Juliana_Stratton.jpg/800px-Juliana_Stratton.jpg",
    ("Ashley Hinson", "IA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Ashley_Hinson_Official_Portrait.jpg/800px-Ashley_Hinson_Official_Portrait.jpg",
    ("Mike Collins", "GA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Mike_Collins_118th_Congress.jpg/800px-Mike_Collins_118th_Congress.jpg",
    ("Julia Letlow", "LA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Julia_Letlow_official_portrait.jpg/800px-Julia_Letlow_official_portrait.jpg",
    ("Sherrod Brown", "OH"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Sherrod_Brown_official_photo_2019.jpg/800px-Sherrod_Brown_official_photo_2019.jpg",
    ("Andy Beshear", "KY"): "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Andy_Beshear_official_portrait.jpg/800px-Andy_Beshear_official_portrait.jpg",
    ("Barry Moore", "AL"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Barry_Moore_117th_U.S_Congress.jpg/800px-Barry_Moore_117th_U.S_Congress.jpg",
    ("Kevin Hern", "OK"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Kevin_Hern_118th_Congress.jpg/800px-Kevin_Hern_118th_Congress.jpg",
    ("Alex Vindman", "FL"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Alexander_Vindman_official_portrait.jpg/800px-Alexander_Vindman_official_portrait.jpg",
    ("Brian Kemp", "GA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Brian_Kemp_official_portrait%2C_2023.jpg/800px-Brian_Kemp_official_portrait%2C_2023.jpg",
    ("Chris Sununu", "NH"): "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Chris_Sununu_official_portrait_%28cropped%29.jpg/800px-Chris_Sununu_official_portrait_%28cropped%29.jpg",
    ("Colin Allred", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Colin_Allred_official_photo.jpg/800px-Colin_Allred_official_photo.jpg",
    ("Brad Lander", "NY"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Brad_Lander_by_Gage_Skidmore.jpg/800px-Brad_Lander_by_Gage_Skidmore.jpg",
    ("Steve Toth", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Steve_Toth_Texas_House.jpg/800px-Steve_Toth_Texas_House.jpg",
    ("Troy Jackson", "ME"): "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Troy_Jackson_2019.jpg/800px-Troy_Jackson_2019.jpg",
    ("Josh Turek", "IA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Josh_Turek.jpg/800px-Josh_Turek.jpg",
    ("Mark Baisley", "CO"): "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Mark_Baisley_2023.jpg/800px-Mark_Baisley_2023.jpg",
    ("Marquita Bradshaw", "TN"): "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Marquita_Bradshaw.jpg/800px-Marquita_Bradshaw.jpg",
    ("Annie Andrews", "SC"): "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Annie_Andrews_portrait.jpg/800px-Annie_Andrews_portrait.jpg",
}

# Members present in the roster CSVs who no longer hold the seat. Matched on
# exact name against the member rosters only.
EXCLUDED_MEMBERS = frozenset({"Marco Rubio", "J.D. Vance", "Markwayne Mullin"})

# Seat-status notes that the roster "Status" column does not carry.
# Matched as a case-insensitive substring of the member's name.
STATUS_OVERRIDES = {
    "Ashley Moody": "2026 special election for final two years of Marco Rubio's term",
    "Joni Ernst": "Incumbent not running for re-election in 2026.",
    "Gary Peters": "Incumbent not running for re-election in 2026.",
    "Tina Smith": "Incumbent not running for re-election in 2026.",
    "Steve Daines": "Incumbent not running for re-election in 2026.",
    "Thom Tillis": "Incumbent not running for re-election in 2026.",
    "Jeanne Shaheen": "Incumbent not running for re-election in 2026.",
    "Jon Husted": "2026 special election for final two years of JD Vance's term",
    "John Cornyn": "Incumbent defeated in primary for 2026 election.",
    "Tommy Tuberville": "Retiring to run for governor",
    # The rosters use his legal name; he is usually reported as "Dick Durbin".
    "Richard Durbin": "Incumbent not running for re-election in 2026.",
    "Mitch McConnell": "Incumbent not running for re-election in 2026.",
    "Bill Cassidy": "Incumbent defeated in primary for 2026 election.",
    "Alan Armstrong": "Ineligible to run for a full term this year.",
    "Cynthia Lummis": "Incumbent not running for re-election in 2026.",
}

# Seat-status notes keyed on bioguide id, the only safe key for a person
# (rules 3 and 17). STATUS_OVERRIDES above matches a name substring; put new
# entries here instead. Each value is (status line, source). A member who is
# leaving the seat needs a NOT_SEEKING_MARKERS phrase in the status line.
MEMBER_STATUS_BY_ID = {
    # The DC article is titled "... election in the District of Columbia",
    # which results.page_titles never asks for, so no outcome was ever read.
    "N000147": ("Not running for re-election in 2026 (announced January 2026).",
                "https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_"
                "election_in_the_District_of_Columbia"),
    # Same title problem: "... election in the United States Virgin Islands".
    "P000610": ("Retiring to run for governor of the U.S. Virgin Islands.",
                "https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_"
                "elections#Non-voting_delegates"),
    # Withdrew 2026-07-21, before Wikipedia's LA-6 box existed to say so.
    "F000110": ("Not running for re-election in 2026; running for the Louisiana State Senate.",
                "https://www.thegreenpapers.com/G26/LA"),
}

# Campaign websites that must never be linked, keyed on the host the FEC
# committee registered (lower case; a key without "www." also covers the
# "www." form). The FEC keeps whatever site a committee once filed, and a
# lapsed campaign domain gets bought: on 2026-10-01 seven served gambling pages
# under a candidate's name. Each value is (kind, date checked, what was seen).
# "hijacked" entries must never come back. "dead" entries - the host does not
# exist in DNS, or the hosting platform says the site is gone - may be removed
# once the committee files a working address; validate reports any entry that
# no longer matches a cached site.
BLOCKED_CAMPAIGN_HOSTS = {
    "maxinewatersforcongress.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "tedlieu.com": ("hijacked", "2026-10-01", "serves a gambling page"),
    "electjimbaird.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "troycarter4congress.com": ("hijacked", "2026-10-01", "serves an online-casino page"),
    "suozziforcongress2024.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "votemikefrance.com": ("hijacked", "2026-10-01", "serves a gambling page under his name"),
    "lukebronin.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "benniegthompson.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.plaskettforcongress.org": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.steilforwisconsin.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "cleofields.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.shreveforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "davetaylorforcongrss.com": ("dead", "2026-10-01", "NXDOMAIN; the filing misspells it"),
    "capitolforsenate.com": ("dead", "2026-10-01", "NXDOMAIN; the filing misspells it"),
    "www.hallieforarkansas.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "lanciaforcongress2026.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "infoforpurviforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.raymondesmithjr.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.tonyguyforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "johndeatonforsenate.co": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "burbridgeforri.com": ("dead", "2026-10-01", "Squarespace 'Website Expired' page"),
    "tanianymanforcongress.com": ("dead", "2026-10-01", "Wix 'domain not connected' page"),
}

# The 35 Senate seats on the 2026 ballot, keyed by state with the surname of
# the sitting member of that seat. Previously duplicated verbatim inside both
# index.html and map.html; it is pipeline data, so it belongs here.
SENATE_SEATS_UP_2026 = {
    "AK": "Sullivan", "AL": "Tuberville", "AR": "Cotton", "CO": "Hickenlooper",
    "DE": "Coons", "FL": "Moody", "GA": "Ossoff", "IA": "Ernst", "ID": "Risch",
    "IL": "Durbin", "KS": "Marshall", "KY": "McConnell", "LA": "Cassidy",
    "MA": "Markey", "ME": "Collins", "MI": "Peters", "MN": "Smith",
    "MS": "Hyde-Smith", "MT": "Daines", "NC": "Tillis", "NE": "Ricketts",
    "NH": "Shaheen", "NJ": "Booker", "NM": "Lujan", "OH": "Husted",
    "OK": "Armstrong", "OR": "Merkley", "RI": "Reed", "SC": "Graham",
    "SD": "Rounds", "TN": "Hagerty", "TX": "Cornyn", "VA": "Warner",
    "WV": "Capito", "WY": "Lummis",
}

# Seats whose first round is a nonpartisan ("jungle") primary held on general
# election day, with a runoff after it. Keyed (state, office, cycle); laid over
# the FEC calendar by results.effective_dates, and validate warns whenever the
# FEC's own dates disagree, so the entry is re-examined rather than forgotten.
#
# Louisiana's party primaries for the U.S. House (May 16 / June 27) were
# postponed after Louisiana v. Callais and the state redrew its map; Act 7 of
# the 2026 Regular Session moved the House races to an open primary on
# November 3 with a runoff on December 12 (Louisiana Secretary of State release
# of 2026-07-08; Wikipedia, "2026 United States House of Representatives
# elections in Louisiana", revision 1377090557, re-read 2026-10-01). The FEC
# calendar's "primary 2026-08-07" is the close of qualifying. Louisiana's
# Senate race kept its closed party primaries and is not listed.
OPEN_PRIMARY_SEATS = {
    ("LA", "H", 2026): {
        "primary": "2026-11-03",
        "runoff": "2026-12-12",
        "source": "https://en.wikipedia.org/w/index.php?oldid=1377090557 "
                  "(Louisiana Secretary of State, 2026-07-08; Act 7, 2026 R.S.)",
    },
}

# Phrases in a Status value that mean the incumbent is not on the 2026 ballot.
NOT_SEEKING_MARKERS = ("retiring", "not running", "defeated", "ineligible", "resigned")


def status_override(name, current, member_id=None):
    """Return the curated status for a member, falling back to *current*.

    The bioguide-keyed table wins over the older name-substring one."""
    if member_id and member_id in MEMBER_STATUS_BY_ID:
        return MEMBER_STATUS_BY_ID[member_id][0]
    lowered = str(name).lower()
    for key, val in STATUS_OVERRIDES.items():
        if key.lower() in lowered:
            return val
    return current


def is_not_seeking(status):
    """True when a status line says the incumbent is leaving the seat."""
    lowered = str(status or "").lower()
    return any(marker in lowered for marker in NOT_SEEKING_MARKERS)


def blocked_campaign_host(url):
    """The BLOCKED_CAMPAIGN_HOSTS key that bars *url*, or None."""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return None
    bare = host[4:] if host.startswith("www.") else host
    for key in (host, bare):
        if key and key in BLOCKED_CAMPAIGN_HOSTS:
            return key
    return None
