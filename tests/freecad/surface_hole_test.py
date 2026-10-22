# Knurling & Wrap — test in a real FreeCAD (run by tests/freecad/run.sh).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Test "Τρύπα σε επιφάνεια" (Hole on any surface, Knurling & Wrap) inside a REAL FreeCAD.

    PC_OUT=/tmp/kw xvfb-run -a freecad tests/freecad/surface_hole_test.py

Clicks a part and presses the button: on the flat top, on the side of a cylinder, on a slanted
face; the three depth modes; the panel; a part whose solid was broken by a Part Design Hole with
"Model Thread" (Marios's pulley, 2026-10-22): the hole must go before it; a plain Part solid;
save + reopen. Results: $PC_OUT/result.txt (+ hole_*.png).
"""
import faulthandler
import math
import os
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets

OUT = os.environ["PC_OUT"]
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8")
_fault = open(os.path.join(OUT, "crash.txt"), "w")
faulthandler.enable(_fault, all_threads=True)
V = App.Vector
failures = 0


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


def shot(name):
    Gui.SendMsgToActiveView("ViewFit")
    pump(300)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "hole_%s.png" % name))


def find_button(cmd):
    for tb in Gui.getMainWindow().findChildren(QtWidgets.QToolBar):
        if not tb.isVisible():
            continue
        for btn in tb.findChildren(QtWidgets.QToolButton):
            a = btn.defaultAction()
            if btn.isVisible() and a is not None and a.objectName() == cmd:
                return btn
    return None


def cylinder_body(doc, r=12, h=30, bore=0):
    b = doc.addObject("PartDesign::Body", "Body")
    s = b.newObject("Sketcher::SketchObject", "Sketch")
    s.AttachmentSupport = [(b.Origin.OriginFeatures[3], "")]
    s.MapMode = "FlatFace"
    s.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), r))
    if bore:
        s.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), bore))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = s
    pad.Length = h
    doc.recompute()
    return b, pad


def face_name(obj, test):
    return next("Face%d" % (i + 1) for i, f in enumerate(obj.Shape.Faces) if test(f))


def click(doc, obj, face, p):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, obj.Name, face, p.x, p.y, p.z)
    Gui.runCommand("KnurlWrap_Hole")
    pump(1200)


def close_panel():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    Gui.ActiveDocument.resetEdit()
    pump(300)


class InsideOut:
    """A feature that leaves a broken solid: its base turned inside out."""
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        s = obj.BaseFeature.Shape.copy()
        s.reverse()
        obj.Shape = s


def run():
    from knurlwrap import hole as wh
    from knurlwrap import knurl as wk
    mw = Gui.getMainWindow()
    mw.resize(1600, 1000)
    Gui.activateWorkbench("PartDesignWorkbench")
    pump(1500)
    check(find_button("KnurlWrap_Hole") is not None, "Hole button on the Part Design toolbar")

    doc = App.newDocument("Holes")
    b, pad = cylinder_body(doc)
    Gui.activeView().viewIsometric()
    pump(400)

    # nothing selected: a Greek message, nothing made
    Gui.Selection.clearSelection()
    Gui.runCommand("KnurlWrap_Hole")
    pump(600)
    c = wk._TOLD
    check(c is not None and c.isVisible() and "κλικ" in c.windowTitle(), "no click: Greek message")
    check(doc.getObject("HoleOnSurface") is None, "no click: nothing created")
    if c is not None:
        c.close()

    # 1. the flat top at (5, 0): straight down, through the solid cylinder (no empty space in it)
    full = pad.Shape.Volume
    top = face_name(pad, lambda f: abs(f.CenterOfMass.z - 30) < 1e-6)
    click(doc, pad, top, V(5, 0, 30))
    h1 = doc.getObject("HoleOnSurface")
    check(h1 is not None and h1.TypeId == "PartDesign::FeaturePython" and b.Tip == h1, "hole made, in the Body, Tip")
    if h1 is None:
        return
    vp = Gui.ActiveDocument.getInEdit()
    check(vp is not None and vp.Object == h1 and Gui.Control.activeDialog(), "its panel opens")
    check((V(h1.Direction) - V(0, 0, -1)).Length < 1e-9 and (V(h1.Point) - V(5, 0, 30)).Length < 1e-6,
          "square to the top face at the clicked point (%s, %s)" % (h1.Point, h1.Direction))
    want = math.pi * 1.5 ** 2 * 30
    check(abs(full - h1.Shape.Volume - want) < 0.5, "Ø3 right through the 30 mm: %.2f mm³ cut (want %.2f)"
          % (full - h1.Shape.Volume, want))
    # the panel: diameter 5 and 8 mm deep, then Cancel brings the old values back
    panel = wh.TaskHole(h1)
    panel.dia.setValue(5)
    panel.mode.setCurrentText("Βάθος")
    panel.depth.setValue(8)
    pump(500)
    check(abs(full - h1.Shape.Volume - math.pi * 2.5 ** 2 * 8) < 0.5 and panel.depth.isEnabled(),
          "panel: Ø5, 8 mm deep (%.2f mm³)" % (full - h1.Shape.Volume))
    panel.reject()
    pump(300)
    check(h1.Diameter.Value == 3 and h1.Mode == wh.MODES[0], "Cancel puts the old values back")
    close_panel()
    shot("top")

    # 2. the side of the cylinder at 90°, 10 mm high: radial, into the axis and out the far side
    after1 = h1.Shape.Volume
    side = face_name(h1, lambda f: wk.cylinder_of(f) and abs(f.Surface.Radius - 12) < 1e-6)
    click(doc, h1, side, V(0, 12, 10))
    h2 = doc.getObject("HoleOnSurface001")
    check(h2 is not None and h2.BaseFeature == h1 and b.Tip == h2, "second hole after the first")
    if h2 is not None:
        close_panel()
        check((V(h2.Direction) - V(0, -1, 0)).Length < 1e-6, "side: radial, towards the axis (%s)" % h2.Direction)
        check(abs(after1 - h2.Shape.Volume - math.pi * 1.5 ** 2 * 24) < 0.5,
              "side: right across the solid cylinder (%.1f mm³)" % (after1 - h2.Shape.Volume))

    # 3. a tube (bore 6): "up to the first empty space" stops in the bore; "right through" goes on
    d3 = App.newDocument("Tube")
    b3, p3 = cylinder_body(d3, bore=6)
    side3 = face_name(p3, lambda f: wk.cylinder_of(f) and abs(f.Surface.Radius - 12) < 1e-6)
    h3, br = wh.make_hole(p3, p3.Shape.getElement(side3), V(12, 0, 15))
    wall = math.pi * 1.5 ** 2 * 6
    check(br is None and abs(p3.Shape.Volume - h3.Shape.Volume - wall) < 0.3,
          "tube: through one wall only (%.2f mm³, one wall ≈ %.2f)" % (p3.Shape.Volume - h3.Shape.Volume, wall))
    h3.Mode = "Διαμπερής"
    d3.recompute()
    check(abs(p3.Shape.Volume - h3.Shape.Volume - 2 * wall) < 0.6, "tube, right through: both walls")
    h3.Mode, h3.Depth = "Βάθος", 2
    d3.recompute()
    check(abs(p3.Shape.Volume - h3.Shape.Volume - math.pi * 1.5 ** 2 * 2) < 0.3, "tube, 2 mm deep")
    # 4. clicked where there is nothing under the point: the hole says so (Greek) and is not made
    h3.Point, h3.Direction, h3.Mode = V(30, 0, 15), V(1, 0, 0), wh.MODES[0]
    d3.recompute()
    pump(500)
    check("Invalid" in h3.State or "Error" in str(h3.State) or h3.State != ["Up-to-date"],
          "nothing to drill: error state (%s)" % h3.State)
    check(wk._TOLD is not None and "τρύπα" in wk._TOLD.windowTitle().lower(), "nothing to drill: Greek message")
    wk._TOLD.close()
    App.closeDocument(d3.Name)

    # 5. a slanted face (a wedge): square to the slope
    d5 = App.newDocument("Wedge")
    w = d5.addObject("Part::Feature", "Wedge")
    w.Shape = Part.makeBox(20, 20, 20).cut(
        Part.makeBox(40, 40, 40, V(0, 0, 10), V(0, 0, 1)).rotated(V(0, 0, 10), V(0, 1, 0), 30))
    d5.recompute()
    slope = next(f for f in w.Shape.Faces if 0.5 < abs(f.normalAt(0, 0).z) < 1.0)
    pt = slope.CenterOfMass
    h5, _br = wh.make_hole(w, slope, pt, mode="Βάθος", depth=3)
    n = V(slope.normalAt(*slope.Surface.parameter(pt)))
    check(abs(V(h5.Direction).dot(n) + 1) < 1e-9 and h5.Shape.isValid(), "slanted face: square to the slope")
    check(abs(w.Shape.Volume - h5.Shape.Volume - math.pi * 1.5 ** 2 * 3) < 0.3,
          "plain Part solid: 3 mm deep (%.2f mm³)" % (w.Shape.Volume - h5.Shape.Volume))
    App.closeDocument(d5.Name)

    # 6. Marios's pulley case: a feature before the hole leaves a solid on which every cut fails
    # (his Part Design Hole with "Model Thread" on the HTD 5M pulley did; a plain threaded hole does
    # not reproduce it, so a feature that turns its solid inside out stands in for it). A hole
    # across it must go BEFORE that feature, with a Greek message naming it.
    d6 = App.newDocument("Pulley")
    b6, p6 = cylinder_body(d6, r=22, h=20, bore=7)
    bad = d6.addObject("PartDesign::FeaturePython", "Breaker")
    InsideOut(bad)
    b6.addObject(bad)
    d6.recompute()
    probe = Part.makeCylinder(1.5, 100, V(-50, 0, 10), V(1, 0, 0))
    check(not wh.cut_ok(bad.Shape, probe, bad.Shape.cut(probe)), "the stand-in solid is broken for cuts")
    side6 = face_name(p6, lambda f: wk.cylinder_of(f) and abs(f.Surface.Radius - 22) < 1e-6)
    click(d6, bad, side6, V(22, 0, 10))
    h6 = d6.getObject("HoleOnSurface")
    close_panel()
    check(h6 is not None and h6.BaseFeature == p6 and bad.BaseFeature == h6 and b6.Tip == bad,
          "pulley: the hole went before the broken feature")
    check(wk._TOLD is not None and "πιο πριν" in wk._TOLD.windowTitle() and "Breaker" in wk._TOLD.text(),
          "pulley: Greek message names the feature")
    if h6 is not None:
        hs = h6.Shape
        inside = [t for t in (1, 5, 10, 14) if hs.isInside(V(22 - t, 0, 10), 1e-6, True)]
        check(hs.isValid() and not inside and hs.isInside(V(-18, 0, 10), 1e-6, True),
              "pulley: hole open into the bore, far wall untouched (material at %s, valid %s, far %s, vol %.1f -> %.1f)"
              % (inside, hs.isValid(), hs.isInside(V(-18, 0, 10), 1e-6, True), p6.Shape.Volume, hs.Volume))
    shot("pulley")
    if wk._TOLD is not None:
        wk._TOLD.close()
    # the same hole asked AFTER it (by hand): it refuses with the Greek explanation
    late = d6.addObject("PartDesign::FeaturePython", "Late")
    wh.HoleOnSurface(late)
    b6.addObject(late)
    late.Point, late.Direction = V(22, 0, 10), V(-1, 0, 0)
    d6.recompute()
    pump(500)
    check(late.State != ["Up-to-date"] and wk._TOLD is not None and "Model Thread" in wk._TOLD.informativeText(),
          "a hole after the broken feature: refused, explained (%s)" % late.State)
    if wk._TOLD is not None:
        wk._TOLD.close()

    # 7. save and reopen
    path = os.path.join(OUT, "holes.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    App.closeDocument(d6.Name)
    pump(500)
    d2 = App.openDocument(path)
    pump(800)
    h = d2.getObject("HoleOnSurface")
    check(h is not None and isinstance(h.Proxy, wh.HoleOnSurface)
          and isinstance(h.ViewObject.Proxy, wh.ViewProviderHole),
          "reopened file keeps the hole")
    d2.getObject("Pad").Length = 40      # an edit upstream: the holes follow
    d2.recompute()
    check(all("Invalid" not in o.State and o.Shape.isValid() for o in (h, d2.getObject("HoleOnSurface001"))),
          "holes recompute after an upstream edit")


try:
    run()
except Exception:
    failures += 1
    P("FAIL exception:\n" + traceback.format_exc())
P("RESULT:", "PASS" if failures == 0 else "%d FAILURES" % failures)
log.close()
os._exit(0)
