# Polar CNC — a file made with Polar Face (2.19, removed in 2.20.0) still opens (run by
# tests/freecad/run.sh, own start). tests/fixtures/polarface_2_19.FCStd was saved by 2.19.1: a polar
# Job with a 4-jaw chuck and a Polar Face operation. It must open without an error, the operation
# must keep its path (not remade, not emptied, also on recompute), it is warned about, and Post
# Process still writes the program.
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
from common import REPO, catch_messages, check, fails, finish, log, pump  # noqa: E402


def go():
    try:
        Gui.activateWorkbench("CAMWorkbench")
        boxes = []
        catch_messages(boxes)
        from polarcnc import policy
        doc = App.openDocument(os.path.join(REPO, "tests", "fixtures", "polarface_2_19.FCStd"))
        pump(500)
        op = doc.getObject("PolarFace")
        job = doc.getObject("Job")
        check(op is not None and job is not None, "the file opens: Job and Polar Face are there")
        n = len(op.Path.Commands) if op is not None else 0
        check(n > 10, "the old operation keeps its path (%d commands)" % n)
        check(type(op.Proxy).__name__ == "ObjectPolarFace", "its stand-in: %s" % type(op.Proxy).__name__)
        check(not boxes, "no card while opening: %s" % boxes[:1])
        op.touch()
        doc.recompute()
        check(len(op.Path.Commands) == n, "recompute leaves its path as it was (%d)" % len(op.Path.Commands))
        check(any("removed" in m for m in policy.problems(op)), "it is warned about: %s" % policy.problems(op)[:1])
        check(Gui.Command.get("PolarCNC_PolarFace") is None, "no Polar Face button any more")
        from Path.Post.Processor import PostProcessorFactory
        for tc in job.Tools.Group:          # (since 2.22 a cutter with no spindle speed is refused)
            if tc.SpindleSpeed <= 0:
                tc.SpindleSpeed = 12000
        doc.recompute()
        res = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc").export()
        out = res[0][1] if res else None
        check(out is not None and "G93" in out, "Post Process still writes the polar program %s" % boxes[-1:])
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    finish()


QtCore.QTimer.singleShot(2000, go)
