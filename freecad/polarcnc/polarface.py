# Polar CNC — "Polar Face": facing that cuts only where the stock really is.
#
# The stock in the chuck may be round, square, a hexagon, off-centre or any shape. At every depth
# the area to clear is the stock section at that depth minus the part (everything of the part at
# or above that depth). It is cut with circles round the chuck axis, outside in, each clipped to
# that area: on a polar machine such a circle is a pure turn of the chuck at constant X — the
# smoothest move it has — and the converter turns it into C moves with no error. Where a circle
# leaves the stock (the corners of a square) the cutter crosses the air at the same depth by
# turning the chuck faster, but only where nothing that is still uncut is in the way; otherwise
# it lifts. A straight move at depth is never used to link: a chord runs inside the circle,
# where material may be. The last pass runs straight in to the centre (X only), where the chuck
# could never turn fast enough to keep the feed on a tiny circle.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math

import numpy

import FreeCAD as App
import Part
import Path
import Path.Op.Base as PathOp
import PathScripts.PathUtils as PathUtils

EPS = 0.01          # mm: the cutter just touching the stock edge counts as outside it
MIN_ARC = 0.05      # mm: shorter arcs are not worth cutting
GRID = 0.25         # mm: the grid the uncut material is followed on
MIN_AIR = 2.0       # mm: a free stretch shorter than this is not worth speeding up for
EDGE_REACH = 0.0    # how far the cutter centre goes past the stock edge, in cutter radii
                    # (0: to the edge — the shortest path that still leaves nothing; measured)


# ---- geometry (plain Part shapes in the XY plane; z is added when the moves are made) ----------
def stock_section(stock_shape, z):
    """The stock's cross-section at height z as a face (holes kept), or None."""
    wires = stock_shape.slice(App.Vector(0, 0, 1), z)
    if not wires:
        return None
    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    return _flat(face)


def part_keep(part_shape, z):
    """Everything of the part at or above z, seen from above (the area the cutter must not enter
    at depth z), or None if the part has nothing there."""
    import TechDraw
    if part_shape is None or part_shape.isNull():
        return None
    bb = part_shape.BoundBox
    if bb.ZMax <= z + 1e-6:
        return None
    above = part_shape.common(Part.makeBox(bb.XLength + 2, bb.YLength + 2, bb.ZMax - z + 1,
                                           App.Vector(bb.XMin - 1, bb.YMin - 1, z)))
    if not above.Solids:
        return None
    # one outline per solid: findShapeOutline gives the outline of only one of several separate
    # solids (three jaws -> one jaw)
    out = None
    for solid in above.Solids:
        outline = TechDraw.findShapeOutline(solid, 1, App.Vector(0, 0, 1))
        face = _flat(Part.makeFace(outline, "Part::FaceMakerBullseye"))
        out = face if out is None else out.fuse(face)
    return out.removeSplitter()


def chuck_keep(parts, z):
    """The chuck parts (body, jaws or jaw rings, clamps: all straight up along Z) at or above z,
    seen from above, holes kept (a jaw ring is a ring, not a disc), or None."""
    out = None
    for p in parts:
        bb = p.BoundBox
        if bb.ZMax <= z + 1e-6:
            continue
        zs = (max(bb.ZMin, z) + bb.ZMax) / 2
        wires = p.slice(App.Vector(0, 0, 1), zs)
        if not wires:
            continue
        face = _flat(Part.makeFace(wires, "Part::FaceMakerBullseye"))
        out = face if out is None else out.fuse(face)
    return out.removeSplitter() if out is not None else None


def grow(shape, d):
    """Offset every face of a (possibly multi-face) flat shape by d and join them: makeOffset2D
    on a compound of separate faces (the part and the jaws, say) offsets only the first."""
    faces = shape.Faces
    if not faces:
        return shape
    out = None
    for f in faces:
        # a face that came out of a boolean upside down (normal -Z) is offset the wrong way by
        # makeOffset2D (grown -> shrunk): the direction is checked by the area
        if abs(d) <= 1e-12:
            g = f
        elif len(f.Wires) > 1:
            g = _offset_by_wires(f, d)       # outline out, holes in, each checked
        else:
            g = _offset_signed(f, d)
        out = g if out is None else out.fuse(g)
    return out.removeSplitter() if out is not None else shape


def _offset_signed(face, d):
    """A face without holes offset by d (d > 0 grows it), whichever way its normal points:
    makeOffset2D follows the orientation, so the direction is checked by the area."""
    g = face.makeOffset2D(d, join=0)
    if (d > 0 and g.Area < face.Area) or (d < 0 and g.Area > face.Area):
        g = face.makeOffset2D(-d, join=0)
    return g


def _offset_by_wires(face, d):
    """face offset by d (d > 0 grows it): the outline grown, every hole shrunk (and a hole that
    closes up dropped). Each wire as its own face, the direction checked by the area."""
    loops = sorted((Part.Face(w) for w in face.Wires), key=lambda f: -f.Area)
    out = _offset_signed(loops[0], d)
    for hole in loops[1:]:
        if d > 0 and min(hole.BoundBox.XLength, hole.BoundBox.YLength) <= 2 * d:
            continue
        try:
            out = out.cut(_offset_signed(hole, -d))
        except Exception:
            pass
    return out


def _flat(shape):
    """Move a planar XY shape to z = 0."""
    s = shape.copy()
    s.translate(App.Vector(0, 0, -s.BoundBox.ZMin))
    return s


def _angle(p):
    return math.atan2(p.y, p.x)


def _arc_interval(edge):
    """(start angle, sweep) of an arc round the origin, counter-clockwise, sweep in (0, 2pi]."""
    if edge.isClosed():
        a = _angle(edge.valueAt(edge.FirstParameter))
        return a, 2 * math.pi
    p0, p1 = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
    pm = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
    a0, a1, am = _angle(p0), _angle(p1), _angle(pm)
    sweep = (a1 - a0) % (2 * math.pi)
    if (am - a0) % (2 * math.pi) > sweep:      # the edge runs clockwise: swap its ends
        a0, sweep = a1, (a0 - a1) % (2 * math.pi)
    return a0, sweep


def _pt(r, a):
    return App.Vector(r * math.cos(a), r * math.sin(a), 0)


class Raster:
    """What is still uncut at one depth, on a grid: the stock to remove and the part (never to
    be touched). Updated with every cutting move, so an air move is checked against what is
    really left at that moment — at the corners of a square some stock outside the current
    circle is cut only by later, smaller circles."""

    def __init__(self, stock_face, keep_face, radius, grid=GRID):
        self.r, self.g = radius, grid
        bb = stock_face.BoundBox
        m = radius + grid
        self.xs = numpy.arange(bb.XMin - m, bb.XMax + m + grid, grid)
        self.ys = numpy.arange(bb.YMin - m, bb.YMax + m + grid, grid)
        gx, gy = numpy.meshgrid(self.xs, self.ys)
        self.P = numpy.c_[gx.ravel(), gy.ravel()]
        stock = self._fill(stock_face)
        self.part = self._fill(keep_face) if keep_face is not None else numpy.zeros(len(self.P), bool)
        self.uncut = stock & ~self.part

    def _fill(self, face):
        """Grid points inside a face (even-odd scanlines over its outline)."""
        segs = []
        for w in face.Wires:
            pts = w.discretize(Deflection=self.g * 0.1)
            segs.extend(((a.x, a.y, b.x, b.y) for a, b in zip(pts, pts[1:] + pts[:1])))
        s = numpy.array(segs)
        inside = numpy.zeros((len(self.ys), len(self.xs)), bool)
        x0, y0, x1, y1 = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
        for j, y in enumerate(self.ys):
            cross = ((y0 <= y) & (y < y1)) | ((y1 <= y) & (y < y0))
            if not cross.any():
                continue
            xc = numpy.sort(x0[cross] + (y - y0[cross]) * (x1[cross] - x0[cross]) /
                            (y1[cross] - y0[cross]))
            for a, b in zip(xc[0::2], xc[1::2]):
                inside[j] |= (self.xs >= a) & (self.xs <= b)
        return inside.ravel()

    def dist(self, mv):
        """Distance of every grid point from the path of a move."""
        P = self.P
        if mv[0] in ("cut", "air"):
            _, r, a, b, cw = mv
            sweep = ((a - b) if cw else (b - a)) % (2 * math.pi)
            lo = b if cw else a                       # the arc runs counter-clockwise from lo
            ang = (numpy.arctan2(P[:, 1], P[:, 0]) - lo) % (2 * math.pi)
            on = ang <= sweep
            d = numpy.abs(numpy.hypot(P[:, 0], P[:, 1]) - r)
            p0, p1 = _pt(r, a), _pt(r, b)
            de = numpy.minimum(numpy.hypot(P[:, 0] - p0.x, P[:, 1] - p0.y),
                               numpy.hypot(P[:, 0] - p1.x, P[:, 1] - p1.y))
            return numpy.where(on, numpy.minimum(d, de), de)
        p, q = mv[1], mv[2]
        dx, dy = q.x - p.x, q.y - p.y
        L2 = dx * dx + dy * dy
        t = numpy.zeros(len(P)) if L2 < 1e-12 else \
            numpy.clip(((P[:, 0] - p.x) * dx + (P[:, 1] - p.y) * dy) / L2, 0, 1)
        return numpy.hypot(P[:, 0] - (p.x + t * dx), P[:, 1] - (p.y + t * dy))

    def cut(self, mv):
        self.uncut &= ~(self.dist(mv) <= self.r - self.g)

    def blocked(self, moves, p_from, direction):
        """True if these moves would sweep uncut stock or the part. Material the cutter already
        touches where it starts is allowed only behind or beside it (moving away from it)."""
        if not moves:
            return False
        reach = self.r + self.g                     # grid tolerance: err on the safe side
        hit = numpy.zeros(len(self.P), bool)
        for mv in moves:
            hit |= self.dist(mv) < reach
        hit &= self.uncut | self.part
        if not hit.any():
            return False
        rel = self.P[hit] - (p_from.x, p_from.y)
        touching = numpy.hypot(rel[:, 0], rel[:, 1]) < reach      # same tolerance as above
        behind = rel[:, 0] * direction.x + rel[:, 1] * direction.y <= 0
        return not (touching & behind).all()

    def _reached(self, pts, r, a, sweep, cw, n, reach):
        """For n+1 samples along the circle r from angle a (sweep, direction cw): does any of
        `pts` lie within `reach` of the sample? Each point covers an interval of angles, so
        this is done with intervals, not with a distance matrix."""
        hit = numpy.zeros(n + 2, int)
        if not len(pts):
            return hit[:n + 1] > 0
        rho = numpy.hypot(pts[:, 0], pts[:, 1])
        sel = numpy.abs(rho - r) < reach
        if not sel.any():
            return hit[:n + 1] > 0
        rho, phi = rho[sel], numpy.arctan2(pts[sel, 1], pts[sel, 0])
        c = (rho * rho + r * r - reach * reach) / numpy.maximum(2 * rho * r, 1e-12)
        w = numpy.arccos(numpy.clip(c, -1.0, 1.0))           # half-width of the angle interval
        u = ((a - phi) if cw else (phi - a)) % (2 * math.pi)  # where the point is along the ride
        for shift in (-2 * math.pi, 0.0, 2 * math.pi):
            lo = numpy.ceil((u + shift - w) / sweep * n).astype(int)
            hi = numpy.floor((u + shift + w) / sweep * n).astype(int)
            ok = (hi >= 0) & (lo <= n)
            lo, hi = numpy.clip(lo[ok], 0, n), numpy.clip(hi[ok], 0, n)
            numpy.add.at(hit, lo, 1)
            numpy.add.at(hit, hi + 1, -1)
        return numpy.cumsum(hit)[:n + 1] > 0

    def ride(self, r, a, b, cw, min_air):
        """Moves along the circle r from angle a to b: at cutting feed where the cutter reaches
        material that is still uncut, fast ("air") where it reaches nothing; None if it would
        touch the part. Free stretches shorter than min_air are cut at feed too."""
        sweep = ((a - b) if cw else (b - a)) % (2 * math.pi)
        if sweep < 1e-9:
            return []
        n = max(int(r * sweep / (self.g * 0.5)), 2)
        ang = numpy.linspace(a, a - sweep if cw else a + sweep, n + 1)
        if self._reached(self.P[self.part], r, a, sweep, cw, n, self.r - self.g).any():
            return None
        touch = self._reached(self.P[self.uncut | self.part], r, a, sweep, cw, n, self.r + self.g)
        runs, i = [], 0
        while i < n:
            j = i
            while j + 1 < n and touch[j + 1] == touch[i]:
                j += 1
            runs.append([bool(touch[i] or touch[j + 1]), i, j + 1])
            i = j + 1
        for run in runs:                                   # short free stretches: just cut on
            if not run[0] and r * sweep * (run[2] - run[1]) / n < min_air:
                run[0] = True
        moves = []
        for feed, i, j in runs:
            kind = "cut" if feed else "air"
            if moves and moves[-1][0] == kind:
                moves[-1] = (kind, r, moves[-1][2], ang[j], cw)
            else:
                moves.append((kind, r, ang[i], ang[j], cw))
        return moves

    def hits_part(self, moves):
        hit = numpy.zeros(len(self.P), bool)
        for mv in moves:
            hit |= self.dist(mv) < self.r - self.g
        return bool((hit & self.part).any())


class Plan:
    """The moves for one depth, as plain tuples, so they can be checked without FreeCAD's CAM:
    ("cut", r, a_from, a_to, cw)  arc round the origin, cutting
    ("air", r, a_from, a_to, cw)  arc round the origin through the air, at depth
    ("line", p_from, p_to)        straight cut at depth (a step in, or into the centre)
    ("airline", p_from, p_to)     straight move through the air at depth (X only: out or in)
    ("lift", p_to)                up to the safe height, across, down at p_to"""

    def __init__(self):
        self.moves = []
        self.start = None


def plan_depth(stock_face, keep_face, radius, step, leave=0.0, cw=True, speeds=None, held=None):
    """Rings for one depth. stock_face: the stock section; keep_face: the part (or None);
    held: the jaws and clamps, already grown by their clearance (not by `leave`);
    radius: cutter radius; step: distance between rings; speeds: (cutting feed, plunge feed,
    rapid, air feed factor, lift height) to choose between going on round and lifting."""
    feed, vfeed, rapid, air_k, lift_h = speeds or (10.0, 3.3, 50.0, 3.0, 3.0)
    region = stock_face.makeOffset2D(radius * EDGE_REACH - EPS, join=0) if EDGE_REACH > 0 else stock_face
    keep = None
    if keep_face is not None:
        keep = grow(keep_face, leave) if leave > 0 else keep_face
    if held is not None:
        keep = held if keep is None else keep.fuse(held).removeSplitter()
    if keep is not None:
        region = region.cut(grow(keep, radius))
    plan = Plan()
    if region.isNull() or region.Area < 1e-6:
        return plan
    pts = [p for e in region.Edges for p in e.discretize(Deflection=0.005)]
    r_max = max(p.Length for p in pts)
    centre_in = region.isInside(App.Vector(0, 0, 0), 1e-6, True)
    stock_reach = max(p.Length for e in stock_face.Edges for p in e.discretize(Deflection=0.005))

    mat = Raster(stock_face, keep, radius)

    def travel(a, b, cw_):
        """Angle swept going from a to b in the cutting direction."""
        return ((a - b) if cw_ else (b - a)) % (2 * math.pi)

    reach_out = stock_reach + radius + EPS      # a circle out here never meets the stock

    def link(r1, a1, r2, a2):
        """From the end of an arc at (r1, a1) to the start of the next at (r2, a2), at depth:
        on round the circle r1 (a pure chuck turn: cutting feed where the cutter reaches uncut
        material, fast where it reaches nothing), then straight in to r2 (a cutting step).
        None if that way would touch the part (then the cutter lifts)."""
        moves = mat.ride(r1, a1, a2, cw, MIN_AIR)
        if moves is None:
            return None
        if r1 - r2 > 1e-9:
            step_in = ("line", _pt(r1, a2), _pt(r2, a2))
            if mat.hits_part([step_in]):
                return None
            moves.append(step_in)
        return moves

    def enter(r, a):
        """From above, for the arc that starts at (r, a): down where the cutter reaches nothing,
        a little back along the same circle, then on round to the start; straight down at the
        start if there is no such place."""
        back = 0.0
        reach2 = (radius + GRID) ** 2
        free_pts = mat.P[mat.uncut | mat.part]
        while back < math.pi / 2:
            back += min(radius / max(r, radius), 0.2)
            a_in = a + back if cw else a - back
            p = _pt(r, a_in)
            if not len(free_pts) or (((free_pts - (p.x, p.y)) ** 2).sum(axis=1) >= reach2).all():
                moves = mat.ride(r, a_in, a, cw, MIN_AIR)
                if moves is not None:
                    return [("lift", p)] + moves
                break
        return [("lift", _pt(r, a))]

    def seconds(moves, p_from):
        """Rough time of some moves (to choose the quicker way between two arcs)."""
        t = 0.0
        for mv in moves:
            if mv[0] == "lift":
                d = (mv[1] - p_from).Length if p_from is not None else 0.0
                t += 2 * lift_h / rapid + d / rapid + lift_h / vfeed
            elif mv[0] in ("cut", "air"):
                L = mv[1] * travel(mv[2], mv[3], mv[4])
                t += L / (feed if mv[0] == "cut" else feed * air_k)
            else:
                L = (mv[2] - mv[1]).Length
                t += L / (feed if mv[0] == "line" else feed * air_k)
        return t

    def emit(moves):
        for mv in moves:
            plan.moves.append(mv)
            if mv[0] in ("cut", "line"):
                mat.cut(mv)

    # the radii of the circles: from the outside in by `step`; when the centre is not to be cut
    # (the part is there) the last circle runs exactly along the inner edge of the area
    r_min = 0.0 if centre_in else min(p.Length for p in pts)
    radii = []
    r = r_max
    while r > max(r_min, radius * 0.5) + 1e-6:
        radii.append(r)
        r -= step
    if not centre_in and r_min > radius * 0.5 and (not radii or radii[-1] - r_min > 1e-6):
        radii.append(r_min + EPS)

    pos = None              # (r, angle) of the cutter, None = up
    for r in radii:
        arcs = []
        for e in Part.makeCircle(r).common(region).Edges:
            if e.Length >= MIN_ARC:
                arcs.append(_arc_interval(e))
        if not arcs:
            continue
        # the arcs in the order the cutter meets them, from where it is
        here = pos[1] if pos else (arcs[0][0] + arcs[0][1] if cw else arcs[0][0])

        def first_angle(arc):
            return arc[0] + arc[1] if cw else arc[0]
        arcs.sort(key=lambda arc: travel(here, first_angle(arc), cw))
        for a0, sw in arcs:
            full = sw >= 2 * math.pi - 1e-9
            start = here if full and pos else (a0 + sw if cw else a0)
            end = start - sw if cw else start + sw
            if pos is None:
                emit(enter(r, start))
                if plan.start is None:
                    plan.start = plan.moves[0][1]
            elif full and pos[0] > r:
                # inside the stock all round: step straight in, cutting (a stepover)
                emit([("line", _pt(pos[0], pos[1]), _pt(r, start))])
            elif abs(pos[0] - r) > 1e-9 or travel(pos[1], start, cw) > 1e-9:
                moves = link(pos[0], pos[1], r, start)
                lift = enter(r, start)
                if moves is None or seconds(lift, _pt(pos[0], pos[1])) < seconds(moves, None):
                    moves = lift
                emit(moves)
            if full:            # a full circle as two halves (no 360° arc in the program)
                mid = start - math.pi if cw else start + math.pi
                emit([("cut", r, start, mid, cw), ("cut", r, mid, end, cw)])
            else:
                emit([("cut", r, start, end, cw)])
            pos = (r, end)
            here = end
    if centre_in and pos is not None:
        line = ("line", _pt(pos[0], pos[1]), App.Vector(0, 0, 0))
        if not mat.hits_part([line]):
            emit([line])
    if keep is not None:
        emit(rest_beside_part(mat, keep, radius))
    return plan


def rest_beside_part(mat, keep, radius):
    """Rings stop where they would meet the part; beside a side of the part that runs round the
    centre (an off-centre boss) that leaves cusps between two rings. The cutter follows the
    part's outline, one cutter radius away, only where it still reaches uncut material."""
    moves = []
    reach = radius + GRID
    for wire in grow(keep, radius + EPS).Wires:
        pts = wire.discretize(Distance=GRID)
        left = mat.P[mat.uncut]
        if not len(left):
            break
        on = numpy.array([(((left - (p.x, p.y)) ** 2).sum(axis=1) < reach * reach).any()
                          for p in pts])
        on = on | numpy.roll(on, 1) | numpy.roll(on, -1)        # one point either side
        i, n = 0, len(pts)
        while i < n:
            if not on[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            run = [("line", pts[k], pts[k + 1]) for k in range(i, j)]
            if run and not mat.hits_part(run):
                moves.append(("lift", pts[i]))
                moves.extend(run)
                for mv in run:
                    mat.cut(mv)
            i = j + 1
    return moves


def commands(plan, z, safe, feed, vfeed, air):
    """The Path commands of one depth's plan (feeds in FreeCAD's internal units)."""
    out = []
    up = True
    for mv in plan.moves:
        kind = mv[0]
        if kind == "lift":
            p = mv[1]
            if not up:
                out.append(Path.Command("G0", {"Z": safe}))
            out.append(Path.Command("G0", {"X": p.x, "Y": p.y}))
            out.append(Path.Command("G0", {"Z": safe}))
            out.append(Path.Command("G1", {"Z": z, "F": vfeed}))
            up = False
        elif kind in ("line", "airline"):
            p = mv[2]
            out.append(Path.Command("G1", {"X": p.x, "Y": p.y, "Z": z,
                                           "F": feed if kind == "line" else air}))
        else:
            _, r, a, b, cw_ = mv
            p0, p1 = _pt(r, a), _pt(r, b)
            out.append(Path.Command("G2" if cw_ else "G3", {
                "X": p1.x, "Y": p1.y, "Z": z, "I": -p0.x, "J": -p0.y,
                "F": feed if kind == "cut" else air}))
    if not up:
        out.append(Path.Command("G0", {"Z": safe}))
    return out


# ---- the CAM operation -----------------------------------------------------------------------
FACE_ONLY = "Face only (down to the part top)"
WHOLE = "All the stock round the part"
BAND = "Only round the part (leave the rest)"
CLEARINGS = [FACE_ONLY, WHOLE, BAND]
BAND_AUTO = 1.5         # BandWidth 0: this many cutter diameters

PROPERTIES = (
    ("App::PropertyEnumeration", "Clearing", "Face only: the top, down to the part top. All the "
     "stock: everything outside the part is cut away down to the final depth (a square bar "
     "becomes the round part). Only round the part: a band of Band Width round the part, the "
     "rest of the stock stays as it is."),
    ("App::PropertyLength", "BandWidth", "Only round the part: width of the band cut round it "
     "(0 = 1.5 cutter diameters)."),
    ("App::PropertyPercent", "StepOver", "Distance between the circles, in % of the cutter "
     "diameter."),
    ("App::PropertyDistance", "StockToLeave", "Material left round the part (sideways)."),
    ("App::PropertyEnumeration", "CutMode", "Climb or Conventional, for a spindle turning "
     "forward (M3)."),
    ("App::PropertyLength", "ChuckClearance", "How far the cutter keeps from the jaws and clamps "
     "of the Job's chuck (Polar CNC → Chuck)."),
    ("App::PropertyFloat", "AirFeedFactor", "Where the cutter reaches nothing on its way round "
     "(a pure chuck turn), it goes this many times the cutting feed."),
    ("App::PropertyLink", "PolarChuck", "The Job's chuck: linked so that the path is made again "
     "when the chuck, its jaws or clamps change."),
)


class ObjectPolarFace(PathOp.ObjectOp):

    def opFeatures(self, obj):
        return (PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureHeights
                | PathOp.FeatureStepDown | PathOp.FeatureCoolant)

    def initOperation(self, obj):
        for typ, name, tip in PROPERTIES:
            if not hasattr(obj, name):
                obj.addProperty(typ, name, "Polar Face", tip)
        obj.CutMode = ["Climb", "Conventional"]
        obj.Clearing = CLEARINGS
        obj.setEditorMode("PolarChuck", 1)

    def opOnDocumentRestored(self, obj):
        for typ, name, tip in PROPERTIES:          # files from before a property was added
            if not hasattr(obj, name):
                obj.addProperty(typ, name, "Polar Face", tip)
                if name == "ChuckClearance":
                    obj.ChuckClearance = 2.0
                if name == "Clearing":
                    obj.Clearing = CLEARINGS
                    obj.Clearing = FACE_ONLY
        obj.setEditorMode("PolarChuck", 1)

    def opUpdateDepths(self, obj):
        """Face only: down to the part top (CAM's own default). All the stock / only round the
        part: down to the part bottom, but not into the grip of the jaws (on a faceplate, down
        to the plate). FinalDepth can still be set by hand."""
        if getattr(obj, "Clearing", FACE_ONLY) == FACE_ONLY:
            return
        job = PathUtils.findParentJob(obj)
        if job is None:
            return
        z = job.Proxy.modelBoundBox(job).ZMin
        chuck = getattr(job, "PolarChuck", None)
        if chuck is not None and not chuck.Shape.isNull():
            from . import chuck as chuckmod
            built = chuckmod._build(chuck)
            if not built["body"]:
                tops = []
            elif chuck.ChuckType == chuckmod.FACEPLATE:
                tops = [built["body"].BoundBox.ZMax]
            else:
                tops = [jaw.BoundBox.ZMax for jaw, _r in built["jaws"]]
            if tops:
                z = max(z, max(tops) + max(obj.ChuckClearance.Value, 0))
        if not Path.Geom.isRoughly(obj.OpFinalDepth.Value, z):
            obj.OpFinalDepth = z

    def opSetDefaultValues(self, obj, job):
        obj.StepOver = 40
        obj.StockToLeave = 0
        obj.CutMode = "Climb"
        obj.AirFeedFactor = 3.0
        obj.ChuckClearance = 2.0
        obj.Clearing = FACE_ONLY
        obj.BandWidth = 0
        if job is not None and getattr(job, "PolarChuck", None) is not None:
            obj.PolarChuck = job.PolarChuck

    def opExecute(self, obj):
        radius = self.radius
        step = max(obj.StepOver, 1) / 100.0 * 2 * radius
        stock = self.stock.Shape if self.stock else None
        if stock is None or stock.isNull():
            Path.Log.error("Polar Face needs the Job's stock.")
            return
        part = Part.makeCompound([m.Shape for m in self.model if hasattr(m, "Shape")])
        job = PathUtils.findParentJob(obj)
        chuck = getattr(job, "PolarChuck", None) if job is not None else None
        chuck = getattr(obj, "PolarChuck", None) or chuck
        if chuck is not None and chuck.Shape.isNull():
            chuck = None
        keepout = []
        if chuck is not None:
            from . import chuck as chuckmod
            keepout = chuckmod.keepout_parts(chuck)
        cw = obj.CutMode == "Climb"
        spindle = getattr(obj.ToolController, "SpindleDir", "Forward")
        if spindle == "Reverse":
            cw = not cw
        safe, clearance = obj.SafeHeight.Value, obj.ClearanceHeight.Value
        if not self.horizFeed or not self.vertFeed:
            Path.Log.error("Polar Face: the tool controller '%s' has no feed. Set its Horiz Feed "
                           "and Vert Feed." % getattr(obj.ToolController, "Label", "?"))
            return
        if not stock.BoundBox.isInside(App.Vector(0, 0, stock.BoundBox.Center.z)):
            Path.Log.warning("Polar Face: the chuck axis (X0 Y0) is outside the stock. Is the part "
                             "drawn with its centre at X0 Y0?")
        if keepout:              # moves over the jaws at the safe height must clear them
            top = max(p.BoundBox.ZMax for p in keepout[1:]) if len(keepout) > 1 else None
            need = (top + max(obj.ChuckClearance.Value, 0)) if top is not None else None
            if need is not None and safe < need:
                Path.Log.warning("Polar Face: the Safe Height %.2f is below the jaw / clamp tops "
                                 "%.2f + clearance: %.2f is used instead." % (safe, top, need))
                safe = need
                clearance = max(clearance, need)
        depths = PathUtils.depth_params(clearance, safe, obj.StartDepth.Value, obj.StepDown.Value,
                                        0.0, obj.FinalDepth.Value)
        feed, vfeed = self.horizFeed, self.vertFeed
        air = feed * max(obj.AirFeedFactor, 1.0)
        band = None
        if obj.Clearing == BAND:              # the band round the whole outline of the part
            outline = part_keep(part, part.BoundBox.ZMin - 1.0)
            if outline is None:
                Path.Log.error("Polar Face: 'Only round the part' needs a part.")
                return
            width = obj.BandWidth.Value or BAND_AUTO * 2 * radius
            band = grow(outline, width + max(obj.StockToLeave.Value, 0))
        cmds = self.commandlist
        cmds.append(Path.Command("G0", {"Z": clearance}))
        for z in depths:
            sec = stock_section(stock, z)
            if sec is None:
                continue
            rapid = self.horizRapid if self.horizRapid else 50.0       # 3000 mm/min if not set
            speeds = (feed, vfeed or feed, rapid, max(obj.AirFeedFactor, 1.0), max(safe - z, 0.5))
            keep = part_keep(part, z)
            held = None
            if chuck is not None:                  # jaws and clamps: kept clear like the part
                # the clearance holds in height too: a cut at (or just above) the jaw tops would
                # rub them, so jaws reaching within ChuckClearance below the cut are kept clear
                held = chuck_keep(keepout, z - max(obj.ChuckClearance.Value, 0))
                if held is not None:
                    held = grow(held, max(obj.ChuckClearance.Value, 0) + EPS)
            if band is not None:                 # the stock outside the band stays: kept clear
                rest = sec.cut(band)
                if not rest.isNull() and rest.Area > 1e-6:
                    rest = _flat(rest)
                    held = rest if held is None else held.fuse(rest).removeSplitter()
            plan = plan_depth(sec, keep, radius, step, obj.StockToLeave.Value, cw, speeds, held)
            cmds.extend(commands(plan, z, safe, feed, vfeed, air))


def SetupProperties():
    return ["StepOver", "StockToLeave", "CutMode", "AirFeedFactor", "ChuckClearance", "Clearing",
            "BandWidth"]


def Create(name, obj=None, parentJob=None):
    if obj is None:
        obj = App.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPolarFace(obj, name, parentJob)
    return obj
