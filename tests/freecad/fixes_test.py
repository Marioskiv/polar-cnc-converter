# Polar CNC — FreeCAD test of the 2.22.0 fixes (from the review of 2026-10-20), in a real FreeCAD:
# a cutter with no diameter is refused when a chuck is set up; a Job that splits its output writes
# no file when one of its files is refused, and the simulator plays the files one after the other;
# the setup note says to touch off Z on the stock top; a program edited by hand in the post's
# editor is checked again; drilling cycles count in the Cartesian checks; a Polar Wrap operation
# that cannot be made leaves nothing behind.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import build_job, check, fails, finish, log, catch_messages  # noqa: E402


def tool_controller(job, label, diameter, number):
    from Path.Tool import Controller
    from Path.Tool.toolbit import ToolBit
    bit = ToolBit.from_shape_id("endmill.fcstd")
    tool = bit.attach_to_doc(doc=job.Document)
    tool.Diameter = diameter
    if tool.ViewObject:
        tool.ViewObject.Visibility = False
    tc = Controller.Create(label, tool=tool, toolNumber=number)
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    job.Proxy.addToolController(tc)
    return tc


def export(job):
    from Path.Post.Processor import PostProcessorFactory
    return PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()


def go():
    try:
        Gui.activateWorkbench("CAMWorkbench")
        from polarcnc import chuck as ch, collision, program
        msgs = []
        catch_messages(msgs)

        doc, job, ops = build_job()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        job.PolarXMax = 125
        job.PostProcessorArgs = "--no-show-editor"
        tc1 = job.Tools.Group[0]
        tc1.HorizFeed, tc1.VertFeed = 600, 200
        held = ch.make_chuck(job, "3-jaw SAN OU K11-125 (Ø125)")
        held.GripLength = 4                 # jaws up to Z 4; the Profile stops at Z 6 above them
        ops[0].setExpression("FinalDepth", None)
        ops[0].FinalDepth = 7
        doc.recompute()
        res = export(job)
        check(res and res[0][1] is not None, "the test Job itself is fine with this chuck: %r" % (msgs[-1:] or ""))

        # 1. a cutter with no diameter: with a chuck set up it would be checked as a point
        tool = tc1.Tool
        good = tool.Diameter.Value
        tool.Diameter = 0
        doc.recompute()
        n0 = len(msgs)
        res = export(job)
        check(res and all(g is None for _n, g in res), "no diameter + chuck -> no file")
        check(len(msgs) > n0 and "no diameter" in msgs[-1], "no diameter -> message: %r" % (msgs[-1:] or ""))
        stops, _notes = program.check_operation(job, ops[0])
        check(any(k == "no diameter" for k, _t in stops), "live check: no diameter is a stop: %s" % stops)
        tool.Diameter = good
        doc.recompute()
        res = export(job)
        polar = res[0][1] if res else None
        check(polar is not None, "with its diameter back: written")

        # 2. the setup note: touch off Z on the stock TOP
        check(polar is not None and "Touch off Z on the stock TOP" in polar and "touch off Z there" not in polar,
              "setup note: touch off Z on the stock top")

        # 3. split output: one file per tool; one of them runs into a jaw -> no file at all
        tc2 = tool_controller(job, "T2", 4, 2)
        ops[1].ToolController = tc2
        doc.recompute()
        job.SplitOutput = True
        job.OrderOutputBy = "Tool"
        doc.recompute()
        res = export(job)
        check(res and len(res) == 2 and all(g is not None for _n, g in res),
              "split by tool, all fine: 2 files (%s)" % [n for n, _g in (res or [])])
        text, _opts = program.polar(job)
        check(text.count("( Polar G-code - G93") == 2,
              "simulator program: the two files one after the other, each converted on its own")
        # a cut with T2 straight down into a jaw
        obs = collision.obstacles(held)
        jaw = [o for o in obs if o[0] != "chuck body"][0]
        a = jaw[2][0]                      # on round stock a jaw is a ring (any angle): its middle
        import numpy
        rr = numpy.hypot(a[:, 0], a[:, 1])
        cx, cy = float(rr.min() + rr.max()) / 2.0, 0.0
        import Path.Op.Custom as Custom
        bad = Custom.Create("IntoTheJaw", parentJob=job)
        bad.Source = "Text"
        bad.Gcode = ["G0 X%.3f Y%.3f Z%.3f" % (cx, cy, jaw[1] + 5), "G1 Z%.3f F100" % (jaw[1] - 1),
                     "G0 Z%.3f" % (jaw[1] + 5)]
        bad.ToolController = tc2
        doc.recompute()
        log.write("     jaw %s top %.2f at (%.2f, %.2f); custom path: %s; sections: %s\n" % (
            jaw[0], jaw[1], cx, cy, [c.toGCode() for c in bad.Path.Commands],
            [(n, [o.Label for o in objs]) for n, objs in program.sections(job)]))
        n0 = len(msgs)
        res = export(job)
        check(res and all(g is None for _n, g in res),
              "split output, the T2 file runs into a jaw: NO file written (%s)"
              % [(n, g is None) for n, g in (res or [])])
        check(len(msgs) > n0 and any("chuck" in m for m in msgs[n0:]),
              "split output refusal names the chuck: %r" % [m[:100] for m in msgs[n0:]])
        check(len(msgs) - n0 == 1, "the refusal card is shown once, not once per file (%d)" % (len(msgs) - n0))
        doc.removeObject(bad.Name)
        job.SplitOutput = False
        doc.recompute()

        # 4. the editor: a hand edit that puts a Y move in is refused, an untouched text is not
        import Path.Post.Utils as PostUtils
        real = PostUtils.GCodeEditorDialog

        class FakeEditor:
            def __init__(self, change):
                self.change = change

                class Ed:
                    def setPlainText(s, t):
                        s.t = t

                    def toPlainText(s):
                        return s.t
                self.editor = Ed()

            def exec_(self):
                if self.change:
                    self.editor.t += "\nG1 X10 Y10 Z1 F1\n"
                return 1
        job.PostProcessorArgs = ""
        try:
            PostUtils.GCodeEditorDialog = lambda: FakeEditor(True)
            n0 = len(msgs)
            res = export(job)
            check(res and res[0][1] is None and len(msgs) > n0 and "as edited" in msgs[-1],
                  "edited with a Y move -> refused: %r" % (msgs[-1:] or ""))
            PostUtils.GCodeEditorDialog = lambda: FakeEditor(False)
            res = export(job)
            check(res and res[0][1] is not None, "not edited -> written")
        finally:
            PostUtils.GCodeEditorDialog = real
            job.PostProcessorArgs = "--no-show-editor"

        # 5. drilling cycles in the Cartesian checks (they were skipped)
        import Path
        p = Path.Path([Path.Command("G0", {"X": 10, "Y": 0, "Z": 5}),
                       Path.Command("G81", {"X": 10, "Y": 0, "Z": -7, "R": 2, "F": 100}),
                       Path.Command("G0", {"Z": 5})])
        P, _I, R = collision.samples(p)
        check(len(P) > 0 and abs(float(P[:, 2].min()) + 7) < 1e-6 and not R[P[:, 2].argmin()],
              "drill cycle followed down to its Z -7 as a feed")
        check(ch.lowest_cut(p) == -7, "lowest cut sees the drill depth (%s)" % ch.lowest_cut(p))

        # 6. a Polar Wrap that cannot be made (no tool controller chosen) leaves nothing behind
        from polarcnc import polarwrap_gui
        import Path.Op.Base as PathOp

        class Res:
            name = "PolarWrap"
            job = None

            @staticmethod
            def objFactory(name, obj=None, parentJob=None):
                doc.addObject("Path::FeaturePython", "HalfMade")
                raise PathOp.PathNoTCException()
        Res.job = job
        before = len(doc.Objects)
        made = polarwrap_gui.create(Res)
        check(made is None and len(doc.Objects) == before,
              "Polar Wrap with no tool controller chosen: nothing left (%d -> %d)" % (before, len(doc.Objects)))
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
