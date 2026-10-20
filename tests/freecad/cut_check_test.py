# Polar CNC — does the machine cut the right thing? (run by tests/freecad/run.sh, own start)
#
# An independent check of what comes out at the end: the polar program, read back the way
# LinuxCNC moves the joints (X, C, Z), is followed point by point and the cutter's own body is
# tested against the solid part and the chuck with FreeCAD's isInside: it may never be inside the
# part (gouge) or a jaw. And it must not leave what it was asked to cut: FreeCAD's Face must reach
# the part top everywhere over the part, Polar Wrap must come down to the bar all round.
# Face: FreeCAD's Face in every pattern it offers (round and square stock, both chucks; on a
# faceplate its rectangle runs over the clamps: Polar CNC must say it will crash, and this check
# must find the same) and the usual CAM operations (Profile, Pocket, Helix, Drilling) through the
# polar conversion. Wrap: Polar Wrap on a bar with a groove and a flat.
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
from common import check, fails, finish, log, pump, catch_messages  # noqa: E402

from cutcheck import V, first_inside, face_probes, gouges, keepout, moves, spread  # noqa: E402


def face_covered(label, pts, R, part, z_top):
    """Facing: over the part, the top is cut down to the part top everywhere (a point counts
    as cut when the cutter passed over it at the part top or lower)."""
    bb = part.BoundBox
    low = [(r * math.cos(a), r * math.sin(a)) for r, a, z, rapid in pts if not rapid and z <= z_top + 0.01]
    if not low:
        check(False, "%s: nothing cut at the part top" % label)
        return
    import numpy
    P = numpy.array(low)
    missed = []
    n = 0
    step = 1.5
    x = bb.XMin + 0.5
    while x < bb.XMax - 0.5:
        y = bb.YMin + 0.5
        while y < bb.YMax - 0.5:
            if part.isInside(V(x, y, z_top - 0.05), 1e-4, True):
                n += 1
                d2 = ((P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2).min()
                if d2 > (0.98 * R) ** 2:
                    missed.append((round(x, 1), round(y, 1), round(math.sqrt(d2), 2)))
            y += step
        x += step
    check(n > 20 and not missed, "%s: the whole part top is cut (%d points looked at%s)"
          % (label, n, "" if not missed else ", NOT cut at %d, e.g. %s" % (len(missed), missed[:4])))


def wrap_covered(label, pts, R, r_part, z_lo, z_hi, leave):
    """Polar Wrap: on a plain stretch of the bar, the tip comes down to the bar all round."""
    import numpy
    cut = numpy.array([(r, a, z) for r, a, z, rapid in pts if not rapid])
    worst = 0.0
    where = None
    z = z_lo
    while z <= z_hi:
        for k in range(36):
            a = k * math.pi / 18
            near = numpy.abs(cut[:, 2] - z) < 0.7 * R
            da = numpy.abs((cut[:, 1] - a + math.pi) % (2 * math.pi) - math.pi) * r_part
            sel = cut[near & (da < 0.7 * R)]
            reach = sel[:, 0].min() if len(sel) else 1e9
            if reach - r_part > worst:
                worst, where = reach - r_part, (z, math.degrees(a))
        z += 2.0
    check(worst <= leave + 0.05, "%s: the bar is cut down to R%.1f all round (worst %.3f mm above%s)"
          % (label, r_part, worst, "" if where is None else " at Z %.1f C %.0f" % where))


def make_face_job(doc_name, shape, round_stock, preset):
    import Part  # noqa: F401
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    from polarcnc import setup
    doc = App.newDocument(doc_name)
    part = doc.addObject("Part::Feature", "Part")
    part.Shape = shape
    doc.recompute()
    job = PathJob.Create("Job", [part], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    if round_stock:
        from Path.Main import Stock as PathStock
        old = job.Stock
        job.Stock = PathStock.CreateCylinder(job, 28, 18)
        doc.removeObject(old.Name)
    else:
        st = job.Stock
        st.ExtXneg = st.ExtXpos = st.ExtYneg = st.ExtYpos = 3
        st.ExtZneg, st.ExtZpos = 6, 2
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    tc.SpindleSpeed = 12000
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 125
    job.PostProcessorArgs = "--no-show-editor"
    doc.recompute()
    held = setup.apply_chuck(job, preset, 5)
    doc.recompute()
    return doc, job, held


def face_cases():
    """FreeCAD's Face (MillFacing) in a polar Job, every pattern this FreeCAD offers."""
    import Part
    import Path.Op.MillFacing as MillFacing
    from polarcnc import policy, setup
    cases = [
        ("round part, round stock, 3-jaw", Part.makeCylinder(25, 15), True, setup.MY_CHUCKS[0], False),
        ("square part, square stock, 4-jaw", Part.makeBox(40, 30, 15, V(-20, -15, 0)), False, setup.MY_CHUCKS[1], False),
        ("long plate, faceplate and clamps", Part.makeBox(100, 50, 10, V(-50, -25, 0)), False, "Faceplate Ø250", True),
    ]
    for name, shape, round_stock, preset, crashes in cases:
        doc, job, held = make_face_job("Cut%d" % len(fails), shape, round_stock, preset)
        if crashes:                       # four strap clamps over the plate's edges
            from polarcnc import chuck as chuckmod
            for a in (20, 160, 200, 340):
                chuckmod.add_clamp(held, a)
            doc.recompute()
        part = job.Model.Group[0].Shape
        z_top = part.BoundBox.ZMax
        obs = keepout(held)
        check(bool(obs), "%s: the chuck is there to check against (%d pieces)" % (name, len(obs)))
        op = MillFacing.Create("MillFacing", parentJob=job)
        doc.recompute()
        for pattern in op.getEnumerationsOfProperty("ClearingPattern"):
            op.ClearingPattern = pattern
            t = time.time()
            doc.recompute()
            label = "%s, Face %s" % (name, pattern)
            n = len(op.Path.Commands)
            if n < 5:
                check(False, "%s: a path (%d commands)" % (label, n))
                continue
            log.write("     %s: %d commands in %.1f s\n" % (label, n, time.time() - t))
            stops, _notes = policy.check(op)
            if crashes:
                # its rectangle runs over the clamps: said, and found by this check too
                check(any("WILL CRASH" in m for m in stops), "%s: Polar CNC says it will crash" % label)
                pts, R = moves(job)
                hit = None
                for r, a, z, rapid in spread([p for p in pts if not p[3]]):
                    if first_inside(obs, face_probes(r * math.cos(a), r * math.sin(a), z, R)) is not None:
                        hit = (round(r, 2), round(math.degrees(a), 1), round(z, 2))
                        break
                check(hit is not None, "%s: ... and this check finds the cutter in a clamp too (%s)" % (label, hit))
                continue
            check(not stops, "%s: Polar CNC finds nothing wrong %s" % (label, stops[:1]))
            try:
                pts, R = moves(job)
            except Exception as e:
                check(False, "%s: converts to polar (%s)" % (label, e))
                continue
            gouges(label, pts, R, part, obs)
            face_covered(label, pts, R, part, z_top)
        App.closeDocument(doc.Name)


def usual_ops():
    """Profile, Pocket, Helix, Drilling in a polar Job, through the polar conversion."""
    import Part
    from polarcnc import setup
    shape = Part.makeCylinder(40, 12)
    shape = shape.cut(Part.makeBox(20, 14, 5, V(8, -7, 7)))
    shape = shape.cut(Part.makeCylinder(4, 12, V(-22, 10, 0)))
    shape = shape.cut(Part.makeCylinder(3, 12, V(0, 0, 0)))
    doc, job, held = make_face_job("CutOps", shape, False, setup.MY_CHUCKS[1])
    model = job.Model.Group[0]
    part = model.Shape
    obs = keepout(held)

    def face(test):
        for k, f in enumerate(model.Shape.Faces, 1):
            if test(f):
                return "Face%d" % k
        return None
    floor = face(lambda f: abs(f.CenterOfMass.z - 7) < 1e-6 and f.Area < 300)
    hole = face(lambda f: f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - 4) < 1e-6)
    hole_mid = face(lambda f: f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - 3) < 1e-6)
    made = []
    for label, module, base, props in (
            ("Profile", "Path.Op.Profile", [(model, ())], {}),
            ("Pocket", "Path.Op.PocketShape", [(model, (floor,))], {"ClearingPattern": "Offset"}),
            ("Helix", "Path.Op.Helix", [(model, (hole,))], {}),
            ("Drill off the centre", "Path.Op.Drilling", [(model, (hole,))], {}),
            ("Drill on the centre", "Path.Op.Drilling", [(model, (hole_mid,))], {})):
        mod = __import__(module, fromlist=["Create"])
        op = mod.Create(label.replace(" ", ""), parentJob=job)
        op.Base = base
        for k, v in props.items():
            setattr(op, k, v)
        made.append((label, op))
    doc.recompute()
    prof = made[0][1]
    prof.setExpression("FinalDepth", None)
    prof.FinalDepth = 1.0            # above the jaws that hold the 6 mm under the part
    doc.recompute()
    for label, op in made:
        for _l, o in made:
            o.Active = (o is op)
        doc.recompute()
        if len(op.Path.Commands) < 3:
            check(False, "%s: a path" % label)
            continue
        try:
            pts, R = moves(job)
        except Exception as e:
            check(False, "%s: converts to polar (%s)" % (label, e))
            continue
        if label.startswith("Drill"):
            R = 0.0                  # a drill: only its axis (the hole is its own size)
            pts_ok = [p for p in pts if not p[3]]
            hole_r = 4 if "off" in label else 3
            cx, cy = (-22, 10) if "off" in label else (0, 0)
            off = max((math.hypot(r * math.cos(a) - cx, r * math.sin(a) - cy) for r, a, z, _ in pts_ok), default=99)
            check(off < 1e-3, "%s: drills on the hole axis (off by %.4f mm)" % (label, off))
            deep = min((z for _r, _a, z, _ in pts_ok), default=99)
            check(deep < 1e-3 and hole_r, "%s: down to the hole bottom (Z %.3f)" % (label, deep))
            continue
        gouges(label, pts, R, part, obs)
    App.closeDocument(doc.Name)


def wrap_case():
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    from polarcnc import chuck as ch, machine, polarwrap
    doc = App.newDocument("CutWrap")
    bar = doc.addObject("Part::Feature", "Bar")
    shape = Part.makeCylinder(20, 60)
    shape = shape.cut(Part.makeCylinder(30, 7, V(0, 0, 30)).cut(Part.makeCylinder(17, 7, V(0, 0, 30))))
    shape = shape.cut(Part.makeBox(10, 40, 10, V(16, -20, 42)))
    bar.Shape = shape
    doc.recompute()
    job = PathJob.Create("Job", [bar], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    tc.SpindleSpeed = 12000
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 125
    job.PolarLayout = machine.WRAP
    job.PolarWrapDiameter = 44
    job.PolarWrapToolLengthInX = True
    job.PostProcessorArgs = "--no-show-editor"
    held = ch.make_chuck(job)
    held.GripLength = 10
    doc.recompute()
    op = polarwrap.Create("PolarWrap", parentJob=job)
    doc.recompute()
    part = job.Model.Group[0].Shape
    for strategy in ("Roughing + finishing",):
        op.Strategy = strategy
        doc.recompute()
        label = "Wrap, %s" % strategy
        pts, R = moves(job)
        check(R > 0, "%s: tool radius %.2f" % (label, R))
        gouges(label, pts, R, part, keepout(held), wrap=True)
        leave = getattr(op, "StockToLeave", None)
        leave = getattr(leave, "Value", leave) or 0.0
        wrap_covered(label, pts, R, 20.0, 12.0, 27.0, leave)
    # only From Z set by hand (To Z left at 0): it must still stop clear of the jaws
    op.FromZ = 60
    doc.recompute()
    pts, R = moves(job)
    gouges("Wrap, From Z by hand", pts, R, part, keepout(held), wrap=True)
    App.closeDocument(doc.Name)


def go():
    boxes = []
    try:
        Gui.activateWorkbench("CAMWorkbench")
        catch_messages(boxes)
        for step in (face_cases, usual_ops, wrap_case):
            try:
                step()
            except Exception:
                fails.append("exception in %s" % step.__name__)
                log.write(traceback.format_exc())
            pump(100)
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    if boxes:
        log.write("messages: %s\n" % boxes)
    finish()


QtCore.QTimer.singleShot(2000, go)
