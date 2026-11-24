"""Serial bounded runs of Kaplan's upstream reference search. All outputs retained."""
import argparse
import json
import resource
import subprocess
from pathlib import Path
from collections import Counter
from heesch_verify.grids import GRIDS
from heesch_verify.canonical import canonical_digest

def run_case(row, opts):
    def limit():
        # Research resource allowances, not mathematical cutoffs.
        resource.setrlimit(resource.RLIMIT_AS,(640 * 1024**2,)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(opts.cpu,)*2)
    cmd = ["./sat-hex",opts.mode,"-show","-hh","-maxlevel",str(opts.depth)]
    if not opts.no_iso:
        cmd.append("-isohedral")
    source = "H? " + " ".join(str(v) for xy in row["cells"] for v in xy) + "\n"
    try:
        p = subprocess.run(cmd,input=source,capture_output=True,text=True,
                           preexec_fn=limit,timeout=opts.cpu+4)
    except subprocess.TimeoutExpired:
        return {"status":"timeout"}
    if p.returncode:
        return {"status":"process_failure","exit":p.returncode,"error":p.stderr[-1000:]}
    lines=p.stdout.splitlines()
    if len(lines)<2:
        return {"status":"missing_record","error":p.stderr[-1000:]}
    coords=list(map(int,lines[0].split()[1:]))
    cells=list(zip(coords[::2],coords[1::2]))
    assert canonical_digest(cells,GRIDS["H"],True)==canonical_digest(row["cells"],GRIDS["H"],True)
    return {"status":lines[1],"raw":p.stdout,"stderr":p.stderr}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bank")
    ap.add_argument("output")
    ap.add_argument("--mode",choices=["-old","-new"],default="-new")
    ap.add_argument("--cpu",type=int,default=2)
    ap.add_argument("--depth",type=int,default=2)
    ap.add_argument("--limit",type=int,default=None)
    ap.add_argument("--no-iso",action="store_true")
    opts=ap.parse_args()
    bank=json.loads(Path(opts.bank).read_text())
    tally=Counter()
    with open(opts.output,"w") as out:
        for i,(key,row) in enumerate(sorted(bank.items())[:opts.limit]):
            result=run_case(row,opts); result["canonical_digest"]=key
            tally[result["status"]]+=1
            out.write(json.dumps(result)+"\n"); out.flush()
            if (i+1)%30==0:
                print(i+1,dict(tally),flush=True)
    print("Final",dict(tally))
if __name__=="__main__":
    main()
