# Polar CNC — what suits a polar Job, its polar defaults, and the checks and warnings.
#
# A polar Job is machined with FreeCAD's own operations (2.20.0: Marios wants to make them himself,
# with nothing done automatically). Nothing is greyed out; each operation is checked when it is made
# the way Post Process will write it (converts to X C Z, clears the chuck) and what does not suit
# polar is warned about. Lines and zigzags cross the face again and again, and at the centre the
# chuck would have to turn without limit to keep the feed (it cannot, so the cut crawls there), so
# ring-shaped patterns (Offset, Spiral) are the defaults. See freecad/README.md.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import importlib
import time

import FreeCAD as App

from . import machine

# A polar Job greys nothing out (2.20.0): every FreeCAD operation can be used, and what does not
# suit polar is only warned about (Marios: "only warnings, nothing automatic").
BLOCKED = {}

# a Wrap Job is machined with Polar Wrap only (the router is radial): every operation that cuts a
# flat face from above is greyed out there (Post Process would refuse it anyway)
WRAP_BLOCKED = {
    "CAM_Profile": "Path.Op.Gui.Profile",
    "CAM_Pocket_Shape": "Path.Op.Gui.PocketShape",
    "CAM_Pocket3D": "Path.Op.Gui.Pocket",
    "CAM_MillFacing": "Path.Op.Gui.MillFacing",
    "CAM_MillFace": "Path.Op.Gui.MillFace",
    "CAM_Helix": "Path.Op.Gui.Helix",
    "CAM_Drilling": "Path.Op.Gui.Drilling",
    "CAM_Tapping": "Path.Op.Gui.Tapping",
    "CAM_Adaptive": "Path.Op.Gui.Adaptive",
    "CAM_Engrave": "Path.Op.Gui.Engrave",
    "CAM_Vcarve": "Path.Op.Gui.Vcarve",
    "CAM_Slot": "Path.Op.Gui.Slot",
    "CAM_Deburr": "Path.Op.Gui.Deburr",
    "CAM_ThreadMilling": "Path.Op.Gui.ThreadMilling",
    "CAM_Flute": "Path.Op.Gui.Flute",
    "CAM_Surface": "Path.Op.Gui.Surface",
    "CAM_Waterline": "Path.Op.Gui.Waterline",
    "CAM_PlanarSurface": "Path.Op.Gui.PlanarSurface",
    "CAM_RotarySurface": "Path.Op.Gui.RotarySurface",
    "CAM_Probe": "Path.Op.Gui.Probe",
}

# operations that work in a polar Job but call for a word of warning: module -> (English, Greek)
WARN_OPS = {
    "Path.Op.Adaptive": (
        "Adaptive works, but its many short moves make the chuck change direction very often: "
        "big files, slower near the centre. Keep it to pockets away from the centre.",
        "Το Adaptive δουλεύει, αλλά οι πολλές μικρές κινήσεις του κάνουν το τσοκ να αλλάζει φορά "
        "συνέχεια: μεγάλα αρχεία, πιο αργό κοντά στο κέντρο. Καλύτερα σε τσέπες μακριά από το κέντρο."),
    "Path.Op.Vcarve": (
        "V-carve moves Z together with many direction changes: fine away from the centre, slow "
        "and heavy close to it.",
        "Το V-carve κινεί το Z μαζί με πολλές αλλαγές φοράς: εντάξει μακριά από το κέντρο, αργό και "
        "βαρύ κοντά του."),
    "Path.Op.Slot": (
        "Slot: a slot through the centre is ideal (only X moves); one that passes close to the "
        "centre makes the chuck race there.",
        "Slot: ένα αυλάκι που περνάει από το κέντρο είναι ιδανικό (κινείται μόνο το X)· ένα που "
        "περνάει κοντά στο κέντρο κάνει το τσοκ να γυρίζει πολύ γρήγορα εκεί."),
    "Path.Op.Deburr": (
        "Deburr follows the edge: fine away from the centre, slow close to it.",
        "Το Deburr ακολουθεί την ακμή: εντάξει μακριά από το κέντρο, αργό κοντά του."),
    "Path.Op.ThreadMilling": (
        "Thread milling: each small helix off the centre makes the chuck swing to and fro; use a "
        "low feed, holes away from the centre.",
        "Thread milling: κάθε μικρή έλικα εκτός κέντρου κάνει το τσοκ να πηγαινοέρχεται· χαμηλή "
        "πρόωση, τρύπες μακριά από το κέντρο."),
    "Path.Op.MillFacing": (
        "Face covers the bounding rectangle of the stock, not the stock itself: on round stock "
        "much of it cuts air (about 40 % of the cleared area, measured). Pattern Spiral suits polar "
        "best (rectangular loops inward); ZigZag, Bidirectional and Directional cross the face in "
        "lines. A Pocket (pattern Offset) on the top face follows the real stock.",
        "Το Face καλύπτει το ορθογώνιο γύρω από το υλικό, όχι το ίδιο το υλικό: σε στρογγυλό υλικό "
        "μεγάλο μέρος κόβει αέρα (περίπου 40 % της επιφάνειας, μετρημένο). Το μοτίβο Spiral "
        "ταιριάζει καλύτερα στο πολικό (ορθογώνιοι κύκλοι προς τα μέσα)· τα ZigZag, Bidirectional "
        "και Directional διασχίζουν τη φάτσα σε γραμμές. Ένα Pocket (μοτίβο Offset) στην πάνω "
        "επιφάνεια ακολουθεί το πραγματικό υλικό."),
    "Path.Op.MillFace": (
        "Face (the older MillFace): pattern Offset suits polar; ZigZag, Line and Grid cross the "
        "face in lines, slow near the centre.",
        "Face (το παλαιότερο MillFace): το μοτίβο Offset ταιριάζει στο πολικό· τα ZigZag, Line και "
        "Grid διασχίζουν τη φάτσα σε γραμμές, αργά κοντά στο κέντρο."),
    "Path.Op.Surface": (
        "3D Surface works through the polar conversion, but a 3D path has very many short moves: "
        "a big file, slow near the centre. Pattern Circular, centred on X0 Y0, suits polar best.",
        "Το 3D Surface μετατρέπεται σε πολικό, αλλά μια 3D διαδρομή έχει πάρα πολλές μικρές "
        "κινήσεις: μεγάλο αρχείο, αργό κοντά στο κέντρο. Το μοτίβο Circular με κέντρο X0 Y0 "
        "ταιριάζει καλύτερα στο πολικό."),
    "Path.Op.Waterline": (
        "Waterline: many short moves round the shape; slow near the centre.",
        "Waterline: πολλές μικρές κινήσεις γύρω από το σχήμα· αργό κοντά στο κέντρο."),
    "Path.Op.Probe": (
        "Probing is not converted to polar: Post Process will refuse it.",
        "Η μέτρηση (probe) δεν μετατρέπεται σε πολικό: το Post Process θα την αρνηθεί."),
}
# the same for dressups (no reachable command object, so they are only warned about)
WARN_DRESSUPS = {
    "Path.Dressup.AxisMap": (
        "AxisMap wraps Y onto a rotary axis (4th axis); it does not belong in a polar Job, which "
        "the converter turns into X/C itself.",
        "Το AxisMap τυλίγει το Y σε περιστροφικό άξονα (4ος άξονας)· δεν ανήκει σε πολικό Job, "
        "το μετατρέπει σε X/C ο converter μόνος του."),
    "Path.Dressup.DragKnife": (
        "Drag knife is for knives, not for a milling cutter on a chuck.",
        "Το Drag knife είναι για μαχαίρια, όχι για φρέζα σε τσοκ."),
    "Path.Dressup.ZCorrect": (
        "Z correction needs probing data; probing is not converted to polar.",
        "Το Z correction θέλει δεδομένα μέτρησης· η μέτρηση δεν μετατρέπεται σε πολικό."),
}

# patterns that cross the face line by line -> the ring-shaped ones to use instead (in order of
# preference: the first that this FreeCAD offers for the operation is named)
BAD_PATTERNS = {
    "ClearingPattern": {"ZigZag": ("Offset", "Spiral"), "Line": ("Offset", "Spiral"),
                        "Grid": ("Offset", "Spiral"), "ZigZagOffset": ("Offset", "Spiral"),
                        "Bidirectional": ("Spiral", "Offset"), "Directional": ("Spiral", "Offset")},
    "CutPattern": {"ZigZag": ("Circular", "Offset"), "Line": ("Circular", "Offset"),
                   "ZigZagOffset": ("Circular", "Offset")},
}
PATTERN_REASON = (
    "%s %s is not recommended for polar: it crosses the face line by line, so the chuck reverses "
    "on every pass and crawls at the centre (slower, more wear).",
    "Το %s %s δεν συνιστάται για πολικό: διασχίζει τη φάτσα γραμμή-γραμμή, οπότε το τσοκ "
    "αλλάζει φορά σε κάθε πέρασμα και σέρνεται στο κέντρο (πιο αργό, περισσότερη φθορά).")
PATTERN_USE = (" Use %s.", " Βάλε %s.")
PATTERN_NONE = (" This FreeCAD has no ring-shaped pattern for it.",
                " Αυτό το FreeCAD δεν έχει κυκλικό μοτίβο γι' αυτό.")

# SetupSheet operation defaults of a polar Job (only operations CAM has registered are used)
DEFAULTS = {
    "Pocket Shape": {"ClearingPattern": "Offset"},
    "Pocket3D": {"ClearingPattern": "Offset"},
    "MillFacing": {"ClearingPattern": "Spiral"},
}


POLAR_POST = "polar_linuxcnc"
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


def is_wrap_job(job):
    return job is not None and machine.has_settings(job) and machine.is_wrap(job)


def _wrap(name, module):
    try:
        cmd = importlib.import_module(module).Command
    except Exception:
        return False        # not in this FreeCAD (e.g. no OpenCamLib): nothing to grey out
    if name in _original:
        return True
    orig = cmd.IsActive
    _original[name] = (cmd, orig)
    in_face, in_wrap = name in BLOCKED, name in WRAP_BLOCKED

    def IsActive():
        try:
            job = current_job()
            if (in_face and is_polar(job)) or (in_wrap and is_wrap_job(job)):
                return False
        except Exception:
            pass
        return orig()

    cmd.IsActive = IsActive
    return True


def install_blocking():
    """Grey out the unsuitable operations while the current Job is polar, and every operation but
    Polar Wrap while it is a Wrap Job (everywhere: toolbars, menus, shortcuts). Returns the
    commands that were wrapped."""
    both = dict(WRAP_BLOCKED)
    both.update(BLOCKED)
    return [name for name, module in both.items() if _wrap(name, module)]


def uninstall_blocking():
    for cmd, orig in _original.values():
        cmd.IsActive = orig
    _original.clear()


# ---- defaults ------------------------------------------------------------------------------
def _refresh_choices(sheet, registered, op, prop):
    """The Job's operation defaults keep a choice list from when the entry was first made (an
    older FreeCAD, or a Job template): e.g. MillFacingClearingPattern without "Spiral", though
    the Face operation itself offers it. Bring the list up to what the operation offers now."""
    import Path.Base.SetupSheet as SetupSheet
    name = SetupSheet.OpPropertyName(op, prop)
    if not hasattr(sheet, name) or "Enumeration" not in sheet.getTypeIdOfProperty(name):
        return
    offered = list(registered[op].prototype(op).getProperty(prop).getEnumValues() or [])
    have = list(sheet.getEnumerationsOfProperty(name) or [])
    if offered and offered != have:
        current = getattr(sheet, name)
        setattr(sheet, name, offered)
        if current in offered:
            setattr(sheet, name, current)


def apply_defaults(job):
    """Polar defaults for NEW operations of this Job (the Job's own "Operation defaults")."""
    import Path.Base.SetupSheet as SetupSheet
    registered = getattr(SetupSheet, "_RegisteredOps", {})
    attrs = {op: props for op, props in DEFAULTS.items() if op in registered}
    done = []
    for op, props in attrs.items():     # one by one: one that cannot be set skips only itself
        for prop, value in props.items():
            try:
                _refresh_choices(job.SetupSheet, registered, op, prop)
                job.SetupSheet.Proxy.setFromTemplate({op: {prop: value}})
                done.append(op)
            except Exception as e:
                App.Console.PrintLog("Polar CNC: default %s %s = %s not set: %s\n" % (op, prop, value, e))
    if "Surface" in registered:     # if 3D Surface is ever used: rings round the chuck axis
        ss = job.SetupSheet
        job.SetupSheet.Proxy.setFromTemplate({"Surface": {"CutPattern": "Circular",
                                                          "PatternCenterAt": "Custom"}})
        if not hasattr(ss, "SurfacePatternCenterCustom"):
            ss.addProperty("App::PropertyVector", "SurfacePatternCenterCustom", "Op Surface")
        ss.SurfacePatternCenterCustom = App.Vector(0, 0, 0)
    return sorted(set(done))


# ---- warnings ------------------------------------------------------------------------------
def _say(pair):
    """The English or the Greek of a (en, el) pair, as the help language says."""
    try:
        from . import help
        return pair[1] if help.language() == "el" else pair[0]
    except Exception:
        return pair[0]


def _pattern_message(obj, prop, value, better):
    offered = []
    try:
        offered = obj.getEnumerationsOfProperty(prop) or []
    except Exception:
        pass
    use = next((b for b in better if b in offered), None)
    text = _say(PATTERN_REASON) % (prop, value)
    return text + (_say(PATTERN_USE) % use if use else _say(PATTERN_NONE))


def problems(obj):
    """What is not right for polar about this operation (empty if fine or not in a polar Job):
    warnings, in the help language. What would make Post Process refuse it is in check()."""
    import PathScripts.PathUtils as PathUtils
    if hasattr(obj, "PostProcessor") and hasattr(obj, "Operations"):     # the Job itself
        post = getattr(obj, "PostProcessor", "") or ""
        if machine.has_settings(obj) and post != POLAR_POST:
            return [_say(("This Job is polar, but its post-processor is '%s': Post Process would "
                          "write X Y Z G-code, not X C Z. Choose %s (or press Machining type)."
                          % (post or "none", POLAR_POST),
                          "Αυτό το Job είναι πολικό, αλλά ο post-processor του είναι «%s»: το Post "
                          "Process θα έγραφε G-code X Y Z, όχι X C Z. Διάλεξε %s (ή πάτα «Τύπος "
                          "κατεργασίας»)." % (post or "κανένας", POLAR_POST)))]
        return []
    job = PathUtils.findParentJob(obj)
    if job is not None and machine.has_settings(job) and machine.is_wrap(job):
        if hasattr(obj, "ToolController") and \
                type(getattr(obj, "Proxy", None)).__name__ != "ObjectPolarWrap":
            return [_say(("A Wrap Job is machined with Polar Wrap (the router is radial); this "
                          "operation works on a flat face and Post Process will refuse it.",
                          "Ένα Wrap Job κατεργάζεται με το Polar Wrap (ο router είναι ακτινικός)· "
                          "αυτή η κατεργασία δουλεύει σε επίπεδη φάτσα και το Post Process θα την "
                          "αρνηθεί."))]
        return []
    if not is_polar(job):
        return []
    out = []
    proxy = getattr(obj, "Proxy", None)
    mod = type(proxy).__module__
    if type(proxy).__name__ == "ObjectPolarFace":
        from . import polarface
        out.append(_say((polarface.REMOVED, polarface.REMOVED_EL)))
    if mod in WARN_OPS:
        out.append(_say(WARN_OPS[mod]))
    if mod in WARN_DRESSUPS:
        out.append(_say(WARN_DRESSUPS[mod]))
    for prop, bad in BAD_PATTERNS.items():
        val = getattr(obj, prop, None)
        if val in bad:
            out.append(_pattern_message(obj, prop, val, bad[val]))
    if hasattr(obj, "Path") and obj in getattr(getattr(job, "Operations", None), "Group", []):
        from . import chuck
        msg = chuck.head_warning(getattr(job, "PolarChuck", None), obj.Path)
        if msg:
            out.append(msg)
    if proxy is not None and mod == "Path.Op.Drilling" and getattr(obj, "Strategy", "") == "Tapping":
        out.append(_say(("Tapping is not converted to polar (the converter refuses tapping cycles).",
                         "Το σπείρωμα (tapping) δεν μετατρέπεται σε πολικό (ο converter αρνείται "
                         "τους κύκλους tapping).")))
    return out


STOP_TEXT = {
    "chuck": ("WILL CRASH: %s Post Process will not write the program until this is fixed.",
              "ΘΑ ΤΡΑΚΑΡΕΙ: %s Το Post Process δεν θα γράψει το πρόγραμμα μέχρι να διορθωθεί."),
    "not converted": ("This operation cannot be written as polar (X C Z) G-code: %s",
                      "Αυτή η κατεργασία δεν γράφεται σε πολικό (X C Z) G-code: %s"),
    "Y in output": ("The polar output still has a Y move (it must be X, C, Z only): %s",
                    "Το πολικό G-code έχει ακόμα κίνηση Y (πρέπει να είναι μόνο X, C, Z): %s"),
}
SLOWER = ("About %.0f %% slower than its programmed feed (%.1f -> %.1f min): near the centre the "
          "C axis reaches its top speed.",
          "Περίπου %.0f %% πιο αργή από την προγραμματισμένη πρόωση (%.1f -> %.1f λεπτά): κοντά "
          "στο κέντρο ο C φτάνει τη μέγιστη ταχύτητά του.")
SLOWER_LIMIT = 20.0          # % slower than programmed before it is said
BIG = ("A big path (%d commands): not checked now, so that FreeCAD stays quick; Post Process checks it "
       "(polar G-code and the chuck) when the program is written.",
       "Μεγάλη διαδρομή (%d εντολές): δεν ελέγχεται τώρα, για να μένει γρήγορο το FreeCAD· το Post "
       "Process την ελέγχει (πολικό G-code και τσοκ) όταν γράφει το πρόγραμμα.")


def check(obj):
    """(stops, notes) for an operation of a polar Job, checked alone the way Post Process will
    write it: stops (crash into the chuck, not convertible, Y left) stop Post Process; notes are
    warnings. Large paths (over LIVE_CHECK_LIMIT commands) are left to Post Process."""
    import PathScripts.PathUtils as PathUtils
    job = PathUtils.findParentJob(obj)
    if not is_polar(job) or not hasattr(obj, "Path") or not hasattr(obj, "ToolController") or \
            obj not in getattr(getattr(job, "Operations", None), "Group", []) or \
            not getattr(obj, "Active", True) or len(obj.Path.Commands) < 2:
        return [], []
    if len(obj.Path.Commands) > LIVE_CHECK_LIMIT:
        return [], [_say(BIG) % len(obj.Path.Commands)]
    from . import program
    raw_stops, raw_notes = program.check_operation(job, obj)
    stops = [_say(STOP_TEXT[kind]) % text for kind, text in raw_stops]
    notes = []
    for note in raw_notes:
        if note[0] == "slower" and note[1] > SLOWER_LIMIT:
            notes.append(_say(SLOWER) % (note[1], note[2] / 60.0, note[3] / 60.0))
    return stops, notes


class Observer:
    """Checks an operation of a polar Job when it is made or changed. Warnings (patterns, slow
    near the centre...) go to the Report view and the status bar. What would crash or cannot be
    written as polar G-code opens a card, once; Post Process then refuses the program until it is
    fixed. Nothing is changed in the operation. Checks are deferred: CAM sets temporary values
    while it creates an operation (e.g. ZigZag first, then the Job's default)."""

    WATCH = ("ClearingPattern", "CutPattern", "Strategy", "Base", "Path", "Active", "PostProcessor")

    def __init__(self):
        self._said = {}
        self._stopped = {}
        self._pending = set()

    def _later(self, obj):
        try:
            name, doc = obj.Name, obj.Document.Name
            if "Restore" in obj.State or getattr(obj.Document, "Restoring", False):
                return                       # a file being opened: nothing pops up
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
            key = (doc, name)
            msgs = problems(obj)
            stops, notes = [], []
            try:
                stops, notes = check(obj)
            except Exception as e:
                App.Console.PrintLog("Polar CNC check (%s): %s\n" % (obj.Label, e))
            msgs = msgs + notes
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
            if stops and self._stopped.get(key) != stops:
                self._stopped[key] = stops
                for m in stops:
                    App.Console.PrintError("Polar CNC (%s): %s\n" % (obj.Label, m))
                from . import help
                help.error_card("%s\n\n%s" % (obj.Label, "\n\n".join(stops)),
                                "Polar CNC — %s" % obj.Label)
            elif not stops and key in self._stopped:
                del self._stopped[key]
                App.Console.PrintMessage("Polar CNC (%s): OK now, it converts to polar G-code and "
                                         "clears the chuck.\n" % obj.Label)
        except Exception:
            pass

    def slotCreatedObject(self, obj):
        self._later(obj)

    def slotChangedObject(self, obj, prop):
        try:
            if prop in self.WATCH or prop == "Group":
                self._later(obj)
            if prop in ("PolarXMax", "PolarCuttingSide", "PolarPastCentre", "PolarProfile",
                        "PolarCMaxVelocity", "PolarLayout") and hasattr(obj, "Operations"):
                for op in getattr(obj.Operations, "Group", []):      # the Job's machine changed
                    self._later(op)
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
