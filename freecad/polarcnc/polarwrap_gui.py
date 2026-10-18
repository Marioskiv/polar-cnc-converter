# Polar CNC — the Polar Wrap operation in the CAM workbench: command, task panel page, tree icon.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os

import Path.Base.SetupSheet as PathSetupSheet
import Path.Op.Gui.Base as PathOpGui
import PathScripts.PathUtils as PathUtils
from PySide import QtGui

from . import polarface_gui, polarwrap

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
        lay.addRow("Strategy", self.strategy)

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
        self.step = percent("StepOver")
        lay.addRow("Finish step over", self.step)
        self.rstep = percent("RoughStepOver")
        lay.addRow("Rough step over", self.rstep)
        self.down = length("StepDown", 0.01, 50)
        lay.addRow("Step down", self.down)
        self.allow = length("FinishAllowance", 0, 10)
        lay.addRow("Finish allowance", self.allow)
        self.leave = length("StockToLeave", -5, 10)
        lay.addRow("Stock to leave", self.leave)
        self.direction = QtGui.QComboBox()
        self.direction.addItems(polarwrap.DIRECTIONS)
        self.direction.setToolTip(_tip("Direction"))
        lay.addRow("Chuck turns", self.direction)
        self.grid = length("GridStep", 0.05, 5)
        lay.addRow("Resolution", self.grid)
        note = QtGui.QLabel("The part as it is (solid or STL), its axis on Z: it is unrolled "
                            "automatically and machined with helices round it, from the free "
                            "end toward the chuck. Set the stock diameter in the Job "
                            "(Polar Wrap Diameter).")
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def getFields(self, obj):
        if obj.Strategy != self.strategy.currentText():
            obj.Strategy = self.strategy.currentText()
        if obj.Direction != self.direction.currentText():
            obj.Direction = self.direction.currentText()
        for prop, box in (("StepOver", self.step), ("RoughStepOver", self.rstep)):
            if getattr(obj, prop) != box.value():
                setattr(obj, prop, box.value())
        for prop, box in (("StepDown", self.down), ("FinishAllowance", self.allow),
                          ("StockToLeave", self.leave), ("GridStep", self.grid)):
            if abs(getattr(obj, prop).Value - box.value()) > 1e-9:
                setattr(obj, prop, box.value())

    def setFields(self, obj):
        self.strategy.setCurrentIndex(max(self.strategy.findText(obj.Strategy), 0))
        self.direction.setCurrentIndex(max(self.direction.findText(obj.Direction), 0))
        self.step.setValue(obj.StepOver)
        self.rstep.setValue(obj.RoughStepOver)
        self.down.setValue(obj.StepDown.Value)
        self.allow.setValue(obj.FinishAllowance.Value)
        self.leave.setValue(obj.StockToLeave.Value)
        self.grid.setValue(obj.GridStep.Value)

    def getSignalsForUpdate(self, obj):
        return [self.strategy.currentIndexChanged, self.direction.currentIndexChanged,
                self.step.valueChanged, self.rstep.valueChanged, self.down.valueChanged,
                self.allow.valueChanged, self.leave.valueChanged, self.grid.valueChanged]


class ViewProvider(polarface_gui.ViewProvider):
    def __init__(self, vobj, resources):
        super().__init__(vobj, resources)
        self.OpIcon = ICON

    def getIcon(self):
        if getattr(self.Object, "Active", True):
            return ICON
        return ":/icons/CAM_OpActive.svg"


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
    """CAM's own Create(res), with this operation's view provider."""
    import FreeCAD as App
    doc = App.ActiveDocument
    doc.openTransaction("Create %s" % res.name)
    try:
        obj = res.objFactory(res.name, obj=None, parentJob=res.job)
        if obj.Proxy:
            obj.ViewObject.Proxy = ViewProvider(obj.ViewObject, res)
            obj.ViewObject.Visibility = True
            doc.commitTransaction()
            obj.ViewObject.Document.setEdit(obj.ViewObject, 0)
            return obj
    except PathUtils.PathNoTCExistsException:
        QtGui.QMessageBox.warning(None, "Polar Wrap",
                                  "No suitable tool controller found. Add one to the Job first.")
    doc.abortTransaction()
    doc.recompute()
    return None


def register():
    PathSetupSheet.RegisterOperation(NAME, polarwrap.Create, polarwrap.SetupProperties)
