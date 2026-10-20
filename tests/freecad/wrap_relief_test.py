# Polar CNC — a relief round a bar, machined with three cutters one after the other (run by
# tests/freecad/run.sh, own start).
#
# The part: a bar R20 x 60 (its lower 10 mm in the 3-jaw chuck), round it a raised rib, a narrow
# groove (1.2 wide), a slot along the bar (2 wide) and a dimple. Stock D44.
#   1. Polar Wrap, flat Ø6, Strategy Roughing.
#   2. Polar Wrap, ball Ø2, Strategy Finishing, After operation = 1: it starts from what 1 left
#      (without it a finishing pass alone would be refused: too deep for one pass).
#   3. Polar Wrap, ball Ø1, Strategy Finishing, After operation = 2.
# Checks, independent of the planner where it matters: no cutter ever inside the part or the
# chuck (the polar program read back as the machine moves, the cutter body against the solid);
# the tool report says what each cutter leaves, the Ø2 one names a smaller ball for the groove,
# and the Ø1 one reaches it; the leftover each report gives is checked against the solid; time.
# Screenshots of the simulator for a person to look at.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math
import os
import sys
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, catch_messages, check, fails, finish, log, pump  # noqa: E402
from cutcheck import gouges, keepout, moves  # noqa: E402

V = App.Vector


def relief():
    import Part
    bar = Part.makeCylinder(20, 60)
    bar = bar.fuse(Part.makeCylinder(21.5, 3, V(0, 0, 46)))                       # rib 3 x 1.5
    bar = bar.cut(Part.makeCylinder(25, 1.2, V(0, 0, 40)).cut(Part.makeCylinder(18.8, 1.2, V(0, 0, 40))))
    bar = bar.cut(Part.makeBox(3, 2, 10, V(18.8, -1, 26)))                        # slot along Z
    bar = bar.cut(Part.makeSphere(3, V(-22, 0, 31)))                              # dimple 1 deep
    return bar.removeSplitter()


def tool_controller(job, label, shape, diameter, number):
    from Path.Tool import Controller
    from Path.Tool.toolbit import ToolBit
    bit = ToolBit.from_shape_id(shape)
    tool = bit.attach_to_doc(doc=job.Document)
    tool.Diameter = diameter
    if tool.ViewObject:
        tool.ViewObject.Visibility = False
    tc = Controller.Create(label, tool=tool, toolNumber=number)
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    job.Proxy.addToolController(tc)
    return tc


def go():
    try:
        from Path.Main import Job as PathJob
        from Path.Main.Gui import Job as PathJobGui
        from polarcnc import chuck as ch, machine, polarwrap, simulator
        Gui.activateWorkbench("CAMWorkbench")
        Gui.getMainWindow().resize(1500, 950)
        boxes = []
        catch_messages(boxes)
        doc = App.newDocument("Relief")
        part = doc.addObject("Part::Feature", "Relief")
        part.Shape = relief()
        doc.recompute()
        job = PathJob.Create("Job", [part], None)
        job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
        doc.recompute()
        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        job.PolarXMax = 125
        job.PolarLayout = machine.WRAP
        job.PolarWrapDiameter = 44
        job.PolarWrapToolLengthInX = True
        job.PostProcessorArgs = "--no-show-editor"
        held = ch.make_chuck(job, "3-jaw SAN OU K11-125 (Ø125)")
        held.GripLength = 10
        doc.recompute()
        t6 = tool_controller(job, "T1 flat 6", "endmill.fcstd", 6, 1)
        t2 = tool_controller(job, "T2 ball 2", "ballend.fcstd", 2, 2)
        t1 = tool_controller(job, "T3 ball 1", "ballend.fcstd", 1, 3)
        class Uses:
            ToolController = t2
        check(polarwrap.tool_of(Uses)[1] and not polarwrap.tool_of(type("U6", (), {"ToolController": t6}))[1],
              "the ball end is seen as a ball end, the flat one as flat")

        model = job.Model.Group[0].Shape

        # with several tool controllers CAM asks which one (a dialog): the test says it instead
        import PathScripts.PathUtils as PathUtils
        chosen = [t6]
        PathUtils.findToolController = lambda obj, proxy, name=None: chosen[0]

        def op(label, tc, strategy, after=None, **props):
            chosen[0] = tc
            o = polarwrap.Create(label, parentJob=job)
            o.ToolController = tc
            o.Strategy = strategy
            o.AfterOperation = after
            for k, v in props.items():
                setattr(o, k, v)
            t = time.time()
            doc.recompute()
            log.write("     %s: %d commands in %.1f s; report: %s\n"
                      % (label, len(o.Path.Commands), time.time() - t, o.ToolReport))
            return o

        rough = op("Rough6", t6, "Roughing", FinishAllowance=0.3, StepDown=1.0)
        check(len(rough.Path.Commands) > 100, "roughing Ø6: a path (%d)" % len(rough.Path.Commands))
        alone = op("FinishAlone", t2, "Finishing", StepOver=15)
        check(len(alone.Path.Commands) < 5, "finishing Ø2 alone from the bar: refused (too deep)")
        doc.removeObject(alone.Name)
        # finishing alone after it is still too deep where the Ø6 did not fit (1.5 mm beside the rib):
        # refused; roughing + finishing after it roughs only what the Ø6 left
        only = op("FinishOnly", t2, "Finishing", after=rough, StepOver=15)
        check(len(only.Path.Commands) < 5, "Ø2 finishing alone after the Ø6: refused where the Ø6 left 1.5 mm")
        doc.removeObject(only.Name)
        fin2 = op("Finish2", t2, "Roughing + finishing", after=rough, StepOver=15, FinishAllowance=0.1)
        check(len(fin2.Path.Commands) > 100, "Ø2 roughing + finishing after the Ø6: a path (%d)" % len(fin2.Path.Commands))
        # the roughing alone, after the Ø6 and from the bar: how much each cuts
        rest = op("Rest2", t2, "Roughing", after=rough, FinishAllowance=0.1)
        full = op("Full2", t2, "Roughing", FinishAllowance=0.1)

        def cutting(o):
            """mm cut at the cutting feed (the rest goes at the air feed)."""
            feed = o.ToolController.HorizFeed.Value
            total, last = 0.0, None
            for c in o.Path.Commands:
                p = c.Parameters
                if "X" in p and "Z" in p:
                    here = V(p["X"], p.get("Y", 0), p["Z"])
                    if last is not None and c.Name == "G1" and abs(p.get("F", 0) - feed) < 1e-6:
                        total += (here - last).Length
                    last = here
            return total
        a, b = cutting(rest), cutting(full)
        # (it still cuts beside the rib where the Ø6 did not fit, and the 2 mm by the chuck the
        # Ø6 kept clear of with its bigger radius)
        check(b > 0 and a < 0.7 * b, "Ø2 roughing after the Ø6 cuts %.0f mm, from the bar %.0f mm" % (a, b))
        doc.removeObject(rest.Name)
        doc.removeObject(full.Name)
        check("Ø1." in fin2.ToolReport or "Ø1.0" in fin2.ToolReport or "Ø0." in fin2.ToolReport,
              "the Ø2 report names a smaller ball for the groove: %s" % fin2.ToolReport)
        fin1 = op("Finish1", t1, "Roughing + finishing", after=fin2, StepOver=15, FinishAllowance=0.1)
        check(len(fin1.Path.Commands) > 100, "Ø1 roughing + finishing after the Ø2: a path (%d)" % len(fin1.Path.Commands))

        # every operation alone, the way Post Process writes it, followed against the solid
        made = [rough, fin2, fin1]
        for o in made:
            for x in made:
                x.Active = (x is o)
            doc.recompute()
            pts, R = moves(job)
            gouges(o.Label, pts, R, model, keepout(held), wrap=True)
        for x in made:
            x.Active = True
        doc.recompute()

        # the reports, against the solid: where the Ø2 report says material is left, the solid
        # has the narrow groove there
        import re
        m = re.search(r"Z ([\d.]+), C", fin2.ToolReport)
        check(m is not None and 39.5 <= float(m.group(1)) <= 41.7,
              "the Ø2 leaves its material at the 1.2 mm groove (Z 40-41.2): %s" % (m.group(1) if m else None))
        check("does not get down" in fin2.ToolReport, "the Ø2 says it does not get down into the groove")
        check(fin1.ToolReport.startswith("Ø1.0 ball gets down into every hollow") or
              fin1.ToolReport.startswith("Ø1.0 ball reaches every detail"),
              "the Ø1 gets down into the groove: %s" % fin1.ToolReport)

        from Path.Post.Processor import PostProcessorFactory
        from polarcnc import program
        try:                                   # the program as converted, for a person to read
            text, _opts = program.polar(job)
            open(os.path.join(OUT, "relief_polar.ngc"), "w").write(text)
        except Exception as e:
            log.write("     polar program: %s\n" % e)
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        out = res[0][1] if res else None
        check(out is not None and "G93" in out and "T2" in out and "T3" in out,
              "Post Process writes the three tools in one program %s" % boxes[-1:])
        if out:
            open(os.path.join(OUT, "relief.ngc"), "w").write(out)
        panel = simulator.open_for(job)
        pump(400)
        check(panel is not None, "the simulator opens")
        if panel is not None:
            panel.partv.setChecked(True)
            for name, f in (("relief_rough.png", 0.30), ("relief_finish2.png", 0.75), ("relief_end.png", 0.999)):
                panel._jump(panel.motion.total * f)
                pump(300)
                Gui.getMainWindow().grab().save(os.path.join(OUT, name))
            panel.reject()
            pump(300)
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    finish()


QtCore.QTimer.singleShot(3000, go)
