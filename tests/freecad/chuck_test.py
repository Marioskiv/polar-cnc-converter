# Polar CNC — the chuck / faceplate in a real FreeCAD (run by tests/freecad/run.sh, own start).
#
# Set-ups: round stock in a 3-jaw SC-10, square stock in a 4-jaw chuck (jaws on the flats),
# off-centre square in a 3-jaw (must be refused with a note), a square and a rectangle in the
# SAN OU K12-125 4-jaw self-centring chuck (the rectangle refused; held by the K72-125), a plate on a faceplate with three
# clamps. Checks: presets fill the sizes, the jaws meet the stock where they should, every
# operation is checked against the jaws and clamps when it is made (a cut or a rapid into a jaw
# says it will crash, and Post Process refuses it), and screenshots of the simulator with the real
# chuck.
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
from common import OUT, check, fails, finish, log, pump, catch_messages  # noqa: E402


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


def custom(job, label, gcode):
    """A Custom operation with this G-code (a cut where the test wants it)."""
    import Path.Op.Custom as Custom
    op = Custom.Create(label, parentJob=job)
    op.Source = "Text"
    op.Gcode = gcode
    job.Document.recompute()
    return op


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
        # a cut 4 mm below the jaw tops, well inside the jaws: clear of them, but the collet nut
        # above the cutter is not checked -> a reminder
        op = custom(job, "Inside", ["G0 X0 Y0 Z30", "G1 Z6 F100", "G1 X10 F300", "G0 Z30"])
        check(not policy.check(op)[0], "A: a cut inside the jaws clears them: %s" % policy.check(op)[0][:1])
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
        # every operation is checked when it is made, the way the machine moves X, C and Z: one
        # clear of the jaws passes, a cut onto a jaw and a rapid into a jaw say they will crash,
        # and Post Process writes no file
        op = custom(job, "Clear", ["G0 X0 Y0 Z30", "G1 Z6 F100", "G1 X12 F300", "G0 Z30"])
        check(not policy.check(op)[0], "B: a cut clear of the jaws passes: %s" % policy.check(op)[0][:1])
        import Path.Op.Custom as Custom
        bad = Custom.Create("OntoJaw", parentJob=job)
        bad.Source = "Text"
        bad.Gcode = ["G0 X40 Y0 Z30", "G1 Z5 F100", "G0 Z30"]
        doc.recompute()
        msgs = policy.check(bad)[0]
        check(len(msgs) == 1 and "WILL CRASH" in msgs[0] and "The cut runs into the jaw" in msgs[0],
              "B: cut onto a jaw found: %s" % msgs)
        bad.Gcode = ["G0 X40 Y0 Z30", "G0 Z5", "G0 Z30"]
        doc.recompute()
        msgs = policy.check(bad)[0]
        check(len(msgs) == 1 and "A rapid move runs into" in msgs[0], "B: rapid into a jaw found: %s" % msgs)
        from Path.Post.Processor import PostProcessorFactory
        job.PostProcessorArgs = "--no-show-editor"
        boxes = []
        catch_messages(boxes)
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
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
        op = custom(job, "Inside", ["G0 X0 Y0 Z30", "G1 Z6 F100", "G1 X10 F300", "G0 Z30"])
        check(not policy.check(op)[0], "E: a cut inside the jaws clears them: %s" % policy.check(op)[0][:1])
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
                if dlg is None:
                    return
                if dlg.objectName() == "PolarPickFace":      # no face picked: choose by hand
                    dlg._hand()
                    QtCore.QTimer.singleShot(400, answer)
                    return
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

        # G: the SAN OU K11-125 3-jaw (measured jaws), and what its jaws can hold
        for dia, word in ((30, None), (60, "reversed jaws"), (120, "bigger than")):
            doc = App.newDocument("ChuckG%d" % dia)
            job = job_for(doc, Part.makeCylinder(dia / 2 - 1, 20), Part.makeCylinder(dia / 2, 30))
            c = ch.make_chuck(job, "3-jaw SAN OU K11-125 (Ø125)")
            doc.recompute()
            if dia == 30:
                check(c.ChuckType == ch.THREE_JAW and abs(c.JawHeight.Value - 25.5) < 1e-9
                      and abs(c.JawLength.Value - 53) < 1e-9 and abs(c.JawWidth.Value - 16) < 1e-9,
                      "G: K11-125 with the measured jaws (25.5 / 53 / 16)")
            said = [n for n in c.Notes if "jaws (" in n or "bigger than" in n or "smaller than" in n]
            check((not said) if word is None else any(word in n for n in said),
                  "G: Ø%d stock -> %s" % (dia, said or "no grip-range note"))
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
        # each clamp object is drawn at its own angle (it was drawn at 0 degrees) ...
        mid = clamps[1].Shape.BoundBox.Center
        check(abs(math.degrees(math.atan2(mid.y, mid.x)) - 120) < 1, "D: the 120 degree clamp is drawn at 120 (%s)" % mid)
        # ... and turned, it moves in to the stock edge again (the plate is 70 x 40: far corner)
        r0 = clamps[2].Radius.Value
        clamps[2].Angle = 270
        doc.recompute()
        check(abs(clamps[2].Radius.Value - (16 - clamps[2].Overlap.Value)) < 1e-6 and clamps[2].Radius.Value != r0,
              "D: turned to 270, the clamp reaches the stock edge (radius %.2f)" % clamps[2].Radius.Value)
        clamps[2].Angle = 240
        doc.recompute()
        op = custom(job, "OnPlate", ["G0 X0 Y0 Z30", "G1 Z19 F100", "G1 X20 F300", "G0 Z30"])
        check(not policy.check(op)[0], "D: a cut on the plate clears the clamps: %s" % policy.check(op)[0][:1])
        far = custom(job, "IntoClamp", ["G0 X0 Y0 Z30", "G1 Z19 F100", "G1 X60 F300", "G0 Z30"])
        msgs = policy.check(far)[0]
        check(len(msgs) == 1 and "WILL CRASH" in msgs[0] and "clamp" in msgs[0],
              "D: a cut out over a clamp will crash: %s" % msgs)
        doc.removeObject(far.Name)
        doc.recompute()
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
