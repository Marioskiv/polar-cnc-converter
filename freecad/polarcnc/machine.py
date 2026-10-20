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
    ("PolarCMaxVelocity", "App::PropertyFloat",
     "Optional: the C axis top speed in degrees per second ([JOINT_n] MAX_VELOCITY of C in the "
     "LinuxCNC .ini). With it, each operation says how much slower the C axis makes it near the "
     "centre. 0 = not given (no estimate)."),
    ("PolarLayout", "App::PropertyEnumeration",
     "Face: the router looks at the face of the part (parallel to Z). Wrap: the router is turned to "
     "look at the outside of the part (radial); the part is drawn as it is, its axis on Z through "
     "X0 Y0, and the Polar Wrap operation machines it."),
    ("PolarWrapXMax", "App::PropertyLength",
     "Wrap only: the largest X with the router radial (the Wrap profile of the machine has its "
     "own travel and X zero). 0 = the same as Polar X Max."),
    ("PolarWrapDiameter", "App::PropertyLength",
     "Wrap only: the diameter of the stock (the bar in the chuck). Required."),
    ("PolarWrapToolLengthInX", "App::PropertyBool",
     "Wrap only: tick when the tool lengths are in the X column of the LinuxCNC tool table (the "
     "router lies sideways, so its length runs along X). Until then a program with G43 is refused."),
    ("PolarToolChangePark", "App::PropertyBool",
     "Before every tool change (M6) the cutter goes where it can be changed by hand: face: G53 G0 Z0 "
     "then G53 G0 X0; Wrap: X out to X max, then G53 G0 Z0. C stays. Only for a machine whose "
     "machine Z0 (where Home All leaves Z) is the park position AWAY from the part, as on the "
     "author's lathe conversion. Untick if machine Z0 is at the chuck end."),
    ("PolarProfile", "App::PropertyFile",
     "Optional machine profile (.polar-profile.json, saved from the web page): rotary letter, "
     "directions, X as diameter, chord tolerance, centre mode."),
)


def has_settings(job):
    return hasattr(job, "PolarXMax")


NORMAL_POST = "linuxcnc"


def remove_settings(job):
    """Back to an ordinary CAM Job: the Polar CNC properties go, the post-processor it had before
    comes back. (A chuck stays in the document; it is linked again if the Job becomes polar.)"""
    before = getattr(job, "PolarPreviousPost", "") or NORMAL_POST
    for name, _typ, _tip in PROPERTIES:
        if hasattr(job, name):
            job.removeProperty(name)
    if hasattr(job, "PolarPreviousPost"):
        job.removeProperty("PolarPreviousPost")
    choices = job.getEnumerationsOfProperty("PostProcessor")
    for post in (before, NORMAL_POST, NORMAL_POST + "_legacy", ""):    # "" = none chosen
        if post in choices:
            job.PostProcessor = post
            break


def add_settings(job):
    """Add the Polar CNC properties to a Job (no values are guessed: X Max stays 0 = not set)."""
    if not hasattr(job, "PolarPreviousPost"):       # to go back to an ordinary Job later
        job.addProperty("App::PropertyString", "PolarPreviousPost", GROUP,
                        "The post-processor the Job had before it became polar.")
        job.setEditorMode("PolarPreviousPost", 2)
        post = getattr(job, "PostProcessor", "") or ""
        job.PolarPreviousPost = post if post and not post.startswith("polar") else NORMAL_POST
    for name, typ, tip in PROPERTIES:
        if not hasattr(job, name):
            job.addProperty(typ, name, GROUP, tip)
            if name == "PolarToolChangePark":
                job.PolarToolChangePark = True
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
                         "Polar CNC -> Machining type first.")
    opts = {}
    if job.PolarProfile:
        with open(job.PolarProfile, encoding="utf-8") as f:
            prof = json.load(f)
        if prof.get("format") != "polar-cnc-profile":
            raise ValueError("%s is not a Polar CNC profile." % job.PolarProfile)
        opts.update(prof.get("options") or {})
    # the two machine settings always come from the Job (a profile may carry old ones)
    x_max = job.PolarXMax.Value
    wrap_max = getattr(job, "PolarWrapXMax", None)
    if is_wrap(job) and wrap_max is not None and wrap_max.Value > 0:
        x_max = wrap_max.Value                 # the Wrap profile of the machine
    if x_max <= 0:
        raise ValueError("X Axis Max is not set: enter the largest X your machine can reach "
                         "(button Machining type, or Job -> Polar CNC -> Polar X Max).")
    opts["xMax"] = x_max
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
