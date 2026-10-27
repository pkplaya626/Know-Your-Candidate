"""The owner's photograph decisions of 2026-10-25: nobody else in the frame
on any route (rule 38), one test of what a person refused (rule 12), and a
Commons photograph's year in its credit (rule 87)."""

import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import (judge_links, legislature, officers, overrides, photos, portraits,  # noqa: E402
                 stategov, statewide_photos, validate)

ROOT = os.path.join(os.path.dirname(__file__), "..")
REFUSED = "https://example.org/crowd.jpg"
TABLE = {REFUSED: ("2026-10-25", "Pat Doe: people behind her")}


class TestOneRefusalTest(unittest.TestCase):
    """Every page-time reader asks photos.not_a_portrait, which records what
    it refused for validate's staleness check."""

    def test_it_names_the_first_refused_and_records_it_once(self):
        passed = []
        self.assertEqual(photos.not_a_portrait("https://ok.org/a.jpg", REFUSED, table=TABLE,
                                               passed_over=passed), REFUSED)
        photos.not_a_portrait(REFUSED, table=TABLE, passed_over=passed)
        self.assertEqual(passed, [REFUSED])
        self.assertEqual(photos.not_a_portrait("https://ok.org/a.jpg", None, table=TABLE), "")

    def test_no_reader_keeps_its_own_membership_test(self):
        # Rule 12: one implementation. The readers name the list only in
        # words, never as "in overrides.NOT_A_PORTRAIT".
        import re
        for name in ("enrich", "court_photos", "officers", "statewide_photos", "judge_links"):
            with open(os.path.join(ROOT, "kyc", name + ".py"), encoding="utf-8") as handle:
                code = handle.read()
            self.assertIsNone(re.search(r"\bin overrides\.NOT_A_PORTRAIT\b(?!;)", code), name)
            self.assertNotIn("import NOT_A_PORTRAIT", code, name)

    def test_an_attorney_generals_office_photograph_refused_is_recorded(self):
        page = ("https://ag.example.gov/about", '<img src="/img/doe-headshot.jpg" '
                'alt="Attorney General Pat Doe headshot">')
        url = "https://ag.example.gov/img/doe-headshot.jpg"
        passed = []
        found, _why = officers.ag_photo("Pat Doe", "XX", [page], check=lambda u, h: (True, {
            "bytes": 1000, "width": 200, "height": 250}), refused={url: ("d", "w")},
            passed_over=passed)
        self.assertIsNone(found)
        self.assertEqual(passed, [url])

    def test_a_statewide_guide_photograph_refused_is_recorded(self):
        passed = []
        with unittest.mock.patch.object(statewide_photos, "parse_arizona",
                                        return_value=[("governor", "PAT DOE", None, REFUSED, "")]):
            records, problems, _ = statewide_photos.read_guides(
                {"AZ": {"governor": [{"name": "PAT DOE"}]}}, get=lambda u: "", pause=0,
                refused=TABLE, passed_over=passed)
        self.assertEqual(records, {})
        self.assertEqual(passed, [REFUSED])
        self.assertIn(REFUSED, statewide_photos.doubted({"notPortraits": passed}))


class TestEveryRouteAsksAtBuildTime(unittest.TestCase):
    """A file refused since it was read is not shown, on any route."""

    def test_a_profiles_article_portrait(self):
        upload = "https://upload.wikimedia.org/wikipedia/commons/d/de/Pat_Doe.jpg"
        record = {"via": "wikipedia", "title": "Pat Doe", "linked": "Pat Doe",
                  "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Pat_Doe.jpg/"
                         "330px-Pat_Doe.jpg",
                  "credit": {"licence": "CC BY 4.0", "by": "X", "year": 2019,
                             "file": "https://commons.wikimedia.org/wiki/File:Pat_Doe.jpg"}}
        profile = {"id": "B000001", "isCandidate": False, "name": "Pat Doe", "state": "XX",
                   "wikipedia": "Pat Doe", "photos": ["placeholder"]}
        key = portraits.profile_key(profile)
        self.assertEqual(portraits.addresses(record)[-1], upload)
        self.assertEqual(portraits.apply_cache([dict(profile)], {key: record}), 1)
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {upload: ("d", "w")}):
            shown = dict(profile)
            self.assertEqual(portraits.apply_cache([shown], {key: record}), 0)
            self.assertEqual(shown["photos"], ["placeholder"])

    def test_an_officers_roster_card_and_an_attorney_generals_photograph(self):
        card = "https://www.nass.org/sites/default/files/MA-Galvin-2023.jpg"
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {card: ("d", "w")}):
            self.assertNotIn("photo", officers._credited({"name": "William Galvin",
                                                          "photo": card}, officers.NASS_BY))
            cache = {"lt": {}, "sos": {}, "ag": {"XX": {"name": "Pat Doe", "photo": card,
                                                        "photoPage": "https://ag.example.gov/"}}}
            self.assertNotIn("photo", officers.for_state("XX", cache, [])["ag"])
        self.assertEqual(officers._credited({"name": "W", "photo": card}, "N")["photoBy"], "N")

    def test_a_curated_association_card(self):
        entry = {"ag": {"name": "Pat Doe"}}
        curated = {("XX", "ag"): {"name": "Pat Doe", "photo": REFUSED, "by": "NAAG",
                                  "page": "https://www.naag.org/"}}
        with unittest.mock.patch.dict(overrides.OFFICER_PHOTOS, curated), \
                unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            problems = stategov.officer_photos("XX", entry)
        self.assertNotIn("photo", entry["ag"])
        self.assertTrue(any("NOT_A_PORTRAIT" in p for p in problems))

    def test_a_legislators_card_falls_to_the_legislatures_own_or_says_why(self):
        # Gregg Haddad's caucus file shows two colleagues at the next desks.
        member = {"id": "ocd-person/haddad", "name": "Gregg Haddad", "chamber": "lower",
                  "district": "54", "party": "Democratic", "partyKey": "D",
                  "image": "http://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg"}
        self.assertIn("https://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg",
                      overrides.NOT_A_PORTRAIT)
        self.assertEqual(legislature.photo_kind(member, {"people": {}}), "notAPortrait")
        self.assertNotIn("image", legislature._person(member, "CT", 2026, pages={member["id"]: None},
                                                      photos={"people": {}}))

    def test_a_judges_file_is_withheld_and_recorded(self):
        cache = judge_links.load_cache(ROOT)
        refused = set(cache.get("notPortraits") or ())
        self.assertTrue(refused <= set(overrides.NOT_A_PORTRAIT))
        shown = {judge_links.source_url(e["portrait"]["source"])
                 for e in cache["judges"].values() if e.get("portrait")}
        # What withholds a judge's file: any entry but one whose only
        # finding is other people in the frame (the owner's "keep").
        withheld = {u for u, e in overrides.NOT_A_PORTRAIT.items() if photos.applies(e, judge=True)}
        self.assertFalse(shown & withheld)


class TestAJudgeIsNotRefusedForPeopleBehindThem(unittest.TestCase):
    """The owner, 2026-10-25: the background-people rule ("probably better
    to leave out background people") is for candidates' and officials'
    photographs; of the judges' Senate Judiciary hearing stills he said
    "keep". An entry whose only finding is other people in the frame
    withholds a candidate's photograph and never a judge's; any other
    entry withholds both."""

    # Upload addresses as Commons forms them, so a portrait's source page
    # leads back to them (judge_links.source_url).
    STILL = judge_links.commons_url(judge_links.file_ref("Pat Doe.png"))
    OTHER = judge_links.commons_url(judge_links.file_ref("Lee Roe.png"))
    TABLE = {
        STILL: ("2026-10-25", "Judge Pat Doe (FJC 1): people seated behind her (a hearing still)",
                overrides.OTHERS_IN_FRAME),
        OTHER: ("2026-10-25", "Judge Lee Roe (FJC 2): another man is the subject; the judge is at "
                              "the edge"),
    }

    def test_a_hearing_still_is_refused_for_a_candidate_and_not_for_a_judge(self):
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, self.TABLE):
            self.assertIn("NOT_A_PORTRAIT", photos.refused(self.STILL))
            self.assertEqual(photos.refused(self.STILL, judge=True), "")
            self.assertEqual(photos.not_a_portrait(self.STILL), self.STILL)
            self.assertEqual(photos.not_a_portrait(self.STILL, judge=True), "")
            # Any other finding still withholds a judge's.
            self.assertIn("NOT_A_PORTRAIT", photos.refused(self.OTHER, judge=True))
            self.assertEqual(photos.not_a_portrait(self.OTHER, judge=True), self.OTHER)

    def test_every_judges_route_asks_as_a_judge(self):
        from kyc import official_photos
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, self.TABLE):
            # A federal judge's Commons file (judge_links).
            self.assertEqual(judge_links.source_url(judge_links.file_page(self.STILL)), self.STILL)
            self.assertIsNone(judge_links.held_back({"source": judge_links.file_page(self.STILL)}))
            self.assertTrue(judge_links.held_back({"source": judge_links.file_page(self.OTHER)}))
            # A state justice's from the court's roster (court_photos asks
            # official_photos as a judge); a statewide candidate's is not.
            rec = {"photo": self.STILL}
            self.assertIsNone(official_photos.held_back(rec, judge=True))
            self.assertTrue(official_photos.held_back(rec))
            # A statewide candidate's or a nominee's Commons file is refused.
            passed = []
            self.assertEqual(photos.not_a_portrait(self.STILL, passed_over=passed), self.STILL)
            self.assertEqual(passed, [self.STILL])

    def test_a_judge_entry_with_a_still_is_never_met_by_a_judges_read(self):
        # The join's own test: the file is taken, not passed over.
        passed = []
        self.assertEqual(photos.not_a_portrait(self.STILL, table=self.TABLE, judge=True,
                                               passed_over=passed), "")
        self.assertEqual(passed, [])

    def test_no_committed_entry_withholds_a_judge_for_people_behind_them(self):
        # The 50 hearing stills of 2026-10-25 are shown again; a judge's
        # entry must find something other than people in the frame.
        for url, entry in overrides.NOT_A_PORTRAIT.items():
            if "(FJC " in entry[1]:
                self.assertFalse(photos.others_only(entry), url)

    def test_a_picture_of_a_person_is_no_person_in_the_frame(self):
        # Decided for the owner, 2026-10-25: a framed photograph, a poster, a
        # book jacket behind someone refuses nothing. A screen showing a face
        # (a rally's live feed) is not decided, and stays refused.
        import re
        pictures = re.compile(r"\b(framed|poster|book jacket)\b", re.I)
        for url, entry in overrides.NOT_A_PORTRAIT.items():
            self.assertIsNone(pictures.search(entry[1]), url)


def _stale(enrichment, routes, table):
    """The ``NOT_A_PORTRAIT`` entries of *table* the staleness check calls
    stale against *enrichment* and the other routes' *routes*."""
    with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, table, clear=True):
        issues = validate.check_portrait_overrides(enrichment, routes)
    return [u for i in issues if i.code == "stale-portrait-override" for u in i.detail]


def _forms(url):
    """Every way a cache may write *url*: as given, JSON-escaped,
    percent-encoded, and for a Commons upload its thumbnails' path and its
    File: page, the name in either spelling."""
    import json
    import re
    import urllib.parse
    out = {url, json.dumps(url)[1:-1], urllib.parse.quote(url, safe=":/")}
    commons = re.match(r"https://upload\.wikimedia\.org/wikipedia/[^/]+/"
                       r"([0-9a-f]/[0-9a-f]{2})/([^/]+)$", url)
    if commons:
        name = urllib.parse.unquote(commons.group(2))
        for spelt in {name, urllib.parse.quote(name)}:
            out |= {f"/{commons.group(1)}/{spelt}/", f"File:{spelt}",
                    f"File:{spelt.replace('_', ' ')}"}
    return out


def _held_in(data, urls):
    """Which of *urls* some file under the folder *data* still holds, in any
    form (:func:`_forms`)."""
    forms = {u: _forms(u) for u in urls}
    found = set()
    for folder, _dirs, files in os.walk(data):
        for name in files:
            with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            found |= {u for u, said in forms.items() if any(f in text for f in said)}
    return found


class TestTheStalenessCheckSeesEveryRoute(unittest.TestCase):
    """validate.check_portrait_overrides, with cli._photo_routes, must count
    as still offered every address any route's cache offers or records as
    passed over. It tests the rule on caches it makes, not the day's data:
    an entry whose site no longer offers its file is a warning for a person
    (CLAUDE.md, "Curated data"), never a failed refresh."""

    COMMONS = "https://commons.wikimedia.org/wiki/File:Pat_Doe_crowd.jpg"

    def cases(self):
        from kyc import courts, guide_photos, judge_links, legphotos, officers, statelegs
        upload = judge_links.source_url(self.COMMONS)
        u = REFUSED
        return {
            "a court's photograph's notPortraits": (courts.CACHE_PATH, {"courts": {"XX": {
                "photos": {"Pat Doe": {"photo": "https://c.example.gov/ok.jpg",
                                       "notPortraits": [u]}}}}}, u),
            "a court's refusal for a member none was taken for": (courts.CACHE_PATH, {
                "courts": {"XX": {"photoRefused": {"Pat Doe": [u]}}}}, u),
            "a court's kept photograph itself": (courts.CACHE_PATH, {"courts": {"XX": {
                "photos": {"Pat Doe": {"photo": u}}}}}, u),
            "a statewide race's refusal": (statewide_photos.CACHE_PATH, {
                "photos": {}, "notPortraits": {"XX|ag|PAT DOE": [u]}}, u),
            "a statewide refusal as caches wrote it before": (statewide_photos.CACHE_PATH, {
                "photos": {}, "notPortraits": [u]}, u),
            "a statewide licence doubt kept": (statewide_photos.CACHE_PATH, {
                "photos": {}, "licenceDoubts": {"XX|ag|PAT DOE": [u]}}, u),
            "a statewide record's Commons file": (statewide_photos.CACHE_PATH, {"photos": {
                "XX|ag|PAT DOE": {"photo": "https://upload.wikimedia.org/x/250px-a.jpg",
                                  "credit": {"page": self.COMMONS}}}}, upload),
            "an attorney general's photograph": (officers.CACHE_PATH, {"ag": {"XX": {
                "name": "Pat Doe", "photo": u}}}, u),
            "an attorney general's refusal": (officers.CACHE_PATH, {"ag": {"XX": {
                "name": "Pat Doe", "notPortraits": [u]}}}, u),
            "an attorney general's heavy original": (officers.CACHE_PATH, {"ag": {"XX": {
                "name": "Pat Doe", "photo": "https://ag.example.gov/small.jpg",
                "photoHeavy": [{"url": u}]}}}, u),
            "a lieutenant governor's roster card": (officers.CACHE_PATH, {"lt": {"XX": {
                "name": "Pat Doe", "photo": u}}}, u),
            "a judge's refusal": (judge_links.CACHE_PATH, {"judges": {},
                                                          "notPortraits": {"100": [u]}}, u),
            "a judge's refusal as caches wrote it before": (judge_links.CACHE_PATH, {
                "judges": {}, "notPortraits": [u]}, u),
            "a judge's portrait": (judge_links.CACHE_PATH, {"judges": {"100": {
                "portrait": {"source": self.COMMONS}}}}, upload),
            "a profile's portrait": (portraits.CACHE_PATH, {"k": {"url": u}}, u),
            "a profile's original": (portraits.CACHE_PATH, {"k": {
                "url": "https://example.org/small.jpg", "original": u}}, u),
            "what a profile's portrait replaces": (portraits.CACHE_PATH, {"k": {
                "url": None, "via": "unresolved", "replaces": [u]}}, u),
            "a legislator's Open States file": (statelegs.CACHE_PATH, {"states": {"XX": [
                {"id": "ocd-person/a", "name": "Pat Doe", "image": u}]}}, u),
            "a legislature's own photograph": (legphotos.CACHE_PATH, {"people": {
                "ocd-person/a": {"image": u}}}, u),
            "a legislature's file set aside": (legphotos.CACHE_PATH, {"people": {
                "ocd-person/a": {"image": None, "offered": u, "withheld": "older"}}}, u),
            "a guide's hosted photograph": (guide_photos.CACHE_PATH, {"photos": {
                "person:P1": {"state": "OR", "page": "https://sos.example.gov/book#page=3",
                              "photo": "photos/abc.jpg"}}}, "photos/abc.jpg"),
            "a guide's candidate page": (guide_photos.CACHE_PATH, {"photos": {
                "person:P1": {"state": "WA", "page": u, "photo": "photos/abc.jpg"}}}, u),
            "a guide's refusal": (guide_photos.CACHE_PATH, {
                "photos": {}, "notPortraits": {"H-WA-04-2026": [u]}}, u),
        }

    def enrichment_cases(self):
        u = REFUSED
        return {f"a campaign site's {key} {field}": {"people": {"P1": {key: value}}}
                for key in ("site", "listed", "drawn")
                for field, value in (("notPortraits", {"notPortraits": [u]}),
                                     ("portrait", {"portrait": u}),
                                     ("heavy original", {"portrait": "https://e.org/s.jpg",
                                                         "portraitHeavy": [{"url": u}]}))}

    def routes(self, files):
        import json
        import tempfile
        from kyc import cli
        with tempfile.TemporaryDirectory() as root:
            for path, content in files.items():
                os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
                with open(os.path.join(root, path), "w", encoding="utf-8") as handle:
                    json.dump(content, handle)
            return cli._photo_routes(root)

    def test_every_route_offering_or_refusing_a_file_keeps_its_entry(self):
        nobody = {"people": {"P0": {"site": {"url": "https://e.org/"}}}}
        for label, (path, content, url) in self.cases().items():
            with self.subTest(label):
                table = {url: ("2026-10-25", "Pat Doe: people behind her")}
                self.assertEqual(_stale(nobody, self.routes({path: content}), table), [])
                # The same entry with no route offering it is stale: the
                # check can fail.
                self.assertEqual(_stale(nobody, self.routes({}), table), [url])
        for label, enrichment in self.enrichment_cases().items():
            with self.subTest(label):
                self.assertEqual(_stale(enrichment, self.routes({}), TABLE), [])

    def test_a_stale_entry_on_the_committed_caches_is_in_no_data_file(self):
        """A stale entry is a warning for a person to act on. Only one whose
        address some data file still holds is the check's own failure - a
        route it does not read - and fails here."""
        import json
        from kyc import cli, enrich
        issues = validate.check_portrait_overrides(enrich.load_cache(ROOT),
                                                   cli._photo_routes(ROOT))
        stale = [u for i in issues if i.code == "stale-portrait-override" for u in i.detail]
        found = _held_in(os.path.join(ROOT, "candidate_profiles_site", "data"), stale)
        self.assertEqual(sorted(found), [], "stale to the check, yet a data file holds them")

    def test_the_search_finds_a_file_in_any_form_a_cache_writes_it(self):
        """A route may hold a Commons file only as a scaled thumbnail, its
        name percent-encoded, or as its File: page (the review of PR #159:
        two of the day's three files were held only so)."""
        import json
        import tempfile
        upload = "https://upload.wikimedia.org/wikipedia/commons/2/23/Pat_Doe_(cropped).jpg"
        held = {
            "thumbnail": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/"
                         "Pat_Doe_%28cropped%29.jpg/250px-Pat_Doe_%28cropped%29.jpg",
            "file page": "https://commons.wikimedia.org/wiki/File:Pat_Doe_(cropped).jpg",
            "encoded file page": "https://commons.wikimedia.org/wiki/File:Pat_Doe_%28cropped%29.jpg",
            "as written": upload,
            "another address": "https://example.org/x.jpg",
        }
        for label, address in held.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as data:
                with open(os.path.join(data, "c.json"), "w", encoding="utf-8") as handle:
                    json.dump({"photo": address}, handle)
                self.assertEqual(_held_in(data, [upload, REFUSED]),
                                 set() if label == "another address" else {upload})


class TestARefusalOutlivesAReadThatConcludesNothing(unittest.TestCase):
    """The refresh of 2026-10-27 (run 40510851775) failed: its ballotphotos
    step did not read the races' articles (--no-wikipedia), withheld the
    kept Commons files of Mayes Middleton and JoCasta Zamarripa a person had
    refused and dropped them unrecorded, and wrote its refusals from that
    run's reads alone, so Heather Baxter's went too; three NOT_A_PORTRAIT
    entries then read as stale. A read that concludes nothing keeps the
    refusals its last good read recorded (rule 8)."""

    KEY = "XX|ag|PAT DOE"
    OTHER = "XX|sos|LEE ROE"
    BAXTER = "https://upload.wikimedia.org/wikipedia/commons/7/7d/Lee_Roe.jpg"

    def record(self):
        return {"route": "wikipedia", "photo": "https://upload.wikimedia.org/x/250px-Pat_Doe.jpg",
                "page": "https://en.wikipedia.org/wiki/2026_race", "evidence": "the race links",
                "read": "2026-10-26", "bytes": 1000, "width": 250, "height": 300,
                "credit": {"by": "X", "licence": "CC BY 4.0", "via": "Wikimedia Commons",
                           "page": "https://commons.wikimedia.org/wiki/File:Pat_Doe_crowd.jpg"}}

    def fetch(self, previous, wikipedia, wiki=None):
        lists = {"states": {"XX": {"offices": {"ag": {"candidates": [{"name": "PAT DOE"}]},
                                              "sos": {"candidates": [{"name": "LEE ROE"}]}}}}}
        patches = [unittest.mock.patch.object(statewide_photos, "read_members",
                                              return_value=({}, [], set())),
                   unittest.mock.patch.object(statewide_photos, "read_guides",
                                              return_value=({}, [], set())),
                   unittest.mock.patch.object(statewide_photos, "read_wikipedia",
                                              return_value=wiki or ({}, [], set(), {}))]
        for p in patches:
            p.start()
        try:
            return statewide_photos.fetch(lists, {}, previous, wikipedia=wikipedia, log=None)
        finally:
            for p in patches:
                p.stop()

    def test_a_kept_photograph_a_person_refused_stays_offered(self):
        rec = self.record()
        upload = statewide_photos.official_photos.commons_upload(rec)
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                      {upload: ("2026-10-25", "Pat Doe: people behind")}):
            cache, problems = self.fetch({"photos": {self.KEY: rec}}, wikipedia=False)
        self.assertNotIn(self.KEY, cache["photos"])
        self.assertTrue(any("is withheld" in p for p in problems))
        self.assertEqual(cache["notPortraits"], {self.KEY: [upload]})
        self.assertIn(upload, statewide_photos.doubted(cache))

    def test_a_kept_photograph_whose_licence_a_person_doubts_stays_offered(self):
        rec = self.record()
        upload = statewide_photos.official_photos.commons_upload(rec)
        with unittest.mock.patch.dict(overrides.PORTRAIT_LICENCE_DOUBTS,
                                      {upload: ("2026-10-25", "CC0 by a user account")}):
            cache, _ = self.fetch({"photos": {self.KEY: rec}}, wikipedia=False)
        self.assertEqual(cache["licenceDoubts"], {self.KEY: [upload]})
        self.assertIn(upload, statewide_photos.doubted(cache))

    def test_a_race_unread_keeps_its_last_refusals(self):
        for before in ({self.OTHER: [self.BAXTER]}, [self.BAXTER]):
            with self.subTest(form=type(before).__name__):
                cache, _ = self.fetch({"photos": {}, "notPortraits": before}, wikipedia=False)
                self.assertIn(self.BAXTER, statewide_photos.doubted(cache))
                # A race whose article could not be read keeps it too.
                cache, _ = self.fetch({"photos": {}, "notPortraits": before}, wikipedia=True,
                                      wiki=({}, [], {self.OTHER}, {}))
                self.assertIn(self.BAXTER, statewide_photos.doubted(cache))

    def test_a_race_read_lets_its_refusals_go(self):
        for before in ({self.OTHER: [self.BAXTER]}, [self.BAXTER]):
            with self.subTest(form=type(before).__name__):
                cache, _ = self.fetch({"photos": {}, "notPortraits": before}, wikipedia=True,
                                      wiki=({}, [], set(), {self.OTHER: "no-image"}))
                self.assertNotIn(self.BAXTER, statewide_photos.doubted(cache))
                self.assertNotIn("notPortraits", cache)

    def test_an_unread_day_keeps_why_a_race_had_none(self):
        cache, _ = self.fetch({"photos": {}, "misses": {self.OTHER: "not-a-portrait"}},
                              wikipedia=False)
        self.assertEqual(cache["misses"], {self.OTHER: "not-a-portrait"})

    def test_a_court_member_unread_keeps_their_refusals(self):
        from kyc import court_photos, courts as court_module
        roster = "https://courts.example.gov/justices"
        court_module.COURTS["XX"] = {"url": roster}
        try:
            # The roster not read at all: what it refused stands.
            read = {"XX": {"members": ["Pat Doe"]}}
            court_photos.add_justice_photos(read, {}, {"XX": {
                "photoRefused": {"Pat Doe": [REFUSED]}}}, pause=0)
            self.assertIn(REFUSED, court_photos.refused_offered({"courts": read}))
            # Read, but the member's own page did not answer.
            page = '<a href="/doe">Justice Pat Doe</a>'

            def fail(url, **kw):
                raise court_module.CourtsError("timed out")
            read = {"XX": {"members": ["Pat Doe"]}}
            with unittest.mock.patch.object(court_photos, "bio_pages",
                                            return_value={"Pat Doe": roster + "/doe"}):
                court_photos.add_justice_photos(read, {"XX": page}, {"XX": {
                    "photoRefused": {"Pat Doe": [REFUSED]}}}, get=fail, pause=0)
            self.assertEqual(read["XX"].get("photoRefused"), {"Pat Doe": [REFUSED]})
            # Read whole, and offering nothing: the refusal goes.
            read = {"XX": {"members": ["Pat Doe"]}}
            court_photos.add_justice_photos(read, {"XX": "<p>Justices</p>"}, {"XX": {
                "photoRefused": {"Pat Doe": [REFUSED]}}}, pause=0)
            self.assertNotIn(REFUSED, court_photos.refused_offered({"courts": read}))
        finally:
            del court_module.COURTS["XX"]

    def test_a_court_refusal_with_no_photograph_taken_is_recorded(self):
        from kyc import court_photos, courts as court_module
        roster = "https://courts.example.gov/justices"
        url = "https://courts.example.gov/doe.jpg"
        court_module.COURTS["XX"] = {"url": roster}
        try:
            read = {"XX": {"members": ["Pat Doe"]}}
            with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                          {url: ("2026-10-25", "Pat Doe: a drawing")}):
                court_photos.add_justice_photos(
                    read, {"XX": '<img src="/doe.jpg" alt="Justice Pat Doe">'}, {}, pause=0)
        finally:
            del court_module.COURTS["XX"]
        self.assertEqual(read["XX"]["photoRefused"], {"Pat Doe": [url]})

    def test_an_attorney_generals_office_unread_keeps_its_refusals(self):
        old = {"XX": {"name": "Pat Doe", "notPortraits": [REFUSED]}}
        # The office's site did not answer: the row is the association's.
        rows = {"XX": {"name": "Pat Doe", "unconfirmed": True, "unreadable": True}}
        officers.add_ag_photos(rows, {}, old, pause=0)
        self.assertEqual(rows["XX"].get("notPortraits"), [REFUSED])
        # Confirmed, but the pages with the photograph did not answer.
        rows = {"XX": {"name": "Pat Doe"}}
        with unittest.mock.patch.object(officers, "ag_photo", return_value=(None, "unknown")):
            officers.add_ag_photos(rows, {"XX": []}, old, pause=0, get=lambda u: "")
        self.assertEqual(rows["XX"].get("notPortraits"), [REFUSED])
        # Read whole, and offering nothing: the refusal goes.
        rows = {"XX": {"name": "Pat Doe"}}
        with unittest.mock.patch.object(officers, "ag_photo", return_value=(None, "none")):
            officers.add_ag_photos(rows, {"XX": []}, old, pause=0, get=lambda u: "")
        self.assertNotIn("notPortraits", rows["XX"])

    def test_a_judge_unread_keeps_their_refusals_and_a_withheld_kept_file(self):
        judges = {"fjc-100": {"id": "fjc-100", "nid": "100", "name": "Pat Doe"}}
        source = "https://commons.wikimedia.org/wiki/File:Pat_Doe_drawing.jpg"
        upload = judge_links.source_url(source)
        previous = {"100": {"wikidata": "Q1", "portrait": {"source": source, "url": upload}}}
        before = {"notPortraits": {"100": [REFUSED]}}
        report = {}
        # The FJC page was not read this run.
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                      {upload: ("2026-10-25", "Pat Doe: a drawing")}):
            joined, _ = judge_links.join(judges, {}, {}, {}, previous, report=report,
                                         previous_refused=before)
        self.assertNotIn("portrait", joined["100"])
        self.assertEqual(report["notPortraits"], {"100": sorted([REFUSED, upload])})
        # Nobody to read: a previous refusal for a judge the run reached
        # nothing about stays; the flat list a cache wrote before stays too.
        report = {}
        judge_links.join(judges, {}, {}, {}, {}, report=report,
                         previous_refused={"notPortraits": [REFUSED]})
        self.assertEqual(photos.refused_urls(report["notPortraits"]), {REFUSED})

    def test_a_campaign_about_page_unread_keeps_its_refusals(self):
        from kyc import enrich
        old = {"url": "https://doe.example.com/", "safe": True, "notPortraits": [REFUSED]}
        new = {"url": "https://doe.example.com/", "safe": True,
               "portraitUnread": "https://doe.example.com/about"}
        self.assertEqual(enrich._keep(old, new)["notPortraits"], [REFUSED])
        whole = {"url": "https://doe.example.com/", "safe": True}
        self.assertNotIn("notPortraits", enrich._keep(old, whole))

    def test_a_nominee_with_no_record_keeps_the_refusal_met(self):
        from kyc import nominee_photos
        profile = {"id": "H6XX01000", "name": "Pat Doe", "state": "XX", "isCandidate": True}
        key = portraits.profile_key(profile)
        cache = {}
        nominee_photos.record_passed(cache, {key: [REFUSED]}, [profile])
        self.assertEqual(cache[key]["replaces"], [REFUSED])
        self.assertIsNone(cache[key]["url"])
        self.assertEqual(nominee_photos.replaced(cache[key]), [REFUSED])

    def test_a_record_that_only_holds_a_refusal_resolves_nothing(self):
        """The review of PR #159: a filer with no article has no portrait
        record, and a record made only to hold a refusal must not stop
        portraits resolving them once their ballot page links one."""
        from kyc import nominee_photos
        profile = {"id": "H6XX01000", "name": "Jane Filer", "state": "XX",
                   "isCandidate": True, "source": "fec-field"}
        key = portraits.profile_key(profile)
        cache = {}
        nominee_photos.record_passed(cache, {key: [REFUSED]}, [profile])
        later = dict(profile, wikipedia="Jane Filer", wikipediaVia="election-page")
        self.assertFalse(portraits.route_ok(later, cache[key]))
        # What portraits then resolves keeps the refusal, and is a record
        # like any other.
        found = portraits.resolved_over(cache[key], {
            "url": "https://upload.wikimedia.org/x/Jane_Filer.jpg", "via": "wikipedia",
            "title": "Jane Filer", "linked": "Jane Filer", "name": "Jane Filer"})
        self.assertEqual(found["replaces"], [REFUSED])
        self.assertNotIn(nominee_photos.REFUSALS_ONLY, found)
        # A record portraits resolved to nothing stays resolved.
        self.assertTrue(portraits.route_ok(later, {"url": None, "via": "unresolved"}))

    def test_a_profile_resolved_again_keeps_what_another_route_refused(self):
        from kyc import nominee_photos
        old = {"url": REFUSED, "via": nominee_photos.WIKIDATA,
               "replaces": ["https://e.org/older.jpg"]}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            new = portraits.resolved_over(old, {"url": None, "via": "unresolved", "name": "P"})
        self.assertEqual(new["replaces"], sorted([REFUSED, "https://e.org/older.jpg"]))
        # Its own route's refused file goes with the route it re-read: an
        # article the profile no longer links offers it no more.
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            new = portraits.resolved_over({"url": REFUSED, "via": "wikipedia"},
                                          {"url": None, "via": "unresolved", "name": "P"})
        self.assertNotIn("replaces", new)
        # Resolved again to the very file, it replaces nothing new.
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            again = portraits.resolved_over({"url": REFUSED, "via": nominee_photos.WIKIDATA},
                                            {"url": REFUSED})
        self.assertNotIn("replaces", again)

    def test_a_court_members_kept_photograph_a_person_refused_is_recorded(self):
        from kyc import court_photos, courts as court_module
        roster = "https://courts.example.gov/justices"
        court_module.COURTS["XX"] = {"url": roster}

        def fail(url, **kw):
            raise court_module.CourtsError("timed out")
        try:
            read = {"XX": {"members": ["Pat Doe"]}}
            with unittest.mock.patch.object(court_photos, "bio_pages",
                                            return_value={"Pat Doe": roster + "/doe"}), \
                    unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
                court_photos.add_justice_photos(read, {"XX": "<p>Justices</p>"}, {"XX": {
                    "photos": {"Pat Doe": {"photo": REFUSED}}}}, get=fail, pause=0)
        finally:
            del court_module.COURTS["XX"]
        self.assertNotIn("photos", read["XX"])
        self.assertEqual(read["XX"].get("photoRefused"), {"Pat Doe": [REFUSED]})

    def test_an_unreadable_offices_old_photograph_a_person_refused_is_recorded(self):
        rows = {"XX": {"name": "Pat Doe", "unconfirmed": True, "unreadable": True}}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            officers.add_ag_photos(rows, {}, {"XX": {"name": "Pat Doe", "photo": REFUSED}},
                                   pause=0)
        self.assertEqual(rows["XX"].get("notPortraits"), [REFUSED])
        # Another holder's old photograph is not this one's.
        rows = {"XX": {"name": "Lee Roe", "unconfirmed": True, "unreadable": True}}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            officers.add_ag_photos(rows, {}, {"XX": {"name": "Pat Doe", "photo": REFUSED}},
                                   pause=0)
        self.assertNotIn("notPortraits", rows["XX"])

    def campaign(self):
        return {"id": "H6XX01000", "name": "Pat Doe", "state": "XX"}

    def test_a_campaign_about_page_that_concludes_nothing_is_marked(self):
        from kyc import enrich
        about = "https://doe.example.com/about"
        record = {"url": "https://doe.example.com/", "safe": enrich.SAFE}
        with unittest.mock.patch.object(enrich, "about_link", return_value=about), \
                unittest.mock.patch.object(enrich, "fetch", return_value=(about, 503, "")), \
                unittest.mock.patch.object(enrich, "assess", return_value=(None, "503")), \
                unittest.mock.patch.object(enrich, "portrait", return_value=[]), \
                unittest.mock.patch.object(enrich.time, "sleep"):
            enrich.look_for_portrait(record, self.campaign(), enrich.parse_page(""), record["url"],
                                     pause=0)
        self.assertEqual(record.get("portraitUnread"), about)
        old = dict(record, notPortraits=[REFUSED])
        old.pop("portraitUnread")
        self.assertEqual(enrich._keep(old, record)["notPortraits"], [REFUSED])

    def drawn(self, before, about_markup):
        """render_portraits over one site whose home page has no portrait
        and links an About page drawn as *about_markup* (None: not drawn)."""
        from kyc import enrich
        url = "https://doe.example.com/"
        profile = self.campaign()
        cache = {"people": {profile["id"]: {"drawn": before}}}

        def reader(pages):
            code = next(iter(pages))
            if pages[code] == url:
                return {code: "<html>home</html>"}, []
            return ({code: about_markup} if about_markup is not None else {}), []

        def pictures(page, base, who):
            return [(REFUSED, "Pat Doe")] if base.endswith("/about") else []
        with unittest.mock.patch.object(enrich, "render_wanted",
                                        return_value=[(profile, "k", url)]), \
                unittest.mock.patch.object(enrich, "assess", return_value=(enrich.SAFE, "ok")), \
                unittest.mock.patch.object(enrich, "about_link", return_value=url + "about"), \
                unittest.mock.patch.object(enrich, "portrait", side_effect=pictures), \
                unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, TABLE):
            enrich.render_portraits([profile], cache, reader=reader, log=lambda *a: None)
        return cache["people"][profile["id"]]["drawn"]

    def test_a_campaign_about_page_not_drawn_keeps_its_refusals(self):
        before = {"url": "https://doe.example.com/", "safe": True, "notPortraits": [REFUSED]}
        self.assertEqual(self.drawn(before, None).get("notPortraits"), [REFUSED])

    def test_what_a_drawn_about_page_refused_is_recorded(self):
        self.assertEqual(self.drawn(None, "<html>about</html>").get("notPortraits"), [REFUSED])


class TestACommonsPhotographsYear(unittest.TestCase):
    """Tad Jude's (MN) black-and-white legislature portrait is from 1981
    and read as current: every Commons credit says the year its file's own
    page gives, and none where it gives no single one."""

    def test_the_credit_carries_the_files_own_year_only(self):
        self.assertEqual(portraits.commons_credit({"licence": "CC0", "year": 1981})["year"], 1981)
        self.assertNotIn("year", portraits.commons_credit({"licence": "CC0", "year": None}))
        self.assertNotIn("year", portraits.commons_credit({"licence": "CC0"}))

    def test_a_statewide_credit_read_before_years_is_dated_once(self):
        upload = "https://upload.wikimedia.org/wikipedia/commons/1/1d/Portrait_of_Tad_Jude.jpg"
        rec = {"route": "wikipedia", "photo": upload,
               "credit": {"licence": "Public domain", "via": "Wikimedia Commons",
                          "page": "https://commons.wikimedia.org/wiki/File:Portrait_of_Tad_Jude.jpg"}}
        cache = {"photos": {"MN|sos|TAD JUDE": rec}}
        asked = []

        def info_of(urls):
            asked.extend(urls)
            return {u: {"width": 400, "height": 500, "extmetadata": {
                "DateTimeOriginal": {"value": "1981"},
                "LicenseShortName": {"value": "Public domain"}}} for u in urls}
        self.assertEqual(statewide_photos.date_credits(cache, info_of, log=None), 1)
        self.assertEqual(rec["credit"]["year"], 1981)
        self.assertEqual(statewide_photos.date_credits(cache, info_of, log=None), 0)
        self.assertEqual(len(asked), 1)
        # A page that gives no single year is said once and never guessed.
        undated = statewide_photos.dated_credit({"licence": "CC0"}, {"year": None})
        self.assertEqual(undated, {"licence": "CC0", "yearUnstated": True,
                                   "yearForm": portraits.CREDIT_FORM})

    def test_a_credit_dated_by_an_earlier_reading_is_dated_again(self):
        # The third reading took "13 October 2020 (upload date)" as a year.
        rec = {"route": "wikipedia",
               "photo": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Amanda_Edwards.jpg",
               "credit": {"licence": "CC BY 4.0", "via": "Wikimedia Commons", "year": 2020,
                          "page": "https://commons.wikimedia.org/wiki/File:Amanda_Edwards.jpg"}}
        cache = {"photos": {"TX|x|AMANDA EDWARDS": rec}}

        def info_of(urls):
            return {u: {"width": 400, "height": 500, "timestamp": "2023-04-27T03:58:14Z",
                        "extmetadata": {"DateTimeOriginal": {"value": "13 October 2020 (upload date)"},
                                        "LicenseShortName": {"value": "CC BY 4.0"}}} for u in urls}
        self.assertEqual(statewide_photos.date_credits(cache, info_of, log=None), 1)
        self.assertNotIn("year", rec["credit"])
        self.assertTrue(rec["credit"]["yearUnstated"])


class TestAYearIsOnlyOneCommonsStatesPlainly(unittest.TestCase):
    """The PR #139 review: an upload date, an estimate, a span or the upload
    day itself was printed as the year a photograph was taken."""

    def test_an_upload_date_is_no_year(self):
        self.assertIsNone(portraits.year_of("13 October 2020 (upload date)"))
        self.assertIsNone(portraits.year_of("15 September 2006 (original upload date)"))

    def test_an_estimate_is_no_year(self):
        self.assertIsNone(portraits.year_of(
            'circa 2023<div style="display: none;">date QS:P,+2023-00-00T00:00:00Z/9,'
            'P1480,Q5727902</div>'))
        self.assertIsNone(portraits.year_of("circa 1993"))
        self.assertIsNone(portraits.year_of("c. 2000"))
        self.assertIsNone(portraits.year_of("ca. November 2024"))
        self.assertIsNone(portraits.year_of("before 1950"))
        self.assertIsNone(portraits.year_of("1975?"))
        self.assertIsNone(portraits.year_of("2005 or 2006"))
        # The hidden statement alone says so.
        self.assertIsNone(portraits.year_of(
            '1990<div style="display: none;">date QS:P,+1990-00-00T00:00:00Z/9,P1480,Q5727902</div>'))

    def test_a_span_is_no_year_and_a_month_is_a_date(self):
        self.assertIsNone(portraits.year_of("circa 2025-26"))
        self.assertIsNone(portraits.year_of("2025-26"))
        self.assertIsNone(portraits.year_of("2024\u201325"))
        self.assertEqual(portraits.year_of("2017-05"), 2017)
        self.assertEqual(portraits.year_of("2017-05-25 11:50:06"), 2017)

    def test_the_upload_day_is_no_evidence(self):
        self.assertIsNone(portraits.year_of("27 April 2023", uploaded="2023-04-27T03:58:14Z"))
        self.assertIsNone(portraits.year_of("2023-04-27", uploaded="2023-04-27T03:58:14Z"))
        self.assertEqual(portraits.year_of("2023-04-26", uploaded="2023-04-27T03:58:14Z"), 2023)
        info = {"timestamp": "2025-02-03T10:00:00Z",
                "extmetadata": {"DateTimeOriginal": {"value": "3 February 2025"},
                                "LicenseShortName": {"value": "CC BY 4.0"}}}
        self.assertIsNone(portraits.credit_of(info)["year"])

    def test_every_reader_asks_for_the_upload_time(self):
        self.assertIn("timestamp", portraits.IIPROP)

    def test_no_committed_credit_shows_a_year_its_reading_refused(self):
        # Every cache's year was read by the current reading.
        commons = [r for r in portraits.load_cache(ROOT).values()
                   if r.get("url") and portraits.wikimedia_file(r["url"]) and r.get("credit")]
        dated = [r for r in commons if (r["credit"].get("year")
                                        and r["credit"].get("form") != portraits.CREDIT_FORM)]
        self.assertLess(len(dated), 5, [r.get("name") for r in dated])
        for rec in statewide_photos.load_cache(ROOT)["photos"].values():
            if rec.get("route") == "wikipedia" and rec["credit"].get("year"):
                self.assertEqual(rec["credit"].get("yearForm"), portraits.CREDIT_FORM)

    def test_the_committed_credits_are_dated(self):
        cache = statewide_photos.load_cache(ROOT)
        for key, rec in cache["photos"].items():
            if rec.get("route") == "wikipedia":
                self.assertTrue({"year", "yearUnstated"} & set(rec["credit"]), key)
        jude = [r for k, r in cache["photos"].items() if "TAD JUDE" in k.upper()]
        self.assertEqual([r["credit"]["year"] for r in jude], [1981])
        # A file Commons no longer describes (Todd Achilles's was deleted)
        # keeps its last credit until a read answers (rule 8): a few, never
        # the many read before credits carried a year.
        commons = [r for r in portraits.load_cache(ROOT).values()
                   if r.get("url") and portraits.wikimedia_file(r["url"]) and r.get("credit")]
        stale = [r.get("name") for r in commons if r["credit"].get("form") != portraits.CREDIT_FORM]
        self.assertLess(len(stale), len(commons) / 50, stale)


class TestARefusalPromotesNothingUnseen(unittest.TestCase):
    """The PR #139 review: refusing James Talarico's Commons crop promoted
    his campaign's photograph of him helping a child in a classroom, which
    nobody had looked at."""

    CROP = "https://upload.wikimedia.org/wikipedia/commons/7/70/Pat_Doe_(cropped).jpg"
    CAMPAIGN = "https://patdoe.example/wp-content/uploads/pat-classroom.webp"

    def profile(self, shown, source):
        return {"id": "CAND_1", "name": "Pat Doe", "state": "TX", "officeLabel": "Senate (TX)",
                "isCandidate": True, "source": "curated", "chamber": "Senate (Candidate)",
                "photos": [shown, "placeholder"], "photoSource": source}

    def cache_for(self, profile, record):
        return {portraits.profile_key(profile): record}

    def test_a_photograph_promoted_by_a_refusal_is_named_until_seen(self):
        p = self.profile(self.CAMPAIGN, "campaign-site")
        cache = self.cache_for(p, {"via": "election-page", "url": self.CROP})
        table = {self.CROP: ("2026-10-25", "Pat Doe: a person at the right edge")}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, table):
            issues = validate.check_refusal_fallbacks([p], cache)
            self.assertEqual([i.code for i in issues], ["portrait-fallback-unseen"])
            self.assertIn(self.CAMPAIGN, issues[0].detail[0])
            # Looked at, and the person alone: said once, and quiet.
            with unittest.mock.patch.dict(overrides.SEEN_AFTER_A_REFUSAL,
                                          {self.CAMPAIGN: ("2026-10-25", "Pat Doe alone")}):
                self.assertEqual(validate.check_refusal_fallbacks([p], cache), [])
        # Nothing refused: the campaign's photograph is the first route's.
        self.assertEqual(validate.check_refusal_fallbacks([p], cache), [])

    def test_a_studio_route_or_the_silhouette_needs_no_look(self):
        table = {self.CROP: ("2026-10-25", "Pat Doe: a person at the right edge")}
        house = "https://house.texas.gov/images/members/1.jpg"
        for shown, source in ((house, "state-legislature"), ("placeholder", None)):
            p = self.profile(shown, source)
            record = {"via": "state-legislature", "url": house, "replaces": [self.CROP]}
            with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, table):
                self.assertEqual(validate.check_refusal_fallbacks([p], self.cache_for(p, record)),
                                 [])

    def test_a_route_asked_again_keeps_what_it_stands_in_for(self):
        from kyc import nominee_photos
        uncut = "https://upload.wikimedia.org/wikipedia/commons/8/8b/Pat_Doe.jpg"
        record = {"via": "wikidata-fec", "url": uncut + "/330px", "replaces": [self.CROP]}
        self.assertEqual(nominee_photos.replaced(record), [self.CROP])
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                      {self.CROP: ("2026-10-25", "x")}):
            p = self.profile(record["url"], "wikidata-fec")
            issues = validate.check_refusal_fallbacks([p], self.cache_for(p, record))
            self.assertEqual([i.code for i in issues], ["portrait-fallback-unseen"])
        refused = {"via": "election-page", "url": self.CROP}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {self.CROP: ("2026-10-25", "x")}):
            self.assertEqual(nominee_photos.replaced(refused), [self.CROP])
        self.assertEqual(nominee_photos.replaced(refused), [])

    def test_the_committed_build_promotes_nothing_unseen(self):
        # Every profile's photograph that came forward after a refusal was
        # looked at (the review's Talarico): the committed caches and data
        # say nothing is waiting.
        self.assertTrue(all(len(v) == 2 and v[0] and v[1]
                            for v in overrides.SEEN_AFTER_A_REFUSAL.values()))


class TestAPersonsChoice(unittest.TestCase):
    """overrides.CANDIDATE_PHOTOS after the background-people sweep: a
    person on the ballot is not left a silhouette where a page tied to them
    shows them alone (Ken Paxton's office photograph). The entry is keyed on
    the profile's id, is the portrait cache's `curated` route, stands ahead
    of the automatic routes, and keeps what the person refused counted."""

    CROP = "https://upload.wikimedia.org/wikipedia/commons/0/06/Pat_Doe_(cropped).jpg"
    OFFICE = "https://www.example.gov/images/pat_doe_bio.jpg"
    ENTRY = {"url": OFFICE, "page": "https://www.example.gov/about",
             "words": "Attorney General Pat Doe", "by": "Office of the Attorney General",
             "tie": "she holds the office", "seen": "her alone, a studio portrait",
             "read": "2026-10-25"}

    def profile(self, pid="CAND_1"):
        return {"id": pid, "name": "Pat Doe", "state": "TX", "isCandidate": True,
                "chamber": "Senate (Candidate)", "photos": ["placeholder"]}

    def test_the_entry_stands_ahead_of_a_refused_article_and_keeps_the_refusal(self):
        p = self.profile()
        key = portraits.profile_key(p)
        cache = {key: {"via": "wikipedia", "url": self.CROP, "name": "Pat Doe"}}
        with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": self.ENTRY}), \
                unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                         {self.CROP: ("2026-10-25", "a crowd behind her")}):
            self.assertEqual(portraits.sync_curated([p], cache), 1)
            record = cache[key]
            self.assertEqual((record["via"], record["url"]), ("curated", self.OFFICE))
            self.assertEqual(record["replaces"], [self.CROP])
            self.assertEqual(record["credit"], {"by": "Office of the Attorney General",
                                                "page": "https://www.example.gov/about"})
            record.update(bytes=9622, width=262, height=394)
            # Read again, it keeps what was measured.
            self.assertEqual(portraits.sync_curated([p], cache), 0)
            self.assertEqual(portraits.apply_cache([p], cache), 1)
            self.assertEqual(p["photos"][0], self.OFFICE)
            self.assertEqual(p["photoSource"], "curated")
            self.assertEqual(p["photoCredit"]["by"], "Office of the Attorney General")
            self.assertEqual(validate.check_photo_evidence([p], cache), [])
        # Without the entry the record stands for nobody (route_ok).
        q = self.profile()
        self.assertFalse(portraits.route_ok(q, cache[key]))
        self.assertEqual(portraits.apply_cache([q], cache), 0)
        self.assertEqual(q["photos"], ["placeholder"])

    def test_it_is_one_profile_by_id_never_a_namesake(self):
        p, namesake = self.profile("CAND_1"), self.profile("FEC_H6TX01001")
        with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": self.ENTRY}):
            cache = {}
            portraits.sync_curated([p], cache)
            self.assertFalse(portraits.route_ok(namesake, cache[portraits.profile_key(p)]))

    def test_a_commons_choice_draws_a_standard_size_with_its_read_credit(self):
        url = "https://upload.wikimedia.org/wikipedia/commons/3/3d/Pat_Doe_at_the_White_House.jpg"
        entry = dict(self.ENTRY, url=url, by="",
                     page="https://commons.wikimedia.org/wiki/File:Pat_Doe_at_the_White_House.jpg")
        p = self.profile()
        with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": entry}):
            self.assertEqual(photos.curated_problems(entry), [])
            cache = {}
            portraits.sync_curated([p], cache)
            record = cache[portraits.profile_key(p)]
            self.assertNotIn("credit", record)
            # Not credited yet (Commons not read): withheld, never uncredited.
            self.assertEqual(portraits.apply_cache([p], cache), 0)
            record["set"] = portraits.thumb_set(url, 1079)
            record["credit"] = {"by": "@whitehouse (The White House)",
                                "licence": "Public domain", "form": portraits.CREDIT_FORM,
                                "file": entry["page"]}
            self.assertEqual(portraits.apply_cache([p], cache), 1)
            self.assertEqual(p["photos"][0], record["set"][-1][1])
            self.assertIn("/500px-", p["photos"][0])
            self.assertEqual(p["photoCredit"]["licence"], "Public domain")

    def test_validate_names_an_entry_refused_unshown_or_unevidenced(self):
        p = self.profile()
        table = overrides.CANDIDATE_PHOTOS
        with unittest.mock.patch.dict(table, {"CAND_1": self.ENTRY}, clear=True):
            self.assertEqual(validate.check_curated_photos([p]), [])
            issues = validate.check_photo_evidence([p], {})
            self.assertIn("not shown", issues[0].detail[0])
            with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT,
                                          {self.OFFICE: ("2026-10-25", "x")}):
                self.assertEqual([i.code for i in validate.check_curated_photos([p])],
                                 ["photo-curated-unevidenced"])
        with unittest.mock.patch.dict(table, {"CAND_1": dict(self.ENTRY, tie="")}, clear=True):
            self.assertEqual([i.code for i in validate.check_curated_photos([p])],
                             ["photo-curated-unevidenced"])
        with unittest.mock.patch.dict(table, {"CAND_404": self.ENTRY}, clear=True):
            self.assertEqual([i.code for i in validate.check_curated_photos([p])],
                             ["stale-photo-override"])

    def test_a_refusal_is_kept_by_the_address_its_entry_names(self):
        # Jacqui Irwin's refused Commons file stood in her new record as the
        # 960px thumbnail, which no NOT_A_PORTRAIT entry names: the entry's
        # key is the file's upload address, from its description page.
        from kyc import nominee_photos
        page = "https://commons.wikimedia.org/wiki/File:Pat_Doe_(cropped).jpg"
        upload = judge_links.source_url(page)
        thumb = upload.replace("/commons/", "/commons/thumb/") + "/960px-Pat_Doe_(cropped).jpg"
        record = {"via": "wikipedia", "url": thumb, "credit": {"file": page}}
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {upload: ("2026-10-25", "x")}):
            self.assertEqual(nominee_photos.replaced(record), [upload])
        # A record refused by its own address still names that address.
        with unittest.mock.patch.dict(overrides.NOT_A_PORTRAIT, {thumb: ("2026-10-25", "x")}):
            self.assertEqual(nominee_photos.replaced(record), [thumb])

    def test_the_committed_entries_are_complete(self):
        from kyc import photocopies, statelegs
        manifest = photocopies.load(ROOT)
        roster = statelegs.load_cache(ROOT)
        for pid, entry in overrides.CANDIDATE_PHOTOS.items():
            self.assertEqual(photos.curated_problems(entry), [], pid)
            self.assertEqual(photos.curated_problems(entry, manifest), [], pid)
            self.assertFalse(photos.refused(entry["url"]), pid)
            if roster:
                self.assertTrue(photos.curated_seated(entry, roster), pid)
        # A committed hosted choice is on disk as its manifest entry gives it,
        # listed for that very profile (photocopies.problems checks the bytes).
        for pid, entry in overrides.CANDIDATE_PHOTOS.items():
            if photocopies.is_hosted(entry["url"]):
                listed = photocopies.hosted_entry(manifest, entry["url"])
                self.assertIn(f"person:{pid}", listed["for"], pid)
                self.assertEqual(listed["by"], entry["by"], pid)

    # Brent Taylor's Tennessee Senate portrait is drawn on its page only as
    # a data: image, so it is hosted here unmodified (the PR #141 review).
    HOSTED = "photos/0123456789abcdef0123.png"
    PAGE = "https://www.example.gov/member?district=S31"

    def hosted(self):
        entry = dict(self.ENTRY, url=self.HOSTED, page=self.PAGE, by="Example General Assembly")
        manifest = {"originals": {}, "hosted": {self.HOSTED[len("photos/"):]: {
            "method": "unmodified", "page": self.PAGE, "from": self.PAGE, "bytes": 286711,
            "width": 400, "height": 400, "sha256": "0123456789abcdef0123" + "0" * 44,
            "read": "2026-10-25", "by": "Example General Assembly",
            "for": ["person:CAND_1"]}}}
        return entry, manifest

    def test_a_hosted_choice_is_weighed_from_its_manifest_and_shared_on_the_host(self):
        from kyc import share
        entry, manifest = self.hosted()
        self.assertEqual(photos.curated_problems(entry, manifest), [])
        self.assertIn(f"{self.HOSTED} is not in the manifest's hosted files",
                      photos.curated_problems(entry, {"originals": {}, "hosted": {}}))
        other = {"originals": {}, "hosted": {k: dict(v, page="https://www.example.gov/x")
                                             for k, v in manifest["hosted"].items()}}
        self.assertIn(f"the manifest's {self.HOSTED} was read from another page",
                      photos.curated_problems(entry, other))
        # Neither a name-built address nor a plain path outside photos/.
        self.assertIn("an address that is not https",
                      photos.curated_problems(dict(entry, url="img/taylor.png")))
        p = self.profile()
        with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": entry},
                                      clear=True):
            cache = {}
            portraits.sync_curated([p], cache, manifest)
            record = cache[portraits.profile_key(p)]
            self.assertEqual((record["bytes"], record["width"], record["height"]),
                             (286711, 400, 400))
            # Never fetched: measure_all leaves an address from the site's root.
            with unittest.mock.patch.object(portraits, "measure",
                                            side_effect=AssertionError("fetched")):
                portraits.measure_all({"k": {k: v for k, v in record.items() if k != "bytes"}},
                                      log=lambda *_: None)
            self.assertEqual(portraits.apply_cache([p], cache), 1)
            self.assertEqual(p["photos"][0], self.HOSTED)
            self.assertEqual(p["photoCredit"], {"by": "Example General Assembly",
                                                "page": self.PAGE})
            self.assertEqual(validate.check_photo_evidence([p], cache), [])
            self.assertEqual(validate.check_curated_photos([p], None, manifest), [])
            self.assertEqual(share.og_photo(p, "candidates.example.org"),
                             f"https://candidates.example.org/{self.HOSTED}")
            self.assertIsNone(share.og_photo(p))

    def test_a_guide_read_keeps_a_hosted_choice(self):
        # guide_photos.fetch rewrites the manifest's hosted files from what
        # the guides gave; a file a person chose is not its to remove.
        import json
        import tempfile
        from kyc import guide_photos, photocopies
        entry, manifest = self.hosted()
        orphan = "fedcba9876543210fedc.jpg"
        manifest["hosted"][orphan] = dict(manifest["hosted"][self.HOSTED[7:]],
                                          **{"for": ["person:gone"]})
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, photocopies.PHOTOS_DIR))
            for name in (self.HOSTED[7:], orphan):
                with open(os.path.join(root, photocopies.PHOTOS_DIR, name), "wb") as handle:
                    handle.write(b"\x89PNG")
            photocopies.save(manifest, root)

            def no_network(url, *a, **k):
                raise AssertionError(f"fetched {url}")

            with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": entry},
                                          clear=True):
                guide_photos.fetch(root, profiles=[], stategov={}, getter=no_network,
                                   log=lambda *_: None)
            with open(os.path.join(root, photocopies.CACHE_PATH), encoding="utf-8") as handle:
                after = json.load(handle)["hosted"]
            self.assertEqual(after, {self.HOSTED[7:]: manifest["hosted"][self.HOSTED[7:]]})
            self.assertEqual(os.listdir(os.path.join(root, photocopies.PHOTOS_DIR)),
                             [self.HOSTED[7:]])

    # Pat Moore's file is the Louisiana House's "rep17.jpg", which shows
    # whoever holds District 17 (the PR #141 review).
    SEAT = {"state": "LA", "chamber": "lower", "district": "17",
            "legislator": "ocd-person/1", "name": "Pat Doe"}

    def roster(self, who="ocd-person/1", name="Pat Doe"):
        return {"states": {"LA": [{"id": who, "name": name, "chamber": "lower",
                                   "district": "17", "state": "LA"}]}}

    def test_a_seat_keyed_choice_stands_only_while_its_member_holds_the_seat(self):
        entry = dict(self.ENTRY, seat=self.SEAT)
        self.assertEqual(photos.curated_problems(entry), [])
        self.assertIn("a seat that does not name its state, chamber, district and member",
                      photos.curated_problems(dict(entry, seat={"state": "LA"})))
        p = self.profile()
        with unittest.mock.patch.dict(overrides.CANDIDATE_PHOTOS, {"CAND_1": entry},
                                      clear=True):
            cache = {}
            portraits.sync_curated([p], cache)
            record = cache[portraits.profile_key(p)]
            record.update(bytes=9622, width=262, height=394)
            seated, successor = self.roster(), self.roster("ocd-person/2", "Lee Roe")
            self.assertTrue(portraits.route_ok(p, record, seated))
            self.assertEqual(validate.check_curated_photos([p], seated), [])
            # A successor in the seat: the file now shows them, so it is
            # withheld and named, not reported as merely unread.
            self.assertFalse(portraits.route_ok(p, record, successor))
            q = self.profile()
            self.assertEqual(portraits.apply_cache([q], cache, successor), 0)
            self.assertEqual(q["photos"], ["placeholder"])
            self.assertEqual([i.code for i in validate.check_curated_photos([q], successor)],
                             ["photo-curated-unseated"])
            self.assertEqual(validate.check_photo_evidence([q], cache, legislators=successor),
                             [])
            # Without a roster (a test, a missing cache) nothing is decided.
            self.assertTrue(portraits.route_ok(p, record))


if __name__ == "__main__":
    unittest.main()
