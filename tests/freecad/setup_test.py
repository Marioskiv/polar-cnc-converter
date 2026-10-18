# Polar CNC — the chuck from one click, in a real FreeCAD: the face that goes into the chuck is
# picked, the part is turned and centred with Z0 on the stock top, and the chuck that holds the
# stock is chosen (round bar -> K11-125 3-jaw, square -> K72-125 4-jaw).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, check, fails, finish, log, pump  # noqa: E402

seen = []


def answer(accept=True, by_hand=False):
    """Answer the next dialog the way a person would."""
    def go():
        dlg = QtGui.QApplication.activeModalWidget()
        if dlg is None:
            QtCore.QTimer.singleShot(200, go)
            return
        seen.append((dlg.objectName(), dlg.preset() if hasattr(dlg, "preset") else None,
                     dlg.grip() if hasattr(dlg, "grip") else None,
                     dlg.findChild(QtGui.QLabel, "found").text() if dlg.findChild(QtGui.QLabel, "found") else ""))
        try:
            dlg.grab().save(os.path.join(OUT, "%s.png" % dlg.objectName()))
        except Exception:
            pass
        if by_hand and hasattr(dlg, "_hand"):
            dlg._hand()
        elif accept:
            dlg.accept()
        else:
            dlg.reject()
    QtCore.QTimer.singleShot(300, go)


def job_with(doc, part_shape, stock_shape):
    import Draft
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    p = doc.addObject("Part::Feature", "Part")
    p.Shape = part_shape
    doc.recompute()
    job = PathJob.Create("Job", [p], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    holder = doc.addObject("Part::Feature", "StockShape")
    holder.Shape = stock_shape
    holder.ViewObject.Visibility = False
    old = job.Stock
    stock = Draft.make_clone(holder)
    stock.Label = "Stock"
    job.Stock = stock
    doc.removeObject(old.Name)
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 150
    return job


def face_named(obj, test):
    for k, f in enumerate(obj.Shape.Faces, 1):
        if test(f):
            return "Face%d" % k
    return None


def run():
    import Part
    from polarcnc import chuck as ch, policy
    Gui.activateWorkbench("CAMWorkbench")
    Gui.getMainWindow().resize(1500, 950)
    V = App.Vector

    # H1: a round bar lying along X; its +X end goes into the chuck
    doc = App.newDocument("SetupH1")
    part = Part.makeCylinder(10, 40, V(0, 0, 0), V(1, 0, 0))
    stock = Part.makeCylinder(12, 49, V(-3, 0, 0), V(1, 0, 0))
    job = job_with(doc, part, stock)
    model = job.Model.Group[0]
    name = face_named(model, lambda f: abs(f.CenterOfMass.x - 40) < 1e-6 and f.Area < 400)
    check(name is not None, "H1: the end face of the part found (%s)" % name)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(model, name)
    policy._cache[0] = 0.0
    answer()
    Gui.runCommand("PolarCNC_Chuck")
    pump(500)
    sb = job.Stock.Shape.BoundBox
    mb = model.Shape.BoundBox
    check(abs(sb.XLength - 24) < 0.05 and abs(sb.ZLength - 49) < 0.01,
          "H1: the bar stands on its end (stock %.2f x %.2f x %.2f)" % (sb.XLength, sb.YLength, sb.ZLength))
    axis = [e.Curve.Center for e in job.Stock.Shape.Edges if e.Curve.__class__.__name__ == "Circle"]
    check(abs(sb.ZMax) < 1e-6 and axis and all(abs(p.x) < 1e-6 and abs(p.y) < 1e-6 for p in axis),
          "H1: stock top at Z0, its axis on the chuck axis (%.3f, %.3f, top %.3f)" % (sb.Center.x, sb.Center.y, sb.ZMax))
    check(abs((mb.ZMin - sb.ZMin) - 6) < 0.01, "H1: the picked end is down: 6 mm of stock under the part (%.2f)"
          % (mb.ZMin - sb.ZMin))
    c = getattr(job, "PolarChuck", None)
    check(c is not None and c.Preset == "3-jaw SAN OU K11-125 (Ø125)" and abs(c.GripLength.Value - 6) < 0.01,
          "H1: round Ø24 -> K11-125 3-jaw, grip 6 (%s, %s)" % (c and c.Preset, c and c.GripLength))
    check(seen and seen[-1][0] == "PolarChuckSetup" and "Ø24" in seen[-1][3], "H1: the dialog said what it found: %r" % (seen[-1:],))
    check(c is not None and not any("cannot hold" in n or "bigger" in n for n in c.Notes), "H1: %s" % (c and c.Notes))
    check(c is not None and c.ViewObject.Visibility and c.ViewObject.DisplayMode == "Flat Lines",
          "H1: the chuck is shown and drawn (display mode %r)" % (c and c.ViewObject.DisplayMode))
    Gui.SendMsgToActiveView("ViewFit")
    pump(300)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "H1_bar_in_3jaw.png"))
    # undo puts everything back
    doc.undo()
    doc.recompute()
    check(abs(job.Stock.Shape.BoundBox.XLength - 49) < 0.01 and getattr(job, "PolarChuck", None) is None,
          "H1: Undo puts the bar back as it was, no chuck")
    App.closeDocument(doc.Name)

    # H2: a square block, the stock's bottom picked: nothing to turn, the 4-jaw
    doc = App.newDocument("SetupH2")
    job = job_with(doc, Part.makeBox(30, 30, 20, V(-15, -15, 0)), Part.makeBox(40, 40, 26, V(-20, -20, -6)))
    name = face_named(job.Stock, lambda f: abs(f.CenterOfMass.z + 6) < 1e-6)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job.Stock, name)
    policy._cache[0] = 0.0
    answer()
    Gui.runCommand("PolarCNC_Chuck")
    pump(500)
    sb = job.Stock.Shape.BoundBox
    c = getattr(job, "PolarChuck", None)
    check(c is not None and c.ViewObject.Visibility, "H2: the chuck is shown")
    check(job.Model.Group[0].ViewObject.Visibility and not job.Model.Group[0].Objects[0].ViewObject.Visibility,
          "H2: the Job's copy of the part is shown (it is the one that was turned), the original hidden")
    check(abs(sb.ZMax) < 1e-6 and abs(sb.ZMin + 26) < 1e-6 and abs(sb.XLength - 40) < 1e-6,
          "H2: block still flat, its top moved to Z0 (%.2f..%.2f)" % (sb.ZMin, sb.ZMax))
    check(c is not None and c.ChuckType == ch.FOUR_JAW and abs(c.GripLength.Value - 6) < 0.01,
          "H2: square -> the 4-jaw K72-125, grip 6 (%s, %s)" % (c and c.Preset, c and c.GripLength))
    check(c is not None and any("closed on the stock" in n for n in c.Notes), "H2: jaws closed: %s" % (c and c.Notes))
    Gui.getMainWindow().grab().save(os.path.join(OUT, "H2_block_in_4jaw.png"))

    # H3: Cancel keeps everything as it was
    before = job.Model.Group[0].Placement.toMatrix()
    side = face_named(job.Model.Group[0], lambda f: abs(f.CenterOfMass.x - 15) < 1e-6)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job.Model.Group[0], side)
    policy._cache[0] = 0.0
    answer(accept=False)
    Gui.runCommand("PolarCNC_Chuck")
    pump(500)
    check(job.Model.Group[0].Placement.toMatrix() == before, "H3: Cancel leaves the part as it was")
    App.closeDocument(doc.Name)

    # H4: no face and no chuck: the hint, then 'by hand' opens the chooser
    doc = App.newDocument("SetupH4")
    job = job_with(doc, Part.makeCylinder(8, 15), Part.makeCylinder(10, 20, V(0, 0, -5)))
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    policy._cache[0] = 0.0
    seen[:] = []
    answer()
    Gui.runCommand("PolarCNC_Chuck")
    pump(500)
    check(seen and seen[0][0] == "PolarPickFace" and getattr(job, "PolarChuck", None) is None,
          "H4: no face picked -> it says what to click, nothing made (%r)" % seen)
    seen[:] = []
    answer(by_hand=True)
    QtCore.QTimer.singleShot(1200, lambda: answer())
    Gui.runCommand("PolarCNC_Chuck")
    pump(2500)
    check(getattr(job, "PolarChuck", None) is not None, "H4: 'by hand' opens the chooser and makes the chuck")
    App.closeDocument(doc.Name)

    # H5: the chucks this person has can be set
    from polarcnc import setup
    check(setup.my_chucks()[0].startswith("3-jaw SAN OU K11"), "H5: Marios's chucks by default: %s" % setup.my_chucks())


def go():
    try:
        run()
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    finish()


QtCore.QTimer.singleShot(2000, go)
