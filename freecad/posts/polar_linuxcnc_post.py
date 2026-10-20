# Polar CNC — post-processor "polar_linuxcnc" for the FreeCAD CAM workbench.
#
# Choose it as the Job's post-processor (Job -> Output -> Processor). Post Process then writes
# POLAR G-code (X radius, C chuck, Z depth, G93 inverse-time feed): FreeCAD's own LinuxCNC post
# writes the usual milling program, and the Polar CNC converter (the code of the web page,
# src/core) turns it into polar moves. Nothing is converted silently: if the converter refuses
# a line, no file is written and its message is shown.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import re
import sys

import FreeCAD
import Path.Post.Utils as PostUtils
import PathScripts.PathUtils as PathUtils

# freecad/posts -> freecad, so that `polarcnc` imports however FreeCAD loaded this file
_ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ADDON not in sys.path:
    sys.path.append(_ADDON)

from polarcnc import bridge, machine, program  # noqa: E402

UNITS = "G21"  # the converter always writes mm
TOOLTIP = """Polar CNC: polar XZC G-code for a lathe converted to face milling (X radius, C chuck,
Z depth, G93 inverse-time feed). Set the machine in the Job's "Polar CNC" properties.
The arguments are those of FreeCAD's LinuxCNC post, which writes the milling program first."""


TOOLTIP_ARGS = program.linuxcnc_post().TOOLTIP_ARGS


def _job(objectslist):
    for item in objectslist:
        # 26.3 hands posts wrappers (Postable) with the document object in .source
        obj = getattr(item, "source", None) or item
        try:
            job = PathUtils.findParentJob(obj)
        except Exception:
            job = None
        if job is not None:
            return job
    return None


def _refuse(msg):
    FreeCAD.Console.PrintError("Polar CNC: %s\n" % msg)
    if FreeCAD.GuiUp:
        try:
            from polarcnc import help
            help.error_card(msg, "Polar CNC — Post Process")
        except Exception:
            from PySide import QtGui
            QtGui.QMessageBox.warning(None, "Polar CNC", msg)
    return None  # Post Process writes no file


class _Refused(Exception):
    pass


def _polar_program(job, objectslist, argstring, quiet=False):
    """The polar program for these objects, after every check; raises _Refused (in plain words)."""
    try:
        opts = machine.options(job)
    except (ValueError, OSError) as e:
        raise _Refused(str(e))
    wrap = machine.is_wrap(job)
    ops = [getattr(item, "source", item) for item in objectslist]
    held = getattr(job, "PolarChuck", None)
    from polarcnc import chuck, collision
    if held is None and not quiet:
        FreeCAD.Console.PrintWarning("Polar CNC: no chuck set up for this Job: the jaws are not "
                                     "checked (Polar CNC -> Chuck).\n")
    if held is not None:
        # 2.22.0: a cutter with no diameter would be checked as a point (radius 0) - refused
        bare = program.missing_diameters(ops)
        if bare:
            raise _Refused(program.NO_DIAMETER % ", ".join(bare))
    if held is not None and not wrap:
        # the CAM paths first: names the operation and the move
        obs = collision.obstacles(held)
        hits = ["%s: %s" % (o.Label, m) for o in ops for m in [collision.hit_message(o, obs)] if m]
        if hits:
            raise _Refused("the program runs into the chuck.\n" + "\n".join(hits))
        for o in ops:       # cuts below the jaw / clamp tops: a reminder, never a refusal
            msg = chuck.head_warning(held, getattr(o, "Path", None))
            if msg and not quiet:
                FreeCAD.Console.PrintWarning("Polar CNC (%s): %s\n" % (o.Label, msg))

    # every cutter must start the spindle: without a speed FreeCAD writes no M3
    spindle = program.spindle_problems(ops)
    if spindle:
        raise _Refused("a cutter would go in with the spindle stopped.\n" + "\n".join(spindle) +
                       "\nSet Spindle Speed (and direction Forward) in its Tool Controller.")

    # the milling program, without its editor (it is not what goes to the machine)
    cartesian = program.cartesian(objectslist, argstring)
    if wrap:                # the real part's paths, unrolled for the wrap layout
        try:
            program.wrap_operations_only(objectslist)
            program.wrap_tool_length_check(job, cartesian)
            cartesian = program.unroll(cartesian, opts["wrapRadius"])
        except ValueError as e:
            raise _Refused(str(e))
    try:
        polar = bridge.convert(cartesian, opts)
    except bridge.ConverterError as e:
        # the converter's own words; its line numbers are those of the milling program
        raise _Refused("the program was not converted.\n%s" % e)

    polar = _with_setup_notes(polar, job, wrap, held)
    _machine_check(polar, job, ops, opts, wrap, held)
    # after the checks: the park before each tool change (machine coordinates), the spindle off
    if getattr(job, "PolarToolChangePark", True):
        polar = program.tool_change_park(polar, opts)
    return program.spindle_off_at_end(polar)


def _machine_check(polar, job, ops, opts, wrap, held):
    """The polar text as the machine will run it: no Y left, and (with a chuck set up) every
    block in joint space against the jaws / clamps, each cutter with its own radius. Raises
    _Refused. Run on the converted program and again on what the editor gives back if it was
    changed there (2.22.0: edits were written unchecked)."""
    from polarcnc import collision
    left = program.y_move(polar)
    if left:
        raise _Refused("the polar output still has a Y move (it must be X, C, Z only): %s" % left)
    if held is None:
        return
    radius = max([collision.tool_radius(o) for o in ops] + [0.0])
    try:
        data = bridge.parse(polar, opts)
    except Exception as e:
        raise _Refused("the program could not be read back for the chuck check: %s" % e)
    by_number = {}                        # each cutter checked with its own radius
    for o in ops:
        tc = getattr(o, "ToolController", None)
        if tc is not None and collision.tool_radius(o) > 0:
            # two tool controllers with one number: the bigger cutter (the safe side)
            n = int(tc.ToolNumber)
            by_number[n] = max(by_number.get(n, 0.0), collision.tool_radius(o))
    radii = collision.tool_radii(polar, data, by_number, radius)
    if wrap:
        msg = collision.wrap_hits(held, data, radius, radii=radii)
    else:
        msg = collision.polar_hits(collision.obstacles(held), data, radius, radii=radii)
    if msg:
        raise _Refused("the program runs into the chuck.\n" + msg)


def _with_setup_notes(polar, job, wrap, held):
    """A few lines for the operator at the top (after the converter's header): where Z0 is and
    how the part sits in the chuck, taken from the Job."""
    notes = []
    try:
        sb = job.Stock.Shape.BoundBox
        if wrap:
            notes.append("( Setup: X0 = the chuck axis, X = radius of the tool tip. Z: the part's free "
                         "end is at Z %.3f, its chuck end at Z %.3f )" % (sb.ZMax, sb.ZMin))
        else:
            # 2.22.0: said plainly - "stock bottom ... touch off Z there" read as "touch off at
            # the bottom", wrong by the stock height
            notes.append("( Setup: X0 Y0 = the chuck axis. Touch off Z on the stock TOP with the "
                         "value Z %.3f. Stock bottom at Z %.3f )" % (sb.ZMax, sb.ZMin))
            if abs(sb.ZMax) > 1e-6:
                notes.append("( Note: Z0 is not on the stock top in this Job )")
        if held is not None:
            notes.append("( Chuck: %s, grip %.1f mm )" % (held.Preset, held.GripLength.Value))
    except Exception:
        return polar
    lines = polar.split("\n")
    at = lines.index("G21") if "G21" in lines else 0
    if at > 0 and lines[at - 1] == "":
        at -= 1
    return "\n".join(lines[:at] + notes + lines[at:])


_shown = {"job": None, "time": 0.0}


def _refuse_once(msg, job):
    """One card per Post Process run: FreeCAD calls this post once per file when the Job splits
    its output, and every file is refused then - the first card says why, the others only go to
    the Report view. (A run takes seconds; a card more than 10 s after the last one is a new run.)"""
    import time
    now = time.time()
    if _shown["job"] == job.Name and now - _shown["time"] < 10:
        _shown["time"] = now
        FreeCAD.Console.PrintError("Polar CNC: %s\n" % msg)
        return None
    _shown["job"], _shown["time"] = job.Name, now
    return _refuse(msg)


def _names(objs):
    return [getattr(getattr(o, "source", o), "Name", None) for o in objs]


def _other_sections_refused(job, objectslist, argstring):
    """2.22.0: FreeCAD calls this post once per output file when the Job splits its output (by
    tool, fixture or operation) and then writes every file that was not refused. So a file
    that runs into the chuck would be missing while the others are written. Every other file
    of the Job is checked too; if one is refused, none is written. Returns its message or None."""
    try:
        secs = program.sections(job)
    except Exception:
        return None
    if len(secs) < 2:
        return None
    mine = _names(objectslist)
    for name, objs in secs:
        if _names(objs) == mine:
            continue
        try:
            _polar_program(job, objs, argstring, quiet=True)
        except _Refused as e:
            return ("the file %s of this Job is refused, so no file is written (the Job splits "
                    "its output):\n%s" % (name, e))
    return None


def export(objectslist, filename, argstring):
    argstring = argstring or ""
    job = _job(objectslist)
    if job is None:
        return _refuse("no CAM Job found for the operations to post.")
    try:
        polar = _polar_program(job, objectslist, argstring)
        other = _other_sections_refused(job, objectslist, argstring)
        if other:
            return _refuse_once(other, job)
    except _Refused as e:
        return _refuse_once(str(e), job)
    except Exception as e:          # never a raw traceback: say what happened, plainly
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())
        return _refuse("something went wrong while writing the program (%s: %s). Nothing was "
                       "written. The details are in the Report view." % (type(e).__name__, e))
    if polar is None:
        return None
    _shown["job"] = None            # a file that passed: the next refusal is a new run's

    if FreeCAD.GuiUp and "--no-show-editor" not in argstring:
        if len(polar) > 100000:
            FreeCAD.Console.PrintMessage("Polar CNC: editor skipped, the output is over 100 kB\n")
        else:
            dia = PostUtils.GCodeEditorDialog()
            dia.editor.setPlainText(polar)
            if dia.exec_():
                edited = dia.editor.toPlainText()
                if edited != polar:
                    # 2.22.0: what is written must pass the same checks as what was converted
                    # the park lines (G53, machine coordinates) are added after the checks, as
                    # when the program is first written: left out of the check here too
                    checked = "\n".join(l for l in edited.split("\n")
                                         if not re.match(r"\s*G0*53\b", l.upper()))
                    try:
                        _machine_check(checked, job, [getattr(i, "source", i) for i in objectslist],
                                       machine.options(job), machine.is_wrap(job),
                                       getattr(job, "PolarChuck", None))
                    except _Refused as e:
                        return _refuse("the program as edited is refused: %s" % e)
                    FreeCAD.Console.PrintWarning("Polar CNC: the program was edited by hand before "
                                                 "it was written; it passed the checks again.\n")
                polar = edited

    if filename != "-":
        with open(filename, "w") as f:
            f.write(polar)
    return polar
