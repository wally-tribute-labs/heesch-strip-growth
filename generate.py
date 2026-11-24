"""All nearest-neighbour axial strip duplications, represented up to D6 and translation."""
import json
from collections import Counter
from pathlib import Path
from heesch_verify.canonical import canonical_digest, canonical_form
from heesch_verify.grids import GRIDS
from heesch_verify.shape import check_shape
from tools.polyforms import parse_kaplan_file

grid = GRIDS["H"]
source = parse_kaplan_file(Path("kaplan17.txt").read_text())
parents = {}
bank = {}
proposals = Counter()
for row, (cells, hc, hh) in enumerate(source,1):
    if hc != 3:
        continue
    assert len(set(cells)) == 17
    parent = canonical_digest(cells, grid, True)
    assert parent not in parents
    parents[parent] = {"row":row, "cells":cells, "hc":hc, "hh":hh, "interior_triples":0}
    for axis in range(3):
        # The row labels in frames 0,1,2 are y, x+y, x in source coordinates.
        frame = [grid.orientations[axis].apply(p) for p in cells]
        ys = [y for x,y in frame]
        for cut in range(min(ys)+1,max(ys)):
            cross = sorted(x for x,y in frame if y==cut)
            if len(cross)!=3 or cross[-1]-cross[0]!=2:
                continue
            parents[parent]["interior_triples"] += 1
            for dx in (-1,0):
                # Duplicate the cut row; move it AND the portion above as a rigid set.
                child = {(x,y) for x,y in frame if y<=cut}
                child.update((x+dx,y+1) for x,y in frame if y>=cut)
                assert len(child)==20
                shape = canonical_form(child, grid, True)
                check_shape(shape,grid)
                key = canonical_digest(shape,grid,True)
                bank.setdefault(key,{"cells":shape,"origins":[]})["origins"].append(
                    {"source_row":row, "rotation":axis,"cut_y":cut,"dx":dx})
                proposals[axis] += 1
Path("parents.json").write_text(json.dumps(parents,sort_keys=True))
Path("family.json").write_text(json.dumps(bank,sort_keys=True))
print(json.dumps({"source_records":len(source),"parents":len(parents),"parents_with_triples":sum(p["interior_triples"]>0 for p in parents.values()),"attempts_by_axis":proposals,"total_attempts":sum(proposals.values()),"unique":len(bank)},sort_keys=True))
