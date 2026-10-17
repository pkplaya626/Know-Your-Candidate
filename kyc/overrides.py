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
    ("Barry Moore", "AL"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Barry_Moore_117th_U.S_Congress.jpg/800px-Barry_Moore_117th_U.S_Congress.jpg",
    ("Kevin Hern", "OK"): "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Kevin_Hern_118th_Congress.jpg/800px-Kevin_Hern_118th_Congress.jpg",
    ("Alex Vindman", "FL"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Alexander_Vindman_official_portrait.jpg/800px-Alexander_Vindman_official_portrait.jpg",
    ("Colin Allred", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Colin_Allred_official_photo.jpg/800px-Colin_Allred_official_photo.jpg",
    ("Brad Lander", "NY"): "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Brad_Lander_by_Gage_Skidmore.jpg/800px-Brad_Lander_by_Gage_Skidmore.jpg",
    ("Steve Toth", "TX"): "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Steve_Toth_Texas_House.jpg/800px-Steve_Toth_Texas_House.jpg",
    ("Troy Jackson", "ME"): "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Troy_Jackson_2019.jpg/800px-Troy_Jackson_2019.jpg",
    ("Josh Turek", "IA"): "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Josh_Turek.jpg/800px-Josh_Turek.jpg",
    ("Mark Baisley", "CO"): "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Mark_Baisley_2023.jpg/800px-Mark_Baisley_2023.jpg",
    ("Marquita Bradshaw", "TN"): "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Marquita_Bradshaw.jpg/800px-Marquita_Bradshaw.jpg",
    ("Annie Andrews", "SC"): "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Annie_Andrews_portrait.jpg/800px-Annie_Andrews_portrait.jpg",
}

# There is no list of members to leave out. Whoever has left is decided by
# bioguide id from Congress's own records (legislators.departures) and moved
# to Former_Members.csv by `congress --apply`. The name list that stood here
# matched on names (rules 3 and 17), and all three of its names had already
# left the roster.

# Where the Senate notes below were checked (2026-10-02). Each is the section
# that states the fact, read from the live article, never from memory.
_SENATE_2026 = "https://en.wikipedia.org/wiki/2026_United_States_Senate_elections"

# Seat-status notes keyed on bioguide id, the only safe key for a person
# (rules 3 and 17). These used to sit in a second table matched as a
# case-insensitive substring of the member's name, which only worked while the
# roster spelled every name the way the table did. Each value is (status line,
# source). A member who is leaving the seat needs a NOT_SEEKING_MARKERS phrase
# in the status line; the two special-election notes are for members who are
# on the ballot.
MEMBER_STATUS_BY_ID = {
    # Interim appointees running in the specials (the article's seat count
    # footnote: "the interim appointees from Florida and Ohio running").
    "M001244": ("2026 special election for final two years of Marco Rubio's term",
                _SENATE_2026 + "#Seats"),                                   # Ashley Moody, FL
    "H001104": ("2026 special election for final two years of JD Vance's term",
                _SENATE_2026 + "#Seats"),                                   # Jon Husted, OH
    # Listed in the article's Retirements table.
    "T000278": ("Retiring to run for governor",
                _SENATE_2026 + "#Retirements"),                             # Tommy Tuberville, AL
    "E000295": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Joni Ernst, IA
    # The rosters use his legal name; he is usually reported as "Dick Durbin".
    # Keyed on the id, the spelling no longer matters.
    "D000563": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Richard Durbin, IL
    "M000355": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Mitch McConnell, KY
    "S001181": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Jeanne Shaheen, NH
    "L000571": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Cynthia Lummis, WY
    # "where incumbent Gary Peters is not running for reelection".
    "P000595": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Democratic_incumbents"),                   # Gary Peters, MI
    # Marked "(retiring)" in the article's ratings table.
    "D000618": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Predictions"),                             # Steve Daines, MT
    # "Republican Thom Tillis of North Carolina is retiring from the Senate".
    "T000476": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026),                                              # Thom Tillis, NC
    # "Democratic incumbent Tina Smith is not seeking a second full term."
    "S001203": ("Incumbent not running for re-election in 2026.",
                "https://en.wikipedia.org/wiki/"
                "2026_United_States_Senate_election_in_Minnesota"),         # Tina Smith, MN
    # The article's Defeats section: both lost renomination in their primaries.
    "C001056": ("Incumbent defeated in primary for 2026 election.",
                _SENATE_2026 + "#Defeats"),                                 # John Cornyn, TX
    "C001075": ("Incumbent defeated in primary for 2026 election.",
                _SENATE_2026 + "#Defeats"),                                 # Bill Cassidy, LA
    # "Armstrong was sworn in on March 24 and was required to sign an oath
    # stating that he would not run in the 2026 election."
    "A000383": ("Not running in 2026: appointed in March 2026 on an oath not to seek the seat.",
                _SENATE_2026 + "#Oklahoma"),                                # Alan Armstrong, OK
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

# Members who are on the November ballot for an office this site does not
# cover, keyed on bioguide id: {bioguide: (what they are, source, checked)}.
# Without it Byron Donalds, Florida's Republican nominee for governor, read
# only "Not running for this seat in 2026", and Tommy Tuberville "Withdrew".
# Each entry is the winner the results page marks with its `winning
# candidate` template (rule 29), read from the article's wikitext on the day
# given, never from memory; a nominee who later withdraws is taken out.
# The profile drops an entry once its member starts a new term, `validate`
# reports one whose member has gone (stale-other-office), and after Election
# Day it reports them all, for the result to be read from the same page.
_GOV = "https://en.wikipedia.org/wiki/2026_{}_gubernatorial_election"
OTHER_OFFICE_NOMINEES = {
    # Republican primary results, May 19: Tuberville 85.4%.
    "T000278": ("Republican nominee for Governor of Alabama",
                _GOV.format("Alabama"), "2026-10-17"),
    # Republican primary results, July 21: Biggs 74.0%.
    "B001302": ("Republican nominee for Governor of Arizona",
                _GOV.format("Arizona"), "2026-10-17"),
    # Republican primary results, August 18: Donalds 47.8%.
    "D000032": ("Republican nominee for Governor of Florida",
                _GOV.format("Florida"), "2026-10-17"),
    # Republican primary results, August 4: James 50.05%.
    "J000307": ("Republican nominee for Governor of Michigan",
                _GOV.format("Michigan"), "2026-10-17"),
    # Republican primary results, August 11: Tiffany 95.32%.
    "T000165": ("Republican nominee for Governor of Wisconsin",
                _GOV.format("Wisconsin"), "2026-10-17"),
    # Democratic primary results, August 1 (the Election System of the
    # Virgin Islands' territorial summary): Plaskett and Potter 46.99%.
    "P000610": ("Democratic nominee for Governor of the U.S. Virgin Islands",
                _GOV.format("United_States_Virgin_Islands"), "2026-10-17"),
}

# FEC registrations that are one person although their totals differ, so the
# exact same-committee signal (candidates.same_committee) cannot see it. Each
# entry maps the registration folded away to (the one kept, the evidence).
# Rule 25 still holds: a shared name alone never earns an entry here.
# A member's own FEC candidate id that congress-legislators does not list,
# keyed on bioguide id: {bioguide: (candidate id, evidence)}. Merged into the
# snapshot's `fecAll` (and `fec` once they sit in that chamber) when it is
# built, so a member elected to the other chamber is linked to that
# candidacy - and their money looked up - by its id, never by a name search.
# Rule 17; validate's member-candidacy-id-missing lists any further gap.
MEMBER_FEC_IDS = {
    # Ashley Hinson, IA-2, running for Iowa's Senate seat: S6IA00314 is
    # filed as "ARENHOLZ, ASHLEY HINSON" (Iowa, Senate, Republican), her
    # legal name, and is the FEC Candidate ID of the curated row for her
    # Senate candidacy; congress-legislators lists only her House id,
    # H0IA01174. Checked 2026-10-16.
    "H001091": ("S6IA00314", "the curated row for her Iowa Senate candidacy; filed under "
                             "her legal name, Arenholz"),
}

SAME_PERSON_FILINGS = {
    # NV-3: the results page links both registrations to one article,
    # [[Martin O'Donnell]], and their receipts and disbursements differ by the
    # same $28,832.67 - one transfer counted under one id only. Checked
    # 2026-10-02.
    "H6NV03204": ("H4NV03225", "one article on the results page; totals differ by "
                               "a single $28,832.67 transfer"),
}

# The name a results page uses for a filing the matcher cannot connect to it:
# a nickname the FEC filing does not carry. Keyed on the FEC candidate id;
# each entry is (the name exactly as the race's results page writes it, the
# evidence), and the evidence is the candidate's own principal campaign
# committee at the FEC (its name or its registered website), so the alias
# is the campaign's word, not a guess about a nickname (rule 17). Where the
# committee's register entry does not carry the name, the home page of the
# website that entry registers may, in its own title. Applied only inside
# the filing's own race (results.apply_cache). Checked 2026-10-14, the
# committees read from the FEC's /candidate/{id}/committees/ that day.
# Not settled, for want of such evidence: Rakhi Israni Singh (CA-14; her
# site says "Rakhi Israni"), Sonia Kacker (CA-26) and J. D. Scholten (Iowa
# Senate; both sites draw themselves with script), Daira Smith-Rodriguez
# (Maine Senate; no site registered).
RESULT_NAMES = {
    "S6GA00374": ("Buddy Carter", "committee C00543967 BUDDY CARTER FOR SENATE"),
    "S6IL00482": ("Raja Krishnamoorthi", "committee C00904466 RAJA FOR ILLINOIS; "
                                         "filed as KRISHNAMOORTHI, S"),
    "S6SC04452": ("Mark Sanford", "committee C00285254 SANFORD FOR SENATE, "
                                  "website marksanford.com"),
    "H6TN06205": ("Van Hilleary", "committee C00909838 VAN FOR TENNESSEE; "
                                  "filed as HILLEARY, WILLIAM V."),
    "H6WV02150": ("Ace Parsi", "committee C00927723 ACE PARSI FOR CONGRESS"),
    "H4NC02150": ("Max Ganorkar", "committee C00769463 GANORKAR FOR CONGRESS, "
                                  "website maxforcongress.com"),
    "H6MS04259": ("Carl Boyanton", "committee C00937136 CARL4CONGRESS; filed with "
                                   "the names reversed, CARL, BOYANTON LESTER"),
    "H6TX34098": ("Fred Hinojosa", "committee C00917724 FRED HINOJOSA FOR CONGRESS"),
    "H6VA01232": ("Salaam Bhatti", "committee C00912287 SALAAM BHATTI FOR CONGRESS"),
    "H6CO06157": ("Mel Tewahade", "committee C00944173 MEL FOR COLORADO, website "
                                  "melforcolorado.com; filed as TEWAHADE, BEMELEKOT W"),
    "S6IL00466": ("Casey Chlebek", "committee C00903823 CASEY CHLEBEK FOR US SENATE"),
    "H6NJ05239": ("Sandy Gajapathy", "committee C00920066 SANDY GAJAPATHY FOR CONGRESS"),
    "H4TX27105": ("Scott Mandel", "authorized committee C00862946 SCOTT MANDEL FOR "
                                  "CONGRESS; filed as MANDEL, CHARLES"),
    "H6TX09199": ("Crystal DeLeon-Sarmiento", "committee C00926535 CRYSTAL FOR US CONGRESS, "
                  "website crystalforuscongress.com titled \"Crystal De Leon Sarmiento for "
                  "US Congress\""),
    "H6IL09210": ("Mark Su", "committee C00904680 MARK SU FOR CONGRESS; filed as SU, DONGBO"),
    "H6OH14222": ("Nicole Frenchko", "committee C00935023 NIKI FRENCHKO FOR CONGRESS; "
                                     "filed reversed as NICOLE, FRENCHKO MICHELE"),
    "H6MI10300": ("Tripp Adams", "committee C00908293 TRIPP ADAMS FOR CONGRESS"),
    "H6FL22164": ("Herbie Wertheim", "committee C00945014 DR. HERBIE WERTHEIM FOR CONGRESS"),
    "H4FL02138": ("Yen Bailey", "committee C00882886 YEN BAILEY FOR CONGRESS"),
    "H6TX21376": ("Trey Trainor", "committee C00922344 TREY TRAINOR FOR TEXAS"),
    "H4OR01121": ("Jamil Ahmad", "committee C00870303 CHAUDHRY-AHMAD FOR CONGRESS, "
                                 "website jamilahmadforcongress.com"),
    "H6VA00028": ("J.P. Cooney", "committee C00938670 COONEY FOR CONGRESS, website "
                                 "cooneyforcongress.com titled \"J.P. Cooney for Congress\""),
    "H6IL09285": ("Hoan Huynh", "committee C00909903 HOAN FOR 9, website hoanfor9.com; "
                                "filed as HUYNH, KHAI-HOAN"),
    "H6CA30219": ("Pini Herman", "committee C00917641 PINI HERMAN FOR HOUSE CA30"),
    "H2CA18171": ("Luis Arregu\u00edn", "committee C00805770 LUIS ARREGUIN FOR CONGRESS CA-18"),
    "H6NC11222": ("Moe Davis", "committee C00906081 MOE DAVIS FOR CONGRESS COMMITTEE"),
    "H6NM01129": ("Didi Okpareke", "committee C00908509 NDIDIAMAKA OKPAREKE FOR CONGRESS, "
                                   "website didiforcongress.com"),
    "S6FL00863": ("Neil J. Gillespie", "committee C00943399 NEIL J GILLESPIE FOR US SENATE; "
                                       "filed as GILESPIE, NEIL JOSEPH"),
    "H6WI07256": ("Niina Baum", "committee C00938019 BAUM FOR CONGRESS, website "
                                "baumforwisconsin.com; filed as THRELFALL-BAUM, NIINA"),
    "H6TX31151": ("Vince Offer", "committee C00928614 OFFER VINCE SHAMWOW SHLOMI FOR CONGRESS"),
    "H6TX35111": ("Randy Adams", "committee C00929570 RANDY ADAMS FOR CONGRESS"),
    "H6GA01208": ("Sharon Williamson", "committee C00931949 SHARON STOKES-WILLIAMSON FOR "
                                       "CONGRESS, website sswilliamsonforcongress.com"),
    "H6TX24180": ("TJ Ware", "committee C00907527 TJ WARE FOR CONGRESS"),
}

# Official voting pages that replace what NASS's "Can I Vote" lists for a
# state, keyed (state, kind) - kind is status, polling, absentee or register.
# Each is (the URL NASS lists, the state's own page that replaces it or None
# to show no button, a label or None for the usual one, the evidence). The
# NASS URL is kept so validate warns once NASS changes its entry and the
# override can go. Checked 2026-10-14, every replacement found on the
# state's own election site and answering 200.
VOTING_LINKS = {
    ("IA", "absentee"): (
        "https://sos.iowa.gov/elections/electioninfo/absenteeinfo.html",
        "https://sos.iowa.gov/voters/absentee-voting", None,
        "NASS's page answers 404 'Page not found'; sos.iowa.gov links Absentee Voting here"),
    ("IN", "absentee"): (
        "http://www.in.gov/sos/elections/2402.htm",
        "https://www.in.gov/sos/elections/voter-information/ways-to-vote/absentee-voting", None,
        "NASS's page answers 404; in.gov/sos/elections links absentee voting here"),
    ("MD", "polling"): (
        "http://www.elections.state.md.us/voting/where.html",
        "https://elections.maryland.gov/voting/where.html", None,
        "the old domain now redirects to the board's home page; this is the same "
        "'Voter Registration and Polling Place Look-Up' on the current one"),
    ("CO", "absentee"): (
        "https://www.sos.state.co.us/pubs/elections/FAQs/ElectionDay.html",
        "https://www.sos.state.co.us/pubs/elections/FAQs/mailBallotsFAQ.html", None,
        "NASS links the Election Day FAQ; Colorado mails every voter a ballot, and this "
        "is the Secretary of State's Mail-in Ballots FAQ"),
    ("ND", "register"): (
        "https://www.sos.nd.gov/elections/voter",
        "https://www.sos.nd.gov/elections/voter", "Voting in North Dakota",
        "North Dakota does not register voters; NASS lists its general voter page "
        "under 'register', which the page labelled 'Register to vote'"),
    ("ND", "status"): (
        "https://www.sos.nd.gov/elections", None, None,
        "no registration to check; NASS lists the general Elections page"),
}

# Campaign websites that must never be linked, keyed on the host the FEC
# committee registered (lower case; a key without "www." also covers the
# "www." form). The FEC keeps whatever site a committee once filed, and a
# lapsed campaign domain gets bought: on 2026-10-01 seven served gambling pages
# under a candidate's name. Each value is (kind, date checked, what was seen).
# "hijacked" entries must never come back. "dead" entries - the host does not
# exist in DNS, the hosting platform says the site is gone, or the domain is
# parked - and "unrelated" ones - it answers, with a site that is not a
# campaign - may be removed once the committee files a working address;
# validate reports any entry that no longer matches a cached site.
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
    # Found by `enrich`, which reads every linked committee site, and each
    # confirmed by hand on 2026-10-02.
    "joshweil.us": ("hijacked", "2026-10-02",
                    "www and bare both 301 through other domains to an Indonesian "
                    "slot-gambling page"),
    "dannymintonfortexas.com": ("dead", "2026-10-02",
                                "parked: a script sends visitors to a registrar's parking lander"),
    "marklambforcongress.com": ("dead", "2026-10-02",
                                "parked: a script sends visitors to a registrar's parking lander"),
    "angusformaine.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "jakeforma.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "drkumar4congress.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "abudahbisa.org": ("unrelated", "2026-10-02",
                       "an electronics shop's page; nothing about a campaign"),
}

# Images on a campaign's own site that `enrich` would take as the candidate's
# portrait but that are not one, keyed on the image URL: (date checked, what it
# shows). Its rules turn away logos, share cards, merchandise and most group
# shots by file name and shape; these passed both, and only a look tells. The
# weekly refresh re-reads every site, so a correction made by editing the
# cache would not last. validate reports an entry no cached site offers.
NOT_A_PORTRAIT = {
    "https://kaileebuller.com/wp-content/uploads/2026/03/Buller.jpg":
        ("2026-10-02", "a family photograph: four people in the snow"),
    "https://rickbrattin.com/wp-content/uploads/2026/02/Brattin-extended-scaled.png":
        ("2026-10-02", "a hunting scene; no face at card size"),
}

# The 2026 Senate seats are no longer typed here. A surname table matched
# Darline Graham to Lindsey Graham's seat; the seats are now the frozen race
# record, keyed on bioguide ids (kyc/record.py, data/record_2026.json).

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

# States whose federal general election goes to a runoff when no candidate wins
# a majority, and when (state code: (date, evidence)). After Election Day the
# results reader treats an unpartisan "Runoff results" table on these states'
# pages as that runoff (results.resolve_race). Louisiana's House seats are an
# open primary with its own December round (OPEN_PRIMARY_SEATS).
GENERAL_RUNOFFS = {
    "GA": ("2026-12-01", "O.C.G.A. 21-2-501(a): a runoff is held on the 28th day after a "
                         "general election in which no candidate receives a majority; "
                         "November 3 + 28 days = December 1, 2026"),
}

# Incorporated places the Census Bureau's 2022 Government Units listing files
# under a name the city join (counties.match_cities) cannot tie to the place,
# each joined here on the listing's own government id - never on a name
# (rule 59). {place GEOID: (listing id, the listing's name, evidence)}. The
# build refuses an entry whose id holds another name, lies in another county
# than the place, or is joined elsewhere, and reports one the join no longer
# needs. Checked 2026-10-16: in each case the place's county holds no other
# government the place could be. Never a government the place replaced:
# Rib Mountain and Lisbon, Wisconsin, and Baldwin and Empire, Minnesota,
# incorporated from the towns and townships the 2022 listing holds (rule 59).
PLACE_GOVERNMENTS = {
    "0934460": ("07200620100000", "Borough of Groton Long Point Association",
                "the Census maps the borough as Groton Long Point; its government is the "
                "Groton Long Point Association, the only one under that name in the region"),
    "1234132": ("10204430100000", "Village of Islamorada",
                "the Census maps it as Islamorada, Village of Islands, the village's full name"),
    "1326156": ("11105005000000", "County of Echols",
                "Echols County and Statenville are one consolidated government, which the "
                "Census maps as a place and lists as Echols County's county government"),
    "1939675": ("16204000300000", "City of Jewell",
                "the Census maps the city as Jewell Junction; the listing as Jewell, in the "
                "same county, Hamilton"),
    "2904248": ("26209500500000", "Village of Bellerive",
                "the Census maps it as Bellerive Acres, the listing as Bellerive, both in "
                "St. Louis County"),
    "2925411": ("26205730100000", "Village of Fountain-N-Lake",
                "the same name, spelled Fountain N' Lakes on the Census map"),
    "2964478": ("26209507500000", "City of St Johns",
                "the listing's St Johns, in St. Louis County, is the Census map's St. John"),
    "2975814": ("26209508600000", "Village of Velda Hills",
                "the Census maps it as Velda Village Hills, the listing as Velda Hills, both "
                "in St. Louis County"),
    "3709530": ("34201440100000", "Town of Cajah Mountain",
                "the same name, spelled Cajah's Mountain on the Census map"),
    "4030900": ("37204970100000", "Town of Grand Lake",
                "the Census maps the town as Grand Lake Towne; the listing as Grand Lake, in "
                "the same county, Mayes"),
    "4811155": ("44215220100000", "Village of Buffalo Springs",
                "the Census maps the village as Buffalo Springs Lake; the listing as Buffalo "
                "Springs, in the same county, Lubbock"),
    "5526350": ("50206500500000", "Village of Fontana",
                "the Census maps the village by its full name, Fontana-on-Geneva Lake"),
    "5624750": ("51200400500000", "Town of Grand Encampment",
                "the Census maps the town as Encampment; its legal name is Grand Encampment"),
    # Governments the listing files as towns or townships on a county
    # subdivision code the Census has since replaced: the 2025 map draws each
    # as an incorporated place with a subdivision of the same name and land,
    # coextensive with it (functional status F), on a new code - Mount
    # Lebanon 51696 -> 51794, Penn Hills 59032 -> 59040, Bridgewater 08085 ->
    # 08130, Randolph 55955 -> 56000. The same government, reclassified, not
    # a new one that replaced it.
    "4251794": ("39300202300000", "Township of Mount Lebanon",
                "the Census now maps the township as the municipality of Mount Lebanon"),
    "4259040": ("39300202900000", "Township of Penn Hills",
                "the Census now maps the township as the municipality of Penn Hills"),
    "2508130": ("22301200200000", "Town of Bridgewater",
                "the Census now maps the town, which has a city form of government, as "
                "Bridgewater Town city"),
    "2556000": ("22301102000000", "Town of Randolph",
                "the Census now maps the town, which has a city form of government, as "
                "Randolph Town city"),
}

# Phrases in a Status value that mean the incumbent is not on the 2026 ballot.
NOT_SEEKING_MARKERS = ("retiring", "not running", "defeated", "ineligible", "resigned")


def status_override(member_id, current):
    """Return the curated status for a member, falling back to *current*.

    Keyed on bioguide id only (rules 3 and 17): a name never selects a note."""
    entry = MEMBER_STATUS_BY_ID.get(member_id) if member_id else None
    return entry[0] if entry else current


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
