# Polar CNC — the two small dialogs: the machine settings of a Job (asked once, when the Job
# becomes polar) and the chuck chooser (type first, then the size). Greek or English, with a "?"
# on every field, like the rest of the help.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import FreeCAD as App
from PySide import QtCore, QtGui

from . import help, machine

PARAM = help.PARAM


def text(key):
    d = help.data()["dialogs"]
    return (d.get(help.language()) or d["en"]).get(key) or d["en"][key]


def ask_settings_on():
    """The settings dialog opens when a Job becomes polar (the tests switch it off)."""
    return App.ParamGet(PARAM).GetBool("SettingsDialog", True)


def _length(lo, hi, value):
    box = QtGui.QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setDecimals(3)
    box.setSuffix(" mm")
    box.setValue(value)
    return box


class SettingsDialog(QtGui.QDialog):
    """The Job's Polar CNC settings in one place, instead of the property editor."""

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setObjectName("PolarSettings")
        self.setWindowTitle(text("settings"))
        lay = QtGui.QVBoxLayout(self)
        form = QtGui.QFormLayout()
        lay.addLayout(form)
        self.layout_box = QtGui.QComboBox()
        self.layout_box.addItems([text("face"), text("wrap")])
        self.layout_box.setCurrentIndex(1 if machine.is_wrap(job) else 0)
        help.add_row(form, "Settings:Layout", "Router", self.layout_box)
        self.xmax = _length(0, 10000, job.PolarXMax.Value)
        help.add_row(form, "Settings:XMax", "X Max", self.xmax)
        self.side = QtGui.QComboBox()
        self.side.addItems([text("one"), text("both")])
        self.side.setCurrentIndex(1 if job.PolarCuttingSide == machine.BOTH_SIDES else 0)
        help.add_row(form, "Settings:Side", "Cutting side", self.side)
        self.past = _length(0, 1000, job.PolarPastCentre.Value)
        help.add_row(form, "Settings:PastCentre", "Past the centre", self.past)
        self.diameter = _length(0, 10000, job.PolarWrapDiameter.Value)
        help.add_row(form, "Settings:WrapDiameter", "Bar diameter", self.diameter)
        self.in_x = QtGui.QCheckBox()
        self.in_x.setChecked(bool(job.PolarWrapToolLengthInX))
        help.add_row(form, "Settings:ToolLengthInX", "Tool lengths in X", self.in_x)
        self.problem = QtGui.QLabel()
        self.problem.setObjectName("problem")
        self.problem.setStyleSheet("color: #9b1c1c;")
        self.problem.setWordWrap(True)
        lay.addWidget(self.problem)
        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.layout_box.currentIndexChanged.connect(self._enable)
        self.side.currentIndexChanged.connect(self._enable)
        for box in (self.xmax, self.diameter):
            box.valueChanged.connect(lambda *_: self.problem.setText(""))
        self._enable()
        self.setMinimumWidth(460)

    def _enable(self, *_):
        wrap = self.layout_box.currentIndex() == 1
        self.past.setEnabled(self.side.currentIndex() == 1)
        self.diameter.setEnabled(wrap)
        self.in_x.setEnabled(wrap)

    def accept(self):
        if self.xmax.value() <= 0:
            self.problem.setText(text("need_x"))
            self.xmax.setFocus()
            return
        wrap = self.layout_box.currentIndex() == 1
        if wrap and self.diameter.value() <= 0:
            self.problem.setText(text("need_d"))
            self.diameter.setFocus()
            return
        job = self.job
        job.PolarLayout = machine.WRAP if wrap else machine.FACE
        job.PolarXMax = self.xmax.value()
        job.PolarCuttingSide = machine.BOTH_SIDES if self.side.currentIndex() == 1 else machine.ONE_SIDE
        job.PolarPastCentre = self.past.value()
        job.PolarWrapDiameter = self.diameter.value()
        job.PolarWrapToolLengthInX = self.in_x.isChecked()
        super().accept()


class ChuckDialog(QtGui.QDialog):
    """Type first, then the size; the sizes of the choice are shown under it."""

    def __init__(self, presets, custom, current, parent=None):
        super().__init__(parent)
        self.presets = presets
        self.custom = custom
        self.setObjectName("PolarChuckChooser")
        self.setWindowTitle(text("chuck"))
        lay = QtGui.QVBoxLayout(self)
        form = QtGui.QFormLayout()
        lay.addLayout(form)
        names = text("types")
        self.types = []
        for value in presets.values():
            if value is not None and value[0] not in self.types:
                self.types.append(value[0])
        self.type_box = QtGui.QComboBox()
        for typ in self.types:
            self.type_box.addItem(names.get(typ, typ))
        self.type_box.addItem(text("custom"))
        help.add_row(form, "Chuck:Type", "Type", self.type_box)
        self.size_box = QtGui.QComboBox()
        help.add_row(form, "Chuck:Size", "Size", self.size_box)
        self.sizes = QtGui.QLabel()
        self.sizes.setObjectName("sizes")
        self.sizes.setStyleSheet("color: #334e68;")
        lay.addWidget(self.sizes)
        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.type_box.currentIndexChanged.connect(self._fill_sizes)
        self.size_box.currentIndexChanged.connect(self._show_sizes)
        self.setTextValue(current)
        self.setMinimumWidth(460)

    def _names_of(self, index):
        if index >= len(self.types):
            return [self.custom]
        return [n for n, v in self.presets.items() if v is not None and v[0] == self.types[index]]

    def _fill_sizes(self, *_):
        self.size_box.blockSignals(True)
        self.size_box.clear()
        self.size_box.addItems(self._names_of(self.type_box.currentIndex()))
        self.size_box.setEnabled(self.type_box.currentIndex() < len(self.types))
        self.size_box.blockSignals(False)
        self._show_sizes()

    def _show_sizes(self, *_):
        value = self.presets.get(self.textValue())
        if value is None:
            self.sizes.setText(text("custom_note"))
        elif value[3] == 0:
            self.sizes.setText(text("plate") % {"d": value[1], "b": value[2]})
        else:
            self.sizes.setText(text("sizes") % {"d": value[1], "l": value[3], "w": value[4], "h": value[5]})

    def textValue(self):
        """The preset name chosen (the same answer QInputDialog gave)."""
        return self.size_box.currentText() or self.custom

    def setTextValue(self, name):
        value = self.presets.get(name)
        index = self.types.index(value[0]) if value is not None else len(self.types)
        self.type_box.blockSignals(True)
        self.type_box.setCurrentIndex(index)
        self.type_box.blockSignals(False)
        self._fill_sizes()
        if value is not None:
            self.size_box.setCurrentIndex(max(self.size_box.findText(name), 0))
        self._show_sizes()


def run(dialog):
    """Shows a dialog modally; True when OK was pressed."""
    result = dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()
    return result == QtGui.QDialog.Accepted
