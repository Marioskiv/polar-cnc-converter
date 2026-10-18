# Polar CNC — the Polar Face operation in the CAM workbench: command, task panel page, tree icon.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os

import FreeCAD as App
import FreeCADGui as Gui
import Path.Base.SetupSheet as PathSetupSheet
import Path.Op.Gui.Base as PathOpGui
import Path.Op.Gui.Selection as PathSelection
import PathScripts.PathUtils as PathUtils
from PySide import QtCore, QtGui

from . import help, polarface

NAME = "PolarFace"          # also the key of its defaults in the Job's SetupSheet
ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Resources", "PolarFace.svg")


class TaskPanelOpPage(PathOpGui.TaskPanelPage):

    def getForm(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Polar Face")
        lay = QtGui.QFormLayout(w)
        self.clearing = QtGui.QComboBox()
        self.clearing.addItems(polarface.CLEARINGS)
        self.clearing.setToolTip(polarface_tip("Clearing"))
        help.add_row(lay, "PolarFace:Clearing", "What to cut", self.clearing)
        self.band = QtGui.QDoubleSpinBox()
        self.band.setRange(0, 500)
        self.band.setDecimals(3)
        self.band.setSuffix(" mm")
        self.band.setSpecialValueText("auto")
        self.band.setToolTip(polarface_tip("BandWidth"))
        help.add_row(lay, "PolarFace:BandWidth", "Band width", self.band)
        self.clearing.currentIndexChanged.connect(
            lambda i: self.band.setEnabled(polarface.CLEARINGS[i] == polarface.BAND))
        self.step = QtGui.QSpinBox()
        self.step.setRange(5, 100)
        self.step.setSuffix(" %")
        self.step.setToolTip(polarface_tip("StepOver"))
        help.add_row(lay, "PolarFace:StepOver", "Step over", self.step)
        self.leave = QtGui.QDoubleSpinBox()
        self.leave.setRange(0, 50)
        self.leave.setDecimals(3)
        self.leave.setSuffix(" mm")
        self.leave.setToolTip(polarface_tip("StockToLeave"))
        help.add_row(lay, "PolarFace:StockToLeave", "Stock to leave", self.leave)
        self.mode = QtGui.QComboBox()
        self.mode.addItems(["Climb", "Conventional"])
        self.mode.setToolTip(polarface_tip("CutMode"))
        help.add_row(lay, "PolarFace:CutMode", "Cut mode", self.mode)
        self.air = QtGui.QDoubleSpinBox()
        self.air.setRange(1, 20)
        self.air.setDecimals(1)
        self.air.setSuffix(" ×")
        self.air.setToolTip(polarface_tip("AirFeedFactor"))
        help.add_row(lay, "PolarFace:AirFeedFactor", "Air feed", self.air)
        note = QtGui.QLabel(help.note("PolarFace", ""))
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def getFields(self, obj):
        if obj.Clearing != self.clearing.currentText():
            obj.Clearing = self.clearing.currentText()
        if abs(obj.BandWidth.Value - self.band.value()) > 1e-9:
            obj.BandWidth = self.band.value()
        if obj.StepOver != self.step.value():
            obj.StepOver = self.step.value()
        if abs(obj.StockToLeave.Value - self.leave.value()) > 1e-9:
            obj.StockToLeave = self.leave.value()
        if obj.CutMode != self.mode.currentText():
            obj.CutMode = self.mode.currentText()
        if abs(obj.AirFeedFactor - self.air.value()) > 1e-9:
            obj.AirFeedFactor = self.air.value()

    def setFields(self, obj):
        self.clearing.setCurrentIndex(max(self.clearing.findText(obj.Clearing), 0))
        self.band.setValue(obj.BandWidth.Value)
        self.band.setEnabled(obj.Clearing == polarface.BAND)
        self.step.setValue(obj.StepOver)
        self.leave.setValue(obj.StockToLeave.Value)
        self.mode.setCurrentIndex(max(self.mode.findText(obj.CutMode), 0))
        self.air.setValue(obj.AirFeedFactor)

    def getSignalsForUpdate(self, obj):
        return [self.clearing.currentIndexChanged, self.band.valueChanged,
                self.step.valueChanged, self.leave.valueChanged, self.mode.currentIndexChanged,
                self.air.valueChanged]


def polarface_tip(prop):
    for typ, name, tip in polarface.PROPERTIES:
        if name == prop:
            return tip
    return ""


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
            NAME, polarface.Create, TaskPanelOpPage, ICON, "Polar Face", None,
            "Polar Face: facing for a polar Job, cutting only where the stock is (round, "
            "square, hexagon, any shape): circles round the chuck axis, outside in.")

    def GetResources(self):
        return {"Pixmap": ICON, "MenuText": "Polar Face", "ToolTip": self.res.toolTip}

    def IsActive(self):
        try:
            from . import policy
            return policy.is_polar(policy.current_job())
        except Exception:
            return False

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
        help.error_card("No suitable tool controller found. Add one to the Job first.", "Polar Face")
    doc.abortTransaction()
    doc.recompute()
    return None


def register():
    """The Job's SetupSheet keeps defaults for operations registered here."""
    PathSetupSheet.RegisterOperation(NAME, polarface.Create, polarface.SetupProperties)
