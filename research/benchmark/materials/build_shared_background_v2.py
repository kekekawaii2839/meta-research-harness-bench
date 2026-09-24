"""Re-index immutable v1 backgrounds as faithful R2 seed corpus, not full coverage."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import read_json, write_json
from mrhbench.literature import original_abstract, SharedCorpusView


def build(destination):
    old = read_json(ROOT / "materials/background_corpus.json")
    rows = []
    for document in old["documents"]:
        row = original_abstract(document, ROOT.parents[1])
        row.pop("support_pages", None)
        row.update(index_approved=True, disclosure_status="verified_background_version",
                   version_number=1, paper_aliases=[row["source_url"].rsplit("/", 1)[-1].removesuffix("v1")])
        rows.append(row)
    SharedCorpusView(rows, "2024-09-01", set())
    result = {"schema_version": "shared-background-1", "documents": rows,
              "coverage_status": "seed_8_only_not_accepted_for_field_coverage",
              "selection_status": "existing_backgrounds_only_additional_cross_package_neighbors_pending",
              "relevance_labels": "private_per_task_not_embedded",
              "rights": "service_only_no_blanket_redistribution_permission",
              "full_text": "pinned_original_PDF_pages_available",
              "ranking": "deterministic_lexical_abstract_baseline_not_validated_retrieval_quality"}
    write_json(destination, result, exclusive=True)
    return result

if __name__ == "__main__":
    result = build(ROOT / "materials/pilot_v2/shared_background_corpus.json")
    print({"documents": len(result["documents"]), "formal_accepted": False})
