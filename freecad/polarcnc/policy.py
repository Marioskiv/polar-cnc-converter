# Polar CNC — which CAM operations suit a polar Job, their polar defaults, and the warnings.
#
# The choice follows how commercial CAM handles polar (C-axis) face milling: the machine makes the
# Job polar, and the face is cut with 2D / 2.5D operations (contour, pocket, facing, drilling);
# 3D surfacing is not offered. Lines and zigzags cross the face again and again, and at the
# centre the chuck would have to turn without limit to keep the feed (it cannot, so the cut
# crawls there), so ring-shaped patterns (Offset, Spiral) are the defaults. See freecad/README.md.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import importlib
import time

import FreeCAD as App

from . import machine

# CAM operation commands that are greyed out while the current Job is polar:
# command -> module that holds its Python command object (`Command`)
BLOCKED = {
    "CAM_Pocket3D": "Path.Op.Gui.Pocket",
    "CAM_Surface": "Path.Op.Gui.Surface",
    "CAM_Waterline": "Path.Op.Gui.Waterline",
    "CAM_PlanarSurface": "Path.Op.Gui.PlanarSurface",
    "CAM_RotarySurface": "Path.Op.Gui.RotarySurface",
    "CAM_Probe": "Path.Op.Gui.Probe",
}

# operations allowed in a polar Job with a word of warning: operation module -> reason
WARN_OPS = {
    "Path.Op.Adaptive": "Adaptive works, but its many short moves make the chuck change direction "
                        "very often: big files, slower near the centre. Keep it to pockets away "
                        "from the centre.",
    "Path.Op.Vcarve": "V-carve moves Z together with many direction changes: fine away from the "
                      "centre, slow and heavy close to it.",
    "Path.Op.Slot": "Slot: a slot through the centre is ideal (only X moves); one that passes "
                    "close to the centre makes the chuck race there.",
    "Path.Op.Deburr": "Deburr follows the edge: fine away from the centre, slow close to it.",
    "Path.Op.ThreadMilling": "Thread milling: each small helix off the centre makes the chuck "
                             "swing to and fro; use a low feed, holes away from the centre.",
}
# the same (dressups have no reachable command object, so they are only warned about)
WARN_DRESSUPS = {
    "Path.Dressup.AxisMap": "AxisMap wraps Y onto a rotary axis (4th axis); it does not belong in "
                            "a polar Job, which the converter turns into X/C itself.",
    "Path.Dressup.DragKnife": "Drag knife is for knives, not for a milling cutter on a chuck.",
    "Path.Dressup.ZCorrect": "Z correction needs probing data; probing is not converted to polar.",
}

# patterns that cross the face line by line -> what to use instead
BAD_PATTERNS = {
    "ClearingPattern": {"ZigZag": "Offset", "Line": "Offset", "Grid": "Offset",
                        "ZigZagOffset": "Offset", "Bidirectional": "Spiral",
                        "Directional": "Spiral"},
}
PATTERN_REASON = ("crosses the face line by line: the chuck reverses on every pass and crawls at "
                  "the centre.")

# SetupSheet operation defaults of a polar Job (only operations CAM has registered are used)
DEFAULTS = {
    "Pocket Shape": {"ClearingPattern": "Offset"},
    "Pocket3D": {"ClearingPattern": "Offset"},
    "MillFacing": {"ClearingPattern": "Spiral"},
}


def is_polar(job):
    return job is not None and machine.has_settings(job)


# ---- the current Job, the way CAM itself picks one for a new operation ----------------------
_cache = [0.0, None]


def current_job():
    """The Job a new operation would go to: the selected Job, the Job of the selected object,
    or the only Job of the document. Cached for a moment: Qt asks IsActive very often."""
    now = time.monotonic()
    if now - _cache[0] < 0.25:
        return _cache[1]
    job = None
    try:
        import FreeCADGui as Gui
        import PathScripts.PathUtils as PathUtils
        sel = Gui.Selection.getSelection()
        if sel:
            job = PathUtils.findParentJob(sel[0])
        if job is None and App.ActiveDocument is not None:
            jobs = PathUtils.GetJobs()
            if len(jobs) == 1:
                job = jobs[0]
    except Exception:
        job = None
    _cache[0], _cache[1] = now, job
    return job


# ---- greying out ---------------------------------------------------------------------------
_original = {}


def _wrap(name, module):
    try:
        cmd = importlib.import_module(module).Command
    except Exception:
        return False        # not in this FreeCAD (e.g. no OpenCamLib): nothing to grey out
    if name in _original:
        return True
    orig = cmd.IsActive
    _original[name] = (cmd, orig)

    def IsActive():
        try:
            if is_polar(current_job()):
                return False
        except Exception:
            pass
        return orig()

    cmd.IsActive = IsActive
    return True


def install_blocking():
    """Grey out the unsuitable operations while the current Job is polar (everywhere: toolbars,
    menus, shortcuts). Returns the commands that were wrapped."""
    return [name for name, module in BLOCKED.items() if _wrap(name, module)]


def uninstall_blocking():
    for cmd, orig in _original.values():
        cmd.IsActive = orig
    _original.clear()


# ---- defaults ------------------------------------------------------------------------------
def apply_defaults(job):
    """Polar defaults for NEW operations of this Job (the Job's own "Operation defaults")."""
    import Path.Base.SetupSheet as SetupSheet
    registered = getattr(SetupSheet, "_RegisteredOps", {})
    attrs = {op: props for op, props in DEFAULTS.items() if op in registered}
    job.SetupSheet.Proxy.setFromTemplate(attrs)
    if "Surface" in registered:     # if 3D Surface is ever used: rings round the chuck axis
        ss = job.SetupSheet
        job.SetupSheet.Proxy.setFromTemplate({"Surface": {"CutPattern": "Circular",
                                                          "PatternCenterAt": "Custom"}})
        if not hasattr(ss, "SurfacePatternCenterCustom"):
            ss.addProperty("App::PropertyVector", "SurfacePatternCenterCustom", "Op Surface")
        ss.SurfacePatternCenterCustom = App.Vector(0, 0, 0)
    return sorted(attrs)


# ---- warnings ------------------------------------------------------------------------------
def problems(obj):
    """What is not right for polar about this operation (empty if fine or not in a polar Job)."""
    import PathScripts.PathUtils as PathUtils
    job = PathUtils.findParentJob(obj)
    if not is_polar(job):
        return []
    out = []
    mod = type(getattr(obj, "Proxy", None)).__module__
    if mod in WARN_OPS:
        out.append(WARN_OPS[mod])
    if mod in WARN_DRESSUPS:
        out.append(WARN_DRESSUPS[mod])
    for prop, bad in BAD_PATTERNS.items():
        val = getattr(obj, prop, None)
        if val in bad:
            out.append("%s %s %s Use %s." % (prop, val, PATTERN_REASON, bad[val]))
    if getattr(obj, "Proxy", None) and mod == "Path.Op.Drilling" and \
            getattr(obj, "Strategy", "") == "Tapping":
        out.append("Tapping is not converted to polar (the converter refuses tapping cycles).")
    return out


class Observer:
    """Warns (Report view and status bar, never a dialog) when a polar Job gets an operation or a
    pattern that does not suit it. Checks are deferred: CAM sets temporary values while it
    creates an operation (e.g. ZigZag first, then the Job's default)."""

    WATCH = ("ClearingPattern", "CutPattern", "Strategy", "Base")

    def __init__(self):
        self._said = {}
        self._pending = set()

    def _later(self, obj):
        try:
            name, doc = obj.Name, obj.Document.Name
        except Exception:
            return
        if (doc, name) in self._pending:
            return
        self._pending.add((doc, name))
        from PySide import QtCore
        QtCore.QTimer.singleShot(0, lambda: self._check(doc, name))

    def _check(self, doc, name):
        self._pending.discard((doc, name))
        try:
            d = App.getDocument(doc)
            obj = d.getObject(name) if d else None
            if obj is None or "Restore" in obj.State:
                return
            msgs = problems(obj)
            key = (doc, name)
            if msgs and self._said.get(key) != msgs:
                self._said[key] = msgs
                for m in msgs:
                    App.Console.PrintWarning("Polar CNC (%s): %s\n" % (obj.Label, m))
                try:
                    import FreeCADGui as Gui
                    Gui.getMainWindow().statusBar().showMessage(
                        "Polar CNC (%s): %s" % (obj.Label, msgs[0]), 15000)
                except Exception:
                    pass
            elif not msgs:
                self._said.pop(key, None)
        except Exception:
            pass

    def slotCreatedObject(self, obj):
        self._later(obj)

    def slotChangedObject(self, obj, prop):
        if prop in self.WATCH or prop == "Group":
            self._later(obj)


_observer = []


def install_observer():
    if not _observer:
        _observer.append(Observer())
        App.addDocumentObserver(_observer[0])
    return _observer[0]
