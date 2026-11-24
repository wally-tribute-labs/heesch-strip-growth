"""Reconcile the full search by child geometry and a within-perimeter matched subset."""
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path

BASE=Path(__file__).resolve().parent


def rows(path):
    with gzip.open(path,'rt') as stream:
        yield from (line.split() for line in stream)


def jsonlines(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as stream:
        yield from map(json.loads,stream)


def main():
    dims={int(i):(d,float(r)) for i,d,r in rows(BASE/'family/dimensions.tsv.gz')}
    first={int(r[0]) for r in rows(BASE/'strict/rings.tsv.gz') if r[1]=='1'}
    units={r['id'] for r in jsonlines(BASE/'deep/periods.jsonl.gz') if r['unit']}
    deep={r['id']:r for r in jsonlines(BASE/'deep/strict.jsonl')}
    assert not units&deep.keys()
    two_receipt=json.loads((BASE/'screen/strict-two.json').read_text())
    assert two_receipt['complete']
    two=set(two_receipt['verified_ids'])|{i for i,r in deep.items() if r['strict_lower']>=2}
    three={i for i,r in deep.items() if r['strict_lower']>=3}
    assert three<=two and two<=first and not two&units
    tally=lambda ids:dict(shapes=len(ids),strict_first=len(ids&first),proven_periodic=len(ids&units),
                          finite_strict_two_or_more=len(ids&two),finite_strict_three=len(ids&three),finite_strict_four=0)
    classes=defaultdict(set)
    buckets=defaultdict(lambda:{'elongated':[],'compact':[]})
    st=((1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1))
    for line in rows(BASE/'family/shapes.tsv.gz'):
        i,*nums=map(int,line)
        cells=set(zip(nums[::2],nums[1::2]))
        perimeter=sum((x+dx,y+dy) not in cells for x,y in cells for dx,dy in st)
        kind='elongated' if dims[i][1]>=2 else 'compact'
        classes[kind].add(i)
        buckets[perimeter][kind].append(i)
    matched=defaultdict(set)
    pairs={}
    for per,groups in sorted(buckets.items()):
        n=min(map(len,groups.values()))
        pairs[per]=n
        for kind,ids in groups.items():
            matched[kind].update(sorted(ids, key=lambda i:dims[i][0])[:n])
    origins=defaultdict(set)
    for line in rows(BASE/'family/origins.tsv.gz'):
        i,r,*_=map(int,line); origins[i].add(r)
    parents=json.loads((BASE/'family/parents.json').read_text())
    by_parent=defaultdict(set)
    for i,source in origins.items():
        flags={parents[str(r)]['axis_ratio']>=2 for r in source}
        group='both' if len(flags)>1 else 'elongated_only' if True in flags else 'compact_only'
        by_parent[group].add(i)
    result=dict(all=tally(set(dims)),child_classes={k:tally(v) for k,v in classes.items()},
                matching='Within each exposed-edge count take the same number of children from each class, in ascending canonical SHA-256 order.',
                matched_pairs_by_perimeter=pairs,matched={k:tally(v) for k,v in matched.items()},
                disjoint_parent_groups={k:tally(v) for k,v in by_parent.items()},
                finalists=[dict(id=i,digest=dims[i][0],axis_ratio=dims[i][1],parents=sorted(origins[i])) for i in sorted(three)])
    assert len(dims)==59968 and len(units)==1948 and len(three)==4 and len(two)==59
    (BASE/'cohorts.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
