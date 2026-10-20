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


def spindle_problems(ops):
    """Plain words for every tool controller that would start no spindle (FreeCAD writes M3/M4 S
    only with a speed above 0 and a direction other than None), else []."""
    out, seen = [], set()
    for o in ops:
        tc = getattr(o, "ToolController", None)
        if tc is None or tc.Name in seen:
            continue
        seen.add(tc.Name)
        speed = float(getattr(tc, "SpindleSpeed", 0) or 0)
        direction = getattr(tc, "SpindleDir", "Forward")
        if speed <= 0 or direction == "None":
            out.append("%s (T%d): Spindle Speed %g, direction %s: no M3 S would start the spindle."
                       % (tc.Label, int(getattr(tc, "ToolNumber", 0)), speed, direction))
    return out


def _code(line):
    return line.split("(")[0].split(";")[0].upper()


def tool_change_park(polar, opts):
    """Before every tool change (M6) the cutter goes where it can be changed by hand; C stays.
    Face layout: Z to machine Z0 first (where Home All parks it, at the tailstock end, away from
    the part), then X to machine X0 (the chuck centre). Wrap layout: X out to X max first (away
    from the bar), then Z to machine Z0. G53 goes to the machine position whatever the tool length
    offset. After M6 the converter's next move gives every axis again."""
    import re
    if opts.get("layout") == "wrap":
        x_out = (-1 if opts.get("invertX") else 1) * float(opts["xMax"])
        park = ["( tool change: X out, then Z to the park position; C stays )",
                "G0 X%.4f" % x_out, "G53 G0 Z0"]
    else:
        park = ["( tool change: Z to the park position, then X to the centre; C stays )",
                "G53 G0 Z0", "G53 G0 X0"]
    out = []
    for line in polar.split("\n"):
        if re.search(r"\bM0*6\b", _code(line)):
            out.extend(park)
        out.append(line)
    return "\n".join(out)


def spindle_off_at_end(polar):
    """M5 before the program end (M2/M30) if the spindle was left on."""
    import re
    lines = polar.split("\n")
    on = False
    for i, line in enumerate(lines):
        code = _code(line)
        if re.search(r"\bM0*[34]\b", code):
            on = True
        elif re.search(r"\bM0*5\b", code):
            on = False
        elif re.search(r"\bM(0*2|30)\b", code):
            if on:
                lines.insert(i, "M5")
            break
    return "\n".join(lines)



def check_operation(job, op):
    """One operation of a polar (face) Job alone, the way Post Process will write it: FreeCAD's
    LinuxCNC output for it, converted to X/C/Z by the converter, then read back as the machine
    runs it and checked against the chuck. Returns (stops, notes): stops are what Post Process
    will refuse (it does not convert, it runs into the chuck, a Y is left in the polar output);
    notes are for information (e.g. the time the C axis adds). Raises nothing."""
    import re
    from . import collision
    stops, notes = [], []
    tc = getattr(op, "ToolController", None)
    objs = ([tc] if tc is not None else []) + [op]
    try:
        opts = machine.options(job)
        text = cartesian(objs, getattr(job, "PostProcessorArgs", ""))
        polar = bridge.convert(text, opts)
    except Exception as e:
        stops.append(("not converted", str(e)))
        return stops, notes
    # XYZ and XZC are never mixed: a polar program moves X, C and Z only
    for line in polar.splitlines():
        code = line.split("(")[0].split(";")[0].upper()
        if re.search(r"\bY\s*[-+]?\d", code) and re.search(r"\bG\s*0*[0123]\b", code):
            stops.append(("Y in output", line.strip()))
            break
    try:
        data = bridge.parse(polar, opts)
    except Exception as e:
        stops.append(("not converted", str(e)))
        return stops, notes
    held = getattr(job, "PolarChuck", None)
    if held is not None and not held.Shape.isNull():
        msg = collision.polar_hits(collision.obstacles(held), data, collision.tool_radius(op))
        if msg:
            stops.append(("chuck", msg))
    vmax = getattr(job, "PolarCMaxVelocity", 0) or 0
    vmax = getattr(vmax, "Value", vmax)
    if vmax > 0:
        nominal = sum(d for d, rapid in zip(data["dur"][1:], data["rapid"][1:]) if not rapid)
        real = 0.0
        for i in range(1, len(data["dur"])):
            if data["rapid"][i]:
                continue
            dc = abs(data["c"][i] - data["c"][i - 1])
            real += max(data["dur"][i], dc / vmax)
        if nominal > 0:
            notes.append(("slower", (real - nominal) / nominal * 100.0, nominal, real))
    return stops, notes
