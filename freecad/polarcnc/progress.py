# Polar CNC — FreeCAD's progress bar while an operation makes its path, and Esc to stop it.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import FreeCAD as App


class Stopped(Exception):
    """The person pressed Esc while the path was being made."""


class Progress:
    """FreeCAD's progress bar in the status bar while a long path is made: the window keeps
    drawing, and Esc stops the work (FreeCAD raises in next(); we turn it into Stopped)."""

    def __init__(self, what):
        self.bar = None
        try:
            self.bar = App.Base.ProgressIndicator()
            self.bar.start("%s: making the path (Esc stops)" % what, 0)
        except Exception:
            self.bar = None

    def tick(self):
        if self.bar is None:
            return
        try:
            self.bar.next(True)
        except Exception:
            raise Stopped()

    def stop(self):
        if self.bar is not None:
            try:
                self.bar.stop()
            except Exception:
                pass
            self.bar = None
