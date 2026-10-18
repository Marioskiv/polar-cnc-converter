# Polar CNC — simulator in FreeCAD's 3D view.
#
# Plays the POLAR program (what goes to the machine), not the CAM paths: the Job is converted
# exactly as Post Process does, and the program is read back by the web simulator's own parser
# (src/core/polar-parser.js), which interpolates every block in joint space as LinuxCNC does.
# Machine view: the part turns with the chuck (C) and the cutter only moves in X and Z.
# Part view: the part stands still and the cutter moves over it — compare with the CAM paths.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

import bisect
import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from . import bridge, program

SPEEDS = (("1×", 1.0), ("5×", 5.0), ("20×", 20.0), ("100×", 100.0), ("500×", 500.0))
CUT_RGB = (1.0, 0.45, 0.0)
PATH_RGB = (0.55, 0.6, 0.7)
RAPID_RGB = (0.85, 0.15, 0.15)


class Motion:
    """The program as a time line: joint positions (r, c, z) and the time each point is reached."""

    def __init__(self, data):
        self.r, self.c, self.z = data["r"], data["c"], data["z"]
        self.rapid, self.line = data["rapid"], data["line"]
        tools = [d for d in data["toolD"] if d]
        self.tool_d = tools[0] if tools else None
        self.t = []
        acc = 0.0
        for i, d in enumerate(data["dur"]):
            acc += d if i else 0.0
            self.t.append(acc)
        self.total = acc
        # the fastest chuck speed a cutting block asks for (the machine may be slower)
        peak = 0.0
        for i in range(1, len(self.t)):
            dt = self.t[i] - self.t[i - 1]
            if not self.rapid[i] and dt > 0:
                peak = max(peak, abs(self.c[i] - self.c[i - 1]) / dt)
        self.peak_c = peak
        self.c_span = (max(self.c) - min(self.c)) if self.c else 0.0

    def __len__(self):
        return len(self.t)

    def at(self, t):
        """(index of the point being moved to, r, c, z) at program time t."""
        n = len(self.t)
        i = min(max(bisect.bisect_left(self.t, t), 1), n - 1) if n > 1 else 0
        if n < 2:
            return 0, self.r[0], self.c[0], self.z[0]
        t0, t1 = self.t[i - 1], self.t[i]
        f = 1.0 if t1 <= t0 else min(max((t - t0) / (t1 - t0), 0.0), 1.0)
        lerp = lambda a: a[i - 1] + (a[i] - a[i - 1]) * f
        return i, lerp(self.r), lerp(self.c), lerp(self.z)

    def xyz(self, i):
        a = math.radians(self.c[i])
        return (self.r[i] * math.cos(a), self.r[i] * math.sin(a), self.z[i])


def _mesh_node(shape, rgb, transparency=0.0, tol=0.2):
    from pivy import coin
    sep = coin.SoSeparator()
    mat = coin.SoMaterial()
    mat.diffuseColor.setValue(*rgb)
    mat.transparency.setValue(transparency)
    sep.addChild(mat)
    hints = coin.SoShapeHints()
    hints.vertexOrdering.setValue(coin.SoShapeHints.COUNTERCLOCKWISE)
    hints.shapeType.setValue(coin.SoShapeHints.UNKNOWN_SHAPE_TYPE)
    sep.addChild(hints)
    pts, tris = shape.tessellate(tol)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
    faces = coin.SoIndexedFaceSet()
    idx = []
    for a, b, c in tris:
        idx.extend((a, b, c, -1))
    faces.coordIndex.setValues(0, len(idx), idx)
    sep.addChild(coords)
    sep.addChild(faces)
    return sep


def _polyline(points, rgb, width):
    from pivy import coin
    sep = coin.SoSeparator()
    mat = coin.SoMaterial()
    mat.diffuseColor.setValue(*rgb)
    mat.emissiveColor.setValue(*rgb)
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(width)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    lines = coin.SoLineSet()
    lines.numVertices.setValue(len(points))
    for n in (mat, style, coords, lines):
        sep.addChild(n)
    return sep, lines


class Scene:
    """The Coin nodes of the simulation: a turning part group (chuck, stock, model, path) and a
    cutter that only moves in X and Z."""

    def __init__(self, job, motion, opts=None):
        from pivy import coin
        self.motion = motion
        self.wrap = (opts or {}).get("layout") == "wrap"
        self.root = coin.SoSeparator()
        self.part = coin.SoSeparator()
        self.turn = coin.SoRotationXYZ()
        self.turn.axis.setValue(coin.SoRotationXYZ.Z)
        self.part.addChild(self.turn)

        stock = job.Stock.Shape if getattr(job, "Stock", None) else None
        if self.wrap:       # the Job is drawn unrolled: show the cylinder it is wrapped on
            stock, models = None, []
            self._wrap_cylinder(opts["wrapRadius"])
        bb = stock.BoundBox if stock and not stock.isNull() else None
        if not self.wrap:
            models = [m.Shape for m in job.Model.Group if hasattr(m, "Shape") and not m.Shape.isNull()]
        if bb is None and models:
            bb = models[0].BoundBox
            for s in models[1:]:
                bb.add(s.BoundBox)
        radius = max(abs(bb.XMin), abs(bb.XMax), abs(bb.YMin), abs(bb.YMax)) if bb else 50.0
        zbot = bb.ZMin if bb else 0.0
        # the chuck in a switch: left out while the view is framed on the part
        self.chuck_sw = coin.SoSwitch()
        self.chuck_sw.whichChild.setValue(0)
        holder = coin.SoSeparator()
        self.chuck_sw.addChild(holder)
        chuck = getattr(job, "PolarChuck", None)
        if self.wrap and (chuck is None or chuck.Shape.isNull()):
            pass                                                  # no chuck set up for this Job
        elif chuck is not None and not chuck.Shape.isNull():      # the Job's own chuck / faceplate
            from . import chuck as chuckmod
            pieces, _notes = chuckmod.build_parts(chuck)
            if pieces:
                holder.addChild(_mesh_node(pieces[0], (0.62, 0.65, 0.7), transparency=0.55, tol=0.5))
                for piece in pieces[1:]:                          # jaws and clamps
                    holder.addChild(_mesh_node(piece, (0.8, 0.18, 0.18), tol=0.3))
        else:
            holder.addChild(self._chuck(radius, zbot))
        self.part.addChild(self.chuck_sw)
        for shape in models:
            self.part.addChild(_mesh_node(shape, (0.62, 0.66, 0.74)))
        if stock and not stock.isNull():
            self.part.addChild(_mesh_node(stock, (0.85, 0.8, 0.6), transparency=0.75))

        pts = [motion.xyz(i) for i in range(len(motion))]
        self.all_sw = coin.SoSwitch()
        all_sep, _ = _polyline(pts, PATH_RGB, 1)
        self.all_sw.addChild(all_sep)
        self.all_sw.whichChild.setValue(0)
        self.part.addChild(self.all_sw)
        self.done_sw = coin.SoSwitch()
        done_sep, self.done = _polyline(pts, CUT_RGB, 3)
        self.done_sw.addChild(done_sep)
        self.part.addChild(self.done_sw)
        self.root.addChild(self.part)

        self.tool = coin.SoSeparator()
        self.tool_at = coin.SoTranslation()
        self.tool.addChild(self.tool_at)
        self.tool_turn = coin.SoRotationXYZ()          # part view: the cutter's angle
        self.tool_turn.axis.setValue(coin.SoRotationXYZ.Z)
        self.tool.addChild(self.tool_turn)
        if self.wrap:                                   # the router radial: its body along +X
            lie = coin.SoRotationXYZ()
            lie.axis.setValue(coin.SoRotationXYZ.Y)
            lie.angle.setValue(math.pi / 2)
            self.tool.addChild(lie)
        self.tool_mat = coin.SoMaterial()
        self.tool.addChild(self.tool_mat)
        self.tool.addChild(self._cutter(motion.tool_d or 6.0))
        self.root.addChild(self.tool)
        self.machine_view = True

    def _wrap_cylinder(self, radius):
        """The cylinder of the wrap radius along the program's Z range (part of the turning group)."""
        from pivy import coin
        zs = [self.motion.z[i] for i in range(len(self.motion)) if not self.motion.rapid[i]] or [0.0, 1.0]
        z0, z1 = min(zs), max(zs)
        margin = max((z1 - z0) * 0.1, radius * 0.2, 2.0)
        sep = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor.setValue(0.85, 0.8, 0.6)
        mat.transparency.setValue(0.6)
        sep.addChild(mat)
        cx = coin.SoComplexity()
        cx.value.setValue(0.9)
        sep.addChild(cx)
        tr = coin.SoTransform()
        tr.translation.setValue(0, 0, (z0 + z1) / 2)
        tr.rotation.setValue(coin.SbVec3f(1, 0, 0), math.pi / 2)   # cylinder axis Y -> Z
        sep.addChild(tr)
        cyl = coin.SoCylinder()
        cyl.radius.setValue(radius)
        cyl.height.setValue(z1 - z0 + 2 * margin)
        sep.addChild(cyl)
        self.part.addChild(sep)

    @staticmethod
    def _chuck(radius, zbot):
        from pivy import coin
        sep = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor.setValue(0.5, 0.53, 0.58)
        sep.addChild(mat)
        cx = coin.SoComplexity()
        cx.value.setValue(0.9)                   # round, not an octagon
        sep.addChild(cx)
        r = radius * 1.1
        body = coin.SoSeparator()
        tr = coin.SoTransform()
        tr.translation.setValue(0, 0, zbot - 8)
        tr.rotation.setValue(coin.SbVec3f(1, 0, 0), math.pi / 2)   # cylinder axis Y -> Z
        body.addChild(tr)
        cyl = coin.SoCylinder()
        cyl.radius.setValue(r)
        cyl.height.setValue(16)
        body.addChild(cyl)
        sep.addChild(body)
        for k in range(3):                       # three jaws, so the turning is easy to see
            jaw = coin.SoSeparator()
            a = 2 * math.pi * k / 3
            t = coin.SoTransform()
            t.translation.setValue((r * 0.92) * math.cos(a), (r * 0.92) * math.sin(a), zbot + 4)
            t.rotation.setValue(coin.SbVec3f(0, 0, 1), a)
            jaw.addChild(t)
            jm = coin.SoMaterial()
            jm.diffuseColor.setValue(0.75, 0.2, 0.2)
            jaw.addChild(jm)
            cube = coin.SoCube()
            cube.width.setValue(r * 0.16)
            cube.height.setValue(r * 0.1)
            cube.depth.setValue(8)
            jaw.addChild(cube)
            sep.addChild(jaw)
        return sep

    @staticmethod
    def _cutter(d):
        from pivy import coin
        sep = coin.SoSeparator()
        for z0, h, rad, rgb in ((0, 20, d / 2, (0.85, 0.85, 0.9)), (20, 40, max(d / 2, 3) * 1.05,
                                                                       (0.45, 0.47, 0.52))):
            part = coin.SoSeparator()
            tr = coin.SoTransform()
            tr.translation.setValue(0, 0, z0 + h / 2)
            tr.rotation.setValue(coin.SbVec3f(1, 0, 0), math.pi / 2)
            part.addChild(tr)
            m = coin.SoMaterial()
            m.diffuseColor.setValue(*rgb)
            part.addChild(m)
            c = coin.SoCylinder()
            c.radius.setValue(rad)
            c.height.setValue(h)
            part.addChild(c)
            sep.addChild(part)
        return sep

    def show(self, t):
        i, r, c, z = self.motion.at(t)
        if self.machine_view:
            self.turn.angle.setValue(-math.radians(c))   # the part turns; its point at C faces +X
            self.tool_at.translation.setValue(r, 0, z)
            self.tool_turn.angle.setValue(0)
        else:
            self.turn.angle.setValue(0)
            a = math.radians(c)
            self.tool_at.translation.setValue(r * math.cos(a), r * math.sin(a), z)
            self.tool_turn.angle.setValue(a if self.wrap else 0)
        self.tool_mat.diffuseColor.setValue(*(RAPID_RGB if self.motion.rapid[i] else (1, 1, 1)))
        self.done.numVertices.setValue(max(i, 1))
        self.done_sw.whichChild.setValue(0 if i >= 2 else -1)
        return i, r, c, z


class TaskPanel:
    def __init__(self, job, polar_text, opts):
        self.job = job
        self.motion = Motion(bridge.parse(polar_text, opts))
        self.scene = Scene(job, self.motion, opts)
        self.view = Gui.ActiveDocument.ActiveView
        self.view.getSceneGraph().addChild(self.scene.root)
        try:     # framed on the part (not on the whole chuck), while the part is still shown
            self.scene.chuck_sw.whichChild.setValue(-1)
            self.view.viewIsometric()
            self.view.fitAll()
        except Exception:
            pass
        self.scene.chuck_sw.whichChild.setValue(0)
        # everything of the document is hidden while the simulation shows its own turning copy
        # (the part, the stock and the paths would otherwise stand still on top of it)
        # (all states are read first: hiding a group such as the Job also hides its children)
        self._visibility = [(o, o.ViewObject.Visibility) for o in job.Document.Objects
                            if getattr(o, "ViewObject", None) is not None]
        for obj, shown in self._visibility:
            if shown:
                obj.ViewObject.Visibility = False
        self.t = 0.0
        self.playing = False
        self._last = None
        self.timer = QtCore.QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.form = self._build_form()
        self._show()

    # ---- form ----
    def _build_form(self):
        w = QtGui.QWidget()
        w.setWindowTitle("Polar simulation")
        lay = QtGui.QVBoxLayout(w)
        m = self.motion
        summary = QtGui.QLabel(
            "Program time %s · %d points · chuck turns %.1f · fastest chuck speed asked %.0f°/s"
            % (_hms(m.total), len(m), m.c_span / 360.0, m.peak_c))
        summary.setWordWrap(True)
        lay.addWidget(summary)
        self.info = QtGui.QLabel()
        self.info.setStyleSheet("font-family: monospace;")
        lay.addWidget(self.info)
        self.slider = QtGui.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._scrub)
        lay.addWidget(self.slider)
        row = QtGui.QHBoxLayout()
        self.b_start = QtGui.QPushButton("⏮")
        self.b_play = QtGui.QPushButton("▶")
        self.b_end = QtGui.QPushButton("⏭")
        self.b_start.clicked.connect(lambda: self._jump(0.0))
        self.b_play.clicked.connect(self._toggle)
        self.b_end.clicked.connect(lambda: self._jump(self.motion.total))
        for b in (self.b_start, self.b_play, self.b_end):
            row.addWidget(b)
        self.speed = QtGui.QComboBox()
        for name, _v in SPEEDS:
            self.speed.addItem(name)
        self.speed.setCurrentIndex(2)
        row.addWidget(QtGui.QLabel("Speed"))
        row.addWidget(self.speed)
        lay.addLayout(row)
        self.machine = QtGui.QRadioButton("Machine view: the chuck turns, the cutter moves in X and Z")
        self.partv = QtGui.QRadioButton("Part view: the part stands still (compare with CAM)")
        self.machine.setChecked(True)
        self.machine.toggled.connect(self._view_mode)
        lay.addWidget(self.machine)
        lay.addWidget(self.partv)
        self.whole = QtGui.QCheckBox("Show the whole path")
        self.whole.setChecked(True)
        self.whole.toggled.connect(lambda on: self.scene.all_sw.whichChild.setValue(0 if on else -1))
        lay.addWidget(self.whole)
        note = QtGui.QLabel("Times are the program's own (G93). Near the centre a real machine is "
                            "slower: its controller limits the chuck speed.")
        note.setWordWrap(True)
        lay.addWidget(note)
        return w

    # ---- playback ----
    def _show(self):
        i, r, c, z = self.scene.show(self.t)
        m = self.motion
        dt = m.t[i] - m.t[i - 1] if i > 0 else 0.0
        speed = abs(m.c[i] - m.c[i - 1]) / dt if i > 0 and dt > 0 else 0.0
        self.info.setText("%s  %s   line %d\nX %8.3f   C %9.2f°   Z %8.3f\nchuck %6.0f°/s"
                          % (_hms(self.t), "rapid" if m.rapid[i] else "cut  ", m.line[i],
                             r, c, z, speed))
        self.slider.blockSignals(True)
        self.slider.setValue(int(1000 * self.t / m.total) if m.total > 0 else 0)
        self.slider.blockSignals(False)

    def _tick(self):
        now = time.monotonic()
        if self._last is not None:
            self.t += (now - self._last) * SPEEDS[self.speed.currentIndex()][1]
        self._last = now
        if self.t >= self.motion.total:
            self.t = self.motion.total
            self._stop()
        self._show()

    def _toggle(self):
        if self.playing:
            self._stop()
        else:
            if self.t >= self.motion.total:
                self.t = 0.0
            self.playing = True
            self._last = None
            self.b_play.setText("⏸")
            self.timer.start()

    def _stop(self):
        self.playing = False
        self.timer.stop()
        self.b_play.setText("▶")

    def _jump(self, t):
        self.t = t
        self._show()

    def _scrub(self, v):
        self.t = self.motion.total * v / 1000.0
        self._show()

    def _view_mode(self, machine_on):
        self.scene.machine_view = machine_on
        self._show()

    # ---- task dialog ----
    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.StandardButton.Close

    def _cleanup(self):
        self._stop()
        try:
            self.view.getSceneGraph().removeChild(self.scene.root)
        except Exception:
            pass
        for obj, shown in self._visibility:      # every object back exactly as it was
            try:
                obj.ViewObject.Visibility = shown
            except Exception:
                pass
        self._visibility = []

    def reject(self):
        self._cleanup()
        Gui.Control.closeDialog()
        return True

    def accept(self):
        return self.reject()


def _hms(s):
    s = int(round(s))
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


def open_for(job):
    """Convert the Job like Post Process and open the simulator. Problems -> a message."""
    try:
        text, opts = program.polar(job)
    except (ValueError, OSError, bridge.ConverterError) as e:
        QtGui.QMessageBox.warning(None, "Polar CNC", "Cannot simulate: %s" % e)
        return None
    panel = TaskPanel(job, text, opts)
    Gui.Control.showDialog(panel)
    return panel
