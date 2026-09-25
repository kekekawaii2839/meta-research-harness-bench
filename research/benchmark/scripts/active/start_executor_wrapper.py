"""Start the executor reverse proxy: claude-code-openai-wrapper in faithful mode (AGENTS §0.2.14–15).

Verifies before launch: the checkout is the pinned upstream commit, its working-tree diff
equals runtime/wrapper/faithful_mode.patch byte for byte, and the venv has the recorded
claude-agent-sdk version. Then starts uvicorn on 127.0.0.1 with the parent session's
CLAUDE*/ANTHROPIC* variables removed, WRAPPER_FAITHFUL_API=1 and a local API key.
Faithful mode skips the upstream paid startup check, so launching makes no model call.

Setup once (outside the repository):
  git clone https://github.com/RichardAtCT/claude-code-openai-wrapper D:/mrhbench-local-pilot/proxy/claude-code-openai-wrapper
  git -C ... checkout aaad0b96a4cd63833003ac340bbcc37f89418acc && git -C ... apply runtime/wrapper/faithful_mode.patch
  python -m venv D:/mrhbench-local-pilot/proxy/wrapper-venv && pip install -r runtime/wrapper/requirements.install.txt
"""
import argparse
import os
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "aaad0b96a4cd63833003ac340bbcc37f89418acc"
SDK = "claude-agent-sdk==0.2.159"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkout", type=Path, default=Path("D:/mrhbench-local-pilot/proxy/claude-code-openai-wrapper"))
    p.add_argument("--venv", type=Path, default=Path("D:/mrhbench-local-pilot/proxy/wrapper-venv"))
    p.add_argument("--key-file", type=Path, default=Path("D:/mrhbench-local-pilot/proxy/local_api_key.txt"))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--log", type=Path, default=Path("D:/mrhbench-local-pilot/proxy/wrapper-server.log"))
    a = p.parse_args()
    head = subprocess.run(["git", "-C", str(a.checkout), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != COMMIT:
        raise SystemExit("wrapper checkout is %s, expected %s" % (head, COMMIT))
    subprocess.run(["git", "-C", str(a.checkout), "add", "-N", "src/faithful_api.py"], check=True)
    diff = subprocess.run(["git", "-C", str(a.checkout), "diff", "--binary"], capture_output=True, check=True).stdout
    if diff != (ROOT / "runtime/wrapper/faithful_mode.patch").read_bytes():
        raise SystemExit("wrapper working tree differs from runtime/wrapper/faithful_mode.patch")
    python = a.venv / "Scripts" / "python.exe"
    freeze = subprocess.run([str(python), "-m", "pip", "freeze"], capture_output=True, text=True, check=True).stdout
    if SDK not in freeze.splitlines():
        raise SystemExit("wrapper venv lacks " + SDK)
    if not a.key_file.is_file():
        a.key_file.write_text("mrhb-local-" + secrets.token_hex(16), encoding="utf8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    env.update(WRAPPER_FAITHFUL_API="1", API_KEY=a.key_file.read_text(encoding="utf8").strip(), CLAUDE_AUTH_METHOD="cli", PYTHONUTF8="1")
    log = a.log.open("ab")
    proc = subprocess.Popen([str(python), "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(a.port)],
                            cwd=str(a.checkout), env=env, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % a.port, timeout=2) as r:
                if r.status == 200:
                    print("wrapper pid %d on http://127.0.0.1:%d (faithful mode, commit %s)" % (proc.pid, a.port, COMMIT[:12]))
                    return
        except OSError:
            time.sleep(1)
    proc.kill()
    raise SystemExit("wrapper did not become healthy; see " + str(a.log))


if __name__ == "__main__":
    main()
