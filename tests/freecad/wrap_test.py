# Polar CNC — a Wrap Job in a real FreeCAD (run by tests/freecad/run.sh, own start).
#
# The outside of a cylinder R20 drawn UNROLLED: a plate 60 long (X, along the part) and 2 pi 20
# wide (Y, round it), its top at Z0 (the surface), with a slot and a groove all the way round
# (cut by Custom operations: what is tested here is the wrap, not CAM's pocketing). Checks: a
# Wrap Job is not a face Job (nothing greyed out), no wrap radius is refused, the chuck holds
# the cylinder and a groove inside the jaws is refused, Post
# Process writes the wrapped program (X = 20 + Z, C = Y / 20, Z = X), and the simulator shows
# the cylinder with the router radial. Screenshots for a person to look at.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import re
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, check, fails, finish, log, pump  # noqa: E402

R0 = 20.0
ROUND = 2 * math.pi * R0


def shot(name):
    pump(200)
    Gui.getMainWindow().grab().save(os.path.join(OUT, name))


def go():
    try:
        import Part
        from Path.Main import Job as PathJob
        from Path.Main.Gui import Job as PathJobGui
        import Path.Op.Custom as Custom
        from Path.Post.Processor import PostProcessorFactory
        from polarcnc import machine, policy, simulator
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        doc = App.newDocument("Wrap")
        plate = doc.addObject("Part::Feature", "Unrolled")
        shape = Part.makeBox(60, ROUND, 3, App.Vector(0, 0, -3))
        shape = shape.cut(Part.makeBox(30, 8, 1.5, App.Vector(15, 40, -1.5)))
        plate.Shape = shape
        doc.recompute()
        job = PathJob.Create("Job", [plate], None)
        job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
        doc.recompute()
        slot = Custom.Create("Slot", parentJob=job)          # the slot, cleared along its length
        slot.Source = "Text"
        slot.Gcode = ["G0 Z3", "G0 X17.5 Y42.5", "G1 Z-1.5 F200",
                      "G1 X42.5 F600", "G1 Y45.5", "G1 X17.5", "G0 Z3"]
        groove = Custom.Create("Groove", parentJob=job)
        groove.Source = "Text"
        groove.Gcode = ["G0 Z3", "G0 X5 Y0", "G1 Z-0.5 F200", "G1 Y%.4f F600" % ROUND, "G0 Z3"]
        tc = job.Tools.Group[0]
        tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
        doc.recompute()

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        job.PolarXMax = 125
        job.PolarLayout = machine.WRAP
        job.PostProcessorArgs = "--no-show-editor"
        doc.recompute()
        policy._cache[0] = 0.0
        check(not policy.is_polar(job), "a Wrap Job is not a face Job (no greying out)")
        check(Gui.Command.get("PolarCNC_Chuck").isActive() and not Gui.Command.get("PolarCNC_PolarFace").isActive(),
              "Wrap Job: Chuck offered, Polar Face not")

        boxes = []
        QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: boxes.append(a[2]))
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None and boxes and "Wrap radius is not set" in boxes[-1],
              "no wrap radius -> refused: %r" % (boxes[-1:] or "")[:100])
        job.PolarWrapRadius = R0
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        text = res[0][1] if res else None
        check(text is not None and text.startswith("( Wrap G-code"), "wrapped program written")
        if text:
            open(os.path.join(OUT, "wrap.ngc"), "w").write(text)
            g1 = [l for l in text.splitlines() if l.startswith("G1 ")]
            vals = [dict((k, float(v)) for k, v in re.findall(r"([XZC])(-?[\d.]+)", l)) for l in g1]
            xs = [v["X"] for v in vals]
            cs = [v["C"] for v in vals]
            check(abs(min(xs) - (R0 - 1.5)) < 0.01, "slot floor at X = 20 - 1.5 (%.3f)" % min(xs))
            check(any(abs(c - 360) < 0.01 for c in cs) and any(abs(x - 19.5) < 1e-3 for x in xs),
                  "groove: a full turn (C 360) at X 19.5")
            check(all(0 <= v["Z"] <= 60 for v in vals), "Z along the part, inside 0 .. 60")
            check("G93" in text and "G8" in text, "G93 and G8 (X radius)")

        # the chuck: the part (a cylinder R20 from the stock's X min, the chuck end) held 10 mm
        # deep in the SAN OU K72-125; the groove at X 5 is inside the jaws -> refused
        from polarcnc import chuck as ch
        held = ch.make_chuck(job)
        held.GripLength = 10
        doc.recompute()
        check(any("closed on the stock at 20.00, 20.00, 20.00, 20.00" in n for n in held.Notes),
              "wrap: the jaws close on the cylinder R20: %s" % held.Notes)
        top = job.Stock.Shape.BoundBox.XMin + 10        # the Job's stock has a margin round the model
        check(abs(held.Shape.BoundBox.ZMax - top) < 1e-6,
              "wrap: jaw tops at the chuck end + grip 10 (Z %.2f)" % held.Shape.BoundBox.ZMax)
        boxes[:] = []
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None and boxes and "runs into the chuck" in boxes[-1],
              "groove inside the jaws -> refused: %r" % (boxes[-1:] or "")[:140])
        groove.Gcode = ["G0 Z3", "G0 X30 Y0", "G1 Z-0.5 F200", "G1 Y%.4f F600" % ROUND, "G0 Z3"]
        doc.recompute()
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is not None, "groove moved to X 30, clear of the jaws -> written: %r"
              % (boxes[-1:] if res and res[0][1] is None else ""))

        panel = simulator.open_for(job)
        pump(300)
        check(panel is not None and panel.scene.wrap, "simulator opened in wrap mode")
        if panel:
            panel.partv.setChecked(True)
            panel._jump(panel.motion.total * 0.55)
            pump(200)
            _i, _r, c, _z = panel.scene.show(panel.motion.total * 0.55)
            check(abs(panel.scene.tool_turn.angle.getValue() - math.radians(c)) < 1e-5,
                  "part view: the router points at the axis from C %.1f" % c)
            shot("wrap_part_view.png")
            panel.machine.setChecked(True)
            panel._jump(panel.motion.total * 0.55)
            shot("wrap_machine_view.png")
            check(abs(panel.scene.tool_turn.angle.getValue()) < 1e-9, "machine view: the router stays on +X")
            panel.reject()
            pump(200)
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
