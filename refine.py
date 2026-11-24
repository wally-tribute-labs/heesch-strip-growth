"""Necessary local conditions for complete geometric rings, allowing all holes."""
from collections import defaultdict
from audit import LocalPacking

def supported(solver, poses):
    if not solver.solve():
        return []
    possible=set(v for v in solver.get_model() if 1<=v<=len(poses))
    for i in range(1,len(poses)+1):
        if i not in possible and solver.solve(assumptions=[i]):
            possible.update(v for v in solver.get_model() if 1<=v<=len(poses))
    return [poses[i-1] for i in sorted(possible)]

def refine(problem, prior):
    # A d-ring central patch gives every first neighbor a hole-agnostic
    # (d-1)-ring local surround. Thus ALL of its contacts with the central
    # tile and other selected first neighbors must be supported by R_(d-1).
    problem.lift(prior)
    poses=[q for q in prior if problem.central in problem.near(q)]
    allowed={p:set(problem.near(p)) for p in poses}
    with problem.one(poses) as solver:
        for i,p in enumerate(poses):
            rim=problem.ring(p)
            for j in range(i+1,len(poses)):
                q=poses[j]
                if (q not in allowed[p] or p not in allowed[q]) and not rim.isdisjoint(problem.cells(q)):
                    solver.add_clause([-i-1,-j-1])
        return supported(solver,poses)

def local_support(problem,depth):
    sets=[[],problem.base()]
    for d in range(2,depth+1):
        if not sets[-1]:
            break
        sets.append(refine(problem,sets[-1]))
    return sets

