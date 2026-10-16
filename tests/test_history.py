"""The public offices each person has held (kyc/history.py): Congress from
congress-legislators, every other office from Wikidata, shown only where the
person's own Wikipedia infobox gives the same office the same years.

The infobox text below is trimmed from the articles as read on 2026-10-16,
keeping the forms that broke an earlier reading: an embedded block in a
collapsed section, a comment, a lower-case template name, a seat named by
its state, numbering that skips, a unicameral legislature."""

import json
import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cabinet, history  # noqa: E402

RUBIO = """{{Infobox officeholder
| name               = Marco Rubio
| office             = 72nd [[United States Secretary of State]]
| term_start         = January 21, 2025
| term_end           =
| office1            = 30th [[United States National Security Advisor]]
| term_start1        = May 1, 2025
| successor1   =  <!-- | office9 = Commented out | term_start9 = 1990 -->
{{Collapsed infobox section begin |Other administration positions}}
{{Infobox officeholder
| embed        = yes
| office3      = Acting [[Administrator of the United States Agency for International Development]]
| term_start3  = February 3, 2025
| term_end3    = August 29, 2025
{{Collapsed infobox section end}}}}
| jr/sr4             = United States Senator
| state4             = [[Florida]]
| term_start4        = January 3, 2011
| term_end4          = January 20, 2025
{{collapsed infobox section begin |last=yes |Local offices}}{{Infobox officeholder
| embed        = yes
| office8      = 94th [[List of speakers of the Florida House of Representatives|Speaker of the Florida House of Representatives]]
| term_start8  = November 21, 2006
| term_end8    = November 18, 2008
| state_house9 = Florida
| district9    = [[Florida's 111th House of Representatives district|111th]]
| term_start9  = January 25, 2000
| term_end9    = November 18, 2008
{{Collapsed infobox section end}}}}
| birth_date = {{birth date and age|1971|5|28}}
}}"""

SHAHEEN = """{{Infobox officeholder
| jr/sr = United States Senator
| state = [[New Hampshire]]
| term_start = January 3, 2009
| term_end =
| office4 = 78th [[Governor of New Hampshire]]
| term_start4 = January 9, 1997
| term_end4 = January 9, 2003
| state_senate5 = New Hampshire
| term_start5 = December 5, 1990
| term_end5 = December 4, 1996
{{Infobox officeholder | embed = yes
| office5 = Ranking Member of the [[United States Senate Committee on Small Business]]
| term_start5 = January 3, 2025
}}
}}"""

MURPHY = """{{Infobox officeholder
| state3 = [[Connecticut]]
| district3 = {{ushr|CT|5|5th}}
| term_start3 = January 3, 2007
| term_end3 = January 3, 2013
| state_senate4 = Connecticut State
| term_start4 = January 8, 2003
| term_end4 = January 3, 2007
| state_house5 = Connecticut
| district5 = [[Connecticut's 81st House of Representatives district|81st]]
| term_start6 = January 6, 1999
| term_end6 = January 8, 2003
}}"""

FISCHER = """{{Infobox officeholder
| jr/sr1 = United States Senator
| state1 = [[Nebraska]]
| term_start1 = January 3, 2013
| term_end1 =
| state_legislature2 = Nebraska
| district2 = 43rd
| term_start2 = January 5, 2005
| term_end2 = January 2, 2013
}}"""

TRUMP = """{{stack begin}}<!-- DO NOT REMOVE -->
{{infobox officeholder
| office = 47th [[President of the United States]]
| term_start = January 20, 2025
| office1 = 45th [[President of the United States]]
| term_start1 = January 20, 2017
| term_end1 = January 20, 2021
}}"""

VOUGHT = """{{Infobox officeholder
| office       = 42nd and 44th Director of the [[Office of Management and Budget]]
| term_start   = February 7, 2025
| term_end     =
| term_start1  = January 2, 2019
| term_end1    = January 20, 2021
}}"""


def term(start, end, office, acting=False):
    return {"from": start, "to": end, "office": office, "acting": acting}


class TestTheInfoboxes(unittest.TestCase):
    def test_each_embedded_block_is_read_on_its_own(self):
        blocks = cabinet.infoboxes(SHAHEEN)
        self.assertEqual(len(blocks), 2)
        # The outer block's state senate seat and the embedded block's
        # committee are both entry 5, and neither takes the other's years.
        self.assertEqual(blocks[0]["state_senate5"], "New Hampshire")
        self.assertNotIn("office5", blocks[0])
        terms = history.infobox_terms(SHAHEEN)
        self.assertIn(term("1990", "1996", "New Hampshire Senate"), terms)
        self.assertNotIn("1990", [t["from"] for t in terms if "Ranking" in (t["office"] or "")])

    def test_a_long_career_is_read_whole(self):
        terms = history.infobox_terms(RUBIO)
        self.assertIn(term("2000", "2008", "Florida House of Representatives"), terms)
        self.assertIn(term("2006", "2008", "94th Speaker of the Florida House of Representatives"),
                      terms)
        self.assertIn(term("2011", "2025", "United States Senator"), terms)
        acting = [t for t in terms if "Agency for International Development" in t["office"]]
        self.assertTrue(acting[0]["acting"])
        # A field inside a comment is not on the page.
        self.assertNotIn("1990", [t["from"] for t in terms])

    def test_a_lower_case_template_name(self):
        self.assertEqual([t["from"] for t in history.infobox_terms(TRUMP)], ["2025", "2017"])

    def test_an_entry_with_no_office_continues_the_one_before(self):
        terms = history.infobox_terms(VOUGHT)
        self.assertEqual([t["office"] for t in terms], [terms[0]["office"]] * 2)
        # Chris Murphy's article names the seat on entry 5 and its years on 6.
        murphy = history.infobox_terms(MURPHY)
        self.assertIn(term("1999", "2003", "Connecticut House of Representatives"), murphy)
        self.assertIn(term("2007", "2013", "United States Representative"), murphy)

    def test_a_seat_this_module_cannot_name_is_never_its_neighbours(self):
        fischer = history.infobox_terms(FISCHER)
        self.assertIn(term("2005", "2013", "Nebraska Legislature"), fischer)
        self.assertNotIn(term("2005", "2013", "United States Senator"), fischer)


class TestOneOffice(unittest.TestCase):
    def test_names_of_one_office(self):
        for a, b in [("member of the State Senate of Idaho", "Member of the [[Idaho Senate]]"),
                     ("Ohio state representative", "Ohio House of Representatives"),
                     ("Mayor of Richmond, Virginia", "Mayor of Richmond"),
                     ("Nebraska State Senator", "Nebraska Legislature"),
                     ("United States Secretary of State", "72nd United States Secretary of State"),
                     ("Administrator of the United States Agency for International Development",
                      "Acting Administrator of the United States Agency for International Development")]:
            self.assertTrue(history.same_office(a, cabinet._clean(b)), (a, b))

    def test_names_of_different_offices(self):
        for a, b in [("Governor of Virginia", "Lieutenant Governor of Virginia"),
                     ("member of the Florida House of Representatives",
                      "Speaker of the Florida House of Representatives"),
                     # A U.S. senator is not a state senator.
                     ("Member of the State Senate of New Hampshire", "United States Senator"),
                     ("Louisiana State Senate", "Louisiana House of Representatives"),
                     ("United States Secretary of State", "United States Secretary of Defense"),
                     ("Mayor of Salt Lake City", "Mayor of Salt Lake County"),
                     # Rule 5: Virginia is not a part of West Virginia.
                     ("Senate of Virginia", "West Virginia Senate"),
                     # Nebraska's Legislature is its senate; its House of
                     # Representatives ended in 1937 (Deb Fischer's item).
                     ("Member of the Nebraska House of Representatives", "Nebraska Legislature")]:
            self.assertFalse(history.same_office(a, b), (a, b))


def span(start, end=None):
    return {"start": {"year": start}, "end": {"year": end} if end else None}


class TestCorroboration(unittest.TestCase):
    def test_the_same_office_the_same_years(self):
        terms = [term("2006", "2010", "Governor of Virginia")]
        self.assertEqual(history.corroborate(span("2006", "2010"), terms, ["Governor of Virginia"])[0],
                         "exact")
        self.assertEqual(history.corroborate(span("2005", "2010"), terms, ["Governor of Virginia"])[0],
                         "year-off")

    def test_another_offices_years_corroborate_nothing(self):
        # Jeanne Shaheen: a U.S. Senate term never confirms a state senate seat.
        terms = [term("1990", "1996", "United States Senator")]
        self.assertEqual(history.corroborate(
            span("1990", "1996"), terms, ["Member of the State Senate of New Hampshire"]),
            (None, None, None))

    def test_consecutive_terms_are_one_span(self):
        # Michelle Fischbach: Wikidata 1996-2018, her article 1996-2013 and 2013-2018.
        terms = [term("1996", "2013", "Minnesota Senate"), term("2013", "2018", "Minnesota Senate")]
        self.assertEqual(history.corroborate(span("1996", "2018"), terms,
                                             ["member of the State Senate of Minnesota"])[0], "exact")

    def test_an_end_only_the_article_records(self):
        # Wikidata leaves Derek Merrin's seat open; his article ends it.
        terms = [term("2016", "2025", "Member of the Ohio House of Representatives")]
        agreement, end, _term = history.corroborate(span("2016"), terms, ["Ohio state representative"])
        self.assertEqual((agreement, end), ("start", "2025"))
        # Not when the start disagrees too.
        self.assertIsNone(history.corroborate(span("2015"), terms, ["Ohio state representative"])[0])


class TestCongress(unittest.TestCase):
    def test_terms_in_one_seat_are_one_span(self):
        terms = [{"type": "rep", "state": "VT", "district": 0, "start": "1991-01-03", "end": "1993-01-03"},
                 {"type": "rep", "state": "VT", "district": 0, "start": "1993-01-05", "end": "2007-01-03"},
                 {"type": "sen", "state": "VT", "start": "2007-01-04", "end": "2031-01-03"}]
        spans = history.congress_spans(terms, "2026-10-16")
        self.assertEqual([(s["office"], s["from"], s["to"], s["terms"], s["current"]) for s in spans],
                         [("U.S. Senator", "2007", None, 1, True),
                          ("U.S. Representative", "1991", "2007", 2, False)])
        self.assertEqual(spans[1]["district"], 0)

    def test_a_gap_is_two_spans(self):
        terms = [{"type": "rep", "state": "LA", "district": 4, "start": "1993-01-05", "end": "1997-01-03"},
                 {"type": "rep", "state": "LA", "district": 4, "start": "2025-01-03", "end": "2027-01-03"}]
        self.assertEqual(len(history.congress_spans(terms, "2026-10-16")), 2)

    def test_a_territory_sends_a_delegate(self):
        terms = [{"type": "rep", "state": "PR", "district": 0, "start": "2025-01-03", "end": "2029-01-03"}]
        out = history.congress_spans(terms, "2026-10-16")[0]
        self.assertEqual((out["office"], out["district"]), ("Resident Commissioner", None))

    def test_puerto_ricos_four_year_term_is_one(self):
        # congress-legislators lists it one Congress at a time.
        terms = [{"type": "rep", "state": "PR", "district": 0, "start": "2025-01-03", "end": "2027-01-03"},
                 {"type": "rep", "state": "PR", "district": 0, "start": "2027-01-03", "end": "2029-01-03"}]
        self.assertEqual(history.congress_spans(terms, "2027-02-01")[0]["terms"], 1)

    def test_what_is_current_is_the_memberships_to_say(self):
        # Read in October; built after January 3, when the term had ended.
        terms = [{"type": "sen", "state": "KY", "start": "1985-01-03", "end": "2027-01-03"}]
        person = {"congress": history.congress_spans(terms, "2026-10-16"), "offices": []}
        self.assertTrue(history.for_page(person, "2026-10-16", seated=True)["rows"][0]["current"])
        gone = history.for_page(person, "2027-01-05", seated=False)["rows"][0]
        self.assertEqual((gone["current"] if "current" in gone else False, gone["to"]), (False, "2027"))
        # Not seated: never current, whatever the dates.
        self.assertNotIn("current", history.for_page(person, "2026-10-16", seated=False)["rows"][0])


class TestOneSpan(unittest.TestCase):
    def test_a_span_across_a_redistricting_has_no_one_district(self):
        rows = [dict(statement("QSEN", "2011-01-01"), district="D58",
                     end={"year": "2012", "date": "2012-12-31", "precision": "day"}, id="a"),
                dict(statement("QSEN", "2013-01-01"), district="D63",
                     end={"year": "2024", "date": "2024-12-31", "precision": "day"}, id="b")]
        merged = history.merge(rows)
        self.assertEqual((len(merged), merged[0]["district"]), (1, None))
        same = [dict(r, district="D58") for r in rows]
        self.assertEqual(history.merge(same)[0]["district"], "D58")


def statement(position, start="2001-01-01", rank="normal", meaning=()):
    return {"position": position, "rank": rank, "meaning": list(meaning), "district": None,
            "start": {"year": start[:4], "date": start, "precision": "day"} if start else None,
            "end": None, "id": "s1"}


class TestWhichStatementsCount(unittest.TestCase):
    positions = {"QGOV": {"jurisdiction": "QVA"}, "QVA": {"us": True},
                 "QPARIS": {"jurisdiction": "QFR"}, "QFR": {"us": False},
                 "QCIA": {"jurisdiction": history.USA}, "QINTERN": {"jurisdiction": history.USA},
                 "QCHAIR": {}}
    reach = {"QGOV": {history.PUBLIC_OFFICE}, "QVA": {history.ADMIN_ENTITY},
             "QPARIS": {history.PUBLIC_OFFICE}, "QFR": {history.COUNTRY},
             "QINTERN": {history.PUBLIC_OFFICE}, "QAMB": {history.AMBASSADOR},
             "QCHAIR": {history.PUBLIC_OFFICE}}

    def why(self, s):
        return history.keep(s, self.positions, self.reach, {"QCIA"})

    def test_kept(self):
        self.assertIsNone(self.why(statement("QGOV")))
        # A reviewed federal post whose own class never reaches public office.
        self.assertIsNone(self.why(statement("QCIA")))
        self.assertIsNone(self.why(statement("QAMB")))

    def test_dropped(self):
        self.assertEqual(self.why(statement("QGOV", rank="deprecated")), "deprecated")
        # Jerry Moran's "Kansas Attorney General" is qualified "instance of: assistant".
        self.assertTrue(self.why(statement("QGOV", meaning=["P31"])).startswith("qualified"))
        self.assertEqual(self.why(statement("QGOV", start=None)), "no start")
        self.assertEqual(self.why(statement("QPARIS")), "not a U.S. place")
        self.assertEqual(self.why(statement("QINTERN")), "federal, not on the reviewed list")
        self.assertEqual(self.why(statement("QCHAIR")), "no place")
        self.assertEqual(self.why(statement(sorted(history.CONGRESS)[0])), "congress")


PERSON = {
    "wikidata": "Q1", "wikipedia": "Bernie Sanders",
    "congress": [{"office": "U.S. Representative", "state": "VT", "district": 0, "from": "1991",
                  "to": "2007", "terms": 8, "current": False}],
    "offices": [{"office": "Mayor of Burlington", "where": "Burlington, Vermont", "district": None,
                 "from": "1981", "to": "1989", "open": False, "agree": "exact", "item": "Q2"},
                {"office": "Ohio state representative", "where": "Ohio", "district": None,
                 "from": "2016", "to": "2025", "open": False, "agree": "start", "item": "Q3"}],
    "withheld": [{"office": "Mayor of Salt Lake City", "from": "2013", "to": "2019"}],
}


class TestWhatThePageIsGiven(unittest.TestCase):
    def test_newest_first_with_an_at_large_seat(self):
        page = history.for_page(PERSON)
        self.assertEqual([r["from"] for r in page["rows"]], ["2016", "1991", "1981"])
        house = page["rows"][1]
        # District 0 is "at large", not an absence (0 == False in Python).
        self.assertEqual((house["district"], house["where"]), (0, "Vermont"))
        self.assertNotIn("agree", page["rows"][2])
        self.assertEqual(page["rows"][0]["agree"], "start")
        self.assertEqual(page["withheld"], 1)

    def test_a_record_read_from_another_article_is_not_attached(self):
        cache = {"read": "2026-10-16", "people": {
            "FEC_1": dict(PERSON, asked="Jane Doe (politician)"),
            "FEC_2": dict(PERSON, asked="John Roe")}}
        profiles = [{"id": "FEC_1", "name": "Jane Doe", "isCandidate": True,
                     "wikipedia": "Jane Doe (politician)"},
                    {"id": "FEC_2", "name": "John Roe", "isCandidate": True,
                     "wikipedia": "John Roe (judge)"},
                    {"id": "A000001", "name": "A Member", "isCandidate": False}]
        self.assertEqual(history.apply_cache(profiles, cache), 1)
        self.assertIn("politicalHistory", profiles[0])
        self.assertNotIn("politicalHistory", profiles[1])
        codes = {code for _level, code, _m, _d in history.problems(cache, profiles)}
        self.assertTrue({"history-stale", "history-missing", "history-withheld"} <= codes)


# --------------------------------------------------------------- the network

def claim(prop, value, qualifiers=None):
    snak = {"datavalue": {"value": value}}
    out = {"mainsnak": snak, "rank": "normal", "id": f"{prop}-{json.dumps(value)}"}
    if qualifiers:
        out["qualifiers"] = qualifiers
    return out


def item(qid):
    return {"id": qid}


def when(date):
    return [{"datavalue": {"value": {"time": f"+{date}T00:00:00Z", "precision": 11}}}]


def position_held(qid, start, end=None):
    qualifiers = {"P580": when(start)}
    if end:
        qualifiers["P582"] = when(end)
    return claim("P39", item(qid), qualifiers)


ENTITIES = {
    # Tim Kaine, a member, by congress-legislators' id.
    "Q359888": {"sitelinks": {"enwiki": {"title": "Tim Kaine"}}, "claims": {
        "P31": [claim("P31", item("Q5"))],
        "P39": [position_held("QGOVVA", "2006-01-14", "2010-01-16"),
                position_held("QMAYOR", "1998-07-01", "2001-09-01"),
                position_held("Q4416090", "2013-01-03")]}},
    # A challenger, through the article her election page links.
    "Q500": {"sitelinks": {"enwiki": {"title": "Jane Doe (politician)"}}, "claims": {
        "P31": [claim("P31", item("Q5"))],
        "P39": [position_held("QOHHOUSE", "2019-01-07")]}},
    # An election page's article that is not a person.
    "Q600": {"sitelinks": {"enwiki": {"title": "2026 Ohio elections"}}, "claims": {
        "P31": [claim("P31", item("Q40231"))]}},
    # The President, by the executive cache's id.
    "Q22686": {"sitelinks": {"enwiki": {"title": "Donald Trump"}}, "claims": {
        "P31": [claim("P31", item("Q5"))],
        "P39": [position_held("Q11696", "2025-01-20")]}},
    "QGOVVA": {"sitelinks": {"enwiki": {"title": "Governor of Virginia"}},
               "labels": {"en": {"value": "Governor of Virginia"}},
               "claims": {"P1001": [claim("P1001", item("QVA"))]}},
    "QMAYOR": {"sitelinks": {"enwiki": {"title": "Mayor of Richmond, Virginia"}},
               "labels": {"en": {"value": "Mayor of Richmond"}},
               "claims": {"P1001": [claim("P1001", item("QRIC"))]}},
    "QOHHOUSE": {"labels": {"en": {"value": "member of the Ohio House of Representatives"}},
                 "claims": {"P1001": [claim("P1001", item("QOH"))]}},
    "Q4416090": {"labels": {"en": {"value": "United States senator"}},
                 "claims": {"P1001": [claim("P1001", item("Q30"))]}},
    "Q11696": {"sitelinks": {"enwiki": {"title": "President of the United States"}},
               "labels": {"en": {"value": "President of the United States"}},
               "claims": {"P1001": [claim("P1001", item("Q30"))]}},
    "QVA": {"sitelinks": {"enwiki": {"title": "Virginia"}}, "labels": {"en": {"value": "Virginia"}}},
    "QRIC": {"sitelinks": {"enwiki": {"title": "Richmond, Virginia"}},
             "labels": {"en": {"value": "Richmond"}}},
    "QOH": {"sitelinks": {"enwiki": {"title": "Ohio"}}, "labels": {"en": {"value": "Ohio"}}},
    "Q30": {"sitelinks": {"enwiki": {"title": "United States"}},
            "labels": {"en": {"value": "United States"}}},
}
CLASSES = {"QGOVVA": [history.PUBLIC_OFFICE], "QMAYOR": [history.PUBLIC_OFFICE],
           "QOHHOUSE": [history.PUBLIC_OFFICE, history.LEGISLATOR],
           "Q4416090": [history.PUBLIC_OFFICE, history.LEGISLATOR],
           "QVA": [history.ADMIN_ENTITY], "QRIC": [history.ADMIN_ENTITY], "QOH": [history.ADMIN_ENTITY],
           "Q30": [history.COUNTRY]}
US = {"QVA", "QRIC", "QOH", "Q30"}
# The state each place lies in (P131), by its item and its English label.
STATE_OF = {"QVA": ("QVA", "Virginia"), "QRIC": ("QVA", "Virginia"), "QOH": ("QOH", "Ohio")}
TEXTS = {
    "Tim Kaine": """{{Infobox officeholder
| office1 = 38th [[Governor of Virginia]]
| term_start1 = January 14, 2006
| term_end1 = January 16, 2010
| office2 = [[Mayor of Richmond, Virginia|Mayor of Richmond]]
| term_start2 = July 1, 1998
| term_end2 = September 1, 2001
}}""",
    "Jane Doe (politician)": """{{Infobox officeholder
| state_house = Ohio
| term_start = January 7, 2019
| term_end = December 31, 2024
}}""",
    "Donald Trump": TRUMP,
}


def fake_read(url, data=None):
    from kyc.legislators import HISTORICAL_URL, SOURCE_URL

    if url == SOURCE_URL:
        return [{"id": {"bioguide": "K000384", "wikidata": "Q359888"},
                 "terms": [{"type": "sen", "state": "VA", "start": "2013-01-03", "end": "2031-01-03"}]}]
    if url == HISTORICAL_URL:
        return []
    if data is not None:
        query = urllib.parse.parse_qs(data.decode())["query"][0]
        import re
        values = re.findall(r"VALUES \?item \{([^}]*)\}", query)[0].split()
        asked = [v[3:] for v in values]
        if "wdt:P17" in query:
            return {"results": {"bindings": [{"item": {"value": "http://www.wikidata.org/entity/" + q}}
                                             for q in asked if q in US]}}
        if "wdt:P131*" in query:
            return {"results": {"bindings": [
                {"item": {"value": "http://www.wikidata.org/entity/" + q},
                 "state": {"value": "http://www.wikidata.org/entity/" + STATE_OF[q][0]},
                 "label": {"value": STATE_OF[q][1]}} for q in asked if q in STATE_OF]}}
        return {"results": {"bindings": [
            {"item": {"value": "http://www.wikidata.org/entity/" + q},
             "root": {"value": "http://www.wikidata.org/entity/" + r}}
            for q in asked for r in CLASSES.get(q, [])]}}
    params = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()}
    if params.get("action") == "wbgetentities" and "ids" in params:
        return {"entities": {q: ENTITIES.get(q, {"missing": ""}) for q in params["ids"].split("|")}}
    if params.get("action") == "wbgetentities":
        out = {}
        for i, title in enumerate(params["titles"].split("|")):
            hit = [q for q, e in ENTITIES.items()
                   if (e.get("sitelinks") or {}).get("enwiki", {}).get("title") == title]
            out[hit[0] if hit else f"-{i + 1}"] = ENTITIES[hit[0]] if hit else {"missing": ""}
        return {"entities": out}
    if params.get("prop") == "revisions":
        return {"query": {"pages": [
            {"title": t, "revisions": [{"slots": {"main": {"content": TEXTS[t]}}}]}
            for t in params["titles"].split("|") if t in TEXTS]}}
    if params.get("prop") == "pageprops":
        return {"query": {"pages": []}}
    raise AssertionError(url)


class TestAFailedRead(unittest.TestCase):
    def test_an_error_answer_is_not_an_empty_one(self):
        import io
        from unittest import mock

        answer = io.BytesIO(json.dumps({"error": {"code": "maxlag"}}).encode())
        with mock.patch.object(history.urllib.request, "urlopen", return_value=answer):
            with self.assertRaises(history.HistoryError):
                history._get(history.WIKIDATA_API + "?action=wbgetentities&ids=Q1")
        # A query service answer without rows read nothing either.
        with self.assertRaises(history.HistoryError):
            history.classes(["Q1"], read=lambda url, data=None: {"head": {}})

    def test_a_short_read_is_refused(self):
        old = {"people": {str(i): {"offices": [1, 2]} for i in range(10)}}
        self.assertIsNone(history.short(old, old))
        self.assertIsNone(history.short(old, None))
        fewer = {"people": {str(i): {"offices": [1, 2]} for i in range(8)}}
        self.assertIn("people", history.short(fewer, old))
        thinner = {"people": {str(i): {"offices": [1]} for i in range(10)}}
        self.assertIn("offices", history.short(thinner, old))


class TestThePlace(unittest.TestCase):
    """Mitch McConnell held Jefferson County's office in Kentucky; Wikidata's
    item for it is in Jefferson County, Oklahoma."""

    entity = {"claims": {"P39": [position_held("QJUDGE", "1978-01-01", "1984-12-31")]}}
    positions = {"QJUDGE": {"title": "Jefferson County Judge/Executive", "jurisdiction": "QJEFF"},
                 "QJEFF": {"title": "Jefferson County, Oklahoma", "us": True, "state": "OK",
                           "statewide": False}}
    reach = {"QJUDGE": {history.PUBLIC_OFFICE}, "QJEFF": {history.ADMIN_ENTITY}}
    terms = [term("1978", "1984", "Jefferson County Judge/Executive")]

    def shown(self, home):
        return history.offices_for(self.entity, self.positions, self.reach, set(), self.terms, {},
                                   home)[0][0]

    def test_a_place_in_another_state_is_not_shown(self):
        office = self.shown({"KY"})
        self.assertEqual((office["office"], office["where"]), ("Jefferson County Judge/Executive", None))
        self.assertEqual(office["placeWithheld"], "Jefferson County, Oklahoma")
        codes = {c for _l, c, _m, _d in history.problems(
            {"read": "2026-10-16", "people": {"M000355": {"offices": [office]}}})}
        self.assertIn("history-place", codes)

    def test_a_place_in_the_persons_state_is(self):
        self.assertEqual(self.shown({"OK"})["where"], "Jefferson County, Oklahoma")

    def test_a_list_is_not_an_offices_name(self):
        self.assertIsNone(history._title({"sitelinks": {"enwiki": {"title": "List of governors of Colorado"}}}))
        self.assertEqual(history._title({"sitelinks": {"enwiki": {"title": "Governor of Colorado"}}}),
                         "Governor of Colorado")


class TestTheRead(unittest.TestCase):
    def test_every_person_by_an_id(self):
        profiles = [{"id": "K000384", "name": "Tim Kaine", "isCandidate": False},
                    {"id": "FEC_H0", "name": "Jane Doe", "isCandidate": True,
                     "wikipediaVia": "election-page", "wikipedia": "Jane Doe (politician)"},
                    {"id": "FEC_H1", "name": "Joe Roe", "isCandidate": True,
                     "wikipediaVia": "election-page", "wikipedia": "2026 Ohio elections"},
                    # A guessed article is never read (rule 24).
                    {"id": "FEC_H2", "name": "Sam Poe", "isCandidate": True,
                     "wikipediaVia": "search", "wikipedia": "Sam Poe"}]
        executive = {"president": {"name": "Donald J. Trump", "ids": {"wikidata": "Q22686"}}}
        cache = history.fetch(profiles, executive=executive, read=fake_read, today="2026-10-16")
        people = cache["people"]
        self.assertEqual(sorted(people), ["FEC_H0", "K000384", "x-donald-j-trump"])
        kaine = people["K000384"]
        self.assertEqual([(o["office"], o["from"], o["to"]) for o in kaine["offices"]],
                         [("Governor of Virginia", "2006", "2010"),
                          ("Mayor of Richmond, Virginia", "1998", "2001")])
        self.assertEqual(kaine["congress"][0]["office"], "U.S. Senator")
        # The Senate seat is congress-legislators' to say, never Wikidata's.
        self.assertNotIn("United States senator", [o["office"] for o in kaine["offices"]])
        doe = people["FEC_H0"]
        self.assertEqual((doe["offices"][0]["from"], doe["offices"][0]["to"], doe["offices"][0]["agree"]),
                         ("2019", "2024", "start"))
        self.assertEqual(doe["asked"], "Jane Doe (politician)")
        trump = people["x-donald-j-trump"]["offices"]
        self.assertEqual([(o["office"], o["where"], o["open"]) for o in trump],
                         [("President of the United States", None, True)])
        self.assertTrue(any("FEC_H1" in line for line in cache["unresolved"]))


if __name__ == "__main__":
    unittest.main()
