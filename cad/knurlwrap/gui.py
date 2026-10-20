# Knurling & Wrap — the two commands and their toolbar in the Part Design workbench.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import FreeCAD as App

COMMANDS = ("KnurlWrap_Knurl", "KnurlWrap_Wrap")
# a toolbar of the Part Design workbench only, the way Tools -> Customize stores one
TOOLBAR = "User parameter:BaseApp/Workbench/PartDesignWorkbench/Toolbar/KnurlWrap"


def ensure_toolbar():
    grp = App.ParamGet(TOOLBAR)
    grp.SetString("Name", "Knurling & Wrap")
    if not grp.GetBool("Created", False):        # the user may hide it later: only the first time
        grp.SetBool("Active", True)
        grp.SetBool("Created", True)
    for cmd in COMMANDS:
        if not grp.GetString(cmd, ""):
            grp.SetString(cmd, "knurlwrap")


def install():
    from . import knurl, wrap
    knurl.install()
    wrap.install()
    ensure_toolbar()
    # the old names of files made while Knurl and Wrap were part of WikiTips: loaded now, because
    # FreeCAD 26.3 lets a document import, while it opens, only modules already loaded (or found
    # under its Mod folders, which a linked install is not)
    import wikitips_knurl  # noqa: F401
    import wikitips_wrap  # noqa: F401
