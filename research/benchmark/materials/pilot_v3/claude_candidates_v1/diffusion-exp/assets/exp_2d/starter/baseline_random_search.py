"""Pure random search: a simple, validated reference baseline (maintainer-written).

Draws `budget` independent points from a proposal distribution, evaluates each
once, and returns the `n_keep` best evaluated points as its final population.
It is a floor/reference, not a competitive optimiser; stronger baselines are the
solver's design. budget, n_keep, k, bins and radius are required: there are no
defaults, because choosing them is part of the solver's experiment design.

Usage (ILLUSTRATIVE values only, unrelated to any recommended setting):
    python baseline_random_search.py --objective himmelblau --budget 3000 \
        --n-keep 100 --k 10 --bins 40 --radius 0.2 --seed 7 \
        --out results/random_search.jsonl
"""

from __future__ import annotations

import argparse
from typing import Any, Dict

import numpy as np

from metrics import CountingObjective, append_jsonl, summarise_population
from objectives import BOX_HIGH, BOX_LOW, Objective, get_objective


def random_search(objective: Objective, budget: int, n_keep: int,
                  rng: np.random.Generator, proposal: str = "uniform_box") -> Dict[str, Any]:
    if budget < 1 or n_keep < 1:
        raise ValueError("budget and n_keep must be positive")
    counter = CountingObjective(objective)
    if proposal == "uniform_box":
        X = rng.uniform(BOX_LOW, BOX_HIGH, size=(budget, 2))
    elif proposal == "standard_normal":
        X = rng.standard_normal(size=(budget, 2))
    else:
        raise ValueError(f"unknown proposal {proposal!r}")
    Q = counter.fitness(X)
    keep = np.argsort(-Q, kind="stable")[:min(n_keep, budget)]
    return {
        "method": "random_search",
        "proposal": proposal,
        "fitness_evaluations": counter.evaluations,
        "final_population": X[keep],
        "final_fitness": Q[keep],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--objective", required=True)
    ap.add_argument("--budget", type=int, required=True)
    ap.add_argument("--n-keep", type=int, required=True)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--bins", type=int, required=True)
    ap.add_argument("--radius", type=float, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--proposal", default="uniform_box",
                    choices=["uniform_box", "standard_normal"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    obj = get_objective(args.objective)
    rng = np.random.default_rng(args.seed)
    res = random_search(obj, args.budget, args.n_keep, rng, args.proposal)
    summary = summarise_population(obj, res["final_population"], k=args.k,
                                   bins=args.bins, radius=args.radius)
    record = {"seed": args.seed, "budget": args.budget, "n_keep": args.n_keep, **summary,
              "method": res["method"], "proposal": res["proposal"],
              "fitness_evaluations": res["fitness_evaluations"]}
    print(record)
    if args.out:
        append_jsonl(args.out, {**record, "final_population": res["final_population"]})


if __name__ == "__main__":
    main()
