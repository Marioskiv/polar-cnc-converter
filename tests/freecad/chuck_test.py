# Polar CNC — the chuck / faceplate in a real FreeCAD (run by tests/freecad/run.sh, own start).
#
# Set-ups: round stock in a 3-jaw SC-10, square stock in a 4-jaw chuck (jaws on the flats),
# off-centre square in a 3-jaw (must be refused with a note), a square and a rectangle in the
# SAN OU K12-125 4-jaw self-centring chuck (the rectangle refused; held by the K72-125), a plate on a faceplate with three
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
from PySide import QtCore, QtGui

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
    for _ in range(50):                  # the task panel opens on a later event-loop turn
        pump(100)
        if Gui.Control.activeTaskDialog() is not None:
            break
    Gui.Control.activeTaskDialog().accept()
    pump(200)
    op.setExpression("FinalDepth", None)
    op.FinalDepth = final
    op.recompute()
    job.Document.recompute()
    return op


def min_clearance(op, chuck, z_top):
    """Smallest distance from the cutter (radius R, its tip and everything above it) to the
    jaws/clamps, over all cutting points below z_top (the jaw tops + the clearance: a cut just
    above the jaws must keep clear of them too)."""
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
    from polarcnc import chuck as ch, policy, simulator
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
        gap = min_clearance(op, c, jaw_top + op.ChuckClearance.Value)  # also just above the jaw tops
        check(gap >= op.ChuckClearance.Value - 0.05, "A: Polar Face keeps %.2f mm from the jaws (needs %.1f)"
              % (gap, op.ChuckClearance.Value))
        # round stock: the jaws may sit anywhere round it, so they are kept clear as a ring -
        # nothing is cut beside them at all below their tops
        def arcs(o):
            return [(round(x.Parameters.get("X", 0), 2), round(x.Parameters.get("Y", 0), 2))
                    for x in o.Path.Commands if x.Name in ("G2", "G3")]
        low = [math.hypot(x.Parameters["X"], x.Parameters["Y"]) for x in op.Path.Commands
               if x.Name in ("G1", "G2", "G3") and "X" in x.Parameters and x.Parameters.get("Z", 99) < 10 + 2]
        check(low and max(low) <= 30 - 2 - 2.5 + 0.05,
              "A: round stock, jaws as a ring: below the jaw tops nothing is cut past r %.2f" % max(low or [0]))
        ringed = arcs(op)
        c.FirstJawAngle = 45
        doc.recompute()
        check(arcs(op) == ringed, "A: round stock: turning the jaws changes nothing (they are a ring)")
        # with C0 set to the jaws, they are where the CAM shows them: the path follows them
        c.JawsAtKnownAngle = True
        doc.recompute()
        before = arcs(op)
        c.FirstJawAngle = 0
        doc.recompute()
        gap = min_clearance(op, c, c.Shape.BoundBox.ZMax + op.ChuckClearance.Value)
        check(op.PolarChuck == c and arcs(op) != before and gap >= op.ChuckClearance.Value - 0.05,
              "A: jaws at a known angle, turned -> Polar Face made again by itself, keeps %.2f mm" % gap)
        c.JawsAtKnownAngle = False
        doc.recompute()
        warn = [m for m in policy.problems(op) if "below the top of the jaws" in m]
        check(len(warn) == 1 and "4.00 mm below" in warn[0], "A: warns about the collet nut: %s" % warn)
        import Path
        check(ch.head_warning(c, Path.Path([Path.Command("G1", {"X": 0, "Z": 12})])) is None,
              "A: no warning for a cut above the jaws")
        App.closeDocument(doc.Name)

        # B: square stock in a 4-jaw chuck, jaws on the flats
        doc = App.newDocument("ChuckB")
        job = job_for(doc, part, Part.makeBox(50, 50, 20, App.Vector(-25, -25, 0)))
        c = ch.make_chuck(job, "4-jaw 12in (Ø300)")
        c.GripLength, c.FirstJawAngle = 10, 0
        doc.recompute()
        check(any("closed on the stock at 25.00, 25.00, 25.00, 25.00" in n for n in c.Notes), "B: %s" % c.Notes)
        op = polar_face(job, 6)
        gap = min_clearance(op, c, c.Shape.BoundBox.ZMax + op.ChuckClearance.Value)
        check(gap >= op.ChuckClearance.Value - 0.05, "B: keeps %.2f mm from the jaws" % gap)
        # the collision check of every operation: Polar Face is clear, a cut onto a jaw and a
        # rapid into a jaw are found, and Post Process writes no file
        from polarcnc import collision
        obs = collision.obstacles(c)
        res = collision.check(obs, op.Path, collision.tool_radius(op))
        check(res is not None and res["clearance"] >= op.ChuckClearance.Value - 0.05,
              "B: collision check agrees: Polar Face keeps %.2f mm" % (res or {}).get("clearance", -1))
        import Path.Op.Custom as Custom
        bad = Custom.Create("OntoJaw", parentJob=job)
        bad.Source = "Text"
        bad.Gcode = ["G0 X40 Y0 Z30", "G1 Z5 F100", "G0 Z30"]
        doc.recompute()
        msgs = [m for m in policy.problems(bad) if "runs into" in m]
        check(len(msgs) == 1 and "The cut runs into the jaw" in msgs[0], "B: cut onto a jaw found: %s" % msgs)
        bad.Gcode = ["G0 X40 Y0 Z30", "G0 Z5", "G0 Z30"]
        doc.recompute()
        msgs = [m for m in policy.problems(bad) if "runs into" in m]
        check(len(msgs) == 1 and "A rapid move runs into" in msgs[0], "B: rapid into a jaw found: %s" % msgs)
        from Path.Post.Processor import PostProcessorFactory
        job.PostProcessorArgs = "--no-show-editor"
        boxes = []
        warn_box = QtGui.QMessageBox.warning
        QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: boxes.append(a[2]))
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        QtGui.QMessageBox.warning = warn_box
        check(res and all(r[1] is None for r in res) and boxes and "runs into the chuck" in boxes[-1],
              "B: Post Process refuses a program that hits the chuck: %r" % (boxes[-1:] or "")[:160])
        doc.removeObject(bad.Name)
        doc.recompute()
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is not None and "G93" in res[0][1], "B: without it the program is written")
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

        # E: SAN OU K12-125, 4 jaws self-centring: a centred square is held, a rectangle is not
        doc = App.newDocument("ChuckE")
        job = job_for(doc, Part.makeCylinder(8, 15), Part.makeBox(40, 40, 20, App.Vector(-20, -20, 0)))
        c = ch.make_chuck(job, "4-jaw SAN OU K12-125 self-centring (Ø125)")
        c.GripLength = 10
        doc.recompute()
        check(c.ChuckType == ch.FOUR_JAW_SC and abs(c.JawHeight.Value - 26) < 1e-9,
              "E: SAN OU K12-125 preset, jaws 26 mm above the face")
        check(any("closed on the stock at 20.00, 20.00, 20.00, 20.00" in n for n in c.Notes), "E: %s" % c.Notes)
        op = polar_face(job, 6)
        gap = min_clearance(op, c, 10 + op.ChuckClearance.Value)
        check(gap >= op.ChuckClearance.Value - 0.05, "E: keeps %.2f mm from the jaws" % gap)
        App.closeDocument(doc.Name)
        doc = App.newDocument("ChuckE2")
        job = job_for(doc, Part.makeCylinder(8, 15), Part.makeBox(50, 30, 20, App.Vector(-25, -15, 0)))
        c = ch.make_chuck(job, "4-jaw SAN OU K12-125 self-centring (Ø125)")
        c.GripLength = 10
        doc.recompute()
        check(any("self-centring chuck cannot hold" in n for n in c.Notes), "E: rectangle refused: %s" % c.Notes)
        App.closeDocument(doc.Name)
        # ... and held by the default chuck, the SAN OU K72-125 with independent jaws
        doc = App.newDocument("ChuckE3")
        job = job_for(doc, Part.makeCylinder(8, 15), Part.makeBox(50, 30, 20, App.Vector(-25, -15, 0)))
        c = ch.make_chuck(job)
        c.GripLength = 10
        doc.recompute()
        check(c.ChuckType == ch.FOUR_JAW and abs(c.Diameter.Value - 125) < 1e-9,
              "E: default chuck is the SAN OU K72-125 (independent)")
        check(any("closed on the stock at 25.00, 15.00, 25.00, 15.00" in n for n in c.Notes), "E: %s" % c.Notes)
        App.closeDocument(doc.Name)

        # F: the Chuck button asks which chuck (catalogue size or Custom)
        doc = App.newDocument("ChuckF")
        job = job_for(doc, Part.makeCylinder(8, 15), Part.makeBox(40, 40, 20, App.Vector(-20, -20, 0)))

        def pick(name):
            def answer():
                dlg = QtGui.QApplication.activeModalWidget()
                if dlg is not None:
                    dlg.setTextValue(name)
                    dlg.accept()
            QtCore.QTimer.singleShot(400, answer)

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)
        policy._cache[0] = 0.0
        pick("4-jaw SAN OU K12-125 self-centring (Ø125)")
        Gui.runCommand("PolarCNC_Chuck")
        c = getattr(job, "PolarChuck", None)
        check(c is not None and c.Preset.startswith("4-jaw SAN OU K12") and c.ChuckType == ch.FOUR_JAW_SC,
              "F: Chuck button made the chosen K12-125")
        pick("4-jaw SAN OU K72-125 independent (Ø125)")
        Gui.runCommand("PolarCNC_Chuck")
        check(c.ChuckType == ch.FOUR_JAW and abs(c.JawHeight.Value - 21.7) < 1e-9 and
              abs(c.JawLength.Value - 56) < 1e-9 and abs(c.JawWidth.Value - 18) < 1e-9,
              "F: changed to the K72-125 (21.7 / 56 / 18)")
        pick(ch.CUSTOM)
        Gui.runCommand("PolarCNC_Chuck")
        c.JawHeight = 30
        doc.recompute()
        check(c.Preset == ch.CUSTOM and abs(c.JawHeight.Value - 30) < 1e-9 and abs(c.JawWidth.Value - 18) < 1e-9,
              "F: Custom keeps the sizes and takes your own (%s, %.1f)" % (c.Preset, c.JawHeight.Value))
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
        gap = min_clearance(op, c, c.Shape.BoundBox.ZMax + op.ChuckClearance.Value)
        check(gap >= op.ChuckClearance.Value - 0.05, "D: keeps %.2f mm from the clamps" % gap)
        check(len([x for x in op.Path.Commands if x.Name in ("G2", "G3")]) > 10, "D: still faces the plate")
        try:
            for o in (job, c, clamps[0], op):
                o.OutListRecursive
            cyc = False
        except Exception:
            cyc = True
        check(not cyc, "D: no dependency cycle between Job, chuck, clamps and operations")
        warn = [m for m in policy.problems(op) if "below the top of the clamps" in m]
        check(len(warn) == 1, "D: warns that the cut is below the clamp tops: %s" % warn)
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
