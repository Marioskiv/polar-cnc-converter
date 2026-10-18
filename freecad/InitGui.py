# Polar CNC — FreeCAD start-up (GUI). The post-processor itself is found by FreeCAD through
# package.xml; this only adds the Polar CNC commands to the CAM workbench.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

try:
    import polarcnc.gui
    polarcnc.gui.install()
except Exception as e:  # never break FreeCAD start-up
    import FreeCAD
    FreeCAD.Console.PrintError("Polar CNC could not start: %s\n" % e)
