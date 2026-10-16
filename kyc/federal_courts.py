"""The federal courts this site follows, as a curated table.

Article III's courts: the Supreme Court; the thirteen courts of appeals - the
eleven numbered circuits, the District of Columbia's and the Federal
Circuit, with the states and territories 28 U.S.C. 41 puts in each (the
Northern Mariana Islands in the Ninth by 48 U.S.C. 1821); the 91 district
courts whose judges hold Article III office; and the Court of International
Trade. The district courts of Guam, the Northern Mariana Islands and the
Virgin Islands are Article IV courts with ten-year terms: they are listed,
in their circuits, and their judges are not, because the Federal Judicial
Center's directory - the source for every other court's judges - covers
Article III judges only (rule 19: "not in the directory", never "none").

``fjc`` is the court's name in the Federal Judicial Center's directory when
it is not ``name``; every sitting court there must be in this table, and a
court name the table does not know stops the read (kyc/judiciary.py).

An id is the page's address too: ``scotus``, ``ca1``-``ca11``, ``cadc``,
``cafc``, ``cit``, a state's code for its only district (``md``), and the
code with ``-n``, ``-s``, ``-e``, ``-w``, ``-c`` or ``-m`` for one of
several (``tx-s``). Checked 2026-10-16 against 28 U.S.C. 41 (govinfo,
2024 edition) and the directory's export of that day.
"""

REVIEWED = "2026-10-16"

# A Chief Justice and eight associate justices (28 U.S.C. 1).
SUPREME_COURT_SEATS = 9

COURTS = {
    "scotus": {"name": "Supreme Court of the United States", "kind": "supreme"},
    "ca1": {
        "name": "U.S. Court of Appeals for the First Circuit",
        "kind": "appeals",
        "circuit": "1",
        "states": ("ME", "MA", "NH", "PR", "RI")},
    "ca2": {
        "name": "U.S. Court of Appeals for the Second Circuit",
        "kind": "appeals",
        "circuit": "2",
        "states": ("CT", "NY", "VT")},
    "ca3": {
        "name": "U.S. Court of Appeals for the Third Circuit",
        "kind": "appeals",
        "circuit": "3",
        "states": ("DE", "NJ", "PA", "VI")},
    "ca4": {
        "name": "U.S. Court of Appeals for the Fourth Circuit",
        "kind": "appeals",
        "circuit": "4",
        "states": ("MD", "NC", "SC", "VA", "WV")},
    "ca5": {
        "name": "U.S. Court of Appeals for the Fifth Circuit",
        "kind": "appeals",
        "circuit": "5",
        "states": ("LA", "MS", "TX")},
    "ca6": {
        "name": "U.S. Court of Appeals for the Sixth Circuit",
        "kind": "appeals",
        "circuit": "6",
        "states": ("KY", "MI", "OH", "TN")},
    "ca7": {
        "name": "U.S. Court of Appeals for the Seventh Circuit",
        "kind": "appeals",
        "circuit": "7",
        "states": ("IL", "IN", "WI")},
    "ca8": {
        "name": "U.S. Court of Appeals for the Eighth Circuit",
        "kind": "appeals",
        "circuit": "8",
        "states": ("AR", "IA", "MN", "MO", "NE", "ND", "SD")},
    "ca9": {
        "name": "U.S. Court of Appeals for the Ninth Circuit",
        "kind": "appeals",
        "circuit": "9",
        "states": ("AK", "AZ", "CA", "ID", "MT", "NV", "OR", "WA", "GU", "HI", "MP")},
    "ca10": {
        "name": "U.S. Court of Appeals for the Tenth Circuit",
        "kind": "appeals",
        "circuit": "10",
        "states": ("CO", "KS", "NM", "OK", "UT", "WY")},
    "ca11": {
        "name": "U.S. Court of Appeals for the Eleventh Circuit",
        "kind": "appeals",
        "circuit": "11",
        "states": ("AL", "FL", "GA")},
    "cadc": {
        "name": "U.S. Court of Appeals for the District of Columbia Circuit",
        "kind": "appeals",
        "circuit": "DC",
        "states": ("DC",)},
    "cafc": {
        "name": "U.S. Court of Appeals for the Federal Circuit",
        "kind": "appeals",
        "circuit": "Federal",
        "states": ()},
    "cit": {"name": "U.S. Court of International Trade", "kind": "trade"},
    "ak": {
        "name": "U.S. District Court for the District of Alaska",
        "kind": "district",
        "circuit": "9",
        "states": ("AK",)},
    "al-m": {
        "name": "U.S. District Court for the Middle District of Alabama",
        "kind": "district",
        "circuit": "11",
        "states": ("AL",)},
    "al-n": {
        "name": "U.S. District Court for the Northern District of Alabama",
        "kind": "district",
        "circuit": "11",
        "states": ("AL",)},
    "al-s": {
        "name": "U.S. District Court for the Southern District of Alabama",
        "kind": "district",
        "circuit": "11",
        "states": ("AL",)},
    "ar-e": {
        "name": "U.S. District Court for the Eastern District of Arkansas",
        "kind": "district",
        "circuit": "8",
        "states": ("AR",)},
    "ar-w": {
        "name": "U.S. District Court for the Western District of Arkansas",
        "kind": "district",
        "circuit": "8",
        "states": ("AR",)},
    "az": {
        "name": "U.S. District Court for the District of Arizona",
        "kind": "district",
        "circuit": "9",
        "states": ("AZ",)},
    "ca-c": {
        "name": "U.S. District Court for the Central District of California",
        "kind": "district",
        "circuit": "9",
        "states": ("CA",)},
    "ca-e": {
        "name": "U.S. District Court for the Eastern District of California",
        "kind": "district",
        "circuit": "9",
        "states": ("CA",)},
    "ca-n": {
        "name": "U.S. District Court for the Northern District of California",
        "kind": "district",
        "circuit": "9",
        "states": ("CA",)},
    "ca-s": {
        "name": "U.S. District Court for the Southern District of California",
        "kind": "district",
        "circuit": "9",
        "states": ("CA",)},
    "co": {
        "name": "U.S. District Court for the District of Colorado",
        "kind": "district",
        "circuit": "10",
        "states": ("CO",)},
    "ct": {
        "name": "U.S. District Court for the District of Connecticut",
        "kind": "district",
        "circuit": "2",
        "states": ("CT",)},
    "dc": {
        "name": "U.S. District Court for the District of Columbia",
        "kind": "district",
        "circuit": "DC",
        "states": ("DC",)},
    "de": {
        "name": "U.S. District Court for the District of Delaware",
        "kind": "district",
        "circuit": "3",
        "states": ("DE",)},
    "fl-m": {
        "name": "U.S. District Court for the Middle District of Florida",
        "kind": "district",
        "circuit": "11",
        "states": ("FL",)},
    "fl-n": {
        "name": "U.S. District Court for the Northern District of Florida",
        "kind": "district",
        "circuit": "11",
        "states": ("FL",)},
    "fl-s": {
        "name": "U.S. District Court for the Southern District of Florida",
        "kind": "district",
        "circuit": "11",
        "states": ("FL",)},
    "ga-m": {
        "name": "U.S. District Court for the Middle District of Georgia",
        "kind": "district",
        "circuit": "11",
        "states": ("GA",)},
    "ga-n": {
        "name": "U.S. District Court for the Northern District of Georgia",
        "kind": "district",
        "circuit": "11",
        "states": ("GA",)},
    "ga-s": {
        "name": "U.S. District Court for the Southern District of Georgia",
        "kind": "district",
        "circuit": "11",
        "states": ("GA",)},
    "gu": {
        "name": "District Court of Guam",
        "kind": "territorial",
        "circuit": "9",
        "states": ("GU",),
        "fjc": None},
    "hi": {
        "name": "U.S. District Court for the District of Hawaii",
        "kind": "district",
        "circuit": "9",
        "states": ("HI",)},
    "ia-n": {
        "name": "U.S. District Court for the Northern District of Iowa",
        "kind": "district",
        "circuit": "8",
        "states": ("IA",)},
    "ia-s": {
        "name": "U.S. District Court for the Southern District of Iowa",
        "kind": "district",
        "circuit": "8",
        "states": ("IA",)},
    "id": {
        "name": "U.S. District Court for the District of Idaho",
        "kind": "district",
        "circuit": "9",
        "states": ("ID",)},
    "il-c": {
        "name": "U.S. District Court for the Central District of Illinois",
        "kind": "district",
        "circuit": "7",
        "states": ("IL",)},
    "il-n": {
        "name": "U.S. District Court for the Northern District of Illinois",
        "kind": "district",
        "circuit": "7",
        "states": ("IL",)},
    "il-s": {
        "name": "U.S. District Court for the Southern District of Illinois",
        "kind": "district",
        "circuit": "7",
        "states": ("IL",)},
    "in-n": {
        "name": "U.S. District Court for the Northern District of Indiana",
        "kind": "district",
        "circuit": "7",
        "states": ("IN",)},
    "in-s": {
        "name": "U.S. District Court for the Southern District of Indiana",
        "kind": "district",
        "circuit": "7",
        "states": ("IN",)},
    "ks": {
        "name": "U.S. District Court for the District of Kansas",
        "kind": "district",
        "circuit": "10",
        "states": ("KS",)},
    "ky-e": {
        "name": "U.S. District Court for the Eastern District of Kentucky",
        "kind": "district",
        "circuit": "6",
        "states": ("KY",)},
    "ky-w": {
        "name": "U.S. District Court for the Western District of Kentucky",
        "kind": "district",
        "circuit": "6",
        "states": ("KY",)},
    "la-e": {
        "name": "U.S. District Court for the Eastern District of Louisiana",
        "kind": "district",
        "circuit": "5",
        "states": ("LA",)},
    "la-m": {
        "name": "U.S. District Court for the Middle District of Louisiana",
        "kind": "district",
        "circuit": "5",
        "states": ("LA",)},
    "la-w": {
        "name": "U.S. District Court for the Western District of Louisiana",
        "kind": "district",
        "circuit": "5",
        "states": ("LA",)},
    "ma": {
        "name": "U.S. District Court for the District of Massachusetts",
        "kind": "district",
        "circuit": "1",
        "states": ("MA",)},
    "md": {
        "name": "U.S. District Court for the District of Maryland",
        "kind": "district",
        "circuit": "4",
        "states": ("MD",)},
    "me": {
        "name": "U.S. District Court for the District of Maine",
        "kind": "district",
        "circuit": "1",
        "states": ("ME",)},
    "mi-e": {
        "name": "U.S. District Court for the Eastern District of Michigan",
        "kind": "district",
        "circuit": "6",
        "states": ("MI",)},
    "mi-w": {
        "name": "U.S. District Court for the Western District of Michigan",
        "kind": "district",
        "circuit": "6",
        "states": ("MI",)},
    "mn": {
        "name": "U.S. District Court for the District of Minnesota",
        "kind": "district",
        "circuit": "8",
        "states": ("MN",)},
    "mo-e": {
        "name": "U.S. District Court for the Eastern District of Missouri",
        "kind": "district",
        "circuit": "8",
        "states": ("MO",)},
    "mo-w": {
        "name": "U.S. District Court for the Western District of Missouri",
        "kind": "district",
        "circuit": "8",
        "states": ("MO",)},
    "mp": {
        "name": "District Court of the Northern Mariana Islands",
        "kind": "territorial",
        "circuit": "9",
        "states": ("MP",),
        "fjc": None},
    "ms-n": {
        "name": "U.S. District Court for the Northern District of Mississippi",
        "kind": "district",
        "circuit": "5",
        "states": ("MS",)},
    "ms-s": {
        "name": "U.S. District Court for the Southern District of Mississippi",
        "kind": "district",
        "circuit": "5",
        "states": ("MS",)},
    "mt": {
        "name": "U.S. District Court for the District of Montana",
        "kind": "district",
        "circuit": "9",
        "states": ("MT",)},
    "nc-e": {
        "name": "U.S. District Court for the Eastern District of North Carolina",
        "kind": "district",
        "circuit": "4",
        "states": ("NC",)},
    "nc-m": {
        "name": "U.S. District Court for the Middle District of North Carolina",
        "kind": "district",
        "circuit": "4",
        "states": ("NC",)},
    "nc-w": {
        "name": "U.S. District Court for the Western District of North Carolina",
        "kind": "district",
        "circuit": "4",
        "states": ("NC",)},
    "nd": {
        "name": "U.S. District Court for the District of North Dakota",
        "kind": "district",
        "circuit": "8",
        "states": ("ND",)},
    "ne": {
        "name": "U.S. District Court for the District of Nebraska",
        "kind": "district",
        "circuit": "8",
        "states": ("NE",)},
    "nh": {
        "name": "U.S. District Court for the District of New Hampshire",
        "kind": "district",
        "circuit": "1",
        "states": ("NH",)},
    "nj": {
        "name": "U.S. District Court for the District of New Jersey",
        "kind": "district",
        "circuit": "3",
        "states": ("NJ",)},
    "nm": {
        "name": "U.S. District Court for the District of New Mexico",
        "kind": "district",
        "circuit": "10",
        "states": ("NM",)},
    "nv": {
        "name": "U.S. District Court for the District of Nevada",
        "kind": "district",
        "circuit": "9",
        "states": ("NV",)},
    "ny-e": {
        "name": "U.S. District Court for the Eastern District of New York",
        "kind": "district",
        "circuit": "2",
        "states": ("NY",)},
    "ny-n": {
        "name": "U.S. District Court for the Northern District of New York",
        "kind": "district",
        "circuit": "2",
        "states": ("NY",)},
    "ny-s": {
        "name": "U.S. District Court for the Southern District of New York",
        "kind": "district",
        "circuit": "2",
        "states": ("NY",)},
    "ny-w": {
        "name": "U.S. District Court for the Western District of New York",
        "kind": "district",
        "circuit": "2",
        "states": ("NY",)},
    "oh-n": {
        "name": "U.S. District Court for the Northern District of Ohio",
        "kind": "district",
        "circuit": "6",
        "states": ("OH",)},
    "oh-s": {
        "name": "U.S. District Court for the Southern District of Ohio",
        "kind": "district",
        "circuit": "6",
        "states": ("OH",)},
    "ok-e": {
        "name": "U.S. District Court for the Eastern District of Oklahoma",
        "kind": "district",
        "circuit": "10",
        "states": ("OK",)},
    "ok-n": {
        "name": "U.S. District Court for the Northern District of Oklahoma",
        "kind": "district",
        "circuit": "10",
        "states": ("OK",)},
    "ok-w": {
        "name": "U.S. District Court for the Western District of Oklahoma",
        "kind": "district",
        "circuit": "10",
        "states": ("OK",)},
    "or": {
        "name": "U.S. District Court for the District of Oregon",
        "kind": "district",
        "circuit": "9",
        "states": ("OR",)},
    "pa-e": {
        "name": "U.S. District Court for the Eastern District of Pennsylvania",
        "kind": "district",
        "circuit": "3",
        "states": ("PA",)},
    "pa-m": {
        "name": "U.S. District Court for the Middle District of Pennsylvania",
        "kind": "district",
        "circuit": "3",
        "states": ("PA",)},
    "pa-w": {
        "name": "U.S. District Court for the Western District of Pennsylvania",
        "kind": "district",
        "circuit": "3",
        "states": ("PA",)},
    "pr": {
        "name": "U.S. District Court for the District of Puerto Rico",
        "kind": "district",
        "circuit": "1",
        "states": ("PR",)},
    "ri": {
        "name": "U.S. District Court for the District of Rhode Island",
        "kind": "district",
        "circuit": "1",
        "states": ("RI",)},
    "sc": {
        "name": "U.S. District Court for the District of South Carolina",
        "kind": "district",
        "circuit": "4",
        "states": ("SC",)},
    "sd": {
        "name": "U.S. District Court for the District of South Dakota",
        "kind": "district",
        "circuit": "8",
        "states": ("SD",)},
    "tn-e": {
        "name": "U.S. District Court for the Eastern District of Tennessee",
        "kind": "district",
        "circuit": "6",
        "states": ("TN",)},
    "tn-m": {
        "name": "U.S. District Court for the Middle District of Tennessee",
        "kind": "district",
        "circuit": "6",
        "states": ("TN",)},
    "tn-w": {
        "name": "U.S. District Court for the Western District of Tennessee",
        "kind": "district",
        "circuit": "6",
        "states": ("TN",)},
    "tx-e": {
        "name": "U.S. District Court for the Eastern District of Texas",
        "kind": "district",
        "circuit": "5",
        "states": ("TX",)},
    "tx-n": {
        "name": "U.S. District Court for the Northern District of Texas",
        "kind": "district",
        "circuit": "5",
        "states": ("TX",)},
    "tx-s": {
        "name": "U.S. District Court for the Southern District of Texas",
        "kind": "district",
        "circuit": "5",
        "states": ("TX",)},
    "tx-w": {
        "name": "U.S. District Court for the Western District of Texas",
        "kind": "district",
        "circuit": "5",
        "states": ("TX",)},
    "ut": {
        "name": "U.S. District Court for the District of Utah",
        "kind": "district",
        "circuit": "10",
        "states": ("UT",)},
    "va-e": {
        "name": "U.S. District Court for the Eastern District of Virginia",
        "kind": "district",
        "circuit": "4",
        "states": ("VA",)},
    "va-w": {
        "name": "U.S. District Court for the Western District of Virginia",
        "kind": "district",
        "circuit": "4",
        "states": ("VA",)},
    "vi": {
        "name": "District Court of the Virgin Islands",
        "kind": "territorial",
        "circuit": "3",
        "states": ("VI",),
        "fjc": None},
    "vt": {
        "name": "U.S. District Court for the District of Vermont",
        "kind": "district",
        "circuit": "2",
        "states": ("VT",)},
    "wa-e": {
        "name": "U.S. District Court for the Eastern District of Washington",
        "kind": "district",
        "circuit": "9",
        "states": ("WA",)},
    "wa-w": {
        "name": "U.S. District Court for the Western District of Washington",
        "kind": "district",
        "circuit": "9",
        "states": ("WA",)},
    "wi-e": {
        "name": "U.S. District Court for the Eastern District of Wisconsin",
        "kind": "district",
        "circuit": "7",
        "states": ("WI",)},
    "wi-w": {
        "name": "U.S. District Court for the Western District of Wisconsin",
        "kind": "district",
        "circuit": "7",
        "states": ("WI",)},
    "wv-n": {
        "name": "U.S. District Court for the Northern District of West Virginia",
        "kind": "district",
        "circuit": "4",
        "states": ("WV",)},
    "wv-s": {
        "name": "U.S. District Court for the Southern District of West Virginia",
        "kind": "district",
        "circuit": "4",
        "states": ("WV",)},
    "wy": {
        "name": "U.S. District Court for the District of Wyoming",
        "kind": "district",
        "circuit": "10",
        "states": ("WY",)},
}


KINDS = {"supreme": "Supreme Court", "appeals": "Court of appeals", "trade": "Court of International Trade",
         "district": "District court", "territorial": "Territorial district court"}


def fjc_name(court_id):
    """The court's name in the FJC directory, or None for a court it does not
    cover (the Article IV territorial courts)."""
    court = COURTS[court_id]
    return court.get("fjc", court["name"]) if "fjc" in court else court["name"]


def by_fjc_name():
    """``{FJC court name: court id}``."""
    return {fjc_name(cid): cid for cid in COURTS if fjc_name(cid)}


def check():
    """Problems with the table itself. Empty when it is sound."""
    from .normalize import TERRITORIES, US_STATES

    problems = []
    kinds = {}
    for court in COURTS.values():
        kinds[court["kind"]] = kinds.get(court["kind"], 0) + 1
    want = {"supreme": 1, "appeals": 13, "trade": 1, "district": 91, "territorial": 3}
    if kinds != want:
        problems.append(f"courts by kind {kinds}, not {want}")
    # American Samoa has no federal district court and is in no circuit
    # under 28 U.S.C. 41; its own High Court decides its cases.
    places = (set(US_STATES.values()) | set(TERRITORIES)) - {"AS"}
    circuits = {}
    for cid, court in COURTS.items():
        if court["kind"] != "appeals":
            continue
        for state in court["states"]:
            circuits.setdefault(state, []).append(cid)
    wrong = sorted(f"{st}: {circuits.get(st)}" for st in places if len(circuits.get(st, [])) != 1)
    if wrong:
        problems.append(f"places not in exactly one circuit (28 U.S.C. 41): {wrong}")
    for cid, court in COURTS.items():
        if court["kind"] in ("district", "territorial"):
            state = court["states"][0]
            circuit = next(COURTS[c]["circuit"] for c in circuits.get(state, ["cafc"])
                           if c in COURTS) if circuits.get(state) else None
            if circuit != court.get("circuit"):
                problems.append(f"{cid} is in circuit {court.get('circuit')}, its state in {circuit}")
    without = sorted(st for st in places if not any(
        st in c["states"] for c in COURTS.values() if c["kind"] in ("district", "territorial")))
    if without:
        problems.append(f"places with no district court: {without}")
    names = [fjc_name(c) for c in COURTS if fjc_name(c)]
    if len(names) != len(set(names)):
        problems.append("two courts share an FJC name")
    return problems
