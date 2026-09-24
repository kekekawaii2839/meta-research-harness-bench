"""Offline controller for round identities, full-search gating and immutable snapshots.

Not a sandbox: the controller store must not be writable/readable by builder workers.
"""
from __future__ import annotations

from pathlib import Path
import shutil

from .io import ProtocolError, contained, digest, file_hash, read_json, write_json, TraceLog
from .materials import validate_split
from .scoring import aggregate, version_summary


class EvolutionRun:
    def __init__(self, root: Path):
        self.root = root
        self.state_path = root / "controller.json"
        self.trace = TraceLog(root / "platform_events.jsonl")

    @classmethod
    def create(cls, root: Path, tasks: list[dict], rounds: int, *, development: bool = True):
        if root.exists() or isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
            raise ProtocolError("New run needs a fresh root and positive round count")
        validate_split(tasks)
        if {t["split"] for t in tasks} != {"search", "test"}:
            raise ProtocolError("Run needs separate nonempty search and test manifests")
        # Formal execution requires a separate verified process/container runner.
        if not development:
            raise ProtocolError("Formal OS isolation adapter has not been accepted")
        root.mkdir(parents=True)
        run = cls(root)
        state = {"schema_version": "0.1", "round_limit": rounds, "development": True, "tasks": tasks,
                 "manifest_hash": digest(tasks), "versions": [], "search_done": [], "feedback_done": [], "test_done": [], "builder_selected": None}
        write_json(run.state_path, state, exclusive=True)
        run.trace.append("run_created", {"manifest_hash": state["manifest_hash"], "round_limit": rounds, "development": True})
        return run

    def _state(self):
        state = read_json(self.state_path)
        if state["manifest_hash"] != digest(state["tasks"]):
            raise ProtocolError("Frozen task manifest changed")
        return state

    def _save(self, state):
        write_json(self.state_path, state)

    def submit(self, harness: Path, *, note: str = "") -> str:
        state = self._state()
        r = len(state["versions"])
        if r > state["round_limit"] or state["builder_selected"] is not None:
            raise ProtocolError("Submission window closed")
        if r and f"H{r-1}" not in state["search_done"]:
            raise ProtocolError("Previous checkpoint needs full search evaluation first")
        if r and f"H{r-1}" not in state["feedback_done"]:
            raise ProtocolError("Previous checkpoint needs complete public-only search feedback first")
        harness = harness.resolve(strict=True)
        if self.root.resolve().is_relative_to(harness):
            raise ProtocolError("Cannot snapshot controller/private workspace as harness")
        files = []
        for p in sorted(harness.rglob("*")):
            name = p.relative_to(harness).as_posix()
            checked = contained(harness, name, must_exist=True)
            if checked.is_file():
                files.append({"path": name, "sha256": file_hash(checked)})
        if not files:
            raise ProtocolError("Empty harness snapshot")
        version = f"H{r}"
        dest = self.root / "snapshots" / version
        if dest.exists():
            raise ProtocolError("Snapshot path already exists")
        dest.mkdir(parents=True)
        for record in files:
            source = contained(harness, record["path"], must_exist=True)
            target = contained(dest, record["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if file_hash(target) != record["sha256"]:
                raise ProtocolError("Harness changed during freeze")
        state["versions"].append({"version_id": version, "round": r, "files": files, "hash": digest(files), "note": note})
        self._save(state)
        self.trace.append("checkpoint_frozen", {"version_id": version, "hash": digest(files)})
        return version

    def verify_snapshot(self, version: str) -> dict:
        state = self._state()
        record = next((v for v in state["versions"] if v["version_id"] == version), None)
        if record is None:
            raise ProtocolError("Unknown version")
        root = self.root / "snapshots" / version
        actual = []
        for p in sorted(root.rglob("*")):
            checked = contained(root, p.relative_to(root).as_posix(), must_exist=True)
            if checked.is_file():
                actual.append({"path": p.relative_to(root).as_posix(), "sha256": file_hash(p)})
        if actual != record["files"] or digest(actual) != record["hash"]:
            raise ProtocolError("Frozen harness mutated")
        return record

    def record_evaluation(self, version: str, split: str, results: list[dict]) -> dict:
        state = self._state()
        self.verify_snapshot(version)
        if split not in ("search", "test") or version in state[split + "_done"]:
            raise ProtocolError("Evaluation already recorded or invalid split")
        if split == "test" and state["builder_selected"] is None:
            raise ProtocolError("This offline implementation evaluates test only AFTER builder selection freezes")
        tasks = [t for t in state["tasks"] if t["split"] == split]
        scores = aggregate(tasks, results)
        destination = self.root / ("private_test" if split == "test" else "search_scores") / (version + ".json")
        write_json(destination, {"version_id": version, "split": split, "results": results, "aggregate": scores}, exclusive=True)
        state[split + "_done"].append(version)
        self._save(state)
        self.trace.append("evaluation_recorded", {"version_id": version, "split": split, "artifact_hash": file_hash(destination)})
        return scores

    def publish_search_feedback(self, version: str, feedback_results: list[dict]) -> None:
        """Trusted controller publishes only validated feedback result projections.

        The caller must have completed task-specific trajectory acceptance before
        formal use. This controller remains development-only; field whitelisting
        is not a proof of semantic nonleakage.
        """
        state = self._state()
        if version not in state["search_done"] or version in state["feedback_done"] or state["builder_selected"] is not None:
            raise ProtocolError("Search feedback requires one unselected, fully evaluated checkpoint")
        tasks = {t["task_id"]: t for t in state["tasks"] if t["split"] == "search"}
        if len(feedback_results) != len(tasks) or {r.get("task_id") for r in feedback_results} != set(tasks):
            raise ProtocolError("Feedback must cover exactly the entire search set")
        released = []
        for row in feedback_results:
            # Do not take a whole score object and redact it heuristically.
            required = {"task_id", "task_type", "mode", "feedback", "public_evidence_inventory_hash"}
            optional = {"acceptance_status", "formal_scientific_score", "model_steps", "validation_scope"}
            if not required.issubset(row) or not set(row).issubset(required | optional) or row["mode"] != "feedback" or row["task_type"] != tasks[row["task_id"]]["task_type"]:
                raise ProtocolError("Only public feedback outputs, not private score records, may be published")
            feedback = row["feedback"]
            if not isinstance(feedback, dict) or set(feedback) != {"issues", "limitations"} or not isinstance(feedback["issues"], list) or not isinstance(feedback["limitations"], list):
                raise ProtocolError("Malformed feedback output")
            released.append({k: row[k] for k in ("task_id", "task_type", "feedback", "public_evidence_inventory_hash")})
        path = self.root/"builder_feedback"/(version + ".json")
        write_json(path, released, exclusive=True)
        state["feedback_done"].append(version)
        self._save(state)
        self.trace.append("search_feedback_published", {"version_id": version, "artifact_hash": file_hash(path)})

    def builder_view(self) -> dict:
        state = self._state()
        if not state["versions"]:
            return {"phase": "build_h0", "search_tasks": [], "versions": [], "search_scores": {}}
        return {"phase": "search", "search_tasks": [t["task_id"] for t in state["tasks"] if t["split"] == "search"],
                "versions": [{"version_id": v["version_id"], "hash": v["hash"]} for v in state["versions"]],
                "search_feedback": {v: read_json(self.root/"builder_feedback"/(v+".json")) for v in state["feedback_done"]},
                "search_scores": {v: {k: value for k, value in read_json(self.root / "search_scores" / (v + ".json"))["aggregate"].items()
                                      if k != "paper_scores"} for v in state["search_done"]}}

    def select(self, version: str, reason: str) -> None:
        state = self._state()
        if len(state["versions"]) != state["round_limit"] + 1 or len(state["search_done"]) != len(state["versions"]):
            raise ProtocolError("Complete configured rounds and search evaluations before selection")
        if set(state["feedback_done"]) != set(state["search_done"]):
            raise ProtocolError("Complete public search feedback before builder version selection")
        if state["builder_selected"] is not None or version not in state["search_done"] or not reason.strip():
            raise ProtocolError("Selection must be valid, justified and frozen once")
        state["builder_selected"] = version
        state["selection_reason"] = reason
        self._save(state)
        self.trace.append("builder_selection_frozen", {"version_id": version, "reason": reason})

    def summary(self) -> dict:
        state = self._state()
        if state["builder_selected"] is None or set(state["test_done"]) != {v["version_id"] for v in state["versions"]}:
            raise ProtocolError("Every checkpoint test evaluation is required")
        rows = []
        for v in state["versions"]:
            result = read_json(self.root / "private_test" / (v["version_id"] + ".json"))
            search = read_json(self.root / "search_scores" / (v["version_id"] + ".json"))
            rows.append({"version_id": v["version_id"], "round": v["round"], "harness_hash": v["hash"],
                         "test_total_quality": result["aggregate"]["total_quality"],
                         "test_module_scores": result["aggregate"]["module_scores"],
                         "search_total_quality": search["aggregate"]["total_quality"]})
        return version_summary(rows, state["builder_selected"])
