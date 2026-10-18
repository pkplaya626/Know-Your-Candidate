"""What the guide's maps say about each state, and where each fact comes from.

Editorial data, like ``overrides``: every value here was checked against a
primary source before it was written down, and every mode names the sources
that support it. The build turns this into ``data/government.js``; the
guide's map pages draw it with the same map as the partisan map
(``assets/kyc-usmap.js``) and list it, state by state, in their panel.

A map that colours every state is a claim about every state, so a mode
must give each of the fifty a value (and say plainly when D.C. or a
territory is outside it), and ``check()`` refuses a value its legend does
not define or a source the guide does not list. A fact true of a few states
and unknown for the rest is not a map: it stays in the guide's text.

A source about one state is cited only on that state's facts (``scoped``):
Oklahoma's fact on choosing judges cited New Jersey's and Utah's courts,
and Tennessee's senate president an Arizona amendment.

Colours are categories, never parties: ``cat-1`` to ``cat-5`` are teal,
magenta, lime, grey and the text colour (kyc.css), because red, blue, amber
and purple already mean a party on this site.
"""

from . import geo
from .government_text import SOURCES as TEXT_SOURCES
from .normalize import TERRITORIES, US_STATES

STATES = sorted(code for code in set(US_STATES.values()) if code not in TERRITORIES)
OUTSIDE = sorted(TERRITORIES)          # D.C. and the five territories

# Sources the maps cite beyond the guide's text.
SOURCES = dict(TEXT_SOURCES)
SOURCES.update({
    "usc-48-1824": ("48 U.S.C. 1824 (District Court for the Northern Mariana Islands)",
                    "https://www.law.cornell.edu/uscode/text/48/1824"),
    "ncsl-legislators": ("NCSL: Number of Legislators and Length of Terms in Years",
                         "https://www.ncsl.org/resources/details/number-of-legislators-and-length-of-terms-in-years"),
    "bots-4-14": ("Council of State Governments, Book of the States 2022, Table 4.14: "
                  "Lieutenant Governors: Powers and Duties",
                  "https://bookofthestates.org/tables/2022-4-14/"),
    "bots-5-1": ("Council of State Governments, Book of the States 2022, Table 5.1: "
                 "State Courts of Last Resort",
                 "https://bookofthestates.org/tables/2022-5-1/"),
    "bots-5-6": ("Council of State Governments, Book of the States 2022, Table 5.6: "
                 "Selection and Retention of Appellate Court Judges",
                 "https://bookofthestates.org/tables/2022-5-6/"),
    "nj-supreme": ("New Jersey Courts: Supreme Court", "https://www.njcourts.gov/courts/supreme"),
    "ut-sb134": ("Utah S.B. 134 (2026), Court Amendments",
                 "https://le.utah.gov/~2026/bills/static/SB0134.html"),
    "az-prop131": ("Arizona Legislature: S.C.R. 1024 (2021), Proposition 131 (2022)",
                   "https://www.azleg.gov/legtext/55leg/2R/bills/SCR1024P.htm"),
    "census-org02": ("U.S. Census Bureau: 2022 Census of Governments, Table CG2200ORG02, "
                     "Local Governments by Type and State",
                     "https://www2.census.gov/programs-surveys/gus/tables/2022/cog2022_cg2200org02.zip"),
})


def sources_for(mode, code):
    """The sources a state's fact in *mode* cites: the general ones and its
    own (kyc-guide.js reads the same ``scoped`` table)."""
    scoped = mode.get("scoped") or {}
    return [key for key in mode["sources"] if key not in scoped or code in scoped[key]]

# Seats in each legislature (NCSL; Nebraska's one chamber is counted as its
# Senate). They add up to NCSL's national total, 7,386 - check() holds them
# to it, so a slip in one state is caught.
SEATS = {
    "AK": (20, 40), "AL": (35, 105), "AR": (35, 100), "AZ": (30, 60), "CA": (40, 80),
    "CO": (35, 65), "CT": (36, 151), "DE": (21, 41), "FL": (40, 120), "GA": (56, 180),
    "HI": (25, 51), "IA": (50, 100), "ID": (35, 70), "IL": (59, 118), "IN": (50, 100),
    "KS": (40, 125), "KY": (38, 100), "LA": (39, 105), "MA": (40, 160), "MD": (47, 141),
    "ME": (35, 151), "MI": (38, 110), "MN": (67, 134), "MO": (34, 163), "MS": (52, 122),
    "MT": (50, 100), "NC": (50, 120), "ND": (47, 94), "NE": (49, 0), "NH": (24, 400),
    "NJ": (40, 80), "NM": (42, 70), "NV": (21, 42), "NY": (63, 150), "OH": (33, 99),
    "OK": (48, 101), "OR": (30, 60), "PA": (50, 203), "RI": (38, 75), "SC": (46, 124),
    "SD": (35, 70), "TN": (33, 99), "TX": (31, 150), "UT": (29, 75), "VA": (40, 100),
    "VT": (30, 150), "WA": (49, 98), "WI": (33, 99), "WV": (34, 100), "WY": (31, 62),
}
NATIONAL_SEATS = 7386

# Who presides over the state senate (Book of the States 2022, table 4.14).
# Tennessee's and West Virginia's senates elect their own leader, whom the law
# also titles lieutenant governor; five states have no lieutenant governor.
SENATE_PRESIDES = {
    "ltgov": ("AL", "AR", "CA", "CT", "DE", "GA", "ID", "IN", "MI", "MS", "MO", "NE", "NV",
              "NM", "NY", "NC", "ND", "OK", "PA", "SD", "TX", "VT", "VA", "WA"),
    "speaker-ltgov": ("TN", "WV"),
    "elected": ("AK", "CO", "FL", "HI", "IL", "IA", "KS", "KY", "LA", "MD", "MA", "MN", "MT",
                "NJ", "OH", "RI", "SC", "UT", "WI"),
    "none": ("AZ", "ME", "NH", "OR", "WY"),
}
PRESIDES_NOTES = {
    "CA": "By the Senate's practice, the lieutenant governor presides only when invited.",
    "OK": "The lieutenant governor may preside when they choose to.",
    "NE": "Nebraska's Legislature has one chamber, and the lieutenant governor presides over it.",
    "AZ": ("Under a 2022 amendment, Arizona's first lieutenant governor, elected on a ticket with "
           "the governor, takes office in January 2027, with no role in the Senate."),
}

# Each state's court of last resort: its name, justices and term (table 5.1),
# and how a justice is first chosen for a full term (table 5.6). The method
# is grouped by what the voters do: choose among candidates with or without
# party labels, vote to retain an appointee, or have no vote at all.
HIGH_COURTS = {
    # code: (court, justices, term, method, note)
    "AL": ("Supreme Court", 9, "6 years", "partisan", ""),
    "AK": ("Supreme Court", 5, "10 years", "retention", ""),
    "AZ": ("Supreme Court", 7, "6 years", "retention", ""),
    "AR": ("Supreme Court", 7, "8 years", "nonpartisan", ""),
    "CA": ("Supreme Court", 7, "12 years", "retention",
           "The governor appoints, with the consent of the Commission on Judicial Appointments."),
    "CO": ("Supreme Court", 7, "10 years", "retention", ""),
    "CT": ("Supreme Court", 7, "8 years", "appointed",
           "The governor appoints from a commission's candidates, with the legislature's consent."),
    "DE": ("Supreme Court", 5, "12 years", "appointed",
           "The governor appoints from a commission's candidates, with the Senate's consent."),
    "FL": ("Supreme Court", 7, "6 years", "retention", ""),
    "GA": ("Supreme Court", 9, "6 years", "nonpartisan", ""),
    "HI": ("Supreme Court", 5, "10 years", "appointed",
           "The governor appoints from a commission's list, with the Senate's consent; the "
           "commission decides on retention."),
    "ID": ("Supreme Court", 5, "6 years", "nonpartisan", ""),
    "IL": ("Supreme Court", 7, "10 years", "partisan",
           "After the first term, justices stand in retention elections."),
    "IN": ("Supreme Court", 5, "10 years", "retention", ""),
    "IA": ("Supreme Court", 7, "8 years", "retention", ""),
    "KS": ("Supreme Court", 7, "6 years", "retention", ""),
    "KY": ("Supreme Court", 7, "8 years", "nonpartisan", ""),
    "LA": ("Supreme Court", 7, "10 years", "partisan",
           "All candidates appear with party labels in a blanket primary."),
    "ME": ("Supreme Judicial Court", 7, "7 years", "appointed",
           "The governor appoints, with the legislature's consent."),
    "MD": ("Supreme Court of Maryland", 7, "10 years", "retention",
           "Called the Court of Appeals until December 2022."),
    "MA": ("Supreme Judicial Court", 7, "to age 70", "appointed",
           "The governor appoints, with the approval of the elected Governor's Council; "
           "justices serve to age 70."),
    "MI": ("Supreme Court", 7, "8 years", "nonpartisan",
           "Candidates may be nominated by political parties, but the ballot shows no party."),
    "MN": ("Supreme Court", 7, "6 years", "nonpartisan", ""),
    "MS": ("Supreme Court", 9, "8 years", "nonpartisan", ""),
    "MO": ("Supreme Court", 7, "12 years", "retention", ""),
    "MT": ("Supreme Court", 7, "8 years", "nonpartisan",
           "A justice with no opponent stands in a retention election instead."),
    "NE": ("Supreme Court", 7, "6 years", "retention", ""),
    "NV": ("Supreme Court", 7, "6 years", "nonpartisan", ""),
    "NH": ("Supreme Court", 5, "to age 70", "appointed",
           "The governor appoints, with the approval of the elected Executive Council; "
           "justices serve to age 70."),
    "NJ": ("Supreme Court", 7, "7 years at first", "appointed",
           "The governor appoints, with the Senate's consent; a justice reappointed after seven "
           "years serves to age 70."),
    "NM": ("Supreme Court", 5, "8 years", "partisan",
           "After the first term, justices stand in retention elections."),
    "NY": ("Court of Appeals", 7, "14 years", "appointed",
           "The governor appoints from a commission's candidates, with the Senate's consent."),
    "NC": ("Supreme Court", 7, "8 years", "partisan", ""),
    "ND": ("Supreme Court", 5, "10 years", "nonpartisan", ""),
    "OH": ("Supreme Court", 7, "6 years", "partisan", ""),
    "OK": ("Supreme Court", 9, "6 years", "retention",
           "Oklahoma's other highest court, the Court of Criminal Appeals (5 judges), is chosen "
           "the same way."),
    "OR": ("Supreme Court", 7, "6 years", "nonpartisan", ""),
    "PA": ("Supreme Court", 7, "10 years", "partisan",
           "After the first term, justices stand in retention elections."),
    "RI": ("Supreme Court", 5, "for life", "appointed",
           "The governor appoints from a commission's candidates, with the consent of both "
           "chambers; justices serve for life."),
    "SC": ("Supreme Court", 5, "10 years", "legislature", ""),
    "SD": ("Supreme Court", 5, "8 years", "retention", ""),
    "TN": ("Supreme Court", 5, "8 years", "retention",
           "The governor appoints, with the legislature's confirmation."),
    "TX": ("Supreme Court", 9, "6 years", "partisan",
           "Texas's other highest court, the Court of Criminal Appeals (9 judges), is chosen the "
           "same way."),
    "UT": ("Supreme Court", 7, "10 years", "retention",
           "A 2026 law, S.B. 134, enlarged the court from five justices to seven."),
    "VT": ("Supreme Court", 5, "6 years", "appointed",
           "The governor appoints from a commission's candidates, with the Senate's consent; the "
           "legislature votes on retention."),
    "VA": ("Supreme Court", 7, "12 years", "legislature", ""),
    "WA": ("Supreme Court", 9, "6 years", "nonpartisan", ""),
    "WV": ("Supreme Court of Appeals", 5, "12 years", "nonpartisan", ""),
    "WI": ("Supreme Court", 7, "10 years", "nonpartisan", ""),
    "WY": ("Supreme Court", 5, "8 years", "retention", ""),
}
METHOD_PHRASE = {
    "partisan": "elected in contests with party labels on the ballot",
    "nonpartisan": "elected in contests without party labels",
    "retention": "appointed, then kept or removed by voters in retention elections",
    "appointed": "appointed, with no election",
    "legislature": "elected by the legislature",
}

# Public Law 280: the six states the statute names, and the ten that later
# took on some jurisdiction by choice (BIA; 18 U.S.C. 1162; 28 U.S.C. 1360).
PL280_MANDATORY = ("AK", "CA", "MN", "NE", "OR", "WI")
PL280_OPTIONAL = ("AZ", "FL", "ID", "IA", "MT", "NV", "ND", "SD", "UT", "WA")
PL280_EXCEPTIONS = {
    "AK": "The Metlakatla Indian Community also keeps criminal jurisdiction.",
    "MN": "Except the Red Lake Reservation.",
    "OR": "Except the Warm Springs Reservation.",
}
# Oklahoma v. Castro-Huerta, 597 U.S. 629 (2022), syllabus: "the Federal
# Government and the State have concurrent jurisdiction to prosecute crimes
# committed by non-Indians against Indians in Indian country."
CASTRO_HUERTA = ("Since Oklahoma v. Castro-Huerta (2022), the state shares jurisdiction with "
                 "the federal government over crimes non-Indians commit against Indians in "
                 "Indian country.")
# McGirt v. Oklahoma, 591 U.S. 894 (2020), syllabus: land reserved for the
# Creek Nation "remains 'Indian country'" for the Major Crimes Act.
PL280_NOTES = {
    "OK": ("In McGirt v. Oklahoma (2020) the Supreme Court held that the Creek Nation's "
           "reservation remains Indian country, where the state cannot prosecute Indians for "
           "the crimes the Major Crimes Act covers."),
}

# 28 U.S.C. 41, and 48 U.S.C. 1824 for the Northern Mariana Islands.
# American Samoa has no federal district court, so it is in no circuit.
# The circuits and their states: kyc/federal_courts.py's courts of appeals,
# the one table the federal hub's map reads too.
from .federal_courts import circuit_colours as _colours, circuits as _court_circuits

CIRCUITS = _court_circuits()
ORDINAL = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth", "5": "Fifth",
           "6": "Sixth", "7": "Seventh", "8": "Eighth", "9": "Ninth", "10": "Tenth",
           "11": "Eleventh", "DC": "D.C."}
CIRCUIT_SITES = {key: f"https://www.ca{key.lower()}.uscourts.gov/" for key in CIRCUITS}

# Lower chambers that are not called the House of Representatives.
LOWER_CHAMBER = {
    "CA": "Assembly", "NV": "Assembly", "NY": "Assembly", "WI": "Assembly",
    "NJ": "General Assembly",
    "MD": "House of Delegates", "VA": "House of Delegates", "WV": "House of Delegates",
    "NE": None,                         # one chamber
}

# Legislatures whose state constitution names them other than "the
# Legislature" (the legislature page's title: "Virginia General Assembly",
# never "Virginia Legislature"). Massachusetts's constitution styles its
# legislature "the General Court of Massachusetts" (Part II, c. 1, s. 1,
# art. 1) and New Hampshire's "the general court"; Oregon's vests its
# legislative power in "a Legislative Assembly" (art. IV, s. 1), as North
# Dakota's does. Checked 2026-10-16 against Wikipedia's "List of U.S. state
# legislatures" as a lead (rule 50), which names the same 23.
LEGISLATURE_NAME = {
    **{code: "General Assembly" for code in (
        "AR", "CO", "CT", "DE", "GA", "IL", "IN", "IA", "KY", "MD", "MO", "NC", "OH", "PA",
        "RI", "SC", "TN", "VT", "VA")},
    "MA": "General Court", "NH": "General Court",
    "ND": "Legislative Assembly", "OR": "Legislative Assembly",
}

NO_LINE_ITEM_VETO = ("IN", "NV", "NH", "NC", "RI", "VT")


def _names():
    """Names as a sentence uses them: "the District of Columbia"."""
    from .pages import state_name
    return lambda code: ("the " if code == "DC" else "") + state_name(code)


def _join(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# --------------------------------------------------------------------- modes

def _legislature():
    name = _names()
    values, facts = {}, {}
    for code in STATES:
        lower = LOWER_CHAMBER.get(code, "House of Representatives")
        senate, house = SEATS[code]
        if code == "NE":
            values[code] = "one"
            facts[code] = (f"One chamber, the Legislature, whose {senate} members are called "
                           f"senators and are elected without party labels on the ballot.")
        else:
            values[code] = {"House of Representatives": "house", "Assembly": "assembly",
                            "General Assembly": "general", "House of Delegates": "delegates"}[lower]
            facts[code] = (f"Two chambers: a Senate of {senate} members and a {lower} of "
                           f"{house}, {senate + house} legislators in all.")
    return {
        "id": "legislature",
        "label": "Legislature",
        "title": "How each state's legislature is built",
        "kind": "category",
        "legend": [
            ("house", "Senate and House of Representatives", "cat-4"),
            ("assembly", "Senate and Assembly", "cat-1"),
            ("general", "Senate and General Assembly", "cat-3"),
            ("delegates", "Senate and House of Delegates", "cat-2"),
            ("one", "One chamber", "cat-5"),
        ],
        "values": values,
        "facts": facts,
        "outside": "Not a state: this map covers the 50 state legislatures.",
        "about": ("Every state but Nebraska has a legislature of two chambers. The upper is the "
                  "Senate; the lower is usually the House of Representatives, but the Assembly in "
                  "four states, the General Assembly in New Jersey and the House of Delegates in "
                  "three. Pick a state to see its own."),
        "sources": ["ncsl-legislators", "nebraska", "nebraska-senators"],
        "scoped": {"nebraska": ["NE"], "nebraska-senators": ["NE"]},
    }


def figures():
    """Counts the guide's text states, from the tables its maps draw (rule
    73): ``{{ltgov-presides}}`` in a sentence is this table's count."""
    from . import ballot2026
    ballot = ballot2026.stats()
    return {
        "ltgov-presides": len(SENATE_PRESIDES["ltgov"]),
        "no-ltgov": _word(len(SENATE_PRESIDES["none"])),
        "governors-2026": ballot["governor"],
        "chambers": ballot["chambers"],
        "chambers-2026": ballot["chambersUp"],
    }


def _word(n):
    """A small count as a sentence starts it."""
    words = ("No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten")
    return words[n] if n < len(words) else str(n)


def _presides():
    of = {code: key for key, codes in SENATE_PRESIDES.items() for code in codes}
    phrase = {
        "ltgov": "The lieutenant governor is the president of the Senate.",
        "speaker-ltgov": ("The Senate elects its own leader, who by law also holds the title of "
                          "lieutenant governor."),
        "elected": ("The Senate elects its own president. The state has a lieutenant governor, "
                    "who does not preside."),
        "none": "The state has no lieutenant governor; the Senate elects its own president.",
    }
    facts = {code: (PRESIDES_NOTES[code] if code == "NE" else
                    phrase[of[code]] + (" " + PRESIDES_NOTES[code] if code in PRESIDES_NOTES else ""))
             for code in STATES}
    return {
        "id": "presides",
        "label": "Senate president",
        "title": "Who presides over the state senate",
        "kind": "category",
        "legend": [
            ("ltgov", "The lieutenant governor", "cat-1"),
            ("speaker-ltgov", "Its own leader, titled lieutenant governor", "cat-3"),
            ("elected", "A president the Senate elects", "cat-4"),
            ("none", "No lieutenant governor", "cat-2"),
        ],
        "values": {code: of[code] for code in STATES},
        "facts": facts,
        "outside": "Not a state: this map covers the 50 state senates.",
        "about": (f"In {len(SENATE_PRESIDES['ltgov'])} states the lieutenant governor is the "
                  "president of the senate, presiding and breaking ties; elsewhere the senate "
                  "elects its own president. Tennessee's and West Virginia's senates elect a "
                  "leader whom the law also calls lieutenant governor, and "
                  f"{_word(len(SENATE_PRESIDES['none'])).lower()} states have no lieutenant "
                  "governor at all. As compiled by the Council of State Governments in 2022."),
        "sources": ["bots-4-14", "ncsl-leaders", "az-prop131"],
        "scoped": {"az-prop131": ["AZ"]},
    }


def _judges():
    values, facts = {}, {}
    for code in STATES:
        court, justices, term, method, note = HIGH_COURTS[code]
        values[code] = method
        tenure = f"for {term}" if term[0].isdigit() else term
        facts[code] = (f"The {court}'s {justices} justices are {METHOD_PHRASE[method]}, and serve "
                       f"{tenure}." + (" " + note if note else ""))
    return {
        "id": "judges",
        "label": "Choosing judges",
        "title": "How each state chooses the justices of its highest court",
        "kind": "category",
        "legend": [
            ("partisan", "Elected, with party labels", "cat-2"),
            ("nonpartisan", "Elected, without party labels", "cat-1"),
            ("retention", "Appointed, then retention elections", "cat-3"),
            ("appointed", "Appointed, no election", "cat-4"),
            ("legislature", "Elected by the legislature", "cat-5"),
        ],
        "values": values,
        "facts": facts,
        "outside": "Not a state: this map covers the 50 state high courts.",
        "about": ("States choose the justices of their highest court in five ways: contested "
                  "elections with or without party labels on the ballot; appointment followed by "
                  "retention elections, in which voters say yes or no to keeping a justice (often "
                  "called the Missouri Plan); appointment with no election; or election by the "
                  "legislature. Vacancies between elections are usually filled by appointment. "
                  "From the Council of State Governments' 2022 tables, checked for changes "
                  "through October 2026: Maryland renamed its high court in 2022, and Utah "
                  "enlarged its own in 2026."),
        "sources": ["bots-5-1", "bots-5-6", "nj-supreme", "ut-sb134", "mo-plan"],
        # The Missouri Plan is what a retention state's method is called.
        "scoped": {"nj-supreme": ["NJ"], "ut-sb134": ["UT"],
                   "mo-plan": [c for c in STATES if HIGH_COURTS[c][3] == "retention"]},
    }


def _veto():
    values = {code: ("no" if code in NO_LINE_ITEM_VETO else "yes") for code in STATES}
    facts = {code: ("The governor can veto single items in a spending bill without vetoing "
                    "the whole bill." if v == "yes" else
                    "The governor cannot veto single items in a spending bill: one of the six "
                    "states without a line-item veto.") for code, v in values.items()}
    return {
        "id": "veto",
        "label": "Line-item veto",
        "title": "Can the governor veto one item in a spending bill?",
        "kind": "category",
        "legend": [("yes", "Line-item veto", "cat-1"), ("no", "No line-item veto", "cat-2")],
        "values": values,
        "facts": facts,
        "outside": "Not a state: this map covers the 50 governors.",
        "about": ("Governors in 44 states can strike individual items from a spending bill and sign "
                  "the rest. The governors of Indiana, Nevada, New Hampshire, North Carolina, Rhode "
                  "Island and Vermont cannot: they sign or veto a bill whole."),
        "sources": ["ncsl-veto"],
    }


def _circuit_colours():
    """A colour for each circuit such that no two neighbouring circuits share
    one (kyc/federal_courts.circuit_colours, over the atlas's borders)."""
    return _colours(geo.neighbours())


def _circuits():
    name = _names()
    colour = _circuit_colours()
    values, facts, labels = {}, {}, {}
    for key, codes in CIRCUITS.items():
        members = [name(c) for c in codes]
        what = "the D.C. Circuit" if key == "DC" else f"the {ORDINAL[key]} Circuit"
        for code in codes:
            values[code] = key
            labels[code] = key
            facts[code] = (f"Appeals from its federal district court go to {what}, which also "
                           f"hears appeals from {_join([m for m in members if m != name(code)])}."
                           if len(codes) > 1 else
                           f"Appeals from its federal district court go to {what}, which serves "
                           f"it alone.")
    facts["AS"] = ("American Samoa has no federal district court, so it is in no circuit: its "
                   "High Court is a territorial court.")
    values["AS"] = "none"
    labels["AS"] = "–"
    return {
        "id": "circuits",
        "label": "Circuits",
        "title": "Which court of appeals hears each state's federal appeals",
        "kind": "category",
        "legend": [(key, ("D.C. Circuit" if key == "DC" else f"{ORDINAL[key]} Circuit"),
                    colour[key]) for key in CIRCUITS] + [("none", "No federal court", "none")],
        "values": values,
        "facts": facts,
        "labels": labels,
        "links": {code: (f"The {ORDINAL[v]} Circuit's site" if v != "DC" else
                         "The D.C. Circuit's site", CIRCUIT_SITES[v])
                  for code, v in values.items() if v in CIRCUIT_SITES},
        "about": ("The country's federal district courts are grouped into twelve regional "
                  "circuits, each with a court of appeals. The number on each state is its circuit. "
                  "A thirteenth court, the Federal Circuit, hears certain kinds of appeal (patents, "
                  "trade, money claims against the United States) from everywhere."),
        "sources": ["usc-28-41", "usc-48-1824", "usc-28-1295", "uscourts-structure"],
        "scoped": {"usc-48-1824": ["MP"]},
    }


def _pl280():
    values, facts = {}, {}
    for code in STATES:
        if code in PL280_MANDATORY:
            values[code] = "mandatory"
            facts[code] = ("Public Law 280 (1953) gave the state criminal jurisdiction over most of "
                           "the Indian country within it, in place of the federal government, and "
                           "opened its courts to private civil suits arising there. "
                           + PL280_EXCEPTIONS.get(code, ""))
        elif code in PL280_OPTIONAL:
            values[code] = "optional"
            facts[code] = ("The state later took on some jurisdiction over Indian country by "
                           "choice, under Public Law 280; how much varies, and some has since been "
                           "returned. " + CASTRO_HUERTA)
        else:
            values[code] = "no"
            # Not "tribal and federal courts only": since Oklahoma v.
            # Castro-Huerta (2022) states share jurisdiction over many crimes
            # by non-Indians in Indian country, PL-280 or not - and the fact
            # now says so, where it only said "other laws and court decisions".
            facts[code] = ("Not a Public Law 280 state. " + CASTRO_HUERTA + " Other "
                           "jurisdiction in Indian country here is divided among tribal, federal "
                           "and state governments by other laws and court decisions. "
                           + PL280_NOTES.get(code, ""))
    return {
        "id": "pl280",
        "label": "Public Law 280",
        "title": "Where states took over jurisdiction in Indian country",
        "kind": "category",
        "legend": [("mandatory", "Named in the 1953 law", "cat-2"),
                   ("optional", "Took some jurisdiction by choice", "cat-1"),
                   ("no", "Neither", "cat-4")],
        "values": values,
        "facts": {k: v.strip() for k, v in facts.items()},
        "outside": "Not a state: Public Law 280 applies only to states.",
        "about": ("Public Law 280 (1953) gave six states criminal jurisdiction over most of the "
                  "Indian country within them, in place of the federal government. Ten more states "
                  "later took on some jurisdiction by choice. It did not let states regulate or tax "
                  "tribes (Bryan v. Itasca County, 1976). Every state, Public Law 280 or not, now "
                  "shares jurisdiction with the federal government over crimes non-Indians "
                  "commit against Indians there (Oklahoma v. Castro-Huerta, 2022)."),
        "sources": ["usc-18-1162", "usc-28-1360", "bia-pl280", "bryan", "castro-huerta",
                    "mcgirt"],
        "scoped": {"castro-huerta": [c for c in STATES if c not in PL280_MANDATORY],
                   "mcgirt": ["OK"]},
    }


# The local map's views: one per kind of government the Census counts.
LOCAL_KINDS = (
    ("total", "All", "Local governments of every kind", "local government", "local governments"),
    ("county", "Counties", "County governments", "county government", "county governments"),
    ("municipal", "Cities and towns", "Municipal governments: cities, towns, villages and boroughs",
     "municipal government", "municipal governments"),
    ("township", "Townships", "Town and township governments",
     "town or township government", "town or township governments"),
    ("school", "School districts", "Independent school districts",
     "independent school district", "independent school districts"),
    ("special", "Special districts", "Special districts",
     "special district", "special districts"),
)
NONE_OF_KIND = {
    "county": "No county governments.",
    "township": "No town or township governments.",
    "school": ("No independent school districts: its public schools are run by the state, a county "
               "or a city, as dependent school systems."),
}
# A count that reads as something it is not. Virginia's one "independent
# school district" in the Census table is no school system: the 2022
# listing files Eastern Virginia Medical School (Norfolk) as one, and
# Virginia's public schools are dependent systems of its counties and
# cities (cog-isd). Said wherever the count is: the guide's school map and
# the counties directory. tests/test_localgov.py holds the listing to it.
COUNT_NOTES = {
    ("VA", "school"): ("The one is Eastern Virginia Medical School, in Norfolk, which the Census "
                       "Bureau's 2022 listing files as a school district; Virginia's public schools "
                       "are dependent systems of its counties and cities."),
}


def _bins(numbers):
    """Five ranges for a map's shades, with round edges, from the spread of
    the counts themselves: deterministic, so the build is reproducible."""
    values = sorted(n for n in numbers if n)
    if not values:
        return []
    # Round numbers a reader can hold in mind: 1, 2 and 5 times a power of ten.
    nice = sorted({m * 10 ** e for e in range(0, 6) for m in (1, 2, 5)})
    edges = []
    for q in (0.2, 0.4, 0.6, 0.8):
        raw = values[min(len(values) - 1, int(q * len(values)))]
        edge = min(nice, key=lambda n: abs(n - raw))
        if edge > 1 and (not edges or edge > edges[-1]):
            edges.append(edge)
    return edges


def _local_about(kind, census_cache):
    """What a local view shows, in words worked out from the same table, so
    no count in it can disagree with the map."""
    state_name = _names()
    states = census_cache["states"]
    total = census_cache["national"][kind]
    none = [state_name(c) for c in sorted(states, key=lambda c: state_name(c).replace("the ", ""))
            if states[c][kind] is None]
    if kind == "total":
        ranked = sorted((v["total"], c) for c, v in states.items() if c != "DC")
        return (f"The Census Bureau counted {total:,} local governments in 2022: the most in "
                f"{state_name(ranked[-1][1])} ({ranked[-1][0]:,}), the fewest among the states in "
                f"{state_name(ranked[0][1])} ({ranked[0][0]:,}).")
    if kind == "county":
        return (f"{total:,} county governments in 2022. Louisiana's are called parishes, and "
                f"Alaska's organized boroughs are counted as counties. {_join(none)} have none. "
                f"Elsewhere some county areas have no county government of their own: a city and "
                f"county governed as one, an independent city outside any county, or an area "
                f"with no government. Pick a state to see which.")
    if kind == "municipal":
        return f"{total:,} cities, towns, villages and boroughs in 2022."
    if kind == "township":
        having = sum(1 for v in states.values() if v["township"])
        return (f"{total:,} town and township governments in 2022, in {having} states, all in the "
                f"Midwest and the Northeast. Elsewhere there are none.")
    if kind == "school":
        return (f"{total:,} independent school districts in 2022. {_join(none)} had none: their "
                f"public schools are run by the state, a county or a city.")
    return (f"{total:,} special districts in 2022, for water, fire protection, transit, hospitals "
            f"and much else: the most numerous kind of local government.")


def _local(census_cache):
    from . import county_areas
    from .pages import state_name
    states = census_cache["states"]
    the = _names()
    out = []
    for kind, label, title, one, many in LOCAL_KINDS:
        numbers = [states[c][kind] for c in states if states[c][kind] is not None]
        edges = _bins(numbers)
        legend, keys = [], []
        low = 1
        for i, edge in enumerate(edges + [None]):
            key = f"b{i + 1}"
            text = (f"{low:,}–{edge - 1:,}" if edge is not None and edge - 1 > low else
                    f"{low:,}" if edge is not None else f"{low:,} or more")
            legend.append((key, text, f"scale-{i + 1}"))
            keys.append((low, edge, key))
            low = edge if edge is not None else low
        legend.append(("zero", "None", "none"))
        values, facts = {}, {}
        for code, counts in states.items():
            n = counts[kind]
            # A state whose county areas are not all governed by a county
            # says why, in the counties directory's words (county_areas).
            why = county_areas.directory_note(code) if kind == "county" else ""
            if not n:
                values[code] = "zero"
                facts[code] = why or NONE_OF_KIND.get(kind, f"No {many}.")
                continue
            values[code] = next(k for lo, hi, k in keys if hi is None or n < hi)
            why = " ".join(filter(None, (why, COUNT_NOTES.get((code, kind)))))
            facts[code] = f"{n:,} {one if n == 1 else many} in 2022." + (" " + why if why else "")
        if kind == "total":
            for code, counts in states.items():
                parts = []
                for k, _, _, o, m in LOCAL_KINDS[1:]:
                    if counts[k]:
                        parts.append(f"{counts[k]:,} {o if counts[k] == 1 else m}")
                facts[code] = (f"{the(code)[0].upper() + the(code)[1:]} had {counts['total']:,} local "
                               f"{'government' if counts['total'] == 1 else 'governments'} in 2022: "
                               + _join(parts) + ".")
        out.append({
            "id": f"local-{kind}",
            "label": label,
            "title": title + ", by state",
            "kind": "category",
            "legend": legend,
            "values": values,
            "facts": facts,
            "outside": "A territory: the Census of Governments covers the states and D.C.",
            "about": _local_about(kind, census_cache),
            "sources": ["census-org02", "cog-isd"],
        })
    return out


# The shades of the tribal-governments map: how many governments the
# directory lists with an office in the state. Fixed edges, so a weekly
# re-read moves a state between shades only when its count crosses one.
TRIBE_BINS = ((1, 4, "1–4", "scale-1"), (5, 19, "5–19", "scale-3"), (20, None, "20 or more", "scale-5"))


def _tribes(cache):
    """Tribal governments by the state of their office, and who leads each,
    as the BIA's Tribal Leaders Directory lists them (kyc/tribes.py). The
    count is the directory's rows for that state, never a count of nations
    beside the Federal Register's 575 (rule 53), and no total is given."""
    from . import tribes
    name = _names()
    found, _ = tribes.placed(cache)
    edited = cache.get("edited")
    as_of = f", as it stood on {_date_words(edited)}" if edited else ""
    values, facts, lists = {}, {}, {}
    for code in STATES:
        here = sorted(found.get(code) or [], key=lambda e: e["name"].lower())
        n = len(here)
        the = name(code)
        if not n:
            values[code] = "none"
            facts[code] = (f"The directory lists no tribal government with its office in {the}. It "
                           "lists each government in the one state its office is in.")
            continue
        values[code] = next(key for lo, hi, key, _ in
                            ((lo, hi, f"b{i}", t) for i, (lo, hi, _, t) in enumerate(TRIBE_BINS))
                            if n >= lo and (hi is None or n <= hi))
        facts[code] = (f"The directory lists {n} tribal "
                       f"{'government' if n == 1 else 'governments'} with an office in {the}"
                       f"{as_of}, and who leads each.")
        lists[code] = [[e["name"], e.get("leader") or "", e.get("title") or "",
                        [[a["name"], a.get("leader") or "", a.get("title") or ""]
                         for a in e["affiliates"]]] for e in here]
    return {
        "id": "tribes",
        "label": "Tribal governments",
        "title": "Tribal governments by the state of their office",
        "kind": "category",
        "legend": [(f"b{i}", text, token) for i, (_, _, text, token) in enumerate(TRIBE_BINS)]
                  + [("none", "No office listed", "none")],
        "values": values,
        "facts": facts,
        "lists": lists,
        "outside": "Not a state: this map covers the 50 states.",
        "about": ("Each tribal government and its leader, as the Bureau of Indian Affairs' Tribal "
                  "Leaders Directory lists them, under the state its office is in: a nation whose "
                  "lands reach into several states is listed in one. Bands and communities the "
                  "directory lists under a tribe are named with it. BIA updates the directory "
                  "weekly and warns that tribal elections can change a leader before it does."),
        "sources": ["bia-tld"],
    }


def _date_words(iso):
    """"October 16, 2026" for "2026-10-16"."""
    import datetime
    day = datetime.date.fromisoformat(iso[:10])
    return f"{day:%B} {day.day}, {day.year}"


def _ballot():
    """What each state elects on November 3, 2026 (kyc/ballot2026.py, each
    value from the state's own record), coloured by whether the governor
    and the legislature are on the ballot. The state's own sources are cited
    on its fact alone."""
    from . import ballot2026
    titles = {"governor": "governor", "lt": "lieutenant governor", "ag": "attorney general",
              "sos": "secretary of state"}
    values, facts, scoped, sources = {}, {}, {}, []
    for code in STATES:
        record = ballot2026.for_state(code)
        offices = [titles[o] for o in ballot2026.OFFICES if record["offices"][o]["up"]]
        seats = []
        for which in ("upper", "lower"):
            chamber = record["chambers"].get(which)
            if chamber and chamber["up"]:
                seats.append((f"all {chamber['seats']} seats" if chamber["up"] == chamber["seats"]
                              else f"{chamber['up']} of the {chamber['seats']} seats")
                             + f" in the {chamber['name']}")
        governor = record["offices"]["governor"]["up"]
        values[code] = ("both" if governor and seats else "governor" if governor else
                        "legislature" if seats else "neither")
        parts = ([_join(offices)] if offices else []) + ([_join(seats)] if seats else [])
        facts[code] = ("On the ballot: " + "; ".join(parts) + "." if parts else
                       "No election for governor, lieutenant governor, attorney general or "
                       "secretary of state, and no regular legislative elections, on the 2026 "
                       "ballot.")
        # Each state's own records, cited on its fact alone.
        urls = []
        for field in ballot2026.OFFICES:
            urls.append(record["offices"][field]["source"])
        for chamber in record["chambers"].values():
            urls.append(chamber["source"])
        for url in dict.fromkeys(urls):
            key = "ballot-" + url
            SOURCES.setdefault(key, (_host_title(code, url), url))
            if key not in scoped:
                sources.append(key)
            scoped.setdefault(key, set()).add(code)
    return {
        "id": "ballot",
        "label": "2026 ballot",
        "title": "What each state elects on November 3, 2026",
        "kind": "category",
        "legend": [
            ("both", "Governor and legislative seats", "cat-1"),
            ("legislature", "Legislative seats, no governor", "cat-3"),
            ("governor", "Governor, no legislative seats", "cat-2"),
            ("neither", "Neither", "cat-4"),
        ],
        "values": values,
        "facts": facts,
        "outside": "Not a state: this map covers the 50 states' own offices.",
        "about": (f"{ballot2026.stats()['governor']} states elect a governor on November 3, "
                  f"2026, and {ballot2026.stats()['chambersUp']} of the "
                  f"{ballot2026.stats()['chambers']} state legislative chambers hold regular "
                  "elections. Pick a state for the statewide offices and the legislative seats "
                  "it elects, each from the state's own constitution, statutes or election "
                  "pages. Special elections to fill a vacancy are not counted."),
        "sources": sources,
        "scoped": {key: sorted(codes) for key, codes in scoped.items()},
    }


def _host_title(code, url):
    """A state's record named by whose it is: "Texas: sos.state.tx.us"."""
    from urllib.parse import urlsplit
    from .pages import state_name
    host = urlsplit(url).netloc
    host = host[4:] if host.startswith("www.") else host
    return f"{state_name(code)}'s own record ({host})"


def modes(root="."):
    """``{page slug: [mode, ...]}`` for every guide page that has a map."""
    from . import census
    found = {
        "states": [_legislature(), _presides(), _veto(), _judges(), _ballot()],
        "courts": [_circuits()],
        "tribal": [_pl280()],
    }
    cache = census.load_cache(root)
    if cache:
        found["local"] = _local(cache)
    from . import tribes
    leaders = tribes.load_cache(root)
    if leaders:
        found["tribal"].append(_tribes(leaders))
    return found


# ------------------------------------------------------------------ payload

def payload():
    """What ``data/government.js`` holds: each mode as the page draws it, and
    the sources they cite."""
    out = {"modes": {}, "pages": {}, "sources": {}}
    for page, items in modes().items():
        out["pages"][page] = [m["id"] for m in items]
        for m in items:
            entry = {
                "label": m["label"],
                "title": m["title"],
                "kind": m["kind"],
                "legend": [{"key": k, "label": text, "token": token} for k, text, token in m["legend"]],
                "values": m["values"],
                "facts": m["facts"],
                "outside": m.get("outside", ""),
                "sources": list(m["sources"]),
            }
            for key in ("labels", "links", "scoped", "lists"):
                if m.get(key):
                    entry[key] = m[key]
            out["modes"][m["id"]] = entry
            for key in m["sources"]:
                out["sources"][key] = list(SOURCES[key])
    # What each legislature is called, so the guide's link to its page reads
    # as the page does ("Virginia General Assembly", not "... Legislature").
    out["legislatureNames"] = dict(sorted(LEGISLATURE_NAME.items()))
    return out


def check():
    """Problems with the maps' data, as strings; empty when it is sound."""
    problems = []
    seen = set()
    for page, items in modes().items():
        for m in items:
            where = f"{page}/{m['id']}"
            if m["id"] in seen:
                problems.append(f"{where}: mode id used twice")
            seen.add(m["id"])
            keys = {k for k, _, _ in m["legend"]}
            missing = [c for c in STATES if c not in m["values"]]
            if missing:
                problems.append(f"{where}: no value for {', '.join(missing)}")
            for code, value in m["values"].items():
                if value not in keys:
                    problems.append(f"{where}: {code} has {value!r}, not in the legend")
                if code not in m["facts"]:
                    problems.append(f"{where}: {code} has a value but no fact")
            for code in OUTSIDE:
                if code not in m["values"] and not m.get("outside"):
                    problems.append(f"{where}: says nothing about {code}")
            for key in m["sources"]:
                if key not in SOURCES:
                    problems.append(f"{where}: unknown source {key!r}")
            for key, codes in (m.get("scoped") or {}).items():
                if key not in m["sources"]:
                    problems.append(f"{where}: scoped source {key!r} is not among its sources")
                if not codes:
                    problems.append(f"{where}: scoped source {key!r} names no state")
            # Every state's fact cites at least one source.
            for code in m["values"]:
                if not sources_for(m, code):
                    problems.append(f"{where}: {code}'s fact cites no source")
            for token in {t for _, _, t in m["legend"]}:
                if token not in ("cat-1", "cat-2", "cat-3", "cat-4", "cat-5", "none",
                                 "scale-1", "scale-2", "scale-3", "scale-4", "scale-5"):
                    problems.append(f"{where}: colour {token!r} is not a category colour")
    if sum(s + h for s, h in SEATS.values()) != NATIONAL_SEATS:
        problems.append(f"legislature seats add up to {sum(s + h for s, h in SEATS.values())}, "
                        f"not NCSL's {NATIONAL_SEATS}")
    placed = [c for codes in SENATE_PRESIDES.values() for c in codes]
    if sorted(placed) != STATES:
        problems.append("SENATE_PRESIDES must place each of the 50 states exactly once")
    if sorted(HIGH_COURTS) != STATES:
        problems.append("HIGH_COURTS must cover each of the 50 states exactly once")
    found = modes()
    if "local" not in found:
        problems.append("no data/census_governments.json: run 'python build_profile_site.py census'")
    if not any(m["id"] == "tribes" for m in found["tribal"]):
        problems.append("no data/tribal_leaders.json: run 'python build_profile_site.py tribes'")
    else:
        from . import tribes
        problems += [f"tribal_leaders.json: {p}" for p in tribes.problems(tribes.load_cache())]
    return problems
