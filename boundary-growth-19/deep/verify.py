"""Recheck saved lattice units, all deep witnesses and coverage of every eligible depth-four ID."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from audit import GRID, VerifyConfig, verify_witness
from controls import check_period
from heesch_verify.canonical import canonical_digest


def read_dataset(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path,"rt") as stream:
        return [list(map(int,l.split())) for l in stream]


def verify(family, screen, archive):
    shapes = {r[0]:list(zip(r[1::2],r[2::2])) for r in read_dataset(family)}
    stages = {r[0]:next((i for i,j in enumerate(r[1:]) if j==0),4) for r in read_dataset(screen)}
    assert shapes.keys() == stages.keys()
    with gzip.open(archive/"periods.jsonl.gz","rt") as stream:
        periods = [json.loads(l) for l in stream]
    assert len(periods) == len({r["id"] for r in periods})
    assert {r["id"] for r in periods} == {i for i,s in stages.items() if s==4}
    units = Counter()
    nonperiodic_queries = set()
    for r in periods:
        tile = shapes[r["id"]]
        assert canonical_digest(tile,GRID,True) == r["digest"]
        if r["unit"]:
            check_period(tile,r["unit"])
            units[len(r["unit"]["placements"])] += 1
        else:
            nonperiodic_queries.add(r["id"])
    searched = list(map(json.loads,(archive/"strict.jsonl").read_text().splitlines()))
    assert len(searched) == len({r["id"] for r in searched})
    assert {r["id"] for r in searched} == nonperiodic_queries | {i for i,s in stages.items() if s==3}
    finite = Counter()
    for r in searched:
        key=r["id"]
        tile = shapes[key]
        assert canonical_digest(tile,GRID,True) == r["digest"]
        assert r["kind"]=="finite" and r["strict_lower"] == r["strict_upper"] < 4
        depth=r["strict_lower"]
        assert any(q["depth"]==depth and (q["dfs"] is True or q.get("exact_sat") is True) for q in r["queries"])
        assert stages[key] == depth or any(q["depth"]==depth+1 and (
            q["dfs"] is False or q.get("exact_sat") is False) for q in r["queries"])
        if depth>=2:
            v=verify_witness((archive/r["witness"]).read_text(),VerifyConfig(strict_claims=True)).result
            assert (v.canonical_digest,v.hc_verified)==(r["digest"],depth)
        finite[depth]+=1
    top={r["id"] for r in searched if r["strict_lower"]==3}
    outer=list(map(json.loads,(archive/"outer.jsonl").read_text().splitlines()))
    assert {r["id"] for r in outer} == {i for i in top if stages[i]==4}
    for r in outer:
        assert r["digest"]==canonical_digest(shapes[r["id"]],GRID,True)
        if r["hh4"]:
            outcome=verify_witness((archive/r["witness"]).read_text(),VerifyConfig(strict_claims=True)).result
            assert (outcome.canonical_digest,outcome.hc_verified,outcome.hh_verified)==(r["digest"],3,4)
    return dict(shapes=len(shapes),tested_for_tiling=len(periods),checked_tilers=sum(units.values()),
                tiling_unit_sizes=dict(sorted(units.items())),without_unit_through_eight=sorted(nonperiodic_queries),
                strict_geometry_cases=len(searched),finite_strict_depths_in_deep_search=dict(sorted(finite.items())),
                finite_three=sorted(top),finite_four_or_more=0,finite_three_with_hh_four=[r["id"] for r in outer if r["hh4"]])


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("family",type=Path)
    p.add_argument("screen",type=Path)
    p.add_argument("archive",type=Path)
    a=p.parse_args()
    print(json.dumps(verify(a.family,a.screen,a.archive),indent=2))
