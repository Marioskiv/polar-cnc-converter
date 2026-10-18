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

import importlib.util
import os
import sys

import FreeCAD
import Path.Post.Utils as PostUtils
import PathScripts.PathUtils as PathUtils

# freecad/posts -> freecad, so that `polarcnc` imports however FreeCAD loaded this file
_ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ADDON not in sys.path:
    sys.path.append(_ADDON)

from polarcnc import bridge, machine  # noqa: E402

UNITS = "G21"  # the converter always writes mm
TOOLTIP = """Polar CNC: polar XZC G-code for a lathe converted to face milling (X radius, C chuck,
Z depth, G93 inverse-time feed). Set the machine in the Job's "Polar CNC" properties.
The arguments are those of FreeCAD's LinuxCNC post, which writes the milling program first."""


def _linuxcnc():
    """A fresh copy of FreeCAD's LinuxCNC post: it keeps its settings in module globals, so a
    copy left from an earlier run could carry e.g. --inches into this one."""
    import Path.Post.scripts as scripts
    path = os.path.join(os.path.dirname(scripts.__file__), "linuxcnc_legacy_post.py")
    spec = importlib.util.spec_from_file_location("polarcnc_linuxcnc_legacy_post", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TOOLTIP_ARGS = _linuxcnc().TOOLTIP_ARGS


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

    # the milling program, without its editor (it is not what goes to the machine)
    cartesian = _linuxcnc().export(objectslist, "-", argstring + " --no-show-editor")
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
