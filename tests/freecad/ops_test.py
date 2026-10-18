# Polar CNC — every usual CAM operation in a polar Job, in a real FreeCAD, end to end: made,
# recomputed, checked against the chuck, written by Post Process as polar G-code, simulated.
# What a person would do for a pocket, a hole, a contour, a facing: none of it may crash, and
# the unsuitable choices only warn.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import sys
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, catch_messages, check, fails, finish, log, pump  # noqa: E402


def run():
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    from Path.Post.Processor import PostProcessorFactory
    from polarcnc import policy, program, setup, simulator
    V = App.Vector
    Gui.activateWorkbench("CAMWorkbench")
    Gui.getMainWindow().resize(1500, 950)
    boxes = []
    catch_messages(boxes)

    # a round plate Ø80 x 12 with a pocket off the centre and two holes (one through the centre)
    doc = App.newDocument("Ops")
    shape = Part.makeCylinder(40, 12)
    shape = shape.cut(Part.makeBox(20, 14, 5, V(8, -7, 7)))            # pocket 5 deep
    shape = shape.cut(Part.makeCylinder(4, 12, V(-22, 10, 0)))         # hole Ø8 off the centre
    shape = shape.cut(Part.makeCylinder(3, 12, V(0, 0, 0)))            # hole Ø6 on the axis
    part = doc.addObject("Part::Feature", "Plate")
    part.Shape = shape
    doc.recompute()
    job = PathJob.Create("Job", [part], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    st = job.Stock
    st.ExtXneg = st.ExtXpos = st.ExtYneg = st.ExtYpos = 3
    st.ExtZneg, st.ExtZpos = 8, 1
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 125
    job.PostProcessorArgs = "--no-show-editor"
    doc.recompute()
    model = job.Model.Group[0]
    held = setup.apply_chuck(job, setup.MY_CHUCKS[1], 8)
    check(held is not None and held.ViewObject.DisplayMode, "the K72 chuck is drawn")

    def face(test):
        for k, f in enumerate(model.Shape.Faces, 1):
            if test(f):
                return "Face%d" % k
        return None
    floor = face(lambda f: abs(f.CenterOfMass.z - 7) < 1e-6 and f.Area < 300)
    hole_off = face(lambda f: f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - 4) < 1e-6)
    hole_mid = face(lambda f: f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - 3) < 1e-6)
    check(floor and hole_off and hole_mid, "faces found: %s %s %s" % (floor, hole_off, hole_mid))

    made = []

    def make(label, module, base, **props):
        """Create an operation as its button does (module.Create), set it up, recompute."""
        t = time.time()
        try:
            mod = __import__(module, fromlist=["Create"])
            op = mod.Create(label, parentJob=job) if "parentJob" in mod.Create.__code__.co_varnames else mod.Create(label)
            if base is not None:
                op.Base = base
            for k, v in props.items():
                setattr(op, k, v)
            doc.recompute()
            n = len(op.Path.Commands)
            check(n > 3, "%s: made a path (%d commands, %.1f s)" % (label, n, time.time() - t))
            made.append(op)
            return op
        except Exception:
            log.write(traceback.format_exc())
            check(False, "%s: made without an exception" % label)
            return None

    prof = make("Profile", "Path.Op.Profile", [(model, ())])
    make("PocketOffset", "Path.Op.PocketShape", [(model, (floor,))], ClearingPattern="Offset")
    zz = make("PocketZigZag", "Path.Op.PocketShape", [(model, (floor,))], ClearingPattern="ZigZag")
    make("HelixOff", "Path.Op.Helix", [(model, (hole_off,))])
    make("DrillOff", "Path.Op.Drilling", [(model, (hole_off,))])
    make("DrillMid", "Path.Op.Drilling", [(model, (hole_mid,))])
    try:
        import Path.Op.Adaptive  # noqa: F401
        make("Adaptive", "Path.Op.Adaptive", [(model, (floor,))])
    except ImportError:
        log.write("Adaptive not in this FreeCAD: skipped\n")
    from polarcnc import polarface as pf
    face_op = make("PolarFace", "polarcnc.polarface", None)

    # the warnings: ZigZag is not for polar, Adaptive is said to be heavy
    said = [m for op in made for m in policy.problems(op)]
    check(zz is not None and any("ZigZag" in m for m in policy.problems(zz)), "ZigZag pocket -> warning: %s" % policy.problems(zz) if zz else "")
    log.write("warnings: %s\n" % said)

    # greyed out in a polar Job, offered in an ordinary one
    policy._cache[0] = 0.0
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    pump(200)
    for name in ("CAM_MillFacing", "CAM_Surface", "CAM_Waterline", "CAM_Pocket3D"):
        cmd = Gui.Command.get(name)
        if cmd is not None:
            check(not cmd.isActive(), "%s greyed out in a polar Job" % name)
    for name in ("CAM_Profile", "CAM_Pocket_Shape", "CAM_Helix", "CAM_Drilling"):
        cmd = Gui.Command.get(name)
        if cmd is not None:
            check(cmd.isActive(), "%s offered in a polar Job" % name)

    # a Wrap Job: only Polar Wrap is offered
    from polarcnc import machine
    job.PolarLayout = machine.WRAP
    job.PolarWrapDiameter = 86
    policy._cache[0] = 0.0
    pump(200)
    for name in ("CAM_Profile", "CAM_Pocket_Shape", "CAM_Helix", "CAM_Drilling", "CAM_MillFacing"):
        cmd = Gui.Command.get(name)
        if cmd is not None:
            check(not cmd.isActive(), "%s greyed out in a Wrap Job" % name)
    check(Gui.Command.get("PolarCNC_PolarWrap").isActive(), "Polar Wrap offered in a Wrap Job")
    job.PolarLayout = machine.FACE
    policy._cache[0] = 0.0
    pump(200)
    check(Gui.Command.get("CAM_Profile").isActive(), "back to polar: Profile offered again")

    # every clearing of Polar Face, with the chuck
    for mode in (pf.FACE_ONLY, pf.WHOLE, pf.BAND):
        if face_op is None:
            break
        face_op.Clearing = mode
        t = time.time()
        doc.recompute()
        check(len(face_op.Path.Commands) > 10 and time.time() - t < 30,
              "Polar Face '%s': %d commands in %.1f s" % (mode, len(face_op.Path.Commands), time.time() - t))
    if face_op is not None:
        face_op.Clearing = pf.FACE_ONLY
        doc.recompute()

    # each operation alone, then all together, through Post Process and the simulator
    for op in made:
        for o in made:
            o.Active = (o is op)
        doc.recompute()
        boxes[:] = []
        try:
            text, opts = program.polar(job)
            ok = "G93" in text or "G94" in text
        except Exception as e:
            ok = False
            log.write("%s: %s\n" % (op.Label, e))
        check(ok, "%s: converted to polar G-code" % op.Label)
    for o in made:
        o.Active = True
    doc.recompute()
    # the Profile goes down to the part bottom, into the jaws that hold the 8 mm under it:
    # Post Process must refuse that, and write the program once the Profile stops above them
    boxes[:] = []
    res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
    check(res and res[0][1] is None and boxes and "runs into the chuck" in boxes[-1],
          "a Profile down into the jaws is refused: %r" % (boxes[-1:] or "")[:120])
    if prof is not None:
        prof.setExpression("FinalDepth", None)
        prof.FinalDepth = 1.0
        doc.recompute()
    boxes[:] = []
    res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
    out = res[0][1] if res else None
    check(out is not None and "G93" in out, "Post Process of all of them: written (%s)" % (boxes[-1:] if out is None else "%d lines" % out.count("\n")))
    if out is not None:
        open(os.path.join(OUT, "all.ngc"), "w").write(out)
    panel = simulator.open_for(job)
    pump(500)
    check(panel is not None, "the simulator opens with all of them")
    if panel is not None:
        panel._jump(panel.motion.total * 0.6)
        pump(300)
        Gui.getMainWindow().grab().save(os.path.join(OUT, "ops_sim.png"))
        panel.reject()
        pump(300)


def go():
    try:
        run()
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    finish()


QtCore.QTimer.singleShot(2000, go)
