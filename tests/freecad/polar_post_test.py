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
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

OUT = os.environ["PC_OUT"]
REPO = os.environ["PC_REPO"]
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, "log.txt"), "w")
fails = []


def check(cond, what):
    log.write("%s %s\n" % ("ok  " if cond else "FAIL", what))
    log.flush()
    if not cond:
        fails.append(what)


def build_job():
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    import Path.Op.Profile as Profile
    import Path.Op.PocketShape as PocketShape
    doc = App.newDocument("PolarTest")
    disk = doc.addObject("Part::Feature", "Disk")
    disk.Shape = Part.makeCylinder(50, 10)            # centred on X0 Y0 = the chuck axis
    doc.recompute()
    job = PathJob.Create("Job", [disk], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    doc.recompute()
    model = job.Model.Group[0]
    top = [n for n, f in enumerate(model.Shape.Faces, 1) if abs(f.CenterOfMass.z - 10) < 1e-6][0]
    prof = Profile.Create("Profile")
    prof.Base = [(model, ())]
    pocket = PocketShape.Create("Pocket")
    pocket.Base = [(model, ("Face%d" % top,))]
    pocket.FinalDepth = 8
    pocket.ClearingPattern = "Offset"
    doc.recompute()
    return doc, job, [prof, pocket]


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
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pc_post", os.path.join(REPO, "freecad", "posts", "polar_linuxcnc_post.py"))
        sys_post = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys_post)
        objs = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc")._buildPostList()[0][1]
        open(os.path.join(OUT, "cartesian.ngc"), "w").write(
            sys_post._linuxcnc().export(objs, "-", "--no-show-editor"))
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
    except Exception:
        log.write(traceback.format_exc())
        fails.append("exception")
    with open(os.path.join(OUT, "result.txt"), "w") as f:
        f.write("RESULT: %s\n" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
    log.close()
    os._exit(0)


QtCore.QTimer.singleShot(3000, go)
