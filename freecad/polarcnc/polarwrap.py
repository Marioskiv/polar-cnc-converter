# Polar CNC — the Polar Wrap operation: machining the outside of the real 3D part with the router
# turned radial (Wrap Job). The part is read as it is (solid or mesh/STL, its axis on Z through
# X0 Y0); its radius round the axis is mapped automatically (wrapcut.radius_map) and the cutter
# runs helices round it: roughing layers from the stock diameter down, then a finishing helix.
# The path is written round the real part (so CAM shows it where it cuts); Post Process unrolls it
# for the converter's wrap layout (program.unroll).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import math

import FreeCAD as App
import Path
import Path.Op.Base as PathOp
import PathScripts.PathUtils as PathUtils

from . import machine, wrapcut

STRATEGIES = ["Roughing + finishing", "Roughing", "Finishing"]
FINISH_STYLES = ["Helix round the part", "Lines along the part"]
DIRECTIONS = ["C+ (counter-clockwise)", "C- (clockwise)"]

PROPERTIES = (
    ("App::PropertyEnumeration", "Strategy", "Roughing layers from the stock diameter down, "
     "then a finishing helix on the part; or only one of them."),
    ("App::PropertyEnumeration", "FinishStyle", "Helix: one continuous cut round the part, the "
     "best surface on round shapes. Lines along the part: better for steps, grooves and flats "
     "along the axis (a helix crosses them at a slant)."),
    ("App::PropertyPercent", "StepOver", "Finishing: distance between the passes (along the part "
     "for the helix, round it for lines), in % of the cutter diameter (small with a ball end: "
     "smooth surface)."),
    ("App::PropertyPercent", "RoughStepOver", "Roughing: advance per turn, in % of the cutter "
     "diameter."),
    ("App::PropertyLength", "StepDown", "Roughing: depth of each layer (radial)."),
    ("App::PropertyLength", "FinishAllowance", "Roughing leaves this much on the part for the "
     "finishing pass."),
    ("App::PropertyDistance", "StockToLeave", "Material left on the part after finishing."),
    ("App::PropertyEnumeration", "Direction", "Which way the chuck turns while cutting."),
    ("App::PropertyLength", "GridStep", "Resolution of the part's map (along the part and round "
     "it). Smaller = more exact, slower."),
    ("App::PropertyFloat", "AirFeedFactor", "Roughing: where the cutter goes round over the part "
     "without touching material, it goes this many times the cutting feed."),
    ("App::PropertyLength", "SafeDistance", "How far above the stock the cutter goes between "
     "passes (radial)."),
    ("App::PropertyLength", "ChuckClearance", "How far the cutter stays from the chuck jaws "
     "along the part (when the Job has a Polar CNC chuck)."),
    ("App::PropertyDistance", "FromZ", "Machine from here (the free end, high Z); equal to ToZ = "
     "automatic: the whole part above the chuck."),
    ("App::PropertyDistance", "ToZ", "... down to here (toward the chuck)."),
)


class ObjectPolarWrap(PathOp.ObjectOp):

    def opFeatures(self, obj):
        return PathOp.FeatureTool | PathOp.FeatureCoolant

    def initOperation(self, obj):
        for typ, name, tip in PROPERTIES:
            if not hasattr(obj, name):
                obj.addProperty(typ, name, "Polar Wrap", tip)
        for prop, items in (("Strategy", STRATEGIES), ("Direction", DIRECTIONS),
                            ("FinishStyle", FINISH_STYLES)):
            value = getattr(obj, prop, "")       # keep the choice when a saved file is opened
            setattr(obj, prop, items)
            setattr(obj, prop, value if value in items else items[0])

    def opOnDocumentRestored(self, obj):
        self.initOperation(obj)

    def opSetDefaultValues(self, obj, job):
        obj.Strategy = STRATEGIES[0]
        obj.StepOver = 15
        obj.RoughStepOver = 50
        obj.StepDown = 1.0
        obj.FinishAllowance = 0.3
        obj.StockToLeave = 0
        obj.Direction = DIRECTIONS[0]
        obj.GridStep = 0.25
        obj.SafeDistance = 5.0
        obj.AirFeedFactor = 3.0
        obj.ChuckClearance = 2.0

    def opExecute(self, obj):
        from .polarface import Progress, Stopped
        progress = Progress("Polar Wrap")
        try:
            self._execute(obj, progress.tick)
        except Stopped:
            del self.commandlist[:]
            Path.Log.warning("Polar Wrap: stopped (Esc). No path was made; press Recompute to "
                             "make it again.")
        finally:
            progress.stop()

    def _execute(self, obj, tick):
        job = PathUtils.findParentJob(obj)
        r_stock = machine.wrap_radius(job) if job is not None else 0.0
        if r_stock <= 0:
            Path.Log.error("Polar Wrap: set the Job's Polar Wrap Diameter (the stock diameter).")
            return
        shapes, meshes, bb = [], [], None
        for m in self.model:
            if hasattr(m, "Mesh"):
                meshes.append(m.Mesh)
                b = m.Mesh.BoundBox
            elif hasattr(m, "Shape") and not m.Shape.isNull():
                shapes.append(m.Shape)
                b = m.Shape.BoundBox
            else:
                continue
            if bb is None:
                bb = App.BoundBox(b)
            else:
                bb.add(b)
        if bb is None:
            Path.Log.error("Polar Wrap: the Job has no model.")
            return
        if abs(bb.Center.x) > 0.5 or abs(bb.Center.y) > 0.5:
            Path.Log.warning("Polar Wrap: the part is not centred on the Z axis (X0 Y0): it is "
                             "machined round the Z axis as it is.")
        step = max(obj.GridStep.Value, 0.05)
        radius = self.radius
        tool = getattr(obj.ToolController, "Tool", None)
        ball = "ball" in str(getattr(tool, "ShapeType", "") or getattr(tool, "ShapeName", "")).lower()

        zlo, zhi = bb.ZMin, bb.ZMax
        zs = [zlo + k * step for k in range(int(math.floor((zhi - zlo) / step)) + 1)]
        if len(zs) < 2:
            Path.Log.error("Polar Wrap: the part is too short along Z.")
            return
        import numpy
        zs = numpy.array(zs)
        na = max(int(math.ceil(2 * math.pi * r_stock / step)), 16)
        # the part's map is the slow step: kept while the part, the grid and the stock stay
        key = (tuple((s.hashCode(), round(s.Volume, 6), str(s.BoundBox)) for s in shapes),
               tuple((m.CountFacets, str(m.BoundBox)) for m in meshes),
               round(step, 6), len(zs), na, round(float(zs[0]), 6), round(r_stock, 6))
        cache = getattr(self, "_map_cache", None)
        if cache and cache[0] == key:
            H = cache[1]
        else:
            tick()
            H = wrapcut.radius_map(shapes, meshes, zs, na, r_stock)
            self._map_cache = (key, H)
        empty = [float(zs[i]) for i in range(1, len(zs) - 1) if float(H[i].max()) <= 0]
        if empty:
            Path.Log.error("Polar Wrap: the part has a gap along Z from %.2f to %.2f (no part there "
                           "at all: two separate parts, or a mesh that does not close). The cutter "
                           "would go down to the axis there: fix the model." % (min(empty), max(empty)))
            return
        # the bar in the Job (a cylinder stock) against the diameter typed in
        stock = getattr(job, "Stock", None)
        sr = getattr(stock, "Radius", None)
        if sr is not None and abs(sr.Value - r_stock) > 0.05:
            Path.Log.warning("Polar Wrap: the Job's stock is a cylinder of diameter %.2f, the Polar "
                             "Wrap Diameter says %.2f: the roughing starts from the diameter typed "
                             "in. Make them the same." % (2 * sr.Value, 2 * r_stock))
        if stock is not None and not stock.Shape.isNull():
            sb = stock.Shape.BoundBox
            if sb.ZMax > zhi + self.radius + 0.5:
                Path.Log.warning("Polar Wrap: the stock is %.1f mm longer than the part at the free "
                                 "end: that end is not cut (cut it off, or face it first)."
                                 % (sb.ZMax - zhi))
        if float(H.max()) > r_stock + 0.01:
            Path.Log.error("Polar Wrap: the part (radius %.2f) is bigger than the stock (Polar Wrap "
                           "Diameter %.2f): check the diameter." % (float(H.max()), 2 * r_stock))
            return
        leave = obj.StockToLeave.Value
        Xf = wrapcut.tip_map(H, zs, na, radius, ball, leave, tick)
        Xr = wrapcut.tip_map(H, zs, na, radius, ball, leave + obj.FinishAllowance.Value, tick)

        # along the part: from the free end (high Z) toward the chuck, stopping clear of the jaws
        z_from, z_to = obj.FromZ.Value, obj.ToZ.Value
        if abs(z_from - z_to) < 1e-9:
            z_from, z_to = zhi + radius, zlo      # past the free end by the cutter radius
            chuck = getattr(job, "PolarChuck", None)
            if chuck is not None and not chuck.Shape.isNull():
                z_to = max(z_to, chuck.Shape.BoundBox.ZMax + obj.ChuckClearance.Value + radius)
        if z_from <= z_to:
            Path.Log.error("Polar Wrap: nothing to machine between Z %.2f and %.2f (the chuck "
                           "holds the rest)." % (z_from, z_to))
            return
        if obj.Strategy == "Finishing":          # one helix may not take the whole depth
            deepest = r_stock - float(Xf.min())
            allowed = obj.FinishAllowance.Value + obj.StepDown.Value + 1e-6
            if deepest > allowed:
                Path.Log.error("Polar Wrap: finishing alone would cut %.2f mm deep in one pass "
                               "(at most finish allowance + step down = %.2f). Use Roughing + "
                               "finishing." % (deepest, allowed))
                return
        d = 2 * radius
        passes = wrapcut.helix_passes(
            Xr, Xf, zs, na, r_stock, z_from, z_to,
            max(obj.RoughStepOver, 1) / 100.0 * d, max(obj.StepOver, 1) / 100.0 * d,
            max(obj.StepDown.Value, 0.01), min(0.5, step * 2),
            roughing=obj.Strategy != "Finishing", finishing=obj.Strategy != "Roughing",
            ccw=obj.Direction == DIRECTIONS[0], radius=radius,
            finish_lines=obj.FinishStyle == FINISH_STYLES[1])

        safe = r_stock + obj.SafeDistance.Value
        feed, vfeed = self.horizFeed, self.vertFeed
        air = feed * max(getattr(obj, "AirFeedFactor", 3.0) or 1.0, 1.0)
        if not feed or not vfeed:
            Path.Log.error("Polar Wrap: the tool controller '%s' has no feed. Set its Horiz Feed "
                           "and Vert Feed." % getattr(obj.ToolController, "Label", "?"))
            return
        cmds = self.commandlist
        for p in passes:
            z0, th0, r0, _c = p[0]
            cmds.append(Path.Command("G0", {"X": safe * math.cos(th0), "Y": safe * math.sin(th0), "Z": z0}))
            cmds.append(Path.Command("G1", {"X": r0 * math.cos(th0), "Y": r0 * math.sin(th0), "Z": z0,
                                            "F": vfeed}))
            for z, th, r, cutting in _thin(p):
                cmds.append(Path.Command("G1", {"X": r * math.cos(th), "Y": r * math.sin(th), "Z": z,
                                                "F": feed if cutting else air}))
            z1, th1, _r1, _c1 = p[-1]
            cmds.append(Path.Command("G0", {"X": safe * math.cos(th1), "Y": safe * math.sin(th1), "Z": z1}))


MAX_TURN = math.radians(10)      # a written point at least every 10 degrees round the part


def _thin(p):
    """The points of a pass after the first, without those that lie on the straight joint move
    between their neighbours: where the radius stays the same the helix (or line along the part)
    is linear in Z and angle, which is exactly how the machine moves between two blocks. Kept at
    least every MAX_TURN, so the path drawn in FreeCAD (straight Cartesian lines) stays close."""
    out = []
    last_th = p[0][1]
    n = len(p)
    for k in range(1, n):
        z, th, r, cut = p[k]
        if k < n - 1:
            r0, r1 = p[k - 1][2], p[k + 1][2]
            same = abs(r - r0) < 1e-6 and abs(r - r1) < 1e-6 and \
                p[k - 1][3] == cut and p[k + 1][3] == cut
            if same and abs(th - last_th) < MAX_TURN:
                continue
        out.append((z, th, r, cut))
        last_th = th
    return out


def SetupProperties():
    return [name for _typ, name, _tip in PROPERTIES]


def Create(name, obj=None, parentJob=None):
    if obj is None:
        obj = App.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPolarWrap(obj, name, parentJob)
    return obj
