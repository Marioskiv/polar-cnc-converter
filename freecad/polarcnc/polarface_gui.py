# Polar CNC — the tree icon of a Polar Face operation from a file made before 2.20.0 (Polar Face
# was removed; see polarface.py).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT


class ViewProvider:
    def __init__(self, vobj=None, *args, **kwargs):
        if vobj is not None:
            vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ":/icons/CAM_OpActive.svg"

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps

    def __setstate__(self, state):
        return None
