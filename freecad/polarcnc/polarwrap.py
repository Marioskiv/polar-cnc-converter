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
DIRECTIONS = ["C+ (counter-clockwise)", "C- (clockwise)"]

PROPERTIES = (
    ("App::PropertyEnumeration", "Strategy", "Roughing layers from the stock diameter down, "
     "then a finishing helix on the part; or only one of them."),
    ("App::PropertyPercent", "StepOver", "Finishing: how far the helix advances along the part "
     "per turn, in % of the cutter diameter (small with a ball end: smooth surface)."),
    ("App::PropertyPercent", "RoughStepOver", "Roughing: advance per turn, in % of the cutter "
     "diameter."),
    ("App::PropertyLength", "StepDown", "Roughing: depth of each layer (radial)."),
    ("App::PropertyLength", "FinishAllowance", "Roughing leaves this much on the part for the "
     "finishing pass."),
    ("App::PropertyDistance", "StockToLeave", "Material left on the part after finishing."),
    ("App::PropertyEnumeration", "Direction", "Which way the chuck turns while cutting."),
    ("App::PropertyLength", "GridStep", "Resolution of the part's map (along the part and round "
     "it). Smaller = more exact, slower."),
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
        obj.Strategy = STRATEGIES
        obj.Direction = DIRECTIONS

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
        obj.ChuckClearance = 2.0

    def opExecute(self, obj):
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
        H = wrapcut.radius_map(shapes, meshes, zs, na, r_stock)
        leave = obj.StockToLeave.Value
        Xf = wrapcut.tip_map(H, zs, na, radius, ball, leave)
        Xr = wrapcut.tip_map(H, zs, na, radius, ball, leave + obj.FinishAllowance.Value)

        # along the part: from the free end (high Z) toward the chuck, stopping clear of the jaws
        z_from, z_to = obj.FromZ.Value, obj.ToZ.Value
        if abs(z_from - z_to) < 1e-9:
            z_from, z_to = zhi, zlo
            chuck = getattr(job, "PolarChuck", None)
            if chuck is not None and not chuck.Shape.isNull():
                z_to = max(z_to, chuck.Shape.BoundBox.ZMax + obj.ChuckClearance.Value + radius)
        if z_from <= z_to:
            Path.Log.error("Polar Wrap: nothing to machine between Z %.2f and %.2f (the chuck "
                           "holds the rest)." % (z_from, z_to))
            return
        d = 2 * radius
        passes = wrapcut.helix_passes(
            Xr, Xf, zs, na, r_stock, z_from, z_to,
            max(obj.RoughStepOver, 1) / 100.0 * d, max(obj.StepOver, 1) / 100.0 * d,
            max(obj.StepDown.Value, 0.01), min(0.5, step * 2),
            roughing=obj.Strategy != "Finishing", finishing=obj.Strategy != "Roughing",
            ccw=obj.Direction == DIRECTIONS[0])

        safe = r_stock + obj.SafeDistance.Value
        feed, vfeed = self.horizFeed, self.vertFeed
        cmds = self.commandlist
        for p in passes:
            z0, th0, r0 = p[0]
            cmds.append(Path.Command("G0", {"X": safe * math.cos(th0), "Y": safe * math.sin(th0), "Z": z0}))
            cmds.append(Path.Command("G1", {"X": r0 * math.cos(th0), "Y": r0 * math.sin(th0), "Z": z0,
                                            "F": vfeed}))
            for z, th, r in p[1:]:
                cmds.append(Path.Command("G1", {"X": r * math.cos(th), "Y": r * math.sin(th), "Z": z,
                                                "F": feed}))
            z1, th1, _r1 = p[-1]
            cmds.append(Path.Command("G0", {"X": safe * math.cos(th1), "Y": safe * math.sin(th1), "Z": z1}))


def SetupProperties():
    return [name for _typ, name, _tip in PROPERTIES]


def Create(name, obj=None, parentJob=None):
    if obj is None:
        obj = App.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPolarWrap(obj, name, parentJob)
    return obj
