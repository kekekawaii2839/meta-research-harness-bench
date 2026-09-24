"""Fresh native Codex agent invocation with provenance, not a bare-model API.

Caller supplies a separately released workspace. Native tools are enabled. No
claim that an isolated cwd or Codex workspace permissions isolate all host reads.
"""
from __future__ import annotations
import os
import math
import re
import subprocess
import time
import uuid
import json
import copy
from pathlib import Path
from .io import ProtocolError, canonical, digest, file_hash, parse_json, read_json, write_json
from .providers import DISABLED_FEATURES
from .runtime_contracts import run_process_tree

NATIVE_FEATURES = {"shell_tool", "unified_exec", "code_mode", "code_mode_host", "view_image"}


def _toml_value(value):
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if type(value) in {int, float} and math.isfinite(value):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return "{" + ",".join(json.dumps(k) + "=" + _toml_value(v) for k,v in value.items()) + "}"
    raise ProtocolError("Unsupported controller MCP configuration")


def capture_session_rollout(events, *, audit_directory, codex_home, secret_values=()):
    """Read only the exact session returned by this invocation, never prior tasks.

    Fresh session persistence is for provenance, not cross-run resume. Missing
    rollout downgrades audit completeness, not a completed construction artifact.
    """
    ids = {e.get("thread_id") for e in events if e.get("type") == "thread.started"}
    if len(ids) != 1:
        return {"status": "unavailable", "reason": "missing_or_ambiguous_session_id", "complete_trajectory_verified": False}
    session_id = ids.pop()
    if not isinstance(session_id, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", session_id):
        return {"status": "unavailable", "reason": "invalid_session_id", "complete_trajectory_verified": False}
    # Filename-constrained discovery: no unrelated rollout is ever opened.
    matches = list((Path(codex_home)/"sessions").rglob(f"*{session_id}.jsonl"))
    if len(matches) != 1:
        return {"status": "unavailable", "reason": "exact_session_rollout_not_found_or_ambiguous", "session_id": session_id,
                "complete_trajectory_verified": False}
    source = matches[0]
    source_hash = file_hash(source)
    rows = [parse_json(line) for line in source.read_text(encoding="utf8").splitlines() if line.strip()]
    metas = [r.get("payload", {}) for r in rows if r.get("type") == "session_meta"]
    if len(metas) != 1 or metas[0].get("id") != session_id:
        return {"status": "unavailable", "reason": "rollout_identity_mismatch", "session_id": session_id,
                "complete_trajectory_verified": False}
    redactions = 0
    secrets = [v for v in secret_values if isinstance(v,str) and len(v) >= 8]
    def redact(value, key=""):
        nonlocal redactions
        if isinstance(value,dict):
            return {k:redact(v,k) for k,v in value.items()}
        if isinstance(value,list):
            return [redact(v) for v in value]
        if isinstance(value,str):
            if re.fullmatch(r"(?i)(?:access_token|refresh_token|id_token|api_key|authorization|password|client_secret)",key):
                redactions += 1; return "<REDACTED_SECRET>"
            for secret in secrets:
                if secret in value:
                    redactions += value.count(secret); value=value.replace(secret,"<REDACTED_SECRET>")
            value,n=re.subn(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]{16,}","Bearer <REDACTED_SECRET>",value); redactions+=n
            value,n=re.subn(r"\bsk-[A-Za-z0-9_-]{20,}","<REDACTED_SECRET>",value); redactions+=n
        return value
    sanitized = [redact(row) for row in rows]
    destination = Path(audit_directory)/"session_rollout.redacted.jsonl"
    with destination.open("xb") as f:
        for row in sanitized:
            f.write(canonical(row)+b"\n")
    tools = []
    for row in rows:
        payload = row.get("payload", {})
        if row.get("type") == "response_item" and payload.get("type") in {"function_call", "custom_tool_call"}:
            tools.append({"type":payload["type"],"name":payload.get("name"),"call_id":payload.get("call_id")})
    return {"status":"captured", "session_id":session_id,"source_sha256":source_hash,
            "path":str(destination),"sha256":file_hash(destination),"redactions_applied":redactions,
            "row_count":len(rows),"observed_tools":tools,"complete_trajectory_verified":False,
            "verification_note":"Captured exact rollout; actual tool/image delivery and evidence coverage require review."}


class NativeCodexRunner:
    def __init__(self, *, binary: Path, model: str, reasoning_effort: str, ledger,
                 audit_root: Path, permission_profile=":workspace", timeout_seconds=900,
                 tool_profile="native_development", mcp_servers=None, hook_guard=None, context_policy=None):
        if not binary.is_file() or not model or reasoning_effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ProtocolError("Invalid native Codex configuration")
        if permission_profile not in {":workspace", ":read-only", ":danger-full-access"} or isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ProtocolError("Invalid native permission/deadline configuration")
        self.binary, self.model, self.effort = binary.resolve(), model, reasoning_effort
        self.ledger, self.audit_root = ledger, audit_root.resolve()
        self.permission_profile, self.timeout = permission_profile, timeout_seconds
        self.context_policy=copy.deepcopy(context_policy)
        if self.context_policy is not None:
            from .context_policy import validate_policy
            validate_policy(self.context_policy,self.binary)
        if tool_profile not in {"native_development", "bounded_mcp"}:
            raise ProtocolError("Unknown native tool profile")
        if tool_profile == "bounded_mcp" and (permission_profile != ":read-only" or not mcp_servers):
            raise ProtocolError("Bounded MCP requires explicit read-only host profile and servers")
        if tool_profile != "bounded_mcp" and mcp_servers:
            raise ProtocolError("MCP servers require explicit bounded profile")
        self.tool_profile, self.mcp_servers = tool_profile, mcp_servers or {}
        _toml_value(self.mcp_servers)
        self.hook_guard, self.hook_guard_metadata, self.hook_guard_spec = None, None, None
        if hook_guard is not None:
            if tool_profile != "bounded_mcp" or set(hook_guard) != {"config_path", "python_binary"}:
                raise ProtocolError("Optional hook guard requires bounded MCP and explicit controller paths")
            from .native_tool_guard import hook_configuration
            self.hook_guard, self.hook_guard_metadata = hook_configuration(**hook_guard)
            self.hook_guard_spec = {
                'config_path': Path(self.hook_guard_metadata['config_path']),
                'python_binary': Path(self.hook_guard_metadata['python_binary'])}

    def command(self, workspace, output, schema=None, images=None):
        if self.hook_guard_metadata is not None:
            from .native_tool_guard import validate_guard_snapshot
            validate_guard_snapshot(self.hook_guard_metadata)
        args = [str(self.binary), "--no-daemon", "exec", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
                "-C", str(workspace), "-m", self.model, "--json", "-o", str(output)]
        # Explicit new permission profile, not legacy --sandbox alone. Clear the
        # inherited Desktop profile in environment as well. No hidden escalation.
        settings = [f'model_reasoning_effort="{self.effort}"', f'default_permissions="{self.permission_profile}"',
                    'approval_policy="never"', "project_doc_max_bytes=0", 'web_search="disabled"',
                    "features.skip_host_skill_discovery=true", "apps._default.enabled=false"]
        for setting in settings:
            args += ["-c", setting]
        if self.context_policy is not None:
            from .context_policy import config_setting
            args += ["-c",config_setting(self.context_policy,self.binary)]
        for feature in DISABLED_FEATURES:
            enabled = (self.tool_profile == "native_development" and feature in NATIVE_FEATURES) or (self.tool_profile == "bounded_mcp" and feature == "code_mode_host") or (feature == "hooks" and self.hook_guard is not None)
            args += ["--enable" if enabled else "--disable", feature]
        if self.mcp_servers:
            args += ["-c", "mcp_servers=" + _toml_value(self.mcp_servers)]
        if self.hook_guard is not None:
            # Only this explicit controller-vetted opt-in hook configuration.
            # This does NOT bypass tool permissions or change global hook trust.
            args += ["--dangerously-bypass-hook-trust", "-c", "hooks=" + _toml_value(self.hook_guard)]
        if schema:
            args += ["--output-schema", str(schema)]
        for path in images or []:
            args += ["--image", str(path)]
        return args + ["--", "-"]

    def run(self, *, workspace: Path, prompt: str, output_schema=None, role="judge", images=None, timeout_seconds=None):
        if role not in {"probe", "builder", "judge", "constructor", "material_reviewer"}:
            raise ProtocolError("Native agent runner cannot silently replace the harness-owned executor")
        workspace = workspace.resolve(strict=True)
        if not workspace.is_dir() or not isinstance(prompt, str) or not prompt.strip():
            raise ProtocolError("Native run needs fresh released workspace and prompt")
        timeout = self.timeout if timeout_seconds is None else min(self.timeout, timeout_seconds)
        if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ProtocolError("Native call deadline exhausted")
        image_rows = []
        for image in images or []:
            image = Path(image).resolve(strict=True)
            if not image.is_relative_to(workspace) or image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                raise ProtocolError("Native images must be explicit released workspace images")
            image_rows.append({"path": str(image), "sha256": file_hash(image)})
        run_dir = self.audit_root / ("native-" + uuid.uuid4().hex)
        run_dir.mkdir(parents=True)
        schema_path = run_dir / "schema.json" if output_schema is not None else None
        if schema_path:
            write_json(schema_path, output_schema)
        output = run_dir / "response.txt"
        command = self.command(workspace, output, schema_path, [r["path"] for r in image_rows])
        request = {"prompt": prompt, "workspace": str(workspace), "output_schema": output_schema, "images": image_rows}
        write_json(run_dir / "request.json", request)
        env = os.environ.copy()
        secret_values = [v for k,v in env.items() if re.search(r"(?i)(?:TOKEN|PASSWORD|API_KEY|SECRET)",k)]
        removed = []
        for key in list(env):
            if key in {"OPENAI_API_KEY", "CODEX_API_KEY"} or (key.startswith("CODEX_") and key != "CODEX_HOME"):
                removed.append(key); env.pop(key)
        env["NO_COLOR"] = "1"
        invocation = {"args": command, "binary_sha256": file_hash(self.binary), "config_hash": digest(command),
                      "environment_keys_removed": removed, "permission_profile_configured": self.permission_profile,
                      "native_tools": sorted(NATIVE_FEATURES) if self.tool_profile == "native_development" else ["code_mode_host"], "bare_model_equivalence": False,
                      "bounded_profile_caveat": "CLI still exposes apply_patch/collaboration schemas; explicit host read-only is not proven read isolation. Development only.",
                      "tool_profile": self.tool_profile, "mcp_servers_configured": list(self.mcp_servers),
                      "session_policy":"fresh_not_resumed_persisted_for_exact_rollout_audit",
                      "formal_isolation_verified": False, "workspace_is_security_boundary": False}
        if self.context_policy is not None:
            invocation["opt_in_context_policy"]={"policy":self.context_policy,"sha256":digest(self.context_policy)}
        if self.hook_guard_metadata is not None:
            invocation["optional_hook_guard"] = copy.deepcopy(self.hook_guard_metadata)
            invocation["optional_hook_guard"]["per_invocation_hook_trust_bypass"] = True
        write_json(run_dir / "invocation.json", invocation)
        call_id = self.ledger.reserve(role=role, model=self.model, effort=self.effort,
                    request_hash=digest(request), artifact_directory=str(run_dir))
        start, status, usage = time.monotonic(), "failed", None
        metadata = dict(invocation, transport="official_codex_native_agent", automatic_outer_retry=False)
        events = []
        capture = {"status":"pending", "complete_trajectory_verified":False}
        try:
            with (run_dir / "events.jsonl").open("wb") as out, (run_dir / "stderr.txt").open("wb") as err:
                try:
                    proc = run_process_tree(command, input=prompt.encode("utf8"), cwd=workspace, env=env,
                                            stdout=out, stderr=err, timeout=timeout)
                except subprocess.TimeoutExpired as exc:
                    status = "timeout"
                    raise ProtocolError("Native Codex timed out; process tree terminated, no automatic retry") from exc
            events = [parse_json(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]
            completed = [e for e in events if e.get("type") == "turn.completed"]
            usage = completed[-1].get("usage") if completed else None
            metadata.update(exit_code=proc.returncode, completed_turns=len(completed))
            if proc.returncode or len(completed) != 1 or any(e.get("type") in {"turn.failed", "error"} for e in events) or not output.is_file():
                raise ProtocolError("Native Codex did not finish auditable turn")
            response = read_json(output) if output_schema is not None else output.read_text(encoding="utf8")
            if output_schema is not None:
                write_json(run_dir / "response.json", response)
            status = "completed"
            return {"response": response, "call_id": call_id, "usage": usage, "status": status,
                    "audit_directory": str(run_dir), "formal_isolation_verified": False, "rollout_capture":capture}
        except Exception as exc:
            metadata["error_type"] = type(exc).__name__
            raise
        finally:
            try:
                if not events and (run_dir/"events.jsonl").is_file():
                    for line in (run_dir/"events.jsonl").read_text(encoding="utf8").splitlines():
                        try: events.append(parse_json(line))
                        except ValueError: pass
                capture.update(capture_session_rollout(events,audit_directory=run_dir,
                    codex_home=Path(os.environ.get("CODEX_HOME",str(Path.home()/".codex"))), secret_values=secret_values))
            except Exception as exc:
                capture.update(status="unavailable",reason="rollout_capture_failed",error_type=type(exc).__name__)
            metadata["rollout_capture"] = capture
            elapsed = time.monotonic() - start
            write_json(run_dir / "result.json", {"call_id": call_id, "status": status, "usage": usage, "wall_seconds": elapsed, **metadata})
            self.ledger.finish(call_id, status=status, wall_seconds=elapsed, usage=usage, metadata=metadata)
