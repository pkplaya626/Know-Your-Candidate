"""County areas with no county government, and why.

A state's county page draws every county the Census Bureau maps, but not
every county area has a government of its own. Rhode Island's five counties
have none; the counties directory and the guide's map say "none" for its
county governments while its page drew five counties and said nothing. So
every such area is in ``AREAS``, keyed by its Census county code, with the
kind of area it is and the government that does the county's work, named as
the Census Government Units listing names it.

The table is Appendix A of the Census Bureau's 2022 Individual State
Descriptions ("County-Type Areas Without County Government"), checked
against the listing itself. Two lines of the appendix predate the map:
Alaska's Valdez-Cordova Census Area was split into Chugach and Copper River
in 2019, and Petersburg is a borough with a government of its own.

``check`` makes any drift a build error, both ways: a county area on the map
with no county government in the listing that is not explained here, and an
entry here whose area has one, is not on the map, has another name, or names
a government the listing does not hold there (rule 53).
"""

from .pages import state_name

SOURCES = {
    "isd": ("U.S. Census Bureau: 2022 Census of Governments, Individual State Descriptions, "
            "Appendix A (County-Type Areas Without County Government)",
            "https://www.census.gov/content/dam/Census/library/publications/2024/econ/2022ISD.pdf"),
    "ct-fr": ("Federal Register, June 6, 2022: Change to County-Equivalents in the State of "
              "Connecticut",
              "https://www.federalregister.gov/documents/2022/06/06/2022-12063/"
              "change-to-county-equivalents-in-the-state-of-connecticut"),
}

# Kinds of area, as the appendix groups them.
CONSOLIDATED = "consolidated"   # a city (or town) government that is also the county's
INDEPENDENT = "independent"     # a city outside any county, doing a county's work
STATE = "state"                 # run by the state government
UNORGANIZED = "unorganized"     # a county in name only: no government at all
CENSUS_AREA = "census-area"     # part of Alaska's Unorganized Borough
REGION = "planning-region"      # Connecticut's planning regions, mapped since 2022

NYC = "36061"   # New York County: where the listing files the City of New York
BOROUGHS = {"36005": "the Bronx", "36047": "Brooklyn", "36061": "Manhattan", "36081": "Queens",
            "36085": "Staten Island"}

# code: (name on the map, kind, government doing the county's work or None,
#        county area whose list holds that government, if not this one)
AREAS = {
    # Consolidated city-county governments operating primarily as cities.
    "02020": ("Anchorage Municipality", CONSOLIDATED, "Municipality of Anchorage", None),
    "02110": ("Juneau City and Borough", CONSOLIDATED, "City and Borough of Juneau", None),
    "02220": ("Sitka City and Borough", CONSOLIDATED, "City and Borough of Sitka", None),
    "02275": ("Wrangell City and Borough", CONSOLIDATED, "City and Borough of Wrangell", None),
    "06075": ("San Francisco County", CONSOLIDATED, "City and County of San Francisco", None),
    "08014": ("Broomfield County", CONSOLIDATED, "City and County of Broomfield", None),
    "08031": ("Denver County", CONSOLIDATED, "City and County of Denver", None),
    "13021": ("Bibb County", CONSOLIDATED, "County of Macon-Bibb", None),
    "15003": ("Honolulu County", CONSOLIDATED, "City and County of Honolulu", None),
    "20071": ("Greeley County", CONSOLIDATED, "Unified Government of Greeley County", None),
    "20209": ("Wyandotte County", CONSOLIDATED,
              "Unified Government of Wyandotte County and Kansas City", None),
    "30023": ("Deer Lodge County", CONSOLIDATED, "County of Anaconda-Deer Lodge", None),
    "30093": ("Silver Bow County", CONSOLIDATED, "City and County of Butte-Silver Bow", None),
    # Metropolitan governments operating primarily as cities.
    "47037": ("Davidson County", CONSOLIDATED,
              "Metropolitan Government of Nashville-Davidson County", None),
    "47127": ("Moore County", CONSOLIDATED, "Metropolitan Government of Lynchburg-Moore County",
              None),
    "47169": ("Trousdale County", CONSOLIDATED,
              "Metropolitan Government of Hartsville-Trousdale County", None),
    # County areas included in another government (city, town or state).
    "12031": ("Duval County", CONSOLIDATED, "City of Jacksonville", None),
    "13053": ("Chattahoochee County", CONSOLIDATED,
              "Unified Government of Cusseta-Chattahoochee County", None),
    "13059": ("Clarke County", CONSOLIDATED, "Unified Government of Athens-Clarke County", None),
    "13215": ("Muscogee County", CONSOLIDATED, "Consolidated Government of Columbus", None),
    "13239": ("Quitman County", CONSOLIDATED,
              "Unified Government of Georgetown and Quitman County", None),
    "13245": ("Richmond County", CONSOLIDATED,
              "Consolidated Government of Augusta-Richmond County", None),
    "13307": ("Webster County", CONSOLIDATED, "Unified Government of Webster County", None),
    "15005": ("Kalawao County", STATE, None, None),
    "18097": ("Marion County", CONSOLIDATED, "City of Indianapolis", None),
    "21067": ("Fayette County", CONSOLIDATED, "Urban County Government of Lexington-Fayette",
              None),
    "21111": ("Jefferson County", CONSOLIDATED, "Metro Government of Louisville-Jefferson County",
              None),
    "22033": ("East Baton Rouge Parish", CONSOLIDATED,
              "City-Parish of Baton Rouge-East Baton Rouge", None),
    "22055": ("Lafayette Parish", CONSOLIDATED, "City-Parish of Lafayette", None),
    "22071": ("Orleans Parish", CONSOLIDATED, "City of New Orleans", None),
    "22109": ("Terrebonne Parish", CONSOLIDATED, "Consolidated Government of Terrebonne", None),
    "25019": ("Nantucket County", CONSOLIDATED, "Town of Nantucket", None),
    "25025": ("Suffolk County", CONSOLIDATED, "City of Boston", None),
    "36005": ("Bronx County", CONSOLIDATED, "City of New York", NYC),
    "36047": ("Kings County", CONSOLIDATED, "City of New York", NYC),
    "36061": ("New York County", CONSOLIDATED, "City of New York", None),
    "36081": ("Queens County", CONSOLIDATED, "City of New York", NYC),
    "36085": ("Richmond County", CONSOLIDATED, "City of New York", NYC),
    "42101": ("Philadelphia County", CONSOLIDATED, "City of Philadelphia", None),
    # Cities outside any county, administering functions counties do elsewhere.
    "24510": ("Baltimore city", INDEPENDENT, "City of Baltimore", None),
    "29510": ("St. Louis city", INDEPENDENT, "City of St Louis", None),
    "32510": ("Carson City", INDEPENDENT, "City of Carson City", None),
    **{code: (f"{name} city", INDEPENDENT, f"City of {name}", None) for code, name in (
        ("51510", "Alexandria"), ("51520", "Bristol"), ("51530", "Buena Vista"),
        ("51540", "Charlottesville"), ("51550", "Chesapeake"), ("51570", "Colonial Heights"),
        ("51580", "Covington"), ("51590", "Danville"), ("51595", "Emporia"),
        ("51600", "Fairfax"), ("51610", "Falls Church"), ("51620", "Franklin"),
        ("51630", "Fredericksburg"), ("51640", "Galax"), ("51650", "Hampton"),
        ("51660", "Harrisonburg"), ("51670", "Hopewell"), ("51678", "Lexington"),
        ("51680", "Lynchburg"), ("51683", "Manassas"), ("51685", "Manassas Park"),
        ("51690", "Martinsville"), ("51700", "Newport News"), ("51710", "Norfolk"),
        ("51720", "Norton"), ("51730", "Petersburg"), ("51735", "Poquoson"),
        ("51740", "Portsmouth"), ("51750", "Radford"), ("51760", "Richmond"),
        ("51770", "Roanoke"), ("51775", "Salem"), ("51790", "Staunton"),
        ("51800", "Suffolk"), ("51810", "Virginia Beach"), ("51820", "Waynesboro"),
        ("51830", "Williamsburg"), ("51840", "Winchester"))},
    # Unorganized areas bearing county designations.
    **{code: (f"{name} County", UNORGANIZED, None, None) for code, name in (
        ("25003", "Berkshire"), ("25009", "Essex"), ("25011", "Franklin"), ("25013", "Hampden"),
        ("25015", "Hampshire"), ("25017", "Middlesex"), ("25027", "Worcester"),
        ("44001", "Bristol"), ("44003", "Kent"), ("44005", "Newport"), ("44007", "Providence"),
        ("44009", "Washington"))},
    # Alaska's Unorganized Borough, in census areas.
    **{code: (f"{name} Census Area", CENSUS_AREA, None, None) for code, name in (
        ("02016", "Aleutians West"), ("02050", "Bethel"), ("02063", "Chugach"),
        ("02066", "Copper River"), ("02070", "Dillingham"), ("02105", "Hoonah-Angoon"),
        ("02158", "Kusilvak"), ("02180", "Nome"), ("02198", "Prince of Wales-Hyder"),
        ("02240", "Southeast Fairbanks"), ("02290", "Yukon-Koyukuk"))},
    # Connecticut's planning regions.
    **{code: (f"{name} Planning Region", REGION, None, None) for code, name in (
        ("09110", "Capitol"), ("09120", "Greater Bridgeport"),
        ("09130", "Lower Connecticut River Valley"), ("09140", "Naugatuck Valley"),
        ("09150", "Northeastern Connecticut"), ("09160", "Northwest Hills"),
        ("09170", "South Central Connecticut"), ("09180", "Southeastern Connecticut"),
        ("09190", "Western Connecticut"))},
}

# What a state calls the areas its map is drawn in: (one, many, the map's button).
# Cities the Census maps as places of their own whose government is the
# consolidated one AREAS names - a name the city join (counties.match_cities)
# cannot tie to the place, since the government's name is not the city's.
# Each government's own name names the city, or a record of its own or the
# Census Bureau's does, cited beside it. {place GEOID: county area}.
# The place is joined to the row AREAS names in that area, and its panel
# says the government also does the county's work. Not every place in such
# an area: St. George, Louisiana, incorporated in East Baton Rouge Parish in
# 2024, has a government of its own the 2022 listing does not hold.
CONSOLIDATED_PLACES = {
    "2036000": "20209",   # Kansas City, Kansas
    "2205000": "22033",   # Baton Rouge
    "1332528": "13239",   # Georgetown-Quitman County
    # Houma: the Terrebonne Parish Consolidated Government's audit reports
    # (tpcg.org, 2007 and 2011) say the city's and the parish's governments
    # were separate until the home rule charter voters approved on July 11,
    # 1981, which consolidated them.
    "2236255": "22109",
    # Not Tribune, Kansas: the Census maps the unified government as its own
    # place ("Greeley County unified government", a balance), joined by
    # name, and records Tribune as a nonfunctioning legal entity - as it
    # does Louisville. Its panel says so, with its area's note.
}

AREA_WORDS = {
    "AK": ("borough or census area", "boroughs and census areas", "Boroughs"),
    "CT": ("planning region", "planning regions", "Planning regions"),
    "LA": ("parish", "parishes", "Parishes"),
}
DEFAULT_WORDS = ("county", "counties", "Counties")

# What a whole state needs said once: on its county page above its areas,
# beside its count in the counties directory, and on the guide's map.
STATE_NOTES = {
    "CT": ("Connecticut has no county governments: it abolished them in 1960 and gave their work "
           "to the state. Since 2022 the Census Bureau has mapped the state by its nine planning "
           "regions in place of its eight old counties."),
    "RI": ("Rhode Island has no county governments. Its five counties are geographic areas the "
           "state uses to organize its courts."),
    "MA": ("Five of Massachusetts's fourteen counties have a county government. Of the other "
           "nine, seven have no government and the state provides their services, and Suffolk "
           "and Nantucket are governed together with the City of Boston and the Town of "
           "Nantucket."),
    "DC": ("The District of Columbia has no county government: the District's own government, "
           "which the Census Bureau counts as a city, does the work counties do elsewhere."),
    "AK": ("Alaska has boroughs, not counties. Where no borough is organized, in the Unorganized "
           "Borough, there is no borough government, and the Census Bureau divides the area into "
           "census areas for its statistics. Anchorage, Juneau, Sitka and Wrangell are each a city "
           "and borough governed as one, which the Census Bureau counts as a city."),
    "VA": ("Virginia's 38 independent cities lie outside any county, and each city's government "
           "also does the work a county does elsewhere."),
    "NY": ("New York City's five boroughs are counties with no county government of their own: "
           "the City of New York does their work, and the Census Bureau lists the city and its "
           "agencies under New York County."),
}


def local_name(fips, name):
    """An area's name as its state writes it (rule 75). The Census names an
    independent city "Alexandria city"; Virginia's code and the city itself
    say "City of Alexandria", Missouri's charter city is the City of St.
    Louis, and Maryland writes "Baltimore City". Carson City is its own
    name. Every other area keeps the Census's name."""
    entry = AREAS.get(fips)
    if not entry or entry[1] != INDEPENDENT or not name.endswith(" city"):
        return name
    if fips == "24510":
        return "Baltimore City"
    return "City of " + name[:-len(" city")]


def words(code):
    """``(one, many, button)``: what the state's map areas are called."""
    return AREA_WORDS.get(code, DEFAULT_WORDS)


def _unit(code, name):
    if name.endswith("Parish"):
        return "parish"
    if code == "AK":
        return "borough"
    return "county"


def _the(name):
    return name if name.startswith("the ") else "the " + name


def note(code, fips, counties):
    """Why the area *fips* has no county government, in a sentence or two,
    or None when it is not one that lacks one."""
    entry = AREAS.get(fips)
    if not entry:
        return None
    census_name, kind, gov, filed = entry
    unit = _unit(code, census_name)
    name = local_name(fips, census_name)
    if kind == CONSOLIDATED:
        place = "town" if gov.startswith("Town of ") else "city"
        if fips in BOROUGHS:
            where = ("here, for all five boroughs" if not filed else
                     f"under {counties[filed]['name']} ({BOROUGHS[filed]})")
            return (f"{name} is {BOROUGHS[fips]}, one of New York City's five boroughs, and has no "
                    f"county government of its own: {_the(gov)} does its work. The Census Bureau "
                    f"lists the city and its agencies {where}.")
        return (f"{name} has no separate {unit} government: {_the(gov)} does the {unit}'s work as "
                f"well as a {place}'s, and the Census Bureau counts the two as one {place} "
                f"government.")
    if kind == INDEPENDENT:
        apart = {"24510": " Baltimore County, next to it, is a separate county.",
                 "29510": " St. Louis County, next to it, is a separate county."}.get(fips, "")
        return (f"{name} is an independent city, outside any county: {_the(gov)} also does the "
                f"work a county does elsewhere, and the Census Bureau counts it as a city."
                + apart)
    if kind == STATE:
        return (f"{name} has no county government. It is the Kalaupapa Settlement on Molokai, run "
                f"by the state Department of Health, and the Census Bureau counts it as part of the "
                f"state government.")
    if kind == UNORGANIZED:
        if code == "RI":
            return (f"{name} has no county government: Rhode Island's counties are geographic "
                    f"areas the state uses to organize its courts.")
        return (f"{name} has no county government: the state provides the county's services "
                f"here, and the county remains a district for elections.")
    if kind == CENSUS_AREA:
        return (f"{name} is part of Alaska's Unorganized Borough, which has no borough "
                f"government. The Census Bureau divides it into census areas for its statistics.")
    if kind == REGION:
        return (f"{name} is one of Connecticut's nine planning regions, which the Census Bureau has "
                f"mapped in place of its counties since 2022. Connecticut has had no county "
                f"governments since 1960.")
    raise ValueError(f"unknown kind of county area: {kind}")


def short(code, fips):
    """A few words for the list of a state's areas: what this one is."""
    name, kind, gov, _filed = AREAS[fips]
    if fips in BOROUGHS:
        return "part of New York City"
    if kind == CONSOLIDATED:
        return f"one government with its {'town' if gov.startswith('Town of ') else 'city'}"
    if kind == INDEPENDENT:
        return "an independent city"
    if kind == STATE:
        return "run by the state"
    return f"no {_unit(code, name)} government"


def for_state(code, counties, governments):
    """``{"areaWords", "stateNote", "noCounty": {fips: {"note", "short",
    "filed"?}}}`` for a state's page data."""
    out = {}
    for fips in sorted(counties):
        text = note(code, fips, counties)
        if text:
            out[fips] = {"note": text, "short": short(code, fips)}
            filed = AREAS[fips][3]
            if filed:
                out[fips]["filed"] = filed
    one, many, button = words(code)
    # Virginia's independent cities are not counties, and the count says so:
    # "95 counties and 38 independent cities", not "133 counties".
    cities = sum(1 for f in counties if (AREAS.get(f) or ("", ""))[1] == INDEPENDENT)
    rest = len(counties) - cities
    count = f"{rest:,} {one if rest == 1 else many}" + (
        f" and {cities} independent cit{'y' if cities == 1 else 'ies'}" if cities else "")
    listed = {"CT": " Its towns and cities are listed here by planning region.",
              "RI": " Its cities and towns are listed here by the county they lie in."}
    return {
        "areaWords": {"one": one, "many": many, "button": button, "count": count},
        "stateNote": (STATE_NOTES[code] + listed.get(code, "") if code in STATE_NOTES
                      else _few(code, counties, sorted(out))),
        "noCounty": out,
    }


def _few(code, counties, lacking):
    """A state with a few such areas and no note of its own names them."""
    if not lacking:
        return ""
    names = [local_name(f, counties[f]["name"]) for f in lacking]
    unit = {"AK": "borough", "LA": "parish"}.get(code, "county")
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    one = len(names) == 1
    return (f"{joined} {'has' if one else 'have'} no separate {unit} government; pick "
            f"{'it' if one else 'one'} to see why.")


def check(code, counties, governments):
    """Problems between the map, the listing and ``AREAS``, as strings."""
    problems = []
    prefix = _fips_prefix(code)
    mine = {f: e for f, e in AREAS.items() if prefix and f.startswith(prefix)}
    for fips in sorted(counties):
        rows = governments.get(fips, [])
        has = any(r[0] == "county" for r in rows)
        entry = mine.get(fips)
        name = counties[fips]["name"]
        if not has and not entry:
            problems.append(f"{code} {fips} {name}: no county government in the listing, and "
                            f"county_areas.AREAS does not say why")
        if has and entry:
            problems.append(f"{code} {fips} {name}: county_areas.AREAS says it has no county "
                            f"government, but the listing holds one")
        if entry and entry[0] != name:
            problems.append(f"{code} {fips}: the map calls it {name!r}, county_areas.AREAS "
                            f"{entry[0]!r}")
        if entry and entry[2]:
            where = entry[3] or fips
            if not any(r[1] == entry[2] for r in governments.get(where, [])):
                problems.append(f"{code} {fips} {name}: the listing holds no {entry[2]!r} under "
                                f"{(counties.get(where) or {}).get('name', where)}")
    for fips in sorted(set(mine) - set(counties)):
        problems.append(f"{code} {fips} {mine[fips][0]}: in county_areas.AREAS but not on the map")
    return problems


def _fips_prefix(code):
    from .geo import FIPS_TO_STATE
    return next((f for f, c in FIPS_TO_STATE.items() if c == code), None)


def state_line(code, counties):
    """The guide's and the directory's words for a state some of whose
    county areas have no county government: ``""`` when every one has."""
    lacking = [f for f in counties if f in AREAS]
    if not lacking:
        return ""
    if code in ("CT", "RI"):
        return STATE_NOTES[code]
    _one, many, _button = words(code)
    unit = {"AK": "borough", "LA": "parish"}.get(code, "county")
    k = len(lacking)
    return (f"{k} of {state_name(code)}'s {len(counties)} {many} "
            f"{'has' if k == 1 else 'have'} no separate {unit} government.")


def directory_note(code):
    """What the counties directory and the guide's map say about a state
    whose county areas are not all governed by a county: ``""`` when they
    are. Built from ``AREAS`` alone, so the two pages cannot disagree."""
    if code in STATE_NOTES:
        return STATE_NOTES[code]
    prefix = _fips_prefix(code)
    mine = [(f, e) for f, e in sorted(AREAS.items()) if prefix and f.startswith(prefix)]
    if not mine:
        return ""
    unit = {"AK": "borough", "LA": "parish"}.get(code, "county")
    phrases = []
    for kind in (CONSOLIDATED, INDEPENDENT, STATE, UNORGANIZED, CENSUS_AREA, REGION):
        names = [local_name(f, e[0]) for f, e in mine if e[1] == kind]
        if not names:
            continue
        one = len(names) == 1
        joined = names[0] if one else ", ".join(names[:-1]) + " and " + names[-1]
        if kind == CONSOLIDATED:
            phrases.append(f"{joined} {'is' if one else 'are each'} governed together with "
                           f"{'its' if one else 'a'} city, as one government the Census Bureau "
                           f"counts as a city")
        elif kind == INDEPENDENT:
            phrases.append(f"{joined} {'is an independent city' if one else 'are independent cities'}"
                           f", outside any county")
        elif kind == STATE:
            phrases.append(f"{joined} {'is' if one else 'are'} run by the state")
        else:
            phrases.append(f"{joined} {'has' if one else 'have'} no government")
    text = "; ".join(phrases)
    return f"No separate {unit} government: " + text + "."
