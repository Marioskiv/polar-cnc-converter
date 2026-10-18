# Polar CNC — test of the FreeCAD addon in a real FreeCAD (run by tests/freecad/run.sh).
#
# Builds a CAM Job on a disk centred on the chuck axis, makes it polar with the toolbar command,
# posts it with polar_linuxcnc and checks: the post is offered in the Job, the output is polar,
# it is exactly what the converter makes of FreeCAD's own LinuxCNC output (run.sh compares it with
# the Node converter), a Job without X Max is refused and no file is written, and the whole
# golden set converts byte for byte inside FreeCAD's JavaScript engine.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO, OUT, build_job, check, fails, finish, log, pump  # noqa: E402


def op_policy(doc, job):
    from Path.Main import Job as PathJob
    from polarcnc import policy
    import Path.Op.PocketShape as PocketShape
    import Path.Op.MillFacing as MillFacing
    import Path.Op.Adaptive as Adaptive
    # a second, ordinary Job in the same document
    other = PathJob.Create("Ordinary", [doc.getObject("Disk")], None)
    doc.recompute()
    blocked = [n for n in policy.BLOCKED if n in Gui.listCommands()]
    check("CAM_Pocket3D" in blocked, "blocked commands present in this FreeCAD: %s" % blocked)

    def active(sel):
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(sel)
        policy._cache[0] = 0.0
        return {n: Gui.Command.get(n).isActive() for n in blocked + ["CAM_Profile", "CAM_Adaptive"]}

    a = active(job)
    check(not any(a[n] for n in blocked), "polar Job selected: 3D/probe greyed out %s" % a)
    check(a["CAM_Profile"] and a["CAM_Adaptive"], "polar Job: Profile and Adaptive stay active")
    a = active(job.Operations.Group[0])
    check(not any(a[n] for n in blocked), "an operation of the polar Job selected: greyed out")
    a = active(other)
    check(all(a[n] for n in blocked), "ordinary Job selected: everything active %s" % a)

    # defaults and warnings for new operations of the polar Job
    obs = policy._observer[0]
    # created with the names the CAM toolbar commands use: the Job's defaults are looked up by them
    face = MillFacing.Create("MillFacing", parentJob=job)
    pocket = PocketShape.Create("Pocket Shape", parentJob=job)
    ofacing = MillFacing.Create("MillFacing", parentJob=other)
    doc.recompute()
    pump(200)
    check(face.ClearingPattern == "Spiral", "polar Job: new Facing is Spiral (%s)" % face.ClearingPattern)
    check(pocket.ClearingPattern == "Offset", "polar Job: new Pocket is Offset (%s)" % pocket.ClearingPattern)
    check(ofacing.ClearingPattern == "ZigZag", "ordinary Job keeps FreeCAD's default (%s)"
          % ofacing.ClearingPattern)
    check(not obs._said.get((doc.Name, face.Name)), "no warning for a Spiral facing")
    pocket.ClearingPattern = "ZigZag"
    pump(200)
    said = obs._said.get((doc.Name, pocket.Name)) or []
    check(any("ZigZag" in m and "Offset" in m for m in said), "ZigZag in polar Job -> warning %s" % said)
    ad = Adaptive.Create("Adaptive", parentJob=job)
    pump(200)
    check(any("Adaptive" in m for m in obs._said.get((doc.Name, ad.Name)) or []), "Adaptive -> warning")
    oad = Adaptive.Create("Adaptive", parentJob=other)
    pump(200)
    check(not obs._said.get((doc.Name, oad.Name)), "no warnings in an ordinary Job")


def go():
    try:
        Gui.activateWorkbench("CAMWorkbench")
        import Path.Preferences
        from Path.Post.Processor import PostProcessorFactory
        posts = Path.Preferences.allEnabledLegacyPostProcessors()
        check("polar_linuxcnc" in posts, "polar_linuxcnc is offered for Jobs: %s" % posts)
        check("PolarCNC_MachineSettings" in Gui.listCommands(), "toolbar command registered")
        grp = App.ParamGet("User parameter:BaseApp/Workbench/CAMWorkbench/Toolbar/PolarCNC")
        check(grp.GetString("PolarCNC_MachineSettings", "") != "", "Polar CNC toolbar in CAM")

        doc, job, ops = build_job()
        check(all(len(o.Path.Commands) > 5 for o in ops), "operations have paths")

        # warnings must not open dialogs during the test
        msgs = []
        QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: msgs.append(a[2]))

        Gui.Selection.addSelection(job)
        Gui.runCommand("PolarCNC_MachineSettings")
        check(job.PostProcessor == "polar_linuxcnc", "the command chose the polar post")
        check(hasattr(job, "PolarXMax") and job.PolarXMax.Value == 0, "X Max added, not guessed")
        job.PostProcessorArgs = "--no-show-editor"

        # 1. without X Max: refused, nothing to write
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None, "no X Max -> no file")
        check(msgs and "X Axis Max" in msgs[-1], "no X Max -> message: %r" % (msgs[-1:] or ""))

        # 2. no feed in the tool controller: refused with the line, as on the web page
        job.PolarXMax = 125
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        check(res and res[0][1] is None and "without a feed rate" in msgs[-1],
              "no feed -> refused: %r" % msgs[-1][:120])

        # 3. polar output
        tc = job.Tools.Group[0]
        tc.HorizFeed, tc.VertFeed = 600, 200
        doc.recompute()
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        polar = res[0][1] if res else None
        check(polar is not None, "polar output written")
        if polar:
            open(os.path.join(OUT, "polar.ngc"), "w").write(polar)
            lines = polar.splitlines()
            check("( Polar G-code - G93 inverse time" in polar, "converter header")
            check("G93" in lines and "G8" in lines, "G93 and G8 (X radius)")
            moves = [l for l in lines if l.startswith(("G0", "G1")) and not l.startswith("G0 Z")]
            check(not any(" Y" in l for l in moves), "no Y in any move")
            check(any(" C" in l for l in moves), "C moves present")
            check(max(float(w[1:]) for l in moves for w in l.split() if w.startswith("X")) <= 125,
                  "X within X Max")
        # the milling program FreeCAD itself writes for the same Job, for run.sh to convert with Node
        import polarcnc.machine as machine
        from polarcnc import program
        objs = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc")._buildPostList()[0][1]
        open(os.path.join(OUT, "cartesian.ngc"), "w").write(
            program.cartesian(objs, job.PostProcessorArgs))
        json.dump(machine.options(job), open(os.path.join(OUT, "options.json"), "w"))

        # 4. the golden set through FreeCAD's JavaScript engine
        from polarcnc import bridge
        G = json.load(open(os.path.join(REPO, "tests", "fixtures", "golden.json")))
        dia = {"real": 6, "wide": 6, "alt": 10}
        same = 0
        for key, want in G["outputs"].items():
            on, mode, pn = key.split("|")
            opts = dict(G["options"][on], centerMode=mode)
            try:
                got = bridge.convert("(T1 D=%d)\n" % dia[on] + G["programs"][pn], opts)
            except bridge.ConverterError as e:
                got = "refused: %s" % e
            same += got == want
        check(same == len(G["outputs"]), "golden %d/%d identical in FreeCAD" % (same, len(G["outputs"])))
        # 5. a polar Job: unsuitable operations greyed out, polar defaults, warnings
        op_policy(doc, job)
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    finish()


QtCore.QTimer.singleShot(3000, go)
