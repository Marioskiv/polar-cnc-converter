# Knurling & Wrap — Hole: a round hole at a clicked point of any surface (Part Design).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Hole on any surface (asked by Marios 2026-10-22: "open holes in every solid without effort").

Click the part where the hole goes (a flat face, a cylinder, the teeth of a pulley, any curved
face) and press the button: a round hole is drilled there, square to the surface at that point.
The drill comes from outside the part, so whatever lies above the point on the hole's line is cut
too, like a real drill; it stops at the depth asked, at the first empty space it meets (the
default: through the wall, e.g. into a pulley's bore) or goes right through.

Some features leave a solid that looks fine but makes every later cut fail ("result is empty"):
a Part Design Hole with "Model Thread" ticked is one (checked on Marios's HTD 5M pulley in
FreeCAD 26.3). The command tests the cut first; when the last solid is broken it puts the hole
just before the first feature that breaks it, and says so.
"""

import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the cad folder
ICON = os.path.join(HERE, "Resources", "Hole.svg")
MODES = ["Ως το πρώτο κενό", "Βάθος", "Διαμπερής"]
V = App.Vector


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def point_and_normal(face, point):
    """The point exactly on the face and the face's outward normal there (out of the material)."""
    u, v = face.Surface.parameter(V(point))
    p = face.Surface.value(u, v)
    n = V(face.normalAt(u, v))         # normalAt follows the face's orientation: out of the solid
    return V(p), n.normalize()


def _diag(shape):
    return max(shape.BoundBox.DiagonalLength, 1.0)


def first_exit(shape, point, direction):
    """Distance from `point` along `direction` to where the line first leaves the material
    (None when it never enters it)."""
    far = 2 * _diag(shape) + (point - shape.BoundBox.Center).Length
    ray = Part.LineSegment(point - direction * 0.01, point + direction * far).toShape()
    inside = ray.common(shape)
    ends = []
    for e in inside.Edges:
        a, b = (e.Vertexes[0].Point - point).dot(direction), (e.Vertexes[-1].Point - point).dot(direction)
        ends.append((min(a, b), max(a, b)))
    ends.sort()
    if not ends:
        return None
    reach = ends[0][1]
    for a, b in ends[1:]:              # touching pieces (split at a seam) are one piece
        if a > reach + 1e-6:
            break
        reach = max(reach, b)
    return reach


def hole_tool(shape, point, direction, diameter, mode, depth):
    """The cylinder that is cut: it starts outside the part and ends at the hole's bottom."""
    out = 2 * _diag(shape) + (point - shape.BoundBox.Center).Length
    if mode == "Διαμπερής":
        length = out
    elif mode == "Βάθος":
        length = depth
    else:
        length = first_exit(shape, point, direction)
        if length is None:
            return None
        length += 0.01                 # a hair past the far wall: no skin left
    if length <= 0:
        return None
    return Part.makeCylinder(diameter / 2.0, out + length, point - direction * out, direction)


def cut_ok(shape, tool, result):
    """True when the cut looks right. A broken solid gives a valid-looking result that has lost
    (almost) all of its material, or one that lost more than the drill can take."""
    if result is None or result.isNull() or not result.Solids or not result.isValid():
        return False
    removed = shape.Volume - result.Volume
    return -1e-6 <= removed <= tool.Volume * 1.001 + 1e-6 and result.Volume > 1e-6


def drill(shape, point, direction, diameter, mode, depth):
    """(result, why): the solid with the hole, or (None, reason)."""
    tool = hole_tool(shape, point, direction, diameter, mode, depth)
    if tool is None:
        return None, "miss"
    try:
        result = shape.cut(tool)
    except Exception:
        return None, "broken"
    if not cut_ok(shape, tool, result):
        return None, "broken"
    if len(result.Solids) == 1:
        result = result.Solids[0]
    return result, ""


def _base_shape(obj):
    base = getattr(obj, "BaseFeature", None) or getattr(obj, "Base", None)
    return base.Shape if base is not None and not base.Shape.isNull() else None


def chain(feature):
    """The features under `feature` in its Body, last first (feature itself included)."""
    out = []
    while feature is not None and feature not in out:
        out.append(feature)
        feature = getattr(feature, "BaseFeature", None)
    return out


def inward(shape, point, direction):
    """`direction`, or its opposite when the material is on the other side of the point (the
    normal of a face of a broken solid can point into the material)."""
    e = min(0.05, _diag(shape) * 1e-3)
    if not shape.isInside(point + direction * e, 1e-7, True) and shape.isInside(point - direction * e, 1e-7, True):
        return -direction
    return direction


def healthy_place(tip, point, direction, diameter, mode, depth):
    """(feature to put the hole after, the feature that breaks the solid or None, direction).

    Walks back from the Tip until the hole cuts right."""
    breaker = None
    for f in chain(tip):
        if f.Shape.isNull() or not f.Shape.Solids:
            break
        d = inward(f.Shape, point, direction)
        res, _why = drill(f.Shape, point, d, diameter, mode, depth)
        if res is not None:
            return f, breaker, d
        breaker = f
    return None, breaker, direction


BROKEN = ("Η τρύπα δεν βγαίνει",
          "Το στερεό πριν από την τρύπα είναι χαλασμένο: κάθε κόψιμο σε αυτό αποτυγχάνει.",
          ["Αν πριν από την τρύπα υπάρχει Hole με σπείρωμα, άνοιξέ το και βγάλε το τικ από το "
           "«Model Thread».",
           "Ή σύρε την τρύπα (HoleOnSurface) στο δέντρο πιο πάνω, πριν από το χαλασμένο βήμα."])
MISS = ("Η τρύπα δεν βγαίνει",
        "Στο σημείο αυτό, προς τα μέσα, δεν υπάρχει υλικό να τρυπηθεί.",
        ["Άνοιξε την τρύπα (διπλό κλικ) και διάλεξε «Βάθος» ή «Διαμπερής».",
         "Ή κάνε κλικ σε άλλο σημείο του κομματιού και ξαναπάτα το κουμπί."])


class HoleOnSurface:
    def __init__(self, obj):
        obj.Proxy = self
        add = obj.addProperty
        add("App::PropertyLength", "Diameter", "Hole", "Διάμετρος της τρύπας")
        obj.Diameter = 3.0
        add("App::PropertyEnumeration", "Mode", "Hole",
            "Ως το πρώτο κενό: περνά τον τοίχο και σταματά. Βάθος: όσο λες. Διαμπερής: από άκρη σε άκρη.")
        obj.Mode = MODES
        add("App::PropertyLength", "Depth", "Hole", "Βάθος από την επιφάνεια (μόνο για «Βάθος»)")
        obj.Depth = 5.0
        add("App::PropertyVector", "Point", "Position", "Το σημείο της επιφάνειας όπου ανοίγει η τρύπα")
        add("App::PropertyVector", "Direction", "Position", "Η κατεύθυνση της τρύπας (προς τα μέσα)")

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def execute(self, obj):
        base = _base_shape(obj)
        if base is None:
            raise RuntimeError("Hole: no base solid")
        direction = V(obj.Direction)
        if direction.Length < 1e-9:
            raise RuntimeError("Hole: no direction")
        result, why = drill(base, V(obj.Point), direction.normalize(), obj.Diameter.Value,
                            obj.Mode, obj.Depth.Value)
        if result is None:
            from .knurl import explain
            explain(*(MISS if why == "miss" else BROKEN))
            raise RuntimeError("Hole: " + ("nothing to drill here" if why == "miss" else
                                           "the solid before the hole is broken"))
        obj.Shape = result


def make_hole(face_owner, face, point, diameter=3.0, mode=MODES[0], depth=5.0):
    """Create the hole at `point` of `face` (a face of face_owner's shape).

    In a Body it is put after the Tip, or before the first feature that breaks the solid.
    Returns (hole, the feature it had to go before, or None)."""
    doc = face_owner.Document
    p, n = point_and_normal(face, point)
    d = -n
    body = next((o for o in face_owner.InList if o.TypeId == "PartDesign::Body"), None)
    breaker = None
    if body is not None:
        tip = body.Tip or face_owner
        after, breaker, d = healthy_place(tip, p, d, diameter, mode, depth)
        # PartDesign::FeatureSubtractivePython crashes 26.3 with the GUI up: use the plain one
        obj = doc.addObject("PartDesign::FeaturePython", "HoleOnSurface")
        HoleOnSurface(obj)
        if after is None or after == tip:   # healthy, or broken everywhere (execute explains)
            body.addObject(obj)
            breaker = None
        else:
            body.insertObject(obj, after, True)
    else:
        d = inward(face_owner.Shape, p, d)
        obj = doc.addObject("Part::FeaturePython", "HoleOnSurface")
        HoleOnSurface(obj)
        obj.addProperty("App::PropertyLink", "Base", "Hole", "Το στερεό")
        obj.Base = face_owner
    obj.Diameter, obj.Mode, obj.Depth = diameter, mode, depth
    obj.Point, obj.Direction = p, d
    doc.recompute()
    return obj, breaker


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

    class TaskHole:
        def __init__(self, obj):
            self.obj = obj
            self.old = (obj.Diameter.Value, obj.Mode, obj.Depth.Value)
            self.form = QtWidgets.QWidget()
            self.form.setWindowTitle("Τρύπα σε επιφάνεια")
            lay = QtWidgets.QFormLayout(self.form)
            self.dia = QtWidgets.QDoubleSpinBox()
            self.dia.setRange(0.1, 500)
            self.dia.setDecimals(2)
            self.dia.setSingleStep(0.5)
            self.dia.setSuffix(" mm")
            self.dia.setValue(obj.Diameter.Value)
            self.mode = QtWidgets.QComboBox()
            self.mode.addItems(MODES)
            self.mode.setCurrentText(obj.Mode)
            self.mode.setToolTip("Ως το πρώτο κενό: περνά τον τοίχο και σταματά (π.χ. ως την κεντρική "
                                 "τρύπα). Βάθος: όσο λες. Διαμπερής: από άκρη σε άκρη.")
            self.depth = QtWidgets.QDoubleSpinBox()
            self.depth.setRange(0.1, 1000)
            self.depth.setDecimals(2)
            self.depth.setSuffix(" mm")
            self.depth.setValue(obj.Depth.Value)
            lay.addRow("Διάμετρος", self.dia)
            lay.addRow("Μέχρι πού", self.mode)
            lay.addRow("Βάθος", self.depth)
            self.depth.setEnabled(obj.Mode == "Βάθος")
            self.dia.valueChanged.connect(self.preview)
            self.mode.currentIndexChanged.connect(self.preview)
            self.depth.valueChanged.connect(self.preview)

        def preview(self, *args):
            try:
                self.obj.Diameter = self.dia.value()
                self.obj.Mode = self.mode.currentText()
                self.obj.Depth = self.depth.value()
                self.depth.setEnabled(self.obj.Mode == "Βάθος")
                self.obj.Document.recompute()
            except Exception:
                pass

        def accept(self):
            self.preview()
            Gui.ActiveDocument.resetEdit()
            return True

        def reject(self):
            self.obj.Diameter, self.obj.Mode, self.obj.Depth = self.old
            self.obj.Document.recompute()
            Gui.ActiveDocument.resetEdit()
            return True

    class ViewProviderHole:
        def __init__(self, vobj):
            vobj.Proxy = self

        def attach(self, vobj):
            self.Object = vobj.Object

        def getIcon(self):
            return ICON

        def claimChildren(self):
            b = getattr(self.Object, "Base", None)
            return [b] if b is not None else []

        def setEdit(self, vobj, mode=0):
            if mode != 0:
                return None
            Gui.Control.showDialog(TaskHole(vobj.Object))
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
        """(owner, face, picked point) of the clicked face, or (None, reason, None)."""
        for s in Gui.Selection.getSelectionEx("", 0):
            for name, sub, pt in zip(s.SubElementNames, s.SubObjects, s.PickedPoints or [None] * 99):
                if not name.split(".")[-1].startswith("Face"):
                    continue
                owner = s.Object.Tip if s.Object.TypeId == "PartDesign::Body" else s.Object
                if owner is None:
                    return None, "none", None
                if pt is None:
                    u0, u1, v0, v1 = sub.ParameterRange
                    pt = sub.valueAt((u0 + u1) / 2, (v0 + v1) / 2)
                return owner, sub, V(pt)
        return None, "none", None

    class HoleCommand:
        def GetResources(self):
            return {"Pixmap": ICON, "MenuText": "Τρύπα σε επιφάνεια",
                    "ToolTip": "Κλικ στο κομμάτι εκεί που θέλεις την τρύπα (σε οποιαδήποτε επιφάνεια, "
                               "και καμπύλη), μετά το κουμπί: τρύπα κάθετα στην επιφάνεια."}

        def IsActive(self):
            return App.ActiveDocument is not None

        def Activated(self):
            owner, face, point = _picked()
            if owner is None:
                wk._tell("Κάνε κλικ στο κομμάτι", "Δεν έχεις κάνει κλικ σε επιφάνεια.",
                         ["Κάνε κλικ στο κομμάτι, ακριβώς εκεί που θέλεις την τρύπα.",
                          "Μετά πάτα το κουμπί «Τρύπα σε επιφάνεια»."])
                return
            doc = owner.Document
            doc.openTransaction("Hole on surface")
            obj, breaker = make_hole(owner, face, point)
            if obj.ViewObject is not None:
                ViewProviderHole(obj.ViewObject)
            if getattr(obj, "Base", None) is not None and obj.Base.ViewObject is not None:
                obj.Base.ViewObject.Visibility = False
            doc.commitTransaction()
            Gui.Selection.clearSelection()
            if breaker is not None:
                wk._tell("Η τρύπα μπήκε πιο πριν στο δέντρο",
                         "Το «%s» χαλάει το στερεό (μετά από αυτό κανένα κόψιμο δεν πετυχαίνει), γι' αυτό "
                         "η τρύπα μπήκε πριν από αυτό." % breaker.Label,
                         ["Δεν χρειάζεται να κάνεις τίποτα: η τρύπα και το «%s» είναι και τα δύο στο "
                          "κομμάτι." % breaker.Label,
                          "Αν το «%s» είναι Hole με σπείρωμα, το «Model Thread» το χαλάει." % breaker.Label])
            Gui.ActiveDocument.setEdit(obj.Name)

    def install():
        Gui.addCommand("KnurlWrap_Hole", HoleCommand())
