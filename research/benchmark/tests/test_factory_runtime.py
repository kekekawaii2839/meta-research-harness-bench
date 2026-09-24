"""Offline tests for mrhbench.factory_runtime; docker is always a fake runner."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, file_hash, read_json, write_json  # noqa: E402
from mrhbench.material_pipeline import validate_package  # noqa: E402
from mrhbench import factory_runtime as fr  # noqa: E402

PRIVATE_SENTENCE = "The withheld author result is that the variance ratio stays below one point two in every regime."
PRIVATE_FACT = "Private-only fact: the hidden benchmark target equals forty two for the selected configuration."
IMAGE_ID = "sha256:" + "ab" * 32
TYPES = ["LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_package(tmp, *, dockerfile="FROM python:3.12-slim\nCOPY requirements.txt /tmp/r.txt\nRUN pip install -r /tmp/r.txt\n",
                 public_text="Task statement: run the starter code and report the metric.\n"):
    job = Path(tmp) / "job"
    out = job / "output"
    (out / "environment/image").mkdir(parents=True)
    (out / "assets").mkdir()
    (out / "private").mkdir()
    (out / "environment/image/Dockerfile").write_text(dockerfile, encoding="utf8")
    (out / "environment/image/requirements.txt").write_text("numpy==2.3.3\n", encoding="utf8")
    (out / "environment/smoke.py").write_text("print('SMOKE OK')\n", encoding="utf8")
    (out / "assets/task.md").write_text(public_text, encoding="utf8")
    (out / "assets/data.csv").write_text("x,y\n1,2\n", encoding="utf8")
    (out / "private/notes.md").write_text("# Notes\n" + PRIVATE_SENTENCE + "\n", encoding="utf8")
    src_hash = "c" * 64
    write_json(job / "request.json", {"sources": [{"source_id": "s", "sha256": src_hash}]})
    package = {
        "schema_version": "material-package-1", "status": "candidate", "paper_id": "p1",
        "facts": [
            {"fact_id": "PUB-F1", "kind": "source_fact", "statement": "The starter code implements the baseline estimator.",
             "allowed_stages": ["EXP"], "discloses_target_contribution": False,
             "evidence": [{"source_id": "s", "source_sha256": src_hash, "locator": "Sec 2"}]},
            {"fact_id": "PRIV-F2", "kind": "source_result", "statement": PRIVATE_FACT,
             "allowed_stages": [], "discloses_target_contribution": True,
             "evidence": [{"source_id": "s", "source_sha256": src_hash, "locator": "Table 1"}]}],
        "coverage": [{"task_type": t, "status": "candidate" if t == "EXP" else "deferred", "reason": "fixture"} for t in TYPES],
        "tasks": [{"task_id": "p1-exp", "task_type": "EXP", "paper_id": "p1", "split": "development",
                   "input_fact_ids": ["PUB-F1"], "private_fact_ids": ["PRIV-F2"], "private_source_ids": ["s"],
                   "input_contract": {"description": "fixture", "files": [
                       {"path": "assets/task.md", "sha256": sha(out / "assets/task.md"), "visibility": "public"}]},
                   "output_contract": {"required": ["result"]},
                   "verification_plan": {"status": "pending"},
                   "assets": [{"path": "assets/task.md", "sha256": sha(out / "assets/task.md"), "visibility": "public"},
                              {"path": "assets/data.csv", "sha256": sha(out / "assets/data.csv"), "visibility": "public"},
                              {"path": "private/notes.md", "sha256": sha(out / "private/notes.md"), "visibility": "private"}]}],
        "environment": {"gpu": False, "network": "none", "runtime_verified": False, "dependencies": ["numpy==2.3.3"],
                        "scientific_rationale": "fixture", "dockerfile": "environment/image/Dockerfile",
                        "smoke_test": "environment/smoke.py",
                        "resources": {"cpus": 2, "memory_mb": 2048, "disk_mb": 512, "pids_limit": 128, "wall_seconds": 1200}}}
    write_json(out / "package.json", package)
    validate_package(package, out, read_json(job / "request.json")["sources"])
    return out, package


class FakeDocker:
    def __init__(self, *, smoke_rc=0, smoke_timeout=False, build_rc=0, leftover=False):
        self.calls = []
        self.smoke_rc, self.smoke_timeout, self.build_rc, self.leftover = smoke_rc, smoke_timeout, build_rc, leftover
        self.smoke_timeout_arg = None

    def __call__(self, argv, *, timeout=None):
        self.calls.append(list(argv))
        ok = {"returncode": 0, "stdout": "", "stderr": "", "timed_out": False, "seconds": 0.1}
        sub = argv[1]
        if sub == "build":
            return dict(ok, returncode=self.build_rc, stdout="built")
        if sub == "image":
            return dict(ok, stdout=IMAGE_ID + "\n")
        if sub == "run" and "pip" in argv:
            return dict(ok, stdout="numpy==2.3.3\npip==25.0\n")
        if sub == "run":
            self.smoke_timeout_arg = timeout
            if self.smoke_timeout:
                return dict(ok, returncode=None, timed_out=True, seconds=timeout, stdout="partial")
            return dict(ok, returncode=self.smoke_rc, stdout="SMOKE OK\n" + "x" * 70000, stderr="")
        if sub == "rm":
            return ok
        if sub == "ps":
            return dict(ok, stdout="deadbeef\n" if self.leftover else "")
        raise AssertionError("unexpected docker call %r" % argv)

    def smoke_argv(self):
        return next(c for c in self.calls if c[1] == "run" and "pip" not in c)


class BaseTests(unittest.TestCase):
    def test_base_pinning_and_rejection(self):
        r = fr.check_base("FROM python:3.12-slim\nRUN true\n")
        self.assertTrue(r["ok"])
        self.assertFalse(r["pinned"])
        self.assertIn("FROM " + fr.BASE_REF + "\n", r["locked_text"])
        self.assertTrue(fr.check_base("FROM " + fr.BASE_REF + "\n")["pinned"])
        for bad in ("FROM python:3.11-slim\n", "FROM ubuntu:24.04\n", "FROM python:3.12-slim AS b\n",
                    "FROM python:3.12-slim@sha256:" + "0" * 64 + "\n",
                    "FROM python:3.12-slim\nFROM python:3.12-slim\n", "RUN true\n"):
            self.assertEqual(fr.check_base(bad)["reason"], "unsupported_base", bad)

    def test_unsupported_base_is_not_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp, dockerfile="FROM ubuntu:24.04\nRUN true\n")
            docker = FakeDocker()
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=docker)
            self.assertEqual(rec["status"], "failed")
            self.assertIn("unsupported_base", rec["reasons"])
            self.assertFalse(any(c[1] == "build" for c in docker.calls))
            self.assertEqual(read_json(Path(tmp) / "rt/runtime_record.json")["status"], "failed")

    def test_build_context_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            (out / "environment/image/answer.json").write_text("{}")
            docker = FakeDocker()
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=docker)
            self.assertEqual(rec["status"], "failed")
            self.assertTrue(rec["reasons"][0].startswith("environment_invalid"))
            self.assertEqual(docker.calls, [])

    def test_passing_run_command_construction(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            before = {p: sha(p) for p in out.rglob("*") if p.is_file()}
            docker = FakeDocker()
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=docker)
            self.assertEqual(rec["status"], "passed", rec["reasons"])
            self.assertEqual({p: sha(p) for p in out.rglob("*") if p.is_file()}, before)
            build = next(c for c in docker.calls if c[1] == "build")
            ctx = Path(build[-1])
            self.assertEqual(sorted(p.name for p in ctx.iterdir()),
                             ["Dockerfile", "Dockerfile.controller_locked", "requirements.txt"])
            self.assertIn(fr.BASE_REF, (ctx / "Dockerfile.controller_locked").read_text())
            self.assertTrue(rec["image"]["tag"].startswith("mrhbench-factory/p1:"))
            self.assertEqual(len(rec["image"]["tag"].split(":")[1]), 12)
            self.assertEqual(rec["image"]["id"], IMAGE_ID)
            self.assertIn("numpy==2.3.3", rec["image"]["pip_freeze"])
            argv = docker.smoke_argv()
            joined = " ".join(argv)
            for flag in ("--network none", "--read-only", "--user 10001:10001", "--cap-drop ALL",
                         "--security-opt no-new-privileges", "--cpus 2", "--memory 2048m", "--pids-limit 128",
                         "--workdir /work", "--entrypoint python"):
                self.assertIn(flag, joined)
            disk = 512 * 1024 * 1024
            self.assertIn("/work:rw,nosuid,nodev,size=%d,uid=10001,gid=10001,mode=0700" % (disk - disk // 5), argv)
            self.assertIn("/tmp:rw,nosuid,nodev,size=%d,uid=10001,gid=10001,mode=0700" % (disk // 5), argv)
            mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
            self.assertEqual(len(mounts), 2)
            self.assertTrue(all(m.endswith(",readonly") for m in mounts))
            self.assertTrue(any("dst=/inputs/public," in m for m in mounts))
            self.assertTrue(any("dst=/smoke/smoke.py," in m for m in mounts))
            self.assertEqual(argv[argv.index(IMAGE_ID):], [IMAGE_ID, "-B", "/smoke/smoke.py"])
            view = Path(tmp) / "rt/public_view"
            files = sorted(p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_file())
            self.assertEqual(files, ["assets/data.csv", "assets/task.md"])
            self.assertNotIn("private", "".join(files))
            self.assertEqual(rec["smoke"]["public_mount"]["private_in_mount"], [])
            self.assertEqual(docker.smoke_timeout_arg, 900)
            self.assertLessEqual(Path(rec["smoke"]["stdout_path"]).stat().st_size, fr.CAPTURE_BYTES)
            self.assertTrue(rec["smoke"]["stdout_truncated"])
            name = rec["smoke"]["container_name"]
            self.assertIn(["docker", "rm", "-f", name], docker.calls)
            self.assertEqual(rec["model_calls"], 0)
            self.assertFalse(rec["leak_check"]["semantic_leakage_accepted"])

    def test_pinned_base_and_unique_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp, dockerfile="FROM %s\nRUN true\n" % fr.BASE_REF)
            d1, d2 = FakeDocker(), FakeDocker()
            r1 = fr.verify_runtime(out, pkg, Path(tmp) / "a", package_slug="p1", docker=d1)
            r2 = fr.verify_runtime(out, pkg, Path(tmp) / "b", package_slug="p1", docker=d2)
            self.assertTrue(r1["image"]["base_was_pinned_by_constructor"])
            self.assertNotEqual(r1["smoke"]["container_name"], r2["smoke"]["container_name"])
            self.assertEqual(r1["image"]["tag"], r2["image"]["tag"])
            with self.assertRaises(ProtocolError):
                fr.verify_runtime(out, pkg, Path(tmp) / "a", package_slug="p1", docker=FakeDocker())
            with self.assertRaises(ProtocolError):
                fr.verify_runtime(out, pkg, Path(tmp) / "c", package_slug="Bad/Slug", docker=FakeDocker())

    def test_timeout_kills_and_cleans(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            pkg["environment"]["resources"]["wall_seconds"] = 30
            write_json(out / "package.json", pkg)
            docker = FakeDocker(smoke_timeout=True)
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=docker)
            self.assertEqual(rec["status"], "failed")
            self.assertIn("smoke_timeout", rec["reasons"])
            self.assertEqual(docker.smoke_timeout_arg, 30)
            self.assertIn(["docker", "rm", "-f", rec["smoke"]["container_name"]], docker.calls)
            self.assertTrue(rec["smoke"]["cleanup"]["verified_absent"])

    def test_cleanup_failure_and_smoke_failure_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=FakeDocker(smoke_rc=1, leftover=True))
            self.assertIn("smoke_failed", rec["reasons"])
            self.assertTrue(any(r.startswith("container_cleanup_failed") for r in rec["reasons"]))

    def test_default_runner_timeout(self):
        res = fr.subprocess_docker([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
        self.assertTrue(res["timed_out"])
        self.assertIsNone(res["returncode"])


class LeakTests(unittest.TestCase):
    def test_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            r = fr.leak_check(out, pkg)
            self.assertEqual(r["hit_count"], 0)
            self.assertEqual(r["private_only_fact_ids"], ["PRIV-F2"])
            self.assertGreaterEqual(r["needle_count"], 2)

    def test_private_asset_sentence_detected_despite_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            leaked = "Intro.\n" + PRIVATE_SENTENCE.replace(" the ", "   the\n").upper() + "\n"
            out, pkg = make_package(tmp, public_text=leaked)
            r = fr.leak_check(out, pkg)
            self.assertGreater(r["hit_count"], 0)
            self.assertEqual(r["hits"][0]["file"], "assets/task.md")
            self.assertIn("private_asset:private/notes.md", r["hits"][0]["private_origins"])
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=FakeDocker())
            self.assertIn("string_leak_hits", rec["reasons"])

    def test_private_fact_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp, public_text="Background. " + PRIVATE_FACT + " PRIV-F2\n")
            r = fr.leak_check(out, pkg)
            self.assertTrue(any("private_only_fact:PRIV-F2" in h["private_origins"] for h in r["hits"]))
            self.assertEqual(r["informational_private_fact_id_mentions"], [{"fact_id": "PRIV-F2", "file": "assets/task.md"}])

    def test_hash_and_label_tokens_are_not_needles(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = "development_candidate_pending_independent_review " + "e" * 64
            out, pkg = make_package(tmp, public_text=token + "\n")
            notes = out / "private/notes.md"
            notes.write_text("# Notes\n" + PRIVATE_SENTENCE + "\n" + token + "\n", encoding="utf8")
            pkg["tasks"][0]["assets"][2]["sha256"] = sha(notes)
            r = fr.leak_check(out, pkg)
            self.assertEqual(r["hit_count"], 0)
            self.assertGreaterEqual(r["needles_excluded_as_non_prose"], 1)

    def test_short_overlap_is_not_a_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp, public_text="variance ratio stays below one\n")
            self.assertEqual(fr.leak_check(out, pkg)["hit_count"], 0)


def passed_record(tmp):
    out, pkg = make_package(tmp)
    rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=FakeDocker())
    return out, pkg, rec


class CompileTests(unittest.TestCase):
    def test_refuses_failed_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg = make_package(tmp)
            rec = fr.verify_runtime(out, pkg, Path(tmp) / "rt", package_slug="p1", docker=FakeDocker(smoke_rc=3))
            with self.assertRaisesRegex(ProtocolError, "not passed"):
                fr.compile_tasks(out, pkg, rec, Path(tmp) / "compiled", package_slug="p1")
            self.assertFalse((Path(tmp) / "compiled").exists())

    def test_refuses_changed_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg, rec = passed_record(tmp)
            pkg2 = dict(pkg, paper_id="p1")
            pkg2["facts"] = pkg["facts"][:1] + pkg["facts"][1:]
            rec2 = dict(rec, package_digest="0" * 64)
            with self.assertRaisesRegex(ProtocolError, "changed"):
                fr.compile_tasks(out, pkg, rec2, Path(tmp) / "c", package_slug="p1")
            with self.assertRaisesRegex(ProtocolError, "slug"):
                fr.compile_tasks(out, pkg, rec, Path(tmp) / "c", package_slug="other")

    def test_compile_layout_and_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg, rec = passed_record(tmp)
            self.assertEqual(rec["status"], "passed", rec["reasons"])
            records = fr.compile_tasks(out, pkg, rec, Path(tmp) / "compiled", package_slug="p1",
                                       compose_fact_statements=False)
            self.assertEqual([r["task_id"] for r in records], ["p1-exp"])
            root = Path(tmp) / "compiled/p1-exp"
            task = read_json(root / "task.json")
            self.assertTrue((root / "collection_contract_provenance.json").is_file())
            self.assertTrue(all(g["status"] == "pending" for g in task["gates"].values()))
            private = [a for a in task["assets"] if a["visibility"] == "private"]
            self.assertTrue(all(a["path"].startswith("private/") for a in private))
            self.assertEqual({a["path"] for a in private}, {"private/notes.md", "private/reference.json"})
            public_ids = set(task["public"]["inputs"])
            self.assertFalse(public_ids & {a["asset_id"] for a in private})
            self.assertNotIn(PRIVATE_FACT, task["public"]["prompt"])
            self.assertNotIn("baseline estimator", task["public"]["prompt"])
            self.assertIn("Controller publication notes", task["public"]["prompt"])
            self.assertEqual(task["public"]["resources"]["image_id"], IMAGE_ID)
            self.assertEqual(task["public"]["resources"]["execution_budget"],
                             {"model_calls": 16, "tool_calls": 120, "wall_seconds": 1200})
            self.assertFalse(task["private"]["formal_eligible"])
            for a in task["assets"]:
                self.assertEqual(file_hash(root / a["path"]), a["sha256"])
            self.assertTrue((Path(tmp) / "compiled/compile_record.json").is_file())

    def test_compose_facts_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pkg, rec = passed_record(tmp)
            fr.compile_tasks(out, pkg, rec, Path(tmp) / "compiled", package_slug="p1")
            task = read_json(Path(tmp) / "compiled/p1-exp/task.json")
            self.assertIn("baseline estimator", task["public"]["prompt"])
            self.assertNotIn(PRIVATE_FACT, task["public"]["prompt"])


class DossierTests(unittest.TestCase):
    def _paper(self, tmp):
        paper = Path(tmp) / "paper"
        (paper / "art").mkdir(parents=True)
        write_json(paper / "art/audit.json", {"ambiguities": [{"id": "A1", "issue": "Eq5 normalisation"}]})
        write_json(paper / "art/adj.json", {"decisions": [{"id": "A1", "decision": "accepted", "reason": "match code"},
                                                          {"id": "A2", "accepted": False, "rationale": "not needed"}]})
        write_json(paper / "art/review.json", {"decision": "revise", "findings": [
            {"finding_id": "R1", "severity": "major", "observed_issue": "H3 near-automatic"}]})
        write_json(paper / "art/pilot.json", {"task_id": "t", "status": "scored",
                                              "judgment": {"dimension_scores": {"rigor": 3}}})
        state = {"schema_version": "factory-paper-state-1", "project_id": "proj-1", "title": "T",
                 "stages": {"source_audit": {"status": "done", "artifacts": {"audit": "art/audit.json"},
                                             "calls": [], "finished_at": "2026-09-24T01:00:00", "notes": []},
                            "adjudication": {"status": "done", "artifacts": {"adj": "art/adj.json"}, "calls": [],
                                             "finished_at": "2026-09-24T02:00:00", "notes": ["root"]},
                            "construct": {"status": "done", "artifacts": {"review": "art/review.json"}, "calls": [401],
                                       "finished_at": "2026-09-24T03:00:00", "notes": []},
                            "runtime": {"status": "done", "artifacts": {"record": "art/missing_runtime.json"},
                                        "calls": [], "finished_at": "2026-09-24T04:00:00", "notes": []},
                            "pilot": {"status": "done", "artifacts": {"j": "art/pilot.json"}, "calls": [402],
                                      "finished_at": "2026-09-24T05:00:00", "notes": []}},
                 "flags": []}
        write_json(paper / "state.json", state)
        return paper

    def test_dossier_with_missing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            paper = self._paper(tmp)
            path = fr.build_dossier(paper)
            d = read_json(path)
            self.assertTrue((paper / "dossier/dossier.md").is_file())
            by = {e["stage"]: e for e in d["stages"]}
            self.assertEqual(by["source_audit"]["extracted"]["audit"]["ambiguities"][0]["issue"], "Eq5 normalisation")
            decisions = by["adjudication"]["extracted"]["adj"]["decisions"]
            self.assertEqual([x["decision"] for x in decisions], ["accepted", "rejected"])
            self.assertEqual(decisions[1]["reason"], "not needed")
            self.assertEqual(by["construct"]["extracted"]["review"]["findings"][0]["severity"], "major")
            self.assertFalse(by["runtime"]["artifacts"]["record"]["present"])
            self.assertEqual(by["runtime"]["extracted"], {})
            self.assertIn("artifact_missing:runtime/record", d["derived_flags"])
            self.assertEqual(by["pilot"]["extracted"]["j"]["pilot"][0]["dimension_scores"], {"rigor": 3})
            self.assertIn("compile", d["stages_absent"])
            self.assertEqual(d["completed_at"], "2026-09-24T05:00:00")
            self.assertIn("MISSING", (paper / "dossier/dossier.md").read_text(encoding="utf8"))

    def test_review_selection_deterministic(self):
        dossiers = [{"project_id": "p%02d" % i, "completed_at": "2026-09-%02dT00:00:00" % (i + 1),
                     "flags": ["odd"] if i == 15 else [], "derived_flags": []} for i in range(30)]
        a = fr.select_for_final_review(dossiers, seed="s1")
        b = fr.select_for_final_review(list(reversed(dossiers)), seed="s1")
        self.assertEqual(a, b)
        ids = [x["project_id"] for x in a]
        self.assertEqual(ids[:10], ["p%02d" % i for i in range(10)])
        self.assertIn("p15", ids)
        self.assertTrue(next(x for x in a if x["project_id"] == "p15")["reason"].startswith("flagged"))
        for x in a[10:]:
            if x["reason"].startswith("seeded"):
                u = int(hashlib.sha256(("s1" + x["project_id"]).encode()).hexdigest()[:16], 16) / 2 ** 64
                self.assertLess(u, 0.2)
        everything = fr.select_for_final_review(dossiers, seed="s1", sample_rate=1.0)
        self.assertEqual(len(everything), 30)
        none_sampled = fr.select_for_final_review(dossiers, seed="s1", sample_rate=0.0)
        self.assertEqual([x["project_id"] for x in none_sampled], ids[:10] + ["p15"])
        with self.assertRaises(ProtocolError):
            fr.select_for_final_review(dossiers + dossiers[:1], seed="s1")


if __name__ == "__main__":
    unittest.main()
