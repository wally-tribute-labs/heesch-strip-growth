"""Positive geometry from coordinates alone; reconstruct and audit the periodic counterexample."""
import hashlib
import json
import re
import resource
from pathlib import Path

from audit import GRID, LocalPacking, VerifyConfig, verify_witness
from exact import find_patch
from heesch_verify.canonical import canonical_digest, canonical_form
from heesch_verify.gates import IsohedralGate
from period_from_patch import find_unit
from refine import local_support
from tools.polyforms import parse_kaplan_file

def geometry(witness):
    return verify_witness(witness, VerifyConfig(strict_claims=True)).result

def check_period(tile, unit):
    assert canonical_digest(tile, GRID, True) == unit["shape_digest"]
    (a, zero), (b, c) = unit["period_vectors"]
    assert zero == 0 and a > 0 and c > 0 and 0 <= b < a
    used = set()
    legal = {(s.a, s.b, s.d, s.e) for s in GRID.orientations}
    for pose in unit["placements"]:
        m, n, u, p, q, v = map(int, re.fullmatch(r"<(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+)>", pose).groups())
        assert (m,n,p,q) in legal
        footprint = set()
        for x,y in tile:
            i,j = m*x+n*y+u, p*x+q*y+v
            footprint.add(((i-b*(j//c))%a, j%c))
        assert len(footprint) == len(tile) and footprint.isdisjoint(used)
        used.update(footprint)
    assert used == {(x,y) for x in range(a) for y in range(c)}
    assert len(used) == unit["cells_per_period"]

def main():
    # Deliberate per-control pilot allowances; these are not mathematical cutoffs.
    resource.setrlimit(resource.RLIMIT_AS,(950*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(150,)*2)
    source = Path("kaplan17.txt").read_bytes()
    assert hashlib.sha256(source).hexdigest() == "77e40d2966a1603b536944e6767d84dbdae9d53677965b1c525da638492a535d"
    [(row, cells)] = [(i,s) for i,(s,hc,hh) in enumerate(parse_kaplan_file(source.decode()),1) if (hc,hh)==(4,4)]
    cells = canonical_form(cells,GRID,True)
    pack = LocalPacking(cells)
    support = local_support(pack,5)
    sizes = [len(s) for s in support[1:]]
    print("finite control supported contacts:",sizes,flush=True)
    witness, stats = find_patch(pack,4,support,True)
    assert witness
    geo = geometry(witness)
    assert (geo.hc_verified,geo.hh_verified)==(4,4)
    assert geo.canonical_digest == canonical_digest(cells,GRID,True)
    Path("control-four.heesch").write_text(witness)
    finite = {"source_row":row,"shape_id":geo.canonical_digest,"size":len(cells),
        "verified_hc":4,"verified_hh":4,"necessary_contacts":sizes,"search":stats,
        "finite_basis":"Kaplan published Hc=Hh=4","local_exclusion_at":5 if len(sizes)==5 and sizes[-1]==0 else None}
    periodic_path = Path("six-copy-periodic.heesch")
    patch = verify_witness(periodic_path.read_text(),VerifyConfig(strict_claims=True))
    assert (patch.result.hc_verified,patch.result.hh_verified)==(4,4)
    unit = find_unit(periodic_path,6)
    assert unit and len(unit["placements"]) == 6
    check_period(patch.submission.cells,unit)
    original = json.loads(Path("six-copy-unit.json").read_text())
    check_period(patch.submission.cells,original)
    data={"finite":finite,"periodic":{"shape_id":patch.result.canonical_digest,"size":len(patch.submission.cells),"verified_hc":4,"verified_hh":4,"recovered_unit":unit,"frozen_tiler_gate":IsohedralGate(GRID).evaluate(patch.submission.cells).detail}}
    Path("controls.json").write_text(json.dumps(data, indent=2)+"\n")
    print(json.dumps(data),flush=True)

if __name__ == "__main__":
    main()
