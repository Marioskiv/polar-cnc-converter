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
| command + toolbar | `freecad/polarcnc/gui.py` | *Polar machine settings*: adds the properties to the selected Job and picks the post. The toolbar is created through `BaseApp/Workbench/CAMWorkbench/Toolbar/PolarCNC` (the same mechanism as Tools → Customize) |
| start-up | `freecad/InitGui.py`, `package.xml` | `package.xml` at the repository root declares a workbench item in the subdirectory `freecad` (FreeCAD runs its `InitGui.py`) |

**FreeCAD 26.3 facts found while building it**

- Job → *Processor* lists **legacy** posts only (`allEnabledLegacyPostProcessors`); class-based "machine" posts
  are used through a Machine definition. Hence the legacy-style post.
- 26.3 passes posts `Postable` wrappers, not document objects; the real object is in `.source`
  (`Path/Post/PostList.py`).
- `package.xml` can declare `<postprocessor>` directories, but 26.3 looks for the key `"Postprocessor"` while
  `FreeCAD.Metadata.Content` returns `"postprocessor"`, so the declaration alone is never found
  (`Path/Preferences.py`, `_scan_addon_post_dirs`). The addon calls `Path.Preferences.addAddonPostPath()` at
  start-up instead; the declaration stays for versions where the scan works.
- FreeCAD's own rotary pieces, for the wrap / 4th-axis work to come: `Path/Dressup/Gui/AxisMap.py` maps Y to A
  but writes the feed as `F / R` in degrees with G94 — wrong on moves that combine a linear axis with A.
  `Path/Op/RotarySurface.py` (experimental, needs OpenCamLib) with the generators
  `Path/Base/Generator/rotary_*.py` does continuous 4-axis surfacing.

## Testing

```bash
npm test                                          # the converter, as always
FREECAD=/path/to/bin/freecad sh tests/freecad/run.sh   # the addon, in a real FreeCAD
```

`tests/freecad/run.sh` makes a throw-away FreeCAD user folder with this repository linked as the PolarCNC
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
