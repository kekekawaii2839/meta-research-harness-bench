"""S3 cpu.run note (user decision 2026-10-13: "cpu.run加上吧"; zero model calls).

v5/v6/v7 EXP/WC/WE task texts (constructor-written) do not state the CPU tool signature; v8-contract task texts do. For
every task flagged by the S3 inventory (D:/mrhbench-local-pilot/s3-release-inventory.json, note
"content_note:no_cpu_run_signature_in_public_text") whose public tools grant cpu_python_execution, this script publishes a
NEW release directory `release-s3` = a byte copy of the task's current release with ONE change: controller publication
note 5 (below, wording taken only from runtime/interface_container_v4.json) appended after note 4 of public.prompt. The
three files that bind the task.json hash (compile_record.json, collection_contract_provenance.json,
identity_release_record.json) get the new hash; s3_provenance.json records old/new hashes. Older releases are untouched.
Usage: python s3_cpu_note.py [--dry]
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys

sys.path.insert(0, r"C:\Users\li_ha\Documents\ChatGPT\meta-research-harness-bench\research\benchmark")
from mrhbench.io import canonical  # noqa: E402

INVENTORY = Path(r"D:/mrhbench-local-pilot/s3-release-inventory.json")
FLAG = "content_note:no_cpu_run_signature_in_public_text"
NOTE4 = "4. Model/tool budget:"
NOTE5 = ("5. CPU tool (capability cpu_python_execution): cpu.run(script, arguments, timeout_seconds). script = relative "
         "path of a .py artifact you have written (write it first with artifact.write_text); arguments = optional list "
         "of strings passed to the script; timeout_seconds = optional positive number, clipped to the remaining task "
         "wall time. It returns returncode, stdout, stderr, timed_out and output_limited; inspect or create other files "
         "with the artifact tools. A script's return code alone is not scientific evidence.")
BINDERS = ("compiled/compile_record.json", "identity_release_record.json")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main(dry):
    inv = json.loads(INVENTORY.read_text(encoding="utf8"))
    rows = []
    for t in inv["tasks"]:
        if FLAG not in (t.get("notes") or []):
            continue
        src, unit = Path(t["release_dir"]), Path(t["unit_dir"])
        dst = unit / "release-s3"
        tj = next((src / "compiled").glob("task-*/task.json"))
        raw = tj.read_bytes()
        task = json.loads(raw)
        if canonical(task) + b"\n" != raw:
            raise SystemExit("task.json is not canonical: " + str(tj))
        if "cpu_python_execution" not in task["public"]["tools"]:
            rows.append({"task": t["task_id"], "skipped": "cpu.run not granted"})
            continue
        prompt = task["public"]["prompt"]
        if prompt.count(NOTE4) != 1 or "\n5. " in prompt[prompt.index(NOTE4):] or "cpu.run(script" in prompt:
            raise SystemExit("unexpected note block: " + str(tj))
        i = prompt.index(NOTE4)
        j = prompt.find("\n", i)
        j = len(prompt) if j < 0 else j
        task["public"]["prompt"] = prompt[:j] + "\n" + NOTE5 + prompt[j:]
        new_raw = canonical(task) + b"\n"
        old_sha, new_sha = sha(raw), sha(new_raw)
        row = {"paper": t["paper_id"], "type": t["task_type"], "task_id": t["task_id"], "source_release": t["release"],
               "release_dir": str(dst), "old_task_sha256": old_sha, "new_task_sha256": new_sha}
        rows.append(row)
        if dry:
            continue
        if dst.exists():
            raise SystemExit("exists: " + str(dst))
        shutil.copytree(src, dst)
        dtj = next((dst / "compiled").glob("task-*/task.json"))
        dtj.write_bytes(new_raw)
        binders = list(BINDERS) + [str(dtj.parent.relative_to(dst) / "collection_contract_provenance.json")]
        for b in binders:
            p = dst / b
            if p.exists():
                text = p.read_bytes()
                if old_sha.encode() not in text:
                    raise SystemExit("binder lacks old hash: " + str(p))
                p.write_bytes(text.replace(old_sha.encode(), new_sha.encode()))
        leftover = [str(p) for p in dst.rglob("*") if p.is_file() and p.suffix == ".json" and old_sha.encode() in p.read_bytes()]
        if leftover:
            raise SystemExit("old hash still referenced: %s" % leftover)
        (dst / "s3_provenance.json").write_text(json.dumps({
            "decided": "user 2026-10-13: cpu.run加上吧", "tool": "s3_cpu_note.py (zero model calls)",
            "source_release": t["release"], "change": "public.prompt: controller publication note 5 appended after note 4",
            "note5": NOTE5, "old_task_sha256": old_sha, "new_task_sha256": new_sha,
            "rebound_files": binders}, ensure_ascii=False, indent=1), encoding="utf8", newline="")
    out = Path(r"D:/mrhbench-local-pilot/s3-cpu-note-%s.json" % ("dryrun" if dry else "applied"))
    out.write_text(json.dumps({"rows": rows, "note5": NOTE5}, ensure_ascii=False, indent=1), encoding="utf8", newline="")
    print("tasks", len(rows), "skipped", sum(1 for r in rows if "skipped" in r), "->", out)


if __name__ == "__main__":
    main("--dry" in sys.argv)
