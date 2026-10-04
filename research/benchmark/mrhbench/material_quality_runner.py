"""Opt-in quality-policy wrapper; does not change historical batch/runner code."""
from pathlib import Path
import jsonschema
from .io import ProtocolError, file_hash, read_json, write_json
from .material_batch import _input_snapshot, _check_inputs
from .material_public_surface import public_surface
from .material_quality_contract import (build_contract, publish_contract,
    bound_output_schema, validate_output, contract_prompt)


class QualityBoundRunner:
    """Same native role, plus immutable policy/coverage publication and local checks.

    No retry, output normalization, generated-code execution or scientific pass
    inference. The caller must bind this module/policy to its fresh run manifest.
    """
    def __init__(self, inner, *, policy_path, project_id, round_no):
        self.inner = inner
        self.policy_path = Path(policy_path)
        self.policy_hash = file_hash(self.policy_path)
        self.project_id = project_id
        self.round_no = round_no

    def run(self, *, workspace, prompt, role, **kwargs):
        ws = Path(workspace)
        if file_hash(self.policy_path) != self.policy_hash:
            raise ProtocolError("Shared quality policy changed before launch")
        if role not in {"constructor", "material_reviewer", "adjudicator"}:
            raise ProtocolError("Unsupported quality-bound material role")
        request = read_json(ws / "request.json")
        if request.get("paper_id") != self.project_id:
            raise ProtocolError("Quality runner identity differs from published request")
        if (ws / "policy.md").exists() and file_hash(ws / "policy.md") != self.policy_hash:
            raise ProtocolError("Conflicting role policy: use a fresh consistent template snapshot")
        protected = ["quality_policy.md"]
        if role == "constructor":
            with (ws / "quality_policy.md").open("xb") as f:
                f.write(self.policy_path.read_bytes())
            prompt += ("\nRead quality_policy.md IN FULL. It is the shared current material policy. "
                       "Apply its stage-specific public identity/scientific/IO requirements to "
                       "all output, including unchanged material. No sidecar is requested from "
                       "the constructor; independent reviewers must verify your output.\n")
            snapshot = _input_snapshot(ws, protected)
            result = self.inner.run(workspace=ws, prompt=prompt, role=role, **kwargs)
            _check_inputs(ws, protected, snapshot, role)
            return result
        surface = public_surface(ws / "output")
        contract = build_contract(self.policy_path, project_id=self.project_id,
            round_no=self.round_no, public_inventory=surface["inventory"],
            package_sha256=surface["package_sha256"], role=role)
        publish_contract(ws, contract, self.policy_path)
        write_json(ws / "quality_public_surface.json", surface, exclusive=True)
        if role == "adjudicator":
            schema = read_json(ws / "review_adjudication.schema.json")
            identity_field, output_name = "project_id", "review_adjudication.json"
        else:
            # Existing material review is file output, not a provider JSON channel.
            # Keep the normal role format and locally enforce its identity/decision.
            schema = {"type": "object", "required": ["schema_version", "paper_id", "decision"],
                "properties": {"schema_version": {"const": "material-review-1"},
                    "paper_id": {"type": "string"}, "decision": {"enum": [
                        "pass_with_pending_runtime", "revise", "reject"]}}}
            identity_field, output_name = "paper_id", "review.json"
        exact = bound_output_schema(schema, contract, identity_field=identity_field)
        write_json(ws / "quality_output.schema.json", exact, exclusive=True)
        protected += ["quality_contract.json", "quality_public_surface.json",
                      "quality_coverage.schema.json", "quality_output.schema.json", "output"]
        snapshot = _input_snapshot(ws, protected)
        prompt += ("\n" + contract_prompt() + "\nPublic-surface records are in "
            "quality_public_surface.json. Actual output bytes remain in output/. "
            "Read quality_coverage.schema.json and write quality_coverage.json. "
            "Your usual " + output_name + " must satisfy quality_output.schema.json. "
            "The exact identity field here is " + identity_field + "; preserve that name.\n")
        result = self.inner.run(workspace=ws, prompt=prompt, role=role, **kwargs)
        _check_inputs(ws, protected, snapshot, role)
        after = public_surface(ws / "output")
        out = read_json(ws / output_name)
        jsonschema.validate(out, exact)
        receipt = validate_output(out, schema, contract, ws / "quality_policy.md",
            coverage=read_json(ws / "quality_coverage.json"),
            public_inventory=after["inventory"], package_sha256=after["package_sha256"],
            identity_field=identity_field, action=out.get("decision"))
        write_json(ws / "quality_controller_validation.json", receipt, exclusive=True)
        return result
