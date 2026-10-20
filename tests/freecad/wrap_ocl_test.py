# Polar CNC — Polar Wrap's radial drop-cutter against OpenCAMLib (FreeCADCmd; run by
# tests/freecad/run.sh).
#
# An independent check of the core of Polar Wrap: how far in the cutter's tip may go at every
# (z, angle) round the part. FreeCAD 26.3 ships its own rotary drop-cutter for its Rotary Surface
# operation (Path/Base/Generator/rotary_dropcutter.py: the part turned so each angle faces up, then
# OpenCAMLib's BatchDropCutter). The same relief as wrap_relief_test.py (rib, 1.2 mm groove, slot,
# dimple), the same cutters (flat Ø6, ball Ø2, ball Ø1), sampled at the same points by both:
#   - ours is never deeper than OpenCAMLib's (never a gouge), beyond 0.01 mm;
#   - and close to it: most points within a few hundredths, the rest within the half cell our map
#     keeps on the safe side next to walls.
# Skipped (with a note) where FreeCAD has no OpenCAMLib. Then checks taken from the rotary tests of
# FreeCAD, Kiri:Moto and LinuxCNC (ideas only, no code): the map of a part turned by a whole number
# of grid steps across the 0 degree seam is the same map turned; a cone matches its formula; what a
# cutter leaves is never below the part, and a smaller ball leaves no more than a bigger one; a map
# twice as fine gives the same tips (within a cell).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import sys
import time
import traceback

import numpy

REPO = os.environ["PC_REPO"]
OUT = os.environ["PC_OUT"]
sys.path.insert(0, os.path.join(REPO, "freecad"))
os.makedirs(OUT, exist_ok=True)

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402

from polarcnc import wrapcut  # noqa: E402

V = App.Vector
log = open(os.path.join(OUT, "log.txt"), "w", encoding="utf-8")
fails = []


def check(cond, what):
    log.write("%s %s\n" % ("ok  " if cond else "FAIL", what))
    log.flush()
    if not cond:
        fails.append(what)


def relief():
    bar = Part.makeCylinder(20, 60)
    bar = bar.fuse(Part.makeCylinder(21.5, 3, V(0, 0, 46)))
    bar = bar.cut(Part.makeCylinder(25, 1.2, V(0, 0, 40)).cut(Part.makeCylinder(18.8, 1.2, V(0, 0, 40))))
    bar = bar.cut(Part.makeBox(3, 2, 10, V(18.8, -1, 26)))
    bar = bar.cut(Part.makeSphere(3, V(-22, 0, 31)))
    return bar.removeSplitter()


def stl_of(shape, ocl):
    import MeshPart
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.002, AngularDeflection=0.05, Relative=False)
    stl = ocl.STLSurf()
    for f in mesh.Facets:
        p = f.Points
        stl.addTriangle(ocl.Triangle(ocl.Point(*p[0]), ocl.Point(*p[1]), ocl.Point(*p[2])))
    return stl


def run():
    try:
        try:
            import ocl
        except ImportError:
            import opencamlib as ocl
    except ImportError:
        log.write("OpenCAMLib is not in this FreeCAD: skipped\n")
        return
    from Path.Base.Generator import rotary_dropcutter
    shape = relief()
    step = 0.25
    zs = numpy.arange(0.0, 60.0 + 1e-9, step)
    na = int(math.ceil(2 * math.pi * 22 / step))
    t = time.time()
    H = wrapcut.radius_map([shape], [], zs, na, 22.0)
    log.write("     map %d x %d in %.1f s\n" % (len(zs), na, time.time() - t))
    stl = stl_of(shape, ocl)
    # where to compare: every 2nd row from 10 to 55 and every 3rd angle (the features are there)
    rows = numpy.nonzero((zs >= 10) & (zs <= 55))[0][::2]
    cols = numpy.arange(0, na, 3)
    thetas = 2 * math.pi * cols / na
    # the angle convention of rotary_dropcutter: found from the part (the slot is at C 0, the
    # dimple at C 180), the one of the four quarter turns and two directions that fits best
    pt = rotary_dropcutter.sample(stl, (0.0, 0.0, 1.0), list(zs[rows]), list(thetas))
    mine = H[numpy.ix_(rows, cols)]
    best = None
    for sgn in (1, -1):
        for k in range(4):
            th = sgn * thetas + k * math.pi / 2
            o = rotary_dropcutter.sample(stl, (0.0, 0.0, 1.0), list(zs[rows]), list(th))
            d = numpy.nanmedian(numpy.abs(mine - o))
            if best is None or d < best[0]:
                best = (d, sgn, k)
    _d, sgn, k = best
    log.write("     angle mapping: theta_ocl = %+d * theta + %d * 90 deg (median %.4f)\n" % (sgn, k, _d))
    th_ocl = list(sgn * thetas + k * math.pi / 2)
    del pt

    for name, dia, ball in (("flat Ø6", 6.0, False), ("ball Ø2", 2.0, True), ("ball Ø1", 1.0, True)):
        t = time.time()
        X = wrapcut.tip_map(H, zs, na, dia / 2, ball)
        cutter = ocl.BallCutter(dia, 50.0) if ball else ocl.CylCutter(dia, 50.0)
        o = rotary_dropcutter.sample(stl, (0.0, 0.0, 1.0), list(zs[rows]), th_ocl, cutter)
        ours = X[numpy.ix_(rows, cols)]
        ok = ~numpy.isnan(o)
        diff = ours[ok] - o[ok]
        log.write("     %s: %d points, %.1f s; ours - OpenCAMLib: min %.4f, median %.4f, 95%% %.4f, max %.4f\n"
                  % (name, ok.sum(), time.time() - t, diff.min(), numpy.median(diff),
                     numpy.percentile(diff, 95), diff.max()))
        deeper = diff < -0.01
        if deeper.any():
            i, j = numpy.argwhere(~numpy.isnan(o) & ((ours - numpy.nan_to_num(o)) < -0.01))[0]
            log.write("       deeper at Z %.2f C %.1f: ours %.4f, OpenCAMLib %.4f\n"
                      % (zs[rows[i]], math.degrees(thetas[j]), ours[i, j], o[i, j]))
        check(not deeper.any(), "%s: never deeper than OpenCAMLib (worst %.4f mm)" % (name, diff.min()))
        check(abs(numpy.median(diff)) < 0.02, "%s: the same as OpenCAMLib at most points (median %.4f mm)"
              % (name, numpy.median(diff)))
        check(numpy.percentile(diff, 95) < 0.25, "%s: 95 %% of points within %.3f mm (a half cell on the safe side next to walls)"
              % (name, numpy.percentile(diff, 95)))


def more():
    shape = relief()
    step = 0.25
    zs = numpy.arange(0.0, 60.0 + 1e-9, step)
    na = int(math.ceil(2 * math.pi * 22 / step))
    H = wrapcut.radius_map([shape], [], zs, na, 22.0)
    # turned by 17 grid steps (the slot at C 0 goes across the seam to C 360 - ...)
    k = 17
    turned = shape.copy()
    turned.rotate(V(0, 0, 0), V(0, 0, 1), math.degrees(2 * math.pi * k / na))
    Ht = wrapcut.radius_map([turned], [], zs, na, 22.0)
    d = numpy.abs(Ht - numpy.roll(H, k, axis=1))
    check(d.max() < 0.02, "the part turned by 17 grid steps across the 0 degree seam: the map turns with it "
          "(worst %.4f mm)" % d.max())
    # a cone: r = 10 - z / 4 over z 0..20
    cone = Part.makeCone(10, 5, 20)
    zc = numpy.arange(0.5, 19.5 + 1e-9, 0.25)
    nc = int(math.ceil(2 * math.pi * 10 / 0.25))
    Hc = wrapcut.radius_map([cone], [], zc, nc, 10.0)
    want = 10 - zc / 4
    err = Hc - want[:, None]
    check(err.min() > -1e-3 and err.max() < 0.07, "cone r = 10 - z/4: the map follows it, never inside "
          "(%.4f .. %.4f mm; a row takes the larger end of its cell)" % (err.min(), err.max()))
    # what a cutter leaves: never below the part; a smaller ball leaves no more than a bigger one
    gaps = {}
    for dia in (2.0, 1.0):
        X = wrapcut.tip_map(H, zs, na, dia / 2, True)
        gap, _c, _f = wrapcut.leftover(H, X, zs, na, dia / 2, True)
        gaps[dia] = gap
        check(gap[H > 0].min() > -1e-3, "ball Ø%.0f: what it leaves is never below the part (%.4f)"
              % (dia, gap[H > 0].min()))
    worse = gaps[1.0] - gaps[2.0]
    check(worse.max() < 0.01, "a Ø1 ball never leaves more than a Ø2 (worst %.4f mm)" % worse.max())
    # a map twice as fine: the same tips within a cell's worth
    zs2 = numpy.arange(20.0, 50.0 + 1e-9, step / 2)
    na2 = 2 * na
    H2 = wrapcut.radius_map([shape], [], zs2, na2, 22.0)
    X1 = wrapcut.tip_map(H, zs, na, 1.0, True)
    X2 = wrapcut.tip_map(H2, zs2, na2, 1.0, True)
    i1 = numpy.nonzero((zs >= 20) & (zs <= 50))[0]
    a = X1[i1]
    b = X2[::2][:len(i1), ::2]
    d = a - b
    check(numpy.median(numpy.abs(d)) < 0.01 and d.min() > -0.05,
          "ball Ø2, map 0.25 vs 0.125 mm: median %.4f, finer at most %.4f deeper" % (numpy.median(numpy.abs(d)), -d.min()))


try:
    run()
    more()
except Exception:
    fails.append("exception")
    log.write(traceback.format_exc())
with open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8") as f:
    f.write("RESULT: %s\n" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
log.close()
