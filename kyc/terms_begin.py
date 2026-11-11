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


def _record(offices, rule, words, day, cite, sources, kind="on", read=READ, note=""):
    return {"offices": tuple(offices), "rule": rule, "words": words, "day": day,
            "cite": cite, "sources": tuple(sources), "kind": kind, "read": read,
            **({"note": note} if note else {})}


# {jurisdiction: (record, ...)}. A rule is ("day", month, day of month),
# ("nth", n, weekday, month) - the nth such weekday of the month - or
# ("after", weekday, rule): the first such weekday after the day the inner
# rule gives. A month from November on is in the election's year, any
# other in the next. Each source is (address, (the page's words, ...)).
TERMS = {
    "AK": (_record(("governor", "lt"), ("nth", 1, "Monday", 12),
                   "noon on the first Monday in December following the election",
                   "2026-12-07", "Alaska Const. art. III, ss.4 and 7",
                   ((LTGOV_AK, (
                       "The term of office of the governor is four years, beginning at noon on the "
                       "first Monday in December following his election and ending at noon on the "
                       "first Monday in December four years later.",
                       "He shall have the same qualifications as the governor and serve for the same "
                       "term.")),)),),
    "AZ": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the first Monday of January next after the regular general election",
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
                   "noon on the first Monday in December next following the election",
                   "2026-12-07", "Haw. Const. art. V, ss.1 and 2",
                   ((HI_CONST, (
                       "The term of office of the governor shall begin at noon on the first Monday in "
                       "December next following the governor’s election",
                       "The lieutenant governor shall be elected at the same time, for the same term "
                       "and in the same manner as the governor")),)),),
    "ID": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the first Monday in January next after the election",
                   "2027-01-04", "Idaho Const. art. IV, s.1",
                   ((ID_4_1, (
                       "a governor, lieutenant governor, secretary of state, state controller, state "
                       "treasurer, attorney general and superintendent of public instruction, each of "
                       "whom shall hold his office for four years beginning on the first Monday in "
                       "January next after his election",)),)),),
    "IL": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Monday", 1),
                   "the second Monday of January after the election",
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
                       "election",)),)),
           _record(("ag", "sos"), ("nth", 3, "Wednesday", 1),
                   "the third Wednesday in January succeeding the election",
                   "2027-01-20", "Mass. Const. amend. art. LXIV, s.1, as adopted by amend. art. LXXXII",
                   ((MA_CONST, (
                       "The terms of the secretary, treasurer and receiver-general, attorney general, "
                       "and auditor shall begin with the third Wednesday in January succeeding their "
                       "election",)),))),
    "MI": (_record(("governor", "lt", "ag", "sos"), ("day", 1, 1),
                   "twelve o'clock noon on the first day of January next succeeding the election",
                   "2027-01-01", "Mich. Const. art. XI, s.2",
                   ((MI_11_2, (
                       "The terms of office of elective state officers, members of the legislature and "
                       "justices and judges of courts of record shall begin at twelve o'clock noon on "
                       "the first day of January next succeeding their election",)),)),),
    "MN": (_record(("governor", "lt", "ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the first Monday in January, when the state's official year commences and all "
                   "terms of office terminate",
                   "2027-01-04", "Minn. Const. art. VII, s.7, with art. V, ss.2 and 4",
                   ((MN_CONST, (
                       "The official year for the state of Minnesota commences on the first Monday in "
                       "January in each year and all terms of office terminate at that time.",
                       "The term of office for the governor and lieutenant governor is four years and "
                       "until a successor is chosen and qualified.",
                       "The term of office of the secretary of state, attorney general and state "
                       "auditor is four years and until a successor is chosen and qualified.")),)),),
    "NE": (_record(("governor", "lt", "ag", "sos"), ("after", "Thursday", ("nth", 1, "Tuesday", 1)),
                   "the first Thursday after the first Tuesday in January next succeeding the election",
                   "2027-01-07", "Neb. Const. art. XVII, s.5",
                   ((NE_17_5, (
                       "Unless otherwise provided by this Constitution or by law the terms of all "
                       "elected officers shall begin on the first Thursday after the first Tuesday in "
                       "January next succeeding their election.",)),)),),
    "NV": (_record(("governor",), FIRST_MONDAY_JANUARY,
                   "the 1st Monday of January next succeeding the election, when the governor takes "
                   "the oath; the term runs from the governor's installment",
                   "2027-01-04", "NRS 223.020 and 223.030",
                   ((NV_223, (
                       "shall hold office for the term of 4 years from the time of his or her "
                       "installment and until his or her successor shall be qualified.",
                       "The Governor shall take and subscribe to the official oath before the Chief "
                       "Justice or one of the associate justices of the Supreme Court on the 1st Monday "
                       "of January next succeeding his or her election.")),)),
           _record(("lt",), FIRST_MONDAY_JANUARY,
                   "the 1st Monday of January next succeeding the election, when the lieutenant "
                   "governor takes the oath; the term runs from the installment",
                   "2027-01-04", "NRS 224.020 and 224.030",
                   ((NV_224, (
                       "The Lieutenant Governor shall be chosen at the general election of 1866, and "
                       "every 4th year thereafter, and shall hold office for the term of 4 years from "
                       "the time of his or her installment",
                       "The Lieutenant Governor shall take and subscribe to the official oath before "
                       "the Chief Justice or one of the associate justices of the Supreme Court on the "
                       "1st Monday of January next succeeding his or her election.")),)),
           _record(("ag", "sos"), FIRST_MONDAY_JANUARY,
                   "the officer's qualification, which must come before the Tuesday after the first "
                   "Monday in January",
                   "2027-01-04", "NRS 228.020, 225.020 and 282.010",
                   ((NV_228, (
                       "The Attorney General shall be chosen at the general election of 1866, and every "
                       "4th year thereafter, and shall hold office for the term of 4 years from the "
                       "time of his or her installment",)),
                    (NV_225, (
                       "The Secretary of State shall be chosen at the general election of 1866, and "
                       "every 4th year thereafter, and shall hold office for the term of 4 years from "
                       "the time of his or her installment",)),
                    (NV_282, (
                       "All officers elected, except Senators and members of the Assembly, shall "
                       "qualify, and execute and deliver their official bonds when required, as "
                       "provided in this section, prior to the Tuesday after the first Monday in "
                       "January ensuing their election.",
                       "The term of office of all officers, elected or appointed, shall begin from the "
                       "time of their qualification, unless some other express provision is made by "
                       "law."))),
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
                   "the election",
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
                       "with that of the Governor.")))),),
    # The Colorado Revised Statutes 2023 as the Office of Legislative Legal
    # Services publishes them, the constitution in title 0.
    "CO": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Tuesday", 1),
                   "the second Tuesday of January, every fourth year from 1967",
                   "2027-01-12", "Colo. Const. art. IV, s.1(1)",
                   ((CO_CONST, (
                       "The executive department shall include the governor, lieutenant governor, "
                       "secretary of state, state treasurer, and attorney general, each of whom shall "
                       "hold his office for the term of four years, commencing on the second Tuesday of "
                       "January in the year 1967, and each fourth year thereafter.",)),)),),
    "IA": (_record(("governor", "lt"), ("after", "Tuesday", ("nth", 2, "Monday", 1)),
                   "the Tuesday after the second Monday of January next after the election",
                   "2027-01-12", "Iowa Const. art. IV, s.15",
                   ((IA_CONST, (
                       "The official terms of the governor and lieutenant governor shall commence on "
                       "the Tuesday after the second Monday of January next after their election",)),)),
           # Iowa Code 39.8 starts every other full term on "the first day of
           # January following the election which is not a Sunday or legal
           # holiday", and 1C.1 makes January 1 New Year's Day, a legal
           # public holiday: in 2027, Saturday, January 2.
           _record(("ag", "sos"), ("not-sunday-or", ("day", 1, 1), ((1, 1),)),
                   "the first day of January following the election which is not a Sunday or legal "
                   "holiday (January 1 being New Year's Day, a legal public holiday)",
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
                       "The following are legal public holidays: 1. New Year’s Day, January 1.",))))),
    "KS": (_record(("governor", "lt", "ag", "sos"), ("nth", 2, "Monday", 1),
                   "the second Monday of January next after the election",
                   "2027-01-11", "Kan. Const. art. 1, s.1",
                   ((KS_1_1, (
                       "The constitutional officers of the executive department shall be the governor, "
                       "lieutenant governor, secretary of state, and attorney general",
                       "such officers elected in 1974 and thereafter shall have terms of four years "
                       "which shall begin on the second Monday of January next after their "
                       "election")),)),),
    "ND": (_record(("ag", "sos"), ("day", 1, 1),
                   "the first day of January next succeeding the election",
                   "2027-01-01", "N.D. Cent. Code 44-01-03",
                   ((ND_44_01, (
                       "Except when otherwise specially provided, all state and district officers shall "
                       "qualify on the first day of January next succeeding their election and on said "
                       "first day of January shall enter upon the discharge of the duties of their "
                       "respective offices",)),)),),
    "OK": (_record(("governor", "lt", "ag"), ("nth", 2, "Monday", 1),
                   "the second Monday of January next after the election",
                   "2027-01-11", "Okla. Const. art. VI, s.4(A)",
                   ((OK_6, (
                       "The term of office of the Governor, Lieutenant Governor, State Auditor and "
                       "Inspector, Attorney General, State Treasurer, Commissioner of Labor and "
                       "Superintendent of Public Instruction shall be four (4) years from the second "
                       "Monday of January next after their election.",)),)),),
    "PA": (_record(("governor", "lt"), ("nth", 3, "Tuesday", 1),
                   "the third Tuesday of January next ensuing the election",
                   "2027-01-19", "Pa. Const. art. IV, ss.3 and 4",
                   ((PA_4_3, (
                       "The Governor shall hold his office during four years from the third Tuesday of "
                       "January next ensuing his election.",)),
                    (PA_4_4, (
                       "A Lieutenant Governor shall be chosen jointly with the Governor by the casting "
                       "by each voter of a single vote applicable to both offices, for the same term, "
                       "and subject to the same provisions as the Governor",)))),),
    "RI": (_record(("governor", "lt", "ag", "sos"), ("nth", 1, "Tuesday", 1),
                   "the first Tuesday of January next succeeding the election",
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
GAPS = {
    ("VT", "governor"): ("Vt. Const. ch. II, s.49 fixes no day: the term \"shall commence when "
                         "they shall be chosen and qualified\"", VT_CONST),
    ("VT", "lt"): ("Vt. Const. ch. II, s.49 fixes no day: the term \"shall commence when they "
                   "shall be chosen and qualified\"", VT_CONST),
}


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
    """The first day the term has certainly begun: the day itself, or for a
    "by" record the day after the last day the officer may qualify."""
    day = datetime.date.fromisoformat(record["day"])
    return day + datetime.timedelta(days=1) if record["kind"] == "by" else day


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
    return {"day": record["day"], "from": begun_from(record).isoformat(), "kind": record["kind"],
            "words": record["words"], "counted": counted(record["rule"]), "cite": record["cite"],
            "source": record["sources"][0][0], "read": record["read"]}


def gaps():
    """``[(code, key, why)]`` for the build log: offices with no day."""
    return [(code, key, why) for (code, key), (why, _source) in sorted(GAPS.items())]
