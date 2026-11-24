"""Hole-agnostic upper bounds and verified positive geometries.

A pose is (orientation, x, y) on the hex grid; drop duplicate orientations
of a symmetric tile by canonicalizing oriented offsets up to translation.
"""
from collections import defaultdict
import json
from pathlib import Path
from pysat.solvers import Minicard
from heesch_verify.grids import GRIDS
from heesch_verify.patch import required_set
from heesch_verify.result import ErrorCode, VerifyError
from heesch_verify.witness import verify_witness, VerifyConfig
from heesch_verify.shape import holes_of

GRID = GRIDS['H']
CONTACT = GRID.contact('point')

def translate(cells,dx,dy):
    return frozenset((x+dx,y+dy) for x,y in cells)

class LocalPacking:
    def __init__(self,tile):
        self.tile=frozenset(tile)
        self.halo=required_set(self.tile,CONTACT)
        self.images={}
        self.image_id={}
        for sym in GRID.orientations:
            raw=frozenset(sym.apply(cell) for cell in self.tile)
            image = GRID.normalize(raw)
            if image not in self.image_id:
                self.image_id[image]=sym.index
                self.images[sym.index]=raw
        self.pose_neighbors={}
        self.cache={}
        self.halo_cache={}
        self.central=(0,0,0)

    def cells(self,pose):
        if pose not in self.cache:
            s,x,y=pose
            self.cache[pose]=translate(self.images[s],x,y)
        return self.cache[pose]

    def ring(self,pose):
        if pose not in self.halo_cache:
            self.halo_cache[pose]=required_set(self.cells(pose),CONTACT)
        return self.halo_cache[pose]

    def domain(self):
        poses=[]
        for si,image in self.images.items():
            shifts={(x-u,y-v) for x,y in self.halo for u,v in image}
            poses.extend(p for dx,dy in sorted(shifts) if self.cells(p:=(si,dx,dy)).isdisjoint(self.tile))
        return poses

    def one(self,poses):
        solver=Minicard()
        by_cell=defaultdict(list)
        for var,p in enumerate(poses,1):
            for c in self.cells(p):
                by_cell[c].append(var)
        for vs in by_cell.values():
            if len(vs)>1:
                solver.add_atmost(vs,1)
        for c in self.halo:
            solver.add_clause(by_cell[c])
        return solver

    def base(self):
        poses=self.domain()
        with self.one(poses) as solver:
            if not solver.solve():
                return []
            possible=set()
            impossible=set()
            for var in range(1,len(poses)+1):
                if var not in possible:
                    if solver.solve(assumptions=[var]):
                        possible.update(x for x in solver.get_model() if 0<x<=len(poses))
                    else:
                        impossible.add(var)
            assert len(possible)+len(impossible)==len(poses)
            return [poses[i-1] for i in sorted(possible)]

    def lift(self,allowed):
        # Express the same allowed relative placements about every oriented central tile.
        for si in self.images:
            sym=GRID.orientations[si]
            transformed=[]
            for p in allowed:
                raw=[sym.apply(c) for c in self.cells(p)]
                sj=self.image_id[GRID.normalize(raw)]
                image=self.images[sj]
                transformed.append((sj, min(x for x,y in raw)-min(x for x,y in image),
                                       min(y for x,y in raw)-min(y for x,y in image)))
            self.pose_neighbors[si]=transformed

    def near(self,pose):
        si,x,y=pose
        return [(sj,x+dx,y+dy) for sj,dx,dy in self.pose_neighbors[si]]

def strict_result(raw):
    """Repair upstream output-format differences and check the actual ring geometry."""
    lines=raw.splitlines()
    nums=list(map(int,lines[0].split()[1:]))
    tile=frozenset(zip(nums[::2],nums[1::2]))
    if len(lines)==2:
        return lines[0]+"\n~ 0 0 0\n"
    rows=lines[2:]
    patches=[]
    while rows:
        n=int(rows[0])
        patch=rows[1:n+1]
        assert len(patch)==n
        patches.append(patch)
        rows=rows[n+1:]
    # Recover both strict and hole-permitted witnesses even if the new CLI
    # emitted a single holey patch. All retained levels must pass frozen checks.
    strict=[]
    prof=[]
    for patch in patches:
        d=max(int(s.split()[0]) for s in patch)
        for k in range(d,-1,-1):
            prefix=[s for s in patch if int(s.split()[0])<=k]
            header=lambda a,b,n:f'~ {a} {b} {n}'
            trial='\n'.join([lines[0],header(k,k,1),str(len(prefix)),*prefix])+'\n'
            try:
                verify_witness(trial,VerifyConfig(strict_claims=True))
            except VerifyError as err:
                if err.code != ErrorCode.PATCH_HOLE_IN_CORONA:
                    raise
                continue
            strict.append((k,prefix))
            prof.append((d,patch))
            break
    k,a=max(strict,key=lambda s:s[0])
    d,b=max(prof,key=lambda s:s[0])
    parts=[lines[0],f'~ {k} {d} {1+int(d>k)}',str(len(a)),*a]
    if d>k:
        parts.extend([str(len(b)),*b])
    out='\n'.join(parts)+'\n'
    result=verify_witness(out,VerifyConfig(strict_claims=True)).result
    assert (k,d)==(result.hc_verified,result.hh_verified)
    return out

