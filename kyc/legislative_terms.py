"""The day the term of the members elected on November 3, 2026 begins, for
every legislative chamber kyc/ballot2026.py puts on that ballot.

The legislators this site shows - the legislature pages, the state pages'
chamber counts and control (rule 54), Your ballot's seats, the search -
come from Open States (data/state_legislators.json, ``statelegs``), which
seats members-elect only when it next updates, often weeks late. On
2026-11-15 the Florida Senate listed "Senator Ashley Viola Gantt" in
District 34 and the Florida House's 2026-2028 list held Audrey Gibson in
District 13, while this site still showed Shevrin Jones and Angie Nixon
there: Florida's members "take office upon election" (Fla. Const. art.
III, s.15(d)), and nothing on the site knew when any legislature's new term
began (rules 16 and 19 for state legislators).

Each record here is read from the state's own constitution or code on an
official host - never NCSL, Ballotpedia, Cornell or Justia, which were
leads only (rules 48 and 50) - asked as this project (rule 103), with the
provision's words quoted as the page gives them and the day read. Its
shape is ``kyc/terms_begin.py``'s: a rule counted on the calendar and
``check`` counting it again, ``kind`` "on" where the provision names the
day the term begins and "by" where it names only the latest day it can
(Colorado's members begin "on the convening of the first regular session",
which meets "no later than the second Wednesday of January"). Two more
rules: ``("election", 0)``, the election day itself (Florida's "upon
election", Hawaii's "the day of the general election at which elected"),
and ``("election", 1)``, the day after it. A term that begins with the
election has certainly begun only from the next day, since the polls close
that evening, as a noon term has (``terms_begin.begun_from``).

Where a chamber's terms are staggered, the record is of the seats on the
2026 ballot: the other seats' members serve on. A hold-over clause ("and
until their successors are elected and qualified") is not a start day and
gives none. A chamber whose provision could not be read, or that names no
day, is in ``GAPS`` with why and the address a person should read: a gap,
never a guess.
"""

import datetime
import re

from . import ballot2026, terms_begin
from .terms_begin import _fold

READ = "2026-11-25"
KINDS = terms_begin.KINDS
CHAMBERS = ("upper", "lower")

AK_CONST = "https://ltgov.alaska.gov/information/alaskas-constitution/"
AK_24_05 = ("https://www.akleg.gov/basis/statutes.asp?media=print&secStart=24.05.080"
            "&secEnd=24.05.100")
AL_CONST = terms_begin.AL_CONST
CO_CONST = terms_begin.CO_CONST
CT_CONST = terms_begin.CT_CONST
DE_2 = "https://delcode.delaware.gov/constitution/constitution-03.html"
FL_CONST = terms_begin.FL_CONST
HI_CONST = terms_begin.HI_CONST
IA_CONST = terms_begin.IA_CONST
IA_39_8 = terms_begin.IA_39_8
IA_1C_1 = terms_begin.IA_1C_1
ID_3_3 = "https://legislature.idaho.gov/statutesrules/idconst/ArtIII/Sect3/"
KS_2_2 = "https://www.ksrevisor.gov/kanconst/093_002_0002.html"
KY_30 = "https://apps.legislature.ky.gov/Law/Constitution/Constitution/ViewConstitution?rsn=34"
MA_CONST = terms_begin.MA_CONST
MD_CONST = terms_begin.MD_CONST
MI_11_2 = terms_begin.MI_11_2
MN_CONST = terms_begin.MN_CONST
MT_5_2_102 = ("https://mca.legmt.gov/bills/mca/title_0050/chapter_0020/part_0010/section_0020/"
              "0050-0020-0010-0020.html")
NC_2 = "https://www.ncleg.gov/Laws/Constitution/Article2"
ND_4 = "https://www.ndlegis.gov/constit/a04.pdf"
NM_CONST = terms_begin.NM_CONST
NV_CONST = "https://www.leg.state.nv.us/Const/NvConst.html"
NY_PBO_4 = terms_begin.NY_PBO_4
OH_2_2 = "https://codes.ohio.gov/ohio-constitution/section-2.2"
OR_CONST = "https://www.oregonlegislature.gov/bills_laws/Pages/OrConst.aspx"
PA_2_2 = "https://www.legis.state.pa.us/WU01/LI/LI/CT/HTM/00/00.002.002.000..HTM"
RI_4 = terms_begin.RI_4
SC_3 = "https://www.scstatehouse.gov/scconstitution/A03.pdf"
TX_CN_3 = "https://tcss.legis.texas.gov/resources/CN/pdf/CN.3.pdf"
TX_GV_301 = "https://tcss.legis.texas.gov/resources/GV/pdf/GV.301.pdf"
UT_6_3 = "https://le.utah.gov/xcode/ArticleVI/UC_AVI_S3_1800010118000101.html"
UT_6_4 = "https://le.utah.gov/xcode/ArticleVI/UC_AVI_S4_1800010118000101.html"
WA_44_04 = "https://app.leg.wa.gov/RCW/default.aspx?cite=44.04&full=true"
WA_CONST = "https://leg.wa.gov/media/o3fg0ey1/washington-state-constitution.pdf"

BOTH = CHAMBERS
ELECTION_DAY = ("election", 0)
DAY_AFTER = ("election", 1)
FIRST_DAY_JANUARY = ("day", 1, 1)
FIRST_DAY_DECEMBER = ("day", 12, 1)


def _record(chambers, rule, words, day, cite, sources, kind="on", read=READ, note="", at=""):
    return {"chambers": tuple(chambers), "rule": rule, "words": words, "day": day,
            "cite": cite, "sources": tuple(sources), "kind": kind, "read": read,
            **({"note": note} if note else {}), **({"at": at} if at else {})}


# {state: (record, ...)}. A rule is terms_begin's ("day", "nth", "after",
# "not-sunday-or"), or ("election", n): n days after the election day. Each
# source is (address, (the page's words, ...)). Every quote below was found
# on its page, asked as this project (kyc/agent.py), on READ.
TERMS = {
    # The constitution's fourth Monday stands "unless otherwise provided by
    # law", and AS 24.05.080 provides otherwise.
    "AK": (_record(BOTH, ("nth", 3, "Tuesday", 1), "the third Tuesday in January",
                   "2027-01-19", "AS 24.05.080; Alaska Const. art. II, s.3",
                   ((AK_24_05, (
                       "The term of each member of the legislature begins on the third Tuesday in "
                       "January.",)),
                    (AK_CONST, (
                       "Their terms begin on the fourth Monday of the January following election "
                       "unless otherwise provided by law.",)))),),
    "AL": (_record(BOTH, DAY_AFTER,
                   "on the day after the general election at which they are elected",
                   "2026-11-04", "Ala. Const. (2022) art. IV, s.46",
                   ((AL_CONST, (
                       "The terms of office of the senators and representatives shall commence on "
                       "the day after the general election at which they are elected, and expire on "
                       "the day after the general election held in the fourth year after their "
                       "election, except as otherwise provided in this Constitution.",)),),
                   note="The Legislature's printing of the recompiled Constitution of 2022 as "
                        "proposed (ratified November 8, 2022)."),),
    # The session that begins the term meets "no later than" the day: a "by"
    # record, begun for certain only from the next day.
    "CO": (_record(BOTH, ("nth", 2, "Wednesday", 1), "no later than the second Wednesday of January",
                   "2027-01-13", "Colo. Const. art. V, s.7",
                   ((CO_CONST, (
                       "The general assembly shall meet in regular session at 10 a.m. no later than "
                       "the second Wednesday of January of each year.",
                       "The term of service of the members of the general assembly shall begin on "
                       "the convening of the first regular session of the general assembly next "
                       "after their election.")),),
                   kind="by"),),
    "CT": (_record(BOTH, ("after", "Wednesday", ("nth", 1, "Monday", 1)),
                   "the Wednesday following the first Monday of the January next succeeding their "
                   "election",
                   "2027-01-06", "Conn. Const. art. III, s.10",
                   ((CT_CONST, (
                       "The members of the general assembly shall hold their offices from the "
                       "Wednesday following the first Monday of the January next succeeding their "
                       "election until the Wednesday after the first Monday of the third January "
                       "next succeeding their election, and until their successors are duly "
                       "qualified.",)),)),),
    "DE": (_record(BOTH, DAY_AFTER, "on the day next after their election",
                   "2026-11-04", "Del. Const. art. II, s.3(e)",
                   ((DE_2, (
                       "The terms of Senators and Representatives begin on the day next after their "
                       "election.",)),)),),
    # "Upon election" names no calendar day but the election's: the record
    # is the election day, begun for certain from the next.
    "FL": (_record(BOTH, ELECTION_DAY, "upon election",
                   "2026-11-03", "Fla. Const. art. III, s.15(d)",
                   ((FL_CONST, (
                       "Members of the legislature shall take office upon election.",)),),
                   note="The provision ties the term to the election and to no calendar day or "
                        "hour."),),
    "HI": (_record(BOTH, ELECTION_DAY, "on the day of the general election at which elected",
                   "2026-11-03", "Haw. Const. art. III, s.4",
                   ((HI_CONST, (
                       "The term of a member of the legislature shall begin on the day of the "
                       "general election at which elected",)),)),),
    "IA": (_record(("lower",), FIRST_DAY_JANUARY, "the first day of January next after their election",
                   "2027-01-01", "Iowa Const. art. III, s.3",
                   ((IA_CONST, (
                       "The members of the house of representatives shall be chosen every second "
                       "year, by the qualified electors of their respective districts,",
                       "and their term of office shall commence on the first day of January next "
                       "after their election, and continue two years, and until their successors "
                       "are elected and qualified.")),)),
           # The constitution gives senators four years and no day (art.
           # III, s.5), so Iowa Code 39.8's day for every officer chosen at a
           # general election stands: January 1, 2027 is New Year's Day, a
           # legal public holiday (1C.1), so Saturday, January 2.
           _record(("upper",), ("not-sunday-or", FIRST_DAY_JANUARY, ((1, 1),)),
                   "the first day of January following the election which is not a Sunday or legal "
                   "holiday",
                   "2027-01-02", "Iowa Code 39.8 and 1C.1; Iowa Const. art. III, s.5",
                   ((IA_39_8, (
                       "The term of office of all officers chosen at a general election for a full "
                       "term shall commence on the first day of January following the election which "
                       "is not a Sunday or legal holiday, except when otherwise provided by the "
                       "Constitution or by statute",)),
                    (IA_1C_1, (
                       "The following are legal public holidays: 1. New Year’s Day, January 1.",)),
                    (IA_CONST, (
                       "Senators shall be chosen for the term of four years, at the same time and "
                       "place as representatives",))),
                   note="The constitution's own day, January 1, is for the House alone "
                        "(art. III, s.3).")),
    "ID": (_record(BOTH, FIRST_DAY_DECEMBER,
                   "from and after the first day of December next following the general election",
                   "2026-12-01", "Idaho Const. art. III, s.3",
                   ((ID_3_3, (
                       "The senators and representatives shall be elected for the term of two years, "
                       "from and after the first day of December next following the general "
                       "election.",)),)),),
    "KS": (_record(("lower",), ("nth", 2, "Monday", 1),
                   "the second Monday of January of the year following election",
                   "2027-01-11", "Kan. Const. art. 2, s.2",
                   ((KS_2_2, (
                       "The terms of representatives and senators shall commence on the second "
                       "Monday of January of the year following election.",)),)),),
    "KY": (_record(BOTH, FIRST_DAY_JANUARY,
                   "the first day of January of the year succeeding their election",
                   "2027-01-01", "Ky. Const. s.30",
                   ((KY_30, (
                       "The term of office of Representatives and Senators shall begin upon the "
                       "first day of January of the year succeeding their election.",)),)),),
    "MA": (_record(BOTH, ("nth", 1, "Wednesday", 1),
                   "the first Wednesday in January succeeding their election",
                   "2027-01-06", "Mass. Const. amend. art. LXIV, s.1, as adopted by amend. art. LXXXII",
                   ((MA_CONST, (
                       "The terms of senators and representatives shall begin with the first "
                       "Wednesday in January succeeding their election",)),)),),
    "MD": (_record(BOTH, ("nth", 2, "Wednesday", 1), "the second Wednesday of January following his "
                   "election",
                   "2027-01-13", "Md. Const. art. III, s.6",
                   ((MD_CONST, (
                       "A member of the General Assembly shall be elected by the registered voters of "
                       "the legislative or delegate district from which he seeks election, to serve "
                       "for a term of four years beginning on the second Wednesday of January "
                       "following his election.",)),)),),
    "MI": (_record(BOTH, FIRST_DAY_JANUARY,
                   "twelve o'clock noon on the first day of January next succeeding their election",
                   "2027-01-01", "Mich. Const. art. XI, s.2",
                   ((MI_11_2, (
                       "The terms of office of elective state officers, members of the legislature and "
                       "justices and judges of courts of record shall begin at twelve o'clock noon on "
                       "the first day of January next succeeding their election",)),), at="noon"),),
    "MN": (_record(BOTH, ("nth", 1, "Monday", 1), "the first Monday in January in each year",
                   "2027-01-04", "Minn. Const. art. VII, s.7, with art. IV, s.4",
                   ((MN_CONST, (
                       "The official year for the state of Minnesota commences on the first Monday in "
                       "January in each year and all terms of office terminate at that time.",
                       "Representatives shall be chosen for a term of two years, except to fill a "
                       "vacancy.")),)),),
    "MT": (_record(BOTH, ("nth", 1, "Monday", 1), "the first Monday of January following the election",
                   "2027-01-04", "Mont. Code Ann. 5-2-102",
                   ((MT_5_2_102, (
                       "The term of service begins on the first Monday of January following the "
                       "election.",)),)),),
    "NC": (_record(BOTH, FIRST_DAY_JANUARY, "the first day of January next after their election",
                   "2027-01-01", "N.C. Const. art. II, s.9",
                   ((NC_2, (
                       "The term of office of Senators and Representatives shall commence on the "
                       "first day of January next after their election.",)),)),),
    "ND": (_record(BOTH, FIRST_DAY_DECEMBER, "the first day of December following their election",
                   "2026-12-01", "N.D. Const. art. IV, s.7",
                   ((ND_4, (
                       "The terms of members of the legislative assembly begin on the first day of "
                       "December following their election.",)),)),),
    # Art. IV, s.4 names no day for members; art. XX, s.3 starts every state
    # officer's term on January 1, and art. IV, s.4 ends an appointee's on
    # December 31.
    "NM": (_record(("lower",), FIRST_DAY_JANUARY, "the first day of January next after the officer's "
                   "election",
                   "2027-01-01", "N.M. Const. art. XX, s.3, with art. IV, s.4",
                   ((NM_CONST, (
                       "The term of office of every state, county or district officer, except those "
                       "elected to fill vacancies, shall commence on the first day of January next "
                       "after the officer's election.",
                       "Such legislative appointments as provided in this section shall be for a "
                       "term ending on December 31, subsequent to the next succeeding general "
                       "election.")),)),),
    "NV": (_record(BOTH, DAY_AFTER, "from the day next after their election",
                   "2026-11-04", "Nev. Const. art. 4, ss.3 and 4",
                   ((NV_CONST, (
                       "their term of Office shall be two years from the day next after their "
                       "election.",
                       "their term of Office shall be four years from the day next after their "
                       "election.")),)),),
    # The constitution gives the terms two years and no day (art. III, s.2),
    # so Public Officers Law s.4(1) applies, as for the governor's.
    "NY": (_record(BOTH, FIRST_DAY_JANUARY, "the first day of January next after his election",
                   "2027-01-01", "N.Y. Pub. Off. Law s.4(1)",
                   ((NY_PBO_4, (
                       "The term of office of an elective officer, unless elected to fill a vacancy "
                       "then existing, shall commence on the first day of January next after his "
                       "election, if the commencement thereof be not otherwise fixed by law.",)),),
                   note="The constitution's art. III, s.2 gives senators and members of assembly "
                        "two years and no day."),),
    "OH": (_record(BOTH, FIRST_DAY_JANUARY, "the first day of January next after their election",
                   "2027-01-01", "Ohio Const. art. II, s.2",
                   ((OH_2_2, (
                       "their term of office shall commence on the first day of January next "
                       "thereafter and continue two years.",
                       "Senators shall be elected by the electors of the respective senate districts; "
                       "their terms of office shall commence on the first day of January next after "
                       "their election.")),)),),
    "OR": (_record(BOTH, ("nth", 2, "Monday", 1), "the second Monday in January following his election",
                   "2027-01-11", "Or. Const. art. IV, s.4(1)",
                   ((OR_CONST, (
                       "The term of each Senator and Representative shall commence on the second "
                       "Monday in January following his election, and shall continue for the full "
                       "period of four years or two years, as the case may be, unless a different "
                       "commencing day for such terms shall have been appointed by law.",)),),
                   note="This read found no law appointing a different commencing day."),),
    "PA": (_record(BOTH, FIRST_DAY_DECEMBER, "the first day of December next after their election",
                   "2026-12-01", "Pa. Const. art. II, s.2",
                   ((PA_2_2, (
                       "Their term of service shall begin on the first day of December next after "
                       "their election.",)),)),),
    "RI": (_record(BOTH, ("nth", 1, "Tuesday", 1),
                   "the first Tuesday of January next succeeding their election",
                   "2027-01-05", "R.I. Const. art. IV, s.1",
                   ((RI_4, (
                       "The senators and representatives in the general assembly shall be elected on "
                       "the Tuesday after the first Monday in November, biennially in even numbered "
                       "years, and shall severally hold their offices for two (2) years from the "
                       "first Tuesday of January next succeeding their election and until their "
                       "successors are elected and qualified.",)),)),),
    "SC": (_record(("lower",), ("after", "Monday", ELECTION_DAY), "the Monday following such election",
                   "2026-11-09", "S.C. Const. art. III, s.10",
                   ((SC_3, (
                       "The terms of office of the Senators and Representatives chosen at a general "
                       "election shall begin on the Monday following such election.",)),)),),
    # The day set by law is Gov't Code 301.001's, the session's: at noon, so
    # begun for certain only from the next day.
    "TX": (_record(BOTH, ("nth", 2, "Tuesday", 1), "the second Tuesday in January of each odd-numbered "
                   "year",
                   "2027-01-12", "Tex. Const. art. III, ss.3 and 4; Tex. Gov't Code 301.001",
                   ((TX_GV_301, (
                       "The legislature shall convene at the seat of government in regular session at "
                       "12 noon on the second Tuesday in January of each odd-numbered year.",)),
                    (TX_CN_3, (
                       "Senators shall take office following their election, on the day set by law "
                       "for the convening of the Regular Session of the Legislature,",
                       "Representatives shall take office following their election, on the day set "
                       "by law for the convening of the Regular Session of the Legislature,"))),
                   at="noon"),),
    "UT": (_record(("lower",), FIRST_DAY_JANUARY, "the first day of January next after their election",
                   "2027-01-01", "Utah Const. art. VI, s.3",
                   ((UT_6_3, (
                       "Their term of office shall be two years from the first day of January next "
                       "after their election.",)),)),
           _record(("upper",), FIRST_DAY_JANUARY, "the first day of January next after their election",
                   "2027-01-01", "Utah Const. art. VI, s.4",
                   ((UT_6_4, (
                       "Their term of office shall be four years from the first day of January next "
                       "after their election.",)),))),
    "WA": (_record(BOTH, ("nth", 2, "Monday", 1), "the second Monday in January following the date of "
                   "election",
                   "2027-01-11", "RCW 44.04.021",
                   ((WA_44_04, (
                       "The regular term of office of each senator and representative shall commence "
                       "on the second Monday in January following the date of election.",)),
                    (WA_CONST, (
                       "members of the house of representatives shall be elected biennially and their "
                       "term of office shall be two years",)))),),
}

# Chambers on the 2026 ballot with no day here, and why: a gap, never a
# guess. Each is (why, the page a person should read, or None). Read on
# READ, as this project; a refusal, a timeout or a page drawn by script
# concludes nothing (rule 8), so the why says what the server answered and
# never that the law has no day.
_AR = ("this read found no official copy of the Arkansas Constitution it could read: the Arkansas "
       "Legislature's constitution PDF answered HTTP 500, as on 2026-11-11 (kyc/terms_begin.py), and "
       "its Arkansas Law page links the Code and the Constitution only to LexisNexis, a commercial "
       "host. A person should read Ark. Const. art. 5 on an official copy",
       "https://www.arkleg.state.ar.us/assembly/Summary/ArkansasConstitution1874.pdf")
_AZ = ("Ariz. Const. art. 4, pt. 2, s.21 gives the members two-year terms and no day (the first "
       "legislature held office \"until the first Monday in January, 1913\"), and A.R.S. 41-1101 "
       "sets only the session's day; this read found no provision that starts the term",
       "https://www.azleg.gov/const/4/21.p2.htm")
_CA = ("leginfo.legislature.ca.gov answered this site's request for Article IV with a Cloudflare "
       "challenge page (\"Just a moment...\", HTTP 403). A person should read Cal. Const. art. IV, "
       "s.2 there",
       "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=CONS&division=&"
       "title=&part=&chapter=&article=IV")
_GA = ("sos.ga.gov answered this site's request for the constitution with a Cloudflare challenge "
       "page on 2026-11-11 (kyc/terms_begin.py), the General Assembly's legis.ga.gov is drawn by "
       "script, and the Official Code of Georgia is on a commercial host. A person should read Ga. "
       "Const. art. III, s.II, para. V",
       "https://sos.ga.gov/sites/default/files/2023-08/Georgia%20Constitution%20-%20Electronic%20"
       "Version%20-%20January%252C%202023.pdf")
_IL = ("Ill. Const. art. IV, s.2 gives the members' terms in years and s.5 convenes the General "
       "Assembly on the second Wednesday of January; neither names the day a term begins, and this "
       "read did not look for a statute that does", "https://www.ilga.gov/commission/lrb/con4.htm")
_IN = ("iga.in.gov, where the Indiana Constitution and Code are published, answers a script with its "
       "app's empty page (kyc/terms_begin.py, 2026-11-11), so Ind. Const. art. 4, s.3 was not read. "
       "A person should read it at https://iga.in.gov/laws/constitution", None)
_ME = ("maine.gov answered this site's request with CloudFront's \"Request blocked\" page on "
       "2026-11-11, and lldc.mainelegislature.org refused this read's TLS handshake on this record's "
       "day. A person should read Me. Const. art. IV, pt. 1, s.2 and pt. 2, s.5 at "
       "https://lldc.mainelegislature.org/Open/Const/Versions/MeConst_2024_Amd.pdf", None)
_MO = ("Mo. Const. art. III, s.20 convenes the General Assembly on the first Wednesday after the "
       "first Monday in January and art. III, ss.2 and 5 give the members' terms in years; none names "
       "the day a term begins, and this read did not look for a statute that does",
       "https://revisor.mo.gov/main/ViewChapter.aspx?chapter=III&constit=y")
_NE = ("Neb. Const. art. III, s.7 gives the members four-year terms and no day, and art. XVII, s.5's "
       "day for \"all elected officers\" holds \"unless otherwise provided by this Constitution or by "
       "law\"; this read did not establish whether a law provides otherwise for the Legislature",
       "https://nebraskalegislature.gov/laws/articles.php?article=III-7")
_NH = ("nh.gov answered this site's request for the constitution 403 (\"Access Denied\") on "
       "2026-11-11 (kyc/terms_begin.py). A person should read N.H. Const. pt. II, arts. 3 and 25 at "
       "https://www.nh.gov/glance/state-constitution/", None)
_OK = ("oksenate.gov's constitution page answered this read with a Sucuri script check (\"You are "
       "being redirected...\"), so the address of Article V's file was not found. A person should read "
       "Okla. Const. art. V there", "https://oksenate.gov/oklahoma-state-constitution")
_SD = ("S.D. Const. art. III, s.6 gives the members two-year terms and no day, and this read did not "
       "look for a statute that does", "https://sdlegislature.gov/api/Statutes/0N-3-6.html")
_TN = ("the Secretary of State's printing of the Tennessee Constitution answered this read with "
       "CloudFront's \"Request blocked\" page (HTTP 403), and the Tennessee Code's free text is on a "
       "commercial host. A person should read Tenn. Const. art. II, ss.3 and 7 at "
       "https://publications.tnsosfiles.com/pub/2023%20TN%20Constitution.pdf", None)
_VT = ("Vt. Const. ch. II, s.7 meets the General Assembly \"biennially on the first Wednesday next "
       "after the first Monday of January\", which is a session's day, not a term's, and this read "
       "found no provision that starts the members' terms",
       "https://legislature.vermont.gov/statutes/constitution-of-the-state-of-vermont/")
_WI = ("Wis. Const. art. IV, ss.4 and 5 give the members' terms in years and no day, and Wis. Stat. "
       "13.02(1) convenes the Legislature on the first Monday of January \"to take the oath of "
       "office\", which is not a term's first day in its own words; this read found no provision "
       "that starts the term", "https://docs.legis.wisconsin.gov/statutes/statutes/13/I/02")
_WV = ("www.wvlegislature.gov and code.wvlegislature.gov did not answer this read (the connection "
       "timed out), so W. Va. Const. art. VI was not read. A person should read it at "
       "https://code.wvlegislature.gov/", None)
_WY = ("Wyo. Const. art. 3, s.2 and Title 28 name no day for the members' terms; art. 6, s.17 and "
       "Wyo. Stat. 22-2-107 seat \"all state and county officers elected at a general election\" on "
       "the first Monday in January, and this read does not take those words to cover legislators",
       "https://wyoleg.gov/statutes/compress/title28.pdf")
_GAPS_BY_STATE = {"AR": _AR, "AZ": _AZ, "CA": _CA, "GA": _GA, "IL": _IL, "IN": _IN, "ME": _ME,
                  "MO": _MO, "NE": _NE, "NH": _NH, "OK": _OK, "SD": _SD, "TN": _TN, "VT": _VT,
                  "WI": _WI, "WV": _WV, "WY": _WY}


def up_chambers():
    """Every (state, chamber) kyc/ballot2026.py puts on the 2026 ballot."""
    return sorted((code, which) for code, entry in ballot2026.STATES.items()
                  for which in CHAMBERS if entry.get(which) and entry[which][2])


GAPS = {pair: _GAPS_BY_STATE[pair[0]] for pair in up_chambers() if pair[0] in _GAPS_BY_STATE}


class LegislativeTermsError(ValueError):
    pass


def count(rule, election=ballot2026.ELECTION):
    """The day *rule* gives for the term the election of *election* chooses."""
    if rule[0] == "election":
        return datetime.date.fromisoformat(election) + datetime.timedelta(days=rule[1])
    if rule[0] == "after" and rule[2][0] == "election":
        base = count(rule[2], election)
        weekday = terms_begin.WEEKDAYS.index(rule[1])
        return base + datetime.timedelta(days=(weekday - base.weekday() - 1) % 7 + 1)
    return terms_begin.count(rule, election)


def counted(rule):
    """True where the day is counted on the calendar from a rule, not named:
    the election day itself is named; the day after it is counted."""
    if rule[0] == "election":
        return rule[1] != 0
    if rule[0] == "after":
        return True
    return terms_begin.counted(rule)


def begun_from(record):
    """The first day the term has certainly begun: terms_begin's rule (a "by"
    record, or a noon term, from the next day), and a term that begins with
    the election from the next day too, since the polls close that evening."""
    day = datetime.date.fromisoformat(record["day"])
    if record["rule"] == ELECTION_DAY:
        return day + datetime.timedelta(days=1)
    return terms_begin.begun_from(record)


def problems(terms=None, gaps=None):
    """Every breach of the table's rules, as strings."""
    terms = TERMS if terms is None else terms
    gaps = GAPS if gaps is None else gaps
    found = []
    covered = {}
    for code, records in sorted(terms.items()):
        for record in records:
            label = f"{code} {'/'.join(record.get('chambers') or ())}"
            for which in record.get("chambers") or ():
                if (code, which) in covered:
                    found.append(f"{code} {which}: two records")
                covered[(code, which)] = record
            try:
                day = count(record["rule"])
            except (terms_begin.TermsBeginError, ValueError, IndexError, TypeError) as exc:
                found.append(f"{label}: {exc}")
                continue
            if record.get("day") != day.isoformat():
                found.append(f"{label}: {record.get('day')} recorded; the rule counts "
                             f"{day.isoformat()}")
            if day.isoformat() < ballot2026.ELECTION:
                found.append(f"{label}: {day.isoformat()} is before the election")
            if record.get("kind") not in KINDS:
                found.append(f"{label}: unknown kind {record.get('kind')!r}")
            if not record.get("cite") or not record.get("words"):
                found.append(f"{label}: no citation or no words for the rule")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", record.get("read") or ""):
                found.append(f"{label}: no day read")
            if not record.get("sources"):
                found.append(f"{label}: no source")
            for source, quotes in record.get("sources") or ():
                found.extend(terms_begin._source_problems(code, record.get("chambers"), source))
                if not quotes or not all(q and q.strip() for q in quotes):
                    found.append(f"{label}: {source} quotes nothing")
            # The page prints `words` in quotation marks, so they are the
            # provision's own words, a span of a quote the record carries.
            quoted = [_fold(q) for _s, quotes in record.get("sources") or () for q in quotes or ()]
            if record.get("words") and not any(_fold(record["words"]) in q for q in quoted):
                found.append(f"{label}: the words {record['words']!r} are not the provision's: "
                             "no quote holds them")
            noon = any("noon" in q for q in quoted)
            if noon != (record.get("at") == "noon"):
                found.append(f"{label}: the provision {'names' if noon else 'does not name'} "
                             f"noon, the record {'does not' if noon else 'does'}")
    up = set(up_chambers())
    for pair in sorted(set(covered) | set(gaps)):
        if pair not in up:
            found.append(f"{pair[0]} {pair[1]}: not on the 2026 ballot in kyc/ballot2026.py")
        if pair in covered and pair in gaps:
            found.append(f"{pair[0]} {pair[1]}: both a day and a gap")
    for pair in sorted(up - set(covered) - set(gaps)):
        found.append(f"{pair[0]} {pair[1]}: on the 2026 ballot with neither a day nor a gap")
    for pair, gap in sorted(gaps.items()):
        why, source = gap if isinstance(gap, tuple) and len(gap) == 2 else ("", None)
        if not why:
            found.append(f"{pair[0]} {pair[1]}: a gap without why")
        if source:
            found.extend(terms_begin._source_problems(pair[0], (pair[1],), source))
    return found


def check(terms=None, gaps=None):
    found = problems(terms, gaps)
    if found:
        raise LegislativeTermsError("; ".join(found))
    return True


def record_for(code, which, terms=None):
    """The record that covers *code*'s *which* chamber, or None."""
    for record in (TERMS if terms is None else terms).get(code, ()):
        if which in record["chambers"]:
            return record
    return None


def for_page(code, which, terms=None):
    """What the page holds of the day *which*'s new term began: ``{"day",
    "from", "kind", "words", "counted", "cite", "source", "read"}``, or None
    for a gap or a chamber not on the ballot. ``from`` is the first day the
    term has certainly begun, which the page compares with the reader's own
    day (rule 84)."""
    record = record_for(code, which, terms)
    if record is None:
        return None
    return {"day": record["day"], "from": begun_from(record).isoformat(), "kind": record["kind"],
            "words": record["words"], "counted": counted(record["rule"]), "cite": record["cite"],
            "source": record["sources"][0][0], "read": record["read"]}


def gap_for(code, which, gaps=None):
    """``{"why", "source"}`` for a chamber on the ballot with no day, or None."""
    gap = (GAPS if gaps is None else gaps).get((code, which))
    return {"why": gap[0], "source": gap[1]} if gap else None


def stats(terms=None, gaps=None):
    """Counts for the build log: chambers with a day, by kind, and gaps."""
    terms = TERMS if terms is None else terms
    gaps = GAPS if gaps is None else gaps
    out = {"on": 0, "by": 0, "gaps": len(gaps)}
    for records in terms.values():
        for record in records:
            out[record["kind"]] += len(record["chambers"])
    return out


# ------------------------------------------------ the roster behind the term

def begun(term, day):
    """Whether the term in *term* (``for_page``'s record) has begun by *day*."""
    return terms_begin.begun(term, day)


def roster_behind(code, which, term, roster_read, current=None):
    """Whether the roster (Open States, read *roster_read*) may still list,
    for *code*'s *which* chamber, members whose terms ended when *term*
    began: always, once the term has begun, unless a person has recorded
    that the roster read on or after that day lists the new term's members
    (``overrides.LEGISLATURE_ROSTERS_CURRENT``, *current*) and the roster
    read now is no older than the one they looked at. Nothing in the
    roster's own records says when a member's term began (its people carry
    no dates), so a later read is no proof of a caught-up one (rule 19)."""
    if not term:
        return False
    from . import overrides
    current = overrides.LEGISLATURE_ROSTERS_CURRENT if current is None else current
    seen = current.get((code, which))
    if not seen:
        return True
    looked = seen.get("rosterRead") or ""
    return not (looked >= term["from"] and (roster_read or "")[:10] >= looked)


def current_problems(current=None, terms=None):
    """Every curated "caught up" entry that cannot stand: no evidence, a
    chamber with no day here, or a roster read before the term began."""
    from . import overrides
    current = overrides.LEGISLATURE_ROSTERS_CURRENT if current is None else current
    found = []
    for (code, which), seen in sorted(current.items()):
        term = for_page(code, which, terms)
        if term is None:
            found.append(f"{code} {which}: no day in kyc/legislative_terms.py for the term the "
                         "entry says the roster has caught up with")
            continue
        for field in ("rosterRead", "seen", "source", "day"):
            if not seen.get(field):
                found.append(f"{code} {which}: no {field}")
        if (seen.get("rosterRead") or "") < term["from"]:
            found.append(f"{code} {which}: the roster it looked at was read "
                         f"{seen.get('rosterRead') or 'on no day'}, before the term began "
                         f"({term['from']})")
    return found


def lagging(payload, today, roster_read):
    """``[(code, which, words)]``: every chamber whose new term has begun by
    *today* (the build's day) while the roster may still list members whose
    terms ended then - what validate warns of (``legislature-roster-behind``),
    never an error, so a lagging roster never stops the refresh (rule 8)."""
    out = []
    for code, entry in sorted(((payload or {}).get("states") or {}).items()):
        for which in CHAMBERS:
            chamber = entry.get(which) or {}
            term = chamber.get("termBegins")
            if not term or not begun(term, today) or not chamber.get("rosterBehind"):
                continue
            from .official_share import date_words
            out.append((code, which,
                        f"{code} {chamber.get('title') or which}: the term of the members elected "
                        f"on Nov. 3, 2026 {terms_begin.began_words(term)} ({term['cite']}); Open "
                        f"States' roster, read {date_words(roster_read[:10])}, may still list "
                        f"members whose terms ended then ({chamber.get('upSeats', 0)} of its "
                        f"{chamber.get('seats', 0)} seats were on that ballot); record the "
                        "chamber in overrides.LEGISLATURE_ROSTERS_CURRENT once a person has seen "
                        "the roster list the new term's members"))
    return out


def unknown(payload):
    """``[(code, which, why)]``: every chamber on the ballot with no day here,
    for validate (``legislature-term-unknown``)."""
    out = []
    for (code, which), (why, _source) in sorted(GAPS.items()):
        out.append((code, which, why))
    return out
