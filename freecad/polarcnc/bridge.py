# Polar CNC — runs the converter (src/core/*.js) inside FreeCAD.
#
# The converter is plain JavaScript with no DOM. Qt's own JavaScript engine (QJSEngine, part of
# the Qt that ships with FreeCAD) runs it unchanged, so the web page and FreeCAD use the very same
# code: no Python port, no Node, nothing to install (FreeCAD's Python on Windows has no SSL, so
# pip packages are not an option).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import os

try:
    from PySide6.QtCore import QLoggingCategory
    from PySide6.QtQml import QJSEngine, QJSValue
except ImportError:  # Qt5 builds of FreeCAD
    from PySide2.QtCore import QLoggingCategory
    from PySide2.QtQml import QJSEngine, QJSValue

# Qt's JS engine notes every `var` used above its declaration (valid JavaScript, used on purpose
# in the converter); without this the notes fill FreeCAD's report view on every post
QLoggingCategory.setFilterRules("qt.qml.usedbeforedeclared=false")

# freecad/polarcnc/bridge.py -> the repository root -> src/core
CORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "src", "core")
# the order index.html loads them in: each file adds itself to PolarCNC
CORE_FILES = ("geometry.js", "gcode-input.js", "layout-xzc.js", "layout-xzcb.js", "converter.js")


class ConverterError(Exception):
    """The converter refused the program; the message names the line, as on the web page."""


def _engine():
    eng = QJSEngine()
    # the files register themselves on `self` (browser) or `module` (Node); give them `self`
    eng.evaluate("var self = this; var module = undefined;")
    for name in CORE_FILES:
        path = os.path.join(CORE_DIR, name)
        with open(path, encoding="utf-8") as f:
            res = eng.evaluate(f.read(), path)
        if res.isError():
            raise RuntimeError("Polar CNC: %s did not load: %s" % (name, res.toString()))
    return eng


def convert(cartesian, options):
    """Cartesian G-code (str) + converter options (dict) -> polar G-code (str).

    Raises ConverterError with the converter's own message when it refuses the program."""
    eng = _engine()
    eng.globalObject().setProperty("SRC", QJSValue(cartesian))
    eng.globalObject().setProperty("OPT", QJSValue(json.dumps(options)))
    res = eng.evaluate(
        "(function () {"
        "  try { return JSON.stringify({ ok: true, out: PolarCNC.converter.convert(SRC, JSON.parse(OPT)) }); }"
        "  catch (e) { return JSON.stringify({ ok: false, err: String((e && e.message) || e) }); }"
        "})()")
    if res.isError():
        raise RuntimeError("Polar CNC: converter crashed: %s" % res.toString())
    data = json.loads(res.toString())
    if not data["ok"]:
        raise ConverterError(data["err"])
    return data["out"]


def default_options():
    eng = _engine()
    return json.loads(eng.evaluate("JSON.stringify(PolarCNC.converter.DEFAULT_OPTIONS)").toString())
