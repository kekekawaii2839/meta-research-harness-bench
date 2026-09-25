"""Native builder on a fresh public ABI release; development, never isolation proof."""
from __future__ import annotations
import argparse
import shutil
import tempfile
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.costs import CallLedger
from mrhbench.cpu_runner import snapshot
from mrhbench.io import ProtocolError, read_json, write_json
from mrhbench.native_codex import NativeCodexRunner


def build(*, binary, output, permission_profile=":workspace", timeout_seconds=900):
    root=Path(__file__).resolve().parents[2]
    output=output.resolve()
    if output.exists():
        raise ProtocolError("New build requires fresh audit directory")
    output.mkdir(parents=True)
    config=read_json(root/"config/development.json")["builder"]
    clean=Path(tempfile.mkdtemp(prefix="mrhb-builder-public-"))
    for source,name in [(root/"prompts/builder_h0.txt","BUILDER_PROMPT.txt"),(root/"runtime/interface.json","interface.json")]:
        shutil.copyfile(source,clean/name)
    release=snapshot(clean)
    write_json(output/"release_manifest.json",{"files":release,"clean_workspace":str(clean),"formal_tasks_released":0,
        "allowed_context":"public construction prompt and ABI only","formal_isolation_verified":False})
    prompt=("Read BUILDER_PROMPT.txt and interface.json in this fresh workspace. Implement unified harness.py:run, "
        "build_manifest.json and interface unit tests. No README/AGENTS/memory/status documents. No real research "
        "tasks are supplied. Use only files in this workspace and Python standard library. No network/model calls, "
        "installs, GPU experiments, delegation, unrelated directories or credentials. Native coding tools and "
        "CPU unit tests are available. Test using scripted fake clients and abstract ABI fixtures, never invent "
        "scientific scores. Manifest must list tests actually run and limitations. Do not alter public input files. "
        "This is H0 construction, not search-set evolution. Final response states artifacts and actual tests.")
    runner=NativeCodexRunner(binary=binary,model=config["model"],reasoning_effort=config["reasoning_effort"],
        ledger=CallLedger(root/"audit/development_call_ledger.json"),audit_root=output/"calls",
        permission_profile=permission_profile,timeout_seconds=timeout_seconds)
    result=None
    try:
        result=runner.run(workspace=clean,prompt=prompt,role="builder")
    finally:
        shutil.copytree(clean,output/"workspace_snapshot")
        files=snapshot(output/"workspace_snapshot")
        original_intact=all((clean/row["path"]).is_file() and row in files for row in release)
        write_json(output/"result.json",{"invocation":result,"files":files,"released_inputs_unchanged":original_intact,
            "build_artifact_status":"present_unreviewed" if all((clean/name).is_file() for name in ("harness.py","build_manifest.json")) else "missing_required_artifacts",
            "build_accepted":False,"formal_isolation_verified":False,
            "acceptance":"Requires source, exact rollout, actual interface-test and input-integrity review."})
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--codex-binary",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--permission-profile",choices=[":workspace",":danger-full-access"],default=":workspace",
        help="Full access is explicit DEVELOPMENT host trust, never an OS isolation guarantee.")
    parser.add_argument("--timeout-seconds",type=float,default=900)
    args=parser.parse_args()
    print(build(binary=args.codex_binary,output=args.output,permission_profile=args.permission_profile,timeout_seconds=args.timeout_seconds))
