"""Reconstruct rings from a two-copy periodic tiling of a hex-grid candidate."""

import argparse
import json
from pathlib import Path

from heesch_verify.grids import GRIDS
from heesch_verify.transform import Xform
from heesch_verify.witness import VerifyConfig, verify_witness


def construct(cells, lattice, rings):
    """Find the second tile in one repeat unit, then expand by tile adjacency."""
    grid = GRIDS["H"]
    a, b, c = lattice   # lattice vectors (a, 0) and (b, c)
    if a <= 0 or c <= 0 or a*c != 2*len(cells):
        raise ValueError(f"Lattice {lattice} must have area {2 * len(cells)}")

    def residue(cell):
        x, y = cell
        k, y = divmod(y, c)
        return (x-k*b) % a, y

    central = Xform(1, 0, 0, 0, 1, 0)
    base = {residue(cell): (central, cell) for cell in cells}
    if len(base) != len(cells):
        raise ValueError("Central tile overlaps a translate of itself")
    for sym in grid.orientations:
        for tx in range(a):
            for ty in range(c):
                xf = Xform(sym.a, sym.b, tx, sym.d, sym.e, ty)
                second = {residue(cell): (xf, cell) for cell in xf.apply_all(cells)}
                if len(second) == len(cells) and base.keys().isdisjoint(second):
                    owners = base | second
                    return expand(cells, owners, residue, central, rings, grid), xf
    raise ValueError(f"No second tile completes lattice {lattice}")


def expand(cells, owners, residue, central, rings, grid):
    levels = {central: 0}
    front = {central}
    for level in range(1, rings+1):
        new = set()
        for xf in front:
            for x in xf.apply_all(cells):
                for y in grid.edge_neighbors(x):
                    proto, ref = owners[residue(y)]
                    other = Xform(proto.a, proto.b, proto.c+y[0]-ref[0],
                                  proto.d, proto.e, proto.f+y[1]-ref[1])
                    if other not in levels:
                        new.add(other)
        levels.update(dict.fromkeys(new, level))
        front = new
    return levels


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("digest")
    parser.add_argument("lattice", type=int, nargs=3)
    parser.add_argument("rings", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cells = frozenset(map(tuple, json.loads(args.bank.read_text())[args.digest]["cells"]))
    levels, second = construct(cells, args.lattice, args.rings)
    lines = ["H " + " ".join(f"{x} {y}" for x, y in sorted(cells)),
             f"~ {args.rings} {args.rings} 1", str(len(levels))]
    lines.extend(f"{level} {xf.as_text()}" for xf, level in
                 sorted(levels.items(), key=lambda item: (item[1], item[0].as_text())))
    witness = "\n".join(lines) + "\n"
    checked = verify_witness(witness, VerifyConfig(strict_claims=True)).result
    if checked.hc_verified != args.rings or checked.canonical_digest != args.digest:
        raise ValueError(f"Unexpected verification result: {checked}")
    args.output.write_text(witness)
    print(f"Second placement {second.as_text()}, {len(levels)} copies, {checked.hc_verified} verified rings")
