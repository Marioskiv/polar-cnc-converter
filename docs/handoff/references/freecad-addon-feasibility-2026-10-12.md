# FreeCAD addon "Polar XZC" — feasibility test 2026-10-12 (prototype, nothing in the repo changed)

Marios: "do it properly as an addon; first for me, later give the idea to FreeCAD; research only, do not change the
code yet; check that it really works and is professional." FreeCAD 1.1 is his stable version; he is trying **26.3**
(new calendar versioning: 26.3 = former "1.2", preview; main is already "27.1dev").

## What was actually run
- **FreeCAD 26.3.0** (`26.3.0devR20260916`, conda-forge build `freecad=2026.09.16`) installed headless in the session
  scratch area with micromamba (GitHub release assets are not reachable from the sandbox; conda-forge is).
- A throw-away addon `PolarXZC` (in `/tmp`, not in the repo): `package.xml` with `<Postprocessor>` and `<machine>`
  content, `Init.py`, `machines/Polar_XZC_LinuxCNC.fcm`, `posts/polar_xzc_post.py` (class `Polar_Xzc(Linuxcnc)`).
- A real CAM job made headless: Part cylinder + boss → `Path.Main.Job.Create` → `Path.Op.Profile.Create`, default
  tool controller "TC: 5mm Endmill", feeds set to 600/150 mm/min.

## Results
| Check | Result |
|---|---|
| XZC machine (X, Z, C — no Y) built with the Machine API, saved as `.fcm`, `validate_machine` | **0 findings**; `machine_type` = "custom" (only a label) |
| Addon discovery (machine list, post list) | both found from the addon |
| Post-processing run (`job.Machine` → `get_machine`) | **fails without `Init.py`**: the machine is only registered when the Machine editor scanned addons. With `Init.py` calling `Path.Preferences.addAddonAssetPath(<addon>)` → found. (Known gap; worth reporting upstream later.) |
| Post class loading (`polar_xzc` → class `Polar_Xzc`, `POST_TYPE = "machine"`) | works; `self._machine` is our XZC machine |
| What the post receives | all commands incl. **12 × G2 arcs** with I/J, tool change M6/G43, **tool number + diameter (T1 = 5.0 mm)** from the tool controller, feeds **in mm/s internally** (2.5 / 10 for 150 / 600 mm/min) |
| An "as-is" output line (`G93 … F123.4567`) | passes the whole pipeline **unchanged** → G93 inverse-time F can be written without FreeCAD's ×60 feed formatting |
| Rotary axis side effect | with a C axis, 26.3's "3+2" support makes **each operation start with `G0 C0`** (workplane pose) after a recompute. Our converter correctly refused it (C word in input). The post must drop pure `G0 C0` and refuse any non-zero A/B/C (rotated workplane). Done in the prototype. |
| End to end (prototype shortcut: FreeCAD LinuxCNC output → our JS core via node) | polar G93 program **identical character for character** to the page's conversion of the same Cartesian program; replay: worst G1 deviation **0.0094 mm**, real feed exactly 150 / 600 mm/min |

## What this means for the real addon
- **Feasible and clean in 26.3:** machine definition + post class, installable via Addon Manager (`freecadmin` 26.3),
  no FreeCAD core change needed. **Not possible in 1.1** (no machine model, no addon post dirs).
- **Professional version must:** port the core to Python (no node), run the transform inside the post (on commands,
  not text), write G93 lines "as-is", read the tool diameter from the tool controller, drop `G0 C0` poses, refuse
  rotated workplanes and anything the core refuses, expose the settings (cutting side, X max, chord tolerance) through
  `get_property_schema`, ship `Init.py`, and test with: (1) pytest on the pure-Python core against the JS golden /
  edge-case outputs (byte-identical), (2) FreeCADCmd integration tests with real jobs like this one, (3) `.fcm`
  validation — all runnable in CI with the conda-forge FreeCAD build.
- **Risks:** 26.3 is a preview and the post hooks used (`_expand_postprocessor_commands`, `_expand_rotary_move`,
  as-is annotations) are underscore/internal → pin the FreeCAD version and keep the integration tests; FreeCAD's own
  simulator does not show C (keep our page's simulator for that); a machine name with parentheses was mangled in the
  header comment (avoid them).
- **Upstream later (FreeCAD AI policy applies to PRs only):** the Init.py registration gap, an official
  `POST_TRANSFORM` hook, G93 support, rotary axes in CAM Sim. PRs must be signed and understood by Marios, with
  `Assisted-by:` disclosure.
