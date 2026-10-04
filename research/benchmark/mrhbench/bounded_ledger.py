"""Fail-closed, serial experiment budgets without changing global authorization.

Constraints are checked under CallLedger's shared lock, immediately before the
attempt is written. They survive controller restarts through the existing ledger.
This limits users of this class, not unrelated controllers using the base ledger.
"""
from pathlib import Path

from .costs import CallLedger
from .io import ProtocolError


def _under(path, root):
    try:
        Path(path).resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


class BoundedCallLedger(CallLedger):
    def __init__(self, path, *, baseline, stop_at, experiment_root,
                 arm_root, arm_maximum=3):
        super().__init__(Path(path))
        if (type(baseline) is not int or type(stop_at) is not int
                or type(arm_maximum) is not int
                or not 0 <= baseline < stop_at or arm_maximum < 1):
            raise ProtocolError("Invalid experiment budget")
        self.baseline, self.stop_at = baseline, stop_at
        self.experiment_root = Path(experiment_root).resolve()
        self.arm_root = Path(arm_root).resolve()
        self.arm_maximum = arm_maximum
        if (self.arm_root == self.experiment_root
                or not _under(self.arm_root, self.experiment_root)):
            raise ProtocolError("Arm must be strictly inside experiment root")

    def _check_reservation(self, state, artifact_directory):
        if not self.baseline <= state["used_attempts"] < self.stop_at:
            raise ProtocolError("Experiment ledger boundary reached or baseline missing")
        if not _under(artifact_directory, self.arm_root):
            raise ProtocolError("Call audit directory outside frozen experiment arm")
        recent = state["attempts"][self.baseline:]
        # Be conservative even if another controller owns the uncertain attempt.
        if any(a["status"] == "reserved" for a in recent):
            raise ProtocolError("Uncertain or concurrent attempt: do not retry")
        if any(a.get("metadata", {}).get("failure_class") == "provider_rate_limit"
               for a in recent):
            raise ProtocolError("First provider rate limit stops experiment; no automatic retry")
        arm_calls = [a for a in recent
                     if _under(a.get("artifact_directory", ""), self.arm_root)]
        if len(arm_calls) >= self.arm_maximum:
            raise ProtocolError("Experiment arm call limit reached (failures count)")
