"""Bounded, controller-owned CPU environment smoke, NOT a formal solver runner.

Only explicitly inspected pilot files are published. Docker daemon access stays
on the host. Every smoke uses a fresh read-only/non-root/network-none container.
No host-wide cleanup, image deletion, credential mounts, or source-cache writes.
"""
from __future__ import annotations
import math
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from .io import ProtocolError, file_hash, read_json, write_json, utc_now
from .runtime_contracts import run_process_tree
from .disk_audit import snapshot, file_storage


def resource_args(resources):
    for key in ("cpus", "memory_mb", "disk_mb", "pids_limit", "wall_seconds"):
        v = resources.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ProtocolError("Missing/invalid explicit package resource " + key)
        if key != "cpus" and int(v) != v:
            raise ProtocolError("Resource must be integral: " + key)
    disk = int(resources["disk_mb"]) * 1024 * 1024
    # Writable tmpfs budget is shared by work and temp, not granted twice.
    tmp = max(4096, disk // 5)
    if tmp >= disk:
        raise ProtocolError("Disk allowance too small")
    memory = str(int(resources["memory_mb"])) + "m"
    return ["--cpus", str(resources["cpus"]), "--memory", memory, "--memory-swap", memory,
            "--pids-limit", str(int(resources["pids_limit"])),
            "--tmpfs", f"/work:rw,nosuid,nodev,size={disk-tmp},uid=10001,gid=10001,mode=0700",
            "--tmpfs", f"/tmp:rw,nosuid,nodev,noexec,size={tmp},uid=10001,gid=10001,mode=0700"]


def create_args(image_id, release, resources, name):
    release = Path(release).resolve(strict=True)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ProtocolError("Runtime requires frozen local image ID")
    if not release.is_dir() or "," in str(release) or "\n" in str(release):
        raise ProtocolError("Invalid release directory")
    if not re.fullmatch(r"mrh-pilot-[a-f0-9]{32}", name):
        raise ProtocolError("Invalid owned container identity")
    limits = resource_args(resources)
    threads = str(max(1, math.floor(resources["cpus"])))
    return ["docker", "create", "--name", name, "--label", "mrhbench.purpose=local-environment-pilot",
            "--platform", "linux/amd64", "--pull", "never", "--network", "none", "--read-only",
            "--user", "10001:10001", "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true",
            "--ipc", "none", "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
            *limits, "--mount", f"type=bind,src={release},dst=/package,readonly",
            "--workdir", "/work", "--env", "HOME=/work", "--env", "MPLCONFIGDIR=/tmp/matplotlib",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "MPLBACKEND=Agg",
            "--env", f"OPENBLAS_NUM_THREADS={threads}", "--env", f"OMP_NUM_THREADS={threads}",
            "--entrypoint", "python", image_id, "-B", "/package/controller_smoke.py"]


SMOKE_WRAPPER = '''import json, os, pathlib, runpy, importlib.metadata, platform
root=pathlib.Path('/package')
assert os.getuid()==10001
assert not pathlib.Path('/var/run/docker.sock').exists()
assert sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir()) == ['lo']
for forbidden in ['/package/forbidden_write', '/etc/forbidden_write']:
    try: pathlib.Path(forbidden).write_text('unexpected write')
    except OSError: pass
    else: raise AssertionError('Read-only mount/root violation: '+forbidden)
marker=pathlib.Path('/work/state_marker')
assert not marker.exists(), 'Prior run state leaked'
marker.write_text('fresh state')
runpy.run_path(str(root/'environment/smoke.py'),run_name='__main__')
cg={name:(pathlib.Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','cpu.max','pids.max'] if (pathlib.Path('/sys/fs/cgroup')/name).is_file()}
status={line.split(':')[0]:line.split(':',1)[1].strip() for line in pathlib.Path('/proc/self/status').read_text().splitlines() if line.startswith(('CapEff:','NoNewPrivs:'))}
assert status.get('NoNewPrivs')=='1' and int(status.get('CapEff','1'),16)==0
print(json.dumps({'non_root':True,'network_interfaces':['lo'],'read_only_inputs':True,'fresh_state':True,'smoke_passed':True,'python':platform.python_version(),'machine':platform.machine(),'kernel_cgroup':cg,'process_security':status,'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}}))
'''


def invoke(args, audit, label, timeout=120):
    started = time.monotonic()
    try:
        p = run_process_tree(args, timeout=timeout, capture_output=True)
        result = dict(command=args, returncode=p.returncode,
                      stdout=p.stdout.decode("utf8", errors="replace"), stderr=p.stderr.decode("utf8", errors="replace"))
    except subprocess.TimeoutExpired as exc:
        result = dict(command=args, returncode=None, timed_out=True,
                      stdout=(exc.output or b"").decode("utf8", errors="replace"),
                      stderr=(exc.stderr or b"").decode("utf8", errors="replace"))
    result["wall_seconds"] = time.monotonic()-started
    write_json(audit/(label+".json"), result, exclusive=True)
    return result


def checked(args, audit, label, timeout=120):
    r = invoke(args, audit, label, timeout)
    if r.get("returncode") != 0:
        raise ProtocolError("Docker command failed; inspect " + str(audit/(label+".json")))
    return r["stdout"].strip()


def measure(workspace, destination, phase):
    s = snapshot(workspace, phase=phase, drives=["C:/", "D:/"])
    root=Path("D:/wsl/docker-desktop-data")
    s["docker_vhdx"] = [file_storage(p) for p in root.rglob("*.vhdx")] if root.is_dir() else []
    write_json(destination, s, exclusive=True)


def smoke(image_id, release, resources, audit):
    name = "mrh-pilot-" + uuid.uuid4().hex
    args = create_args(image_id, release, resources, name)
    cid = checked(args, audit, "create")
    if not re.fullmatch(r"[a-f0-9]{64}", cid):
        raise ProtocolError("Invalid container ID; no broad cleanup attempted")
    result = {"container_id": cid, "container_name": name, "formal_isolation_verified": False}
    try:
        start = invoke(["docker", "start", "-a", cid], audit, "start", resources["wall_seconds"])
        if start.get("timed_out"):
            invoke(["docker", "kill", cid], audit, "timeout_kill", 30)
        state = read_inspect(cid, audit)
        result.update(start=start, inspect=state, passed=start.get("returncode")==0 and state["State"]["ExitCode"]==0)
        if result["passed"]:
            import json
            result["observations"] = json.loads(start["stdout"].strip().splitlines()[-1])
    finally:
        result["cleanup"] = invoke(["docker", "rm", "-f", cid], audit, "remove_owned_container", 30)
        write_json(audit/"smoke_result.json", result, exclusive=True)
    return result


def read_inspect(cid, audit, label="inspect"):
    import json
    return json.loads(checked(["docker", "inspect", cid], audit, label))[0]


def build_package(*, workspace, candidate, destination, base_digest, slug, public_files):
    """Controller copy only; original model-generated candidates stay unchanged."""
    if not re.fullmatch(r"python@sha256:[0-9a-f]{64}", base_digest) or slug not in {"iv", "ssa"}:
        raise ProtocolError("Explicit frozen base and pilot slug required")
    destination.mkdir(parents=True, exist_ok=False)
    context=destination/"image"; context.mkdir()
    output=Path(candidate).resolve(strict=True)
    package=read_json(output/"package.json")
    env=package["environment"]
    resources=env["resources"]
    resource_args(resources)
    if env["gpu"] is not False or env["network"]!="none":
        raise ProtocolError("Not approved CPU offline pilot")
    original=output/env["dockerfile"]
    text=original.read_text(encoding="utf8")
    if not text.startswith("FROM python:3.12-slim\n"):
        raise ProtocolError("Unreviewed Dockerfile base/layout")
    (context/"Dockerfile").write_text(text.replace("FROM python:3.12-slim", "FROM "+base_digest, 1),encoding="utf8")
    shutil.copyfile(original.parent/"requirements.txt", context/"requirements.txt")
    (context/".dockerignore").write_text("*\n!Dockerfile\n!requirements.txt\n",encoding="utf8")
    release=destination/"release";release.mkdir()
    files={a["path"]:a for t in package["tasks"] for a in t["assets"] if a["visibility"]=="public"}
    inventory=[]
    for name in public_files + [env["smoke_test"]]:
        from .io import contained
        src=contained(output,name,must_exist=True)
        if name!=env["smoke_test"] and (name not in files or file_hash(src)!=files[name]["sha256"]):
            raise ProtocolError("File outside audited public whitelist or changed")
        target=contained(release,name);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,target);inventory.append({"path":name,"sha256":file_hash(src)})
    (release/"controller_smoke.py").write_text(SMOKE_WRAPPER,encoding="utf8")
    tag="mrhbench-pilot/"+slug+":"+uuid.uuid4().hex[:12]
    plan={"candidate":str(output),"package_hash":file_hash(output/"package.json"),"base":base_digest,
          "platform":"linux/amd64","tag":tag,"original_dockerfile_sha256":file_hash(original),
          "frozen_dockerfile_sha256":file_hash(context/"Dockerfile"),"resources":resources,"released_files":inventory,
          "phase":"controller_environment_smoke_only","formal_accepted":False}
    write_json(destination/"plan.json",plan,exclusive=True)
    measure(workspace,destination/"storage_before.json",slug+"_before_image")
    checked(["docker","build","--platform","linux/amd64","--label","mrhbench.purpose=local-environment-pilot",
             "--progress","plain","-t",tag,str(context)],destination,"build",1200)
    image=read_inspect(tag,destination,"image_inspect")
    plan["image_id"]=image["Id"]
    plan["image_inspect"]=image
    write_json(destination/"built_image.json",plan,exclusive=True)
    measure(workspace,destination/"storage_after_build.json",slug+"_after_image")
    run=destination/"smoke";run.mkdir()
    result=smoke(image["Id"],release,resources,run)
    measure(workspace,destination/"storage_after_smoke.json",slug+"_after_smoke")
    return {"slug":slug,"tag":tag,"image_id":image["Id"],"smoke_passed":result["passed"],"formal_accepted":False}
