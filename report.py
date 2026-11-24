"""Summarize completed per-member audits and save their replayable source records."""
from pathlib import Path
from collections import Counter
import json
from heesch_verify.witness import verify_witness,VerifyConfig

bank=json.loads(Path('family.json').read_text())
rows=[json.loads(f.read_text()) for f in sorted(Path('cases').glob('*.json'))]
assert set(r['key'] for r in rows)==set(bank)
errors=[r for r in rows if 'error' in r]
assert not errors,errors
finite=[r for r in rows if r.get('upper_hh') is not None]
tilers=[r for r in rows if r.get('tiler_gate','').startswith('tiler:')]
alldeep=[r for r in rows if 'hc' in r and r.get('upper_hh') is None]
assert len(finite)+len(tilers)+len(alldeep)==len(bank)
tally=Counter((r['hc'],r['hh']) for r in finite)
best=max((r['hc'],r['hh']) for r in finite)
champions=[r for r in finite if (r['hc'],r['hh'])==best]
for r in rows:
    if 'witness' in r:
        res=verify_witness(r['witness'],VerifyConfig(strict_claims=True)).result
        assert res.canonical_digest==r['key'] and res.hc_verified==r['hc']
        hh=res.hh_verified
        if r.get('hh_witness'):
            hh=verify_witness(r['hh_witness'],VerifyConfig(strict_claims=True)).result.hh_verified
        assert hh==r['hh']
best_id=next((r['key'] for r in champions if r['key'].startswith('74224b')),champions[0]['key'])
selected=next(r for r in champions if r['key']==best_id)
Path('best-finite.heesch').write_text(selected['witness'])
paired=next(r for r in champions if r['key'].startswith('c5a38210e548'))
Path('paired-finite.heesch').write_text(paired['witness'])
with Path('audit.jsonl').open('w') as audit:
    for row in rows:
        record = row.copy()
        record['shape_digest'] = record.pop('key')
        audit.write(json.dumps(record) + '\n')
from period_from_patch import find_unit
extra=[]
for r in alldeep:
    path=Path(f"four-ring-{r['key'][:12]}.heesch")
    path.write_text(r['witness'])
    unit=find_unit(path,12)
    if unit:
        extra.append(unit)
proved={unit['shape_digest'] for unit in extra}
Path('additional-periods.json').write_text(json.dumps(extra,indent=2)+'\n')
result={'family':len(bank),'finite_counts':{'%d,%d'%k:v for k,v in sorted(tally.items())},
        'finite_total':len(finite),'best_finite_ids':[r['key'] for r in champions],
        'best_finite_selected':best_id,'frozen_gate_tilers':len(tilers),
        'gate_types':dict(Counter(r['tiler_gate'].split(':')[1] for r in tilers)),
        'additional_periodic_tilers':len(extra),'tilers_total':len(tilers)+len(extra),'four_or_more_unclassified':[{'id':r['key'],'hc':r['hc'],'hh':r['hh']} for r in alldeep if r['key'] not in proved],
        'all_native_resource_failures_recovered':all('error' not in r for r in rows if r['native'] in ('process_failure', 'timeout'))}
Path('summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))

