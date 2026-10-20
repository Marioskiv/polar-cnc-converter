# Polar CNC — the two small dialogs: the machine settings of a Job (asked once, when the Job
# becomes polar) and the chuck chooser (type first, then the size). Greek or English, with a "?"
# on every field, like the rest of the help.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import FreeCAD as App
from PySide import QtGui

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
    """The machining type of the Job (ordinary CAM, polar or Wrap) and its settings, in one
    place. After OK, `kind` is "normal", "face" or "wrap"."""

    KINDS = ("normal", "face", "wrap")

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.kind = None
        self.setObjectName("PolarSettings")
        self.setWindowTitle(text("settings"))
        lay = QtGui.QVBoxLayout(self)
        form = QtGui.QFormLayout()
        lay.addLayout(form)
        self.kind_box = QtGui.QComboBox()
        self.kind_box.addItems([text("kind_normal"), text("kind_face"), text("kind_wrap")])
        polar = machine.has_settings(job)
        self.kind_box.setCurrentIndex(0 if not polar else (2 if machine.is_wrap(job) else 1))
        if not polar:
            self.kind_box.setCurrentIndex(1)       # pressed on an ordinary Job: it is to be polar
        help.add_row(form, "Settings:Kind", "Machining type", self.kind_box)

        def value(name):
            v = getattr(job, name, None)
            return getattr(v, "Value", 0.0) if v is not None else 0.0
        self.xmax = _length(0, 10000, value("PolarXMax"))
        help.add_row(form, "Settings:XMax", "X Max", self.xmax)
        self.side = QtGui.QComboBox()
        self.side.addItems([text("one"), text("both")])
        self.side.setCurrentIndex(1 if getattr(job, "PolarCuttingSide", "") == machine.BOTH_SIDES else 0)
        help.add_row(form, "Settings:Side", "Cutting side", self.side)
        self.past = _length(0, 1000, value("PolarPastCentre"))
        help.add_row(form, "Settings:PastCentre", "Past the centre", self.past)
        self.wrap_xmax = _length(0, 10000, value("PolarWrapXMax"))
        help.add_row(form, "Settings:WrapXMax", "Wrap X Max", self.wrap_xmax)
        self.diameter = _length(0, 10000, value("PolarWrapDiameter"))
        help.add_row(form, "Settings:WrapDiameter", "Bar diameter", self.diameter)
        self.in_x = QtGui.QCheckBox()
        self.in_x.setChecked(bool(getattr(job, "PolarWrapToolLengthInX", False)))
        help.add_row(form, "Settings:ToolLengthInX", "Tool lengths in X", self.in_x)
        self.what = QtGui.QLabel()
        self.what.setObjectName("what")
        self.what.setWordWrap(True)
        self.what.setStyleSheet("color: #334e68;")
        lay.addWidget(self.what)
        self.problem = QtGui.QLabel()
        self.problem.setObjectName("problem")
        self.problem.setStyleSheet("color: #9b1c1c;")
        self.problem.setWordWrap(True)
        lay.addWidget(self.problem)
        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.kind_box.currentIndexChanged.connect(self._enable)
        self.side.currentIndexChanged.connect(self._enable)
        for box in (self.xmax, self.wrap_xmax, self.diameter):
            box.valueChanged.connect(lambda *_: self.problem.setText(""))
        self._enable()
        self.setMinimumWidth(500)

    def _chosen(self):
        return self.KINDS[self.kind_box.currentIndex()]

    def _enable(self, *_):
        kind = self._chosen()
        face, wrap = kind == "face", kind == "wrap"
        self.xmax.setEnabled(face or wrap)
        self.side.setEnabled(face)
        self.past.setEnabled(face and self.side.currentIndex() == 1)
        self.wrap_xmax.setEnabled(wrap)
        self.diameter.setEnabled(wrap)
        self.in_x.setEnabled(wrap)
        self.what.setText(text("what_" + kind))
        self.problem.setText("")

    def accept(self):
        kind = self._chosen()
        if kind == "normal":
            self.kind = kind
            super().accept()
            return
        wrap = kind == "wrap"
        x_max = self.wrap_xmax.value() if wrap and self.wrap_xmax.value() > 0 else self.xmax.value()
        if x_max <= 0:
            self.problem.setText(text("need_x"))
            (self.wrap_xmax if wrap else self.xmax).setFocus()
            return
        if wrap and self.diameter.value() <= 0:
            self.problem.setText(text("need_d"))
            self.diameter.setFocus()
            return
        job = self.job
        machine.add_settings(job)
        job.PolarLayout = machine.WRAP if wrap else machine.FACE
        job.PolarXMax = self.xmax.value()
        job.PolarCuttingSide = machine.BOTH_SIDES if self.side.currentIndex() == 1 else machine.ONE_SIDE
        job.PolarPastCentre = self.past.value()
        job.PolarWrapXMax = self.wrap_xmax.value()
        job.PolarWrapDiameter = self.diameter.value()
        job.PolarWrapToolLengthInX = self.in_x.isChecked()
        self.kind = kind
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


class ChuckSetupDialog(QtGui.QDialog):
    """After the face was picked: what was found, the chuck chosen and the grip, to check."""

    def __init__(self, presets, mine, preset, grip, notes, parent=None):
        super().__init__(parent)
        self.setObjectName("PolarChuckSetup")
        self.setWindowTitle(text("chuck"))
        lay = QtGui.QVBoxLayout(self)
        found = QtGui.QLabel("\n".join(notes))
        found.setObjectName("found")
        found.setWordWrap(True)
        found.setStyleSheet("color: #334e68;")
        lay.addWidget(found)
        form = QtGui.QFormLayout()
        lay.addLayout(form)
        self.preset_box = QtGui.QComboBox()
        names = list(mine) + [n for n, v in presets.items() if v is not None and n not in mine]
        self.preset_box.addItems(names)
        if len(mine) < len(names):
            self.preset_box.insertSeparator(len(mine))
        self.preset_box.setCurrentIndex(max(self.preset_box.findText(preset), 0))
        help.add_row(form, "Chuck:Pick", "Chuck", self.preset_box)
        self.grip_box = _length(0, 200, grip)
        help.add_row(form, "Chuck:Grip", "Grip length", self.grip_box)
        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.setMinimumWidth(480)

    def preset(self):
        return self.preset_box.currentText()

    def grip(self):
        return self.grip_box.value()


class PickFaceDialog(QtGui.QDialog):
    """No face picked: say what to do, or let the chuck be chosen by hand."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PolarPickFace")
        self.setWindowTitle(text("chuck"))
        self.by_hand = False
        lay = QtGui.QVBoxLayout(self)
        msg = QtGui.QLabel(text("pick_face"))
        msg.setObjectName("message")
        msg.setWordWrap(True)
        lay.addWidget(msg)
        buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok)
        hand = buttons.addButton(text("by_hand"), QtGui.QDialogButtonBox.ActionRole)
        hand.clicked.connect(self._hand)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)
        self.setMinimumWidth(460)

    def _hand(self):
        self.by_hand = True
        self.accept()
