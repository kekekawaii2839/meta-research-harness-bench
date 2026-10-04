"""Standard material factory: fixed-prompt model stages plus deterministic controller steps.

User decision 2026-09-24 (AGENTS §0.2.16): material construction runs through this
pipeline; root and the user only perform final quality acceptance. Model stages are
fresh native sessions (scout, source_auditor, adjudicator, constructor,
material_reviewer) with versioned prompts from prompts/factory/ and prompts/, each in
its own workspace, recorded in the shared call ledger. The controller only runs
deterministic steps: pool, selection, source fetch, background fetch, hashing, gates,
image build/smoke, compilation, dossier. Nothing here grants formal acceptance.

Stage order per paper (state.json keeps status per stage, never silently retried):
fetch -> source_audit -> adjudication -> background -> construct (constructor + gate +
reviewer) -> review_adjudication -> [repair -> repair_adjudication] -> runtime ->
compile -> pilot -> dossier.
"""
from __future__ import annotations

import hashlib
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema

from .io import ProtocolError, ProviderRateLimit, contained, digest, file_hash, read_json, utc_now, write_json
from .material_batch import MATERIAL_PROMPT_SUFFIX, _check_inputs, _input_snapshot, run_batch
from .source_evidence_index import build_evidence_index

TASK_TYPES = ("LIT", "IDEA", "EXP", "WRITE_CONTENT", "WRITE_EVIDENCE")
PAPER_STAGES = ("fetch", "source_audit", "adjudication", "background", "repo_files", "construct", "review_adjudication",
                "repair", "repair_adjudication", "runtime", "compile", "pilot", "dossier")
DONE = "completed"
# Terminal outcomes after which later stages must not run.
TERMINAL = {"dropped", "blocked_source", "failed_needs_attribution"}
# Provider 429: not terminal; rerun only with an explicit retry (failed attempt kept on disk).
RATE_LIMITED = "platform_rate_limited"
FETCH_FAILED = "platform_fetch_failed"  # transient network/HTTP failure while fetching sources; retryable like RATE_LIMITED
RETRYABLE = {RATE_LIMITED, FETCH_FAILED}
# arXiv statuses that are genuine findings about the paper (terminal blocked_source); anything else is transient.
ARXIV_FINAL = {"arxiv_not_found", "arxiv_ambiguous", "no_version_before_conference_end"}
STAGE_PATHS = {"fetch": ["sources"], "source_audit": ["source_audit"], "adjudication": ["adjudication"],
               "background": ["background", "background_decision.json"], "repo_files": ["repo_files"], "construct": ["construct", "job.json"],
               "review_adjudication": ["review_adjudication"], "repair": ["repair", "job_repair.json"],
               "repair_adjudication": ["repair_adjudication"], "runtime": ["runtime"], "compile": ["compiled"],
               "pilot": ["pilot"], "dossier": ["dossier"]}
STAGE_PATHS.update({"external_data": ["external_data"], "units": [], "repair2": ["repair2", "job_repair2.json"],
                    "repair2_adjudication": ["repair2_adjudication"]})
# Factory v4 (unit_split): shared paper stages, then one construction unit per requested task type.
PAPER_STAGES_V4 = ("fetch", "source_audit", "adjudication", "background", "repo_files", "external_data", "units")
UNIT_STAGES = ("construct", "review_adjudication", "repair", "repair_adjudication", "repair2", "repair2_adjudication",
               "runtime", "compile", "pilot", "dossier")
ALL_STAGES = tuple(dict.fromkeys(PAPER_STAGES + PAPER_STAGES_V4 + UNIT_STAGES))
IN_PROGRESS = "in_progress"  # units stage: some unit has not reached its last requested stage yet
UNIT_ORDER = ("EXP", "WRITE_EVIDENCE", "WRITE_CONTENT", "LIT", "IDEA")  # scarcest module first
# Source classes each unit receives (policy I1); readme/licence travel with the paper.
UNIT_SOURCES = {"LIT": {"paper", "background"}, "IDEA": {"paper", "background"}, "EXP": {"paper", "code", "data"},
                "WRITE_CONTENT": {"paper", "code"}, "WRITE_EVIDENCE": {"paper", "code", "data"}}
CONTINUATION_NOTE = ("CONTINUATION: the previous attempt was cut off by a provider session limit before it finished; "
                     "previous_candidate/ holds its partial output. Keep what is correct and faithful to the original sources, "
                     "complete what is missing and write a complete new output/. This is not a review repair.")


def source_class(role):
    if role == "background_paper":
        return "background"
    if role in ("code_file", "code_tree"):
        return "code"
    if role in ("repo_data_file", "external_data_file"):
        return "data"
    return "paper"


CPU_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0}
DEFAULT_CONFIG = {
    "schema_version": "factory-config-1", "seed": "mrh-factory-v1", "target_papers": 70, "fulltext_papers": 140,
    "triage_pool_size": 400, "triage_batch_size": 10, "conference_end": "2025-04-30",
    "quotas": {"LIT_or_IDEA": 0.4, "EXP": 0.4, "WRITE": 0.3}, "min_background_found": 5,
    "readme_chars": 12000, "license_chars": 3000,
    "final_review": {"first_n": 10, "sample_rate": 0.2},
}


def sha_key(seed, value):
    return hashlib.sha256((seed + "\x00" + value).encode("utf8")).hexdigest()


def slug(project_id):
    if not project_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in project_id):
        raise ProtocolError("Unsafe project id")
    return project_id


def docker_slug(project_id):
    """Lowercase, docker-safe and collision-free (OpenReview ids are case-sensitive)."""
    return slug(project_id).lower() + "-" + hashlib.sha256(project_id.encode("utf8")).hexdigest()[:6]


class CallBudget:
    """Per-invocation cap on model calls, on top of the ledger's global authorization."""

    def __init__(self, maximum):
        self.maximum, self.used, self._lock = maximum, 0, threading.Lock()

    def take(self, n=1):
        with self._lock:
            if self.used + n > self.maximum:
                raise ProtocolError("Factory call budget for this invocation exhausted")
            self.used += n


class Factory:
    def __init__(self, root: Path, *, templates: Path, runner_factory, sources=None, runtime=None, budget=None,
                 pilot=None):
        """runner_factory(role) -> object with .run(workspace=, prompt=, role=) (ClaudeNativeRunner in production)."""
        self.root = Path(root)
        self.templates = Path(templates)
        self._factory_prompts = None  # prompt subdirectory; from factory.json once initialised
        self.runner_factory = runner_factory
        self.sources, self.runtime, self.pilot = sources, runtime, pilot
        self.budget = budget or CallBudget(0)
        self._state_lock = threading.Lock()
        self.halted = None  # set on the first provider rate limit; later calls are refused before the ledger

    def runner(self, role):
        inner, factory = self.runner_factory(role), self

        class Guarded:
            def run(self, **kwargs):
                if factory.halted:
                    raise ProviderRateLimit("Factory halted after a provider rate limit: " + factory.halted)
                try:
                    return inner.run(**kwargs)
                except ProviderRateLimit as exc:
                    factory.halted = str(exc)
                    raise
        return Guarded()

    @staticmethod
    def set_aside(path: Path):
        """Keep a failed attempt: rename to <name>.failed-N (never delete evidence)."""
        if not path.exists():
            return None
        n = 1
        while path.with_name("%s.failed-%d" % (path.name, n)).exists():
            n += 1
        target = path.with_name("%s.failed-%d" % (path.name, n))
        path.rename(target)
        return target.name

    # ------------------------------------------------------------------ config
    @property
    def factory_templates(self):
        if self._factory_prompts is None:
            cfg_path = self.root / "factory.json"
            self._factory_prompts = read_json(cfg_path).get("factory_prompts", "factory") if cfg_path.exists() else "factory"
        return self.templates / self._factory_prompts

    def init(self, overrides=None):
        if (self.root / "factory.json").exists():
            raise ProtocolError("Factory already initialised")
        self._factory_prompts = (overrides or {}).get("factory_prompts", "factory")
        config = {**DEFAULT_CONFIG, **(overrides or {}), "created_at": utc_now(),
                  "policy_sha256": file_hash(self.factory_templates / "policy.md"),
                  "prompt_hashes": self.prompt_hashes()}
        write_json(self.root / "factory.json", config, exclusive=True)
        return config

    def config(self):
        return read_json(self.root / "factory.json")

    def prompt_hashes(self):
        names = [self.factory_templates.name + "/" + p.name for p in sorted(self.factory_templates.iterdir()) if p.is_file()]
        names += ["material_constructor.txt", "material_reviewer.txt", "material_package.schema.json"]
        return {n: file_hash(self.templates / n) for n in names}

    def check_prompts(self):
        # Prompts are frozen per factory run: a changed prompt needs a new factory root.
        if self.prompt_hashes() != self.config()["prompt_hashes"]:
            raise ProtocolError("Prompt/policy files changed since factory init; start a new factory version")

    # --------------------------------------------------------------- model call
    def agent_stage(self, workspace: Path, *, prompt_name, role, output_name, schema_name, inputs):
        """Run one fresh model session and return its validated JSON output."""
        self.check_prompts()
        self.budget.take()
        snapshot = _input_snapshot(workspace, inputs)
        prompt = (self.factory_templates / prompt_name).read_text(encoding="utf8")
        call = self.runner(role).run(workspace=workspace, prompt=prompt, role=role)
        _check_inputs(workspace, inputs, snapshot, role)
        out_path = workspace / output_name
        if not out_path.is_file():
            raise ProtocolError(role + " wrote no " + output_name)
        output = read_json(out_path)
        jsonschema.validate(output, read_json(self.factory_templates / schema_name))
        return output, {"call_id": call.get("call_id"), "status": call.get("status"),
                        "audit_directory": call.get("audit_directory"), "output_sha256": file_hash(out_path)}

    def publish_common(self, ws: Path, names):
        for name in names:
            shutil.copyfile(self.factory_templates / name, ws / name)

    # -------------------------------------------------------------- P1 triage
    def triage_pool(self):
        """Deterministic pre-filter + seeded topic-stratified sample for scout triage."""
        cfg = self.config()
        rows = [r for r in self._pool_rows() if r.get("repo") and (r.get("readme") or {}).get("status") == "found"
                and r.get("abstract")]
        groups = {}
        for r in sorted(rows, key=lambda r: sha_key(cfg["seed"], r["project_id"])):
            groups.setdefault(r.get("topic_group") or "Unknown", []).append(r)
        picked, order = [], sorted(groups)
        while len(picked) < cfg["triage_pool_size"] and any(groups.values()):
            for g in order:
                if groups[g] and len(picked) < cfg["triage_pool_size"]:
                    picked.append(groups[g].pop(0))
        return picked

    def _pool_rows(self):
        path = self.root / "pool" / "candidates.jsonl"
        import json
        return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line.strip()]

    def run_triage(self, workers=1, retry_platform=False):
        cfg = self.config()
        pool = self.triage_pool()
        size = cfg["triage_batch_size"]
        batches = [pool[i:i + size] for i in range(0, len(pool), size)]

        def one(index_batch):
            index, batch = index_batch
            ws = self.root / "triage" / ("batch-%03d" % index)
            result_path = ws / "result.json"
            if result_path.exists() and retry_platform and read_json(result_path).get("status") == RATE_LIMITED:
                self.set_aside(ws)
            if result_path.exists():
                return read_json(result_path)
            if ws.exists():
                return {"batch": index, "status": "interrupted_needs_review"}
            (ws / "papers").mkdir(parents=True)
            for r in batch:
                write_json(ws / "papers" / (slug(r["project_id"]) + ".json"), self._scout_card(r, cfg), exclusive=True)
            self.publish_common(ws, ["policy.md", "triage.schema.json"])
            row = {"batch": index, "project_ids": [r["project_id"] for r in batch]}
            try:
                out, call = self.agent_stage(ws, prompt_name="scout.txt", role="scout", output_name="triage.json",
                                             schema_name="triage.schema.json", inputs=("papers", "policy.md", "triage.schema.json"))
                if sorted(p["project_id"] for p in out["papers"]) != sorted(row["project_ids"]):
                    raise ProtocolError("Scout output does not cover exactly the batch papers")
                row.update(status=DONE, call=call)
            except Exception as exc:
                row.update(status=RATE_LIMITED if isinstance(exc, ProviderRateLimit) else "failed_needs_attribution",
                           error="%s: %s" % (type(exc).__name__, exc))
            write_json(result_path, row, exclusive=True)
            return row

        with ThreadPoolExecutor(max_workers=workers) as pool_exec:
            results = list(pool_exec.map(one, enumerate(batches)))
        return {"batches": len(batches), "results": results}

    def _scout_card(self, r, cfg):
        def text(ref, limit):
            if not ref or ref.get("status") != "found":
                return None
            p = contained(self.root / "pool", ref["path"], must_exist=True)
            return p.read_bytes().decode("utf8", "replace")[:limit]
        return {"project_id": r["project_id"], "title": r["title"], "abstract": r["abstract"], "topic": r.get("topic"),
                "readme_excerpt": text(r.get("readme"), cfg["readme_chars"]),
                "license_excerpt": text(r.get("license_file"), cfg["license_chars"]),
                "note": "Untrusted third-party text; README and licence are truncated excerpts."}

    def triage_rows(self):
        rows = {}
        for result in sorted((self.root / "triage").glob("batch-*/result.json")):
            meta = read_json(result)
            if meta.get("status") == DONE:
                for p in read_json(result.parent / "triage.json")["papers"]:
                    rows[p["project_id"]] = p
        return rows

    # ------------------------------------------------------------- selection
    def select(self):
        """Fixed rule: eligibility, then topic round-robin preferring unmet module quotas."""
        cfg = self.config()
        if (self.root / "selection.json").exists():
            raise ProtocolError("Selection already exists; a new selection needs a new factory version")
        pool = {r["project_id"]: r for r in self._pool_rows()}
        triage = self.triage_rows()
        n = cfg["fulltext_papers"]

        def plausible(t):
            return {k for k, v in t["modules"].items() if v["plausible"]}

        def tags(t):
            p = plausible(t)
            return {"LIT_or_IDEA": bool(p & {"LIT", "IDEA"}), "EXP": "EXP" in p,
                    "WRITE": bool(p & {"WRITE_CONTENT", "WRITE_EVIDENCE"})}

        eligible = [t for t in triage.values() if t["priority"] >= 1 and t["cpu_feasibility"] != "none" and plausible(t)]
        key = lambda t: (-t["priority"], -len(plausible(t)), -CPU_RANK[t["cpu_feasibility"]], sha_key(cfg["seed"], t["project_id"]))
        groups = {}
        for t in sorted(eligible, key=key):
            groups.setdefault(pool[t["project_id"]].get("topic_group") or "Unknown", []).append(t)
        need = {q: int(round(frac * n)) for q, frac in cfg["quotas"].items()}
        have = dict.fromkeys(need, 0)
        chosen = []
        while len(chosen) < n and any(groups.values()):
            for g in sorted(groups):
                if not groups[g] or len(chosen) >= n:
                    continue
                unmet = {q for q in need if have[q] < need[q]}
                pick = next((t for t in groups[g] if any(tags(t)[q] for q in unmet)), groups[g][0]) if unmet else groups[g][0]
                groups[g].remove(pick)
                chosen.append(pick)
                for q, flag in tags(pick).items():
                    have[q] += flag
        rows = [{"rank": i + 1, "project_id": t["project_id"], "title": pool[t["project_id"]]["title"],
                 "topic_group": pool[t["project_id"]].get("topic_group"), "priority": t["priority"],
                 "cpu_feasibility": t["cpu_feasibility"], "plausible_modules": sorted(plausible(t)),
                 "rights_flags": t["rights_flags"], "notes": t["notes"]} for i, t in enumerate(chosen)]
        selection = {"schema_version": "factory-selection-1", "created_at": utc_now(), "rule": "priority>=1, cpu!=none, "
                     "any plausible module; topic round-robin; within topic by priority, #plausible, cpu rank, seeded hash; "
                     "picks prefer unmet quotas", "quotas_target": need, "quotas_reached": have,
                     "triaged": len(triage), "eligible": len(eligible), "papers": rows}
        write_json(self.root / "selection.json", selection, exclusive=True)
        lines = ["# Factory selection (%d of %d eligible, %d triaged)" % (len(rows), len(eligible), len(triage)), "",
                 "Quotas target %s, reached %s" % (need, have), "",
                 "| # | project | title | topic | pri | cpu | modules | rights flags |", "|---|---|---|---|---|---|---|---|"]
        lines += ["| %d | %s | %s | %s | %d | %s | %s | %s |" % (r["rank"], r["project_id"], r["title"].replace("|", "/"),
                  r["topic_group"], r["priority"], r["cpu_feasibility"], ",".join(r["plausible_modules"]),
                  ",".join(r["rights_flags"])) for r in rows]
        (self.root / "selection.md").write_bytes(("\n".join(lines) + "\n").encode("utf8"))
        return selection

    def approve_selection(self, approver):
        sel = self.root / "selection.json"
        record = {"schema_version": "factory-selection-approval-1", "selection_sha256": file_hash(sel),
                  "approved_by": approver, "approved_at": utc_now()}
        write_json(self.root / "selection_approval.json", record, exclusive=True)
        return record

    def approved_papers(self):
        approval = self.root / "selection_approval.json"
        sel = self.root / "selection.json"
        if not approval.exists() or read_json(approval)["selection_sha256"] != file_hash(sel):
            raise ProtocolError("Selection is not approved by the user (or changed after approval)")
        return [r["project_id"] for r in read_json(sel)["papers"]]

    # ------------------------------------------------------------ paper state
    def paper_dir(self, project_id):
        return self.root / "papers" / slug(project_id)

    @property
    def unit_mode(self):
        return bool(self.config().get("unit_split"))

    def paper_stages(self):
        return PAPER_STAGES_V4 if self.unit_mode else PAPER_STAGES

    def wdir(self, state):
        """Working directory of a paper state or (v4) of one construction unit."""
        pdir = self.paper_dir(state["project_id"])
        return pdir / "units" / state["unit"] if state.get("unit") else pdir

    @staticmethod
    def job_id(state):
        return slug(state["project_id"]) + ("__" + state["unit"] if state.get("unit") else "")

    @staticmethod
    def package_slug(state):
        base = docker_slug(state["project_id"])
        return base + "-" + state["unit"].lower().replace("_", "-") if state.get("unit") else base

    def state(self, project_id):
        path = self.paper_dir(project_id) / "state.json"
        if path.exists():
            return read_json(path)
        title = next((r["title"] for r in self._pool_rows() if r["project_id"] == project_id), None)
        return {"schema_version": "factory-paper-state-1", "project_id": project_id, "title": title, "stages": {}, "flags": []}

    def unit_state(self, project_id, unit):
        if unit not in TASK_TYPES:
            raise ProtocolError("Unknown construction unit")
        path = self.paper_dir(project_id) / "units" / unit / "state.json"
        if path.exists():
            return read_json(path)
        return {"schema_version": "factory-paper-state-1", "project_id": project_id, "unit": unit,
                "title": self.state(project_id).get("title"), "stages": {}, "flags": []}

    def units(self, project_id):
        path = self.paper_dir(project_id) / "background_decision.json"
        if not self.unit_mode or not path.exists():
            return []
        requested = set(read_json(path)["requested_task_types"])
        return [t for t in UNIT_ORDER if t in requested]

    def _save(self, state):
        with self._state_lock:
            path = self.wdir(state) / "state.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, state)

    def _record(self, state, stage, status, artifacts=None, calls=(), notes=()):
        state["stages"][stage] = {"status": status, "artifacts": artifacts or {}, "calls": [c for c in calls if c is not None],
                                  "finished_at": utc_now(), "notes": list(notes)}
        self._save(state)

    def run_papers(self, project_ids, stages=ALL_STAGES, workers=1, retry_platform=False, units=None):
        approved = set(self.approved_papers())
        if set(project_ids) - approved:
            raise ProtocolError("Paper outside the approved selection")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda pid: self.advance(pid, stages, retry_platform, units), project_ids))

    def advance(self, project_id, stages=ALL_STAGES, retry_platform=False, units=None):
        """Run the requested stages in order; stops at the first failure or terminal outcome."""
        state = self.state(project_id)
        self.paper_dir(project_id).mkdir(parents=True, exist_ok=True)
        self._unit_filter = set(units) if units else None  # v4: run only these construction units (others stay pending)
        self._run_stages(state, self.paper_stages(), stages, retry_platform)
        result = {"project_id": project_id, "stages": {k: v["status"] for k, v in state["stages"].items()}}
        if self.unit_mode:
            result["units"] = {u: {k: v["status"] for k, v in self.unit_state(project_id, u)["stages"].items()}
                               for u in self.units(project_id)}
        return result

    def _run_stages(self, state, order, stages, retry_platform):
        wdir = self.wdir(state)
        wdir.mkdir(parents=True, exist_ok=True)
        for stage in order:
            done = state["stages"].get(stage, {}).get("status")
            if done == IN_PROGRESS:
                done = None  # units stage: re-enter, each unit resumes where it stopped
            if done in RETRYABLE and retry_platform:
                moved = [self.set_aside(wdir / p) for p in STAGE_PATHS[stage]]
                state.setdefault("history", []).append({"stage": stage, **state["stages"].pop(stage), "set_aside": moved})
                self._save(state)
                done = None
            if done in RETRYABLE:
                break
            if done in TERMINAL:
                break
            if done is not None:
                continue
            if stage not in stages and not (stage == "units" and set(stages) & set(UNIT_STAGES)):
                break
            try:
                if stage == "units":
                    self.stage_units(state, stages, retry_platform)
                else:
                    getattr(self, "stage_" + stage)(state)
            except Exception as exc:
                self._record(state, stage, RATE_LIMITED if isinstance(exc, ProviderRateLimit) else "failed_needs_attribution",
                             notes=["%s: %s" % (type(exc).__name__, exc)])
                break
            if state["stages"][stage]["status"] in TERMINAL | RETRYABLE | {IN_PROGRESS}:
                # A rate-limited or transient-fetch stage must stop the paper too, never let later stages run.
                break

    def stage_units(self, state, stages, retry_platform):
        """Factory v4: run each requested task type as an independent construction unit (policy I1)."""
        summary, rate_limited, finished = {}, False, True
        for unit in self.units(state["project_id"]):
            if getattr(self, "_unit_filter", None) is not None and unit not in self._unit_filter:
                finished = False  # not run in this invocation
                continue
            if self.halted:
                rate_limited = True
                break
            ustate = self.unit_state(state["project_id"], unit)
            self._run_stages(ustate, UNIT_STAGES, stages, retry_platform)
            statuses = {k: v["status"] for k, v in ustate["stages"].items()}
            summary[unit] = statuses
            if set(statuses.values()) & RETRYABLE:
                rate_limited = True
                break
            if not (set(statuses.values()) & TERMINAL) and set(statuses) != set(UNIT_STAGES):
                finished = False
        units = self.units(state["project_id"])
        if rate_limited:
            status = RATE_LIMITED
        elif not finished or len(summary) < len(units):
            status = IN_PROGRESS
        elif any(s.get("compile") == DONE for s in summary.values()):
            status = DONE
        elif all(set(s.values()) & TERMINAL <= {"dropped"} for s in summary.values()):
            status = "dropped"
        else:
            status = "failed_needs_attribution"
        self._record(state, "units", status, {u: "units/%s/state.json" % u for u in summary},
                     notes=["%s: %s" % (u, ",".join("%s=%s" % kv for kv in s.items())) for u, s in summary.items()])

    # --------------------------------------------------------------- stages
    def _candidate(self, project_id):
        return next(r for r in self._pool_rows() if r["project_id"] == project_id)

    def stage_fetch(self, state):
        pdir = self.paper_dir(state["project_id"])
        manifest = self.sources.fetch_paper_sources(self._candidate(state["project_id"]), pdir,
                                                    conference_end=self.config()["conference_end"])
        roles = {s["role"] for s in manifest["sources"]}
        arxiv_status = manifest["arxiv"]["status"]
        status = DONE if roles & {"paper_html", "paper_pdf"} else ("blocked_source" if arxiv_status in ARXIV_FINAL else FETCH_FAILED)
        self._record(state, "fetch", status, {"source_manifest": "sources/manifest.json"},
                     notes=[] if status == DONE else ["no paper full text fetched: arxiv status %s" % manifest["arxiv"]["status"]])

    def _source_workspace(self, state, ws: Path, extra_files=()):
        """Fresh workspace holding the original sources, navigation and manifest (paths rewritten)."""
        pdir = self.paper_dir(state["project_id"])
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh: " + str(ws))
        ws.mkdir(parents=True)
        manifest = read_json(pdir / "sources" / "manifest.json")
        published = []
        for row in manifest["sources"]:
            src = contained(pdir, row["local_path"], must_exist=True)
            if file_hash(src) != row["sha256"]:
                raise ProtocolError("Original source changed: " + row["source_id"])
            rel = "sources/" + row["local_path"].split("sources/files/", 1)[-1]
            target = contained(ws, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            published.append({**row, "local_path": rel})
            if row["role"] == "paper_html":
                write_json(ws / "source_navigation" / (row["source_id"] + ".json"),
                           build_evidence_index(target.read_text(encoding="utf8", errors="replace"), row["source_id"], row["sha256"]))
        write_json(ws / "source_manifest.json", {**manifest, "sources": published})
        write_json(ws / "candidate.json", {k: v for k, v in self._candidate(state["project_id"]).items()
                                           if k in ("project_id", "title", "abstract", "topic", "topic_group", "decision", "openreview_url")})
        for name, src in extra_files:
            shutil.copyfile(src, ws / name)
        return manifest

    SOURCE_INPUTS = ("sources", "source_navigation", "source_manifest.json", "candidate.json", "policy.md")

    def stage_source_audit(self, state):
        pdir = self.paper_dir(state["project_id"])
        ws = pdir / "source_audit"
        manifest = self._source_workspace(state, ws)
        self.publish_common(ws, ["policy.md", "source_audit.schema.json"])
        out, call = self.agent_stage(ws, prompt_name="source_auditor.txt", role="source_auditor", output_name="source_audit.json",
                                     schema_name="source_audit.schema.json", inputs=self.SOURCE_INPUTS + ("source_audit.schema.json",))
        self._check_ids(out, state["project_id"], manifest)
        blocking = [a["ambiguity_id"] for a in out["ambiguities"] if a["blocking"]]
        self._record(state, "source_audit", DONE, {"source_audit": "source_audit/source_audit.json"}, [call["call_id"]],
                     ["%d ambiguities (%d blocking)" % (len(out["ambiguities"]), len(blocking))])

    @staticmethod
    def _check_ids(out, project_id, manifest):
        if out["project_id"] != project_id:
            raise ProtocolError("Stage output names the wrong paper")
        known = {s["source_id"] for s in manifest["sources"]}

        def walk(node):
            if isinstance(node, dict):
                if "source_id" in node and "locator" in node and node["source_id"] not in known:
                    raise ProtocolError("Unknown source_id cited: %s" % node["source_id"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(out)

    def stage_adjudication(self, state):
        pdir = self.paper_dir(state["project_id"])
        ws = pdir / "adjudication"
        manifest = self._source_workspace(state, ws, [("source_audit.json", pdir / "source_audit" / "source_audit.json")])
        self.publish_common(ws, ["policy.md", "adjudication.schema.json"])
        out, call = self.agent_stage(ws, prompt_name="adjudicator_source.txt", role="adjudicator", output_name="adjudication.json",
                                     schema_name="adjudication.schema.json",
                                     inputs=self.SOURCE_INPUTS + ("source_audit.json", "adjudication.schema.json"))
        self._check_ids(out, state["project_id"], manifest)
        audit = read_json(pdir / "source_audit" / "source_audit.json")
        missing = {a["ambiguity_id"] for a in audit["ambiguities"]} - {d["ambiguity_id"] for d in out["ambiguity_decisions"]}
        if missing:
            raise ProtocolError("Adjudication leaves audited ambiguities undecided: %s" % sorted(missing))
        if out["decision"] == "construct" and (not out["requested_task_types"] or not out["scope_request"].strip()):
            raise ProtocolError("Construct decision needs task types and a scope request")
        unrequested = set(TASK_TYPES) - set(out["requested_task_types"])
        if unrequested - set(out["unrequested_reasons"]):
            raise ProtocolError("Every unrequested task type needs a reason")
        if self.unit_mode and out["decision"] == "construct" and set(out.get("task_scopes") or {}) != set(out["requested_task_types"]):
            raise ProtocolError("task_scopes must hold exactly one scope per requested task type")
        status = DONE if out["decision"] == "construct" else "dropped"
        self._record(state, "adjudication", status, {"adjudication": "adjudication/adjudication.json"}, [call["call_id"]],
                     [out["drop_reason"]] if status == "dropped" else ["requested " + ",".join(out["requested_task_types"])])

    def stage_background(self, state):
        """Controller fetch of pre-cutoff background works for LIT/IDEA; downgrades on shortage."""
        pdir = self.paper_dir(state["project_id"])
        adj = read_json(pdir / "adjudication" / "adjudication.json")
        requested = [t for t in adj["requested_task_types"]]
        notes, artifacts = [], {}
        if {"LIT", "IDEA"} & set(requested):
            cutoff = ((read_json(pdir / "sources" / "manifest.json")["arxiv"] or {}).get("earliest_known_public_version") or {}).get("date")
            if not cutoff or not adj["background_requests"]:
                found = 0
                notes.append("no cutoff date or no background requests")
            else:
                reqs = [{"request_id": "bg%03d" % i, "title": r["title"], "arxiv_id": r["arxiv_id"], "cutoff_date": cutoff[:10]}
                        for i, r in enumerate(adj["background_requests"])]
                manifest = self.sources.fetch_background(reqs, pdir / "background", base_dir=pdir)
                found = sum(1 for s in manifest["sources"] if s["role"] == "background_paper")
                artifacts["background_manifest"] = "background/manifest.json"
                notes.append("%d of %d background works fetched before %s" % (found, len(reqs), cutoff[:10]))
            if found < self.config()["min_background_found"]:
                requested = [t for t in requested if t not in ("LIT", "IDEA")]
                notes.append("controller rule: LIT/IDEA withdrawn, fewer than %d background works" % self.config()["min_background_found"])
                state["flags"].append("lit_idea_withdrawn_insufficient_background")
        effective = {"requested_task_types": requested}
        write_json(pdir / "background_decision.json", effective)
        artifacts["decision"] = "background_decision.json"
        self._record(state, "background", DONE if requested else "dropped", artifacts, notes=notes)

    def stage_repo_files(self, state):
        """Controller fetch of adjudicator-requested repository files at the pinned commit (factory v3)."""
        pdir = self.paper_dir(state["project_id"])
        reqs = read_json(pdir / "adjudication" / "adjudication.json").get("repo_file_requests") or []
        if not reqs:
            self._record(state, "repo_files", "skipped", notes=["no repository files requested"])
            return
        repo = read_json(pdir / "sources" / "manifest.json").get("repo") or {}
        if repo.get("status") != "fetched" or not repo.get("commit"):
            state["flags"].append("repo_files_requested_without_pinned_commit")
            self._record(state, "repo_files", DONE, notes=["requests not fetched: repository status %s" % repo.get("status")])
            return
        manifest = self.sources.fetch_repo_files(repo["url"], repo["commit"], reqs, pdir / "repo_files", base_dir=pdir)
        counts = {}
        for r in manifest["requests"]:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        if counts.get("fetched", 0) < len(reqs):
            state["flags"].append("repo_files_partially_fetched")
        self._record(state, "repo_files", DONE, {"repo_files_manifest": "repo_files/manifest.json"},
                     notes=["%s; %d bytes" % (counts, manifest["total_bytes"])])

    def stage_external_data(self, state):
        """Controller fetch of adjudicator-requested public datasets from allowlisted hosts (factory v4)."""
        pdir = self.paper_dir(state["project_id"])
        reqs = read_json(pdir / "adjudication" / "adjudication.json").get("external_data_requests") or []
        if not reqs:
            self._record(state, "external_data", "skipped", notes=["no external data requested"])
            return
        repo_manifest = pdir / "repo_files" / "manifest.json"
        used = read_json(repo_manifest)["total_bytes"] if repo_manifest.exists() else 0
        manifest = self.sources.fetch_external_data([{"url": r["url"], "why": r["why"]} for r in reqs], pdir / "external_data",
                                                    base_dir=pdir, already_used_bytes=used)
        counts = {}
        for r in manifest["requests"]:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        if counts.get("fetched", 0) < len(reqs):
            state["flags"].append("external_data_partially_fetched")
        self._record(state, "external_data", DONE, {"external_data_manifest": "external_data/manifest.json"},
                     notes=["%s; %d bytes" % (counts, manifest["total_bytes"])])

    def build_job(self, state):
        pdir = self.paper_dir(state["project_id"])
        unit = state.get("unit")
        allowed = UNIT_SOURCES[unit] if unit else {"paper", "code", "background", "data"}
        adj = read_json(pdir / "adjudication" / "adjudication.json")
        requested = [unit] if unit else read_json(pdir / "background_decision.json")["requested_task_types"]
        manifest = read_json(pdir / "sources" / "manifest.json")
        sources = [{k: s[k] for k in ("source_id", "url", "version", "sha256", "role", "local_path")} for s in manifest["sources"]
                   if source_class(s["role"]) in allowed]
        bg = pdir / "background" / "manifest.json"
        if bg.exists() and "background" in allowed:
            sources += [{k: s[k] for k in ("source_id", "url", "version", "sha256", "role", "local_path")}
                        for s in read_json(bg)["sources"]]
        decisions = "\n".join("- [%s] %s: %s" % (d["ambiguity_id"], d["decision"], d["statement"]) for d in adj["ambiguity_decisions"])
        scope = adj["scope_request"]
        if unit:
            scope += ("\n\nThis construction unit builds ONLY %s task(s). Unit scope (factory adjudication task_scopes):\n%s"
                      % (unit, adj["task_scopes"][unit]))
        scope += ("\n\nBinding ambiguity decisions (factory adjudication; maintainer choices must be "
                  "labelled as such in public specifications):\n" + (decisions or "- none") +
                  "\n\nWithhold from solver inputs: " + ("; ".join(adj["withheld_from_solver"]) or "nothing listed"))
        env = {**adj["environment_candidate"], "resource_status": "adjudicator_proposal_unmeasured_not_frozen", "runtime_verified": False}
        extra = {}
        repo_manifest = pdir / "repo_files" / "manifest.json"
        ext_manifest = pdir / "external_data" / "manifest.json"
        if "data" not in allowed:
            repo_manifest = ext_manifest = pdir / "_no_data_for_this_unit"
        if ext_manifest.exists():
            em = read_json(ext_manifest)
            archives = {r["sha256"] for r in em["requests"] if r["status"] == "fetched" and (r.get("extracted") or {}).get("status") == "extracted"}
            rows = [s for s in em["sources"] if not (s["sha256"] in archives and "-extracted/" not in s["local_path"])]
            extra["prepopulated_output_files"] = [
                {"from": s["local_path"], "to": "assets/external_data/" + s["local_path"].split("external_data/files/", 1)[1],
                 "sha256": s["sha256"], "provenance": {"url": s["url"], "version": s["version"]}} for s in rows]
            scope += ("\n\nController-fetched external data: every fetched file (archives already extracted) is present in "
                      "output/assets/external_data/. Use it where the construction order needs it (list used files in "
                      "package.json with sha256 CONTROLLER_FILL). Request statuses:\n%s"
                      % "\n".join("- %s: %s" % (r["url"], r["status"]) for r in em["requests"]))
        if repo_manifest.exists():
            rm = read_json(repo_manifest)
            fetched = [r for r in rm["requests"] if r["status"] == "fetched"]
            if fetched:
                by_sid = {s["source_id"]: s for s in rm["sources"]}
                extra.setdefault("prepopulated_output_files", []).extend([
                    {"from": by_sid[r["source_id"]]["local_path"], "to": "assets/repo_data/" + r["path"], "sha256": r["sha256"],
                     "provenance": {"url": by_sid[r["source_id"]]["url"], "version": by_sid[r["source_id"]]["version"]}}
                    for r in fetched])
            status_lines = "\n".join("- %s: %s" % (r["path"], r["status"]) for r in rm["requests"])
            scope += ("\n\nController-fetched repository files (pinned commit %s): every fetched file is already present in "
                      "output/assets/repo_data/<repository path>. Use them as task assets where the construction order needs "
                      "them (list them in package.json with sha256 CONTROLLER_FILL); unused ones may stay unlisted. Request "
                      "statuses:\n%s" % (rm["commit"], status_lines))
        if "data" in allowed:
            from .factory_data import apply_conversions
            populated, conversion_note = apply_conversions(pdir, extra.get("prepopulated_output_files", []))
            if populated:
                extra["prepopulated_output_files"] = populated
            scope += conversion_note
        arxiv = manifest.get("arxiv") or {}
        return {"schema_version": "material-job-1", "job_id": self.job_id(state), "paper_id": state["project_id"],
                "requested_task_types": requested, "scope_request": scope, "sources": sources,
                "first_disclosure": {"date": (arxiv.get("earliest_known_public_version") or {}).get("date"), "verified": False,
                                     "reason": "earliest known arXiv version from controller fetch; not proof of earliest disclosure"},
                "environment_candidate": env, "rights_review": adj["rights_review"], "selection_confirmed": True,
                "status": "approved_by_factory_adjudication", "formal_accepted": False,
                "constructor_model_decision": "User 2026-09-24: Claude native constructor/reviewer via the standard factory", **extra}

    def _batch(self, state, batch_root, repair_from=None, repair_notes=None, job_name="job.json"):
        pdir, wdir = self.paper_dir(state["project_id"]), self.wdir(state)
        job = self.build_job(state)
        write_json(wdir / job_name, job)
        self.check_prompts()
        resumed = self._resume_reviewer_only(job, batch_root)
        if resumed is not None:
            return job, resumed
        continuation = self._continuation_source(job, batch_root)
        if continuation is not None:
            # v4: a truncated constructor run continues from its own partial output (not a review repair round).
            notes = list((repair_notes or {}).get(job["job_id"], [])) + [CONTINUATION_NOTE]
            repair_from, repair_notes = continuation, {job["job_id"]: notes}
            state.setdefault("continuations", []).append({"batch": batch_root.name, "from": continuation.name, "at": utc_now()})
            self._save(state)
        self.budget.take(2)
        result = run_batch([job], workspace=pdir, batch_root=batch_root, templates=self.templates,
                           constructor=self.runner("constructor"), reviewer=self.runner("material_reviewer"),
                           max_workers=1, max_jobs=1, controller_hash_fill=True,
                           prompt_suffix=MATERIAL_PROMPT_SUFFIX + (self.factory_templates / "constructor_addendum.txt").read_text(encoding="utf8"),
                           repair_from=repair_from, repair_notes=repair_notes)
        return job, result["jobs"][0]

    def _continuation_source(self, job, batch_root):
        """Latest set-aside attempt whose constructor was cut off by a provider limit after writing output (factory v4).

        Returns the prior batch directory, or None. A prior that only holds controller-prepopulated files (the
        constructor never ran) is not a continuation; a completed constructor is handled by the reviewer-only resume.
        """
        if not self.config().get("continue_truncated") or batch_root.exists():
            return None
        priors = sorted(batch_root.parent.glob(batch_root.name + ".failed-*"), key=lambda p: int(p.name.rsplit("-", 1)[1]))
        if not priors:
            return None
        prior = priors[-1] / job["job_id"]
        receipt_path = prior / "receipt.json"
        if receipt_path.is_file():
            old = read_json(receipt_path)
            if (old.get("job_hash") != digest(job) or (old.get("constructor") or {}).get("status") == "completed"
                    or (old.get("error") or {}).get("type") != "ProviderRateLimit"):
                return None
        out = prior / "constructor" / "output"
        request_path = prior / "constructor" / "request.json"
        if not out.is_dir() or not request_path.is_file():
            return None
        prepopulated = {r.get("path") or r.get("to") for r in read_json(request_path).get("prepopulated_output_files") or []}
        written = [p for p in out.rglob("*") if p.is_file() and p.relative_to(out).as_posix() not in prepopulated]
        return priors[-1] if written else None

    def _resume_reviewer_only(self, job, batch_root):
        """After a provider rate limit hit only the reviewer, reuse the completed construction.

        The latest set-aside attempt (<batch>.failed-N) is reused when its receipt shows the same job,
        a completed constructor and a ProviderRateLimit error. The constructor tree is copied (the old
        attempt stays untouched), the deterministic gate is re-run and only a fresh reviewer is called.
        """
        from .material_pipeline import prepare_review, validate_package
        from .material_batch import fill_sentinel_hashes
        priors = sorted(batch_root.parent.glob(batch_root.name + ".failed-*"), key=lambda p: int(p.name.rsplit("-", 1)[1]))
        if not priors or batch_root.exists():
            return None
        prior = priors[-1] / job["job_id"]
        receipt_path = prior / "receipt.json"
        if not receipt_path.is_file():
            return None
        old = read_json(receipt_path)
        if (old.get("job_hash") != digest(job) or (old.get("constructor") or {}).get("status") != "completed"
                or (old.get("error") or {}).get("type") != "ProviderRateLimit"
                or not (prior / "constructor" / "output" / "package.json").is_file()):
            return None
        root = batch_root / job["job_id"]
        staged = root / "constructor"
        root.mkdir(parents=True)
        shutil.copytree(prior / "constructor", staged)
        row = {"job_id": job["job_id"], "job_hash": digest(job), "formal_accepted": False,
               "resumed_from": str(prior.resolve()), "constructor": old["constructor"],
               "constructor_reused": True, "repair_source": old.get("repair_source"),
               "repair_notes_hash": old.get("repair_notes_hash")}
        try:
            row["controller_hash_fill"] = fill_sentinel_hashes(staged / "output")
            request = read_json(staged / "request.json")
            row["structural_check"] = validate_package(read_json(staged / "output/package.json"), staged / "output", request["sources"])
            review_dir = root / "reviewer"
            prepare_review(staged, review_dir, self.templates)
            inputs = ("sources", "output", "source_navigation", "request.json", "material_reviewer.txt", "structural_check.json")
            snap = _input_snapshot(review_dir, inputs)
            self.budget.take(1)
            row["reviewer"] = self.runner("material_reviewer").run(
                workspace=review_dir, prompt=(self.templates / "material_reviewer.txt").read_text(encoding="utf8"), role="material_reviewer")
            _check_inputs(review_dir, inputs, snap, "Reviewer")
            review = read_json(review_dir / "review.json")
            if review.get("schema_version") != "material-review-1" or review.get("paper_id") != job["paper_id"]:
                raise ProtocolError("Invalid independent review identity")
            if review.get("decision") not in {"pass_with_pending_runtime", "revise", "reject"}:
                raise ProtocolError("Reviewer cannot grant formal acceptance")
            row["status"] = review["decision"]
        except Exception as exc:
            row["status"] = "failed_needs_attribution"
            row["error"] = {"type": type(exc).__name__, "message": str(exc)}
        write_json(root / "receipt.json", row, exclusive=True)
        return row

    @staticmethod
    def _batch_status(row):
        if row["status"] in {"pass_with_pending_runtime", "revise", "reject"}:
            return DONE
        return RATE_LIMITED if (row.get("error") or {}).get("type") == "ProviderRateLimit" else "failed_needs_attribution"

    def stage_construct(self, state):
        wdir = self.wdir(state)
        job, row = self._batch(state, wdir / "construct")
        calls = [(row.get(k) or {}).get("call_id") for k in ("constructor", "reviewer")]
        status = self._batch_status(row)
        error = row.get("error") or {}
        gate_failure = (status == "failed_needs_attribution" and self.config().get("structural_gate_to_repair")
                        and (row.get("constructor") or {}).get("status") == "completed" and "structural_check" not in row
                        and error.get("type") == "ProtocolError" and "altered" not in error.get("message", ""))
        if gate_failure:
            # Deterministic gate rejected a completed construction: the gate error becomes the single repair round's note.
            self._record(state, "construct", DONE, {"receipt": "construct/%s/receipt.json" % job["job_id"]}, calls,
                         ["structural gate failed, routed to repair: " + error.get("message", "")])
            note = ("The controller's deterministic structural gate rejected the previous package: " + error.get("message", "")
                    + ". Produce a complete package that satisfies material_package.schema.json and every deterministic check,"
                    " keeping the scientific content faithful to the original sources.")
            write_json(wdir / "review_adjudication" / "review_adjudication.json", {
                "schema_version": "factory-review-adjudication-1", "project_id": state["project_id"], "round": 1,
                "finding_decisions": [], "action": "repair", "repair_notes": [note], "drop_reason": None,
                "excluded_task_ids": [], "author": "controller_structural_gate"}, exclusive=True)
            self._record(state, "review_adjudication", DONE, {"review_adjudication": "review_adjudication/review_adjudication.json"},
                         notes=["controller: structural gate failure routed to the single repair round (no model call)"])
            return
        self._record(state, "construct", status, {"receipt": "construct/%s/receipt.json" % job["job_id"],
                     "review": "construct/%s/reviewer/review.json" % job["job_id"]}, calls,
                     ["reviewer decision " + row["status"]] + ([row["error"]["message"]] if row.get("error") else []))

    def max_repair_rounds(self, state):
        return 2 if state.get("unit") == "EXP" and self.config().get("exp_second_repair") else 1

    def _review_adjudication(self, state, stage, batch_dir, round_no):
        wdir = self.wdir(state)
        job_id = self.job_id(state)
        review_dir = wdir / batch_dir / job_id / "reviewer"
        ws = wdir / stage
        if ws.exists():
            raise ProtocolError("Stage workspace must be fresh")
        ws.mkdir(parents=True)
        for folder in ("sources", "output", "source_navigation"):
            for p in sorted((review_dir / folder).rglob("*")):
                if p.is_file():
                    rel = p.relative_to(review_dir).as_posix()
                    target = contained(ws, rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(contained(review_dir, rel, must_exist=True), target)
        for name in ("review.json", "structural_check.json", "request.json"):
            shutil.copyfile(review_dir / name, ws / name)
        allowed = ["pass", "repair", "drop"] if round_no <= self.max_repair_rounds(state) else ["pass", "drop"]
        schema_actions = set(read_json(self.factory_templates / "review_adjudication.schema.json")["properties"]["action"]["enum"])
        if "pass_partial" in schema_actions:  # factory prompts v2+
            allowed.insert(1, "pass_partial")
        write_json(ws / "round.json", {"round": round_no, "allowed_actions": allowed})
        self.publish_common(ws, ["policy.md", "review_adjudication.schema.json"])
        out, call = self.agent_stage(ws, prompt_name="adjudicator_review.txt", role="adjudicator", output_name="review_adjudication.json",
                                     schema_name="review_adjudication.schema.json",
                                     inputs=("sources", "output", "source_navigation", "review.json", "structural_check.json",
                                             "request.json", "round.json", "policy.md", "review_adjudication.schema.json"))
        if out["project_id"] != state["project_id"] or out["round"] != round_no or out["action"] not in allowed:
            raise ProtocolError("Review adjudication identity/round/action invalid")
        n = len(read_json(ws / "review.json").get("findings", []))
        indexed = [d["finding_index"] for d in out["finding_decisions"] if d["finding_index"] is not None]
        if sorted(indexed) != list(range(n)):
            raise ProtocolError("Every reviewer finding needs exactly one decision")
        if out["action"] == "repair" and not out["repair_notes"]:
            raise ProtocolError("Repair action needs repair notes")
        excluded = out.get("excluded_task_ids") or []
        if out["action"] == "pass_partial":
            task_ids = {t["task_id"] for t in read_json(ws / "output" / "package.json")["tasks"]}
            if not excluded or set(excluded) - task_ids or set(excluded) >= task_ids:
                raise ProtocolError("pass_partial must exclude a nonempty proper subset of the package's task ids")
        elif excluded:
            raise ProtocolError("excluded_task_ids only with pass_partial")
        status = {"pass": DONE, "pass_partial": DONE, "repair": DONE, "drop": "dropped"}[out["action"]]
        self._record(state, stage, status, {"review_adjudication": stage + "/review_adjudication.json"}, [call["call_id"]],
                     ["action " + out["action"]] + ([out["drop_reason"]] if out["drop_reason"] else []))
        return out

    def stage_review_adjudication(self, state):
        self._review_adjudication(state, "review_adjudication", "construct", 1)

    def _needs_repair(self, state, adjudication_stage="review_adjudication"):
        path = self.wdir(state) / adjudication_stage / "review_adjudication.json"
        return path.is_file() and read_json(path)["action"] == "repair"

    def _repair(self, state, stage, source_batch, adjudication_stage, job_name):
        wdir = self.wdir(state)
        notes = read_json(wdir / adjudication_stage / "review_adjudication.json")["repair_notes"]
        job, row = self._batch(state, wdir / stage, repair_from=wdir / source_batch,
                               repair_notes={self.job_id(state): notes}, job_name=job_name)
        calls = [(row.get(k) or {}).get("call_id") for k in ("constructor", "reviewer")]
        self._record(state, stage, self._batch_status(row), {"receipt": "%s/%s/receipt.json" % (stage, job["job_id"]),
                     "review": "%s/%s/reviewer/review.json" % (stage, job["job_id"])}, calls, ["reviewer decision " + row["status"]])

    def stage_repair(self, state):
        if not self._needs_repair(state):
            self._record(state, "repair", "skipped", notes=["round-1 action was pass"])
            return
        self._repair(state, "repair", "construct", "review_adjudication", "job_repair.json")

    def stage_repair_adjudication(self, state):
        if state["stages"]["repair"]["status"] == "skipped":
            self._record(state, "repair_adjudication", "skipped")
            return
        self._review_adjudication(state, "repair_adjudication", "repair", 2)

    def stage_repair2(self, state):
        """Factory v4 (policy H): EXP units may get one more targeted repair round."""
        if state["stages"].get("repair_adjudication", {}).get("status") != DONE or not self._needs_repair(state, "repair_adjudication"):
            self._record(state, "repair2", "skipped", notes=["no second repair requested"])
            return
        self._repair(state, "repair2", "repair", "repair_adjudication", "job_repair2.json")

    def stage_repair2_adjudication(self, state):
        if state["stages"]["repair2"]["status"] == "skipped":
            self._record(state, "repair2_adjudication", "skipped")
            return
        self._review_adjudication(state, "repair2_adjudication", "repair2", 3)

    def final_output(self, state):
        batch = next((b for b in ("repair2", "repair") if state["stages"].get(b, {}).get("status") == DONE), "construct")
        return self.wdir(state) / batch / self.job_id(state) / "constructor" / "output"

    def stage_runtime(self, state):
        out = self.final_output(state)
        record = self.runtime.verify_runtime(out, read_json(out / "package.json"), self.wdir(state) / "runtime",
                                             package_slug=self.package_slug(state))
        status = DONE if record["status"] == "passed" else "failed_needs_attribution"
        if status != DONE:
            state["flags"].append("runtime_failed")
        self._record(state, "runtime", status, {"runtime_record": "runtime/runtime_record.json"}, notes=record.get("reasons", []))

    def stage_compile(self, state):
        out = self.final_output(state)
        wdir = self.wdir(state)
        tasks = self.runtime.compile_tasks(out, read_json(out / "package.json"), read_json(wdir / "runtime" / "runtime_record.json"),
                                           wdir / "compiled", package_slug=self.package_slug(state),
                                           **({"per_task_resources": True} if self.config().get("per_task_resources") else {}))
        excluded = self.excluded_tasks(state)
        if excluded:
            (wdir / "compiled" / "_excluded").mkdir()
            for tid in excluded:
                if (wdir / "compiled" / tid).is_dir():
                    (wdir / "compiled" / tid).rename(wdir / "compiled" / "_excluded" / tid)
            tasks = [t for t in tasks if t.get("task_id") not in excluded]
        write_json(wdir / "compiled" / "compiled_tasks.json", tasks)
        self._record(state, "compile", DONE, {"compiled_tasks": "compiled/compiled_tasks.json"},
                     notes=["%d tasks" % len(tasks)] + (["excluded by adjudication: " + ", ".join(excluded)] if excluded else []))

    def excluded_tasks(self, state):
        """Task ids excluded by the latest effective pass_partial adjudication."""
        wdir = self.wdir(state)
        for stage in ("repair2_adjudication", "repair_adjudication", "review_adjudication"):
            if state["stages"].get(stage, {}).get("status") == DONE:
                out = read_json(wdir / stage / "review_adjudication.json")
                return out.get("excluded_task_ids") or [] if out["action"] == "pass_partial" else []
        return []

    def stage_pilot(self, state):
        if self.pilot is None:
            raise ProtocolError("Pilot runner not configured: needs executor/judge budget (official API pending)")
        wdir = self.wdir(state)
        record = self.pilot(state, wdir, self.budget)
        write_json(wdir / "pilot" / "pilot_record.json", record)
        if record.get("flags"):
            state["flags"].extend(record["flags"])
        self._record(state, "pilot", DONE, {"pilot_record": "pilot/pilot_record.json"}, record.get("calls", []))

    def stage_dossier(self, state):
        path = self.runtime.build_dossier(self.wdir(state))
        self._record(state, "dossier", DONE, {"dossier": Path(path).relative_to(self.wdir(state)).as_posix()})

    def _all_states(self):
        paths = sorted((self.root / "papers").glob("*/state.json")) + sorted((self.root / "papers").glob("*/units/*/state.json"))
        return [read_json(p) for p in paths]

    # ----------------------------------------------------------- final review
    def review_queue(self):
        cfg = self.config()["final_review"]
        dossiers = []
        for st in self._all_states():
            if st["stages"].get("dossier", {}).get("status") == DONE:
                dossiers.append({"project_id": st["project_id"] + ("/" + st["unit"] if st.get("unit") else ""),
                                 "flags": st["flags"], "finished_at": st["stages"]["dossier"]["finished_at"]})
        dossiers.sort(key=lambda d: d["finished_at"])
        return self.runtime.select_for_final_review(dossiers, seed=self.config()["seed"], first_n=cfg["first_n"],
                                                    sample_rate=cfg["sample_rate"])

    def status(self):
        rows = []
        for st in self._all_states():
            rows.append({"project_id": st["project_id"], **({"unit": st["unit"]} if st.get("unit") else {}), "flags": st["flags"],
                         "stages": {k: v["status"] for k, v in st["stages"].items()}})
        return rows
