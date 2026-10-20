# Polar CNC — the Polar Wrap operation in the CAM workbench: command, task panel page, tree icon.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os

import Path.Base.SetupSheet as PathSetupSheet
import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.Selection as PathSelection
import PathScripts.PathUtils as PathUtils
from PySide import QtGui

from . import help, polarwrap

NAME = "PolarWrap"          # also the key of its defaults in the Job's SetupSheet
ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Resources", "PolarWrap.svg")


def _tip(prop):
    for _typ, name, tip in polarwrap.PROPERTIES:
        if name == prop:
            return tip
    return ""


class TaskPanelOpPage(PathOpGui.TaskPanelPage):

    def getForm(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Polar Wrap")
        lay = QtGui.QFormLayout(w)
        self.strategy = QtGui.QComboBox()
        self.strategy.addItems(polarwrap.STRATEGIES)
        self.strategy.setToolTip(_tip("Strategy"))
        help.add_row(lay, "PolarWrap:Strategy", "Strategy", self.strategy)

        def length(prop, lo, hi, suffix=" mm", dec=3):
            box = QtGui.QDoubleSpinBox()
            box.setRange(lo, hi)
            box.setDecimals(dec)
            box.setSuffix(suffix)
            box.setToolTip(_tip(prop))
            return box

        def percent(prop):
            box = QtGui.QSpinBox()
            box.setRange(1, 100)
            box.setSuffix(" %")
            box.setToolTip(_tip(prop))
            return box
        self.style = QtGui.QComboBox()
        self.style.addItems(polarwrap.FINISH_STYLES)
        self.style.setToolTip(_tip("FinishStyle"))
        help.add_row(lay, "PolarWrap:FinishStyle", "Finishing", self.style)
        self.step = percent("StepOver")
        help.add_row(lay, "PolarWrap:StepOver", "Finish step over", self.step)
        self.rstep = percent("RoughStepOver")
        help.add_row(lay, "PolarWrap:RoughStepOver", "Rough step over", self.rstep)
        self.down = length("StepDown", 0.01, 50)
        help.add_row(lay, "PolarWrap:StepDown", "Step down", self.down)
        self.allow = length("FinishAllowance", 0, 10)
        help.add_row(lay, "PolarWrap:FinishAllowance", "Finish allowance", self.allow)
        self.leave = length("StockToLeave", -5, 10)
        help.add_row(lay, "PolarWrap:StockToLeave", "Stock to leave", self.leave)
        self.direction = QtGui.QComboBox()
        self.direction.addItems(polarwrap.DIRECTIONS)
        self.direction.setToolTip(_tip("Direction"))
        help.add_row(lay, "PolarWrap:Direction", "Chuck turns", self.direction)
        self.grid = length("GridStep", 0.05, 5)
        help.add_row(lay, "PolarWrap:GridStep", "Resolution", self.grid)
        self.after = QtGui.QComboBox()
        self.after.setToolTip(_tip("AfterOperation"))
        help.add_row(lay, "PolarWrap:AfterOperation", "After operation", self.after)
        self.report = QtGui.QLabel()
        self.report.setObjectName("toolReport")
        self.report.setWordWrap(True)
        self.report.setStyleSheet("color: #334e68;")
        lay.addRow(self.report)
        note = QtGui.QLabel(help.note("PolarWrap", ""))
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def getFields(self, obj):
        if obj.Strategy != self.strategy.currentText():
            obj.Strategy = self.strategy.currentText()
        if obj.FinishStyle != self.style.currentText():
            obj.FinishStyle = self.style.currentText()
        if obj.Direction != self.direction.currentText():
            obj.Direction = self.direction.currentText()
        for prop, box in (("StepOver", self.step), ("RoughStepOver", self.rstep)):
            if getattr(obj, prop) != box.value():
                setattr(obj, prop, box.value())
        for prop, box in (("StepDown", self.down), ("FinishAllowance", self.allow),
                          ("StockToLeave", self.leave), ("GridStep", self.grid)):
            if abs(getattr(obj, prop).Value - box.value()) > 1e-9:
                setattr(obj, prop, box.value())
        chosen = self.after.currentData() if hasattr(self.after, "currentData") else None
        target = obj.Document.getObject(chosen) if chosen else None
        if getattr(obj, "AfterOperation", None) is not target:
            obj.AfterOperation = target

    def setFields(self, obj):
        self.strategy.setCurrentIndex(max(self.strategy.findText(obj.Strategy), 0))
        self.direction.setCurrentIndex(max(self.direction.findText(obj.Direction), 0))
        self.style.setCurrentIndex(max(self.style.findText(obj.FinishStyle), 0))
        self.step.setValue(obj.StepOver)
        self.rstep.setValue(obj.RoughStepOver)
        self.down.setValue(obj.StepDown.Value)
        self.allow.setValue(obj.FinishAllowance.Value)
        self.leave.setValue(obj.StockToLeave.Value)
        self.grid.setValue(obj.GridStep.Value)
        self._fill_after(obj)
        self.report.setText(getattr(obj, "ToolReport", "") or "")

    def _fill_after(self, obj):
        """The Polar Wrap operations of the Job before this one (the machine runs them in order)."""
        self.after.blockSignals(True)
        self.after.clear()
        self.after.addItem("—", "")
        ops = []
        job = PathUtils.findParentJob(obj)
        for o in getattr(getattr(job, "Operations", None), "Group", []):
            if o is obj:
                break
            if type(getattr(o, "Proxy", None)).__name__ == "ObjectPolarWrap":
                ops.append(o)
        for o in ops:
            self.after.addItem(o.Label, o.Name)
        cur = getattr(obj, "AfterOperation", None)
        k = self.after.findData(cur.Name) if cur is not None else 0
        self.after.setCurrentIndex(max(k, 0))
        self.after.blockSignals(False)

    def getSignalsForUpdate(self, obj):
        # no remake on every change of a field (mapping the part can take seconds): on OK/Apply
        return []


class ViewProvider(PathOpGui.ViewProvider):
    """CAM's view provider, with our icon and a selection mode (CAM's own table of operations
    does not know this one)."""

    def __init__(self, vobj, resources):
        super().__init__(vobj, resources)
        self.OpIcon = ICON

    def getIcon(self):
        if getattr(self.Object, "Active", True):
            return ICON
        return ":/icons/CAM_OpActive.svg"

    def getSelectionFactory(self):
        return PathSelection.pocketselect


class Command:
    def __init__(self):
        self.res = PathOpGui.CommandResources(
            NAME, polarwrap.Create, TaskPanelOpPage, ICON, "Polar Wrap", None,
            "Polar Wrap: the outside of the part with the router radial (Wrap Job), from the "
            "3D part itself: helices round it, roughing and finishing.")

    def Activated(self):
        jobs = PathUtils.GetJobs()
        if not jobs:
            return None
        job = PathUtils.UserInput.chooseJob(jobs)
        if job is None:
            return None
        self.res.job = job
        return create(self.res)


def create(res):
    """Make a Polar Wrap operation in res.job and open its task panel.
    2.22.0: written anew for this addon. Everything happens in one undo step: if no operation
    comes out of it - the Job has no tool controller, or the tool controller chooser was
    cancelled - the step is undone, so no half-made operation is left in the Job."""
    import FreeCAD as App
    import Path.Op.Base as PathOp
    doc = App.ActiveDocument
    if doc is None or getattr(res, "job", None) is None:
        return None
    doc.openTransaction("Polar Wrap")
    made = None
    try:
        made = res.objFactory(res.name, obj=None, parentJob=res.job)
    except PathUtils.PathNoTCExistsException:
        help.error_card("This Job has no tool controller. Add one (a cutter with its diameter and "
                        "feeds), then make the Polar Wrap.", "Polar Wrap")
    except PathOp.PathNoTCException:
        App.Console.PrintMessage("Polar Wrap: no tool controller chosen, nothing made.\n")
    if made is None or not getattr(made, "Proxy", None):
        doc.abortTransaction()           # also removes an object the factory had begun
        doc.recompute()
        return None
    view = made.ViewObject
    view.Proxy = ViewProvider(view, res)
    view.Visibility = True
    doc.commitTransaction()
    view.Document.setEdit(view, 0)       # its task panel
    return made


def register():
    PathSetupSheet.RegisterOperation(NAME, polarwrap.Create, polarwrap.SetupProperties)
