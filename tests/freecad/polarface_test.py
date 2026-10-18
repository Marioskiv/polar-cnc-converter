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

        # what to cut: the square stock (50 x 50, Z0..20) round the round part (R15 up to Z10, R6
        # boss up to Z15). Cutter radius from the tool controller.
        from polarcnc import polarface as pf
        rad = op.ToolController.Tool.Diameter.Value / 2

        def at(z):
            """Radii of every cutting point at depth z (arc ends and line ends)."""
            out, x, y, zz = [], None, None, None
            for c in op.Path.Commands:
                pr = c.Parameters
                x, y, zz = pr.get("X", x), pr.get("Y", y), pr.get("Z", zz)
                if c.Name in ("G1", "G2", "G3") and zz is not None and abs(zz - z) < 1e-6 and x is not None:
                    out.append(math.hypot(x, y))
            return out

        check(op.Clearing == pf.FACE_ONLY, "Polar Face starts as 'face only'")
        op.Clearing = pf.WHOLE
        doc.recompute()
        def cut_length():
            total, x, y = 0.0, None, None
            for c in op.Path.Commands:
                pr = c.Parameters
                nx, ny = pr.get("X", x), pr.get("Y", y)
                if x is not None and c.Name == "G1":
                    total += math.hypot(nx - x, ny - y)
                elif x is not None and c.Name in ("G2", "G3"):
                    r = math.hypot(pr["I"], pr["J"])
                    a0, a1 = math.atan2(y, x), math.atan2(ny, nx)
                    sw = (a0 - a1) if c.Name == "G2" else (a1 - a0)
                    total += r * (sw % (2 * math.pi))
                x, y = nx, ny
            return total

        check(abs(op.FinalDepth.Value - 0) < 1e-6, "all the stock: down to the part bottom (%s)" % op.FinalDepth)
        zs = sorted({c.Parameters["Z"] for c in op.Path.Commands if c.Name in ("G1", "G2", "G3") and "Z" in c.Parameters})
        z = min(z for z in zs if z < 10 - 1e-6)
        rs = at(z)
        check(rs and min(rs) > 15 + rad - 0.05 and max(rs) > 30,
              "all the stock at Z%.2f: from the part (R%.2f) out to the corners (R%.2f)" % (z, min(rs), max(rs)))
        whole_len = cut_length()
        op.Clearing = pf.BAND
        op.BandWidth = 6
        doc.recompute()
        rs = at(z)
        check(rs and min(rs) > 15 + rad - 0.05 and max(rs) < 15 + 6 + 0.05,
              "band 6 mm at Z%.2f: only R%.2f .. R%.2f, the corners stay" % (z, min(rs), max(rs)))
        band_len = cut_length()
        check(band_len < 0.7 * whole_len, "the band cuts less than clearing everything (%.0f vs %.0f mm)" % (band_len, whole_len))
        top = at(max(zs))
        check(top and max(top) < 15 + 6 + 0.05, "band: above the part only the band (and the part top) is cut")
        # into the material: ramps along the circle, no plunge (the band is closed in by stock)
        def plunges():
            """Straight-down G1 moves that end below the depth before them (into material)."""
            n = 0
            levels = sorted({c.Parameters["Z"] for c in op.Path.Commands
                             if c.Name in ("G2", "G3") and "Z" in c.Parameters}, reverse=True)
            for c in op.Path.Commands:
                pr = c.Parameters
                if c.Name == "G1" and set(pr) <= {"Z", "F"} and "Z" in pr:
                    above = [l for l in levels if l > pr["Z"] + 1e-6]
                    if above and pr["Z"] < min(above) - 1e-6 and pr["Z"] in levels:
                        n += 1

            return n

        def steepest():
            worst, x, y, zz = 0.0, None, None, None
            for c in op.Path.Commands:
                pr = c.Parameters
                nx, ny, nz = pr.get("X", x), pr.get("Y", y), pr.get("Z", zz)
                if c.Name == "G1" and x is not None and zz is not None and nz < zz - 1e-9:
                    d = math.hypot(nx - x, ny - y)
                    if d > 1e-6:
                        worst = max(worst, math.degrees(math.atan2(zz - nz, d)))
                x, y, zz = nx, ny, nz
            return worst

        check(abs(op.RampAngle.Value - 3) < 1e-9, "ramp angle 3 degrees by default")
        check(plunges() == 0, "band: no straight plunge into the material (%d)" % plunges())
        check(0 < steepest() <= 3.0 + 0.01, "band: ramps at most 3 degrees (%.2f)" % steepest())
        op.RampAngle = 0
        doc.recompute()
        check(plunges() > 0 and steepest() == 0, "ramp 0: straight down again (%d plunges)" % plunges())
        op.RampAngle = 3
        doc.recompute()
        panel_ok = True
        try:
            from polarcnc import polarface_gui
            page = polarface_gui.TaskPanelOpPage(op, 0)
            form = page.getForm()
            page.form = form
            page.setFields(op)
            panel_ok = page.clearing.currentText() == pf.BAND and page.band.isEnabled() and page.band.value() == 6
        except Exception as e:
            log.write("panel: %s\n" % e)
            panel_ok = False
        check(panel_ok, "the panel shows 'what to cut' and the band width")
        op.Clearing = pf.FACE_ONLY
        doc.recompute()
        check(abs(op.FinalDepth.Value - 15) < 1e-6, "back to face only: down to the part top again")
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
