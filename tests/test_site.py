"""Tests for what the build hands the pages: summary figures, emitted files,
page wiring, and the validation checks added alongside them.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import cli, emit, fec, races as races_mod, sources, summary, validate  # noqa: E402
from kyc.profiles import build_profiles  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def member(**kwargs):
    base = {
        "id": kwargs.get("id", "X000001"),
        "name": "Test Member",
        "chamber": "Senate",
        "party": "Republican",
        "state": "TX",
        "district": "N/A",
        "districtNum": None,
        "officeLabel": "Senate • TX",
        "status": "Active Member",
        "isCandidate": False,
        "seatUp2026": False,
        "seekingReelection2026": False,
        "quality": {},
    }
    base.update(kwargs)
    return base


class TestSummary(unittest.TestCase):
    """The sidebar figures. These were hand-typed into both pages."""

    def test_counts_the_senate_by_party(self):
        people = [
            member(id="1", party="Republican"),
            member(id="2", party="Democrat"),
            member(id="3", party="Democratic-Farmer Labor"),
            member(id="4", party="Independent"),
        ]
        result = summary.build(people)
        self.assertEqual(result["senate"], {"D": 2, "R": 1, "I": 1, "vacant": 0, "total": 4})

    def test_democratic_farmer_labor_counts_as_democratic(self):
        # Both pages used to test for this separately and one of them missed
        # it in a branch, so Minnesota's delegation counted short.
        self.assertEqual(summary._party_bucket(member(party="Democratic-Farmer Labor")), "D")

    def test_a_vacant_seat_is_not_a_party(self):
        self.assertEqual(summary._party_bucket(member(party="Vacant")), "vacant")
        self.assertEqual(
            summary._party_bucket(member(party="Republican", status="Vacant")), "vacant"
        )

    def test_territory_delegates_are_excluded_from_the_house_balance(self):
        people = [
            member(id="1", chamber="House", state="TX", party="Republican"),
            member(id="2", chamber="House", state="PR", party="Democrat"),
            member(id="3", chamber="House", state="GU", party="Democrat"),
        ]
        result = summary.build(people)
        self.assertEqual(result["house"]["total"], 1)
        self.assertEqual(result["delegates"], 2)

    def test_house_seats_is_the_chamber_not_the_row_count(self):
        # A mid-term vacancy does not take a seat off the ballot.
        result = summary.build([member(id="1", chamber="House", state="TX")])
        self.assertEqual(result["house"]["seats"], 435)
        self.assertEqual(result["election"]["houseSeatsUp"], 435)

    def test_candidates_are_not_counted_as_members(self):
        people = [member(id="1"), member(id="2", isCandidate=True)]
        result = summary.build(people)
        self.assertEqual(result["senate"]["total"], 1)
        self.assertEqual(result["election"]["challengers"], 1)

    def test_defending_split_covers_only_seats_on_the_ballot(self):
        people = [
            member(id="1", party="Republican", seatUp2026=True),
            member(id="2", party="Democrat", seatUp2026=True),
            member(id="3", party="Democrat", seatUp2026=False),
        ]
        result = summary.build(people)
        self.assertEqual(result["election"]["senateSeatsUp"], 2)
        self.assertEqual(result["election"]["senateDefending"]["D"], 1)
        self.assertEqual(result["election"]["senateDefending"]["R"], 1)


class TestSummaryAgainstRealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = sources.load_all(ROOT)
        cls.record = raw["record"]
        cls.profiles, _ = build_profiles(raw)
        cls.races = races_mod.build(cls.profiles, record=cls.record)
        cls.summary = summary.build(cls.profiles, races=cls.races)

    def test_the_senate_has_one_hundred_seats(self):
        # Sitting senators: a former member is never one.
        self.assertEqual(self.summary["senate"]["total"], 100)

    def test_the_senate_seats_up_are_the_records(self):
        # 35 in 2026, whoever holds them now.
        self.assertEqual(self.summary["election"]["senateSeatsUp"],
                         sum(1 for rid in self.record["races"] if rid.startswith("S-")))

    def test_the_party_split_adds_up(self):
        senate = self.summary["senate"]
        self.assertEqual(senate["D"] + senate["R"] + senate["I"] + senate["vacant"],
                         senate["total"])

    def test_race_counts_match_the_race_list(self):
        self.assertEqual(self.summary["races"]["total"], len(self.races))

    def test_every_state_counts_each_race_as_a_seat_on_the_ballot(self):
        short = {code: (s["seatsUp"], s["races"]) for code, s in self.summary["states"].items()
                 if s["seatsUp"] != s["races"]}
        self.assertEqual(short, {})
        self.assertEqual(sum(s["seatsUp"] for s in self.summary["states"].values()),
                         len(self.races))


def read_people(path):
    """What a people file assigns (rule 94): its one global's value."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            for name in ("window.kycPeopleFile = ", "window.kycBuildMeta = "):
                if line.startswith(name):
                    # _json escapes "<!--" as "<\!--", which JavaScript reads
                    # as "<!--" and JSON does not read at all.
                    return json.loads(line[len(name):].rstrip().rstrip(";")
                                      .replace("<\\!--", "<!--"))
    return None


class TestEmit(unittest.TestCase):
    def test_writes_the_globals_the_pages_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people([member()], {"total": 1}, root=tmp,
                              races=[], summary={"senate": {}})
            with open(os.path.join(tmp, emit.DATA_FILE), encoding="utf-8") as f:
                meta = f.read()
            with open(os.path.join(tmp, emit.PEOPLE_INDEX_FILE), encoding="utf-8") as f:
                index = f.read()
            with open(emit.people_file("TX", tmp), encoding="utf-8") as f:
                texas = f.read()
        self.assertIn("window.kycBuildMeta = ", meta)
        # kyc.js takes each people file in as it is assigned (KYC.people).
        self.assertIn("window.kycPeopleFile = ", index)
        self.assertIn("window.kycPeopleFile = ", texas)

    def test_geo_file_assigns_its_own_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_geo({"states": {}, "territories": []}, root=tmp)
            with open(os.path.join(tmp, emit.GEO_FILE), encoding="utf-8") as f:
                text = f.read()
        self.assertIn("window.kycGeo", text)

    def test_a_profile_cannot_close_the_script_tag(self):
        # A roster field containing "</script>" would end the tag early and
        # break the page for everyone.
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people([member(name="</script><script>alert(1)</script> <!--")],
                              {"total": 1}, root=tmp)
            texts = []
            for name in os.listdir(os.path.join(tmp, emit.PEOPLE_DIR)):
                with open(os.path.join(tmp, emit.PEOPLE_DIR, name), encoding="utf-8") as f:
                    texts.append(f.read())
        self.assertEqual(len(texts), len(emit.people_codes()) + 2)
        for text in texts:
            self.assertNotIn("</script>", text)
            self.assertNotIn("<!--", text)

    def test_source_date_epoch_makes_the_build_reproducible(self):
        previous = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1000000000"
        try:
            self.assertEqual(emit.build_timestamp(), "2001-09-09T01:46:40+00:00")
        finally:
            if previous is None:
                os.environ.pop("SOURCE_DATE_EPOCH")
            else:
                os.environ["SOURCE_DATE_EPOCH"] = previous

    def test_writes_are_atomic(self):
        # An interrupted in-place write once truncated a 900 KB page to one
        # character, so the file is renamed into place rather than opened.
        with tempfile.TemporaryDirectory() as tmp:
            written = emit.write_people([member()], {}, root=tmp)
            self.assertEqual(len(written), len(emit.people_codes()) + 2)
            for path, size in written:
                self.assertTrue(os.path.exists(path))
                self.assertFalse(os.path.exists(path + ".tmp"))
                self.assertGreater(size, 0)
            self.assertEqual([n for n in os.listdir(os.path.join(tmp, emit.PEOPLE_DIR))
                              if n.endswith(".tmp")], [])


class TestPeopleFiles(unittest.TestCase):
    """The profiles in the files each page needs (rule 94): profiles.js held
    all 2,589, 6.7 MB, and the grid, the map and every state and district
    page loaded it to show one state."""

    def people(self):
        texan = member(id="T000001", state="TX", receipts="$10.00", financeSource="FEC",
                       committeeList=[{"code": "SSFI", "title": "Chairman"}],
                       districtOffices=[{"city": "Austin"}], education="B.A.",
                       raceId="S-TX-2026")
        rival = member(id="FEC_S6TX00001", state="TX", isCandidate=True,
                       raceId="S-TX-2026", fundingBreakdown={"individuals": 1})
        californian = member(id="C000001", state="CA", officeLabel="Senate \u2022 CA",
                             raceId="S-CA-2026", website="https://example.org")
        races = [{"id": "S-TX-2026", "state": "TX", "chamber": "Senate",
                  "incumbentIds": ["T000001"], "candidateIds": ["FEC_S6TX00001"]},
                 {"id": "S-CA-2026", "state": "CA", "chamber": "Senate",
                  "incumbentIds": ["C000001"], "candidateIds": []}]
        return [texan, rival, californian], races

    def test_the_index_is_everyone_without_what_only_the_dialog_shows(self):
        profiles, races = self.people()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people(profiles, {}, root=tmp, races=races, summary={"x": 1})
            index = read_people(os.path.join(tmp, emit.PEOPLE_INDEX_FILE))
            texas = read_people(emit.people_file("TX", tmp))
            wyoming = read_people(emit.people_file("WY", tmp))
        self.assertTrue(index["index"])
        self.assertEqual([p["id"] for p in index["people"]], [p["id"] for p in profiles])
        self.assertEqual([r["id"] for r in index["races"]], ["S-TX-2026", "S-CA-2026"])
        for record in index["people"]:
            self.assertEqual(set(record) & emit.INDEX_LEAVES_OUT, set(), record["id"])
        # What a card and the search read stays: the search's own fields.
        self.assertEqual(index["people"][0]["education"], "B.A.")
        # A state's file holds its people whole, and its races, no one else's.
        self.assertEqual(texas["people"], profiles[:2])
        self.assertEqual([r["id"] for r in texas["races"]], ["S-TX-2026"])
        # A state with nobody filed still has its file, so every page can
        # name every state's (rule 76).
        self.assertEqual((wyoming["people"], wyoming["races"]), ([], []))

    def test_a_cards_way_to_the_office_is_in_the_index(self):
        """PR #114 put a "Contact office" action on sitting members' cards
        (kyc-cards.js contactOf), and #116's index left out every field it
        reads: every card on the grid and the map would have lost it, and
        nothing would have failed."""
        offices = [{"city": "Austin"}, {"city": "Waco", "phone": "254-555-0100"}]
        form = member(id="F1", contactForm="https://example.house.gov/contact",
                      contactFormVia="official-site", contactFormChecked="2026-10-10",
                      phone="202-225-0000", districtOffices=offices)
        phone = member(id="P1", phone="202-225-0001", districtOffices=offices)
        neither = member(id="N1", contactForm="mailto:x@example.org", districtOffices=offices)
        no_phone_anywhere = member(id="Z1", districtOffices=[{"city": "Austin"}])
        record = emit.index_record(form)
        for key in ("contactForm", "contactFormVia", "contactFormChecked", "phone"):
            self.assertEqual(record[key], form[key])
        # The district offices are the dialog's, but on the record of a
        # member reached only through one, whole.
        self.assertNotIn("districtOffices", record)
        self.assertNotIn("districtOffices", emit.index_record(phone))
        self.assertEqual(emit.index_record(neither)["districtOffices"], offices)
        self.assertNotIn("districtOffices", emit.index_record(no_phone_anywhere))

    def test_every_file_names_one_build(self):
        profiles, races = self.people()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people(profiles, {}, root=tmp, races=races, summary={"x": 1})
            build = emit.read_signature(tmp)
            files = [read_people(os.path.join(tmp, emit.PEOPLE_INDEX_FILE))] + [
                read_people(emit.people_file(code, tmp)) for code in emit.people_codes()]
        self.assertEqual(build, emit.data_signature(profiles, races, {"x": 1}))
        self.assertEqual({f["build"] for f in files}, {build})

    def test_an_unchanged_file_is_left_alone(self):
        profiles, races = self.people()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people(profiles, {}, root=tmp, races=races)
            again = emit.write_people(profiles, {}, root=tmp, races=races)
            # Only the build's figures, which carry the build time.
            self.assertEqual([os.path.basename(p) for p, _ in again], ["meta.js"])
            self.assertEqual(emit.check_people(profiles, races, None, tmp), [])
            profiles[2]["name"] = "Renamed"
            rewritten = emit.write_people(profiles, {}, root=tmp, races=races)
        # A change anywhere is a new build, which every file names.
        self.assertEqual(len(rewritten), len(emit.people_codes()) + 2)

    def test_what_no_build_writes_is_not_left_to_be_served(self):
        profiles, races = self.people()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.PEOPLE_DIR))
            stray = os.path.join(tmp, emit.PEOPLE_DIR, "zz.js")
            legacy = os.path.join(tmp, emit.LEGACY_PROFILES_FILE)
            for path in (stray, legacy):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("window.legislatorsData = [];\n")
            problems = dict(emit.check_people(profiles, races, None, tmp))
            self.assertIn(stray, problems)
            self.assertIn(legacy, problems)
            emit.write_people(profiles, {}, root=tmp, races=races)
            self.assertFalse(os.path.exists(stray))
            self.assertFalse(os.path.exists(legacy))
            self.assertEqual(emit.check_people(profiles, races, None, tmp), [])

    def test_verify_finds_a_state_file_from_another_build(self):
        profiles, races = self.people()
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people(profiles, {}, root=tmp, races=races)
            path = emit.people_file("CA", tmp)
            os.remove(path)
            self.assertEqual(emit.check_people(profiles, races, None, tmp),
                             [(path, "missing or carries no signature")])
            emit.write_people(profiles, {}, root=tmp, races=races)
            profiles[0]["education"] = "M.A."
            stale = {os.path.basename(p) for p, why in emit.check_people(profiles, races, None, tmp)
                     if why == "stale"}
        self.assertEqual(stale, {"index.js"} | {f"{c.lower()}.js" for c in emit.people_codes()})

    def test_someone_filed_under_another_states_race_stops_the_split(self):
        profiles, races = self.people()
        profiles[2]["contestRaceId"] = "S-TX-2026"
        problems = emit.split_problems(profiles, races)
        self.assertTrue(any("C000001" in p and "S-TX-2026" in p for p in problems), problems)
        races[0]["candidateIds"].append("C000001")
        self.assertTrue(any("race S-TX-2026 lists C000001" in p for p in emit.split_problems(profiles, races)))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(emit.PeopleSplitError):
            emit.write_people(profiles, {}, root=tmp, races=races)
        profiles[2]["state"] = "ZZ"
        self.assertTrue(any("'ZZ'" in p for p in emit.split_problems(profiles, races)))

    def test_the_committed_files_are_one_build_and_everyone(self):
        meta = read_people(os.path.join(ROOT, emit.PEOPLE_META_FILE))
        index = read_people(os.path.join(ROOT, emit.PEOPLE_INDEX_FILE))
        states = [read_people(emit.people_file(c, ROOT)) for c in emit.people_codes()]
        self.assertEqual({index["build"]} | {f["build"] for f in states}, {meta["signature"]})
        whole = {p["id"]: p for f in states for p in f["people"]}
        self.assertEqual([p["id"] for p in index["people"]],
                         [p["id"] for p in index["people"] if p["id"] in whole])
        self.assertEqual(len(whole), len(index["people"]))
        self.assertEqual(sum(len(f["races"]) for f in states), len(index["races"]))
        for record in index["people"]:
            self.assertEqual(record, emit.index_record(whole[record["id"]]))
        self.assertFalse(os.path.exists(os.path.join(ROOT, emit.LEGACY_PROFILES_FILE)))

    def test_a_state_page_loading_everyone_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, emit.SITE_DIR)
            os.makedirs(os.path.join(site, "states"))
            os.makedirs(os.path.join(site, "data", "people"))
            os.makedirs(os.path.join(site, "assets"))
            for name in ("assets/kyc.js", "data/people/meta.js", "data/people/index.js",
                         "assets/kyc-profile.js", "assets/kyc-state.js"):
                with open(os.path.join(site, *name.split("/")), "w"):
                    pass
            with open(os.path.join(site, "states", "tx.html"), "w", encoding="utf-8") as f:
                f.write('<script src="../assets/kyc.js"></script>'
                        '<script src="../data/people/meta.js"></script>'
                        '<script src="../data/people/index.js"></script>'
                        '<script src="../assets/kyc-profile.js"></script>'
                        '<script src="../assets/kyc-state.js"></script>')
            result = {p: (ok, note) for p, ok, note in emit.check_pages(tmp)}
        ok, note = result["states/tx.html"]
        self.assertFalse(ok)
        self.assertIn("../data/people/tx.js", note)
        # And a page that opens profiles names every people file it does not
        # load, to load when wanted.
        self.assertIn("onDemandData template does not name", note)
        self.assertIn("../data/people/ca.js", note)


def _js_functions(text):
    """``{name: body}`` for each top-level function of a page module (two
    spaces in, inside its wrapper), strings and comments blanked so a word
    in prose or a URL ("en.wikipedia.org") is not read as a field."""
    import re

    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', '""', text)
    text = re.sub(r"//[^\n]*", "", text)
    out, name = {}, None
    for line in text.split("\n"):
        m = re.match(r"  function (\w+)\(", line)
        if m:
            name = m.group(1)
        if name:
            out[name] = out.get(name, "") + line + "\n"
    return out


def index_field_reads(modules, kyc_text, leaves_out, fold_drawn, fold_entries, safe_helpers):
    """Where a module that draws from the index (rule 94) reads a field the
    index leaves out, outside the race folds that load the state's file
    first: ``[(module, function, what)]``. *modules* is ``{name: text}``;
    kyc.js's helpers that read such a field (and those that call them) count
    as reads wherever another module calls them."""
    import re

    fields = "|".join(sorted(leaves_out))
    read = re.compile(r"\b\w+\.(%s)\b" % fields)
    kyc = _js_functions(kyc_text)
    readers = {n for n, body in kyc.items() if read.search(body)} - set(safe_helpers)
    while True:
        more = {n for n, body in kyc.items() if n not in readers and n not in safe_helpers
                and any(re.search(r"(?<![\w.])%s\(" % r, body) for r in readers)}
        if not more:
            break
        readers |= more
    exported = dict(re.findall(r"^    (\w+): (\w+),?$", kyc_text, re.M))
    via_kyc = {key for key, fn in exported.items() if fn in readers}
    out = []
    for module, text in modules.items():
        allowed = set(fold_drawn.get(module, ())) | set(fold_entries.get(module, ()))
        functions = _js_functions(text)
        for fn, body in functions.items():
            if fn in allowed:
                continue
            for m in read.finditer(body):
                out.append((module, fn, m.group(0)))
            for key in via_kyc:
                if re.search(r"\bKYC\.%s\(" % key, body):
                    out.append((module, fn, "KYC." + key))
            # A fold's own helpers are reached only from a fold.
            for helper in set(fold_drawn.get(module, ())) - set(fold_entries.get(module, ())):
                if re.search(r"(?<![\w.])%s\(" % helper, body):
                    out.append((module, fn, helper + "()"))
        for entry in fold_entries.get(module, ()):
            if not re.search(r"(?<![\w.])fold\(", functions.get(entry, "")):
                out.append((module, entry, "does not draw through fold()"))
        for other in modules:
            if other == module:
                continue
            for helper in set(fold_drawn.get(module, ())) - set(fold_entries.get(module, ())):
                if re.search(r"\bKYC\.cards\.%s\(" % helper, modules[other]):
                    out.append((other, "?", "KYC.cards." + helper))
    return out


class TestTheIndexDrawsNothingItLeavesOut(unittest.TestCase):
    """Rule 94: a page holding only the index draws every card, filter and
    map from it, so a view that read a field the index leaves out would say
    "No data" about a real person and fail nothing. testPeopleSplit compares
    a sample of views; this reads every module those pages load."""

    PAGES = ("index.html", "map.html", os.path.join("states", "index.html"))
    # The dialog opens a record only once its state's file is in
    # (openWhenLoaded); the state-government panels draw offices, never a
    # profile.
    EXEMPT = {"kyc-profile.js", "kyc-stategov.js"}
    # The race folds (kyc-cards.js fold()) draw their body only once
    # KYC.peopleFull says the race's state is whole.
    FOLD_DRAWN = {"kyc-cards.js": ("moneyBlock", "moneyRow", "outsideLine", "outsideOtherLine",
                                   "compareTable", "compareCell", "platformFrom")}
    FOLD_ENTRIES = {"kyc-cards.js": ("moneyBlock", "compareBlock")}
    # Reads a history record's own `wikipedia`, not the profile's.
    SAFE_HELPERS = ("officesHeld",)
    # A field the index carries, whole, on every record whose card reads it
    # (emit.INDEX_KEEPS_FOR_THE_CARD), read only where the card reads it:
    # a sitting member's way to reach their office (PR #114).
    CARD_KEEPS = {("kyc-cards.js", "contactOf"): tuple(emit.INDEX_KEEPS_FOR_THE_CARD)}

    def modules(self):
        import re

        site = os.path.join(ROOT, "candidate_profiles_site")
        names = set()
        for page in self.PAGES:
            with open(os.path.join(site, page), encoding="utf-8") as f:
                html = f.read()
            self.assertIn("data/people/index.js", html, page)
            names |= set(re.findall(r'<script src="(?:\.\./)?assets/(kyc[\w-]*\.js)', html))
        texts = {}
        for name in sorted(names):
            with open(os.path.join(site, "assets", name), encoding="utf-8") as f:
                texts[name] = f.read()
        return texts

    def check(self, modules):
        found = index_field_reads(
            {n: t for n, t in modules.items() if n not in self.EXEMPT and n != "kyc.js"},
            modules["kyc.js"], emit.INDEX_LEAVES_OUT, self.FOLD_DRAWN, self.FOLD_ENTRIES,
            self.SAFE_HELPERS)
        return [(m, f, what) for m, f, what in found
                if what.split(".")[-1] not in self.CARD_KEEPS.get((m, f), ())]

    def test_no_view_drawn_from_the_index_reads_what_it_leaves_out(self):
        self.assertEqual(self.check(self.modules()), [])

    def test_the_exempt_modules_are_what_they_say(self):
        modules = self.modules()
        self.assertIn("openWhenLoaded", modules["kyc-profile.js"])
        stategov = modules.get("kyc-stategov.js", "")
        for api in ("KYC.people(", "KYC.byId(", "legislatorsData", "kycRaces"):
            self.assertNotIn(api, stategov)

    def test_the_guard_finds_a_card_reading_money(self):
        modules = self.modules()
        modules["kyc-cards.js"] += ("\n  function card2(item) {\n"
                                    "    return item.receipts + KYC.moneyAmount(item, 'x') +"
                                    " moneyRow(item) + item.districtOffices;\n  }\n")
        modules["kyc-map.js"] += "\n  function x(p) { return KYC.cards.compareCell(p); }\n"
        found = {(m, f, what) for m, f, what in self.check(modules)}
        self.assertIn(("kyc-cards.js", "card2", "item.receipts"), found)
        self.assertIn(("kyc-cards.js", "card2", "KYC.moneyAmount"), found)
        self.assertIn(("kyc-cards.js", "card2", "moneyRow()"), found)
        # The offices the index keeps for contactOf are read there only.
        self.assertIn(("kyc-cards.js", "card2", "item.districtOffices"), found)
        self.assertIn(("kyc-map.js", "?", "KYC.cards.compareCell"), found)


class TestChamberScores(unittest.TestCase):
    """The ticks beside a member's own left-right score are every sitting
    member of the chamber's, counted by the build: a state page holds its
    own state's people only (rule 94)."""

    def test_read_as_the_dialog_reads_them(self):
        from kyc import voteview
        text = voteview.describe(0.53, 119)
        self.assertEqual(voteview.read_described(text), (0.53, "119th Congress"))
        self.assertEqual(voteview.read_described("DW-NOMINATE: -0.21"), (-0.21, ""))
        self.assertIsNone(voteview.read_described("Not scored"))
        self.assertIsNone(voteview.read_described(None))

    def test_each_chamber_and_congress_apart_and_only_who_sits(self):
        from kyc import voteview
        people = [
            member(id="S1", voting_alignment=voteview.describe(0.5, 119)),
            member(id="S2", voting_alignment=voteview.describe(-0.4, 119)),
            member(id="S3", voting_alignment=voteview.describe(0.1, 118)),
            member(id="H1", chamber="House", voting_alignment=voteview.describe(0.2, 119)),
            member(id="C1", isCandidate=True, voting_alignment=voteview.describe(0.9, 119)),
            member(id="F1", formerMember={"left": "2026-12-08"},
                   voting_alignment=voteview.describe(0.8, 119)),
            member(id="N1"),
        ]
        self.assertEqual(voteview.chamber_scores(people), {
            "House": {"119th Congress": [0.2]},
            "Senate": {"118th Congress": [0.1], "119th Congress": [-0.4, 0.5]},
        })

    def test_the_build_figures_carry_them(self):
        meta = read_people(os.path.join(ROOT, emit.PEOPLE_META_FILE))
        scores = meta["chamberScores"]
        senate = sum(len(v) for v in scores.get("Senate", {}).values())
        self.assertGreater(senate, 90)
        self.assertLessEqual(senate, 100)


class TestAssetVersions(unittest.TestCase):
    """A page and the code it runs are one version (kyc/assets.py): minutes
    after a deploy a reload ran the new index.html with the previous
    kyc-directory.js, and the grid sat on "Loading profiles..."."""

    def site(self, tmp, files):
        assets_dir = os.path.join(tmp, "candidate_profiles_site", "assets")
        os.makedirs(assets_dir, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(assets_dir, name), "wb") as handle:
                handle.write(data)

    def test_a_url_carries_its_files_content_hash(self):
        from kyc import assets
        with tempfile.TemporaryDirectory() as tmp:
            self.site(tmp, {"kyc.js": b"var a = 1;\nvar b = 2;\n", "kyc.css": b"body{}\n"})
            html = ('<link rel="stylesheet" href="../assets/kyc.css">'
                    '<script src="../assets/kyc.js"></script><script src="../data/odds.js"></script>')
            out = assets.stamp(html, tmp)
            self.assertIn(f'src="../assets/kyc.js?v={assets.version("kyc.js", tmp)}"', out)
            self.assertIn('href="../assets/kyc.css?v=', out)
            # Data files are not stamped: the odds job may change no other file.
            self.assertIn('src="../data/odds.js"', out)
            # Restamping replaces the stamp; a changed file is a new URL.
            again = assets.stamp(out, tmp)
            self.assertEqual(again, out)
            self.site(tmp, {"kyc.js": b"var a = 1;\n"})
            self.assertNotEqual(assets.stamp(out, tmp), out)

    def test_line_endings_do_not_change_the_stamp(self):
        # A Windows checkout holds CRLF, CI LF: both must stamp alike or
        # verify fails on one of them.
        from kyc import assets
        with tempfile.TemporaryDirectory() as unix, tempfile.TemporaryDirectory() as win:
            self.site(unix, {"kyc.js": b"var a = 1;\nvar b = 2;\n"})
            self.site(win, {"kyc.js": b"var a = 1;\r\nvar b = 2;\r\n"})
            self.assertEqual(assets.version("kyc.js", unix), assets.version("kyc.js", win))

    def test_data_is_stamped_by_its_signature_and_odds_is_not(self):
        # New code with data cached from before a deploy is the same mismatch;
        # the odds job may change only data/odds.js (rule 41), so no page
        # names its version.
        from kyc import assets
        with tempfile.TemporaryDirectory() as tmp:
            self.site(tmp, {"kyc.js": b"var a;\n"})
            data = os.path.join(tmp, "candidate_profiles_site", "data")
            os.makedirs(os.path.join(data, "districts"))

            def write(name, built, signature):
                with open(os.path.join(data, *name.split("/")), "w", encoding="utf-8") as handle:
                    handle.write(f"// Built: {built}\nwindow.x = 1;\n"
                                 f'window.xMeta = {{"signature":"{signature}"}};\n')
            write("profiles.js", "2026-10-16", "abcdef0123456789" * 4)
            write("districts/ca.js", "2026-10-16", "0123456789abcdef" * 4)
            write("odds.js", "2026-10-16", "fedcba9876543210" * 4)
            html = ('<script src="../data/profiles.js"></script><script src="../data/odds.js"></script>'
                    '<script src="../data/districts/ca.js"></script>')
            out = assets.stamp(html, tmp)
            self.assertIn('src="../data/profiles.js?v=abcdef0123"', out)
            self.assertIn('src="../data/districts/ca.js?v=0123456789"', out)
            self.assertIn('src="../data/odds.js"', out)
            self.assertEqual(assets.unstamped(out), [])
            # A rebuild of the same data - only the build time moves - restamps
            # nothing (rule 18).
            write("profiles.js", "2026-10-17", "abcdef0123456789" * 4)
            self.assertEqual(assets.stamp(out, tmp), out)
            # A data file the build did not write has nothing to stamp it with.
            with open(os.path.join(data, "stray.js"), "w", encoding="utf-8") as handle:
                handle.write("window.stray = 1;\n")
            with self.assertRaises(ValueError):
                assets.stamp('<script src="data/stray.js"></script>', tmp)

    def test_a_root_without_its_code_fails_rather_than_borrowing_another(self):
        from kyc import assets
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "candidate_profiles_site"))
            with self.assertRaises(OSError):
                assets.stamp('<script src="assets/kyc.js"></script>', tmp)

    def test_a_reference_to_a_missing_script_fails(self):
        from kyc import assets
        with tempfile.TemporaryDirectory() as tmp:
            self.site(tmp, {})
            with self.assertRaises(OSError):
                assets.stamp('<script src="assets/kyc-gone.js"></script>', tmp)

    def test_every_page_loads_its_code_at_the_current_version(self):
        from kyc import assets
        site = os.path.join(ROOT, "candidate_profiles_site")
        stale = []
        for folder, _dirs, files in os.walk(site):
            for name in files:
                if not name.endswith(".html"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    html = handle.read()
                if assets.unstamped(html) or assets.stamp(html, ROOT) != html:
                    stale.append(os.path.relpath(path, site))
        self.assertEqual(stale, [])
        self.assertEqual(assets.stamp_templates(ROOT, write=False), [])


class TestDataSignature(unittest.TestCase):
    """The committed data carries a content hash of what produced it.

    `git diff --exit-code` conflated "is the data in sync?" with "when was it
    built?". A rebuild always stamps a fresh timestamp, so the only way to keep
    the diff quiet was to commit the fixed SOURCE_DATE_EPOCH date - and then
    show 2001 to readers as the site's freshness stamp.
    """

    def test_signature_ignores_the_build_timestamp(self):
        first = emit.data_signature([member()], [], {"a": 1})
        os.environ["SOURCE_DATE_EPOCH"] = "1000000000"
        try:
            second = emit.data_signature([member()], [], {"a": 1})
        finally:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        self.assertEqual(first, second)

    def test_signature_ignores_key_insertion_order(self):
        # json.dumps preserves insertion order, so two builds that attached
        # the same enrichments in a different sequence produced different
        # signatures for identical data - which is what happened when verify
        # applied the disclosure cache after portraits and build applied it
        # before. A signature describes content, not fill order.
        first = dict(member())
        second = {}
        for key in reversed(list(first)):
            second[key] = first[key]
        self.assertNotEqual(list(first), list(second))
        self.assertEqual(emit.data_signature([first]), emit.data_signature([second]))

    def test_signature_changes_with_the_data(self):
        self.assertNotEqual(
            emit.data_signature([member(name="A")]),
            emit.data_signature([member(name="B")]),
        )

    def test_signature_covers_races_and_summary(self):
        base = [member()]
        self.assertNotEqual(emit.data_signature(base, [], {}),
                            emit.data_signature(base, [{"id": "S-TX-2026"}], {}))
        self.assertNotEqual(emit.data_signature(base, [], {}),
                            emit.data_signature(base, [], {"senate": {"R": 1}}))

    def test_written_file_records_its_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_people([member()], {}, root=tmp, races=[], summary={"x": 1})
            recorded = emit.read_signature(tmp)
        self.assertEqual(recorded, emit.data_signature([member()], [], {"x": 1}))

    def test_read_signature_handles_a_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(emit.read_signature(tmp))

    def test_geo_file_records_a_signature_too(self):
        geo = {"states": {"TX": {"d": "M0,0l1,1Z"}}, "territories": []}
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_geo(geo, root=tmp)
            recorded = emit.read_signature(path=os.path.join(tmp, emit.GEO_FILE))
        self.assertEqual(recorded, emit.geo_signature(geo))

    def test_the_committed_data_is_in_sync(self):
        # The same assertion CI makes, so a stale commit fails locally first.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(["--root", ROOT, "verify"])
        self.assertEqual(code, 0, buffer.getvalue())


class TestPageWiring(unittest.TestCase):
    """The build never rewrites a page; it reports when one has drifted."""

    def test_the_shipped_pages_are_wired_up(self):
        for page, ok, note in emit.check_pages(ROOT):
            self.assertTrue(ok, f"{page}: {note}")

    def test_script_sources_are_read_in_document_order(self):
        html = '<script src="a.js"></script><script defer src="b.js"></script>'
        self.assertEqual(emit.script_sources(html), ["a.js", "b.js"])

    def test_a_page_missing_its_data_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = os.path.join(tmp, emit.SITE_DIR)
            os.makedirs(page_dir)
            with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write('<script src="assets/kyc.js"></script>')
            result = dict((p, (ok, note)) for p, ok, note in emit.check_pages(tmp))
        self.assertFalse(result["index.html"][0])
        self.assertIn("data/people/index.js", result["index.html"][1])
        self.assertIn("data/people/meta.js", result["index.html"][1])

    def test_loading_the_page_module_before_its_data_is_reported(self):
        # The modules read their globals as they initialise, so the wrong
        # order renders an empty site with no error anywhere.
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = os.path.join(tmp, emit.SITE_DIR)
            os.makedirs(os.path.join(page_dir, "assets"))
            os.makedirs(os.path.join(page_dir, "data"))
            os.makedirs(os.path.join(page_dir, "data", "people"))
            for name in ("assets/kyc.js", "assets/kyc-profile.js",
                         "assets/kyc-directory.js", "data/people/index.js"):
                with open(os.path.join(page_dir, *name.split("/")), "w"):
                    pass
            with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(
                    '<script src="assets/kyc.js"></script>'
                    '<script src="assets/kyc-directory.js"></script>'
                    '<script src="data/people/index.js"></script>'
                    '<script src="assets/kyc-profile.js"></script>'
                )
            result = dict((p, (ok, note)) for p, ok, note in emit.check_pages(tmp))
        self.assertFalse(result["index.html"][0])
        self.assertIn("out of order", result["index.html"][1])


class TestBallotPage(unittest.TestCase):
    """Your ballot (rule 92): a generated page, in the navigation and the
    sitemap, loading its data before the module that draws it."""

    def setUp(self):
        from kyc import pages
        self.pages = pages
        self.html = pages.render_ballot_page("example.org")

    def test_it_is_in_the_navigation_beside_the_candidates(self):
        keys = [k for _h, entries in self.pages.nav_groups() for k, *_rest in entries]
        # "Start here" (PERSONA-04, #114) opens the list with the lookup.
        self.assertEqual(keys[:4], ["findrep", "candidates", "ballot", "races"])
        self.assertIn('href="ballot.html" data-nav="ballot" aria-current="page"', self.html)

    def test_it_loads_its_data_then_the_modules_in_order(self):
        loaded = emit.script_sources(self.html)
        wanted = [s for s in emit.BALLOT_PAGE_REQUIREMENTS if s != "assets/kyc.js"]
        self.assertEqual([s.split("?")[0] for s in loaded if s.split("?")[0] in wanted], wanted)
        # It opens profiles, so it names the votes the dialog loads.
        self.assertIn('id="onDemandData"', self.html)

    def test_the_election_day_and_cycle_are_the_cycles_never_typed(self):
        from kyc.cycle import CYCLE, general_election_day
        day = general_election_day(CYCLE)
        self.assertIn(f"{day.strftime('%B')} {day.day}, {day.year}", self.html)
        self.assertIn(f"Elections {CYCLE}", self.html)

    def test_who_represents_you_is_another_question(self):
        # Rule 27: the page says it answers who is on the ballot, and sends
        # "who represents me" to the lookup.
        self.assertIn('href="index.html#findrep"', self.html)
        self.assertIn("Who represents you now is another question", self.html)

    def test_the_sitemap_lists_it(self):
        self.assertIn("<loc>https://example.org/ballot.html</loc>",
                      self.pages.sitemap("example.org", ["TX"]))

    def test_the_shipped_page_is_current(self):
        with open(os.path.join(ROOT, emit.BALLOT_FILE), encoding="utf-8") as handle:
            self.assertIn('data-page="ballot"', handle.read())

    def test_every_way_to_it_says_the_same_words_under_its_own_icon(self):
        # The home page's hero and each state's voting block described one
        # link two ways, under the "How to vote" icon (PR #118 review).
        import re
        site = os.path.join(ROOT, emit.SITE_DIR)
        with open(os.path.join(site, "index.html"), encoding="utf-8") as handle:
            index = handle.read()
        with open(os.path.join(site, "assets", "kyc-ballot.js"), encoding="utf-8") as handle:
            script = handle.read()
        hero = re.search(r'<p class="intro-ballot">(.*?)</p>', index, re.S).group(1)
        note = re.search(r'<span class="field-note">(.*?)</span>', hero, re.S).group(1)
        words = re.search(r'var ENTRY_WORDS = ((?:"[^"]*"\s*\+?\s*)+);', script).group(1)
        words = "".join(re.findall(r'"([^"]*)"', words))
        self.assertEqual(" ".join(note.split()), words)
        self.assertIn('<use href="#i-ballot"/>', hero)
        self.assertIn('KYC.icon("ballot")', script)
        self.assertIn('href="ballot.html" data-nav="ballot">\n                <svg class="icon" '
                      'aria-hidden="true"><use href="#i-ballot"/>', index)


class TestStatePages(unittest.TestCase):
    """Fifty-seven pages from one template, checked the way the data is."""

    def test_a_state_page_carries_its_code_and_relative_paths(self):
        from kyc import pages
        html = pages.render_state("TX", "example.org",
                                  {"states": {"TX": {"name": "Texas", "seatsUp": 40, "house": 38}}})
        self.assertIn('data-state="TX"', html)
        self.assertIn('data-root="../"', html)
        self.assertIn("<title>Texas — Know Your Candidate</title>", html)
        self.assertIn('rel="canonical" href="https://example.org/states/tx.html"', html)
        # Its own state's people, not everyone's (rule 94).
        self.assertIn('src="../data/people/tx.js"', html)
        self.assertNotIn("../data/people/index.js", emit.script_sources(html))
        # ...which it names, with every other state's, to load when wanted.
        self.assertIn("../data/people/index.js", emit.on_demand_sources(html))
        self.assertIn("40 seats", html)
        self.assertNotIn("$title", html)          # every placeholder filled

    def test_a_territory_reads_as_a_delegate(self):
        from kyc import pages
        html = pages.render_state("GU", "example.org",
                                  {"states": {"GU": {"name": "Guam", "seatsUp": 1, "house": 1}}})
        self.assertIn("delegate to the U.S. House", html)

    def test_state_names_agree_with_the_pipeline(self):
        from kyc import pages
        from kyc.normalize import US_STATES
        self.assertEqual(pages.state_name("TX"), "Texas")
        self.assertEqual(pages.state_name("DC"), "District of Columbia")
        self.assertEqual(set(pages.STATE_NAMES), set(US_STATES.values()))

    def test_the_sitemap_lists_every_state_after_the_two_pages(self):
        from kyc import pages
        xml = pages.sitemap("example.org", ["TX", "AK"])
        locs = [line.strip() for line in xml.splitlines() if "<loc>" in line]
        self.assertEqual(locs, [
            "<loc>https://example.org/</loc>",
            "<loc>https://example.org/map.html</loc>",
            "<loc>https://example.org/ballot.html</loc>",
            "<loc>https://example.org/about.html</loc>",
            "<loc>https://example.org/states/index.html</loc>",
            "<loc>https://example.org/states/ak.html</loc>",
            "<loc>https://example.org/states/tx.html</loc>",
        ])

    def test_pages_are_written_and_a_hand_edit_is_reported(self):
        people = [member(id="X1", state="TX"), member(id="X2", state="AK"),
                  member(id="C1", state="TX", isCandidate=True)]
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.SITE_DIR))
            with open(os.path.join(tmp, emit.CNAME_FILE), "w", encoding="utf-8") as f:
                f.write("example.org\n")
            written = emit.write_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT)
            relative = sorted(
                os.path.relpath(w, os.path.join(tmp, emit.SITE_DIR)).replace(os.sep, "/")
                for w in written)
            # The guide's pages are checked in test_guide.py, the federal
            # pages in test_federal_pages.py, the share pages in
            # test_share.py. The sitemap is written with the pages it names.
            self.assertEqual([r for r in relative
                              if not r.startswith(("districts/", "government/", "legislature/",
                                                    "counties/", "courts/", "federal/"))],
                             ["404.html", "about.html", "ballot.html", "redistricting/ca.html",
                              "site.webmanifest", "sitemap.xml", "states/ak.html",
                              "states/index.html", "states/tx.html"])
            # A district map for every state and territory, whatever the
            # roster, and the folder's own directory of them.
            self.assertEqual(len([r for r in relative if r.startswith("districts/")
                                  and r != "districts/index.html"]), 56)
            self.assertIn("districts/index.html", relative)
            self.assertIn("courts/index.html", relative)
            self.assertEqual(emit.check_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT), [])
            with open(os.path.join(tmp, emit.STATES_DIR, "tx.html"), "a", encoding="utf-8") as f:
                f.write("<!-- edited by hand -->")
            stale = emit.check_state_pages(people, tmp, summary={"states": {}}, stamp_from=ROOT)
            self.assertEqual([os.path.basename(rel) for rel, _ in stale], ["tx.html"])
            self.assertEqual(stale[0][1], "stale")
            path = emit.write_sitemap(people, tmp)
            with open(path, encoding="utf-8") as f:
                self.assertIn("/states/ak.html", f.read())

    def test_the_committed_state_pages_are_wired(self):
        results = {p: (ok, note) for p, ok, note in emit.check_pages(ROOT)}
        state_pages = [p for p in results if p.startswith("states/")]
        self.assertGreaterEqual(len(state_pages), 50)
        for page in state_pages:
            self.assertTrue(results[page][0], f"{page}: {results[page][1]}")

    def test_a_district_page_loads_its_own_map_after_the_people(self):
        from kyc import pages
        html = pages.render_district_page("CA", "example.org")
        self.assertIn('rel="canonical" href="https://example.org/districts/ca.html"', html)
        self.assertIn('data-page="districts"', html)
        self.assertIn('data-state="CA"', html)
        self.assertIn("Proposition 50", html)
        self.assertNotIn("$", html.replace("$5,000", ""))   # every placeholder filled
        self.assertEqual(emit.script_sources(html), [
            s.replace("{code}", "ca") for s in emit.DISTRICT_PAGE_REQUIREMENTS])
        results = {p: (ok, note) for p, ok, note in emit.check_pages(ROOT)}
        district_pages = [p for p in results if p.startswith("districts/")
                          and p != "districts/index.html"]
        self.assertEqual(len(district_pages), 56)
        self.assertEqual(results["districts/index.html"], (True, "ok"))
        self.assertTrue(all(results[p] == (True, "ok") for p in district_pages))

    def test_a_district_page_says_only_what_its_seats_are(self):
        from kyc import pages
        self.assertIn("elects 4 members of the House",
                      pages.district_page_text("IA", 4)[1])
        self.assertIn("at large", pages.district_page_text("AK", 1)[1])
        self.assertIn("non-voting delegate", pages.district_page_text("GU", 1)[1])
        # A state whose map nearly changed says why it did not: a reader who
        # heard of Virginia's April referendum read only "used again".
        va = pages.district_page_text("VA", 11)[1]
        self.assertIn("struck it down on May 8", va)
        self.assertEqual(va.count("used again in 2026"), 1)
        self.assertIn("not on the ballot in 2026", pages.district_page_text("PR", 1)[1])
        self.assertIn("referendum", pages.district_page_text("MO", 8)[1])
        self.assertEqual(pages.district_page_text("MP", 1)[0],
                         "Northern Mariana Islands' seat in the House")

    def test_the_first_page_address_still_answers(self):
        from kyc import pages
        html = pages.render_redirect("../districts/ca.html", "example.org")
        self.assertIn('content="0; url=../districts/ca.html"', html)
        self.assertIn('rel="canonical" href="https://example.org/districts/ca.html"', html)
        self.assertIn('content="noindex"', html)

    def test_a_state_page_is_byte_for_byte_what_it_was(self):
        # The template grew parameters for the redistricting page; the state
        # pages must not have changed by a character.
        from kyc import pages
        html = pages.render_state("TX", "example.org", {"states": {}})
        self.assertIn('<div id="stateContent" class="state-page" data-guide-name="', html)
        self.assertEqual(emit.script_sources(html),
                         [src.replace("{code}", "tx") for src in emit.STATE_PAGE_REQUIREMENTS])
        self.assertIn("with its author and licence.</p>\n                <p><strong>Who counts", html)

    def test_the_sitemap_lists_the_district_maps_last(self):
        from kyc import pages
        xml = pages.sitemap("example.org", ["TX"], district_maps=["CA", "TX"])
        locs = [line.strip() for line in xml.splitlines() if "<loc>" in line]
        self.assertEqual(locs[-2:], ["<loc>https://example.org/districts/ca.html</loc>",
                                     "<loc>https://example.org/districts/tx.html</loc>"])

    def test_per_state_summary_counts_the_delegation(self):
        people = [
            member(id="S1", state="TX", seatUp2026=True),
            member(id="S2", state="TX"),
            member(id="H1", state="TX", chamber="House", districtNum=3, seatUp2026=True),
            member(id="C1", state="TX", isCandidate=True, raceStatus="nominee"),
            member(id="C2", state="TX", isCandidate=True, raceStatus="eliminated"),
            member(id="D1", state="GU", chamber="House", districtNum=0, seatUp2026=True),
        ]
        races = [{"id": "S-TX-2026", "state": "TX", "openSeat": True},
                 {"id": "H-TX-03-2026", "state": "TX", "openSeat": False}]
        by_state = summary.by_state(people, races)
        self.assertEqual(by_state["TX"]["senators"], 2)
        self.assertEqual(by_state["TX"]["house"], 1)
        self.assertEqual(by_state["TX"]["seatsUp"], 2)
        self.assertEqual(by_state["TX"]["open"], 1)
        self.assertEqual(by_state["TX"]["challengersOnBallot"], 1)
        self.assertEqual(by_state["TX"]["challengersOut"], 1)
        self.assertEqual(by_state["TX"]["name"], "Texas")
        self.assertEqual(by_state["GU"]["delegates"], 1)
        self.assertTrue(by_state["GU"]["territory"])

    def test_a_states_ballot_count_is_the_sum_of_its_race_headers(self):
        # Michigan's page read "16 challengers on the ballot" over race
        # headers summing 58: the headers count the people the results name
        # with no profile here, and the strip did not.
        people = [
            member(id="C1", state="MI", isCandidate=True, raceStatus="nominee"),
            member(id="C2", state="MI", isCandidate=True, ballotUnknown=True),
        ]
        races = [{"id": "S-MI-2026", "state": "MI", "openSeat": True, "candidateCount": 1,
                  "results": {"otherNominees": ["A B", "C D"]}},
                 {"id": "H-MI-01-2026", "state": "MI", "openSeat": False, "candidateCount": 0,
                  "results": {"otherNominees": ["E F"]}}]
        self.assertEqual(summary.by_state(people, races)["MI"]["challengersOnBallot"], 4)
        # Of them, the open seat's are candidates, not challengers (audit
        # 2026-10-17, RACES-14): the page splits the same total.
        self.assertEqual(summary.by_state(people, races)["MI"]["openCandidates"], 3)

    def test_a_race_says_how_its_ballot_is_decided(self):
        # A top-two ballot of two Democrats read like a misprint with the rule
        # only in a hover title (RACES-11), and Georgia's and Louisiana's
        # December rounds were on no page (PERSONA-06). From the tables
        # that cite each statute, never typed per race.
        from kyc import races as races_mod
        self.assertEqual(races_mod.ballot_kind({"state": "CA", "chamber": "House", "year": 2026}),
                         {"primaryKind": "top-two"})
        self.assertEqual(races_mod.ballot_kind({"state": "AK", "chamber": "Senate", "year": 2026}),
                         {"primaryKind": "top-four"})
        self.assertEqual(races_mod.ballot_kind({"state": "LA", "chamber": "House", "year": 2026}),
                         {"primaryKind": "open", "generalRunoff": "2026-12-12"})
        self.assertEqual(races_mod.ballot_kind({"state": "LA", "chamber": "Senate", "year": 2026}), {})
        self.assertEqual(races_mod.ballot_kind({"state": "GA", "chamber": "Senate", "year": 2026}),
                         {"generalRunoff": "2026-12-01"})
        self.assertEqual(races_mod.ballot_kind({"state": "TX", "chamber": "House", "year": 2026}), {})

    def test_filers_with_no_primary_and_no_ballot_are_not_counted_on_it(self):
        # American Samoa read "0 challengers on the ballot" over a race card
        # saying "6 filed": with no primary and no list read, its filers are
        # filers - counted apart, never as on the ballot (rule 22).
        people = [member(id="C1", state="MP", isCandidate=True)]
        races = [{"id": "H-MP-00-2026", "state": "MP", "openSeat": False, "candidateCount": 1,
                  "settled": False, "primaryDate": None, "results": None}]
        by_state = summary.by_state(people, races)
        self.assertEqual(by_state["MP"]["challengersOnBallot"], 0)
        self.assertEqual(by_state["MP"]["challengersFiled"], 1)
        # Once its list is read the race is settled and counts as any other.
        races[0].update(settled=True, results={"otherNominees": ["A B"]})
        by_state = summary.by_state(people, races)
        self.assertEqual(by_state["MP"]["challengersOnBallot"], 2)
        self.assertNotIn("challengersFiled", by_state["MP"])
        # And the national breakdown still adds up.
        races[0].update(settled=False, results=None)
        e = summary.build(people, races=races)["election"]
        self.assertEqual(e["challengersWithProfile"] + e["challengersUnprofiled"],
                         e["challengersOnBallot"])

    def test_an_empty_seat_says_who_left_and_when(self):
        # FL-20 and TX-23 read only "Vacant" for six months, with no word
        # of who left, when, or that no special election was called.
        from kyc import overrides
        people = [member(id="H1", state="TX", chamber="House", districtNum=22)]
        races = [{"id": f"H-TX-{n}-2026", "state": "TX", "chamber": "House", "district": n}
                 for n in (22, 23)]
        by_state = summary.by_state(people, races)
        entry = overrides.SEAT_VACANCIES[("TX", 23)]
        self.assertEqual(by_state["TX"]["vacancies"], [{
            "district": 23, "name": entry["name"], "left": entry["left"], "how": entry["how"],
            "special": entry["special"], "checked": entry["checked"]}])
        # Not a word once someone sits there; validate says the entry is stale.
        people.append(member(id="H2", state="TX", chamber="House", districtNum=23))
        self.assertNotIn("vacancies", summary.by_state(people, races)["TX"])
        codes = [i.code for i in validate.check_seat_vacancies(people)]
        self.assertIn("seat-vacancy-filled", codes)

    def test_every_vacancy_entry_names_a_date_and_who_left(self):
        from kyc import overrides
        for key, entry in overrides.SEAT_VACANCIES.items():
            for field in ("bioguide", "name", "left", "how", "special", "checked", "source"):
                self.assertTrue(entry.get(field), (key, field))
            self.assertRegex(entry["left"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(entry["checked"], r"^\d{4}-\d{2}-\d{2}$")

    def test_the_sidebar_breakdown_adds_up_without_subtracting(self):
        # The tooltip printed 812 - 556 = 256 names "with no FEC filing over
        # $5,000"; 245 exist. Each part is counted from the races.
        with open(os.path.join(ROOT, emit.DATA_FILE), encoding="utf-8") as handle:
            text = handle.read()
        meta = json.JSONDecoder().raw_decode(text.split("window.kycBuildMeta = ", 1)[1])[0]
        e = meta["election"]
        self.assertEqual(e["challengersWithProfile"] + e["challengersUnprofiled"],
                         e["challengersOnBallot"])

    def test_puerto_ricos_seat_says_its_title_and_when_it_is_elected(self):
        # The state page read "1 delegate - 0 seats in Congress on the 2026
        # ballot - 0 challengers", with no reason: the Resident Commissioner
        # serves four years (48 U.S.C. 891), elected in 2024 and 2028.
        people = [member(id="PR1", state="PR", chamber="House", districtNum=0),
                  member(id="G1", state="GU", chamber="House", districtNum=0, seatUp2026=True)]
        by_state = summary.by_state(people, [{"id": "H-GU-00-2026", "state": "GU"}])
        self.assertEqual(by_state["PR"]["delegateTitle"], "Resident Commissioner")
        self.assertEqual(by_state["PR"]["houseTerm"], {"years": 4, "last": 2024, "next": 2028})
        self.assertEqual(by_state["PR"]["seatsUp"], 0)
        self.assertEqual(by_state["GU"]["delegateTitle"], "Delegate")
        self.assertNotIn("houseTerm", by_state["GU"])

    def test_each_state_has_its_own_balance_and_its_vacancies(self):
        # The roster holds no row for a seat nobody holds; the races cover
        # every seat, so a race with no member is a vacancy, not a gap.
        people = [
            member(id="S1", state="TX"),
            member(id="S2", state="TX", party="Democrat"),
            member(id="H1", state="TX", chamber="House", districtNum=1),
            member(id="H2", state="TX", chamber="House", districtNum=2, party="Democrat"),
            member(id="D1", state="GU", chamber="House", districtNum=0, party="Democrat"),
        ]
        races = [{"id": f"H-TX-0{n}-2026", "state": "TX", "chamber": "House", "district": n}
                 for n in (1, 2, 3)]
        by_state = summary.by_state(people, races)
        self.assertEqual(by_state["TX"]["balance"], {
            "senate": {"D": 1, "R": 1, "I": 0, "vacant": 0},
            "house": {"D": 1, "R": 1, "I": 0, "vacant": 1}})
        self.assertEqual(by_state["GU"]["balance"]["house"], {"D": 1, "R": 0, "I": 0, "vacant": 0})
        # The vacant seat is on the ballot too: Texas read "38 seats on the
        # 2026 ballot" over 39 races when this counted members.
        self.assertEqual(by_state["TX"]["seatsUp"], 3)
        national = summary.build(people, races=races)
        self.assertEqual(national["house"]["vacant"], 1)       # the territory is not counted

    def test_the_real_house_adds_up_to_its_seats(self):
        meta = json.loads(open(os.path.join(ROOT, emit.DATA_FILE), encoding="utf-8").read()
                          .split("window.kycBuildMeta = ", 1)[1].rstrip().rstrip(";"))
        house = meta["house"]
        self.assertEqual(house["D"] + house["R"] + house["I"] + house["vacant"], house["seats"])
        for code, state in meta["states"].items():
            if state["territory"] or not state["races"]:
                continue
            seats = sum(state["balance"]["house"].values())
            with self.subTest(state=code):
                self.assertEqual(seats, state["house"] + state["balance"]["house"]["vacant"])


class TestHostnameConsistency(unittest.TestCase):
    """One hostname, six places, five files.

    GitHub Pages serves from CNAME; everything else has to agree with it or
    the site tells search engines and social networks it lives somewhere it
    does not. Nothing about a rename would look wrong locally.
    """

    def site(self, tmp, host="example.test", robots_host=None, sitemap_host=None,
             page_host=None, card_host=None):
        site = os.path.join(tmp, emit.SITE_DIR)
        os.makedirs(site, exist_ok=True)
        with open(os.path.join(site, "CNAME"), "w", encoding="utf-8") as f:
            f.write(host + "\n")
        for page in ("index.html", "map.html"):
            with open(os.path.join(site, page), "w", encoding="utf-8") as f:
                f.write('<link rel="canonical" href="https://%s/">' % (page_host or host))
        with open(os.path.join(site, "robots.txt"), "w", encoding="utf-8") as f:
            f.write("Sitemap: https://%s/sitemap.xml\n" % (robots_host or host))
        with open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write("<loc>https://%s/</loc>" % (sitemap_host or host))
        os.makedirs(os.path.join(tmp, "tools"), exist_ok=True)
        with open(os.path.join(tmp, "tools", "social-card.html"), "w", encoding="utf-8") as f:
            f.write('<div class="host">%s</div>' % (card_host or host))
        return tmp

    def problems(self, root):
        return [f"{n}: {note}" for n, ok, note in emit.check_hostname(root) if not ok]

    def test_a_consistent_site_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.problems(self.site(tmp)), [])

    def test_a_stale_robots_host_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = self.problems(self.site(tmp, robots_host="old.test"))
            self.assertEqual(len(found), 1)
            self.assertIn("robots.txt", found[0])

    def test_a_stale_canonical_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = self.problems(self.site(tmp, page_host="old.test"))
            self.assertEqual(len(found), 2, found)   # both pages

    def test_a_stale_share_card_is_caught(self):
        # The card prints the host into its image; its source is checked.
        with tempfile.TemporaryDirectory() as tmp:
            found = self.problems(self.site(tmp, card_host="old.test"))
            self.assertEqual(len(found), 1, found)
            self.assertIn("social-card.html", found[0])

    def test_a_stale_host_in_the_home_pages_structured_data_is_caught(self):
        # The canonical link agreed and the JSON-LD did not: every address
        # of the site's own on the page is read, not only the first.
        with tempfile.TemporaryDirectory() as tmp:
            self.site(tmp)
            with open(os.path.join(tmp, emit.SITE_DIR, "index.html"), "a", encoding="utf-8") as f:
                f.write('<script type="application/ld+json">{"url":"https://old.test/"}</script>')
            found = self.problems(tmp)
            self.assertEqual(len(found), 1, found)
            self.assertIn("index.html", found[0])

    def test_a_stale_sitemap_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = self.problems(self.site(tmp, sitemap_host="old.test"))
            self.assertIn("sitemap.xml", found[0])

    def test_no_cname_means_no_custom_domain_and_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, emit.SITE_DIR))
            self.assertIsNone(emit.canonical_host(tmp))
            self.assertEqual(self.problems(tmp), [])

    def test_a_missing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.site(tmp)
            os.remove(os.path.join(tmp, emit.SITE_DIR, "sitemap.xml"))
            self.assertTrue(any("missing" in p for p in self.problems(tmp)))

    def test_the_real_site_agrees_with_its_cname(self):
        self.assertEqual(self.problems(ROOT), [])

    def test_the_cname_is_a_bare_hostname(self):
        # GitHub Pages wants "host.example", not a URL and not a trailing slash.
        host = emit.canonical_host(ROOT)
        if host is None:
            self.skipTest("no custom domain configured")
        self.assertNotIn("/", host)
        self.assertNotIn(":", host)
        self.assertIn(".", host)


class TestNewValidators(unittest.TestCase):
    def test_duplicate_ids_are_an_error(self):
        issues = validate.check_identity([member(id="A"), member(id="A")])
        self.assertEqual([i.code for i in issues], ["duplicate-id"])
        self.assertEqual(issues[0].level, "error")

    def test_unique_ids_pass(self):
        self.assertEqual(validate.check_identity([member(id="A"), member(id="B")]), [])

    def test_a_missing_id_is_an_error(self):
        codes = [i.code for i in validate.check_identity([member(id="")])]
        self.assertIn("missing-id", codes)

    def test_a_race_naming_an_unknown_profile_is_an_error(self):
        races = [{"id": "S-TX-2026", "incumbentIds": ["ghost"], "candidateIds": []}]
        issues = validate.check_races([member(id="A", seatUp2026=False)], races)
        self.assertIn("dangling-race-member", [i.code for i in issues])

    def test_a_profile_on_the_ballot_with_no_race_is_a_warning(self):
        issues = validate.check_races([member(id="A", seatUp2026=True)], [])
        self.assertEqual([i.code for i in issues], ["unraced-profile"])
        self.assertEqual(issues[0].level, "warn")

    def test_no_races_supplied_means_no_findings(self):
        self.assertEqual(validate.check_races([member()], None), [])

    def test_markup_in_a_roster_field_is_flagged(self):
        issues = validate.check_markup([member(education="<b>Harvard</b>")])
        self.assertEqual([i.code for i in issues], ["markup-in-data"])

    def test_ordinary_prose_is_not_flagged(self):
        self.assertEqual(
            validate.check_markup([member(education="B.A. < 1990, M.A. 1994")]), []
        )

    def test_a_state_with_members_but_no_shape_is_an_error(self):
        geo = {"states": {"TX": {}}, "territories": []}
        issues = validate.check_geometry([member(state="CA")], geo)
        self.assertEqual([i.code for i in issues], ["unmapped-state"])

    def test_a_territory_counts_as_mapped(self):
        geo = {"states": {}, "territories": [{"code": "PR"}]}
        self.assertEqual(validate.check_geometry([member(state="PR")], geo), [])

    def test_no_geometry_means_no_geometry_findings(self):
        self.assertEqual(validate.check_geometry([member(state="CA")], None), [])


class TestFecKey(unittest.TestCase):
    """Where the FEC key comes from, and where it must never end up."""

    def setUp(self):
        self.previous = os.environ.pop("FEC_API_KEY", None)

    def tearDown(self):
        if self.previous is not None:
            os.environ["FEC_API_KEY"] = self.previous
        else:
            os.environ.pop("FEC_API_KEY", None)

    def test_environment_wins(self):
        os.environ["FEC_API_KEY"] = "from-env"
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as f:
                f.write("FEC_API_KEY=from-file\n")
            self.assertEqual(fec.api_key(tmp), "from-env")

    def test_falls_back_to_a_local_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as f:
                f.write("# a comment\nFEC_API_KEY = 'quoted-key'\nOTHER=x\n")
            self.assertEqual(fec.api_key(tmp), "quoted-key")

    def test_falls_back_to_demo_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(fec.api_key(tmp), "DEMO_KEY")
            self.assertTrue(fec.using_demo_key(tmp))

    def test_a_malformed_env_file_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".env"), "w", encoding="utf-8") as f:
                f.write("no equals sign here\n")
            self.assertEqual(fec.api_key(tmp), "DEMO_KEY")

    def test_dotenv_is_gitignored(self):
        # Committing an API key is trivial to do once and permanent after.
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as handle:
            patterns = {line.strip() for line in handle}
        self.assertTrue(
            {"*.env", ".env"} & patterns,
            ".gitignore must cover .env or an API key can be committed",
        )


class TestCliFlags(unittest.TestCase):
    """--root and --verbose must work on either side of the subcommand.

    CI ran `build --check --strict --verbose` and got
    "unrecognized arguments: --verbose", because the flags existed only on the
    top-level parser. The fix has a trap of its own: argparse's `parents=`
    shares action objects, and `set_defaults` mutates `action.default` in
    place, so seeding a top-level default silently overwrote the SUPPRESS in
    every subparser and reintroduced the bug.
    """

    def parse(self, argv):
        return cli.build_parser().parse_args(argv)

    def test_verbose_after_the_subcommand(self):
        self.assertTrue(self.parse(["build", "--check", "--verbose"]).verbose)

    def test_verbose_before_the_subcommand(self):
        self.assertTrue(self.parse(["--verbose", "build", "--check"]).verbose)

    def test_verbose_defaults_off(self):
        self.assertFalse(self.parse(["build"]).verbose)

    def test_root_on_either_side(self):
        self.assertEqual(self.parse(["--root", "/tmp", "build"]).root, "/tmp")
        self.assertEqual(self.parse(["build", "--root", "/tmp"]).root, "/tmp")

    def test_root_defaults_to_here(self):
        self.assertEqual(self.parse(["build"]).root, ".")

    def test_every_subcommand_accepts_the_shared_flags(self):
        for command in ("build", "fetch", "geo", "portraits", "finance", "refresh"):
            with self.subTest(command=command):
                args = self.parse([command, "--verbose", "--root", "/tmp"])
                self.assertTrue(args.verbose)
                self.assertEqual(args.root, "/tmp")
                self.assertEqual(args.command, command)

    def test_bare_invocation_still_builds(self):
        args = self.parse([])
        self.assertIsNone(args.command)

    def test_build_flags_parse(self):
        args = self.parse(["build", "--check", "--strict", "--json"])
        self.assertTrue(args.check and args.strict and args.json)


class TestValidationReport(unittest.TestCase):
    def test_json_report_is_serialisable(self):
        issues = validate.check_identity([member(id="A"), member(id="A")])
        payload = validate.as_dict(issues, {"total": 2})
        json.dumps(payload)  # must not raise
        self.assertEqual(payload["errors"], 1)
        self.assertEqual(payload["warnings"], 0)
        self.assertEqual(payload["stats"], {"total": 2})
        self.assertEqual(payload["issues"][0]["code"], "duplicate-id")

    def test_the_real_data_has_no_errors(self):
        raw = sources.load_all(ROOT)
        profiles, _ = build_profiles(raw)
        race_list = races_mod.build(profiles)
        issues = validate.run(profiles, raw, races=race_list)
        errors = [f"{i.code}: {i.message}" for i in issues if i.level == "error"]
        self.assertEqual(errors, [])


class TestOddsWorkflow(unittest.TestCase):
    """The twelve-hourly odds refresh publishes on its own, so what it may
    touch, and what it must pass first, is pinned here."""

    @classmethod
    def setUpClass(cls):
        def read(name):
            with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as handle:
                return handle.read()
        cls.text, cls.refresh = read("odds.yml"), read("refresh.yml")

    def test_prices_freeze_before_the_first_polls_close(self):
        # Prices moving on early returns would read as results (audit CG-15).
        self.assertIn('"2026-11-03T22:59"', self.text)
        self.assertIn("steps.due.outputs.run == 'true'", self.text)
        commit = self.text.index("Commit the new prices and deploy")
        self.assertIn("if: steps.due.outputs.run == 'true'",
                      self.text[commit:commit + 120])

    def test_it_runs_every_twelve_hours(self):
        import re

        cron = re.search(r'cron:\s*"(\d+) ([\d,]+) \* \* \*"', self.text)
        self.assertIsNotNone(cron)
        self.assertEqual(len(cron.group(2).split(",")), 2)

    def test_nothing_is_committed_before_the_checks_a_deploy_runs(self):
        commit = self.text.index("git push origin HEAD:main")
        for gate in ("build --check --strict", "build_profile_site.py verify",
                     "unittest discover tests"):
            self.assertLess(self.text.index(gate), commit, gate)

    def test_it_may_commit_only_the_odds_files(self):
        self.assertIn(r"'^candidate_profiles_site/data/odds\.(json|js)$'", self.text)
        self.assertIn("git add candidate_profiles_site/data/odds.json "
                      "candidate_profiles_site/data/odds.js", self.text)
        self.assertNotIn("git add -A", self.text)

    def test_it_starts_the_deploy_its_own_push_cannot(self):
        # A GITHUB_TOKEN push starts no workflow; workflow_dispatch is allowed.
        self.assertIn("gh workflow run deploy.yml", self.text)
        self.assertIn("actions: write", self.text)

    def test_the_roster_refresh_leaves_prices_to_it(self):
        self.assertNotIn("build_profile_site.py odds", self.refresh)


class TestRefreshWorkflow(unittest.TestCase):
    """The scheduled refresh shipped four silent defects; keep each one fixed."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, ".github", "workflows", "refresh.yml")
        with open(path, encoding="utf-8") as handle:
            cls.text = handle.read()

    def test_cached_incumbents_are_refreshed(self):
        # Without --refresh, fec.resolve_all fetches only uncached profiles.
        self.assertIn("build_profile_site.py finance --refresh", self.text)

    def test_portraits_run_on_a_schedule(self):
        # `inputs` is empty on a schedule, so this was never true there.
        self.assertNotIn("if: inputs.portraits != false", self.text)
        self.assertIn("github.event_name != 'workflow_dispatch' || inputs.portraits",
                      self.text)

    def test_a_failure_opens_an_issue(self):
        self.assertIn("issues: write", self.text)
        self.assertIn("if: failure()", self.text)
        self.assertIn('title="Weekly refresh failed"', self.text)
        self.assertIn("actions/runs/${{ github.run_id }}", self.text)

    def test_the_branch_name_is_unique_per_run(self):
        self.assertIn('branch="refresh/congress-$(date -u +%Y-%m-%d)-${{ github.run_id }}"',
                      self.text)

    def test_a_state_roster_that_cannot_be_read_stops_nothing_else(self):
        # 2026-10-19: one association's page did not resolve in DNS, the
        # four state-government commands ran as one step, and the whole
        # daily refresh failed. Each is its own step now and keeps the
        # committed cache when its source cannot be read (rule 8).
        import re
        steps = re.split(r"\n      - ", self.text)
        for command in ("executives", "officers", "statelegs", "courts"):
            step = [s for s in steps if f"build_profile_site.py {command}\n" in s + "\n"]
            self.assertEqual(len(step), 1, command)
            self.assertIn("continue-on-error: true", step[0], command)

    def test_runs_twice_a_week_then_daily_into_the_election_and_through_the_runoffs(self):
        self.assertIn('cron: "20 7 * * *"', self.text)
        self.assertIn('"2026-11-03"', self.text)
        self.assertIn('"2026-12-15"', self.text)      # after Louisiana's Dec 12 runoff
        self.assertIn("needs.gate.outputs.run == 'true'", self.text)

    def test_the_gate_picks_the_right_days(self):
        # Run the gate's own shell for a few dates; bash is on every runner.
        import re
        import shutil
        import subprocess
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("no bash")
        script = re.search(r"- id: due\n        run: \|\n(.*?)\n\n", self.text, re.S).group(1)
        script = "\n".join(line[10:] for line in script.splitlines())
        script = script.replace("${{ github.event_name }}", "schedule")
        script = script.replace(' >> "$GITHUB_OUTPUT"', "")

        def due(day, weekday):
            body = (script.replace("$(date -u +%Y-%m-%d)", day)
                    .replace("$(date -u +%u)", weekday))
            # As Actions runs a step: -e, -o pipefail.
            return subprocess.run([bash, "-eo", "pipefail", "-c", body], capture_output=True,
                                  text=True, check=True).stdout.strip()

        self.assertEqual(due("2026-10-12", "1"), "run=true")     # a Monday in October
        self.assertEqual(due("2026-10-14", "3"), "run=false")    # a Wednesday before Q3 day
        # Daily from the Q3 deadline: a Thursday run read before the filings
        # left every nominee's money at June 30 for four days (2026-10-17).
        self.assertEqual(due("2026-10-15", "4"), "run=true")
        self.assertEqual(due("2026-10-17", "6"), "run=true")     # a Saturday
        self.assertEqual(due("2026-10-21", "3"), "run=true")     # the day before pre-general reports
        self.assertEqual(due("2026-11-02", "1"), "run=true")     # the eve
        self.assertEqual(due("2026-11-03", "2"), "run=false")    # Election Day itself
        self.assertEqual(due("2026-11-04", "3"), "run=true")     # the morning after
        self.assertEqual(due("2026-12-13", "7"), "run=true")     # Louisiana's runoff
        self.assertEqual(due("2026-12-16", "3"), "run=false")
        self.assertEqual(due("2026-12-21", "1"), "run=true")

    def test_its_pull_request_gets_ci_without_a_person_approving_it(self):
        # #50 and #51 sat at "action_required" for days in October 2026.
        self.assertIn('gh workflow run ci.yml --ref "$branch"', self.text)
        self.assertIn("actions: write", self.text)

    def test_its_pull_request_merges_itself_once_ci_passes(self):
        # A refresh nobody merged kept the site eight days behind; results
        # after Nov 3 travel the same way.
        watch = self.text.index('gh run watch "$run" --exit-status')
        merge = self.text.index('gh pr merge "$new" --merge --delete-branch')
        self.assertLess(watch, merge)                    # never before CI passes
        # The dispatched run, not the pull_request one GitHub holds at
        # "action_required" (which failed #60's merge).
        self.assertIn("--event workflow_dispatch", self.text)
        self.assertIn('gh workflow run deploy.yml --ref main', self.text[merge:])

    def test_a_newer_refresh_closes_the_older_ones(self):
        self.assertIn('select(.headRefName | startswith("refresh/"))', self.text)
        self.assertIn('gh pr close "$old"', self.text)
        # A superseded pull request keeps its branch; only a merged one goes.
        close = [l for l in self.text.splitlines() if 'gh pr close "$old"' in l]
        self.assertTrue(close and not any("--delete-branch" in l for l in close))

    def test_a_waiting_refresh_reaches_a_person(self):
        path = os.path.join(ROOT, ".github", "workflows", "refresh-waiting.yml")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('title="Refresh waiting for review"', text)
        self.assertIn("24 hours ago", text)
        self.assertIn("gh issue close", text)          # and goes away once merged
        self.assertIn("issues: write", text)
        # It reports; it never changes the repository or merges anything.
        self.assertNotIn("contents: write", text)
        self.assertNotIn("gh pr merge", text)

    def test_campaign_lookups_fit_the_hourly_budget(self):
        import re

        limit = int(re.search(r"campaigns --limit (\d+)", self.text).group(1))
        # ~540 members by id + ~120 for roster challengers + ~45 field pages.
        self.assertLessEqual(540 + 120 + 45 + limit, 1000)


class TestNoControlCharacters(unittest.TestCase):
    """A backslash escape that a shell ate is a control character in a file.

    `content: "\\25B8"` in kyc.css was written through a heredoc that read
    "\\25" as octal: every "no longer in this race" toggle on the site showed a
    missing-glyph box beside "B8" for three weeks. The same pass turned two
    regular expressions in render_test.js into ones that could never match -
    `\\b` became a backspace and `\\1` a 0x01 - so two checks passed vacuously.
    Nothing a person reads or writes here needs a C0 control character.
    """

    def test_no_tracked_text_file_holds_one(self):
        import re
        import subprocess

        try:
            files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                   text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        control = re.compile(rb"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]")
        binary = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip")
        found = []
        for name in files:
            if name.lower().endswith(binary):
                continue
            with open(os.path.join(ROOT, name), "rb") as handle:
                for number, line in enumerate(handle.read().split(b"\n"), start=1):
                    if control.search(line):
                        found.append(f"{name}:{number}")
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
