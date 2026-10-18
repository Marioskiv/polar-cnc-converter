# FreeCAD addon — technical notes

How the FreeCAD addon (`freecad/`) is built and tested. For users: [freecad/README.md](../freecad/README.md).

## One converter, two front ends

The addon does **not** contain its own converter. `freecad/polarcnc/bridge.py` loads `src/core/*.js` — the
files the web page loads, in the same order — into Qt's JavaScript engine (`QJSEngine`, part of the Qt that
ships with FreeCAD) and calls `PolarCNC.converter.convert()`. So:

- a change to the converter reaches the web page and FreeCAD at the same time;
- nothing has to be installed: FreeCAD's bundled Python on Windows has no `ssl` module, so pip packages are not
  an option for an addon;
- the golden set (`tests/fixtures/golden.json`, 144 outputs) is converted inside FreeCAD by
  `tests/freecad/polar_post_test.py` and must be byte-for-byte identical.

Qt reports `qt.qml.usedbeforedeclared` for every `var` used above its declaration (valid JavaScript); the
bridge turns that logging category off, or it fills FreeCAD's report view on every post.

## How it plugs into CAM

| Piece | File | What it does |
|---|---|---|
| post-processor | `freecad/posts/polar_linuxcnc_post.py` | a legacy-style post (`export(objectslist, filename, argstring)`), so it appears in the Job's *Processor* list. It runs a **fresh copy** of FreeCAD's `linuxcnc_legacy_post` (that post keeps its settings in module globals) and converts its output. Any refusal: message box + `None`, so Post Process writes no file |
| machine settings | `freecad/polarcnc/machine.py` | Job properties, group *Polar CNC*: `PolarXMax` (required, 0 = not set), `PolarCuttingSide`, `PolarPastCentre`, `PolarProfile` (the web page's profile file). Builds the converter options; nothing is guessed |
| command + toolbar | `freecad/polarcnc/gui.py` | *Machining type* (`PolarCNC_MachineSettings`): Ordinary / Polar / Wrap in one transaction (Cancel aborts it); Polar and Wrap add the properties and pick the post, Ordinary removes them and restores `PolarPreviousPost`. `policy.WRAP_BLOCKED` greys out every CAM operation in a Wrap Job. The toolbar is created through `BaseApp/Workbench/CAMWorkbench/Toolbar/PolarCNC` (the same mechanism as Tools → Customize) |
| polar Job policy | `freecad/polarcnc/policy.py` | greys out 3D operations and Probe while the current Job is polar, by wrapping `IsActive` of their Python command objects (`Path.Op.Gui.<Op>.Command`; the original is kept and called) — no toolbar rebuild, works in toolbars, menus and shortcuts. Sets the Job's SetupSheet operation defaults (`setFromTemplate`). A document observer warns (deferred to the next event-loop turn: CAM sets temporary values while creating an operation) about warned operations and line-by-line patterns |
| Polar Face | `freecad/polarcnc/polarface.py`, `polarface_gui.py` | an `ObjectOp` subclass. Per depth: stock section (`slice` + `FaceMakerBullseye`, any stock shape, holes kept) minus the part at or above that depth (`TechDraw.findShapeOutline`). Circles round the origin clipped to it (`Part.makeCircle(r).common(region)`), written as origin-centred G2/G3 (I, J = −start). The uncut material is followed on a 0.25 mm grid (`Raster`), updated after every cutting move; links go on round the same circle, each stretch at cutting feed if the cutter reaches uncut material within its radius + grid, else fast; or the cutter lifts, whichever is quicker (rough time with the tool controller's feeds). Its own `ViewProvider` subclass (CAM's selection table and icon path do not know addon operations), its own `create()`, SetupSheet registration as `PolarFace`. Tested independently of the planner (moves replayed on a grid) in `tests/freecad/polarface_geometry_test.py` |
| chuck | `freecad/polarcnc/chuck.py` | `Chuck` and `Clamp` FeaturePython objects. Links go one way only (Job → chuck → stock, chuck → clamps, Polar Face → chuck), so changing the chuck re-makes Polar Face and there is no dependency cycle; a clamp is built by the chuck, the chuck is found from the Job through `InList`. Everything turns together, so in the part frame jaws and clamps are fixed obstacles: Polar Face adds the chuck's outline above each depth (grown by *ChuckClearance*) to the part it must not touch. Jaws close on the stock along a ray (`contact_radius`); the chuck face sits at stock bottom + grip − jaw height. Tested in `tests/freecad/chuck_test.py` (round in 3-jaw, square in 4-jaw, off-centre square refused by the 3-jaw note, plate with 3 clamps on a faceplate) |
| collision | `freecad/polarcnc/collision.py` | every move of every operation (G0–G3, arcs sampled every 0.5 mm) with the cutter as a cylinder from its tip up, against the outline and top of the chuck body, each jaw and clamp (`TechDraw.findShapeOutline` per solid, numpy distances). A hit: a warning on the operation and Post Process refuses |
| Polar Wrap | `freecad/polarcnc/wrapcut.py`, `polarwrap.py`, `polarwrap_gui.py` | Wrap Jobs (router radial). `radius_map`: the model's outermost radius on a (z, angle) grid from slices (`Shape.slice`, `Mesh.crossSections`), two slices per row half a step apart (a slice exactly on a flat face is ambiguous: solid and mesh pick opposite sides), max per angle cell; `tip_map`: radial drop-cutter (flat or ball) measured from each cell's near edge, so the cutter is never in the part between grid points; `helix_passes`: roughing layers and a finishing helix. The path is written round the real part; `program.unroll` turns it into the converter's wrap input (X = z, Y = unwound angle x r0, Z = r - r0) |
| program | `freecad/polarcnc/program.py` | the Job's milling program (a fresh copy of FreeCAD's LinuxCNC post) and its polar conversion; used by the post and the simulator, so both see the same program |
| simulator | `freecad/polarcnc/simulator.py` | converts the Job like Post Process, reads the polar program back with the web simulator's parser (`src/core/polar-parser.js`, joint-space interpolation as LinuxCNC does) and plays it in the 3D view with Coin nodes: a turning group (chuck, model and stock tessellated, path) and a cutter that only moves in X and Z. All document objects are hidden while it runs and every visibility is put back on close (hiding a group also hides its children, so states are read first). `View3D.saveImage` renders without these nodes; tests capture the window |
| help | `freecad/polarcnc/help.py`, `freecad/help/help.json`, `freecad/help/img/*.gif` + `*.json` | own MIT code, no packages. One event filter, put only on the *Polar CNC* toolbar buttons (re-put on every CAM activation, the toolbar is rebuilt): hover 500 ms → a `Qt.ToolTip` frame (title, `QMovie` animation, numbered steps, warning); the plain tooltip is suppressed while popups are on. Task-panel fields get a **?** `QToolButton` (`add_row`), no event filters on dialogs. `error_card()` matches the message against `errors[].re` in help.json (first match, else a generic card) and shows why/what to do with the message; it falls back to `QMessageBox` if the card cannot be built. Language: parameter `Mod/PolarCNC/HelpLanguage` (`auto` = Greek if FreeCAD's language is Greek). Animations: `tools/help_gifs/record.py` in a real FreeCAD (`QT_SCALE_FACTOR=1.5`, one scene per start, the addon's own objects and simulator), `compose.py` (Pillow, only for the tool): 1248 × 750, one shared 256-colour palette, the button card and a step badge, no words; `<name>.json` beside it lists the step of every frame, and the popup (`help._Player`) draws each frame smoothly at the card size and lights that step |
| one-click chuck | `freecad/polarcnc/setup.py`, `gui.ChuckCommand`, `dialogs.ChuckSetupDialog` | the picked face (on the Job's model copy, its original or the stock) gives the outward normal (tested with `isInside` just beside the face); the model copies (and a stock that is not *FromBase*) are turned so it points to −Z, moved so the stock is on the axis (centre of a round section, else the middle of the outline) with its top at Z0. `suggest()` picks from `MyChucks` (round + fits the catalogue grip range → self-centring, else the 4-jaw independent) and the grip = stock under the part, capped at the jaw height. All in one transaction (Cancel aborts it). The chuck and clamps have `ViewProviderSteel` (display mode "Flat Lines"): without it a script-made FeaturePython is not drawn |
| speed | `polarface.Raster`, `wrapcut.radius_map` | Polar Face: a grid move looks only at the grid window of its bounding box (`near`), rides look at the ring of points `|rho − r| < reach` (sorted radii), the exact keep-out check is one boolean per run of moves. Polar Wrap: solids are meshed once (`MeshPart`, 2 µm deflection) and sliced in one `crossSections` call; radii within 2× the deflection of a row's maximum take the maximum, then + deflection: never below the part. Both show FreeCAD's progress bar; Esc raises `Stopped` |
| start-up | `freecad/InitGui.py`, `package.xml` | `package.xml` at the repository root declares a workbench item in the subdirectory `freecad` (FreeCAD runs its `InitGui.py`) |

**FreeCAD 26.3 facts found while building it**

- Job → *Processor* lists **legacy** posts only (`allEnabledLegacyPostProcessors`); class-based "machine" posts
  are used through a Machine definition. Hence the legacy-style post.
- 26.3 passes posts `Postable` wrappers, not document objects; the real object is in `.source`
  (`Path/Post/PostList.py`).
- `package.xml` can declare post-processor directories. 26.3 looks for the content key `"Postprocessor"` (capital
  P), and `FreeCAD.Metadata` keeps tag names exactly as written, so the tag must be `<Postprocessor>`; a lowercase
  `<postprocessor>` is silently ignored (`Path/Preferences.py`, `_scan_addon_post_dirs`, while machines use the
  lowercase `<machine>`). The addon also calls `Path.Preferences.addAddonPostPath()` at start-up.
- SetupSheet operation defaults are looked up by the name the operation was created with (`Op/Base.py`,
  `setOperationProperties(obj, name)`): the toolbar commands use `"MillFacing"`, `"Pocket Shape"`, …; an operation
  created from Python under another name gets none of them.
- MillFacing (26.3) slices the stock and then faces its bounding rectangle (`Op/MillFacing.py`, `get_angled_polygon`);
  `spiral_facing` only does rectangles. Measured with `Path.getClearedArea`: on round stock R30, 40 % of the
  cleared area is outside the stock. `PocketBase.opExecute` returns nothing without Base geometry, so MillFace /
  Pocket with no face selected make no path.
- `TechDraw.findShapeOutline` of a shape with several separate solids returns the outline of one of them, and
  `makeOffset2D` of a compound of separate faces offsets only the first: Polar Face builds one outline per solid
  and grows faces one by one (`grow`).
- Two objects that link each other (`PropertyLink` both ways) make a dependency cycle: `OutListRecursive` raises
  "cyclic dependency detected" and recomputes go wrong. Tests calling `obj.recompute()` one by one do not show it;
  `tests/freecad/chuck_test.py` checks `OutListRecursive`.
- A new operation's task panel deletes the operation on Cancel (`deleteOnReject`); tests press OK.
- Workbench manipulators are applied only when a workbench is (re)activated, and re-applying them rebuilds every
  toolbar (and puts restored buttons at the end): unsuitable for following the selected Job.
- FreeCAD's own rotary pieces, for the wrap / 4th-axis work to come: `Path/Dressup/Gui/AxisMap.py` maps Y to A
  but writes the feed as `F / R` in degrees with G94 — wrong on moves that combine a linear axis with A.
  `Path/Op/RotarySurface.py` (experimental, needs OpenCamLib) with the generators
  `Path/Base/Generator/rotary_*.py` does continuous 4-axis surfacing.

## Testing

```bash
npm test                                          # the converter, as always
FREECAD=/path/to/bin/freecad sh tests/freecad/run.sh   # the addon, in a real FreeCAD
```

`tests/freecad/run.sh` runs one FreeCAD start per test (one task dialog per start): `polar_post_test.py`,
`simulator_test.py` (cutter position in both views, playback, everything hidden and restored, screenshots),
`polarface_geometry_test.py` (FreeCADCmd), `polarface_test.py`, `chuck_test.py`, `wrapcut_geometry_test.py`,
`wrap_test.py`, `setup_test.py` (the one-click chuck), `ops_test.py` (every usual operation in a polar Job, end
to end) and `help_test.py` (popups on the toolbar, field help, error cards, both languages). Tests that
expect a refusal catch the error card (`common.catch_messages`) instead of letting it block.
It makes a throw-away FreeCAD user folder with this repository linked as the PolarCNC
addon, runs `polar_post_test.py` under `xvfb-run`, and then converts FreeCAD's own LinuxCNC output with the
Node converter (`compare.js`): the post's output must be the same. The test checks that the post is offered
for Jobs, that the command adds the settings without guessing X Max, that a Job without X Max and a tool
controller without a feed are refused with no file written, that the output is polar (G93, G8, C moves, no Y,
X within X Max), and the golden set inside FreeCAD.

Lessons carried over from other FreeCAD addon work (FreeCAD 26.3):

- Never wrap short-lived widgets in Python (`findChildren` over a task dialog, event filters on dialog fields):
  stale PySide wrappers crashed FreeCAD when the dialog closed.
- Opening and closing many CAM task dialogs from one script crashes 26.3 even without any addon: test one
  dialog per FreeCAD start. Close a dialog the way Cancel does: `Gui.Control.activeTaskDialog().reject()`.
- Everything that runs at start-up is wrapped in `try/except`: an addon must never stop FreeCAD from starting.
- Bump `<version>` in `package.xml` on every release, or the Addon Manager offers no update.

## Open items

- **Jaws in the CAM at their real angle.** The cutter is zeroed on the stock face, so heights are right; where
  the jaws are round the axis is not: *First jaw angle* is a CAM setting with nothing on the machine tied to it.
  Plan: a known start point for C (C0 at a reference that LinuxCNC knows, e.g. a mark or home on the chuck) so the
  jaws in the CAM match the jaws on the machine.
- Spindle head / collet nut against the turning jaws (needs the nut diameter and the cutter stick-out).
- The C axis max velocity from the machine's `.ini`, for the near-centre time estimate.
- Wrap is done (Polar Wrap). Still open: Kiri:Moto-style XYZA input, and 4-axis.
- Stepped jaws (the real K72 jaws have steps): needs a photo or the sizes of the steps.
- An axis-layout helper on the web page, so that others can describe their own machine layout.
- Asked to keep for later (Marios, 2.17.0): C0 tied to the jaws, stepped K72 jaws, the axis-layout helper,
  the C max velocity from the `.ini`.
- Help animations: re-record with `tools/help_gifs` when a command's look changes (the texts are in
  `freecad/help/help.json`, en and el).
- SAN OU K12-125 and 3-jaw 125 presets: jaw length / width (and the 3-jaw's jaw height) are scaled from catalogue
  drawings, not measured. K72-125 is measured.

