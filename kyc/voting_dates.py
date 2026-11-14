"""Each jurisdiction's key dates for the November 3, 2026 election.

Seventeen days out, every state page offered "Register to vote" with no
word that most states' deadlines had passed, gave no early-voting or
mail-ballot date, and left Georgia's December 1 runoff and Louisiana's
December 12 House round off the voting block (audit 2026-10-17,
STATEGOV-11, PERSONA-03, FRESHNESS-11, VISUALS-25). ``kyc/voting.py``
deliberately typed no date, because a date typed from memory drifts.

So the dates are a hand-editable cache, ``data/voting_dates.json``, read
jurisdiction by jurisdiction from each election office's own pages,
calendars and statutes on 2026-10-17, and every value re-opened at its
source by a second researcher (``verified``). Each value the page shows
carries, in ``sources``, the official page's address and its words. A null
is a gap, never a guess, and the page says nothing where the record is
null: the state's own links stay beside it.

``check`` holds the cache to that:

- a value the page shows needs a source entry for its own field (a
  qualifier - a time of day, "postmarked", where same-day registration
  happens - may stand on its value's source), on the jurisdiction's own
  domains (``JURISDICTION_DOMAINS``) or an evidenced page elsewhere
  (``OFFICIAL_ELSEWHERE``): any .gov host is not enough, since another
  state's office, a county and a federal guide are all on .gov;
- "postmarked" and "received" must be said in a quote they stand on
  (``RULE_WORDS``), and where same-day registration happens is the office's
  own words, quoted (``where_problems``);
- a compiled table is a lead, never a source (rule 50): NCSL, Ballotpedia,
  Wikipedia, vote.gov, Vote.org and the like are refused wherever they
  appear;
- every date parses and falls in the cycle, windows run forwards, and no
  deadline falls after the election it is for: a runoff's own early voting
  and mail-ballot dates (``runoff.earlyVoting``, ``runoff.mail``) fall
  between November 3 and the runoff, but for a ballot still arriving after
  it, its own registration deadlines (``runoff.registration``) on or before
  it, and none stands without the runoff's date;
- a day the office says early voting is not held inside its window
  (``earlyVoting.except``, ``runoff.earlyVoting.except``: Louisiana's
  "excluding Sunday, November 29") is named, closed, in a quote it stands
  on (``closes``), and every day of a weekday the office closes as a class
  ("Excluding Sundays") is listed: on Sunday, October 25 the Louisiana,
  Delaware, South Carolina and Hawaii pages called early voting "Under way"
  on a day each office had excluded. A day the law closes as a state
  holiday is named so by two of the office's own quotes together
  (``closes_as_holiday``): one that closes state holidays ("Early voting
  shall not be held on state holidays", Arkansas's State Board of Election
  Commissioners), one that names the day a holiday (its Secretary of
  State's calendar moves Thursday, November 26's deadline to the Friday as
  falling on a legal holiday);
- a window held only in an office's regular hours ("during regular office
  hours": Arkansas's December 1 runoff, South Dakota's in-person absentee
  voting) says so in the office's words, quoted (``hours_problems``), and
  the page then calls it "Under way, during those hours", never "Under
  way" alone: on Saturday, November 28 a county clerk's office with no
  Saturday hours holds no early voting, and no office's words say which
  offices keep which hours;
- a qualifier that is a claim of its own is said in a quote it stands on
  (``SAID``): a runoff's early voting that may begin before its first date
  ("as soon as possible, but no later than"), an application taken in
  person alone ("over the counter"); and a line that says ballots
  "postmarked by" one day count if they arrive by another links a quote
  that says "postmarked" (``arrive_sources``), on the general election's
  line as on a runoff's;
- a December date the results reader also holds (``overrides.GENERAL_RUNOFFS``,
  ``OPEN_PRIMARY_SEATS``) must be the same date here (rule 53).

``for_page`` turns a record into the lines the page shows, in words, each
with its links; the page decides only what the reader's own calendar day
makes of each date (upcoming, today, passed), as ``KYC.electionStatus``
does. The researchers' notes stay in the cache for the next editor and are
never shown: they are a researcher's words, not the office's.
"""

import datetime
import json
import os
import re
import urllib.parse

from .normalize import US_STATES

CACHE_PATH = os.path.join("candidate_profiles_site", "data", "voting_dates.json")
ELECTION = "2026-11-03"
# Every date in the record falls between these: the cycle's registration
# windows open in the summer, and the last ballot counted arrives in
# December.
EARLIEST, LATEST = "2026-06-01", "2026-12-31"
# The day a source was read, where it was read after the record's own
# read and check ("read" on a source): Nevada's Secretary of State's page,
# which serves only a person's browser, was read by hand on 2026-10-25.
_ISO_DAY = re.compile(r"^2026-(?:0[6-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")

# Every jurisdiction with a state page: the fifty states, D.C. and the five
# territories.
JURISDICTIONS = frozenset(US_STATES.values())

# Compiled tables, and directories of other people's pages: leads, never
# the cited source (rule 50). vote.gov is a .gov site, so it is refused by
# name before any domain test could accept it.
COMPILED_HOSTS = ("ncsl.org", "ballotpedia.org", "wikipedia.org", "vote.gov", "vote.org",
                  "usvotefoundation.org", "canivote.org", "nass.org", "eac.gov",
                  "votinginfoproject.org", "rockthevote.org", "headcount.org",
                  # The federal government's state-by-state guides: fvap.gov's
                  # for voters abroad, usa.gov's for everyone.
                  "fvap.gov", "usa.gov")

# Official pages on a domain that is not the jurisdiction's own, each by its
# address and with what makes it the jurisdiction's: {url prefix: (codes,
# label, evidence)}. A county's page or a federal one counts only here,
# for the jurisdictions listed: being on .gov makes a page a government's,
# not this jurisdiction's (PR #102 review: sos.ga.gov passed for Florida).
OFFICIAL_ELSEWHERE = {
    "https://drive.google.com/file/d/1h6Rb8t-XaocN-TfM7Q2CVHgExEXO2ARS/": (
        ("AS",), "American Samoa Election Office's 2026 calendar",
        "the calendar embedded on https://www.aselectionoffice.gov/calendar"),
    "https://drive.google.com/file/d/1KsY2DpP753FVksT3Yg_EF6JI476E9hdI/": (
        ("AS",), "American Samoa Election Office's absentee ballot form",
        "ASG Form EO-08, linked from https://www.aselectionoffice.gov/absentee-voting"),
    "https://docs.google.com/forms/d/e/1FAIpQLSeH9yVWrIrhA2dcHdCrF-a0g2c8qFBpCZe5CwxA2Kch-ZAwpw/": (
        ("GU",), "Guam Election Commission's online registration form",
        "embedded on the Commission's 'Register online' page, https://gec.guam.gov/register/"),
    # Title 48 of the U.S. Code is the territories' organic law: Guam's
    # Organic Act sets its governor's runoff (48 U.S.C. 1422), and chapter
    # 16 its Delegate's runoff and how American Samoa's Delegate is elected
    # (48 U.S.C. 1712; 1732, by a plurality, with no runoff since 2004).
    "https://www.govinfo.gov/content/pkg/USCODE-2024-title48/": (
        ("AS", "GU"), "govinfo.gov (48 U.S.C.)",
        "the Code as the Government Publishing Office publishes it; Title 48 governs elections "
        "in the territories"),
    # The Court's opinion on counting mail ballots that arrive after
    # Election Day, cited only in the researchers' notes, never shown.
    "https://www.supremecourt.gov/opinions/25pdf/24-1260_": (
        ("AK", "CA"), "supremecourt.gov",
        "the Supreme Court's slip opinion on counting mail ballots received after Election Day"),
}

# Each jurisdiction's own government domains: its election office's, its
# legislature's and its general state domain. A host counts for a
# jurisdiction only when it is one of these or under one (a state.<xx>.us
# host counts for <xx>), or is listed in voting.OFFICIAL_HOSTS for it.
JURISDICTION_DOMAINS = {
    "AK": ("alaska.gov",), "AL": ("alabama.gov", "alabamavotes.gov"),
    "AR": ("arkansas.gov",), "AS": ("aselectionoffice.gov", "americansamoa.gov"),
    # The Secretary of State publishes on azsos.gov (and apps.azsos.gov) and
    # arizona.vote (its candidate listing on apps.arizona.vote, read by hand
    # 2026-10-26); arizona.vote, not a .gov host, counts through
    # voting.OFFICIAL_HOSTS, as the sentence above says.
    "AZ": ("azsos.gov", "azleg.gov", "az.gov"), "CA": ("ca.gov",),
    "CO": ("coloradosos.gov", "colorado.gov"), "CT": ("ct.gov",), "DC": ("dc.gov",),
    "DE": ("delaware.gov",), "FL": ("fl.gov", "registertovoteflorida.gov", "flsenate.gov"),
    "GA": ("ga.gov", "georgia.gov"), "GU": ("guam.gov", "guamcourts.gov"),
    "HI": ("hawaii.gov",), "IA": ("iowa.gov",), "ID": ("idaho.gov", "voteidaho.gov"),
    "IL": ("il.gov", "illinois.gov", "ilga.gov"), "IN": ("in.gov",),
    # kansasvoterinfo.gov is the Secretary of State's VoterView, linked as
    # "VoterView" from sos.ks.gov/elections/elections.html (read 2026-11-01).
    "KS": ("ks.gov", "ksrevisor.gov", "kssos.org", "kansasvoterinfo.gov"),
    "KY": ("ky.gov",), "LA": ("la.gov",),
    "MA": ("mass.gov", "malegislature.gov"), "MD": ("maryland.gov",), "ME": ("maine.gov",),
    "MI": ("michigan.gov",), "MN": ("mn.gov",), "MO": ("mo.gov",), "MP": ("gov.mp",),
    "MS": ("ms.gov",), "MT": ("mt.gov", "votemt.gov", "sosmt.gov", "legmt.gov"),
    "NC": ("nc.gov", "ncsbe.gov", "ncleg.gov"), "ND": ("nd.gov",), "NE": ("nebraska.gov",),
    "NH": ("nh.gov",), "NJ": ("nj.gov",), "NM": ("nm.gov", "nmlegis.gov"),
    # nvsos.gov is the Secretary of State's own domain, where its election
    # pages and certified lists are published.
    "NV": ("nv.gov", "nvsos.gov"),
    "NY": ("ny.gov",), "OH": ("ohiosos.gov", "ohio.gov"), "OK": ("oklahoma.gov", "ok.gov"),
    "OR": ("oregon.gov", "oregonlegislature.gov"), "PA": ("pa.gov",), "PR": ("pr.gov",),
    "RI": ("ri.gov",), "SC": ("sc.gov", "scvotes.gov", "scstatehouse.gov"),
    "SD": ("sd.gov", "sdsos.gov", "sdlegislature.gov"), "TN": ("tn.gov",),
    "TX": ("texas.gov", "votetexas.gov"), "UT": ("utah.gov",), "VA": ("virginia.gov",),
    "VI": ("vivote.gov", "vi.gov"), "VT": ("vermont.gov",),
    # votewa.gov is the Secretary of State's VoteWA, linked from sos.wa.gov
    # (read 2026-11-01); NASS lists voter.votewa.gov too.
    "WA": ("wa.gov", "votewa.gov"),
    "WI": ("wi.gov", "wisconsin.gov"), "WV": ("wv.gov",), "WY": ("wyo.gov", "wyoming.gov"),
}

# A value the page shows, and the source fields that may stand for it: a
# qualifier stands on its value's source; everything else needs its own.
SHOWN = {
    "noElection": (),
    "registration.none": (),
    "registration.online.deadline": (),
    "registration.online.time": ("registration.online.deadline",),
    "registration.mail.deadline": (),
    "registration.mail.rule": ("registration.mail.deadline",),
    "registration.inPerson.deadline": (),
    # The last day a new registrant is still mailed a ballot, where
    # registration itself runs on (Nevada's online registration runs
    # through Election Day; from the fourteenth day before, a new
    # registrant votes in person).
    "registration.mailedBallotBy": (),
    "registration.sameDay.available": (),
    # The office's own words, quoted (``where_problems``), never a summary.
    "registration.sameDay.where": ("registration.sameDay.available",),
    # The last day same-day registration is offered, where it ends before
    # Election Day (North Carolina's is at early-voting sites only).
    "registration.sameDay.through": (),
    "earlyVoting.start": (),
    "earlyVoting.end": (),
    # Days inside the window the office says early voting is not held, each
    # named in a quote the window stands on (``except_problems``): Louisiana's
    # "October 20-27 (excluding Sunday, October 25)", South Carolina's
    # "Closed Sunday, October 25".
    "earlyVoting.except": ("earlyVoting.start", "earlyVoting.end"),
    # The office's words where its window runs only in an office's regular
    # hours, quoted (``hours_problems``): South Dakota's "during regular
    # office hours".
    "earlyVoting.hours": ("earlyVoting.start", "earlyVoting.end"),
    # Each local office sets its own days within the window (Wisconsin's
    # "possibly through November 1").
    "earlyVoting.setLocally": (),
    "mail.allMail": (),
    # Where every voter is mailed a ballot, nobody needs an excuse.
    "mail.noExcuse": ("mail.allMail",),
    "mail.requestDeadline.date": (),
    "mail.requestDeadline.rule": ("mail.requestDeadline.date",),
    "mail.returnDeadline.date": (),
    "mail.returnDeadline.time": ("mail.returnDeadline.date",),
    "mail.returnDeadline.rule": ("mail.returnDeadline.date", "mail.returnDeadline.receivedBy"),
    "mail.returnDeadline.receivedBy": (),
    "runoff.date": (),
    # A runoff's own early voting and mail ballots, kept as the general
    # election's are: the Northern Mariana Islands' Commission published its
    # runoff's on 2026-11-08, and only the runoff's date had a field, so the
    # page never said that early voting for it opened on November 13.
    "runoff.earlyVoting.start": (),
    "runoff.earlyVoting.end": (),
    # The start is the latest day early voting may begin, not the first day
    # it is offered: Georgia's calendar gives its runoff's "As soon as
    # possible, but no later than 11/23/26" (``SAID``).
    "runoff.earlyVoting.startsBy": ("runoff.earlyVoting.start",),
    # Louisiana's December 12: "November 28-December 5 (excluding Sunday,
    # November 29)".
    "runoff.earlyVoting.except": ("runoff.earlyVoting.start", "runoff.earlyVoting.end"),
    # Arkansas's December 1: "during your county clerk’s regular office
    # hours" (the Secretary of State's voting page).
    "runoff.earlyVoting.hours": ("runoff.earlyVoting.start", "runoff.earlyVoting.end"),
    # A runoff's own registration deadlines, kept as the general election's
    # are: Louisiana's dates page gives December 12's ("in person, by mail,
    # or at an OMV Office is November 12", online "November 21"), and with
    # no field for them the page said nothing of them on the in-person
    # deadline's own day (read 2026-11-12).
    "runoff.registration.online.deadline": (),
    "runoff.registration.online.time": ("runoff.registration.online.deadline",),
    "runoff.registration.mail.deadline": (),
    "runoff.registration.mail.rule": ("runoff.registration.mail.deadline",),
    "runoff.registration.inPerson.deadline": (),
    "runoff.mail.requestDeadline.date": (),
    "runoff.mail.requestDeadline.rule": ("runoff.mail.requestDeadline.date",),
    # How an application must reach the office by that day, where the office
    # names one way alone (the Commission's "over the counter"; ``HOWS``).
    "runoff.mail.requestDeadline.how": ("runoff.mail.requestDeadline.date",),
    "runoff.mail.returnDeadline.date": (),
    "runoff.mail.returnDeadline.time": ("runoff.mail.returnDeadline.date",),
    "runoff.mail.returnDeadline.rule": ("runoff.mail.returnDeadline.date",
                                        "runoff.mail.returnDeadline.receivedBy"),
    "runoff.mail.returnDeadline.receivedBy": (),
}
# Flags shown only when true: false says nothing on the page.
SHOWN_WHEN_TRUE = {"noElection", "registration.none", "registration.sameDay.available",
                   "mail.allMail", "earlyVoting.setLocally", "runoff.earlyVoting.startsBy"}
# A runoff's own dates, each beside the runoff's: none of them may stand
# without a runoff date in the record.
RUNOFF_DATES = ("runoff.earlyVoting.start", "runoff.earlyVoting.end",
                "runoff.mail.requestDeadline.date", "runoff.mail.returnDeadline.date",
                "runoff.mail.returnDeadline.receivedBy")
# A runoff's own registration deadlines: each on or before the runoff, but
# not always after November 3 (Arkansas's and Mississippi's December 1 closed
# registration on November 2), and none without the runoff's date.
RUNOFF_REGISTRATION = ("runoff.registration.online.deadline", "runoff.registration.mail.deadline",
                       "runoff.registration.inPerson.deadline")

# "Postmarked by then" and "must arrive by then" are claims of their own:
# each must be said in a quote the value stands on (its own source or a
# stand-in's), not merely beside a date (PR #102 review: South Dakota's
# "received" stood on a quote that said only the date).
RULE_WORDS = {
    # Mississippi's calendar writes "post-marked".
    "postmarked": re.compile(r"post-?mark", re.I),
    "received": re.compile(r"receiv|receipt|arriv|\breach|in the hands of|in (?:the )?possession"
                           r"|deliver(?:y|ed) to", re.I),
}
RULES = ("registration.mail.rule", "mail.requestDeadline.rule", "mail.returnDeadline.rule",
         "runoff.registration.mail.rule", "runoff.mail.requestDeadline.rule",
         "runoff.mail.returnDeadline.rule")

# A day inside an early-voting window that the office says is not one of its
# days, as its own words name it: {field: the window it is inside}. The
# window's line said "Under way" on Sunday, October 25 in Louisiana, Delaware,
# South Carolina and Hawaii, each of which had excluded it, and would have on
# Louisiana's Sunday, November 29; a day is never inferred from a weekday or
# a holiday the office does not name (Arkansas's "during regular office
# hours" names none: its hours are ``HOURS``' words, and only the state
# holiday its own calendar names is listed, ``closes_as_holiday``).
EXCEPT = {"earlyVoting.except": "earlyVoting",
          "runoff.earlyVoting.except": "runoff.earlyVoting"}
# Where a window runs only in an office's regular hours, the office's words
# that say so: {field: the window it is about}. Arkansas's December 1 runoff
# is held "during your county clerk’s regular office hours" (the Secretary of
# State's voting page; Ark. Code 7-5-418(a)(2)), and the page called it
# "Under way" on Saturday and Sunday, November 28 and 29, though no source
# says any clerk's office keeps hours then, and the State Board of Election
# Commissioners' own manual says "in most cases" none does.
HOURS = {"earlyVoting.hours": "earlyVoting",
         "runoff.earlyVoting.hours": "runoff.earlyVoting"}
# Words that put a window's days in an office's regular hours: "during
# regular office hours", "during regular county clerk office hours",
# "normal business hours". A quote the window stands on that says so holds
# the record to ``hours``, or the page calls every day of it "Under way".
OFFICE_HOURS = re.compile(r"\b(?:regular|normal|usual)\b(?:\s+[\w’']+){0,3}?\s+"
                          r"(?:office|business|working)\s+hours\b", re.I)
# The words that close state holidays as a class: Arkansas's State Board of
# Election Commissioners' "Early voting shall not be held on state holidays"
# and "Excludes all STATE Holidays", Ark. Code 7-5-418(a)(1)(B)'s "shall not
# be available on state ... holidays" (Act 92 of 2023 struck "or county").
HOLIDAYS_CLOSED = re.compile(
    r"\bnot be (?:available|held)\s+on\s+(?:all\s+)?state(?:\s+(?:or\s+county|\.\.\.|…))?\s+holidays\b"
    r"|\bexclud(?:e|es|ed|ing)\s+all\s+state\s+holidays\b", re.I)
# The form of a calendar that marks a deadline moved off a day that is no
# business day: Arkansas's "November 26, 2026 – Thursday*" beside
# "[*Deadlines falling on a Saturday, Sunday, or legal holiday are extended
# to the following business day ...]". A weekday so marked is the holiday.
_MOVED_OFF = re.compile(r"\*\s*Deadlines\s+(?:falling|that\s+fall)\s+on\s+a\s+Saturday,\s+Sunday,?\s+"
                        r"or\s+(?:a\s+)?legal\s+holiday\s+(?:are\s+extended|will\s+advance)\b", re.I)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# What says a day is not held: "excluding", "except", "closed", "no early
# voting" (Delaware's "October 25, 2026 – NO EARLY VOTING").
_CLOSED = r"(?:exclud(?:e|es|ed|ing)|except(?:ed|ing)?|closed(?: on)?|no early voting(?: on)?)"
# The words that close a day named AFTER them: never a bare "no early
# voting", which ends Delaware's sentence for one day and runs on into the
# next ("October 25, 2026 - NO EARLY VOTING October 26, 2026 - October 27"),
# and never a day that opens a range (the second reader of PR #240).
_BEFORE = r"(?:exclud(?:e|es|ed|ing)|except(?:ed|ing)?|closed(?: on)?|no early voting on)"
_NOT_A_RANGE = r"(?![,\s\d]*[–—-]|[,\s\d]*(?:through|to)\b)"
# A weekday the office closes as a class, beside the words that close it:
# Hawaii's "(Excluding Sundays)", or "Sundays ... excepted".
CLOSED_CLASS = re.compile(
    r"\b" + _CLOSED + r"\s+(?:all\s+)?(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)days\b"
    r"|\b(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)days\b[^.;()]{0,40}?\b(?:excluded|excepted|closed)\b",
    re.I)
# A qualifier that is a claim of its own is said in a quote it stands on, as
# "postmarked" and "received" are: a start that is only the latest day early
# voting may begin, and an application taken in person alone.
SAID = {
    "runoff.earlyVoting.startsBy": re.compile(r"as soon as possible|no later than", re.I),
    "runoff.mail.requestDeadline.how": re.compile(r"over the counter|in person", re.I),
}
# The ways an application may be limited to (``runoff.mail.requestDeadline.how``).
HOWS = ("in person",)

# What a runoff in the record decides, in words the page shows beside its
# date, each from the record's runoff source and note: Arkansas's and
# Mississippi's December 1 are not runoffs for Congress, and a line that
# said only "Runoff" would read as one. {code: (before, after the date)}.
# Georgia's and Louisiana's words are those the page used since #94.
RUNOFF_WORDS = {
    "AR": ("Runoff, if one is needed, for county and municipal offices (and, after a tie, "
           "certain state or township offices); not for federal offices",
           "The date set for runoffs for county and municipal offices"),
    "GA": ("If no candidate for an office wins a majority of the votes on November 3, the top "
           "two meet in a runoff on this date",
           "The date set for a runoff in any race no candidate won with a majority of the "
           "votes on November 3"),
    "GU": ("Runoff between the top two, if no ticket for Governor and Lieutenant Governor or no "
           "candidate for Delegate wins a majority: the fourteenth day after the election, "
           "as federal law sets it",
           "The date set for any runoff for Governor and Lieutenant Governor or for Delegate"),
    "LA": ("The U.S. House vote on November 3 is an open primary; a seat no candidate wins "
           "with a majority is decided at a general election on this date",
           "The date set for a general election for any U.S. House seat no candidate won "
           "with a majority in the November 3 open primary"),
    "MS": ("Runoff, if one is needed, for judges and school board members only",
           "The date set for runoffs for judges and school board members"),
    # The Commission's own calendar sets it (read 2026-11-11), fourteen
    # days after it certified the results on November 6, as 1 CMC 6509(a)
    # and (b) count it. 1 CMC 6509 holds a majority runoff for these
    # offices; 6524(b) also holds one where two or more tie for any office
    # (the second reader of PR #235). No Commission page says in words
    # which this one decides, so the
    # words do not say either (rule 91: this site reads no territory's
    # result). Not "if one is needed": the Commission has set it.
    "MP": ("Runoff election set by the Commonwealth Election Commission: the law holds one "
           "between the top two for Governor and Lieutenant Governor, or for Attorney General, "
           "where no ticket or candidate won more than half the votes on November 3",
           "The date set for the Commonwealth Election Commission's runoff election, which the "
           "law holds for Governor and Lieutenant Governor, or for Attorney General, where no "
           "ticket or candidate won more than half the votes on November 3"),
    "VI": ("Runoff, if one is needed, for Governor and Lieutenant Governor or for Delegate",
           "The date set for any runoff for Governor and Lieutenant Governor or for Delegate"),
}
# The calendar strip's labels for a runoff, before and after its date: a
# strip that said only "Runoff, if needed" over Mississippi's judges'
# runoff read as a runoff for Congress (PR #102 review).
RUNOFF_SHORT = {
    "AR": ("Local runoff, if needed", "Local runoff date"),
    "LA": ("House general, if needed", "House general date"),
    "MS": ("Judicial, school board runoff, if needed", "Judicial, school board runoff date"),
    # Set, not "if needed", and naming the offices 1 CMC 6509 holds it for:
    # a bare "Runoff" where the Delegate to Congress was elected the same day
    # would read as a runoff for that seat, which the section does not name.
    "MP": ("Governor or attorney general runoff", "Governor or attorney general runoff date"),
}
RUNOFF_SHORT_DEFAULT = ("Runoff, if needed", "Runoff date")
# Where the office has set its runoff, not "if one is needed" (the
# Commission's calendar, as RUNOFF_WORDS["MP"] says): the runoff's own dates
# are "for the runoff" there, and "for a runoff, if one is held" anywhere
# else, as that runoff's own words are conditional (Georgia's). Neither says
# which race went to one, or who is in it (rule 91).
RUNOFF_SET = frozenset({"MP"})
# What a runoff's own dates are for, where "a runoff" and "Runoff" would say
# what it is not: {code: (in their sentences, at the start of their strip
# labels)}. Louisiana's December 12 is a general election for any U.S.
# House seat the November 3 open primary did not decide, never a runoff, as
# its line says (RUNOFF_WORDS); Arkansas's and Mississippi's December 1 are
# no runoff for Congress, and a strip cell that said only "Runoff early
# voting" there would read as one, as a bare "Runoff, if needed" did (PR
# #102 review). Their sentences follow the runoff's own line, which says what
# it decides; a strip cell stands alone. None names which race went to one,
# or who is in it (rule 91).
RUNOFF_OWN = {
    "AR": ("a runoff", "Local runoff"),
    "LA": ("a U.S. House general election", "House general"),
    "MS": ("a runoff", "Judicial, school board runoff"),
}
RUNOFF_OWN_DEFAULT = ("a runoff", "Runoff")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A time of day as the record gives it; anything longer ("7:00 pm (postmark);
# received by 5:00 pm November 4") is not shown, the dates saying it.
_TIME = re.compile(r"^(\d{1,2}:\d{2} [ap]m)(?: \(noon\))?$")


class VotingDatesError(RuntimeError):
    """The cache breaks its rules."""


def load(root="."):
    path = os.path.join(root, CACHE_PATH)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def get(record, path):
    for part in path.split("."):
        if not isinstance(record, dict):
            return None
        record = record.get(part)
    return record


def _host(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def _unarchived(url):
    """An Internet Archive capture's original address, else None."""
    m = re.match(r"^https?://web\.archive\.org/web/(\d{8,14})[a-z_]*/(https?://.+)$", url)
    return (m.group(2), m.group(1)) if m else None


def compiled(url):
    """Is *url* (or the page an archive captured) a compiled table?"""
    inner = _unarchived(url)
    host = _host(inner[0] if inner else url)
    return any(host == h or host.endswith("." + h) for h in COMPILED_HOSTS)


def official_source(url, code):
    """``(True, label)`` when *url* is *code*'s own official page, else
    ``(False, why)``. A capture in the Internet Archive counts as the page it
    captured (Guam's Election Commission refused connections on 2026-10-17)."""
    from . import voting

    if not re.match(r"^https?://", str(url or "")):
        return False, "not a web address"
    if compiled(url):
        return False, "a compiled table, a lead and never a source (rule 50)"
    inner = _unarchived(url)
    if inner:
        ok, label = official_source(inner[0], code)
        stamp = inner[1]
        return ok, (f"{label} (archived {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]})" if ok else label)
    for prefix, (owners, label, _evidence) in OFFICIAL_ELSEWHERE.items():
        if url.startswith(prefix):
            return (code in owners), (label if code in owners
                                      else f"{'/'.join(owners)}'s page, not {code}'s")
    host = _host(url)
    label = host[4:] if host.startswith("www.") else host
    state = re.search(r"\.state\.([a-z]{2})\.us$", host)
    if state:
        return (state.group(1) == code.lower()), label
    domains = list(JURISDICTION_DOMAINS.get(code, ())) + [
        d for d, owner in voting.OFFICIAL_HOSTS.items() if owner == code]
    if any(host == d or host.endswith("." + d) for d in domains):
        return True, label
    return False, f"{host} is not {code}'s own domain"


def _sources(record, field):
    return [s for s in record.get("sources") or [] if s.get("field") == field]


def _shown(record, path):
    value = get(record, path)
    if value in (None, "") or value == []:
        return None
    if path in SHOWN_WHEN_TRUE and value is not True:
        return None
    return value


def problems(data, runoffs=None):
    """Every way *data* breaks the cache's rules, as strings."""
    if runoffs is None:
        runoffs = override_runoffs()
    states = (data or {}).get("states") or {}
    out = [f"{code}: no record" for code in sorted(JURISDICTIONS - set(states))]
    out += [f"{code}: not a jurisdiction" for code in sorted(set(states) - JURISDICTIONS)]
    for code, record in sorted(states.items()):
        out += state_problems(code, record, runoffs)
    return out


def state_problems(code, record, runoffs):
    """What is wrong with one jurisdiction's record, as strings."""
    out = []
    if record.get("election") != ELECTION:
        out.append(f"{code}: election {record.get('election')!r}, not {ELECTION}")
    for source in record.get("sources") or []:
        ok, why = official_source(source.get("url"), code)
        if not ok:
            out.append(f"{code} {source.get('field')}: {source.get('url')} - {why}")
        if not str(source.get("quote") or "").strip():
            out.append(f"{code} {source.get('field')}: a source with no quote")
        if "read" in source and not _ISO_DAY.match(str(source.get("read") or "")):
            out.append(f"{code} {source.get('field')}: read {source.get('read')!r} is not a day "
                       "(YYYY-MM-DD)")
    fields = {s.get("field") for s in record.get("sources") or []}
    for path, stand_ins in SHOWN.items():
        if _shown(record, path) is None:
            continue
        if path not in fields and not fields & set(stand_ins):
            out.append(f"{code} {path}: shown with no source")
    for path in RULES:
        rule = get(record, path)
        if rule is None:
            continue
        if rule not in RULE_WORDS:
            out.append(f"{code} {path}: {rule!r} is neither 'postmarked' nor 'received'")
            continue
        quotes = [s.get("quote") or "" for s in record.get("sources") or []
                  if s.get("field") in (path,) + SHOWN[path]]
        if not any(RULE_WORDS[rule].search(q) for q in quotes):
            out.append(f"{code} {path}: {rule!r}, but no quote it stands on says so")
    how = get(record, "runoff.mail.requestDeadline.how")
    if how is not None and how not in HOWS:
        out.append(f"{code} runoff.mail.requestDeadline.how: {how!r} is not one of {HOWS}")
    for path, words in SAID.items():
        if _shown(record, path) is None:
            continue
        quotes = [s.get("quote") or "" for s in record.get("sources") or []
                  if s.get("field") in (path,) + SHOWN[path]]
        if not any(words.search(q) for q in quotes):
            out.append(f"{code} {path}: shown, but no quote it stands on says so")
    out += where_problems(code, record)
    out += except_problems(code, record)
    out += hours_problems(code, record)
    out += _date_problems(code, record)
    date = get(record, "runoff.date")
    if date and code not in RUNOFF_WORDS:
        out.append(f"{code}: a runoff on {date} with no RUNOFF_WORDS saying what it decides")
    if not date and code in RUNOFF_WORDS:
        out.append(f"{code}: RUNOFF_WORDS for a runoff the record does not hold")
    if code in runoffs and runoffs[code] != date:
        out.append(f"{code}: the overrides hold a December date of {runoffs[code]}, the record "
                   f"{date}; two sources of one date must agree (rule 53)")
    return out


def _plain(text):
    """Text compared as words: case, spacing, curly quotes and dashes aside."""
    text = str(text or "").translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
                                      0x2013: "-", 0x2014: "-", 0xA0: " "})
    return re.sub(r"\s+", " ", text).strip().lower()


def where_excerpts(where):
    """The office's words a ``sameDay.where`` quotes: excerpts joined by " ... "."""
    return [part.strip() for part in str(where or "").split(" ... ") if part.strip()]


def _where_sources(record):
    return [s for s in record.get("sources") or []
            if s.get("field") in ("registration.sameDay.where", "registration.sameDay.available")]


def where_problems(code, record):
    """Where same-day registration happens is shown in the office's words:
    each excerpt of ``where`` must be in a quote of a same-day source. The
    first record held a researcher's summary there, and the page showed it
    (PR #102 review)."""
    where = _shown(record, "registration.sameDay.where")
    if not where:
        return []
    quotes = [_plain(s.get("quote")) for s in _where_sources(record)]
    return [f"{code} registration.sameDay.where: {part!r} is not in the office's words quoted "
            f"for same-day registration" for part in where_excerpts(where)
            if not any(_plain(part) in q for q in quotes)]


def _day_words(iso):
    """A day as an office writes it, as a pattern: "Sunday, November 29",
    "Nov. 29", "11/29/26", with or without its weekday and its year."""
    date = datetime.date.fromisoformat(iso)
    month = _MONTHS[date.month - 1]
    return (rf"(?:{_WEEKDAYS[date.weekday()]},?\s+)?"
            rf"(?:(?:{month}|{month[:3]}\.?)\s+0?{date.day}(?:st|nd|rd|th)?(?!\d)"
            rf"|0?{date.month}/0?{date.day}(?:/(?:20)?{date.year % 100:02d})?(?!\d))"
            rf"(?:,?\s*{date.year})?")


def closed_weekdays(quote):
    """The weekdays *quote* closes as a class ("Excluding Sundays"), by name."""
    out = set()
    for m in CLOSED_CLASS.finditer(str(quote or "")):
        stem = (m.group(1) or m.group(2)).lower()
        out |= {w for w in _WEEKDAYS if w[:-3].lower() == stem}
    return out


def closes(quote, iso):
    """Does *quote* say early voting is not held on the day *iso*: the day
    named beside the words that close it ("excluding Sunday, November 29",
    "Closed Sunday, October 25", "October 25, 2026 – NO EARLY VOTING"), or
    its weekday closed as a class ("Excluding Sundays")? A day the words do
    not name is not closed, whatever the calendar makes of it (rule 84)."""
    if closes_on_date(quote, iso):
        return True
    return _WEEKDAYS[datetime.date.fromisoformat(iso).weekday()] in closed_weekdays(str(quote or ""))


def closes_on_date(quote, iso):
    """Does *quote* name the day *iso* itself closed ("excluding Sunday,
    November 29", "October 25, 2026 - NO EARLY VOTING"), its weekday as a
    class aside?"""
    quote = str(quote or "")
    day = _day_words(iso)
    if re.search(r"\b" + _BEFORE + r"\W{0,3}(?:on\s+)?" + day + _NOT_A_RANGE, quote, re.I):
        return True
    return bool(re.search(day + r"\s*\W{0,3}\s*(?:no early voting|closed)\b", quote, re.I))


def names_holiday(quote, iso):
    """Does *quote* name the day *iso* a holiday: the day beside "state
    holiday" or "legal holiday" in one sentence, or a weekday a calendar
    stars as a day whose deadline moves to the next business day, beside
    its own note that such a day is "a Saturday, Sunday, or legal holiday"
    (Arkansas's "November 26, 2026 – Thursday*")? A Saturday or a Sunday so
    starred is a weekend, not a holiday."""
    quote = str(quote or "")
    day = _day_words(iso)
    holiday = r"\b(?:state|legal)\s+holiday\b"
    if (re.search(day + r"[^.;\[\]]{0,40}?" + holiday, quote, re.I)
            or re.search(holiday + r"[^.;\[\]]{0,40}?" + day, quote, re.I)):
        return True
    weekday = datetime.date.fromisoformat(iso).weekday()
    if weekday >= 5:
        return False
    starred = re.search(day + r"\s*[–—-]?\s*(?:" + _WEEKDAYS[weekday] + r")?\s*\*", quote, re.I)
    return bool(starred and _MOVED_OFF.search(quote))


def closes_as_holiday(quotes, iso):
    """Do *quotes*, together, close the day *iso* as a state holiday: one
    that says early voting is not held on state holidays (``HOLIDAYS_CLOSED``)
    and one that names this day a holiday (``names_holiday``)? Arkansas's
    Thanksgiving, November 26, inside its December 1 runoff's early voting.
    Never a holiday no quote names: a general calendar is not the office's
    word (rule 84)."""
    quotes = [str(q or "") for q in quotes]
    return (any(HOLIDAYS_CLOSED.search(q) for q in quotes)
            and any(names_holiday(q, iso) for q in quotes))


def _closed_in(quotes, iso):
    """Do *quotes* close the day *iso*, one of them naming it closed or two
    of them closing it as a state holiday?"""
    return any(closes(q, iso) for q in quotes) or closes_as_holiday(quotes, iso)


def _window_days(start, end):
    day, last = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    while day <= last:
        yield day
        day += datetime.timedelta(days=1)


def except_problems(code, record):
    """The days an early-voting window is not held (``EXCEPT``): a list of
    dates, in order, each inside its window and named closed in a quote the
    window stands on; and where a quote closes a weekday as a class, every
    such day of the window is listed, or the page would call one "Under
    way"."""
    out = []
    for path, window in EXCEPT.items():
        days = get(record, path)
        if days is None or days == []:
            # An office's words that name a day closed hold the record to
            # listing it, or the page calls that day "Under way": Louisiana's
            # October 25 shipped so (the second reader of PR #240). A weekday
            # closed as a class is not asked here: Colorado's and Nevada's
            # words close a class for some sites only.
            start, end = get(record, f"{window}.start"), get(record, f"{window}.end")
            if (isinstance(start, str) and isinstance(end, str) and _DATE.match(start)
                    and _DATE.match(end) and start <= end):
                quotes = [s.get("quote") or "" for s in record.get("sources") or []
                          if s.get("field") in (path,) + SHOWN[path]]
                # A state holiday two quotes close together is named as
                # surely as one a quote closes alone (Arkansas's November 26).
                named = [day.isoformat() for day in _window_days(start, end)
                         if start < day.isoformat() < end
                         and (any(closes_on_date(q, day.isoformat()) for q in quotes)
                              or closes_as_holiday(quotes, day.isoformat()))]
                if named:
                    out.append(f"{code} {path}: a quote the window stands on names "
                               f"{', '.join(named)} closed, but no day is listed")
            continue
        if not (isinstance(days, list) and all(isinstance(d, str) and _DATE.match(d) for d in days)):
            out.append(f"{code} {path}: {days!r} is not a list of dates")
            continue
        try:
            for value in days:
                datetime.date.fromisoformat(value)
        except ValueError:
            out.append(f"{code} {path}: {days!r} holds a day that is not a date")
            continue
        if days != sorted(set(days)):
            out.append(f"{code} {path}: {days!r} is not in order, each day once")
        start, end = get(record, f"{window}.start"), get(record, f"{window}.end")
        if not (isinstance(start, str) and isinstance(end, str) and _DATE.match(start)
                and _DATE.match(end) and start <= end):
            out.append(f"{code} {path}: days the window is not held, with no window")
            continue
        out += [f"{code} {path}: {value} is not inside the window, {start} to {end}"
                for value in days if not start < value < end]
        quotes = [s.get("quote") or "" for s in record.get("sources") or []
                  if s.get("field") in (path,) + SHOWN[path]]
        out += [f"{code} {path}: {value}, but no quote it stands on names that day closed"
                for value in days if not _closed_in(quotes, value)]
        named = [day.isoformat() for day in _window_days(start, end)
                 if start < day.isoformat() < end and day.isoformat() not in days
                 and (any(closes_on_date(q, day.isoformat()) for q in quotes)
                      or closes_as_holiday(quotes, day.isoformat()))]
        if named:
            out.append(f"{code} {path}: a quote the window stands on names "
                       f"{', '.join(named)} closed, but it is not listed")
        weekdays = set().union(*(closed_weekdays(q) for q in quotes))
        missing = [day.isoformat() for day in _window_days(start, end)
                   if _WEEKDAYS[day.weekday()] in weekdays and day.isoformat() not in days]
        if missing:
            out.append(f"{code} {path}: the office closes "
                       f"{' and '.join(sorted(w + 's' for w in weekdays))}, but {', '.join(missing)} "
                       f"{'is' if len(missing) == 1 else 'are'} not listed")
    return out


def hours_problems(code, record):
    """A window held only in an office's regular hours (``HOURS``) says so in
    the office's words: ``hours`` is text, words of office hours
    (``OFFICE_HOURS``), found in a quote of its own field or its window's,
    and stands only beside a window. And a quote the window stands on that
    puts its days in an office's regular hours holds the record to saying
    so: otherwise the page calls every day of the window "Under way",
    Arkansas's weekend before its December 1 runoff included."""
    out = []
    for path, window in HOURS.items():
        hours = get(record, path)
        fields = (path, f"{window}.start", f"{window}.end", f"{window}.except")
        quotes = [s.get("quote") or "" for s in record.get("sources") or []
                  if s.get("field") in fields]
        start, end = get(record, f"{window}.start"), get(record, f"{window}.end")
        if hours in (None, ""):
            if start and end:
                said = [m.group(0) for q in quotes for m in [OFFICE_HOURS.search(q)] if m]
                if said:
                    out.append(f"{code} {path}: a quote the window stands on gives its days as "
                               f"{said[0]!r}, but the record does not say so: the page would call "
                               f"every day of it 'Under way'")
            continue
        if not isinstance(hours, str) or not OFFICE_HOURS.search(hours):
            out.append(f"{code} {path}: {hours!r} is not the office's words for its regular hours")
            continue
        if not (start and end):
            out.append(f"{code} {path}: office hours, with no window")
        if not any(_plain(hours) in _plain(q) for q in quotes):
            out.append(f"{code} {path}: {hours!r} is not in the office's words quoted for the window")
    return out


def _date_problems(code, record):
    out = []

    def day(path):
        value = get(record, path)
        if value is None:
            return None
        if not (isinstance(value, str) and _DATE.match(value)):
            out.append(f"{code} {path}: {value!r} is not a date")
            return None
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            out.append(f"{code} {path}: {value!r} is not a date")
            return None
        if not EARLIEST <= value <= LATEST:
            out.append(f"{code} {path}: {value} is outside the cycle")
        return value

    for path in ("registration.online.deadline", "registration.mail.deadline",
                 "registration.inPerson.deadline", "registration.mailedBallotBy",
                 "registration.sameDay.through", "mail.requestDeadline.date"):
        value = day(path)
        if value and value > ELECTION:
            out.append(f"{code} {path}: {value} is after the election")
    start, end = day("earlyVoting.start"), day("earlyVoting.end")
    if (start is None) != (end is None):
        out.append(f"{code} earlyVoting: a window with one end")
    elif start and not start <= end <= ELECTION:
        out.append(f"{code} earlyVoting: {start} to {end} does not run forwards to the election")
    returned, received = day("mail.returnDeadline.date"), day("mail.returnDeadline.receivedBy")
    if returned and returned > ELECTION:
        out.append(f"{code} mail.returnDeadline.date: {returned} is after the election")
    if returned and received and received < returned:
        out.append(f"{code} mail.returnDeadline: received by {received}, before {returned}")
    if get(record, "mail.returnDeadline.rule") == "postmarked" and received == returned:
        # A postmark deadline whose ballots must also arrive that day is a
        # receipt deadline; the page would promise days that do not exist.
        out.append(f"{code} mail.returnDeadline: postmarked, yet received the same day")
    runoff = day("runoff.date")
    if runoff and runoff <= ELECTION:
        out.append(f"{code} runoff.date: {runoff} is not after the election")
    out += _runoff_date_problems(code, record, runoff, day)
    if get(record, "registration.online.deadline") and get(
            record, "registration.online.available") is not True:
        out.append(f"{code} registration.online: a deadline for registration not offered online")
    if get(record, "registration.sameDay.through") and get(
            record, "registration.sameDay.available") is not True:
        out.append(f"{code} registration.sameDay.through: an end to same-day registration not offered")
    return out


def _runoff_date_problems(code, record, runoff, day):
    """A runoff's own dates (``runoff.earlyVoting``, ``runoff.mail``): each
    after the election it follows and in order with the runoff's date, and
    none without one. *day* reads and checks a date as ``_date_problems``
    does."""
    out = []
    dates = {path: day(path) for path in RUNOFF_DATES}
    registered = {path: day(path) for path in RUNOFF_REGISTRATION}
    if not runoff:
        out += [f"{code} {path}: a runoff's own date, with no runoff date in the record"
                for path, value in list(dates.items()) + list(registered.items()) if value]
        return out
    out += [f"{code} {path}: {value} is after the runoff on {runoff}"
            for path, value in registered.items() if value and value > runoff]
    if registered["runoff.registration.online.deadline"] and get(
            record, "registration.online.available") is not True:
        out.append(f"{code} runoff.registration.online: a deadline for registration not offered "
                   "online")
    start, end = dates["runoff.earlyVoting.start"], dates["runoff.earlyVoting.end"]
    if (start is None) != (end is None):
        out.append(f"{code} runoff.earlyVoting: a window with one end")
    elif start and not ELECTION < start <= end < runoff:
        out.append(f"{code} runoff.earlyVoting: {start} to {end} does not run forwards between "
                   f"the election and the runoff on {runoff}")
    if get(record, "runoff.earlyVoting.startsBy") is True and not start:
        out.append(f"{code} runoff.earlyVoting.startsBy: a latest start with no start")
    request = dates["runoff.mail.requestDeadline.date"]
    if request and not ELECTION < request <= runoff:
        out.append(f"{code} runoff.mail.requestDeadline.date: {request} is not between the "
                   f"election and the runoff on {runoff}")
    returned = dates["runoff.mail.returnDeadline.date"]
    received = dates["runoff.mail.returnDeadline.receivedBy"]
    if returned and not ELECTION < returned <= runoff:
        out.append(f"{code} runoff.mail.returnDeadline.date: {returned} is not between the "
                   f"election and the runoff on {runoff}")
    if received and received <= ELECTION:
        out.append(f"{code} runoff.mail.returnDeadline.receivedBy: {received} is not after the "
                   "election")
    if returned and received and received < returned:
        out.append(f"{code} runoff.mail.returnDeadline: received by {received}, before {returned}")
    if (get(record, "runoff.mail.returnDeadline.rule") == "postmarked" and returned
            and received == returned):
        out.append(f"{code} runoff.mail.returnDeadline: postmarked, yet received the same day")
    return out


def override_runoffs():
    """The December dates the results reader holds: {code: date}."""
    from .overrides import GENERAL_RUNOFFS, OPEN_PRIMARY_SEATS

    out = {code: date for code, (date, _evidence) in GENERAL_RUNOFFS.items()}
    for (code, _office, _cycle), seat in OPEN_PRIMARY_SEATS.items():
        if seat.get("runoff"):
            out[code] = seat["runoff"]
    return out


def check(data, runoffs=None):
    found = problems(data, runoffs)
    if found:
        raise VotingDatesError("; ".join(found))


# ------------------------------------------------------------------ the page

def _time(value):
    m = _TIME.match(str(value or ""))
    return m.group(1) if m else None


def _join(words):
    words = [w for w in words if w]
    return words[0] if len(words) < 2 else ", ".join(words[:-1]) + " or " + words[-1]


class _Links:
    """A record's source addresses, numbered once each for the page."""

    def __init__(self, code, record):
        self.code, self.record, self.urls, self.labels = code, record, [], []

    def of(self, *fields, want=None):
        out = []
        for field in fields:
            for source in _sources(self.record, field):
                if want is not None and not want(source):
                    continue
                url = source["url"]
                ok, label = official_source(url, self.code)
                if not ok:
                    continue
                if url not in self.urls:
                    self.urls.append(url)
                    self.labels.append(label)
                index = self.urls.index(url)
                # One link per label: two pages of one office read as one
                # site twice.
                if index not in out and all(self.labels[i] != label for i in out):
                    out.append(index)
            if out:
                break
        return out


def _says_postmarked(source):
    return bool(RULE_WORDS["postmarked"].search(source.get("quote") or ""))


def arrive_sources(links, deadline):
    """The links of a line that says ballots "postmarked by" one day count if
    they arrive by another (``deadline`` is ``mail.returnDeadline`` or
    ``runoff.mail.returnDeadline``). The line shows two things, the arrival
    day and the word, and each keeps its source (rule 84): the arrival day's
    own source where its quote says "postmarked"; else one of its sources on
    a page that says it under any of the deadline's fields; else the sources
    that say the word, followed by the arrival day's own. The first version
    linked only the page saying the word, so a shown day lost its source (the
    CNMI's December 4, which the law counts and the calendar names; the
    second reader of PR #238)."""
    day_field = f"{deadline}.receivedBy"
    rest = (f"{deadline}.date", f"{deadline}.rule")
    own = links.of(day_field, want=_says_postmarked)
    if own:
        return own
    saying = {s["url"] for field in (day_field,) + rest
              for s in _sources(links.record, field) if _says_postmarked(s)}
    page = links.of(day_field, want=lambda s: s["url"] in saying)
    if page:
        return page
    word = links.of(*rest, want=_says_postmarked)
    day = links.of(day_field)
    return word + [i for i in day if i not in word]


def _excluding(days):
    """", excluding Sunday, November 29": the days inside a window the office
    says it is not held, each with its weekday, as its words name them."""
    if not days:
        return ""
    named = [f"{_WEEKDAYS[datetime.date.fromisoformat(d).weekday()]}, {_long(d)}" for d in days]
    return ", excluding " + (named[0] if len(named) == 1
                             else ", ".join(named[:-1]) + " and " + named[-1])


def _in_hours(hours):
    """"; in the office’s words, “during your county clerk’s regular office
    hours”": the hours a window is held in, quoted, never summed up (rule
    84), or "" with none."""
    return f"; in the office’s words, “{hours.rstrip('.')}”" if hours else ""


def _window_sources(links, window, days):
    """The links of an early-voting line: the window's own (``window`` is
    ``earlyVoting`` or ``runoff.earlyVoting``) and, for each day it says the
    window is not held, a page whose words close that day, where none linked
    already does (rule 84: the words "excluding Sunday, November 29" keep
    their source as the dates do)."""
    fields = (f"{window}.start", f"{window}.end")
    linked = links.of(*fields)
    every = (f"{window}.except",) + fields
    for day in days:
        urls = {links.urls[i] for i in linked}
        shown = [s.get("quote") for field in every for s in _sources(links.record, field)
                 if s["url"] in urls]
        if _closed_in(shown, day):
            continue
        more = links.of(*every, want=lambda s, day=day: closes(s.get("quote"), day))
        if not more:
            # A state holiday: the page whose words close state holidays and
            # the page that names this day one, each linked (Arkansas's State
            # Board of Election Commissioners' manual and the Secretary of
            # State's calendar).
            more = (links.of(*every, want=lambda s: bool(HOLIDAYS_CLOSED.search(s.get("quote") or "")))
                    + links.of(*every, want=lambda s, day=day: names_holiday(s.get("quote"), day)))
        linked = linked + [i for i in more if i not in linked]
    return linked


def _hours_words(record, window):
    """The office's words for a window held in its regular hours
    (``HOURS``), or None."""
    hours = _shown(record, f"{window}.hours")
    return hours if isinstance(hours, str) and OFFICE_HOURS.search(hours) else None


def _hours_sources(links, window, hours):
    """The links of a window's hours: a page whose quote holds the office's
    words, its own field's first (rule 84: quoted words keep their source)."""
    words = _plain(hours)
    return links.of(f"{window}.hours", f"{window}.start", f"{window}.end", f"{window}.except",
                    want=lambda s: words in _plain(s.get("quote")))


def lines(code, record, place):
    """The page's lines for one record: ``(lines, register, links)``.

    Each line is ``{"k": kind, "d": date, "e"?: end of a window, "x"?: days
    inside the window it is not held, "h"?: true where the window is held in
    an office's regular hours alone, "t": words,
    "p"?: words once the date has passed, "s": a short label for the
    calendar, "src": [link numbers], "keep"?: still shown after Election
    Day}``; a line with no date is a standing fact. ``register`` is when
    registration for November 3 closes, for the page's lead sentence and the
    "Register to vote" button; ``links`` numbers the sources the lines cite.
    """
    links = _Links(code, record)
    out = []
    if _shown(record, "noElection"):
        out.append({"k": "none", "t": f"No election is held in {place} on November 3, 2026",
                    "src": links.of("noElection")})
        return out, None, links

    reg = record.get("registration") or {}
    if _shown(record, "registration.none"):
        out.append({"k": "noreg", "t": f"{place[:1].upper() + place[1:]} has no voter registration",
                    "src": links.of("registration.none")})
    by_date = {}
    online = _shown(record, "registration.online.deadline")
    if online:
        time = _time(get(record, "registration.online.time"))
        by_date.setdefault(online, []).append(
            ("online", "online" + (f" (until {time})" if time else ""),
             "registration.online.deadline"))
    mailed = _shown(record, "registration.mail.deadline")
    if mailed:
        rule = get(record, "registration.mail.rule")
        by_date.setdefault(mailed, []).append(
            ("mail", "by mail" + {"postmarked": " (postmarked by then)",
                                  "received": " (the form must arrive by then)"}.get(rule, ""),
             "registration.mail.deadline"))
    person = _shown(record, "registration.inPerson.deadline")
    if person:
        by_date.setdefault(person, []).append(("in person", "in person",
                                               "registration.inPerson.deadline"))
    # Whether a reader who misses a deadline can still register and vote at
    # once: True, False, or None where the record does not say. In a
    # same-day state a deadline before Election Day is the *regular*
    # deadline, never the last chance: the first page told Illinois readers
    # "Today is the last day to register" on a day grace-period
    # registration ran on to November 3 (PR #102 review).
    same = True if _shown(record, "registration.sameDay.available") else (
        False if get(reg, "sameDay.available") is False else None)
    every = len(by_date) == 1 and len(next(iter(by_date.values()))) == 3
    for date, methods in sorted(by_date.items()):
        how = _join([m[1] for m in methods])
        short = " / ".join(m[0] if m[0] != "mail" else "by mail" for m in methods)
        if same and date < ELECTION:
            words = (f"Regular deadline to register {how}; after it you can still register "
                     f"and vote at the same time (below)")
            label = "Regular deadline to register" + ("" if every else f": {short}")
        elif same is None:
            words = f"Deadline to register to vote {how}"
            label = "Registration deadline" if every else f"Register {short}"
        else:
            words = f"Last day to register to vote {how}"
            label = "Registration closes" if every else f"Register {short}"
        out.append({"k": "register", "d": date, "t": words, "s": label,
                    "src": links.of(*[m[2] for m in methods])})
    mailed_by = _shown(record, "registration.mailedBallotBy")
    if mailed_by:
        out.append({"k": "mailreg", "d": mailed_by,
                    "t": "Last day to register and still be mailed a ballot; a voter who "
                         "registers after it votes in person",
                    "s": "Register to be mailed a ballot",
                    "src": links.of("registration.mailedBallotBy")})
    register = None
    if by_date:
        last = max(by_date)
        register = {"by": last, "how": _join([m[0] if m[0] != "mail" else "by mail"
                                              for m in by_date[last]])}
    if same:
        where = _shown(record, "registration.sameDay.where")
        excerpts = where_excerpts(where)
        through = _shown(record, "registration.sameDay.through")
        # The office's own words, quoted; never a summary of them.
        quote = ("; in the office's words, " + " … ".join(
            f"“{part.rstrip('.')}”" for part in excerpts)) if excerpts else ""
        line = {"k": "sameday",
                "t": "Same-day registration: you can register and vote at the same time" +
                     (", until this day" if through else "") + quote}
        if through:
            line.update({"d": through, "s": "Same-day registration ends",
                         "p": "Same-day registration ended on this day" + quote})
        quoted = [_plain(p) for p in excerpts]
        line["src"] = links.of(
            "registration.sameDay.where", "registration.sameDay.available",
            want=(lambda s: any(p in _plain(s.get("quote")) for p in quoted)) if quoted else None)
        out.append(line)
        register = dict(register or {}, sameDay=True)
        if through:
            register["through"] = through
    elif register is not None and same is False:
        register["sameDay"] = False

    start, end = _shown(record, "earlyVoting.start"), _shown(record, "earlyVoting.end")
    if start and end:
        # Wisconsin's window is the earliest and latest a municipal clerk may
        # offer, not days every clerk is open (PR #102 review).
        local = _shown(record, "earlyVoting.setLocally")
        closed = _shown(record, "earlyVoting.except") or []
        hours = _hours_words(record, "earlyVoting")
        line = {"k": "early", "d": start, "e": end,
                "t": "In-person early voting" + _excluding(closed) + (
                    ", on the days and hours each local election office sets: it may start "
                    "later or end sooner than these dates" if local else "") + _in_hours(hours),
                "s": "Early voting" + (" (local days)" if local else ""),
                "src": _window_sources(links, "earlyVoting", closed)
                + (links.of("earlyVoting.setLocally") if local else [])}
        if hours:
            line["src"] += [i for i in _hours_sources(links, "earlyVoting", hours)
                            if i not in line["src"]]
            # Held in the office's hours alone: never "Under way" alone
            # (kyc-ballot.js when()).
            line["h"] = True
        if closed:
            # The days the page never calls "Under way" (kyc-ballot.js when()).
            line["x"] = list(closed)
        out.append(line)

    if _shown(record, "mail.allMail"):
        out.append({"k": "allmail", "t": "Every registered voter is mailed a ballot without "
                                         "asking for one",
                    "src": links.of("mail.allMail")})
    elif _shown(record, "mail.noExcuse") is True:
        out.append({"k": "excuse", "t": "Any voter may vote by mail; no reason is needed",
                    "src": links.of("mail.noExcuse")})
    elif _shown(record, "mail.noExcuse") is False:
        out.append({"k": "excuse", "t": "Voting by mail is open only to voters with a reason "
                                        "the law accepts",
                    "src": links.of("mail.noExcuse")})
    request = _shown(record, "mail.requestDeadline.date")
    if request:
        received = get(record, "mail.requestDeadline.rule") == "received"
        out.append({"k": "request", "d": request,
                    "t": "Last day to apply for a mail ballot" +
                         (" (the application must arrive by then)" if received else ""),
                    "s": "Mail ballot application due",
                    "src": links.of("mail.requestDeadline.date")})
    returned = _shown(record, "mail.returnDeadline.date")
    received = _shown(record, "mail.returnDeadline.receivedBy")
    time = _time(get(record, "mail.returnDeadline.time"))
    if get(record, "mail.returnDeadline.rule") == "postmarked" and returned:
        out.append({"k": "postmark", "d": returned,
                    "t": "Mail ballots must be postmarked by this day",
                    "s": "Postmark deadline",
                    "src": links.of("mail.returnDeadline.date", "mail.returnDeadline.rule")})
        if received:
            out.append({"k": "arrive", "d": received, "keep": True,
                        "t": f"Mail ballots postmarked by {_long(returned)} are counted if they "
                             f"arrive by this day",
                        "p": f"The last day for mail ballots postmarked by {_long(returned)} to "
                             f"arrive",
                        "s": "Mailed ballots arrive by",
                        # Its words say "postmarked", so it links a quote that
                        # does (rule 84), as the runoff's arrive line does:
                        # Illinois's, Mississippi's, Nevada's and Virginia's
                        # receipt-day quotes give the day and never the word,
                        # and from the day after the election the postmark line
                        # that linked one is gone (the reader of PR #237).
                        "src": arrive_sources(links, "mail.returnDeadline")})
    elif get(record, "mail.returnDeadline.rule") == "received" and (returned or received):
        due = returned or received
        line = {"k": "return", "d": due,
                "t": "Mail ballots must arrive at the election office by " +
                     (time + " on " if time else "") + "this day",
                "s": "Mail ballots due",
                "src": links.of("mail.returnDeadline.date" if returned
                                else "mail.returnDeadline.receivedBy",
                                "mail.returnDeadline.receivedBy")}
        if due > ELECTION:
            # Ballots still arriving after Election Day are still news then
            # (the Virgin Islands count those received by November 13).
            line.update({"keep": True,
                         "p": "The last day for mail ballots to arrive at the election office"})
        out.append(line)

    runoff = _shown(record, "runoff.date")
    if runoff and code in RUNOFF_WORDS:
        before, after = RUNOFF_WORDS[code]
        short, short_past = RUNOFF_SHORT.get(code, RUNOFF_SHORT_DEFAULT)
        out.append({"k": "runoff", "d": runoff, "t": before, "p": after, "keep": True,
                    "s": short, "sp": short_past, "src": links.of("runoff.date")})
        # After the runoff's own line, which says what it decides: "for the
        # runoff" in each of them is the runoff it names. In the order of
        # their days; the calendar strip sorts every date alike.
        out += sorted(runoff_lines(code, record, links), key=lambda line: line["d"])
    return out, register, links


def runoff_registration_lines(record, links, of, name, needed):
    """The runoff's own registration deadlines (``runoff.registration``),
    said as the general election's are, one line a day: "Last day to
    register to vote by mail (postmarked by then) or in person for a U.S.
    House general election, if one is held". "Last day" only where the
    record says the state has no same-day registration, a word its source
    gives of every election ("registered at least 20 days prior to an
    election"); else "Deadline", claiming nothing more (rule 84). Each is
    kept after Election Day until its day has passed. A line that says
    "postmarked" links a quote that says so, beside the page that gives the
    day (``arrive_sources``' rule): Louisiana's dates page gives November 12,
    its registration questions page the postmark."""
    by_date = {}
    online = _shown(record, "runoff.registration.online.deadline")
    if online:
        time = _time(get(record, "runoff.registration.online.time"))
        by_date.setdefault(online, []).append(
            ("online", "online" + (f" (until {time})" if time else ""),
             "runoff.registration.online.deadline"))
    mailed = _shown(record, "runoff.registration.mail.deadline")
    rule = get(record, "runoff.registration.mail.rule") if mailed else None
    if mailed:
        by_date.setdefault(mailed, []).append(
            ("mail", "by mail" + {"postmarked": " (postmarked by then)",
                                  "received": " (the form must arrive by then)"}.get(rule, ""),
             "runoff.registration.mail.deadline"))
    person = _shown(record, "runoff.registration.inPerson.deadline")
    if person:
        by_date.setdefault(person, []).append(("in person", "in person",
                                               "runoff.registration.inPerson.deadline"))
    last = get(record, "registration.sameDay.available") is False
    out = []
    for date, methods in sorted(by_date.items()):
        how = _join([m[1] for m in methods])
        short = " / ".join(m[0] if m[0] != "mail" else "by mail" for m in methods)
        every = len(by_date) == 1 and len(methods) == 3
        fields = [m[2] for m in methods]
        # Each way's own source: the day of each is the page's word.
        src = []
        for field in fields:
            src = src + [i for i in links.of(field) if i not in src]
        if rule in RULE_WORDS and "runoff.registration.mail.deadline" in fields:
            urls = {links.urls[i] for i in src}
            says = lambda s: bool(RULE_WORDS[rule].search(s.get("quote") or ""))
            if not any(says(s) for field in ("runoff.registration.mail.deadline",
                                             "runoff.registration.mail.rule")
                       for s in _sources(record, field) if s["url"] in urls):
                src = src + [i for i in links.of("runoff.registration.mail.rule",
                                                 "runoff.registration.mail.deadline", want=says)
                             if i not in src]
        out.append({"k": "runoff-register", "d": date, "keep": True,
                    "t": ("Last day to register to vote " if last else "Deadline to register to vote ")
                         + f"{how} {of}",
                    "s": f"{name} registration " + ("closes" if last else "deadline") +
                         ("" if every else f" ({short})") + needed,
                    "src": src})
    return out


def runoff_lines(code, record, links):
    """The runoff's own registration deadlines (``runoff_registration_lines``),
    early voting (with the days the office excludes, ``_excluding``) and
    mail-ballot dates, as the general
    election's are said: each kept after Election Day ("keep") until its day
    has passed, on the reader's calendar, so they go with the runoff but for a
    ballot still arriving after it (rule 84). "For the runoff" where the
    office has set one (``RUNOFF_SET``), else "for a runoff, if one is held"
    (Louisiana's December 12 is "a U.S. House general election", and a strip
    label names whose runoff it is where "Runoff" would read as one for
    Congress: ``RUNOFF_OWN``); never which race went to one or who is in it
    (rule 91)."""
    held = code in RUNOFF_SET
    what, name = RUNOFF_OWN.get(code, RUNOFF_OWN_DEFAULT)
    of = "for the runoff" if held else f"for {what}, if one is held"
    # Inside a sentence the condition is set off on both sides.
    of_mid = of if held else of + ","
    needed = "" if held else ", if needed"
    out = runoff_registration_lines(record, links, of, name, needed)
    start, end = _shown(record, "runoff.earlyVoting.start"), _shown(record, "runoff.earlyVoting.end")
    if start and end:
        sooner = _shown(record, "runoff.earlyVoting.startsBy")
        closed = _shown(record, "runoff.earlyVoting.except") or []
        hours = _hours_words(record, "runoff.earlyVoting")
        line = {"k": "runoff-early", "d": start, "e": end, "keep": True,
                "t": f"In-person early voting {of}" + _excluding(closed) + (
                    f"; it begins as soon as possible, and no later than {_long(start)}"
                    if sooner else "") + _in_hours(hours),
                "s": f"{name} early voting" + needed,
                "src": _window_sources(links, "runoff.earlyVoting", closed)}
        if hours:
            line["src"] += [i for i in _hours_sources(links, "runoff.earlyVoting", hours)
                            if i not in line["src"]]
            line["h"] = True
        if closed:
            line["x"] = list(closed)
        out.append(line)
    request = _shown(record, "runoff.mail.requestDeadline.date")
    if request:
        # An application made in person may be for a ballot picked up there,
        # not mailed (1 CMC 6509(e)): an absentee ballot, then, not a mail one.
        in_person = get(record, "runoff.mail.requestDeadline.how") == "in person"
        received = get(record, "runoff.mail.requestDeadline.rule") == "received"
        out.append({"k": "runoff-request", "d": request, "keep": True,
                    "t": ("Last day to apply in person for an absentee ballot " if in_person
                          else "Last day to apply for a mail ballot ") + of +
                         (" (the application must arrive by then)"
                          if received and not in_person else ""),
                    "s": name + (" absentee application, in person" if in_person
                                 else " mail ballot application due") + needed,
                    "src": links.of("runoff.mail.requestDeadline.date")})
    returned = _shown(record, "runoff.mail.returnDeadline.date")
    received = _shown(record, "runoff.mail.returnDeadline.receivedBy")
    rule = get(record, "runoff.mail.returnDeadline.rule")
    if rule == "postmarked" and returned:
        out.append({"k": "runoff-postmark", "d": returned, "keep": True,
                    "t": f"Mail ballots {of_mid} must be postmarked by this day",
                    "s": f"{name} postmark deadline" + needed,
                    "src": links.of("runoff.mail.returnDeadline.date",
                                    "runoff.mail.returnDeadline.rule")})
        if received:
            out.append({"k": "runoff-arrive", "d": received, "keep": True,
                        "t": f"Mail ballots {of_mid} postmarked by {_long(returned)} are counted if "
                             f"they arrive by this day",
                        "p": f"The last day for mail ballots {of_mid} postmarked by "
                             f"{_long(returned)} to arrive",
                        "s": f"{name} mailed ballots arrive by",
                        # The line says "postmarked", so it links a quote that
                        # does (rule 84): the CNMI's calendar gives the day and
                        # never the word, the law (1 CMC 6213(a)) both, and the
                        # postmark line that linked the law is gone after the
                        # runoff (the second reader of PR #237).
                        "src": arrive_sources(links, "runoff.mail.returnDeadline")})
    elif rule == "received" and (returned or received):
        due = returned or received
        time = _time(get(record, "runoff.mail.returnDeadline.time"))
        out.append({"k": "runoff-return", "d": due, "keep": True,
                    "t": f"Mail ballots {of_mid} must arrive at the election office by " +
                         (time + " on " if time else "") + "this day",
                    "s": f"{name} mail ballots due" + needed,
                    "src": links.of("runoff.mail.returnDeadline.date" if returned
                                    else "runoff.mail.returnDeadline.receivedBy",
                                    "runoff.mail.returnDeadline.receivedBy")})
    return out


_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")


def _long(iso):
    year, month, day = (int(x) for x in iso.split("-"))
    return f"{_MONTHS[month - 1]} {day}"


# A place's own name where its short name is not one (rule 75).
PLACES = {"DC": "the District of Columbia", "MP": "the Northern Mariana Islands",
          "VI": "the U.S. Virgin Islands"}


def place(code):
    from .pages import state_name
    return PLACES.get(code) or state_name(code)


def reread(record, links, checked):
    """The linked sources read after the record's own check, as the page's
    note names them: ``[{"d": day, "labels": [link label, ...]}]``, earliest
    first. The note under the dates says when they were read; a page read by
    hand later (Nevada's Secretary of State's, 2026-10-25) is not "read on
    2026-10-17" (PR #140 review)."""
    days = {}
    for source in record.get("sources") or []:
        day, url = source.get("read"), source.get("url")
        if not day or day <= checked or url not in links.urls:
            continue
        label = links.labels[links.urls.index(url)]
        if label not in days.setdefault(day, []):
            days[day].append(label)
    return [{"d": day, "labels": labels} for day, labels in sorted(days.items())]


def for_page(data, runoffs=None):
    """The build meta's ``voting._dates``: ``{"states": {code: {"lines",
    "urls", "labels", "register"?}}, ...}``, with when the record was read and
    checked. A record that breaks the cache's rules is not sent at all:
    validate fails the build over it, and the page keeps its links."""
    if not data:
        return {}
    if runoffs is None:
        runoffs = override_runoffs()
    states = data.get("states") or {}
    out = {}
    for code, record in sorted(states.items()):
        if code not in JURISDICTIONS or state_problems(code, record, runoffs):
            continue
        found, register, links = lines(code, record, place(code))
        if not found:
            continue
        entry = {"lines": found, "urls": links.urls, "labels": links.labels}
        if register:
            entry["register"] = register
        later = reread(record, links, data.get("checked") or data.get("read") or "")
        if later:
            entry["reread"] = later
        out[code] = entry
    return {"states": out, "election": data.get("election") or ELECTION,
            "read": data.get("read") or "", "checked": data.get("checked") or ""}


def deadlines_known(data, code):
    """Does the record say when *code*'s registration closes, or that it has
    none to close? Then vote.gov's page, a compiled table that states the
    rule in its own words, is not shown beside it (rules 50 and 53)."""
    record = ((data or {}).get("states") or {}).get(code) or {}
    return bool(_shown(record, "noElection") or _shown(record, "registration.none") or any(
        _shown(record, f"registration.{m}.deadline") for m in ("online", "mail", "inPerson")))
