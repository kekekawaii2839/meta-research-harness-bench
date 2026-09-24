"""Minimal, self-authored reader for the FTCT Table 1 data assets.

Parsing and validation only. This module deliberately contains no plotting,
layout, colour or labelling logic: presentation design is the solver's job.
It works on any CSV/manifest pair that follows the same schema (same row ids
and column names), not only on the shipped values.

Usage:
    from table1_reader import load_rows, load_manifest, validate
    rows = load_rows("assets/common/ftct_table1_values.csv")
    manifest = load_manifest("assets/common/ftct_table1_manifest.json")
    validate(rows, manifest)
"""

import csv
import json
from decimal import Decimal

METRIC_COLUMNS = (
    "train_valid_loss",
    "train_vertices_acc",
    "train_values_acc",
    "test_vertices_acc",
    "test_values_acc",
    "test_whole_acc",
)
ACCURACY_COLUMNS = METRIC_COLUMNS[1:]


def load_rows(csv_path):
    """Return a list of dicts. Each metric keeps its printed string under
    '<col>' and gets an exact Decimal under '<col>__decimal' and a float
    under '<col>__float'. Parameter counts stay as printed strings; a float
    in millions is added under 'params_millions' for convenience."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            for col in METRIC_COLUMNS:
                text = rec[col]
                rec[col + "__decimal"] = Decimal(text)
                rec[col + "__float"] = float(text)
            p = rec["params_reported"]
            if not p.endswith("M"):
                raise ValueError("unexpected params format: %r" % p)
            rec["params_millions"] = float(p[:-1])
            rec["heads_reported"] = None if rec["heads_reported"] == "NA" else int(rec["heads_reported"])
            rec["layers_reported"] = int(rec["layers_reported"])
            rows.append(rec)
    return rows


def load_manifest(json_path):
    with open(json_path, encoding="utf-8") as fh:
        return json.load(fh)


def validate(rows, manifest):
    """Check the CSV against the provenance manifest. Raises on mismatch."""
    if len(rows) != len(manifest["cells"]):
        raise ValueError("row count mismatch")
    by_id = {c["row_id"]: c for c in manifest["cells"]}
    for rec in rows:
        cell = by_id[rec["row_id"]]
        if cell["params_reported"]["value"] != rec["params_reported"]:
            raise ValueError("params mismatch for %s" % rec["row_id"])
        for col in METRIC_COLUMNS:
            if cell[col]["value"] != rec[col]:
                raise ValueError("value mismatch %s/%s" % (rec["row_id"], col))
        for col in ACCURACY_COLUMNS:
            if not (Decimal(0) <= rec[col + "__decimal"] <= Decimal(1)):
                raise ValueError("accuracy out of [0,1]: %s/%s" % (rec["row_id"], col))
        if rec["train_valid_loss__decimal"] <= 0:
            raise ValueError("non-positive loss for %s" % rec["row_id"])
    return True


def cell_locator(manifest, row_id, column):
    """Return the source cell locator string for (row_id, column)."""
    for c in manifest["cells"]:
        if c["row_id"] == row_id:
            return c[column]["cell"]
    raise KeyError(row_id)
