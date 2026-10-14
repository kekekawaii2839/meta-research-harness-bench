"""Offline tests for factory_v8_4 (zero model calls, no network): v8_4 prompt snapshot, round-1 leak gate always runs
(locked-frame pack after a gate routing), a missing round-1 verdict is an error, carry-paper and rejudge-final."""
from pathlib import Path
import shutil
import sys
import unittest

DRIVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVER))
import factory_v8_4 as v84  # noqa: E402
import factory_v8 as v8  # noqa: E402
import factory_v8_3 as v83  # noqa: E402
import factory_v5  # noqa: E402
from tests_v8 import test_factory_v8 as T  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, ProtocolError  # noqa: E402
from mrhbench.factory import DONE  # noqa: E402

ODATE = "2024-10-04"


def found(date):
    return lambda forum: (date, {"odate": 0})


class Prompts(unittest.TestCase):
    def test_only_leak_judge_and_framer_differ_and_rule_present(self):
        a, b = DRIVER / "prompts_next/v8", DRIVER / "prompts_next/v8_4"
        diff = sorted(p.name for p in a.iterdir() if file_hash(p) != file_hash(b / p.name))
        self.assertEqual(diff, ["framer.txt", "leak_judge.txt"])
        self.assertIn("source-stated gaps", (b / "leak_judge.txt").read_text(encoding="utf8"))
        self.assertIn("accuracy first", (b / "framer.txt").read_text(encoding="utf8"))

    def test_snapshot_uses_v8_4_and_keeps_bg_screen_without_global_side_effect(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        info = factory_v5.build_prompt_snapshot(tmp / "snap")
        self.assertEqual(file_hash(tmp / "snap/factory_v4/v8_leak_judge.txt"),
                         file_hash(DRIVER / "prompts_next/v8_4/leak_judge.txt"))
        self.assertTrue((tmp / "snap/factory_v4/v8_bg_screen.txt").is_file())
        self.assertIn("factory_v8_1", info)
        self.assertEqual(v8.V8, DRIVER / "prompts_next" / "v8")


class Flow(unittest.TestCase):
    setUp, tearDown, make, run_unit = T.Flow.setUp, T.Flow.tearDown, T.Flow.make, T.Flow.run_unit

    def make84(self, script):
        f = self.make(script)
        f.__class__ = v84.FactoryV84  # same fixture as the v8 tests; background_cutoff stays stubbed
        # the v8 fixture has no v8.1 background screen; use the v8 frame/background behaviour (not under test here)
        f.stage_frame = lambda state: v8.FactoryV8.stage_frame(f, state)
        f.frame_background_sources = lambda pid: v8.FactoryV8.frame_background_sources(f, pid)
        # v8.3 record: disclosure 14 days after the fixture's CUTOFF, so the public cutoff equals the fake framer's date
        v83.stamp_manifest(f.paper_dir(T.PID), found("2024-10-18"))
        del f.background_cutoff  # read the record, as in a real v8.3/v8.4 root
        return f

    def test_lock_violation_still_runs_round1_gate_on_the_locked_frame(self):
        s = T.Script(verdicts=["acceptable", "acceptable"], adjudications=["pass"], tamper_construct=True)
        f = self.make84(s)
        st = self.run_unit(f)
        self.assertEqual(st["probe"]["status"], "completed")
        self.assertIn(v84.FRAME_PACK_NOTE, st["probe"]["notes"])
        self.assertEqual(st["leak_judge"]["status"], "completed")
        files = s.probe_inputs[0]
        self.assertIn("public/assets/task.md", files)
        self.assertIn("controller_frame_pack.json", files)
        wdir = f.wdir(f.unit_state(T.PID, "IDEA"))
        self.assertEqual(file_hash(wdir / "probe_ws/public/assets/task.md"), file_hash(wdir / "frame/assets/task.md"))
        self.assertEqual(st["repair_adjudication"]["status"], "completed")

    def test_lock_violation_with_round1_leak_now_reframes(self):
        s = T.Script(verdicts=["leak", "acceptable"], adjudications=["pass"], tamper_construct=True)
        f = self.make84(s)
        st = self.run_unit(f)
        self.assertEqual(st["reframe"]["status"], "completed")
        self.assertEqual(st["repair_adjudication"]["status"], "completed")

    def test_missing_round1_verdict_is_an_error(self):
        s = T.Script(verdicts=["acceptable"], adjudications=["repair"])
        f = self.make84(s)
        pstate = f.state(T.PID)
        f.stage_area_brief(pstate)
        u = f.unit_state(T.PID, "IDEA")
        f._run_stages(u, ("frame", "construct"), ("frame", "construct"), False)
        u = f.unit_state(T.PID, "IDEA")
        u["stages"]["review_adjudication"] = {"status": DONE}
        write_json(f.wdir(u) / "review_adjudication/review_adjudication.json", {"action": "repair", "repair_notes": ["x"]})
        with self.assertRaises(ProtocolError):
            f.stage_reframe(u)

    def test_normal_paths_unchanged(self):
        s = T.Script(verdicts=["leak", "leak"], adjudications=["pass", "pass"])
        st = self.run_unit(self.make84(s))
        self.assertEqual(st["repair_adjudication"]["status"], "dropped")


class Carry(unittest.TestCase):
    setUp, tearDown, make, run_unit = T.Flow.setUp, T.Flow.tearDown, T.Flow.make, T.Flow.run_unit

    def source_root(self, verdicts, adjudications):
        f = self.make(T.Script(verdicts=verdicts, adjudications=adjudications))
        self.run_unit(f)  # source root built with the v8 controller (stands in for the older v8.2 root)
        old = factory_v5.FactoryV5._review_adjudication
        return f, old

    def test_carry_refuses_cutoff_mismatch_and_leaves_source_untouched(self):
        f, _ = self.source_root(["acceptable"], ["pass"])
        pdir = f.paper_dir(T.PID)
        before = file_hash(pdir / "sources/manifest.json")
        with self.assertRaises(ProtocolError):  # frames used CUTOFF 2024-10-04; recorded public cutoff is 14 days earlier
            v84.cmd_carry_paper(self.tmp / "v84", self.root, [T.PID], lookup=found(ODATE))
        self.assertFalse((self.tmp / "v84/papers" / T.PID).exists())
        out = v84.cmd_carry_paper(self.tmp / "v84", self.root, [T.PID], with_unit="IDEA", lookup=found("2024-10-18"))
        d = self.tmp / "v84/papers" / T.PID
        self.assertEqual(out[0]["first_disclosure"]["public_cutoff"], T.CUTOFF)
        self.assertTrue((d / "units/IDEA/state.json").is_file())
        self.assertNotIn("units", read_json(d / "state.json")["stages"])
        self.assertEqual(file_hash(pdir / "sources/manifest.json"), before)

    def carried_rejudge(self, src_verdicts, src_adjs, new_verdict):
        f, _ = self.source_root(src_verdicts, src_adjs)
        v84.cmd_carry_paper(self.tmp / "v84", self.root, [T.PID], with_unit="IDEA", lookup=found("2024-10-18"))
        s = T.Script(verdicts=[new_verdict])
        g = v84.FactoryV84(self.tmp / "v84", native_factory=lambda role: T.FakeRunner(s, role), sources=None, runtime=None,
                           budget=factory_v5.CallBudget(5))
        g.__dict__["_factory_prompts"] = "factory_v4"
        shutil.copytree(self.root / "prompts_snapshot", self.tmp / "v84/prompts_snapshot")
        shutil.copyfile(self.root / "factory_config.json", self.tmp / "v84/factory_config.json") \
            if (self.root / "factory_config.json").exists() else None
        for item in self.root.iterdir():
            if item.is_file() and not (self.tmp / "v84" / item.name).exists():
                shutil.copyfile(item, self.tmp / "v84" / item.name)
        g._source_workspace = f._source_workspace.__func__.__get__(g)
        g._candidate = f._candidate
        out = v84.cmd_rejudge_final(g, [T.PID])
        return out[0], g.unit_state(T.PID, "IDEA"), s

    def test_rejudge_acceptable_restores_pass_without_adjudicator_call(self):
        res, u, s = self.carried_rejudge(["leak", "leak"], ["pass", "pass"], "acceptable")
        self.assertEqual(res["repair_adjudication"], DONE)
        self.assertEqual(u["stages"]["repair_adjudication"]["status"], DONE)
        self.assertEqual([r for r, _ in s.calls], ["material_reviewer"])  # judge only
        wdir = self.tmp / "v84/papers" / T.PID / "units/IDEA"
        self.assertTrue((wdir / "leak_judge2.v82/leak_verdict.json").is_file())
        self.assertTrue((wdir / "repair_adjudication/controller_leak_override.v82.json").is_file())
        self.assertFalse((wdir / "repair_adjudication/controller_leak_override.json").exists())

    def test_rejudge_leak_stays_dropped(self):
        res, u, _ = self.carried_rejudge(["leak", "leak"], ["pass", "pass"], "leak")
        self.assertEqual(u["stages"]["repair_adjudication"]["status"], "dropped")

    def test_adjudicator_drop_is_kept(self):
        res, u, _ = self.carried_rejudge(["leak", "acceptable"], ["pass", "drop"], "acceptable")
        self.assertEqual(u["stages"]["repair_adjudication"]["status"], "dropped")


if __name__ == "__main__":
    unittest.main()
