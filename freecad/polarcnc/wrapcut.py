# Polar CNC — Wrap from the real 3D part: the router turned radial machines the outside of a
# part that turns on the chuck axis (Z through X0 Y0). Nothing is drawn flat by hand: the part
# (a solid or a mesh/STL) is read here, "unrolled" automatically into a map of its radius round
# the axis, and the cutter's path is made on that map.
#
#   radius_map   the part's outermost radius at every (z, angle) of a grid (slices along Z)
#   tip_map      how far in the cutter's tip may go at every (z, angle) without cutting into the
#                part (flat or ball end, radial): the radial drop-cutter
#   helix_passes roughing layers and a finishing pass as helices round the part: the chuck turns
#                continuously while Z advances one step per turn (no reversals, no lines)
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math

import numpy

TWO_PI = 2 * math.pi


def _section_points(obj_shape, mesh, z, ds):
    """Points of the part's outline in the plane at height z, as an (n, 2) array."""
    import FreeCAD as App
    pts = []
    if mesh is not None:
        for poly in mesh.crossSections([(App.Vector(0, 0, z), App.Vector(0, 0, 1))], 1e-3)[0]:
            pl = [(p.x, p.y) for p in poly]
            for (x0, y0), (x1, y1) in zip(pl, pl[1:]):          # densify the mesh polylines
                n = max(int(math.hypot(x1 - x0, y1 - y0) / ds), 1)
                for k in range(n):
                    t = k / n
                    pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            if pl:
                pts.append(pl[-1])
    if obj_shape is not None:
        for w in obj_shape.slice(App.Vector(0, 0, 1), z):
            pts.extend((p.x, p.y) for p in w.discretize(Distance=ds))
    return numpy.array(pts) if pts else numpy.zeros((0, 2))


def radius_map(shapes, meshes, zs, na, r_ref):
    """H[i, j]: the outermost radius of the part in the cell round height zs[i] and angle
    2 pi j / na (0 where the part is not). Conservative, so a cutter kept off this map never
    cuts into the part between the grid points: each row takes the larger of two slices half a
    step above and below it (a slice exactly on a flat face is ambiguous), and each angle step
    the largest radius of the points that fall in it. Every slice is sampled densely enough
    that every angle step at a third of r_ref gets points; steps left empty (the ray only
    grazes a wall) take their neighbours' value."""
    bin_w = TWO_PI / na
    ds = max(r_ref / 3.0 * bin_w * 0.5, 0.005)
    half = 0.49 * (zs[1] - zs[0]) if len(zs) > 1 else 0.0
    H = numpy.zeros((len(zs), na))
    for i, z in enumerate(zs):
        P = [_section_points(s, None, zz, ds) for s in shapes for zz in (z - half, z + half)] + \
            [_section_points(None, m, zz, ds) for m in meshes for zz in (z - half, z + half)]
        P = numpy.vstack([p for p in P if len(p)] or [numpy.zeros((0, 2))])
        if not len(P):
            continue
        rho = numpy.hypot(P[:, 0], P[:, 1])
        phi = numpy.mod(numpy.arctan2(P[:, 1], P[:, 0]), TWO_PI)
        b = numpy.minimum((phi / bin_w + 0.5).astype(int) % na, na - 1)
        row = numpy.zeros(na)
        numpy.maximum.at(row, b, rho)
        empty = row <= 0
        if empty.all():
            continue
        if empty.any():                      # fill gaps from the nearest filled angle each way
            idx = numpy.arange(na)
            good = idx[~empty]
            row[empty] = numpy.interp(idx[empty], numpy.r_[good - na, good, good + na],
                                      numpy.r_[row[good], row[good], row[good]])
        H[i] = row
    return H


def tip_map(H, zs, na, radius, ball=False, leave=0.0):
    """X[i, j]: the smallest radius the tool tip may have at (zs[i], angle j) without the cutter
    (radius `radius`, flat or ball end, pointing at the axis) touching the part grown by
    `leave`. The cutter's disk lies across the ray: a part point at radius rho, dTheta off the
    ray and dz along the axis is lateral rho sin(dTheta) away and rho cos(dTheta) out along it."""
    Hl = numpy.where(H > 0, H + leave, 0.0)
    dz_step = zs[1] - zs[0] if len(zs) > 1 else 1.0
    dth = TWO_PI / na
    rmax = max(float(Hl.max()), radius)
    rpos = Hl[Hl > 0]
    rmin = max(float(rpos.min()) if len(rpos) else rmax, radius)
    kz = int(math.ceil(radius / dz_step + 0.5))
    ka = int(math.ceil(math.asin(min(radius / rmin, 1.0)) / dth + 0.5)) if rmin > 0 else 0
    nz = len(zs)
    X = numpy.zeros_like(Hl)
    padded = numpy.zeros((nz + 2 * kz, na))
    padded[kz:kz + nz] = Hl
    for oz in range(-kz, kz + 1):
        # a row stands for the cell half a step round it: measure from its near edge
        dz = max(abs(oz) * dz_step - 0.5 * dz_step, 0.0)
        if dz > radius:
            continue
        rows = padded[kz + oz:kz + oz + nz]
        for oa in range(-ka, ka + 1):
            a = max(abs(oa) * dth - 0.5 * dth, 0.0)
            rho = numpy.roll(rows, -oa, axis=1)
            lat = rho * math.sin(a)
            reach = radius * radius - lat * lat - dz * dz
            inside = (rho > 0) & (reach >= 0)
            if not inside.any():
                continue
            out = rho * math.cos(a)
            if ball:
                need = out + numpy.sqrt(numpy.maximum(reach, 0)) - radius
            else:
                need = out
            X = numpy.where(inside & (need > X), need, X)
    return X


def sample(X, zs, na, z, theta):
    """X at (z, theta): the largest of the four grid points round it (theta wraps round), so
    the cutter between grid points is never lower than at any of them."""
    fz = (z - zs[0]) / (zs[1] - zs[0]) if len(zs) > 1 else 0.0
    fz = numpy.clip(fz, 0, len(zs) - 1)
    i0 = numpy.minimum(numpy.floor(fz).astype(int), len(zs) - 2) if len(zs) > 1 else numpy.zeros_like(fz, int)
    tz = fz - i0
    fa = numpy.mod(theta, TWO_PI) / (TWO_PI / na)
    j0 = numpy.floor(fa).astype(int) % na
    j1 = (j0 + 1) % na
    i1 = numpy.minimum(i0 + 1, len(zs) - 1)
    i1 = numpy.where(tz > 1e-9, i1, i0)
    return numpy.maximum(numpy.maximum(X[i0, j0], X[i0, j1]), numpy.maximum(X[i1, j0], X[i1, j1]))


def helix(z_from, z_to, pitch, ds, r_ref, theta0=0.0, ccw=True):
    """(z, theta) of a helix from z_from to z_to, `pitch` mm along Z per turn, a point every
    ds mm of arc at r_ref. theta is unwound (it keeps growing)."""
    turns = abs(z_to - z_from) / pitch
    n = max(int(math.ceil(turns * TWO_PI * r_ref / ds)), 2)
    t = numpy.linspace(0.0, 1.0, n + 1)
    z = z_from + (z_to - z_from) * t
    th = theta0 + (1 if ccw else -1) * turns * TWO_PI * t
    # one more full turn at the end, so the last line round the part is cut all the way
    extra = int(math.ceil(TWO_PI * r_ref / ds))
    th_e = th[-1] + (1 if ccw else -1) * TWO_PI * numpy.arange(1, extra + 1) / extra
    return numpy.r_[z, numpy.full(extra, z[-1])], numpy.r_[th, th_e]


def helix_passes(X_rough, X_finish, zs, na, r_stock, z_from, z_to, pitch_rough, pitch_finish,
                 step_down, ds, roughing=True, finishing=True, ccw=True):
    """The passes, each a list of (z, theta, r) of the tool tip (theta unwound): roughing layers
    from the stock radius down by step_down (each layer rides up over the part where it is
    higher: r = max(layer, X_rough)); layers that cut nothing are left out; then the finishing
    helix on X_finish."""
    passes = []
    theta = 0.0
    if roughing:
        level = None                       # what the previous layer left: starts at the stock
        layer = r_stock
        floor = float(X_rough.min())
        while layer > floor + 1e-6:
            layer = max(layer - step_down, floor)
            z, th = helix(z_from, z_to, pitch_rough, ds, r_stock, theta, ccw)
            r = numpy.maximum(sample(X_rough, zs, na, z, th), layer)
            before = numpy.full_like(r, r_stock) if level is None else \
                numpy.maximum(sample(X_rough, zs, na, z, th), level)
            if (r < before - 1e-3).any():
                passes.append(numpy.c_[z, th, r])
                theta = th[-1]
            level = layer
    if finishing:
        z, th = helix(z_from, z_to, pitch_finish, ds, r_stock, theta, ccw)
        passes.append(numpy.c_[z, th, sample(X_finish, zs, na, z, th)])
    return passes
