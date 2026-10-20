# Knurling & Wrap — FreeCAD start-up: the Knurl and Wrap commands on a Part Design toolbar.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

try:
    import knurlwrap.gui
    knurlwrap.gui.install()
except Exception as e:  # never break FreeCAD start-up
    import FreeCAD
    FreeCAD.Console.PrintError("Knurling & Wrap could not start: %s\n" % e)
