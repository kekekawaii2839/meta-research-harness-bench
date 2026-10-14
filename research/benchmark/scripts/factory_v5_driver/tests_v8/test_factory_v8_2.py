"""Offline tests for factory v8.2 frame-finding routing (no model calls)."""
import unittest

import factory_v8_2 as v82

FRAME = {"files": [{"path": "assets/task.md"}, {"path": "assets/background_report.md"}, {"path": "assets/check_proposal.py"}]}


def finding(fid, locator, issue, action, fact_id=None):
    return {"id": fid, "locator": locator, "observed_issue": issue, "repair_action": action, "fact_id": fact_id}


class Routing(unittest.TestCase):
    def test_routes_frame_findings_and_blocks_paper_dependent_ones(self):
        review = {"findings": [
            finding("F1", "citation_abstract (bg001_abs_page); compare request.json scope_request items (b),(e) and paper_html S1.p4",
                    "background_report.md omits scope items", "Re-run framing adding the overlap evidence"),
            finding("F2", "citation_abstract: 'less than 10-20%'", "background_report.md drops 'less than'",
                    "In the re-frame, write 'less than 10-20% of the original size'.", "PF-10"),
            finding("F3", "main(), loop", "check_proposal.py crashes on a non-string id", "Guard with isinstance(sid, str)."),
            finding("F4", "private rubric R2", "rubric threshold too strict", "Relax R2 to the public limit."),
            finding("F5", "task.md 'Deliverables'", "names a forbidden coined term", "Rename it to the Glorbnet layer.")]}
        adj = {"finding_decisions": [{"finding_index": i, "decision": "accept"} for i in range(5)]}
        routed, blocked, ctor = v82.classify_frame_findings(review, adj, FRAME, ["glorbnet"])
        self.assertEqual([r["id"] for r in routed], ["F2", "F3"])
        self.assertEqual({b["id"] for b in blocked}, {"F1", "F5"})
        self.assertEqual([c["id"] for c in ctor], ["F4"])
        self.assertNotIn("observed_issue", routed[0])  # reviewer's issue text (may quote the paper) never passed

    def test_only_accepted_findings_and_adjudicator_note_wins(self):
        review = {"findings": [finding("F1", "task.md", "x", "reviewer text"), finding("F2", "task.md", "y", "z")]}
        adj = {"finding_decisions": [{"finding_index": 0, "decision": "accept", "repair_note": "adjudicator text"},
                                     {"finding_index": 1, "decision": "reject"}]}
        routed, blocked, ctor = v82.classify_frame_findings(review, adj, FRAME, [])
        self.assertEqual([(r["id"], r["rewrite_guidance"]) for r in routed], [("F1", "adjudicator text")])
        self.assertEqual(blocked, [])

    def test_background_source_ids_are_not_target_sources(self):
        review = {"findings": [finding("F1", "bg012_abs_page sentence 2; background_report.md", "misquote", "Quote bg012_abs_page exactly.")]}
        routed, blocked, _ = v82.classify_frame_findings(review, {"finding_decisions": []}, FRAME, [])
        self.assertEqual(len(routed), 1)
        self.assertEqual(blocked, [])


if __name__ == "__main__":
    unittest.main()
