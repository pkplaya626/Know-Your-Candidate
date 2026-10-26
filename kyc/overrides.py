"""Hand-curated corrections layered on top of the CSV rosters.

Everything here is an editorial judgement rather than pipeline logic, so it
lives apart from the loaders. Keep entries sourced and minimal - the CSVs are
the source of truth wherever they are correct.
"""

from urllib.parse import urlsplit

# A candidate's portrait chosen by a person, keyed on the profile's id (rules
# 3 and 17): a curated row's ``ID`` ("CAND_4") or a filer's ("FEC_<candidate
# id>"). A name key put one Mike Rogers's portrait on the other's profile,
# and in 2026-10-17 24 of the 25 entries that stood here named Commons files
# made up from a name ("Roy_Cooper_official_photo.jpg"), which do not exist -
# the guess rule 24 forbids. Each entry names a file a page serves now, and
# a person looked at the photograph and at the page:
#
#   url    the file shown: a government office's or the campaign's own file
#          as the page serves it, or a Commons file's upload address; or,
#          where an office's page draws the portrait with no address of its
#          own (a data: image), the file hosted here unmodified
#          ("photos/<hash>.png", listed in rule 101's manifest, ``hosted``,
#          with the page, the hash and the day read)
#   page   the page that names the person beside it (a Commons file: its own
#          description page, in the person's own category)
#   words  the page's words that name them beside it
#   by     whose photograph it is, for the credit line (rule 87); a Commons
#          file's credit is read from its page (``portraits.credit_all``),
#          never typed here
#   tie    why the person the page names is this profile's (rule 25: the
#          state, the office, the years)
#   seen   what the photograph shows: the person alone, nobody else in the
#          frame even in part, the face a tenth of the 4:5 card or more
#   read   the day the page and the photograph were read
#   seat   only for a file the legislature names by its seat ("rep17.jpg"),
#          which shows whoever holds it: the state, chamber, district, Open
#          States id and name of the member it was read for. The photograph
#          is withheld, and validate warns (photo-curated-unseated), once the
#          roster no longer seats them there (photos.curated_seated). A file
#          hosted here is the member's bytes, read once, and needs none.
#
# ``portraits`` puts the entry in the portrait cache as route ``curated``,
# where its size, its weight and a Commons file's credit are read like any
# other; it stands ahead of every automatic route, since a person chose it,
# and ``validate`` fails an entry without these fields, one a person
# refused (NOT_A_PORTRAIT) and one for a profile that no longer exists.
#
# The first entries (2026-10-25) are for people on the November ballot
# whom the background-people sweep of PR #139 left with the silhouette,
# where a route tied to them offers a clean photograph (the owner: "more
# content is better than strict rules", but "better to leave out background
# people").
CANDIDATE_PHOTOS = {
    "CAND_4": {
        "url": "https://www.texasattorneygeneral.gov/sites/default/files/inline-images/"
               "ken_paxton_bio_thumb.jpg",
        "page": "https://www.texasattorneygeneral.gov/about-office",
        "words": "\"About the Attorney General\": \"Ken Paxton is the 51st Attorney General of "
                 "Texas\", the image's alt text \"Texas Attorney General Ken Paxton\"",
        "by": "Office of the Texas Attorney General",
        "tie": "Ken Paxton, the Texas Republican Senate nominee, holds that office: his record "
               "of offices (history, Wikidata and his article agreeing) gives Texas Attorney "
               "General since 2015, and this site's Texas attorney general card shows the same "
               "file from the same page (officers.add_ag_photos)",
        "seen": "a studio portrait, him alone against a plain backdrop",
        "read": "2026-10-25",
    },
    "CAND_9": {
        "url": "https://run.imgix.net/68d35dd5-f7a6-4a7e-9057-c3908286d00f/"
               "e4f5b452-3eca-4f0c-82ea-227d95204138/e4f5b452-3eca-4f0c-82ea-227d95204138.jpg"
               "?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C393%2C2102%2C2282"
               "&auto=compress%2Cformat&fit=fillmax&w=640&q=75&s=7faf701c8ebd5e5e8466e7faf23dc0dc",
        "page": "https://www.bradlanderforcongress.com/",
        "words": "the page's opening photograph, beside \"Fight, Don't Fold. Brad Lander is "
                 "running for Congress\" (the srcset's 640px form, signed by the site)",
        "by": "the campaign's website (bradlanderforcongress.com)",
        "tie": "the site his filed campaign site (landerfornyc.com) moved to, which enrich "
               "read as still naming him; his file names no surname, so rule 38's reader "
               "could not take it unattended",
        "seen": "him alone in front of a brick house and a red door, arms folded",
        "read": "2026-10-25",
    },
    "FEC_H6IL02355": {
        "url": "https://www.cookcountyil.gov/sites/g/files/ywwepo161/files/styles/"
               "crop_profile_photo/public/images/portraits/2021-09/"
               "donna_miller_6th_district_0.jpg?h=9326d3c7&itok=su4DaALf",
        "page": "https://www.cookcountyil.gov/all-people/donna-miller",
        "words": "\"Donna Miller - County Board Commissioner, 6th District\", the image's alt "
                 "text \"Board of Commissioner Donna Miller\"",
        "by": "Cook County",
        "tie": "the IL-2 nominee is that commissioner: the article her ballot page links is "
               "about the Cook County commissioner, and her campaign's site says \"As a Cook "
               "County Commissioner, she's led major initiatives\"",
        "seen": "a studio portrait, her alone before the county's seal",
        "read": "2026-10-25",
    },
    "FEC_H6IN05307": {
        "url": "https://indianasenatedemocrats.org/wp-content/uploads/2024/08/"
               "Ford_Headshot-with-State-Flag.jpg",
        "page": "https://indianasenatedemocrats.org/senator/s29/",
        "words": "\"State Senator J.D. Ford - Indiana Senate Democrats\", the image's alt text "
                 "\"Senator J.D. Ford\"",
        "by": "Indiana Senate Democrats",
        "tie": "the IN-5 nominee sits in the Indiana Senate (history: Member of the State "
               "Senate of Indiana since 2018, corroborated), and the legislature roster "
               "(Open States) links this caucus page for him; his card's own route stops "
               "because the legislature's page it links shows no photograph",
        "seen": "a studio portrait, him alone before the state flag",
        "read": "2026-10-25",
    },
    "FEC_H6TN09449": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3d/"
               "Justin_J._Pearson_at_the_White_House.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Justin_J._Pearson_at_the_White_House.jpg",
        "words": "\"Tennessee state representative Justin J. Pearson at the White House, April "
                 "24, 2023\", in Category:Justin J. Pearson; {{PD-USGov-POTUS}}, author "
                 "\"@whitehouse (The White House)\"",
        "tie": "the TN-9 nominee is that representative (history: Member of the Tennessee "
               "House of Representatives since 2023, corroborated); the legislature serves "
               "his photograph only inline, with no file to link",
        "seen": "him alone outside the Eisenhower building, facing the camera",
        "read": "2026-10-25",
    },
    "FEC_H6TN09464": {
        # Brent Taylor, TN-9's Republican nominee. His Commons file was
        # refused (someone else in the frame); the Senate's member page draws
        # his portrait only inline, so it is hosted here unmodified (the PR
        # #141 review: TN-9's Democratic nominee had a photograph and he did
        # not).
        "url": "photos/dc407c55c78c101cce27.png",
        "page": "https://wapp.capitol.tn.gov/apps/LegislatorInfo/member?district=S31",
        "words": "\"Senator Brent Taylor\" heading the page, directly above the photograph "
                 "(alt text \"Photo of Brent Taylor\"), then \"Republican\", \"Memphis\", "
                 "\"District 31\", \"Born on August 9, 1968\"",
        "by": "Tennessee General Assembly",
        "tie": "the article his ballot page links (Brent Taylor (Tennessee politician)) says "
               "he has served since 2023 as a member of the Tennessee Senate representing "
               "District 31, born August 9, 1968, and is a candidate for Tennessee's 9th "
               "district; the roster (Open States) seats Brent Taylor in TN upper 31. The "
               "file is the page's data: image decoded, so it stays his whoever later "
               "holds the seat",
        "seen": "a studio portrait, him alone against a grey backdrop",
        "read": "2026-10-25",
    },
    "FEC_H6AZ05190": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/72/Jay_Feely_2026_%28cropped%29.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Jay_Feely_2026_(cropped).jpg",
        "words": "\"Jay Feely speaking with attendees at the 'Build the Red Wall' rally at Dream "
                 "City Church in Phoenix, Arizona\" (2026-04-17), in Category:Jay Feely; Gage "
                 "Skidmore's photograph, CC BY-SA 4.0",
        "tie": "the AZ-1 nominee, in Phoenix in his campaign's year; the article his ballot "
               "page links (Jay Feely) is his",
        "seen": "him alone at a lectern, microphones at the foot of the frame and nobody else",
        "read": "2026-10-25",
    },
    "FEC_H6CT01206": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/2/2e/Luke_Bronin_%28cropped_3x4%29.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Luke_Bronin_(cropped_3x4).jpg",
        "words": "\"Governor Dannel P. Malloy today joined Hartford Mayor Luke Bronin\" (2018-09-20), "
                 "in Category:Luke Bronin; extracted from the governor's office's Flickr "
                 "photograph, CC BY 2.0",
        "tie": "the CT-1 nominee, Hartford's mayor from 2016 to 2024 (history, corroborated); "
               "the article his ballot page links (Luke Bronin) is his",
        "seen": "him alone, head and shoulders, before a market's banner",
        "read": "2026-10-25",
    },
    "FEC_H6LA05341": {
        "url": "https://house.louisiana.gov/H_Reps/RepPics/rep17.jpg",
        "page": "https://house.louisiana.gov/H_Reps/members?ID=17",
        "words": "'State Representative Patricia \"Pat\" Moore', 'Democrat', 'District 17' "
                 "above the file",
        "by": "Louisiana House of Representatives",
        "tie": "her filed campaign site (patmooreforcongress.com) says \"State Representative, "
               "Louisiana House District 17 since 2019\" and links \"Official Louisiana House "
               "profile\"; its own headshot (refused for the chamber behind her) is the same "
               "woman. The file is keyed by seat, and legphotos withholds it unattended "
               "because its date is a copy's; a person compared the two photographs",
        "seen": "a studio portrait, her alone against a grey backdrop",
        "read": "2026-10-25",
        # rep17.jpg shows whoever holds District 17 (the PR #141 review).
        "seat": {"state": "LA", "chamber": "lower", "district": "17",
                 "legislator": "ocd-person/88548c7a-b637-4821-b336-c99cfa475e22",
                 "name": "Pat Moore"},
    },
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
# Until then the page says it in the past tense from the day after Election
# Day ("Was the ..."), so a stale entry never reads as a race still to come.
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
    # Democratic primary results, August 11: Klobuchar 89.7% ("Election box
    # winning candidate ... [[Amy Klobuchar]] ... 615,041", read 2026-10-18;
    # the article: "Democratic senator Amy Klobuchar ... launched a campaign
    # for the governor's office on January 29, 2026"). The Secretary of
    # State's sample ballot prints "Amy Klobuchar and Ben Schierer
    # Democratic-Farmer-Labor" (data/statewide_candidates.json). Her Senate
    # seat is not up, so only her profile says it (PR #109 review).
    "K000367": ("Democratic-Farmer-Labor nominee for Governor of Minnesota",
                _GOV.format("Minnesota"), "2026-10-18"),
    # Republican primary results, August 6: Blackburn 43.6%. Her Senate
    # seat is not up, so only her profile says it.
    "B001243": ("Republican nominee for Governor of Tennessee",
                _GOV.format("Tennessee"), "2026-10-17"),
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

# Names a reader searches a member by that congress-legislators does not
# record (its name.nickname covers "Jim Clyburn"), keyed on bioguide id
# (rules 3 and 17), each with where the name is given as theirs. Search
# only: never displayed as the person's name. "AOC" found only a candidate
# whose text said "endorsed by AOC" (audit 2026-10-17, GRID-05); "MTG" found
# nobody (GRID-08). validate reports a key that is neither a profile nor a
# departed member the page lists.
SEARCH_ALIASES = {
    "O000172": (("AOC", "Wikipedia, Alexandria Ocasio-Cortez, first sentence: \"also known as "
                        "AOC\"; read 2026-10-18"),),
    "G000596": (("MTG", "Wikipedia, Marjorie Taylor Greene, first sentence: \"also known by her "
                        "initials MTG\"; read 2026-10-18"),),
}

SAME_PERSON_FILINGS = {
    # NV-3: the results page links both registrations to one article,
    # [[Martin O'Donnell]], and their receipts and disbursements differ by the
    # same $28,832.67 - one transfer counted under one id only. Checked
    # 2026-10-02.
    "H6NV03204": ("H4NV03225", "one article on the results page; totals differ by "
                               "a single $28,832.67 transfer"),
    # Each pair below is one principal campaign committee whose Form 1 lists
    # both ids, as the FEC's /candidate/{id}/committees/ gave it on
    # 2026-10-17. They are off every ballot, so the campaigns cache (which
    # reads committees only for people still running) does not hold the
    # committee that rule 72 joins them on; the money is equal to the cent.
    "H6FL01440": ("H6FL01457", "FL-1: committee C00894337 BRODEN FOR HOUSE lists both; "
                               "$19,541.21 in and out on each"),
    "H6TX38107": ("H6TX38099", "TX-38: committee C00928077 WILLIAM TAGGART FOR CONGRESS "
                               "lists both; $9,995.08 in and out on each"),
    "S6ME00316": ("S6ME00324", "Maine Senate: committee C00902759 CARMEN4SENATE.COM lists "
                               "both ('Carmem' is a misspelling); $17,759.71 on each"),
    # VA-11: committee C00959106 PURVES FOR CONGRESS lists all three, filed as
    # "PURVES, ARTHUR GRAHAME MR."; the same name and committee fold them
    # (rule 72). H6VA11249 is the one kept: its totals also count his second
    # committee, C00951277, and run to 2026-09-30, where H6VA11256's stop at
    # 2026-08-27 - so the race shows his current money, not a stale $5,142.86.
    "H6VA11256": ("H6VA11249", "VA-11: committee C00959106 lists H6VA11249, H6VA11256 and "
                               "H6VA11264, all filed as PURVES, ARTHUR GRAHAME MR."),
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
    # Audit 2026-10-17, STATEGOV-10. Nevada's absentee link (a page under
    # "voters-with-disabilities") is held: it answered 403 to a plain
    # request and drew a blank page in headless Chrome, which concludes
    # nothing (rule 8) until a person opens it.
    ("DC", "absentee"): (
        "https://www.dcboe.org/voters/casting-your-vote/voting-by-special-ballot",
        "https://www.dcboe.org/voters/casting-your-vote/mail-ballot-instructions", None,
        "NASS links 'Voting by Special Ballot', a ballot cast at the polls when a voter's "
        "eligibility is in question; D.C. mails every voter a ballot, and this is the Board's "
        "'Mail Ballot Instructions', linked from dcboe.org (title read 2026-10-17)"),
    ("WY", "status"): (
        "https://sos.wyo.gov/Elections/State/RegisteringToVote.aspx", None, None,
        "NASS lists 'Registering to Vote in Wyoming' - the same page as 'register', with no "
        "lookup on it - so 'Check your registration' led to no check (read 2026-10-17)"),
    # The lookup itself is not dead: it sits behind a bot wall that answered
    # a captcha page ("Oregon Secretary of State Captcha/Support ID") to a
    # browser-like request on 2026-10-19 and 404 to GitHub's runner twice on
    # 2026-10-18, after reading live on 2026-10-17. A wall concludes nothing
    # (rule 8), and its 404 stopped the daily refresh; the Secretary of
    # State's own My Vote page, which a script can read, links the lookup.
    ("OR", "status"): (
        "https://secure.sos.state.or.us/orestar/vr/showVoterSearch.do?lang=eng",
        "https://sos.oregon.gov/elections/pages/myvote.aspx", None,
        "NASS links the ORESTAR voter lookup, behind a bot wall a script cannot pass; "
        "'Oregon Secretary of State : My Vote' on sos.oregon.gov links it as 'Go to My Vote "
        "Now' (read 2026-10-19)"),
}

# Links on a state's government block that the rosters give wrongly, each
# opened on 2026-10-17 (audit 2026-10-17, LINKS-08, LINKS-09):
# {(state, office, field): (what the roster lists, or None for nothing;
# what to show instead, or None to show nothing; evidence)}. office is
# "governor", "lt", "ag" or "sos"; field is "website" or "bio". A dead
# biography is dropped, never guessed at: the office's own home page is
# already linked beside it ("Office"). An entry applies only while the
# roster still lists what it replaces, and stategov reports one that no
# longer matches, so the next refresh cannot put a dead link back silently.
OFFICE_LINKS = {
    ("ME", "sos", "bio"): ("https://www.maine.gov/sos/about/bio.html", None,
                           "404 'Sorry, but I can't find that page'"),
    ("LA", "sos", "bio"): ("https://www.sos.la.gov/OurOffice/LearnAboutNancyLandry/Pages/default.aspx",
                           None, "404 'Oops! Page not found'"),
    ("WV", "sos", "bio"): ("https://sos.wv.gov/about/Pages/KWBio.aspx", None,
                           "404 'Page not found | WV Secretary of State'"),
    ("VT", "sos", "bio"): ("https://sos.vermont.gov/secretary-s-desk/secretary-copeland-hanzas/", None,
                           "404 'Page not found | Secretary of State'"),
    ("KS", "sos", "bio"): ("https://sos.ks.gov/about-the-office/schwab-biography.html", None,
                           "redirects to /messages/page404.html, 'Page Not Found', with status 200"),
    ("AZ", "sos", "bio"): ("https://azsos.gov/about-office/about-secretary", None,
                           "404 'Page not found | Arizona Secretary of State'"),
    ("IN", "governor", "website"): ("https://www.in.gov/gov/index.htm", "https://www.in.gov/gov/",
                                    "the NGA's link answers 404 'Governor Braun: Error - Page Not "
                                    "Found'; /gov/ is 'Governor Braun: Governor Home'"),
    # The NGA's pages for the two governors sworn in in January 2026 carry no
    # website; each is the office's own, titled with the governor's office.
    ("NJ", "governor", "website"): (None, "https://nj.gov/governor/",
                                    "'Office of New Jersey Governor Mikie Sherrill'"),
    ("VA", "governor", "website"): (None, "https://www.governor.virginia.gov/",
                                    "'Governor of Virginia'"),
}


# Photographs of state officers whose roster has none (STATEGOV-13), each looked at on the day given: {(state, office):
# {name, photo, page, by, weight, checked, evidence}}. office is "governor",
# "lt", "ag" or "sos". An entry is shown only while the roster names that
# very person as the holder (stategov.officer_photos): once the office
# changes hands the build says so and shows nothing, never a predecessor's
# face (rule 87). Never from a search - the office's own page, or the
# association whose roster names them.
def _officer_photo(name, photo, page, by, weight, evidence, checked="2026-10-18"):
    return {"name": name, "photo": photo, "page": page, "by": by,
            "weight": dict(zip(("bytes", "width", "height"), weight)),
            "checked": checked, "evidence": evidence}


_NASS = "https://www.nass.org/sites/default/files/styles/secretary/public/"
_NASS_BY = "National Association of Secretaries of State"
# NASS files its members' photographs under the state's code, which
# officers._surname_in cannot tie to a person; each of these was looked at
# and was uploaded after its holder took office, so it cannot be a
# predecessor's.
_NASS_CARD = ("NASS's roster card names {} beside this photograph, filed as {} in {}, after "
              "they took office ({}); a head-and-shoulders portrait. {}")


# An attorney general's photograph is read by the pipeline from the
# office's own pages (officers.add_ag_photos). Where those show none, or one
# offered only above the caps that no resizer serves smaller (rule 87: the
# office's file is then kept, heavy, and this lighter card goes first), it is
# the National Association of Attorneys General's: its "Find
# my AG" roster puts each attorney general's name and state on a card beside
# the photograph. naag.org answers a script and a headless browser with a
# Cloudflare challenge, so the roster was read by a person in a windowed
# Chrome (tools/read_naag_cards.mjs), each photograph at the size the card
# itself offers (WordPress's 225x300), weighed there; a windowed Chrome with
# a fresh profile loads these files from another site, and a row whose
# photograph fails to load keeps its empty circle (kyc-stategov.js). Matched
# on the card's state and full name, never on the file's name: NAAG filed
# West Virginia's as "ag-WA-McCusker". NAAG publishes no licence ("(c) 2026
# National Association of Attorneys General"): the credit says whose it is,
# as the NGA's and NASS's do. Read again when the build says one has gone
# stale (a new holder) - never carried to someone else. Massachusetts's and
# New Hampshire's cards are not recorded: their offices' pages have not
# confirmed the holder's name (rule 56), and a photograph is given only to a
# confirmed one. Maryland's, Michigan's, Tennessee's and Texas's offices'
# own pages give theirs (officers.BIO_PAGES and the page the front page
# links). So, since 2026-10-25, do Arizona's, California's, Hawaii's, New
# Jersey's, Pennsylvania's, South Dakota's and West Virginia's: each offers
# its photograph only above the caps, and Photon serves the same file
# smaller (rule 87), so their cards were dropped. Florida's and Washington's
# offices' files are served no smaller, so the cards below go first there.
_NAAG_ROSTER = "https://www.naag.org/find-my-ag/"
_NAAG_BY = "National Association of Attorneys General"


def _naag_card(name, path, weight, evidence, checked="2026-10-25"):
    return _officer_photo(name, "https://www.naag.org/wp-content/uploads/" + path, _NAAG_ROSTER,
                          _NAAG_BY, weight, evidence + " Read in a windowed Chrome on 2026-10-20"
                          " and again on " + checked + ", the same file, bytes and size both "
                          "times; naag.org challenges a script.", checked)


OFFICER_PHOTOS = {
    ("AZ", "sos"): _officer_photo(
        "Adrian Fontes", _NASS + "2024-07/AZ.jpg?itok=-XCD586X", "https://www.nass.org/membership",
        _NASS_BY, (24106, 355, 450), _NASS_CARD.format(
            "Adrian Fontes", "AZ.jpg", "July 2024", "January 2023",
            "azsos.gov refuses a script (HTTP 403).")),
    ("MN", "sos"): _officer_photo(
        "Steve Simon", _NASS + "2024-07/MN.jpg?itok=eqzGnPsy", "https://www.nass.org/membership",
        _NASS_BY, (18126, 355, 450), _NASS_CARD.format(
            "Steve Simon", "MN.jpg", "July 2024", "January 2015",
            "sos.mn.gov answers a script with a bot check.")),
    ("VT", "sos"): _officer_photo(
        "Sarah Copeland Hanzas", _NASS + "2023-07/VT.jpg?itok=OT3AvScG",
        "https://www.nass.org/membership", _NASS_BY, (23856, 355, 450), _NASS_CARD.format(
            "Sarah Copeland Hanzas", "VT.jpg", "July 2023", "January 2023",
            "sos.vermont.gov shows no photograph of her a script can find.")),
    ("MS", "sos"): _officer_photo(
        "Michael Watson", _NASS + "2022-07/MS.jpg?itok=3rNYOJpS", "https://www.nass.org/membership",
        _NASS_BY, (22287, 355, 450), _NASS_CARD.format(
            "Michael Watson", "MS.jpg", "July 2022", "January 2020",
            "The same man as the office's own headshot on sos.ms.gov/about-us/biography, which is "
            "2.9 MB.")),
    ("NY", "sos"): _officer_photo(
        "Walter Mosley", _NASS + "2024-06/NY.jpg?itok=Jors_L6r", "https://www.nass.org/membership",
        _NASS_BY, (17599, 355, 450),
        "NASS's roster card names Walter Mosley beside this photograph, filed as NY.jpg in June "
        "2024; a head-and-shoulders portrait, the same photograph as the department's own "
        "'Walter T. Mosley Headshot' on dos.ny.gov/about-our-executive-team. dos.ny.gov answers "
        "a script and a headless browser with a Cloudflare challenge, so a reader's browser may "
        "be refused it too: NASS's copy is linked."),
    ("SD", "sos"): _officer_photo(
        "Monae Johnson",
        "https://sdsos.gov/general-information/assets/Secretary%20Johnson_Pic2024.5.jpg",
        "https://sdsos.gov/about-the-office/about-secretary-johnson.aspx",
        "South Dakota Secretary of State", (16591, 310, 431),
        "The office's 'About Secretary Johnson' page; the same photograph as NASS's card for "
        "South Dakota."),
    ("AR", "ag"): _naag_card(
        "Tim Griffin", "2022/11/ag-AG-Griffin-1-225x300.png", (105306, 225, 300),
        "NAAG's Find my AG card reads \"Tim Griffin Arkansas\" beside this photograph, the "
        "card's own 225x300 size (ag-AG-Griffin-1-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("DE", "ag"): _naag_card(
        "Kathy Jennings", "2020/09/ag-DE-jennings-225x300.jpg", (11201, 225, 300),
        "NAAG's Find my AG card reads \"Kathy Jennings Delaware\" beside this photograph, the "
        "card's own 225x300 size (ag-DE-jennings-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("FL", "ag"): _naag_card(
        "James Uthmeier", "2025/01/ag-FL-Uthmeier-James-225x300.png", (32592, 225, 300),
        "NAAG's Find my AG card reads \"James Uthmeier Florida\" beside this photograph, the "
        "card's own 225x300 size (ag-FL-Uthmeier-James-225x300.png, uploaded 2025-01); a "
        "single head-and-shoulders portrait."),
    ("IA", "ag"): _naag_card(
        "Brenna Bird", "2022/11/ag-IA-Bird-225x300.png", (95965, 225, 300),
        "NAAG's Find my AG card reads \"Brenna Bird Iowa\" beside this photograph, the card's "
        "own 225x300 size (ag-IA-Bird-225x300.png, uploaded 2022-11); a single head-and-"
        "shoulders portrait."),
    ("ID", "ag"): _naag_card(
        "Raúl Labrador", "2022/11/ag-ID-Labrador-225x300.png", (102503, 225, 300),
        "NAAG's Find my AG card reads \"Raúl Labrador Idaho\" beside this photograph, the "
        "card's own 225x300 size (ag-ID-Labrador-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("IL", "ag"): _naag_card(
        "Kwame Raoul", "2020/09/ag-IL-raoul-2-225x300.jpg", (10604, 225, 300),
        "NAAG's Find my AG card reads \"Kwame Raoul Illinois\" beside this photograph, the "
        "card's own 225x300 size (ag-IL-raoul-2-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("KS", "ag"): _naag_card(
        "Kris Kobach", "2022/11/ag-KS-Kobach-225x300.png", (30604, 225, 300),
        "NAAG's Find my AG card reads \"Kris Kobach Kansas\" beside this photograph, the card's"
        " own 225x300 size (ag-KS-Kobach-225x300.png, uploaded 2022-11); a single head-and-"
        "shoulders portrait."),
    ("ME", "ag"): _naag_card(
        "Aaron Frey", "2020/09/ag-ME-Frey-Aaron-2025-225x300.png", (20774, 225, 300),
        "NAAG's Find my AG card reads \"Aaron Frey Maine\" beside this photograph, the card's "
        "own 225x300 size (ag-ME-Frey-Aaron-2025-225x300.png, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("MS", "ag"): _naag_card(
        "Lynn Fitch", "2020/09/ag-MS-Fitch-2024-225x300.jpg", (17333, 225, 300),
        "NAAG's Find my AG card reads \"Lynn Fitch Mississippi\" beside this photograph, the "
        "card's own 225x300 size (ag-MS-Fitch-2024-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("NC", "ag"): _naag_card(
        "Jeff Jackson", "2025/01/ag-NC-Jackson-Jeff-2025-225x300.png", (24212, 225, 300),
        "NAAG's Find my AG card reads \"Jeff Jackson North Carolina\" beside this photograph, "
        "the card's own 225x300 size (ag-NC-Jackson-Jeff-2025-225x300.png, uploaded 2025-01);"
        " a single head-and-shoulders portrait."),
    ("NE", "ag"): _naag_card(
        "Mike Hilgers", "2022/11/Mike-Hilgers-AG-600px-headshot-300x298.png", (26792, 300, 298),
        "NAAG's Find my AG card reads \"Mike Hilgers Nebraska\" beside this photograph, the "
        "card's own 300x298 size (Mike-Hilgers-AG-600px-headshot-300x298.png, uploaded "
        "2022-11); a single head-and-shoulders portrait."),
    ("NY", "ag"): _naag_card(
        "Letitia James", "2020/09/ag-NY-james2-225x300.jpg", (7901, 225, 300),
        "NAAG's Find my AG card reads \"Letitia A. James New York\" beside this photograph, the"
        " card's own 225x300 size (ag-NY-james2-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait. The card's 'Letitia A. James' is the office's 'Letitia "
        "James' with her middle initial."),
    ("OK", "ag"): _naag_card(
        "Gentner Drummond", "2022/11/ag-OK-Drummond-225x300.png", (118321, 225, 300),
        "NAAG's Find my AG card reads \"Gentner Drummond Oklahoma\" beside this photograph, the"
        " card's own 225x300 size (ag-OK-Drummond-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("SC", "ag"): _naag_card(
        "Alan Wilson", "2020/09/ag-SC-Wilson_new-225x300.jpg", (6382, 225, 300),
        "NAAG's Find my AG card reads \"Alan Wilson South Carolina\" beside this photograph, "
        "the card's own 225x300 size (ag-SC-Wilson_new-225x300.jpg, uploaded 2020-09); a "
        "single head-and-shoulders portrait."),
    ("UT", "ag"): _naag_card(
        "Derek Brown", "2025/01/ag-UT-Brown-Derek-225x300.png", (30412, 225, 300),
        "NAAG's Find my AG card reads \"Derek Brown Utah\" beside this photograph, the card's "
        "own 225x300 size (ag-UT-Brown-Derek-225x300.png, uploaded 2025-01); a single head-"
        "and-shoulders portrait."),
    ("VA", "ag"): _naag_card(
        "Jay Jones", "2026/01/ag-VA-jones-jay-225x300.png", (31065, 225, 300),
        "NAAG's Find my AG card reads \"Jay Jones Virginia\" beside this photograph, the card's"
        " own 225x300 size (ag-VA-jones-jay-225x300.png, uploaded 2026-01); a single head-"
        "and-shoulders portrait."),
    ("WA", "ag"): _naag_card(
        "Nick Brown", "2025/01/ag-WA-Brown-Nick-225x300.png", (19311, 225, 300),
        "NAAG's Find my AG card reads \"Nick Brown Washington\" beside this photograph, the "
        "card's own 225x300 size (ag-WA-Brown-Nick-225x300.png, uploaded 2025-01); a single "
        "head-and-shoulders portrait."),
    ("WI", "ag"): _naag_card(
        "Josh Kaul", "2020/09/ag-WI-kaul-225x300.jpg", (8850, 225, 300),
        "NAAG's Find my AG card reads \"Josh Kaul Wisconsin\" beside this photograph, the "
        "card's own 225x300 size (ag-WI-kaul-225x300.jpg, uploaded 2020-09); a single head-"
        "and-shoulders portrait."),
    ("WY", "ag"): _naag_card(
        "Keith Kautz", "2025/07/ag-WY-Kautz-Keith-2025-225x300.png", (29024, 225, 300),
        "NAAG's Find my AG card reads \"Keith Kautz Wyoming\" beside this photograph, the "
        "card's own 225x300 size (ag-WY-Kautz-Keith-2025-225x300.png, uploaded 2025-07); a "
        "single head-and-shoulders portrait."),
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
    # From the 2026-10-17 reader audit, each confirmed that day at 1.1.1.1
    # and 8.8.8.8 and fetched again by hand.
    "trevordforme.com": ("hijacked", "2026-10-17",
                         "www and bare 302 to ww38.trevordforme.com on a parking network "
                         "(103.224.212.210); one browser was sent to a 'Security Check' "
                         "software download, another saw 'This domain may be for sale'"),
    "rickwallenforcongress.com": ("hijacked", "2026-10-17",
                                  "301 to www.leopard-outpost.com, an unrelated domain that "
                                  "does not exist in DNS (NXDOMAIN at both resolvers)"),
    "zabelforcongress.com": ("dead", "2026-10-17", "www and bare NXDOMAIN at two resolvers"),
    "johnmcbride4congress.com": ("dead", "2026-10-17",
                                 "www and bare SERVFAIL at two resolvers: nobody can reach it"),
    "drkednermaximeforcongress.com": ("dead", "2026-10-17",
                                      "the domain is registered but neither www nor bare has "
                                      "an address record at two resolvers"),
    "gordonchaffin.com": ("unrelated", "2026-10-17",
                          "'High Skill Dog Care', a business page; nothing about a campaign"),
}

# Local governments' websites, as the Census Bureau's 2022 listing gives them,
# that must not be linked, keyed on the host (lower case; a key without
# "www." also covers the "www." form). `localgov --check-sites` withdraws
# what it finds on its own (data/local_sites.json, kyc/localsites.py); an
# entry here is a person's look, which no later check undoes - the kind is
# one of the check's verdicts. Each was opened in headless Chrome on
# 2026-10-17 by the reader-side audit and again by its verifier (LINKS-07,
# TRUST-07). The build warns about an entry no listed address matches.
BLOCKED_LOCAL_HOSTS = {
    "clintonct.com": ("gambling", "2026-10-17",
                      "Town of Clinton, CT: redirects to id-pgdemoslot.com, 'Demo Slot'"),
    "corralesnm.org": ("gambling", "2026-10-17",
                       "Village of Corrales, NM: redirects to a 'Salju4d: Link Slot' page"),
    "alvaok.org": ("gambling", "2026-10-17", "City of Alva, OK: a 'Sweepstakes Casinos' page"),
    "mcgrathalaska.net": ("gambling", "2026-10-17",
                          "City of McGrath, AK: redirects through two domains to laskar138, 'SLOT88'"),
    "vermilionparishpolicejury.com": ("gambling", "2026-10-17",
                                      "Parish of Vermilion, LA: an 'SBOBET88 ... Judi Bola' page"),
    "haccga.com": ("gambling", "2026-10-17",
                   "Clayton County Housing Authority, GA: redirects to qh88, a betting site"),
    "bismarck.org": ("parked", "2026-10-17", "City of Bismarck, ND: an empty Sedo-parked page"),
    "rutlandcity.com": ("expired", "2026-10-17",
                        "City of Rutland, VT: 'This domain is expired'; a parking page of links"),
    "northcodorustwp.com": ("for-sale", "2026-10-17",
                            "Township of North Codorus, PA: a HugeDomains for-sale page"),
    "imperialne.com": ("for-sale", "2026-10-17", "City of Imperial, NE: a HugeDomains for-sale page"),
    "switzerlandcounty.com": ("for-sale", "2026-10-17",
                              "County of Switzerland, IN: redirects to forsale.godaddy.com"),
    "townofprovidencevillage.com": ("parked", "2026-10-17",
                                    "Town of Providence Village, TX: a script sends visitors to "
                                    "/lander, a registrar's parking page"),
    # Gambling seen in one passage of the page's text, which the check
    # leaves for a person (localsites.STICKY); each looked at on 2026-10-18
    # and its title or visible text read.
    "ci.yorba-linda.ca.us": ("gambling", "2026-10-18",
                             "City of Yorba Linda, CA: titled 'Bundaslot', Indonesian text offering "
                             "'Kasino Live & Dealer Togel' and a 'Sportsbook'"),
    "cityofpevely.org": ("gambling", "2026-10-18",
                         "City of Pevely, MO: titled 'MANTIS88: inovasi baru! kapten game online', "
                         "a product card reading 'Material: Slot Gacor'"),
    "kennedale.net": ("gambling", "2026-10-18",
                      "Kennedale ISD, TX: titled 'ZUMA78: Daftar sekarang', a login for 'RTP Slot'"),
    "mooresvillealabama.com": ("gambling", "2026-10-18",
                               "Town of Mooresville, AL: Indonesian text inserted in the page about "
                               "'platform togel online'"),
    "simontontexas.org": ("gambling", "2026-10-18",
                          "City of Simonton, TX: posts headed 'Slot Naga Mahjong: Sensasi Bermain "
                          "Game Slot Online'"),
    "whitehallcitygov.com": ("gambling", "2026-10-18",
                             "City of White Hall, IL: titled 'tiger227 ini sebuah permainan games "
                             "online', 'Min Depo 20.000 ... Maxwin'"),
}

# A member's contact-form address that congress-legislators holds in a form
# no browser can open, keyed on bioguide id: {bioguide: (the source's value,
# the address used instead, evidence)}. Applied only while the source still
# holds exactly that value; validate reports an entry that no longer matches.
MEMBER_CONTACT_FORMS = {
    "F000484": ("hhttps://fine.house.gov/address_authentication?form=/contact/email-me",
                "https://fine.house.gov/contact/",
                "2026-10-17: the scheme 'hhttps' is a typo upstream, and the address "
                "with it corrected answers HTTP 404; the office's contact page answers 200"),
}

# YouTube names in congress-legislators that are neither a channel id (UC...)
# nor an @handle: legacy usernames, which youtube.com/user/<name> served.
# Most no longer do. Each was fetched on 2026-10-17, both as /user/<name>
# and as /@<name>, and an @handle kept only where its channel's own title
# names the member: {bioguide: (the source's value, "user" | "handle" |
# None, what was seen)}. None drops the link: neither form exists, or the
# value is not a name at all. validate lists any legacy name not here.
YOUTUBE_LEGACY_NAMES = {
    "A000148": ("RepAuchincloss", "handle", "/user/ 404; /@ is 'Rep. Auchincloss'"),
    "B001301": ("RepJackBergman", None, "/user/ and /@ both 404"),
    "B001318": ("YouTubeChannelID", None, "placeholder text upstream, not a channel"),
    "C001055": ("RepEdCase", "handle", "/user/ 404; /@ is 'Congressman Ed Case'"),
    "C001112": ("repcarbajal", "handle", "/user/ 404; /@ is 'Congressman Salud Carbajal'"),
    "C001115": ("RepCloudTX", "handle", "/user/ 404; /@ is 'Rep. Michael Cloud'"),
    "E000294": ("RepTomEmmer", "handle", "/user/ 404; /@ is 'Rep. Tom Emmer'"),
    "F000246": ("RepPatFallon", "handle", "/user/ 404; /@ is 'Rep. Pat Fallon'"),
    "K000377": ("SenMarkKelly", "handle", "/user/ 404; /@ is 'Senator Mark Kelly'"),
    "M001199": ("repbrianmast", "handle", "/user/ 404; /@ is 'Congressman Brian Mast'"),
    "R000609": ("Reprutherfordfl", "handle", "/user/ 404; /@ is 'Rep. John H. Rutherford'"),
    "R000610": ("RepGuyReschenthaler", None, "/user/ and /@ both 404"),
    "S001150": ("adamschiff", "user", "/user/ is 'Sen. Adam Schiff'; /@ 404"),
    "S001190": ("RepBradSchneider", "user", "/user/ is 'Rep. Brad Schneider'"),
    "S001200": ("repdarrensoto", "handle", "/user/ 404; /@ is 'Rep. Darren Soto'"),
    "W000790": ("senatorwarnock", "handle",
                "/user/ 404; /@ is 'Senator Reverend Raphael Warnock'"),
}

# YouTube @handles in congress-legislators that YouTube answers 404 for,
# with the handle the member's own House or Senate site links instead (None
# drops the link when the office links none). {bioguide: (the source's
# value, the handle the office links or None, date, what was seen)}. Applied
# only while the source holds exactly that value; validate reports an entry
# the source has moved past.
YOUTUBE_HANDLE_CORRECTIONS = {
    "H001100": ("@RepJeffHurd03", "@RepJeffHurd", "2026-10-17",
                "youtube.com/@RepJeffHurd03 answers 404; hurd.house.gov links "
                "youtube.com/@RepJeffHurd, which answers 200 with his floor speeches"),
}

# X handles in congress-legislators that X answers "User Profile Not Found"
# for, where the file holds no twitter_id to link the account by instead
# (an id follows a rename: x.com/i/user/827279765287559171 is Speaker
# Johnson's, 307 to SpeakerJohnson, where his RepMikeJohnson is 404).
# {bioguide: (the handle, date, what was seen)}. The handle is dropped while
# the source still holds exactly it with no id; validate reports an entry
# that no longer matches.
DEAD_X_HANDLES = {
    "M001219": ("JMoylanforGuam", "2026-10-17",
                "x.com/JMoylanforGuam answers 404 'User Profile Not Found', as a "
                "nonsense handle does, while x.com/SpeakerJohnson answers 200; "
                "congress-legislators lists no twitter_id for him"),
}

# A ballot page's link that redirects to the person's own article under a
# title without their surname (rule 33). Without an entry here such a link is
# withheld: "any living person's article" would also let a redirect to a
# spouse or a namesake through, and its infobox be quoted onto this profile.
# {profile id: (the title the link must land on, date, evidence)}.
ARTICLE_UNDER_ANOTHER_NAME = {
    "FEC_H4FL20098": ("Uncle Luke", "2026-10-17",
                      "FL-20's 2026 election page links 'Luther Campbell', which redirects to "
                      "'Uncle Luke'; that article (Q3267867) opens 'Luther Roderick Campbell "
                      "(born December 22, 1960), also known by his stage names Luke or "
                      "Uncle Luke'"),
}


def article_alias(profile_id):
    """The title a ballot link is known to land on for this profile, or None."""
    entry = ARTICLE_UNDER_ANOTHER_NAME.get(profile_id)
    return entry[0] if entry else None


# A portrait a person looked at on a campaign's own page, which the reader's
# words test cannot take (rule 38), keyed on the profile id: {"url": the file
# the page draws, "page", "read": the day it was looked at, "evidence": what
# the page says beside it}. The reader still takes it only from that
# campaign's site read as theirs (rules 38, 39), only while the page draws
# that very file, and only portrait-shaped; one over the caps is shown all
# the same, lighter where it can be (rule 87); validate reports an entry no
# read site offers.
# The 2026-10-19 photo research's check found two genuine likenesses refused:
# Brian James Miller's, whose alt text runs his names together
# ("BrianMiller-5.jpg"), which the reader now reads, and Justin Murphy's,
# whose alt text names the campaign ("for senate") as a wordmark's does.
CAMPAIGN_PORTRAITS = {
    "CAND_40": {
        "url": "https://jerseyjustin4senate.org/wp-content/uploads/2024/02/D70_8732-Web-684x1024.webp",
        "page": "https://jerseyjustin4senate.org/",
        "read": "2026-10-25",
        "evidence": "alt text \"justin murphy for senate\" on the campaign's home page; one man in "
                    "a suit, 684x1024, 43 KB (looked at 2026-10-25)"},
}


# A Wikidata item's label that names a nominee by a nickname their profile
# and filing do not write (kyc/nominee_photos.py), keyed on the profile id:
# {"label": the label exactly as the item writes it, "evidence": where the
# person uses that name - their campaign's own site or ballot listing - and
# the day it was read}. Without one, "Drew Williams" is not "WILLIAMS, JOHN
# ANDREW": the label is all that ties an item to a person besides the id
# (rule 82), and a nickname table would let "Bob" stand for any Robert.
PORTRAIT_NAME_FORMS = {}


# An election office's guide that prints a candidate under a short form of
# the name their filing, profile or the office's list writes
# (kyc/guide_photos.py), keyed on (state, the guide's name exactly as
# printed): (the person it stands for - "person:<profile id>" or
# "candidate:<state>:<office>:<name shown>" - and the evidence tying the
# two, with the day it was read). Without one, a guide's name joins only
# where its words are the person's (rule 62): "David Russ" is not "RUSS,
# DAVID HONORABLE".
GUIDE_NAME_FORMS = {
    ("OR", "David Russ"): (
        "person:FEC_H2OR01240",
        "the State Voters' Pamphlet's statement for David Russ, Republican, US "
        "Representative, 6th District (VP_G26-Book12 page 35, read 2026-10-25), prints "
        "'RussIsForUS.com' and is 'furnished by David Russ Is For US'; the filing RUSS, DAVID "
        "HONORABLE (H2OR01240) names that site, russisforus.com, as its campaign's (FEC "
        "Form 1)"),
}


# Images that a route would take as a person's portrait but that are not one,
# keyed on the image URL: (date checked, what it shows). One list for every
# route (rule 38): a campaign's own site (`enrich`), a nominee's Wikidata item
# or legislature card (nominee_photos), an attorney general's office
# (officers.add_ag_photos), a court's page (court_photos), a statewide
# candidate's guide or Commons file (statewide_photos, keyed on the Commons
# upload address), a judge's Commons file (judge_links); every route asks it,
# of a record kept from an earlier read as well as of one read now. The
# rules turn away logos, share cards, merchandise and most group shots by
# file name and shape; these passed both, and only a look tells. The
# refreshes re-read every source, so a correction made by editing a cache
# would not last. validate reports an entry no cached route offers.
#
# One test for every image a person looks at (rule 38, the review of PR
# #134): a photograph of the candidate alone - nobody else in the frame, even
# in the background or in part (the owner, 2026-10-25: "probably better to
# leave out background people") - whose face, brow to chin, is at
# least a tenth of the height of the 4:5 card that crops it from the top -
# 6.5px of the state pages' 65px phone card, where eyes and a mouth can be
# made out - is a likeness and is shown ("more content", the owner's
# decision of 2026-10-25). Anything else is here, with what was seen and
# measured: another person in the frame, a scene, a full-length figure.
# Measured on 2026-10-25, Brian Bengs's park photograph (a seventh and a
# half) and Jena Nelson's street portrait (a ninth) pass; Jamie Davis by his
# tractor (an eleventh), Lauren Jewett by a seal (a fifteenth) and Jordan
# Herrera in a vehicle's hatch (a thirteenth) do not.
NOT_A_PORTRAIT = {
    "https://kaileebuller.com/wp-content/uploads/2026/03/Buller.jpg":
        ("2026-10-02", "a family photograph: four people in the snow"),
    "https://rickbrattin.com/wp-content/uploads/2026/02/Brattin-extended-scaled.png":
        ("2026-10-02", "a hunting scene; no face at card size"),
    "https://run.imgix.net/f9df0b31-2ce0-4b8a-9a5d-4765b3afb86b/ab4b5c88-afea-4c83-9eb7-311e7cead6a6/ab4b5c88-afea-4c83-9eb7-311e7cead6a6.jpg?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C777%2C3648%2C3648&auto=compress%2Cformat&fit=fillmax&w=2048&q=75&s=cb469615bb857ebbc21f8c8780cda69b":
        ("2026-10-25", "Elizabeth Lee: a rally - speaking through a megaphone, other people "
                       "behind her"),
    "https://run.imgix.net/744b9e51-6fcd-4260-a2b5-35da9e4ad0b4/19462903-8b50-4a50-9e43-b99bb2febeed/19462903-8b50-4a50-9e43-b99bb2febeed.jpg?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C0%2C4024%2C6048&auto=compress%2Cformat&fit=fillmax&w=2048&q=75&s=0c9c30e09b5531bbdff48c00dd0dfda7":
        ("2026-10-25", "Michaela Barnett: a festival stall - holding up a T-shirt under a county "
                       "party's banner, another person behind her and one seated"),
    "https://shaunfinnieforcongress.com/wp-content/uploads/2026/05/Selme-Finnie-img.jpg":
        ("2026-10-25", "two people: Shaun Finnie with someone else ('Selme-Finnie')"),
    "https://jordanjherrera.com/wp-content/uploads/2025/05/Jordan_Herrera_IMG_9126-768x1024.jpeg":
        ("2026-10-25", "Jordan Herrera: seated in a military vehicle's hatch, his face a "
                       "thirteenth of the card's height"),
    # Found once heavy portraits were shown again (PR #134 review), and looked at.
    "https://samgallucci.com/assets/samfamily-BetoMA7c.webp":
        ("2026-10-25", "Sam Gallucci: a family photograph, seventeen people on a beach"),
    "https://irp.cdn-website.com/a2163ddd/dms3rep/multi/opt/MCGOWAN-BIO-1406h.png":
        ("2026-10-25", "Chris McGowan: a page of biography text under the campaign's logo"),
    "https://assets.nationbuilder.com/themes/69d46ee99be3286671f3d5a8/attachments/original/1776836856/11089a203ea7bb260717a77ab963cb40942791be.png?1776836856":
        ("2026-10-25", "Greg Stoker: a halftone street scene, several people holding signs"),
    # Judged by the one test above (the review of PR #134).
    "https://jamieforlouisiana.com/assets/general/tractor-portrait.jpg":
        ("2026-10-25", "Jamie Davis: a full-length figure leaning on a tractor, his face an "
                       "eleventh of the card's height"),
    "https://laurenjewett.com/images/campaign/lauren-jewett-jefferson.png":
        ("2026-10-25", "Lauren Jewett: a full-length figure beside the Clerk of Court's seal, her "
                       "face a fifteenth of the card's height"),
    # The owner, 2026-10-25: "probably better to leave out background people".
    # Every photograph shown by the routes the owner's brief named that can
    # take a picture not made in a studio was looked at on 2026-10-25 (701
    # of them; not the judges' item route, CLAUDE.md rule 38); these show
    # someone else, in the background or in part. Keyed as each route asks: a
    # campaign's or an office's file by its address, a Commons file by its
    # upload address.
    # a campaign's own site (enrich): 1.
    "https://raw.githubusercontent.com/dpconway4-bot/pat-moore-for-congress/main/assets/pat-moore-headshot.jpg":
        ("2026-10-25", "Patricia Ann Moore (LA): the House chamber behind her, with members seated"),
    # the article a profile's bioguide id or ballot page links (portraits): 33.
    "https://upload.wikimedia.org/wikipedia/commons/7/7e/Adam_Hollier_at_Whitmer's_inauguration_(January_1,_2023)_(cropped).jpg":
        ("2026-10-25", "Adam Hollier (MI): a person standing by the tents at the right"),
    "https://upload.wikimedia.org/wikipedia/commons/7/79/2025_Virginia_State_of_the_Commonwealth,_Youngkin_procession_(cropped).jpg":
        ("2026-10-25", "Adele McClure (VA): people behind her"),
    "https://upload.wikimedia.org/wikipedia/commons/0/09/Adrian_Boafo_Feb2023.jpg":
        ("2026-10-25", "Adrian Boafo (MD): another person's arm raised at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6a/Amy_McGrath_Event-_(49220643717)_1.jpg":
        ("2026-10-25", "Amy McGrath (KY): another person's hair at the left edge"),
    "https://upload.wikimedia.org/wikipedia/commons/2/26/Brad_Lander.jpg":
        ("2026-10-25", "Brad Lander (NY): a person behind him at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/d/d8/Brent_Taylor_(Tennessee_politician).jpg":
        ("2026-10-25", "Brent Taylor (TN): people at the stalls behind him at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/8/82/Cameron_Kasky_3.jpg":
        ("2026-10-25", "Cameron Kasky (NY): a crowd around him"),
    "https://upload.wikimedia.org/wikipedia/commons/0/0f/Chris_Stigall_2017_(cropped).jpg":
        ("2026-10-25", "Chris Stigall (MO): people behind him at the left, one with a camera"),
    "https://upload.wikimedia.org/wikipedia/commons/9/92/Dale_Romans.jpg":
        ("2026-10-25", "Dale Romans (KY): people on the track behind him"),
    "https://upload.wikimedia.org/wikipedia/commons/e/e0/Emanuel_Jones_(46948866015).jpg":
        ("2026-10-25", "Emanuel Jones (GA): people in purple shirts behind him"),
    "https://upload.wikimedia.org/wikipedia/commons/9/90/Heather_Keeler_at_DFL_post-Roe_Agenda_Press_Conference_(cropped).jpg":
        ("2026-10-25", "Heather Keeler (MN): another person's hair at the foot of the frame"),
    "https://upload.wikimedia.org/wikipedia/commons/7/74/JD_Ford,_Indy_Pride_Parade_2023_(2)_(cropped).jpg":
        ("2026-10-25", "J.D. Ford (IN): a crowd at a parade around him"),
    "https://upload.wikimedia.org/wikipedia/commons/7/70/James_Talarico_Press_Conference_(cropped).jpg":
        ("2026-10-25", "James Talarico (TX): a person at the right edge"),
    "https://upload.wikimedia.org/wikipedia/commons/0/0f/Jay_Feely_by_Gage_Skidmore.jpg":
        ("2026-10-25", "Jay Feely (AZ): audience heads at the foot of the frame"),
    "https://upload.wikimedia.org/wikipedia/commons/2/22/Michigan_Senator_Jeremy_Moss_2019.jpg":
        ("2026-10-25", "Jeremy Moss (MI): people behind him in the room"),
    "https://upload.wikimedia.org/wikipedia/commons/8/8c/JillianGilchrestFebruary2026Cropped.jpg":
        ("2026-10-25", "Jillian Gilchrest (CT): people standing behind her in the chamber"),
    "https://upload.wikimedia.org/wikipedia/commons/6/60/Colorado_State_Senator_Julie_Gonzales_2025_(cropped).jpg":
        ("2026-10-25", "Julie Gonzales (CO): a person standing in the chamber behind her, right"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f3/Julie_Won_(54199169237)_(cropped).jpg":
        ("2026-10-25", "Julie Jaehee Won (NY): a man standing behind her"),
    "https://upload.wikimedia.org/wikipedia/commons/2/23/Justin_J_Pearson_August_2023.jpg":
        ("2026-10-25", "Justin J. Pearson (TN): a man's shoulder behind him at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/0/06/Ken_Paxton_(54816860552)_(cropped).jpg":
        ("2026-10-25", "Ken Paxton (TX): a crowd behind him"),
    "https://upload.wikimedia.org/wikipedia/commons/a/a3/La_Shawn_K._Ford_on_11_December_2023_-_8_(cropped).jpg":
        ("2026-10-25", "La Shawn K Ford (IL): people standing behind him, a woman's hand on his "
                       "shoulder"),
    "https://upload.wikimedia.org/wikipedia/commons/c/ca/Luke_Bronin_(42831415392).jpg":
        ("2026-10-25", "Luke Bronin (CT): a man in a blue shirt behind him, left"),
    "https://upload.wikimedia.org/wikipedia/commons/4/47/Mallory_McMorrow_in_2023_-_8R4A5252_(cropped).jpg":
        ("2026-10-25", "Mallory McMorrow (MI): a person in blue behind her at the top left"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f2/Mark_Teixeira_basepaths_2011.jpg":
        ("2026-10-25", "Mark Charles Teixeira (TX): spectators in the stands behind him"),
    "https://upload.wikimedia.org/wikipedia/commons/e/ec/Matt_Strickler,_ribbon_cutting.jpg":
        ("2026-10-25", "Matt Strickler (VA): another person's shoulder at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/3/35/Mike_LiPetri_(2024_Italian_Heritage_Street_Festival)_(cropped).jpg":
        ("2026-10-25", "Mike Lipetri (NY): people behind him at the foot of the frame"),
    "https://upload.wikimedia.org/wikipedia/commons/0/06/William_V_Bill_Bell_Way_Dedication_Ceremony_Nida_Allam.jpg":
        ("2026-10-25", "Nida Allam (NC): people behind her at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/b/bf/Phil_Lyman_at_Riley_Gaines_Speech_(cropped).jpg":
        ("2026-10-25", "Phil Lyman (UT): another person at the right edge"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6d/Unveiling_the_NYS_Historic_Marker_Robert_Smullen.jpg":
        ("2026-10-25", "Robert Smullen (NY): another man's shoulder at the right"),
    "https://upload.wikimedia.org/wikipedia/commons/0/09/Robin_Ficker_(35598540490).jpg":
        ("2026-10-25", "Robin Ficker (MD): another man's shoulder at the left, and a person behind"),
    "https://upload.wikimedia.org/wikipedia/commons/b/b3/Rushern_Baker,_May_2017.jpg":
        ("2026-10-25", "Rushern L Baker III (MD): a man behind him at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/e/ea/Sharif_Street_-_18901_gov_minwage_dz_030_(cropped).jpg":
        ("2026-10-25", "Sharif Street (PA): a white-haired man behind him at the left"),
    "https://upload.wikimedia.org/wikipedia/commons/0/00/(03-12-24)_Taylor_Darling.jpg":
        ("2026-10-25", "Taylor R Darling (NY): people in white shirts behind her"),
    # a statewide candidate's guide or Commons file (statewide_photos): 5.
    "https://www.azcleanelections.gov/Custom/Picture/2469":
        ("2026-10-25", "Duwayne Collier (AZ secretary of state candidate): a child's face and "
                       "another person's arm (the Clean Elections guide photograph, cropped from a "
                       "family snapshot)"),
    "https://upload.wikimedia.org/wikipedia/commons/7/7d/Heather_Baxter_by_Gage_Skidmore.jpg":
        ("2026-10-25", "Heather Baxter (SD secretary of state candidate): a person seated behind her "
                       "at the right"),
    "https://www.azcleanelections.gov/Custom/Picture/2640":
        ("2026-10-25", "John Giles (AZ lieutenant governor candidate): framed photographs of people "
                       "on the shelves behind him"),
    "https://upload.wikimedia.org/wikipedia/commons/2/23/Mayes_Middleton_by_Gage_Skidmore_(cropped).jpg":
        ("2026-10-25", "Mayes Middleton (TX attorney general candidate): people behind him at the "
                       "left and right"),
    "https://www.nass.org/sites/default/files/styles/secretary/public/2023-03/MA-Galvin-2023.jpg?itok=7JV1GBsz":
        ("2026-10-25", "William Francis Galvin (MA secretary of state candidate): people walking on "
                       "the path behind him"),
    # an attorney general's office (officers.add_ag_photos): 1.
    "https://i0.wp.com/www.attorneygeneral.gov/wp-content/uploads/sunday-in-office-image-scaled.jpg?w=500&ssl=1":
        ("2026-10-25", "Dave Sunday (PA attorney general): a framed snapshot of people on the "
                       "bookcase at the left"),
    # a judge's Commons crop of a hearing still (judge_links, route 'crop'): 9.
    "https://upload.wikimedia.org/wikipedia/commons/d/d4/Ann_Donnelly_(cropped).jpg":
        ("2026-10-25", "Judge Ann Donnelly (FJC 1394806): people seated behind her (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/b/bb/Jennifer_Rearden_(Judge)_(cropped).jpg":
        ("2026-10-25", "Judge Jennifer H. Rearden (FJC 12537146): a figure behind her at the right"),
    "https://upload.wikimedia.org/wikipedia/commons/b/bf/Katherine_Failla_(cropped).jpg":
        ("2026-10-25", "Judge Katherine Polk Failla (FJC 1394136): a person seated behind her at the "
                       "left (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/6/64/Landya_McCafferty_(cropped).jpg":
        ("2026-10-25", "Judge Landya B. McCafferty (FJC 1394326): people seated behind her (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/0/0a/Leigh_May_(cropped).jpg":
        ("2026-10-25", "Judge Leigh Martin May (FJC 1394641): people seated behind her at the left "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/1/16/Hannah_Lauck_(cropped).jpg":
        ("2026-10-25", "Judge M. Hannah Lauck (FJC 1394551): people seated behind her at the right "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/c/c4/Jose_Olvera_Jr_(cropped).jpg":
        ("2026-10-25", "Judge Rolando Olvera (FJC 1394786): a person seated behind him at the right "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/5/55/Stephanie_Davis_(Judge)_(cropped).jpg":
        ("2026-10-25", "Judge Stephanie D. Davis (FJC 7545481): people seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/b/b3/Tiffany_Cunningham_(cropped).jpg":
        ("2026-10-25", "Judge Tiffany P. Cunningham (FJC 10376611): a person in pink behind her"),
    # a judge's article's image (judge_links, route 'article'): 39.
    "https://upload.wikimedia.org/wikipedia/commons/5/5d/Aaron_C._Peterson.png":
        ("2026-10-25", "Judge Aaron C. Peterson (FJC 13762106): a grey-haired person seated behind "
                       "him at the left (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/0/07/Andrew_B._Davis.png":
        ("2026-10-25", "Judge Andrew B. Davis (FJC 13762122): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/5/5c/Angela_V._Colmenero.png":
        ("2026-10-25", "Judge Angela Colmenero (FJC 13762219): a person standing behind her (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/8/89/Anna_St._John.png":
        ("2026-10-25", "Judge Anna St. John (FJC 13762116): people seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/8/87/Anne-Leigh_Moe.png":
        ("2026-10-25", "Judge Anne-Leigh Gaylord Moe (FJC 13762067): people seated behind her (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/f/ff/Bill_W._Lewis.png":
        ("2026-10-25", "Judge Bill Lewis (FJC 13762071): a person in a patterned dress seated behind "
                       "him (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/d/d7/Brian_Lea.png":
        ("2026-10-25", "Judge Brian C. Lea (FJC 13762108): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/7/76/Byron_B._Conway-7-31-24.jpg":
        ("2026-10-25", "Judge Byron B. Conway (FJC 13761869): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/9/9e/Christopher_R._Wolfe.png":
        ("2026-10-25", "Judge Chris Wolfe (FJC 13762121): a person seated behind him at the right (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/a/ac/David_Steven_Morales_(Judge).jpg":
        ("2026-10-25", "Judge David S. Morales (FJC 6278461): a person seated behind him at the "
                       "right (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/d/df/Edward_L._Artau.png":
        ("2026-10-25", "Judge Ed Artau (FJC 13762047): people seated behind him (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/4/40/Embry_J_Kidd.png":
        ("2026-10-25", "Judge Embry Kidd (FJC 13761891): people seated behind him (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/e/e5/Eric_C._Schulte.png":
        ("2026-10-25", "Judge Eric Schulte (FJC 13761661): a person seated behind him at the right "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/8/8b/Fernando_Rodriguez_Jr._(Judge)_(cropped).jpg":
        ("2026-10-25", "Judge Fernando Rodriguez Jr. (FJC 4733056): a person seated behind him at "
                       "the right (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/4/42/Gail_A._Weilheimer-7-31-24.jpg":
        ("2026-10-25", "Judge Gail A. Weilheimer (FJC 13761902): a person seated behind her at the "
                       "left (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/3a/Harold_D._Mooty.png":
        ("2026-10-25", "Judge Harold Mooty (FJC 13762066): a person in red seated behind him (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6b/James_Maxwell.png":
        ("2026-10-25", "Judge James D. Maxwell II (FJC 13762095): a person seated behind him (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6a/Jeffrey_M._Kuhlman.png":
        ("2026-10-25", "Judge Jeffrey M. Kuhlman (FJC 13762129): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/7/7d/John_Thomas_Shepherd.png":
        ("2026-10-25", "Judge John T. Shepherd (FJC 13762120): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/9/9c/Jonathan_E._Hawley-7-31-24.jpg":
        ("2026-10-25", "Judge Jonathan E. Hawley (FJC 13761886): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f2/Joshua_M._Divine.png":
        ("2026-10-25", "Judge Josh Divine (FJC 13762033): a person seated behind him at the right (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/e/ee/Justin_Olson.png":
        ("2026-10-25", "Judge Justin R. Olson (FJC 13762109): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/38/Kara_M._Westercamp.png":
        ("2026-10-25", "Judge Kara Westercamp (FJC 13762146): people seated behind her at the right "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/a/a7/Kasdin_M._Mitchell.png":
        ("2026-10-25", "Judge Kasdin Mitchell (FJC 13762214): a person in a striped shirt behind her "
                       "(a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/8/87/Kathleen_S._Lane.png":
        ("2026-10-25", "Judge Katie Lane (FJC 13762128): a person seated behind her at the left (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/e/e5/Kyle_C._Dudek.png":
        ("2026-10-25", "Judge Kyle Dudek (FJC 13762049): people seated behind him (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/3e/Maria_Lanahan.png":
        ("2026-10-25", "Judge Maria Lanahan (FJC 13762048): a person seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/a/a1/Matthew_R._Byrne.png":
        ("2026-10-25", "Judge Matthew R. Byrne (FJC 13762157): a person standing behind him at the "
                       "right (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/b/b4/Matthew_A._Schwartz.png":
        ("2026-10-25", "Judge Matthew Schwartz (FJC 13762140): a person seated behind him at the "
                       "right (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/9/9c/Megan_Benton.png":
        ("2026-10-25", "Judge Megan Benton (FJC 13762107): people seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/1/1d/Michael_C._Martin.png":
        ("2026-10-25", "Judge Michael C. Martin (FJC 13762148): a person standing behind him (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/37/Robert_Chamberlin.png":
        ("2026-10-25", "Judge Robert P. Chamberlin (FJC 13762093): people seated behind him (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/34/Sanket_J._Bulsara.png":
        ("2026-10-25", "Judge Sanket J. Bulsara (FJC 13761656): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/3/3e/Sheria_Akins_Clarke.png":
        ("2026-10-25", "Judge Sheria Clarke (FJC 13762124): people seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/b/b1/Stephanos_Bibas.png":
        ("2026-10-25", "Judge Stephanos Bibas (FJC 3989731): people seated behind him (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f3/Susan_Courtwright_Rodriguez.png":
        ("2026-10-25", "Judge Susan C. Rodriguez (FJC 13762092): people seated behind her (a hearing "
                       "still)"),
    "https://upload.wikimedia.org/wikipedia/commons/a/a4/Thomas_Lee_R._Parker_(cropped).jpg":
        ("2026-10-25", "Judge Tommy Parker (FJC 4028131): a person seated behind him at the right (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/d/dc/Whitney_Hermandorfer.png":
        ("2026-10-25", "Judge Whitney Hermandorfer (FJC 13762030): people seated behind her (a "
                       "hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/2/24/Zack_Bluestone.png":
        ("2026-10-25", "Judge Zack Bluestone (FJC 13762035): a person in pink behind him (a hearing "
                       "still)"),
    # A legislator's card (Open States's file or the legislature's,
    # legislature.photo_kind): the 267 cards credited to a caucus were looked
    # at on 2026-10-25, when the owner allowed caucus credits; these two show
    # colleagues.
    "https://www2.housedems.ct.gov/Genga/images/Genga_HS.jpg":
        ("2026-10-25", "Henry Genga (CT House): at his desk in the chamber, Rep. Conway seated "
                       "behind him"),
    "https://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg":
        ("2026-10-25", "Gregg Haddad (CT House): at his desk in the chamber, two colleagues "
                       "beside and behind him"),
    # The PR #139 review, looked at again on 2026-10-25. A refusal promoted
    # James Talarico's campaign photograph, which nobody had looked at, in
    # place of his Commons one (validate's portrait-fallback-unseen now
    # names any such photograph); the sweep missed four more; and a framed
    # photograph of people on the wall counts as it did for John Giles and
    # Dave Sunday.
    "https://jamestalarico.com/wp-content/uploads/2025/09/james-talarico-texas-education-819x1024.webp":
        ("2026-10-25", "James Talarico (TX): bent over a desk helping a child in a classroom, "
                       "two more children in the frame, his face turned down"),
    # The uncut file the refused crop came from, which his Wikidata item
    # carries (nominee_photos' Wikidata route then offered it).
    "https://upload.wikimedia.org/wikipedia/commons/8/8b/James_Talarico_Press_Conference.jpg":
        ("2026-10-25", "James Talarico (TX): another person's shoulder at the right edge"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f0/JoCasta_Zamarripa_(51017746066).jpg":
        ("2026-10-25", "JoCasta Zamarripa (WI secretary of state candidate): another person's "
                       "hand and fingers at the left edge"),
    "https://upload.wikimedia.org/wikipedia/commons/a/aa/Matthew_E._Orso.png":
        ("2026-10-25", "Judge Matthew E. Orso (FJC 13762088): a standing person's legs and shoe "
                       "behind him at the upper right (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/f/f5/Anthony_J._Powell.png":
        ("2026-10-25", "Judge Anthony J. Powell (FJC 13762132): people in suits seated behind "
                       "him (a hearing still)"),
    "https://upload.wikimedia.org/wikipedia/commons/a/a1/Cook_County_Commissioner_Donna_Miller_at_May_Day_2025.jpg":
        ("2026-10-25", "Donna Miller (IL): a person's face on the screen behind her, at the "
                       "upper right"),
    "https://upload.wikimedia.org/wikipedia/commons/1/11/Adam_Hamawy_in_2025.jpg":
        ("2026-10-25", "Adam Hamawy (NJ): a framed photograph of people on the wall behind him"),
    # The same California National Guard photograph under its new name (the
    # old one answered 404 and was never looked at by the sweep), offered
    # again when her portrait was resolved anew.
    "https://upload.wikimedia.org/wikipedia/commons/6/62/Jacqui_Irwin_(cropped)_150302-Z-WQ610-_(16698067641).jpg":
        ("2026-10-25", "Jacqui V Irwin (CA): another woman seated at the right edge, and another "
                       "person's hair at the left"),
}

# Photographs that came forward when a person refused the one before them
# (NOT_A_PORTRAIT), from a route that can take a picture not made in a
# studio, each looked at and found to be of the person alone, keyed on the
# address shown: (date, what was seen). validate names any other such
# photograph (portrait-fallback-unseen) - a refusal must never put a
# photograph nobody has looked at in front of readers (the PR #139 review:
# James Talarico's classroom photograph).
SEEN_AFTER_A_REFUSAL = {
}

# Commons files a judge's route (kyc/judge_links.py) or a statewide
# candidate's (kyc/statewide_photos.py) reaches whose licence is in doubt,
# keyed on the upload URL: (date, what the file's page says).
# Each is withheld - and reported - until a person reads the file's page and
# decides; delete the entry to show it, or move it to NOT_A_PORTRAIT to
# refuse it for good.
#
# One test, applied to every portrait alike: Commons' licence tag stands
# unless the file's page or its name points to an author who is neither its
# uploader nor a government office - a studio's code, a university's credit,
# a private site's photograph guessed to be official - or the page names no
# author at all. A
# court's own photograph tagged PD-USGov-Judiciary (or PD-USGov, author the
# court) stands, as it does for the 491 court-credited portraits shown on
# 2026-10-19, and so does an uploader's {{own}} work with nothing on its page
# that says otherwise. The review of PR #127 found the first list doubting
# two D.C. court photographs (Mehta, Sooknanan), two {{own}} uploads
# (Arias-Marxuach, Carreno-Coll), a Southern District of Florida photograph
# (Marra, author the court, "work of the Federal Government") and the
# Supreme Court photographer's portrait of Justice Jackson
# ({{PD-USGov-SCOTUS}}) on grounds that every shown portrait of their kind
# would fail; those were dropped (read 2026-10-19).
PORTRAIT_LICENCE_DOUBTS = {
    "https://upload.wikimedia.org/wikipedia/commons/f/fc/Richard_C._Wesley_(cropped).jpg":
        ("2026-10-19", "CC BY-SA 4.0 on a photograph credited 'Photo courtesy of the "
                       "University of Albany', with no permission recorded"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6b/Higginbotham_Patrick_E.jpg":
        ("2026-10-19", "public domain on the uploader's reasoning that 'it must be his official "
                       "portrait'; taken from innsofcourt.org"),
    "https://upload.wikimedia.org/wikipedia/commons/7/7d/Rufe,_Hon_CynthiaVLF22561r_web2.jpg":
        ("2026-10-19", "'own work' by an uploader, of a file carrying a studio's code "
                       "(VLF22561r)"),
    "https://upload.wikimedia.org/wikipedia/commons/6/62/Header_NA_Yoon_US-Senate-Collection.jpg":
        ("2026-10-19", "public domain, from the Senate Press Gallery, author {{Unknown}}"),
    # Statewide candidates' (PR #135's review, 2026-10-25). The test above
    # finds Jolly's (no author) and Kobach's ("official portrait" under a
    # user's CC0) by itself (statewide_photos.licence_doubt); these three a
    # person must read.
    "https://upload.wikimedia.org/wikipedia/commons/8/89/Allen_Headshot_-_Pikes_Peak_background_(cropped).jpg":
        ("2026-10-25", "CC0 by the user account 'Koncurrentkat' on a studio-style headshot "
                       "against a backdrop ('Pikes Peak background'), with nothing on the page "
                       "showing the uploader took it"),
    "https://upload.wikimedia.org/wikipedia/commons/2/27/Ra%C3%BAl_Torrez_(cropped_2).jpg":
        ("2026-10-25", "CC0 by the user account 'LandofEnchantment Pics', with nothing on the "
                       "page showing the account took the photograph"),
    "https://upload.wikimedia.org/wikipedia/commons/9/94/Paul_Pate_(cropped).jpeg":
        ("2026-10-25", "'Copyrighted free use', author 'Iowa General Assembly', with no "
                       "permission or statute recorded behind the tag"),
}

# Each sitting justice's official portrait as Wikimedia Commons holds it,
# keyed on the FJC nid: (the Commons file, its author as the file's page
# names it, the day read, what shows it is the Court's own). The owner's
# decision of 2026-10-20: the Court's photographs page says its images "may
# not be reproduced for publication (print or web) without prior approval";
# the official portraits are its staff photographers' work, and Commons holds
# them, so a justice's portrait is taken from Commons, credited to its
# photographer, wherever this table names it. Commons holds the Court's
# official portraits, not always the ones it shows now: by each file's date,
# Roberts's is of 2005, Alito's 2006, Thomas's 2007, Sotomayor's 2009 (the
# Court's biographies page shows one of 2025), Kagan's 2010, Gorsuch's 2017,
# Kavanaugh's 2018, Barrett's 2021, Jackson's 2022 (read 2026-10-25; whether
# a newer public-domain copy should replace one is the owner's call). The
# judges' read (kyc/judge_links.py) takes this file for the justice, by the
# same checks as any judge's, and the federal pages show it only while
# Commons still names the author recorded here; otherwise the Court's own
# portrait stands, and the page says the read did not confirm the file.
# Sonia Sotomayor's Wikidata item's image is a 2009 White House photograph,
# not the Court's portrait, and Elena Kagan's is a 2013 upload of hers tagged
# CC BY-SA 3.0: each entry below names the Court's own portrait as Commons
# holds it, in the public domain (both read 2026-10-25).
_SCOTUS_STAFF = ("the Court's official portrait, by its staff photographer, as the Court's "
                 "Collection credits it")
JUSTICE_PORTRAITS = {
    "1391841": ("Official roberts CJ.jpg", "Steve Petteway", "2026-10-20",
                _SCOTUS_STAFF + "; the Chief Justice's official portrait"),
    "1388686": ("Clarence Thomas official SCOTUS portrait.jpg",
                "Steve Petteway, Collection of the Supreme Court of the United States",
                "2026-10-20", _SCOTUS_STAFF),
    "1377101": ("Justice Alito official.jpg", "Steve Petteway", "2026-10-20", _SCOTUS_STAFF),
    "1388091": ("Sonia Sotomayor in SCOTUS robe.jpg",
                "Collection of the Supreme Court of the United States, Steve Petteway",
                "2026-10-25", _SCOTUS_STAFF + "; public domain, its source Oyez; the item's "
                "image is a 2009 White House photograph by Stacey Ilyse"),
    "1393281": ("Elena Kagan official SCOTUS portrait.jpg",
                "Steve Petteway, Collection of the Supreme Court of the United States",
                "2026-10-25", _SCOTUS_STAFF + "; public domain, its source Oyez; the item's "
                "image, 'Elena Kagan Official SCOTUS Portrait (2013).jpg', is tagged CC BY-SA 3.0"),
    "1392461": ("Associate Justice Neil Gorsuch Official Portrait.jpg",
                "Franz Jantzen, Collection of the Supreme Court of the United States",
                "2026-10-20", _SCOTUS_STAFF),
    "1392406": ("Associate Justice Brett Kavanaugh Official Portrait.jpg",
                "The Collection of the Supreme Court of the United States", "2026-10-20",
                "the Court's official portrait, credited to the Court's Collection"),
    "3979311": ("Amy Coney Barrett official portrait.jpg", "United States Supreme Court",
                "2026-10-20", "the Court's official portrait, credited to the Court"),
    "1394151": ("Ketanji Brown Jackson official SCOTUS portrait.jpg",
                "Fred Schilling / United States Supreme Court", "2026-10-20", _SCOTUS_STAFF),
}

# A member's official issues page whose list `members` reads but that is not
# the page's list of issues, keyed on bioguide id: (date checked, the page
# read, what it shows). The rules take a page's links or one level of its
# headings in its words; a page that splits each title across two headings
# passes them and reads as fragments. The page is linked instead ("On their
# official site's issues page"). The refresh re-reads every site, so a
# correction made by editing the cache would not last; members.problems
# reports an entry whose page is no longer the one read.
OFFICIAL_ISSUES_NOT_A_LIST = {
    "L000575": ("2026-10-18", "https://www.lankford.senate.gov/issues/",
                "each title is split over two headings: 'Protecting' over 'Life, Liberty & "
                "Our Families', 'Bringing Down' over 'High Costs in Our Nation'"),
    # Read 2026-10-18 for the review of PR #106: the index lists the House
    # template's stock categories, each twice, beside categories that are
    # labels for constituent mail rather than positions - "PRO CHOICE",
    # "Pro Life", "PRO AG", "REDUCE TROOPS IN MIDDLE EAST PRO" - and one page
    # under two names ("11 Ideals for TX-11", "TX-11 Ideals"). As a platform
    # it would read as though a member who lists "Pro Life" held both views.
    "P000048": ("2026-10-18", "https://pfluger.house.gov/issues/",
                "mail categories ('PRO CHOICE', 'Pro Life', 'REDUCE TROOPS IN MIDDLE EAST PRO') "
                "listed among the stock categories, each of those twice"),
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

# Seats whose 2026 primary was not the state's (results.seat_dates), keyed on
# race id: {"primary", "runoff", "source"}. A per-state calendar cannot hold
# them, and the four Alabama seats read "Primary held 2026-05-19" for a
# primary held in August.
#
# Alabama: after the Supreme Court stayed the court-drawn map, Governor Ivey's
# special primary proclamation of 2026-05-12 postponed the primaries for the
# 1st, 2nd, 6th and 7th districts to a special primary on August 11, 2026,
# under the Legislature's 2023 plan, with no runoff; the winners go to the
# November 3 ballot (governor.alabama.gov newsroom, 2026-05-12; Alabama Public
# Radio, 2026-08-10; read 2026-10-17).
_AL_SPECIAL = {"primary": "2026-08-11", "runoff": None,
               "source": "https://governor.alabama.gov/newsroom/2026/05/governor-ivey-celebrates-"
                         "major-court-victory-in-states-redistricting-battle-calls-special-"
                         "election-for-alabama-drawn-congressional-map/ (special primary "
                         "proclamation of 2026-05-12; read 2026-10-17)"}
SEAT_PRIMARY_DATES = {
    "H-AL-01-2026": _AL_SPECIAL,
    "H-AL-02-2026": _AL_SPECIAL,
    "H-AL-06-2026": _AL_SPECIAL,
    "H-AL-07-2026": _AL_SPECIAL,
}

# House seats left empty during the 119th Congress with no special election
# to fill them, keyed (state, district): who left, the day their term ended
# as congress-legislators' legislators-historical records it (the bioguide id
# is the key into it), how, and whether a special election has been called,
# each with the day it was checked. Shown on the delegation and the district
# map (RACES-05, FRESHNESS-12) while nobody sits there. validate reports an
# entry for a seat someone now sits in, and one whose member the snapshot
# still seats; it cannot check `left`, which the build has no offline record
# of (neither member is in Former_Members.csv), so check it by hand against
# legislators-historical when adding an entry. Re-check `special` before
# moving `checked`.
SEAT_VACANCIES = {
    ("FL", 20): {
        "bioguide": "C001127", "name": "Sheila Cherfilus-McCormick", "left": "2026-04-21",
        "how": "resigned", "special": "no special election called", "checked": "2026-10-17",
        "source": "legislators-historical (term end 2026-04-21); House Press Gallery, party "
                  "breakdown: resigned 04/21/26; Wikipedia, 119th United States Congress: no "
                  "special election before the 2026 elections; read 2026-10-17",
    },
    ("TX", 23): {
        "bioguide": "G000594", "name": "Tony Gonzales", "left": "2026-04-14",
        "how": "resigned", "special": "no special election called", "checked": "2026-10-17",
        "source": "legislators-historical (term end 2026-04-14); House Press Gallery, party "
                  "breakdown: resigned 04/14/2026; Texas Tribune: the governor has called no "
                  "special election; read 2026-10-17",
    },
}

# Certified November ballots published only as a PDF, which the standard
# library cannot read (kyc/certified.py reads the HTML ones), transcribed from
# the document named, printed names only: name and party as the list gives
# them, in its order. ``complete`` says the list is the whole ballot for its
# races, so that a filer it does not name is not on the ballot (rule 77); a
# list that is not (a party's own list of its nominees) only adds names.
# Re-read the document before the election and move ``read``.
CERTIFIED_BALLOTS = {
    "IA": {
        "source": "Iowa Secretary of State, Candidate List, November 3, 2026 General Election "
                  "(last updated 8/14/2026)",
        "url": "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate"
               "%20List%20Database%20-%20All%20Elections_0.pdf",
        "read": "2026-10-17", "complete": True,
        "races": {
            "S-IA-2026": [("Ashley Hinson", "Republican"), ("Josh Turek", "Democratic"),
                          ("Thomas Laehn", "Libertarian")],
            "H-IA-01-2026": [("Mariannette Miller-Meeks", "Republican"),
                             ("Christina Bohannan", "Democratic"),
                             ("Michael Bridgford", "No Party")],
            # Rick Stewart: kept on the ballot by the State Objections Panel
            # on June 15 (KCRG); the Cerro Gordo County list revised 9/3/2026
            # prints the same four.
            "H-IA-02-2026": [("Joe Mitchell", "Republican"), ("Lindsay James", "Democratic"),
                             ("Rick Stewart", "Libertarian"), ("Dave Bushaw", "No Party")],
            "H-IA-03-2026": [("Zach Nunn", "Republican"), ("Sarah Trone Garriott", "Democratic")],
            "H-IA-04-2026": [("Chris McGowan", "Republican"), ("Dave Dawson", "Democratic")],
        },
    },
    "NE": {
        "source": "Nebraska Secretary of State, Final Statewide General Candidate List, "
                  "November 3, 2026 General Election (9/11/2026)",
        "url": "https://sos.nebraska.gov/sites/default/files/doc/elections/2026/"
               "Final_Statewide_General_Candidate_Filing_List_9.11.26.pdf",
        "read": "2026-10-17", "complete": True,
        "races": {
            # Mike Marvin suspended his campaign on August 21 and stays on
            # the ballot (Nebraska Examiner via WOWT, 2026-09-02); the
            # certified list prints him.
            "S-NE-2026": [("Pete Ricketts", "Republican"), ("Mike Marvin", "Legal Marijuana NOW"),
                          ("Robin Richards", "Nebraska Working People"),
                          ("Chuck Conboy", "America First"), ("Dan Osborn", "By Petition")],
            "H-NE-01-2026": [("Mike Flood", "Republican"), ("Chris Backemeyer", "Democratic"),
                             ("Nik Sandman", "Libertarian"), ("Dan Hartong", "America First")],
            "H-NE-02-2026": [("Brinker Harding", "Republican"), ("Denise Powell", "Democratic"),
                             ("Eric Michael Foreman", "Libertarian")],
            "H-NE-03-2026": [("Adrian Smith", "Republican"), ("Becky Kelly Stille", "Democratic"),
                             ("David J. Else", "Legal Marijuana NOW"),
                             ("Macey Budke", "Nebraska Working People"),
                             ("Mark Cohen", "By Petition")],
        },
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

# A committee seat's title as the body itself styles it, where the rosters
# give the minority's lead the majority's title. Keyed on the committee's
# code, the side and the rosters' own title, never on a person: (code,
# side, rosters' title) -> (title, evidence). congress-legislators titles
# both leads of the Senate Caucus on International Narcotics Control
# "Chairman", so the guide's committee table showed two chairmen of one
# panel and the minority's lead's profile read "(Chairman)". Checked
# 2026-10-17: the caucus's own site, drugcaucus.senate.gov, styles its
# majority lead "Chairman" and its minority lead "Co-Chair". validate
# warns on any other minority seat titled as a chair, and on an entry here
# that matches no seat.
COMMITTEE_TITLES = {
    ("SCNC", "minority", "Chairman"): (
        "Co-Chair", "drugcaucus.senate.gov, 2026-10-17: 'Chairman (R - TX)' and "
        "'Co-CHAIR (D - RI)' at the head of its home page"),
}

# A leadership post congress-legislators titles in words that read as
# something else, shown in the chamber's own words. "Senate Republican
# Committee Chair" sat beside Tim Scott's chair of the Banking Committee and
# read as the chair of a Senate committee; it is the party's campaign
# committee (the same title was Steve Daines's for 2023-24). Keyed on the
# record's title, never a person; validate warns once no one holds it.
LEADERSHIP_TITLES = {
    "Senate Republican Committee Chair": (
        "Republican Senatorial Committee Chair",
        "senate.gov/senators/leadership.htm, 2026-10-18: 'Republican Senatorial Committee "
        "Chair' Scott, Tim (R-SC), among the party leadership"),
}

# A justice's official portrait on their court's own page that the strict
# words test of kyc/court_photos.py refuses - an alt text that misspells
# them, a nickname, a file named by initials - looked at by a person, with
# the page's own words beside it and the day. Keyed (court, the name as the
# court's roster gives it); each is the record a read photograph carries
# (official_photos.record: the file, its page, the evidence, the day, its
# bytes and pixel size), with portraitHeavy where it is over the caps (rule
# 87: shown all the same and said).
# Not shown once the court no longer lists the justice, and the build says
# so.
def _justice_photo(photo, page, evidence, weight, read):
    return dict(zip(("bytes", "width", "height"), weight), photo=photo, page=page,
                evidence=evidence, read=read)


JUSTICE_PHOTOS = {
}

# State high courts whose own sites refuse every automated reader - a plain
# request and the headless Chrome of tools/read_court_pages.mjs alike (a
# Cloudflare or Akamai wall, a 403) - read once by hand, in an ordinary
# windowed Chrome, on the court's own page and nowhere else (rule 57). Each is
# (the court's page, the day it was read, the members in the court's order,
# the chief or "" when the page names none, what the page says, quoted).
# The build checks each against its seats and chief as it would a read
# roster, and warns once one is STALE_DAYS old (kyc/courts.py):
# read the page again, then move the date or change the names. The page
# says each was read by hand, and on which day.
COURT_ROSTERS = {
    "MO": ("https://www.courts.mo.gov/page.jsp?id=133", "2026-10-18",
           ("W. Brent Powell", "Zel M. Fischer", "Robin Ransom", "Paul C. Wilson",
            "Kelly C. Broniec", "Ginger K. Gooch", "Mary R. Russell"),
           "W. Brent Powell",
           "'The current Supreme Court of Missouri judges are:', then one per line: 'Chief "
           "Justice W. Brent Powell', 'Judge Zel M. Fischer', 'Judge Robin Ransom', 'Judge Paul "
           "C. Wilson', 'Judge Kelly C. Broniec', 'Judge Ginger K. Gooch', 'Judge Mary R. "
           "Russell'. A headless Chrome gets 'Error 403' and a notice that access 'by a site "
           "data scraper or any similar software' is prohibited."),
    "NH": ("https://www.courts.nh.gov/our-courts/supreme-court/about/justices", "2026-10-18",
           ("Patrick E. Donovan", "Melissa B. Countway", "Bryan K. Gould", "Daniel E. Will"),
           "",
           "One per line: 'Senior Associate Justice Patrick E. Donovan', 'Justice Melissa B. "
           "Countway', 'Justice Bryan K. Gould', 'Justice Daniel E. Will'. The page names no "
           "chief justice (a Senior Associate Justice is not one), and lists 'Senior Associate "
           "Justice Anna Barbara Hantz Marconi - February 12, 2026' and 'Senior Associate "
           "Justice James P. Bassett - August 31, 2025' under 'Recent retirements'. Akamai "
           "answers a headless Chrome 'Access Denied'."),
    "NV": ("https://nvcourts.gov/supreme/court_information/the_supreme_court_of_nevada_justices",
           "2026-10-18",
           ("Kristina Pickering", "Linda Marie Bell", "Ron D. Parraguirre", "Patricia Lee",
            "Elissa F. Cadish", "Douglas Herndon", "Lidia S. Stiglich"),
           "Douglas Herndon",
           "'Justice Kristina Pickering, Justice Linda Marie Bell, Justice Ron D. Parraguirre, "
           "Justice Patricia Lee, Justice Elissa F. Cadish, Chief Justice Douglas Herndon, "
           "Justice Lidia S. Stiglich', and the same seven under 'SUPREME COURT OF NEVADA "
           "JUSTICES'. Cloudflare answers a headless Chrome 'Just a moment...'."),
    "NY": ("https://www.nycourts.gov/ctapps/", "2026-10-18",
           ("Shirley Troutman", "Madeline Singas", "Jenny Rivera", "Rowan D. Wilson",
            "Michael J. Garcia", "Anthony Cannataro", "Caitlin J. Halligan"),
           "Rowan D. Wilson",
           "The menu 'JUDGES OF THE COURT': 'Hon. Shirley Troutman', 'Hon. Madeline Singas', "
           "'Hon. Jenny Rivera', 'Hon. Rowan D. Wilson', 'Hon. Michael J. Garcia', 'Hon. "
           "Anthony Cannataro', 'Hon. Caitlin J. Halligan'; the same page: 'On September 24, "
           "2026, Chief Judge Rowan D. Wilson conducted a statewide public hearing'. "
           "Cloudflare answers a headless Chrome 'Just a moment...'."),
}

# Ids a chamber's roll calls list that belong to no member of that Congress,
# with what the record shows and why (kyc/rollcalls.py). Their votes are
# given to nobody either way (rule 17); an entry here only says the build
# need not warn about it, and validate warns once the id is a member's after
# all. Keyed on the record's id, never a name.
ROLL_CALL_NON_MEMBERS = {
    "G000578": (
        "Matt Gaetz, re-elected for FL-1 in 2024, did not take the seat in the 119th "
        "Congress: congress-legislators gives him no term in it, and FL-1's next member, "
        "Jimmy Patronis (P000622), was seated on 2025-04-02 after a special election. The "
        "Clerk's roll call 1 of 2025 (the call of the House by states, 2025-01-03) lists "
        "'Gaetz' (FL) as Not Voting; read 2026-10-18."),
}

# Lists of the statewide candidates (data/statewide_candidates.json, rule
# 91) published on a host that is not the jurisdiction's own domain
# (voting_dates.JURISDICTION_DOMAINS): the state election office's own file
# store or vendor, or - only where the state's own list could not be read or
# does not exist - a county's election office or another state body. A list
# the state's office serves only to a person's browser is read by hand from
# its own page, quoted and dated, never stood in for by another body's (rule
# 91: Nevada's, read 2026-10-25, replaced Clark County's notice; Arizona's
# Secretary of State's listing, read 2026-10-26, its Clean Elections
# Commission's voter education guide).
# {url prefix: (codes, who publishes it, own, evidence)}, where *own* is True
# only for the state election office's own document on another host. A list
# that is not the state's own is never called certified and says on the page
# why it was used (statewide.problems; PR #109 review: a county's sample
# ballot read "Certified by" the county). Being a .gov host is not enough: a
# list counts here only for the jurisdictions named. Read 2026-10-18.
STATEWIDE_LISTS_ELSEWHERE = {
    "https://votepulaskiar.gov/": (
        ("AR",), "Pulaski County Board of Election Commissioners", False,
        "the county board's Notice of Election for November 3, 2026 (PDF, Last-Modified "
        "2026-10-05); Arkansas's Secretary of State publishes no list of the November "
        "candidates, and its candidate search (candidates.arkansas.gov) names the same people "
        "for these offices"),
    "https://drive.google.com/file/d/1RKr3bLuivj8n0n29XKbQVHEgdUYwILMN/": (
        ("GU",), "Guam Election Commission", True,
        "'2026 General Election Sample Ballot', linked by that name from the Commission's home "
        "page, https://gec.guam.gov/"),
    "https://mi-boe.entellitrak.com/etk-mi-boe-prod/": (
        ("MI",), "Michigan Department of State", True,
        "the Bureau of Elections' Official Candidate Listing, linked as '2026 November General "
        "Candidate Listing' from https://www.michigan.gov/sos/elections"),
    "https://sos-prod.tnsosgovfiles.com/": (
        ("TN",), "Tennessee Secretary of State", True,
        "the Division of Elections' file store, linked as PDF from "
        "https://sos.tn.gov/elections/2026-candidate-lists"),
}

# The statewide ballot measures (data/ballot_measures.json, rule 95) cited
# from an official page on a host that is not the jurisdiction's own domain
# (voting_dates.JURISDICTION_DOMAINS): the election office's own file store
# or second domain, or a county's or town's official ballot where the state
# publishes the wording nowhere it could be read. A statewide question is
# printed on every ballot in the state, so one county's full set of official
# ballots shows what is statewide. {url prefix: (codes, who publishes it,
# evidence)}. Being a .gov host is not enough: a page counts here only for
# the jurisdictions named. Read 2026-10-19.
MEASURE_SOURCES_ELSEWHERE = {
    "https://www.clarkcountynv.gov/": (
        ("NV",), "Clark County Election Department",
        "the Department's official ballot-questions booklet for the November 3, 2026 general "
        "election, which prints State Questions 6 and 7, the two questions the Secretary of "
        "State's 2026 Petitions page names. The questions' words are quoted from it because, "
        "read on 2026-10-19, the Secretary of State's 2026 Ballot Question Guide was not yet "
        "posted ('will be published HERE prior to the 2026 General Election'); it is posted "
        "now (https://www.nvsos.gov/home/showpublisheddocument/20519/639233354596030000, linked "
        "from the 2026 Election Information page, read by hand 2026-10-25) and is the voter "
        "guide the page links; its text has not been compared with the booklet's, since "
        "nvsos.gov serves no script, so each question's words and its page stay the booklet's"),
    "https://s3.amazonaws.com/dl.ncsbe.gov/": (
        ("NC",), "North Carolina State Board of Elections",
        "the State Board's file store, linked as 'Statewide referenda' from "
        "https://www.ncsbe.gov/voting/upcoming-election"),
    "https://www.beaufortncboe.org/": (
        ("NC",), "Beaufort County Board of Elections",
        "the Legislative Services Officer's official summary explanation of the 2026 "
        "amendments (N.C.G.S. 147-54.10, adopted August 20, 2026) as the county board posts "
        "it; it was found on no state host"),
    "https://www.votedouglascounty-ne.gov/": (
        ("NE",), "Douglas County Election Commission",
        "the Commission's countywide sample ballot for the 11/03/2026 general election, the "
        "printed wording of Proposed Amendment No. 1, which the Secretary of State's pamphlet "
        "does not cover; the Legislative Council Executive Board's approved ballot statement "
        "on sos.nebraska.gov (a scan) carries the same words"),
    "https://www.edenvt.org/": (
        ("VT",), "Town of Eden",
        "the town's official sample ballot, whose 'OFFICIAL STATE CONSTITUTIONAL AMENDMENT "
        "BALLOT NOVEMBER 3, 2026' column prints both proposals; Burlington's sample ballot "
        "prints the same text word for word"),
    "https://drive.google.com/file/d/1RKr3bLuivj8n0n29XKbQVHEgdUYwILMN/": (
        ("GU",), "Guam Election Commission",
        "'2026 General Election Sample Ballots', linked by that name from "
        "https://gec.guam.gov/2026-general-election-info/"),
    "https://www.somersetcountynj.gov/": (
        ("NJ",), "Somerset County Clerk",
        "the Clerk's official 2026 general-election sample ballots for every municipality "
        "(Last-Modified 2026-10-09), linked from the County Clerk's Election Division page; "
        "the Division of Elections' 2026 page lists no statewide public question"),
    "https://www.vote.nyc/": (
        ("NY",), "Board of Elections in the City of New York",
        "the Board's 'Appendix A, Proposed Questions, 2026 General Election', linked from "
        "https://vote.nyc/page/ballot-proposals; the State Board of Elections publishes no "
        "2026 ballot-proposals page"),
    "https://www.gtcountysc.gov/": (
        ("SC",), "Georgetown County Board of Voter Registration and Elections",
        "the county's official sample ballots for all 52 ballot styles of the November 3, "
        "2026 general election, linked from https://www.gtcountysc.gov/398/Upcoming-Elections"),
}

# A holder whose name the list of candidates prints with another given name,
# where only a short form and its full form differ (rule 56: a different
# first name is never taken on a surname alone). {(state, office, holder as
# the rosters name them): (the list's name, evidence)}.
STATEWIDE_NAME_FORMS = {
    ("NV", "governor", "Joe Lombardo"): (
        "Lombardo, Joseph",
        "the Governor's own site, gov.nv.gov (read 2026-10-18), links his account "
        "twitter.com/JosephMLombardo; the Secretary of State's statewide certified list "
        "prints 'Lombardo, Joseph | Joseph Lombardo | Republican Party | Governor' (read by "
        "hand 2026-10-25), as Clark County's notice printed 'Lombardo, Joseph REP', and every "
        "reader read it as the governor"),
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
