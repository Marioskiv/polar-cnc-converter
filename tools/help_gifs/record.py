# Polar CNC — records the frames of the help animations in a real FreeCAD, one scene per
# FreeCAD start (opening many CAM task dialogs in one session crashes FreeCAD 26.3):
#
#   HELP_SCENE=chuck HELP_OUT=/tmp/frames xvfb-run -a -s "-screen 0 1600x1000x24" \
#       freecad tools/help_gifs/record.py
#
# Writes <HELP_OUT>/<scene>/NNN.png (the 3D view) and frames.json: for every frame the step it
# belongs to (1, 2, 3 = the numbered steps of the popup; 0 = the result) and whether the
# toolbar button is shown pressed. compose.py then adds the button card and the captions.
# Everything shown is made by the addon itself (chuck, clamps, Polar Face, Polar Wrap, the
# simulator), on small example parts.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import json
import math
import os
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

SCENE = os.environ.get("HELP_SCENE", "chuck")
OUT = os.path.join(os.environ.get("HELP_OUT", "/tmp/polarcnc-help-frames"), SCENE)
os.makedirs(OUT, exist_ok=True)
FRAMES = []
SHOT = [0]           # a new camera (a cut): compose.py frames each shot on its own
BG = (244, 245, 242)


def pump(ms=40):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        QtGui.QApplication.processEvents()


def light_view():
    """A plain light background, no navigation cube or axis cross: the part is what counts."""
    p = App.ParamGet("User parameter:BaseApp/Preferences/View")
    p.SetBool("Simple", True)
    p.SetBool("Gradient", False)
    p.SetBool("RadialGradient", False)
    p.SetUnsigned("BackgroundColor", (BG[0] << 24) | (BG[1] << 16) | (BG[2] << 8))
    p.SetBool("ShowNaviCube", False)
    p.SetBool("CornerCoordSystem", False)
    p.SetBool("ShowAxisCross", False)


def view_widget():
    mdi = Gui.getMainWindow().findChild(QtGui.QMdiArea)
    return mdi.activeSubWindow().widget()


def frame(step, pressed=False, n=1):
    """Grab the 3D view n times (n equal frames make a pause)."""
    pump(60)
    img = view_widget().grab()
    for _ in range(n):
        path = os.path.join(OUT, "%03d.png" % len(FRAMES))
        img.save(path)
        FRAMES.append({"step": step, "pressed": pressed, "shot": SHOT[0]})


def iso(zoom=1.0):
    SHOT[0] += 1
    v = Gui.ActiveDocument.ActiveView
    v.viewIsometric()
    v.fitAll()
    if zoom != 1.0:
        cam = v.getCameraNode()
        try:
            cam.height.setValue(cam.height.getValue() / zoom)
        except Exception:
            pass
    pump(60)


def orbit(step, frames=12, total=40.0):
    v = Gui.ActiveDocument.ActiveView
    base = v.getCameraOrientation()
    for k in range(1, frames + 1):
        a = total * k / frames
        v.setCameraOrientation(App.Rotation(App.Vector(0, 0, 1), a).multiply(base))
        frame(step)


def polar_job(doc, shape, name="Part", stock=None):
    """A CAM Job round a part centred on the chuck axis, made polar as the button does."""
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    part = doc.addObject("Part::Feature", name)
    part.Shape = shape
    doc.recompute()
    job = PathJob.Create("Job", [part], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    if stock:
        st = job.Stock
        st.ExtXneg = st.ExtXpos = st.ExtYneg = st.ExtYpos = stock[0]
        st.ExtZneg, st.ExtZpos = 0, stock[1]
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    doc.recompute()
    return job, part


def make_polar(job):
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(job)
    Gui.runCommand("PolarCNC_MachineSettings")
    job.PolarXMax = 125
    job.PostProcessorArgs = "--no-show-editor"
    job.Document.recompute()
    Gui.Selection.clearSelection()


def steel(obj, rgb=(0.66, 0.68, 0.72), transparency=0):
    obj.ViewObject.ShapeColor = rgb
    obj.ViewObject.Transparency = transparency


def only(doc, keep):
    """Show only these objects (the chuck and clamps through show_copy)."""
    names = {o.Name for o in keep}
    for o in doc.Objects:
        vo = getattr(o, "ViewObject", None)
        if vo is not None:
            vo.Visibility = o.Name in names


def show_copy(doc, obj, rgb=(0.66, 0.68, 0.72), name="Copy"):
    """A plain copy of an object's shape. The chuck and the clamps belong to the Job, and with
    the Job hidden (only the part, the stock and the chuck are shown here) FreeCAD does not draw
    them: their copies are drawn instead."""
    copy = doc.getObject(name) or doc.addObject("Part::Feature", name)
    copy.Shape = obj.Shape
    steel(copy, rgb)
    copy.ViewObject.Visibility = True
    return copy


def open_simulator(job, part_view=False):
    from polarcnc import simulator
    panel = simulator.open_for(job)
    SHOT[0] += 1
    pump(400)
    panel.whole.setChecked(True)
    if part_view:
        panel.partv.setChecked(True)
    return panel


def play(panel, step, frames, start=0.0, end=1.0):
    total = panel.motion.total
    for k in range(frames):
        panel._jump(total * (start + (end - start) * k / max(frames - 1, 1)))
        frame(step)


class Sim:
    """The simulator's own scene in the 3D view, without its task dialog (several of them can
    be shown one after the other in one FreeCAD start)."""

    def __init__(self, job, machine=False, whole=True, chuck=True):
        from polarcnc import bridge, program, simulator
        SHOT[0] += 1
        text, opts = program.polar(job)
        self.motion = simulator.Motion(bridge.parse(text, opts))
        self.scene = simulator.Scene(job, self.motion, opts)
        self.scene.machine_view = machine
        self.view = Gui.ActiveDocument.ActiveView
        self.view.getSceneGraph().addChild(self.scene.root)
        self.scene.chuck_sw.whichChild.setValue(0 if chuck else -1)
        self.scene.all_sw.whichChild.setValue(0 if whole else -1)
        self.shown = [(o, o.ViewObject.Visibility) for o in job.Document.Objects
                      if getattr(o, "ViewObject", None) is not None]
        for o, v in self.shown:
            if v:
                o.ViewObject.Visibility = False
        self.scene.show(0.0)
        self.view.viewIsometric()
        vp = self.view.getViewer().getSoRenderManager().getViewportRegion()
        self.view.getCameraNode().viewAll(self.scene.root, vp)
        pump(200)

    def play(self, step, frames, start=0.0, end=1.0):
        total = self.motion.total
        for k in range(frames):
            self.scene.show(total * (start + (end - start) * k / max(frames - 1, 1)))
            frame(step)

    def close(self):
        self.view.getSceneGraph().removeChild(self.scene.root)
        for o, v in self.shown:
            o.ViewObject.Visibility = v
        pump(100)


def fit_to(doc, shape, zoom=1.0):
    """Aim the camera at one region (a box round it), then show the scene again."""
    SHOT[0] += 1
    keep = [(o, o.ViewObject.Visibility) for o in doc.Objects if getattr(o, "ViewObject", None)]
    for o, _v in keep:
        o.ViewObject.Visibility = False
    aim = doc.addObject("Part::Feature", "Aim")
    aim.Shape = shape
    doc.recompute()
    v = Gui.ActiveDocument.ActiveView
    v.viewIsometric()
    v.fitAll()
    if zoom != 1.0:
        cam = v.getCameraNode()
        cam.height.setValue(cam.height.getValue() / zoom)
    doc.removeObject(aim.Name)
    for o, vis in keep:
        o.ViewObject.Visibility = vis
    pump(100)


def box_of(bb):
    import Part
    return Part.makeBox(max(bb.XLength, 1e-3), max(bb.YLength, 1e-3), max(bb.ZLength, 1e-3),
                        App.Vector(bb.XMin, bb.YMin, bb.ZMin))


def bar_job(doc, part, stock):
    """A Job whose stock is a solid of its own (a round bar), made polar."""
    import Draft
    from Path.Main import Job as PathJob
    from Path.Main.Gui import Job as PathJobGui
    p = doc.addObject("Part::Feature", "Part")
    p.Shape = part
    doc.recompute()
    job = PathJob.Create("Job", [p], None)
    job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
    holder = doc.addObject("Part::Feature", "Bar")
    holder.Shape = stock
    holder.ViewObject.Visibility = False
    old = job.Stock
    clone = Draft.make_clone(holder)
    clone.Label = "Stock"
    job.Stock = clone
    doc.removeObject(old.Name)
    tc = job.Tools.Group[0]
    tc.HorizFeed, tc.VertFeed = "600 mm/min", "200 mm/min"
    doc.recompute()
    make_polar(job)
    return job, p


# ---------------------------------------------------------------- scenes

def scene_machine(doc):
    """The polar machine: the Job, the button, X Max, then the program played on the machine."""
    import Part
    import Path.Op.Profile as Profile
    job, part = polar_job(doc, Part.makeCylinder(40, 10).cut(
        Part.makeBox(30, 30, 6, App.Vector(5, -15, 4))), stock=(5, 2))
    prof = Profile.Create("Profile")
    prof.Base = [(part, ())]
    doc.recompute()
    only(doc, [part])
    steel(part, (0.80, 0.62, 0.30))
    iso(0.9)
    frame(1, n=4)
    Gui.Selection.addSelection(part)
    frame(1, n=8)
    frame(2, pressed=True, n=10)
    Gui.Selection.clearSelection()
    make_polar(job)
    from polarcnc import chuck
    held = chuck.make_chuck(job)
    held.GripLength = 6
    doc.recompute()
    only(doc, [part])
    show_copy(doc, held)
    iso(0.9)
    frame(3, n=12)
    panel = open_simulator(job)
    play(panel, 0, 24, 0.0, 0.8)
    panel.reject()


def scene_chuck(doc):
    """A bar lying on its side; its end is clicked; the button: the bar turns to stand on that
    end, on the chuck axis; the 3-jaw chuck that holds it comes, its jaws close; a look round."""
    import Part
    from polarcnc import chuck, setup
    V = App.Vector
    part = Part.makeCylinder(12, 45, V(0, 0, 0), V(1, 0, 0)).cut(
        Part.makeCylinder(14, 4, V(20, 0, 0), V(1, 0, 0)).cut(Part.makeCylinder(9, 4, V(20, 0, 0), V(1, 0, 0))))
    job, orig = bar_job(doc, part, Part.makeCylinder(14, 54, V(-3, 0, 0), V(1, 0, 0)))
    model = job.Model.Group[0]
    stock = job.Stock
    setup.show_job_copy(job)
    steel(model, (0.80, 0.62, 0.30))
    steel(stock, (0.80, 0.62, 0.30), 70)
    start = {o: App.Placement(o.Placement) for o in (model, stock)}
    k = next(k for k, f in enumerate(model.Shape.Faces) if abs(f.CenterOfMass.x - 45) < 1e-6)
    face, name = model.Shape.Faces[k], "Face%d" % (k + 1)
    # where it ends: turned, centred, in the chuck (the camera is set for that)
    setup.orient(job, model, face)
    held = setup.apply_chuck(job, setup.MY_CHUCKS[0], 6)
    end = {o: App.Placement(o.Placement) for o in (model, stock)}
    bb_end = stock.Shape.BoundBox
    only(doc, [model, stock, held])
    held.ViewObject.Visibility = False
    for o in (model, stock):
        o.Placement = start[o]
    doc.recompute()
    bb_start = stock.Shape.BoundBox
    fit_to(doc, box_of(bb_start), 0.9)
    frame(1, n=4)
    Gui.Selection.addSelection(model, name)
    frame(1, n=10)
    frame(2, pressed=True, n=4)
    Gui.Selection.clearSelection()
    both = App.BoundBox(bb_start)
    both.add(bb_end)
    fit_to(doc, box_of(both), 0.95)
    for k in range(1, 15):
        t = 0.5 - 0.5 * math.cos(math.pi * k / 14)
        for o in (model, stock):
            a, b = start[o], end[o]
            o.Placement = App.Placement(a.Base + (b.Base - a.Base) * t, a.Rotation.slerp(b.Rotation, t))
        doc.recompute()
        frame(2)
    built = chuck._build(held)
    body = doc.addObject("Part::Feature", "AnimBody")
    body.Shape = built["body"]
    steel(body)
    jaws = []
    for k, (shape, _r) in enumerate(built["jaws"]):
        j = doc.addObject("Part::Feature", "AnimJaw%d" % k)
        j.Shape = shape
        c = shape.BoundBox.Center
        d = App.Vector(c.x, c.y, 0)
        steel(j, (0.56, 0.58, 0.62))
        jaws.append((j, d.normalize() if d.Length > 1e-6 else App.Vector(1, 0, 0), App.Placement(j.Placement)))
    held.ViewObject.Visibility = True
    iso(1.0)
    held.ViewObject.Visibility = False
    for k in range(12):
        open_by = 20.0 * (1 - k / 11.0)
        for j, d, p0 in jaws:
            j.Placement = App.Placement(d * open_by, App.Rotation()).multiply(p0)
        frame(3)
    for j in [j[0] for j in jaws] + [body]:
        doc.removeObject(j.Name)
    held.ViewObject.Visibility = True
    steel(held)
    frame(3, n=6)
    orbit(0, 12, 50.0)


def scene_clamp(doc):
    """A faceplate, the clamps added one by one round square stock, then one turned."""
    import Part
    from polarcnc import chuck
    job, part = polar_job(doc, Part.makeBox(60, 60, 12, App.Vector(-30, -30, 0)), stock=(0, 0))
    make_polar(job)
    plate = chuck.make_chuck(job, "Faceplate Ø250")
    doc.recompute()
    stock = job.Stock
    steel(stock, (0.80, 0.62, 0.30))
    only(doc, [stock])
    show_copy(doc, plate, name="Plate")
    iso(1.0)
    frame(1, n=10)
    clamps = []
    for k, angle in enumerate((0, 90, 180, 270)):
        cl = chuck.add_clamp(plate, angle=angle)
        doc.recompute()
        clamps.append(cl)
        show_copy(doc, cl, (0.46, 0.48, 0.52), "Clamp%d" % k)
        frame(2, pressed=True, n=2)
        frame(2, n=4)
    cl = clamps[0]
    for a in range(0, 50, 5):
        cl.Angle = a
        doc.recompute()
        show_copy(doc, cl, (0.85, 0.55, 0.15), "Clamp0")
        frame(3)
    show_copy(doc, cl, (0.46, 0.48, 0.52), "Clamp0")
    frame(3, n=6)
    orbit(0, 14, 50.0)


def scene_polarface(doc):
    """Square stock round a round part: Polar Face cuts circles only where the stock is."""
    import Part
    job, part = polar_job(doc, Part.makeCylinder(15, 10).fuse(Part.makeCylinder(6, 15)), stock=(10, 5))
    make_polar(job)
    from polarcnc import chuck
    held = chuck.make_chuck(job)
    held.GripLength = 4
    doc.recompute()
    stock = job.Stock
    steel(stock, (0.80, 0.62, 0.30), 55)
    steel(part, (0.35, 0.55, 0.85))
    only(doc, [stock, part])
    copy = show_copy(doc, held)
    iso(1.0)
    frame(1, n=4)
    Gui.Selection.addSelection(job.Stock)
    frame(1, n=6)
    Gui.Selection.clearSelection()
    from polarcnc import polarface_gui
    polarface_gui.register()
    cmd = polarface_gui.Command()
    cmd.res.job = job
    frame(2, pressed=True, n=6)
    op = polarface_gui.create(cmd.res)
    pump(500)
    Gui.Control.activeTaskDialog().accept()
    pump(300)
    doc.recompute()
    only(doc, [stock, part, copy, op])
    frame(3, n=10)
    panel = open_simulator(job, part_view=True)
    play(panel, 0, 34, 0.0, 1.0)
    panel.reject()


def scene_polarwrap(doc):
    """A bar with a groove and a flat: the Wrap Job, Polar Wrap, the helices on the machine."""
    import Part
    from polarcnc import machine
    shape = Part.makeCylinder(20, 60)
    shape = shape.cut(Part.makeCylinder(30, 7, App.Vector(0, 0, 30)).cut(
        Part.makeCylinder(17, 7, App.Vector(0, 0, 30))))
    shape = shape.cut(Part.makeBox(10, 40, 10, App.Vector(16, -20, 42)))
    job, part = polar_job(doc, shape)
    make_polar(job)
    job.PolarLayout = machine.WRAP
    job.PolarWrapDiameter = 44
    job.PolarWrapToolLengthInX = True
    doc.recompute()
    from polarcnc import policy
    policy._cache[0] = 0.0
    steel(part, (0.80, 0.62, 0.30))
    only(doc, [part])
    iso(0.8)
    frame(1, n=12)
    from polarcnc import polarwrap_gui
    polarwrap_gui.register()
    cmd = polarwrap_gui.Command()
    cmd.res.job = job
    frame(2, pressed=True, n=8)
    op = polarwrap_gui.create(cmd.res)
    pump(500)
    op.Strategy = op.getEnumerationsOfProperty("Strategy")[0]
    Gui.Control.activeTaskDialog().accept()
    pump(300)
    doc.recompute()
    panel = open_simulator(job, part_view=True)
    panel.whole.setChecked(False)          # the helices as they are cut, the bar still visible
    play(panel, 3, 12, 0.0, 0.35)
    panel.machine.setChecked(True)
    play(panel, 0, 22, 0.35, 1.0)
    panel.reject()


def scene_simulate(doc):
    """A pocket off the centre: the machine view (the chuck turns), then the part view."""
    import Part
    import Path.Op.PocketShape as PocketShape
    import Path.Op.Profile as Profile
    job, part = polar_job(doc, Part.makeCylinder(40, 10).cut(
        Part.makeBox(25, 25, 6, App.Vector(10, -8, 4))), stock=(3, 1))
    prof = Profile.Create("Profile")
    prof.Base = [(part, ())]
    face = [n for n, f in enumerate(part.Shape.Faces, 1) if abs(f.CenterOfMass.z - 4) < 1e-6][0]
    pocket = PocketShape.Create("Pocket")
    pocket.Base = [(part, ("Face%d" % face,))]
    pocket.ClearingPattern = "Offset"
    doc.recompute()
    make_polar(job)
    from polarcnc import chuck
    held = chuck.make_chuck(job)
    held.GripLength = 5
    doc.recompute()
    steel(part, (0.80, 0.62, 0.30))
    only(doc, [part])
    show_copy(doc, held)
    iso(0.9)
    Gui.Selection.addSelection(part)
    frame(1, n=8)
    Gui.Selection.clearSelection()
    frame(2, pressed=True, n=6)
    panel = open_simulator(job)
    play(panel, 2, 6, 0.0, 0.02)
    play(panel, 3, 18, 0.02, 0.7)
    panel.partv.setChecked(True)
    play(panel, 0, 12, 0.7, 1.0)
    panel.reject()


ICONS = {"machine": "PolarCNC.svg", "chuck": "PolarChuck.svg", "clamp": "PolarClamp.svg",
         "polarface": "PolarFace.svg", "polarwrap": "PolarWrap.svg", "simulate": "PolarSimulate.svg"}
# field animations have no button card


def save_icon():
    """The toolbar icon as a PNG for compose.py (PIL cannot draw SVG)."""
    from PySide import QtCore
    if SCENE not in ICONS:
        return
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "freecad", "Resources", ICONS[SCENE])
    icon = QtGui.QIcon(path)
    icon.pixmap(QtCore.QSize(96, 96)).save(os.path.join(OUT, "icon.png"))


def scene_pf_clearing(doc):
    """What Polar Face cuts: 1 the top only, 2 all the stock round the part, 3 a band round it."""
    import Part
    from polarcnc import polarface as pf, polarface_gui
    job, part = polar_job(doc, Part.makeCylinder(18, 16).fuse(Part.makeBox(10, 10, 20, App.Vector(-5, -5, 0))),
                          stock=(12, 3))
    job.Stock.ExtZneg = 6
    make_polar(job)
    from polarcnc import setup
    held = setup.apply_chuck(job, setup.MY_CHUCKS[1], 6)
    polarface_gui.register()
    cmd = polarface_gui.Command()
    cmd.res.job = job
    op = polarface_gui.create(cmd.res)
    pump(500)
    Gui.Control.activeTaskDialog().accept()
    pump(300)
    for step, mode in ((1, pf.FACE_ONLY), (2, pf.WHOLE), (3, pf.BAND)):
        op.Clearing = mode
        op.BandWidth = 6
        doc.recompute()
        sim = Sim(job, chuck=False)
        sim.play(step, 14, 0.0, 1.0)
        frame(step, n=6)
        sim.close()


def scene_pf_ramp(doc):
    """Into the material without plunging: the cutter ramps down along its circle (1), then goes
    back to the start at depth (2) and cuts on."""
    import Part
    from polarcnc import polarface as pf, polarface_gui, setup
    job, part = polar_job(doc, Part.makeCylinder(15, 14), stock=(10, 3))
    job.Stock.ExtZneg = 6
    make_polar(job)
    setup.apply_chuck(job, setup.MY_CHUCKS[1], 6)
    polarface_gui.register()
    cmd = polarface_gui.Command()
    cmd.res.job = job
    op = polarface_gui.create(cmd.res)
    pump(500)
    Gui.Control.activeTaskDialog().accept()
    pump(300)
    op.Clearing = pf.BAND
    op.BandWidth = 6
    op.StepDown = 3
    op.RampAngle = 6
    doc.recompute()
    # the first ramp: the run of G1 moves that go down while they move sideways
    pts, z_prev, ramp, back = [], None, [], []
    x = y = z = None
    for c in op.Path.Commands:
        p = c.Parameters
        nx, ny, nz = p.get("X", x), p.get("Y", y), p.get("Z", z)
        if c.Name == "G1" and x is not None and z is not None and nz < z - 1e-6 and \
                math.hypot(nx - x, ny - y) > 1e-6:
            ramp.append(App.Vector(nx, ny, nz))
        elif ramp and c.Name == "G1" and abs(nz - z) < 1e-9 and math.hypot(nx - x, ny - y) > 1e-6:
            back.append(App.Vector(nx, ny, nz))
        elif ramp and c.Name in ("G2", "G3", "G0"):
            break
        x, y, z = nx, ny, nz
    ramp = [App.Vector(ramp[0].x, ramp[0].y, ramp[0].z + 0.5)] + ramp if ramp else ramp
    region = Part.makeCompound([Part.Vertex(p) for p in ramp + back]).BoundBox
    fit_to(doc, Part.makeBox(max(region.XLength, 1) + 24, max(region.YLength, 1) + 24, region.ZLength + 16,
                             App.Vector(region.XMin - 12, region.YMin - 12, region.ZMin - 8)), 1.25)
    steel(job.Stock, (0.80, 0.62, 0.30), 75)
    steel(part, (0.35, 0.55, 0.85))
    only(doc, [job.Stock, part])
    r = op.ToolController.Tool.Diameter.Value / 2
    tool = doc.addObject("Part::Feature", "Cutter")
    tool.Shape = Part.makeCylinder(r, 30)
    steel(tool, (0.30, 0.33, 0.38))
    trail = doc.addObject("Part::Feature", "Trail")
    steel(trail, (0.94, 0.45, 0.10))

    def tube(points, r=0.35):
        """The path so far as a thin tube (a plain line is too thin to see at this size)."""
        parts = []
        for a, b in zip(points, points[1:]):
            d = b - a
            if d.Length > 1e-6:
                parts.append(Part.makeCylinder(r, d.Length, a, d))
        return Part.makeCompound(parts)
    for step, pts in ((1, ramp), (2, back)):
        n = len(pts)
        idx = [int(round(k * (n - 1) / 13.0)) for k in range(14)] if n > 14 else list(range(n))
        for i in idx:
            q = pts[i]
            tool.Placement = App.Placement(App.Vector(q.x, q.y, q.z), App.Rotation())
            done = (ramp if step == 1 else ramp + back)[: (i + 1) if step == 1 else len(ramp) + i + 1]
            if len(done) > 1:
                trail.Shape = tube(done)
            doc.recompute()
            frame(step)
    frame(0, n=8)


def scene_wrap_strategy(doc):
    """Polar Wrap: 1 roughing layers from the bar down, 2 finishing as a helix round the part,
    3 finishing as lines along it."""
    import Part
    from polarcnc import machine, polarwrap, polarwrap_gui, policy, setup
    shape = Part.makeCylinder(20, 60)
    shape = shape.cut(Part.makeCylinder(30, 7, App.Vector(0, 0, 30)).cut(
        Part.makeCylinder(17, 7, App.Vector(0, 0, 30))))
    shape = shape.cut(Part.makeBox(10, 40, 10, App.Vector(16, -20, 42)))
    job, part = polar_job(doc, shape)
    make_polar(job)
    job.PolarLayout = machine.WRAP
    job.PolarWrapDiameter = 44
    job.PolarWrapToolLengthInX = True
    doc.recompute()
    policy._cache[0] = 0.0
    polarwrap_gui.register()
    cmd = polarwrap_gui.Command()
    cmd.res.job = job
    op = polarwrap_gui.create(cmd.res)
    pump(500)
    Gui.Control.activeTaskDialog().accept()
    pump(300)
    strategies = op.getEnumerationsOfProperty("Strategy")
    styles = op.getEnumerationsOfProperty("FinishStyle")
    rough = next((x for x in strategies if "ough" in x and "inish" not in x), strategies[0])
    finish = next((x for x in strategies if "inish" in x and "ough" not in x), strategies[-1])
    both = strategies[0]
    # finishing alone on the full bar would cut too deep (Polar Wrap refuses it), so steps 2 and 3
    # play the finishing part of roughing + finishing
    for step, (strat, style, a, b) in ((1, (rough, styles[0], 0.0, 1.0)), (2, (both, styles[0], 0.62, 1.0)),
                                       (3, (both, styles[-1], 0.62, 1.0))):
        op.Strategy = strat
        op.FinishStyle = style
        doc.recompute()
        sim = Sim(job, machine=False, whole=False)
        sim.play(step, 16, a, b)
        frame(step, n=6)
        sim.close()


def run():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/PolarCNC").SetBool("SettingsDialog", False)
    light_view()
    save_icon()
    Gui.activateWorkbench("CAMWorkbench")
    mw = Gui.getMainWindow()
    mw.resize(1500, 950)
    for name in ("Report view", "Python console"):
        for dock in mw.findChildren(QtGui.QDockWidget):
            if dock.windowTitle() == name:
                dock.hide()
    doc = App.newDocument("Help")
    pump(300)
    globals()["scene_" + SCENE](doc)
    with open(os.path.join(OUT, "frames.json"), "w") as f:
        json.dump({"scene": SCENE, "frames": FRAMES}, f)


try:
    run()
except Exception:
    with open(os.path.join(OUT, "error.txt"), "w") as f:
        f.write(traceback.format_exc())
os._exit(0)
