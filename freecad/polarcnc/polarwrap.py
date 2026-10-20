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
    ("App::PropertyLink", "AfterOperation", "The Polar Wrap operation that cut this part before this "
     "one (with another cutter): this one starts from what that one left, not from the whole bar. "
     "Empty = from the bar."),
    ("App::PropertyString", "ToolReport", "What this cutter leaves on the part (filled in when the "
     "path is made): the most it leaves and where, and the largest ball end that reaches every "
     "detail."),
)

REPORT_TOL = 0.05        # mm: left on the part more than asked, before the tool report says so
BALLS = (6.0, 5.0, 4.0, 3.0, 2.5, 2.0, 1.5, 1.2, 1.0, 0.8, 0.6, 0.5)     # ball end sizes tried


def tool_of(op):
    """(radius, ball end?) of an operation's cutter."""
    tool = getattr(getattr(op, "ToolController", None), "Tool", None)
    d = getattr(tool, "Diameter", None)
    d = d.Value if hasattr(d, "Value") else float(d or 0)
    ball = "ball" in str(getattr(tool, "ShapeType", "") or getattr(tool, "ShapeName", "")).lower()
    return d / 2.0, ball


def z_range(op, job, zlo, zhi, radius, warn=True):
    """(from, to) along the part: from the free end (high Z) toward the chuck, stopping clear of
    the jaws; FromZ = ToZ means automatic (the whole part, past its free end by the cutter
    radius)."""
    z_from, z_to = op.FromZ.Value, op.ToZ.Value
    if abs(z_from - z_to) < 1e-9:
        z_from, z_to = zhi + radius, zlo
    chuck = getattr(job, "PolarChuck", None)       # set by hand too: never down into the jaws
    if chuck is not None and not chuck.Shape.isNull():
        clear = chuck.Shape.BoundBox.ZMax + op.ChuckClearance.Value + radius
        if warn and z_to < clear - 1e-9 and abs(op.FromZ.Value - op.ToZ.Value) >= 1e-9:
            Path.Log.warning("Polar Wrap: To Z %.2f is in the jaws: it stops at Z %.2f." % (z_to, clear))
        z_to = max(z_to, clear)
    return z_from, z_to


def _say(pair):
    from . import policy
    return policy._say(pair)


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
        self._readonly(obj)

    def opOnDocumentRestored(self, obj):
        self.initOperation(obj)

    def _readonly(self, obj):
        try:
            obj.setEditorMode("ToolReport", 1)
        except Exception:
            pass

    def opSetDefaultValues(self, obj, job):
        obj.Strategy = STRATEGIES[0]
        obj.StepOver = 15
        obj.RoughStepOver = 50
        obj.StepDown = 1.0
        obj.FinishAllowance = 0.3
        obj.StockToLeave = 0
        obj.Direction = DIRECTIONS[0]
        obj.AfterOperation = None
        obj.GridStep = 0.25
        obj.SafeDistance = 5.0
        obj.AirFeedFactor = 3.0
        obj.ChuckClearance = 2.0

    def opExecute(self, obj):
        from .progress import Progress, Stopped
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

        z_from, z_to = z_range(obj, job, zlo, zhi, radius)
        if z_from <= z_to:
            Path.Log.error("Polar Wrap: nothing to machine between Z %.2f and %.2f (the chuck "
                           "holds the rest)." % (z_from, z_to))
            return
        rows = (zs >= z_to - 1e-9) & (zs <= z_from + 1e-9)

        # after another Polar Wrap with another cutter: start from what that one left
        start = None
        before = getattr(obj, "AfterOperation", None)
        if before is not None:
            start = self._left_by(obj, before, job, H, zs, na, zlo, zhi, r_stock, tick)
            if start is None:
                return
        if obj.Strategy == "Finishing":          # one helix may not take the whole depth
            top = start if start is not None else numpy.full_like(Xf, r_stock)
            deepest = float(numpy.max((top - Xf)[rows])) if rows.any() else 0.0
            allowed = obj.FinishAllowance.Value + obj.StepDown.Value + 1e-6
            if deepest > allowed:
                Path.Log.error("Polar Wrap: finishing alone would cut %.2f mm deep in one pass "
                               "(at most finish allowance + step down = %.2f). Use Roughing + "
                               "finishing (with After Operation set it roughs only what the cutter "
                               "before it left)." % (deepest, allowed))
                return
        d = 2 * radius
        passes = wrapcut.helix_passes(
            Xr, Xf, zs, na, r_stock, z_from, z_to,
            max(obj.RoughStepOver, 1) / 100.0 * d, max(obj.StepOver, 1) / 100.0 * d,
            # FIX 2.22.0: a written point at most ONE map cell apart (was two: min(0.5, step * 2)).
            # wrapcut.sample takes the highest of the 4 grid points round each written point,
            # so every grid point between two written points is seen by one of them only when
            # they are at most a cell apart. Two cells apart, a flat cutter cut 0.78 mm too deep
            # at the edge of a key along the bar (the machine moves straight between blocks).
            max(obj.StepDown.Value, 0.01), min(0.5, 0.99 * 2 * math.pi * r_stock / na),
            roughing=obj.Strategy != "Finishing", finishing=obj.Strategy != "Roughing",
            ccw=obj.Direction == DIRECTIONS[0], radius=radius,
            finish_lines=obj.FinishStyle == FINISH_STYLES[1], start=start)

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
        self._report(obj, H, Xf if obj.Strategy != "Roughing" else Xr, zs, na, rows, radius, ball,
                     leave if obj.Strategy != "Roughing" else leave + obj.FinishAllowance.Value, tick)

    def _left_by(self, obj, before, job, H, zs, na, zlo, zhi, r_stock, tick):
        """The material an earlier Polar Wrap left (its cutter's surface where it machined, the
        bar elsewhere), on this operation's map; None (with a message) if it cannot be used."""
        import numpy
        ops = list(getattr(getattr(job, "Operations", None), "Group", []))
        if before is obj or type(getattr(before, "Proxy", None)).__name__ != "ObjectPolarWrap" or \
                before not in ops:
            Path.Log.error("Polar Wrap: After Operation must be another Polar Wrap of this Job.")
            return None
        if ops.index(before) > ops.index(obj):
            Path.Log.error("Polar Wrap: After Operation '%s' comes after this one in the Job: move it "
                           "up, the machine runs them in that order." % before.Label)
            return None
        pr, pball = tool_of(before)
        if pr <= 0:
            Path.Log.error("Polar Wrap: '%s' has no cutter diameter." % before.Label)
            return None
        pleave = before.StockToLeave.Value
        if before.Strategy == "Roughing":
            pleave += before.FinishAllowance.Value
        Xp = wrapcut.tip_map(H, zs, na, pr, pball, pleave, tick)
        M = numpy.minimum(wrapcut.envelope(Xp, zs, na, pr, pball, tick), r_stock)
        p_from, p_to = z_range(before, job, zlo, zhi, pr, warn=False)
        M[(zs < p_to - 1e-9) | (zs > p_from + 1e-9)] = r_stock       # it did not go there
        return M

    def _report(self, obj, H, X, zs, na, rows, radius, ball, leave, tick):
        """What the cutter leaves on the part, and the largest ball end that gets down into every
        hollow: in the operation's Tool Report and the Report view."""
        try:
            # measured cell centre to cell centre: what really fits (the path itself keeps to
            # the safe side by half a cell)
            X = wrapcut.tip_map(H, zs, na, radius, ball, leave, tick, edge=0.0)
            _gap, corner, floor = wrapcut.leftover(H, X, zs, na, radius, ball, leave, rows, tick, edge=0.0)
            name = ("Ø%.1f %s" % (2 * radius, "ball" if ball else "flat"),
                    "Ø%.1f %s" % (2 * radius, "σφαιρικό" if ball else "επίπεδο"))

            def at(w):
                return float(zs[w[1]]), math.degrees(2 * math.pi * w[2] / na)
            if floor[0] > REPORT_TOL:
                z, c = at(floor)
                text = _say(("%s does not get down into a hollow: %.2f mm left at its bottom (Z %.1f, C %.0f)."
                             % (name[0], floor[0], z, c),
                             "Το %s δεν κατεβαίνει σε μια κοιλότητα: μένουν %.2f mm στον πάτο της (Z %.1f, C %.0f)."
                             % (name[1], floor[0], z, c)))
                if obj.Strategy != "Roughing":
                    text += " " + self._advice(H, zs, na, rows, radius, leave, tick)
            elif corner[0] > REPORT_TOL:
                # (how much a corner keeps is not given: on the map's cells it reads too high for
                # small cutters; what is always true is the cutter's own radius)
                text = _say(("%s gets down into every hollow; inside corners are rounded with its radius "
                             "(%.2f mm)." % (name[0], radius),
                             "Το %s κατεβαίνει σε κάθε κοιλότητα· οι εσωτερικές γωνίες στρογγυλεύουν με την "
                             "ακτίνα του (%.2f mm)." % (name[1], radius)))
            else:
                text = _say(("%s reaches every detail." % name[0], "Το %s φτάνει κάθε λεπτομέρεια." % name[1]))
            obj.ToolReport = text
            (App.Console.PrintWarning if floor[0] > REPORT_TOL else App.Console.PrintMessage)(
                "Polar Wrap (%s): %s\n" % (obj.Label, text))
        except Exception as e:
            App.Console.PrintLog("Polar Wrap: tool report: %s\n" % e)

    def _advice(self, H, zs, na, rows, radius, leave, tick):
        """The largest ball end (of the usual sizes, smaller than this cutter) that gets down into
        every hollow (searched by halving: a smaller ball never reaches less)."""
        sizes = [d for d in BALLS if d < 2 * radius - 1e-9]
        if not sizes:
            return ""

        def fits(d):
            Xb = wrapcut.tip_map(H, zs, na, d / 2, True, leave, tick, edge=0.0)
            return wrapcut.leftover(H, Xb, zs, na, d / 2, True, leave, rows, tick, edge=0.0)[2][0] <= REPORT_TOL
        lo, hi = 0, len(sizes) - 1          # sizes from large to small: find the first that fits
        if not fits(sizes[hi]):
            return _say(("Even a Ø%.1f ball end does not get down there: the detail is finer." % sizes[hi],
                         "Ούτε σφαιρικό Ø%.1f κατεβαίνει εκεί: η λεπτομέρεια είναι πιο ψιλή." % sizes[hi]))
        while lo < hi:
            mid = (lo + hi) // 2
            if fits(sizes[mid]):
                hi = mid
            else:
                lo = mid + 1
        return _say(("A ball end Ø%.1f (or smaller) gets down into every hollow: finish with it, After "
                     "Operation = this one." % sizes[lo],
                     "Σφαιρικό Ø%.1f (ή μικρότερο) κατεβαίνει σε κάθε κοιλότητα: φινίρισμα με αυτό, "
                     "Μετά από = αυτή η κατεργασία." % sizes[lo]))

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
