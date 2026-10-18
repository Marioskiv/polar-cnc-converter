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
        from PySide import QtGui
        QtGui.QMessageBox.warning(None, "Polar CNC", msg)
    return None  # Post Process writes no file


def export(objectslist, filename, argstring):
    argstring = argstring or ""
    job = _job(objectslist)
    if job is None:
        return _refuse("no CAM Job found for the operations to post.")
    try:
        opts = machine.options(job)
    except (ValueError, OSError) as e:
        return _refuse(str(e))

    held = getattr(job, "PolarChuck", None)
    if held is not None and not machine.is_wrap(job):     # wrap: the Job is drawn unrolled
        from polarcnc import chuck, collision
        obs = collision.obstacles(held)
        ops = [getattr(item, "source", item) for item in objectslist]
        hits = ["%s: %s" % (o.Label, m) for o in ops
                for m in [collision.hit_message(o, obs)] if m]
        if hits:            # the cutter would run into the chuck: no file
            return _refuse("the program runs into the chuck.\n" + "\n".join(hits))
        for o in ops:       # cuts below the jaw / clamp tops: a reminder, never a refusal
            msg = chuck.head_warning(held, getattr(o, "Path", None))
            if msg:
                FreeCAD.Console.PrintWarning("Polar CNC (%s): %s\n" % (o.Label, msg))

    # the milling program, without its editor (it is not what goes to the machine)
    cartesian = program.cartesian(objectslist, argstring)
    try:
        polar = bridge.convert(cartesian, opts)
    except bridge.ConverterError as e:
        # the converter's own words; its line numbers are those of the milling program
        return _refuse("the program was not converted.\n%s" % e)

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
