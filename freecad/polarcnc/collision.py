# Polar CNC — do the Job's operations hit the chuck? Every move of every operation (rapids
# too) is followed with the cutter as a cylinder (its tip and everything above it) against the
# jaws, the clamps and the chuck body. Everything turns together, so in the part's frame the
# chuck stands still and this is a plain 3-axis check.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math

import numpy

STEP = 0.5          # mm between samples along a move
TOUCH = 0.01        # mm: closer than this to an obstacle counts as a hit

RAPIDS = ("G0", "G00")
LINES = ("G1", "G01")
ARCS_CW = ("G2", "G02")
ARCS_CCW = ("G3", "G03")


_obs_cache = {}


def obstacles(chuck):
    """[(name, top Z, outline as an (n, 2) array)] of the chuck body, jaws and clamps (kept
    while the chuck's shape stays the same: asked for on every operation recompute)."""
    try:
        key = (chuck.Document.Name, chuck.Name, chuck.Shape.hashCode(), str(chuck.Shape.BoundBox),
               round(chuck.Shape.Volume, 6))
    except Exception:
        key = None
    if key is not None and key in _obs_cache:
        return _obs_cache[key]
    out = _obstacles(chuck)
    if key is not None:
        _obs_cache.clear()
        _obs_cache[key] = out
    return out


def _obstacles(chuck):
    import FreeCAD as App
    import TechDraw
    from . import chuck as chuckmod
    parts, _notes = chuckmod.build_parts(chuck)
    out = []
    for i, solid in enumerate(parts):
        for k, s in enumerate(solid.Solids or [solid]):
            outline = TechDraw.findShapeOutline(s, 1, App.Vector(0, 0, 1))
            pts = outline.discretize(Deflection=0.02)
            poly = numpy.array([(p.x, p.y) for p in pts])
            name = "chuck body" if i == 0 else ("jaw / clamp %d" % i)
            out.append((name, s.BoundBox.ZMax, poly))
    return out


def _inside(poly, P):
    """Even-odd test of points P (n, 2) against a closed polygon."""
    x0, y0 = poly[:, 0], poly[:, 1]
    x1, y1 = numpy.roll(x0, -1), numpy.roll(y0, -1)
    px, py = P[:, 0][:, None], P[:, 1][:, None]
    cross = ((y0 <= py) & (py < y1)) | ((y1 <= py) & (py < y0))
    with numpy.errstate(divide="ignore", invalid="ignore"):
        xc = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
    return ((cross & (px < xc)).sum(axis=1) % 2) == 1


def _edge_dist(poly, P):
    """Distance of points P (n, 2) from the outline of a polygon."""
    a = poly
    b = numpy.roll(poly, -1, axis=0)
    d = b - a
    L2 = numpy.maximum((d * d).sum(axis=1), 1e-12)
    rel = P[:, None, :] - a[None, :, :]
    t = numpy.clip((rel * d[None]).sum(axis=2) / L2, 0, 1)
    near = a[None] + t[..., None] * d[None]
    return numpy.sqrt(((P[:, None, :] - near) ** 2).sum(axis=2)).min(axis=1)


def samples(path):
    """The tool tip along a Path: (points (n, 3), index of the command, rapid?) per sample.
    Moves before X, Y and Z are all known are skipped (CAM starts with G0 Z only)."""
    pos = [None, None, None]
    out_p, out_i, out_r = [], [], []
    for idx, cmd in enumerate(path.Commands):
        name = cmd.Name.upper()
        if name not in RAPIDS + LINES + ARCS_CW + ARCS_CCW:
            continue
        prm = cmd.Parameters
        new = [prm.get("X", pos[0]), prm.get("Y", pos[1]), prm.get("Z", pos[2])]
        if None in pos or None in new:
            pos = new
            continue
        if name in ARCS_CW + ARCS_CCW:
            cx, cy = pos[0] + prm.get("I", 0.0), pos[1] + prm.get("J", 0.0)
            r = math.hypot(pos[0] - cx, pos[1] - cy)
            a0 = math.atan2(pos[1] - cy, pos[0] - cx)
            a1 = math.atan2(new[1] - cy, new[0] - cx)
            if name in ARCS_CW:
                sweep = -((a0 - a1) % (2 * math.pi)) or -2 * math.pi
            else:
                sweep = ((a1 - a0) % (2 * math.pi)) or 2 * math.pi
            n = max(int(abs(sweep) * r / STEP), 2)
            t = numpy.linspace(0, 1, n + 1)
            a = a0 + sweep * t
            pts = numpy.c_[cx + r * numpy.cos(a), cy + r * numpy.sin(a), pos[2] + (new[2] - pos[2]) * t]
        else:
            L = math.dist(pos, new)
            n = max(int(L / STEP), 1)
            t = numpy.linspace(0, 1, n + 1)[:, None]
            pts = numpy.array(pos)[None] + t * (numpy.array(new) - numpy.array(pos))[None]
        out_p.append(pts)
        out_i.append(numpy.full(len(pts), idx))
        out_r.append(numpy.full(len(pts), name in RAPIDS))
        pos = new
    if not out_p:
        return numpy.zeros((0, 3)), numpy.zeros(0, int), numpy.zeros(0, bool)
    return numpy.vstack(out_p), numpy.concatenate(out_i), numpy.concatenate(out_r)


def check(obs, path, radius):
    """The closest the cutter (radius, tip and everything above it) comes to the obstacles.
    Returns None (nothing reaches down to the cut) or a dict: clearance (negative = it cuts into
    an obstacle), obstacle name, tip position, command index, rapid."""
    P, I, R = samples(path)
    best = None
    for name, top, poly in obs:
        below = P[:, 2] < top - 1e-6           # only where the tip is lower than the obstacle top
        if not below.any():
            continue
        Q = P[below]
        for start in range(0, len(Q), 4000):
            chunk = Q[start:start + 4000]
            d = _edge_dist(poly, chunk[:, :2])
            d = numpy.where(_inside(poly, chunk[:, :2]), -d, d) - radius
            k = int(numpy.argmin(d))
            if best is None or d[k] < best["clearance"]:
                j = numpy.nonzero(below)[0][start + k]
                best = {"clearance": float(d[k]), "obstacle": name, "at": tuple(P[j]),
                        "command": int(I[j]), "rapid": bool(R[j])}
    return best


def wrap_hits(chuck, data, radius, step=0.5):
    """Wrap (router radial): the cutter is a cylinder from its tip OUTWARD along the radius. Its
    moves come from the polar program read back as the machine runs it (data: bridge.parse);
    everything is in the part's frame, where the chuck stands still. Returns a sentence for the
    first move that runs into the chuck body, a jaw or a clamp, else None."""
    import FreeCAD as App
    import Part
    from . import chuck as chuckmod
    parts, _notes = chuckmod.build_parts(chuck)
    if not parts:
        return None
    obs = Part.makeCompound(parts)
    bb = obs.BoundBox
    zlo, zhi = bb.ZMin - radius, bb.ZMax + radius
    outer = max(abs(bb.XMin), abs(bb.XMax), abs(bb.YMin), abs(bb.YMax)) + radius + 5
    r, c, z, rapid, line = data["r"], data["c"], data["z"], data["rapid"], data["line"]
    for i in range(1, len(r)):
        if not (min(z[i - 1], z[i]) <= zhi and max(z[i - 1], z[i]) >= zlo):
            continue
        a0, a1 = math.radians(c[i - 1]), math.radians(c[i])
        L = math.hypot(r[i] - r[i - 1], z[i] - z[i - 1]) + abs(a1 - a0) * max(r[i - 1], r[i])
        n = max(int(L / step), 1)
        for k in range(n + 1):
            t = k / n
            rr, aa, zz = r[i - 1] + (r[i] - r[i - 1]) * t, a0 + (a1 - a0) * t, z[i - 1] + (z[i] - z[i - 1]) * t
            if not zlo <= zz <= zhi or rr >= outer:
                continue
            d = App.Vector(math.cos(aa), math.sin(aa), 0)
            tool = Part.makeLine(d * rr + App.Vector(0, 0, zz), d * outer + App.Vector(0, 0, zz))
            gap = tool.distToShape(obs)[0] - radius
            if gap < -TOUCH:
                return ("%s runs into the chuck at X %.2f C %.1f Z %.2f (line %s of the program). "
                        "Change the operation, the grip length or the jaw position."
                        % ("A rapid move" if rapid[i] else "The cut", rr, math.degrees(aa) % 360,
                           zz, line[i]))
    return None


def tool_radius(op):
    tc = getattr(op, "ToolController", None)
    tool = getattr(tc, "Tool", None)
    d = getattr(tool, "Diameter", None)
    return (d.Value if hasattr(d, "Value") else float(d or 0)) / 2.0


def hit_message(op, obs):
    """A sentence if this operation runs into the chuck, else None."""
    path = getattr(op, "Path", None)
    if path is None or not obs:
        return None
    res = check(obs, path, tool_radius(op))
    if res is None or res["clearance"] >= -TOUCH:
        return None
    x, y, z = res["at"]
    return ("%s runs into the %s at X %.2f Y %.2f Z %.2f (command %d, %.2f mm deep). Change the "
            "operation, the grip length or the jaw / clamp position." %
            ("A rapid move" if res["rapid"] else "The cut", res["obstacle"], x, y, z,
             res["command"] + 1, -res["clearance"]))
