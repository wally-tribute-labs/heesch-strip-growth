"""Classify one family member per worker process, retaining diagnostic/geometry records."""
import json, sys
from pathlib import Path
from audit import LocalPacking,GRID,strict_result,VerifyConfig,verify_witness
from refine import local_support
from exact import find_patch
from heesch_verify.gates import IsohedralGate

def main():
    row=json.loads(sys.stdin.read())
    key=row['key']
    tile=list(map(tuple,row['cells']))
    native=row['native']
    status=native['status']
    data={'key':key,'native':status}
    if status.startswith('I'):
        data['tiler_gate']=IsohedralGate(GRID).evaluate(tile).detail
        if data['tiler_gate'].startswith('tiler:'):
            return data
    p=LocalPacking(tile)
    support=local_support(p,4)
    data['necessary_contacts']=[len(z) for z in support[1:]]
    upper=next((k-1 for k in range(1,len(support)) if not support[k]),4)
    if upper>=3 and 'tiler_gate' not in data:
        data['tiler_gate']=IsohedralGate(GRID).evaluate(tile).detail
        if data['tiler_gate'].startswith('tiler:'):
            return data
    source='H '+' '.join(str(a) for c in sorted(tile) for a in c)+'\n~ 0 0 0\n'
    archive={}
    def retain(witness):
        r=verify_witness(witness,VerifyConfig(strict_claims=True)).result
        assert r.canonical_digest==key
        archive[r.hc_verified,r.hh_verified]=witness
    retain(source)
    if 'raw' in native:
        retain(strict_result(native['raw']))
    data['exact_queries']=[]
    # First recover the deepest hole-permitted geometry and exclusion.
    hh=None
    for level in range(upper,-1,-1):
        if any(d>=level for k,d in archive):
            hh=level
            break
        witness,stats=find_patch(p,level,support,False)
        data['exact_queries'].append({'level':level,'strict':False,'sat':bool(witness),**stats})
        if witness:
            retain(witness)
            hh=level
            break
    # If every surviving top ring was holey, search its strict version.
    hc=max(k for k,d in archive)
    if hh>hc:
        witness,stats=find_patch(p,hh,support,True)
        data['exact_queries'].append({'level':hh,'strict':True,'sat':bool(witness),**stats})
        if witness:
            retain(witness)
            hc=hh
    assert hc in (hh,hh-1)
    data.update(hc=hc,hh=hh,upper_hh=None if hh==4 else hh)
    data['witness']=archive[max(archive)]
    if (hc,hh) not in archive:
        data['hh_witness']=archive[max(archive,key=lambda x:x[1])]
    return data
if __name__=='__main__':
    print(json.dumps(main()))

