# Polar CNC — test of the simulator in a real FreeCAD (run by tests/freecad/run.sh).
#
# A polar Job with an off-centre pocket is opened in the simulator: the scene is added, the Job's
# own objects are hidden, the cutter is where the program says in both views (machine view: the
# part turns by -C and the cutter stays on +X; part view: the cutter is over the part point),
# playing moves time forward, and closing removes everything and shows the Job again.
# Screenshots of both views are written for a person to look at.
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
from common import OUT, build_job, check, fails, finish, log, pump  # noqa: E402


def close(a, b, tol=1e-4):   # Coin keeps positions as 32-bit floats
    return all(abs(x - y) < tol for x, y in zip(a, b))


def shot(name):
    """The window as a person sees it (View3D.saveImage renders without the simulator's nodes)."""
    pump(200)
    Gui.getMainWindow().grab().save(os.path.join(OUT, name))


def go():
    try:
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        doc, job, ops = build_job(pocket_off_centre=True)
        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        job.PolarXMax = 125
        tc = job.Tools.Group[0]
        tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
        doc.recompute()
        check(Gui.Command.get("PolarCNC_Simulate").isActive(), "Simulate is active for a polar Job")

        from polarcnc import simulator
        before = {o.Name: o.ViewObject.Visibility for o in doc.Objects if getattr(o, "ViewObject", None)}
        panel = simulator.open_for(job)
        pump(300)
        check(panel is not None, "simulator opened")
        m = panel.motion
        check(len(m) > 100 and m.total > 10, "%d points, %.0f s of program" % (len(m), m.total))
        check(m.tool_d == 5.0, "tool diameter from the program: %s" % m.tool_d)
        root = panel.view.getSceneGraph()
        check(root.findChild(panel.scene.root) >= 0, "scene added to the 3D view")
        shown = [o for o in doc.Objects if getattr(o, "ViewObject", None) and o.ViewObject.Visibility]
        check(not shown, "the document's own objects are hidden: %s" % [o.Name for o in shown])

        # machine view at 40 %: part turned by -C, cutter on +X at (r, 0, z)
        panel._jump(0.4 * m.total)
        i, r, c, z = m.at(panel.t)
        tr = panel.scene.tool_at.translation.getValue()
        check(close((tr[0], tr[1], tr[2]), (r, 0, z)), "machine view: cutter at X=r on the X axis")
        check(abs(panel.scene.turn.angle.getValue() + math.radians(c)) < 1e-6, "machine view: part turned by -C")
        shot("machine_view.png")
        # part view: cutter over the part point
        panel.partv.setChecked(True)
        pump(100)
        tr = panel.scene.tool_at.translation.getValue()
        a = math.radians(c)
        check(close((tr[0], tr[1], tr[2]), (r * math.cos(a), r * math.sin(a), z)), "part view: cutter over the part")
        check(panel.scene.turn.angle.getValue() == 0, "part view: part does not turn")
        shot("part_view.png")
        panel._jump(m.total)
        shot("part_view_end.png")
        panel.machine.setChecked(True)
        shot("machine_view_end.png")

        # play
        panel._jump(0.0)
        panel._toggle()
        pump(600)
        panel._toggle()
        check(panel.t > 1.0, "playing moves the time on (%.1f s of program in 0.6 s at 20x)" % panel.t)

        # close
        check(Gui.Control.activeDialog(), "the simulator is the open task dialog")
        panel.reject()
        pump(200)
        check(root.findChild(panel.scene.root) < 0, "closing removes the scene")
        after = {o.Name: o.ViewObject.Visibility for o in doc.Objects if getattr(o, "ViewObject", None)}
        check(after == before and any(before.values()),
              "closing puts every object's visibility back: %s" % {k: v for k, v in before.items() if v})
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
