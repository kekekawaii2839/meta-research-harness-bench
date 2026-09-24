"""Synthetic runners exercise publication boundaries without paid model calls."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import ProtocolError, file_hash, read_json, write_json
from mrhbench.material_batch import run_batch


class MaterialInputIntegrityTests(unittest.TestCase):
    def test_draft_proposal_rejected_before_any_batch_work(self):
        proposal = read_json(ROOT / "materials/next_batch_proposals_v1/jobs/ftct.json")
        approved = read_json(ROOT / "materials/pilot_v2/jobs/ssa.json")
        for jobs in ([proposal], [approved, proposal]):
            with self.subTest(jobs=len(jobs)), tempfile.TemporaryDirectory() as tmp:
                batch = Path(tmp) / "batch"
                with self.assertRaisesRegex(ProtocolError, "Unselected material proposal"):
                    run_batch(jobs, workspace=ROOT.parents[1], batch_root=batch, templates=ROOT / "prompts",
                              constructor=None, reviewer=None, max_workers=2)
                self.assertFalse(batch.exists())

    def run_case(self, root, *, constructor_mutation=None, reviewer_mutation=None, repair_from=None, repeat=False):
        source = root / "paper.txt"
        source.write_text("Synthetic source; not a scientific benchmark.", encoding="utf8")
        resources = dict(cpus=1, memory_mb=128, disk_mb=128, pids_limit=32, wall_seconds=60)
        job = dict(schema_version="material-job-1", job_id="fixture", paper_id="p",
                   requested_task_types=["EXP"], scope_request="Synthetic fixture", first_disclosure={},
                   environment_candidate=dict(gpu=False, network="none", scientific_rationale="Fixture", **resources),
                   sources=[dict(source_id="s", url="https://example.invalid/p", version="v1",
                                 local_path="paper.txt", sha256=file_hash(source), role="paper_text")])
        class Constructor:
            count = 0
            def run(self, *, workspace, **kwargs):
                self.count += 1
                out = workspace / "output"
                (out / "environment/image").mkdir(parents=True)
                (out / "environment/image/Dockerfile").write_text("FROM python:3.12-slim\n")
                (out / "environment/smoke.py").write_text("assert True\n")
                package = dict(schema_version="material-package-1", status="candidate", paper_id="p",
                    facts=[dict(fact_id="f", kind="maintainer_scope", statement="Fixture",
                                allowed_stages=["EXP"])],
                    coverage=[dict(task_type=t, status="candidate" if t == "EXP" else "deferred", reason="Fixture")
                              for t in ["LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE"]],
                    tasks=[dict(task_id="t", paper_id="p", split="development", task_type="EXP",
                                input_fact_ids=["f"], input_contract={"description":"Fixture"},
                                output_contract={"description":"Fixture"}, verification_plan={"pending":True})],
                    environment=dict(gpu=False, network="none", runtime_verified=False, dependencies=[],
                                     scientific_rationale="Fixture", resources=resources))
                write_json(out / "package.json", package)
                (workspace / "runtime-log.txt").write_text("Permitted new run log")
                if constructor_mutation:
                    constructor_mutation(workspace)
                return {"status":"completed"}
        class Reviewer:
            count = 0
            def run(self, *, workspace, **kwargs):
                self.count += 1
                write_json(workspace / "review.json", dict(schema_version="material-review-1", paper_id="p",
                                                           decision="pass_with_pending_runtime"))
                if reviewer_mutation:
                    reviewer_mutation(workspace)
                return {"status":"completed"}
        constructor, reviewer = Constructor(), Reviewer()
        options=dict(workspace=root, batch_root=root / "batch", templates=ROOT / "prompts",
                     constructor=constructor, reviewer=reviewer, repair_from=repair_from)
        result = run_batch([job], **options)
        if repeat:
            receipt=root/'batch/fixture/receipt.json'
            frozen=receipt.read_bytes()
            counts=(constructor.count,reviewer.count)
            resumed=run_batch([job],**options)
            self.assertEqual(resumed,result)
            self.assertEqual((constructor.count,reviewer.count),counts)
            self.assertEqual(receipt.read_bytes(),frozen)
        return result["jobs"][0], constructor, reviewer

    def test_clean_outputs_and_logs_allowed_and_inputs_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, constructor, reviewer = self.run_case(Path(tmp))
            self.assertEqual(row["status"], "pass_with_pending_runtime")
            self.assertFalse(row["formal_accepted"])
            self.assertEqual((constructor.count, reviewer.count), (1, 1))
            self.assertIn("material_package.schema.json", row["constructor_input_snapshot"])
            self.assertIn("request.json", row["reviewer_input_snapshot"])
            self.assertIn("structural_check.json", row["reviewer_input_snapshot"])

    def test_constructor_input_changes_stop_before_review(self):
        def added_navigation(workspace):
            (workspace / "source_navigation").mkdir(exist_ok=True)
            (workspace / "source_navigation/forged.json").write_text("{}")
        mutations = [
            lambda w: (w / "material_package.schema.json").write_text("{}"),
            lambda w: (w / "material_constructor.txt").unlink(),
            lambda w: (w / "publication.json").write_text("{}"),
            added_navigation,
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                row, _, reviewer = self.run_case(Path(tmp), constructor_mutation=mutation)
                self.assertEqual(row["status"], "failed_needs_attribution")
                self.assertIn("Constructor altered", row["error"]["message"])
                self.assertEqual(reviewer.count, 0)

    def test_reviewer_cannot_rewrite_request_prompt_or_structural_gate(self):
        for name in ["request.json", "material_reviewer.txt", "structural_check.json", "output/package.json"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                row, _, reviewer = self.run_case(Path(tmp),
                    reviewer_mutation=lambda w: (w / name).write_text("{}"))
                self.assertEqual(row["status"], "failed_needs_attribution")
                self.assertIn("Reviewer altered", row["error"]["message"])
                self.assertEqual(reviewer.count, 1)
                self.assertFalse(row["formal_accepted"])

    def test_success_and_integrity_failure_resume_do_not_reinvoke(self):
        for mutation in (None, lambda w:(w/'material_constructor.txt').write_text('changed')):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                row,constructor,reviewer=self.run_case(Path(tmp),constructor_mutation=mutation,repeat=True)
                self.assertEqual(constructor.count,1)
                self.assertEqual(reviewer.count,0 if mutation else 1)
                self.assertEqual(row['status'],'failed_needs_attribution' if mutation else 'pass_with_pending_runtime')

    def test_repair_inputs_protected_without_editing_prior_candidate(self):
        for name in ('repair_request.json','previous_candidate/prior.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);prior=root/'prior'
                artifact=prior/'fixture/constructor/output/prior.json'
                write_json(artifact,{'synthetic_prior_candidate':True})
                before=artifact.read_bytes()
                row,_,reviewer=self.run_case(root,repair_from=prior,
                    constructor_mutation=lambda w:(w/name).write_text('{}'),repeat=True)
                self.assertEqual(row['status'],'failed_needs_attribution')
                self.assertIn('Constructor altered',row['error']['message'])
                self.assertEqual(reviewer.count,0)
                self.assertEqual(artifact.read_bytes(),before)

    def test_deleted_source_and_added_reviewer_output_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            row,_,reviewer=self.run_case(Path(tmp),constructor_mutation=lambda w:next((w/'sources').iterdir()).unlink())
            self.assertEqual(row['status'],'failed_needs_attribution');self.assertEqual(reviewer.count,0)
        with tempfile.TemporaryDirectory() as tmp:
            row,_,_=self.run_case(Path(tmp),reviewer_mutation=lambda w:(w/'output/injected.txt').write_text('new file'))
            self.assertEqual(row['status'],'failed_needs_attribution')
            self.assertIn('Reviewer altered',row['error']['message'])


if __name__ == "__main__":
    unittest.main()
