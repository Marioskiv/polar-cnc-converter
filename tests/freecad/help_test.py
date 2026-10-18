# Polar CNC — the help in a real FreeCAD: popups on the toolbar buttons (text, steps,
# animation), the "?" buttons of the task-panel fields, the error cards, Greek and English.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import os
import re
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, REPO, check, fails, finish, log, pump  # noqa: E402

GREEK = re.compile("[Ͱ-Ͽ]")


def grab(widget, name):
    try:
        widget.grab().save(os.path.join(OUT, name))
    except Exception as e:
        log.write("could not save %s: %s\n" % (name, e))


def contents():
    """help.json itself: every command, field and error in both languages, the animations there."""
    with open(os.path.join(REPO, "freecad", "help", "help.json"), encoding="utf-8") as f:
        d = json.load(f)
    for name, entry in d["commands"].items():
        for lang in ("el", "en"):
            text = entry.get(lang) or {}
            check(text.get("t") and text.get("d"), "%s has a %s title and text" % (name, lang))
        check(GREEK.search(entry["el"]["d"]) and not GREEK.search(entry["en"]["d"]),
              "%s: the Greek text is Greek, the English is not" % name)
        if entry.get("i"):
            for lang in ("el", "en"):
                path = os.path.join(REPO, "freecad", "help", "img", lang, entry["i"])
                check(os.path.isfile(path), "%s animation %s/%s exists" % (name, lang, entry["i"]))
    for key, entry in d["fields"].items():
        check(entry.get("el", {}).get("d") and entry.get("en", {}).get("d"), "field %s in both" % key)
    for err in d["errors"]:
        re.compile(err["re"])
        check(all(err.get(l, {}).get(k) for l in ("el", "en") for k in ("t", "why", "do")),
              "error card '%s' complete in both languages" % err["re"])
    # every field the panels ask for has help
    for gui, op in (("polarface_gui.py", "PolarFace"), ("polarwrap_gui.py", "PolarWrap")):
        with open(os.path.join(REPO, "freecad", "polarcnc", gui), encoding="utf-8") as f:
            keys = re.findall(r'add_row\(lay, "([^"]+)"', f.read())
        check(keys and all(k in d["fields"] for k in keys), "%s: help for every field %s" % (gui, keys))


def run():
    contents()
    from polarcnc import help
    Gui.activateWorkbench("CAMWorkbench")
    pump(800)
    count = help.install_toolbar()
    check(count == 7, "hover help on the 7 Polar CNC toolbar buttons (%d)" % count)
    check(help.install_toolbar() == count, "installing again changes nothing")

    bars = [b for b in Gui.getMainWindow().findChildren(QtGui.QToolBar) if b.windowTitle() == "Polar CNC"]
    buttons = {}
    for bar in bars:
        bar.show()
        for action in bar.actions():
            w = bar.widgetForAction(action)
            if w is not None and w.property("polarHelp"):
                buttons[action.objectName()] = w
    pump(200)

    for lang in ("el", "en"):
        help.set_setting(lang)
        check(help.language() == lang, "language setting %s" % lang)
        button = buttons.get("PolarCNC_Chuck")
        if button is None:
            check(False, "the Chuck button found")
            break
        QtGui.QApplication.sendEvent(button, QtCore.QEvent(QtCore.QEvent.Enter))
        # the popup checks underMouse(): put the pointer on the button
        QtGui.QCursor.setPos(button.mapToGlobal(button.rect().center()))
        pump(help.DELAY_MS + 600)
        pop = help._POPUP
        check(pop is not None and pop.isVisible(), "%s: hovering Chuck shows the popup" % lang)
        if pop is not None:
            title = pop.findChild(QtGui.QLabel, "title").text()
            check(title == help.command("PolarCNC_Chuck")["t"], "%s: popup title %r" % (lang, title))
            check(bool(GREEK.search(title)) == (lang == "el"), "%s: popup in the right language" % lang)
            pic = pop.findChild(QtGui.QLabel, "animation")
            check(pic is not None and pop.movie is not None and pop.movie.state() == QtGui.QMovie.Running,
                  "%s: the animation plays in the popup" % lang)
            check(len(pop.findChildren(QtGui.QLabel, "badge")) == 3, "%s: three numbered steps" % lang)
            scr = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            check(scr.contains(pop.geometry()), "%s: popup inside the screen %s" % (lang, pop.geometry()))
            pump(400)
            grab(pop, "popup_chuck_%s.png" % lang)
        ev = QtGui.QHelpEvent(QtCore.QEvent.ToolTip, QtCore.QPoint(2, 2), button.mapToGlobal(QtCore.QPoint(2, 2)))
        check(help._FILTER.eventFilter(button, ev) is True, "%s: the plain tooltip is replaced" % lang)
        QtGui.QApplication.sendEvent(button, QtCore.QEvent(QtCore.QEvent.Leave))
        pump(100)
        check(help._POPUP is None, "%s: leaving the button hides the popup" % lang)

    # every toolbar command builds its popup in both languages
    for lang in ("el", "en"):
        help.set_setting(lang)
        for name in buttons:
            frame = help.build_popup(name)
            ok = frame.findChild(QtGui.QLabel, "title").text() == help.command(name)["t"]
            if help.animation(name):
                ok = ok and frame.movie is not None and frame.movie.isValid()
            check(ok, "%s popup %s" % (lang, name))
            frame.deleteLater()

    # off: the plain tooltip again, no popup
    help.set_setting("off")
    button = buttons["PolarCNC_PolarFace"]
    QtGui.QApplication.sendEvent(button, QtCore.QEvent(QtCore.QEvent.Enter))
    pump(help.DELAY_MS + 300)
    check(help._POPUP is None, "off: no popup")
    ev = QtGui.QHelpEvent(QtCore.QEvent.ToolTip, QtCore.QPoint(2, 2), button.mapToGlobal(QtCore.QPoint(2, 2)))
    check(help._FILTER.eventFilter(button, ev) is False, "off: the plain tooltip stays")
    QtGui.QApplication.sendEvent(button, QtCore.QEvent(QtCore.QEvent.Leave))

    # the "?" button of a field
    help.set_setting("el")
    box = QtGui.QWidget()
    form = QtGui.QFormLayout(box)
    spin = QtGui.QSpinBox()
    help.add_row(form, "PolarWrap:FinishStyle", "Finishing", spin)
    box.show()
    pump(200)
    q = box.findChild(QtGui.QToolButton, "polarFieldHelp")
    check(q is not None, "the field has a ? button")
    lab = form.labelForField(form.itemAt(0, QtGui.QFormLayout.FieldRole).layout())
    check(lab is not None and lab.text() == "Φινίρισμα", "field label in Greek: %r" % (lab.text() if lab else None))
    if q is not None:
        q.click()
        pump(300)
        check(help._POPUP is not None and help._POPUP.isVisible() and
              "Έλικα" in help._POPUP.findChild(QtGui.QLabel, "text").text(), "? shows the field help")
        grab(help._POPUP, "field_help_el.png")
        q.click()
        pump(100)
        check(help._POPUP is None, "? again hides it")
    box.deleteLater()

    # error cards
    cases = [("the program runs into the chuck.\nA rapid move runs into the jaw 2 at X12 Z3", "τσοκ"),
             ("X Axis Max is not set: enter the largest X your machine can reach", "διαδρομή"),
             ("the program uses tool length offsets (G43), and in Wrap the router lies sideways", "μήκος"),
             ("something nobody expected", "σταμάτησε")]
    for msg, word in cases:
        card = help.explain(msg)
        check(word in card["t"].lower(), "card for %r: %r" % (msg[:30], card["t"]))
    help.set_setting("el")
    dlg = help.build_card(cases[0][0], "Polar CNC — Post Process", Gui.getMainWindow())
    dlg.show()
    pump(300)
    check("τσοκ" in dlg.findChild(QtGui.QLabel, "head").text(), "the card heading is Greek")
    check(dlg.findChild(QtGui.QPlainTextEdit, "message").toPlainText() == cases[0][0], "the card keeps the message")
    grab(dlg, "card_el.png")
    dlg.close()
    help.set_setting("en")
    dlg = help.build_card(cases[1][0], "Polar CNC — Post Process", Gui.getMainWindow())
    dlg.show()
    pump(300)
    check("travel" in dlg.findChild(QtGui.QLabel, "head").text(), "the English card")
    grab(dlg, "card_en.png")
    dlg.close()

    # error_card falls back to a message box when the card cannot be made
    seen = []
    keep_build, keep_box = help.build_card, QtGui.QMessageBox.warning
    help.build_card = lambda *a, **k: 1 / 0
    QtGui.QMessageBox.warning = staticmethod(lambda *a, **k: seen.append(a[2]))
    help.error_card("X Axis Max is not set")
    help.build_card, QtGui.QMessageBox.warning = keep_build, keep_box
    check(seen == ["X Axis Max is not set"], "a broken card falls back to a message box")

    # the machine settings dialog
    import Part
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    from polarcnc import chuck, dialogs, machine
    doc = App.newDocument("HelpDialogs")
    part = doc.addObject("Part::Feature", "Part")
    part.Shape = Part.makeCylinder(20, 10)
    doc.recompute()
    job = PathJob.Create("Job", [part], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    doc.recompute()
    machine.add_settings(job)
    help.set_setting("el")
    dlg = dialogs.SettingsDialog(job, Gui.getMainWindow())
    dlg.show()
    pump(200)
    check(len(dlg.findChildren(QtGui.QToolButton, "polarFieldHelp")) == 6, "settings: a ? on every field")
    check(not dlg.diameter.isEnabled() and not dlg.past.isEnabled(), "settings: Wrap and both-sides fields off for Face")
    dlg.accept()
    check(dlg.isVisible() and "X Max" in dlg.findChild(QtGui.QLabel, "problem").text(),
          "settings: OK without X Max is refused, in Greek: %r" % dlg.findChild(QtGui.QLabel, "problem").text())
    dlg.xmax.setValue(125)
    dlg.layout_box.setCurrentIndex(1)
    pump(50)
    check(dlg.diameter.isEnabled() and dlg.in_x.isEnabled(), "settings: Wrap fields on for Wrap")
    dlg.accept()
    check(dlg.isVisible() and "διάμετρο" in dlg.findChild(QtGui.QLabel, "problem").text(), "settings: Wrap without a diameter refused")
    dlg.diameter.setValue(40)
    dlg.side.setCurrentIndex(1)
    dlg.past.setValue(3)
    grab(dlg, "settings_el.png")
    dlg.accept()
    pump(50)
    check(not dlg.isVisible() and job.PolarXMax.Value == 125 and machine.is_wrap(job)
          and job.PolarWrapDiameter.Value == 40 and job.PolarCuttingSide == machine.BOTH_SIDES
          and job.PolarPastCentre.Value == 3, "settings: OK writes them into the Job")

    # the chuck chooser: type, then size
    dlg = dialogs.ChuckDialog(chuck.PRESETS, chuck.CUSTOM, "4-jaw SAN OU K72-125 independent (Ø125)", Gui.getMainWindow())
    dlg.show()
    pump(200)
    check(dlg.type_box.currentText() == "4άρι (ανεξάρτητες σιαγόνες)" and "21.7" in dlg.findChild(QtGui.QLabel, "sizes").text(),
          "chuck: K72 shown as a 4-jaw independent, its sizes under it: %r" % dlg.findChild(QtGui.QLabel, "sizes").text())
    grab(dlg, "chuck_chooser_el.png")
    dlg.type_box.setCurrentIndex(0)
    pump(50)
    names = [dlg.size_box.itemText(i) for i in range(dlg.size_box.count())]
    check(names and all(chuck.PRESETS[n][0] == dlg.types[0] for n in names), "chuck: sizes of the chosen type only")
    dlg.type_box.setCurrentIndex(dlg.type_box.count() - 1)
    pump(50)
    check(dlg.textValue() == chuck.CUSTOM and not dlg.size_box.isEnabled(), "chuck: Custom")
    dlg.setTextValue("Faceplate Ø250")
    check(dlg.textValue() == "Faceplate Ø250" and "250" in dlg.findChild(QtGui.QLabel, "sizes").text(), "chuck: faceplate")
    dlg.close()
    App.closeDocument(doc.Name)

    # the language command
    check(Gui.Command.get("PolarCNC_Help") is not None, "the help language command exists")
    help.set_setting("auto")


try:
    run()
except Exception:
    fails.append("exception")
    log.write(traceback.format_exc())
finish()
