# Polar CNC — setting a part up in the chuck from one click: the face of the part (or of the
# stock) that goes into the chuck. The Job's model is turned so that this face looks down, put on
# the chuck axis and with Z0 on the stock top; then the chuck that suits the stock is chosen from
# the chucks you have, with a grip length that holds only what is below the part.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT


import FreeCAD as App
import Part

from . import chuck as ch

PARAM = "User parameter:BaseApp/Preferences/Mod/PolarCNC"
# Marios's chucks: the SAN OU K11-125 3-jaw and the K72-125 4-jaw with independent jaws
MY_CHUCKS = ("3-jaw SAN OU K11-125 (Ø125)", "4-jaw SAN OU K72-125 independent (Ø125)")
MIN_GRIP = 3.0          # mm: less than this below the part cannot be held


def my_chucks():
    """The chucks this person has (preference MyChucks, one preset name per line)."""
    text = App.ParamGet(PARAM).GetString("MyChucks", "")
    names = [n.strip() for n in text.splitlines() if n.strip() in ch.PRESETS and ch.PRESETS[n.strip()]]
    return names or list(MY_CHUCKS)


def set_my_chucks(names):
    App.ParamGet(PARAM).SetString("MyChucks", "\n".join(names))


def _is_stock(job, obj):
    return getattr(job, "Stock", None) is not None and obj == job.Stock


def model_objects(job):
    return list(getattr(getattr(job, "Model", None), "Group", []) or [])


def pick_owner(job, obj):
    """The Job object a picked face belongs to: the stock, a model clone, or the clone of the
    original that was picked. None if it is not part of this Job."""
    if _is_stock(job, obj):
        return obj
    models = model_objects(job)
    if obj in models:
        return obj
    for m in models:                      # the original body behind a model clone
        if obj in (getattr(m, "Objects", None) or []):
            return m
    return None


def outward_normal(face, solid):
    """The normal of a picked face that points out of the solid. (Which way normalAt points
    depends on how the face was made; a point just beside the face tells for sure.)"""
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    n = face.normalAt(u, v).normalize()
    p = face.valueAt(u, v)
    step = max(solid.BoundBox.DiagonalLength * 1e-4, 1e-3)
    try:
        if solid.isInside(p + n * step, step * 0.1, False):
            n = n.negative()
    except Exception:
        if face.Orientation == "Reversed":
            n = n.negative()
    return n


def turn_down(normal):
    """The rotation that turns `normal` to point straight down (-Z)."""
    down = App.Vector(0, 0, -1)
    if (normal - down).Length < 1e-9:
        return App.Rotation()
    if (normal + down).Length < 1e-9:                 # pointing up: half a turn about X
        return App.Rotation(App.Vector(1, 0, 0), 180)
    return App.Rotation(normal, down)


def _move(objs, placement):
    for o in objs:
        o.Placement = placement.multiply(o.Placement)


def _round_centre(shape):
    """The centre of the stock's section near its bottom when it is round, else None."""
    bb = shape.BoundBox
    wires = shape.slice(App.Vector(0, 0, 1), bb.ZMin + min(1.0, bb.ZLength / 2))
    if not wires:
        return None
    face = Part.makeFace(wires, "Part::FaceMakerBullseye")
    outer = max(face.Wires, key=lambda w: w.BoundBox.DiagonalLength)
    circles = [e for e in outer.Edges if e.Curve.__class__.__name__ == "Circle"]
    if circles and abs(sum(e.Length for e in circles) - outer.Length) < 1e-6:
        c = circles[0].Curve.Center
        if all((e.Curve.Center - c).Length < 1e-4 and abs(e.Curve.Radius - circles[0].Curve.Radius) < 1e-4
               for e in circles):
            return App.Vector(c.x, c.y, 0)
    return None


def orient(job, face_owner, face):
    """Turn the Job's model (and a stock of its own) so the picked face looks down, put the stock
    on the chuck axis (its round centre, else the middle of its outline) and its top at Z0."""
    doc = job.Document
    models = model_objects(job)
    stock = getattr(job, "Stock", None)
    follows = stock is not None and getattr(stock, "StockType", "") == "FromBase"
    objs = models + ([stock] if stock is not None and not follows else [])
    normal = outward_normal(face, face_owner.Shape)
    turn = turn_down(normal)
    pivot = face.CenterOfMass
    _move(objs, App.Placement(App.Vector(), turn, pivot))
    doc.recompute()
    shape = stock.Shape if stock is not None and not stock.Shape.isNull() else \
        Part.makeCompound([m.Shape for m in models])
    bb = shape.BoundBox
    centre = _round_centre(shape)
    if centre is None:
        centre = App.Vector(bb.Center.x, bb.Center.y, 0)
    _move(objs, App.Placement(App.Vector(-centre.x, -centre.y, -bb.ZMax), App.Rotation()))
    doc.recompute()
    show_job_copy(job)
    return centre is not None


def show_job_copy(job):
    """Show the Job's copy of the part (the one that was turned) and hide the original drawing,
    which stays where it was drawn: otherwise the part seems not to have moved."""
    for m in model_objects(job):
        try:
            for orig in getattr(m, "Objects", None) or []:
                if orig.ViewObject is not None:
                    orig.ViewObject.Visibility = False
            if m.ViewObject is not None:
                m.ViewObject.Visibility = True
        except Exception:
            pass


def suggest(job, owned=None):
    """(preset, grip length, notes) for the stock as it now stands in the Job."""
    owned = owned or my_chucks()
    notes = []
    stock = job.Stock.Shape if getattr(job, "Stock", None) is not None else None
    models = [m.Shape for m in model_objects(job) if hasattr(m, "Shape")]
    if stock is None or stock.isNull():
        return owned[0], 10.0, ["The Job has no stock."]
    sb = stock.BoundBox
    wires = stock.slice(App.Vector(0, 0, 1), sb.ZMin + min(1.0, sb.ZLength / 2))
    section = Part.makeFace(wires, "Part::FaceMakerBullseye") if wires else None
    round_ = ch.stock_is_round(section)
    reach = 0.0
    if section is not None:
        reach = max(v.Point.sub(App.Vector(0, 0, v.Point.z)).Length for v in section.Vertexes) \
            if section.Vertexes else section.BoundBox.XLength / 2
        if round_:
            reach = ch.contact_radius(section, 0.0) or reach
    dia = 2 * reach

    def holds(name):
        span = ch.GRIP_RANGES.get(name)
        if span is None:
            return ch.PRESETS[name][1] > dia
        return span[0] <= dia <= span[3]
    pick = None
    if round_:
        pick = next((n for n in owned if ch.PRESETS[n][0] in ch.SELF_CENTRING and holds(n)), None)
    if pick is None:
        pick = next((n for n in owned if ch.PRESETS[n][0] == ch.FOUR_JAW and holds(n)), None)
    if pick is None:
        pick = next((n for n in owned if holds(n)), None)
    if pick is None:
        notes.append("None of your chucks holds this stock (Ø%.1f): a catalogue chuck was chosen."
                     % dia)
        sizes = sorted((p[1], n) for n, p in ch.PRESETS.items()
                       if p and p[0] != ch.FACEPLATE and p[1] > dia * 1.2)
        pick = sizes[0][1] if sizes else owned[0]
    jaw_h = ch.PRESETS[pick][5] or 10.0
    below = (min(m.BoundBox.ZMin for m in models) - sb.ZMin) if models else 0.0
    if below >= MIN_GRIP:
        grip = min(below, jaw_h)
        notes.append("The jaws hold the %.1f mm of stock under the part." % grip)
    else:
        grip = min(jaw_h, max(sb.ZLength * 0.3, MIN_GRIP))
        notes.append("There is no spare stock under the part: the jaws hold the lowest %.1f mm of "
                     "it, and nothing is cut there." % grip)
    shape = "round Ø%.1f" % dia if round_ else "not round, Ø%.1f over its corners" % dia
    notes.insert(0, "Stock %s, %.1f long." % (shape, sb.ZLength))
    return pick, round(grip, 2), notes


def apply_chuck(job, preset, grip):
    """Make or change the Job's chuck."""
    obj = getattr(job, "PolarChuck", None)
    if obj is None:
        obj = ch.make_chuck(job, preset)
    obj.Preset = preset
    obj.GripLength = grip
    job.Document.recompute()
    if obj.ViewObject is not None and not getattr(job, "PolarLayout", "").startswith("Wrap"):
        obj.ViewObject.Visibility = True
    return obj
