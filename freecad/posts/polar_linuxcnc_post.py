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


def _polar_program(job, objectslist, argstring):
    """The polar program for these objects, after every check; raises _Refused (in plain words)."""
    try:
        opts = machine.options(job)
    except (ValueError, OSError) as e:
        raise _Refused(str(e))
    wrap = machine.is_wrap(job)
    ops = [getattr(item, "source", item) for item in objectslist]
    held = getattr(job, "PolarChuck", None)
    from polarcnc import chuck, collision
    if held is None:
        FreeCAD.Console.PrintWarning("Polar CNC: no chuck set up for this Job: the jaws are not "
                                     "checked (Polar CNC -> Chuck).\n")
    elif not wrap:
        # the CAM paths first: names the operation and the move
        obs = collision.obstacles(held)
        hits = ["%s: %s" % (o.Label, m) for o in ops for m in [collision.hit_message(o, obs)] if m]
        if hits:
            raise _Refused("the program runs into the chuck.\n" + "\n".join(hits))
        for o in ops:       # cuts below the jaw / clamp tops: a reminder, never a refusal
            msg = chuck.head_warning(held, getattr(o, "Path", None))
            if msg:
                FreeCAD.Console.PrintWarning("Polar CNC (%s): %s\n" % (o.Label, msg))

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

    if held is not None:    # then the program as the machine really moves (joint space)
        radius = max([collision.tool_radius(o) for o in ops] + [0.0])
        data = bridge.parse(polar, opts)
        by_number = {}                        # each cutter checked with its own radius
        for o in ops:
            tc = getattr(o, "ToolController", None)
            if tc is not None and collision.tool_radius(o) > 0:
                by_number[int(tc.ToolNumber)] = collision.tool_radius(o)
        radii = collision.tool_radii(polar, data, by_number, radius)
        if wrap:
            msg = collision.wrap_hits(held, data, radius, radii=radii)
        else:
            msg = collision.polar_hits(collision.obstacles(held), data, radius, radii=radii)
        if msg:
            raise _Refused("the program runs into the chuck.\n" + msg)
    return polar


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
            notes.append("( Setup: X0 Y0 = the chuck axis. Stock top at Z %.3f, stock bottom at "
                         "Z %.3f - touch off Z there )" % (sb.ZMax, sb.ZMin))
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


def export(objectslist, filename, argstring):
    argstring = argstring or ""
    job = _job(objectslist)
    if job is None:
        return _refuse("no CAM Job found for the operations to post.")
    try:
        polar = _polar_program(job, objectslist, argstring)
    except _Refused as e:
        return _refuse(str(e))
    except Exception as e:          # never a raw traceback: say what happened, plainly
        import traceback
        FreeCAD.Console.PrintError(traceback.format_exc())
        return _refuse("something went wrong while writing the program (%s: %s). Nothing was "
                       "written. The details are in the Report view." % (type(e).__name__, e))
    if polar is None:
        return None

    if FreeCAD.GuiUp and "--no-show-editor" not in argstring:
        if len(polar) > 100000:
            FreeCAD.Console.PrintMessage("Polar CNC: editor skipped, the output is over 100 kB\n")
        else:
            dia = PostUtils.GCodeEditorDialog()
            dia.editor.setPlainText(polar)
            if dia.exec_():
                polar = dia.editor.toPlainText()

    if filename != "-":
        with open(filename, "w") as f:
            f.write(polar)
    return polar
