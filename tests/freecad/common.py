# Polar CNC — shared pieces of the FreeCAD tests (tests/freecad/run.sh runs each test file in its
# own FreeCAD start: opening and closing many CAM task dialogs in one session crashes 26.3).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import time

import FreeCAD as App
from PySide import QtGui

OUT = os.environ["PC_OUT"]
REPO = os.environ["PC_REPO"]
os.makedirs(OUT, exist_ok=True)
# the machine settings dialog would wait for a person: the tests set the properties themselves
App.ParamGet("User parameter:BaseApp/Preferences/Mod/PolarCNC").SetBool("SettingsDialog", False)
log = open(os.path.join(OUT, "log.txt"), "w")
fails = []


def check(cond, what):
    log.write("%s %s\n" % ("ok  " if cond else "FAIL", what))
    log.flush()
    if not cond:
        fails.append(what)


def finish():
    with open(os.path.join(OUT, "result.txt"), "w") as f:
        f.write("RESULT: %s\n" % ("PASS" if not fails else "FAIL " + "; ".join(fails)))
    log.close()
    os._exit(0)


def pump(ms=50):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        QtGui.QApplication.processEvents()


def build_job(pocket_off_centre=False):
    """A disk of R50 x 10 centred on X0 Y0 (the chuck axis) with a Profile round it and a Pocket:
    the whole top face down to Z8, or (pocket_off_centre) a 25 x 25 mm pocket 6 mm deep off the
    centre."""
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    import Path.Op.Profile as Profile
    import Path.Op.PocketShape as PocketShape
    doc = App.newDocument("PolarTest")
    disk = doc.addObject("Part::Feature", "Disk")
    shape = Part.makeCylinder(50, 10)
    if pocket_off_centre:
        shape = shape.cut(Part.makeBox(25, 25, 10, App.Vector(12, -8, 4)))
    disk.Shape = shape
    doc.recompute()
    job = PathJob.Create("Job", [disk], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    doc.recompute()
    model = job.Model.Group[0]
    floor_z = 4 if pocket_off_centre else 10       # the pocket floor, or the top face
    face = [n for n, f in enumerate(model.Shape.Faces, 1) if abs(f.CenterOfMass.z - floor_z) < 1e-6][0]
    prof = Profile.Create("Profile")
    prof.Base = [(model, ())]
    pocket = PocketShape.Create("Pocket")
    pocket.Base = [(model, ("Face%d" % face,))]
    if not pocket_off_centre:
        pocket.FinalDepth = 8
    pocket.ClearingPattern = "Offset"
    doc.recompute()
    return doc, job, [prof, pocket]


def catch_messages(store):
    """Error cards and message boxes must not block the test: their messages go into `store`
    (the card's own heading is kept in catch_messages.cards)."""
    from polarcnc import help

    def card(dlg):
        store.append(dlg.findChild(QtGui.QPlainTextEdit, "message").toPlainText())
        head = dlg.findChild(QtGui.QLabel, "head")
        catch_messages.cards.append(head.text() if head is not None else "")
        dlg.deleteLater()
        return 0
    help._exec = card
    QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: store.append(a[2]))


catch_messages.cards = []
