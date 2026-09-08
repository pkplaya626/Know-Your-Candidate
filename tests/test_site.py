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
        cls.profiles, _ = build_profiles(raw)
        cls.races = races_mod.build(cls.profiles)
        cls.summary = summary.build(cls.profiles, races=cls.races)

    def test_the_senate_has_one_hundred_seats(self):
        self.assertEqual(self.summary["senate"]["total"], 100)

    def test_thirty_five_senate_seats_are_up(self):
        self.assertEqual(self.summary["election"]["senateSeatsUp"], 35)

    def test_the_party_split_adds_up(self):
        senate = self.summary["senate"]
        self.assertEqual(senate["D"] + senate["R"] + senate["I"] + senate["vacant"],
                         senate["total"])

    def test_race_counts_match_the_race_list(self):
        self.assertEqual(self.summary["races"]["total"], len(self.races))


class TestEmit(unittest.TestCase):
    def test_writes_the_globals_the_pages_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            emit.write_profiles([member()], {"total": 1}, root=tmp,
                                races=[], summary={"senate": {}})
            with open(os.path.join(tmp, emit.DATA_FILE), encoding="utf-8") as f:
                text = f.read()
        for global_name in ("window.legislatorsData", "window.kycRaces",
                            "window.kycBuildMeta"):
            self.assertIn(global_name, text)

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
            emit.write_profiles([member(name="</script><script>alert(1)</script>")],
                                {"total": 1}, root=tmp)
            with open(os.path.join(tmp, emit.DATA_FILE), encoding="utf-8") as f:
                text = f.read()
        self.assertNotIn("</script>", text)

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
            path, size = emit.write_profiles([member()], {}, root=tmp)
            self.assertTrue(os.path.exists(path))
            self.assertFalse(os.path.exists(path + ".tmp"))
            self.assertGreater(size, 0)


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
            emit.write_profiles([member()], {}, root=tmp, races=[], summary={"x": 1})
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
        self.assertIn("data/profiles.js", result["index.html"][1])

    def test_loading_the_page_module_before_its_data_is_reported(self):
        # The modules read their globals as they initialise, so the wrong
        # order renders an empty site with no error anywhere.
        with tempfile.TemporaryDirectory() as tmp:
            page_dir = os.path.join(tmp, emit.SITE_DIR)
            os.makedirs(os.path.join(page_dir, "assets"))
            os.makedirs(os.path.join(page_dir, "data"))
            for name in ("assets/kyc.js", "assets/kyc-profile.js",
                         "assets/kyc-directory.js", "data/profiles.js"):
                with open(os.path.join(page_dir, *name.split("/")), "w"):
                    pass
            with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(
                    '<script src="assets/kyc.js"></script>'
                    '<script src="assets/kyc-directory.js"></script>'
                    '<script src="data/profiles.js"></script>'
                    '<script src="assets/kyc-profile.js"></script>'
                )
            result = dict((p, (ok, note)) for p, ok, note in emit.check_pages(tmp))
        self.assertFalse(result["index.html"][0])
        self.assertIn("out of order", result["index.html"][1])


class TestHostnameConsistency(unittest.TestCase):
    """One hostname, six places, five files.

    GitHub Pages serves from CNAME; everything else has to agree with it or
    the site tells search engines and social networks it lives somewhere it
    does not. Nothing about a rename would look wrong locally.
    """

    def site(self, tmp, host="example.test", robots_host=None, sitemap_host=None,
             page_host=None):
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


if __name__ == "__main__":
    unittest.main()
