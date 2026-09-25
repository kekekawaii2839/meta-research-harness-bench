# research/benchmark/scripts

Entry-point scripts grouped by purpose. Run from anywhere, e.g.
`python research/benchmark/scripts/audits/audit_candidates.py --help`;
each script puts the benchmark root on sys.path itself.

- `probes/` - bounded transport / runtime probes (real calls where stated in the docstring)
- `audits/` - one-off independent audits that produced files under `audit/` (mostly zero model calls)
- `prepare/` - fixture / material / task-variant preparation
- `legacy_codex/` - Codex-era runners and judges (historical configuration, AGENTS 0.2.1-0.2.12)

Scripts in current use still live at the benchmark top level until reorg step 3.
Old->new paths: `_moves_step1.json` (historical audit records keep citing old paths; they are not rewritten).
