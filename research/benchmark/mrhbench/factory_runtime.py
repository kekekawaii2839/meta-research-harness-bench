"""Material factory controller steps: runtime/leak verification, TaskView compilation, dossiers.

Generalises the one-off controllers used for the first Claude-constructed candidates
(materials/pilot_v3/claude_candidates_v1/{verify,compile}_claude_candidates_v1.py and
D:/mrhbench-local-pilot/runtime-verify-20260924-r1/{controller_verify,leak_check_v2}.py).

Trusted controller code, zero model calls. Constructor-written code (smoke tests,
starter code) is never executed on the host, only inside a locked-down container.
A passed runtime record means: the dependency image was built from the pinned base,
the package smoke exited 0 under the package's declared limits, and a string-level
leak check found no hits. It is NOT scientific, semantic-leakage, rights, judge or
resource-sufficiency acceptance, and no task gate is promoted by this module.

Docker is reached only through an injectable runner ``docker(argv, timeout=...)``
returning ``{"returncode", "stdout", "stderr", "timed_out", "seconds"}`` so that
tests never call a real daemon.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .io import ProtocolError, contained, digest, file_hash, read_json, utc_now, write_json

SCHEMA_VERSION = "factory-runtime-1"
BASE_DIGEST = "sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9"
BASE_TAG = "python:3.12-slim"
BASE_REF = BASE_TAG + "@" + BASE_DIGEST
CONTEXT_FILES = ("Dockerfile", "requirements.txt", ".dockerignore")
CAPTURE_BYTES = 64 * 1024
SMOKE_MAX_SECONDS = 900
MIN_NEEDLE = 40
MIN_WORDS = 5
UID = "10001"
SMOKE_CONTAINER_PATH = "/smoke/smoke.py"
PUBLIC_ROOT = "/inputs/public"
MIB = 1024 * 1024
# Same order as mrhbench.factory.PAPER_STAGES (construct/repair each include their review).
STAGE_ORDER = ("fetch", "source_audit", "adjudication", "background", "repo_files", "external_data", "units", "construct", "review_adjudication",
               "repair", "repair_adjudication", "repair2", "repair2_adjudication", "runtime", "compile", "pilot", "dossier")
# Artifact name recorded by the factory -> extraction kind.
ARTIFACT_KIND = {"source_audit": "source_audit", "adjudication": "adjudication", "review": "review",
                 "review_adjudication": "review_adjudication", "runtime_record": "runtime", "compiled_tasks": "compile",
                 "pilot_record": "pilot"}
NOT_CERTIFIED = [
    "scientific_fidelity_of_package",
    "semantic_leakage (only an exact normalized >=40-char string check was run)",
    "resource_sufficiency_for_agent_runs (smoke only; no executor trajectory)",
    "OOM/PID/disk stress under the declared limits",
    "rights / licence / redistribution",
    "judge_behavior",
    "cross_host_reproducibility (requirements not hash-locked; image built locally)",
    "Dockerfile code security audit",
    "absence of task/private content inside the image beyond build-context restriction",
]

# Development defaults mirroring materials/pilot_v3/collection_candidates_v2 packages;
# unmeasured candidates, overridable per task by the caller.
DEFAULT_BUDGETS = {
    "LIT": {"model_calls": 12, "tool_calls": 120, "collection": (16 * MIB, 500)},
    "IDEA": {"model_calls": 6, "tool_calls": 60, "collection": (8 * MIB, 200)},
    "EXP": {"model_calls": 16, "tool_calls": 120, "collection": (128 * MIB, 2000)},
    "WRITE_CONTENT": {"model_calls": 4, "tool_calls": 60, "collection": (16 * MIB, 500)},
    "WRITE_EVIDENCE": {"model_calls": 12, "tool_calls": 60, "collection": (64 * MIB, 1000)},
}
BUDGET_BASIS = ("Unmeasured development candidate chosen by analogy to comparable collection_candidates_v2 "
                "packages (LIT 12/120, IDEA 6/60, EXP 16/120, WRITE_CONTENT 4/60, WRITE_EVIDENCE 12/60 model/tool "
                "calls) unless the caller supplied explicit values. No executor pilot has measured sufficiency; "
                "not a formal budget.")
FACTS_NOTE = ("Fixed supplied facts: the authoritative fixed inputs are the public asset files listed in the input "
              "contract above (task statement, fact sheets / specification, data and starter code). Fact IDs used in "
              "those files are provenance labels; fact statements are not restated in this prompt, and no other "
              "material-package wording is part of the task.")


# --------------------------------------------------------------------------- docker runner

def subprocess_docker(argv, *, timeout=None, keep_bytes=4 * MIB):
    """Default runner: real docker CLI; output spooled to temp files and bounded."""
    t0 = time.monotonic()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
        timed_out = False
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
            rc = None

        def bounded(f):
            size = f.seek(0, os.SEEK_END)
            f.seek(max(0, size - keep_bytes))
            return f.read().decode("utf-8", errors="replace")
        return {"returncode": rc, "stdout": bounded(out), "stderr": bounded(err), "timed_out": timed_out,
                "seconds": round(time.monotonic() - t0, 3)}


def _call(docker, argv, timeout):
    result = docker(argv, timeout=timeout)
    if not isinstance(result, dict) or "returncode" not in result:
        raise ProtocolError("Docker runner returned an invalid result")
    result.setdefault("stdout", "")
    result.setdefault("stderr", "")
    result.setdefault("timed_out", False)
    result.setdefault("seconds", None)
    return result


def _bounded_write(path: Path, text: str, *, keep="head") -> dict:
    data = (text or "").encode("utf-8", errors="replace")
    truncated = len(data) > CAPTURE_BYTES
    if truncated:
        data = data[:CAPTURE_BYTES] if keep == "head" else data[-CAPTURE_BYTES:]
    path.write_bytes(data)
    return {"path": path.as_posix(), "bytes_written": len(data), "truncated": truncated, "kept": keep}


def _mount_src(path: Path) -> str:
    src = Path(path).resolve(strict=True).as_posix()
    if "," in src or "\n" in src or "=" in src:
        raise ProtocolError("Mount source path cannot be expressed safely: " + src)
    return src


# --------------------------------------------------------------------------- base pinning

_FROM = re.compile(r"^\s*FROM\s+(?P<rest>.+?)\s*$", re.I | re.M)


def check_base(dockerfile_text: str) -> dict:
    """Return {'ok', 'pinned', 'reason', 'locked_text'}; only python:3.12-slim is supported."""
    matches = list(_FROM.finditer(dockerfile_text))
    if len(matches) != 1:
        return {"ok": False, "reason": "unsupported_base", "detail": "exactly one FROM line required"}
    rest = matches[0].group("rest")
    if rest.split()[0].startswith("--") or len(rest.split()) != 1:
        return {"ok": False, "reason": "unsupported_base", "detail": "FROM flags/stage names not supported: " + rest}
    ref = rest.split()[0]
    for prefix in ("docker.io/library/", "library/"):
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
    if ref == BASE_REF:
        return {"ok": True, "pinned": True, "locked_text": dockerfile_text}
    if ref == BASE_TAG:
        start, end = matches[0].span()
        return {"ok": True, "pinned": False,
                "locked_text": dockerfile_text[:start] + "FROM " + BASE_REF + dockerfile_text[end:]}
    return {"ok": False, "reason": "unsupported_base", "detail": "base must be %s (optionally @%s); got %s"
            % (BASE_TAG, BASE_DIGEST, ref)}


# --------------------------------------------------------------------------- assets and leak check

def _asset_inventory(output_dir: Path, package: dict) -> dict:
    declared = {}
    for task in package.get("tasks", []):
        for a in task.get("assets", []):
            declared.setdefault(a["path"], []).append((a["sha256"], a["visibility"], task["task_id"]))
    rows, problems = {}, []
    for path, decl in sorted(declared.items()):
        p = contained(output_dir, path)
        actual = file_hash(p) if p.is_file() else None
        hashes = {d[0] for d in decl}
        vis = {d[1] for d in decl}
        if actual is None or hashes != {actual}:
            problems.append("asset_hash_mismatch:" + path)
        if len(vis) > 1:
            problems.append("asset_visibility_conflict:" + path)
        rows[path] = {"sha256": actual, "declared": sorted(hashes), "visibility": sorted(vis),
                      "tasks": sorted({d[2] for d in decl}),
                      # Any private declaration makes the file private for mounting purposes.
                      "effective_visibility": "private" if "private" in vis else "public"}
    return {"assets": rows, "problems": problems}


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def needles_from_text(text: str, minimum: int = MIN_NEEDLE) -> set:
    """Normalized lines and sentences of at least ``minimum`` characters."""
    out = set()
    for line in text.splitlines():
        s = _norm(line.strip().strip("|"))
        if len(s) >= minimum:
            out.add(s)
    for sentence in re.split(r"(?<=[.;:!?])\s+", text):
        s = _norm(sentence)
        if len(s) >= minimum:
            out.add(s)
    return out


def _read_text(path: Path):
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None


def _text_needles(path: Path):
    text = _read_text(path)
    if text is None:
        return None
    if path.suffix.lower() == ".json":
        try:
            found = set()
            for s in _strings(json.loads(text)):
                found |= needles_from_text(s)
            return found
        except ValueError:
            pass
    return needles_from_text(text)


def private_only_fact_ids(package: dict) -> list:
    public_ids = {f for t in package.get("tasks", []) for f in t.get("input_fact_ids", [])}
    private_ids = {f for t in package.get("tasks", []) for f in t.get("private_fact_ids", [])}
    result = set()
    for fact in package.get("facts", []):
        fid = fact.get("fact_id")
        if fact.get("allowed_stages") == [] or (fid in private_ids and fid not in public_ids):
            result.add(fid)
    return sorted(result - public_ids)


def leak_check(output_dir: Path, package: dict, inventory: dict | None = None) -> dict:
    """Exact normalized substring search of public assets for private strings."""
    output_dir = Path(output_dir)
    inventory = inventory or _asset_inventory(output_dir, package)
    assets = inventory["assets"]
    private_paths = sorted(p for p, r in assets.items() if r["effective_visibility"] == "private")
    public_paths = sorted(p for p, r in assets.items() if r["effective_visibility"] == "public")
    facts = {f.get("fact_id"): f for f in package.get("facts", [])}
    public_fact_ids = sorted({f for t in package.get("tasks", []) for f in t.get("input_fact_ids", [])})
    public_fact_text = _norm("\n".join(facts[f].get("statement", "") for f in public_fact_ids if f in facts))
    priv_ids = private_only_fact_ids(package)

    needles, not_text = {}, []
    for path in private_paths:
        found = _text_needles(contained(output_dir, path, must_exist=True))
        if found is None:
            not_text.append({"path": path, "role": "private_asset"})
            continue
        for n in found:
            needles.setdefault(n, set()).add("private_asset:" + path)
    for fid in priv_ids:
        for n in needles_from_text(facts[fid].get("statement", "")):
            needles.setdefault(n, set()).add("private_only_fact:" + fid)
    for task in package.get("tasks", []):
        for s in _strings(task.get("verification_plan", {})):
            for n in needles_from_text(s):
                needles.setdefault(n, set()).add("verification_plan:" + task["task_id"])
    excluded = {n for n in needles if n in public_fact_text}
    # Needles must be prose: bare hashes, IDs and status labels (< MIN_WORDS words) are shared by design.
    hash_like = {n for n in needles if len(n.split()) < MIN_WORDS}
    for n in excluded | hash_like:
        del needles[n]

    haystacks = {}
    for path in public_paths:
        text = _read_text(contained(output_dir, path, must_exist=True))
        if text is None:
            not_text.append({"path": path, "role": "public_asset"})
        else:
            haystacks[path] = (_norm(text), text)
    hits = []
    for needle, origins in sorted(needles.items()):
        for path, (hay, _) in haystacks.items():
            if needle in hay:
                hits.append({"class": "private_string_in_public_asset", "file": path,
                             "needle_excerpt": needle[:160], "needle_chars": len(needle),
                             "private_origins": sorted(origins)})
    private_hashes = {assets[p]["sha256"]: p for p in private_paths}
    for path in public_paths:
        twin = private_hashes.get(assets[path]["sha256"])
        if twin:
            hits.append({"class": "public_asset_bytes_identical_to_private_asset", "file": path,
                         "needle_excerpt": None, "private_origins": ["private_asset:" + twin]})
    id_mentions = []
    for fid in priv_ids:
        if not fid or len(fid) < 4:
            continue
        pattern = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(fid) + r"(?![A-Za-z0-9_])")
        for path, (_, raw) in haystacks.items():
            if pattern.search(raw):
                id_mentions.append({"fact_id": fid, "file": path})
    return {"method": ("Exact substring search, after whitespace collapsing and casefolding, of every public "
                       "text asset for each >=%d-char line/sentence of (a) private assets, (b) private-only fact "
                       "statements (allowed_stages == [] or referenced only in private_fact_ids), (c) task "
                       "verification plans; needles also present in public input fact statements, and non-prose needles with fewer than 5 words (hashes, IDs, status labels), are excluded. "
                       "Byte-identical public/private assets are also flagged. This is a string check, NOT "
                       "semantic leakage acceptance." % MIN_NEEDLE),
            "semantic_leakage_accepted": False,
            "needle_count": len(needles), "needles_excluded_as_public_fact_text": len(excluded), "needles_excluded_as_non_prose": len(hash_like),
            "private_assets": private_paths, "public_assets": public_paths,
            "private_only_fact_ids": priv_ids, "not_text_checked": not_text,
            "hit_count": len(hits), "hits": hits[:200], "hits_truncated": len(hits) > 200,
            "informational_private_fact_id_mentions": id_mentions}


# --------------------------------------------------------------------------- runtime verification

def _slug_ok(slug) -> bool:
    return isinstance(slug, str) and re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", slug) is not None and len(slug) <= 64


def context_hash(context: Path) -> str:
    h = hashlib.sha256()
    for name in CONTEXT_FILES:
        p = context / name
        if p.is_file():
            h.update(name.encode() + b"\0" + file_hash(p).encode() + b"\n")
    return h.hexdigest()


def smoke_args(*, name, image_id, resources, public_view: Path, smoke_file: Path,
               smoke_container_path=SMOKE_CONTAINER_PATH) -> list:
    """docker run argv for the package smoke; public assets and smoke are separate ro binds."""
    for key in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds"):
        v = resources.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ProtocolError("Invalid resource " + key)
    disk = int(resources["disk_mb"]) * MIB
    tmp = disk // 5
    work = disk - tmp
    memory = "%dm" % int(resources["memory_mb"])
    threads = str(max(1, int(resources["cpus"])))
    return ["docker", "run", "--rm", "--name", name, "--label", "mrhbench.purpose=factory-runtime-smoke",
            "--platform", "linux/amd64", "--pull", "never", "--network", "none", "--read-only",
            "--user", UID + ":" + UID, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--ipc", "none", "--cpus", str(resources["cpus"]), "--memory", memory, "--memory-swap", memory,
            "--pids-limit", str(int(resources["pids_limit"])),
            "--tmpfs", "/work:rw,nosuid,nodev,size=%d,uid=%s,gid=%s,mode=0700" % (work, UID, UID),
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=%d,uid=%s,gid=%s,mode=0700" % (tmp, UID, UID),
            "--mount", "type=bind,src=%s,dst=%s,readonly" % (_mount_src(public_view), PUBLIC_ROOT),
            "--mount", "type=bind,src=%s,dst=%s,readonly" % (_mount_src(smoke_file), smoke_container_path),
            "--workdir", "/work", "--env", "HOME=/work", "--env", "MPLCONFIGDIR=/tmp/matplotlib",
            "--env", "MPLBACKEND=Agg", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", "OMP_NUM_THREADS=" + threads, "--env", "OPENBLAS_NUM_THREADS=" + threads,
            "--env", "MRH_PUBLIC_ROOT=" + PUBLIC_ROOT,
            "--entrypoint", "python", image_id, "-B", smoke_container_path]


def _remove_container(docker, name) -> dict:
    rm = _call(docker, ["docker", "rm", "-f", name], 60)
    ps = _call(docker, ["docker", "ps", "-a", "-q", "--filter", "name=^/?%s$" % name], 60)
    return {"rm_returncode": rm["returncode"], "remaining": ps["stdout"].split(),
            "verified_absent": ps["returncode"] == 0 and not ps["stdout"].strip()}


def verify_runtime(output_dir, package, dest_dir, *, package_slug, docker=None,
                   build_timeout=1800, smoke_container_path=SMOKE_CONTAINER_PATH) -> dict:
    """Build the per-package image, run the smoke, string-check leakage; write runtime_record.json."""
    output_dir, dest_dir = Path(output_dir), Path(dest_dir)
    docker = docker or subprocess_docker
    if not _slug_ok(package_slug):
        raise ProtocolError("package_slug must be a lowercase docker-safe name component")
    if dest_dir.exists():
        raise ProtocolError("Runtime verification requires a fresh destination: " + str(dest_dir))
    dest_dir.mkdir(parents=True)
    reasons = []
    record = {"schema_version": SCHEMA_VERSION, "status": "failed", "reasons": reasons,
              "package_slug": package_slug, "output_dir": output_dir.as_posix(), "dest_dir": dest_dir.as_posix(),
              "record_path": (dest_dir / "runtime_record.json").as_posix(), "created_at": utc_now(),
              "package_json_sha256": file_hash(output_dir / "package.json") if (output_dir / "package.json").is_file() else None,
              "package_digest": digest(package),
              "controller_filled": (output_dir / "package.constructor_original.json").is_file(),
              "controller_module_sha256": file_hash(Path(__file__)),
              "image": None, "smoke": None, "leak_check": None, "model_calls": 0,
              "constructor_code_executed_on_host": False, "not_certified": list(NOT_CERTIFIED)}

    def finish():
        record["status"] = "passed" if not reasons else "failed"
        write_json(dest_dir / "runtime_record.json", record, exclusive=True)
        return record

    from .material_pipeline import validate_environment
    env = package.get("environment", {})
    try:
        record["environment_check"] = validate_environment(env, output_dir)
    except ProtocolError as exc:
        reasons.append("environment_invalid: %s" % exc)
        return finish()
    resources = env["resources"]
    try:
        inventory = _asset_inventory(output_dir, package)
    except ProtocolError as exc:
        reasons.append("asset_path_invalid: %s" % exc)
        return finish()
    reasons.extend(inventory["problems"])
    record["assets"] = inventory["assets"]
    record["leak_check"] = leak_check(output_dir, package, inventory)
    if record["leak_check"]["hit_count"]:
        reasons.append("string_leak_hits")

    dockerfile = contained(output_dir, env.get("dockerfile", "environment/image/Dockerfile"), must_exist=True)
    context = dockerfile.parent
    smoke_src = contained(output_dir, env.get("smoke_test", "environment/smoke.py"), must_exist=True)
    private_paths = {p for p, r in inventory["assets"].items() if r["effective_visibility"] == "private"}
    private_hashes = {inventory["assets"][p]["sha256"] for p in private_paths}
    context_files = sorted(p.relative_to(context).as_posix() for p in context.rglob("*") if p.is_file())
    ctx_rel = context.relative_to(output_dir.resolve()).as_posix()
    in_context = [f for f in context_files if (ctx_rel + "/" + f) in private_paths
                  or file_hash(context / f) in private_hashes]
    record["build_context"] = {"source_dir": ctx_rel, "files": context_files,
                               "files_sha256": {f: file_hash(context / f) for f in context_files},
                               "private_asset_in_context": in_context}
    if in_context:
        reasons.append("private_asset_in_build_context")

    base = check_base(dockerfile.read_bytes().decode("utf-8"))
    if not base["ok"]:
        reasons.append(base["reason"])
        record["image"] = {"base_check": {k: v for k, v in base.items() if k != "locked_text"}}
        return finish()
    stage = dest_dir / "build_context"
    stage.mkdir()
    for f in context_files:
        shutil.copyfile(context / f, stage / f)
    locked = stage / "Dockerfile.controller_locked"
    locked.write_bytes(base["locked_text"].encode("utf-8"))
    tag = "mrhbench-factory/%s:%s" % (package_slug, context_hash(context)[:12])
    record["image"] = {"tag": tag, "id": None, "base_ref": BASE_REF, "base_digest": BASE_DIGEST,
                       "base_was_pinned_by_constructor": base["pinned"],
                       "controller_locked_dockerfile_sha256": file_hash(locked),
                       "controller_change": ("none" if base["pinned"] else
                                             "FROM tag replaced by digest-pinned reference only"),
                       "pip_freeze": None, "shared_with_other_packages": False}
    try:
        build = _call(docker, ["docker", "build", "--progress=plain", "--platform", "linux/amd64",
                               "-f", locked.as_posix(), "-t", tag, stage.as_posix()], build_timeout)
    except OSError as exc:
        reasons.append("docker_unavailable: %s" % exc)
        return finish()
    record["image"]["build"] = {"returncode": build["returncode"], "timed_out": build["timed_out"],
                                "seconds": build["seconds"],
                                "log": _bounded_write(dest_dir / "build.log",
                                                      build["stdout"] + "\n----STDERR----\n" + build["stderr"], keep="tail")}
    if build["returncode"] != 0 or build["timed_out"]:
        reasons.append("image_build_failed")
        return finish()
    inspect = _call(docker, ["docker", "image", "inspect", "--format", "{{.Id}}", tag], 60)
    image_id = inspect["stdout"].strip()
    if inspect["returncode"] != 0 or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
        reasons.append("image_inspect_failed")
        return finish()
    record["image"]["id"] = image_id
    freeze_name = "mrh-factory-freeze-" + os.urandom(8).hex()
    freeze = _call(docker, ["docker", "run", "--rm", "--name", freeze_name, "--network", "none",
                            "--user", UID + ":" + UID, "--entrypoint", "python", image_id,
                            "-m", "pip", "freeze", "--all"], 120)
    freeze_cleanup = _remove_container(docker, freeze_name)
    if freeze["returncode"] == 0:
        record["image"]["pip_freeze"] = [l for l in freeze["stdout"].splitlines() if l.strip()]
    else:
        reasons.append("pip_freeze_failed")
    if not freeze_cleanup["verified_absent"]:
        reasons.append("container_cleanup_failed:" + freeze_name)

    view = dest_dir / "public_view"
    view.mkdir()
    public_paths = sorted(p for p, r in inventory["assets"].items() if r["effective_visibility"] == "public")
    for path in public_paths:
        src = contained(output_dir, path, must_exist=True)
        dst = contained(view, path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if file_hash(dst) != inventory["assets"][path]["sha256"]:
            reasons.append("public_asset_changed_during_staging:" + path)
    smoke_dir = dest_dir / "smoke_mount"
    smoke_dir.mkdir()
    smoke_file = smoke_dir / "smoke.py"
    shutil.copyfile(smoke_src, smoke_file)
    mounted = sorted(p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_file())
    private_in_mount = [f for f in mounted if f in private_paths or file_hash(view / f) in private_hashes]
    if file_hash(smoke_file) in private_hashes:
        private_in_mount.append("smoke:" + smoke_container_path)
    if private_in_mount:
        reasons.append("private_asset_in_public_mount")
    if mounted != public_paths:
        reasons.append("public_mount_file_set_mismatch")

    timeout = min(float(resources["wall_seconds"]), SMOKE_MAX_SECONDS)
    name = "mrh-factory-%s-%s" % (package_slug[:24].strip("._-") or "pkg", os.urandom(8).hex())
    argv = smoke_args(name=name, image_id=image_id, resources=resources, public_view=view,
                      smoke_file=smoke_file, smoke_container_path=smoke_container_path)
    run = _call(docker, argv, timeout)
    cleanup = _remove_container(docker, name)
    record["smoke"] = {"container_name": name, "argv": argv, "exit_code": run["returncode"],
                       "timed_out": run["timed_out"], "seconds": run["seconds"], "timeout_seconds": timeout,
                       "stdout_path": _bounded_write(dest_dir / "smoke_stdout.txt", run["stdout"])["path"],
                       "stderr_path": _bounded_write(dest_dir / "smoke_stderr.txt", run["stderr"])["path"],
                       "stdout_truncated": len(run["stdout"].encode("utf-8", "replace")) > CAPTURE_BYTES,
                       "stderr_truncated": len(run["stderr"].encode("utf-8", "replace")) > CAPTURE_BYTES,
                       "smoke_sha256": file_hash(smoke_file), "smoke_container_path": smoke_container_path,
                       "public_mount": {"container_path": PUBLIC_ROOT, "files": mounted, "readonly": True,
                                        "private_in_mount": private_in_mount},
                       "limits": {"cpus": resources["cpus"], "memory_mb": resources["memory_mb"],
                                  "disk_mb": resources["disk_mb"], "work_tmpfs_bytes": int(resources["disk_mb"]) * MIB
                                  - int(resources["disk_mb"]) * MIB // 5,
                                  "tmp_tmpfs_bytes": int(resources["disk_mb"]) * MIB // 5,
                                  "pids_limit": resources["pids_limit"], "wall_seconds_declared": resources["wall_seconds"],
                                  "network": "none", "read_only_root": True, "user": UID + ":" + UID,
                                  "cap_drop": "ALL", "no_new_privileges": True},
                       "cleanup": cleanup}
    if run["timed_out"]:
        reasons.append("smoke_timeout")
    elif run["returncode"] != 0:
        reasons.append("smoke_failed")
    if not cleanup["verified_absent"]:
        reasons.append("container_cleanup_failed:" + name)
    return finish()


# --------------------------------------------------------------------------- compilation

def controller_notes(container, collection, budget) -> str:
    total_mib = collection["max_total_bytes"] // MIB
    return ("\nController publication notes (development candidate; limits not formally frozen):\n"
            "1. Released paths: a document path written in the task files, such as assets/<...>, refers to the material "
            "package; its released copy is listed in asset_manifest with the extra prefix \"assets/\" (for example "
            "assets/assets/<...>) under the read-only public input root. Relative paths for your deliverables "
            "(for example submission/..., results/...) are inside your writable work directory.\n"
            f"2. Container: {container['cpus']} CPU, {container['memory_mb']} MB memory, {container['disk_mb']} MB total "
            "writable tmpfs (80% work directory, 20% /tmp; counted against memory), "
            f"{container['pids_limit']} processes, {container['wall_seconds']} s total task wall time; no network, no GPU.\n"
            f"3. Artifact collection quota: at most {total_mib} MiB ({collection['max_total_bytes']} bytes) of file bytes "
            f"and at most {collection['max_entries']} entries (files AND directories) under the work directory, excluding "
            "top-level .broker and .process-*. If your outputs exceed this quota, collection is recorded as a failure and "
            "outputs may be lost or not evaluated; keep raw logs and per-step trajectories compact and save only what is "
            "needed as evidence.\n"
            f"4. Model/tool budget: {budget['model_calls']} model calls and {budget['tool_calls']} controller broker tool "
            f"calls within {budget['wall_seconds']} s (unmeasured development candidate values).")


def _drop_fact_statements(prompt: str) -> str:
    head, sep, rest = prompt.partition("\nFixed supplied facts:\n")
    if not sep:
        raise ProtocolError("Unexpected compiled prompt layout")
    _, sep2, tail = rest.partition("\nScientific output requirements:\n")
    if not sep2:
        raise ProtocolError("Unexpected compiled prompt layout")
    return head + "\n" + FACTS_NOTE + "\nScientific output requirements:\n" + tail


def compile_tasks(output_dir, package, runtime_record, dest_dir, *, package_slug,
                  source_manifest=None, execution_budgets=None, artifact_collections=None,
                  compose_fact_statements=True, material_origin="factory_constructor",
                  review_path=None, require_visual_png_preview=True, per_task_resources=False) -> list:
    """Compile a runtime-passed package into development TaskViews; every gate stays pending.

    source_manifest defaults to <output_dir>/../request.json["sources"]. compose_fact_statements=False
    reproduces the claude_candidates_v1 decision (statements withheld, public assets authoritative) and
    is only allowed when every task with input facts has public assets.
    """
    from .material_adapter import compile_package
    from .materials import check_task, load_task
    from .rubrics import rubric
    from .artifact_policy import make_collection_policy, collection_policy

    output_dir, dest_dir = Path(output_dir), Path(dest_dir)
    if not isinstance(runtime_record, dict) or runtime_record.get("schema_version") != SCHEMA_VERSION:
        raise ProtocolError("A factory runtime record is required")
    if runtime_record.get("status") != "passed" or runtime_record.get("reasons"):
        raise ProtocolError("Refusing to compile: runtime record status is not passed")
    if runtime_record.get("package_slug") != package_slug:
        raise ProtocolError("Runtime record belongs to another package slug")
    package_sha = file_hash(output_dir / "package.json")
    if runtime_record.get("package_json_sha256") != package_sha or runtime_record.get("package_digest") != digest(package):
        raise ProtocolError("Package changed since runtime verification")
    image_id = (runtime_record.get("image") or {}).get("id")
    if not isinstance(image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
        raise ProtocolError("Runtime record lacks an immutable image id")
    if dest_dir.exists():
        raise ProtocolError("Compilation requires a fresh destination: " + str(dest_dir))
    if source_manifest is None:
        source_manifest = read_json(output_dir.parent / "request.json")["sources"]
    container = {k: package["environment"]["resources"][k]
                 for k in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds")}
    tasks = package["tasks"]
    from .material_adapter import task_container
    task_containers = {t["task_id"]: (task_container(t, container) if per_task_resources else container) for t in tasks}
    budgets, collections = {}, {}
    for t in tasks:
        default = DEFAULT_BUDGETS[t["task_type"]]
        b = (execution_budgets or {}).get(t["task_id"]) or {"model_calls": default["model_calls"],
                                                           "tool_calls": default["tool_calls"]}
        budgets[t["task_id"]] = {"model_calls": b["model_calls"], "tool_calls": b["tool_calls"],
                                 "wall_seconds": task_containers[t["task_id"]]["wall_seconds"]}
        collections[t["task_id"]] = ((artifact_collections or {}).get(t["task_id"])
                                     or make_collection_policy(max_total_bytes=default["collection"][0],
                                                               max_entries=default["collection"][1]))
    if not compose_fact_statements:
        for t in tasks:
            if t.get("input_fact_ids") and not any(a["visibility"] == "public" for a in t["assets"]):
                raise ProtocolError("Cannot withhold fact statements from a task without public assets: " + t["task_id"])
    source_tree_before = {p.relative_to(output_dir).as_posix(): file_hash(p) for p in output_dir.rglob("*") if p.is_file()}
    staging = dest_dir / "staging.compile_package"
    types = sorted({t["task_type"] for t in tasks})
    result = compile_package(output_dir, {"sources": source_manifest}, staging, execution_budgets=budgets,
                             image_id=image_id, public_rubrics={k: rubric(k) for k in types},
                             artifact_collections=collections,
                             require_visual_png_preview=require_visual_png_preview,
                             per_task_resources=per_task_resources)
    review = None
    if review_path is not None:
        review = {"path": Path(review_path).as_posix(), "sha256": file_hash(Path(review_path)),
                  "decision": read_json(Path(review_path)).get("decision")}
    runtime_digest = digest(runtime_record)
    records = []
    for t in tasks:
        compiled_root = staging / t["task_id"]
        compiled = read_json(compiled_root / "task.json")
        final_root = dest_dir / t["task_id"]
        task = copy.deepcopy(compiled)
        relocations, taken = [], {a["path"] for a in task["assets"]}
        for asset in task["assets"]:
            if asset["visibility"] == "private" and not asset["path"].startswith("private/"):
                new_path = "private/" + asset["path"]
                if new_path in taken:
                    raise ProtocolError("Private relocation collides: " + new_path)
                relocations.append({"from": asset["path"], "to": new_path, "sha256": asset["sha256"]})
                taken.add(new_path)
                asset["path"] = new_path
        back = {r["to"]: r["from"] for r in relocations}
        final_root.mkdir()
        for asset in task["assets"]:
            source = contained(compiled_root, back.get(asset["path"], asset["path"]), must_exist=True)
            target = contained(final_root, asset["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if file_hash(target) != asset["sha256"]:
                raise ProtocolError("Asset changed during copy")
        view = task["public"]
        prompt = view["prompt"] if compose_fact_statements else _drop_fact_statements(view["prompt"])
        view["prompt"] = prompt + controller_notes(view["resources"]["container"],
                                                   view["resources"]["artifact_collection"],
                                                   view["resources"]["execution_budget"])
        view["resources"]["budget_status"] = "explicit_development_candidate_pending_task_feasibility"
        task["private"].update({
            "material_origin": material_origin, "package_slug": package_slug,
            "source_output": output_dir.as_posix(), "source_package_json_sha256": package_sha,
            "runtime_record_digest": runtime_digest, "runtime_record_path": runtime_record.get("record_path"),
            "reviewer": review, "execution_budget_basis": BUDGET_BASIS,
            "controller_publication_decisions": {
                "fact_statements_composed_into_prompt": bool(compose_fact_statements),
                "private_asset_relocations": relocations, "controller_notes_appended": True,
                "visual_png_preview_rule_applied_to_write_evidence": bool(require_visual_png_preview)},
            "formal_eligible": False})
        for gate in task["gates"].values():
            gate["status"] = "pending"
        rt = runtime_record.get("record_path") or "runtime_record.json"
        task["gates"]["runtime"]["evidence"] = (
            "Per-package image %s built from pinned base %s and package smoke exited 0 in a locked-down container "
            "(%s); no executor trajectory, resource-sufficiency measurement or OOM/PID/disk stress on this task. Pending."
            % (image_id, BASE_REF, rt))
        task["gates"]["input_leakage"]["evidence"] = (
            "Controller string leak check (normalized >=40-char needles) found no hits (%s); not semantic "
            "contamination acceptance. Pending." % rt)
        task["gates"]["source_semantics"]["evidence"] = (
            ("Independent reviewer decision %s (%s); " % (review["decision"], review["path"]) if review else
             "No reviewer record supplied to compilation; ") + "not formal acceptance. Pending.")
        task["gates"]["rights"]["evidence"] = "Source licence and benchmark reuse/redistribution rights not reviewed. Pending."
        task["gates"]["judge_behavior"]["evidence"] = "No judge run or trajectory audit for this task. Pending."
        check_task(task, final_root)
        public_ids = set(view["inputs"])
        if any(a["asset_id"] in public_ids for a in task["assets"] if a["visibility"] == "private"):
            raise ProtocolError("Private asset listed as public input")
        write_json(final_root / "task.json", task, exclusive=True)
        load_task(final_root / "task.json")
        collection_policy(view["resources"])
        provenance = {
            "compilation_tool": "mrhbench.factory_runtime.compile_tasks (mrhbench.material_adapter.compile_package + controller publication decisions)",
            "factory_runtime_sha256": file_hash(Path(__file__)),
            "material_adapter_sha256": file_hash(Path(__file__).with_name("material_adapter.py")),
            "source_output": output_dir.as_posix(), "source_package_json_sha256": package_sha,
            "staging_compiled_task_sha256": file_hash(compiled_root / "task.json"),
            "final_task_sha256": file_hash(final_root / "task.json"),
            "task_id": task["task_id"], "material_origin": material_origin,
            "published_policy": view["resources"]["artifact_collection"],
            "execution_budget": view["resources"]["execution_budget"],
            "container": view["resources"]["container"], "image_id": image_id,
            "runtime_record_digest": runtime_digest, "formal": False,
            "interpretation": "Development compilation of a reviewed candidate; not scientific, runtime-sufficiency, rights or judge acceptance."}
        write_json(final_root / "collection_contract_provenance.json", provenance, exclusive=True)
        records.append({"task_id": task["task_id"], "task_type": task["task_type"], "dir": final_root.as_posix(),
                        "task_sha256": provenance["final_task_sha256"],
                        "public_assets": [a["path"] for a in task["assets"] if a["visibility"] == "public"],
                        "private_assets": [a["path"] for a in task["assets"] if a["visibility"] == "private"],
                        "gates": {k: v["status"] for k, v in task["gates"].items()},
                        "provenance": provenance, "compile_result_hash": digest(result)})
    after = {p.relative_to(output_dir).as_posix(): file_hash(p) for p in output_dir.rglob("*") if p.is_file()}
    if after != source_tree_before:
        raise ProtocolError("Source material output changed during compilation")
    write_json(dest_dir / "compile_record.json", {"schema_version": "factory-compile-1", "package_slug": package_slug,
                                                  "tasks": records, "model_calls": 0, "formal_accepted": False},
               exclusive=True)
    return records


# --------------------------------------------------------------------------- dossiers

def _first_list(obj, keys):
    if isinstance(obj, dict):
        for k in keys:
            if isinstance(obj.get(k), list):
                return k, obj[k]
    elif isinstance(obj, list):
        return "(root list)", obj
    return None, None


def _pick(item, keys):
    if not isinstance(item, dict):
        return None
    for k in keys:
        if item.get(k) not in (None, ""):
            return item[k]
    return None


def _decision(item):
    d = _pick(item, ("decision", "verdict", "status"))
    if d is None and isinstance(item, dict) and isinstance(item.get("accepted"), bool):
        d = "accepted" if item["accepted"] else "rejected"
    return d


def _extract(stage, data):
    """Stage-specific summary of one artifact; absent fields reported as None, never invented."""
    ident = ("id", "finding_id", "finding_index", "ambiguity_id", "decision_id", "fact_id", "task_id")
    if stage == "source_audit":
        key, items = _first_list(data, ("ambiguities", "ambiguity_list", "issues"))
        if items is None:
            return {"ambiguities": "missing_field"}
        return {"ambiguities": [{"id": _pick(i, ident), "issue": _pick(i, ("issue", "description", "text", "question", "summary")) if isinstance(i, dict) else i}
                                for i in items], "field": key}
    if stage in ("adjudication", "review_adjudication", "repair_adjudication"):
        key, items = _first_list(data, ("ambiguity_decisions", "finding_decisions", "decisions", "findings", "adjudications", "items"))
        if items is None:
            return {"decisions": "missing_field"}
        return {"decisions": [{"id": _pick(i, ident), "decision": _decision(i),
                               "reason": _pick(i, ("reason", "rationale", "justification"))} for i in items], "field": key}
    if stage in ("review", "repair_review"):
        key, items = _first_list(data, ("findings", "issues"))
        out = {"decision": data.get("decision") if isinstance(data, dict) else None}
        if items is None:
            out["findings"] = "missing_field"
        else:
            out["findings"] = [{"id": _pick(i, ident), "severity": _pick(i, ("severity", "level")),
                                "issue": _pick(i, ("observed_issue", "issue", "description", "summary"))} for i in items]
        return out
    if stage == "runtime":
        if not isinstance(data, dict):
            return {"runtime": "missing_field"}
        leak = data.get("leak_check") or {}
        return {"status": data.get("status"), "reasons": data.get("reasons"),
                "image_tag": (data.get("image") or {}).get("tag"), "image_id": (data.get("image") or {}).get("id"),
                "smoke_exit_code": (data.get("smoke") or {}).get("exit_code"),
                "leak_hit_count": leak.get("hit_count")}
    if stage == "compile":
        key, items = _first_list(data, ("tasks", "records"))
        if items is None:
            return {"task_ids": "missing_field"}
        return {"task_ids": [_pick(i, ("task_id",)) for i in items]}
    if stage == "pilot":
        items = data if isinstance(data, list) else (data.get("results") if isinstance(data, dict) and isinstance(data.get("results"), list) else [data])
        out = []
        for i in items:
            if not isinstance(i, dict):
                continue
            judgment = i.get("judgment") if isinstance(i.get("judgment"), dict) else i
            scores = judgment.get("dimension_scores") or judgment.get("scores") or judgment.get("dimensions")
            out.append({"task_id": i.get("task_id"), "status": i.get("status"),
                        "dimension_scores": scores, "quality_score": i.get("quality_score", judgment.get("quality_score"))})
        return {"pilot": out or "missing_field"}
    return {}


def build_dossier(paper_dir) -> Path:
    """Summarise a paper's factory state into dossier/dossier.json and dossier.md."""
    paper_dir = Path(paper_dir)
    state = read_json(paper_dir / "state.json")
    if state.get("schema_version") != "factory-paper-state-1" or not state.get("project_id"):
        raise ProtocolError("Unsupported factory paper state")
    stages = state.get("stages") or {}
    unknown = sorted(set(stages) - set(STAGE_ORDER))
    derived = []
    summary = []
    finished = []
    for name in STAGE_ORDER:
        if name not in stages:
            continue
        st = stages[name]
        entry = {"stage": name, "status": st.get("status"), "finished_at": st.get("finished_at"),
                 "calls": st.get("calls", []), "notes": st.get("notes", []), "artifacts": {}, "extracted": {}}
        if st.get("finished_at"):
            finished.append(st["finished_at"])
        if st.get("status") in ("failed", "blocked", "error", "dropped", "blocked_source") or str(st.get("status")).startswith("failed"):
            derived.append("stage_%s_%s" % (name, st["status"]))
        for art, rel in sorted((st.get("artifacts") or {}).items()):
            try:
                p = contained(paper_dir, rel)
            except ProtocolError:
                entry["artifacts"][art] = {"path": rel, "present": False, "error": "unsafe_path"}
                derived.append("artifact_unsafe_path:%s/%s" % (name, art))
                continue
            if not p.is_file():
                entry["artifacts"][art] = {"path": rel, "present": False}
                derived.append("artifact_missing:%s/%s" % (name, art))
                continue
            info = {"path": rel, "present": True, "sha256": file_hash(p)}
            try:
                data = read_json(p)
            except (ValueError, UnicodeDecodeError) as exc:
                info["parse_error"] = str(exc)[:200]
                derived.append("artifact_unparseable:%s/%s" % (name, art))
                entry["artifacts"][art] = info
                continue
            entry["artifacts"][art] = info
            extracted = _extract(ARTIFACT_KIND.get(art, name), data)
            if extracted:
                entry["extracted"][art] = extracted
        if name == "runtime":
            for ex in entry["extracted"].values():
                if ex.get("status") not in (None, "passed"):
                    derived.append("runtime_not_passed")
                if ex.get("leak_hit_count"):
                    derived.append("runtime_leak_hits")
        summary.append(entry)
    dossier = {"schema_version": "factory-dossier-1", "project_id": state["project_id"], "title": state.get("title"),
               "generated_at": utc_now(), "state_sha256": file_hash(paper_dir / "state.json"),
               "completed_at": max(finished) if finished else None,
               "stages_present": [e["stage"] for e in summary],
               "stages_absent": [s for s in STAGE_ORDER if s not in stages],
               "unknown_stages": unknown, "flags": list(state.get("flags", [])),
               "derived_flags": sorted(set(derived)), "stages": summary,
               "note": "Summary of recorded artifacts only; missing artifacts/fields are reported, never inferred."}
    out = paper_dir / "dossier"
    out.mkdir(exist_ok=True)
    write_json(out / "dossier.json", dossier)
    (out / "dossier.md").write_bytes(_dossier_md(dossier).encode("utf-8"))
    return out / "dossier.json"


def _dossier_md(d) -> str:
    lines = ["# Dossier: %s" % d["project_id"], "", "Title: %s" % (d.get("title") or "(none)"),
             "Completed at: %s" % (d.get("completed_at") or "(unknown)"),
             "Flags: %s" % (", ".join(d["flags"]) or "none"),
             "Derived flags: %s" % (", ".join(d["derived_flags"]) or "none"),
             "Stages absent: %s" % (", ".join(d["stages_absent"]) or "none"), ""]
    for e in d["stages"]:
        lines.append("## %s: %s" % (e["stage"], e.get("status")))
        if e["calls"]:
            lines.append("- calls: %s" % ", ".join(str(c) for c in e["calls"]))
        for n in e["notes"]:
            lines.append("- note: %s" % n)
        for art, info in e["artifacts"].items():
            lines.append("- artifact %s: %s%s" % (art, info["path"], "" if info.get("present") else " (MISSING)"))
        for art, ex in e["extracted"].items():
            for key, value in ex.items():
                if isinstance(value, list):
                    lines.append("- %s/%s (%d):" % (art, key, len(value)))
                    for v in value[:50]:
                        lines.append("  - " + json.dumps(v, ensure_ascii=False)[:300])
                else:
                    lines.append("- %s/%s: %s" % (art, key, json.dumps(value, ensure_ascii=False)[:300]))
        lines.append("")
    return "\n".join(lines) + "\n"


def select_for_final_review(dossiers, *, seed, first_n=10, sample_rate=0.2) -> list:
    """First ``first_n`` completed papers, then every flagged paper, then a seeded sample of the rest."""
    if not isinstance(seed, str) or not seed or not 0 <= sample_rate <= 1 or first_n < 0:
        raise ProtocolError("Explicit seed and valid selection parameters required")
    order = sorted(enumerate(dossiers), key=lambda x: (x[1].get("completed_at") is None,
                                                       x[1].get("completed_at") or "", x[0]))
    selected, seen = [], set()
    for rank, (_, d) in enumerate(order):
        pid = d["project_id"]
        if pid in seen:
            raise ProtocolError("Duplicate project in review selection: " + pid)
        seen.add(pid)
        flags = list(d.get("flags", [])) + list(d.get("derived_flags", []))
        if rank < first_n:
            selected.append({"project_id": pid, "reason": "first_%d_in_completion_order" % first_n})
        elif flags:
            selected.append({"project_id": pid, "reason": "flagged: " + ", ".join(sorted(set(flags)))})
        else:
            u = int(hashlib.sha256((seed + pid).encode("utf-8")).hexdigest()[:16], 16) / 2 ** 64
            if u < sample_rate:
                selected.append({"project_id": pid, "reason": "seeded_sample_%g" % sample_rate})
    return selected
