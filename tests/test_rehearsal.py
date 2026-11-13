"""The changeover rehearsal (tools/rehearse_changeover.py): fiction about
real people that must never land in the repository, and a membership that
seats one person in every seat."""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import rehearse_changeover as rehearsal  # noqa: E402
from kyc import cycle, legislators, sources  # noqa: E402


class TestWhereItWrites(unittest.TestCase):
    def test_never_inside_the_repository(self):
        for inside in (ROOT, os.path.join(ROOT, "rehearsal"),
                       os.path.join(ROOT, "candidate_profiles_site", "x")):
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.check_out(inside)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rehearsal.check_out(tmp), os.path.realpath(tmp))

    def test_the_command_refuses_too(self):
        self.assertEqual(rehearsal.main(["--out", os.path.join(ROOT, "rehearsal")]), 2)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "rehearsal")))


class TestAStepsOutputIsReadAsItIsWritten(unittest.TestCase):
    """On Windows under ``python -X utf8`` the rehearsal read as UTF-8 what
    its steps wrote in the console's code page, and stopped on ``None +
    str`` before any step was judged. The step is handed the parent's
    choice (``rehearsal.step_io``)."""

    class Flags:
        def __init__(self, utf8_mode):
            self.utf8_mode = utf8_mode

    def test_a_utf8_parent_makes_a_utf8_child_and_reads_it_as_utf8(self):
        how = rehearsal.step_io(self.Flags(1), {"PATH": "x"})
        self.assertEqual((how["encoding"], how["errors"], how["text"]), ("utf-8", "replace", True))
        self.assertEqual(how["env"], {"PATH": "x", "PYTHONUTF8": "1"})

    def test_any_other_parent_changes_nothing_for_the_child(self):
        # Linux and CI as they were: the locale's encoding on both sides,
        # and the child's environment untouched.
        how = rehearsal.step_io(self.Flags(0), {"PATH": "x"})
        self.assertNotIn("env", how)
        self.assertNotIn("encoding", how)
        self.assertTrue(how["text"])

    def test_a_step_that_prints_an_accented_name_is_read_whole(self):
        # The state is made here: a child, started as a step is started,
        # that prints the name the January rehearsal stopped on, in whatever
        # encoding this parent's mode gives it.
        import subprocess
        code = "print('Pablo Jos\u00e9 Hern\u00e1ndez Rivera'); print('done')"
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, **rehearsal.step_io())
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIsNotNone(done.stdout)
        self.assertIn("done", done.stdout)
        self.assertIn("Pablo José Hernández Rivera", done.stdout)

    def test_a_byte_that_will_not_decode_is_replaced_never_fatal(self):
        import subprocess
        # A byte of the console's code page where UTF-8 is expected: what
        # the first read met at "José".
        code = r"import sys; sys.stdout.buffer.write(b'Jos\xe9 ok\n')"
        done = subprocess.run([sys.executable, "-c", code], capture_output=True,
                              **rehearsal.step_io(self.Flags(1), dict(os.environ)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIsNotNone(done.stdout)
        self.assertIn("ok", done.stdout)
        self.assertIn("Jos�", done.stdout)


class TestTheFictionalMemberships(unittest.TestCase):
    def test_january_seats_one_person_in_every_record_seat(self):
        made = rehearsal.january()
        if made is None:
            self.skipTest("the new Congress is sitting: the committed data is the case")
        snapshot, gone, _log = made
        self.assertEqual(cycle.phase(snapshot), "record")
        record = sources.load_all(ROOT)["record"]
        seats = {(p["chamber"], p["state"],
                  p.get("district") if p["chamber"] == "House" else p.get("senateClass"))
                 for p in snapshot["legislators"]}
        for rid, race in record["races"].items():
            key = (race["chamber"], race["state"],
                   race.get("district") if race["chamber"] == "House" else race.get("senateClass"))
            self.assertIn(key, seats, rid)
        # Everyone who left is in the historical file the departures read.
        before = legislators.by_bioguide(legislators.load_snapshot(ROOT))
        after = legislators.by_bioguide(snapshot)
        self.assertEqual({g["id"]["bioguide"] for g in gone}, set(before) - set(after))
        # Fiction is never a real id.
        self.assertTrue(all(b in before or b.startswith("Z9") for b in after))

    def test_january_follows_the_results_once_they_are_read(self):
        # The first refresh to carry a result (2026-11-04) failed four page
        # checks: "elected" was not among the statuses that win, so the seat
        # Andy Barr won went to Kentucky's best-funded filer, who had withdrawn.
        # The state is made here, on a seat whose holder is running again and
        # a seat a member is running for, whatever the day's results hold.
        from unittest import mock
        from kyc import candidates, fec, results
        from kyc.profiles import build_profiles
        raw = sources.load_all(ROOT)
        snap = legislators.load_snapshot(ROOT)
        if cycle.phase(snap) == "record":
            self.skipTest("the new Congress is sitting: the committed data is the case")
        field = candidates.load_cache(ROOT)
        profiles, _ = build_profiles(raw, snapshot=snap, field=field, finance=fec.load_cache(ROOT))
        record = raw["record"]
        member_ids = {i for p in snap["legislators"] for i in p.get("fecAll") or []}
        members = {p["id"]: p for p in profiles if not p["isCandidate"]}
        filers = {}
        for row in field["candidates"]:
            rid = candidates.race_id(row)
            if rid in record["races"] and row["candidate_id"] not in member_ids \
                    and row.get("incumbent_challenge") != "I":
                filers.setdefault(rid, []).append(row)
        # (Rows the FEC does not flag, so the pick below is no member's own
        # filing; the winner picked is then flagged, as the FEC flags winners.)
        people = legislators.by_bioguide(snap)
        # A holder running again who loses to the least-funded filer in the race
        # (two filers or more), in a seat whose index does not fall on the
        # rehearsal's every fifth, unlinked, newcomer.
        ordered = sorted(record["races"])
        beaten = next(rid for rid in ordered
                      if rid.startswith("H-") and ordered.index(rid) % 5 != 0
                      and len(filers.get(rid) or []) >= 2
                      and (record["incumbents"].get(rid) or {}).get("bioguide") in members
                      and members[record["incumbents"][rid]["bioguide"]].get("seekingReelection2026")
                      and people.get(record["incumbents"][rid]["bioguide"], {}).get("fecAll"))
        bid = record["incumbents"][beaten]["bioguide"]
        winner = min(filers[beaten], key=lambda r: (r.get("receipts") or 0, r["candidate_id"]))
        status = {beaten: {winner["candidate_id"]: "elected",
                           **{i: "defeated" for i in people[bid]["fecAll"]}}}
        # A sitting member elected to the seat they are running for instead.
        mover = next((p for p in members.values()
                      if p.get("contestRaceId") in record["races"]
                      and p["contestRaceId"] != p.get("raceId")
                      and people.get(p["id"], {}).get("fecAll")), None)
        if mover:
            status[mover["contestRaceId"]] = {i: "elected" for i in people[mover["id"]]["fecAll"]}
        # From 2026-11-12 the FEC flags a November winner as the incumbent:
        # the fiction dropped every flagged row, and seated CA-1's eliminated
        # filer in the seat its called winner had won.
        import copy
        flagged = copy.deepcopy(field)
        for row in flagged["candidates"]:
            if row["candidate_id"] == winner["candidate_id"]:
                row["incumbent_challenge"] = "I"
        with mock.patch.object(results, "load_cache",
                               return_value={"races": {r: {"status": st} for r, st in status.items()}}), \
                mock.patch.object(candidates, "load_cache", return_value=flagged):
            snapshot, _gone, _log = rehearsal.january()
        after = legislators.by_bioguide(snapshot)
        self.assertNotIn(bid, after, "a holder the results say lost leaves")
        seated = [p for p in after.values() if p["bioguide"].startswith("Z9")
                  and winner["candidate_id"] in (p.get("fecAll") or [])]
        self.assertEqual(len(seated), 1, "whoever the results elected takes the seat")
        self.assertEqual(seated[0]["state"], record["races"][beaten]["state"])
        if mover:
            race = record["races"][mover["contestRaceId"]]
            self.assertIn(mover["id"], after)
            self.assertEqual(after[mover["id"]]["chamber"], race["chamber"])
            self.assertEqual(after[mover["id"]]["state"], race["state"])

    def test_january_keeps_only_the_november_nominee_or_winner(self):
        # Asked only whether a holder was "defeated", the rehearsal kept 52
        # members the results had off the November ballot - eliminated in the
        # primary, withdrawn, or not listed - and read the record's ids alone,
        # missing a status keyed on the bioguide id (a roster alias) or on the
        # profile's own filing (PR #225 review). The state is made here.
        from unittest import mock
        from kyc import candidates, fec, results
        from kyc.profiles import build_profiles
        raw = sources.load_all(ROOT)
        snap = legislators.load_snapshot(ROOT)
        if cycle.phase(snap) == "record":
            self.skipTest("the new Congress is sitting: the committed data is the case")
        field = candidates.load_cache(ROOT)
        profiles, _ = build_profiles(raw, snapshot=snap, field=field, finance=fec.load_cache(ROOT))
        record = raw["record"]
        people = legislators.by_bioguide(snap)
        members = {p["id"]: p for p in profiles if not p["isCandidate"]}
        targets = {p.get("contestRaceId") for p in members.values()}
        seats = [rid for rid in sorted(record["races"])
                 if rid.startswith("H-") and rid not in targets
                 and (record["incumbents"].get(rid) or {}).get("bioguide") in members
                 and members[record["incumbents"][rid]["bioguide"]].get("seekingReelection2026")
                 and members[record["incumbents"][rid]["bioguide"]].get("fecCandidateId")
                 and people.get(record["incumbents"][rid]["bioguide"], {}).get("fecAll")]
        self.assertGreaterEqual(len(seats), 5)
        out_elim, out_wd, out_unlisted, in_elected, in_nominee = seats[:5]
        bid = {rid: record["incumbents"][rid]["bioguide"] for rid in seats[:5]}
        status = {
            out_elim: {i: "eliminated" for i in people[bid[out_elim]]["fecAll"]},
            out_wd: {bid[out_wd]: "withdrawn"},
            # out_unlisted: the results list nobody of the seat's holder.
            out_unlisted: {},
            in_elected: {bid[in_elected]: "elected"},
            in_nominee: {members[bid[in_nominee]]["fecCandidateId"]: "nominee"},
        }
        with mock.patch.object(results, "load_cache",
                               return_value={"races": {r: {"status": st} for r, st in status.items()}}):
            snapshot, gone, _log = rehearsal.january()
        after = legislators.by_bioguide(snapshot)
        left = {g["id"]["bioguide"] for g in gone}
        for rid, why in ((out_elim, "eliminated in the primary"), (out_wd, "withdrawn"),
                         (out_unlisted, "not on the results' list")):
            self.assertFalse(bid[rid] in after, f"{rid}: a holder {why} leaves")
            self.assertTrue(bid[rid] in left, rid)
        for rid in (in_elected, in_nominee):
            race = record["races"][rid]
            self.assertTrue(bid[rid] in after,
                            f"{rid}: the November nominee or winner keeps the seat")
            self.assertEqual((after[bid[rid]]["state"], after[bid[rid]]["district"]),
                             (race["state"], race["district"]), rid)

    def test_december_replaces_one_appointee(self):
        for label in ("december-loses", "december-wins"):
            made = rehearsal.december(label)
            if made is None:
                self.skipTest("the specials' winners are seated")
            snapshot, historical = made
            self.assertEqual(len(historical), 1, label)
            self.assertEqual(sum(1 for p in snapshot["legislators"]
                                 if p["bioguide"].startswith("Z9")), 1, label)


if __name__ == "__main__":
    unittest.main()
