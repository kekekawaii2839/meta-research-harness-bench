"""Explicit, evidence-bound controller data conversions; no model or author code.

An optional paper-level data_conversion/publication.json replaces selected binary
prepopulations in future jobs, never modifies sources or historical candidates.
Conversion plans bind the adjudication that requested a neutral representation.
The Docker image is a separate controller dependency, NOT a solver/package image.
"""
from pathlib import Path
import re
import uuid

from .io import ProtocolError, contained, file_hash, read_json, write_json
from .factory_runtime import subprocess_docker, _mount_src


def check_plan(paper, plan):
    if plan.get("schema_version") != "factory-data-conversion-plan-1":
        raise ProtocolError("Unknown data conversion plan")
    if not plan.get("evidence") or not plan.get("conversions"):
        raise ProtocolError("Conversion needs binding evidence and inputs")
    for e in plan["evidence"]:
        if file_hash(contained(paper, e["path"], must_exist=True)) != e["sha256"]:
            raise ProtocolError("Conversion evidence changed")
    paths, names = set(), set()
    for row in plan["conversions"]:
        src = contained(paper, row["source"], must_exist=True)
        if file_hash(src) != row["source_sha256"]:
            raise ProtocolError("Conversion source changed")
        contained(paper, row["replace_path"])
        name = row["name"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name):
            raise ProtocolError("Invalid neutral conversion name")
        if row["replace_path"] in paths or name in names:
            raise ProtocolError("Duplicate conversion target")
        paths.add(row["replace_path"]); names.add(name)


def convert_plan(paper, plan_path, output, *, image_id, docker=subprocess_docker):
    """Run each conversion in a new bounded container, publish only on full success.

    output must be new and lie in paper. On failure logs/partial output are kept;
    retry in a new directory. The caller must not consume without publication.json.
    """
    paper, plan_path, output = map(lambda p: Path(p).resolve(), (paper, plan_path, output))
    if not plan_path.is_relative_to(paper) or not output.is_relative_to(paper):
        raise ProtocolError("Plan and output must lie in paper directory")
    plan_hash = file_hash(plan_path)
    plan = read_json(plan_path)
    if file_hash(plan_path) != plan_hash:
        raise ProtocolError("Conversion plan changed while reading")
    check_plan(paper, plan)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ProtocolError("Conversion image must be pinned by image ID")
    output.mkdir()  # exclusive: preserve failed attempts
    script = Path(__file__).with_name("tensor_conversion.py")
    frozen_script = output / "converter.py"
    frozen_script.write_bytes(script.read_bytes())
    entries = []
    for row in plan["conversions"]:
        item = output / row["name"]
        item.mkdir()
        src = contained(paper, row["source"], must_exist=True)
        name = "mrh-convert-" + uuid.uuid4().hex[:16]
        command = ["docker", "run", "--name", name, "--network", "none", "--read-only",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--user", "10001:10001", "--cpus", "1", "--memory", "1g", "--memory-swap", "1g",
                   "--pids-limit", "64", "--ulimit", "fsize=268435456:268435456",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001",
                   "--mount", f"type=bind,src={_mount_src(src)},dst=/input.pt,readonly",
                   "--mount", f"type=bind,src={_mount_src(frozen_script)},dst=/converter.py,readonly",
                   "--mount", f"type=bind,src={_mount_src(item)},dst=/output",
                   "--entrypoint", "python", image_id, "/converter.py",
                   "--source", "/input.pt", "--output", "/output/data.npz",
                   "--manifest", "/output/manifest.json", "--expected-source-sha256", row["source_sha256"]]
        try:
            result = docker(command, timeout=120)
            write_json(item / "execution.json", {"command": command, "result": result})
            if result["returncode"] != 0 or result.get("timed_out"):
                raise ProtocolError("Tensor conversion failed; inspect " + str(item / "execution.json"))
        finally:
            cleanup = docker(["docker", "rm", "-f", name], timeout=20)
            write_json(item / "cleanup.json", cleanup)
        receipt = read_json(item / "manifest.json")
        if receipt["source"]["sha256"] != row["source_sha256"] or receipt["output"]["sha256"] != file_hash(item / "data.npz"):
            raise ProtocolError("Conversion output identity mismatch")
        # Only neutral representation metadata is public; no source paths/URLs or adjudication.
        write_json(item / "array_metadata.json", {"schema_version": "neutral-tensor-arrays-1",
                   "container_type": receipt["container_type"], "arrays": receipt["arrays"],
                   "data_sha256": receipt["output"]["sha256"], "nonfinite_policy": "preserve"})
        entries.append({**row, "output": (item / "data.npz").relative_to(paper).as_posix(),
                        "output_sha256": receipt["output"]["sha256"],
                        "metadata": (item / "array_metadata.json").relative_to(paper).as_posix(),
                        "metadata_sha256": file_hash(item / "array_metadata.json"),
                        "receipt": (item / "manifest.json").relative_to(paper).as_posix(),
                        "receipt_sha256": file_hash(item / "manifest.json")})
    check_plan(paper, plan)  # detect persistent source/evidence changes
    if file_hash(plan_path) != plan_hash:
        raise ProtocolError("Conversion plan changed during execution")
    publication = {"schema_version": "factory-data-conversion-publication-1", "image_id": image_id,
                   "plan": plan_path.relative_to(paper).as_posix(), "plan_sha256": plan_hash,
                   "converter_sha256": file_hash(frozen_script), "entries": entries,
                   "note": "Representation-only conversion; no scientific/rights acceptance. No author code executed."}
    write_json(output / "publication.json", publication)
    return publication


def apply_conversions(paper, prepopulated):
    """Fail closed if a configured publication is incomplete or its bindings change."""
    paper = Path(paper)
    folder = paper / "data_conversion"
    if not folder.exists():
        return prepopulated, ""
    pub = read_json(contained(paper, "data_conversion/publication.json", must_exist=True))
    if pub.get("schema_version") != "factory-data-conversion-publication-1":
        raise ProtocolError("Unknown conversion publication")
    plan_path = contained(paper, pub["plan"], must_exist=True)
    if file_hash(plan_path) != pub["plan_sha256"]:
        raise ProtocolError("Conversion plan changed")
    plan = read_json(plan_path)
    check_plan(paper, plan)
    if file_hash(contained(paper, "data_conversion/converter.py", must_exist=True)) != pub["converter_sha256"]:
        raise ProtocolError("Conversion script snapshot changed")
    expected = {r["replace_path"]: r for r in plan["conversions"]}
    entries = {r["replace_path"]: r for r in pub["entries"]}
    if set(entries) != set(expected) or len(entries) != len(pub["entries"]):
        raise ProtocolError("Conversion publication/plan mismatch")
    for target, r in entries.items():
        if any(r[k] != v for k, v in expected[target].items()):
            raise ProtocolError("Conversion mapping changed")
        for key in ("output", "metadata", "receipt"):
            if file_hash(contained(paper, r[key], must_exist=True)) != r[key + "_sha256"]:
                raise ProtocolError("Converted asset changed")
    destinations = [r["to"] for r in prepopulated]
    if len(destinations) != len(set(destinations)):
        raise ProtocolError("Duplicate prepopulated destination")
    converted_sources = {r["source"] for r in entries.values()}
    converted_hashes = {r["source_sha256"] for r in entries.values()}
    out, descriptions, used = [], [], set()
    for row in prepopulated:
        r = entries.get(row["to"])
        if r is None:
            if row["from"] in converted_sources or row["sha256"] in converted_hashes:
                raise ProtocolError("Configured raw conversion source renamed in job")
            out.append(row); continue
        if row["from"] != r["source"] or row["sha256"] != r["source_sha256"]:
            raise ProtocolError("Conversion does not match job source")
        used.add(row["to"])
        target = "assets/converted_data/" + r["name"]
        provenance = {**row.get("provenance", {}), "conversion_publication_sha256": file_hash(folder / "publication.json"),
                      "original_sha256": row["sha256"]}
        for key, suffix in (("output", ".npz"), ("metadata", ".metadata.json")):
            out.append({"from": r[key], "to": target + suffix, "sha256": r[key + "_sha256"], "provenance": provenance})
        descriptions.append(f"- {row['to']} replaced by {target}.npz; array order, dtype, shape and neutral keys in {target}.metadata.json.")
    if not used:
        return out, ""
    if used != set(entries):
        raise ProtocolError("Job contains only part of the configured conversion set")
    if len(out) != len({r["to"] for r in out}):
        raise ProtocolError("Converted destination collides with existing asset")
    return out, ("\n\nTrusted controller representation conversion (supersedes raw binary prepopulation above and any previous candidate paths):\n"
                 + "\n".join(descriptions) + "\nUse ONLY these neutral .npz files as solver data. Original .pt files are not prepopulated. "
                 "Read metadata, adapt the loader using numpy.load(..., allow_pickle=False), preserve event order and dtype. "
                 "Do not execute or copy previous candidate conversion code. No values, splits, resampling or scientific settings were changed.")
