# Polar CNC — the chuck / faceplate in a real FreeCAD (run by tests/freecad/run.sh, own start).
#
# Four set-ups: round stock in a 3-jaw SC-10, square stock in a 4-jaw chuck (jaws on the flats),
# off-centre square in a 3-jaw (must be refused with a note), a plate on a faceplate with three
# clamps. Checks: presets fill the sizes, the jaws meet the stock where they should, Polar Face cut
# below the top of the jaws keeps the chuck clearance from every jaw and clamp, and screenshots
# of the simulator with the real chuck.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, check, fails, finish, log, pump  # noqa: E402


def job_for(doc, part_shape, stock_shape):
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    import Path.Main.Stock as PathStock
    p = doc.addObject("Part::Feature", "Part")
    p.Shape = part_shape
    doc.recompute()
    job = PathJob.Create("Job", [p], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    holder = doc.addObject("Part::Feature", "StockShape")
    holder.Shape = stock_shape
    holder.ViewObject.Visibility = False
    old = job.Stock
    job.Stock = PathStock.CreateFromBase(job) if False else old
    # stock from an existing solid, as "Stock from existing" does
    import Draft
    clone = Draft.make_clone(holder)
    clone.Label = "Stock"
    job.Stock = clone
    doc.removeObject(old.Name)
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 150
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    return job


def polar_face(job, final):
    from polarcnc import polarface_gui
    polarface_gui.register()
    cmd = polarface_gui.Command()
    cmd.res.job = job
    op = polarface_gui.create(cmd.res)
    pump(300)
    Gui.Control.activeTaskDialog().accept()
    pump(200)
    op.setExpression("FinalDepth", None)
    op.FinalDepth = final
    op.recompute()
    job.Document.recompute()
    return op


def min_clearance(op, chuck, z_top):
    """Smallest distance (XY) from the cutter edge to the jaws/clamps, over all cutting points
    below the top of the jaws."""
    import Part
    R = op.ToolController.Tool.Diameter.Value / 2
    obst = chuck.Shape
    worst = 1e9
    x = y = None
    for c in op.Path.Commands:
        p = c.Parameters
        x, y, z = p.get("X", x), p.get("Y", y), p.get("Z", None)
        if z is not None:
            zc = z
        if x is None or c.Name == "G0" or zc >= z_top:
            continue
        v = Part.Vertex(App.Vector(x, y, zc + 0.01))
        d = v.distToShape(obst)[0] - R
        if d < worst:
            worst = d
            min_clearance.where = (c.Name, round(x, 2), round(y, 2), round(zc, 2))
    log.write("   closest: %s\n" % (getattr(min_clearance, "where", None),))
    return worst


def shot(name):
    pump(200)
    Gui.getMainWindow().grab().save(os.path.join(OUT, name))


def go():
    import Part
    from polarcnc import chuck as ch, simulator
    try:
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        part = Part.makeCylinder(15, 10).fuse(Part.makeCylinder(6, 15))

        # A: round stock in a 3-jaw SC-10
        doc = App.newDocument("ChuckA")
        job = job_for(doc, part, Part.makeCylinder(30, 20))
        c = ch.make_chuck(job, "3-jaw SC-10 (Ø273)")
        check(abs(c.Diameter.Value - 273) < 1e-9 and abs(c.JawHeight.Value - 39.5) < 1e-9,
              "preset SC-10 fills the sizes")
        c.GripLength = 10
        doc.recompute()
        check(any("closed on the stock at 30.00, 30.00, 30.00" in n for n in c.Notes), "A: %s" % c.Notes)
        jaw_top = c.Shape.BoundBox.ZMax
        check(abs(jaw_top - 10) < 1e-6, "A: jaw tops at stock bottom + grip = 10 (%.2f)" % jaw_top)
        op = polar_face(job, 6)
        gap = min_clearance(op, c, jaw_top)
        check(gap >= op.ChuckClearance.Value - 0.05, "A: Polar Face keeps %.2f mm from the jaws (needs %.1f)"
              % (gap, op.ChuckClearance.Value))
        App.closeDocument(doc.Name)

        # B: square stock in a 4-jaw chuck, jaws on the flats
        doc = App.newDocument("ChuckB")
        job = job_for(doc, part, Part.makeBox(50, 50, 20, App.Vector(-25, -25, 0)))
        c = ch.make_chuck(job, "4-jaw 12in (Ø300)")
        c.GripLength, c.FirstJawAngle = 10, 0
        doc.recompute()
        check(any("closed on the stock at 25.00, 25.00, 25.00, 25.00" in n for n in c.Notes), "B: %s" % c.Notes)
        op = polar_face(job, 6)
        gap = min_clearance(op, c, c.Shape.BoundBox.ZMax)
        check(gap >= op.ChuckClearance.Value - 0.05, "B: keeps %.2f mm from the jaws" % gap)
        panel = simulator.open_for(job)
        panel.machine.setChecked(True)
        panel._jump(panel.motion.total * 0.3)
        shot("B_square_4jaw.png")
        panel.reject()
        pump(200)
        App.closeDocument(doc.Name)

        # C: the same square off the centre in a 3-jaw chuck -> refused with a note
        doc = App.newDocument("ChuckC")
        job = job_for(doc, part, Part.makeBox(50, 50, 20, App.Vector(-20, -25, 0)))
        c = ch.make_chuck(job, "3-jaw SC-10 (Ø273)")
        c.GripLength = 10
        doc.recompute()
        check(any("self-centring chuck cannot hold" in n for n in c.Notes), "C: %s" % c.Notes)
        App.closeDocument(doc.Name)

        # D: a plate on a faceplate with three clamps
        doc = App.newDocument("ChuckD")
        job = job_for(doc, part, Part.makeBox(70, 40, 20, App.Vector(-27, -16, 0)))
        c = ch.make_chuck(job, "Faceplate Ø250")
        doc.recompute()
        clamps = [ch.add_clamp(c, a) for a in (0, 120, 240)]
        doc.recompute()
        check(len(c.Clamps) == 3 and all(abs(k.Height.Value - 28) < 1e-6 for k in clamps),
              "D: three strap clamps, 8 mm above the stock")
        check(abs(c.Shape.BoundBox.ZMax - 28) < 1e-6, "D: clamps stand on the faceplate (top %.1f)" % c.Shape.BoundBox.ZMax)
        op = polar_face(job, 15)
        gap = min_clearance(op, c, c.Shape.BoundBox.ZMax)
        check(gap >= op.ChuckClearance.Value - 0.05, "D: keeps %.2f mm from the clamps" % gap)
        check(len([x for x in op.Path.Commands if x.Name in ("G2", "G3")]) > 10, "D: still faces the plate")
        panel = simulator.open_for(job)
        panel.partv.setChecked(True)
        panel._jump(panel.motion.total)
        shot("D_plate_faceplate.png")
        panel.reject()
        pump(200)
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
