"""Who is elected to an office, and how its candidates reach the ballot:
one table, keyed on the state and the office, never the state alone.

Three tables answered these questions by state (``results.RANKED_CHOICE``,
``overrides.GENERAL_RUNOFFS`` and ``results.ALL_PARTY_PRIMARIES``), which was
true while the only offices read were Congress's. It is not true of a state's
other offices: Maine counts its races for Congress by ranked choice (21-A
M.R.S. 723-A) and elects its governor by plurality, so a gate keyed on "ME"
would hold Maine's governor uncalled for ever. Each entry here is one
office's law, its provision quoted as the reader read it; an office with no
entry is elected by plurality, as this site's reader has always read it, and
holds a party primary.

``office`` is the race id's own letter: "S" for the U.S. Senate, "H" for the
U.S. House (a Delegate's or the Resident Commissioner's seat included).

Each entry may hold:

- ``elect``: how the November count elects (:data:`PLURALITY`, the default;
  :data:`MAJORITY_OR_RUNOFF`, with the runoff's day in ``runoff``;
  :data:`MAJORITY_OR_LEGISLATURE`; :data:`RANKED_CHOICE`), and ``law``, the
  provision that says so;
- ``primary``: ``(kind, provision)`` where every candidate runs on one
  primary ballot and the leaders go through whatever their party ("top-two",
  "top-four"): nobody there is a party's nominee.

Standard library only; this module imports nothing, so ``overrides`` and
``results`` can both read it.
"""

PLURALITY = "plurality"
MAJORITY_OR_RUNOFF = "majority-or-runoff"
MAJORITY_OR_LEGISLATURE = "majority-or-legislature"
RANKED_CHOICE = "ranked-choice"

RULES = (PLURALITY, MAJORITY_OR_RUNOFF, MAJORITY_OR_LEGISLATURE, RANKED_CHOICE)

# The provisions, quoted as they were when each table was keyed by state.
_GA_RUNOFF = ("O.C.G.A. 21-2-501(a): a runoff is held on the 28th day after a "
              "general election in which no candidate receives a majority; "
              "November 3 + 28 days = December 1, 2026")
# The Delegates from Guam and the Virgin Islands are elected by a majority
# too (results night, 2026-11-04: read by plurality, a page marking a leader
# short of one would have been "elected" a fortnight before the runoff). The
# dates are data/voting_dates.json's.
_GU_RUNOFF = ("48 U.S.C. 1712: \"The Delegate from Guam shall be elected at large "
              "and by a majority of the votes cast for the office of Delegate. If "
              "no candidate receives such majority, on the fourteenth day following "
              "such election a runoff election shall be held\"; November 3 + 14 "
              "days = November 17, 2026")
_VI_RUNOFF = ("48 U.S.C. 1712 elects the Delegate from the Virgin Islands by a "
              "majority, with a runoff between the top two on the fourteenth day "
              "after the election; the Elections System of the Virgin Islands' "
              "2026 Elections Calendar (amended June 10, 2026) lists November 17 "
              "as \"RUN-OFF ELECTION DAY (Revised Organic Act of 1954, Sec., 11 re: "
              "Gov.-Lt. Gov.; P.L. 92-271 re: Delegate to House of "
              "Representatives)\"")
# A candidate with no majority of the first choices is not elected until the
# rounds are tabulated, a week or more later (Maine's 2nd district in 2018:
# Bruce Poliquin led the first choices and Jared Golden won).
_ME_RANKED = "21-A M.R.S. 723-A"
_AK_RANKED = "AS 15.15.350"
# Primaries in which every candidate runs on one ballot and the leaders go
# through to November whatever their party, so nobody is a party's nominee
# and two of one party can both go through: "Won the primary" and
# "Renominated" were on 116 people in these states, two "winners" of one
# party in nine races. The guide cites the same laws (government_text).
_CA_PRIMARY = ("top-two", "Cal. Elections Code 8141.5; California Secretary of State, "
                          "Primary elections in California")
_WA_PRIMARY = ("top-two", "RCW 29A.52.112")
_AK_PRIMARY = ("top-four", "AS 15.25.010")

ELECTION_LAWS = {
    ("GA", "S"): {"elect": MAJORITY_OR_RUNOFF, "runoff": "2026-12-01", "law": _GA_RUNOFF},
    ("GA", "H"): {"elect": MAJORITY_OR_RUNOFF, "runoff": "2026-12-01", "law": _GA_RUNOFF},
    ("GU", "H"): {"elect": MAJORITY_OR_RUNOFF, "runoff": "2026-11-17", "law": _GU_RUNOFF},
    ("VI", "H"): {"elect": MAJORITY_OR_RUNOFF, "runoff": "2026-11-17", "law": _VI_RUNOFF},
    ("ME", "S"): {"elect": RANKED_CHOICE, "law": _ME_RANKED},
    ("ME", "H"): {"elect": RANKED_CHOICE, "law": _ME_RANKED},
    ("AK", "S"): {"elect": RANKED_CHOICE, "law": _AK_RANKED, "primary": _AK_PRIMARY},
    ("AK", "H"): {"elect": RANKED_CHOICE, "law": _AK_RANKED, "primary": _AK_PRIMARY},
    ("CA", "S"): {"primary": _CA_PRIMARY},
    ("CA", "H"): {"primary": _CA_PRIMARY},
    ("WA", "S"): {"primary": _WA_PRIMARY},
    ("WA", "H"): {"primary": _WA_PRIMARY},
}


def law(state, office):
    """The entry for *office* in *state*: ``{}`` where none is recorded."""
    return ELECTION_LAWS.get((state, office)) or {}


def elected_by(state, office):
    """How the November count elects to *office* in *state*: one of
    :data:`RULES`, :data:`PLURALITY` where no entry says otherwise."""
    return law(state, office).get("elect") or PLURALITY


def ranked_choice(state, office):
    """Whether *office* in *state* is counted by ranked choice."""
    return elected_by(state, office) == RANKED_CHOICE


def general_runoff(state, office):
    """``(day, provision)`` of the runoff the law holds where nobody wins a
    majority of *office* in *state* on November 3, or None."""
    entry = law(state, office)
    if entry.get("elect") == MAJORITY_OR_RUNOFF and entry.get("runoff"):
        return entry["runoff"], entry["law"]
    return None


def all_party_primary(state, office):
    """``(kind, provision)`` where *office*'s primary in *state* puts every
    candidate on one ballot ("top-two", "top-four"), or None."""
    return law(state, office).get("primary")


def office_of(race_id):
    """``(state, office)`` of a race id ("H-CA-03-2026", "S-GA-2026")."""
    parts = str(race_id or "").split("-")
    return (parts[1] if len(parts) > 1 else ""), parts[0]


def runoff_days():
    """Every day a general election runoff the table holds falls on."""
    return sorted({entry["runoff"] for entry in ELECTION_LAWS.values()
                   if entry.get("elect") == MAJORITY_OR_RUNOFF and entry.get("runoff")})


def _by_state(read):
    """``{state: value}`` of what *read* answers for each entry that answers,
    for the views by state kept for one release; a state whose offices
    answer differently has no single answer and is refused."""
    out = {}
    for (state, office), _entry in sorted(ELECTION_LAWS.items()):
        value = read(state, office)
        if value is None:
            continue
        if state in out and out[state] != value:
            raise ValueError(f"{state}'s offices answer differently: {out[state]!r}, {value!r}")
        out[state] = value
    return out


# Views by state, as the old tables were, for one release: tests and modules
# that read ``overrides.GENERAL_RUNOFFS``, ``results.RANKED_CHOICE`` or
# ``results.ALL_PARTY_PRIMARIES`` read these. Nothing in kyc/ decides by them.
GENERAL_RUNOFFS_BY_STATE = _by_state(general_runoff)
RANKED_CHOICE_BY_STATE = _by_state(lambda s, o: law(s, o)["law"] if ranked_choice(s, o) else None)
ALL_PARTY_PRIMARIES_BY_STATE = _by_state(all_party_primary)
