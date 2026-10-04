"""Controller-owned byte-preserving repair seeds and independent review navigation.

These helpers do not edit scientific content, repair declared hashes, or grant
scientific approval. Inputs must be quiescent: checks are not an OS sandbox or
an atomic filesystem snapshot against concurrent adversarial mutation.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import stat
from pathlib import Path


EXCLUDED_SEED_NAME = "package.constructor_original.json"
REVIEW_WARNING = (
    "Unchanged bytes do not imply scientific acceptance. Independently inspect "
    "all unresolved findings in the previous review and their dependencies. "
    "Method, formula, scientific semantics or code changes require related "
    "source, data, tests and downstream-claim checks. If impact cannot be "
    "reliably bounded, perform a full review. This navigation is not a pass "
    "decision; full current candidate and original sources remain required."
)


def _safe_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Links/reparse points are forbidden: {part}")
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise ValueError(f"Hardlinked files are forbidden: {part}")
    return path


def _disjoint(left: Path, right: Path) -> None:
    if left == right or left in right.parents or right in left.parents:
        raise ValueError("Source and destination trees must be disjoint")


def _tree(root: Path) -> dict[str, bytes]:
    root = _safe_path(root)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        _safe_path(path)
        if path.is_dir():
            continue
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError(f"Not a regular file: {path}")
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _identity(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _inventory(files: dict[str, bytes]) -> dict:
    return {name: _identity(data) for name, data in files.items()}


def _write_new(path: Path, data: bytes) -> None:
    _safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def seed_output(previous_candidate: Path, output: Path) -> dict:
    """Copy old files, preserving prepopulated outputs and recording conflicts.

    Existing files win even when their bytes differ. File/directory topology
    conflicts fail closed before copying. No old input is modified.
    """
    source, target = _safe_path(previous_candidate), _safe_path(output)
    _disjoint(source, target)
    before = _tree(source)
    existing = _tree(target) if target.exists() else {}
    excluded = [name for name in before if Path(name).name == EXCLUDED_SEED_NAME]
    candidates = {name: data for name, data in before.items() if name not in excluded}
    # Preflight the entire target topology before writing anything.
    for name in candidates:
        path = _safe_path(target / name)
        if path.exists() and not path.is_file():
            raise ValueError(f"File/directory collision: {name}")
        for parent in path.parents:
            if parent == target:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"File/directory collision: {name}")
    copied, preserved, conflicts = [], [], []
    target.mkdir(parents=True, exist_ok=True)
    for name, data in candidates.items():
        if name in existing:
            preserved.append(name)
            if data != existing[name]:
                conflicts.append({"path": name, "previous": _identity(data),
                                  "preserved_output": _identity(existing[name])})
        else:
            _write_new(target / name, data)
            copied.append(name)
    after = _tree(target)
    if _tree(source) != before:
        raise ValueError("Previous candidate changed during seeding")
    expected = {**candidates, **existing}
    if after != expected:
        raise ValueError("Output bytes changed during seeding")
    return {"schema_version": 1, "copied": copied, "preserved": preserved,
            "conflicts": conflicts, "excluded": excluded,
            "previous_inventory": _inventory(before), "output_inventory": _inventory(after),
            "copied_bytes": sum(len(candidates[name]) for name in copied)}


def _text(data: bytes) -> str | None:
    try:
        result = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if "\x00" in result else result


def _diff(before: dict[str, bytes], after: dict[str, bytes]) -> dict:
    entries = []
    counts = dict.fromkeys(("added", "deleted", "changed", "unchanged"), 0)
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name), after.get(name)
        status = "added" if old is None else "deleted" if new is None else (
            "unchanged" if old == new else "changed")
        counts[status] += 1
        entry = {"path": name, "status": status,
                 "before": None if old is None else _identity(old),
                 "after": None if new is None else _identity(new)}
        old_text, new_text = _text(old or b""), _text(new or b"")
        entry["binary"] = old_text is None or new_text is None
        if status != "unchanged" and not entry["binary"]:
            chunks = difflib.unified_diff(old_text.splitlines(keepends=True),
                                          new_text.splitlines(keepends=True),
                                          fromfile="before/" + name, tofile="after/" + name)
            entry["unified_diff"] = "".join(
                chunk if chunk.endswith("\n") else chunk + "\n\\ No newline at end of file\n"
                for chunk in chunks)
        entries.append(entry)
    return {"schema_version": 1, "entries": entries, "counts": counts,
            "before_inventory": _inventory(before), "after_inventory": _inventory(after),
            "bytes": {"before_total": sum(map(len, before.values())),
                      "after_total": sum(map(len, after.values())),
                      "changed_or_deleted_before": sum(e["before"]["bytes"] for e in entries
                          if e["status"] in ("changed", "deleted")),
                      "changed_or_added_after": sum(e["after"]["bytes"] for e in entries
                          if e["status"] in ("changed", "added"))},
            "truncated": False}


def diff_outputs(before: Path, after: Path) -> dict:
    """Full byte inventories and untruncated UTF-8 text diffs, never model claims."""
    return _diff(_tree(before), _tree(after))


def _json_changes(before: dict[str, bytes], after: dict[str, bytes]) -> dict:
    """JSON structural changes only; never infer scientific meaning."""
    changes, fallbacks = [], []

    def walk(path, pointer, old, new, has_old=True, has_new=True):
        if has_old and has_new and type(old) is type(new):
            if isinstance(old, dict):
                for key in sorted(old.keys() | new.keys()):
                    token = key.replace("~", "~0").replace("/", "~1")
                    walk(path, pointer + "/" + token, old.get(key), new.get(key),
                         key in old, key in new)
                return
            if isinstance(old, list):
                for index in range(max(len(old), len(new))):
                    walk(path, pointer + "/" + str(index),
                         old[index] if index < len(old) else None,
                         new[index] if index < len(new) else None,
                         index < len(old), index < len(new))
                return
            if old == new:
                return
        entry = {"path": path, "pointer": pointer,
                 "operation": "add" if not has_old else "remove" if not has_new else "replace"}
        if has_old:
            entry["before"] = old
        if has_new:
            entry["after"] = new
        changes.append(entry)

    def reject_constant(value):
        raise ValueError(f"Nonstandard JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    for name in sorted(before.keys() | after.keys()):
        if before.get(name) == after.get(name):
            continue
        if not name.lower().endswith(".json"):
            fallbacks.append({"path": name, "reason": "not_json", "fallback": "diff_navigation.json"})
            continue
        try:
            old = json.loads(before[name], parse_constant=reject_constant,
                             object_pairs_hook=unique_object) if name in before else None
            new = json.loads(after[name], parse_constant=reject_constant,
                             object_pairs_hook=unique_object) if name in after else None
        except (ValueError, UnicodeError):
            fallbacks.append({"path": name, "reason": "json_parse_failed", "fallback": "diff_navigation.json"})
            continue
        walk(name, "", old, new, name in before, name in after)
    return {"schema_version": 1, "interpretation": "Structural JSON changes, not scientific interpretation",
            "changes": changes, "fallbacks": fallbacks, "truncated": False}


def prepare_incremental_review(previous_candidate: Path, previous_review: Path | None,
                               current_output: Path, destination: Path) -> dict:
    """Create fresh reviewer navigation, prior review and complete prior candidate.

    Destination must not exist. The caller must separately publish full current
    candidate and original sources to the independent reviewer.
    """
    previous = _safe_path(previous_candidate)
    current = _safe_path(current_output)
    review = _safe_path(previous_review) if previous_review is not None else None
    target = _safe_path(destination)
    for source in (previous, current, *((review,) if review is not None else ())):
        _disjoint(source, target)
    if target.exists():
        raise ValueError("Review destination must be new")
    missing_review = review is None or not review.exists()
    if not missing_review and not review.is_file():
        raise ValueError("Previous review must be a regular file")
    old_files, new_files = _tree(previous), _tree(current)
    review_bytes = None if missing_review else review.read_bytes()
    delta = _diff(old_files, new_files)
    structural_changes = _json_changes(old_files, new_files)
    for name, data in old_files.items():
        _write_new(target / "previous_candidate" / name, data)
    if not missing_review:
        _write_new(target / "previous_review" / review.name, review_bytes)
    record = {"schema_version": 1, "warning": REVIEW_WARNING,
              "previous_review": None if missing_review else {
                  "path": "previous_review/" + review.name, **_identity(review_bytes)},
              "missing_prior_review": missing_review,
              "full_review_required": missing_review,
              "previous_candidate_path": "previous_candidate",
              "full_current_candidate_required": True, "original_sources_required": True,
              "scientific_acceptance": "not_assessed", "diff": delta}
    _write_new(target / "diff_navigation.json",
               (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    _write_new(target / "json_changes.json",
               (json.dumps(structural_changes, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    lines = ["# Incremental review navigation", "", REVIEW_WARNING, "",
             "Read the byte-preserved previous review and full previous candidate here.",
             "Full current candidate and original sources must be separately available.",
             "First read json_changes.json for compact JSON Pointer change locations, then inspect full files as needed.",
             "JSON changes describe structure only, not scientific meaning. Text/binary fallbacks are explicitly listed.",
             "All hashes and full text diffs are in diff_navigation.json; nothing is truncated.", ""]
    if missing_review:
        lines.extend(["MISSING PRIOR REVIEW: full independent scientific review is required.", ""])
    lines.extend(f"- {entry['status']}: {json.dumps(entry['path'], ensure_ascii=False)}"
                 for entry in delta["entries"])
    _write_new(target / "diff_navigation.md", ("\n".join(lines) + "\n").encode("utf-8"))
    if (_tree(previous) != old_files or _tree(current) != new_files
            or (not missing_review and review.read_bytes() != review_bytes)):
        raise ValueError("Review inputs changed during publication")
    # Keep potentially very large full diffs in the published file, not prompts.
    return {key: value for key, value in record.items() if key != "diff"} | {
        "navigation_json": "diff_navigation.json", "navigation_markdown": "diff_navigation.md",
        "json_changes": "json_changes.json",
        "json_changes_identity": _identity((target / "json_changes.json").read_bytes()),
        "counts": delta["counts"], "bytes": delta["bytes"],
        "navigation_identity": _identity((target / "diff_navigation.json").read_bytes())}
