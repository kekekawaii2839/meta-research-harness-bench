"""Real CPU resource acceptance checks; no target-method or GPU experiment.

Run with a Python containing NumPy. Writes only observed checks, not a research
score or a fabricated solver trajectory. The test validates input infrastructure.
"""
from __future__ import annotations

import importlib.util
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mrhbench.io import file_hash, utc_now, write_json


def run():
    source = ROOT / "materials/iv_analysis/public/baseline.py"
    spec = importlib.util.spec_from_file_location("iv_starting_resources", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    started, start_time = time.perf_counter(), utc_now()
    checks = []

    def check(name, condition, **evidence):
        row = {"name": name, "passed": bool(condition), **evidence}
        checks.append(row)
        if not condition:
            raise AssertionError(name)

    a, b, c = module.generate(7), module.generate(7), module.generate(8)
    check("deterministic_same_seed", all(np.array_equal(a[k], b[k]) for k in a))
    check("different_seeds", not np.array_equal(a["X"], c["X"]))
    check("shapes", a["Z"].shape == (50, 10) and a["X"].shape == (50, 5) and a["Y"].shape == (50,))
    errors = []
    for seed in range(20):
        data = module.generate(seed, n=50, p=5, q=10)
        z, x, y = data["Z"], data["X"], data["Y"]
        fit = module.two_stage_least_squares(z, x, y)
        xhat = z @ fit["theta"]
        normal_residual = np.linalg.norm(xhat.T @ (xhat @ fit["beta"] - y))
        scale = max(1.0, np.linalg.norm(xhat.T @ y))
        errors.append(float(normal_residual / scale))
        direct_theta = np.linalg.solve(z.T @ z, z.T @ x)
        direct = np.linalg.solve(direct_theta.T @ z.T @ z @ direct_theta, direct_theta.T @ z.T @ y)
        check(f"2sls_equivalent_formula_seed_{seed}", np.allclose(fit["beta"], direct, rtol=1e-9, atol=1e-10))
    check("normal_equation_residual", max(errors) < 1e-10, maximum_relative_residual=max(errors))
    noiseless = a["X"] @ a["beta_true"]
    check("ols_noiseless_recovery", np.allclose(module.ordinary_least_squares(a["X"], noiseless), a["beta_true"]))
    try:
        module.two_stage_least_squares(np.zeros((50, 10)), a["X"], a["Y"])
    except ValueError:
        check("rank_failure_is_explicit", True)
    else:
        check("rank_failure_is_explicit", False)
    try:
        module.generate(0, n=5, p=5, q=10)
    except ValueError:
        check("invalid_dimensions_rejected", True)
    else:
        check("invalid_dimensions_rejected", False)
    output = {
        "purpose": "CPU_starting_resources_check_not_target_research_or_judge_acceptance",
        "source_sha256": file_hash(source), "started_at_utc": start_time,
        "finished_at_utc": utc_now(), "elapsed_seconds": time.perf_counter() - started,
        "python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
        "numpy": np.__version__, "gpu_used": False, "model_calls": 0,
        "checks": checks, "all_passed": all(c["passed"] for c in checks),
        "unverified": ["target_iteration_execution", "full_task_resource_budget", "judge_behavior", "OS_isolation"],
    }
    write_json(ROOT / "audit/iv_starting_resources.json", output)
    print(f"{len(checks)} CPU resource checks passed; not scientific task results.")


if __name__ == "__main__":
    run()
