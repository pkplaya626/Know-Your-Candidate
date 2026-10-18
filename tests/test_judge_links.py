"""Judges' portraits and Wikipedia links through the FJC id on Wikidata
(FEDERAL-04, FEDERAL-05: kyc/judge_links.py), and the territorial courts'
judges from the courts' own sites (FEDERAL-06: kyc/territorial_courts.py).

The court fixtures are the shape of each court's page as read on
2026-10-17, cut down to what the recipes read."""

import json
import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import federal_build, judge_links as jl, territorial_courts as tc  # noqa: E402

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")


def fixture(name):
    with open(os.path.join(HERE, "fixtures", "courts", name), encoding="utf-8") as handle:
        return handle.read()


def entity(qid, slug, label="Ann Example", images=(), article=None, lang="en", born="1960"):
    out = {"id": qid, "labels": {lang: {"value": label}} if label else {},
           "claims": {"P2736": [{"mainsnak": {"datavalue": {"value": slug}}, "rank": "normal"}],
                      "P569": [{"mainsnak": {"datavalue": {"value": {"time": f"+{born}-05-01T00:00:00Z"}}},
                                "rank": "normal"}] if born else [],
                      "P18": [{"mainsnak": {"datavalue": {"value": i}}, "rank": "normal"}
                              for i in images]},
           "sitelinks": {"enwiki": {"title": article}} if article else {}}
    return out


def wd(*entities):
    return jl.read_entities({"entities": {e["id"]: e for e in entities}})


JUDGE = {"id": "fjc-100", "name": "Ann B. Example", "sortName": "Example, Ann",
         "born": {"city": "Newark", "state": "NJ", "year": "1960"}}


class TestTheChainOfIds(unittest.TestCase):
    def test_the_slug_is_the_pages_own_canonical_address(self):
        page = ('<link rel="canonical" href="https://www.fjc.gov/history/judges/neals-julien-xavier" />'
                '<link rel="shortlink" href="https://www.fjc.gov/node/10226111" />')
        self.assertEqual(jl.slug_of(page), "neals-julien-xavier")
        self.assertIsNone(jl.slug_of("<html>Request Rejected</html>"))

    def test_a_page_not_read_is_tried_again_and_never_guessed(self):
        pages = {"https://www.fjc.gov/node/1": '<link rel="canonical" href="https://www.fjc.gov/history/judges/a-b" />'}

        def read(url):
            if url not in pages:
                raise OSError("timed out")
            return pages[url]

        slugs, unread = jl.read_slugs({"1", "2"}, read=read, log=None)
        self.assertEqual((slugs, unread), ({"1": "a-b"}, 1))

    def test_the_commons_address_is_computed_from_the_files_name(self):
        url = jl.commons_url("http://commons.wikimedia.org/wiki/Special:FilePath/Julien%20Neals.jpg")
        self.assertTrue(url.startswith("https://upload.wikimedia.org/wikipedia/commons/"))
        self.assertTrue(url.endswith("/Julien_Neals.jpg"))
        self.assertIsNone(jl.commons_url("https://example.org/Julien_Neals.jpg"))

    def test_the_listing_is_completed_by_an_exact_lookup(self):
        # The search index's paging missed one sitting judge's item: it is
        # looked up by its own id, never by name.
        many = [entity(f"Q{i}", f"slug-{i}") for i in range(1, 1101)]
        late = entity("Q9999", "late-slug", label="Ann Example")
        asked = []

        def read(url):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            asked.append(query)
            if query.get("list") == "search":
                if query["srsearch"] == "haswbstatement:P2736":
                    return json.dumps({"query": {"search": [{"title": e["id"]} for e in many],
                                                 "searchinfo": {"totalhits": 1101}}})
                self.assertEqual(query["srsearch"], 'haswbstatement:"P2736=late-slug"')
                return json.dumps({"query": {"search": [{"title": "Q9999"}]}})
            ids = query["ids"].split("|")
            pool = {e["id"]: e for e in many + [late]}
            return json.dumps({"entities": {i: pool[i] for i in ids}})

        found = jl.fetch_wikidata(read, wanted={"slug-5", "late-slug"})
        self.assertIn("late-slug", found)
        self.assertEqual(list(found["late-slug"]), ["Q9999"])

    def test_a_short_listing_is_a_failure_not_a_finding(self):
        def read(url):
            if "list=search" in url:
                return json.dumps({"query": {"search": [{"title": "Q1"}]}})
            return json.dumps({"entities": {"Q1": entity("Q1", "a")}})

        with self.assertRaises(jl.JudgeLinksError):
            jl.fetch_wikidata(read)


class TestTheJoin(unittest.TestCase):
    IMAGE = "http://commons.wikimedia.org/wiki/Special:FilePath/Ann%20Example.jpg"

    CREDIT = {"by": "Gage Skidmore", "licence": "CC BY-SA 3.0",
              "licenceUrl": "https://creativecommons.org/licenses/by-sa/3.0", "nonFree": False}

    def join(self, *entities, size=(400, 500), credit=CREDIT):
        url = jl.commons_url(self.IMAGE)
        return jl.join({"fjc-100": JUDGE}, {"100": "example-ann"}, wd(*entities), {url: size},
                       credits={url: credit})

    def test_an_item_carrying_the_id_gives_its_article_and_portrait(self):
        joined, problems = self.join(entity("Q1", "example-ann", images=[self.IMAGE.rsplit("/", 1)[1]
                                                                        .replace("%20", " ")],
                                            article="Ann Example"))
        self.assertEqual(problems, [])
        self.assertEqual(joined["100"]["wikipedia"], "Ann Example")
        self.assertEqual(joined["100"]["wikidata"], "Q1")
        portrait = joined["100"]["portrait"]
        # Rule 42: only Wikimedia's sizes of that one file.
        self.assertTrue(all("Ann_Example.jpg" in u for _w, u in portrait["set"]))
        self.assertEqual(portrait["credit"], "Wikimedia Commons")
        # Rule 87: with its author and licence, as the file's page gives them.
        self.assertEqual((portrait["by"], portrait["licence"]), ("Gage Skidmore", "CC BY-SA 3.0"))
        self.assertTrue(portrait["licenceUrl"].startswith("https://creativecommons.org/"))

    def test_a_file_with_no_licence_or_not_free_is_not_shown(self):
        name = "Ann Example.jpg"
        for credit, said in ((None, "no licence"), ({"by": "X", "licence": None}, "no licence"),
                             (dict(self.CREDIT, nonFree=True), "not a free file")):
            joined, problems = self.join(entity("Q1", "example-ann", images=[name]), credit=credit)
            self.assertNotIn("portrait", joined["100"])
            self.assertIn(said, problems[0])

    def test_portraits_read_before_licences_were_get_them(self):
        good, _ = self.join(entity("Q1", "example-ann", images=["Ann Example.jpg"]))
        portrait = {k: v for k, v in good["100"]["portrait"].items()
                    if k not in ("by", "licence", "licenceUrl")}
        info = {"width": 400, "height": 500, "extmetadata": {
            "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:G">Gage Skidmore</a>'},
            "LicenseShortName": {"value": "CC BY-SA 3.0"}}}
        cache = {"judges": {"100": {"portrait": dict(portrait)}, "101": {"portrait": dict(portrait)}}}
        asked = []

        def info_of(urls):
            asked.extend(urls)
            return {u: info for u in urls}
        self.assertEqual(jl.credit_portraits(cache, info_of, log=None), (2, 0))
        self.assertEqual(cache["judges"]["100"]["portrait"]["by"], "Gage Skidmore")
        self.assertEqual(len(asked), 2)
        self.assertEqual(jl.credit_portraits(cache, info_of, log=None), (0, 0))   # once
        # A fair-use file is withdrawn and said.
        cache = {"judges": {"100": {"portrait": dict(portrait)}}}
        nonfree = dict(info, extmetadata=dict(info["extmetadata"], NonFree={"value": "true"}))
        self.assertEqual(jl.credit_portraits(cache, lambda urls: {u: nonfree for u in urls},
                                             log=None), (0, 1))
        self.assertNotIn("portrait", cache["judges"]["100"])
        self.assertTrue(cache["problems"])

    def test_a_credit_of_the_first_reading_is_read_again_and_cleaned(self):
        """Six judges read "Unknown author Unknown author" (a hidden span),
        Judge Forrest an uploader's three-line sentence, and Judge Moore's
        CC BY-SA file no author at all."""
        good, _ = self.join(entity("Q1", "example-ann", images=["Ann Example.jpg"]))
        old = dict(good["100"]["portrait"], by="Unknown author Unknown author")
        old.pop("creditForm", None)
        unknown = {"width": 400, "height": 500, "extmetadata": {
            "Artist": {"value": 'Unknown author<span style="display: none;">Unknown author'
                                '</span>'},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "AttributionRequired": {"value": "true"}}}
        cache = {"judges": {"100": {"portrait": old}}}
        self.assertEqual(jl.credit_portraits(cache, lambda urls: {u: unknown for u in urls},
                                             log=None), (1, 0))
        portrait = cache["judges"]["100"]["portrait"]
        self.assertNotIn("by", portrait)
        self.assertTrue(portrait["authorUnrecorded"])
        self.assertEqual(portrait["licence"], "CC BY-SA 4.0")
        self.assertEqual(jl.credit_portraits(cache, lambda urls: {u: unknown for u in urls},
                                             log=None), (0, 0))   # once per form

    def test_two_items_for_one_id_name_nobody(self):
        joined, problems = self.join(entity("Q1", "example-ann"), entity("Q2", "example-ann"))
        self.assertEqual(joined, {})
        self.assertTrue(problems)

    def test_an_item_without_the_surname_is_refused(self):
        joined, problems = self.join(entity("Q1", "example-ann", label="Somebody Else",
                                            article="Somebody Else"))
        self.assertEqual(joined, {})
        self.assertIn("labelled", problems[0])

    def test_an_id_on_someone_elses_item_is_refused_by_the_year_of_birth(self):
        # Wikidata carried Judge Robert H. Whaley's FJC id (born 1943) on
        # the basketball player Robert Whaley (born 1982): same surname,
        # his photograph and his article. The year of birth refuses it.
        joined, problems = self.join(entity("Q1", "example-ann", born="1982",
                                            article="Ann Example"))
        self.assertEqual(joined, {})
        self.assertIn("1982", problems[0])
        joined, problems = self.join(entity("Q1", "example-ann", born=None, article="Ann Example"))
        self.assertEqual(joined, {})
        self.assertIn("no year of birth", problems[0])

    def test_the_committed_links_never_put_the_basketball_player_on_the_judge(self):
        cache = jl.load_cache(ROOT) or {}
        whaley = (cache.get("judges") or {}).get("1389651") or {}
        self.assertNotEqual(whaley.get("wikidata"), "Q3938468")
        self.assertNotIn("portrait", whaley)

    def test_a_multilingual_label_counts(self):
        joined, _ = self.join(entity("Q1", "example-ann", label="Ann Example", lang="mul",
                                     article="Ann Example"))
        self.assertEqual(joined["100"]["wikipedia"], "Ann Example")

    def test_an_article_not_about_them_is_not_linked(self):
        joined, problems = self.join(entity("Q1", "example-ann", article="Protests in 2026"))
        self.assertNotIn("wikipedia", joined["100"])
        self.assertTrue(problems)

    def test_a_wide_frame_or_two_images_is_no_portrait(self):
        name = "Ann Example.jpg"
        wide, problems = self.join(entity("Q1", "example-ann", images=[name]), size=(1280, 720))
        self.assertNotIn("portrait", wide["100"])
        self.assertIn("wider than a portrait", problems[0])
        square, _ = self.join(entity("Q1", "example-ann", images=[name]), size=(2429, 2227))
        self.assertIn("portrait", square["100"])
        two, problems = self.join(entity("Q1", "example-ann", images=[name, "Other.jpg"]))
        self.assertNotIn("portrait", two["100"])

    def test_a_size_not_read_keeps_the_last_portrait_of_that_file(self):
        # Rule 8: one 429 from Commons' imageinfo used to drop up to fifty
        # working portraits until the next good run.
        name = "Ann Example.jpg"
        good, _ = self.join(entity("Q1", "example-ann", images=[name]))
        last = {"100": good["100"]}
        joined, problems = jl.join({"fjc-100": JUDGE}, {"100": "example-ann"},
                                   wd(entity("Q1", "example-ann", images=[name])), {}, last)
        self.assertEqual(joined["100"]["portrait"], good["100"]["portrait"])
        self.assertIn("last portrait read is kept", problems[0])
        # Not a portrait of another file: the item's image changed, so the
        # old one is not kept.
        other, problems = jl.join({"fjc-100": JUDGE}, {"100": "example-ann"},
                                  wd(entity("Q1", "example-ann", images=["Ann Example 2.jpg"])), {}, last)
        self.assertNotIn("portrait", other["100"])
        self.assertIn("not shown", problems[0])
        # And without a last read, nothing is shown.
        none, _ = jl.join({"fjc-100": JUDGE}, {"100": "example-ann"},
                          wd(entity("Q1", "example-ann", images=[name])), {})
        self.assertNotIn("portrait", none["100"])

    def test_a_page_not_read_keeps_the_last_entry(self):
        last = {"100": {"wikidata": "Q1", "wikipedia": "Ann Example"}}
        joined, _ = jl.join({"fjc-100": JUDGE}, {}, {}, {}, last)
        self.assertEqual(joined, last)

    def test_a_refresh_whose_sizes_fail_keeps_the_portraits(self):
        import tempfile
        name = "Ann Example.jpg"
        good, _ = self.join(entity("Q1", "example-ann", images=[name]))
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, os.path.dirname(jl.CACHE_PATH)))
            jl.save_cache({"slugs": {"100": "example-ann"}, "judges": {"100": good["100"]}}, root)
            original = jl.fetch_wikidata
            jl.fetch_wikidata = lambda *a, **k: wd(entity("Q1", "example-ann", images=[name]))
            try:
                cache = jl.refresh({"judges": {"fjc-100": JUDGE}}, root, read=lambda url: "",
                                   sizes_of=lambda urls: {}, log=None)
            finally:
                jl.fetch_wikidata = original
        self.assertEqual(cache["judges"]["100"]["portrait"], good["100"]["portrait"])

    def test_a_judge_without_an_id_on_wikidata_has_nothing(self):
        joined, problems = jl.join({"fjc-100": JUDGE}, {}, {}, {})
        self.assertEqual((joined, problems), ({}, []))

    def test_the_committed_links_hold_only_what_passed(self):
        cache = jl.load_cache(ROOT)
        if not cache or not cache.get("judges"):
            self.skipTest("no judge links committed")
        for nid, entry in cache["judges"].items():
            self.assertRegex(entry["wikidata"], r"^Q\d+$")
            for _w, url in (entry.get("portrait") or {}).get("set") or []:
                self.assertTrue(url.startswith("https://upload.wikimedia.org/"), (nid, url))


class TestTheTerritorialCourts(unittest.TestCase):
    def test_guams_officers_page(self):
        judges = tc.read_lines(fixture("territorial_gu.html"))
        # The magistrate judge, a script, the menu and a comment are not judges.
        self.assertEqual(judges, [{"name": "Frances Tydingco-Gatewood", "title": "Chief Judge",
                                   "chief": True}])

    def test_the_northern_mariana_islands_banner(self):
        judges = tc.read_banner(fixture("territorial_mp.html"))
        self.assertEqual([j["name"] for j in judges], ["Ramona V. Manglona"])
        self.assertTrue(judges[0]["chief"])

    def test_the_virgin_islands_judges_own_pages(self):
        pages = {"https://www.vid.uscourts.gov/judges-info": fixture("territorial_vi_list.html")}
        for slug in ("robert-molloy", "evan-rikhye", "emile-henderson-iii"):
            pages[f"https://www.vid.uscourts.gov/content/honorable-{slug}"] = \
                fixture(f"territorial_vi_{slug}.html")
        judges = tc.read_court("vi", read=pages.__getitem__)
        self.assertEqual([(j["name"], j["chief"]) for j in judges],
                         [("Robert A. Molloy", True), ("Evan Rikhye", False)])

    def test_more_judges_than_seats_or_two_chiefs_is_refused(self):
        chief = {"name": "A", "title": "Chief Judge", "chief": True}
        with self.assertRaises(tc.TerritorialCourtError):
            tc.check("gu", [chief, {"name": "B", "title": "District Judge", "chief": False}])
        with self.assertRaises(tc.TerritorialCourtError):
            tc.check("vi", [chief, dict(chief, name="B")])

    def test_a_page_not_read_keeps_the_last_roster(self):
        def read(url):
            raise tc.TerritorialCourtError(f"could not fetch {url}")

        before = {"gu": {"judges": [{"name": "A", "title": "Chief Judge", "chief": True}],
                         "read": "2026-10-01", "source": "x", "seats": 1, "statute": "s"}}
        out, problems = tc.fetch(before, read=read)
        self.assertEqual(out["gu"], before["gu"])
        self.assertEqual(out["mp"], {"unread": True, "source": tc.COURTS["mp"]["url"]})
        self.assertEqual(len(problems), 3)

    def test_the_built_pages_carry_the_courts_own_list(self):
        payload, courts, _search, _ = federal_build.build(ROOT)
        for cid in tc.COURTS:
            court = next(c for c in payload["courts"] if c["id"] == cid)
            self.assertFalse(court["listed"])
            own = courts[cid].get("courtList")
            if own and not own.get("unread"):
                self.assertLessEqual(len(own["judges"]), own["seats"])
                self.assertEqual(court["courtListed"]["judges"], len(own["judges"]))
            # Never a record to open: they are not in the FJC's directory.
            self.assertEqual(courts[cid]["judges"], [])


class TestAppointers(unittest.TestCase):
    """FEDERAL-22: a court's active judges by appointing President."""

    def test_counted_over_the_active_judges_earliest_first(self):
        judges = {
            "a": {"seats": [{"court": "x", "appointedBy": "Barack Obama", "commissioned": "2011-01-01",
                             "seniorSince": None}]},
            "b": {"seats": [{"court": "x", "appointedBy": "George W. Bush", "commissioned": "2003-01-01",
                             "seniorSince": None}]},
            "c": {"seats": [{"court": "x", "appointedBy": "Barack Obama", "commissioned": "2014-01-01",
                             "seniorSince": None}]},
            "d": {"seats": [{"court": "x", "appointedBy": "Bill Clinton", "commissioned": "1995-01-01",
                             "seniorSince": "2015-01-01"}]},
            "e": {"seats": [{"court": "x", "appointedBy": "Donald J. Trump", "commissioned": "2019-01-01",
                             "seniorSince": None}]},
        }
        held = {"judges": list(judges)}
        self.assertEqual(federal_build.appointers("x", held, judges, moving={"e"}),
                         [["George W. Bush", 1], ["Barack Obama", 2]])

    def test_every_court_sums_to_its_active_count(self):
        payload, _courts, _search, _ = federal_build.build(ROOT)
        for court in payload["courts"]:
            if court["listed"]:
                self.assertEqual(sum(n for _p, n in court["appointers"]), court["active"], court["id"])
