"""Maintainer-only: load/export the package with the benchmark loaders and grep the
public export for private-reference phrases. Usage: python check_export.py <fresh_out_dir>
Run with the controller Python from any cwd."""
import hashlib, json, sys
from pathlib import Path
PKG = Path(__file__).resolve().parents[1]
BENCH = PKG.parents[3]
sys.path.insert(0, str(BENCH))
from mrhbench.materials import load_task, export_task, check_task
from mrhbench.providers import validate_application_schema
from mrhbench.artifact_policy import collection_policy
from mrhbench.sdk import Budget
from mrhbench.io import read_json

base = Path(sys.argv[1]); base.mkdir(parents=True, exist_ok=False)
out = {}
t = load_task(PKG / 'task.json'); out['load_task'] = 'ok'
out['pending_gates'] = check_task(t, PKG)
validate_application_schema(t['public']['output_contract']); out['output_contract_schema'] = 'valid'
out['collection_policy'] = collection_policy(t['public']['resources'])
try: load_task(PKG / 'task.json', formal=True); out['formal'] = 'ACCEPTED'
except Exception as e: out['formal_rejected'] = str(e)
dest = base / 'export-public'
out['export_result'] = export_task(t, PKG, dest, audience='development_executor')
try: export_task(t, PKG, base / 'export-hidden', audience='hidden_executor'); out['hidden'] = 'EXPORTED'
except Exception as e: out['hidden_audience_rejected'] = str(e)
view = read_json(dest / 'task.json')
b = Budget.from_task(view); out['budget_from_view'] = {'limits': b.limits, 'wall': b.wall_limit}
out['deadlines_consistent'] = view['resources']['execution_budget']['wall_seconds'] == view['resources']['container']['wall_seconds']
files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()); out['exported_files'] = files
out['exported_file_sha256'] = {f: hashlib.sha256((dest / f).read_bytes()).hexdigest() for f in files}
text = '\n'.join((dest / f).read_text(encoding='utf8') for f in files)
ref = read_json(PKG / 'private/reference.json')
phrases = ['Monte Carlo','l=5','linspace','NB_TRIALS','half the empirical','half-MSE','half MSE','Fig1b','Figure','rises as alpha','generalization error rises','data-structure strength','High data spread','align closely','label second moment','label variance','non-monotone','0.0036','0.189','Fashion','cGAN','maintainer_observations','judge_checks','private_facts','R_ALPHA_TREND','R_AGREEMENT','S_NOTEBOOK_DESIGN','U_EQ6','Eq6','reference.json','private-reference','source_cache','5m','conditional on fixed data','paper_id','iclr2025','tNn6Hskmti','KU-MLIP/2-Layer','Fig1b-alpha','ipynb','20 trials','invalidating','acceptable_outcomes','construction_audit']
out['phrases_checked'] = phrases
out['phrase_hits'] = {p: text.count(p) for p in phrases if p in text}
out['private_statement_prefix_hits'] = {
    'private_facts': [f['fact_id'] for f in ref['private_facts'] if f['statement'][:50] in text],
    'observations': [o[:50] for o in ref['maintainer_observations']['observations'] if o[:50] in text],
    'judge_checks': [c[:50] for v in ref['judge_checks'].values() for c in v if c[:50] in text]}
out['private_keys_in_view'] = [k for k in ('private', 'paper_id', 'assets', 'gates') if k in view]
(base / 'export_leak_check.json').write_text(json.dumps(out, indent=1), encoding='utf8')
print(json.dumps({k: out[k] for k in ('load_task','output_contract_schema','formal_rejected','hidden_audience_rejected','budget_from_view','deadlines_consistent','exported_files','phrase_hits','private_statement_prefix_hits','private_keys_in_view')}, indent=1))
