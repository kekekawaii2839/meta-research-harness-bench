from pathlib import Path
for p in sorted(Path('inputs').rglob('*')):
    if p.is_file():
        print(p.as_posix())
