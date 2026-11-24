"""Run the official frozen proof gate on the private best candidate."""
from pathlib import Path
from heesch_verify.witness import verify_witness,VerifyConfig
from heesch_verify.proofgate import ProofCarryingGate
from heesch_verify.profile import detect
import json,os
repo=Path(os.environ.get('HEESCH_VERIFIER','/tmp/yukon-home/heesch'))
submission=Path('proof/best.heesch').resolve()
p=detect()
out=verify_witness(submission.read_text(),VerifyConfig(strict_claims=True))
verdict=ProofCarryingGate(submission.parent,repo/'tools/bin',profile=p).check(out.submission,out)
result={'profile':p.name,'geometry':out.result.to_json(),'proof_gate':verdict.to_json()}
Path('proof-gate.json').write_text(json.dumps(result,indent=2)+'\n')
print(result)
raise SystemExit(int(verdict.code is not None))

