"""Material factory v7 (2026-10-05): factory v6 + public-surface rules + automatic controller asset materialization.

Differences from factory v6 (everything else is the unchanged v6 composition, incl. OpenReview fetch, corrected
background cutoff, --workers, admissibility/leak rules, frozen budgets, platform lint):
  1. prompts: the frozen snapshot appends prompts_next/constructor_platform_contract_v7.txt (v6.1 exact tool list +
     public-surface rules R1-R5) to the constructor addendum and prompts_next/reviewer_platform_check_v7.txt
     (v6.1 authoritative tool description + public-surface and private-vs-public checks) to material_reviewer.txt.
     Causes (factory v6): contribution leaks in public justification fields incl. negative statements (6 withdrawn
     tasks), private checks stricter than the public contract (3 dropped units), incomplete tool list (2 misjudgements).
  2. controller step: right after a constructor returns and before the reviewer starts, the controller byte-copies
     prepopulated assets to the public paths listed in tasks[i].controller_asset_materialization (hash-verified, only
     inside assets/), then fills CONTROLLER_FILL hashes as before. Constructors have no shell and cannot copy files.
  3. platform lint (task_platform_lint) includes the public_field_disclosure check (justification/visibility/scope/
     note fields, incl. those embedded in the compiled prompt).
Usage: same CLI as factory_v6.py (init / run [--workers N] / status).
"""
from pathlib import Path
import json
import shutil
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import factory_v6  # noqa: E402  (platform patches, v6 rules; rebinds factory_v5.open_factory/build_prompt_snapshot)
import mrhbench.material_batch as _mb  # noqa: E402
from mrhbench.io import read_json, write_json, file_hash, contained, utc_now, ProtocolError  # noqa: E402

factory_v6.CONTRACT = DRIVER / "prompts_next/constructor_platform_contract_v7.txt"
factory_v6.REVIEW_CHECK = DRIVER / "prompts_next/reviewer_platform_check_v7.txt"

_orig_fill = _mb.fill_sentinel_hashes


def materialize_assets(output_root):
    """Controller byte copies for controller_asset_materialization mappings; returns the copy log."""
    output_root = Path(output_root)
    pkg = output_root / "package.json"
    if not pkg.is_file():
        return []
    log = []
    for t in read_json(pkg).get("tasks", []):
        m = t.get("controller_asset_materialization") or {}
        for row in (m.get("mappings") or []) if isinstance(m, dict) else []:
            src, dst, sha = row.get("prepopulated_path"), row.get("public_path"), row.get("sha256")
            if not (isinstance(src, str) and isinstance(dst, str) and src.startswith("assets/") and dst.startswith("assets/")) or ".." in src + dst:
                raise ProtocolError("controller_asset_materialization path outside assets/")
            s, d = contained(output_root, src, must_exist=True), contained(output_root, dst)
            if sha and file_hash(s) != sha:
                raise ProtocolError("controller_asset_materialization hash mismatch: " + src)
            if d.exists():
                if file_hash(d) != file_hash(s):
                    raise ProtocolError("controller_asset_materialization target exists and differs: " + dst)
                log.append({"from": src, "to": dst, "sha256": file_hash(d), "action": "already_present"})
                continue
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(s, d)
            log.append({"from": src, "to": dst, "sha256": file_hash(d), "action": "copied"})
    if log:
        write_json(output_root.parent / "controller_materialization.json",
                   {"at": utc_now(), "copies": log, "model_calls_made": 0,
                    "note": "factory v7 controller step before review; hash-verified byte copies inside assets/"})
    return log


def fill_sentinel_hashes(output_root, *a, **k):
    materialize_assets(output_root)
    return _orig_fill(output_root, *a, **k)


_mb.fill_sentinel_hashes = fill_sentinel_hashes


def main():
    """Same CLI as factory_v6; the frozen prompt snapshot records the v7 contract/check sources and hashes."""
    factory_v6.main()


if __name__ == "__main__":
    main()
