"""Recover a periodic unit from part of a verified patch, checking exact coverage."""

from collections import defaultdict
import argparse
from itertools import combinations
import json
from pathlib import Path

from heesch_verify.witness import VerifyConfig, verify_witness


def lattices(patch, cells, max_copies):
    # Every index-n sublattice has one Hermite normal form.
    translations = defaultdict(set)
    for _, xf in patch:
        translations[xf.a, xf.b, xf.d, xf.e].add((xf.c, xf.f))
    deltas = {(x-u, y-v) for positions in translations.values()
              for (x, y), (u, v) in combinations(sorted(positions), 2)}
    all_periods = []
    for copies in range(1, max_copies+1):
        area = copies*len(cells)
        for c in range(1, area+1):
            if area % c:
                continue
            a = area//c
            for b in range(a):
                matches = sum(y % c == 0 and (x-b*(y//c)) % a == 0 for x, y in deltas)
                all_periods.append((-matches, copies, a, b, c))
    return sorted(all_periods)


def cover(rows, covered, limit):
    if len(covered) == len(rows):
        return []
    if not limit:
        return None
    choices = min(([p for p in poses if p.isdisjoint(covered)] for c, poses in rows.items()
                   if c not in covered), key=len)
    for pose in choices:
        rest = cover(rows, covered | pose, limit-1)
        if rest is not None:
            return [pose, *rest]
    return None


def find_unit(witness, max_copies):
    outcome = verify_witness(witness.read_text(), VerifyConfig(strict_claims=True))
    tile = outcome.submission.cells
    patch = outcome.submission.patches[0]
    central = next(xf for level, xf in patch if level == 0)
    for _, copies, a, b, c in lattices(patch, tile, max_copies):
        def footprint(xf):
            return frozenset(((x-b*(y//c)) % a, y % c) for x, y in xf.apply_all(tile))
        base = footprint(central)
        if len(base) != len(tile):
            continue
        placements = {}
        for _, xf in patch:
            mask = footprint(xf)
            if len(mask) == len(tile) and mask.isdisjoint(base):
                placements.setdefault(mask, xf)
        rows = {(x, y): [] for x in range(a) for y in range(c)}
        for mask in placements:
            for cell in mask:
                rows[cell].append(mask)
        match = cover(rows, base, copies-1)
        if match is not None:
            unit = [central, *(placements[p] for p in match)]
            assert len(unit) == copies and len(set().union(*map(footprint, unit))) == copies*len(tile)
            return {"shape_digest": outcome.result.canonical_digest, "period_vectors": [[a, 0], [b, c]],
                    "placements": [xf.as_text() for xf in unit], "cells_per_period": a*c}
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    parser.add_argument("--max-copies", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(find_unit(args.witness, args.max_copies), indent=2))
