"""Maintenance repair driven by the unified acceptance audit (standard unified-v1 U1-U6, 2026-10-10; user approved
standards S1-S5 and repairing fix_minor/fix_major units).

Same pipeline as maintenance_repair_v6 `rebuild` (constructor -> independent reviewer -> adjudicator pass/drop ->
runtime gate -> compile with current release notes and platform lint; 3 model calls per unit). The only difference:
the repair notes are exactly the audit findings in unified-audit-v1-repair-notes/<pid>__<UNIT>.txt (the unit's earlier,
already-resolved review findings are not re-sent), and the notes record goes to a separate directory so earlier
maintenance notes are never overwritten.
Usage: MRH_FACTORY_ROOT=<root> python audit_repair_v1.py <paper_id>:<UNIT> [...]
Stops at the first provider rate limit (no automatic retry).
"""
from pathlib import Path
import sys

DRIVER = Path(__file__).resolve().parent
sys.path.insert(0, str(DRIVER))
import maintenance_repair_v6 as m  # noqa: E402
from mrhbench.io import write_json, utc_now  # noqa: E402

NOTES_SRC = Path(r"D:/mrhbench-local-pilot/unified-audit-v1-repair-notes")
m.NOTES_DIR = DRIVER / ("maintenance_notes_audit_v1_" + m.ROOT.name)


def prepare(target):
    pid, unit = target.split(":")
    f = m.factory_v6.open_factory(m.ROOT)
    state = f.unit_state(pid, unit)
    batch, adj = m._last_batch(f, state, target)
    text = (NOTES_SRC / ("%s__%s.txt" % (pid, unit))).read_text(encoding="utf8")
    notes = [n.strip() for n in text.split("\n\n") if n.strip()]
    m.NOTES_DIR.mkdir(exist_ok=True)
    write_json(m.NOTES_DIR / ("%s__%s.json" % (pid, unit)), {
        "target": target, "source_batch": batch, "source_adjudication": adj, "accepted_review_findings": [],
        "controller_notes": notes, "created_at": utc_now(),
        "origin": "unified-audit-v1 (independent subagent audit, zero ledger calls): " + str(NOTES_SRC / ("%s__%s.txt" % (pid, unit)))},
        exclusive=True)


def resume(target):
    """The latest maintN batch hit a provider rate limit. Set the batch and its job file aside (kept, never deleted),
    then re-run the SAME batch from the same controller request (constructor + reviewer again: factory v5 deliberately
    disables reviewer-only reuse so the quality/identity wrappers are never bypassed; the rate-limited attempt is kept as
    <batch>.failed-N); then adjudication/runtime/compile."""
    from mrhbench.io import read_json
    pid, unit = target.split(":")
    f = m.factory_v6.open_factory(m.ROOT, max_calls=3)
    state = f.unit_state(pid, unit)
    wdir = f.wdir(state)
    n = max(int(k[5:]) for k in state["stages"] if k.startswith("maint") and k[5:].isdigit())
    batch, adj, req = "maint%d" % n, "maint%d_adjudication" % n, "maint%d_request" % n
    if state["stages"][batch]["status"] != "platform_rate_limited":
        raise m.ProtocolError("%s is not rate limited: %s" % (batch, state["stages"][batch]["status"]))
    moved = [f.set_aside(wdir / batch), f.set_aside(wdir / ("job_%s.json" % batch))]
    state.setdefault("history", []).append({"stage": batch, **state["stages"].pop(batch), "set_aside": moved, "at": utc_now()})
    f._save(state)
    m.factory_v5.ROUND_OF_BATCH[batch] = 3
    f._repair(state, batch, read_json(wdir / req / "review_adjudication.json")["source_batch"], req, "job_%s.json" % batch)
    st = state["stages"][batch]
    print("repair batch (resumed):", st["status"], st.get("notes"), flush=True)
    if st["status"] != "completed":
        return
    out = f._review_adjudication(state, adj, batch, 3)
    print("adjudication:", out["action"], (out.get("drop_reason") or "")[:300])
    if out["action"] not in ("pass", "pass_partial"):
        return
    final = wdir / batch / f.job_id(state) / "constructor" / "output"
    record = f.runtime.verify_runtime(final, read_json(final / "package.json"), wdir / ("runtime-" + batch), package_slug=f.package_slug(state))
    print("runtime:", record["status"], record.get("reasons"))
    if record["status"] != "passed":
        return
    m._compile(f, state, final, record, batch)


if __name__ == "__main__":
    args = sys.argv[1:]
    resume_first = None
    if args and args[0] == "--resume":
        resume_first, args = args[1], args[2:]
    for t in ([resume_first] if resume_first else []) + args:
        print("=== audit repair", t, "root", m.ROOT, flush=True)
        try:
            if t == resume_first:
                resume(t)
            else:
                prepare(t)
                m.cmd_run(t, rebuild=True)
            pid, unit = t.split(":")
            st = m.factory_v6.open_factory(m.ROOT).unit_state(pid, unit)["stages"]
            if any(v.get("status") == "platform_rate_limited" for v in st.values()):
                print("HALT: provider rate limit", flush=True)
                break
        except Exception as e:  # noqa: BLE001
            print("ERROR", t, type(e).__name__, str(e)[:500], flush=True)
            if "ProviderRateLimit" in type(e).__name__ or "429" in str(e):
                print("HALT: provider rate limit", flush=True)
                break
        print("=== done", t, flush=True)
