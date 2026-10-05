"""Tests for the guide's maps (kyc/government_maps.py) and the Census of
Governments reader behind the local map (kyc/census.py).

A map that colours every state is a claim about every state, so the tests
hold each view to covering all fifty, to colours that are categories rather
than parties, and to the counts adding up to the sources' own totals.
"""

import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import census, geo, government_maps  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def xlsx(rows):
    """A minimal .xlsx holding *rows* as inline strings, to test the reader."""
    def col(i):
        name = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            name = chr(65 + r) + name
        return name

    body = "".join(
        f'<row r="{r + 1}">' + "".join(
            f'<c r="{col(c)}{r + 1}" t="inlineStr"><is><t>{v}</t></is></c>'
            for c, v in enumerate(row)) + "</row>"
        for r, row in enumerate(rows))
    sheet = ('<?xml version="1.0" encoding="UTF-8"?><worksheet '
             'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f"<sheetData>{body}</sheetData></worksheet>")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as book:
        book.writestr("xl/worksheets/sheet1.xml", sheet)
    return out.getvalue()


HEAD = ["GEO_ID", "GEO_TTL", "YEAR", "AMOUNT", "AGG_DESC", "ST"]


def table(national, states):
    rows = [HEAD]
    codes = {v: k for k, v in census.KINDS.items()}
    for st, counts in [("00", national)] + states:
        for kind, amount in counts.items():
            rows.append(["", "", "2022", amount, codes[kind], st])
    return xlsx(rows)


class TestCensusReader(unittest.TestCase):

    NATIONAL = {"total": "15", "county": "3", "municipal": "5", "township": "2",
                "special": "4", "school": "1"}

    def test_not_applicable_is_kept_apart_from_zero(self):
        data = table(self.NATIONAL, [
            ("48", {"total": "9", "county": "2", "municipal": "3", "township": "X",
                    "special": "3", "school": "1"}),
            ("17", {"total": "6", "county": "1", "municipal": "2", "township": "2",
                    "special": "1", "school": "0"}),
        ])
        national, states = census.parse(data)
        self.assertEqual(national["total"], 15)
        self.assertIsNone(states["TX"]["township"])       # Texas has none: "X"
        self.assertEqual(states["IL"]["school"], 0)       # a count of zero

    def test_a_table_that_does_not_add_up_is_refused(self):
        data = table(self.NATIONAL, [
            ("48", {"total": "9", "county": "2", "municipal": "3", "township": "X",
                    "special": "3", "school": "1"}),
        ])
        with self.assertRaises(census.CensusError):
            census.parse(data)

    def test_an_unreadable_count_is_refused(self):
        data = table(self.NATIONAL, [("48", {"total": "n/a"})])
        with self.assertRaises(census.CensusError):
            census.parse(data)

    def test_the_committed_cache_adds_up(self):
        cache = census.load_cache(ROOT)
        self.assertIsNotNone(cache, "run: python build_profile_site.py census")
        for kind in census.KINDS.values():
            total = sum(v[kind] or 0 for v in cache["states"].values())
            self.assertEqual(total, cache["national"][kind], kind)
        self.assertEqual(len(cache["states"]), 51)        # 50 states and D.C.


class TestGuideMaps(unittest.TestCase):

    def test_the_data_is_sound(self):
        self.assertEqual(government_maps.check(), [])

    def test_every_view_covers_every_state(self):
        for page, modes in government_maps.modes(ROOT).items():
            for mode in modes:
                missing = [c for c in government_maps.STATES if c not in mode["values"]]
                self.assertEqual(missing, [], f"{page}/{mode['id']}")

    def test_colours_are_categories_never_parties(self):
        for modes in government_maps.modes(ROOT).values():
            for mode in modes:
                for _, _, token in mode["legend"]:
                    self.assertNotIn("party", token)
                    self.assertRegex(token, r"^(cat-[1-5]|scale-[1-5]|none)$")

    def test_neighbouring_circuits_never_share_a_colour(self):
        circuits = government_maps._circuits()
        colour = {e[0]: e[2] for e in circuits["legend"]}
        near = geo.neighbours()
        for code, others in near.items():
            a = circuits["values"].get(code)
            for other in others:
                b = circuits["values"].get(other)
                if a and b and a != b:
                    self.assertNotEqual(colour[a], colour[b], f"{code} ({a}) and {other} ({b})")

    def test_every_state_is_in_one_circuit_and_samoa_in_none(self):
        values = government_maps._circuits()["values"]
        for code in government_maps.STATES:
            self.assertIn(values[code], government_maps.CIRCUITS)
        self.assertEqual(values["AS"], "none")
        self.assertEqual(values["MP"], "9")              # 48 U.S.C. 1824

    def test_the_seats_add_up_to_ncsl(self):
        seats = government_maps.SEATS
        self.assertEqual(sum(s + h for s, h in seats.values()), government_maps.NATIONAL_SEATS)
        self.assertEqual(seats["NE"], (49, 0))

    def test_every_high_court_is_one_of_five_methods(self):
        counts = {}
        for court, justices, term, method, note in government_maps.HIGH_COURTS.values():
            counts[method] = counts.get(method, 0) + 1
            self.assertGreaterEqual(justices, 5)
        self.assertEqual(sorted(counts), sorted(government_maps.METHOD_PHRASE))
        self.assertEqual(sum(counts.values()), 50)
        # The 2022 table's errors and changes, as checked: New Jersey has
        # seven justices, Utah has seven since 2026, Michigan's ballot shows
        # no party.
        self.assertEqual(government_maps.HIGH_COURTS["NJ"][1], 7)
        self.assertEqual(government_maps.HIGH_COURTS["UT"][1], 7)
        self.assertEqual(government_maps.HIGH_COURTS["MI"][3], "nonpartisan")

    def test_a_local_view_says_none_when_there_is_none(self):
        local = {m["id"]: m for m in government_maps.modes(ROOT)["local"]}
        self.assertEqual(local["local-county"]["values"]["CT"], "zero")
        self.assertIn("No county governments", local["local-county"]["facts"]["CT"])
        self.assertIn("No town or township", local["local-township"]["facts"]["TX"])

    def test_bins_rise_and_are_round(self):
        edges = government_maps._bins([3, 40, 70, 150, 320, 900, 2400, 6000, 15, 22])
        self.assertEqual(edges, sorted(set(edges)))
        for edge in edges:
            self.assertRegex(str(edge), r"^[125]0*$")

    def test_the_payload_lists_only_known_sources(self):
        payload = government_maps.payload()
        for mode in payload["modes"].values():
            for key in mode["sources"]:
                self.assertIn(key, payload["sources"])
                self.assertTrue(payload["sources"][key][1].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
