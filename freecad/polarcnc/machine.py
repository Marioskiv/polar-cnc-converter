# Polar CNC — the machine settings of a CAM Job.
#
# The same two settings the web page asks for under "Machine" (cutting side, X Axis Max) are
# properties of the Job, so they are saved with the document. Everything else (rotary letter,
# directions, X as diameter, chord tolerance, centre mode) comes from an optional profile file,
# the same .polar-profile.json the web page saves and loads.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json

GROUP = "Polar CNC"
ONE_SIDE = "One side of the centre"
BOTH_SIDES = "Both sides"
FACE = "Face (router parallel to Z)"
WRAP = "Wrap (router radial, outside of a cylinder)"

# name, type, tooltip
PROPERTIES = (
    ("PolarCuttingSide", "App::PropertyEnumeration",
     "One side: X never goes below 0, a cut through the centre turns the chuck instead. "
     "Both sides: the cutter may cross the centre (only on cuts that pass exactly through it)."),
    ("PolarPastCentre", "App::PropertyLength",
     "Both sides only: how far past the centre the cutter may go (your negative X travel)."),
    ("PolarXMax", "App::PropertyLength",
     "Largest X (radius) your machine can reach: its X soft limit. Required."),
    ("PolarLayout", "App::PropertyEnumeration",
     "Face: the router looks at the face of the part (parallel to Z). Wrap: the router is turned to "
     "look at the outside of the part (radial); the part is drawn as it is, its axis on Z through "
     "X0 Y0, and the Polar Wrap operation machines it."),
    ("PolarWrapDiameter", "App::PropertyLength",
     "Wrap only: the diameter of the stock (the bar in the chuck). Required."),
    ("PolarWrapToolLengthInX", "App::PropertyBool",
     "Wrap only: tick when the tool lengths are in the X column of the LinuxCNC tool table (the "
     "router lies sideways, so its length runs along X). Until then a program with G43 is refused."),
    ("PolarProfile", "App::PropertyFile",
     "Optional machine profile (.polar-profile.json, saved from the web page): rotary letter, "
     "directions, X as diameter, chord tolerance, centre mode."),
)


def has_settings(job):
    return hasattr(job, "PolarXMax")


def add_settings(job):
    """Add the Polar CNC properties to a Job (no values are guessed: X Max stays 0 = not set)."""
    for name, typ, tip in PROPERTIES:
        if not hasattr(job, name):
            job.addProperty(typ, name, GROUP, tip)
    side = job.PolarCuttingSide if job.PolarCuttingSide in (ONE_SIDE, BOTH_SIDES) else ONE_SIDE
    job.PolarCuttingSide = [ONE_SIDE, BOTH_SIDES]
    job.PolarCuttingSide = side
    layout = getattr(job, "PolarLayout", "") or FACE
    job.PolarLayout = [FACE, WRAP]
    job.PolarLayout = layout if layout in (FACE, WRAP) else FACE
    job.PolarProfile = job.PolarProfile or ""


def is_wrap(job):
    return getattr(job, "PolarLayout", FACE) == WRAP


def wrap_radius(job):
    d = getattr(job, "PolarWrapDiameter", None)
    return d.Value / 2 if d is not None and d.Value > 0 else 0.0


def options(job):
    """Converter options for this Job. Raises ValueError (in plain words) if something is missing."""
    if not has_settings(job):
        raise ValueError("This Job has no Polar CNC machine settings. Select the Job and use "
                         "Polar CNC -> Machine settings first.")
    opts = {}
    if job.PolarProfile:
        with open(job.PolarProfile, encoding="utf-8") as f:
            prof = json.load(f)
        if prof.get("format") != "polar-cnc-profile":
            raise ValueError("%s is not a Polar CNC profile." % job.PolarProfile)
        opts.update(prof.get("options") or {})
    # the two machine settings always come from the Job (a profile may carry old ones)
    if job.PolarXMax.Value <= 0:
        raise ValueError("X Axis Max is not set: enter the largest X your machine can reach "
                         "(Job -> Polar CNC -> Polar X Max).")
    opts["xMax"] = job.PolarXMax.Value
    opts["xMin"] = 0 if job.PolarCuttingSide == ONE_SIDE else -job.PolarPastCentre.Value
    if is_wrap(job):
        d = getattr(job, "PolarWrapDiameter", None)
        if d is None or d.Value <= 0:
            raise ValueError("Wrap diameter is not set: enter the diameter of the stock "
                             "(Job -> Polar CNC -> Polar Wrap Diameter).")
        opts["layout"] = "wrap"
        opts["wrapRadius"] = d.Value / 2
    else:
        opts["layout"] = opts.get("layout") if opts.get("layout") in ("xzc", "xzcb") else "xzc"
    return opts
