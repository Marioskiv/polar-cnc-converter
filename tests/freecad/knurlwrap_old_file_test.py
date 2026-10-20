# Knurling & Wrap — an old file still opens (run by tests/freecad/run.sh).
#
# tests/fixtures/knurlwrap_wikitips_0_2.FCStd was made with WikiTips 0.4.1 (2026-10-20), when Knurl and
# Wrap were part of it: a Knurl in a Body, a Wrap after it and a straight Knurl on a Part cylinder. With
# this repository installed and NO WikiTips, the file must open with working objects (proxies and
# icons), recompute to the same solids, and be saved under the new module names.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import os
import shutil
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, REPO, check, fails, finish, log, pump  # noqa: E402

# volumes when the file was made (WikiTips 0.4.1)
MADE = {"Knurl": 9307.911, "Wrap": 9292.711, "Knurl001": 2149.837}


def go():
    try:
        check(not any(m == "wikitips" or m.startswith("wikitips_errors") for m in sys.modules),
              "WikiTips is not loaded in this FreeCAD")
        from knurlwrap import knurl, wrap
        src = os.path.join(REPO, "tests", "fixtures", "knurlwrap_wikitips_0_2.FCStd")
        path = os.path.join(OUT, "old.FCStd")
        shutil.copy(src, path)
        doc = App.openDocument(path)
        pump(800)
        for name, cls, vp in (("Knurl", knurl.Knurl, knurl.ViewProviderKnurl),
                              ("Wrap", wrap.Wrap, wrap.ViewProviderWrap),
                              ("Knurl001", knurl.Knurl, knurl.ViewProviderKnurl)):
            o = doc.getObject(name)
            check(o is not None and isinstance(o.Proxy, cls) and isinstance(o.ViewObject.Proxy, vp),
                  "%s opens with its object and view (%s)" % (name, type(getattr(o, "Proxy", None)).__name__))
        for o in doc.Objects:
            if o.Name in MADE:
                o.touch()
        doc.recompute()
        for name, vol in MADE.items():
            o = doc.getObject(name)
            check(o is not None and "Invalid" not in o.State and o.Shape.isValid() and
                  abs(o.Shape.Volume - vol) < 1e-3,
                  "%s recomputes to the same solid (%.3f, made %.3f)" % (name, o.Shape.Volume if o else 0, vol))
        doc.save()
        App.closeDocument(doc.Name)
        import zipfile
        xml = zipfile.ZipFile(path).read("Document.xml").decode("utf-8")
        check("knurlwrap.knurl" in xml and "knurlwrap.wrap" in xml and "wikitips_" not in xml,
              "saved again: stored under the new module names")
        doc = App.openDocument(path)
        pump(500)
        o = doc.getObject("Knurl")
        check(o is not None and isinstance(o.Proxy, knurl.Knurl), "and opens again")
    except Exception:
        fails.append("exception")
        log.write(traceback.format_exc())
    finish()


QtCore.QTimer.singleShot(2000, go)
