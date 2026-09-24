"""Released stdlib harness bootstrap; contains no credentials or private inputs."""
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT = Path("/work/.broker")
ROOT.mkdir(exist_ok=True)
sequence = 0


class BrokerError(RuntimeError):
    """Typed broker failure (interface v4): .category is one of the public categories."""

    def __init__(self, message, category=None):
        super().__init__(message)
        self.category = category


def rpc(operation, arguments):
    global sequence
    sequence += 1
    request = {"sequence": sequence, "operation": operation, "arguments": arguments}
    temporary = ROOT / "request.tmp"
    temporary.write_text(json.dumps(request), encoding="utf8")
    os.replace(temporary, ROOT / f"request-{sequence}.json")
    result = ROOT / f"response-{sequence}.json"
    while not result.exists():
        time.sleep(.1)
    answer = json.loads(result.read_text(encoding="utf8"))
    if answer.get("sequence") != sequence or not answer.get("ok"):
        raise BrokerError(answer.get("message", "Invalid broker response"), answer.get("category"))
    return answer["value"]


class ModelClient:
    def complete(self, request, *, output_schema, image_ids=None):
        return rpc("complete", {"request": request, "output_schema": output_schema, "image_ids": image_ids or []})


class ToolClient:
    def call(self, name, arguments):
        return rpc("tool", {"name": name, "arguments": arguments})


class Budget:
    def remaining(self):
        return rpc("remaining", {})


if __name__ == "__main__":
    os.chdir("/work")
    try:
        spec = importlib.util.spec_from_file_location("research_harness", "/inputs/harness.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        view = json.loads(Path("/inputs/public/task.json").read_text(encoding="utf8"))
        result = module.run(view, ModelClient(), ToolClient(), Budget())
        (ROOT / "submission.tmp").write_text(json.dumps(result), encoding="utf8")
        os.replace(ROOT / "submission.tmp", ROOT / "submission.json")
    except BaseException as exc:
        (ROOT / "worker_failure.tmp").write_text(json.dumps({"type": type(exc).__name__, "message": str(exc)}), encoding="utf8")
        os.replace(ROOT / "worker_failure.tmp", ROOT / "worker_failure.json")
