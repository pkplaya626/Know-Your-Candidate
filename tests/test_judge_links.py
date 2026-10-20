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


def light(url, size, weight=20_000):
    """Every size a page may draw of one file, weighed at *weight* bytes."""
    return {u: {"bytes": weight, "width": w, "height": round(w * size[1] / size[0])}
            for w, u in jl.renditions(url, size[0])}


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
                       credits={url: credit}, weights=light(url, size))

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
        self.assertIn("was not read", problems[0])

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


def article(title="Ann Example", born="1960", image=None, lead=..., fjc_bio=(), item="Q1"):
    """An article as read; its lead image is its infobox's unless *lead*
    says otherwise (None: the article gives no lead image)."""
    return {"title": title, "item": item, "born": born, "image": image,
            "lead": image if lead is ... else lead, "fjcBio": sorted(fjc_bio)}


def ref(name):
    return jl.file_ref(name)


def up(name):
    return jl.commons_url(jl.file_ref(name))


class TestThePhotoRoutes(unittest.TestCase):
    """The routes the 2026-10-19 photo research found, as its second reader
    corrected them (FEDERAL-05): every one tied to the judge by an id."""

    CREDIT = TestTheJoin.CREDIT

    def run_join(self, item, files, articles=None, crops=None, bio=None, slugs=None,
                 weights=None, judge=JUDGE, previous=None, report=None, wanted=None,
                 bio_missed=None):
        """*files* is ``{file name: (width, height)}``."""
        sizes = {up(n): s for n, s in files.items()}
        if weights is None:
            weights = {}
            for n, s in files.items():
                weights.update(light(up(n), s))
        return jl.join({"fjc-100": judge}, slugs if slugs is not None else {"100": "example-ann"},
                       wd(item) if item else {}, sizes, previous,
                       {up(n): self.CREDIT for n in files}, articles=articles or {},
                       crops=crops or {}, bio=bio or {}, weights=weights, report=report,
                       wanted=wanted, today="2026-10-19", bio_missed=bio_missed)

    # ---- the slug's percent-encoding

    def test_an_accented_slug_is_read_and_joined(self):
        """Ten judges (Pérez, Vázquez, Gelpí ...) were 'unread' on every run:
        the FJC's canonical slug is percent-encoded, as Wikidata's P2736 is."""
        page = '<link rel="canonical" href="https://www.fjc.gov/history/judges/p%C3%A9rez-myrna" />'
        self.assertEqual(jl.slug_of(page), "p%C3%A9rez-myrna")
        judge = {"id": "fjc-100", "name": "Myrna Pérez", "sortName": "Pérez, Myrna",
                 "born": {"year": "1974"}}
        item = entity("Q107251252", "p%C3%A9rez-myrna", label="Myrna Pérez",
                      images=["Myrna Perez (Judge) (cropped).jpg"], born="1974")
        joined, problems = self.run_join(item, {"Myrna Perez (Judge) (cropped).jpg": (449, 535)},
                                         slugs={"100": "p%C3%A9rez-myrna"}, judge=judge)
        self.assertEqual(problems, [])
        self.assertEqual(joined["100"]["portrait"]["route"], "item")
        # Either escaping of one slug is the same slug.
        self.assertEqual(jl.slug_key("p%C3%A9rez-myrna"), jl.slug_key("pérez-myrna"))

    # ---- every portrait carries its record

    def test_a_portrait_records_its_route_evidence_day_and_weight(self):
        name = "Ann Example.jpg"
        joined, _ = self.run_join(entity("Q1", "example-ann", images=[name]), {name: (400, 500)})
        portrait = joined["100"]["portrait"]
        for key in jl.RECORD_KEYS:
            self.assertTrue(portrait.get(key), key)
        self.assertIn("Q1", portrait["evidence"])
        self.assertIn("example-ann", portrait["evidence"])
        self.assertIn("born 1960", portrait["evidence"])
        self.assertEqual(portrait["read"], "2026-10-19")
        # Only Wikimedia's own sizes, and none wider than a page draws.
        self.assertEqual([w for w, _u in portrait["set"]], [120, 250])
        self.assertEqual(portrait["file"], [400, 500])
        # The page gets what it draws and credits; the record stays behind.
        out = federal_build._judge({"id": "fjc-100", "name": "Ann B. Example"},
                                   {"judges": joined})
        self.assertNotIn("evidence", out["portrait"])
        self.assertNotIn("bytes", out["portrait"])
        self.assertEqual(out["portrait"]["licence"], "CC BY-SA 3.0")

    def test_a_portrait_without_its_record_fails_the_build(self):
        name = "Ann Example.jpg"
        joined, _ = self.run_join(entity("Q1", "example-ann", images=[name]), {name: (400, 500)})
        bare = {k: v for k, v in joined["100"]["portrait"].items() if k != "evidence"}
        codes = {code: level for level, code, _m, _d in jl.problems({"judges": {"100": {
            "wikidata": "Q1", "portrait": bare}}})}
        self.assertEqual(codes.get("judge-portrait-unevidenced"), "error")
        heavy = dict(joined["100"]["portrait"], bytes=400_000)
        codes = {code: level for level, code, _m, _d in jl.problems({"judges": {"100": {
            "wikidata": "Q1", "portrait": heavy}}})}
        self.assertEqual(codes.get("judge-portrait-heavy"), "error")

    # ---- the official small renditions only

    def test_a_size_over_the_cap_gives_way_to_the_next_smaller(self):
        name = "Ann Example.png"
        url = up(name)
        weights = light(url, (742, 912))
        big = [u for w, u in jl.renditions(url, 742) if w == 250][0]
        weights[big] = dict(weights[big], bytes=307_800)       # Judge Clarke's 500px PNG
        joined, problems = self.run_join(entity("Q1", "example-ann", images=[name]),
                                         {name: (742, 912)}, weights=weights)
        self.assertEqual([w for w, _u in joined["100"]["portrait"]["set"]], [120])
        self.assertEqual(problems, [])

    def test_an_image_offered_only_oversized_is_left_out_and_counted(self):
        name = "Ann Example.png"
        url = up(name)
        weights = {u: dict(v, bytes=650_800) for u, v in light(url, (742, 912)).items()}
        report = {}
        joined, problems = self.run_join(entity("Q1", "example-ann", images=[name]),
                                         {name: (742, 912)}, weights=weights, report=report)
        self.assertNotIn("portrait", joined["100"])
        self.assertEqual(report["oversized"], ["Ann B. Example"])
        self.assertIn("left out", problems[0])
        said = {code: message for _l, code, message, _d in jl.problems(
            {"judges": joined, "oversized": report["oversized"]})}
        self.assertIn("1 judges' photographs left out", said["judge-portraits-oversized"])

    def test_a_size_not_yet_weighed_is_asked_for_and_not_shown(self):
        name = "Ann Example.jpg"
        wanted = set()
        joined, problems = self.run_join(entity("Q1", "example-ann", images=[name]),
                                         {name: (400, 500)}, weights={}, wanted=wanted)
        self.assertNotIn("portrait", joined["100"])
        self.assertEqual(wanted, {u for w, u in jl.renditions(up(name), 400) if w == 250})
        self.assertIn("not been weighed", problems[0])

    def test_a_refresh_weighs_what_it_shows_and_nothing_else(self):
        import tempfile
        name = "Ann Example.jpg"
        weighed = []

        def weigh_of(urls):
            weighed.extend(urls)
            return {u: {"bytes": 20_000, "width": 250, "height": 312} for u in urls}

        info = {"width": 400, "height": 500, "extmetadata": {
            "Artist": {"value": "Senate Judiciary Committee"},
            "LicenseShortName": {"value": "Public domain"}}}
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, os.path.dirname(jl.CACHE_PATH)))
            jl.save_cache({"slugs": {"100": "example-ann"}, "judges": {}}, root)
            original = jl.fetch_wikidata
            jl.fetch_wikidata = lambda *a, **k: wd(entity("Q1", "example-ann", images=[name]))
            try:
                cache = jl.refresh({"judges": {"fjc-100": JUDGE}}, root, read=lambda url: "{}",
                                   sizes_of=lambda urls: {u: info for u in urls},
                                   weigh_of=weigh_of, log=None)
                self.assertEqual(len(weighed), 1)
                self.assertTrue(weighed[0].endswith("/250px-Ann_Example.jpg"))
                self.assertEqual(cache["judges"]["100"]["portrait"]["bytes"], 20_000)
                # The next run reuses the weight of the same file.
                weighed.clear()
                jl.refresh({"judges": {"fjc-100": JUDGE}}, root, read=lambda url: "{}",
                           sizes_of=lambda urls: {u: info for u in urls},
                           weigh_of=weigh_of, log=None)
                self.assertEqual(weighed, [])
            finally:
                jl.fetch_wikidata = original

    def test_weighing_stops_when_wikimedia_keeps_refusing(self):
        """Wikimedia answered every rendition of the first full run with 429
        ("does not comply with our robot policy"): its user agent named no
        way to reach the project. One that does, and a run that stops after
        a few refusals in a row rather than keep the burst going."""
        self.assertIn("https://github.com/", jl.USER_AGENT)
        asked = []

        def refused(url):
            asked.append(url)
            return None, 10.0

        self.assertEqual(jl.weigh([f"u{i}" for i in range(20)], log=None, measure_one=refused), {})
        self.assertEqual(len(asked), 5)
        # One read that fails is asked about again next run; the rest are weighed.
        answers = {"a": ({"bytes": 9000, "width": 250, "height": 300}, None), "b": (None, None)}
        got = jl.weigh(["a", "b"], log=None, measure_one=lambda u: answers[u])
        self.assertEqual(list(got), ["a"])
        self.assertEqual(got["a"]["bytes"], 9000)

    # ---- two images: the one the article shows

    def test_two_images_give_the_one_the_article_shows(self):
        a, b = "Ann Example official.jpg", "Ann and Bob Example.jpg"
        item = entity("Q1", "example-ann", images=[a, b], article="Ann Example")
        files = {a: (400, 500), b: (400, 500)}
        joined, _ = self.run_join(item, files, articles={"Ann Example": article(image=a)})
        self.assertEqual(joined["100"]["portrait"]["route"], "agree")
        self.assertIn("Ann_Example_official.jpg", joined["100"]["portrait"]["url"])
        # An article that shows a third file agrees with neither.
        joined, problems = self.run_join(item, files,
                                         articles={"Ann Example": article(image="Other.jpg")})
        self.assertNotIn("portrait", joined["100"])
        self.assertIn("2 images; none shown", problems[0])

    # ---- a wide frame: its crop, extracted from it and depicting the judge alone

    def test_a_wide_frame_gives_its_crop_that_depicts_the_judge_alone(self):
        wide, crop = "Ann Example hearing.jpg", "Ann Example hearing (cropped).jpg"
        item = entity("Q1", "example-ann", images=[wide])
        files = {wide: (1280, 720), crop: (446, 566)}
        joined, problems = self.run_join(item, files, crops={wide: [{"file": crop, "depicts": ["Q1"]}]})
        self.assertEqual(problems, [])
        self.assertEqual(joined["100"]["portrait"]["route"], "crop")
        self.assertIn("Extracted from", joined["100"]["portrait"]["evidence"])
        # Don Willett's crop depicts a microphone (Q46384), not him; another's
        # depicts no one; a crop of two people names both.
        for depicts in (["Q46384"], [], ["Q1", "Q2"]):
            joined, problems = self.run_join(item, files,
                                             crops={wide: [{"file": crop, "depicts": depicts}]})
            self.assertNotIn("portrait", joined["100"])
            self.assertIn("no crop of it depicts Q1 alone", problems[0])
        # Crops not read: nothing concluded, nothing invented.
        joined, problems = self.run_join(item, files, crops={})
        self.assertNotIn("portrait", joined["100"])
        self.assertIn("crops were not read", problems[0])

    def test_the_crops_are_read_from_commons_own_pages(self):
        self.assertEqual(jl.extracted_from("{{Extracted from|File:Ann_Example hearing.jpg}}"),
                         ["Ann Example hearing.jpg"])
        self.assertEqual(jl.extracted_from("{{extracted from|1=Ann Example hearing.jpg|x=1}}"),
                         ["Ann Example hearing.jpg"])

        def read(url):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            self.assertTrue(url.startswith(jl.COMMONS_API))
            if query.get("prop") == "linkshere":
                return json.dumps({"query": {"pages": [{"title": "File:Ann Example hearing.jpg",
                    "linkshere": [{"title": "File:Ann Example hearing (cropped).jpg"},
                                  {"title": "File:Unrelated.jpg"}]}]}})
            if query.get("prop") == "revisions":
                pages = [{"title": "File:Ann Example hearing (cropped).jpg", "pageid": 7,
                          "revisions": [{"slots": {"main": {
                              "content": "{{Extracted from|Ann Example hearing.jpg}}"}}}]},
                         {"title": "File:Unrelated.jpg", "pageid": 8,
                          "revisions": [{"slots": {"main": {
                              "content": "[[File:Ann Example hearing.jpg]]"}}}]}]
                return json.dumps({"query": {"pages": pages}})
            self.assertEqual(query["ids"], "M7")
            return json.dumps({"entities": {"M7": {"statements": {"P180": [
                {"mainsnak": {"datavalue": {"value": {"id": "Q1"}}}, "rank": "normal"}]}}}})

        crops = jl.fetch_crops(["Ann Example hearing.jpg"], read, live=False)
        self.assertEqual(crops, {"Ann Example hearing.jpg": [
            {"file": "Ann Example hearing (cropped).jpg", "depicts": ["Q1"]}]})

    # ---- no image: the article's infobox image, where its lead agrees

    def test_an_item_without_an_image_gives_its_articles_infobox_image(self):
        name = "Ann Example.png"
        item = entity("Q1", "example-ann", article="Ann Example")
        joined, problems = self.run_join(item, {name: (742, 912)},
                                         articles={"Ann Example": article(image=name)})
        self.assertEqual(problems, [])
        self.assertEqual(joined["100"]["portrait"]["route"], "article")
        # The article's lead image is another file: the two disagree.
        joined, _ = self.run_join(item, {name: (742, 912)},
                                  articles={"Ann Example": article(image=name, lead="Courthouse.jpg")})
        self.assertNotIn("portrait", joined["100"])
        # An article that gives no lead image confirms nothing: the infobox
        # alone is not the route, and the evidence would not be true.
        joined, problems = self.run_join(item, {name: (742, 912)},
                                         articles={"Ann Example": article(image=name, lead=None)})
        self.assertNotIn("portrait", joined["100"])
        self.assertIn("gives no lead image", problems[0])
        # An article whose title is not theirs gives nothing.
        item = entity("Q1", "example-ann", article="Protests in 2026")
        joined, _ = self.run_join(item, {name: (742, 912)},
                                  articles={"Protests in 2026": article(title="Protests in 2026",
                                                                       image=name)})
        self.assertNotIn("portrait", joined["100"])
        self.assertNotIn("wikipedia", joined["100"])

    def test_the_article_is_read_for_its_year_image_and_fjc_id(self):
        text = ("{{Infobox judge\n| name = Ann Example\n| image = [[File:Ann_Example.png|250px]]"
                "\n| birth_date = {{birth date and age|1960|5|1}}<ref>x 1999</ref>\n}}\n"
                "'''Ann Example''' (born 1960) is a judge.\n== Links ==\n{{FJC Bio|nid=100}}\n")
        self.assertEqual(jl.article_facts(text),
                         {"born": "1960", "image": "Ann Example.png", "fjcBio": ["100"]})
        lead = "{{Infobox officeholder\n| image = Ann Example.jpg\n}}\nAnn Example (born May 1, 1961) ...\n"
        self.assertEqual(jl.article_facts(lead)["born"], "1961")
        self.assertEqual(jl.article_facts(lead)["image"], "Ann Example.jpg")
        self.assertIsNone(jl.article_facts("{{Infobox judge\n| image = <!-- none -->\n}}")["image"])
        self.assertEqual(jl.article_facts("{{FJC Bio|nid=1389371}}")["fjcBio"], ["1389371"])
        # The positional value is the directory's retired id, not the nid:
        # read as one, it refused 82 judges' own articles.
        self.assertEqual(jl.article_facts("{{FJC Bio|261|nid=1378271}}")["fjcBio"], ["1378271"])
        self.assertEqual(jl.article_facts("{{FJC Bio|261}}")["fjcBio"], [])

    def test_articles_are_read_in_batches_through_redirects(self):
        def read(url):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            self.assertTrue(url.startswith(jl.ENWIKI_API))
            self.assertEqual(query["titles"], "Ann Example")
            return json.dumps({"query": {
                "redirects": [{"from": "Ann Example", "to": "Ann B. Example"}],
                "pages": [{"title": "Ann B. Example", "pageimage": "Ann_Example.png",
                           "pageprops": {"wikibase_item": "Q1"},
                           "revisions": [{"slots": {"main": {"content":
                               "{{Infobox judge\n| image = Ann Example.png\n}}\n(born 1960)"}}}]}]}})

        got = jl.fetch_articles(["Ann Example"], read, live=False)
        self.assertEqual(got["Ann Example"]["item"], "Q1")
        self.assertEqual(got["Ann Example"]["lead"], "Ann Example.png")
        self.assertEqual(got["Ann Example"]["image"], "Ann Example.png")

    # ---- the year of birth, from both sources

    def test_an_item_without_a_year_is_checked_by_its_article(self):
        name = "Ann Example.jpg"
        item = entity("Q1", "example-ann", images=[name], article="Ann Example", born=None)
        joined, problems = self.run_join(item, {name: (400, 500)},
                                         articles={"Ann Example": article(born="1960")})
        self.assertEqual(problems, [])
        self.assertIn("born 1960 by the article", joined["100"]["portrait"]["evidence"])
        joined, problems = self.run_join(item, {name: (400, 500)},
                                         articles={"Ann Example": article(born="1982")})
        self.assertEqual(joined, {})
        self.assertIn("1982", problems[0])
        joined, problems = self.run_join(item, {name: (400, 500)},
                                         articles={"Ann Example": article(born=None)})
        self.assertEqual(joined, {})
        self.assertIn("no year of birth", problems[0])

    def test_wikidata_and_the_article_disagreeing_gives_nothing(self):
        name = "Ann Example.jpg"
        item = entity("Q1", "example-ann", images=[name], article="Ann Example", born="1960")
        joined, problems = self.run_join(item, {name: (400, 500)},
                                         articles={"Ann Example": article(born="1961")})
        self.assertEqual(joined, {})
        self.assertIn("1961", problems[0])

    # ---- {{FJC Bio}}: the article that carries the judge's nid

    def bio(self, slugs=(), title="Ann Example", label="Ann Example"):
        item = entity("Q5", None, label=label, images=["Ann Example.jpg"], article=title)
        item["claims"]["P2736"] = [{"mainsnak": {"datavalue": {"value": s}}, "rank": "normal"}
                                   for s in slugs]
        (qid, entry), = jl.read_items({"entities": {"Q5": item}}).items()
        return {"100": (qid, entry, "Ann Example")}

    def test_a_judge_no_item_carries_is_found_by_their_fjc_bio(self):
        name = "Ann Example.jpg"
        articles = {"Ann Example": article(fjc_bio=["100"], item="Q5")}
        joined, problems = self.run_join(None, {name: (400, 500)}, articles=articles,
                                         bio=self.bio())
        self.assertEqual(problems, [])
        self.assertEqual(joined["100"]["wikidata"], "Q5")
        self.assertEqual(joined["100"]["wikipedia"], "Ann Example")
        # The evidence quotes the template as it was matched: its nid=.
        self.assertIn("{{FJC Bio|nid=100}}", joined["100"]["portrait"]["evidence"])
        # The entry says how it was found, for the page's note.
        self.assertEqual(joined["100"]["linkVia"], "fjc-bio")
        out = federal_build._judge({"id": "fjc-100", "name": "Ann B. Example"}, {"judges": joined})
        self.assertEqual(out["linkVia"], "fjc-bio")
        # A judge found through the item carrying their id has no such mark.
        item = entity("Q1", "example-ann", images=[name], article="Ann Example")
        joined_by_id, _ = self.run_join(item, {name: (400, 500)},
                                        articles={"Ann Example": article(item="Q1")})
        self.assertNotIn("linkVia", joined_by_id["100"])
        # An item that carries another judge's FJC id is someone else's.
        joined, problems = self.run_join(None, {name: (400, 500)}, articles=articles,
                                         bio=self.bio(slugs=["other-judge"]))
        self.assertEqual(joined, {})
        self.assertIn("another FJC id", problems[0])
        # An item whose article is another page than the one found.
        joined, problems = self.run_join(None, {name: (400, 500)}, articles=articles,
                                         bio=self.bio(title="Ann Example (judge)"))
        self.assertEqual(joined, {})

    def test_the_fjc_bio_search_is_on_the_id_and_takes_one_answer(self):
        asked = []

        def read(url):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            asked.append(query["srsearch"])
            hits = {"100": ["Ann Example"], "200": list("ABCDEF"), "300": [],
                    "400": ["Ann Example (judge)", "Appointment controversies"]}[query["srsearch"][-4:-1]]
            return json.dumps({"query": {"search": [{"title": t} for t in hits]}})

        found, missed = jl.find_by_fjc_bio(["100", "200", "300", "400"], read, live=False)
        self.assertEqual(found, {"100": ["Ann Example"],
                                 "400": ["Ann Example (judge)", "Appointment controversies"]})
        # No article, or too many to read, is said - never silently nothing.
        self.assertEqual(sorted(missed), ["200", "300"])
        self.assertIn("6 English Wikipedia articles", missed["200"])
        self.assertIn("no English Wikipedia article", missed["300"])
        self.assertEqual(asked[0], 'hastemplate:"FJC Bio" insource:"100"')

    def test_of_the_articles_the_search_answers_the_one_whose_fjc_bio_names_the_nid(self):
        """The search matches the id anywhere in a page's source. Each
        answer is read, and only an article whose {{FJC Bio|nid=}} names
        the judge is theirs; two that name them alone name nobody (Justin
        D. Smith's search answered his article and a page on appointment
        controversies citing only his record, 2026-10-20)."""
        answers = {"400": ["Ann Example (judge)", "Appointment controversies"]}
        articles = {"Ann Example (judge)": article(title="Ann Example (judge)", fjc_bio=["400"],
                                                   item="Q9"),
                    "Appointment controversies": article(title="Appointment controversies",
                                                         fjc_bio=["7"], item="Q8")}
        missed = {}
        self.assertEqual(jl.settle_fjc_bio(answers, articles, missed),
                         {"400": ("Q9", "Ann Example (judge)")})
        self.assertEqual(missed, {})
        # A list citing this judge among others gives way to the article
        # that cites them alone.
        articles["Appointment controversies"]["fjcBio"] = ["400", "7"]
        self.assertEqual(jl.settle_fjc_bio(answers, articles, missed),
                         {"400": ("Q9", "Ann Example (judge)")})
        # Two articles citing this judge alone name nobody.
        articles["Appointment controversies"]["fjcBio"] = ["400"]
        self.assertEqual(jl.settle_fjc_bio(answers, articles, missed), {})
        self.assertIn("2 English Wikipedia articles carry {{FJC Bio|nid=400}}", missed["400"])
        # None of them carrying it as nid= is said, not passed over.
        missed = {}
        self.assertEqual(jl.settle_fjc_bio({"400": ["Appointment controversies"]},
                                           {"Appointment controversies": article(fjc_bio=[])},
                                           missed), {})
        self.assertIn("carries {{FJC Bio|nid=400}}", missed["400"])

    def test_a_failed_fjc_bio_search_keeps_the_last_entry(self):
        """Rule 8: a judge found only through {{FJC Bio}} keeps their links
        and portrait when the next run's search for them cannot be read."""
        name = "Ann Example.jpg"
        articles = {"Ann Example": article(fjc_bio=["100"], item="Q5")}
        first, _ = self.run_join(None, {name: (400, 500)}, articles=articles, bio=self.bio())
        self.assertIn("portrait", first["100"])

        def read(url):
            raise OSError("timed out")

        found, missed = jl.find_by_fjc_bio(["100"], read, live=False)
        self.assertEqual((found, missed), ({}, {}))
        joined, problems = self.run_join(None, {}, previous=first, bio={}, bio_missed=missed)
        self.assertEqual(joined["100"], first["100"])
        self.assertIn("was not read; the last entry is kept", problems[0])
        # A search that was read and found nothing is a finding: said, and
        # nothing linked.
        joined, problems = self.run_join(None, {}, previous=first, bio={},
                                         bio_missed={"100": "no English Wikipedia article's "
                                                            "{{FJC Bio}} names nid 100"})
        self.assertEqual(joined, {})
        self.assertIn("no Wikidata item carries the FJC id example-ann", problems[0])

    def test_an_article_naming_another_judges_id_is_refused(self):
        """A page that names someone else is not theirs, whatever its title."""
        name = "Ann Example.jpg"
        item = entity("Q1", "example-ann", images=[name], article="Ann Example")
        joined, problems = self.run_join(item, {name: (400, 500)},
                                         articles={"Ann Example": article(fjc_bio=["999"])})
        self.assertEqual(joined, {})
        self.assertIn("another judge's FJC id", problems[0])

    # ---- a licence a person must decide

    def test_a_doubted_licence_is_withheld_and_said(self):
        from kyc import overrides
        name = "Richard C. Wesley (cropped).jpg"
        self.assertIn(up(name), overrides.PORTRAIT_LICENCE_DOUBTS)
        report = {}
        joined, problems = self.run_join(entity("Q1", "example-ann", images=[name]),
                                         {name: (255, 357)}, report=report)
        self.assertNotIn("portrait", joined["100"])
        self.assertIn("PORTRAIT_LICENCE_DOUBTS", problems[0])
        self.assertEqual(report["doubted"], [up(name)])

    def test_a_kept_portrait_is_asked_of_the_overrides_again(self):
        """A doubt or a refusal added after a file was read withholds it,
        even on a run that could not read that judge again (rule 8 keeps
        what was read; it does not keep what a person withdrew)."""
        from kyc import overrides
        name = "Richard C. Wesley (cropped).jpg"
        url = up(name)
        kept = {"wikidata": "Q1", "portrait": {
            "url": url, "set": [[120, url]], "credit": "Wikimedia Commons",
            "source": jl.file_page(url), "licence": "CC BY-SA 4.0", "route": "item",
            "evidence": "Wikidata Q1 carries the FJC id", "read": "2026-10-01",
            "bytes": 20_000, "width": 120, "height": 150}}
        self.assertIn(url, overrides.PORTRAIT_LICENCE_DOUBTS)
        # The FJC page was not read this time: the entry is kept, the file not.
        joined, problems = self.run_join(None, {}, slugs={}, previous={"100": kept})
        self.assertEqual(joined["100"], {"wikidata": "Q1"})
        self.assertIn("PORTRAIT_LICENCE_DOUBTS", problems[0])
        # A wide frame whose crops were not read: the last portrait is not kept either.
        item = entity("Q1", "example-ann", images=[name])
        joined, problems = jl.join({"fjc-100": JUDGE}, {"100": "example-ann"}, wd(item),
                                   {url: (1600, 900)}, {"100": kept}, today="2026-10-19")
        self.assertNotIn("portrait", joined["100"])
        self.assertIn("is not shown", problems[0])
        # And a cache that holds one anyway fails the build.
        found = jl.problems({"judges": {"100": kept}})
        self.assertIn("judge-portrait-overridden", [code for _l, code, _m, _d in found])
        self.assertEqual([lvl for lvl, code, _m, _d in found
                          if code == "judge-portrait-overridden"], ["error"])

    def test_the_committed_portraits_carry_their_record_within_the_caps(self):
        from kyc import overrides
        cache = jl.load_cache(ROOT) or {}
        if "oversized" not in cache:
            self.skipTest("the judge links were read before the photo routes")
        for nid, entry in (cache.get("judges") or {}).items():
            portrait = entry.get("portrait")
            if not portrait:
                continue
            for key in jl.RECORD_KEYS:
                self.assertTrue(portrait.get(key), (nid, key))
            self.assertLessEqual(portrait["bytes"], jl.CAP_BYTES, nid)
            self.assertLessEqual(max(w for w, _u in portrait["set"]), jl.SHOWN_STEPS[-1], nid)
            self.assertNotIn(jl.source_url(portrait["source"]), overrides.PORTRAIT_LICENCE_DOUBTS)
            self.assertNotIn(jl.source_url(portrait["source"]), overrides.NOT_A_PORTRAIT)
            # The evidence quotes {{FJC Bio}} as it was matched, by nid=.
            self.assertNotRegex(portrait["evidence"], r"\{\{FJC Bio\|\d", nid)
            if "FJC Bio" in portrait["evidence"]:
                self.assertEqual(entry.get("linkVia"), "fjc-bio", nid)


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
