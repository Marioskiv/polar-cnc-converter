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
CORE_FILES = ("geometry.js", "gcode-input.js", "layout-xzc.js", "layout-xzcb.js", "layout-wrap.js",
              "converter.js",
              "polar-parser.js")


class ConverterError(Exception):
    """The converter refused the program; the message names the line, as on the web page."""


_ENGINE = []


def _engine():
    """One engine with the converter loaded, kept: loading the core files takes a moment and the
    converter keeps no state between calls (each call builds its own)."""
    if _ENGINE:
        return _ENGINE[0]
    eng = _load_engine()
    _ENGINE.append(eng)
    return eng


def _load_engine():
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


def parse(polar_text, options):
    """The polar program as the machine runs it, read back by the web simulator's own parser
    (src/core/polar-parser.js): blocks interpolated in joint space, as LinuxCNC does.
    Returns a dict of equal-length lists: r, c (deg), z, rapid (bool), dur (s), line, toolD."""
    eng = _engine()
    eng.globalObject().setProperty("SRC", QJSValue(polar_text))
    eng.globalObject().setProperty("OPT", QJSValue(json.dumps(options)))
    res = eng.evaluate(
        "(function () {"
        "  var o = PolarCNC.converter.normalizeOptions(JSON.parse(OPT));"
        "  var p = PolarCNC.parser.parsePolarGCode(SRC, o);"
        "  var out = { r: [], c: [], z: [], rapid: [], dur: [], line: [], toolD: [] };"
        "  for (var i = 0; i < p.length; i++) {"
        "    out.r.push(p[i].r); out.c.push(p[i].theta); out.z.push(p[i].z);"
        "    out.rapid.push(p[i].type === 'G0'); out.dur.push(p[i].segDurNom);"
        "    out.line.push(p[i].lineNum); out.toolD.push(p[i].toolD);"
        "  }"
        "  return JSON.stringify(out);"
        "})()")
    if res.isError():
        raise RuntimeError("Polar CNC: the simulator parser failed: %s" % res.toString())
    return json.loads(res.toString())
