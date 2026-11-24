"""Render complete rings from a strict, verified hex-grid witness as an SVG."""

import argparse
from collections import Counter
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from heesch_verify.witness import VerifyConfig, verify_witness


COLORS = ["#e4a338", "#264865", "#389387", "#a8cea6", "#9cbadd"]
HEX = [(2, 0), (1, 1), (-1, 1), (-2, 0), (-1, -1), (1, -1)]


def element(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})


def vertices(cell):
    q, r = cell
    return [(3*q + x, 2*r + q + y) for x, y in HEX]


def draw(witness, destination):
    outcome = verify_witness(witness.read_text(), VerifyConfig(strict_claims=True))
    sub = outcome.submission
    depth = outcome.result.hc_verified
    if sub.grid_id != "H" or depth >= len(COLORS):
        raise ValueError(f"Expected a hex-grid witness through level four, got {sub.grid_id} level {depth}")
    patch = [(level, xf.apply_all(sub.cells)) for level, xf in sub.patches[0] if level <= depth]
    points = [p for _, cells in patch for cell in cells for p in vertices(cell)]
    left, right = min(x for x, y in points), max(x for x, y in points)
    top, bottom = min(y for x, y in points), max(y for x, y in points)
    width, height = 900, 720
    scale = min(820/(right-left), 575/((bottom-top)*math.sqrt(3)))
    def point(p):
        x = width/2 + (p[0] - (left+right)/2)*scale
        y = 330 + (p[1] - (top+bottom)/2)*scale*math.sqrt(3)
        return f"{x:.3f},{y:.3f}"

    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", viewBox=f"0 0 {width} {height}")
    element(svg, "title").text = f"{len(sub.cells)}-hex candidate with {depth} complete rings"
    element(svg, "desc").text = f"{len(patch)} copies. White outlines separate individual copies."
    element(svg, "rect", width=width, height=height, fill="#fbfaf6")
    for level, cells in patch:
        edges = Counter()
        faces = []
        for cell in sorted(cells):
            v = vertices(cell)
            faces.append("M" + " ".join(map(point, v)) + "Z")
            edges.update(tuple(sorted((a, b))) for a, b in zip(v, v[1:] + v[:1]))
        color = COLORS[level]
        element(svg, "path", d="".join(faces), fill=color, stroke=color, stroke_width=0.65)
        outline = "".join(f"M{point(a)}L{point(b)}" for (a, b), count in edges.items() if count == 1)
        element(svg, "path", d=outline, stroke="#fbfaf6", stroke_width=1.4, fill="none")
    counts = Counter(level for level, _ in patch)
    spacing = 146
    for index in range(depth+1):
        x = width/2 + (index-depth/2)*spacing - 52
        element(svg, "rect", x=x, y=660, width=17, height=17, rx=3, fill=COLORS[index])
        label = "Center" if index == 0 else f"Ring {index} · {counts[index]}"
        element(svg, "text", x=x+24, y=675, font_family="sans-serif", font_size=16, fill="#21303a").text = label
    ET.ElementTree(svg).write(destination, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()
    draw(args.witness, args.svg)
