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
    step = zs[1] - zs[0] if len(zs) > 1 else 1.0
    # one slice at every cell edge (a hair off the round value, which may be a flat face), each
    # shared by the two rows it bounds
    edges = [z - 0.5 * step + 1e-4 for z in zs] + [zs[-1] + 0.5 * step - 1e-4]
    # solids are cut as a fine mesh, all slices in one call: one exact slice of a solid per
    # height took 0.1 s (480 of them on a 120 mm part). A mesh lies inside the curved faces it
    # follows by at most MESH_DEFLECTION, which is added below, so the map stays on the safe side.
    pad = 0.0
    if shapes:
        meshes = list(meshes) + [_mesh_of(s) for s in shapes]
        pad = MESH_DEFLECTION
    cuts = [[] for _ in edges]
    for m in meshes:
        for k, pts in enumerate(_mesh_sections(m, edges, ds)):
            if len(pts):
                cuts[k].append(pts)
    cuts = [numpy.vstack(c) if c else numpy.zeros((0, 2)) for c in cuts]
    H = numpy.zeros((len(zs), na))
    for i, z in enumerate(zs):
        P = [cuts[i], cuts[i + 1]]
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
        if pad:
            # the facets of a mesh leave a few microns of ripple round a round part: what is
            # within that of the row's largest radius takes that radius (the safe side), so the
            # round parts of a row are one smooth helix and not thousands of tiny steps
            on = row > 0
            top = float(row.max())
            row[on & (row >= top - 2 * pad)] = top      # raising a radius is always safe
            row[on] += pad
        H[i] = row
    return H


MESH_DEFLECTION = 0.002     # mm: how far the mesh of a solid may lie inside its curved faces


def _mesh_of(shape):
    import MeshPart
    return MeshPart.meshFromShape(Shape=shape, LinearDeflection=MESH_DEFLECTION,
                                  AngularDeflection=0.05, Relative=False)


def _mesh_sections(mesh, zs, ds):
    """The outline points of a mesh at every height in zs (one call for all), each slice
    densified to ds, as a list of (n, 2) arrays."""
    import FreeCAD as App
    out = []
    planes = [(App.Vector(0, 0, z), App.Vector(0, 0, 1)) for z in zs]
    for polys in mesh.crossSections(planes, 1e-3):
        pts = []
        for poly in polys:
            pl = numpy.array([(p.x, p.y) for p in poly])
            if len(pl) < 2:
                pts.extend(pl.tolist())
                continue
            a, b = pl[:-1], pl[1:]
            n = numpy.maximum((numpy.hypot(*(b - a).T) / ds).astype(int), 1)
            t = numpy.concatenate([numpy.arange(k) / k for k in n])
            seg = numpy.repeat(numpy.arange(len(n)), n)
            pts.extend((a[seg] + (b[seg] - a[seg]) * t[:, None]).tolist())
            pts.append(pl[-1].tolist())
        out.append(numpy.array(pts) if pts else numpy.zeros((0, 2)))
    return out


def tip_map(H, zs, na, radius, ball=False, leave=0.0, tick=None, edge=-0.5):
    """X[i, j]: the smallest radius the tool tip may have at (zs[i], angle j) without the cutter
    (radius `radius`, flat or ball end, pointing at the axis) touching the part grown by
    `leave`. The cutter's disk lies across the ray: a part point at radius rho, dTheta off the
    ray and dz along the axis is lateral rho sin(dTheta) away and rho cos(dTheta) out along it.
    Distances to a neighbouring cell are measured to its near edge (edge -0.5: the safe side,
    for the path); edge 0 measures to its centre (for the tool report: what really fits)."""
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
        if tick is not None:
            tick()
        # a row stands for the cell half a step round it: measure from its near edge
        dz = max(abs(oz) * dz_step + (edge * dz_step if oz else 0.0), 0.0)
        if dz > radius:
            continue
        rows = padded[kz + oz:kz + oz + nz]
        for oa in range(-ka, ka + 1):
            a = max(abs(oa) * dth + (edge * dth if oa else 0.0), 0.0)
            rho = numpy.roll(rows, -oa, axis=1)
            lat = rho * math.sin(a)
            reach = radius * radius - lat * lat - dz * dz
            # a wall exactly a radius away only touches the cutter's side: on the safe side
            # (edge < 0) it still counts, measured centre to centre (the report) it does not
            inside = (rho > 0) & ((reach >= 0) if edge < 0 else (reach > 1e-9))
            if not inside.any():
                continue
            out = rho * math.cos(a)
            if ball:
                need = out + numpy.sqrt(numpy.maximum(reach, 0)) - radius
            else:
                need = out
            X = numpy.where(inside & (need > X), need, X)
    return X


def envelope(X, zs, na, radius, ball=False, tick=None, edge=0.5):
    """E[i, j]: the radius of the surface the cutter leaves at (zs[i], angle j) when its tip has
    been at X everywhere (the inverse of tip_map: what is left of the stock after the cutter,
    smallest wins). The cutter at a tip q covers the points p within its radius round the ray of
    q; at p it reaches in to its flat end (X / cos dTheta, the end is a disk across the ray) or
    to its ball. Distances are measured to the far edge of a cell, so E is on the high side:
    never less material than is really left (safe for what comes after, and for "what is left")."""
    dz_step = zs[1] - zs[0] if len(zs) > 1 else 1.0
    dth = TWO_PI / na
    nz = len(zs)
    big = float(X.max()) + 10 * radius + 1.0
    E = numpy.full_like(X, big)
    pos = X[X > 0]
    rmin = max(float(pos.min()) if len(pos) else radius, radius)
    kz = int(math.ceil(radius / dz_step + 0.5))
    ka = int(math.ceil(math.asin(min(radius / rmin, 1.0)) / dth + 0.5))
    padded = numpy.full((nz + 2 * kz, na), big)
    padded[kz:kz + nz] = X
    for oz in range(-kz, kz + 1):
        if tick is not None:
            tick()
        dz = abs(oz) * dz_step + (edge * dz_step if oz else 0.0)
        if dz > radius:
            continue
        rows = padded[kz + oz:kz + oz + nz]
        for oa in range(-ka, ka + 1):
            a = abs(oa) * dth + (edge * dth if oa else 0.0)
            if a >= math.pi / 2:
                continue
            x = numpy.roll(rows, -oa, axis=1)          # the tip q, oa steps round from p
            if ball:
                c = x + radius                            # the ball's centre, on q's ray
                disc = radius * radius - dz * dz - (c * math.sin(a)) ** 2
                ok = disc >= 0
                rho = c * math.cos(a) - numpy.sqrt(numpy.maximum(disc, 0))
            else:
                lat = x * math.tan(a)
                ok = lat * lat + dz * dz <= radius * radius
                rho = x / math.cos(a)
            E = numpy.where(ok & (rho < E), rho, E)
    return E


def leftover(H, X, zs, na, radius, ball=False, leave=0.0, rows=None, tick=None, edge=0.5):
    """What the cutter (tips X) leaves on the part beyond `leave`: (gap map, worst corner, worst
    floor), each worst as (mm, row, angle index). The corner one is the most it leaves anywhere
    (a ball always rounds an inside corner with its own radius); the floor one is the most it
    leaves at the bottom of a hollow it cannot get down into (a groove narrower than the ball):
    every hollow's floor is a connected stretch of cells lower than their neighbours, and it
    counts as reached where the cutter gets down at any of its cells."""
    E = envelope(X, zs, na, radius, ball, tick, edge)
    gap = numpy.where(H > 0, E - (H + leave), 0.0)
    if rows is not None:
        gap[~rows] = 0.0
    k = int(numpy.argmax(gap))
    corner = (float(gap.flat[k]),) + divmod(k, gap.shape[1])
    floor = _floors(H, gap, rows)
    return gap, corner, floor


def _floors(H, gap, rows):
    """The worst hollow floor: (mm left at its best-reached cell, row, angle index)."""
    nz, na = H.shape
    on = H > 0
    lower = on.copy()
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = numpy.roll(numpy.roll(H, di, axis=0), dj, axis=1)
        if di == 1:
            nb[0] = numpy.inf
        elif di == -1:
            nb[-1] = numpy.inf
        lower &= H <= nb + 1e-6
    if rows is not None:
        lower &= rows[:, None]
    seen = numpy.zeros_like(lower)
    worst = (0.0, 0, 0)
    for i0, j0 in zip(*numpy.nonzero(lower)):
        if seen[i0, j0]:
            continue
        best = None
        stack = [(i0, j0)]
        seen[i0, j0] = True
        while stack:
            i, j = stack.pop()
            if best is None or gap[i, j] < best[0]:
                best = (float(gap[i, j]), i, j)
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = i + di, (j + dj) % na
                if 0 <= a < nz and lower[a, b] and not seen[a, b] and abs(H[a, b] - H[i, j]) < 0.3:
                    seen[a, b] = True
                    stack.append((a, b))
        if best[0] > worst[0]:
            worst = best
    return worst


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
    ds mm of arc at r_ref. theta is unwound (it keeps growing). A full turn at each end (as
    Fusion's Rotary Spiral does), so the ends are cut all the way round, not left as a ramp."""
    sign = 1 if ccw else -1
    per_turn = int(math.ceil(TWO_PI * r_ref / ds))
    ring = sign * TWO_PI * numpy.arange(0, per_turn) / per_turn
    turns = abs(z_to - z_from) / pitch
    n = max(int(math.ceil(turns * TWO_PI * r_ref / ds)), 2)
    t = numpy.linspace(0.0, 1.0, n + 1)
    z = z_from + (z_to - z_from) * t
    th = theta0 + sign * TWO_PI + sign * turns * TWO_PI * t
    th_e = th[-1] + sign * TWO_PI * numpy.arange(1, per_turn + 1) / per_turn
    return (numpy.r_[numpy.full(per_turn, z_from), z, numpy.full(per_turn, z[-1])],
            numpy.r_[theta0 + ring, th, th_e])


def lines(z_from, z_to, step_angle, ds, theta0=0.0, ccw=True):
    """(z, theta) of lines along the part (zigzag), one every step_angle round it, linked at
    the ends by a short move round the part: for steps, grooves and flats along the axis,
    which a helix crosses at a slant (Fusion and SprutCAM offer it for that)."""
    sign = 1 if ccw else -1
    n_lines = max(int(math.ceil(TWO_PI / step_angle)), 3)
    da = TWO_PI / n_lines
    nz = max(int(math.ceil(abs(z_to - z_from) / ds)), 2)
    zl = numpy.linspace(z_from, z_to, nz + 1)
    zs_, ths = [], []
    for k in range(n_lines + 1):                    # the last line closes on the first
        a = theta0 + sign * da * k
        zz = zl if k % 2 == 0 else zl[::-1]
        zs_.append(zz)
        ths.append(numpy.full(len(zz), a))
    return numpy.concatenate(zs_), numpy.concatenate(ths)


def _pieces(cut, per_turn, keep):
    """Index ranges [a, b) of a pass worth cutting: the samples that cut, joined where they are
    less than a turn apart, each with `keep` samples before and after."""
    idx = numpy.nonzero(cut)[0]
    if not len(idx):
        return []
    out = []
    a = prev = idx[0]
    for k in idx[1:]:
        if k - prev > per_turn:
            out.append((max(a - keep, 0), min(prev + keep + 1, len(cut))))
            a = k
        prev = k
    out.append((max(a - keep, 0), min(prev + keep + 1, len(cut))))
    return out


def helix_passes(X_rough, X_finish, zs, na, r_stock, z_from, z_to, pitch_rough, pitch_finish,
                 step_down, ds, roughing=True, finishing=True, ccw=True, radius=0.0,
                 finish_lines=False, start=None):
    """The passes, each an array of (z, theta, r, cutting) of the tool tip (theta unwound).
    Roughing: layers from the stock radius down by step_down, each riding up over the part
    where it is higher (r = max(layer, X_rough)); a layer is cut only along the stretches of its
    helix where it removes material (pieces less than a turn apart are joined), and inside them
    every sample is marked cutting or not (air: faster feed) with a cutter's width of margin.
    The layers turn the chuck one way and back the other, so C does not pile up hundreds of
    turns over the program (LinuxCNC's C soft limits). Then the finishing pass on X_finish, all
    of it cutting, the way `ccw` says. start: the material there is to begin with (a map of its
    radius, e.g. what an earlier operation with another cutter left); None = the whole bar."""
    passes = []
    theta = 0.0
    per_turn = max(int(math.ceil(TWO_PI * r_stock / ds)), 1)
    margin = max(int(math.ceil((2 * radius + 1.0) / ds)), 2)
    if roughing:
        top = r_stock if start is None else min(r_stock, float(start.max()))
        level = top                        # what the previous layer left (the stock at first)
        n_layer = 0
        layer = top
        floor = float(X_rough.min())
        while layer > floor + 1e-6:
            layer = max(layer - step_down, floor)
            z, th = helix(z_from, z_to, pitch_rough, ds, r_stock, theta, ccw if n_layer % 2 == 0 else not ccw)
            part = sample(X_rough, zs, na, z, th)
            r = numpy.maximum(part, layer)
            there = numpy.maximum(part, level)           # the material on top before this layer
            if start is not None:
                there = numpy.minimum(there, sample(start, zs, na, z, th))
            cut = r < there - 1e-3
            if cut.any():
                # a cutter's width either side of every cutting sample counts as cutting
                near = numpy.convolve(cut.astype(float), numpy.ones(2 * margin + 1), "same") > 0
                for a, b in _pieces(cut, per_turn, margin):
                    passes.append(numpy.c_[z[a:b], th[a:b], r[a:b], near[a:b]])
                theta = th[-1]
                n_layer += 1
            level = layer
    if finishing:
        if finish_lines:      # the step round the part at the largest radius it is cut at
            r_top = max(float(X_finish.max()), radius, 1.0)
            z, th = lines(z_from, z_to, pitch_finish / r_top, ds, theta, ccw)
            # the link at each end goes round the part: sample it, it may ride over the part
            zz, tt = [z[0]], [th[0]]
            for k in range(1, len(z)):
                if abs(th[k] - th[k - 1]) > 1e-12:
                    m = max(int(math.ceil(abs(th[k] - th[k - 1]) * r_top / ds)), 1)
                    for j in range(1, m):
                        zz.append(z[k])
                        tt.append(th[k - 1] + (th[k] - th[k - 1]) * j / m)
                zz.append(z[k])
                tt.append(th[k])
            z, th = numpy.array(zz), numpy.array(tt)
        else:
            z, th = helix(z_from, z_to, pitch_finish, ds, r_stock, theta, ccw)
        passes.append(numpy.c_[z, th, sample(X_finish, zs, na, z, th), numpy.ones(len(z))])
    return passes
