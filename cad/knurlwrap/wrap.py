# Knurling & Wrap — Wrap: draw on a cylinder (Part Design).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Wrap: draw on a cylinder (moved from WikiTips 2026-10-20). Not the Polar Wrap machining
operation of Polar CNC: this one changes the 3D part.

Click the outside of a cylinder where you want the drawing and press the
button: a flat sketch opens there, touching the cylinder (X goes around, Y goes
along the axis; a construction frame shows the whole unrolled surface). Draw
text, shapes or holes; when the sketch is closed they are wrapped exactly
around the cylinder and become raised (Ανάγλυφο), cut in (Χάραξη) or cut down
to the axis (Μέχρι τον άξονα).

How: every sketch edge is turned into a B-spline whose poles are mapped to the
cylinder's own coordinates (angle = x / R, height = y). That mapping is linear,
so the wrap is exact: lengths along the surface stay the same. The faces on
the cylinder are thickened with an offset (an offset of a cylinder is a
cylinder) and fused to or cut from the solid. Checked in FreeCAD 26.3.
"""

import math
import os

import FreeCAD as App
import Part

from .knurl import cylinder_of, find_cylinder, is_outer, upwards

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the cad folder
ICON = os.path.join(HERE, "Resources", "Wrap.svg")
MODES = ["Χάραξη", "Ανάγλυφο", "Μέχρι τον άξονα"]
V = App.Vector


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def cylinder_surface(center, axis, radius):
    s = Part.Cylinder()
    s.Radius = radius
    s.Center = center
    s.Axis = axis
    return s


def frame_at(surf, point):
    """(u, v, x direction, y direction, normal) of the tangent sketch at a point of the cylinder."""
    u, v = surf.parameter(point)
    du, dv = surf.tangent(u, v)
    n = surf.normal(u, v)
    return u, v, V(du).normalize(), V(dv).normalize(), V(n).normalize()


def sketch_placement(surf, point):
    """Placement of a sketch touching the cylinder at `point`.

    Y goes along the axis, pointing up; Z points out of the cylinder; X = Y x Z,
    so the sketch is a normal right-handed one (text is never mirrored).
    """
    u, v = surf.parameter(point)
    p = surf.value(u, v)
    up = upwards(V(surf.Center), V(surf.Axis), 0, 0)[1]
    radial = p - V(surf.Center)
    n = (radial - up * radial.dot(up)).normalize()
    x = up.cross(n)
    m = App.Matrix(x.x, up.x, n.x, 0, x.y, up.y, n.y, 0, x.z, up.z, n.z, 0, 0, 0, 0, 1)
    return App.Placement(p, App.Rotation(m))


def _wrap_edge(edge, surf, R, u0, v0, sx, sy):
    bs = edge.Curve.toBSpline(edge.FirstParameter, edge.LastParameter)
    poles = [App.Base.Vector2d(u0 + sx * p.x / R, v0 + sy * p.y) for p in bs.getPoles()]
    c2 = Part.Geom2d.BSplineCurve2d()
    c2.buildFromPolesMultsKnots(poles, bs.getMultiplicities(), bs.getKnots(), bs.isPeriodic(),
                                bs.Degree, bs.getWeights())
    return c2.toShape(surf, c2.FirstParameter, c2.LastParameter)


def _face_on(surf, wire):
    f = Part.Face(surf, wire)
    if f.Area > 1e9:          # wire went the wrong way round: OCC took the outside
        f = Part.Face(surf, wire.reversed())
    return f


def wrapped_faces(flat_shape, surf, u0, v0, sx=1.0, sy=1.0):
    """Faces on the cylinder for the closed shapes of a flat sketch shape (sketch coordinates)."""
    R = surf.Radius
    wires = [w for w in flat_shape.Wires if w.isClosed()]
    if not wires:
        return []
    flat = Part.makeFace(wires, "Part::FaceMakerBullseye")
    out = []
    for ff in flat.Faces:
        faces = [_face_on(surf, Part.Wire([_wrap_edge(e, surf, R, u0, v0, sx, sy) for e in w.OrderedEdges]))
                 for w in ff.Wires]
        f = faces[0]
        for hole in faces[1:]:
            f = f.cut(hole)
        out += f.Faces
    return out


def wrap_solid(faces, depth, mode, radius):
    """The solid to fuse (raised) or cut (cut in / down to the axis)."""
    if mode == "Ανάγλυφο":
        h = depth
    elif mode == "Μέχρι τον άξονα":
        h = -(radius - 1e-3)
    else:
        h = -depth
    solids = [f.makeOffsetShape(h, 1e-6, fill=True) for f in faces]
    return solids[0] if len(solids) == 1 else Part.makeCompound(solids)


# --------------------------------------------------------------------------
# the feature
# --------------------------------------------------------------------------
def _base_shape(obj):
    base = getattr(obj, "BaseFeature", None) or getattr(obj, "Base", None)
    return base.Shape if base is not None and not base.Shape.isNull() else None


class Wrap:
    def __init__(self, obj):
        obj.Proxy = self
        add = obj.addProperty
        add("App::PropertyLink", "Sketch", "Wrap", "Το σκαρίφημα που τυλίγεται στον κύλινδρο")
        add("App::PropertyEnumeration", "Mode", "Wrap", "Χάραξη, Ανάγλυφο ή κόψιμο μέχρι τον άξονα")
        obj.Mode = MODES
        add("App::PropertyLength", "Depth", "Wrap", "Βάθος χάραξης ή ύψος ανάγλυφου")
        obj.Depth = 1.0
        for name in ("AxisCenter", "AxisDirection"):
            add("App::PropertyVector", name, "Cylinder", "Ο κύλινδρος (αποθηκεύεται ως αριθμοί)")
        add("App::PropertyLength", "Radius", "Cylinder", "Ακτίνα του κυλίνδρου")
        for name in ("AxisCenter", "AxisDirection", "Radius"):
            obj.setEditorMode(name, 1)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        base = _base_shape(obj)
        sk = obj.Sketch
        if base is None or sk is None:
            raise RuntimeError("Wrap: no base solid or no sketch")
        axis = V(obj.AxisDirection).normalize()
        center = V(obj.AxisCenter)
        cyl = find_cylinder(base, center, axis, obj.Radius.Value)
        radius = cyl[2] if cyl else obj.Radius.Value
        surf = cylinder_surface(center, axis, radius)
        pl = sk.Placement
        u0, v0, xd, yd, n = frame_at(surf, pl.Base)
        sx = 1.0 if pl.Rotation.multVec(V(1, 0, 0)).dot(xd) >= 0 else -1.0
        sy = 1.0 if pl.Rotation.multVec(V(0, 1, 0)).dot(yd) >= 0 else -1.0
        flat = sk.Shape.copy()
        flat.transformShape(pl.inverse().toMatrix())   # sketch coordinates (z = 0)
        faces = wrapped_faces(flat, surf, u0, v0, sx, sy)
        if not faces:
            from .knurl import explain
            explain("Το σχέδιο στον κύλινδρο δεν βγαίνει",
                    "Το σκαρίφημα δεν έχει κλειστά σχήματα. Οι διακεκομμένες γραμμές (το πλαίσιο) δεν "
                    "μετράνε.",
                    ["Άνοιξε το WrapSketch (διπλό κλικ) και σχεδίασε κλειστά σχήματα ή γράμματα μέσα "
                     "στο πλαίσιο.",
                     "Ένωσε τα άκρα με τον περιορισμό Coincident (σύμπτωση σημείων)."])
            raise RuntimeError("Wrap: the sketch has no closed shapes")
        tool = wrap_solid(faces, obj.Depth.Value, obj.Mode, radius)
        result = base.fuse(tool) if obj.Mode == "Ανάγλυφο" else base.cut(tool)
        if len(result.Solids) == 1:
            result = result.Solids[0]
        obj.Shape = result


def make_wrap(face_owner, face, point, doc=None):
    """Create the tangent sketch at `point` and the Wrap feature that uses it."""
    doc = doc or face_owner.Document
    center, axis, radius, vmin, vmax = cylinder_of(face)
    surf = cylinder_surface(center, axis, radius)
    body = next((o for o in face_owner.InList if o.TypeId == "PartDesign::Body"), None)
    if body is not None:
        sk = body.newObject("Sketcher::SketchObject", "WrapSketch")
    else:
        sk = doc.addObject("Sketcher::SketchObject", "WrapSketch")
    sk.MapMode = "Deactivated"
    sk.Placement = sketch_placement(surf, point)
    # construction frame = the whole surface unrolled; the solid line is where the sketch touches
    u, v = surf.parameter(point)
    w = 2 * math.pi * radius
    up = sk.Placement.Rotation.multVec(V(0, 1, 0))
    y0, y1 = sorted(((vv - v) * axis).dot(up) for vv in (vmin, vmax))
    corners = [V(-w / 2, y0, 0), V(w / 2, y0, 0), V(w / 2, y1, 0), V(-w / 2, y1, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(corners[i], corners[(i + 1) % 4]), True)
    if body is not None:
        # PartDesign::FeatureSubtractivePython crashes 26.3 with the GUI up: use the plain one
        obj = doc.addObject("PartDesign::FeaturePython", "Wrap")
        body.addObject(obj)
    else:
        obj = doc.addObject("Part::FeaturePython", "Wrap")
        obj.addProperty("App::PropertyLink", "Base", "Wrap", "Το στερεό")
        obj.Base = face_owner
    Wrap(obj)
    obj.Sketch = sk
    obj.AxisCenter, obj.AxisDirection, obj.Radius = center, axis, radius
    return obj, sk


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
if App.GuiUp:
    import FreeCADGui as Gui
    from PySide import QtGui

    try:
        from PySide import QtWidgets
    except ImportError:  # pragma: no cover
        QtWidgets = QtGui

    from . import knurl as wk

    class TaskWrap:
        def __init__(self, obj):
            self.obj = obj
            self.form = QtWidgets.QWidget()
            self.form.setWindowTitle("Σκαρίφημα σε κύλινδρο")
            lay = QtWidgets.QFormLayout(self.form)
            self.mode = QtWidgets.QComboBox()
            self.mode.addItems(MODES)
            self.mode.setCurrentText(obj.Mode)
            self.mode.setToolTip("Χάραξη: κόβει μέσα. Ανάγλυφο: βγαίνει έξω. Μέχρι τον άξονα: κόβει όλο το βάθος.")
            self.depth = QtWidgets.QDoubleSpinBox()
            self.depth.setRange(0.05, 100)
            self.depth.setDecimals(2)
            self.depth.setSingleStep(0.1)
            self.depth.setSuffix(" mm")
            self.depth.setValue(obj.Depth.Value)
            lay.addRow("Τρόπος", self.mode)
            lay.addRow("Βάθος / ύψος", self.depth)
            btn = QtWidgets.QPushButton("Άνοιξε το σκαρίφημα")
            btn.clicked.connect(self.edit_sketch)
            lay.addRow(btn)
            self.mode.currentIndexChanged.connect(self.preview)
            self.depth.valueChanged.connect(self.preview)

        def preview(self, *args):
            try:
                self.obj.Mode = self.mode.currentText()
                self.obj.Depth = self.depth.value()
                self.depth.setEnabled(self.obj.Mode != "Μέχρι τον άξονα")
                self.obj.Document.recompute()
            except Exception:
                pass

        def edit_sketch(self):
            sk = self.obj.Sketch
            Gui.Control.closeDialog()
            Gui.ActiveDocument.resetEdit()
            Gui.ActiveDocument.setEdit(sk.Name)

        def accept(self):
            self.preview()
            Gui.ActiveDocument.resetEdit()
            return True

        def reject(self):
            Gui.ActiveDocument.resetEdit()
            return True

    class ViewProviderWrap:
        def __init__(self, vobj):
            vobj.Proxy = self

        def attach(self, vobj):
            self.Object = vobj.Object

        def getIcon(self):
            return ICON

        def claimChildren(self):
            o = self.Object
            return [x for x in (getattr(o, "Base", None), o.Sketch) if x is not None]

        def setEdit(self, vobj, mode=0):
            if mode != 0:
                return None
            Gui.Control.showDialog(TaskWrap(vobj.Object))
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

    def _picked():
        """(owner, face, picked point) of the clicked cylinder, or (None, reason, None)."""
        for s in Gui.Selection.getSelectionEx("", 0):
            for name, sub, pt in zip(s.SubElementNames, s.SubObjects, s.PickedPoints or [None] * 99):
                if not name.split(".")[-1].startswith("Face"):
                    continue
                owner = s.Object.Tip if s.Object.TypeId == "PartDesign::Body" else s.Object
                if cylinder_of(sub) is None:
                    return None, "flat", None
                if not is_outer(sub):
                    return None, "inner", None
                if pt is None:
                    u0, u1, v0, v1 = sub.ParameterRange
                    pt = sub.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
                else:
                    pt = sub.Surface.value(*sub.Surface.parameter(V(pt)))   # exactly on the surface
                return owner, sub, V(pt)
        return None, "none", None

    class WrapCommand:
        def GetResources(self):
            return {"Pixmap": ICON, "MenuText": "Σκαρίφημα σε κύλινδρο",
                    "ToolTip": "Κλικ στον κύλινδρο εκεί που θέλεις το σχέδιο, μετά το κουμπί: "
                               "γράμματα, σχήματα ή τρύπες τυλιγμένα γύρω του."}

        def IsActive(self):
            return App.ActiveDocument is not None

        def Activated(self):
            owner, face, point = _picked()
            if owner is None:
                why = {"none": "Δεν έχεις κάνει κλικ σε επιφάνεια.",
                       "flat": "Η επιφάνεια που διάλεξες δεν είναι κυλινδρική.",
                       "inner": "Διάλεξες το εσωτερικό μιας τρύπας: το σχέδιο μπαίνει απ' έξω."}[face]
                wk._tell("Κάνε κλικ στον κύλινδρο", why,
                         ["Κάνε κλικ στην εξωτερική πλευρά του κυλίνδρου, εκεί που θέλεις το σχέδιο.",
                          "Μετά πάτα το κουμπί «Σκαρίφημα σε κύλινδρο»."])
                return
            doc = owner.Document
            doc.openTransaction("Wrap")
            obj, sk = make_wrap(owner, face, point)
            if obj.ViewObject is not None:
                ViewProviderWrap(obj.ViewObject)
            if getattr(obj, "Base", None) is not None and obj.Base.ViewObject is not None:
                obj.Base.ViewObject.Visibility = False
            doc.commitTransaction()
            Gui.Selection.clearSelection()
            Gui.ActiveDocument.setEdit(sk.Name)

    def install():
        Gui.addCommand("KnurlWrap_Wrap", WrapCommand())
