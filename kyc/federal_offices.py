"""The federal executive offices this site follows, as a curated table.

The fifteen executive departments are the ones 5 U.S.C. 101 lists, in the
order 3 U.S.C. 19(d)(1) puts their heads in the line of presidential
succession - an order taken from the statute, never from a page (the White
House's Cabinet page lists people by surname). The other offices are the
ones the White House's own Cabinet page counts as Cabinet-level; that page
is the authority on which officials it designates, and on nothing else
(rule 55).

Each office keeps:

- ``titles`` - the titles the White House's page may give it. "Secretary of
  War" is the Secretary of Defense's secondary title under Executive Order
  14347 (90 FR 43893, 2025-09-05); 10 U.S.C. 113 and 3 U.S.C. 19 still say
  Defense, and so does this table's ``office``. A title the table does not
  know stops the read rather than dropping a person (see federal.py).
- ``senate`` - the office as the Senate's roll-call votes name it ("to be
  Secretary of Defense"), how a confirmation is found.
- ``pages`` - the office's own pages, tried in order, where its head is
  named beside the title (rule 56). Several departments refuse scripted
  requests (403); a refusal concludes nothing (rule 8), and an office with
  no readable page is shown as the White House lists it, attributed. These
  addresses change: a page that stops naming anyone is reported, and the
  table is fixed by hand, like ``courts.COURTS``.
- ``pageTitle`` - the title as the office's page writes it before or after
  the name, folded (``officers._fold``): lower case, no punctuation.

Checked 2026-10-16 against whitehouse.gov/administration/cabinet/, each
office's page, and the Senate's 119th-Congress roll-call votes.
"""

import re

REVIEWED = "2026-10-16"

CABINET_URL = "https://www.whitehouse.gov/administration/cabinet/"
ADMINISTRATION_URL = "https://www.whitehouse.gov/administration/"

# A title on the head's own page, folded, before or after the name. A bare
# "secretary" or "administrator" there is the department's own (its page
# says "Secretary Doug Burgum"); a deputy's, under secretary's or former
# holder's is excluded by federal.names_holder.
_SECRETARY = r"\bsecretary"

DEPARTMENTS = (
    {"key": "state", "wikidata": "Q14213", "office": "Secretary of State", "body": "Department of State",
     "titles": ("Secretary of State",), "senate": ("Secretary of State",),
     "pages": ("https://www.state.gov/biographies/marco-rubio/",),
     "pageTitle": r"secretary of state|" + _SECRETARY},
    {"key": "treasury", "wikidata": "Q4215834", "office": "Secretary of the Treasury", "body": "Department of the Treasury",
     "titles": ("Secretary of the Treasury",), "senate": ("Secretary of the Treasury",),
     "pages": ("https://home.treasury.gov/about/general-information/officials",),
     "pageTitle": r"secretary of the treasury|treasury secretary|" + _SECRETARY},
    {"key": "defense", "wikidata": "Q735015", "office": "Secretary of Defense", "body": "Department of Defense",
     "titles": ("Secretary of Defense", "Secretary of War"), "senate": ("Secretary of Defense",),
     "pages": ("https://www.war.gov/About/Biographies/",),
     "pageTitle": r"secretary of (?:defense|war)|" + _SECRETARY},
    {"key": "justice", "wikidata": "Q636207", "office": "Attorney General", "body": "Department of Justice",
     "titles": ("Attorney General",), "senate": ("Attorney General",),
     "pages": ("https://www.justice.gov/ag",),
     "pageTitle": r"attorney general"},
    {"key": "interior", "wikidata": "Q2287650", "office": "Secretary of the Interior", "body": "Department of the Interior",
     "titles": ("Secretary of the Interior",), "senate": ("Secretary of the Interior",),
     "pages": ("https://www.doi.gov/secretary-doug-burgum",),
     "pageTitle": r"secretary of the interior|" + _SECRETARY},
    {"key": "agriculture", "wikidata": "Q1029955", "office": "Secretary of Agriculture", "body": "Department of Agriculture",
     "titles": ("Secretary of Agriculture",), "senate": ("Secretary of Agriculture",),
     "pages": ("https://www.usda.gov/our-agency/about-usda/our-secretary",),
     "pageTitle": r"secretary of agriculture|agriculture secretary|" + _SECRETARY},
    {"key": "commerce", "wikidata": "Q2003296", "office": "Secretary of Commerce", "body": "Department of Commerce",
     "titles": ("Secretary of Commerce",), "senate": ("Secretary of Commerce",),
     "pages": ("https://www.commerce.gov/about/leadership/howard-lutnick",),
     "pageTitle": r"secretary of commerce|commerce secretary|" + _SECRETARY},
    {"key": "labor", "wikidata": "Q967750", "office": "Secretary of Labor", "body": "Department of Labor",
     "titles": ("Secretary of Labor",), "senate": ("Secretary of Labor",),
     "pages": ("https://www.dol.gov/agencies/osec",),
     "pageTitle": r"secretary of labor|labor secretary|" + _SECRETARY},
    {"key": "hhs", "wikidata": "Q2305968", "office": "Secretary of Health and Human Services",
     "body": "Department of Health and Human Services",
     "titles": ("Secretary of Health and Human Services",),
     "senate": ("Secretary of Health and Human Services",),
     "pages": ("https://www.hhs.gov/about/leadership/index.html",),
     "pageTitle": r"secretary of health and human services|hhs secretary|" + _SECRETARY},
    {"key": "hud", "wikidata": "Q2419581", "office": "Secretary of Housing and Urban Development",
     "body": "Department of Housing and Urban Development",
     "titles": ("Secretary of Housing and Urban Development",),
     "senate": ("Secretary of Housing and Urban Development",),
     "pages": ("https://www.hud.gov/aboutus/secretary",),
     "pageTitle": r"secretary of housing and urban development|hud secretary|" + _SECRETARY},
    {"key": "transportation", "wikidata": "Q967737", "office": "Secretary of Transportation",
     "body": "Department of Transportation",
     "titles": ("Secretary of Transportation",), "senate": ("Secretary of Transportation",),
     "pages": ("https://www.transportation.gov/meet-secretary",),
     "pageTitle": r"secretary of transportation|transportation secretary|" + _SECRETARY},
    {"key": "energy", "wikidata": "Q1029968", "office": "Secretary of Energy", "body": "Department of Energy",
     "titles": ("Secretary of Energy",), "senate": ("Secretary of Energy",),
     "pages": ("https://www.energy.gov/",),
     "pageTitle": r"secretary of energy|energy secretary|" + _SECRETARY},
    {"key": "education", "wikidata": "Q967762", "office": "Secretary of Education", "body": "Department of Education",
     "titles": ("Secretary of Education",), "senate": ("Secretary of Education",),
     "pages": ("https://www.ed.gov/about/ed-organization/leadership-directory",),
     "pageTitle": r"secretary of education|education secretary|" + _SECRETARY},
    {"key": "veterans", "wikidata": "Q1658460", "office": "Secretary of Veterans Affairs",
     "body": "Department of Veterans Affairs",
     "titles": ("Secretary of Veterans Affairs",), "senate": ("Secretary of Veterans Affairs",),
     "pages": ("https://department.va.gov/about/", "https://www.va.gov/opa/bios/"),
     "pageTitle": r"secretary of veterans affairs|va secretary|" + _SECRETARY},
    {"key": "homeland", "wikidata": "Q642859", "office": "Secretary of Homeland Security",
     "body": "Department of Homeland Security",
     "titles": ("Secretary of Homeland Security",), "senate": ("Secretary of Homeland Security",),
     "pages": ("https://www.dhs.gov/leadership",),
     "pageTitle": r"secretary of homeland security|" + _SECRETARY},
)

# Offices the White House's Cabinet page may list beside the departments.
# Shown only when that page lists them; never called a department.
CABINET_LEVEL = (
    {"key": "epa", "wikidata": "Q2087596", "office": "Administrator of the Environmental Protection Agency",
     "body": "Environmental Protection Agency",
     "titles": ("Administrator of the Environmental Protection Agency",),
     "senate": ("Administrator of the Environmental Protection Agency",),
     "pages": ("https://www.epa.gov/aboutepa/epa-administrator",),
     "pageTitle": r"epa administrator|administrator of the (?:u s )?environmental protection agency|"
                  r"\badministrator"},
    {"key": "omb", "wikidata": "Q16300323", "office": "Director of the Office of Management and Budget",
     "body": "Office of Management and Budget",
     "titles": ("Director of the Office of Management and Budget",),
     "senate": ("Director of the Office of Management and Budget",),
     # OMB's own pages name no Director (checked 2026-10-16).
     "pages": (), "pageTitle": r"director"},
    {"key": "ustr", "wikidata": "Q27907212", "office": "United States Trade Representative",
     "body": "Office of the United States Trade Representative",
     "titles": ("United States Trade Representative",),
     "senate": ("United States Trade Representative", "U.S. Trade Representative"),
     "pages": ("https://ustr.gov/about-us/biographies-key-officials",),
     "pageTitle": r"(?:united states |u s )?trade representative|\bambassador"},
    {"key": "dni", "wikidata": "Q1154057", "office": "Director of National Intelligence",
     "body": "Office of the Director of National Intelligence",
     "titles": ("Director of National Intelligence",),
     "senate": ("Director of National Intelligence",),
     "pages": ("https://www.odni.gov/index.php/who-we-are/leadership",),
     "pageTitle": r"director of national intelligence|\bdirector"},
    {"key": "cia", "wikidata": "Q27656", "office": "Director of the Central Intelligence Agency",
     "body": "Central Intelligence Agency",
     "titles": ("Director of the Central Intelligence Agency",),
     "senate": ("Director of the Central Intelligence Agency",),
     "pages": ("https://www.cia.gov/about/director-of-cia/",),
     "pageTitle": r"director of the central intelligence agency|cia director|\bdirector"},
    {"key": "sba", "wikidata": "Q15623718", "office": "Administrator of the Small Business Administration",
     "body": "Small Business Administration",
     "titles": ("Administrator of the Small Business Administration",),
     "senate": ("Administrator of the Small Business Administration",),
     "pages": ("https://www.sba.gov/person/kelly-loeffler/",),
     "pageTitle": r"administrator of the (?:u s )?small business administration|sba administrator|"
                  r"\badministrator"},
    {"key": "un", "wikidata": "Q1785225", "office": "Representative of the United States to the United Nations",
     "body": "U.S. Mission to the United Nations",
     "titles": ("United States Ambassador to the United Nations",
                "Ambassador to the United Nations",
                "U.S. Ambassador to the United Nations"),
     "senate": ("Representative of the United States of America to the United Nations",),
     "pages": ("https://usun.usmission.gov/",),
     "pageTitle": r"(?:u s |united states )?(?:ambassador|representative) to the united nations|"
                  r"\bambassador"},
    {"key": "chief-of-staff", "wikidata": "Q786242", "office": "White House Chief of Staff",
     "body": "Executive Office of the President",
     "titles": ("White House Chief of Staff", "Chief of Staff"),
     "senate": (), "pages": (), "pageTitle": r"chief of staff"},
)

OFFICES = DEPARTMENTS + CABINET_LEVEL

# A head's name as their office's page writes it, where its first name is
# not the one the White House uses - each from the Senate's own record of
# the confirmation, which names the person by both. Keyed on the office and
# the White House's spelling, so a new holder never inherits an entry.
NAME_FORMS = {
    ("veterans", "Doug Collins"): ("Douglas A. Collins",
                                   "Senate vote 119-1-32 (2025-02-04): 'Douglas Collins, of Georgia, "
                                   "to be Secretary of Veterans Affairs'"),
}


def by_title():
    """``{title as the White House writes it: office}``."""
    out = {}
    for office in OFFICES:
        for title in office["titles"]:
            out[title] = office
    return out


def check():
    """Problems with the table itself: 15 departments, unique keys and
    titles, and each office's own Wikidata item (the history of who held it,
    kyc/cabinet.py). Empty when it is sound."""
    problems = []
    items = [o.get("wikidata") for o in OFFICES]
    if any(not re.fullmatch(r"Q\d+", i or "") for i in items) or len(set(items)) != len(items):
        problems.append("every office needs its own Wikidata item")
    if len(DEPARTMENTS) != 15:
        problems.append(f"{len(DEPARTMENTS)} departments, not the 15 of 5 U.S.C. 101")
    keys = [o["key"] for o in OFFICES]
    if len(keys) != len(set(keys)):
        problems.append("two offices share a key")
    titles = [t for o in OFFICES for t in o["titles"]]
    if len(titles) != len(set(titles)):
        problems.append("two offices share a title")
    for (key, _name), _form in NAME_FORMS.items():
        if key not in keys:
            problems.append(f"NAME_FORMS names an office the table lacks: {key}")
    return problems
