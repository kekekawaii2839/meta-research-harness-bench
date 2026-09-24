"""Opt-in synchronous Codex PreToolUse guardrail, NOT an OS security boundary.

The Codex hook engine can fail open and some tool paths are not covered. This
helper never upgrades a permission, reads tool-selected paths or executes input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid


def decide(payload, config):
    allowed = config.get('allowed_tools')
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) or not re.fullmatch(r'mcp__mrhbench__[A-Za-z0-9_]+', x) for x in allowed):
        raise ValueError('Exact mrhbench MCP allowlist required')
    name = payload.get('tool_name') if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get('hook_event_name') != 'PreToolUse':
        return 'deny', 'Malformed or unsupported hook event'
    if name in allowed:
        return 'allow', 'Exact controller-owned MCP allowlist match'
    return 'deny', 'Tool outside controller-owned MCP allowlist'


def response_for(decision, reason):
    # No allow output: retain ordinary permissions rather than overriding them.
    if decision == 'allow':
        return {}
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}


def hook_main(config_path):
    decision, reason, payload = 'deny', 'Guard failed; deny this tool', None
    try:
        raw = sys.stdin.buffer.read(2_000_001)
        if len(raw) > 2_000_000: raise ValueError('Hook input limit')
        payload = json.loads(raw)
        config = json.loads(Path(config_path).read_text(encoding='utf8'))
        decision, reason = decide(payload, config)
        logdir = Path(config['log_directory'])
        if not logdir.is_absolute() or not logdir.is_dir(): raise ValueError('Guard audit directory unavailable')
        row = {'at': time.time(), 'session_id': payload.get('session_id'),
               'tool_use_id': payload.get('tool_use_id'), 'tool_name': payload.get('tool_name'),
               'tool_input_sha256': hashlib.sha256(json.dumps(payload.get('tool_input'), sort_keys=True).encode()).hexdigest(),
               'decision': decision, 'reason': reason, 'config_sha256': hashlib.sha256(Path(config_path).read_bytes()).hexdigest()}
        with (logdir/(uuid.uuid4().hex+'.json')).open('x', encoding='utf8') as f:
            json.dump(row, f, ensure_ascii=False)
    except Exception as exc:
        decision, reason = 'deny', 'Guard error: '+type(exc).__name__
        # A valid deny response is emitted even when our own audit is unavailable.
        # Process launch/crash/engine timeout is outside this guarantee.
    print(json.dumps(response_for(decision, reason)))
    return 0


def hook_configuration(config_path, python_binary):
    path = Path(config_path).resolve(strict=True)
    python = Path(python_binary).resolve(strict=True)
    config = json.loads(path.read_text(encoding='utf8'))
    decide({'hook_event_name':'PreToolUse', 'tool_name':'test_validation'}, config)
    if not Path(config['log_directory']).is_absolute() or not Path(config['log_directory']).is_dir():
        raise ValueError('Existing absolute guard log directory required')
    script = Path(__file__).resolve()
    # The current Windows host has a no-space Python path; do not silently guess
    # shell quoting for an executable path requiring another launch wrapper.
    if any(c.isspace() for c in str(python)):
        raise ValueError('Guard Python executable must have a no-whitespace path')
    if any(c in str(p) for p in (path, python, script) for c in '\n\r"'):
        raise ValueError('Unsupported guard command path')
    command = python.as_posix()+' -I "'+script.as_posix()+'" --config "'+path.as_posix()+'"'
    hooks = {'PreToolUse': [{'matcher':'*','hooks':[{'type':'command','command':command,
                'commandWindows':command,'timeout':10,'async':False}]}]}
    metadata = {'opt_in': True, 'config_path': str(path), 'config_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'script_path': str(script), 'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
                'python_binary': str(python), 'python_binary_sha256': hashlib.sha256(python.read_bytes()).hexdigest(),
                'allowed_tools': config['allowed_tools'], 'log_directory': config['log_directory'],
                'coverage': 'Guardrail only; hook engine errors and uncovered tool paths may fail open.'}
    return hooks, metadata


def validate_guard_snapshot(metadata):
    """Preflight identity only; not a lock against mutation after process launch."""
    for path_key, hash_key in (('config_path', 'config_sha256'),
                               ('script_path', 'script_sha256'),
                               ('python_binary', 'python_binary_sha256')):
        if hashlib.sha256(Path(metadata[path_key]).read_bytes()).hexdigest() != metadata[hash_key]:
            raise ValueError('Frozen guard dependency changed: '+path_key)
    if not Path(metadata['log_directory']).is_dir():
        raise ValueError('Guard audit directory unavailable')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);args=p.parse_args()
    raise SystemExit(hook_main(args.config))
