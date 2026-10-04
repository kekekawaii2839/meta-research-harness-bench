"""Write checks.json for the 4 GETS v5 tasks. Every check transcribes a requirement stated in that task's
public task.md (mechanical transcription by the maintainer; no scientific judgement). Paths: outputs are
relative to the collected /work directory, assets relative to the public root."""
import json
from pathlib import Path

UNITS = Path(r"D:/mrhbench-local-pilot/factory-v5/papers/iclr2025-qgsXsqahMq/units")
IDENTITY = {"method_acronym": r"(?-i:\bGETS\b)", "method_name": r"graph\s+ensemble\s+temperature\s+scaling",
            "arxiv_id": r"2410\.09570", "openreview_id": r"qgsXsqahMq"}

SPECS = {
 "WRITE_EVIDENCE": [
  {"id": "we-files", "type": "exists", "severity": "hard", "requirement": "task.md Required outputs 1-5",
   "files": ["submission/make_figure.py", "submission/caption.md", "submission/manifest.json", "submission/interpretation.md"],
   "any_of": [["submission/*.png", "submission/*.pdf", "submission/*.svg"]]},
  {"id": "we-manifest-schema", "type": "json_schema", "severity": "hard", "requirement": "manifest conforms to manifest.schema.json",
   "file": "submission/manifest.json", "schema_asset": "assets/manifest.schema.json"},
  {"id": "we-manifest-rows-exist", "type": "ids_in", "severity": "hard", "requirement": "every manifest row_id maps to a CSV row",
   "file": "submission/manifest.json", "path": "plotted_values.*.row_id", "allowed_regex": r"(?m)^(R\d{3}),", "allowed_asset": "assets/data/ece_main_table.csv"},
  {"id": "we-manifest-values-match", "type": "table_values", "severity": "flag", "requirement": "every manifest value matches the CSV field",
   "file": "submission/manifest.json", "path": "plotted_values", "table_asset": "assets/data/ece_main_table.csv",
   "key_column": "row_id", "id_field": "row_id", "field_field": "field", "value_field": "value_shown"},
  {"id": "we-interpretation-length", "type": "word_count", "severity": "flag", "requirement": "interpretation at most about 250 words",
   "file": "submission/interpretation.md", "min": 1, "max": 275},
  {"id": "we-offline-regeneration", "type": "rerun", "severity": "hard", "requirement": "make_figure.py regenerates the artifact and manifest deterministically offline",
   "workdir": "submission", "command": ["python", "make_figure.py"], "compare": ["submission/manifest.json"],
   "compare_flag": ["submission/*.png", "submission/*.pdf", "submission/*.svg"], "timeout": 300},
  {"id": "we-no-fabricated-inference", "type": "regex_none", "severity": "flag", "requirement": "no CIs, standard errors, p-values or significance claims",
   "file": "submission/caption.md", "patterns": {"ci": r"confidence interval|\bCI\b", "stderr": r"standard error", "pvalue": r"p[- ]?value", "significance": r"statistically significant|significance"}},
  {"id": "we-identity-caption", "type": "regex_none", "severity": "flag", "requirement": "do not name the source paper/method", "file": "submission/caption.md", "patterns": IDENTITY},
  {"id": "we-identity-interp", "type": "regex_none", "severity": "flag", "requirement": "do not name the source paper/method", "file": "submission/interpretation.md", "patterns": IDENTITY}],
 "WRITE_CONTENT": [
  {"id": "wc-files", "type": "exists", "severity": "hard", "requirement": "both required outputs",
   "files": ["output/method_section.md", "output/fact_trace.json"]},
  {"id": "wc-length", "type": "word_count", "severity": "flag", "requirement": "about 1,000-2,500 words of prose excluding displayed equations",
   "file": "output/method_section.md", "min": 1000, "max": 2500, "strip_math": True},
  {"id": "wc-required-content", "type": "regex_all", "severity": "hard", "requirement": "required equations and fixed constants",
   "file": "output/method_section.md",
   "patterns": {"topk": r"top\s*-?\s*k|\\operatorname\{TopK\}|TopK", "softmax": r"softmax", "softplus": r"softplus",
                "gaussian_noise": r"\\mathcal\{N\}\s*\(\s*0\s*,\s*1\s*\)|N\s*\(\s*0\s*,\s*1\s*\)",
                "gcn_normalisation": r"D\}*\s*\^\s*\{?\s*-\s*(1\s*/\s*2|\\t?frac\{1\}\{2\})",
                "M_7": r"M\s*=\s*7", "k_2": r"k\s*=\s*2", "embed_16": r"\b16\b", "B_10": r"B\s*=\s*10", "ece": r"\bECE\b"}},
  {"id": "wc-trace-ids", "type": "ids_in", "severity": "hard", "requirement": "every fact ID in the trace exists in the fact sheet",
   "file": "output/fact_trace.json", "path": "sections.*.fact_ids.*", "allowed_regex": r"(?m)^\*\*(F\d{2}) \[", "allowed_asset": "assets/fact_sheet.md"},
  {"id": "wc-impl-derived-marked", "type": "regex_all", "severity": "hard", "requirement": "F11 and F17 listed in implementation_derived_marked",
   "file": "output/fact_trace.json",
   "patterns": {"F11": r"\"implementation_derived_marked\"\s*:\s*\[[^\]]*\"F11\"", "F17": r"\"implementation_derived_marked\"\s*:\s*\[[^\]]*\"F17\""}},
  {"id": "wc-out-of-scope-numbers", "type": "regex_none", "severity": "flag", "requirement": "no results, hyperparameter values or runtime claims",
   "file": "output/method_section.md",
   "patterns": {"plusminus": r"±|\\pm", "percent": r"\d+\.\d+\s*\\?%", "oom": r"\bOOM\b", "lr": r"learning rate", "wd": r"weight decay", "dropout": r"dropout", "gpu": r"\bGPU\b"}},
  {"id": "wc-identity", "type": "regex_none", "severity": "flag", "requirement": "refer to the method only by a neutral name", "file": "output/method_section.md", "patterns": IDENTITY}],
 "LIT": [
  {"id": "lit-files", "type": "exists", "severity": "hard", "requirement": "report.md and references.json", "files": ["output/report.md", "output/references.json"]},
  {"id": "lit-manifest-schema", "type": "json_schema", "severity": "hard", "requirement": "references.json validates against report_manifest.schema.json",
   "file": "output/references.json", "schema_asset": "assets/lit/report_manifest.schema.json"},
  {"id": "lit-identity", "type": "regex_none", "severity": "flag", "requirement": "no knowledge of the post-cutoff source paper", "file": "output/report.md", "patterns": IDENTITY}],
 "IDEA": [
  {"id": "idea-files", "type": "exists", "severity": "hard", "requirement": "proposal.json", "files": ["output/proposal.json"]},
  {"id": "idea-schema", "type": "json_schema", "severity": "hard", "requirement": "proposal.json validates against proposal_output_schema.json (>= 2 hypotheses, >= 3 grounding refs)",
   "file": "output/proposal.json", "schema_asset": "assets/idea/proposal_output_schema.json"},
  {"id": "idea-ref-ids", "type": "ids_in", "severity": "hard", "requirement": "every cited ref_id exists in the background report",
   "file": "output/proposal.json", "path": "background_grounding.*.ref_id", "allowed_regex": r"(?m)^\| (R\d{2}) \|", "allowed_asset": "assets/idea/background_report.md"},
  {"id": "idea-no-results", "type": "regex_none", "severity": "flag", "requirement": "no experimental results reported",
   "file": "output/proposal.json", "patterns": {"observed": r"we (observed|found|obtained|measured)", "results_show": r"(our )?(experiments|results) (show|demonstrate)ed?"}},
  {"id": "idea-identity", "type": "regex_none", "severity": "flag", "requirement": "no identification of the source paper", "file": "output/proposal.json", "patterns": IDENTITY}],
}

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from output_checks import validate_spec
    for unit, spec in SPECS.items():
        validate_spec(spec)
        dest = UNITS / unit / "checks.json"
        dest.write_text(json.dumps({"schema_version": "task-checks-1", "unit": unit, "author": "maintainer transcription of task.md requirements",
                                    "checks": spec}, ensure_ascii=False, indent=1), encoding="utf8")
        print(unit, len(spec), "checks ->", dest)
