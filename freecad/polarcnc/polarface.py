# Polar CNC — Polar Face was removed in 2.20.0: a polar Job is machined with FreeCAD's own
# operations (Face, Pocket, Profile, Drilling...), checked and warned about by Polar CNC.
# What is left here only lets files made with Polar Face open: such an operation keeps the path
# it had, is not remade, and a warning says to replace it.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import FreeCAD as App

REMOVED = ("Polar Face was removed from Polar CNC (2.20.0): this operation keeps the path it had "
           "and is not remade. Delete it and use FreeCAD's Face or Pocket instead.")
REMOVED_EL = ("Το Polar Face αφαιρέθηκε από το Polar CNC (2.20.0): αυτή η κατεργασία κρατάει τη διαδρομή "
              "που είχε και δεν ξαναϋπολογίζεται. Σβήσ' την και χρησιμοποίησε το Face ή το Pocket του "
              "FreeCAD.")


class ObjectPolarFace:
    """A Polar Face operation from a file made before 2.20.0."""

    def __init__(self, obj=None, *args, **kwargs):
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps

    def __setstate__(self, state):
        return None

    def onDocumentRestored(self, obj):
        App.Console.PrintWarning("Polar CNC (%s): %s\n" % (obj.Label, REMOVED))

    def execute(self, obj):
        pass
