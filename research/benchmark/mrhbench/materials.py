"""Material checks and explicit public-view exports. Not an execution sandbox."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil

from .io import ProtocolError, contained, digest, file_hash, read_json, relative_path, write_json
from .scoring import TASK_TYPES

TASK_GATES = ("source_semantics", "rights", "input_leakage", "runtime", "judge_behavior")
PUBLIC_FIELDS = {"task_id", "task_type", "prompt", "inputs", "output_contract", "resources", "tools", "public_rubric"}


def check_task(task: dict, root: Path, *, formal: bool = False) -> list[str]:
    required = {"schema_version", "task_id", "task_type", "paper_id", "split", "public", "private", "assets", "gates"}
    if not required.issubset(task) or task["schema_version"] != "0.1":
        raise ProtocolError("Incomplete task manifest")
    for key in ("task_id", "paper_id"):
        if not isinstance(task[key], str) or not task[key]:
            raise ProtocolError("Task and source-paper IDs must be nonempty")
    if task["task_type"] not in TASK_TYPES or task["split"] not in ("development", "search", "test"):
        raise ProtocolError("Unknown task type/split")
    public = task["public"]
    if set(public) != PUBLIC_FIELDS or public["task_id"] != task["task_id"] or public["task_type"] != task["task_type"]:
        raise ProtocolError("Public task view violates explicit field contract")
    if not isinstance(public["prompt"], str) or not public["prompt"].strip():
        raise ProtocolError("Task requires a substantive prompt")
    names, ids = set(), set()
    for asset in task["assets"]:
        relative_path(asset["path"])
        if asset["path"].casefold() in names or asset["asset_id"] in ids:
            raise ProtocolError("Duplicate asset identity/path (case-insensitive)")
        names.add(asset["path"].casefold())
        ids.add(asset["asset_id"])
        if asset["visibility"] not in ("public", "private"):
            raise ProtocolError("Unknown asset visibility")
        p = contained(root, asset["path"], must_exist=True)
        if not p.is_file() or file_hash(p) != asset["sha256"]:
            raise ProtocolError("Missing or mutated asset")
    public_ids = {a["asset_id"] for a in task["assets"] if a["visibility"] == "public"}
    if not isinstance(public["inputs"], list) or set(public["inputs"]) != public_ids:
        raise ProtocolError("Public inputs must exactly enumerate public assets")
    gates = task["gates"]
    if set(gates) != set(TASK_GATES):
        raise ProtocolError("All material/runtime/judge gates must be explicitly recorded")
    incomplete = [k for k in TASK_GATES if gates[k].get("status") != "passed"]
    for name, gate in gates.items():
        if gate.get("status") not in ("passed", "pending", "blocked", "not_applicable") or not gate.get("evidence"):
            raise ProtocolError(f"Gate {name} needs status and evidence/reason")
    if formal and (task["split"] == "development" or incomplete):
        raise ProtocolError("Task not accepted for formal runs: " + ", ".join(incomplete))
    return incomplete


def validate_split(tasks: list[dict]) -> None:
    papers, ids = {}, set()
    for task in tasks:
        if task["task_id"] in ids:
            raise ProtocolError("Duplicate task ID")
        ids.add(task["task_id"])
        paper = task["paper_id"]
        if paper in papers and papers[paper] != task["split"]:
            raise ProtocolError("Source paper spans splits")
        papers[paper] = task["split"]


def export_task(task: dict, asset_root: Path, destination: Path, *, audience: str, formal: bool = False) -> dict:
    pending = check_task(task, asset_root, formal=formal)
    if audience not in ("development_executor", "search_executor", "hidden_executor"):
        raise ProtocolError("Export audience must be an executor role")
    expected = {"development_executor": "development", "search_executor": "search", "hidden_executor": "test"}
    if task["split"] != expected[audience]:
        raise ProtocolError("Audience cannot access this split")
    if destination.exists():
        raise ProtocolError("Export needs a new directory; no residual private files allowed")
    # Validate everything before writing any publication bytes.
    sources = [(a, contained(asset_root, a["path"], must_exist=True)) for a in task["assets"] if a["visibility"] == "public"]
    destination.mkdir(parents=True)
    releases = []
    for asset, source in sources:
        target = contained(destination, "assets/" + asset["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if file_hash(target) != asset["sha256"]:
            raise ProtocolError("Asset changed during export")
        releases.append({"asset_id": asset["asset_id"], "path": "assets/" + asset["path"], "sha256": asset["sha256"]})
    view = dict(task["public"])
    view["asset_manifest"] = releases
    view["release_mode"] = "formal" if formal else "development_not_formal_acceptance"
    write_json(destination / "task.json", view, exclusive=True)
    return {"task_id": task["task_id"], "public_view_hash": digest(view), "pending_gates": pending,
            "private_assets_exported": 0, "os_isolation_verified": False}


class FrozenCorpus:
    """Read/search enforce the same historical view BEFORE ranking or snippet creation.

    Caller must prevent independent HTTP/filesystem access separately. This class does
    not claim to remove model memory or supply a production search index.
    """
    def __init__(self, documents: list[dict], cutoff: str, excluded_papers: set[str]):
        limit = date.fromisoformat(cutoff)
        self.docs = {}
        seen = set()
        for doc in documents:
            if doc["document_id"] in seen:
                raise ProtocolError("Duplicate corpus document IDs")
            seen.add(doc["document_id"])
            if not doc.get("version") or not doc.get("source_url") or not doc.get("published_evidence"):
                raise ProtocolError("Corpus needs pinned version and publication evidence")
            published = date.fromisoformat(doc["published_date"])
            if published > limit or doc["paper_id"] in excluded_papers:
                continue
            # Maintenance metadata (local paths, private notes, selection reasons)
            # must not leak through read(). Snapshot only documented public fields.
            fields = ("document_id", "paper_id", "title", "version", "source_url", "published_date", "text")
            self.docs[doc["document_id"]] = {key: doc[key] for key in fields}

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not isinstance(query, str) or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ProtocolError("Invalid search request")
        words = set(query.lower().split())
        hits = []
        for key, doc in self.docs.items():
            text = doc["title"] + "\n" + doc["text"]
            score = sum(text.lower().count(word) for word in words)
            if score:
                hits.append((score, key, {"document_id": key, "title": doc["title"], "version": doc["version"],
                                          "snippet": doc["text"][:500]}))
        return [x[2] for x in sorted(hits, key=lambda x: (-x[0], x[1]))[:limit]]

    def read(self, document_id: str) -> dict:
        if document_id not in self.docs:
            raise ProtocolError("Document not available in this task view")
        return dict(self.docs[document_id])


def load_task(path: Path, *, formal: bool = False) -> dict:
    task = read_json(path)
    check_task(task, path.parent, formal=formal)
    return task
