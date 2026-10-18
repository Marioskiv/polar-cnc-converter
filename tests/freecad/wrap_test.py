# Polar CNC — a Wrap Job in a real FreeCAD (run by tests/freecad/run.sh, own start).
#
# The real 3D part, nothing drawn flat: a bar R20 x 60 along Z (its lower end in the chuck) with a
# groove round it and a flat, stock diameter 44, the SAN OU K72-125 holding it 10 mm deep, and a
# Polar Wrap operation made from its own command and task panel. Checks: a Wrap Job is not a face
# Job; no diameter and a flat-face operation are refused; Post Process writes the wrapped program
# (roughing from the stock down, the groove floor and the flat reached, stopping clear of the
# jaws); the simulator shows the part, the chuck and the radial router. Screenshots for a person
# to look at.
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
        from polarcnc import chuck as ch, machine, policy, simulator, polarwrap_gui
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        doc = App.newDocument("Wrap")
        bar = doc.addObject("Part::Feature", "Bar")
        shape = Part.makeCylinder(20, 60)
        shape = shape.cut(Part.makeCylinder(30, 7, App.Vector(0, 0, 30)).cut(
            Part.makeCylinder(17, 7, App.Vector(0, 0, 30))))
        shape = shape.cut(Part.makeBox(10, 40, 10, App.Vector(16, -20, 42)))
        bar.Shape = shape
        doc.recompute()
        job = PathJob.Create("Job", [bar], None)
        job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
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
        check(Gui.Command.get("PolarCNC_PolarWrap").isActive() and Gui.Command.get("PolarCNC_Chuck").isActive()
              and not Gui.Command.get("PolarCNC_PolarFace").isActive(),
              "Wrap Job: Polar Wrap and Chuck offered, Polar Face not")

        boxes = []
        QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: boxes.append(a[2]))
        job.PolarWrapDiameter = 44
        held = ch.make_chuck(job)
        held.GripLength = 10
        doc.recompute()
        jaw_top = held.Shape.BoundBox.ZMax
        check(abs(jaw_top - (job.Stock.Shape.BoundBox.ZMin + 10)) < 1e-6
              and any("closed on the stock at 22.00" in n for n in held.Notes),
              "the chuck holds the bar (D44) 10 mm deep, jaw tops at Z %.2f: %s" % (jaw_top, held.Notes))

        # Polar Wrap from its command and task panel, as a user makes it
        polarwrap_gui.register()
        cmd = polarwrap_gui.Command()
        cmd.res.job = job
        op = polarwrap_gui.create(cmd.res)
        for _ in range(50):
            pump(100)
            if Gui.Control.activeTaskDialog() is not None:
                break
        Gui.Control.activeTaskDialog().accept()
        pump(300)
        doc.recompute()
        check(op is not None and len(op.Path.Commands) > 1000,
              "Polar Wrap made %d moves" % (len(op.Path.Commands) if op else 0))

        job.PolarWrapDiameter = 0            # (the operation keeps its path: not recomputed)
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None and boxes and "Wrap diameter is not set" in boxes[-1],
              "no wrap diameter -> refused: %r" % (boxes[-1:] or "")[:100])
        job.PolarWrapDiameter = 44

        other = Custom.Create("FlatOp", parentJob=job)
        other.Source = "Text"
        other.Gcode = ["G0 X0 Y0 Z70"]
        doc.recompute()
        check(any("Polar Wrap" in m for m in policy.problems(other)), "a flat-face operation is warned about")
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None and "only Polar Wrap" in boxes[-1],
              "... and refused by Post Process: %r" % boxes[-1][:100])
        doc.removeObject(other.Name)
        doc.recompute()

        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        text = res[0][1] if res else None
        check(text is not None and text.startswith("( Wrap G-code"),
              "wrapped program written %r" % (boxes[-1:] if text is None else ""))
        if text:
            open(os.path.join(OUT, "wrap.ngc"), "w").write(text)
            g1 = [l for l in text.splitlines() if l.startswith("G1 ")]
            vals = [dict((k, float(v)) for k, v in re.findall(r"([XZC])(-?[\d.]+)", l)) for l in g1]
            xs = [v["X"] for v in vals]
            zs = [v["Z"] for v in vals]
            check(abs(max(xs) - 21) < 0.01, "first roughing layer 1 mm into the stock: X up to %.3f" % max(xs))
            check(15.99 < min(xs) < 16.1, "the flat is reached: X down to %.3f" % min(xs))
            groove = [v["X"] for v in vals if 31.5 <= v["Z"] <= 35.5]
            check(groove and abs(min(groove) - 17) < 0.05, "the groove floor is reached: X %.3f" % min(groove))
            check(min(zs) >= jaw_top + 2 + 2.5 - 1e-6,
                  "it stops clear of the jaws: Z down to %.2f (jaws %.2f + 2 + cutter radius)" % (min(zs), jaw_top))
            check("G93" in text and "G8" in text, "G93 and G8 (X radius)")

        panel = simulator.open_for(job)
        pump(300)
        check(panel is not None and panel.scene.wrap, "simulator opened in wrap mode")
        if panel:
            panel.partv.setChecked(True)
            panel._jump(panel.motion.total * 0.7)
            pump(200)
            _i, _r, c, _z = panel.scene.show(panel.motion.total * 0.7)
            a = panel.scene.tool_turn.angle.getValue()
            check(abs(math.cos(a) - math.cos(math.radians(c))) < 1e-4 and
                  abs(math.sin(a) - math.sin(math.radians(c))) < 1e-4,
                  "part view: the router points at the axis from C %.1f" % c)
            shot("wrap_part_view.png")
            panel.machine.setChecked(True)
            panel._jump(panel.motion.total * 0.7)
            shot("wrap_machine_view.png")
            check(abs(panel.scene.tool_turn.angle.getValue()) < 1e-9, "machine view: the router stays on +X")
            panel.reject()
            pump(200)
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
