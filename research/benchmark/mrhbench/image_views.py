"""Controller-side image views for the Claude transports (AGENTS §0.2.13).

The Claude CLI downscales images whose long side exceeds 2000 px before the API request
(observed integration v2 WRITE_EVIDENCE: 2550x1080 delivered as 2000x847). Two remedies:
full-resolution tiles that stay within the limit (so exact bytes reach the model), and a
check that a downscaled delivery is a faithful derivative of the released image.
Derived views are labelled as such; they never replace the original record.
"""
from __future__ import annotations

import io
import math

PROVIDER_MAX_SIDE = 2000
TILE_SIDE = 1600
TILE_OVERLAP = 128


def _open(data):
    from PIL import Image
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def image_size(data):
    return _open(data).size


def full_resolution_tiles(data, *, max_side=PROVIDER_MAX_SIDE, tile=TILE_SIDE, overlap=TILE_OVERLAP):
    """Lossless PNG tiles of an oversized image; empty when the image already fits."""
    image = _open(data)
    width, height = image.size
    if max(width, height) <= max_side:
        return []
    step = tile - overlap
    cols = max(1, math.ceil((width - overlap) / step))
    rows = max(1, math.ceil((height - overlap) / step))
    tiles = []
    for r in range(rows):
        for c in range(cols):
            left, top = min(c * step, max(0, width - tile)), min(r * step, max(0, height - tile))
            box = (left, top, min(left + tile, width), min(top + tile, height))
            out = io.BytesIO()
            image.crop(box).save(out, format="PNG", optimize=False)
            tiles.append({"row": r, "col": c, "box": list(box), "png": out.getvalue()})
    return tiles


def downscaled_match(original, delivered, *, min_psnr=30.0):
    """Is `delivered` a faithful uniformly downscaled rendering of `original`?"""
    from PIL import Image
    a, b = _open(original).convert("RGB"), _open(delivered).convert("RGB")
    (wa, ha), (wb, hb) = a.size, b.size
    scale = wb / wa
    aspect_ok = wb <= wa and hb <= ha and abs(ha * scale - hb) <= 1.5
    reference = a.resize((wb, hb), Image.LANCZOS)
    diff = sum((x - y) ** 2 for p, q in zip(reference.getdata(), b.getdata()) for x, y in zip(p, q))
    mse = diff / (wb * hb * 3)
    psnr = float("inf") if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    return {"original_size": [wa, ha], "delivered_size": [wb, hb], "scale": scale, "aspect_preserved": aspect_ok,
            "psnr_vs_lanczos_reference_db": psnr if math.isfinite(psnr) else "inf",
            "faithful_downscale": bool(aspect_ok and psnr >= min_psnr), "min_psnr_db": min_psnr}
