# Polar CNC — Polar Face in a real FreeCAD (run by tests/freecad/run.sh, own FreeCAD start).
#
# A part with a boss in SQUARE stock: the polar Job offers Polar Face and greys out FreeCAD's
# Facing; Polar Face is created the way its button does (task panel opens, closes), its path is
# made of arcs centred on the chuck axis, the polar program converts, and the simulator shows
# it (screenshot for a person to look at).
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


def build():
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    doc = App.newDocument("PolarFace")
    p = doc.addObject("Part::Feature", "Part")
    p.Shape = Part.makeCylinder(15, 10).fuse(Part.makeCylinder(6, 15))
    doc.recompute()
    job = PathJob.Create("Job", [p], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    st = job.Stock                                # 50 x 50 square stock, top at Z20
    st.ExtXneg = st.ExtXpos = st.ExtYneg = st.ExtYpos = 10
    st.ExtZneg, st.ExtZpos = 0, 5
    doc.recompute()
    return doc, job


def go():
    try:
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        doc, job = build()
        bb = job.Stock.Shape.BoundBox
        check(abs(bb.XLength - 50) < 0.05 and abs(bb.ZMax - 20) < 1e-3,   # FreeCAD: model box of a cylinder
              "square stock 50 x 50 up to Z20 (%.4f x %.4f, Z %.4f..%.4f)" % (bb.XLength, bb.YLength, bb.ZMin, bb.ZMax))
        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        job.PolarXMax = 125
        tc = job.Tools.Group[0]
        tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
        doc.recompute()
        from polarcnc import policy
        policy._cache[0] = 0.0
        check(Gui.Command.get("PolarCNC_PolarFace").isActive(), "Polar Face offered in a polar Job")
        check(not Gui.Command.get("CAM_MillFacing").isActive(), "FreeCAD's Facing greyed out")

        # as the button does: the operation, its view provider and its task panel
        from polarcnc import polarface_gui
        polarface_gui.register()
        cmd = polarface_gui.Command()
        cmd.res.job = job
        op = polarface_gui.create(cmd.res)
        pump(500)
        check(op is not None and Gui.Control.activeDialog(), "created; its task panel is open")
        Gui.Control.activeTaskDialog().accept()        # OK (Cancel deletes a new operation)
        pump(300)
        doc.recompute()
        check(op.ViewObject.Proxy.getIcon().endswith("PolarFace.svg"), "own tree icon")
        check(abs(op.StartDepth.Value - 20) < 1e-6 and abs(op.FinalDepth.Value - 15) < 1e-6,
              "depths from the stock top to the part top: %s .. %s" % (op.StartDepth, op.FinalDepth))
        cmds = op.Path.Commands
        arcs = [c for c in cmds if c.Name in ("G2", "G3")]
        check(len(arcs) > 20, "%d arcs in the path" % len(arcs))
        # every arc centred on the chuck axis: start + (I, J) = (0, 0)
        x = y = None
        off = 0
        for c in cmds:
            pr = c.Parameters
            if c.Name in ("G2", "G3") and x is not None:
                if math.hypot(x + pr["I"], y + pr["J"]) > 1e-6:
                    off += 1
            x, y = pr.get("X", x), pr.get("Y", y)
        check(off == 0, "every arc centred on X0 Y0 (%d not)" % off)
        lifts = sum(1 for c in cmds if c.Name == "G0" and "Z" in c.Parameters)
        log.write("info: %d commands, %d arcs, %d Z rapids\n" % (len(cmds), len(arcs), lifts))

        from polarcnc import program
        text, opts = program.polar(job)
        check("G93" in text and text.count("\n") > 50, "the Job converts to polar (%d lines)" % text.count("\n"))
        open(os.path.join(OUT, "polar.ngc"), "w").write(text)

        from polarcnc import simulator
        panel = simulator.open_for(job)
        pump(300)
        panel.partv.setChecked(True)
        panel._jump(panel.motion.total)
        pump(300)
        Gui.getMainWindow().grab().save(os.path.join(OUT, "polar_face_square.png"))
        panel.machine.setChecked(True)
        panel._jump(panel.motion.total * 0.35)
        pump(300)
        Gui.getMainWindow().grab().save(os.path.join(OUT, "polar_face_machine.png"))
        panel.reject()
        pump(200)
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
