"""Trusted tensor-only conversion worker; execute in a bounded offline container.

Importing this module does not import torch or numpy. weights_only is NOT an OS
sandbox: callers must provide a current trusted runtime, read-only source mount,
fresh output directory, memory/storage limits and a hard external deadline.
No author code, custom safe globals, unsafe loading fallback or dtype casts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat


def _identity(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    stream.seek(0)
    return {"sha256": digest.hexdigest(), "bytes": size}


def _arrays(value, torch, np, max_array_bytes):
    if type(value) is torch.Tensor:
        kind, items = "tensor", [(None, value)]
    elif type(value) in (list, tuple):
        kind, items = type(value).__name__, list(enumerate(value))
    elif type(value) is dict and all(type(k) is str for k in value):
        kind, items = "dict", list(value.items())
    else:
        raise ValueError("expected a plain Tensor, list/tuple of Tensor, or str-key dict of Tensor")
    arrays, metadata, total_bytes = {}, [], 0
    for i, (locator, tensor) in enumerate(items):
        if type(tensor) is not torch.Tensor:
            raise ValueError("nested values and Tensor subclasses are unsupported")
        if tensor.layout != torch.strided or tensor.is_quantized:
            raise ValueError("only dense non-quantized tensors are supported")
        # numpy() refuses unsupported dtypes (e.g. bfloat16); never silently cast.
        array = tensor.detach().cpu().resolve_conj().resolve_neg().numpy()
        if array.dtype.hasobject or array.dtype.kind not in "biufc":
            raise ValueError("only native numeric/bool numpy arrays are supported")
        total_bytes += int(array.nbytes)
        if total_bytes > max_array_bytes:
            raise ValueError("tensor array byte limit exceeded")
        key = f"arr_{i:06d}"
        arrays[key] = array
        metadata.append({
            "npz_key": key, "source_locator": locator,
            "torch_dtype": str(tensor.dtype), "numpy_dtype": array.dtype.str,
            "shape": list(array.shape), "elements": int(array.size),
            "bytes": int(array.nbytes),
            "nonfinite_elements": int(np.count_nonzero(~np.isfinite(array))),
            "c_order_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        })
    return kind, arrays, metadata


def convert_tensor_file(source, output, manifest, *, expected_source_sha256=None,
                        max_array_bytes=200 * 1024 * 1024):
    """Convert without overwriting; manifest is the completion marker.

    A failed conversion removes only files created by this invocation. An abrupt
    process kill may leave partial files: consumers must require and verify the
    manifest, and retries must use a fresh output directory. No trust is conferred
    on scientific interpretation, licensing or task suitability by conversion.
    """
    source, output, manifest = map(Path, (source, output, manifest))
    if type(max_array_bytes) is not int or max_array_bytes <= 0:
        raise ValueError("max_array_bytes must be a positive integer")
    if len({p.resolve() for p in (source, output, manifest)}) != 3:
        raise ValueError("source, output and manifest must be distinct")
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be a regular non-symlink file")
    if output.exists() or output.is_symlink() or manifest.exists() or manifest.is_symlink():
        raise FileExistsError("output or manifest already exists")
    import numpy as np
    import torch
    version = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:\+[^\s]+)?$", str(torch.__version__))
    if version is None or tuple(map(int, version.groups())) < (2, 6, 0):
        raise ValueError("torch >= 2.6.0 stable is required for weights-only loading")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as incoming:
        if not stat.S_ISREG(os.fstat(incoming.fileno()).st_mode):
            raise ValueError("source must be a regular file")
        source_id = _identity(incoming)
        if expected_source_sha256 is not None and source_id["sha256"] != expected_source_sha256:
            raise ValueError("source hash mismatch")
        value = torch.load(incoming, weights_only=True, map_location="cpu")
        kind, arrays, metadata = _arrays(value, torch, np, max_array_bytes)
        if _identity(incoming) != source_id:
            raise ValueError("source changed during conversion")
    receipt = {
        "schema_version": 1, "conversion": "tensor_only_pt_to_npz_v1",
        "source": {"name": source.name, **source_id}, "container_type": kind,
        "arrays": metadata, "nonfinite_policy": "preserve",
        "max_array_bytes": max_array_bytes,
        "runtime": {"torch": str(torch.__version__), "numpy": str(np.__version__)},
        "loader": {"weights_only": True, "map_location": "cpu"},
    }
    created = []
    try:
        # Reserve both names exclusively before serialization, never clobber.
        with output.open("xb+") as out:
            created.append(output)
            with manifest.open("x", encoding="utf-8", newline="\n") as meta:
                created.append(manifest)
                np.savez(out, **arrays)
                out.flush()
                receipt["output"] = {"name": output.name, **_identity(out)}
                meta.write(json.dumps(receipt, ensure_ascii=True, indent=2, allow_nan=False) + "\n")
        return receipt
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--max-array-bytes", type=int, default=200 * 1024 * 1024)
    args = parser.parse_args(argv)
    convert_tensor_file(args.source, args.output, args.manifest,
                        expected_source_sha256=args.expected_source_sha256,
                        max_array_bytes=args.max_array_bytes)


if __name__ == "__main__":
    main()
