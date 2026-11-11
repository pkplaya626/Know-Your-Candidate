"""The day the term the November 3, 2026 election chooses begins, for every
office kyc/ballot2026.py puts on that ballot (the January sweep of
2026-11-11, state-exec-past-inauguration).

Nothing in the build knew when a state office's new term began. The
rosters this site reads its holders from - the National Governors
Association's, the National Lieutenant Governors Association's, the
National Association of Secretaries of State's, the two parties'
associations of attorneys general - are read as they stand, and one that
lags an inauguration would have kept a former governor on the page as
governor, "In office since" the day they first took office, and Arizona's
"No one holds this office yet" over a lieutenant governor already sworn
in, with no warning (rule 16 for state executives).

Each record here is read from the jurisdiction's own constitution or code
on an official host - never NCSL, Ballotpedia or the Book of the States,
which were leads only (rule 50) - with the provision's words quoted as the
page gives them and the day read. A rule ("the first Monday in January") is
counted on the calendar and said to be counted (rule 84): ``check`` counts
every rule again and refuses a recorded day it does not give. One record
may cover every office of a jurisdiction where one provision sets them all.

A record's ``kind`` is "on" where the provision names the day the term
begins, and "by" where it names only the last day by which the officer must
qualify, the term running from then (Nevada's attorney general and
secretary of state): the page says "began no later than" that day, and
counts it as begun only from the day after.

An office on the ballot whose provision could not be read, or names no day
(Vermont's: the term "shall commence when they shall be chosen and
qualified"), is in ``GAPS`` with why, and has no day: a gap, never a guess.
"""

import datetime
import re
import urllib.parse

from . import ballot2026

READ = "2026-11-11"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
KINDS = ("on", "by")

LTGOV_AK = "https://ltgov.alaska.gov/information/alaskas-constitution/"
AZ_5_1 = "https://www.azleg.gov/const/5/1.htm"
FL_CONST = "https://www.flsenate.gov/Laws/Constitution"
HI_CONST = "https://lrb.hawaii.gov/constitution"
ID_4_1 = "https://legislature.idaho.gov/statutesrules/idconst/ArtIV/Sect1/"
IL_5 = "https://www.ilga.gov/commission/lrb/con5.htm"
MA_CONST = "https://malegislature.gov/Laws/Constitution"
MI_11_2 = "https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-Article-XI-2"
MN_CONST = "https://www.revisor.mn.gov/constitution/"
NE_17_5 = "https://nebraskalegislature.gov/laws/articles.php?article=XVII-5"
NV_223 = "https://www.leg.state.nv.us/NRS/NRS-223.html"
NV_224 = "https://www.leg.state.nv.us/NRS/NRS-224.html"
NV_225 = "https://www.leg.state.nv.us/NRS/NRS-225.html"
NV_228 = "https://www.leg.state.nv.us/NRS/NRS-228.html"
NV_282 = "https://www.leg.state.nv.us/NRS/NRS-282.html"
OH_3_2 = "https://codes.ohio.gov/ohio-constitution/section-3.2"
SC_4 = "https://www.scstatehouse.gov/scconstitution/A04.pdf"
SC_6 = "https://www.scstatehouse.gov/scconstitution/A06.pdf"
VT_CONST = "https://legislature.vermont.gov/statutes/constitution-of-the-state-of-vermont/"
CO_CONST = "https://leg.colorado.gov/sites/default/files/images/olls/crs2023-title-00.pdf"
IA_CONST = "https://www.legis.iowa.gov/docs/publications/ICP/1518288.pdf"
IA_39_8 = "https://www.legis.iowa.gov/docs/code/39.8.pdf"
IA_39_9 = "https://www.legis.iowa.gov/docs/code/39.9.pdf"
IA_1C_1 = "https://www.legis.iowa.gov/docs/code/1C.1.pdf"
KS_1_1 = "https://www.ksrevisor.gov/kanconst/093_001_0001.html"
ND_44_01 = "https://www.ndlegis.gov/cencode/t44c01.pdf"
OK_6 = "https://oksenate.gov/sites/default/files/2022-05/oc6.pdf"
PA_4_3 = "https://www.legis.state.pa.us/WU01/LI/LI/CT/HTM/00/00.004.003.000..HTM"
PA_4_4 = "https://www.legis.state.pa.us/WU01/LI/LI/CT/HTM/00/00.004.004.000..HTM"
RI_4 = "https://www.rilegislature.gov/riconstitution/Constitution/C04.aspx"
# The United States Code as the Government Publishing Office serves it
# (the organic acts of Guam and the Virgin Islands).
USC_48_1422 = "https://www.govinfo.gov/link/uscode/48/1422?type=usc&year=mostrecent&link-type=html"
USC_48_1591 = "https://www.govinfo.gov/link/uscode/48/1591?type=usc&year=mostrecent&link-type=html"

FIRST_MONDAY_JANUARY = ("nth", 1, "Monday", 1)

# Nevada's attorney general and secretary of state: NRS 282.010's last day
# to qualify, from which the term runs.
NV_282_QUOTES = (NV_282, (
    "All officers elected, except Senators and members of the Assembly, shall "
    "qualify, and execute and deliver their official bonds when required, as "
    "provided in this section, prior to the Tuesday after the first Monday in "
    "January ensuing their election.",
    "The term of office of all officers, elected or appointed, shall begin from the "
    "time of their qualification, unless some other express provision is made by "
    "law."))
NV_QUALIFY_WORDS = "prior to the Tuesday after the first Monday in January ensuing their election"


def _record(offices, rule, words, day, cite, sources, kind="on", read=READ, note="", at=""):
    return {"offices": tuple(offices), "rule": rule, "words": words, "day": day,
            "cite": cite, "sources": tuple(sources), "kind": kind, "read": read,
            **({"note": note} if note else {}), **({"at": at} if at else {})}


# {jurisdiction: (record, ...)}. A rule is ("day", month, day of month),
# ("nth", n, weekday, month) - the nth such weekday of the month - or
# ("after", weekday, rule): the first such weekday after the day the inner
# rule gives. A month from November on is in the election's year, any
# other in the next. Each source is (address, (the page's words, ...)).
TERMS = {
    "AK": (_record(("governor", "lt"), ("nth", 1, "Monday", 12),
                   "noon on the first Monday in December following his election",
                   "2026-12-07", "Alaska Const. art. III, ss.4 and 7",
                   ((LTGOV_AK, (
                       "The term of office of the governor is four years, beginning at noon on the "
                       "first Monday in December following his election and ending at noon on the "
                       "first Monday in December four years later.",
                       "He shall have the same qualifications as the governor and serve for the same "
                       "term.")),), at="noon"),),
    "AZ": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   # The span ends before "1971": the page shows it in quotation
                   # marks after "counted from", where a 1971 read as this term's
                   # (the second reader, 2026-11-11).
                   "beginning on the first Monday of January",
                   "2027-01-04", "Ariz. Const. art. 5, s.1(A)",
                   ((AZ_5_1, (
                       "The executive department shall consist of the governor, lieutenant governor, "
                       "secretary of state, attorney general, state treasurer and superintendent of "
                       "public instruction, each of whom shall hold office for four years beginning on "
                       "the first Monday of January, 1971 next after the regular general election in "
                       "1970.",)),)),),
    "FL": (_record(("governor", "lt", "ag"), ("after", "Tuesday", FIRST_MONDAY_JANUARY),
                   "the first Tuesday after the first Monday in January of the succeeding year",
                   "2027-01-05", "Fla. Const. art. IV, ss.4(a) and 5(a)",
                   ((FL_CONST, (
                       "the electors shall choose a governor and a lieutenant governor and members of "
                       "the cabinet each for a term of four years beginning on the first Tuesday after "
                       "the first Monday in January of the succeeding year.",
                       "There shall be a cabinet composed of an attorney general, a chief financial "
                       "officer, and a commissioner of agriculture.")),)),),
    "HI": (_record(("governor", "lt"), ("nth", 1, "Monday", 12),
                   "noon on the first Monday in December next following the governor’s election",
                   "2026-12-07", "Haw. Const. art. V, ss.1 and 2",
                   ((HI_CONST, (
                       "The term of office of the governor shall begin at noon on the first Monday in "
                       "December next following the governor’s election",
                       "The lieutenant governor shall be elected at the same time, for the same term "
                       "and in the same manner as the governor")),), at="noon"),),
    "ID": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the first Monday in January next after his election",
                   "2027-01-04", "Idaho Const. art. IV, s.1",
                   ((ID_4_1, (
                       "a governor, lieutenant governor, secretary of state, state controller, state "
                       "treasurer, attorney general and superintendent of public instruction, each of "
                       "whom shall hold his office for four years beginning on the first Monday in "
                       "January next after his election",)),)),),
    "IL": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Monday", 1),
                   "the second Monday of January after their election",
                   "2027-01-11", "Ill. Const. art. V, ss.1 and 2",
                   ((IL_5, (
                       "The Executive Branch shall include a Governor, Lieutenant Governor, Attorney "
                       "General, Secretary of State, Comptroller and Treasurer elected by the electors "
                       "of the State.",
                       "These elected officers of the Executive Branch shall hold office for four years "
                       "beginning on the second Monday of January after their election")),)),),
    "MA": (_record(("governor", "lt"), ("after", "Thursday", ("nth", 1, "Wednesday", 1)),
                   "noon on the Thursday next following the first Wednesday in January",
                   "2027-01-07", "Mass. Const. amend. art. LXIV, s.1, as adopted by amend. art. LXXXII",
                   ((MA_CONST, (
                       "The terms of the governor and lieutenant-governor shall begin at noon on the "
                       "Thursday next following the first Wednesday in January succeeding their "
                       "election",)),), at="noon"),
           _record(("ag", "sos"), ("nth", 3, "Wednesday", 1),
                   "the third Wednesday in January succeeding their election",
                   "2027-01-20", "Mass. Const. amend. art. LXIV, s.1, as adopted by amend. art. LXXXII",
                   ((MA_CONST, (
                       "The terms of the secretary, treasurer and receiver-general, attorney general, "
                       "and auditor shall begin with the third Wednesday in January succeeding their "
                       "election",)),))),
    "MI": (_record(("governor", "lt", "ag", "sos"), ("day", 1, 1),
                   "twelve o'clock noon on the first day of January next succeeding their election",
                   "2027-01-01", "Mich. Const. art. XI, s.2",
                   ((MI_11_2, (
                       "The terms of office of elective state officers, members of the legislature and "
                       "justices and judges of courts of record shall begin at twelve o'clock noon on "
                       "the first day of January next succeeding their election",)),), at="noon"),),
    "MN": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the first Monday in January in each year",
                   "2027-01-04", "Minn. Const. art. VII, s.7, with art. V, ss.2 and 4",
                   ((MN_CONST, (
                       "The official year for the state of Minnesota commences on the first Monday in "
                       "January in each year and all terms of office terminate at that time.",
                       "The term of office for the governor and lieutenant governor is four years and "
                       "until a successor is chosen and qualified.",
                       "The term of office of the secretary of state, attorney general and state "
                       "auditor is four years and until a successor is chosen and qualified.")),)),),
    "NE": (_record(("governor", "lt", "ag", "sos"), ("after", "Thursday", ("nth", 1, "Tuesday", 1)),
                   "the first Thursday after the first Tuesday in January next succeeding their "
                   "election",
                   "2027-01-07", "Neb. Const. art. XVII, s.5",
                   ((NE_17_5, (
                       "Unless otherwise provided by this Constitution or by law the terms of all "
                       "elected officers shall begin on the first Thursday after the first Tuesday in "
                       "January next succeeding their election.",)),)),),
    "NV": (_record(("governor",), FIRST_MONDAY_JANUARY,
                   "the 1st Monday of January next succeeding his or her election",
                   "2027-01-04", "NRS 223.020 and 223.030",
                   ((NV_223, (
                       "shall hold office for the term of 4 years from the time of his or her "
                       "installment and until his or her successor shall be qualified.",
                       "The Governor shall take and subscribe to the official oath before the Chief "
                       "Justice or one of the associate justices of the Supreme Court on the 1st Monday "
                       "of January next succeeding his or her election.")),)),
           _record(("lt",), FIRST_MONDAY_JANUARY,
                   "the 1st Monday of January next succeeding his or her election",
                   "2027-01-04", "NRS 224.020 and 224.030",
                   ((NV_224, (
                       "The Lieutenant Governor shall be chosen at the general election of 1866, and "
                       "every 4th year thereafter, and shall hold office for the term of 4 years from "
                       "the time of his or her installment",
                       "The Lieutenant Governor shall take and subscribe to the official oath before "
                       "the Chief Justice or one of the associate justices of the Supreme Court on the "
                       "1st Monday of January next succeeding his or her election.")),)),
           # One record per office, each led by its own chapter (the page
           # links the first source), with NRS 282.010's day to qualify by.
           _record(("ag",), FIRST_MONDAY_JANUARY, NV_QUALIFY_WORDS,
                   "2027-01-04", "NRS 228.020 and 282.010",
                   ((NV_228, (
                       "The Attorney General shall be chosen at the general election of 1866, and every "
                       "4th year thereafter, and shall hold office for the term of 4 years from the "
                       "time of his or her installment",)),
                    NV_282_QUOTES),
                   kind="by"),
           _record(("sos",), FIRST_MONDAY_JANUARY, NV_QUALIFY_WORDS,
                   "2027-01-04", "NRS 225.020 and 282.010",
                   ((NV_225, (
                       "The Secretary of State shall be chosen at the general election of 1866, and "
                       "every 4th year thereafter, and shall hold office for the term of 4 years from "
                       "the time of his or her installment",)),
                    NV_282_QUOTES),
                   kind="by")),
    "OH": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Monday", 1),
                   "the second Monday of January",
                   "2027-01-11", "Ohio Const. art. III, s.2",
                   ((OH_3_2, (
                       "The governor, lieutenant governor, secretary of state, treasurer of state, and "
                       "attorney general shall hold their offices for four years commencing on the "
                       "second Monday of January, 1959.",)),)),),
    "SC": (_record(("governor", "lt", "ag", "sos"), ("after", "Wednesday", ("nth", 2, "Tuesday", 1)),
                   "noon on the first Wednesday following the second Tuesday in January next after "
                   "his election",
                   "2027-01-13", "S.C. Const. art. IV, ss.4 and 8(A); art. VI, s.7",
                   ((SC_4, (
                       "The term of office of the Governor shall be four years, beginning at noon on "
                       "the first Wednesday following the second Tuesday in January next after his "
                       "election",
                       "A Lieutenant Governor must be chosen at the same time, in the same manner, "
                       "continue in office for the same period, and be possessed of the same "
                       "qualifications as the Governor.")),
                    (SC_6, (
                       "There shall be elected by the qualified voters of the State a Secretary of "
                       "State, an Attorney General",
                       "who shall hold their respective offices for a term of four years, coterminous "
                       "with that of the Governor."))), at="noon"),),
    # The Colorado Revised Statutes 2023 as the Office of Legislative Legal
    # Services publishes them, the constitution in title 0.
    "CO": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Tuesday", 1),
                   "the second Tuesday of January in the year 1967, and each fourth year thereafter",
                   "2027-01-12", "Colo. Const. art. IV, s.1(1)",
                   ((CO_CONST, (
                       "The executive department shall include the governor, lieutenant governor, "
                       "secretary of state, state treasurer, and attorney general, each of whom shall "
                       "hold his office for the term of four years, commencing on the second Tuesday of "
                       "January in the year 1967, and each fourth year thereafter.",)),)),),
    "IA": (_record(("governor", "lt"), ("after", "Tuesday", ("nth", 2, "Monday", 1)),
                   "the Tuesday after the second Monday of January next after their election",
                   "2027-01-12", "Iowa Const. art. IV, s.15",
                   ((IA_CONST, (
                       "The official terms of the governor and lieutenant governor shall commence on "
                       "the Tuesday after the second Monday of January next after their election",)),)),
           # The secretary of state's day is the constitution's own (art. IV,
           # s.22, as rewritten by amendment 32 of 1972), which Iowa Code
           # 39.8 gives way to ("except when otherwise provided by the
           # Constitution"): January 1, never 39.8's January 2 (the review
           # of PR #230).
           _record(("sos",), ("day", 1, 1),
                   "the first day of January next after their election",
                   "2027-01-01", "Iowa Const. art. IV, s.22",
                   ((IA_CONST, (
                       "A secretary of state, an auditor of state and a treasurer of state shall be "
                       "elected by the qualified electors at the same time that the governor is "
                       "elected and for a four-year term commencing on the first day of January next "
                       "after their election",)),)),
           # The attorney general's term the constitution leaves to law with
           # no day (art. V, s.12), and Iowa Code 39.8 starts it on "the first
           # day of January following the election which is not a Sunday or
           # legal holiday"; 1C.1 makes January 1 New Year's Day, a legal
           # public holiday: in 2027, Saturday, January 2.
           _record(("ag",), ("not-sunday-or", ("day", 1, 1), ((1, 1),)),
                   "the first day of January following the election which is not a Sunday or legal "
                   "holiday",
                   "2027-01-02", "Iowa Code 39.8, 39.9 and 1C.1",
                   ((IA_39_8, (
                       "The term of office of all officers chosen at a general election for a full "
                       "term shall commence on the first day of January following the election which "
                       "is not a Sunday or legal holiday, except when otherwise provided by the "
                       "Constitution or by statute",)),
                    (IA_39_9, (
                       "The governor, lieutenant governor, secretary of state, auditor of state, "
                       "treasurer of state, secretary of agriculture, and attorney general shall be "
                       "elected for a term of four years",)),
                    (IA_1C_1, (
                       "The following are legal public holidays: 1. New Year’s Day, January 1.",)),
                    (IA_CONST, (
                       "The general assembly shall provide, by law, for the election of an attorney "
                       "general by the people, whose term of office shall be four years, and until his "
                       "successor is elected and qualifies.",))))),
    "KS": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Monday", 1),
                   "the second Monday of January next after their election",
                   "2027-01-11", "Kan. Const. art. 1, s.1",
                   ((KS_1_1, (
                       "The constitutional officers of the executive department shall be the governor, "
                       "lieutenant governor, secretary of state, and attorney general",
                       "such officers elected in 1974 and thereafter shall have terms of four years "
                       "which shall begin on the second Monday of January next after their "
                       "election")),)),),
    "ND": (_record(("ag", "sos"), ("day", 1, 1),
                   "the first day of January next succeeding their election",
                   "2027-01-01", "N.D. Cent. Code 44-01-03",
                   ((ND_44_01, (
                       "Except when otherwise specially provided, all state and district officers shall "
                       "qualify on the first day of January next succeeding their election and on said "
                       "first day of January shall enter upon the discharge of the duties of their "
                       "respective offices",)),)),),
    "OK": (_record(("governor", "lt", "ag"), ("nth", 2, "Monday", 1),
                   "the second Monday of January next after their election",
                   "2027-01-11", "Okla. Const. art. VI, s.4(A)",
                   ((OK_6, (
                       "The term of office of the Governor, Lieutenant Governor, State Auditor and "
                       "Inspector, Attorney General, State Treasurer, Commissioner of Labor and "
                       "Superintendent of Public Instruction shall be four (4) years from the second "
                       "Monday of January next after their election.",)),)),),
    "PA": (_record(("governor", "lt"), ("nth", 3, "Tuesday", 1),
                   "the third Tuesday of January next ensuing his election",
                   "2027-01-19", "Pa. Const. art. IV, ss.3 and 4",
                   ((PA_4_3, (
                       "The Governor shall hold his office during four years from the third Tuesday of "
                       "January next ensuing his election.",)),
                    (PA_4_4, (
                       "A Lieutenant Governor shall be chosen jointly with the Governor by the casting "
                       "by each voter of a single vote applicable to both offices, for the same term, "
                       "and subject to the same provisions as the Governor",)))),),
    "RI": (_record(("governor", "lt", "ag", "sos"), ("nth", 1, "Tuesday", 1),
                   "the first Tuesday of January next succeeding their election",
                   "2027-01-05", "R.I. Const. art. IV, s.1",
                   ((RI_4, (
                       "The governor, lieutenant governor, secretary of state, attorney general and "
                       "general treasurer shall be elected on the Tuesday after the first Monday in "
                       "November, quadrennially commencing A.D. 1994, and every four (4) years "
                       "thereafter, and shall severally hold their offices, subject to recall as "
                       "provided for herein, for four (4) years from the first Tuesday of January next "
                       "succeeding their election",)),)),),
    "GU": (_record(("governor", "lt"), FIRST_MONDAY_JANUARY,
                   "the first Monday of January following the date of election",
                   "2027-01-04", "48 U.S.C. 1422",
                   ((USC_48_1422, (
                       "The term of the elected Governor and Lieutenant Governor shall commence on the "
                       "first Monday of January following the date of election.",)),)),),
    "VI": (_record(("governor", "lt"), FIRST_MONDAY_JANUARY,
                   "the first Monday of January following the date of election",
                   "2027-01-04", "48 U.S.C. 1591",
                   ((USC_48_1591, (
                       "The term of the elected Governor and Lieutenant Governor shall commence on the "
                       "first Monday of January following the date of election.",)),)),),
}

# Offices on the 2026 ballot with no day here, and why: a gap, never a guess.
# Each is (why, the page that says so, or None where nothing was read). Read
# on 2026-11-11; a refusal or a page drawn by script concludes nothing (rule
# 8), so those offices wait for a person to read the provision by hand.
_NOT_READ = "this read found no official copy of the provision it could read"
_VT_49 = ("Vt. Const. ch. II, s.49 fixes no day: the term \"shall commence when they shall be "
          "chosen and qualified\"")
_GAPS_BY_STATE = {
    "AL": (_NOT_READ + " (the Alabama Legislature's constitution pages are drawn by script)", None),
    "AR": (_NOT_READ, None),
    "CA": (_NOT_READ + " (leginfo.legislature.ca.gov refused this site's request, HTTP 403)", None),
    "CT": (_NOT_READ, None),
    "DE": (_NOT_READ, None),
    "GA": (_NOT_READ + " (sos.ga.gov refused this site's request, HTTP 403); the leads say the "
           "governor is installed by the General Assembly, on no fixed day", None),
    "IN": (_NOT_READ, None),
    "MD": (_NOT_READ + " (msa.maryland.gov closed the connection)", None),
    "ME": (_NOT_READ + " (legislature.maine.gov closed the connection)", None),
    "MP": (_NOT_READ + " (the Law Revision Commission's constitution page is drawn by script)", None),
    "NH": (_NOT_READ, None),
    "NM": (_NOT_READ, None),
    "NY": (_NOT_READ + " (nysenate.gov refused this site's request, HTTP 403)", None),
    # The review of PR #230 read the page this read had not: the
    # constitution starts "all officers, except the Governor" on the first
    # Monday in January, and art. V, s.1 gives the governor's term no day.
    "OR": ("Or. Const. art. II, s.14 starts the duties of \"all officers, except the Governor\" on "
           "the first Monday in January following the election, and art. V, s.1 gives the "
           "governor's term of four years no day; this read found no provision for the governor's",
           "https://www.oregonlegislature.gov/bills_laws/Pages/OrConst.aspx"),
    "SD": (_NOT_READ + " (sdlegislature.gov's constitution pages are drawn by script)", None),
    "TN": (_NOT_READ + " (the Tennessee Code's official text is published on a commercial host; "
           "the leads cite two sections giving different days)", None),
    "TX": (_NOT_READ + " (statutes.capitol.texas.gov closed the connection)", None),
    "WI": ("Wis. Const. art. XIII, s.1 starts the political year on the first Monday of January; "
           "this read found no provision saying these terms begin with it",
           "https://docs.legis.wisconsin.gov/constitution/wi/000242/000013"),
    "WY": (_NOT_READ, None),
}
GAPS = {
    ("VT", "governor"): (_VT_49, VT_CONST),
    ("VT", "lt"): (_VT_49, VT_CONST),
    ("VT", "ag"): (_NOT_READ + " (Vt. Const. ch. II, s.49 covers the governor, lieutenant "
                   "governor and treasurer only)", VT_CONST),
    ("VT", "sos"): (_NOT_READ + " (Vt. Const. ch. II, s.49 covers the governor, lieutenant "
                    "governor and treasurer only)", VT_CONST),
}
for _code, _gap in _GAPS_BY_STATE.items():
    for _key in ballot2026.OFFICES:
        _entry = ballot2026.STATES.get(_code) or ballot2026.TERRITORIES.get(_code) or {}
        if _key in _entry and _entry[_key][1]:
            GAPS[(_code, _key)] = _gap


class TermsBeginError(ValueError):
    pass


def count(rule, election=ballot2026.ELECTION):
    """The day *rule* gives for the term the election of *election* chooses."""
    year = int(election[:4])
    kind = rule[0]
    if kind == "day":
        month, day = rule[1], rule[2]
        return datetime.date(year if month >= 11 else year + 1, month, day)
    if kind == "nth":
        n, weekday, month = rule[1], WEEKDAYS.index(rule[2]), rule[3]
        first = datetime.date(year if month >= 11 else year + 1, month, 1)
        return first + datetime.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    if kind == "after":
        base = count(rule[2], election)
        weekday = WEEKDAYS.index(rule[1])
        return base + datetime.timedelta(days=(weekday - base.weekday() - 1) % 7 + 1)
    if kind == "not-sunday-or":
        # The day the inner rule gives, or the first after it that is neither
        # a Sunday nor one of the (month, day) holidays named.
        day = count(rule[1], election)
        while day.weekday() == 6 or (day.month, day.day) in tuple(map(tuple, rule[2])):
            day += datetime.timedelta(days=1)
        return day
    raise TermsBeginError(f"unknown rule {rule!r}")


def counted(rule):
    """True where the day is counted on the calendar from a rule, not named."""
    return not (rule[0] == "day" or (rule[0] == "not-sunday-or" and count(rule) == count(rule[1])))


def begun_from(record):
    """The first day the term has certainly begun: the day itself; or the
    day after, for a "by" record (the last day the officer may qualify) and
    for a term that begins at noon (``at``), since a reader's day, or the
    build's in UTC, can reach the day hours before noon where the office
    sits (the review of PR #230: Alaska's noon on December 7 is 21:00 UTC)."""
    day = datetime.date.fromisoformat(record["day"])
    late = record["kind"] == "by" or record.get("at") == "noon"
    return day + datetime.timedelta(days=1) if late else day


def _fold(text):
    """Text compared as words: curly quotes straight, runs of space one."""
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def up_offices():
    """Every (jurisdiction, office) kyc/ballot2026.py puts on the 2026 ballot."""
    every = dict(ballot2026.STATES, **ballot2026.TERRITORIES)
    return sorted((code, key) for code, entry in every.items() for key in ballot2026.OFFICES
                  if key in entry and entry[key][1])


def problems(terms=None, gaps=None):
    """Every breach of the table's rules, as strings."""
    terms = TERMS if terms is None else terms
    gaps = GAPS if gaps is None else gaps
    found = []
    covered = {}
    for code, records in sorted(terms.items()):
        for record in records:
            for key in record["offices"]:
                if (code, key) in covered:
                    found.append(f"{code} {key}: two records")
                covered[(code, key)] = record
            try:
                day = count(record["rule"])
            except (TermsBeginError, ValueError, IndexError) as exc:
                found.append(f"{code} {record['offices']}: {exc}")
                continue
            if record["day"] != day.isoformat():
                found.append(f"{code} {record['offices']}: {record['day']} recorded; the rule "
                             f"counts {day.isoformat()}")
            if record["kind"] not in KINDS:
                found.append(f"{code} {record['offices']}: unknown kind {record['kind']!r}")
            if not record.get("cite") or not record.get("words"):
                found.append(f"{code} {record['offices']}: no citation or no words for the rule")
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", record.get("read") or ""):
                found.append(f"{code} {record['offices']}: no day read")
            if not record["sources"]:
                found.append(f"{code} {record['offices']}: no source")
            for source, quotes in record["sources"]:
                found.extend(_source_problems(code, record["offices"], source))
                if not quotes or not all(q and q.strip() for q in quotes):
                    found.append(f"{code} {record['offices']}: {source} quotes nothing")
            # The page prints `words` in quotation marks after "counted
            # from", so they are the provision's own words, a span of a quote
            # the record carries, never a paraphrase (rules 38 and 84; the
            # review of PR #230 found 19 of 24 paraphrased).
            quoted = [_fold(q) for _source, quotes in record["sources"] for q in quotes or ()]
            if record.get("words") and not any(_fold(record["words"]) in q for q in quoted):
                found.append(f"{code} {record['offices']}: the words {record['words']!r} are not "
                             f"the provision's: no quote holds them")
            # A term that begins at noon is begun only from the next day
            # (begun_from), so a provision that names noon says so here.
            noon = any("noon" in q for q in quoted)
            if noon != (record.get("at") == "noon"):
                found.append(f"{code} {record['offices']}: the provision "
                             f"{'names' if noon else 'does not name'} noon, the record "
                             f"{'does not' if noon else 'does'}")
    up = set(up_offices())
    for pair in sorted(set(covered) | set(gaps)):
        if pair not in up:
            found.append(f"{pair[0]} {pair[1]}: not on the 2026 ballot in kyc/ballot2026.py")
        if pair in covered and pair in gaps:
            found.append(f"{pair[0]} {pair[1]}: both a day and a gap")
    for pair in sorted(up - set(covered) - set(gaps)):
        found.append(f"{pair[0]} {pair[1]}: on the 2026 ballot with neither a day nor a gap")
    for pair, (why, source) in sorted(gaps.items()):
        if not why:
            found.append(f"{pair[0]} {pair[1]}: a gap without why")
        if source:
            found.extend(_source_problems(pair[0], (pair[1],), source))
    return found


def _source_problems(code, offices, source):
    parts = urllib.parse.urlsplit(source or "")
    if parts.scheme != "https" or not parts.netloc:
        return [f"{code} {offices}: source is not an https link: {source!r}"]
    if any(parts.netloc.endswith(host) for host in ballot2026.NOT_A_SOURCE + (
            "justia.com", "findlaw.com", "cornell.edu", "counselstack.com")):
        return [f"{code} {offices}: {parts.netloc} is not an official host"]
    return []


def check(terms=None, gaps=None):
    found = problems(terms, gaps)
    if found:
        raise TermsBeginError("; ".join(found))
    return True


def record_for(code, key, terms=None):
    """The record that covers *code*'s *key*, or None."""
    for record in (TERMS if terms is None else terms).get(code, ()):
        if key in record["offices"]:
            return record
    return None


def for_page(code, key, terms=None):
    """What the page holds of the day *key*'s new term begins: ``{"day",
    "from", "kind", "words", "counted", "cite", "source", "read"}``, or None
    for a gap. ``from`` is the first day the term has certainly begun, which
    the page compares with the reader's own day (rule 84)."""
    record = record_for(code, key, terms)
    if record is None:
        return None
    # `source` is the record's first, which names this office: a record
    # covering offices whose own provisions differ is one record per office
    # (Nevada's attorney general and secretary of state).
    return {"day": record["day"], "from": begun_from(record).isoformat(), "kind": record["kind"],
            "words": record["words"], "counted": counted(record["rule"]), "cite": record["cite"],
            "source": record["sources"][0][0], "read": record["read"]}


def gaps():
    """``[(code, key, why)]`` for the build log: offices with no day."""
    return [(code, key, why) for (code, key), (why, _source) in sorted(GAPS.items())]


# ------------------------------------------------ the holder past the term

# Who the rosters name for each office, in a sentence's opening words; an
# attorney general's is the association that lists them.
ROSTERS = {"governor": "The National Governors Association’s roster",
           "lt": "The National Lieutenant Governors Association’s roster",
           "sos": "The National Association of Secretaries of State’s roster"}
AG_ROSTERS = "The attorneys general associations’ rosters"
LEAVING = ("not-listed", "term-limit")
WHY_WORDS = {"not-listed": "who was not among the candidates for this office",
             "term-limit": "who was term-limited"}


def roster_words(key, holder):
    """The opening words naming the roster a holder of *key* comes from."""
    if key == "ag":
        return f"The {holder['listedBy']}’s roster" if holder.get("listedBy") else AG_ROSTERS
    return ROSTERS[key]


def outgoing(key, holder, status, read):
    """``{holder, why, roster, read}`` for a holder who will not hold the
    office past the term the 2026 election chooses - the election office's
    list did not print them, or a term limit stopped them (the holder line,
    ``stategov.holder_line``) - else None. *read*: the roster's day read."""
    if not status or status.get("why") not in LEAVING or not (holder or {}).get("name"):
        return None
    return {"holder": holder["name"], "why": status["why"], "roster": roster_words(key, holder),
            "read": read}


def begun(term, day):
    """Whether the term in *term* (``for_page``'s record) has begun by *day*
    (an ISO day or a date), as the page decides it on the reader's day."""
    if not term or not day:
        return False
    return str(day)[:10] >= term["from"]


def began_words(term):
    """ "began on Jan. 4, 2027, counted from “...”", the page's words
    (``KYC.stategov``'s ``beganWords``)."""
    from .official_share import date_words
    return (("began no later than " if term["kind"] == "by" else "began on ")
            + date_words(term["day"])
            + (f", counted from “{term['words']}”" if term.get("counted") else ""))


def past_term_text(key, item, day):
    """The sentence the page puts in place of the holder's "In office since"
    once the term the 2026 election chose has begun on *day* and the roster
    still names a holder who was not on the ballot for it (rule 19: what
    the roster says, when it was read, and the law's day); "" otherwise.
    ``KYC.stategov.pastTermText``, word for word."""
    from .official_share import date_words
    term = (item or {}).get("termBegins")
    gone = (item or {}).get("outgoing")
    if not gone or not begun(term, day):
        return ""
    office = ballot2026.TITLES[key].lower()
    # "Still" only of a read on or after the first day the term had
    # certainly begun (`from`): a read on the morning of a noon term, or on
    # a "by" record's last day to qualify, may precede it.
    still = "still lists" if gone["read"] >= term["from"] else "lists"
    # "The term the 2026 election chose", never "the governor elected on
    # Nov. 3": Guam's and the Virgin Islands' organic acts hold a runoff
    # fourteen days later where no ticket has a majority, and this site
    # reads no territory's result (the review of PR #230).
    return (f"The term the 2026 election chose for the {office} {began_words(term)} "
            f"({term['cite']}). {gone['roster']}, read {date_words(gone['read'])}, {still} "
            f"{gone['holder']}, {WHY_WORDS[gone['why']]}.")


def lagging(payload, today):
    """Every office whose new term has begun by *today* (the build's day)
    while its roster still names the holder who was not on the ballot for
    it, or, for an office no one held before (Arizona's lieutenant
    governor), still lists no one: what the build warns of
    (``holder-past-inauguration``), never an error, so a lagging roster
    never stops the refresh's other data (rule 8)."""
    out = []
    sources = (payload or {}).get("sources") or {}
    for code, entry in sorted(((payload or {}).get("states") or {}).items()):
        offices = (entry.get("ballot2026") or {}).get("offices") or {}
        for key, item in sorted(offices.items()):
            term = item.get("termBegins")
            if not item.get("up") or not begun(term, today):
                continue
            title = ballot2026.TITLES[key].lower()
            when = (f"the term the 2026 election chose {began_words(term)} ({term['cite']})")
            gone = item.get("outgoing")
            if gone:
                out.append(f"{code} {title}: {gone['roster'][0].lower()}{gone['roster'][1:]}, "
                           f"read {gone['read']}, still names {gone['holder']} "
                           f"({gone['why']}); {when}")
            elif key == "lt" and (entry.get("lt") or {}).get("none"):
                read = (sources.get("nlga") or ["", "", ""])[2]
                out.append(f"{code} {title}: the National Lieutenant Governors Association’s "
                           f"roster, read {read}, lists none; {when}")
    return out


# From this day an office in GAPS whose holder is leaving may already be past
# its new term's first day, which nobody here has read: most of the dated
# terms begin in January's first three weeks (the review of PR #230).
UNREAD_FROM = "2027-01-01"


def unread(payload, today):
    """Every office in ``GAPS`` whose roster names a holder who was not on
    the ballot for the term the 2026 election chose (``outgoing``), once
    *today* (the build's day) is ``UNREAD_FROM`` or later: what the build
    warns of (``term-day-unread``), so a person reads the provision. No page
    words and no guess: without a day, the page says nothing of the term."""
    if not today or str(today)[:10] < UNREAD_FROM:
        return []
    out = []
    for code, entry in sorted(((payload or {}).get("states") or {}).items()):
        offices = (entry.get("ballot2026") or {}).get("offices") or {}
        for key, item in sorted(offices.items()):
            gone = item.get("outgoing")
            if not item.get("up") or item.get("termBegins") or not gone:
                continue
            why = (GAPS.get((code, key)) or ("no record in kyc/terms_begin.py", None))[0]
            out.append(f"{code} {ballot2026.TITLES[key].lower()}: no day read for the term the "
                       f"2026 election chose ({why}); {gone['roster'][0].lower()}"
                       f"{gone['roster'][1:]}, read {gone['read']}, names {gone['holder']} "
                       f"({gone['why']})")
    return out
