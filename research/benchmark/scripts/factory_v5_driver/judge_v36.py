"""Judge v3.6 = judge v3.5 + four rules from the P11 sonnet-4-6/low trajectory review (2026-09-30).

Review findings (p11-sonnet46low-review-{A,B,C}.json): rule 4 (task/platform mismatches) was the weakest; the judge
did not read the harness's own stop record and once called an executor's own finish an "early stop"; it read a fact
sheet only partly; single defects were sometimes charged in several dimensions. Also carries the controller
platform-failure summary fix (ProtocolError description, failed path argument, harness self-report).
Same API as judge_v35 (import this instead). repo native_judge.py is not modified.
"""
import judge_v35
from judge_v35 import platform_failure_summary, summary_record  # noqa: F401  (re-exported)
import mrhbench.native_judge as nj

V36_RULES = '''
Additional rules (judge v3.6):
7. Check the task against the platform. Compare the task text and output contract with the tools, paths, field names
   and formats the platform actually provided (tool list, asset manifest, platform notes). Name every inconsistency
   explicitly as a task/platform mismatch in uncertainty (or serious_issues if it decided the outcome), and judge the
   solver's scientific work separately from its consequences.
8. Distinguish how the run ended. Read harness_self_report and the platform records in
   controller-platform-failure-summary: a solver that chose to finish is not an "early stop"; a harness stop because
   calls were reserved or exhausted is not a timeout. State the actual ending in your rationale.
9. Read key inputs completely. For the task's fact sheet, reference record and the submission's principal
   deliverables, follow next_char until the end before concluding that something is covered, missing or wrong.
10. Charge each defect once. Lower the dimension a defect primarily affects; lower another dimension only when the
   defect independently affects that dimension's anchor, and say why in that dimension's rationale.'''

VERSION = "native-judge-claude-v3.6"
_v35_common = nj.claude_common
if not getattr(_v35_common, "_v36", False):
    def claude_common():
        return _v35_common() + V36_RULES
    claude_common._v36 = True
    claude_common._v35 = True
    nj.claude_common = claude_common
    nj.CLAUDE_VERSION = VERSION
    judge_v35.VERSION = VERSION
