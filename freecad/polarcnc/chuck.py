# Polar CNC — the work holding of a polar Job: a 3-jaw chuck, a 4-jaw chuck or a faceplate with
# clamps, as a solid in the Job's coordinates.
#
# Everything here turns with the part, so seen from the part it stands still: the jaws and
# clamps are obstacles exactly like the part itself. Polar Face keeps the cutter away from them,
# the simulator shows them turning, and a check can test every move against them.
#
# The jaws close on the real stock: each jaw is placed where a ray from the chuck axis in its
# direction leaves the stock (at the middle of the gripped length). A self-centring 3-jaw chuck
# can only hold stock that is centred; if the jaws would not all meet it at the same radius, the
# chuck says so instead of pretending.
#
# Dimensions as in the makers' catalogues (letters of the scroll-chuck tables): diameter A,
# body thickness B, jaw length H (radial), jaw width J, jaw height above the chuck face K. The
# jaw is modelled as a full block of height K over its whole length (its steps ignored), so it is
# never smaller than the real jaw.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math

import FreeCAD as App
import Part

THREE_JAW = "3-jaw (self-centring)"
FOUR_JAW = "4-jaw (independent jaws)"
FOUR_JAW_SC = "4-jaw (self-centring)"
FACEPLATE = "Faceplate with clamps"
TYPES = [THREE_JAW, FOUR_JAW_SC, FOUR_JAW, FACEPLATE]
SELF_CENTRING = (THREE_JAW, FOUR_JAW_SC)

CUSTOM = "Custom (my own sizes)"
OLD_NAMES = {"Custom": CUSTOM,         # presets saved under an older name
             "4-jaw SAN OU K12-125 (Ø125)": "4-jaw SAN OU K12-125 self-centring (Ø125)"}

# catalogue sizes: (type, A diameter, B body, H jaw length, J jaw width, K jaw height)
PRESETS = {
    CUSTOM: None,
    # SAN OU catalogue sizes. Body thickness from the tables; jaw height above the face, jaw
    # length and width are not in them for every model: scaled from the catalogue drawings
    # (3-jaw: body 58 -> jaws about 18). Measure your own chuck.
    # K72-125: jaw height 21.7, length 56, width 18 measured on a real chuck
    "4-jaw SAN OU K72-125 independent (Ø125)": (FOUR_JAW, 125, 56, 56, 18, 21.7),
    # K12 table: D 125, H1 58 body, H 84 overall -> jaws 26 above the face
    "4-jaw SAN OU K12-125 self-centring (Ø125)": (FOUR_JAW_SC, 125, 58, 40, 14, 26),
    "3-jaw SAN OU 125 (Ø125)": (THREE_JAW, 125, 58, 39, 14, 18),
    "3-jaw SC-3 (Ø86)": (THREE_JAW, 86, 46, 36, 11, 14.3),
    "3-jaw SC-4 (Ø112)": (THREE_JAW, 112, 60, 42, 14, 16.6),
    "3-jaw SC-5 (Ø132)": (THREE_JAW, 132, 60, 50, 16, 20.3),
    "3-jaw SC-6 (Ø167)": (THREE_JAW, 167, 67, 63, 19, 23.7),
    "3-jaw SC-7 (Ø192)": (THREE_JAW, 192, 76.5, 77, 21.5, 29.4),
    "3-jaw SC-8 (Ø200)": (THREE_JAW, 200, 76.5, 77, 21.5, 29.4),
    "3-jaw SC-9 (Ø232)": (THREE_JAW, 232, 84, 87, 24, 35.6),
    "3-jaw SC-10 (Ø273)": (THREE_JAW, 273, 87, 98, 28, 39.5),
    "3-jaw SC-12 (Ø310)": (THREE_JAW, 310, 96, 110, 30, 45.6),
    "3-jaw SC-16 (Ø405)": (THREE_JAW, 405, 122, 146, 42, 56.3),
    "4-jaw 12in (Ø300)": (FOUR_JAW, 300, 90, 112, 35, 45),
    "4-jaw 14in (Ø350)": (FOUR_JAW, 350, 100, 112, 35, 45),
    "4-jaw 16in (Ø400)": (FOUR_JAW, 400, 100, 132, 40, 55),
    "4-jaw 18in (Ø450)": (FOUR_JAW, 450, 105, 132, 40, 55),
    "4-jaw 20in (Ø500)": (FOUR_JAW, 500, 110, 149, 45, 65),
    "4-jaw 24in (Ø600)": (FOUR_JAW, 600, 120, 159, 50, 70),
    "Faceplate Ø250": (FACEPLATE, 250, 25, 0, 0, 0),
    "Faceplate Ø400": (FACEPLATE, 400, 30, 0, 0, 0),
}

GROUP = "Chuck"
PROPS = (
    # the stock, not the Job: the Job links the chuck (PolarChuck) and its operations link it
    # too, so a link back to the Job would make a dependency cycle
    ("App::PropertyLink", "Stock", "The stock this chuck holds (the Job's stock)."),
    ("App::PropertyEnumeration", "Preset", "A catalogue size; choosing one fills in the sizes below "
     "(they can still be changed: the preset then reads Custom)."),
    ("App::PropertyEnumeration", "ChuckType", "3-jaw or 4-jaw self-centring (all jaws move together), "
     "4-jaw with independent jaws, or a faceplate with clamps you place yourself."),
    ("App::PropertyLength", "Diameter", "Chuck (or faceplate) diameter, A in the catalogues."),
    ("App::PropertyLength", "BodyThickness", "Body (or faceplate) thickness, B."),
    ("App::PropertyLength", "JawLength", "Radial length of a jaw, H."),
    ("App::PropertyLength", "JawWidth", "Width of a jaw, J."),
    ("App::PropertyLength", "JawHeight", "How far the jaws stand out of the chuck face, K. The one "
     "that matters most: measure it on your chuck."),
    ("App::PropertyLength", "GripLength", "How much of the stock is held between the jaws, from its "
     "bottom up. 0 = the stock stands on the chuck face / faceplate."),
    ("App::PropertyAngle", "FirstJawAngle", "Direction of the first jaw (the others follow at "
     "120° or 90°). Turn it so the jaws meet the flats of a hexagon or a square."),
    ("App::PropertyLinkList", "Clamps", "Clamps and supports (Polar CNC clamps or any solids): they "
     "turn with the chuck and are kept clear like the jaws."),
    ("App::PropertyStringList", "Notes", "What the chuck found when it closed on the stock."),
)


class Chuck:
    def __init__(self, obj):
        obj.Proxy = self
        for typ, name, tip in PROPS:
            if not hasattr(obj, name):
                obj.addProperty(typ, name, GROUP, tip)
        obj.Preset = list(PRESETS)
        obj.ChuckType = TYPES
        obj.setEditorMode("Notes", 1)
        self._presetting = False

    def onDocumentRestored(self, obj):
        self._presetting = True             # files saved before a type or preset was added
        try:
            if "Job" in obj.PropertiesList:     # an early version linked the Job (a cycle)
                job = obj.Job
                obj.removeProperty("Job")
                if "Stock" not in obj.PropertiesList:
                    obj.addProperty("App::PropertyLink", "Stock", GROUP, PROPS[0][2])
                obj.Stock = getattr(job, "Stock", None)
            kind, preset = obj.ChuckType, obj.Preset
            obj.ChuckType, obj.Preset = TYPES, list(PRESETS)
            obj.ChuckType = kind
            preset = OLD_NAMES.get(preset, preset)
            sizes = PRESETS.get(preset)
            now = (obj.ChuckType, obj.Diameter.Value, obj.BodyThickness.Value,
                   obj.JawLength.Value, obj.JawWidth.Value, obj.JawHeight.Value)
            if sizes is None or _differs(sizes, now):   # e.g. a preset whose sizes were corrected
                preset = CUSTOM
            obj.Preset = preset
        finally:
            self._presetting = False

    def onChanged(self, obj, prop):
        if getattr(self, "_presetting", False) or "Restore" in obj.State:
            return
        if prop == "Preset" and PRESETS.get(obj.Preset):
            self._presetting = True
            try:
                kind, a, b, h, j, k = PRESETS[obj.Preset]
                obj.ChuckType = kind
                obj.Diameter, obj.BodyThickness = a, b
                obj.JawLength, obj.JawWidth, obj.JawHeight = h, j, k
            finally:
                self._presetting = False
        elif prop in ("ChuckType", "Diameter", "BodyThickness", "JawLength", "JawWidth",
                      "JawHeight") and obj.Preset != CUSTOM:
            preset = PRESETS.get(obj.Preset)
            now = (obj.ChuckType, obj.Diameter.Value, obj.BodyThickness.Value, obj.JawLength.Value,
                   obj.JawWidth.Value, obj.JawHeight.Value)
            if preset and _differs(preset, now):
                self._presetting = True
                obj.Preset = CUSTOM
                self._presetting = False

    def execute(self, obj):
        shape, notes = build(obj)
        obj.Shape = shape
        obj.Notes = notes

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _differs(preset, now):
    return any((p != n if isinstance(p, str) else abs(p - n) > 1e-6) for p, n in zip(preset, now))


def job_of(obj):
    """The Job whose PolarChuck this chuck is (found through the links to it), or None."""
    for o in obj.InList:
        if getattr(o, "PolarChuck", None) == obj:
            return o
    return None


def stock_of(obj):
    job = job_of(obj)
    stock = getattr(job, "Stock", None) if job is not None else None
    if stock is None:
        stock = obj.Stock
    if stock is None or stock.Shape.isNull():
        return None
    if job is not None and getattr(job, "PolarLayout", "").startswith("Wrap"):
        return wrap_stock(job, stock.Shape)
    return stock.Shape


def wrap_stock(job, stock):
    """Wrap: the bar in the chuck is a cylinder of the wrap diameter along Z, over the stock's
    Z range (its lower end is the chuck end)."""
    d = getattr(job, "PolarWrapDiameter", None)
    r = d.Value / 2 if d is not None else 0.0
    bb = stock.BoundBox
    if r <= 0 or bb.ZLength <= 0:
        return None
    return Part.makeCylinder(r, bb.ZLength, App.Vector(0, 0, bb.ZMin))


def face_z(obj, stock=None):
    """Height of the chuck face / faceplate (the jaws and clamps stand on it)."""
    stock = stock if stock is not None else stock_of(obj)
    if stock is None:
        return 0.0
    sb = stock.BoundBox
    if obj.ChuckType == FACEPLATE:
        return sb.ZMin
    grip = min(obj.GripLength.Value, sb.ZLength)
    return sb.ZMin + min(grip - obj.JawHeight.Value, 0.0)


def contact_radius(section, angle):
    """Where a ray from the chuck axis in this direction last leaves the stock section, or None
    if it never meets it."""
    far = section.BoundBox.DiagonalLength + abs(section.BoundBox.XMax) + abs(section.BoundBox.YMax)
    z = section.BoundBox.ZMin
    ray = Part.makeLine(App.Vector(0, 0, z), App.Vector(far * math.cos(angle), far * math.sin(angle), z))
    hits = ray.common(section)
    if hits.isNull() or not hits.Edges:
        return None
    return max(v.Point.sub(App.Vector(0, 0, z)).Length for v in hits.Vertexes)


def _jaw(r_in, length, width, z0, height, angle, chamfer=0.0):
    box = Part.makeBox(length, width, height, App.Vector(r_in, -width / 2, z0))
    if chamfer > 0:                      # the look of a real jaw: its top edges broken
        try:
            top = [e for e in box.Edges if abs(e.BoundBox.ZMin - (z0 + height)) < 1e-6
                   and abs(e.BoundBox.ZMax - (z0 + height)) < 1e-6]
            box = box.makeChamfer(min(chamfer, width / 4, height / 4), top)
        except Exception:
            pass
    box.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), math.degrees(angle))
    return box


def _body(obj, z_face, n_jaws, first_angle):
    """The chuck body or faceplate as it looks: chamfered edges, the bore through it and, on a jaw
    chuck, the slots the jaws run in. A few simple booleans, made once per recompute."""
    r = obj.Diameter.Value / 2
    t = obj.BodyThickness.Value
    body = Part.makeCylinder(r, t, App.Vector(0, 0, z_face - t))
    try:
        ring = [e for e in body.Edges if e.Curve.__class__.__name__ == "Circle"]
        body = body.makeChamfer(min(1.5, r * 0.02 + 0.5, t / 6), ring)
    except Exception:
        pass
    bore = min(r * 0.24, max(r - 10.0, 1.0))
    cuts = [Part.makeCylinder(bore, t + 2, App.Vector(0, 0, z_face - t - 1))]
    if n_jaws:
        w = obj.JawWidth.Value + 2.0
        depth = min(3.0, t / 8)
        for k in range(n_jaws):
            slot = Part.makeBox(r + 2, w, depth + 1, App.Vector(0, -w / 2, z_face - depth))
            slot.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1),
                        math.degrees(first_angle) + 360.0 * k / n_jaws)
            cuts.append(slot)
    try:
        body = body.cut(Part.makeCompound(cuts))
    except Exception:
        pass
    return body


def build(obj):
    """The chuck solid and notes."""
    parts, notes = build_parts(obj)
    if not parts:
        return Part.Shape(), notes
    shape = parts[0]
    for p in parts[1:]:
        shape = shape.fuse(p)
    return shape.removeSplitter(), notes


def build_parts(obj):
    """[body, jaw or clamp, ...] and notes. The chuck face is where the stock bottom is, lowered
    by (jaw height - grip length) for jaw chucks."""
    notes = []
    stock = stock_of(obj)
    if stock is None:
        return [], ["No Job stock: the chuck cannot be placed."]
    sb = stock.BoundBox
    kind = obj.ChuckType
    grip = min(obj.GripLength.Value, sb.ZLength)
    jaw_h = obj.JawHeight.Value
    fz = face_z(obj, stock)
    if kind != FACEPLATE and grip > jaw_h + 1e-9:
        notes.append("Grip length %.1f is more than the jaw height %.1f: the jaws hold only %.1f."
                     % (grip, jaw_h, jaw_h))
    n = 0 if kind == FACEPLATE else (3 if kind == THREE_JAW else 4)
    parts = [_body(obj, fz, n, math.radians(obj.FirstJawAngle.Value))]
    if kind != FACEPLATE:
        z_grip = sb.ZMin + max(grip, 0.5) * 0.5
        wires = stock.slice(App.Vector(0, 0, 1), min(z_grip, sb.ZMax - 1e-3))
        section = Part.makeFace(wires, "Part::FaceMakerBullseye") if wires else None
        radii = []
        for k in range(n):
            a = math.radians(obj.FirstJawAngle.Value) + 2 * math.pi * k / n
            r = contact_radius(section, a) if section is not None else None
            if r is None:
                notes.append("Jaw %d (%.0f°) does not meet the stock." % (k + 1, math.degrees(a)))
                continue
            radii.append(r)
            if r + obj.JawLength.Value > obj.Diameter.Value / 2 + obj.JawLength.Value * 0.5:
                notes.append("Jaw %d would stand %.0f mm out of the chuck: the stock is too big for "
                             "this chuck." % (k + 1, r + obj.JawLength.Value - obj.Diameter.Value / 2))
            parts.append(_jaw(r, obj.JawLength.Value, obj.JawWidth.Value, fz, jaw_h, a, chamfer=1.0))
        if kind in SELF_CENTRING and radii and max(radii) - min(radii) > 0.05:
            notes.append("A self-centring chuck cannot hold this stock as it is placed: the jaws "
                         "would meet it at %s mm. Centre the stock on X0 Y0, turn the jaws "
                         "(First Jaw Angle) or use a 4-jaw chuck with independent jaws."
                         % ", ".join("%.2f" % r for r in radii))
        if radii and not notes:
            notes.append("Jaws closed on the stock at %s mm." % ", ".join("%.2f" % r for r in radii))
    for c in obj.Clamps:
        if isinstance(getattr(c, "Proxy", None), Clamp):      # built here, on this chuck's face
            parts.append(clamp_shape(c, fz))
        elif hasattr(c, "Shape") and not c.Shape.isNull():
            parts.append(c.Shape)
    return parts, notes


def obstacles_above(chuck, z):
    """The chuck parts that stand above height z (what a cutter at depth z must keep away from),
    or None."""
    if chuck is None or chuck.Shape.isNull():
        return None
    bb = chuck.Shape.BoundBox
    if bb.ZMax <= z + 1e-6:
        return None
    above = chuck.Shape.common(Part.makeBox(bb.XLength + 2, bb.YLength + 2, bb.ZMax - z + 1,
                                            App.Vector(bb.XMin - 1, bb.YMin - 1, z)))
    return above if above.Solids else None


def lowest_cut(path):
    """The lowest Z of the feed moves of a Path, or None."""
    z, low = None, None
    for cmd in path.Commands:
        if "Z" in cmd.Parameters:
            z = cmd.Parameters["Z"]
        if cmd.Name in ("G1", "G01", "G2", "G02", "G3", "G03") and z is not None:
            low = z if low is None else min(low, z)
    return low


def head_warning(chuck, path):
    """A word of warning when an operation cuts lower than the top of the jaws or clamps: the
    cutter keeps clear of them, but the collet nut / spindle above it is not checked."""
    if chuck is None or chuck.Shape.isNull() or path is None:
        return None
    low = lowest_cut(path)
    top = chuck.Shape.BoundBox.ZMax
    if low is None or low >= top - 1e-6:
        return None
    what = "clamps" if chuck.ChuckType == FACEPLATE else "jaws"
    return ("cuts down to Z %.2f, %.2f mm below the top of the %s (Z %.2f). The cutter keeps clear "
            "of them, the collet nut and spindle are not checked: the cutter must stick out of the "
            "nut more than %.1f mm." % (low, top - low, what, top, top - low))


# ---- clamps for a faceplate (or anywhere): a block you place by radius and angle -------------
CLAMP_PROPS = (
    ("App::PropertyLength", "Radius", "Distance of its inner end from the chuck axis."),
    ("App::PropertyAngle", "Angle", "Direction from the chuck axis."),
    ("App::PropertyLength", "Length", "Radial length."),
    ("App::PropertyLength", "Width", "Width."),
    ("App::PropertyLength", "Height", "Height above the chuck face / faceplate."),
    ("App::PropertyLength", "Overlap", "How far it reaches over the stock (a strap clamp); 0 for a "
     "stop or support beside it."),
)


class Clamp:
    def __init__(self, obj):
        obj.Proxy = self
        for typ, name, tip in CLAMP_PROPS:
            if not hasattr(obj, name):
                obj.addProperty(typ, name, "Clamp", tip)

    def onDocumentRestored(self, obj):
        if "Chuck" in obj.PropertiesList:      # an early version linked the chuck (a cycle)
            obj.removeProperty("Chuck")

    def execute(self, obj):
        # the chuck lists its clamps (and builds them itself); the clamp only finds its chuck
        # for its own shape, so that there is no link back
        chuck = next((o for o in obj.InList if obj in getattr(o, "Clamps", [])), None)
        obj.Shape = clamp_shape(obj, face_z(chuck) if chuck is not None else 0.0)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def clamp_shape(clamp, z0):
    return _jaw(clamp.Radius.Value, clamp.Length.Value, clamp.Width.Value, z0,
                clamp.Height.Value, math.radians(clamp.Angle.Value))


def make_chuck(job, preset="4-jaw SAN OU K72-125 independent (Ø125)"):
    doc = job.Document
    obj = doc.addObject("Part::FeaturePython", "PolarChuck")
    Chuck(obj)
    obj.Label = "Chuck"
    obj.Stock = job.Stock
    obj.Preset = preset
    obj.GripLength = 10
    if not hasattr(job, "PolarChuck"):
        job.addProperty("App::PropertyLink", "PolarChuck", "Polar CNC",
                        "The chuck or faceplate that holds the stock (Polar CNC).")
    job.PolarChuck = obj
    for op in getattr(job.Operations, "Group", []):      # Polar Face ops follow the chuck
        if "PolarChuck" in op.PropertiesList:
            op.PolarChuck = obj
    obj.recompute()
    return obj


def add_clamp(chuck, angle=None, length=30, width=20, height=20):
    """A clamp next to the stock in the given direction (or the next free quarter)."""
    doc = chuck.Document
    n = len(chuck.Clamps)
    if angle is None:
        angle = 45 + 90 * n
    obj = doc.addObject("Part::FeaturePython", "PolarClamp")
    Clamp(obj)
    obj.Label = "Clamp%d" % (n + 1)
    obj.Angle, obj.Length, obj.Width, obj.Height = angle, length, width, height
    stock = stock_of(chuck)
    obj.Overlap = 5
    r = 0
    if stock is not None:
        obj.Height = stock.BoundBox.ZLength + 8 if chuck.ChuckType == FACEPLATE else height
        sb = stock.BoundBox
        wires = stock.slice(App.Vector(0, 0, 1), sb.ZMin + min(1.0, sb.ZLength / 2))
        if wires:
            r = contact_radius(Part.makeFace(wires, "Part::FaceMakerBullseye"), math.radians(angle)) or 0
    obj.Radius = max(r - obj.Overlap.Value, 0)
    obj.recompute()
    chuck.Clamps = list(chuck.Clamps) + [obj]
    chuck.recompute()
    return obj
