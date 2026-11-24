"""Reconcile complete native per-shape decisions and prepare the depth-two batch."""
import gzip
import json
from collections import Counter
from pathlib import Path
import sys


def records(paths):
    result = {}
    for path in paths:
        for line in path.read_text().splitlines():
            i,*counts=map(int,line.split())
            assert len(counts)==4 and i not in result
            result[i]=counts
    return result


def write_gzip(path, data):
    path.write_bytes(gzip.compress(data.encode(),mtime=0))


def main():
    family = Path(sys.argv[1])
    streams = sorted(Path('.').glob('results-*.tsv'))
    initial=records(streams)
    retry_paths=sorted(Path('.').glob('retry-*.tsv'))
    retried=records(retry_paths)
    capped={i for i,counts in initial.items() if 0 not in counts and -1 in counts}
    assert set(retried)==capped
    all_rows={**initial,**retried}
    lines,strict_two=[],[]
    with gzip.open(family,'rt') as f:
        for line in f:
            i=int(line.split()[0])
            counts=all_rows[i]
            if counts[1]>0 and counts[2]==0:
                strict_two.append(line)
            lines.append(' '.join(map(str,[i,*counts]))+'\n')
    assert len(lines)==len(initial)==len(all_rows)
    assert {int(line.split()[0]) for line in lines}==initial.keys()
    assert all(0 in counts or min(counts)>0 for counts in all_rows.values())
    complete=Counter(counts.index(0) if 0 in counts else 4 for counts in all_rows.values())
    write_gzip(Path('results.tsv.gz'),''.join(lines))
    write_gzip(Path('two-only.tsv.gz'),''.join(strict_two))
    Path('summary.json').write_text(json.dumps(dict(shapes=len(lines),retry_count=len(retried),
        initial_node_limit=100000,retry_node_limit=10000000,unresolved=0,
        nonempty_necessary_layers=complete),indent=2)+'\n')


if __name__=='__main__':main()
