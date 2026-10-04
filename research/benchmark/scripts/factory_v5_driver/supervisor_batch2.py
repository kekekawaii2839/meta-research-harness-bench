"""Unattended supervisor for the batch-2 P11 pilots (no model calls of its own).

Loop until every (executor, task) has a terminal outcome:
  1. wait while any pilot_v5.py process is running;
  2. classify each task per executor from all p11-v5-batch2-<ex>-* run dirs:
       done          - a judge score exists, or execution failed for a non-rate-limit reason (e.g. deadline)
       judge_pending - execution completed but the judge did not score (e.g. 429)  -> judge-only
       pending       - never run, or cut by a provider 429                          -> rerun
  3. if the account is rate-limited, sleep until the five-hour reset (+3 min) read from the newest
     rate_limit_event in saved Claude CLI streams (fallback: 30 min);
  4. judge-only the judge_pending tasks, then run each executor's pending tasks as a new run dir
     (the two executors in parallel).
Every step is appended to supervisor_batch2.log as one JSON line. Stops after MAX_ROUNDS.
"""
from pathlib import Path
import datetime
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
PY = r"D:/mrhbench-local-pilot/controller-venv/Scripts/python.exe"
DRIVER = Path(__file__).resolve().parent
PILOT = Path("D:/mrhbench-local-pilot")
PAPERS = PILOT / "factory-v5/papers"
LEDGER = Path("C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/audit/development_call_ledger.json")
LOG = DRIVER / "supervisor_batch2.log"
HARNESS = ["--harness", str(PILOT / "h0-claude-frozen-v3/harness.py"),
           "--harness-sha256", "619dc7240d7d0437e6f449319adcf710e2c13ffa2220bb45e5f06e343309b181"]
EXECUTORS = {"opus": "C:/Users/li_ha/Documents/ChatGPT/meta-research-harness-bench/research/benchmark/config/role_transport_claude_v2.json",
             "haiku": str(DRIVER / "config/role_transport_haiku45_executor.json")}
TASKS = [(p, u) for p in ("iclr2025-qpXctF2aLZ", "iclr2025-SyVPiehSbg")
         for u in ("WRITE_EVIDENCE", "WRITE_CONTENT", "IDEA", "EXP", "LIT")]  # cheap types first
MAX_ROUNDS = 12


def log(**kw):
    kw["at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")
    print(json.dumps(kw, ensure_ascii=False), flush=True)


def rj(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf8"))
    except Exception:
        return default


def ledger():
    return rj(LEDGER) or {"attempts": []}


def rate_limited_in(task_dir, attempts):
    t = str(task_dir).replace("\\", "/").lower()
    return any(t in str(a.get("artifact_directory", "")).replace("\\", "/").lower()
               and ("provider_rate_limit" in json.dumps(a) or "HTTP 429" in json.dumps(a)) for a in attempts)


def classify(ex, attempts):
    out = {}
    for pid, unit in TASKS:
        state, where = "pending", None
        for rd in sorted(PILOT.glob("p11-v5-batch2-%s-*" % ex)):
            td = rd / ("%s__%s" % (pid, unit))
            if not td.is_dir():
                continue
            j = rj(td / "judge_run_result.json") or {}
            if j.get("quality") is not None:
                state, where = "done", td
                break
            limited = rate_limited_in(td, attempts)
            if (td / "execution" / "submission.json").is_file() and not limited_exec(td, attempts):
                judge_limited = rate_limited_in(td / "judge_calls", attempts)
                if (td / "judge_run_result.json").exists() and not judge_limited:
                    state, where = "done", td  # judge failed for a non-rate-limit reason: terminal, reported, not retried
                else:
                    state, where = "judge_pending", td
            elif (td / "execution" / "failure.json").is_file() and not limited:
                state, where = "done", td  # non-rate-limit execution failure is a terminal outcome (kept, not rerun)
        out[(pid, unit)] = (state, where)
    return out


def limited_exec(td, attempts):
    t = str(td / "executor_calls").replace("\\", "/").lower()
    return any(t in str(a.get("artifact_directory", "")).replace("\\", "/").lower()
               and ("provider_rate_limit" in json.dumps(a) or "HTTP 429" in json.dumps(a)) for a in attempts)


def pilots_running():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'pilot_v5.py' -and $_.CommandLine -notmatch 'supervisor' }).Count"],
                       capture_output=True, text=True)
    try:
        return int((r.stdout or "0").strip() or 0)
    except ValueError:
        return 0


def five_hour_reset():
    """Newest five-hour window reading across saved Claude CLI streams: (utilization, resetsAt, status)."""
    best = None
    files = sorted(glob.glob(str(PILOT / "**" / "events.jsonl"), recursive=True), key=os.path.getmtime)[-40:]
    for f in files:
        try:
            for line in open(f, encoding="utf8", errors="replace"):
                if '"rate_limit_event"' in line:
                    i = json.loads(line)["rate_limit_info"]
                    w = (i.get("unifiedWindows") or {}).get("five_hour") or {}
                    best = (w.get("utilization", i.get("utilization")), w.get("resetsAt", i.get("resetsAt")), i.get("status"), os.path.getmtime(f))
        except Exception:
            continue
    return best


def recently_limited(attempts):
    """True if the newest finished call was a provider 429."""
    fin = [a for a in attempts if a.get("status") != "reserved"]
    return bool(fin) and ("provider_rate_limit" in json.dumps(fin[-1]) or "HTTP 429" in json.dumps(fin[-1]))


def wait_for_reset():
    r = five_hour_reset()
    now = time.time()
    if r and r[1] and r[1] > now:
        secs = r[1] - now + 180
        log(event="sleep_until_reset", reset_at=datetime.datetime.fromtimestamp(r[1]).isoformat(timespec="minutes"),
            seconds=int(secs), last_reading=r[:3])
    else:
        secs = 1800
        log(event="sleep_fallback", seconds=secs, last_reading=r[:3] if r else None)
    time.sleep(secs)


def judge_only(pid, unit, td, ex):
    for name in ("judge_run_result.json", "output_checks.json"):
        p = td / name
        if p.exists():
            n = 1
            while (td / ("%s.failed-%d%s" % (p.stem, n, p.suffix))).exists():
                n += 1
            p.rename(td / ("%s.failed-%d%s" % (p.stem, n, p.suffix)))
    if (td / "judge").exists():
        n = 1
        while (td / ("judge.failed-%d" % n)).exists():
            n += 1
        (td / "judge").rename(td / ("judge.failed-%d" % n))
    code = ("import pilot_v5 as p,json;print(json.dumps(p.judge_only(r'%s',r'%s',r'%s','release-v3'),ensure_ascii=False))"
            % (PAPERS / pid / "units" / unit, td, EXECUTORS[ex]))
    r = subprocess.run([PY, "-X", "utf8", "-c", code], cwd=str(DRIVER), capture_output=True, text=True, encoding="utf8", errors="replace")
    log(event="judge_only", executor=ex, task="%s:%s" % (pid, unit), rc=r.returncode, out=(r.stdout or "")[-300:], err=(r.stderr or "")[-300:])


def ensure_wrapper():
    """The executor wrapper may have died with the Claude session that started it; restart it if needed."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as r:
            if r.status == 200:
                return True
    except Exception:
        pass
    r = subprocess.run([PY, "-X", "utf8", "start_executor_wrapper_v2.py", "--log", str(PILOT / "proxy/wrapper-server-sup.log")],
                       cwd=str(DRIVER), capture_output=True, text=True, timeout=300)
    log(event="wrapper_restart", rc=r.returncode, out=(r.stdout or "")[-200:], err=(r.stderr or "")[-300:])
    return r.returncode == 0


def run_pilot(ex, tasks, round_no):
    out = PILOT / ("p11-v5-batch2-%s-s%02d" % (ex, round_no))
    units = ",".join("%s@release-v3" % (PAPERS / p / "units" / u) for p, u in tasks)
    cmd = [PY, "-X", "utf8", "pilot_v5.py", "--paper-prefix", "--units", units] + HARNESS + ["--roles", EXECUTORS[ex], "--out", str(out)]
    logf = open(str(out) + ".log", "w", encoding="utf8")
    log(event="launch", executor=ex, out=str(out), tasks=["%s:%s" % t for t in tasks])
    return subprocess.Popen(cmd, cwd=str(DRIVER), stdout=logf, stderr=subprocess.STDOUT)


def write_report():
    """Deterministic morning report (no model calls): score pivot, failures, costs, supervisor log."""
    import html
    att = ledger()["attempts"]
    rows = []
    for jr in sorted(PILOT.glob("p11-v5-*/*/judge_run_result.json")) + sorted(PILOT.glob("p11-v5-*/*/execution/failure.json")):
        td = jr.parent if jr.name == "judge_run_result.json" else jr.parent.parent
        view = rj(td / "public/task.json") or {}
        role = rj(td / "role_configuration.json") or {}
        ex = ((role.get("executor") or {}).get("model") or "?").replace("claude-", "").split("-2025")[0]
        j = rj(td / "judge_run_result.json") or {}
        f = rj(td / "execution/failure.json") or {}
        name = td.name
        pid, unit = (name.split("__") + [None])[:2] if "__" in name else ("iclr2025-qgsXsqahMq", name)
        t = str(td).replace("\\", "/").lower()
        calls = [a for a in att if t in str(a.get("artifact_directory", "")).replace("\\", "/").lower()]
        tin = sum(sum(((a.get("usage") or {}).get(k) or 0) for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens")) for a in calls)
        rows.append({"paper": pid, "task": unit or view.get("task_type"), "executor": ex, "run": td.parent.name,
                     "quality": j.get("quality"), "dims": j.get("dimension_scores"), "judge": j.get("status"),
                     "failure": f.get("message"), "calls": len(calls), "failed_calls": sum(a.get("status") != "completed" for a in calls),
                     "in_M": round(tin / 1e6, 2), "limited": rate_limited_in(td, att), "budget": ((view.get("resources") or {}).get("execution_budget") or {}).get("model_calls")})
    seen = {}
    for r in rows:
        k = (r["paper"], r["task"], r["executor"])
        if r["quality"] is not None or k not in seen or seen[k]["quality"] is None:
            seen[k] = r
    exs = sorted({k[2] for k in seen})
    keys = sorted({(k[0], k[1]) for k in seen})
    esc = html.escape
    def cell(r):
        if not r:
            return "<td>—</td>"
        if r["quality"] is not None:
            tip = " · ".join("%s %s" % kv for kv in (r["dims"] or {}).items())
            return '<td title="%s"><b>%s</b> <small>(%s)</small></td>' % (esc(tip), r["quality"], r["budget"])
        why = "429" if r["limited"] else (r["failure"] or r["judge"] or "未评分")
        return '<td style="color:#c33">%s</td>' % esc(str(why)[:60])
    pivot = "".join("<tr><td>%s</td><td>%s</td>%s</tr>" % (esc(p[-10:]), esc(str(u)), "".join(cell(seen.get((p, u, e))) for e in exs)) for p, u in keys)
    detail = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        esc(r["run"]), esc(r["paper"][-10:]), esc(str(r["task"])), esc(r["executor"]), r["quality"], esc(str(r["failure"] or r["judge"] or "")[:80]),
        r["calls"], r["failed_calls"], r["in_M"]) for r in rows)
    logtail = esc("".join(open(LOG, encoding="utf8").readlines()[-60:])) if LOG.exists() else ""
    page = """<!doctype html><meta charset=utf-8><title>P11 batch2 report</title><style>body{font:14px system-ui,'Microsoft YaHei';max-width:1200px;margin:20px auto;padding:0 16px}
table{border-collapse:collapse;width:100%%;margin:10px 0}td,th{border-bottom:1px solid #ddd;padding:5px 8px;text-align:left;font-size:13px}pre{white-space:pre-wrap;font-size:11px;background:#f5f5f5;padding:8px}</style>
<h1>P11 试跑报告（batch2，监工自动生成）</h1><p>生成时间 %s。每格为该 executor 在该题最新一次的总分（悬停看各维度分，括号内为 executor 预算）；红字为未评分原因。judge 均为 opus-5-5。未做逐轨迹审阅。</p>
<h2>得分对照</h2><table><tr><th>论文</th><th>题型</th>%s</tr>%s</table>
<h2>每次运行明细</h2><table><tr><th>运行</th><th>论文</th><th>题型</th><th>executor</th><th>分数</th><th>失败/judge状态</th><th>调用</th><th>失败调用</th><th>输入(M)</th></tr>%s</table>
<h2>监工日志（最后60行）</h2><pre>%s</pre>""" % (datetime.datetime.now().isoformat(timespec="minutes"), "".join("<th>%s</th>" % esc(e) for e in exs), pivot, detail, logtail)
    out = PILOT / "p11-batch2-report.html"
    out.write_text(page, encoding="utf8")
    log(event="report_written", path=str(out))


def main():
    log(event="supervisor_start", tasks=len(TASKS), executors=list(EXECUTORS))
    for rnd in range(1, MAX_ROUNDS + 1):
        while pilots_running():
            time.sleep(120)
        att = ledger()["attempts"]
        status = {ex: classify(ex, att) for ex in EXECUTORS}
        summary = {ex: {s: sum(1 for v in st.values() if v[0] == s) for s in ("done", "judge_pending", "pending")} for ex, st in status.items()}
        log(event="round", round=rnd, summary=summary)
        if all(v[0] == "done" for st in status.values() for v in st.values()):
            log(event="all_done", summary=summary)
            write_report()
            return
        if recently_limited(att):
            if rnd == 1 and "--skip-wait" in sys.argv:
                log(event="skip_first_wait", reason="user switched to another account with a fresh five-hour window")
            else:
                wait_for_reset()
        for ex, st in status.items():
            for (pid, unit), (s, td) in st.items():
                if s == "judge_pending":
                    judge_only(pid, unit, td, ex)
        att = ledger()["attempts"]
        if recently_limited(att) and not (rnd == 1 and "--skip-wait" in sys.argv):
            continue  # judge-only hit the limit again; next round waits
        procs = []
        if not ensure_wrapper():
            log(event="wrapper_unavailable_retry_later")
            time.sleep(600)
            continue
        for ex in EXECUTORS:
            todo = [t for t, (s, _) in classify(ex, att).items() if s == "pending"]
            if todo:
                procs.append(run_pilot(ex, todo, rnd))
                time.sleep(20)
        for p in procs:
            p.wait()
    log(event="max_rounds_reached")
    write_report()


if __name__ == "__main__":
    main()
