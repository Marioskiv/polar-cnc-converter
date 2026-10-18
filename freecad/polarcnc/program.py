# Polar CNC — the program of a Job: FreeCAD's LinuxCNC milling output, then the polar output.
# Used by the polar_linuxcnc post-processor and by the simulator, so both see the same program.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import importlib.util
import os

from . import bridge, machine


def linuxcnc_post():
    """A fresh copy of FreeCAD's LinuxCNC post: it keeps its settings in module globals, so a
    copy left from an earlier run could carry e.g. --inches into this one."""
    import Path.Post.scripts as scripts
    path = os.path.join(os.path.dirname(scripts.__file__), "linuxcnc_legacy_post.py")
    spec = importlib.util.spec_from_file_location("polarcnc_linuxcnc_legacy_post", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cartesian(objectslist, argstring=""):
    """The milling program FreeCAD's LinuxCNC post writes for these objects (no editor)."""
    return linuxcnc_post().export(objectslist, "-", (argstring or "") + " --no-show-editor")


def job_objects(job):
    """Everything Post Process would send for the whole Job, in order."""
    from Path.Post.Processor import PostProcessorFactory
    proc = PostProcessorFactory.get_post_processor(job, "polar_linuxcnc")
    objs = []
    for _name, sublist in proc._buildPostList():
        objs.extend(sublist)
    return objs


def polar(job):
    """(polar G-code, converter options) for the whole Job.
    Raises ValueError (settings) or bridge.ConverterError (refused program)."""
    opts = machine.options(job)
    return bridge.convert(cartesian(job_objects(job), job.PostProcessorArgs), opts), opts
