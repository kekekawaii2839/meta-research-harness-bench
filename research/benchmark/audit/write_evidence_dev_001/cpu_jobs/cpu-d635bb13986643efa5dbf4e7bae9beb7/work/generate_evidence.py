import json, csv, math, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path('.')
NUMERIC = Path('inputs/numeric_evidence.json')
FACTS = Path('inputs/research_facts.json')

def font(size, bold=False):
    candidates = ([
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf'
    ] if bold else [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/arial.ttf'
    ])
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()

def mix(a, b, t):
    t=max(0.0,min(1.0,t)); return tuple(round(a[i]*(1-t)+b[i]*t) for i in range(3))

def score_color(x):
    # Fixed, explicit scale. Negative values are red; nonnegative values progress white-to-blue.
    if x < 0:
        return mix((247,247,247),(178,24,43),min(1.0,-x/4.0))
    return mix((247,247,247),(33,102,172),min(1.0,x/1.0))

def text_color(rgb):
    lum=0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]
    return (255,255,255) if lum < 132 else (25,25,25)

def esc_svg(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\"','&quot;')

with NUMERIC.open('r', encoding='utf-8') as f:
    data=json.load(f)
with FACTS.open('r', encoding='utf-8') as f:
    facts=json.load(f)
rows=data['rows']
methods=[]; conditions=[]
for r in rows:
    if r['method'] not in methods: methods.append(r['method'])
    if r['condition'] not in conditions: conditions.append(r['condition'])
lookup={(r['method'],r['condition']):r for r in rows}
assert len(rows)==len(methods)*len(conditions)==98
assert methods==['Source','TTT','BN-Adapt','FR','RSD','SSA (ours)','Oracle']
assert conditions[-1]=='Mean' and len(conditions)==14
for r in rows:
    assert r['reported_decimal']==f"{r['r2']:.3f}"

# Cell-linked ledger: numeric table values, exactly one entry per supplied cell.
ledger=[{'cell_id':r['cell_id'],'value':r['r2']} for r in rows]
Path('displayed_values.json').write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf-8')

# Machine-editable table.
with Path('table.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['Method']+conditions)
    for m in methods:
        w.writerow([m]+[lookup[(m,c)]['reported_decimal'] for c in conditions])

# Paper-oriented Markdown table; three decimals retained verbatim.
short={'Defocus blur':'Defocus','Motion blur':'Motion','Zoom blur':'Zoom','Elastic transform':'Elastic','Jpeg comp.':'JPEG','Gaussian noise':'Gaussian','Impulse noise':'Impulse','Shot noise':'Shot','Brightness':'Bright','Pixelate':'Pixelate','Contrast':'Contrast','Fog':'Fog','Snow':'Snow','Mean':'Mean'}
md=[]
md.append('# Corrupted UTKFace age prediction ($R^2$)')
md.append('')
md.append('Higher is better; negative values are valid. Values are author-reported aggregates at severity 5. **Oracle†** uses target labels and is not a same-information competitor.')
md.append('')
headers=['Method']+[short[c] for c in conditions]
md.append('| '+' | '.join(headers)+' |')
md.append('| '+' | '.join(['---']+['---:']*len(conditions))+' |')
for m in methods:
    label=('**'+m+'**') if m=='SSA (ours)' else ('Oracle†' if m=='Oracle' else m)
    md.append('| '+label+' | '+' | '.join(lookup[(m,c)]['reported_decimal'] for c in conditions)+' |')
md.extend(['','Notes: Source is unadapted. SSA adapts only normalization affine scale/shift parameters while keeping the regression head and all other parameters fixed. No target labels or source examples are used during adaptation; precomputed source statistics are used. No uncertainty is shown because per-run observations and sampling uncertainty were not supplied. Source: arXiv:2410.03263v1, Table S4.T4.'])
Path('table.md').write_text('\n'.join(md)+'\n',encoding='utf-8')

# LaTeX source for editing/typesetting.
latex=[]
latex.append('\\begin{table*}[t]')
latex.append('\\centering\\scriptsize')
latex.append('\\caption{Corrupted UTKFace age prediction at severity 5. $R^2$ is higher-better and may be negative. Values are author-reported aggregates; no uncertainty is available. Oracle uses target labels and is not a same-information competitor.}')
latex.append('\\label{tab:utkface-corruptions}')
latex.append('\\resizebox{\\textwidth}{!}{%')
latex.append('\\begin{tabular}{l'+'r'*len(conditions)+'}')
latex.append('\\toprule')
latex.append('Method & '+' & '.join(short[c] for c in conditions)+' \\\\')
latex.append('\\midrule')
for m in methods:
    name={'SSA (ours)':'\\textbf{SSA (ours)}','Oracle':'Oracle$^{\\dagger}$'}.get(m,m)
    vals=[]
    for c in conditions:
        v=lookup[(m,c)]['reported_decimal']
        vals.append('\\textbf{'+v+'}' if m=='SSA (ours)' else v)
    latex.append(name+' & '+' & '.join(vals)+' \\\\')
latex.append('\\bottomrule')
latex.append('\\end{tabular}}')
latex.append('\\vspace{2pt}\\parbox{\\textwidth}{\\footnotesize $^{\\dagger}$Target-label access. Source is unadapted. No target labels or source examples are used by SSA during adaptation. Source: arXiv:2410.03263v1, Table S4.T4.}')
latex.append('\\end{table*}')
Path('table.tex').write_text('\n'.join(latex)+'\n',encoding='utf-8')

# Derived comparisons used in results text (not additional experiments).
ssa={c:lookup[('SSA (ours)',c)]['r2'] for c in conditions}
nonoracle=['TTT','BN-Adapt','FR','RSD']
best_comp={c:max(lookup[(m,c)]['r2'] for m in nonoracle) for c in conditions[:-1]}
deltas={c:ssa[c]-best_comp[c] for c in conditions[:-1]}
wins=sum(v>1e-12 for v in deltas.values()); ties=sum(abs(v)<=1e-12 for v in deltas.values()); losses=sum(v< -1e-12 for v in deltas.values())
max_gain_c=max(deltas,key=deltas.get); min_gain_c=min(deltas,key=deltas.get)
ssa_source_gains={c:ssa[c]-lookup[('Source',c)]['r2'] for c in conditions[:-1]}
mean_order=sorted([(lookup[(m,'Mean')]['r2'],m) for m in methods if m!='Oracle'],reverse=True)
results=(
'## Results\n\n'
'On the 13 severity-5 corruptions, SSA has the highest reported non-oracle mean $R^2$ (0.731), followed by RSD (0.701) and FR (0.700); this is a 0.030 absolute increase over the strongest comparator mean. '
+f'Against the best value among TTT, BN-Adapt, FR, and RSD for each corruption, SSA is higher on {wins} conditions, tied on {ties}, and lower on {losses}. '
+f'The largest per-condition advantage is for shot noise (+{deltas[max_gain_c]:.3f}); the sole deficit is on {min_gain_c.lower()} ({deltas[min_gain_c]:+.3f}). '
+'The oracle mean is 0.789, but its target-label access makes it a reference ceiling rather than a same-information competitor. '
+'These comparisons are descriptive only: the inputs contain rounded aggregate cells, not independent repetitions, so no error bars, confidence intervals, or significance claims are supported.\n'
)
caption=(
'**Figure 1. Author-reported $R^2$ on corrupted UTKFace age prediction (severity 5).** '
'(A) Every supplied condition value and reported mean; blue denotes nonnegative performance and red denotes negative performance on the fixed -4 to 1 color scale. Negative $R^2$ values are retained. '
'(B) SSA minus the strongest reported non-oracle comparator (TTT, BN-Adapt, FR, or RSD) separately for each condition; positive values favor SSA. '
'The oracle row is outlined in gold because it uses target labels and is not a same-information competitor. Cells are rounded author-reported aggregates from arXiv:2410.03263v1, Table S4.T4; no per-run observations or uncertainty were supplied.\n'
)
Path('caption_and_results.md').write_text('# Caption and results text\n\n'+caption+'\n'+results,encoding='utf-8')

# Render a publication-sized two-panel figure using PIL.
W,H=3000,1740
im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
f_title=font(52,True); f_panel=font(37,True); f_body=font(29); f_small=font(24); f_cell=font(23,True); f_method=font(27,True)
d.text((90,45),'Corruption robustness in UTKFace age prediction',font=f_title,fill=(20,27,38))
d.text((90,112),'Author-reported R² at severity 5  •  higher is better  •  negative values are valid',font=f_body,fill=(65,73,86))
# Panel A geometry
x0,y0=330,285; cw=172; ch=105
d.text((70,205),'A',font=f_panel,fill=(20,27,38)); d.text((115,205),'Reported values',font=f_panel,fill=(20,27,38))
# column headers rotated for compactness
for j,c in enumerate(conditions):
    label=short[c]
    layer=Image.new('RGBA',(220,60),(255,255,255,0)); ld=ImageDraw.Draw(layer); ld.text((3,3),label,font=f_small,fill=(35,40,48,255))
    rot=layer.rotate(42,expand=True,resample=Image.Resampling.BICUBIC)
    im.paste(rot,(x0+j*cw+20,y0-120),rot)
for i,m in enumerate(methods):
    yy=y0+i*ch
    if m=='SSA (ours)': d.rounded_rectangle((55,yy+7,x0-12,yy+ch-7),12,fill=(222,235,247))
    if m=='Oracle': d.rounded_rectangle((55,yy+7,x0-12,yy+ch-7),12,fill=(255,247,220),outline=(190,135,25),width=4)
    d.text((72,yy+34),m+(' †' if m=='Oracle' else ''),font=f_method,fill=(28,34,43))
    for j,c in enumerate(conditions):
        x=x0+j*cw; r=lookup[(m,c)]; rgb=score_color(r['r2'])
        d.rectangle((x,yy,x+cw-5,yy+ch-5),fill=rgb)
        if c=='Mean': d.rectangle((x,yy,x+cw-5,yy+ch-5),outline=(25,25,25),width=4)
        if m=='Oracle': d.rectangle((x,yy,x+cw-5,yy+ch-5),outline=(190,135,25),width=4)
        txt=r['reported_decimal']; box=d.textbbox((0,0),txt,font=f_cell); tw=box[2]-box[0]; th=box[3]-box[1]
        d.text((x+(cw-5-tw)/2,yy+(ch-5-th)/2-2),txt,font=f_cell,fill=text_color(rgb))
# legend
leg_y=y0+len(methods)*ch+30
d.text((70,leg_y),'Color scale',font=f_small,fill=(45,50,58))
bar_x=230; bar_w=820
for xx in range(bar_w):
    value=-4+5*xx/(bar_w-1); d.line((bar_x+xx,leg_y,bar_x+xx,leg_y+30),fill=score_color(value))
for val in [-4,-3,-2,-1,0,1]:
    xx=bar_x+(val+4)/5*bar_w; d.line((xx,leg_y+30,xx,leg_y+40),fill=(30,30,30),width=2); d.text((xx-13,leg_y+43),str(val),font=f_small,fill=(45,50,58))
d.text((1130,leg_y+5),'Gold outline = oracle (target-label access)',font=f_small,fill=(110,79,18))
# Panel B: delta bars
pb_y=1325
d.text((70,pb_y-95),'B',font=f_panel,fill=(20,27,38)); d.text((115,pb_y-95),'SSA relative to strongest non-oracle comparator by condition',font=f_panel,fill=(20,27,38))
plot_x0=360; plot_x1=2860; zero_y=pb_y+100; scale=1050
d.line((plot_x0,zero_y,plot_x1,zero_y),fill=(35,40,48),width=3)
bar_gap=(plot_x1-plot_x0)/len(conditions[:-1]); bw=92
for j,c in enumerate(conditions[:-1]):
    v=deltas[c]; cx=plot_x0+(j+0.5)*bar_gap; end=zero_y-v*scale; col=(42,121,170) if v>=0 else (202,72,66)
    d.rectangle((cx-bw/2,min(zero_y,end),cx+bw/2,max(zero_y,end)),fill=col)
    lab=f'{v:+.3f}'; bb=d.textbbox((0,0),lab,font=f_small); d.text((cx-(bb[2]-bb[0])/2,(end-37 if v>=0 else end+7)),lab,font=f_small,fill=(35,40,48))
    layer=Image.new('RGBA',(190,45),(255,255,255,0)); ld=ImageDraw.Draw(layer); ld.text((1,1),short[c],font=f_small,fill=(45,50,58,255)); rot=layer.rotate(35,expand=True,resample=Image.Resampling.BICUBIC); im.paste(rot,(int(cx-28),zero_y+28),rot)
d.text((90,1665),'Bars are descriptive differences of rounded aggregates; no uncertainty or significance is implied.',font=f_small,fill=(80,86,96))
im.save('figure1.png',dpi=(300,300),optimize=True)

# Editable SVG counterpart with equivalent values and oracle distinction.
svg=[]; A=svg.append
A(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
A('<rect width="100%" height="100%" fill="white"/>')
A('<style>text{font-family:Arial,sans-serif;fill:#1c222b}.title{font-size:52px;font-weight:700}.sub{font-size:29px;fill:#414956}.panel{font-size:37px;font-weight:700}.method{font-size:27px;font-weight:700}.cell{font-size:23px;font-weight:700;text-anchor:middle}.small{font-size:24px;fill:#505660}</style>')
A('<text x="90" y="85" class="title">Corruption robustness in UTKFace age prediction</text>')
A('<text x="90" y="145" class="sub">Author-reported R² at severity 5 • higher is better • negative values are valid</text>')
A('<text x="70" y="245" class="panel">A  Reported values</text>')
for j,c in enumerate(conditions):
    xx=x0+j*cw+65; A(f'<text x="{xx}" y="{y0-15}" class="small" transform="rotate(-42 {xx} {y0-15})">{esc_svg(short[c])}</text>')
for i,m in enumerate(methods):
    yy=y0+i*ch
    if m=='SSA (ours)': A(f'<rect x="55" y="{yy+7}" width="263" height="{ch-14}" rx="12" fill="#deebf7"/>')
    if m=='Oracle': A(f'<rect x="55" y="{yy+7}" width="263" height="{ch-14}" rx="12" fill="#fff7dc" stroke="#be8719" stroke-width="4"/>')
    A(f'<text x="72" y="{yy+67}" class="method">{esc_svg(m)}{" †" if m=="Oracle" else ""}</text>')
    for j,c in enumerate(conditions):
        x=x0+j*cw; r=lookup[(m,c)]; rgb=score_color(r['r2']); fill='#%02x%02x%02x'%rgb; tc='#ffffff' if text_color(rgb)==(255,255,255) else '#191919'; stroke='#be8719' if m=='Oracle' else ('#191919' if c=='Mean' else 'none'); sw=4 if (m=='Oracle' or c=='Mean') else 0
        A(f'<rect x="{x}" y="{yy}" width="{cw-5}" height="{ch-5}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        A(f'<text x="{x+(cw-5)/2}" y="{yy+63}" class="cell" style="fill:{tc}">{r["reported_decimal"]}</text>')
A(f'<text x="70" y="{leg_y+25}" class="small">Color scale: red = negative, white = 0, blue = positive (fixed −4 to 1); gold outline = oracle</text>')
A(f'<text x="70" y="{pb_y-55}" class="panel">B  SSA relative to strongest non-oracle comparator by condition</text>')
A(f'<line x1="{plot_x0}" y1="{zero_y}" x2="{plot_x1}" y2="{zero_y}" stroke="#232830" stroke-width="3"/>')
for j,c in enumerate(conditions[:-1]):
    v=deltas[c]; cx=plot_x0+(j+0.5)*bar_gap; end=zero_y-v*scale; col='#2a79aa' if v>=0 else '#ca4842'; y=min(zero_y,end); hh=abs(end-zero_y)
    A(f'<rect x="{cx-bw/2:.1f}" y="{y:.1f}" width="{bw}" height="{hh:.1f}" fill="{col}"/>')
    A(f'<text x="{cx:.1f}" y="{end-10 if v>=0 else end+32:.1f}" class="small" text-anchor="middle">{v:+.3f}</text>')
    A(f'<text x="{cx:.1f}" y="{zero_y+46}" class="small" transform="rotate(35 {cx:.1f} {zero_y+46})">{esc_svg(short[c])}</text>')
A('<text x="90" y="1695" class="small">Bars are descriptive differences of rounded aggregates; no uncertainty or significance is implied.</text>')
A('</svg>')
Path('figure1.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')

manifest={
 'source':{'asset':'numeric-evidence','sha256':data.get('source_sha256'),'url':data.get('source_url'),'paper_version':data.get('paper_version')},
 'input_rows':len(rows),'methods':methods,'conditions':conditions,
 'transformations':{
   'panel_a':'Direct display of supplied r2 cells and author-reported means; labels use reported_decimal.',
   'panel_b':'For each non-Mean condition: SSA r2 minus max(TTT, BN-Adapt, FR, RSD) r2.',
   'ledger':'One numeric value per supplied cell_id, copied from r2.'
 },
 'derived_checks':{'ssa_reported_mean':ssa['Mean'],'best_nonoracle_reported_mean':mean_order[1][0] if mean_order[0][1]=='SSA (ours)' else mean_order[0][0],'ssa_mean_margin_over_rsd':ssa['Mean']-lookup[('RSD','Mean')]['r2'],'condition_wins':wins,'condition_ties':ties,'condition_losses':losses,'panel_b_deltas':deltas},
 'limitations':['Rounded author-reported aggregates are not independent repetitions.','No per-run observations or sampling uncertainty were supplied.','Oracle uses target labels and is not a same-information competitor.','No new experiment or causal test was performed.']
}
Path('provenance.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'ok','outputs':['displayed_values.json','table.csv','table.md','table.tex','figure1.png','figure1.svg','caption_and_results.md','provenance.json'],'rows':len(rows),'wins_ties_losses':[wins,ties,losses]},indent=2))
