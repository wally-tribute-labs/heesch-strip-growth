"""Enumerate every edge-connected two-cell extension of each exact Hc=Hh=3 parent."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
from itertools import combinations
import json
from math import atan2, cos, hypot, sin, sqrt
from pathlib import Path
from statistics import mean

from heesch_verify.canonical import canonical_form
from heesch_verify.grids import GRIDS
from heesch_verify.result import VerifyError
from heesch_verify.shape import check_shape

G = GRIDS["H"]


def proportions(cells):
    # One nearest-neighbor distance is one unit. Elongation is the spread of tile centers.
    centers = [(sqrt(3)/2 * x, y + x/2) for x,y in cells]
    mx,my = map(mean, zip(*centers))
    a = sum((x-mx)**2 for x,y in centers)
    b = sum((x-mx)*(y-my) for x,y in centers)
    c = sum((y-my)**2 for x,y in centers)
    delta = hypot(a-c, 2*b)
    return sqrt((a+c+delta)/(a+c-delta))


def halo(cells):
    return set().union(*(G.edge_neighbors(c) for c in cells)) - cells


def added_pairs(cells):
    border = halo(cells)
    yield from combinations(sorted(border), 2)
    for a in sorted(border):
        for b in G.edge_neighbors(a):
            if b not in cells and b not in border:
                yield a,b


def zipped(path, text):
    path.write_bytes(gzip.compress(text.encode("ascii"), mtime=0))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kaplan", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    records = args.kaplan.read_text().splitlines()
    parents, bank, rejected = {}, defaultdict(list), Counter()
    for i in range(0, len(records), 2):
        if records[i+1].strip() != "Hc = 3 Hh = 3":
            continue
        number = i//2+1
        values = list(map(int, records[i].split()))
        cells = set(zip(values[::2], values[1::2]))
        assert len(cells)==17
        parents[number] = dict(axis_ratio=proportions(cells), cells=sorted(cells))
        for a,b in added_pairs(cells):
            candidate = canonical_form(cells | {a,b}, G, True)
            if candidate not in bank:
                try:
                    check_shape(candidate, G)
                except VerifyError as error:
                    rejected[error.code.value] += 1
                    continue
            bank[candidate].append((number, *a, *b))
    assert len(parents)==161 and sum(p["axis_ratio"]>=2 for p in parents.values())==109
    coords, origins, dimensions = [], [], []
    # Split solver shards by id, with a stable order uncorrelated with parent or elongation.
    def digest(shape):
        return hashlib.sha256(("H"+repr(shape)).encode("ascii")).hexdigest()
    for shape_id, (shape, ways) in enumerate(sorted(bank.items(), key=lambda pair: digest(pair[0]))):
        coords.append(" ".join(map(str,[shape_id,*(v for c in shape for v in c)])))
        dimensions.append(f"{shape_id}\t{digest(shape)}\t{proportions(shape):.10f}")
        for way in sorted(ways):
            origins.append(" ".join(map(str,[shape_id,*way])))
    out=args.output
    out.mkdir(exist_ok=True)
    for name, lines in [("shapes",coords),("origins",origins),("dimensions",dimensions)]:
        zipped(out/(name+".tsv.gz"), "\n".join(lines)+"\n")
    (out/"parents.json").write_text(json.dumps(parents,sort_keys=True,separators=(",",":"))+"\n")
    meta=dict(parents=len(parents),shapes=len(coords),growth_routes=len(origins),rejected_growth_routes=dict(rejected),
              kaplan_sha256=hashlib.sha256(args.kaplan.read_bytes()).hexdigest(), id_origin=0,
              elongated_cutoff=2, axis_measure="ratio of principal-axis standard deviations of hexagon centers")
    (out/"generation.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(meta,flush=True)


if __name__=="__main__":
    main()
