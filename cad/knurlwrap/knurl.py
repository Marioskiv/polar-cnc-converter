# Knurling & Wrap — Knurl: knurling on a cylinder in one click (Part Design).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Knurl: knurling on a cylinder in one click (moved from WikiTips 2026-10-20).

Select the outer cylindrical face of a solid, press the Knurl button, pick the
pattern and the pitch. Two kinds:
  - "Πραγματικό": real V-shaped teeth cut into the solid (3D printing, renders);
  - "Ελαφρύ": the groove lines are only drawn on screen by the view provider; the
    solid is not changed, so later features never see them. (For a technical
    drawing, TechDraw's geometric hatch "Diamond" is the usual knurl symbol.)
Inside a Part Design Body it becomes a normal feature of the Body (it follows
the Tip like a Pocket); elsewhere a Part feature that cuts the selected solid.

The teeth are pyramids on a diamond grid (or straight V-grooves), built from
planar faces, so the boolean is fast and always valid (checked in FreeCAD 26.3:
D20 x L20, pitch 1 mm: about 10 s, one valid solid).
The cylinder is stored as numbers (axis, radius, start, length), not as a face
name, so renaming faces upstream ("topological naming") does not break it; on
every recompute the matching cylinder of the new base shape is looked up again.
"""

import math
import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the cad folder
ICON = os.path.join(HERE, "Resources", "Knurl.svg")
PATTERNS = ["Διαμάντι", "Ίσιο"]
KINDS = ["Πραγματικό", "Ελαφρύ"]
V = App.Vector


# --------------------------------------------------------------------------
# geometry (no GUI: also usable from FreeCADCmd and in tests)
# --------------------------------------------------------------------------
def cylinder_of(face):
    """(center, axis, radius, vmin, vmax) of a cylindrical face, or None."""
    s = getattr(face, "Surface", None)
    if s is None or s.TypeId != "Part::GeomCylinder":
        return None
    u0, u1, v0, v1 = face.ParameterRange
    return V(s.Center), V(s.Axis).normalize(), s.Radius, v0, v1


def is_outer(face):
    """True for the outside of a shaft, False for the inside of a hole."""
    c = cylinder_of(face)
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    p = face.valueAt(u, v)
    n = face.normalAt(u, v)
    center, axis = c[0], c[1]
    radial = p - center
    radial = radial - axis * radial.dot(axis)
    return radial.dot(n) > 0


def upwards(center, axis, vmin, vmax):
    """The same cylinder with its axis pointing "up" (world Z, else Y, else X).

    FreeCAD often gives the side of a Pad an axis pointing down (v from -L to 0);
    people mean "from the bottom" and want text the right way up.
    """
    for ref in (V(0, 0, 1), V(0, 1, 0), V(1, 0, 0)):
        d = axis.dot(ref)
        if abs(d) > 1e-9:
            if d < 0:
                return center, -axis, -vmax, -vmin
            break
    return center, axis, vmin, vmax


def depth_for(pitch, pattern, angle):
    """Full height of sharp 90° teeth: half the groove spacing measured across the groove.

    It is also the deepest a knurl of this pitch can be: deeper teeth would run into each
    other (Marios tried pitch 0.3 with depth 0.8: an impossible shape that took 10 minutes).
    """
    a = 0.0 if pattern == "Ίσιο" else _angle(angle)
    return 0.5 * pitch * math.cos(math.radians(a))


DEFAULT_DEPTH = 0.75   # x full height: the teeth get flat tops (a quarter of the tooth), like a real
MIN_DEPTH = 0.2        # knurl rolled to normal depth; sharp points only when the full height is asked


def tooth_depth(depth, pitch, pattern, angle):
    """The depth actually used: 0 = automatic; always between 20 % and 100 % of the full height."""
    full = depth_for(pitch, pattern, angle)
    if depth <= 0:
        return DEFAULT_DEPTH * full
    return min(max(depth, MIN_DEPTH * full), full)


def _angle(angle):
    """Helix angle kept between 5° and 60°: 0° divides by zero, near 90° gives endless rows."""
    return min(max(angle, 5.0), 60.0)


def _grid(R, L, pitch, angle, straight):
    angle = _angle(angle)
    n = max(3, int(round(2 * math.pi * R / pitch)))
    if straight:
        return n, 1, L
    k = math.tan(math.radians(angle)) / R
    rows = max(1, int(round(L / (math.pi / n / k))))
    return n, rows, L / rows


# Limits measured in FreeCAD 26.3 (2026-10-17), flat-topped teeth written as BREP text (_Brep):
# direct build ~0.25 ms and ~11 KB per face (D50 x 40 mm, pitch 1 = 36 000 faces: 8.6 s, 410 MB;
# D20 x 20 mm, pitch 0.3 = 80 000 faces: 22 s, 810 MB). In the GUI storing the shape in the feature
# (element names) and showing it add ~0.25 ms per face: D10 x 10, pitch 0.3 = 20 600 faces: 9-10 s.
# The boolean fallback (band crossed by a hole or a flat) is ~0.9 ms per face (36 000: 34 s, 1 GB).
MAX_FACES = 60000
MAX_FACES_BOOLEAN = 25000
LAST_METHOD = ""
WHY_BOOLEAN = ""       # why the last knurl could not be built directly (for tests and notes)
PEAK_INSET = 0.002   # teeth tips 2 µm inside the cylinder: no tangent faces, boolean 3-5x faster


def _normal(f):
    """Normal of a planar face as it faces out (cheap: no centre of mass)."""
    n = f.Surface.Axis
    return -n if f.Orientation == "Reversed" else n


class _Brep:
    """Writes flat faces straight into OpenCASCADE's BREP text, read back in one go.

    Making faces one by one through Part costs ~0.5 ms each and a shell of tens of
    thousands of them is checked face by face (36 000 faces: 30 s). Written as text
    the same solid loads in a few seconds. `old` is the BREP text of existing shapes
    (the rest of the part) whose faces and wires the new solid uses as they are;
    it must be a compound of two compounds, faces and wires (see direct_knurl).
    Records are numbered the OpenCASCADE way: the last one written is 1.
    """

    def __init__(self, pts, old=None):
        self.pts = pts
        self.curves, self.surfs, self.recs = [], [], []
        self.vert, self.edges = {}, {}
        self.old = None
        self.c0 = self.s0 = 0                # curves and surfaces already in the old text
        if old is not None:
            self._read_old(old)

    # --- the shapes already there ---
    def _read_old(self, text):
        lines = text.split("\n")
        head = {}
        for i, ln in enumerate(lines):
            w = ln.split()
            if len(w) == 2 and w[0] in ("Curves", "Surfaces", "TShapes") and w[1].isdigit():
                head[w[0]] = (i, int(w[1]))
        recs, i = [], head["TShapes"][0] + 1
        while len(recs) < head["TShapes"][1]:
            kind = lines[i].strip()
            while lines[i].strip():          # type line and geometry, up to the blank line
                i += 1
            i += 2                           # blank line, flags line
            start, toks = i, []
            while True:
                toks += lines[i].split()
                if lines[i].rstrip().endswith("*"):
                    break
                i += 1
            recs.append((kind, start, i, toks[:-1]))
            i += 1
        self.old = dict(lines=lines, head=head, recs=recs)
        self.c0, self.s0 = head["Curves"][1], head["Surfaces"][1]

    def old_refs(self, index):
        """[(sign, record, location)] inside the old record numbered `index` (1 = the root)."""
        recs = self.old["recs"]
        toks = recs[len(recs) - index][3]
        return [(toks[k][0], int(toks[k][1:]), toks[k + 1]) for k in range(0, len(toks), 2)]

    # --- new shapes ---
    def _rec(self, head, refs):
        self.recs.append((head, refs))
        return len(self.recs)

    def vertex(self, i):
        k = self.vert.get(i)
        if k is None:
            p = self.pts[i]
            k = self.vert[i] = self._rec("Ve\n1e-07\n%r %r %r\n0 0\n\n0101101\n" % (p.x, p.y, p.z), [])
        return k

    def edge(self, i, j):
        """(record, sign) of the straight edge from point i to point j."""
        a, b = (i, j) if i < j else (j, i)
        k = self.edges.get((a, b))
        if k is None:
            pa, pb = self.pts[a], self.pts[b]
            d = pb - pa
            n = d.Length
            d = d * (1.0 / n)
            self.curves.append("1 %r %r %r %r %r %r" % (pa.x, pa.y, pa.z, d.x, d.y, d.z))
            k = self.edges[(a, b)] = self._rec(
                "Ed\n 1e-07 1 1 0\n1  %d 0 0 %r\n0\n\n0101000\n" % (self.c0 + len(self.curves), n),
                [("+", self.vertex(a), "0"), ("-", self.vertex(b), "0")])
        return k, "+" if i == a else "-"

    def wire(self, idx):
        refs = []
        for m in range(len(idx)):
            k, sg = self.edge(idx[m], idx[(m + 1) % len(idx)])
            refs.append((sg, k, "0"))
        return self._rec("Wi\n\n0101100\n", refs)

    def face(self, loops, normal=None):
        """A flat face: loops are point-index lists (outer one first, anticlockwise about
        `normal`; holes clockwise) or (sign, -old record, location) for old wires.
        Without `normal` the face has one loop and faces the side it turns anticlockwise."""
        if normal is None:
            p = [self.pts[i] for i in loops[0]]
            normal = V()
            for k in range(len(p)):
                normal += p[k].cross(p[(k + 1) % len(p)])
            normal.normalize()
        o = self.pts[loops[0][0]] if isinstance(loops[0], list) else self._old_point(loops)
        x = normal.cross(V(1, 0, 0) if abs(normal.x) < 0.9 else V(0, 1, 0))
        x.normalize()
        y = normal.cross(x)
        self.surfs.append("1 %r %r %r %r %r %r %r %r %r %r %r %r" % (o.x, o.y, o.z, normal.x, normal.y, normal.z,
                                                                   x.x, x.y, x.z, y.x, y.y, y.z))
        refs = [("+", self.wire(l), "0") if isinstance(l, list) else l for l in loops]
        return self._rec("Fa\n0  1e-07 %d 0\n\n0101000\n" % (self.s0 + len(self.surfs)), refs)

    def _old_point(self, loops):
        for l in loops:
            if isinstance(l, list):
                return self.pts[l[0]]
        raise ValueError("a face needs one new loop")

    def solid(self, faces):
        """faces: new face records or (sign, old record, location); returns the BREP text."""
        sh = self._rec("Sh\n\n0101000\n", [("+", f, "0") if isinstance(f, int) else f for f in faces])
        self._rec("So\n\n1100000\n", [("+", sh, "0")])
        return self.text()

    def text(self):
        nm = len(self.recs)

        def ref(sg, k, loc):
            return "%s%d %s" % (sg, nm - k + 1 if k > 0 else -k + nm, loc)

        mine = [head + " ".join(ref(*r) for r in refs) + " *" for head, refs in self.recs]
        if self.old is None:
            out = ["CASCADE Topology V1, (c) Matra-Datavision", "Locations 0", "Curve2ds 0",
                   "Curves %d" % len(self.curves)] + self.curves + [
                   "Polygon3D 0", "PolygonOnTriangulations 0", "Surfaces %d" % len(self.surfs)] + self.surfs + [
                   "Triangulations 0", "", "TShapes %d" % nm] + mine + ["", "+1 0", ""]
            return "\n".join(out)
        lines = list(self.old["lines"])
        head = self.old["head"]
        # old records keep their numbers + nm (new ones come after them in the file)
        for kind, a, b, toks in self.old["recs"]:
            out = []
            for k, t in enumerate(toks):
                out.append("%s%d" % (t[0], int(t[1:]) + nm) if k % 2 == 0 else t)
            lines[a] = " ".join(out) + " *"
            for i in range(a + 1, b + 1):
                lines[i] = None
        ti, tn = head["TShapes"]
        lines[ti] = "TShapes %d" % (tn + nm)
        end = len(lines) - 1
        while not lines[end] or not lines[end].strip():
            end -= 1
        lines[end] = "\n".join(mine) + "\n\n+1 0"           # the new solid replaces the old root
        # old curves and surfaces may take several lines each: new ones go just before the next section
        for name, nxt_name, new_lines in (("Curves", "Polygon3D", self.curves), ("Surfaces", "Triangulations", self.surfs)):
            i, n = head[name]
            nxt = next(j for j in range(i + 1, len(lines)) if lines[j] is not None and lines[j].startswith(nxt_name))
            lines[i] = "%s %d" % (name, n + len(new_lines))
            lines[nxt] = "\n".join(new_lines + [lines[nxt]])
        return "\n".join(l for l in lines if l is not None)


def teeth_polys(R, L, pitch, angle, depth, straight=False, place=None):
    """The knurled surface as planar faces sharing their edges, axis Z, z from 0 to L.

    Teeth have 90° flanks. With `depth` below the full height they are truncated
    pyramids (diamond) or ridges (straight) with a flat top just under the
    cylinder radius, as on a real knurled part. Each top corner lies on the line
    from the (missing) sharp tip to a valley point, at the height of the top
    plane, so every flank and every top is one exact flat face (5 faces a diamond
    tooth, 3 a straight ridge) and no sewing is needed.
    Returns (points, polygons, bottom outline, top outline): polygons and
    outlines are point indices, polygons turning anticlockwise seen from outside,
    outlines along z=0 and z=L in increasing angle.
    """
    pts = []
    n, rows, dz = _grid(R, L, pitch, angle, straight)
    na = 2 * n
    half = math.pi / n
    full = depth_for(pitch, "Ίσιο" if straight else "", angle)
    depth = min(depth, full)
    sharp = depth > 0.98 * full
    if sharp:
        depth = full
    r_low = R - PEAK_INSET - depth        # valleys
    r_tip = r_low + full                  # where the sharp tip would be
    # height of the flat tops along each tooth's centre line, a little lower than R - PEAK_INSET
    # so the top corners (off the centre line) stay inside the cylinder too
    h = R - PEAK_INSET
    lat = (r_tip - h) / (r_tip - r_low * math.cos(half)) * r_low * math.sin(half)
    h -= lat * lat / h
    pl = place or App.Placement()
    index = {}

    def local(a, b, r):
        t = a * half
        return V(r * math.cos(t), r * math.sin(t), b * dz)

    def valley(a, b):
        key = ("v", a % na, b)
        if key not in index:
            pts.append(pl.multVec(local(a, b, r_low)))
            index[key] = len(pts) - 1
        return index[key]

    def corner(a, b, da, db):             # top corner of the tooth at (a, b) towards a neighbour
        key = ("t", a % na, b) if sharp else ("t", a % na, b, da, db)
        if key not in index:
            tip = local(a, b, r_tip)
            if not sharp:
                v = local(a + da, b + db, r_low)
                u = V(math.cos(a * half), math.sin(a * half), 0)
                tip = tip + (v - tip) * ((r_tip - h) / (r_tip - v.dot(u)))
            pts.append(pl.multVec(tip))
            index[key] = len(pts) - 1
        return index[key]

    out_axis = pl.Rotation.multVec(V(0, 0, 1))
    origin = V(pl.Base)

    def outward(p):
        d = p - origin
        return d - out_axis * d.dot(out_axis)

    polys = []
    lines = {0: [], rows: []}

    def add(idx):
        p = [pts[i] for i in idx]
        nrm = V()
        for k in range(len(p)):
            nrm += p[k].cross(p[(k + 1) % len(p)])
        polys.append(idx if nrm.dot(outward(p[0])) > 0 else idx[::-1])

    if straight:
        for a in range(1, na, 2):
            w0, w1, e0, e1 = corner(a, 0, -1, 0), corner(a, 1, -1, 0), corner(a, 0, 1, 0), corner(a, 1, 1, 0)
            l0, l1, r0, r1 = valley(a - 1, 0), valley(a - 1, 1), valley(a + 1, 0), valley(a + 1, 1)
            add([l0, w0, w1, l1])
            add([e0, r0, r1, e1])
            if not sharp:
                add([w0, e0, e1, w1])
            for b, w, e, lv in ((0, w0, e0, l0), (1, w1, e1, l1)):
                lines[b] += [lv, w] + ([] if sharp else [e])
    else:
        dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))     # E, N, W, S
        for b in range(rows + 1):
            for a in range(na):
                if (a + b) % 2 == 0:
                    if b in (0, rows):
                        lines[b].append(valley(a, b))
                    continue
                tops = {d: corner(a, b, *d) for d in dirs if 0 <= b + d[1] <= rows}
                for k in range(4):
                    d1, d2 = dirs[k], dirs[(k + 1) % 4]
                    if d1 in tops and d2 in tops:
                        v1, v2 = valley(a + d1[0], b + d1[1]), valley(a + d2[0], b + d2[1])
                        add([tops[d1], v1, v2] if sharp else [tops[d1], v1, v2, tops[d2]])
                if not sharp:
                    add([tops[d] for d in dirs if d in tops])
                if b in (0, rows):
                    lines[b] += [tops[(-1, 0)]] + ([] if sharp else [tops[(1, 0)]])
    lines = {0: lines[0], L: lines[rows]}
    inv = pl.inverse()

    def angle_of(i):
        q = inv.multVec(pts[i])
        return math.atan2(q.y, q.x) % (2 * math.pi)

    for z in lines:
        lines[z] = sorted(set(lines[z]), key=angle_of)
    return pts, polys, lines[0], lines[L]


def face_count(R, L, pitch, angle, straight=False):
    """How many faces the knurled surface has, at most (to refuse knurls that are too big)."""
    if R <= 0 or L <= 0 or pitch <= 0:
        return 0
    n, rows, dz = _grid(R, L, pitch, angle, straight)
    return n * rows * (3 if straight else 5)     # flat-topped teeth: 4 flanks + the top


def seconds_for(faces):
    return max(1, int(round(faces / 2000.0)))   # build + store in the feature + show, measured in the GUI


def knurl_tool(R, L, pitch, angle, depth, straight=False):
    """The material a knurling removes from a cylinder of radius R, axis Z, from z=0 to L.

    The knurled surface (facing inwards), an outer prism just outside the cylinder
    and two flat end rings, written as one closed shell (see _Brep).
    """
    pts, polys, low, high = teeth_polys(R, L, pitch, angle, depth, straight)
    pts = list(pts)
    n = 72
    ro = R / math.cos(math.pi / n) + 0.01
    ring = {}
    for z in (0.0, L):
        ring[z] = list(range(len(pts), len(pts) + n))
        pts += [V(ro * math.cos(2 * math.pi * k / n), ro * math.sin(2 * math.pi * k / n), z) for k in range(n)]
    b = _Brep(pts)
    faces = [b.face([q[::-1]]) for q in polys]
    for k in range(n):
        a0, a1, b0, b1 = ring[0.0][k], ring[0.0][(k + 1) % n], ring[L][k], ring[L][(k + 1) % n]
        faces.append(b.face([[a0, a1, b1, b0]]))          # anticlockwise seen from outside
    # rings and outlines go round anticlockwise seen from +Z
    faces.append(b.face([ring[0.0][::-1], low], V(0, 0, -1)))
    faces.append(b.face([ring[L], high[::-1]], V(0, 0, 1)))
    shape = Part.Shape()
    shape.importBrepFromString(b.solid(faces), False)
    solid = shape.Solids[0]
    if solid.Volume < 0:
        solid.reverse()
    return solid


def _no(why):
    global WHY_BOOLEAN
    WHY_BOOLEAN = why
    return None


def direct_knurl(base, pl, R, L, pitch, angle, depth, straight=False):
    """Knurled solid built directly, without the slow boolean (4-8x faster).

    The band is the cylinder of radius R from pl.Base along pl's Z for a length L.
    Works when the band is a clean full ring of material (no hole, flat or slot
    crossing it): the part gets a plain groove (an analytic cut, instant), whose
    faces are replaced by the tooth faces and two end faces, written together
    with the rest of the part as one BREP text (see _Brep): no sewing, no boolean. Everything is built in the part's own coordinates (moving shapes
    back and forth left some faces behind, found in a Body test). Returns None
    when not possible; the caller then uses the boolean.
    Checked in FreeCAD 26.3: same volume as the boolean, valid solid, booleans
    with the result behave.
    """
    origin = V(pl.Base)
    axis = pl.Rotation.multVec(V(0, 0, 1))
    rin = R - depth - 0.05
    ring = Part.makeCylinder(R + 1, L, origin, axis).cut(Part.makeCylinder(rin, L, origin, axis))
    full = math.pi * (R * R - rin * rin) * L
    if abs(base.common(ring).Volume - full) > 1e-6 * full:
        return _no('crossed')  # something crosses the band: use the boolean

    def along(p):
        return (p - origin).dot(axis)

    def radial(p):
        d = p - origin
        return (d - axis * d.dot(axis)).Length

    grooved = base.cut(ring)
    wall = math.pi * (R * R - rin * rin)
    # at each end the band either meets more material (a groove wall is left) or the end of
    # the part (the part's end face, now a disc of radius rin, must become the knurl outline)
    probe = R - depth / 2
    outside = {0.0: base.isInside(pl.multVec(V(probe, 0, -1e-3)), 1e-9, False),
               L: base.isInside(pl.multVec(V(probe, 0, L + 1e-3)), 1e-9, False)}
    keep, loops = [], {0.0: [], L: []}      # loops: (old wire, normal of the face it came from)
    for f in grooved.Faces:
        srf, c = f.Surface, f.CenterOfMass
        z = along(c)
        if srf.TypeId == "Part::GeomCylinder" and abs(srf.Radius - rin) < 1e-7 and -1e-7 < z < L + 1e-7:
            continue                     # groove bottom
        if srf.TypeId == "Part::GeomPlane":
            end = 0.0 if abs(z) < 1e-7 else L if abs(z - L) < 1e-7 else None
            if end is not None and outside[end] and abs(f.Area - wall) < 1e-6 * wall:
                loops[end].append((f.OuterWire, _normal(f)))   # groove wall: its rim circle stays
                continue
            if end is not None and not outside[end] and radial(c) < rin:
                loops[end] += [(w, _normal(f)) for w in f.Wires if not w.isSame(f.OuterWire)]
                continue                 # the part's end face: replaced by the knurl outline
        keep.append(f)
    if any(outside[z] and len(loops[z]) != 1 for z in outside):
        return _no('rims')
    # one BREP text: the kept faces and wires as they are, the teeth and two end faces new
    wires = loops[0.0] + loops[L]
    b = _Brep(None, Part.Compound([Part.Compound(keep), Part.Compound([w for w, nrm in wires])]).exportBrepToString())
    (s1, kc, l1), (s2, wc, l2) = b.old_refs(1)
    if l1 != "0" or l2 != "0":
        return _no('locations')
    old_faces = [(sg, -k, loc) for sg, k, loc in b.old_refs(kc)]
    old_wires = [(sg, -k, loc) for sg, k, loc in b.old_refs(wc)]
    pts, polys, low, high = teeth_polys(R, L, pitch, angle, depth, straight, place=pl)
    b.pts = pts
    faces = [b.face([q]) for q in polys]
    m = 0
    for z, line in ((0.0, low), (L, high)):
        # facing out of the material: into the band when the part goes on past the end
        out = axis if outside[z] == (z == 0.0) else -axis
        zig = line if out.dot(axis) > 0 else line[::-1]      # outline anticlockwise about `out`
        old = []
        for w, nrm in loops[z]:
            sg, k, loc = old_wires[m]
            m += 1
            if nrm.dot(out) < 0:                               # a wire turns with its face
                sg = "-" if sg == "+" else "+"
            old.append((sg, k, loc))
        faces.append(b.face(old + [zig[::-1]] if outside[z] else [zig] + old, out))
    shape = Part.Shape()
    shape.importBrepFromString(b.solid(old_faces + faces), False)
    if len(shape.Solids) != 1:
        return _no('solids')
    solid = shape.Solids[0]
    shell = solid.Shells[0]
    if not shell.isClosed() or solid.Volume < 0:
        return _no('open shell')
    # cheap sanity instead of a full isValid() (5 s on 29k faces): the volume must lie between
    # the part with a plain groove and the untouched part, and the far ends must still be solid
    if not (grooved.Volume < solid.Volume < base.Volume):
        return _no('volume')
    core = (R - depth) / 2
    checks = [pl.multVec(V(core, 0, L / 2))] + [pl.multVec(V(probe, 0, z)) for z, inside in
                                                ((-1e-3, outside[0.0]), (L + 1e-3, outside[L])) if inside]
    for pt in checks:
        if base.isInside(pt, 1e-9, False) and not solid.isInside(pt, 1e-9, False):
            return _no('inside')  # a defective solid: let the boolean do it
    return solid


def knurl_lines(R, L, pitch, angle, straight=False):
    """Groove lines on the surface (helices or straight lines) for the light kind."""
    n, rows, dz = _grid(R, L, pitch, angle, straight)
    edges = []
    step = max(1, -(-n // 360))   # at most 360 lines each way: a drawing needs no more
    if straight:
        for i in range(0, n, step):
            t = 2 * math.pi * i / n
            p = V(R * math.cos(t), R * math.sin(t), 0)
            edges.append(Part.makeLine(p, p + V(0, 0, L)))
        return Part.makeCompound(edges)
    lead = 2 * math.pi * R / math.tan(math.radians(_angle(angle)))   # axial length of one turn
    for left in (False, True):
        h = Part.makeHelix(lead, L, R, 0, left)
        for i in range(0, n, step):
            c = h.copy()
            c.rotate(V(), V(0, 0, 1), 360.0 * i / n)
            edges += c.Edges
    return Part.makeCompound(edges)


def placement_for(center, axis, start):
    rot = App.Rotation(V(0, 0, 1), axis)
    return App.Placement(center + axis * start, rot)


def find_cylinder(shape, center, axis, radius):
    """The outer cylinder of `shape` on the same axis line, closest in radius (after upstream edits)."""
    best = None
    for f in shape.Faces:
        c = cylinder_of(f)
        if c is None or abs(abs(c[1].dot(axis)) - 1) > 1e-6:
            continue
        d = c[0] - center
        if (d - axis * d.dot(axis)).Length > 1e-4 or not is_outer(f):
            continue
        if best is None or abs(c[2] - radius) < abs(best[2] - radius):
            best = c
    return best


# --------------------------------------------------------------------------
# the feature
# --------------------------------------------------------------------------
def _props(obj):
    add = obj.addProperty
    add("App::PropertyEnumeration", "Pattern", "Knurl", "Διαμάντι (σταυρωτό) ή Ίσιο (παράλληλο με τον άξονα)")
    obj.Pattern = PATTERNS
    add("App::PropertyEnumeration", "Kind", "Knurl", "Πραγματικό: κόβει δόντια. Ελαφρύ: μόνο γραμμές στην οθόνη, το στερεό μένει ίδιο")
    obj.Kind = KINDS
    add("App::PropertyLength", "Pitch", "Knurl", "Βήμα: απόσταση ανάμεσα στα δόντια γύρω-γύρω")
    add("App::PropertyAngle", "Angle", "Knurl", "Γωνία των ραβδώσεων ως προς τον άξονα (συνήθως 30°)")
    add("App::PropertyLength", "Depth", "Knurl", "Βάθος δοντιού (0 = αυτόματο: δόντια 90° με επίπεδη κορυφή)")
    add("App::PropertyDistance", "StartMargin", "Knurl", "Απόσταση από την αρχή του κυλίνδρου")
    add("App::PropertyDistance", "EndMargin", "Knurl", "Απόσταση από το τέλος του κυλίνδρου")
    for name in ("AxisCenter", "AxisDirection"):
        add("App::PropertyVector", name, "Cylinder", "Ο κύλινδρος (αποθηκεύεται ως αριθμοί)")
    add("App::PropertyLength", "Radius", "Cylinder", "Ακτίνα του κυλίνδρου")
    add("App::PropertyFloat", "VMin", "Cylinder", "Αρχή κατά μήκος του άξονα")
    add("App::PropertyFloat", "VMax", "Cylinder", "Τέλος κατά μήκος του άξονα")
    for name in ("AxisCenter", "AxisDirection", "Radius", "VMin", "VMax"):
        obj.setEditorMode(name, 1)   # read only: set by the command
    obj.Pitch, obj.Angle = 1.0, 30.0


def _base_shape(obj):
    base = getattr(obj, "BaseFeature", None) or getattr(obj, "Base", None)
    return base.Shape if base is not None and not base.Shape.isNull() else None


def layout(obj, base):
    """(center, axis, radius, start, length) of the knurled band, axis pointing up."""
    axis = V(obj.AxisDirection).normalize()
    center = V(obj.AxisCenter)
    cyl = find_cylinder(base, center, axis, obj.Radius.Value) or (
        center, axis, obj.Radius.Value, obj.VMin, obj.VMax)
    center, axis, radius, vmin, vmax = cyl
    center, axis, vmin, vmax = upwards(center, axis, vmin, vmax)   # margins count from the bottom
    start = vmin + obj.StartMargin.Value
    return center, axis, radius, start, (vmax - obj.EndMargin.Value) - start


def lines_for(obj):
    """The groove lines of a light knurl, in the same coordinates as obj.Shape (None if not light)."""
    if getattr(obj, "Kind", "") != "Ελαφρύ":
        return None
    base = _base_shape(obj)
    if base is None:
        return None
    center, axis, radius, start, length = layout(obj, base)
    if length <= 0 or obj.Pitch.Value <= 0:
        return None
    lines = knurl_lines(radius, length, obj.Pitch.Value, obj.Angle.Value, obj.Pattern == "Ίσιο")
    lines.Placement = placement_for(center, axis, start)
    return lines


def size_report(obj):
    """(faces of the real teeth, seconds, too big?) for the Greek panel; None if unknown."""
    try:
        base = _base_shape(obj)
        if base is None:
            return None
        center, axis, radius, start, length = layout(obj, base)
        faces = face_count(radius, length, obj.Pitch.Value, obj.Angle.Value, obj.Pattern == "Ίσιο")
        return faces, seconds_for(faces), faces > MAX_FACES
    except Exception:
        return None


def explain(title, text, steps):
    """Greek explanation of a refusal, shown after the recompute (the GUI box, see _tell)."""
    if not App.GuiUp:
        return
    try:
        from PySide import QtCore
        QtCore.QTimer.singleShot(0, lambda: _tell(title, text, steps))
    except Exception:
        pass


TOO_BIG = ("Το knurling είναι πολύ μεγάλο",
           "Τόσα πραγματικά δόντια θα βάραιναν πολύ τον υπολογιστή, γι' αυτό δεν υπολογίστηκαν.",
           ["Άνοιξε το Knurl (διπλό κλικ) και μεγάλωσε το βήμα ή μίκρυνε το μήκος.",
            "Για να το βλέπεις μόνο, διάλεξε «Ελαφρύ»: γραμμές στην οθόνη, γρήγορο."])
NO_KNURL = ("Το knurling δεν βγαίνει",
            "Μετά τις αποστάσεις από την αρχή και το τέλος δεν μένει μήκος, ή το βήμα είναι 0, ή ο "
            "κύλινδρος χάθηκε.",
            ["Άνοιξε το Knurl (διπλό κλικ) και μίκρυνε τις αποστάσεις «Από την αρχή» και «Από το τέλος».",
             "Δες ότι ο κύλινδρος υπάρχει ακόμα πριν από το Knurl στο δέντρο."])


class Knurl:
    def __init__(self, obj):
        obj.Proxy = self
        _props(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        base = _base_shape(obj)
        if base is None:
            explain(*NO_KNURL)
            raise RuntimeError("Knurl: no base solid")
        center, axis, radius, start, length = layout(obj, base)
        pitch = obj.Pitch.Value
        if length <= 0 or pitch <= 0:
            explain(*NO_KNURL)
            raise RuntimeError("Knurl: length and pitch must be greater than zero")
        straight = obj.Pattern == "Ίσιο"
        depth = min(tooth_depth(obj.Depth.Value, pitch, obj.Pattern, obj.Angle.Value), radius * 0.5)
        pl = placement_for(center, axis, start)
        if obj.Kind == "Ελαφρύ":
            # the solid stays as it is: the lines are only drawn by the view provider, so
            # later features (Pocket, Fillet...) never see them (checked: lines in the shape
            # made a Fillet after it fail)
            result = base.copy()
            tool = None
        else:
            faces = face_count(radius, length, pitch, obj.Angle.Value, straight)
            if faces > MAX_FACES:
                explain(*TOO_BIG)
                raise RuntimeError("Knurl: too many teeth (%d faces, max %d)" % (faces, MAX_FACES))
            try:
                result = direct_knurl(base, pl, radius, length, pitch, obj.Angle.Value, depth, straight)
            except Exception:
                result = None
            global LAST_METHOD
            LAST_METHOD = "direct" if result is not None else "boolean"   # for tests and notes
            if result is not None:
                tool = None
            else:                         # band not clean (hole, flat...): the slower boolean
                if faces > MAX_FACES_BOOLEAN:
                    explain(*TOO_BIG)
                    raise RuntimeError("Knurl: too many teeth for a band with holes or flats "
                                       "(%d faces, max %d)" % (faces, MAX_FACES_BOOLEAN))
                tool = knurl_tool(radius, length, pitch, obj.Angle.Value, depth, straight)
                tool.Placement = pl
                result = base.cut(tool)
                if len(result.Solids) == 1:
                    result = result.Solids[0]
        if hasattr(obj, "AddSubShape"):
            obj.AddSubShape = tool if tool is not None else Part.Shape()
        obj.Shape = result


def make_knurl(face_owner, face, doc=None):
    """Create the knurl feature for `face` of `face_owner` (a document object)."""
    doc = doc or face_owner.Document
    cyl = cylinder_of(face)
    if cyl is None:
        raise ValueError("not a cylinder")
    body = None
    for o in face_owner.InList:
        if o.TypeId == "PartDesign::Body":
            body = o
    if body is not None:
        # PartDesign::FeatureSubtractivePython / AdditivePython crash FreeCAD 26.3 when created with
        # the GUI up (even with no addon installed, checked 2026-10-17); the plain FeaturePython is fine
        obj = doc.addObject("PartDesign::FeaturePython", "Knurl")
        body.addObject(obj)
    else:
        obj = doc.addObject("Part::FeaturePython", "Knurl")
        obj.addProperty("App::PropertyLink", "Base", "Knurl", "Το στερεό που παίρνει knurling")
        obj.Base = face_owner
    Knurl(obj)
    center, axis, radius, vmin, vmax = cyl
    obj.AxisCenter, obj.AxisDirection, obj.Radius, obj.VMin, obj.VMax = center, axis, radius, vmin, vmax
    obj.Label = "Knurl"
    return obj


# --------------------------------------------------------------------------
# GUI: button, Greek task panel, view provider
# --------------------------------------------------------------------------
def default_pitch(diameter):
    """A usual knurl pitch for the diameter (ideas from DIN 82 tables; easy to change)."""
    for d, p in ((8, 0.6), (16, 0.8), (32, 1.0)):
        if diameter <= d:
            return p
    return 1.2


if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtCore, QtGui

    try:
        from PySide import QtWidgets
    except ImportError:  # pragma: no cover
        QtWidgets = QtGui

    _TOLD = None      # the last guidance box (for tests)

    def _tell(title, text, steps):
        """Greek guidance in a small box that does not block FreeCAD (and the status bar)."""
        global _TOLD
        try:
            Gui.getMainWindow().statusBar().showMessage("%s. %s" % (title, text), 10000)
        except Exception:
            pass
        try:
            if _TOLD is not None:
                _TOLD.close()
            box = QtWidgets.QMessageBox(Gui.getMainWindow())
            box.setWindowTitle(title)
            box.setText("<b>%s</b>" % text)
            box.setInformativeText("<br>".join("%d. %s" % (i + 1, s) for i, s in enumerate(steps)))
            box.setModal(False)
            box.show()
            _TOLD = box
        except Exception:
            pass

    def _selected_face():
        """(owner object, face) of the selected cylindrical face, or (None, reason)."""
        sel = Gui.Selection.getSelectionEx("", 0)   # resolve to the object that owns the face
        for s in sel:
            for name, sub in zip(s.SubElementNames, s.SubObjects):
                if not name.split(".")[-1].startswith("Face"):
                    continue
                owner = s.Object
                if owner.TypeId == "PartDesign::Body":
                    owner = owner.Tip
                if cylinder_of(sub) is None:
                    return None, "flat"
                if not is_outer(sub):
                    return None, "inner"
                return owner, sub
        return None, "none"

    _FIELDS = ("Pattern", "Kind", "Pitch", "Angle", "Depth", "StartMargin", "EndMargin")

    class TaskKnurl:
        """Greek panel. Changing a value shows fast lines; Εφαρμογή (Apply) computes the
        real teeth and keeps the panel open; OK only closes it (computing first if a value
        changed after the last Apply); Cancel puts everything back."""

        def __init__(self, obj):
            self.obj = obj
            self.saved = {name: getattr(obj, name) for name in _FIELDS}
            self.dirty = True             # the shown result does not match the fields yet
            self.form = QtWidgets.QWidget()
            self.form.setWindowTitle("Knurl (ραβδώσεις)")
            lay = QtWidgets.QFormLayout(self.form)
            self.pattern = QtWidgets.QComboBox()
            self.pattern.addItems(PATTERNS)
            self.pattern.setCurrentText(obj.Pattern)
            self.kindbox = QtWidgets.QComboBox()
            self.kindbox.addItems(["Πραγματικό (κόβει δόντια)", "Ελαφρύ (μόνο γραμμές)"])
            self.kindbox.setCurrentIndex(KINDS.index(obj.Kind))
            self.pitch = self._spin(obj.Pitch.Value, 0.1, 10, " mm")
            self.angle = self._spin(obj.Angle.Value, 5, 60, "°")
            self.depth = self._spin(obj.Depth.Value, 0, 10, " mm")
            self.depth.setSpecialValueText("αυτόματο")
            self.start = self._spin(obj.StartMargin.Value, 0, 1000, " mm")
            self.end = self._spin(obj.EndMargin.Value, 0, 1000, " mm")
            rows = [("Μοτίβο", self.pattern, "Διαμάντι: σταυρωτές ραβδώσεις. Ίσιο: παράλληλες με τον άξονα."),
                    ("Είδος", self.kindbox, "Πραγματικό: για 3D εκτύπωση. Ελαφρύ: γραμμές μόνο στην οθόνη (γρήγορο). Για τεχνικό σχέδιο: TechDraw, γράμμωση «Diamond»."),
                    ("Βήμα", self.pitch, "Απόσταση ανάμεσα στα δόντια. Μικρό = λεπτό knurling."),
                    ("Γωνία", self.angle, "Γωνία των ραβδώσεων ως προς τον άξονα. Συνήθως 30°."),
                    ("Βάθος", self.depth, "0 = αυτόματο: τα 3/4 του πλήρους ύψους, δόντια 90° με επίπεδη "
                                          "κορυφή, όπως ένα κανονικό knurling. Το μέγιστο είναι το πλήρες "
                                          "ύψος του βήματος (μυτερές κορυφές)."),
                    ("Από την αρχή", self.start, "Πόσο μακριά από την αρχή του κυλίνδρου ξεκινάει."),
                    ("Από το τέλος", self.end, "Πόσο πριν από το τέλος σταματάει.")]
            for label, w, tip in rows:
                w.setToolTip(tip)
                lay.addRow(label, w)
            self.limits = QtWidgets.QLabel()
            self.limits.setWordWrap(True)
            self.limits.setStyleSheet("color:gray")
            lay.addRow(self.limits)
            self.size = QtWidgets.QLabel()
            self.size.setWordWrap(True)
            lay.addRow(self.size)
            hint = QtWidgets.QLabel("Όταν αλλάζεις τιμές βλέπεις γρήγορη προεπισκόπηση με γραμμές. "
                                    "«Εφαρμογή»: υπολογίζει τα πραγματικά δόντια και το παράθυρο μένει ανοιχτό. "
                                    "«OK»: τέλος.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color:gray")
            lay.addRow(hint)
            self.angle.setEnabled(obj.Pattern != "Ίσιο")
            for w in (self.pitch, self.angle, self.depth, self.start, self.end):
                w.valueChanged.connect(self.preview)
            self.pattern.currentIndexChanged.connect(self.preview)
            self.kindbox.currentIndexChanged.connect(self.preview)
            self.preview()
            global _PANEL
            _PANEL = self     # for tests

        @staticmethod
        def _spin(value, lo, hi, suffix):
            s = QtWidgets.QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(2)
            s.setSingleStep(0.1 if hi <= 10 else 1)
            s.setSuffix(suffix)
            s.setValue(value)
            return s

        def getStandardButtons(self):
            B = QtWidgets.QDialogButtonBox
            return B.Ok | B.Apply | B.Cancel

        def clicked(self, button):
            if button == QtWidgets.QDialogButtonBox.Apply:
                self.compute()

        def apply(self):
            o = self.obj
            o.Pattern = self.pattern.currentText()
            o.Pitch, o.Angle, o.Depth = self.pitch.value(), self.angle.value(), self.depth.value()
            o.StartMargin, o.EndMargin = self.start.value(), self.end.value()
            self.angle.setEnabled(o.Pattern != "Ίσιο")
            full = depth_for(o.Pitch.Value, o.Pattern, o.Angle.Value)
            used = tooth_depth(o.Depth.Value, o.Pitch.Value, o.Pattern, o.Angle.Value)
            text = "Βάθος δοντιού: %.2f mm (αυτόματο %.2f, μέγιστο %.2f για αυτό το βήμα)." % (
                used, DEFAULT_DEPTH * full, full)
            if o.Depth.Value > 0 and abs(used - o.Depth.Value) > 1e-6:
                text += " Το %.2f δεν χωράει: τα δόντια θα έπεφταν το ένα πάνω στο άλλο." % o.Depth.Value
            self.limits.setText(text)

        def show_size(self):
            """How big the real teeth will be, before anything heavy is computed."""
            rep = size_report(self.obj)
            if rep is None:
                self.size.setText("")
                return False
            faces, secs, too_big = rep
            if too_big:
                self.size.setStyleSheet("color:#B91C1C")
                self.size.setText("Πολύ μεγάλο για πραγματικά δόντια (%d επιφάνειες, όριο %d): θα "
                                  "βάραινε πολύ τον υπολογιστή. Μεγάλωσε το βήμα, μίκρυνε το μήκος, "
                                  "ή διάλεξε Ελαφρύ." % (faces, MAX_FACES))
            else:
                self.size.setStyleSheet("color:gray")
                self.size.setText("Πραγματικά δόντια: %d επιφάνειες, περίπου %d δευτερόλεπτα." % (faces, secs))
            return too_big

        def preview(self, *args):
            """A value changed: show the fast lines until the next Apply or OK."""
            try:
                self.dirty = True
                self.obj.Kind = "Ελαφρύ"
                self.apply()
                self.show_size()
                self.obj.Document.recompute()
            except Exception:
                pass

        def compute(self):
            """The chosen kind for real (Apply, or OK after a change). False if too big."""
            self.apply()
            if KINDS[self.kindbox.currentIndex()] == "Πραγματικό" and self.show_size():
                return False          # too big: the panel stays open, the red text says what to do
            self.obj.Kind = KINDS[self.kindbox.currentIndex()]
            QtWidgets.QApplication.setOverrideCursor(_cursor())
            Gui.getMainWindow().statusBar().showMessage("Knurl: υπολογίζω το knurling…")
            QtWidgets.QApplication.processEvents()
            try:
                self.obj.Document.recompute()
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
                Gui.getMainWindow().statusBar().clearMessage()
            self.dirty = False
            return True

        def accept(self):
            if self.dirty and not self.compute():
                return False
            Gui.ActiveDocument.resetEdit()
            return True

        def reject(self):
            for name, value in self.saved.items():
                setattr(self.obj, name, value)
            self.obj.Document.recompute()
            Gui.ActiveDocument.resetEdit()
            return True

    _PANEL = None

    def _cursor():
        # Qt5 names it Qt.WaitCursor, Qt6 (PySide6) Qt.CursorShape.WaitCursor
        shape = getattr(QtCore.Qt, "WaitCursor", None)
        if shape is None:
            shape = QtCore.Qt.CursorShape.WaitCursor
        return QtGui.QCursor(shape)

    class ViewProviderKnurl:
        def __init__(self, vobj):
            vobj.Proxy = self

        def attach(self, vobj):
            self.Object = vobj.Object
            self.lines = None
            try:   # thousands of small tooth edges: thin grey lines instead of thick black ones
                vobj.LineWidth = 1.0
                vobj.LineColor = (0.35, 0.38, 0.42)
            except Exception:
                pass
            try:   # the light kind: groove lines drawn on screen only (not part of the solid)
                from pivy import coin
                self.lines = coin.SoSeparator()
                col = coin.SoBaseColor()
                col.rgb = (0.12, 0.16, 0.22)
                style = coin.SoDrawStyle()
                style.lineWidth = 1.5
                self.coords = coin.SoCoordinate3()
                self.lineset = coin.SoLineSet()
                for n in (col, style, self.coords, self.lineset):
                    self.lines.addChild(n)
                vobj.RootNode.addChild(self.lines)
            except Exception:
                self.lines = None

        def updateData(self, obj, prop):
            if prop != "Shape" or getattr(self, "lines", None) is None:
                return
            try:
                pts, counts = [], []
                shape = lines_for(obj)
                if shape is not None:
                    inv = obj.Placement.inverse()
                    for e in shape.Edges:
                        ps = [inv.multVec(p) for p in e.discretize(Deflection=0.05)]
                        pts += [(p.x, p.y, p.z) for p in ps]
                        counts.append(len(ps))
                self.coords.point.setValues(0, len(pts), pts)
                self.coords.point.setNum(len(pts))
                self.lineset.numVertices.setValues(0, len(counts), counts)
                self.lineset.numVertices.setNum(len(counts))
            except Exception:
                pass

        def getIcon(self):
            return ICON

        def claimChildren(self):
            base = getattr(self.Object, "Base", None)
            return [base] if base is not None else []

        def setEdit(self, vobj, mode=0):
            if mode != 0:
                return None
            Gui.Control.showDialog(TaskKnurl(vobj.Object))
            return True

        def unsetEdit(self, vobj, mode=0):
            Gui.Control.closeDialog()
            return True

        def doubleClicked(self, vobj):
            Gui.ActiveDocument.setEdit(vobj.Object.Name)
            return True

        def dumps(self):
            return None

        def loads(self, state):
            return None

    class KnurlCommand:
        def GetResources(self):
            return {"Pixmap": ICON, "MenuText": "Knurl (ραβδώσεις)",
                    "ToolTip": "Knurling σε κύλινδρο: διάλεξε την εξωτερική κυλινδρική επιφάνεια και πάτα το κουμπί."}

        def IsActive(self):
            return App.ActiveDocument is not None

        def Activated(self):
            owner, face = _selected_face()
            if owner is None:
                why = {"none": "Δεν έχεις διαλέξει επιφάνεια.",
                       "flat": "Η επιφάνεια που διάλεξες δεν είναι κυλινδρική.",
                       "inner": "Διάλεξες το εσωτερικό μιας τρύπας: το knurling γίνεται απ' έξω."}[face]
                _tell("Διάλεξε τον κύλινδρο", why,
                      ["Κάνε κλικ στην εξωτερική πλευρά του κυλίνδρου στο 3D (γίνεται πράσινη).",
                       "Μετά πάτα το κουμπί Knurl."])
                return
            doc = owner.Document
            doc.openTransaction("Knurl")
            obj = make_knurl(owner, face)
            obj.Pitch = default_pitch(2 * obj.Radius.Value)
            if obj.ViewObject is not None:
                ViewProviderKnurl(obj.ViewObject)
            if getattr(obj, "Base", None) is not None and obj.Base.ViewObject is not None:
                obj.Base.ViewObject.Visibility = False
            doc.commitTransaction()
            Gui.Selection.clearSelection()
            Gui.ActiveDocument.setEdit(obj.Name)

    def install():
        Gui.addCommand("KnurlWrap_Knurl", KnurlCommand())
