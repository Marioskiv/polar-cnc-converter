# Polar CNC — Polar Face geometry, checked without the GUI (FreeCADCmd; run by tests/freecad/run.sh).
#
# Five kinds of stock (round, square, square turned and off the centre, hexagon, plate off the
# centre) round a part with a boss. For each, at two depths, independently of the planner:
#  - nothing is left uncut (1 mm grid, cutter swept along every cutting move);
#  - the cutter never enters the part;
#  - no fast ("air") move passes over material that is still uncut at that moment (the moves are
#    replayed in order on a 0.4 mm grid);
#  - every arc is centred on the chuck axis (a pure turn of the chuck for the converter);
#  - the time is well below cutting full circles over the whole swept circle.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import sys
import traceback

import numpy as np

REPO = os.environ["PC_REPO"]
OUT = os.environ["PC_OUT"]
sys.path.insert(0, os.path.join(REPO, "freecad"))
os.makedirs(OUT, exist_ok=True)

import Part  # noqa: E402
from FreeCAD import Vector as V  # noqa: E402
from polarcnc import polarface as pf  # noqa: E402

log = open(os.path.join(OUT, "log.txt"), "w")
fails = []


def check(cond, what):
    log.write("%s %s\n" % ("ok  " if cond else "FAIL", what))
    log.flush()
    if not cond:
        fails.append(what)


D, R = 6.0, 3.0
STEP = 0.4 * D
F = 10.0                                    # mm/s, for the time comparison


def prism(w, h=20):
    return Part.Face(w).extrude(V(0, 0, h))


def poly(n, rc, rot=0, off=(0, 0)):
    pts = [V(off[0] + rc * math.cos(rot + 2 * math.pi * k / n),
             off[1] + rc * math.sin(rot + 2 * math.pi * k / n), 0) for k in range(n)]
    return Part.makePolygon(pts + [pts[0]])


STOCKS = {
    "round R30": Part.makeCylinder(30, 20),
    "square 50": prism(poly(4, 25 * math.sqrt(2), math.pi / 4)),
    "square 50 turned 30deg, off (3,2)": prism(poly(4, 25 * math.sqrt(2), math.pi / 4 + math.radians(30), (3, 2))),
    "hexagon 50 across flats": prism(poly(6, 25 / math.cos(math.pi / 6))),
    "plate 70x40 off (8,4)": Part.makeBox(70, 40, 20, V(-27, -16, 0)),
}
PART = Part.makeCylinder(15, 10).fuse(Part.makeCylinder(6, 15))


def samples(m, h=0.2):
    if m[0] in ("cut", "air"):
        _, r, a, b, cw = m
        sw = ((a - b) if cw else (b - a)) % (2 * math.pi)
        n = max(int(r * sw / h), 2)
        t = np.linspace(0, 1, n)
        ang = a - sw * t if cw else a + sw * t
        return np.c_[r * np.cos(ang), r * np.sin(ang)]
    p, q = m[1], m[2]
    n = max(int((q - p).Length / h), 2)
    t = np.linspace(0, 1, n)[:, None]
    return np.array([[p.x, p.y]]) * (1 - t) + np.array([[q.x, q.y]]) * t


def seconds(plan):
    t = 0.0
    for m in plan.moves:
        if m[0] in ("cut", "air"):
            sw = ((m[2] - m[3]) if m[4] else (m[3] - m[2])) % (2 * math.pi)
            t += m[1] * sw / (F if m[0] == "cut" else 3 * F)
        elif m[0] in ("line", "airline"):
            t += (m[2] - m[1]).Length / (F if m[0] == "line" else 3 * F)
        else:
            t += 3.0 / 50 * 2 + 3.0 / 3.3
    return t


def full_circles(sec):
    rmax = max(p.Length for e in sec.Edges for p in e.discretize(Deflection=0.01)) + R
    t, r = 0.0, rmax
    while r > R * 0.5:
        t += (2 * math.pi * r + STEP) / F
        r -= STEP
    return t


# a part of separate solids (two bosses, not joined): findShapeOutline sees only one of them
PART_SPLIT = Part.makeCompound([Part.makeCylinder(6, 15, V(12, 0, 0)), Part.makeCylinder(5, 15, V(-12, 6, 0))])


def one(name, st, z, part=PART):
    sec = pf.stock_section(st, z)
    keep = pf.part_keep(part, z)
    for solid in [s for s in part.Solids if s.BoundBox.ZMax > z]:   # every solid, not only the first
        c = solid.BoundBox.Center
        check(keep is not None and keep.isInside(V(c.x, c.y, 0), 1e-6, True),
              "%s, z=%g: part solid at (%.0f, %.0f) protected" % (name, z, c.x, c.y))
    plan = pf.plan_depth(sec, keep, R, STEP, 0.0, True)
    bb = sec.BoundBox
    xs = np.arange(bb.XMin - R, bb.XMax + R, 0.4)
    ys = np.arange(bb.YMin - R, bb.YMax + R, 0.4)
    pts = np.array([(x, y) for x in xs for y in ys])
    stock = np.array([sec.isInside(V(x, y, 0), 1e-6, True) for x, y in pts])
    part = np.array([keep is not None and keep.isInside(V(x, y, 0), 1e-6, True) for x, y in pts])
    edge_dist = np.array([keep.distToShape(Part.Vertex(V(x, y, 0)))[0] if (keep is not None and p) else 0
                          for (x, y), p in zip(pts, part)])
    cut = np.zeros(len(pts), bool)
    crossed = into_part = 0
    arcs_off_axis = 0
    for m in plan.moves:
        if m[0] == "lift":
            continue
        if m[0] in ("cut", "air") and abs(math.hypot(*pf._pt(m[1], m[2])[:2]) - m[1]) > 1e-9:
            arcs_off_axis += 1
        q = samples(m)
        d = np.sqrt(((pts[:, None, :] - q[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
        if m[0] in ("air", "airline"):
            ends = np.vstack([q[0], q[-1]])
            de = np.sqrt(((pts[:, None, :] - ends[None, :, :]) ** 2).sum(axis=2)).min(axis=1)
            crossed += int(((d < R - 0.05) & stock & ~part & ~cut & (de >= R)).sum())
        else:
            cut |= d <= R
            into_part += int(((d < R - 0.05) & part & (edge_dist > 0.05)).sum())
    left = stock & ~part & ~cut
    if keep is not None:      # a skin thinner than 0.05 mm on the part is the planner's tolerance
        for i in np.nonzero(left)[0]:
            if keep.distToShape(Part.Vertex(V(pts[i][0], pts[i][1], 0)))[0] < 0.05:
                left[i] = False
    uncut = float(left.sum()) * 0.16
    t, t0 = seconds(plan), full_circles(sec)
    lifts = sum(1 for m in plan.moves if m[0] == "lift")
    tag = "%s, z=%g" % (name, z)
    check(uncut <= 0.5, "%s: uncut %.2f mm2" % (tag, uncut))
    check(into_part == 0, "%s: cutter into the part at %d grid points" % (tag, into_part))
    check(crossed == 0, "%s: air moves over uncut material at %d grid points" % (tag, crossed))
    check(arcs_off_axis == 0, "%s: all arcs centred on the chuck axis" % tag)
    check(t < t0 * 0.95 or name.startswith("round"),
          "%s: %.0f s against %.0f s for full circles (%.0f %% saved), %d lift(s)"
          % (tag, t, t0, 100 * (1 - t / t0), lifts))


try:
    for name, st in STOCKS.items():
        for z in (17.0, 12.0):
            one(name, st, z)
    one("square 50, part of two separate bosses", STOCKS["square 50"], 12.0, PART_SPLIT)
except Exception:
    log.write(traceback.format_exc())
    fails.append("exception")
with open(os.path.join(OUT, "result.txt"), "w") as f:
    f.write("RESULT: %s\n" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
log.close()
