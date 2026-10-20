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
    """Each part as (name, top Z, edges): the edges of its section half way up (all the chuck's
    parts stand straight up along Z), as two (n, 2) arrays of segment ends, holes included (a
    jaw ring is a ring, the body has its bore)."""
    import FreeCAD as App
    from . import chuck as chuckmod
    parts = chuckmod.keepout_parts(chuck)
    out = []
    for i, solid in enumerate(parts):
        for s in (solid.Solids or [solid]):
            bb = s.BoundBox
            a, b = [], []
            for w in s.slice(App.Vector(0, 0, 1), (bb.ZMin + bb.ZMax) / 2):
                pts = [(p.x, p.y) for p in w.discretize(Deflection=0.02)]
                a.extend(pts)
                b.extend(pts[1:] + pts[:1])
            if not a:
                continue
            name = "chuck body" if i == 0 else ("jaw / clamp %d" % i)
            out.append((name, bb.ZMax, (numpy.array(a), numpy.array(b))))
    return out


def _inside(edges, P):
    """Even-odd test of points P (n, 2) against closed loops given as their edges (a, b)."""
    a, b = edges
    x0, y0 = a[:, 0], a[:, 1]
    x1, y1 = b[:, 0], b[:, 1]
    px, py = P[:, 0][:, None], P[:, 1][:, None]
    cross = ((y0 <= py) & (py < y1)) | ((y1 <= py) & (py < y0))
    with numpy.errstate(divide="ignore", invalid="ignore"):
        xc = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
    return ((cross & (px < xc)).sum(axis=1) % 2) == 1


def _edge_dist(edges, P):
    """Distance of points P (n, 2) from the edges (a, b)."""
    a, b = edges
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
    return check_points(obs, P, I, R, radius)


def check_points(obs, P, I, R, radius):
    """check() for tip positions P (n, 3) with their command/line I and rapid flags R. Only the
    points near an obstacle (its box grown by the cutter radius and 5 mm) are measured, in chunks
    small enough for the memory."""
    best = None
    for name, top, edges in obs:
        lo = numpy.minimum(edges[0].min(axis=0), edges[1].min(axis=0)) - radius - 5
        hi = numpy.maximum(edges[0].max(axis=0), edges[1].max(axis=0)) + radius + 5
        near = (P[:, 2] < top + TOUCH) & (P[:, 0] >= lo[0]) & (P[:, 0] <= hi[0]) & \
            (P[:, 1] >= lo[1]) & (P[:, 1] <= hi[1])
        if not near.any():
            continue
        idx = numpy.nonzero(near)[0]
        Q = P[idx]
        step = max(int(2e6 // max(len(edges[0]), 1)), 1)
        for start in range(0, len(Q), step):
            chunk = Q[start:start + step]
            d = _edge_dist(edges, chunk[:, :2])
            d = numpy.where(_inside(edges, chunk[:, :2]), -d, d) - radius
            k = int(numpy.argmin(d))
            if best is None or d[k] < best["clearance"]:
                j = idx[start + k]
                best = {"clearance": float(d[k]), "obstacle": name, "at": tuple(P[j]),
                        "command": int(I[j]), "rapid": bool(R[j])}
    return best


def _radii(data, fallback):
    """The cutter radius at every point of a program read back: the diameter its tool comment
    gives (a program with several cutters checks each with its own), else `fallback`."""
    out = []
    for d in data.get("toolD") or []:
        try:
            out.append(float(d) / 2.0 if d else fallback)
        except (TypeError, ValueError):
            out.append(fallback)
    return out if len(out) == len(data["r"]) else [fallback] * len(data["r"])


def polar_hits(obs, data, radius, step=0.5):
    """Face mode, on the polar program as the machine runs it (data: bridge.parse): every block
    followed in joint space (X, C, Z linear, as LinuxCNC moves them), so a rapid that curves
    between two points is checked where it really goes. A sentence for a hit, else None."""
    r, c, z = data["r"], data["c"], data["z"]
    radii = _radii(data, radius)
    pts, lines, rapid, rads = [], [], [], []
    for i in range(1, len(r)):
        a0, a1 = math.radians(c[i - 1]), math.radians(c[i])
        L = math.hypot(r[i] - r[i - 1], z[i] - z[i - 1]) + abs(a1 - a0) * max(abs(r[i - 1]), abs(r[i]))
        n = max(int(L / step), 1)
        t = numpy.linspace(0.0, 1.0, n + 1)[1:]
        rr = r[i - 1] + (r[i] - r[i - 1]) * t
        aa = a0 + (a1 - a0) * t
        pts.append(numpy.c_[rr * numpy.cos(aa), rr * numpy.sin(aa), z[i - 1] + (z[i] - z[i - 1]) * t])
        lines.append(numpy.full(len(t), data["line"][i] or 0))
        rapid.append(numpy.full(len(t), bool(data["rapid"][i])))
        rads.append(numpy.full(len(t), radii[i]))
    if not pts:
        return None
    P, L, Rp, Rr = numpy.vstack(pts), numpy.concatenate(lines), numpy.concatenate(rapid), numpy.concatenate(rads)
    res = None
    for rad in numpy.unique(Rr):          # each cutter with its own radius
        sel = Rr == rad
        got = check_points(obs, P[sel], L[sel], Rp[sel], float(rad))
        if got is not None and (res is None or got["clearance"] < res["clearance"]):
            res = got
    if res is None or res["clearance"] >= -TOUCH:
        return None
    x, y, zz = res["at"]
    return ("%s runs into the %s at X %.2f C %.1f Z %.2f (line %d of the polar program, %.2f mm "
            "deep). Change the operation, the grip length or the jaw / clamp position."
            % ("A rapid move" if res["rapid"] else "The cut", res["obstacle"], math.hypot(x, y),
               math.degrees(math.atan2(y, x)) % 360, zz, res["command"], -res["clearance"]))


def wrap_hits(chuck, data, radius, step=0.5):
    """Wrap (router radial): the cutter is a cylinder from its tip OUTWARD along the radius. Its
    moves come from the polar program read back as the machine runs it (data: bridge.parse);
    everything is in the part's frame, where the chuck stands still. Returns a sentence for the
    first move that runs into the chuck body, a jaw or a clamp, else None."""
    import FreeCAD as App
    import Part
    from . import chuck as chuckmod
    parts = chuckmod.keepout_parts(chuck)
    if not parts:
        return None
    obs = Part.makeCompound(parts)
    bb = obs.BoundBox
    radii = _radii(data, radius)
    big = max(radii + [radius])
    zlo, zhi = bb.ZMin - big, bb.ZMax + big
    outer = max(abs(bb.XMin), abs(bb.XMax), abs(bb.YMin), abs(bb.YMax)) + big + 5
    r, c, z, rapid, line = data["r"], data["c"], data["z"], data["rapid"], data["line"]
    for i in range(1, len(r)):
        rad = radii[i]
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
            gap = tool.distToShape(obs)[0] - rad
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
