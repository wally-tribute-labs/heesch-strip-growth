"""Regenerate each search formula from the four archive shapes and check its LRAT."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from pysat.solvers import Glucose4
from audit import VerifyConfig,verify_witness
from prove import GRID, LocalPacking, canonical_digest, local, local_support, partial


def digest(data):
    return hashlib.sha256(data).hexdigest()


def positive(path, last):
    value=verify_witness(path.read_text(),VerifyConfig(strict_claims=True))
    assert value.result.hc_verified>=4
    p=LocalPacking(value.submission.cells)
    supports=local_support(p,4)
    f,_,index=partial(p,supports,last,outer_pairs=last==2)
    selected={(level,transform.apply_all(value.submission.cells))
              for level,transform in value.submission.patches[0] if level<=last}
    seen=set()
    assumptions=[]
    for (level,pose),var in index.items():
        key=(level,p.cells(pose))
        if key in selected:
            seen.add(key)
            assumptions.append(var)
        else:
            assumptions.append(-var)
    assert seen==selected
    with Glucose4(bootstrap_with=f.clauses) as solver:
        assert solver.solve(assumptions=assumptions)
    return len(selected)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',type=Path)
    ap.add_argument('lrat_checker',type=Path)
    ap.add_argument('--four-ring-control',type=Path)
    ap.add_argument('--three-ring-witnesses',type=Path)
    args=ap.parse_args()
    archive=args.root.resolve()
    proved={}
    with TemporaryDirectory() as d:
        work=Path(d)
        for case in (37921,33048,26263,1228):
            folder=archive/str(case)
            geometry=json.loads((folder/'geometry.json').read_text())
            tile=list(map(tuple,geometry['cells']))
            p=LocalPacking(tile)
            assert geometry['digest']==canonical_digest(tile,GRID,True)
            supports=[[]]+[[tuple(q) for q in s] for s in geometry['supported']]
            assert list(map(len,supports[1:]))==geometry['contacts']
            proofs=[]
            for stage in sorted(folder.iterdir()):
                if not stage.is_dir():
                    continue
                manifest=json.loads((stage/'receipt.json').read_text())
                scope=manifest['scope']
                if stage.name.startswith('contacts-'):
                    k=scope['depth']
                    assert stage.name==f'contacts-{k}' and scope['supported']==len(supports[k])
                    f=local(p,supports[k-1] if k>1 else None,supports[k])
                else:
                    assert scope['required_depth']==4 and scope['claim']=='no weak fourth corona'
                    last=len(scope['retained_layers'])-1
                    f,sizes,_=partial(p,supports,last,scope['check_outer_contacts'])
                    assert sizes==scope['retained_layers']
                cnf=work/'input.cnf'
                lrat=work/'proof.lrat'
                f.to_file(str(cnf))
                raw=cnf.read_bytes()
                assert digest(raw)==manifest['formula_sha256'] and raw==lzma.decompress((stage/'input.cnf.xz').read_bytes())
                proof=lzma.decompress((stage/'proof.lrat.xz').read_bytes())
                assert digest(proof)==manifest['lrat_sha256']
                lrat.write_bytes(proof)
                status=subprocess.run([args.lrat_checker.resolve(),cnf,lrat],check=True,capture_output=True,text=True)
                assert 'c VERIFIED' in status.stdout.splitlines()
                proofs.append(stage.name)
            assert all(f'contacts-{k}' in proofs for k in range(1,len(supports)))
            failed=next((k for k in range(1,len(supports)) if not supports[k]),None)
            if any(s.startswith('partial-') for s in proofs):
                failed=min(failed or 4,4)
            if failed != 4:
                raise ValueError(
                    f'{case}: expected a weak fourth-ring exclusion, got depth {failed}. '
                    f'Check the contact and partial-patch proof directories in {folder}.'
                )
            proved[case]={'checked':proofs,'excluded_weak_depth':failed}
            if args.three_ring_witnesses:
                witness=(args.three_ring_witnesses/f'{case}-3.heesch').read_text()
                result=verify_witness(witness,VerifyConfig(strict_claims=True)).result
                assert (result.canonical_digest,result.hc_verified,result.hh_verified)==(geometry['digest'],3,3)
                proved[case]['verified_positive_depth']=3
        if args.four_ring_control:
            # Pin the actual placements through two layers of a known four-ring shape.
            proved['control']={'depth_two_pinned_placements':positive(args.four_ring_control,2),
                               'depth_three_pinned_placements':positive(args.four_ring_control,3)}
    print(json.dumps(proved,indent=2))


if __name__=='__main__':
    main()
