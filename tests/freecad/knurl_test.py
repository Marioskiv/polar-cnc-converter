# Knurling & Wrap — test in a real FreeCAD (run by tests/freecad/run.sh).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
"""Test the Knurl tool inside a REAL FreeCAD (moved from WikiTips with the tool, 2026-10-20).

    PC_OUT=/tmp/kw xvfb-run -a freecad tests/freecad/knurl_test.py

The button is on a Part Design toolbar (not in CAM). Pads a circle in a Body,
selects its side, presses the Knurl button, checks the Greek panel and the fast
preview, presses OK and checks the real teeth (one valid solid, material
removed). Also: a wrong selection gives the Greek message, a Part cylinder
works, the file saves and opens again.
Results: $PC_OUT/result.txt (+ knurl_*.png).
"""
import faulthandler
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
    Gui.getMainWindow().grab().save(os.path.join(OUT, "knurl_%s.png" % name))


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
    mw = Gui.getMainWindow()
    mw.resize(1600, 1000)
    Gui.activateWorkbench("CAMWorkbench")
    pump(1500)
    check(find_button("KnurlWrap_Knurl") is None, "no Knurl button in CAM (Part Design only)")
    Gui.activateWorkbench("PartDesignWorkbench")
    pump(1500)
    check(find_button("KnurlWrap_Knurl") is not None, "Knurl button on the Part Design toolbar")

    doc = App.newDocument("Knurl")
    b = doc.addObject("PartDesign::Body", "Body")
    s = b.newObject("Sketcher::SketchObject", "Sketch")
    s.AttachmentSupport = [(b.Origin.OriginFeatures[3], "")]
    s.MapMode = "FlatFace"
    s.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 10))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = s
    pad.Length = 30
    doc.recompute()
    Gui.activeView().viewIsometric()
    pump(500)
    faces = {n: f for n, f in ((("Face%d" % (i + 1)), f) for i, f in enumerate(pad.Shape.Faces))}
    side = next(n for n, f in faces.items() if wk.cylinder_of(f))
    flat = next(n for n, f in faces.items() if not wk.cylinder_of(f))

    # wrong selection: a flat face -> Greek message, nothing created
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Pad", flat)
    Gui.runCommand("KnurlWrap_Knurl")
    pump(600)
    c = wk._TOLD
    check(c is not None and c.isVisible() and "κύλινδρο" in c.windowTitle(), "flat face: Greek message")
    check(doc.getObject("Knurl") is None, "flat face: nothing created")
    if c is not None:
        c.close()

    # the right selection
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Pad", side)
    Gui.runCommand("KnurlWrap_Knurl")
    pump(1500)
    k = doc.getObject("Knurl")
    check(k is not None and k.TypeId == "PartDesign::FeaturePython", "Knurl feature in the Body")
    check(bool(Gui.Control.activeDialog()) and wk._PANEL is not None, "Greek panel open")
    if k is None or wk._PANEL is None:
        return
    check(abs(k.Pitch.Value - 1.0) < 1e-9, "default pitch for D20 = 1.0 mm (got %s)" % k.Pitch)
    lineset = getattr(k.ViewObject.Proxy, "lineset", None)
    check(k.Kind == "Ελαφρύ" and lineset is not None and lineset.numVertices.getNum() > 100,
          "fast preview with lines (drawn on screen) while editing")
    check(len(k.Shape.Solids) == 1 and abs(k.Shape.Volume - pad.Shape.Volume) < 1e-6,
          "light kind leaves the solid untouched")
    check("επιφάνειες" in wk._PANEL.size.text(), "panel shows the size of the real teeth (%r)" % wk._PANEL.size.text())
    shot("preview")
    panel = wk._PANEL
    boxes = [bx for bx in Gui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox) if bx.isVisible()]
    names = [b.text() for bx in boxes for b in bx.buttons()]
    check(any(bx.button(QtWidgets.QDialogButtonBox.Apply) is not None for bx in boxes),
          "panel has an Apply button (%s)" % names)
    check("μέγιστο" in panel.limits.text(), "panel shows the depth limits (%r)" % panel.limits.text())
    panel.start.setValue(5)
    panel.end.setValue(3)
    pump(500)
    t = time.time()
    panel.clicked(QtWidgets.QDialogButtonBox.Apply)
    pump(800)
    P("     real teeth in %.1f s" % (time.time() - t))
    check(bool(Gui.Control.activeDialog()) and k.Kind == "Πραγματικό" and "Invalid" not in k.State,
          "Apply computes the real teeth and the panel stays open")
    t = time.time()
    panel.accept()
    pump(300)
    check(not Gui.Control.activeDialog() and time.time() - t < 2,
          "OK only closes the panel (%.1f s, nothing computed again)" % (time.time() - t))
    sh = k.Shape
    check(k.Kind == "Πραγματικό" and "Invalid" not in k.State, "real knurl computed (%s)" % k.getStatusString())
    check(sh.isValid() and len(sh.Solids) == 1, "one valid solid")
    check(wk.LAST_METHOD == "direct", "fast direct build used (got %r)" % wk.LAST_METHOD)
    removed = pad.Shape.Volume - sh.Volume
    check(200 < removed < 600, "material removed %.1f mm³" % removed)
    check(b.Tip == k, "Knurl is the Tip of the Body")
    cut = pad.Shape.cut(sh).BoundBox
    check(abs(cut.ZMin - 5) < 0.3 and abs(cut.ZMax - 27) < 0.3,
          "margins count from the bottom: teeth from z %.2f to %.2f (want 5 to 27)" % (cut.ZMin, cut.ZMax))
    Gui.Selection.clearSelection()
    shot("real")
    for o in (pad,):
        o.ViewObject.Visibility = False
    # a Pocket after the knurl still works (it is a normal Body feature)
    s2 = b.newObject("Sketcher::SketchObject", "Sketch001")
    s2.AttachmentSupport = [(b.Origin.OriginFeatures[3], "")]
    s2.MapMode = "FlatFace"
    s2.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 4))
    q = b.newObject("PartDesign::Pocket", "Pocket")
    q.Profile = s2
    q.Type = 1
    q.Reversed = True
    doc.recompute()
    check("Invalid" not in q.State and q.Shape.isValid(), "Pocket after the Knurl")
    shot("pocket_after")

    # a knurl that is far too big: refused at once with a Greek message, FreeCAD does not freeze
    dbig = App.newDocument("Big")
    bb = dbig.addObject("PartDesign::Body", "Body")
    big = bb.newObject("Sketcher::SketchObject", "SketchBig")
    big.AttachmentSupport = [(bb.Origin.OriginFeatures[3], "")]
    big.MapMode = "FlatFace"
    big.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 40))
    padbig = bb.newObject("PartDesign::Pad", "PadBig")
    padbig.Profile = big
    padbig.Length = 80
    dbig.recompute()
    fbig = next(f for f in padbig.Shape.Faces if wk.cylinder_of(f) and abs(wk.cylinder_of(f)[2] - 40) < 1e-6)
    kb = wk.make_knurl(padbig, fbig)
    kb.Pitch = 0.4
    t = time.time()
    dbig.recompute()
    took = time.time() - t
    check("Invalid" in kb.State and "too many teeth" in kb.getStatusString() and took < 10,
          "too big knurl refused in %.1f s (%s)" % (took, kb.getStatusString()))
    pump(1600)
    c = wk._TOLD
    check(c is not None and c.isVisible() and "πολύ μεγάλο" in c.windowTitle(), "Greek message for the too big knurl")
    if c is not None:
        c.close()
    kb.Kind = "Ελαφρύ"
    t = time.time()
    dbig.recompute()
    check("Invalid" not in kb.State and time.time() - t < 15, "the light kind still works for it (%.1f s)" % (time.time() - t))
    App.closeDocument(dbig.Name)
    App.setActiveDocument(doc.Name)
    pump(500)

    # Part workbench cylinder, lying along X
    cyl = doc.addObject("Part::Cylinder", "Cylinder")
    cyl.Radius, cyl.Height = 6, 25
    cyl.Placement = App.Placement(V(40, 0, 0), App.Rotation(V(0, 1, 0), 90))
    doc.recompute()
    face = next(f for f in cyl.Shape.Faces if wk.cylinder_of(f))
    k2 = wk.make_knurl(cyl, face)
    k2.Pattern = "Ίσιο"
    doc.recompute()
    check(k2.TypeId == "Part::FeaturePython" and k2.Shape.isValid() and cyl.Shape.Volume - k2.Shape.Volume > 50,
          "straight knurl on a Part cylinder")
    # a cross hole in the band: the direct build is not possible, the boolean takes over
    holed = doc.addObject("Part::Feature", "Holed")
    holed.Shape = Part.makeCylinder(8, 30, V(0, 60, 0)).cut(Part.makeCylinder(2, 30, V(-15, 60, 15), V(1, 0, 0)))
    doc.recompute()
    hf = next(f for f in holed.Shape.Faces if wk.cylinder_of(f) and abs(wk.cylinder_of(f)[2] - 8) < 1e-6)
    k3 = wk.make_knurl(holed, hf)
    k3.StartMargin, k3.EndMargin = 5, 5
    doc.recompute()
    check(wk.LAST_METHOD == "boolean" and k3.Shape.isValid() and len(k3.Shape.Solids) == 1,
          "band with a cross hole: boolean fallback, valid (%s)" % wk.LAST_METHOD)

    # Marios's try: pitch 0.3 with depth 0.8 (deeper than the teeth can be): the depth is held at the
    # full height of the pitch, the teeth come out fast and valid (it took 10 minutes before)
    small = doc.addObject("Part::Cylinder", "Small")
    small.Radius, small.Height = 5, 10
    small.Placement = App.Placement(V(0, -40, 0), App.Rotation())
    doc.recompute()
    sf = next(f for f in small.Shape.Faces if wk.cylinder_of(f))
    k4 = wk.make_knurl(small, sf)
    k4.Pitch, k4.Depth = 0.3, 0.8
    full = wk.depth_for(0.3, k4.Pattern, k4.Angle.Value)
    check(abs(wk.tooth_depth(0.8, 0.3, k4.Pattern, k4.Angle.Value) - full) < 1e-9,
          "depth 0.8 held at the full height %.3f mm for pitch 0.3" % full)
    t = time.time()
    doc.recompute()
    took = time.time() - t
    sh4 = k4.Shape
    check("Invalid" not in k4.State and sh4.isValid() and len(sh4.Solids) == 1 and took < 30,
          "pitch 0.3 / depth 0.8 knurl in %.1f s, valid (%s)" % (took, wk.LAST_METHOD))
    k4.Depth = 0
    t = time.time()
    doc.recompute()
    planar = sum(1 for f in k4.Shape.Faces if f.Surface.TypeId == "Part::GeomPlane")
    check("Invalid" not in k4.State and k4.Shape.isValid() and planar > 1000,
          "automatic depth: flat-topped teeth, %d flat faces, %.1f s" % (planar, time.time() - t))

    # save and open again
    path = os.path.join(OUT, "knurl.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    pump(500)
    d2 = App.openDocument(path)
    pump(800)
    k = d2.getObject("Knurl")
    check(k is not None and isinstance(k.Proxy, wk.Knurl) and isinstance(k.ViewObject.Proxy, wk.ViewProviderKnurl),
          "reopened file keeps the Knurl (object + icon)")
    d2.recompute()
    check("Invalid" not in k.State and k.Shape.isValid(), "reopened Knurl recomputes")


try:
    run()
except Exception:
    failures += 1
    P("FAIL exception:\n" + traceback.format_exc())
P("RESULT:", "PASS" if failures == 0 else "%d FAILURES" % failures)
log.close()
os._exit(0)
