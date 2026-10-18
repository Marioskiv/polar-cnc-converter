# Polar CNC — help inside the addon: hover popups on the Polar CNC toolbar (text, steps and an
# animation), "?" buttons on the task-panel fields, and error cards (what happened, why, what
# to do) in Greek or English.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
#
# Nothing here may break FreeCAD: every path the GUI calls into is wrapped in try/except, and
# when something fails the plain FreeCAD tooltip or message box is used instead.

import json
import os
import re

import FreeCAD as App

HERE = os.path.dirname(os.path.abspath(__file__))
HELP_DIR = os.path.join(os.path.dirname(HERE), "help")
PARAM = "User parameter:BaseApp/Preferences/Mod/PolarCNC"
LANGUAGES = ("auto", "el", "en", "off")
TOOLBAR = "Polar CNC"
DELAY_MS = 500           # hover time before the popup shows
TEXT_W = 480             # width of the popup's animation and text

_DATA = None
_FILTER = None
_POPUP = None


def data():
    global _DATA
    if _DATA is None:
        with open(os.path.join(HELP_DIR, "help.json"), encoding="utf-8") as f:
            _DATA = json.load(f)
    return _DATA


def setting():
    value = App.ParamGet(PARAM).GetString("HelpLanguage", "auto")
    return value if value in LANGUAGES else "auto"


def set_setting(value):
    App.ParamGet(PARAM).SetString("HelpLanguage", value if value in LANGUAGES else "auto")


def language():
    """'el' or 'en' for the text. 'off' only switches the popups off; the language is then
    chosen as for 'auto' (the error cards stay)."""
    value = setting()
    if value in ("el", "en"):
        return value
    lang = App.ParamGet("User parameter:BaseApp/Preferences/General").GetString("Language", "")
    if lang.lower().startswith("greek") or lang.lower().startswith("el"):
        return "el"
    if not lang:       # FreeCAD follows the system language until one is chosen
        try:
            from PySide import QtCore
            if QtCore.QLocale.system().name().lower().startswith("el"):
                return "el"
        except Exception:
            pass
    return "en"


def popups_on():
    return setting() != "off"


def _pick(entry):
    """The entry's text in the current language (English when the Greek is missing)."""
    if not entry:
        return {}
    return entry.get(language()) or entry.get("en") or {}


def command(name):
    return _pick(data()["commands"].get(name))


def field(key):
    return _pick(data()["fields"].get(key))


def label(key, default):
    return field(key).get("t") or default


def note(name, default):
    return (data().get("notes", {}).get(name) or {}).get(language()) or default


def animation(name):
    """Path of a command's animation, in the help language if there is one, else any."""
    file = (data()["commands"].get(name) or {}).get("i")
    if not file:
        return None
    for lang in (language(), "en", "el"):
        path = os.path.join(HELP_DIR, "img", lang, file)
        if os.path.isfile(path):
            return path
    return None


def explain(message):
    """The error card for a message: dict(t, why, do), from the first pattern that matches."""
    for err in data()["errors"]:
        if re.search(err["re"], message, re.IGNORECASE):
            return _pick(err)
    return _pick(data()["generic_error"])


# ---------------------------------------------------------------- widgets

_CSS = """
QFrame#PolarHelp { background: #fbfbf8; border: 1px solid #9aa3ad; border-radius: 6px; }
QLabel { color: #1f2933; background: transparent; }
QLabel#title { font-size: 14px; font-weight: bold; color: #102a43; }
QLabel#warn { color: #8a4b00; background: #fff4d6; border-radius: 4px; padding: 4px; }
QLabel#badge { background: #f0a020; color: #1f2933; border-radius: 9px; font-weight: bold;
               min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; }
"""


def _qt():
    from PySide import QtCore, QtGui
    return QtCore, QtGui


def _step_rows(QtGui, lay, steps):
    for n, text in enumerate(steps, 1):
        row = QtGui.QHBoxLayout()
        badge = QtGui.QLabel(str(n))
        badge.setObjectName("badge")
        badge.setAlignment(_qt()[0].Qt.AlignCenter)
        row.addWidget(badge, 0, _qt()[0].Qt.AlignTop)
        lab = QtGui.QLabel(text)
        lab.setWordWrap(True)
        lab.setFixedWidth(TEXT_W - 28)    # a fixed width gives wrapped text its true height
        row.addWidget(lab, 1)
        lay.addLayout(row)


def build_popup(name=None, entry=None, parent=None):
    """The popup frame for a toolbar command (name) or a field (entry): title, animation, text,
    numbered steps (the same numbers as the badges in the animation) and a warning."""
    QtCore, QtGui = _qt()
    entry = entry if entry is not None else command(name)
    frame = QtGui.QFrame(parent, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint)
    frame.setObjectName("PolarHelp")
    frame.setStyleSheet(_CSS)
    frame.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
    lay = QtGui.QVBoxLayout(frame)
    lay.setContentsMargins(12, 10, 12, 12)
    title = QtGui.QLabel(entry.get("t", name or ""))
    title.setObjectName("title")
    lay.addWidget(title)
    path = animation(name) if name else None
    frame.movie = None
    if path:
        movie = QtGui.QMovie(path)
        if movie.isValid():
            size = QtGui.QImageReader(path).size()
            if size.isValid() and size.width() > TEXT_W:   # recorded larger, shown TEXT_W wide
                size = size * (float(TEXT_W) / size.width())
                movie.setScaledSize(size)
            pic = QtGui.QLabel()
            if size.isValid():
                pic.setFixedSize(size)       # its room before the first frame is read
            pic.setObjectName("animation")
            pic.setMovie(movie)
            lay.addWidget(pic)
            frame.movie = movie
    text = QtGui.QLabel(entry.get("d", ""))
    text.setWordWrap(True)
    text.setFixedWidth(TEXT_W)
    text.setObjectName("text")
    lay.addWidget(text)
    if entry.get("steps"):
        _step_rows(QtGui, lay, entry["steps"])
    if entry.get("w"):
        warn = QtGui.QLabel("⚠ " + entry["w"])
        warn.setObjectName("warn")
        warn.setWordWrap(True)
        warn.setFixedWidth(TEXT_W)
        lay.addWidget(warn)
    frame.setFixedWidth(TEXT_W + 24)
    return frame


def hide_popup():
    global _POPUP
    if _POPUP is not None:
        try:
            if _POPUP.movie is not None:
                _POPUP.movie.stop()
            _POPUP.hide()
            _POPUP.deleteLater()
        except Exception:
            pass
        _POPUP = None


def show_popup(widget, name=None, entry=None):
    """Show the popup next to a widget, inside the screen. Returns the frame."""
    global _POPUP
    QtCore, QtGui = _qt()
    hide_popup()
    frame = build_popup(name, entry)
    frame.adjustSize()
    pos = widget.mapToGlobal(QtCore.QPoint(0, widget.height() + 4))
    try:
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(pos.x(), area.left()), area.right() - frame.width())
        y = pos.y()
        if y + frame.height() > area.bottom():
            y = max(area.top(), widget.mapToGlobal(QtCore.QPoint(0, 0)).y() - frame.height() - 4)
        pos = QtCore.QPoint(x, y)
    except Exception:
        pass
    frame.move(pos)
    frame.show()
    if frame.movie is not None:
        frame.movie.start()
    _POPUP = frame
    return frame


def _toolbar_filter():
    """One event filter for the Polar CNC toolbar buttons: hover shows our popup instead of the
    plain tooltip, leaving or clicking hides it."""
    QtCore, QtGui = _qt()

    class ButtonHelp(QtCore.QObject):
        def __init__(self):
            super().__init__()
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._show)
            self.target = None

        def _show(self):
            try:
                button = self.target
                if button is not None and button.underMouse() and popups_on():
                    show_popup(button, button.property("polarHelp"))
            except Exception as e:
                App.Console.PrintLog("Polar CNC help: %s\n" % e)

        def eventFilter(self, obj, event):
            try:
                kind = event.type()
                if kind == QtCore.QEvent.Enter:
                    self.target = obj
                    self.timer.start(DELAY_MS)
                elif kind in (QtCore.QEvent.Leave, QtCore.QEvent.MouseButtonPress,
                              QtCore.QEvent.Hide):
                    self.timer.stop()
                    hide_popup()
                elif kind == QtCore.QEvent.ToolTip and popups_on():
                    return True           # ours instead of the one-line tooltip
            except Exception:
                pass
            return False

    return ButtonHelp()


def install_toolbar():
    """Put the hover help on the Polar CNC toolbar buttons. The toolbar is rebuilt when the
    workbench changes, so this is called on every CAM activation; buttons already done are
    skipped. Returns the number of buttons with help."""
    global _FILTER
    try:
        import FreeCADGui as Gui
        QtCore, QtGui = _qt()
        if _FILTER is None:
            _FILTER = _toolbar_filter()
        names = data()["commands"]
        count = 0
        for bar in Gui.getMainWindow().findChildren(QtGui.QToolBar):
            if bar.windowTitle() != TOOLBAR and bar.objectName() != TOOLBAR:
                continue
            for action in bar.actions():
                name = action.objectName()
                if name not in names:
                    continue
                button = bar.widgetForAction(action)
                if button is None:
                    continue
                if button.property("polarHelp") != name:
                    button.setProperty("polarHelp", name)
                    button.installEventFilter(_FILTER)
                count += 1
        return count
    except Exception as e:
        App.Console.PrintLog("Polar CNC help: toolbar: %s\n" % e)
        return 0


def help_button(key):
    """A small '?' button for a task-panel field; click shows the field's help next to it."""
    QtCore, QtGui = _qt()
    button = QtGui.QToolButton()
    button.setText("?")
    button.setObjectName("polarFieldHelp")
    button.setProperty("polarHelp", key)
    button.setAutoRaise(True)
    button.setFocusPolicy(QtCore.Qt.NoFocus)
    entry = field(key)
    button.setToolTip(entry.get("d", ""))

    def clicked():
        try:
            if _POPUP is not None and _POPUP.isVisible():
                hide_popup()
            else:
                show_popup(button, entry=field(key))
        except Exception as e:
            App.Console.PrintLog("Polar CNC help: %s\n" % e)
    button.clicked.connect(clicked)
    return button


def add_row(form, key, default_label, widget):
    """A QFormLayout row: label in the help language, the widget, and its '?' button."""
    QtCore, QtGui = _qt()
    try:
        row = QtGui.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(widget, 1)
        row.addWidget(help_button(key))
        form.addRow(label(key, default_label), row)
    except Exception:
        form.addRow(default_label, widget)


# ---------------------------------------------------------------- error cards

def card_text(message):
    """The card as plain text (the Report view and the tests)."""
    card = explain(message)
    names = (data()["labels"].get(language()) or data()["labels"]["en"])
    return "%s\n%s: %s\n%s: %s\n%s: %s" % (card.get("t", ""), names["why"], card.get("why", ""),
                                          names["do"], card.get("do", ""), names["msg"], message)


def build_card(message, title="Polar CNC", parent=None):
    """The error card: what happened (big), why, what to do, and the original message."""
    QtCore, QtGui = _qt()
    card = explain(message)
    names = (data()["labels"].get(language()) or data()["labels"]["en"])
    dlg = QtGui.QDialog(parent)
    dlg.setObjectName("PolarErrorCard")
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(
        "QDialog#PolarErrorCard { background: #fbfbf8; }"
        "QLabel#head { font-size: 15px; font-weight: bold; color: #9b1c1c; }"
        "QLabel#name { font-weight: bold; color: #102a43; }"
        "QPlainTextEdit { background: #f1f3f5; color: #1f2933; font-family: monospace; }")
    lay = QtGui.QVBoxLayout(dlg)
    head = QtGui.QLabel("✖  " + card.get("t", ""))
    head.setObjectName("head")
    head.setWordWrap(True)
    lay.addWidget(head)
    for key in ("why", "do"):
        name = QtGui.QLabel(names[key])
        name.setObjectName("name")
        lay.addWidget(name)
        text = QtGui.QLabel(card.get(key, ""))
        text.setObjectName(key)
        text.setWordWrap(True)
        lay.addWidget(text)
    name = QtGui.QLabel(names["msg"])
    name.setObjectName("name")
    lay.addWidget(name)
    raw = QtGui.QPlainTextEdit(message)
    raw.setObjectName("message")
    raw.setReadOnly(True)
    raw.setMaximumHeight(140)
    lay.addWidget(raw)
    buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok)
    copy = buttons.addButton("Copy", QtGui.QDialogButtonBox.ActionRole)
    copy.clicked.connect(lambda: QtGui.QApplication.clipboard().setText(card_text(message)))
    buttons.accepted.connect(dlg.accept)
    lay.addWidget(buttons)
    dlg.setMinimumWidth(520)
    return dlg


def _exec(dlg):
    """Shows the card modally (the tests replace this to look at the card instead)."""
    return dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()


def error_card(message, title="Polar CNC"):
    """Show an error card; falls back to a plain message box if the card cannot be built."""
    App.Console.PrintLog("Polar CNC card: %s\n" % card_text(message).replace("\n", " | "))
    try:
        import FreeCADGui as Gui
        return _exec(build_card(message, title, Gui.getMainWindow()))
    except Exception as e:
        App.Console.PrintLog("Polar CNC help: card: %s\n" % e)
        from PySide import QtGui
        return QtGui.QMessageBox.warning(None, title, message)


# ---------------------------------------------------------------- language command

class LanguageCommand:
    """Choose the language of the help popups and the error cards (or switch the popups off)."""

    CHOICES = (("auto", "Automatic (Greek if FreeCAD is in Greek)", "Αυτόματα (ελληνικά αν το FreeCAD είναι στα ελληνικά)"),
               ("el", "Ελληνικά", "Ελληνικά"),
               ("en", "English", "English"),
               ("off", "No popups (plain tooltips)", "Χωρίς παράθυρα βοήθειας (απλά tooltips)"))

    def GetResources(self):
        return {"Pixmap": os.path.join(os.path.dirname(HERE), "Resources", "PolarHelp.svg"),
                "MenuText": "Polar CNC help language",
                "ToolTip": "The language of the Polar CNC help popups and error cards: "
                           "Greek, English, automatic, or no popups."}

    def IsActive(self):
        return True

    def Activated(self):
        import FreeCADGui as Gui
        from PySide import QtGui
        greek = language() == "el"
        items = [c[2] if greek else c[1] for c in self.CHOICES]
        now = [c[0] for c in self.CHOICES].index(setting())
        text, ok = QtGui.QInputDialog.getItem(
            Gui.getMainWindow(), "Polar CNC",
            "Γλώσσα βοήθειας:" if greek else "Help language:", items, now, False)
        if ok:
            set_setting(self.CHOICES[items.index(text)][0])
            App.Console.PrintMessage("Polar CNC help: %s\n" % setting())
