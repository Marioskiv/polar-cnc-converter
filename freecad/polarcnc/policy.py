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
    # FreeCAD's Facing covers the stock's bounding rectangle (measured on round stock: 40 % of
    # its path in the air); a polar Job faces with Polar Face, which follows the real stock
    "CAM_MillFacing": "Path.Op.Gui.MillFacing",
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
    "Path.Op.MillFacing": "Facing covers the bounding rectangle of the stock, not the stock "
                          "itself, so much of it cuts air; use Polar Face.",
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


LIVE_CHECK_LIMIT = 5000      # Path commands an operation may have for the live chuck check


def is_polar(job):
    """A Job made for the FACE (Polar Face, the chuck, greying out). A Wrap Job is drawn flat
    (unrolled), so every operation and pattern suits it and the chuck is not in its frame."""
    return job is not None and machine.has_settings(job) and not machine.is_wrap(job)


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
    if job is not None and machine.has_settings(job) and machine.is_wrap(job):
        if hasattr(obj, "ToolController") and \
                type(getattr(obj, "Proxy", None)).__name__ != "ObjectPolarWrap":
            return ["A Wrap Job is machined with Polar Wrap (the router is radial); this operation "
                    "works on a flat face and Post Process will refuse it."]
        return []
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
    if hasattr(obj, "Path") and obj in getattr(getattr(job, "Operations", None), "Group", []):
        from . import chuck, collision
        held = getattr(job, "PolarChuck", None)
        # checked here (on every change) only for paths of a usual size, so a big 3D path never
        # slows FreeCAD down while editing; Post Process checks every path anyway
        small = len(obj.Path.Commands) <= LIVE_CHECK_LIMIT
        msg = collision.hit_message(obj, collision.obstacles(held)) if held is not None and small else None
        if msg:
            out.append(msg)
        msg = chuck.head_warning(held, obj.Path)
        if msg:
            out.append(msg)
    if getattr(obj, "Proxy", None) and mod == "Path.Op.Drilling" and \
            getattr(obj, "Strategy", "") == "Tapping":
        out.append("Tapping is not converted to polar (the converter refuses tapping cycles).")
    return out


class Observer:
    """Warns (Report view and status bar, never a dialog) when a polar Job gets an operation or a
    pattern that does not suit it. Checks are deferred: CAM sets temporary values while it
    creates an operation (e.g. ZigZag first, then the Job's default)."""

    WATCH = ("ClearingPattern", "CutPattern", "Strategy", "Base", "Path")

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
        try:
            if prop in self.WATCH or prop == "Group":
                self._later(obj)
            if prop == "Shape" and obj.TypeId == "Part::FeaturePython":
                self._chuck_changed(obj)
            elif prop in ("Stock", "PolarLayout", "PolarWrapDiameter") and \
                    getattr(obj, "PolarChuck", None) is not None:
                # not inside the change notification (it also runs during undo/redo): on the
                # next turn of the event loop, and only if something is really out of date
                from PySide import QtCore
                doc, name = obj.Document.Name, obj.Name
                QtCore.QTimer.singleShot(0, lambda: self._follow_job(doc, name))
        except Exception:
            pass

    def _follow_job(self, doc, name):
        """The chuck follows a new Job stock, layout or wrap diameter."""
        try:
            d = App.getDocument(doc)
            job = d.getObject(name) if d else None
            held = getattr(job, "PolarChuck", None) if job is not None else None
            if held is None:
                return
            if getattr(job, "Stock", None) is not None and held.Stock != job.Stock:
                held.Stock = job.Stock
            else:
                held.touch()
        except Exception:
            pass

    def _chuck_changed(self, obj):
        """A chuck or clamp changed: check the Job's operations again (cut below the jaws?)."""
        from . import chuck
        if isinstance(getattr(obj, "Proxy", None), chuck.Clamp):
            obj = next((o for o in obj.InList if obj in getattr(o, "Clamps", [])), None)
        if obj is None or not isinstance(getattr(obj, "Proxy", None), chuck.Chuck):
            return
        job = chuck.job_of(obj)
        for op in getattr(getattr(job, "Operations", None), "Group", []):
            self._later(op)


_observer = []


def install_observer():
    if not _observer:
        _observer.append(Observer())
        App.addDocumentObserver(_observer[0])
    return _observer[0]
