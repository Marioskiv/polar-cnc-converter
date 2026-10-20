# Knurling & Wrap — test in a real FreeCAD (run by tests/freecad/run.sh).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Test "Σκαρίφημα σε κύλινδρο" (Wrap, Knurling & Wrap) inside a REAL FreeCAD (moved from WikiTips
with the tool, 2026-10-20; not Polar CNC's Polar Wrap machining, that is wrap_test.py).

    PC_OUT=/tmp/kw xvfb-run -a freecad tests/freecad/cyl_wrap_test.py

Clicks a cylinder, presses the button, checks the tangent sketch opens there,
writes text and a circle in it, closes it and checks the wrapped result for
the three modes; also a wrong selection and save + reopen.
Results: $PC_OUT/result.txt (+ wrap_*.png).
"""
import faulthandler
import math
import os
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher
from PySide import QtCore, QtWidgets

OUT = os.environ["PC_OUT"]
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8")
_fault = open(os.path.join(OUT, "crash.txt"), "w")
faulthandler.enable(_fault, all_threads=True)
V = App.Vector
failures = 0
FONT = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "C:/Windows/Fonts/arialbd.ttf") if os.path.isfile(f)), "")


def P(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


def check(ok, what):
    global failures
    if not ok:
        failures += 1
    P("OK  " if ok else "FAIL", what)


def pump(ms):
    t = QtCore.QElapsedTimer()
    t.start()
    while t.elapsed() < ms:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


def shot(name, fit=True):
    if fit:
        Gui.SendMsgToActiveView("ViewFit")
    pump(300)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "wrap_%s.png" % name))


def find_button(cmd):
    """The visible toolbar button of a command, or None."""
    for tb in Gui.getMainWindow().findChildren(QtWidgets.QToolBar):
        if not tb.isVisible():
            continue
        for btn in tb.findChildren(QtWidgets.QToolButton):
            a = btn.defaultAction()
            if btn.isVisible() and a is not None and a.objectName() == cmd:
                return btn
    return None


def run():
    from knurlwrap import knurl as wk
    from knurlwrap import wrap as ww
    mw = Gui.getMainWindow()
    mw.resize(1600, 1000)
    Gui.activateWorkbench("PartDesignWorkbench")
    pump(1500)
    check(find_button("KnurlWrap_Wrap") is not None, "Wrap button on the Part Design toolbar")

    doc = App.newDocument("Wrap")
    b = doc.addObject("PartDesign::Body", "Body")
    s = b.newObject("Sketcher::SketchObject", "Sketch")
    s.AttachmentSupport = [(b.Origin.OriginFeatures[3], "")]
    s.MapMode = "FlatFace"
    s.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 12))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = s
    pad.Length = 30
    doc.recompute()
    Gui.activeView().viewIsometric()
    pump(400)
    names = ["Face%d" % (i + 1) for i in range(len(pad.Shape.Faces))]
    side = next(n for n, f in zip(names, pad.Shape.Faces) if wk.cylinder_of(f))
    top = next(n for n, f in zip(names, pad.Shape.Faces) if not wk.cylinder_of(f))

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Pad", top, 0, 0, 30)
    Gui.runCommand("KnurlWrap_Wrap")
    pump(600)
    c = wk._TOLD
    check(c is not None and c.isVisible() and "κύλινδρο" in c.windowTitle(), "flat face: Greek message")
    check(doc.getObject("Wrap") is None, "flat face: nothing created")
    if c is not None:
        c.close()

    # click on the side, 12 mm radius, at 45° and 15 mm high
    px, py = 12 * math.cos(math.radians(45)), 12 * math.sin(math.radians(45))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Pad", side, px, py, 15)
    Gui.runCommand("KnurlWrap_Wrap")
    pump(1500)
    w, sk = doc.getObject("Wrap"), doc.getObject("WrapSketch")
    check(w is not None and sk is not None and w.TypeId == "PartDesign::FeaturePython", "Wrap + sketch in the Body")
    if w is None or sk is None:
        return
    vp = Gui.ActiveDocument.getInEdit()
    check(vp is not None and vp.Object == sk, "the sketch opens for drawing")
    o = sk.Placement.Base
    check(abs(math.hypot(o.x, o.y) - 12) < 1e-6 and abs(o.z - 15) < 1e-6 and
          abs(math.degrees(math.atan2(o.y, o.x)) - 45) < 1e-6, "sketch touches the cylinder where clicked (%s)" % o)
    check(len(sk.Geometry) == 4 and all(sk.getConstruction(i) for i in range(4)), "construction frame of the unrolled surface")
    rot = sk.Placement.Rotation
    xs, ys, zs = (rot.multVec(V(*a)) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    out = V(o.x, o.y, 0).normalize()
    check(ys.z > 0.999 and zs.dot(out) > 0.999 and abs(xs.cross(ys).dot(zs) - 1) < 1e-9,
          "sketch Y points up, Z out of the cylinder, not mirrored")
    shot("sketch_open", fit=False)

    # draw: text "CNC" and a circle, as the user would
    h = sk.addGeometry(Part.LineSegment(V(-10, -3, 0), V(10, -3, 0)), True)
    if FONT:
        sk.addConstraint(Sketcher.Constraint("Text", [h, 0], "CNC", FONT, False))
        sk.setTextAndFont(len(sk.Constraints) - 1, "CNC", FONT, False, False)
    sk.addGeometry(Part.Circle(V(16, 0, 0), V(0, 0, 1), 2))
    doc.recompute()
    pump(500)
    Gui.ActiveDocument.resetEdit()
    pump(800)
    doc.recompute()
    pump(1600)
    base = pad.Shape.Volume
    check("Invalid" not in w.State and w.Shape.isValid() and len(w.Shape.Solids) == 1,
          "engraved text + circle: one valid solid (%s)" % w.getStatusString())
    check(w.Shape.Volume < base - 5, "material cut %.1f mm³" % (base - w.Shape.Volume))
    check(b.Tip == w, "Wrap is the Tip")
    Gui.Selection.clearSelection()
    sk.ViewObject.Visibility = False
    shot("engrave")
    w.Mode = "Ανάγλυφο"
    doc.recompute()
    check(w.Shape.isValid() and w.Shape.Volume > base + 5, "raised: material added %.1f mm³" % (w.Shape.Volume - base))
    shot("raised")
    w.Mode = "Μέχρι τον άξονα"
    doc.recompute()
    check(w.Shape.isValid() and w.Shape.Volume < base - 50, "down to the axis")
    w.Mode = "Χάραξη"
    doc.recompute()

    # where does a drawing land? a 2x2 square at sketch (8, 5) must be cut 5 mm higher and
    # 8 mm along the surface towards sketch +X (catches upside-down or mirrored wraps)
    d3 = App.newDocument("Where")
    b3 = d3.addObject("PartDesign::Body", "Body")
    s3 = b3.newObject("Sketcher::SketchObject", "Sketch")
    s3.AttachmentSupport = [(b3.Origin.OriginFeatures[3], "")]
    s3.MapMode = "FlatFace"
    s3.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 12))
    p3 = b3.newObject("PartDesign::Pad", "Pad")
    p3.Profile = s3
    p3.Length = 30
    d3.recompute()
    f3 = next(f for f in p3.Shape.Faces if wk.cylinder_of(f))
    w3, k3 = ww.make_wrap(p3, f3, V(12, 0, 15))
    sq = [V(7, 4, 0), V(9, 4, 0), V(9, 6, 0), V(7, 6, 0)]
    for i in range(4):
        k3.addGeometry(Part.LineSegment(sq[i], sq[(i + 1) % 4]))
    d3.recompute()
    com = p3.Shape.cut(w3.Shape).Solids[0].CenterOfMass
    xs = k3.Placement.Rotation.multVec(V(1, 0, 0))
    ang = math.degrees(math.atan2(com.y, com.x))
    want = math.degrees(8 / 12.0) * (1 if xs.y > 0 else -1)
    check(abs(com.z - 20) < 0.2 and abs(ang - want) < 1.0,
          "drawing lands where drawn (z %.2f want 20, angle %.1f want %.1f)" % (com.z, ang, want))
    App.closeDocument(d3.Name)

    path = os.path.join(OUT, "wrap.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    pump(500)
    d2 = App.openDocument(path)
    pump(800)
    w = d2.getObject("Wrap")
    check(w is not None and isinstance(w.Proxy, ww.Wrap) and isinstance(w.ViewObject.Proxy, ww.ViewProviderWrap),
          "reopened file keeps the Wrap")
    d2.getObject("Pad").Length = 40      # an edit upstream: the wrap follows
    d2.recompute()
    check("Invalid" not in w.State and w.Shape.isValid(), "Wrap recomputes after an upstream edit")


try:
    run()
except Exception:
    failures += 1
    P("FAIL exception:\n" + traceback.format_exc())
P("RESULT:", "PASS" if failures == 0 else "%d FAILURES" % failures)
log.close()
os._exit(0)
