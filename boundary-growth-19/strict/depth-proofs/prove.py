"""Research non-tiling certificates for depth-three finalists.

For a tile at contact distance j from the center of a d-ring patch, its
neighbors in the patch are consistent with its own d-j layers whenever
d-j>=1. At positive depth it is surrounded: in the weak final corona it
is sufficient that the immediate halo is covered, even if there are pockets.
Every layer here relaxes topology and uses a previously certified superset
of contacts. Dropping outermost layers relaxes the corresponding patch.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import tempfile

from audit import GRID, LocalPacking
from heesch_verify.canonical import canonical_digest
from pysat.card import CardEnc, EncType
from pysat.formula import CNF
from pysat.solvers import Glucose4
from refine import local_support


class Formula(CNF):
    def disjoint(self, owners):
        for cell in sorted(owners):
            variables = owners[cell]
            if len(variables)<=1:
                continue
            self.extend(CardEnc.atmost(variables,bound=1,top_id=self.nv,encoding=EncType.seqcounter).clauses)


def local(problem, previous, supported):
    if previous is None:
        poses=problem.domain()
    else:
        problem.lift(previous)
        # If the selected neighbor is present its inverse contact must be
        # supported too: the neighbor has at least depth-1 layers around it.
        poses=[p for p in previous if problem.central in problem.near(p)]
    formula=Formula()
    formula.nv=len(poses)
    owners=defaultdict(list)
    for i,p in enumerate(poses,1):
        for c in problem.cells(p):
            owners[c].append(i)
    formula.disjoint(owners)
    for c in sorted(problem.halo):
        formula.append(owners[c])
    if previous is not None:
        allowed={p:set(problem.near(p)) for p in poses}
        for i,p in enumerate(poses):
            for j in range(i+1,len(poses)):
                q=poses[j]
                if (q not in allowed[p] or p not in allowed[q]) and problem.ring(p)&problem.cells(q):
                    formula.append([-i-1,-j-1])
    indices={p:i for i,p in enumerate(poses,1)}
    assert set(supported)<=indices.keys()
    # UNSAT certifies that not one discarded pose is possible.
    formula.append([i for p,i in indices.items() if p not in supported])
    return formula


def partial(problem, supports, last, outer_pairs):
    depth=4
    templates={}
    for s in range(1,depth+1):
        problem.lift(supports[s])
        templates[s]={ori:set(poses) for ori,poses in problem.pose_neighbors.items()}
    def near(p,s):
        ori,x,y=p
        return ((j,x+dx,y+dy) for j,dx,dy in sorted(templates[s][ori]))
    def allowed(p,q,s):
        return (q[0],q[1]-p[1],q[2]-p[2]) in templates[s][p[0]]
    layers=[[problem.central]]
    for r in range(1,last+1):
        candidates={q for p in layers[-1] for q in near(p,depth-r+1)}
        if r>1:
            candidates={p for p in candidates if problem.cells(p).isdisjoint(problem.tile|problem.halo)}
        layers.append(sorted(candidates))
    index={(r,p):0 for r,poses in enumerate(layers) for p in poses}
    for i,k in enumerate(index,1):
        index[k]=i
    f=Formula()
    f.nv=len(index)
    owners=defaultdict(list)
    for (_,p),i in index.items():
        for c in problem.cells(p):
            owners[c].append(i)
    f.disjoint(owners)
    f.append([index[0,problem.central]])
    for r,poses in enumerate(layers[:-1]):
        for p in poses:
            cover=defaultdict(list)
            for q in near(p,depth-r):
                vs=[index[j,q] for j in range(max(0,r-1),r+2) if (j,q) in index]
                if vs:
                    for c in problem.cells(q)&problem.ring(p):
                        cover[c].extend(vs)
            for c in sorted(problem.ring(p)):
                f.append([-index[r,p],*cover[c]])
    # Each outer tile has a compatible predecessor. A tile in layer r cannot
    # also occupy any lower layer by the exact no-overlap constraints.
    for r in range(1,last+1):
        predecessors=defaultdict(list)
        for p in layers[r-1]:
            for q in near(p,depth-r+1):
                if (r,q) in index:
                    predecessors[q].append(index[r-1,p])
        for q in layers[r]:
            f.append([-index[r,q],*predecessors[q]])
    if outer_pairs:
        # Optional strong relaxation for the retained outer layer. In a
        # depth-four patch, touching tiles at distance r both have d-r layers.
        # When d-r=0 there is no such implication.
        assert last<depth
        ids={index[last,q]:q for q in layers[last]}
        for p in layers[last]:
            i=index[last,p]
            touching={j for c in problem.ring(p) for j in owners[c] if j>i and j in ids}
            for j in sorted(touching):
                q=ids[j]
                if not allowed(p,q,depth-last) or not allowed(q,p,depth-last):
                    f.append([-i,-j])
    return f,list(map(len,layers)),index


def checksum(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def record(formula, target, checker, scope):
    with tempfile.TemporaryDirectory(dir='.') as temp:
        work=Path(temp)
        cnf=work/'input.cnf'
        proof=work/'proof.drat'
        lrat=work/'proof.lrat'
        formula.to_file(str(cnf))
        with Glucose4(bootstrap_with=formula.clauses,with_proof=True) as solver:
            if solver.solve():
                return False
            lines=solver.get_proof()
            if not lines or lines[-1]!='0':
                lines.append('0')
            proof.write_text('\n'.join(lines)+'\n')
        checks=[('lrat-check',[cnf,lrat],'c VERIFIED')]
        if [] in formula.clauses:
            # drat-trim reports trivial UNSAT when the CNF already has an empty
            # clause. Its one-step LRAT cites the existing empty clause directly.
            lrat.write_text(f'{len(formula.clauses)+1} 0 {formula.clauses.index([])+1} 0\n')
        else:
            checks.insert(0,('drat-trim',[cnf,proof,'-L',lrat],'s VERIFIED'))
        for exe,args,mark in checks:
            result=subprocess.run([checker/exe,*args],capture_output=True,text=True,check=True)
            if mark not in result.stdout.splitlines():
                raise ValueError(f'{target} {exe} expected {mark}, got {result.stdout[-500:]}')
        target.mkdir(exist_ok=True)
        info=dict(scope=scope,variables=formula.nv,clauses=len(formula.clauses),
                  formula_sha256=checksum(cnf),lrat_sha256=checksum(lrat),drat_sha256=checksum(proof))
        for file in (cnf,lrat):
            (target/(file.name+'.xz')).write_bytes(lzma.compress(file.read_bytes(),preset=3))
        (target/'receipt.json').write_text(json.dumps(info,indent=2)+'\n')
        print(target,info['variables'],info['clauses'],'VERIFIED',flush=True)
        return True


def read_tiles(path):
    tiles={}
    for line in path.read_text().splitlines():
        row=list(map(int,line.split()))
        tiles[row[0]]=list(zip(row[1::2],row[2::2]))
    return tiles


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('tiles',type=Path)
    ap.add_argument('id',type=int)
    ap.add_argument('checker',type=Path)
    ap.add_argument('--local',action='store_true')
    ap.add_argument('--partial',type=int,choices=[1,2,3,4])
    ap.add_argument('--outer-pairs',action='store_true')
    args=ap.parse_args()
    tile=read_tiles(args.tiles)[args.id]
    out=Path(str(args.id))
    out.mkdir(exist_ok=True)
    p=LocalPacking(tile)
    # The four-step and five-step classifications are separate from Yukon non-tiling proofs.
    supports=local_support(p,5 if args.id in (33048,26263) else 4)
    if args.local:
        (out/'geometry.json').write_text(json.dumps(dict(cells=tile,digest=canonical_digest(tile,GRID,True),
             contacts=[len(s) for s in supports[1:]],supported=supports[1:]),separators=(',',':'))+'\n')
        for d in range(1,len(supports)):
            scope={'claim':'all possible contacts belong to retained set','depth':d,'supported':len(supports[d])}
            target=out/f'contacts-{d}'
            if not (target/'receipt.json').is_file():
                assert record(local(p,supports[d-1] if d>1 else None,supports[d]),target,args.checker,scope)
    if args.partial:
        assert len(supports)>=5 and supports[4]
        f,sizes,_=partial(p,supports,args.partial,args.outer_pairs)
        scope=dict(claim='no weak fourth corona',required_depth=4,retained_layers=sizes,
                   check_outer_contacts=args.outer_pairs)
        print(scope,flush=True)
        print('unsat',record(f,out/f'partial-{args.partial}',args.checker,scope),flush=True)


if __name__=='__main__':
    main()
