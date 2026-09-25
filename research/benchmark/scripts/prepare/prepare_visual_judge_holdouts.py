"""Controller-authored synthetic visual calibration, rendered only in fresh CPU Docker.

Not research benchmark tasks, not actual solver traces, and no model calls here.
Freeze the generic judge prompt before building these paired numeric fixtures.
"""
import argparse,base64,hashlib,json,sys
from pathlib import Path
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))  # benchmark root (scripts/<group>/)
from mrhbench.container_runtime import ContainerSession
from mrhbench.judge_runner import evidence_record
from mrhbench.native_judge import make_prompt,VERSION
from mrhbench.judging import EvidenceSession
from mrhbench.io import write_json,file_hash

BASE=Path(__file__).resolve().parents[2]
CSV='batch_size,Reference,Optimized\n1,2.0,3.0\n8,6.0,5.0\n32,18.0,12.0\n'
CAPTION='Synthetic CPU inference latency summaries, not measurements of any real system. Batch latency in milliseconds, lower is better. Batch sizes 1, 8 and 32 are distinct conditions, not equal numeric intervals. Reference and Optimized are two implementation labels. Each point is a supplied aggregate; raw repeated runs and dispersion are not supplied, so no significance or uncertainty interval is inferred.'
INTERPRETATION='Reference has lower reported latency at batch size 1 (2.0 versus 3.0 ms). Optimized has lower reported latency at batch sizes 8 (5.0 versus 6.0 ms) and 32 (12.0 versus 18.0 ms). Neither implementation is uniformly faster across the three conditions. These descriptive comparisons do not establish significance or generalization beyond the synthetic table.'
TEMPLATE='''from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/inputs'); OUT=Path('/work'); rows=list(csv.DictReader((ROOT/'data.csv').open()))
fig,ax=plt.subplots(figsize=(8,5),dpi=150)
fig.subplots_adjust(left=0.13,right=0.96,bottom=BOTTOM,top=0.84)
for col,color,marker in [('Reference','#0072B2','o'),('Optimized','#D55E00','s')]:
 vals=[float(r[col]) for r in rows]
 ax.plot(range(3),vals,label=col,color=color,marker=marker,linewidth=2,markersize=7)
 for j,v in enumerate(vals): ax.annotate(f'{v:.1f}',(j,v),xytext=(-12 if col=='Reference' else 12,0),textcoords='offset points',ha='right' if col=='Reference' else 'left',va='center',fontsize=10,bbox={'facecolor':'white','edgecolor':'none','pad':1})
ax.set_xticks(range(3),[r['batch_size'] for r in rows]);ax.set_xlabel('Batch size (categorical conditions)',fontsize=11)
ax.set_ylabel('Batch latency (ms; lower is better)',fontsize=11);ax.set_ylim(0,21);ax.set_xlim(-0.2,2.2)
ax.set_title('Synthetic CPU inference latency',fontsize=15,pad=14)
ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
ax.legend(loc='upper center',bbox_to_anchor=(.5,LEGEND_Y),ncol=2,frameon=False)
fig.savefig(OUT/'figure.png',facecolor='white');plt.close(fig)
print(json.dumps({'rows':len(rows),'values':{k:[r[k] for r in rows] for k in rows[0]},'figure':'figure.png'}))
'''

def build(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 frozen=make_prompt('visual-policy-freeze','WRITE_EVIDENCE',EvidenceSession([]))
 write_json(output/'prompt_freeze.json',{'protocol':VERSION,'prompt_sha256':hashlib.sha256(frozen.encode()).hexdigest(),'native_judge_file_sha256':file_hash(BASE/'mrhbench/native_judge.py'),'frozen_before_fixture_rendering':True,'synthetic_not_benchmark':True})
 for name,bottom,legend_y,expect in [('visual_alpha',.25,-.25,'Readable labels and legend; do not invent a defect.'),('visual_beta',.015,-.35,'XAxis tick labels clipped at lower edge; legend below canvas and absent, preventing reliable standalone condition/series decoding.')]:
  folder=output/name;folder.mkdir();(folder/'data.csv').write_text(CSV,encoding='utf8')
  code=TEMPLATE.replace('BOTTOM',str(bottom)).replace('LEGEND_Y',str(legend_y));(folder/'render.py').write_text(code,encoding='utf8')
  resources={'cpus':1,'memory_mb':512,'disk_mb':32,'pids_limit':64,'wall_seconds':60}
  with ContainerSession(image_id='sha256:399341648ce68031cef84e225a8b4985fed3125fd020ec96a8d6c5d6563036d0',resources=resources,input_files={'data.csv':folder/'data.csv','render.py':folder/'render.py'},audit_dir=folder/'cpu_session') as c:
   result=c.exec(['python','/inputs/render.py'],timeout=25)
   if result['returncode']!=0:raise RuntimeError(result)
   bitmap=c.read('/work/figure.png',max_bytes=2000000);(folder/'figure.png').write_bytes(bitmap)
  task='Synthetic calibration only: present the supplied CPU inference latency table using a readable PNG, generation code that loads the CSV, exact numeric mapping, caption and short descriptive interpretation. Preserve all six values and both implementation identities and all batch conditions. Use labelled axes/legend, metric units and direction. No unprovided raw-run uncertainty or significance. The native PNG is intended as an 8 by 5 inch figure at 150dpi; no conference-column size is specified. All input observations are synthetic supplied aggregates; this is not a real study.'
  records=[evidence_record('task','task',task),evidence_record('submission','submission',json.dumps({'deliverables':['figure.png','render.py','caption','interpretation','numeric mapping'],'caption':CAPTION,'interpretation':INTERPRETATION,'numeric_mapping':json.loads(result['stdout'])['values']})),evidence_record('source','reference',CSV),evidence_record('generator','submission',code),evidence_record('image','rendered_artifact',base64.b64encode(bitmap).decode(),media_type='image/png'),evidence_record('platform','platform_trace',json.dumps({'provenance':'actual trusted controller-generated synthetic calibration; no research agent executed','resources':resources,'command':['python','/inputs/render.py'],'result':result,'image_sha256':hashlib.sha256(bitmap).hexdigest(),'image_bytes':len(bitmap)})),evidence_record('reference','reference','The six supplied numeric values and corresponding implementation/batch labels are the complete reference. Accept any scientifically readable faithful visualization; no expected visual style or target grade. Check the pixels. No repeated-run evidence exists.',visibility='private')]
  write_json(output/(name+'.fixture.json'),{'name':name,'task_type':'WRITE_EVIDENCE','synthetic_fixture':True,'fixture_split':'new_prompt_frozen_holdout_pair_not_population_validation','records':records,'review_expectations':{'behavior':expect,'forced_score':None},'actual_cpu_render':True,'image_sha256':hashlib.sha256(bitmap).hexdigest()})
 write_json(output/'construction.json',{'new_model_calls':0,'identical_data_and_narrative':True,'different_from_prior_scientific_context':'CPU latency versus batch conditions, not SSA research table','not_blind_to_fixture_author':True,'holdout_scope':'Fixture rendered after generic prompt freeze; no prompt change or expected-grade tuning using either image. Parent-authorized pair only.'})
 print(output)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);build(p.parse_args().output)
