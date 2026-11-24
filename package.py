"""Copy only replay inputs, source, reports, proofs, and witnesses to artifact/."""
from pathlib import Path
import shutil,hashlib
source=Path.cwd()
target=source/'artifact'
target.mkdir(exist_ok=True)
names=['README.md','generate.py','check_family.py','search.py','audit.py','refine.py','exact.py',
       'classify.py','batch.py','report.py','period_from_patch.py','build.sh','source-deps.sh',
       'prove-best.sh','check_proof.py','package.py','downloads.sha256','kaplan17.txt','parents.json',
       'family.json','generate.log','stage.jsonl','stage.log','audit.jsonl','audit.log','summary.json',
       'additional-periods.json','best-finite.heesch','paired-finite.heesch','check-family.log','proof.log','finish-status.txt']
names.extend(p.name for p in source.glob('four-ring-????????????.heesch'))
if (source/'proof-gate.json').exists():
    names.append('proof-gate.json')
for name in ['best.heesch','core.txt.xz','proof.lrat.xz']:
    if (source/'proof'/name).exists():
        names.append(f'proof/{name}')
for name in names:
    p=target/name
    p.parent.mkdir(exist_ok=True)
    shutil.copyfile(source/name,p)
manifest=''.join(hashlib.sha256((target/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in sorted(names))
(target/'SHA256SUMS').write_text(manifest)
print(f'{len(names)} files hashed in {target}')

