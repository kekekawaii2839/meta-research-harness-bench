# research/benchmark/scripts

Entry-point scripts grouped by purpose. Run from anywhere, e.g.
`python research/benchmark/scripts/audits/audit_candidates.py --help`;
each script puts the benchmark root on sys.path itself.

- `active/` - entry points in current use (Claude-era runners, material factory, executor wrapper, cost report)
- `probes/` - bounded transport / runtime probes (real calls where stated in the docstring)
- `audits/` - one-off independent audits that produced files under `audit/` (mostly zero model calls)
- `prepare/` - fixture / material / task-variant preparation
- `legacy_codex/` - Codex-era runners and judges (historical configuration, AGENTS 0.2.1-0.2.12)

Shared stage-controller logic lives in `mrhbench/stage_controller.py`; `active/run_container_stage_development.py` is only its CLI.
Old->new paths: `_moves_step1.json`, `_moves_step23.json` (historical audit records keep citing old paths; they are not rewritten).
