from pathlib import Path
p=Path('generate_evidence.py')
s=p.read_text(encoding='utf-8')
files=[q for q in Path('inputs').rglob('*') if q.is_file()]
numeric=next(q for q in files if 'numeric' in q.name.lower())
facts=next(q for q in files if 'research' in q.name.lower() or 'fact' in q.name.lower())
s=s.replace("NUMERIC = Path('inputs/numeric_evidence.json')",f"NUMERIC = Path({str(numeric)!r})")
s=s.replace("FACTS = Path('inputs/research_facts.json')",f"FACTS = Path({str(facts)!r})")
exec(compile(s,'generate_evidence.py','exec'),{'__name__':'__main__'})
