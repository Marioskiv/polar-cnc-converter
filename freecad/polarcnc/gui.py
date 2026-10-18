# Polar CNC — commands in the CAM workbench.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import machine

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(os.path.dirname(HERE), "Resources", "PolarCNC.svg")
POST = "polar_linuxcnc"


def _selected_job():
    import PathScripts.PathUtils as PathUtils
    for obj in Gui.Selection.getSelection():
        job = PathUtils.findParentJob(obj)
        if job is not None:
            return job
    jobs = PathUtils.GetJobs() if App.ActiveDocument else []
    return jobs[0] if len(jobs) == 1 else None


class MachineSettingsCommand:
    """Make the selected Job a polar Job: the Polar CNC properties and the polar post."""

    def GetResources(self):
        return {
            "Pixmap": ICON,
            "MenuText": "Polar machine settings",
            "ToolTip": "Make the selected CAM Job a polar Job: adds the Polar CNC machine settings "
                       "(cutting side, X Axis Max, profile) and chooses the polar_linuxcnc "
                       "post-processor. Post Process then writes polar G-code.",
        }

    def IsActive(self):
        return _selected_job() is not None

    def Activated(self):
        job = _selected_job()
        if job is None:
            return
        App.ActiveDocument.openTransaction("Polar machine settings")
        machine.add_settings(job)
        if POST in job.getEnumerationsOfProperty("PostProcessor"):
            job.PostProcessor = POST
        else:
            App.Console.PrintWarning("Polar CNC: the %s post-processor was not found; check that "
                                     "the addon is installed.\n" % POST)
        App.ActiveDocument.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)   # the property editor shows the new "Polar CNC" group
        App.Console.PrintMessage(
            "Polar CNC: Job '%s' is now polar. Set Polar X Max (and the cutting side) in its "
            "properties, group 'Polar CNC'. The CAM work origin X0 Y0 must be the chuck centre.\n"
            % job.Label)


def _ensure_toolbar():
    """A 'Polar CNC' toolbar in the CAM workbench (the same mechanism as Tools -> Customize)."""
    grp = App.ParamGet("User parameter:BaseApp/Workbench/CAMWorkbench/Toolbar/PolarCNC")
    if not grp.GetString("Name", ""):
        grp.SetString("Name", "Polar CNC")
        grp.SetBool("Active", True)
    if not grp.GetString("PolarCNC_MachineSettings", ""):
        grp.SetString("PolarCNC_MachineSettings", "PolarCNC")


def register_post():
    """Make the polar_linuxcnc post known to CAM. package.xml declares it, but FreeCAD 26.3 looks
    for the key "Postprocessor" while its own Metadata gives "postprocessor", so the declaration
    alone is never found; addAddonPostPath() is the documented call for addons."""
    import Path.Preferences
    if hasattr(Path.Preferences, "addAddonPostPath"):
        Path.Preferences.addAddonPostPath(os.path.join(os.path.dirname(HERE), "posts"))


def install():
    register_post()
    Gui.addCommand("PolarCNC_MachineSettings", MachineSettingsCommand())
    _ensure_toolbar()
