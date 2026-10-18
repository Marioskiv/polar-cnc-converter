# Polar CNC — Polar Wrap geometry without the GUI (FreeCADCmd; run by tests/freecad/run.sh).
#
# A bar R20 x 60 with a groove round it (R17, 7 wide) and a flat (at 16 from the axis), as a solid
# and as a mesh (what an STL gives). Checks: the part's radius map is the same from both; the
# cutter's tip map reaches the groove floor and the flat and stays on the bar elsewhere (flat and
# ball end); a ball never cuts into the part (checked against the solid, not against the map);
# the roughing layers come down from the stock by the step down and the finishing helix lies on
# the part.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import sys
import traceback

OUT = os.environ["PC_OUT"]
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(os.environ["PC_REPO"], "freecad"))
log = open(os.path.join(OUT, "log.txt"), "w")
fails = []


def check(cond, what):
    log.write("%s %s\n" % ("ok  " if cond else "FAIL", what))
    log.flush()
    if not cond:
        fails.append(what)


try:
    import numpy
    import FreeCAD as App
    import Part
    import Mesh
    import MeshPart
    from polarcnc import wrapcut as wc

    part = Part.makeCylinder(20, 60)
    part = part.cut(Part.makeCylinder(30, 7, App.Vector(0, 0, 30)).cut(Part.makeCylinder(17, 7, App.Vector(0, 0, 30))))
    part = part.cut(Part.makeBox(10, 40, 10, App.Vector(16, -20, 42)))
    mesh = MeshPart.meshFromShape(Shape=part, LinearDeflection=0.01, AngularDeflection=0.05)
    step = 0.25
    zs = numpy.arange(0, 60 + 1e-9, step)
    na = int(math.ceil(2 * math.pi * 22 / step))
    H = wc.radius_map([part], [], zs, na, 22)
    Hm = wc.radius_map([], [mesh], zs, na, 22)
    iz = lambda z: int(round(z / step))
    diff = numpy.abs(H - Hm).max()
    check(diff < 0.03, "solid and mesh (STL) give the same radius map: worst %.4f mm" % diff)
    # a solid is mapped through a fine mesh: never below the real radius, at most TOL above
    TOL = 2.5e-3
    check(0 <= H[iz(10)].min() - 20 < TOL and 0 <= H[iz(33.5)].max() - 17 < TOL,
          "radius map: bar 20, groove floor 17 (%.4f, %.4f: never below, at most %.4f above)"
          % (H[iz(10)].min(), H[iz(33.5)].max(), TOL))
    flat = H[iz(47), 0]
    check(abs(flat - 16) < 0.01, "radius map: the flat at 16 (%.4f)" % flat)

    for ball in (False, True):
        X = wc.tip_map(H, zs, na, 2.5, ball)
        kind = "ball" if ball else "flat"
        check(0 <= X[iz(10)].min() - 20 < TOL and 0 <= X[iz(10)].max() - 20 < TOL,
              "%s end: rides on the bar at 20" % kind)
        check(abs(X[iz(33.5)].min() - 17) < 0.01, "%s end: reaches the groove floor (%.3f)" % (kind, X[iz(33.5)].min()))
        check(X[iz(47), 0] < 16.1, "%s end: reaches the flat (%.3f)" % (kind, X[iz(47), 0]))
        # never into the part: points of the cutter's end (disk or ball) must not be inside the solid
        bad, n = 0, 0
        for z in numpy.arange(26, 52, 0.75):
            for a in numpy.linspace(0, 2 * math.pi, 37)[:-1]:
                r = float(wc.sample(X, zs, na, numpy.array([z]), numpy.array([a]))[0])
                d = App.Vector(math.cos(a), math.sin(a), 0)
                t = App.Vector(-math.sin(a), math.cos(a), 0)
                for u in numpy.linspace(-2.49, 2.49, 9):
                    for v in numpy.linspace(-2.49, 2.49, 9):
                        if u * u + v * v > 2.49 * 2.49:
                            continue
                        lift = (2.5 - math.sqrt(2.5 * 2.5 - u * u - v * v)) if ball else 0.0
                        p = d * (r + lift + 0.005) + t * u + App.Vector(0, 0, z + v)
                        n += 1
                        if part.isInside(p, 1e-6, False):
                            bad += 1
                            if bad <= 5:
                                log.write("   inside: z %.2f a %.1f r %.3f u %.2f v %.2f depth %.4f\n"
                                          % (z, math.degrees(a), r, u, v, part.distToShape(Part.Vertex(p))[0]))
        check(bad == 0, "%s end: no cutter point inside the part (%d points tested)" % (kind, n))

    Xr = wc.tip_map(H, zs, na, 2.5, False, 0.3)
    Xf = wc.tip_map(H, zs, na, 2.5, False, 0.0)
    passes = wc.helix_passes(Xr, Xf, zs, na, 22.0, 58.0, 12.0, 2.5, 0.75, 1.0, 0.5, radius=2.5)
    layers = sorted(set(round(float(p[:, 2].min()), 6) for p in passes[:-1]), reverse=True)
    check(len(passes) >= 5, "%d passes: roughing layers and one finishing" % len(passes))
    # below the bar (layers under R20) only the groove and the flat are cut: short pieces
    deep = [p for p in passes[:-1] if p[:, 2].min() < 19.9]
    span = max((p[:, 0].max() - p[:, 0].min()) for p in deep) if deep else 0
    check(deep and span < 25, "layers under the bar cut only where the groove and the flat are "
          "(longest piece %.1f mm along the part, not 46)" % span)
    air = sum(int((p[:, 3] == 0).sum()) for p in passes[:-1])
    check(air > 0, "roughing marks %d samples as air (faster feed)" % air)
    check(all(any(abs(v - L) < 1e-6 for v in layers) for L in (21.0, 20.0, 19.0, 18.0))
          and min(layers) >= float(Xr.min()) - 1e-6,
          "roughing layers 1 mm apart from the stock R22, never below the part: %s"
          % ["%.2f" % v for v in layers])
    fin = passes[-1]
    on_bar = fin[(fin[:, 0] > 13) & (fin[:, 0] < 27)]
    check(len(on_bar) and ((on_bar[:, 2] - 20) >= 0).all() and (on_bar[:, 2] - 20).max() < 2.5e-3,
          "finishing helix on the bar at 20 (+0..2.5 microns)")
    check(abs(fin[:, 0].max() - 58) < 1e-9 and abs(fin[:, 0].min() - 12) < 1e-9,
          "from the free end (58) toward the chuck (12)")
    check(abs(abs(fin[:, 1].max() - fin[:, 1].min()) - 2 * math.pi * (1 + 46 / 0.75 + 1)) < 0.05,
          "the finishing helix has a full turn at each end")
    lp = wc.helix_passes(Xr, Xf, zs, na, 22.0, 58.0, 12.0, 2.5, 0.75, 1.0, 0.5, roughing=False,
                         radius=2.5, finish_lines=True)[0]
    on_flat = lp[(lp[:, 0] > 44) & (lp[:, 0] < 50) & (numpy.abs(numpy.mod(lp[:, 1] + math.pi, 2 * math.pi) - math.pi) < 0.02)]
    check(len(on_flat) and on_flat[:, 2].min() < 16.1, "lines along the part reach the flat (%.3f)"
          % (on_flat[:, 2].min() if len(on_flat) else -1))
    turned = lp[:, 1].max() - lp[:, 1].min()
    check(abs(turned - 2 * math.pi) < 1e-6 and set(numpy.round(lp[:, 0], 6)) >= {58.0, 12.0},
          "lines along the part, all the way round (%.3f rad) and from end to end" % turned)
except Exception:
    log.write(traceback.format_exc())
    fails.append("exception")
with open(os.path.join(OUT, "result.txt"), "w") as f:
    f.write("RESULT: %s\n" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
log.close()
