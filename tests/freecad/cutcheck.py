# Polar CNC — the cut check's pieces, shared by the tests that follow a polar program against the
# solid part and the chuck (cut_check_test.py, wrap_relief_test.py).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import time

import FreeCAD as App

from common import check, log

V = App.Vector
SKIN = 0.02          # the cutter body is tested this far off its tip (a tip ON a floor is fine)
MAX_SAMPLES = 2500   # cutting points tested per program (evenly spread over all of it)


def moves(job):
    """Joint points of the polar program as the machine runs it, each block followed in joint
    space: [(r, c in rad, z, rapid)] every ~0.5 mm, plus the tool radius."""
    from polarcnc import bridge, program
    text, opts = program.polar(job)
    d = bridge.parse(text, opts)
    r, c, z, rapid = d["r"], d["c"], d["z"], d["rapid"]
    pts = []
    for i in range(1, len(r)):
        a0, a1 = math.radians(c[i - 1]), math.radians(c[i])
        L = math.hypot(r[i] - r[i - 1], z[i] - z[i - 1]) + abs(a1 - a0) * max(abs(r[i - 1]), abs(r[i]))
        n = max(int(L / 0.5), 1)
        for k in range(1, n + 1):
            t = k / n
            pts.append((r[i - 1] + (r[i] - r[i - 1]) * t, a0 + (a1 - a0) * t,
                        z[i - 1] + (z[i] - z[i - 1]) * t, bool(rapid[i])))
    tools = [x for x in d["toolD"] if x]
    return pts, (tools[0] / 2.0 if tools else 0.0)


def spread(pts, n=MAX_SAMPLES):
    if len(pts) <= n:
        return pts
    step = len(pts) / float(n)
    return [pts[int(k * step)] for k in range(n)]


def first_inside(solids, probes):
    """The first probe point inside one of the solids (only solids whose box the probes reach)."""
    lo = [min(p[i] for p in probes) for i in range(3)]
    hi = [max(p[i] for p in probes) for i in range(3)]
    for s in solids:
        bb = s.BoundBox
        if (hi[0] < bb.XMin or lo[0] > bb.XMax or hi[1] < bb.YMin or lo[1] > bb.YMax
                or hi[2] < bb.ZMin or lo[2] > bb.ZMax):
            continue
        for p in probes:
            if s.isInside(p, 1e-4, False):
                return p
    return None


def face_probes(x, y, z, R):
    """The flat end mill standing at its tip (x, y, z): a few points of its body, just above
    the tip and higher up, at the centre and near its rim."""
    out = []
    for h in (SKIN, 1.0, 6.0):
        out.append(V(x, y, z + h))
        for k in range(8):
            a = k * math.pi / 4
            for f in (0.5, 0.98):
                out.append(V(x + f * R * math.cos(a), y + f * R * math.sin(a), z + h))
    return out


def wrap_probes(r, a, z, R):
    """The router lying radially, tip at radius r: points of its body, from just outside the tip
    outward, across its width (round the bar and along it)."""
    d, t, k = V(math.cos(a), math.sin(a), 0), V(-math.sin(a), math.cos(a), 0), V(0, 0, 1)
    out = []
    for h in (SKIN, 1.0, 5.0):
        base = d * (r + h) + V(0, 0, z)
        out.append(base)
        for j in range(8):
            b = j * math.pi / 4
            for f in (0.5, 0.98):
                out.append(base + t * (f * R * math.cos(b)) + k * (f * R * math.sin(b)))
    return out


def gouges(label, pts, R, part, obstacles, wrap=False):
    """Every cutting sample (and every rapid) against the part and the chuck."""
    t = time.time()
    cut = [p for p in pts if not p[3]]
    rap = [p for p in pts if p[3]]
    hit_part = hit_chuck = None
    for r, a, z, _rapid in spread(cut):
        x, y = r * math.cos(a), r * math.sin(a)
        pr = wrap_probes(r, a, z, R) if wrap else face_probes(x, y, z, R)
        if hit_part is None:
            p = first_inside([part], pr)
            if p is not None:
                hit_part = (r, math.degrees(a), z, p)
        if hit_chuck is None and obstacles:
            p = first_inside(obstacles, pr)
            if p is not None:
                hit_chuck = (r, math.degrees(a), z, p)
        if hit_part and (hit_chuck or not obstacles):
            break
    hit_rapid = None
    for r, a, z, _rapid in spread(rap, 800):
        x, y = r * math.cos(a), r * math.sin(a)
        pr = wrap_probes(r, a, z, R) if wrap else face_probes(x, y, z, R)
        p = first_inside([part] + list(obstacles), pr)
        if p is not None:
            hit_rapid = (r, math.degrees(a), z)
            break
    check(hit_part is None, "%s: the cutter never goes into the part%s" % (label, "" if hit_part is None else
          " - IN at X %.3f C %.1f Z %.3f (point %s)" % hit_part))
    if obstacles:
        check(hit_chuck is None, "%s: the cutter never goes into the chuck%s" % (label, "" if hit_chuck is None
              else " - IN at X %.3f C %.1f Z %.3f" % hit_chuck[:3]))
    check(hit_rapid is None, "%s: no rapid through the part or the chuck%s" % (label, "" if hit_rapid is None
          else " - at X %.3f C %.1f Z %.3f" % hit_rapid))
    log.write("     (%d cutting, %d rapid points, %.1f s)\n" % (len(cut), len(rap), time.time() - t))


def keepout(held):
    if held is None:
        return []
    from polarcnc import chuck as chuckmod
    return [s for s in chuckmod.keepout_parts(held) if not s.isNull()]
