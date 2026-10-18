# Polar CNC — the program of a Job: FreeCAD's LinuxCNC milling output, then the polar output.
# Used by the polar_linuxcnc post-processor and by the simulator, so both see the same program.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import importlib.util
import os

from . import bridge, machine


def linuxcnc_post():
    """A fresh copy of FreeCAD's LinuxCNC post: it keeps its settings in module globals, so a
    copy left from an earlier run could carry e.g. --inches into this one."""
    import Path.Post.scripts as scripts
    path = os.path.join(os.path.dirname(scripts.__file__), "linuxcnc_legacy_post.py")
    spec = importlib.util.spec_from_file_location("polarcnc_linuxcnc_legacy_post", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cartesian(objectslist, argstring=""):
    """The milling program FreeCAD's LinuxCNC post writes for these objects (no editor)."""
    return linuxcnc_post().export(objectslist, "-", (argstring or "") + " --no-show-editor")


def job_objects(job):
    """Everything Post Process would send for the whole Job, in order."""
    try:
        from Path.Post.Processor import PostProcessorFactory
        proc = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc")
        objs = []
        for _name, sublist in proc._buildPostList():      # FreeCAD's own order (26.3)
            objs.extend(sublist)
        return objs
    except AttributeError:
        # another FreeCAD version without that (private) call: fixture, then each active
        # operation after its tool controller
        objs = []
        last_tc = None
        for op in job.Operations.Group:
            if not getattr(op, "Active", True):
                continue
            tc = getattr(op, "ToolController", None)
            if tc is not None and tc is not last_tc:
                objs.append(tc)
                last_tc = tc
            objs.append(op)
        return objs


def wrap_operations_only(objs):
    """A Wrap Job is the real 3D part: only Polar Wrap operations make its path (the other CAM
    operations work on a flat face). Raises ValueError naming the others."""
    others = [o.Label for o in (getattr(i, "source", i) for i in objs)
              if hasattr(o, "Path") and hasattr(o, "ToolController")
              and getattr(o, "Active", True)
              and type(getattr(o, "Proxy", None)).__name__ != "ObjectPolarWrap"]
    if others:
        raise ValueError("In a Wrap Job only Polar Wrap operations can be used (the router is "
                         "radial); remove or disable: %s." % ", ".join(others))


def wrap_tool_length_check(job, text):
    """With the router lying sideways the tool length runs along X, not Z. A G43 with lengths
    in the Z column (as on every mill) would shift the whole program along the part. Refused
    until the Job says the lengths are in the X column."""
    import re
    uses = any(re.search(r"\bG\s*0*43(?![.\d])", l.split("(")[0].upper()) for l in text.splitlines())
    if uses and not getattr(job, "PolarWrapToolLengthInX", False):
        raise ValueError(
            "the program uses tool length offsets (G43), and in Wrap the router lies sideways: its "
            "tool length runs along X. Put each tool's length in the X column of the LinuxCNC "
            "tool table (not Z), then tick Job -> Polar CNC -> Polar Wrap Tool Length In X. "
            "(Or switch tool length offsets off in the post-processor.)")


def unroll(text, r0):
    """Polar Wrap paths are written round the real part (tip at x, y, z); the converter's wrap
    layout takes them unrolled: X = z along the part, Y = angle (unwound) x r0, Z = radius - r0.
    Every motion line (also with an N number, or with no G word under --modal) gets all three;
    other lines are kept. Refused: arcs (Polar Wrap writes none) and inches (G20)."""
    import math
    import re
    out = []
    pos = [None, None, None]
    theta = None
    motion = None
    word = re.compile(r"([XYZ])\s*([-+]?\d*\.?\d+)", re.I)
    gword = re.compile(r"G\s*0*(\d+(?:\.\d+)?)", re.I)
    for line in text.splitlines():
        code = line.split("(")[0].split(";")[0].upper()
        code = re.sub(r"^\s*N\d+\s*", "", code)
        gs = [g for g in gword.findall(code)]
        if "20" in gs:
            raise ValueError("Wrap needs the program in mm: remove --inches from the post arguments.")
        for g in gs:
            if g in ("0", "1", "2", "3"):
                motion = "G" + g
        if not word.search(code) or motion is None or \
                (not any(g in ("0", "1", "2", "3") for g in gs) and gs):
            out.append(line)            # no motion (or a G that is not a move, e.g. G43 H1 Z..)
            continue
        if motion in ("G2", "G3"):
            raise ValueError("arcs in a Wrap program: %s" % line.strip())
        for k, v in word.findall(code):
            pos["XYZ".index(k.upper())] = float(v)
        if None in pos:
            raise ValueError("a Wrap move before X, Y and Z are all known: %s" % line.strip())
        x, y, z = pos
        r = math.hypot(x, y)
        if r > 0.01 or theta is None:       # on the axis the angle means nothing: keep it
            raw = math.atan2(y, x)
            theta = raw if theta is None else theta + ((raw - theta + math.pi) % (2 * math.pi) - math.pi)
        rest = gword.sub("", word.sub("", code)).strip()
        out.append("%s X%.4f Y%.4f Z%.4f%s" % (motion, z, theta * r0, r - r0,
                                               (" " + rest) if rest else ""))
    return "\n".join(out)


def polar(job):
    """(polar G-code, converter options) for the whole Job.
    Raises ValueError (settings) or bridge.ConverterError (refused program)."""
    opts = machine.options(job)
    objs = job_objects(job)
    text = cartesian(objs, job.PostProcessorArgs)
    if machine.is_wrap(job):
        wrap_operations_only(objs)
        wrap_tool_length_check(job, text)
        text = unroll(text, opts["wrapRadius"])
    return bridge.convert(text, opts), opts
