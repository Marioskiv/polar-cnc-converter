# Polar CNC — commands in the CAM workbench.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import help, machine, policy

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(os.path.dirname(HERE), "Resources", "PolarCNC.svg")
ICON_SIM = os.path.join(os.path.dirname(HERE), "Resources", "PolarSimulate.svg")
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
        try:
            machine.add_settings(job)
        except Exception:
            App.ActiveDocument.abortTransaction()
            raise
        try:      # X Max, cutting side, Face or Wrap in one small dialog (Cancel keeps them as they are)
            from . import dialogs
            if dialogs.ask_settings_on():
                dialogs.run(dialogs.SettingsDialog(job, Gui.getMainWindow()))
        except Exception as e:
            App.Console.PrintWarning("Polar CNC: the settings dialog failed (%s); set them in the "
                                     "Job's properties, group 'Polar CNC'.\n" % e)
        if POST in job.getEnumerationsOfProperty("PostProcessor"):
            job.PostProcessor = POST
        else:
            App.Console.PrintWarning("Polar CNC: the %s post-processor was not found; check that "
                                     "the addon is installed.\n" % POST)
        try:
            ops = policy.apply_defaults(job)
            App.Console.PrintMessage("Polar CNC: polar defaults for new operations: %s\n"
                                     % ", ".join(ops))
        except Exception as e:
            App.Console.PrintWarning("Polar CNC: could not set the operation defaults: %s\n" % e)
        App.ActiveDocument.commitTransaction()
        for op in job.Operations.Group:     # operations made before the Job became polar
            for msg in policy.problems(op):
                App.Console.PrintWarning("Polar CNC (%s): %s\n" % (op.Label, msg))
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(job)   # the property editor shows the new "Polar CNC" group
        App.Console.PrintMessage(
            "Polar CNC: Job '%s' is now polar. The settings are in its properties, group 'Polar "
            "CNC'%s. The CAM work origin X0 Y0 must be the chuck centre.\n"
            % (job.Label, "" if job.PolarXMax.Value > 0 else " (Polar X Max is still to be set)"))


class SimulateCommand:
    """Play the polar program of the Job: the chuck turns, the cutter moves in X and Z."""

    def GetResources(self):
        return {
            "Pixmap": ICON_SIM,
            "MenuText": "Polar simulation",
            "ToolTip": "Simulate the POLAR program of the selected polar Job (what Post Process "
                       "writes): the part turns with the chuck and the cutter moves only in X "
                       "and Z. A part view shows the same with the part standing still.",
        }

    def IsActive(self):
        try:
            job = policy.current_job()      # face or wrap Job
            return job is not None and machine.has_settings(job) and Gui.Control.activeDialog() is False
        except Exception:
            return False

    def Activated(self):
        from . import simulator
        job = policy.current_job()
        if job is not None and machine.has_settings(job):
            simulator.open_for(job)


class PolarFaceCommand:
    """Polar Face (the CAM modules are loaded only when it is used)."""

    def GetResources(self):
        return {"Pixmap": os.path.join(os.path.dirname(HERE), "Resources", "PolarFace.svg"),
                "MenuText": "Polar Face",
                "ToolTip": "Polar Face: facing for a polar Job that cuts only where the stock "
                           "is (round, square, hexagon, any shape): circles round the chuck "
                           "axis, outside in, linked without cutting air."}

    def IsActive(self):
        try:
            return policy.is_polar(policy.current_job())
        except Exception:
            return False

    def Activated(self):
        from . import polarface_gui
        polarface_gui.register()
        return polarface_gui.Command().Activated()


class PolarWrapCommand:
    """Polar Wrap (Wrap Jobs: the router radial, the outside of the real part)."""

    def GetResources(self):
        return {"Pixmap": os.path.join(os.path.dirname(HERE), "Resources", "PolarWrap.svg"),
                "MenuText": "Polar Wrap",
                "ToolTip": "Polar Wrap: machine the outside of the 3D part (solid or STL) with "
                           "the router radial. It is unrolled automatically; enter only the "
                           "stock diameter (Job -> Polar Wrap Diameter)."}

    def IsActive(self):
        try:
            job = policy.current_job()
            return job is not None and machine.is_wrap(job)
        except Exception:
            return False

    def Activated(self):
        from . import polarwrap_gui
        polarwrap_gui.register()
        return polarwrap_gui.Command().Activated()


class ChuckCommand:
    """The Job's chuck or faceplate: made the first time, selected (to edit) after that."""

    def GetResources(self):
        return {"Pixmap": os.path.join(os.path.dirname(HERE), "Resources", "PolarChuck.svg"),
                "MenuText": "Chuck",
                "ToolTip": "The chuck or faceplate that holds the stock of the polar Job: 3-jaw, "
                           "4-jaw (independent or self-centring), or a faceplate with clamps. "
                           "Choose a catalogue size (SAN OU K72-125, K12-125, …) or your own; the jaws close on the real stock. "
                           "Polar Face keeps clear of it and the simulator shows it."}

    def IsActive(self):
        try:
            job = policy.current_job()      # face or wrap Job
            return job is not None and machine.has_settings(job)
        except Exception:
            return False

    def Activated(self):
        from . import chuck
        job = policy.current_job()
        obj = getattr(job, "PolarChuck", None)
        names = list(chuck.PRESETS)
        current = obj.Preset if obj is not None else names[1]
        from . import dialogs
        dlg = dialogs.ChuckDialog(chuck.PRESETS, chuck.CUSTOM, current if current in names else names[1],
                                  Gui.getMainWindow())
        ok = dialogs.run(dlg)
        name = dlg.textValue()
        if not ok:
            if obj is None:
                return
        else:
            doc = App.ActiveDocument
            doc.openTransaction("Polar chuck")
            try:
                if obj is None:
                    obj = chuck.make_chuck(job, name if name != chuck.CUSTOM else names[1])
                    _style(obj)
                    if machine.is_wrap(job):      # in the machine frame, not the unrolled one
                        obj.ViewObject.Visibility = False
                obj.Preset = name              # Custom keeps the sizes, ready to be changed
                doc.recompute()
            except Exception:
                doc.abortTransaction()
                raise
            doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        for note in obj.Notes:
            App.Console.PrintMessage("Polar CNC chuck: %s\n" % note)


class ClampCommand:
    def GetResources(self):
        return {"Pixmap": os.path.join(os.path.dirname(HERE), "Resources", "PolarClamp.svg"),
                "MenuText": "Add clamp",
                "ToolTip": "Add a clamp or support to the Job's chuck / faceplate, next to the "
                           "stock; set its radius, angle and size in its properties."}

    def IsActive(self):
        try:
            return getattr(policy.current_job(), "PolarChuck", None) is not None
        except Exception:
            return False

    def Activated(self):
        from . import chuck
        job = policy.current_job()
        doc = App.ActiveDocument
        doc.openTransaction("Polar clamp")
        try:
            obj = chuck.add_clamp(job.PolarChuck)
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        _style(obj, (0.46, 0.48, 0.52))
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)


def _style(obj, rgb=(0.66, 0.68, 0.72)):
    try:
        obj.ViewObject.ShapeColor = rgb          # steel
        obj.ViewObject.Transparency = 30
    except Exception:
        pass


def _ensure_toolbar():
    """A 'Polar CNC' toolbar in the CAM workbench (the same mechanism as Tools -> Customize)."""
    grp = App.ParamGet("User parameter:BaseApp/Workbench/CAMWorkbench/Toolbar/PolarCNC")
    if not grp.GetString("Name", ""):
        grp.SetString("Name", "Polar CNC")
        grp.SetBool("Active", True)
    for cmd in ("PolarCNC_MachineSettings", "PolarCNC_Chuck", "PolarCNC_Clamp",
                "PolarCNC_PolarFace", "PolarCNC_PolarWrap", "PolarCNC_Simulate", "PolarCNC_Help"):
        if not grp.GetString(cmd, ""):
            grp.SetString(cmd, "PolarCNC")


def register_post():
    """Make the polar_linuxcnc post known to CAM. package.xml declares it (<Postprocessor>, with
    the capital P that FreeCAD 26.3 looks for); addAddonPostPath() is the documented call for
    addons and covers versions that scan package.xml differently."""
    import Path.Preferences
    if hasattr(Path.Preferences, "addAddonPostPath"):
        Path.Preferences.addAddonPostPath(os.path.join(os.path.dirname(HERE), "posts"))


def _on_workbench(name):
    # the CAM command objects exist once CAM has loaded: grey out the unsuitable ones then
    if name == "CAMWorkbench":
        try:
            policy.install_blocking()
            from . import polarface_gui, polarwrap_gui
            polarface_gui.register()
            polarwrap_gui.register()
        except Exception as e:
            App.Console.PrintError("Polar CNC: %s\n" % e)
        try:     # the toolbar buttons exist once the workbench has built them
            from PySide import QtCore
            QtCore.QTimer.singleShot(300, help.install_toolbar)
        except Exception as e:
            App.Console.PrintLog("Polar CNC help: %s\n" % e)


def install():
    register_post()
    Gui.addCommand("PolarCNC_MachineSettings", MachineSettingsCommand())
    Gui.addCommand("PolarCNC_Simulate", SimulateCommand())
    Gui.addCommand("PolarCNC_PolarFace", PolarFaceCommand())
    Gui.addCommand("PolarCNC_PolarWrap", PolarWrapCommand())
    Gui.addCommand("PolarCNC_Chuck", ChuckCommand())
    Gui.addCommand("PolarCNC_Clamp", ClampCommand())
    Gui.addCommand("PolarCNC_Help", help.LanguageCommand())
    _ensure_toolbar()
    policy.install_observer()
    Gui.getMainWindow().workbenchActivated.connect(_on_workbench)
