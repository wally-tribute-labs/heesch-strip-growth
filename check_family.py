"""Cross-check free shape counts by working directly in the unrotated axial coordinates."""
import json
from pathlib import Path
from heesch_verify.grids import GRIDS
from heesch_verify.canonical import canonical_digest
from tools.polyforms import parse_kaplan_file

grid=GRIDS['H']
rows=parse_kaplan_file(Path('kaplan17.txt').read_text())
out=set()
records=0
for shape,hc,hh in rows:
    if hc!=3:
        continue
    for a,b in [(1,0),(0,1),(1,1)]:
        proj=lambda p:a*p[0]+b*p[1]
        vals=list(map(proj,shape))
        for level in range(min(vals)+1,max(vals)):
            stripe={p for p in shape if proj(p)==level}
            # A 3-cell line is connected iff its three cells have four directed adjacencies.
            if len(stripe)!=3 or sum(n in stripe for p in stripe for n in grid.edge_neighbors(p))!=4:
                continue
            for dx,dy in grid.edge_neighbors((0,0)):
                if proj((dx,dy))!=1:
                    continue
                child={p for p in shape if proj(p)<=level}
                child.update((x+dx,y+dy) for x,y in shape if proj((x,y))>=level)
                out.add(canonical_digest(child,grid,True))
                records+=1
bank=json.loads(Path('family.json').read_text())
assert set(bank)==out and sum(len(r['origins']) for r in bank.values())==records
print(f'Independent in-place axial projection reproduces {records} constructions and {len(out)} distinct digests.')

