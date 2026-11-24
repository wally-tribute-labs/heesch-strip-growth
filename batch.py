"""Resume the serial audit; native timeouts first, optional CPU/memory cap in seconds/MiB."""
import argparse,json,os,resource,subprocess,sys
from collections import Counter
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--cpu',type=int,default=30)
parser.add_argument('--memory',type=int,default=850)
parser.add_argument('--retry',action='store_true')
args=parser.parse_args()
bank=json.loads(Path('family.json').read_text())
native={r['canonical_digest']:r for r in map(json.loads,Path('stage.jsonl').read_text().splitlines())}
assert len(native)==len(bank)
store=Path('cases');store.mkdir(exist_ok=True)
def limit():
    resource.setrlimit(resource.RLIMIT_AS,(args.memory*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(args.cpu,args.cpu+1))
def order(item):
    k,r=item
    return ('raw' in r,r['status'].startswith('I'),k)
tally=Counter()
for key,n in sorted(native.items(),key=order):
    out=store/(key+'.json')
    if out.exists():
        old=json.loads(out.read_text())
        if 'error' not in old or not args.retry:
            continue
    try:
        p=subprocess.run([sys.executable,'classify.py'],input=json.dumps({'key':key,'cells':bank[key]['cells'],'native':n}),
                         capture_output=True,text=True,preexec_fn=limit,timeout=args.cpu+30)
        result=json.loads(p.stdout) if not p.returncode else {'key':key,'error':p.returncode,'stderr':p.stderr[-3000:]}
    except subprocess.TimeoutExpired:
        result={'key':key,'error':'timeout'}
    temp=out.with_suffix('.tmp')
    temp.write_text(json.dumps(result))
    temp.replace(out)
    label=(result.get('hc'),result.get('hh'),result.get('error'),result.get('tiler_gate','').split(':')[0])
    tally[label]+=1
    if result.get('hc',0)>=2 or 'error' in result or sum(tally.values())%20==0:
        print(sum(tally.values()),key,label,dict(tally),flush=True)

