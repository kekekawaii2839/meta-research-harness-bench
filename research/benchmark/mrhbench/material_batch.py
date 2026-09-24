"""Bounded resumable native construction scheduling, without an internal agent loop.

One OS controller owns a batch (exclusive file lock). Interrupted invocations are
not silently retried. Each fresh attempt has its own workspace and receipt; native
transport owns the shared call ledger and real usage accounting.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .io import ProtocolError, contained, digest, file_hash, read_json, write_json
from .material_pipeline import prepare_material_job, prepare_review, validate_package, stage_repair_candidate


def _input_snapshot(root, names):
    """Hash controller-published inputs, including directory file membership.

    This is a post-run integrity gate, not filesystem access prevention. Keep
    the expected snapshot in controller memory; never trust an agent's manifest.
    Runtime logs and the role's permitted new outputs are deliberately excluded.
    """
    files = {}
    for name in names:
        path = contained(root, name)
        if path.is_file():
            files[name] = file_hash(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                rel = child.relative_to(root).as_posix()
                checked = contained(root, rel)
                if checked.is_file():
                    files[rel] = file_hash(checked)
    return files


def _check_inputs(root, names, expected, role):
    if _input_snapshot(root, names) != expected:
        raise ProtocolError(role + " altered controller-published inputs")


CONTROLLER_FILL = "CONTROLLER_FILL"
# Appended to the constructor prompt for file-tool-only (no shell) constructors.
MATERIAL_PROMPT_SUFFIX = (
    "\nThis session has file tools only and cannot execute code. For every sha256 of a file you write, put the literal "
    "string CONTROLLER_FILL; the trusted controller computes those hashes from the final bytes after you finish. "
    "Do not write helper scripts for hashing.\n")


def fill_sentinel_hashes(output_root, sentinels=(CONTROLLER_FILL,)):
    """Trusted controller hashing for constructors without code execution (AGENTS §0.2.13).

    Replaces only sentinel sha256 values of {path, sha256} entries with the actual
    bytes' hash, keeps the constructor's original package.json, and records every
    fill. Constructor-written helper code is never executed.
    """
    output_root = Path(output_root)
    package_path = output_root / "package.json"
    original = package_path.read_bytes()
    package = read_json(package_path)
    fills = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("sha256") in sentinels and isinstance(node.get("path"), str):
                target = contained(output_root, node["path"], must_exist=True)
                if not target.is_file():
                    raise ProtocolError("Sentinel hash names a missing file")
                fills.append({"path": node["path"], "sentinel": node["sha256"], "sha256": file_hash(target)})
                node["sha256"] = fills[-1]["sha256"]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(package)
    if fills:
        (output_root / "package.constructor_original.json").write_bytes(original)
        write_json(package_path, package)
    record = {"controller_hash_fill": True, "fills": fills, "original_package_sha256": digest_bytes(original),
              "filled_package_sha256": file_hash(package_path), "constructor_code_executed": False}
    return record


def digest_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run_batch(jobs, *, workspace, batch_root, templates, constructor, reviewer,
              max_workers=1, max_jobs=2, repair_from=None, repair_notes=None,
              controller_hash_fill=False, prompt_suffix=""):
    """constructor/reviewer expose native runner .run(...); injected for testing."""
    if not 1 <= max_workers <= 4 or not 1 <= max_jobs <= 20 or len(jobs) > max_jobs:
        raise ProtocolError("Batch exceeds explicit bounded pilot settings")
    if len({j["job_id"] for j in jobs}) != len(jobs):
        raise ProtocolError("Duplicate batch job")
    # Preparation accepts draft proposals; execution must not mistake an
    # explicitly unselected draft for permission to spend model calls. Check the
    # whole batch before launching any worker, including otherwise ready jobs.
    # Legacy approved pilot jobs lack these fields; this is not a general
    # authentication or user-authorization mechanism.
    if any(j.get("selection_confirmed") is False or
           j.get("status") == "proposal_source_only_not_authorized_for_model_launch" for j in jobs):
        raise ProtocolError("Unselected material proposal: confirm strategy and create an approved job version before launch")
    if repair_notes is not None:
        if repair_from is None or not isinstance(repair_notes, dict):
            raise ProtocolError("Repair notes require an explicit prior batch and job mapping")
        if set(repair_notes) - {j["job_id"] for j in jobs}:
            raise ProtocolError("Repair notes reference a job outside this batch")
        if any(not isinstance(v, list) or any(not isinstance(x, str) or not x.strip() for x in v)
               for v in repair_notes.values()):
            raise ProtocolError("Repair notes must contain nonempty text items")
    batch_root = Path(batch_root)
    if repair_from is not None and batch_root.resolve() == Path(repair_from).resolve():
        raise ProtocolError("Repair must use a new batch directory")
    batch_root.mkdir(parents=True, exist_ok=True)
    lock = batch_root / ".controller.lock"
    try:
        fd = lock.open("x", encoding="utf8")
    except FileExistsError as exc:
        raise ProtocolError("Another/interrupted batch controller owns this run; inspect before recovery") from exc
    try:
        fd.write("single batch controller\n")
        fd.close()
        def run_one(job):
            # IDs are validated as path components by contained() in publication;
            # also reject path syntax here before creating any directory.
            if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in job["job_id"]):
                raise ProtocolError("Unsafe job ID")
            root = batch_root / job["job_id"]
            receipt = root / "receipt.json"
            if receipt.exists():
                old = read_json(receipt)
                if old["job_hash"] != digest(job):
                    raise ProtocolError("Resume job changed; use a new batch version")
                if old.get("repair_source") != (str(Path(repair_from).resolve()) if repair_from is not None else None):
                    raise ProtocolError("Resume repair source changed; use a new batch version")
                if old.get("repair_notes_hash") != (digest(repair_notes.get(job["job_id"], [])) if repair_notes else None):
                    raise ProtocolError("Resume repair notes changed; use a new batch version")
                return old
            if root.exists():
                return {"job_id": job["job_id"], "status": "interrupted_needs_review", "formal_accepted": False}
            root.mkdir()
            row = {"job_id": job["job_id"], "job_hash": digest(job), "formal_accepted": False,
                   "repair_notes_hash": digest(repair_notes.get(job["job_id"], [])) if repair_notes else None,
                   "repair_source": str(Path(repair_from).resolve()) if repair_from is not None else None}
            try:
                staged = root / "constructor"
                publication = prepare_material_job(job, workspace, staged, templates)
                prompt = (templates / "material_constructor.txt").read_text(encoding="utf8") + prompt_suffix
                if repair_from is not None:
                    row["repair_publication"] = stage_repair_candidate(Path(repair_from) / job["job_id"], staged,
                        adjudicated_notes=(repair_notes or {}).get(job["job_id"]))
                    prompt += "\nThis is ONE explicit repair attempt. Read repair_request.json and previous_candidate/; follow the NEW schema and prompt. Write a complete new output/, never overwrite historical files.\n"
                constructor_inputs = ("sources", "source_navigation", "request.json", "publication.json",
                                      "material_constructor.txt", "material_package.schema.json",
                                      "repair_request.json", "previous_candidate")
                row["constructor_input_snapshot"] = _input_snapshot(staged, constructor_inputs)
                result = constructor.run(workspace=staged,
                    prompt=prompt, role="constructor")
                row["constructor"] = result
                _check_inputs(staged, constructor_inputs, row["constructor_input_snapshot"], "Constructor")
                if controller_hash_fill:
                    row["controller_hash_fill"] = fill_sentinel_hashes(staged / "output")
                package = read_json(staged / "output/package.json")
                request = read_json(staged / "request.json")
                if digest(request) != publication["request_hash"]:
                    raise ProtocolError("Constructor altered request/source whitelist")
                if package.get("paper_id") != job["paper_id"]:
                    raise ProtocolError("Generated package belongs to wrong source paper")
                if any(t.get("task_type") not in job["requested_task_types"] for t in package.get("tasks", [])):
                    raise ProtocolError("Generated task outside explicitly requested pilot scope")
                row["structural_check"] = validate_package(package, staged / "output", request["sources"])
                review_dir = root / "reviewer"
                prepare_review(staged, review_dir, templates)
                reviewer_inputs = ("sources", "output", "source_navigation", "request.json",
                                   "material_reviewer.txt", "structural_check.json")
                row["reviewer_input_snapshot"] = _input_snapshot(review_dir, reviewer_inputs)
                row["reviewer"] = reviewer.run(workspace=review_dir,
                    prompt=(templates / "material_reviewer.txt").read_text(encoding="utf8"), role="material_reviewer")
                _check_inputs(review_dir, reviewer_inputs, row["reviewer_input_snapshot"], "Reviewer")
                review = read_json(review_dir / "review.json")
                if review.get("schema_version") != "material-review-1" or review.get("paper_id") != job["paper_id"]:
                    raise ProtocolError("Invalid independent review identity")
                if review.get("decision") not in {"pass_with_pending_runtime", "revise", "reject"}:
                    raise ProtocolError("Reviewer cannot grant formal acceptance")
                row["status"] = review["decision"]
            except Exception as exc:
                row["status"] = "failed_needs_attribution"
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            row["disk_bytes"] = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
            write_json(receipt, row, exclusive=True)
            return row
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(run_one, jobs))
        return {"jobs": results, "formal_accepted": False, "automatic_retry": False}
    finally:
        fd.close()
        lock.unlink(missing_ok=True)
