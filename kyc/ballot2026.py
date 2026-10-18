"""Which state offices are on the November 3, 2026 ballot, state by state.

The site covered Congress only, and said nothing about the rest of a
reader's ballot: 36 governorships, most lieutenant governors, attorneys
general and secretaries of state, and most of the 99 legislative chambers
are elected the same day, and a member running for governor read as simply
"not running" (audit CG-6, CG-16, MAP-8).

A table of every state is a claim about every state (rule 49), so each
value here cites the state's own constitution, statute or 2026 election
pages - never NCSL, Ballotpedia or Wikipedia, which were leads only (rule
50). It was researched state by state on 2026-10-14 and every value checked
again, independently, by a second reader; ``check`` holds the table to its
own rules and its chamber sizes to ``government_maps.SEATS``. Who is
running for these offices is not here: no source keyed by an id the site
can hold lists state candidates, and names from a search are not data.

Each office is ``(how it is filled, on the 2026 ballot, a note, source)``.
Each chamber is ``(its name, seats, seats on the 2026 ballot, which, source)``;
Nebraska's one chamber is its ``upper`` and its ``lower`` is None. Only
regular elections are counted: a special election to fill an unexpired term
(two Kansas Senate seats in 2026, for one) is not, and the page says
"regular" wherever a count could be read as the whole ballot.
"""

import urllib.parse

from .government_maps import SEATS
from .government_maps import STATES as STATE_CODES

ELECTION = "2026-11-03"
REVIEWED = "2026-10-14"

SELECTIONS = ("elected", "elected-jointly-with-governor", "appointed",
              "chosen-by-legislature", "no-such-office")
OFFICES = ("governor", "lt", "ag", "sos")
TITLES = {"governor": "Governor", "lt": "Lieutenant governor", "ag": "Attorney general",
          "sos": "Secretary of state"}
# Compiled tables are leads, never the cited source (rule 50); a county's
# page is not the state's record of a statewide count.
NOT_A_SOURCE = ("ncsl.org", "ballotpedia.org", "wikipedia.org", "270towin.com",
                "countyohio.gov")

STATES = {
    "AK": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; 'Governor / Lieutenant Governor' in the 2026 pamphlet",
            "https://www.elections.alaska.gov/election/2026/General/OEPbooks/2026%20Alaska%20General%20VP_Region%201_ENG_web.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "Runs on a joint ticket with the governor in the general election",
            "https://www.elections.alaska.gov/election/2026/General/OEPbooks/2026%20Alaska%20General%20VP_Region%201_ENG_web.pdf"),
        "ag": ("appointed", False,
            "Appointed by the governor as head of the Department of Law",
            "https://www.akleg.gov/basis/statutes.asp#44.23.010"),
        "sos": ("no-such-office", False,
            "No secretary of state; the lieutenant governor oversees elections",
            "https://www.elections.alaska.gov/election/2026/General/OEPbooks/2026%20Alaska%20General%20VP_Region%201_ENG_web.pdf"),
        "upper": ("Senate", 20, 10,
            "districts A, C, E, G, I, K, M, O, Q, S",
            "https://www.elections.alaska.gov/election/2026/General/OEPbooks/2026%20Alaska%20General%20VP_Region%201_ENG_web.pdf"),
        "lower": ("House of Representatives", 40, 40,
            "all (districts 1-40)",
            "https://www.elections.alaska.gov/election/2026/General/OEPbooks/2026%20Alaska%20General%20VP_Region%201_ENG_web.pdf"),
    },
    "AL": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; on 2026 sample ballot",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
        "lt": ("elected", True,
            "Elected separately; 4-year term; on 2026 sample ballot",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
        "ag": ("elected", True,
            "4-year term; 'For Attorney General' on 2026 sample ballot",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
        "sos": ("elected", True,
            "4-year term; on 2026 sample ballot",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
        "upper": ("Senate", 35, 35,
            "all (4-year terms, elected with the House)",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
        "lower": ("House of Representatives", 105, 105,
            "all (4-year terms)",
            "https://www.sos.alabama.gov/sites/default/files/sample-ballots/2026/gen/Montgomery-Sample.pdf"),
    },
    "AR": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
        "lt": ("elected", True,
            "Elected separately; 4-year term; last elected 2022",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
        "upper": ("Senate", 35, 17,
            "17 seats, as the State Board of Election Commissioners lists the offices up in 2026",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
        "lower": ("House of Representatives", 100, 100,
            "all (2-year terms)",
            "https://sbec.arkansas.gov/wp-content/uploads/2025-Running-for-Public-Office-8-13-25-FINAL-small.pdf"),
    },
    "AZ": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.azleg.gov/const/5/1.htm"),
        "lt": ("elected-jointly-with-governor", True,
            "New office (Prop 131, 2022): the governor nominee names a running mate on a joint ticket; first elected 2026",
            "https://www.azleg.gov/const/5/1.htm"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.azleg.gov/const/5/1.htm"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.azleg.gov/const/5/1.htm"),
        "upper": ("Senate", 30, 30,
            "all (2-year terms)",
            "https://www.azleg.gov/const/4/21.p2.htm"),
        "lower": ("House of Representatives", 60, 60,
            "all (2 per district, 2-year terms)",
            "https://www.azleg.gov/const/4/21.p2.htm"),
    },
    "CA": {
        "governor": ("elected", True,
            "4-year term; on the SoS certified list",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
        "lt": ("elected", True,
            "Elected separately; on the SoS certified list",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
        "ag": ("elected", True,
            "4-year term; on the SoS certified list",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
        "sos": ("elected", True,
            "4-year term; on the SoS certified list",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
        "upper": ("Senate", 40, 20,
            "the 20 even-numbered districts (2-40)",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
        "lower": ("Assembly", 80, 80,
            "all",
            "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"),
    },
    "CO": {
        "governor": ("elected", True,
            "4-year term; 'Governor/Lt. Governor' one row",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
        "lt": ("elected-jointly-with-governor", True,
            "Joint ticket with the governor",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
        "ag": ("elected", True,
            "4-year term",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
        "sos": ("elected", True,
            "4-year term",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
        "upper": ("Senate", 35, 17,
            "regular 4-year: districts 1,3,4,7,8,9,11,15,20,22,24,25,27,30,32,34,35 (plus 17,21,29,31 for 2-year vacancy remainders, not counted)",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
        "lower": ("House of Representatives", 65, 65,
            "all",
            "https://www.coloradosos.gov/pubs/elections/vote/officeUpForElection.html"),
    },
    "CT": {
        "governor": ("elected", True,
            "4-year term; constitutional officer on the 2026 ballot",
            "https://portal.ct.gov/-/media/sots/electionservices/voter_guide/2026/2026_voter_guide_final.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "elected jointly with the governor: one vote for both (Const. art. IV, s3)",
            "https://www.cga.ct.gov/asp/Content/constitutions/Constitution_State_CT.pdf"),
        "ag": ("elected", True,
            "4-year term",
            "https://portal.ct.gov/-/media/sots/electionservices/voter_guide/2026/2026_voter_guide_final.pdf"),
        "sos": ("elected", True,
            "Official title 'Secretary of the State'; 4-year term",
            "https://portal.ct.gov/-/media/sots/electionservices/voter_guide/2026/2026_voter_guide_final.pdf"),
        "upper": ("Senate", 36, 36,
            "all",
            "https://portal.ct.gov/-/media/sots/electionservices/voter_guide/2026/2026_voter_guide_final.pdf"),
        "lower": ("House of Representatives", 151, 151,
            "all",
            "https://portal.ct.gov/-/media/sots/electionservices/voter_guide/2026/2026_voter_guide_final.pdf"),
    },
    "DE": {
        "governor": ("elected", False,
            "4-year term; elected 2024; next 2028",
            "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.html"),
        "lt": ("elected", False,
            "Separate contest chosen 'at the same time' as the governor (Const. Art. III s.19); elected 2024",
            "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.html"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.html"),
        "sos": ("appointed", False,
            "Appointed by the governor with Senate consent (29 Del.C. s.8702; Const. Art. III s.10)",
            "https://delcode.delaware.gov/title29/c087/sc01/index.html"),
        "upper": ("Senate", 21, 11,
            "districts 1, 5, 7, 8, 9, 12, 13, 14, 15, 19, 20",
            "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.html"),
        "lower": ("House of Representatives", 41, 41,
            "all",
            "https://elections.delaware.gov/candidates/candidatelist/genl_fcddt_2026.html"),
    },
    "FL": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://dos.elections.myflorida.com/candidates/CanList.asp?elecid=20261103-GEN&OfficeCode=GOV"),
        "lt": ("elected-jointly-with-governor", True,
            "Joint ticket with the governor (Const. Art. IV s.5); not listed separately",
            "https://dos.elections.myflorida.com/candidates/CanList.asp?elecid=20261103-GEN&OfficeCode=GOV"),
        "ag": ("elected", True,
            "Cabinet officer; 4-year term",
            "https://dos.elections.myflorida.com/candidates/CanList.asp?elecid=20261103-GEN&OfficeCode=ATG"),
        "sos": ("appointed", False,
            "Appointed by the governor, confirmed by the Senate (s.20.10 F.S.)",
            "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0000-0099/0020/Sections/0020.10.html"),
        "upper": ("Senate", 40, 20,
            "the 20 even-numbered districts (2-40)",
            "https://dos.elections.myflorida.com/candidates/CanList.asp?elecid=20261103-GEN&OfficeCode=STS"),
        "lower": ("House of Representatives", 120, 120,
            "all",
            "https://dos.elections.myflorida.com/candidates/CanList.asp?elecid=20261103-GEN&OfficeCode=STR"),
    },
    "GA": {
        "governor": ("elected", True,
            "4-year term; term begins 01/2027",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
        "lt": ("elected", True,
            "Elected separately; 4-year term",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
        "ag": ("elected", True,
            "4-year term",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
        "sos": ("elected", True,
            "4-year term",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
        "upper": ("Senate", 56, 56,
            "all 56 districts (2-year terms)",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
        "lower": ("House of Representatives", 180, 180,
            "all 180 districts",
            "https://sos.ga.gov/2026-offices-appear-ballot"),
    },
    "HI": {
        "governor": ("elected", True,
            "4-year term, through Dec 2, 2030",
            "https://elections.hawaii.gov/2026-proclamation/"),
        "lt": ("elected-jointly-with-governor", True,
            "Separate primaries; votes in the general count for the party's ticket (Const. Art. V s.2)",
            "https://elections.hawaii.gov/2026-proclamation/"),
        "ag": ("appointed", False,
            "Appointed by the governor with Senate consent (Const. Art. V s.6)",
            "https://lrb.hawaii.gov/constitution"),
        "sos": ("no-such-office", False,
            "No secretary of state; the lieutenant governor holds those duties",
            "https://lrb.hawaii.gov/constitution"),
        "upper": ("Senate", 25, 13,
            "districts 2, 5, 8, 9, 10, 11, 13, 14, 15, 17, 20, 21, 25 (plus a District 19 vacancy for 2 years, not counted)",
            "https://elections.hawaii.gov/2026-proclamation/"),
        "lower": ("House of Representatives", 51, 51,
            "all",
            "https://elections.hawaii.gov/2026-proclamation/"),
    },
    "IA": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "Joint ticket with the governor (Const. Art. IV s.3)",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
        "ag": ("elected", True,
            "4-year term",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
        "sos": ("elected", True,
            "4-year term",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
        "upper": ("Senate", 50, 25,
            "the 25 odd-numbered districts (1-49)",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
        "lower": ("House of Representatives", 100, 100,
            "all",
            "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf"),
    },
    "ID": {
        "governor": ("elected", True,
            "4-year term, on the cycle starting 1946",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIV/Sect1/"),
        "lt": ("elected", True,
            "Elected separately; 4-year term",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIV/Sect1/"),
        "ag": ("elected", True,
            "4-year term",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIV/Sect1/"),
        "sos": ("elected", True,
            "4-year term",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIV/Sect1/"),
        "upper": ("Senate", 35, 35,
            "all (2-year terms)",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIII/Sect3/"),
        "lower": ("House of Representatives", 70, 70,
            "all (2 per district)",
            "https://legislature.idaho.gov/statutesrules/idconst/ArtIII/Sect3/"),
    },
    "IL": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.elections.il.gov/electionoperations/CandidateList.aspx?ElectionID=Z2J%2FvYpKX8w%3D&OfficeID=Rqf5Z%2FpnY7D53Pi5fA4orw%3D%3D"),
        "lt": ("elected-jointly-with-governor", True,
            "SBE lists the office as 'Governor and Lieutenant Governor'",
            "https://www.elections.il.gov/electionoperations/CandidateList.aspx?ElectionID=Z2J%2FvYpKX8w%3D&OfficeID=Rqf5Z%2FpnY7D53Pi5fA4orw%3D%3D"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.elections.il.gov/ElectionOperations/CandidatesFiled.aspx"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.elections.il.gov/ElectionOperations/CandidatesFiled.aspx"),
        "upper": ("Senate", 59, 39,
            "first group (4-year) and second group (2-year) under 10 ILCS 5/29C-10",
            "https://www.ilga.gov/Documents/legislation/ilcs/documents/001000050K29C-10.htm"),
        "lower": ("House of Representatives", 118, 118,
            "all",
            "https://www.ilga.gov/Documents/legislation/ilcs/documents/001000050K29C-10.htm"),
    },
    "IN": {
        "governor": ("elected", False,
            "4-year term; elected 2024; next 2028",
            "https://www.in.gov/sos/elections/files/2026-Candidate-Guide.FINAL.pdf"),
        "lt": ("elected-jointly-with-governor", False,
            "Joint ticket with the governor; elected 2024",
            "https://www.in.gov/sos/elections/files/2026-Candidate-Guide.FINAL.pdf"),
        "ag": ("elected", False,
            "4-year term; elected 2024; next 2028",
            "https://www.in.gov/sos/elections/files/Candidate_List_Abbreviated_20260922_011251PM.xlsx"),
        "sos": ("elected", True,
            "4-year term; last elected 2022; nominated at convention",
            "https://www.in.gov/sos/elections/files/Candidate_List_Abbreviated_20260922_011251PM.xlsx"),
        "upper": ("Senate", 50, 25,
            "districts 1,4,6,11,14,15,17,19,21,22,23,25,26,27,29,31,38,39,41,43,45,46,47,48,49",
            "https://www.in.gov/sos/elections/files/Candidate_List_Abbreviated_20260922_011251PM.xlsx"),
        "lower": ("House of Representatives", 100, 100,
            "all",
            "https://www.in.gov/sos/elections/files/Candidate_List_Abbreviated_20260922_011251PM.xlsx"),
    },
    "KS": {
        "governor": ("elected", True,
            "4-year term; 'Governor and Lieutenant Governor' on the 2026 ballot",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
        "lt": ("elected-jointly-with-governor", True,
            "Elected on one ticket with the governor",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
        "ag": ("elected", True,
            "4-year term",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
        "sos": ("elected", True,
            "4-year term",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
        "upper": ("Senate", 40, 0,
            "none regular: all 40 elected 2024 for 4 years; only districts 24 and 25 are on the 2026 ballot",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
        "lower": ("House of Representatives", 125, 125,
            "all",
            "https://sos.ks.gov/media/press-releases/2026/06-01-26-candidate-filing-deadline-closes.html"),
    },
    "KY": {
        "governor": ("elected", False,
            "4-year term; odd-year elections; next 2027",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
        "lt": ("elected-jointly-with-governor", False,
            "Joint slate with the governor; next 2027",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
        "ag": ("elected", False,
            "4-year term; next 2027",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
        "sos": ("elected", False,
            "4-year term; next 2027",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
        "upper": ("Senate", 38, 19,
            "the 19 even-numbered districts",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
        "lower": ("House of Representatives", 100, 100,
            "all (2-year terms)",
            "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
    },
    "LA": {
        "governor": ("elected", False,
            "4-year term; elected in gubernatorial (odd) years, last 2023, next 2027",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
        "lt": ("elected", False,
            "elected separately from governor; 4-year term; last elected 2023",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
        "ag": ("elected", False,
            "4-year term; elected with governor in 2023",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
        "sos": ("elected", False,
            "4-year term; elected with governor in 2023",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
        "upper": ("Senate", 39, 0,
            "none: elected with the governor in odd years (last 2023, next 2027)",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
        "lower": ("House of Representatives", 105, 0,
            "none: elected with the governor in odd years (last 2023, next 2027)",
            "https://legis.la.gov/legis/Law.aspx?d=81545"),
    },
    "MA": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
        "lt": ("elected-jointly-with-governor", True,
            "nominated separately in the primary, elected jointly with the governor in November",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
        "sos": ("elected", True,
            "Secretary of the Commonwealth; 4-year term; last elected 2022",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
        "upper": ("Senate", 40, 40,
            "all (2-year terms)",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
        "lower": ("House of Representatives", 160, 160,
            "all (2-year terms)",
            "https://www.sec.state.ma.us/divisions/elections/research-and-statistics/dem-state-primary-candidates2026.htm"),
    },
    "MD": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
        "lt": ("elected-jointly-with-governor", True,
            "runs on a joint Governor/Lt. Governor ticket",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
        "sos": ("appointed", False,
            "the secretary of state is appointed by the governor with Senate consent (Const. Art. II, s.22)",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
        "upper": ("Senate", 47, 47,
            "all (4-year terms, elected in gubernatorial years)",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
        "lower": ("House of Delegates", 141, 141,
            "all (4-year terms, elected in gubernatorial years)",
            "https://www.elections.maryland.gov/elections/2026/general_candidates/2026_GG_statewide_candidatelist.html"),
    },
    "ME": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; open seat (Mills term-limited)",
            "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20General%20Candidate%20List%20-%20FINAL.xlsx"),
        "lt": ("no-such-office", False,
            "Maine has no lieutenant governor; the Senate president is first in succession",
            "https://www.maine.gov/legis/const/"),
        "ag": ("chosen-by-legislature", False,
            "chosen biennially by joint ballot of the Legislature (Const. Art. IX, s.11)",
            "https://www.maine.gov/legis/const/"),
        "sos": ("chosen-by-legislature", False,
            "chosen biennially by joint ballot of the Legislature (Const. Art. V, Pt. 2)",
            "https://www.maine.gov/legis/const/"),
        "upper": ("Senate", 35, 35,
            "all (2-year terms)",
            "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20General%20Candidate%20List%20-%20FINAL.xlsx"),
        "lower": ("House of Representatives", 151, 151,
            "all (2-year terms)",
            "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20General%20Candidate%20List%20-%20FINAL.xlsx"),
    },
    "MI": {
        "governor": ("elected", True,
            "4-year term, elected in alternate even years; last elected 2022",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-V-21"),
        "lt": ("elected-jointly-with-governor", True,
            "one vote cast jointly for governor and lieutenant governor (Const. Art. V, s.21)",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-V-21"),
        "ag": ("elected", True,
            "4-year term, elected with the governor; last elected 2022",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-V-21"),
        "sos": ("elected", True,
            "4-year term, elected with the governor; last elected 2022",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-V-21"),
        "upper": ("Senate", 38, 38,
            "all (4-year terms, elected at the same election as the governor)",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-IV-2"),
        "lower": ("House of Representatives", 110, 110,
            "all (2-year terms)",
            "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-IV-3"),
    },
    "MN": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
        "lt": ("elected-jointly-with-governor", True,
            "chosen jointly with the governor by a single vote",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
        "upper": ("Senate", 67, 67,
            "all (2-4-4 cycle; 4-year terms elected 2022 expire)",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
        "lower": ("House of Representatives", 134, 134,
            "all (2-year terms)",
            "https://www.sos.mn.gov/elections-voting/whats-on-my-ballot"),
    },
    "MO": {
        "governor": ("elected", False,
            "4-year term; elected in presidential years, last 2024",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
        "lt": ("elected", False,
            "elected separately; last elected 2024",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
        "ag": ("elected", False,
            "last elected 2024",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
        "sos": ("elected", False,
            "last elected 2024",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
        "upper": ("Senate", 34, 17,
            "the 17 even-numbered districts (2-34)",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
        "lower": ("House of Representatives", 163, 163,
            "all (2-year terms)",
            "https://www.sos.mo.gov/CMSImages/ElectionCandidates/2026GeneralElectionCertifiedCandidates.pdf"),
    },
    "MS": {
        "governor": ("elected", False,
            "4-year term; last elected 2023; next 2027",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
        "lt": ("elected", False,
            "elected separately; last elected 2023; next 2027",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
        "ag": ("elected", False,
            "last elected 2023; next 2027",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
        "sos": ("elected", False,
            "last elected 2023; next 2027",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
        "upper": ("Senate", 52, 0,
            "none: elected in odd years (next 2027)",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
        "lower": ("House of Representatives", 122, 0,
            "none: elected in odd years (next 2027)",
            "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    },
    "MT": {
        "governor": ("elected", False,
            "4-year term; last elected 2024",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
        "lt": ("elected-jointly-with-governor", False,
            "elected on a joint ticket with the governor; last elected 2024",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
        "ag": ("elected", False,
            "last elected 2024",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
        "sos": ("elected", False,
            "last elected 2024",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
        "upper": ("Senate", 50, 25,
            "25 of 50 (staggered 4-year terms)",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
        "lower": ("House of Representatives", 100, 100,
            "all (2-year terms)",
            "https://sosmt.gov/best-of-luck-to-all-secretary-christi-jacobsen-opens-2026-candidate-filing-period/"),
    },
    "NC": {
        "governor": ("elected", False,
            "4-year term; elected in presidential years, last 2024",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
        "lt": ("elected", False,
            "elected separately from the governor; last elected 2024",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
        "ag": ("elected", False,
            "Council of State; last elected 2024",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
        "sos": ("elected", False,
            "Council of State; last elected 2024",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
        "upper": ("Senate", 50, 50,
            "all (2-year terms)",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
        "lower": ("House of Representatives", 120, 120,
            "all (2-year terms)",
            "https://dl.ncsbe.gov/Elections/2026/Candidate%20Filing/2026_general_candidate_list_by_contest.pdf"),
    },
    "ND": {
        "governor": ("elected", False,
            "4-year term; last elected 2024",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
        "lt": ("elected-jointly-with-governor", False,
            "elected jointly with the governor; last elected 2024",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
        "upper": ("Senate", 47, 24,
            "the 24 odd-numbered districts (1-47), 4-year terms",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
        "lower": ("House of Representatives", 94, 48,
            "2 seats in each of the 24 odd-numbered districts (4-year terms); unexpired 2-year specials in Districts 20, 26 and 42 not counted",
            "https://vip.sos.nd.gov/candidatelist.aspx?eid=348"),
    },
    "NE": {
        "governor": ("elected", True,
            "4-year term; elected 2022, 2026, 2030",
            "https://sos.nebraska.gov/sites/default/files/doc/elections/Candidates/Elected_Offices_and_Maps.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "elected with the governor (Governor and Lieutenant Governor, one statewide office)",
            "https://sos.nebraska.gov/sites/default/files/doc/elections/Candidates/Elected_Offices_and_Maps.pdf"),
        "ag": ("elected", True,
            "4-year term; elected 2022, 2026",
            "https://sos.nebraska.gov/sites/default/files/doc/elections/Candidates/Elected_Offices_and_Maps.pdf"),
        "sos": ("elected", True,
            "4-year term; elected 2022, 2026",
            "https://sos.nebraska.gov/sites/default/files/doc/elections/Candidates/Elected_Offices_and_Maps.pdf"),
        "upper": ("Legislature", 49, 24,
            "the 24 even-numbered districts (nonpartisan, 4-year terms); District 41 also has a 2-year special in 2026 (not counted)",
            "https://sos.nebraska.gov/sites/default/files/doc/elections/Candidates/Elected_Offices_and_Maps.pdf"),
        "lower": None,
    },
    "NH": {
        "governor": ("elected", True,
            "2-year term; elected every even year",
            "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/filing-for-office-2026.pdf"),
        "lt": ("no-such-office", False,
            "New Hampshire has no lieutenant governor; the Senate president is first in succession (Const. pt. II, art. 49)",
            "https://www.nh.gov/glance/state-constitution/executive-power-governor"),
        "ag": ("appointed", False,
            "appointed by the governor and Executive Council (RSA 7:1, RSA 21-M:3; Const. Pt. II, Art. 46)",
            "https://gc.nh.gov/rsa/html/I/7/7-1.htm"),
        "sos": ("chosen-by-legislature", False,
            "chosen biennially by joint ballot of the General Court (RSA 5:1; Const. Pt. II, Art. 67)",
            "https://gc.nh.gov/rsa/html/I/5/5-1.htm"),
        "upper": ("Senate", 24, 24,
            "all (2-year terms)",
            "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/filing-for-office-2026.pdf"),
        "lower": ("House of Representatives", 400, 400,
            "all (2-year terms)",
            "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/filing-for-office-2026.pdf"),
    },
    "NJ": {
        "governor": ("elected", False,
            "4-year term; elected in odd years (last 2025)",
            "https://www.njleg.state.nj.us/constitution"),
        "lt": ("elected-jointly-with-governor", False,
            "elected conjointly with the governor (Art. V, s.I); last 2025",
            "https://www.njleg.state.nj.us/constitution"),
        "ag": ("appointed", False,
            "appointed by the governor with Senate advice and consent (Art. V, s.IV, para. 3)",
            "https://www.njleg.state.nj.us/constitution"),
        "sos": ("appointed", False,
            "appointed by the governor with Senate advice and consent (Art. V, s.IV, para. 3)",
            "https://www.njleg.state.nj.us/constitution"),
        "upper": ("Senate", 40, 0,
            "none: elected in odd years (next 2027)",
            "https://www.nj.gov/state/elections/election-information-2026.shtml"),
        "lower": ("General Assembly", 80, 0,
            "none: elected in odd years (last 2025, next 2027)",
            "https://www.nj.gov/state/elections/election-information-2026.shtml"),
    },
    "NM": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "nominated separately in the primary, elected jointly with the governor in November",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
        "upper": ("Senate", 42, 0,
            "none regular: 4-year terms elected in presidential years (2024); only a District 33 special for the remaining two years",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
        "lower": ("House of Representatives", 70, 70,
            "all (districts 1-70, 2-year terms)",
            "https://www.sos.nm.gov/wp-content/uploads/2026/04/2026-General-Election-Proclamation-English.pdf"),
    },
    "NV": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.leg.state.nv.us/Const/NvConst.html"),
        "lt": ("elected", True,
            "elected separately, 'at the same time and places and in the same manner as the Governor' (Art. 5 s.17)",
            "https://www.leg.state.nv.us/Const/NvConst.html"),
        "ag": ("elected", True,
            "elected with the governor (Art. 5 s.19); last elected 2022",
            "https://www.leg.state.nv.us/Const/NvConst.html"),
        "sos": ("elected", True,
            "elected with the governor (Art. 5 s.19); last elected 2022",
            "https://www.leg.state.nv.us/Const/NvConst.html"),
        "upper": ("Senate", 21, 11,
            "11 districts: 2, 8, 9, 10, 12, 13, 14, 16, 17, 20, 21 (4-year staggered terms)",
            "https://www.leg.state.nv.us/Division/Research/Documents/CandidatesList_2026General.pdf"),
        "lower": ("Assembly", 42, 42,
            "all (2-year terms)",
            "https://www.leg.state.nv.us/Division/Research/Documents/CandidatesList_2026General.pdf"),
    },
    "NY": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://elections.ny.gov/certification-offices-be-filled-november-3-2026-general-election"),
        "lt": ("elected-jointly-with-governor", True,
            "chosen jointly with the governor",
            "https://elections.ny.gov/certification-offices-be-filled-november-3-2026-general-election"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://elections.ny.gov/certification-offices-be-filled-november-3-2026-general-election"),
        "sos": ("appointed", False,
            "the secretary of state is appointed by the governor with Senate confirmation (Const. Art. V, s.4)",
            "https://dos.ny.gov/system/files/documents/2025/12/constitution-january-1-2026.pdf"),
        "upper": ("Senate", 63, 63,
            "all (2-year terms)",
            "https://elections.ny.gov/certification-offices-be-filled-november-3-2026-general-election"),
        "lower": ("Assembly", 150, 150,
            "all (2-year terms)",
            "https://elections.ny.gov/certification-offices-be-filled-november-3-2026-general-election"),
    },
    "OH": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; on the Nov 3 2026 official sample ballot",
            "https://www.ohiosos.gov/assets/dir2026-45-official-sample-ballot-november-3-2026.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "one vote for 'Governor and Lieutenant Governor' on the 2026 sample ballot",
            "https://www.ohiosos.gov/assets/dir2026-45-official-sample-ballot-november-3-2026.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022; 'For Attorney General' on 2026 sample ballot",
            "https://www.ohiosos.gov/assets/dir2026-45-official-sample-ballot-november-3-2026.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022; 'For Secretary of State' on 2026 sample ballot",
            "https://www.ohiosos.gov/assets/dir2026-45-official-sample-ballot-november-3-2026.pdf"),
        "upper": ("Senate", 33, 17,
            "the 17 odd-numbered districts (4-year staggered terms, Ohio Const. art. II, s2)",
            "https://codes.ohio.gov/ohio-constitution/section-2.2"),
        "lower": ("House of Representatives", 99, 99,
            "all (2-year terms, Ohio Const. art. II, s2)",
            "https://www.ohiosos.gov/assets/candidate-requirement-guide-2026.pdf"),
    },
    "OK": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; listed on the State Election Board's 2026 general election notice",
            "https://oklahoma.gov/elections/voters/military-overseas-voters/2026-election-notice-general-election.html"),
        "lt": ("elected", True,
            "elected separately from the governor; 4-year term; last elected 2022",
            "https://oklahoma.gov/elections/voters/military-overseas-voters/2026-election-notice-general-election.html"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://oklahoma.gov/elections/voters/military-overseas-voters/2026-election-notice-general-election.html"),
        "sos": ("appointed", False,
            "appointed by the governor with Senate consent for a term concurrent with the governor's (Okla. Const. art. VI, s1(B))",
            "https://oksenate.gov/sites/default/files/2022-05/oc6.pdf"),
        "upper": ("Senate", 48, 24,
            "the 24 even-numbered districts (regular); District 17 also has a special election for an unexpired term",
            "https://oklahoma.gov/content/dam/ok/en/elections/candidate-filing-archives/2026-candidate-filing-archives/2026-candidate-list-book.pdf"),
        "lower": ("House of Representatives", 101, 101,
            "all (2-year terms)",
            "https://oklahoma.gov/content/dam/ok/en/elections/candidate-filing-archives/2026-candidate-filing-archives/2026-candidate-list-book.pdf"),
    },
    "OR": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; listed as open for Nov 3 2026",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
        "lt": ("no-such-office", False,
            "Oregon has no lieutenant governor; the secretary of state is first in line of succession",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
        "ag": ("elected", False,
            "4-year term; last elected 2024; not on the 2026 open-offices list",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
        "sos": ("elected", False,
            "4-year term; last elected 2024; not on the 2026 open-offices list",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
        "upper": ("Senate", 30, 15,
            "districts 3, 4, 6, 7, 8, 10, 11, 13, 15, 16, 17, 19, 20, 24, 26",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
        "lower": ("House of Representatives", 60, 60,
            "all",
            "https://sos.oregon.gov/elections/Documents/open-offices-general-election.pdf"),
    },
    "PA": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; Department of State lists 'Governor/Lieutenant Governor' on the Nov 3 ballot",
            "https://www.pa.gov/agencies/dos/newsroom/secretary-reminds-eligible-pennsylvanians-of-oct--19-registratio"),
        "lt": ("elected-jointly-with-governor", True,
            "nominated separately in the primary, elected jointly with the governor by a single vote (Pa. Const. art. IV, s4)",
            "https://www.pa.gov/agencies/dos/newsroom/secretary-reminds-eligible-pennsylvanians-of-oct--19-registratio"),
        "ag": ("elected", False,
            "4-year term; last elected 2024 (presidential-year cycle)",
            "https://www.pa.gov/agencies/dos/newsroom/secretary-reminds-eligible-pennsylvanians-of-oct--19-registratio"),
        "sos": ("appointed", False,
            "the Secretary of the Commonwealth is appointed by the governor with Senate consent (Administrative Code of 1929, s207.1(d))",
            "https://www.legis.state.pa.us/WU01/LI/LI/US/HTM/1929/0/0175..HTM"),
        "upper": ("Senate", 50, 25,
            "the 25 even-numbered districts",
            "https://www.pa.gov/agencies/dos/newsroom/secretary-reminds-eligible-pennsylvanians-of-oct--19-registratio"),
        "lower": ("House of Representatives", 203, 203,
            "all",
            "https://www.pa.gov/agencies/dos/newsroom/secretary-reminds-eligible-pennsylvanians-of-oct--19-registratio"),
    },
    "RI": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://vote.sos.ri.gov/Forms/Elections/Guides/2026RunforOffice.pdf"),
        "lt": ("elected", True,
            "elected separately from the governor; 4-year term",
            "https://vote.sos.ri.gov/Forms/Elections/Guides/2026RunforOffice.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://vote.sos.ri.gov/Forms/Elections/Guides/2026RunforOffice.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://vote.sos.ri.gov/Forms/Elections/Guides/2026RunforOffice.pdf"),
        "upper": ("Senate", 38, 38,
            "all (2-year terms)",
            "https://www.sos.ri.gov/divisions/civics-and-education/your-government/offices-you-vote-for-in-rhode-island"),
        "lower": ("House of Representatives", 75, 75,
            "all (2-year terms)",
            "https://www.sos.ri.gov/divisions/civics-and-education/your-government/offices-you-vote-for-in-rhode-island"),
    },
    "SC": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://scvotes.gov/wp-content/uploads/2026/01/2026-Election-Calendar-Draft-scVOTES_.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "runs on a joint ticket with the governor; filed as 'Governor and Lieutenant Governor'",
            "https://scvotes.gov/wp-content/uploads/2026/01/RP0149-Filing-Fee-Schedule.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://scvotes.gov/wp-content/uploads/2026/01/2026-Election-Calendar-Draft-scVOTES_.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://scvotes.gov/wp-content/uploads/2026/01/2026-Election-Calendar-Draft-scVOTES_.pdf"),
        "upper": ("Senate", 46, 0,
            "none: all 46 serve 4-year terms elected in presidential years (last 2024)",
            "https://scvotes.gov/wp-content/uploads/2026/01/2026-Election-Calendar-Draft-scVOTES_.pdf"),
        "lower": ("House of Representatives", 124, 124,
            "all",
            "https://scvotes.gov/wp-content/uploads/2026/01/2026-Election-Calendar-Draft-scVOTES_.pdf"),
    },
    "SD": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
        "lt": ("elected-jointly-with-governor", True,
            "listed as 'Governor and Lieutenant Governor' on the 2026 general candidate list; running mate nominated at party convention",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
        "ag": ("elected", True,
            "4-year term; last elected 2022; nominated at party convention",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
        "upper": ("Senate", 35, 35,
            "all (2-year terms)",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
        "lower": ("House of Representatives", 70, 70,
            "all (2-year terms)",
            "https://vip.sdsos.gov/candidatelist.aspx?eid=774"),
    },
    "TN": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/Governor_Nov2026.pdf"),
        "lt": ("chosen-by-legislature", False,
            "the Speaker of the Senate, elected by the Senate, holds the title lieutenant governor",
            "https://www.capitol.tn.gov/senate/"),
        "ag": ("appointed", False,
            "appointed by the Tennessee Supreme Court for an 8-year term (Tenn. Const. art. VI, s5)",
            # The General Assembly's constitution PDF now answers "Page Not
            # Found" as HTML (audit 2026-10-17, LINKS-08). The Secretary of
            # State's 2023 printing of the constitution reads, art. VI, s.5:
            # "An Attorney General and Reporter for the State, shall be
            # appointed by the Judges of the Supreme Court and shall hold his
            # office for a term of eight years" (read 2026-10-17; the
            # courts' page cited before sits behind a browser check).
            "https://publications.tnsosfiles.com/pub/2023%20TN%20Constitution.pdf"),
        "sos": ("chosen-by-legislature", False,
            "chosen by joint vote of the General Assembly (Tenn. Const. art. III, s17)",
            # The same printing, art. III, s.17: "A Secretary of State shall
            # be appointed by joint vote of the General Assembly, and
            # commissioned during the term of four years" (read 2026-10-17).
            "https://publications.tnsosfiles.com/pub/2023%20TN%20Constitution.pdf"),
        "upper": ("Senate", 33, 17,
            "the 17 odd-numbered districts",
            "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/TNSenate_Nov2026.pdf"),
        "lower": ("House of Representatives", 99, 99,
            "all",
            "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/TNHouse_Nov2026.pdf"),
    },
    "TX": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.state.tx.us/elections/candidates/guide/2026/offices2026.shtml"),
        "lt": ("elected", True,
            "elected separately from the governor; 4-year term",
            "https://www.sos.state.tx.us/elections/candidates/guide/2026/offices2026.shtml"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://www.sos.state.tx.us/elections/candidates/guide/2026/offices2026.shtml"),
        "sos": ("appointed", False,
            "appointed by the governor with Senate consent (Tex. Const. art. IV, s21)",
            "https://statutes.capitol.texas.gov/Docs/CN/htm/CN.4.htm#4.21"),
        "upper": ("Senate", 31, 16,
            "districts 1, 2, 3, 4, 5, 9, 11, 13, 18, 19, 21, 22, 24, 26, 28, 31",
            "https://www.sos.state.tx.us/elections/candidates/guide/2026/offices2026.shtml"),
        "lower": ("House of Representatives", 150, 150,
            "all",
            "https://www.sos.state.tx.us/elections/candidates/guide/2026/offices2026.shtml"),
    },
    "UT": {
        "governor": ("elected", False,
            "4-year term; last elected 2024",
            "https://vote.utah.gov/2026-candidate-filings/"),
        "lt": ("elected-jointly-with-governor", False,
            "elected jointly with the governor (Utah Const. art. VII, s2); also the state's chief election officer",
            "https://le.utah.gov/xcode/Articlevii/UC_AVII_1800010118000101.pdf"),
        "ag": ("elected", False,
            "4-year term; last elected 2024",
            "https://vote.utah.gov/2026-candidate-filings/"),
        "sos": ("no-such-office", False,
            "Utah has no secretary of state; the lieutenant governor performs those duties",
            "https://le.utah.gov/xcode/Articlevii/UC_AVII_1800010118000101.pdf"),
        "upper": ("Senate", 29, 15,
            "districts 1, 5, 6, 7, 9, 11, 12, 13, 14, 18, 19, 20, 21, 23, 28",
            "https://vote.utah.gov/2026-candidate-filings/"),
        "lower": ("House of Representatives", 75, 75,
            "all",
            "https://vote.utah.gov/2026-candidate-filings/"),
    },
    "VA": {
        "governor": ("elected", False,
            "4-year term; elected in odd years, last 2025 (Va. Code s24.2-210)",
            "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
        "lt": ("elected", False,
            "elected separately; 4-year term; last elected 2025",
            "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
        "ag": ("elected", False,
            "4-year term; last elected 2025",
            "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
        "sos": ("appointed", False,
            "the Secretary of the Commonwealth is appointed by the governor (Va. Code s2.2-400)",
            "https://law.lis.virginia.gov/vacode/title2.2/chapter4/section2.2-400/"),
        "upper": ("Senate", 40, 0,
            "none: elected every four years from 1995 (2023, next 2027)",
            "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-214/"),
        "lower": ("House of Delegates", 100, 0,
            "none: 2-year terms elected in odd years from 1995 (last 2025)",
            "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-215/"),
    },
    "VT": {
        "governor": ("elected", True,
            "2-year term; last elected 2024",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
        "lt": ("elected", True,
            "elected separately from the governor; 2-year term",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
        "ag": ("elected", True,
            "2-year term; last elected 2024",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
        "sos": ("elected", True,
            "2-year term; last elected 2024",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
        "upper": ("Senate", 30, 30,
            "all (2-year terms)",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
        "lower": ("House of Representatives", 150, 150,
            "all (2-year terms)",
            "https://sos.vermont.gov/elections/election-info-resources/candidates"),
    },
    "WA": {
        "governor": ("elected", False,
            "4-year term; last elected 2024; not on the 2026 candidate certification",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
        "lt": ("elected", False,
            "elected separately from the governor; 4-year term; last elected 2024",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
        "ag": ("elected", False,
            "4-year term; last elected 2024",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
        "sos": ("elected", False,
            "4-year term; last elected 2024",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
        "upper": ("Senate", 49, 24,
            "legislative districts 6, 7, 8, 13, 15, 21, 26, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 42, 43, 44, 45, 46, 47, 48 (all 4-year terms)",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
        "lower": ("House of Representatives", 98, 98,
            "all (two positions in each of 49 districts)",
            "https://www.sos.wa.gov/sites/default/files/2026-05/Amended%202026%20Certification%20of%20Candidates%20to%20Primary%20Election.pdf"),
    },
    "WI": {
        "governor": ("elected", True,
            "4-year term; last elected 2022; incumbent filed noncandidacy",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
        "lt": ("elected-jointly-with-governor", True,
            "separate partisan primary, then a joint ticket with the governor in November (Wis. Const. art. V, s3)",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
        "ag": ("elected", True,
            "4-year term; last elected 2022",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022; incumbent filed noncandidacy",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
        "upper": ("Senate", 33, 17,
            "the 17 odd-numbered districts",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
        "lower": ("Assembly", 99, 99,
            "all (2-year terms)",
            "https://elections.wi.gov/sites/default/files/documents/D.%20Ballot%20Access%20Report%206.9.2026.pdf"),
    },
    "WV": {
        "governor": ("elected", False,
            "4-year term; last elected 2024; next election 2028",
            "https://sos.wv.gov/media/460/download?inline="),
        "lt": ("chosen-by-legislature", False,
            "the President of the Senate, elected by the Senate, holds the title lieutenant governor (W. Va. Code s6A-1-4)",
            "https://code.wvlegislature.gov/6A-1-4/"),
        "ag": ("elected", False,
            "4-year term; last elected 2024; next election 2028",
            "https://sos.wv.gov/media/460/download?inline="),
        "sos": ("elected", False,
            "4-year term; last elected 2024; next election 2028",
            "https://sos.wv.gov/media/460/download?inline="),
        "upper": ("Senate", 34, 17,
            "one of the two seats in each of the 17 districts (full terms); unexpired-term specials in Districts 3 and 17 also on the ballot",
            "https://sos.wv.gov/sites/default/files/2026-04/Running%20for%20Office.pdf"),
        "lower": ("House of Delegates", 100, 100,
            "all",
            "https://sos.wv.gov/sites/default/files/2026-04/Running%20for%20Office.pdf"),
    },
    "WY": {
        "governor": ("elected", True,
            "4-year term; last elected 2022",
            "https://sos.wyo.gov/Elections/Docs/2026/2026_Offices_Up_for_Election.pdf"),
        "lt": ("no-such-office", False,
            "Wyoming has no lieutenant governor; the secretary of state is first in succession",
            "https://sos.wyo.gov/Elections/Docs/2026/2026_Offices_Up_for_Election.pdf"),
        "ag": ("appointed", False,
            "appointed by the governor with Senate consent (Wyo. Stat. s9-1-601)",
            "https://wyoleg.gov/statutes/compress/title09.pdf"),
        "sos": ("elected", True,
            "4-year term; last elected 2022",
            "https://sos.wyo.gov/Elections/Docs/2026/2026_Offices_Up_for_Election.pdf"),
        "upper": ("Senate", 31, 16,
            "the 16 odd-numbered districts; District 6 also has an election for an unexpired term",
            "https://sos.wyo.gov/Elections/Docs/2026/2026_Offices_Up_for_Election.pdf"),
        "lower": ("House of Representatives", 62, 62,
            "all (2-year terms)",
            "https://sos.wyo.gov/Elections/Docs/2026/2026_Offices_Up_for_Election.pdf"),
    },
}

# The territories' governors, each from the territory's own record or the
# federal law that sets its elections (audit 2026-10-17, RACES-07): the
# governor2026 map called Guam, the Virgin Islands and the Northern Mariana
# Islands "not covered" while each elects its governor on November 3. Only
# the governor and lieutenant governor: the national associations list no
# territory's attorney general or secretary of state as an elected office
# this site covers. Checked 2026-10-17.
TERRITORIES = {
    "GU": {
        "governor": ("elected", True,
            "Elected with the lieutenant governor on one ticket at the general election "
            "every four years from 1974 (48 U.S.C. 1422); a runoff if no ticket wins a majority",
            "https://www.law.cornell.edu/uscode/text/48/1422"),
        "lt": ("elected-jointly-with-governor", True,
            "Elected on one ticket with the governor (48 U.S.C. 1422)",
            "https://www.law.cornell.edu/uscode/text/48/1422"),
    },
    "VI": {
        "governor": ("elected", True,
            "Elected with the lieutenant governor on one ticket at the general election "
            "every four years from 1974 (48 U.S.C. 1591); the Elections System's 2026 "
            "candidate listing names the tickets",
            "https://www.law.cornell.edu/uscode/text/48/1591"),
        "lt": ("elected-jointly-with-governor", True,
            "Elected on one ticket with the governor (48 U.S.C. 1591)",
            "https://www.law.cornell.edu/uscode/text/48/1591"),
    },
    "MP": {
        "governor": ("elected", True,
            "Three governor and lieutenant governor tickets on the Commonwealth Election "
            "Commission's certified 2026 list; each ticket is elected as a unit",
            "https://www.votecnmi.gov.mp/candidate/2026-certified-candidates-listing"),
        "lt": ("elected-jointly-with-governor", True,
            "Elected on one ticket with the governor, as the Commission's certified list says",
            "https://www.votecnmi.gov.mp/candidate/2026-certified-candidates-listing"),
    },
    "AS": {
        "governor": ("elected", False,
            "Elected in 2024 for a four-year term; the Election Office's 2026 midterm list "
            "holds only the Delegate to Congress and the House of Representatives",
            "https://www.aselectionoffice.gov/candidates-information/candidates-for-the-2026-midterm-election"),
        "lt": ("elected-jointly-with-governor", False,
            "Elected with the governor; not on the Election Office's 2026 midterm list",
            "https://www.aselectionoffice.gov/candidates-information/candidates-for-the-2026-midterm-election"),
    },
    "PR": {
        "governor": ("elected", False,
            "Elected at Puerto Rico's general election of November 2024 for a four-year "
            "term; the State Elections Commission holds no general election in 2026",
            "https://ww2.ceepur.org/sites/ComisionEE/es-pr/Secretaria/INFORME-ESTADISTICO-ELECCIONES-GENERALES-2024.pdf"),
        "lt": ("no-such-office", False,
            "Puerto Rico has no lieutenant governor; the secretary of state is first in succession",
            "https://ww2.ceepur.org/sites/ComisionEE/es-pr/Secretaria/INFORME-ESTADISTICO-ELECCIONES-GENERALES-2024.pdf"),
    },
}
TERRITORY_CODES = ("AS", "GU", "MP", "PR", "VI")

# When an office or chamber that is not on the 2026 ballot is next elected,
# where the state's own record says so (audit 2026-10-17, PERSONA-19): "No
# regular elections in 2026" left a reader to work out the year. Never
# computed from a term length - Virginia's governor was elected in 2025 and
# is next elected in 2029, its legislature in 2027 - so an entry without a
# year here shows none. {(state, office or chamber): (year, source) or
# (year, source, month)}; each source names the year, or the first year and
# the cycle that give it. The month is given only where the election is not
# in November (Louisiana's is in October), and the page then says "Next
# election", since a runoff may follow.
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
NEXT = {
    # Va. Code 24.2-210: "at the general election in November 1997, and
    # every fourth year thereafter"; 24.2-214 (Senate) "November 1995, and
    # every four years"; 24.2-215 (House of Delegates) "every two years".
    ("VA", "governor"): (2029, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
    ("VA", "lt"): (2029, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
    ("VA", "ag"): (2029, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-210/"),
    ("VA", "upper"): (2027, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-214/"),
    ("VA", "lower"): (2027, "https://law.lis.virginia.gov/vacode/title24.2/chapter2/section24.2-215/"),
    # N.J. Const. art. XI, s.III, para. 1: a governor elected "in the year
    # 1949 and every fourth year thereafter", with the lieutenant governor
    # "conjointly" (art. V, s.I, para. 4). The Senate runs a 2-4-4 cycle
    # (art. IV, s.II, para. 2: a two-year term after each census, then two
    # four-year terms), last elected in 2023 for the four-year term to
    # January 2028; the General Assembly serves two-year terms, last elected
    # in 2025. Both are next elected in 2027.
    ("NJ", "governor"): (2029, "https://www.njleg.state.nj.us/constitution"),
    ("NJ", "lt"): (2029, "https://www.njleg.state.nj.us/constitution"),
    ("NJ", "upper"): (2027, "https://www.njleg.state.nj.us/constitution"),
    ("NJ", "lower"): (2027, "https://www.njleg.state.nj.us/constitution"),
    # Kentucky's Election Schedule 2026-2036: the state officers in 2027.
    ("KY", "governor"): (2027, "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
    ("KY", "lt"): (2027, "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
    ("KY", "ag"): (2027, "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
    ("KY", "sos"): (2027, "https://elect.ky.gov/Resources/Documents/Election%20Schedule%202026-2036.pdf"),
    # Louisiana: the Secretary of State's 2027 elections calendar lists the
    # "Gubernatorial Primary" on October 9, 2027 and the "Gubernatorial
    # General" on November 20 (read 2026-10-17). La. Const. art. IV, s.3(A)
    # elects the governor, lieutenant governor, secretary of state and
    # attorney general "at the time and place of voting for members of the
    # legislature" (legis.la.gov/Legis/Law.aspx?d=206439, read 2026-10-17),
    # so the same election chooses all six. R.S. 18:402, cited here before,
    # names no year and no legislator (PR #94 review). October, not
    # November: a candidate with a majority is elected then.
    ("LA", "governor"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    ("LA", "lt"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    ("LA", "ag"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    ("LA", "sos"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    ("LA", "upper"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    ("LA", "lower"): (2027, "https://www.sos.la.gov/media/byfpyc5f/elections-calendar-2027.pdf", "October"),
    # Mississippi elects its governor, statewide officers and legislature
    # together in odd years; last 2023.
    ("MS", "governor"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    ("MS", "lt"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    ("MS", "ag"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    ("MS", "sos"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    ("MS", "upper"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    ("MS", "lower"): (2027, "https://www.sos.ms.gov/sites/default/files/publications/Election%20Calendar_2026.pdf"),
    # The Secretary of State's table of officeholders, with a "Next
    # Election" column.
    ("WV", "governor"): (2028, "https://sos.wv.gov/media/460/download?inline="),
    ("WV", "ag"): (2028, "https://sos.wv.gov/media/460/download?inline="),
    ("WV", "sos"): (2028, "https://sos.wv.gov/media/460/download?inline="),
}

# Offices on the ballot whose holder is not running for them, only where a
# cited source says so (audit 2026-10-17, STATEGOV-01): the constitution's
# term limit, read with the NGA's count of the governor's terms, or the
# election office's certified list for the office, which does not name them.
# Never inferred, and never from news: a term-limited officer may be on the
# ballot for another office, and a holder absent from a list that is not a
# candidate list is not "not running". {(state, office): (holder as the
# rosters name them, "term-limit" | "not-listed" | "listed", terms the limit
# needs or None, source, what the source is)}. "listed" is the other answer
# the same list gives: the holder is on it, for this office. stategov drops
# an entry, and says so, when the office's holder is someone else or the
# NGA counts fewer terms.
#
# An office on the ballot with no entry here is said to be unchecked, by
# name, on the page (``holder_status``): with an open-seat line beside
# Alaska's governor, silence beside Georgia's read as "Brian Kemp is
# running" (PR #94 review, rule 19). Checked 2026-10-17.
OPEN_SEATS = {
    ("AK", "governor"): ("Mike Dunleavy", "term-limit", 2,
        "https://ltgov.alaska.gov/information/alaskas-constitution/",
        "Alaska Const. art. III, s.5: no one elected for two full successive terms"),
    ("AK", "lt"): ("Nancy Dahlstrom", "not-listed", None,
        "https://www.elections.alaska.gov/candidates/?election=26genr",
        "the Division of Elections' certified 2026 general election tickets"),
    ("FL", "governor"): ("Ron DeSantis", "term-limit", 2,
        "http://www.leg.state.fl.us/statutes/index.cfm?submenu=3#A4S05",
        "Fla. Const. art. IV, s.5(b): no one who has served more than six years in two "
        "consecutive terms"),
    ("IA", "governor"): ("Kim Reynolds", "not-listed", None,
        "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf",
        "the Secretary of State's 2026 general election candidate list"),
    ("IA", "lt"): ("Chris Cournoyer", "not-listed", None,
        "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate%20List%20Database%20-%20All%20Elections_1.pdf",
        "the Secretary of State's 2026 general election candidate list"),
    ("MI", "governor"): ("Gretchen Whitmer", "term-limit", 2,
        "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-V-30",
        "Mich. Const. art. V, s.30: no one elected more than two times"),
    ("OH", "governor"): ("Mike DeWine", "term-limit", 2,
        "https://codes.ohio.gov/ohio-constitution/section-3.2",
        "Ohio Const. art. III, s.2: no one longer than two successive terms"),
    ("SC", "governor"): ("Henry McMaster", "term-limit", 2,
        "https://www.scstatehouse.gov/scconstitution/A04.pdf",
        "S.C. Const. art. IV, s.3: no one elected for more than two successive terms"),
    ("GU", "governor"): ("Lou Leon Guerrero", "term-limit", 2,
        "https://www.law.cornell.edu/uscode/text/48/1422",
        "48 U.S.C. 1422: no one elected for two full successive terms"),
    ("VI", "governor"): ("Albert Bryan", "term-limit", 2,
        "https://www.law.cornell.edu/uscode/text/48/1591",
        "48 U.S.C. 1591: no one elected for two full successive terms"),
    ("MP", "governor"): ("David M. Apatang", "not-listed", None,
        "https://www.votecnmi.gov.mp/candidate/2026-certified-candidates-listing",
        "the Commonwealth Election Commission's certified 2026 list"),
    ("MP", "lt"): ("Dennis Mendiola", "not-listed", None,
        "https://www.votecnmi.gov.mp/candidate/2026-certified-candidates-listing",
        "the Commonwealth Election Commission's certified 2026 list"),
    # Georgia's list of candidates on the November 3 ballot, the spreadsheet
    # in the zip this page links ("November 2026 Federal and State
    # Candidates.xlsx", read 2026-10-17): Governor Rick Jackson (R) and
    # Keisha Lance Bottoms (D); Lieutenant Governor Greg Dolezal (R) and
    # Josh McLaurin (D); Secretary of State Tim Fleming (R) and Penny Brown
    # Reynolds (D); Attorney General Brian Strickland (R) and Tanya Miller
    # (D). None of the four holders is on it (PERSONA-02).
    ("GA", "governor"): ("Brian Kemp", "not-listed", None,
        "https://sos.ga.gov/november-3-2026-general-election",
        "the Secretary of State's list of candidates on the November 3 ballot"),
    ("GA", "lt"): ("Burt Jones", "not-listed", None,
        "https://sos.ga.gov/november-3-2026-general-election",
        "the Secretary of State's list of candidates on the November 3 ballot"),
    ("GA", "ag"): ("Chris Carr", "not-listed", None,
        "https://sos.ga.gov/november-3-2026-general-election",
        "the Secretary of State's list of candidates on the November 3 ballot"),
    ("GA", "sos"): ("Brad Raffensperger", "not-listed", None,
        "https://sos.ga.gov/november-3-2026-general-election",
        "the Secretary of State's list of candidates on the November 3 ballot"),
    # California's Official Certified List of Candidates, dated August 27,
    # 2026 (read 2026-10-17): Governor Xavier Becerra and Steve Hilton;
    # Lieutenant Governor Fiona Ma and Gloria Romero (Eleni Kounalakis is
    # on it for Treasurer); Secretary of State Shirley N. Weber* and Attorney
    # General Rob Bonta*, starred as incumbents (STATEGOV-01, RACES-09).
    ("CA", "governor"): ("Gavin Newsom", "not-listed", None,
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
        "the Secretary of State's certified list of candidates"),
    ("CA", "lt"): ("Eleni Kounalakis", "not-listed", None,
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
        "the Secretary of State's certified list of candidates"),
    ("CA", "ag"): ("Rob Bonta", "listed", None,
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
        "the Secretary of State's certified list of candidates"),
    ("CA", "sos"): ("Shirley Weber", "listed", None,
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
        "the Secretary of State's certified list of candidates"),
    # Maine's 2026 General Candidate List (read 2026-10-17): its GOV rows are
    # Rick Bennett (Independent), Robert B. Charles (R) and Hannah M.
    # Pingree (D) (FRESHNESS-04).
    ("ME", "governor"): ("Janet Mills", "not-listed", None,
        "https://www.maine.gov/sos/sites/maine.gov.sos/files/inline-files/2026%20General%20Candidate%20List%20-%20FINAL.xlsx",
        "the Secretary of State's 2026 general election candidate list"),
}
OPEN_REASONS = ("term-limit", "not-listed", "listed")


class Ballot2026Error(ValueError):
    pass


def check(states=None, territories=None, next_=None, open_seats=None):
    """Every rule the tables must keep; raises with every breach at once."""
    states = STATES if states is None else states
    territories = TERRITORIES if territories is None else territories
    next_ = NEXT if next_ is None else next_
    open_seats = OPEN_SEATS if open_seats is None else open_seats
    problems = []
    if sorted(territories) != sorted(TERRITORY_CODES):
        problems.append(f"territories: {', '.join(sorted(territories))}, not "
                        f"{', '.join(TERRITORY_CODES)}")
    for code, entry in sorted(territories.items()):
        if sorted(entry) != ["governor", "lt"]:
            problems.append(f"{code}: a territory holds the governor and lieutenant governor only")
            continue
        problems.extend(_office_problems(code, entry))
    every = dict(states, **territories)
    for (code, key), value in sorted(next_.items()):
        item = _item(every.get(code), key)
        year, source, *rest = value
        if len(rest) > 1 or (rest and rest[0] not in MONTHS):
            problems.append(f"next {code} {key}: {rest!r} is not a month")
        if item is None:
            problems.append(f"next {code} {key}: no such office or chamber")
            continue
        if _is_up(key, item):
            problems.append(f"next {code} {key}: on the 2026 ballot, so no next year")
        if key in OFFICES and not item[0].startswith("elected"):
            problems.append(f"next {code} {key}: {item[0]}, not elected")
        if not isinstance(year, int) or not int(ELECTION[:4]) < year <= int(ELECTION[:4]) + 4:
            problems.append(f"next {code} {key}: {year!r} is not a year after 2026 within a term")
        problems.extend(_source_problems(code, f"next {key}", source))
    for (code, key), value in sorted(open_seats.items()):
        item = _item(every.get(code), key) if key in OFFICES else None
        holder, why, terms, source, cite = value
        if item is None:
            problems.append(f"open seat {code} {key}: no such office")
            continue
        if not item[1]:
            problems.append(f"open seat {code} {key}: the office is not on the 2026 ballot")
        if why not in OPEN_REASONS:
            problems.append(f"open seat {code} {key}: unknown reason {why!r}")
        if (why == "term-limit") != isinstance(terms, int):
            problems.append(f"open seat {code} {key}: a term limit needs the terms it counts, "
                            f"and nothing else does")
        if not holder or not cite:
            problems.append(f"open seat {code} {key}: no holder or no description of the source")
        problems.extend(_source_problems(code, f"open seat {key}", source))
    missing = sorted(set(STATE_CODES) - set(states))
    extra = sorted(set(states) - set(STATE_CODES))
    if missing:
        problems.append(f"no entry for {', '.join(missing)}")
    if extra:
        problems.append(f"not a state: {', '.join(extra)}")
    for code, entry in sorted(states.items()):
        problems.extend(_office_problems(code, entry))
        upper_seats, lower_seats = SEATS[code]
        for which, seats in (("upper", upper_seats), ("lower", lower_seats)):
            chamber = entry[which]
            if chamber is None:
                if seats:
                    problems.append(f"{code} {which}: missing")
                continue
            name, total, up, basis, source = chamber
            if total != seats:
                # Two sources of one count must agree (rule 53).
                problems.append(f"{code} {which}: {total} seats here, "
                                f"{seats} in government_maps.SEATS")
            if not 0 <= up <= total:
                problems.append(f"{code} {which}: {up} of {total} seats up")
            if not name or not basis:
                problems.append(f"{code} {which}: no name or basis")
            problems.extend(_source_problems(code, which, source))
    if problems:
        raise Ballot2026Error("; ".join(problems))
    return True


def _office_problems(code, entry):
    problems = []
    for office in OFFICES:
        if office not in entry:
            continue
        selection, up, note, source = entry[office]
        if selection not in SELECTIONS:
            problems.append(f"{code} {office}: unknown selection {selection!r}")
        if up and selection not in ("elected", "elected-jointly-with-governor"):
            problems.append(f"{code} {office}: {selection} yet on the ballot")
        problems.extend(_source_problems(code, office, source))
        if not note:
            problems.append(f"{code} {office}: no note")
    lt_sel, lt_up = entry["lt"][:2]
    if lt_sel == "elected-jointly-with-governor" and lt_up != entry["governor"][1]:
        problems.append(f"{code}: a joint ticket, but the lieutenant governor's "
                        f"election differs from the governor's")
    return problems


def _item(entry, key):
    """An office's or a chamber's tuple in *entry*, or None."""
    return (entry or {}).get(key) if key in OFFICES or key in ("upper", "lower") else None


def _is_up(key, item):
    return bool(item[1]) if key in OFFICES else bool(item[2])


def open_seat(code, key, holder=None, terms=None):
    """``(record, problem)``: what the page says about whether the holder of
    an office on the ballot is running for it, as OPEN_SEATS records it.

    Every office on the ballot with a named holder gets a record, so the
    page never leaves one office silent beside another that says "Open
    seat" (rule 19): ``why`` is "term-limit", "not-listed" or "listed" from
    a cited source, or "unchecked" where OPEN_SEATS has nothing, which the
    page says in words. None only when the office has no named holder.

    The entry is withheld, the record is "unchecked" and the problem says
    why, when the office's holder is not the person the entry names (they
    have left, or the rosters name someone else) or when the NGA counts
    fewer terms than the term limit needs: an open-seat line about the
    wrong person, or one the limit does not reach, is worse than none.
    """
    unchecked = ({"holder": holder, "why": "unchecked",
                  "text": f"Whether {holder} is running for this office is not checked here"}
                 if holder else None)
    value = OPEN_SEATS.get((code, key))
    if not value:
        return unchecked, None
    name, why, need, source, cite = value
    if holder != name:
        return unchecked, (f"{code} {key}: OPEN_SEATS names {name}, but the office's holder "
                           f"is {holder or 'not listed'}; the open-seat line is withheld")
    if why == "term-limit" and (terms or 0) < need:
        return unchecked, (f"{code} {key}: OPEN_SEATS says {name} is term-limited after "
                           f"{need} terms; the NGA counts {terms or 0}; the open-seat line "
                           f"is withheld")
    text = (f"{name} is term-limited" if why == "term-limit"
            else f"{name} is on the list of candidates for this office" if why == "listed"
            else f"{name} is not on the list of candidates for this office")
    return {"holder": name, "why": why, "text": text, "source": source, "cite": cite}, None


def _source_problems(code, field, source):
    parts = urllib.parse.urlsplit(source or "")
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return [f"{code} {field}: source is not a link: {source!r}"]
    if any(parts.netloc.endswith(host) for host in NOT_A_SOURCE):
        return [f"{code} {field}: {parts.netloc} is a compiled table, not a source"]
    return []


def for_state(code):
    """The page's record for *code*: a state's or a territory's, or ``{}``
    for D.C. A territory's holds its governor and lieutenant governor only.
    An office or chamber not up carries ``next`` where NEXT gives its year.
    Open seats are not here: they depend on who holds the office, which
    ``open_seat`` checks against the rosters."""
    entry = STATES.get(code) or TERRITORIES.get(code)
    if not entry:
        return {}
    out = {"offices": {}, "chambers": {}}
    for office in OFFICES:
        if office not in entry:
            continue
        selection, up, note, source = entry[office]
        out["offices"][office] = {"selection": selection, "up": up, "note": note,
                                  "source": source}
    for which in ("upper", "lower"):
        chamber = entry.get(which)
        if chamber is None:
            continue
        name, total, up, basis, source = chamber
        out["chambers"][which] = {"name": name, "seats": total, "up": up, "basis": basis,
                                  "source": source}
    for (state, key), (year, source, *month) in NEXT.items():
        if state != code:
            continue
        target = out["offices"].get(key) or out["chambers"].get(key)
        if target is not None:
            target["next"] = {"year": year, "source": source, **({"month": month[0]} if month else {})}
    if code in TERRITORIES:
        out["territory"] = True
    return out


def stats(states=None):
    """Counts for the build log and the page's headline: never typed in."""
    states = STATES if states is None else states
    out = {office: sum(1 for e in states.values() if e[office][1]) for office in OFFICES}
    chambers = [e[w] for e in states.values() for w in ("upper", "lower") if e[w]]
    out["chambers"] = len(chambers)
    out["chambersUp"] = sum(1 for c in chambers if c[2])
    out["seatsUp"] = sum(c[2] for c in chambers)
    return out
