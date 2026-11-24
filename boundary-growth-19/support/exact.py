"""Pack bounded coronae with independently supported placement domains."""
from collections import defaultdict
from pysat.solvers import Minicard
from audit import GRID, holes_of, verify_witness, VerifyConfig

def find_patch(problem, depth, support, strict):
    templates={}
    for k in range(1,depth+1):
        if not support[k]:
            return None,{'local_exclusion_at':k}
        problem.lift(support[k])
        templates[k]={s:list(rel) for s,rel in problem.pose_neighbors.items()}
    def near(p,k):
        si,x,y=p
        return ((sj,x+dx,y+dy) for sj,dx,dy in templates[k][si])
    layers=[[problem.central]]
    forb=problem.halo|problem.tile
    for lev in range(1,depth+1):
        generated={q for p in layers[-1] for q in near(p,depth-lev+1)}
        if lev>1:
            generated={q for q in generated if problem.cells(q).isdisjoint(forb)}
        layers.append(sorted(generated))
    index={}
    by_cell=defaultdict(list)
    with Minicard() as solver:
        for lev,layer in enumerate(layers):
            for p in layer:
                v=len(index)+1
                index[lev,p]=v
                for cell in problem.cells(p):
                    by_cell[cell].append(v)
        for vs in by_cell.values():
            if len(vs)>1:
                solver.add_atmost(vs,1)
        solver.add_clause([index[0,problem.central]])
        predecessors=defaultdict(list)
        for lev,layer in enumerate(layers[:-1]):
            for p in layer:
                v=index[lev,p]
                cover=defaultdict(list)
                for q in near(p,depth-lev):
                    ids=[index[l,q] for l in range(max(0,lev-1),lev+2) if (l,q) in index]
                    if ids:
                        for cell in problem.cells(q)&problem.ring(p):
                            cover[cell].extend(ids)
                        if (lev+1,q) in index:
                            predecessors[index[lev+1,q]].append(v)
                for c in problem.ring(p):
                    solver.add_clause([-v,*cover[c]])
        for (lev,p),v in index.items():
            if lev>0:
                solver.add_clause([-v,*predecessors[v]])
        holes_blocked=0
        layer_of={v:lev for (lev,p),v in index.items()}
        stats={'variables_by_level':list(map(len,layers))}
        while solver.solve():
            chosen=set(v for v in solver.get_model() if v>0)
            placed=[(lev,p,v) for (lev,p),v in index.items() if v in chosen]
            have_obstruction=False
            for level in range(1,depth+int(strict)):
                owners={c:v for lev,p,v in placed if lev<=level for c in problem.cells(p)}
                holes=holes_of(frozenset(owners),GRID)
                if not holes:
                    continue
                # Keeping the occupied perimeter of the cavities forces interior
                # holes to be filled at this level. May block many completions.
                wall={owners[n] for c in holes for n in GRID.edge_neighbors(c) if n in owners}
                for c in sorted(holes):
                    solver.add_clause([-v for v in wall]+[v for v in by_cell[c] if layer_of[v]<=level])
                holes_blocked+=1
                have_obstruction=True
                break
            if not have_obstruction:
                shape_line='H '+' '.join(str(a) for c in sorted(problem.tile) for a in c)
                entries=[]
                for lev,(si,x,y),v in placed:
                    sym=GRID.orientations[si]
                    entries.append((lev,f'{lev} <{sym.a},{sym.b},{x},{sym.d},{sym.e},{y}>'))
                hc=depth-int(bool(holes_of(frozenset().union(*(problem.cells(p) for lev,p,v in placed)),GRID)))
                prefix=[s for lev,s in entries if lev<=hc]
                lines=[shape_line,f'~ {hc} {depth} {1+int(hc<depth)}',str(len(prefix)),*prefix]
                if hc<depth:
                    lines.extend([str(len(entries)),*(s for lev,s in entries)])
                witness='\n'.join(lines)+'\n'
                result=verify_witness(witness,VerifyConfig(strict_claims=True)).result
                assert (result.hc_verified,result.hh_verified)==(hc,depth)
                return witness,{**stats,'hole_models_cut':holes_blocked}
        return None,{**stats,'hole_models_cut':holes_blocked}

