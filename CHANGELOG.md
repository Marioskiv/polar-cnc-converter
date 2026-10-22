# Changelog

## 2.26.0 — Knurling & Wrap moved to its own repository

- The Part Design tools **Knurling & Wrap** (Knurl, Wrap on a cylinder, Hole on any surface) are now a separate
  addon: [Marioskiv/freecad-addons](https://github.com/Marioskiv/freecad-addons). Removed from here: `cad/`, their
  tests and notes, and their entry in `package.xml`. Install the new addon from the Addon Manager (custom
  repository); files made with these tools open as before.
- The converter and Polar CNC are unchanged.

## 2.25.0 — Knurling & Wrap: Hole on any surface

### Added
- **Hole on any surface** (Part Design toolbar *Knurling & Wrap*): click the part where the hole goes — a flat
  face, a cylinder, the teeth of a pulley, any curved face — and press the button. A round hole is drilled there,
  square to the surface at that point, from outside the part: through the wall up to the first empty space (the
  default, e.g. into a pulley's bore), to a depth, or right through. The panel changes the diameter and the depth
  with a live preview; Cancel puts the old values back.
- Some features leave a solid on which every later cut fails ("result is empty"), e.g. a Part Design Hole with
  *Model Thread* on the author's HTD 5M pulley. The command tests the cut first and, when the last solid is broken,
  puts the hole just before the feature that breaks it and says so (in Greek); a hole that still cannot be cut
  explains why instead of failing silently.
- Test `tests/freecad/surface_hole_test.py` (real FreeCAD, in `tests/freecad/run.sh`).

The converter and the Polar CNC addon are unchanged.

## 2.24.0 — fixes from a full review (polar checks, Split Output, Wrap orientation)

A full review of the repository (two independent read-throughs of the converter and of the FreeCAD addon, every
test, the sweeps, LinuxCNC 2.9.10's own interpreter on the author's machine `.ini`, `ruff` and `eslint`). The XZC
layout (the face milling machine) is **unchanged**: golden 144/144 identical, sweeps the same, the author's three
real programs give the same output.

### Fixed — polar (face) Jobs in FreeCAD
- **A cutter with no diameter was checked against the chuck as a point.** With a chuck set up, Post Process now
  refuses an operation whose tool bit has no Diameter (and the live check shows it as a stop).
- **Split Output** (one file per tool / fixture / operation): FreeCAD calls the post once per file and writes every
  file that is not refused, so a file running into a jaw was missing while the others were written. Every file of the
  Job is now checked: if one is refused, none is written, and the card is shown once. The simulator and the cut
  check play the files one after the other, each converted on its own, as they will run.
- The setup note at the top said "stock bottom at Z … – touch off Z there": it reads as "touch off at the bottom",
  wrong by the stock height. It now says: touch off Z on the stock TOP with the value Z ….
- A program edited by hand in the post's editor was written without a new check. It is now checked again (Y left,
  the chuck; the 2.22.0 tool-change park lines, in machine coordinates, are left out as on the first write)
  and refused if it fails.
- "Y in the output" is checked by Post Process too (it was only in the live check).
- Two tool controllers with one tool number: the chuck check uses the bigger cutter.
- Drilling cycles (G73, G81–G89) are followed in the Cartesian chuck check and in the jaw-height reminder
  (they were skipped; the polar check after conversion already saw them).
- The chuck's keep-out shapes are rebuilt when the stock or *Jaws at known angle* changes (they could be stale until
  a recompute).

### Fixed — Wrap
- **An unrolled drawing came out mirrored on the part** (web page, layout Wrap): C was +Y/R0, which with the
  converter's own convention (proven by the F test) is left-handed. It is now **C = −Y/R0**, so the drawing reads the
  right way round seen from outside the part. The FreeCAD Polar Wrap operation unrolls with the matching sign, so its
  programs are unchanged. New test: the unrolled X × Y points out of the part. As with the F test, only an asymmetric
  test cut on the machine proves it.
- **The first rapid of a Wrap program** (and the first after a tool change) moved X, Z and C in one block, dragging
  the tool across the part if it started on it: the "radius not known yet" case was dead code. It is now split like
  every other rapid (out first, then along/round). After M6 the position is forgotten, as the input stage says.
- **Polar Wrap with a flat end mill could cut up to 0.78 mm too deep** at a sharp edge (a key along the bar): written
  points were two map cells apart, and the check takes the highest of the four grid points round each point only.
  They are now at most one cell apart (0.000 mm on the same case; a ball end was already fine).
- Wrap arcs are chorded at half the tolerance, as in XZC. A warning that could never appear was removed.
- Polar Wrap's create command is written anew (it was close to FreeCAD's LGPL `Create`); Cancel in the tool
  controller chooser no longer leaves a half-made operation.

### Checked
- `npm test` (wrap 145), sweeps unchanged (worst 0.0225 mm), LinuxCNC 2.9.10 `rs274` with the machine `.ini`: the
  author's three programs OK (time equal to the CAM), Wrap outputs accepted. FreeCAD 26.3: every addon test PASS,
  plus the new `tests/freecad/fixes_test.py`. `ruff` (Python) and `eslint` (JS): no real error.

## 2.23.0 — Knurling & Wrap moved here from WikiTips

### Added
- **Knurling & Wrap** (`cad/`): the Knurl and "Σκαρίφημα σε κύλινδρο" (Wrap) tools, moved from WikiTips 0.4.1
  with their tests and notes, MIT like the rest of the repository. A separate part of the addon (second
  `<workbench>` in `package.xml`), on its own toolbar in **Part Design only**, with nothing of WikiTips inside:
  its Greek messages (wrong selection, knurl too big, no closed shapes) are its own. Commands
  `KnurlWrap_Knurl`, `KnurlWrap_Wrap` (were `WikiTips_Knurl`, `WikiTips_Wrap`).
- Files made with WikiTips' Knurl or Wrap still open (the old module names are kept; FreeCAD 26.3 only lets a
  document import modules already loaded, so they are loaded at start-up) and are saved under the new names.
- Tests in a real FreeCAD: `knurl_test.py`, `cyl_wrap_test.py`, `knurlwrap_old_file_test.py` (fixture made
  with WikiTips 0.4.1).

## 2.22.0 — Tool change by hand: park position, spindle always started

### Added
- **Park before every tool change** (FreeCAD Post Process, Job property *Polar Tool Change Park*, on by default).
  Polar: `G53 G0 Z0` (Z to where Home All parks it, away from the part), then `G53 G0 X0`. Wrap: `G0 X<X max>`
  (away from the bar) first, then `G53 G0 Z0`. C does not move. `G53` goes to the machine position whatever the
  tool length offset (checked in LinuxCNC 2.9 `interp_find.cc`). For machines with machine Z0 at the chuck end the
  property must be unticked.
- `M5` before the program end when the spindle was left on.

### Changed
- **A Tool Controller without a spindle speed (or with direction None) is refused** by Post Process: FreeCAD writes
  no `M3 S` for it, and after `M6` (LinuxCNC stops the spindle) the cutter would go in with the spindle stopped.
  Error card in Greek and English.

### Fixed (comments and the simulation only: no change to the G-code of the web converter)
- `examples/linuxcnc-vismach-xzc-lathe/polarlathe-sim.ini`: X synced with the real `.ini` of 2026-10-19
  (`HOME_OFFSET` -24.039, limits -22.039 … 108.961); the Z comment said machine Z0 is at the chuck end — since
  2026-10-04 the machine is homed like a mill and machine Z0 is the park at the tailstock end.
- The same outdated sentence in `src/core/gcode-input.js` and `docs/TECHNICAL.md`; the G28 error message now says
  "on some lathe conversions the chuck end of Z".
- `profiles/example-lathe-xzc-one-side`, the example README and `tools/linuxcnc-compare.js`: X max 108.961.

## 2.21.0 — Wrap with several cutters, and what each cutter leaves

### Added
- **Polar Wrap *After operation***: a second (third…) Polar Wrap with another cutter starts from what the one before
  it left, not from the whole bar. With *Roughing + finishing* its roughing cuts only where the cutter before did not
  fit and goes through the rest at the air feed (on the test relief the Ø2 cuts less than half of what it would from
  the bar).
- **Tool report** of every Polar Wrap (panel, *Tool Report* property, Report view; Greek or English): whether the
  cutter gets down into every hollow (groove, slot, dimple) or how much it leaves at the bottom of one and where;
  how much inside corners keep (a ball rounds them with its radius); and the largest ball end that gets down into
  every hollow.
- `tests/freecad/wrap_relief_test.py`: a relief (rib, 1.2 mm groove, 2 mm slot, dimple) machined Ø6 flat → Ø2 ball →
  Ø1 ball; every cutter followed against the solid and the chuck.
- `tests/freecad/wrap_ocl_test.py`: Polar Wrap's radial drop-cutter against **OpenCAMLib** (FreeCAD's own rotary
  drop-cutter of its Rotary Surface operation) on the same relief, flat Ø6, ball Ø2, ball Ø1, 16 835 points each:
  never deeper than OpenCAMLib, the same within 0.003 mm at the median (the 2 µm the mesh is padded by). And checks
  taken from the rotary tests of FreeCAD, Kiri:Moto and LinuxCNC (ideas only): a part turned across the 0° seam
  gives the same map turned; a cone follows its formula; what a cutter leaves is never below the part, a smaller
  ball never leaves more; a map twice as fine gives the same tips.

### Fixed
- **Post Process with several cutters checked every move against the chuck with the biggest cutter's radius**, so a
  small cutter running past the jaws could be refused. Each move is now checked with its own cutter (the diameter of
  its tool comment).

## 2.20.0 — polar with FreeCAD's own operations, each one checked when it is made

### Changed
- **Polar Face is removed.** A polar Job is machined with FreeCAD's own operations (Face, Pocket, Profile,
  Drilling, Helix…), made the way you want. Files made with Polar Face still open: such an operation keeps the
  path it had, is not remade, and a warning says to replace it.
- **Nothing is greyed out in a polar Job**, FreeCAD's Face included: what does not suit polar only gets a warning.
  (A Wrap Job still offers only Polar Wrap.)
- **Each operation is checked as soon as it is made**, alone, the way Post Process will write it: FreeCAD's
  LinuxCNC output → the converter (X C Z) → read back as the machine moves the joints → the chuck. If it **will
  crash** into a jaw, a clamp or the chuck body, cannot be written as polar G-code, or a Y is left, a card says so
  and Post Process refuses the program until it is fixed. Nothing in the operation is changed.
- Warnings in Greek or English (the help language): line-by-line patterns name the ring pattern to use (Pocket
  Offset, Face Spiral, Surface Circular); FreeCAD's Face (it covers the stock's bounding rectangle: on round stock
  it cuts air); 3D Surface, Waterline, Probe, Adaptive and the others; a cut below the jaw tops.
- A polar Job with a post-processor other than `polar_linuxcnc` is warned about (it would write X Y Z, not X C Z).
- New optional Job setting **Polar C Max Velocity** (deg/s, from the LinuxCNC `.ini`): with it each operation says
  how much slower the C axis makes it near the centre.

### Fixed
- "could not set the operation defaults: 'Spiral' is not part of the enumeration ... MillFacingClearingPattern":
  FreeCAD's Face does offer Spiral; the Job's *Operation defaults* (SetupSheet) had kept an older list of choices
  for it (from when that entry was first made). The list is now brought up to what the operation offers, then the
  default is set; the defaults are set one by one, so one that fails never stops the others.

### Not changed
- The web converter (`src/`, `lib/`, `css/`): no change since 2.17.0; the golden programs are byte for byte the same.

## 2.19.1 — a cut check, and what it found

### Fixed
- **Polar Face, *All the stock* / *Only round the part*: a skin could stay on the part top.** The depths were equal
  steps from the stock top down, and none had to land on the part top (e.g. 15.43 then 12.86 for a top at 15). Every
  flat face of the part between the start and the final depth is now a depth of its own.
- **Spiral with a step wider than the cutter radius** (Step Over over 50 %) left a lip on the rim: one full turn on
  the edge first.
- **Rings with a wide step** (over 95 %) could leave a thin ring of material round the centre: one more circle a
  cutter radius out.
- ***Only round the part* with a Band Width not wider than the cutter** cut nothing round the part, and said
  nothing: the band is widened (1.5 cutter diameters) with a warning.
- **Polar Wrap with From Z / To Z set by hand** could run down into the jaws (only the automatic range stopped above
  them): it now always stops clear of the chuck, with a warning.
- A step in to a full circle is checked against the part like every other step.

### Added
- **The cut check** (`tests/freecad/cut_check_test.py`): the final polar program, read back the way LinuxCNC moves
  the joints, followed point by point with the cutter's body tested against the solid part and the chuck (never
  inside), and what had to be cut checked as cut. Polar Face in every clearing × pattern on round stock (3-jaw),
  square stock (4-jaw) and a long plate on a faceplate with clamps; Profile, Pocket, Helix, Drilling; Polar Wrap.

## 2.19.0 — machining type, Wrap on its own, spiral facing

### Changed
- **Machining type** (the first Polar CNC button, was *Polar machine settings*): *Ordinary CAM*, *Polar* or *Wrap*
  in one window, each with a line saying which operations to use. *Ordinary CAM* takes a Job back (the Polar CNC
  settings go, its former post-processor comes back). Cancel leaves the Job as it was.
- **A Wrap Job greys out every operation but Polar Wrap** (Post Process refused them anyway).
- **Wrap has its own X Max** (*Polar Wrap X Max*: the Wrap profile of the machine has its own travel and X zero);
  0 = the same as Polar X Max.

### Added
- **Polar Face pattern**: *Rings*, *Spiral* (one spiral from the edge to the centre: X falls steadily while the
  chuck turns, no step-in marks) or *Auto* (spiral on round stock when only the face is cut, rings elsewhere).

## 2.18.0 — the chuck from one click, no more freezes, sharper help

### Fixed
- **The chuck and the clamps were never drawn in the 3D view** (made from a script, they had no display mode; only
  the simulator showed them). They now have a view provider of their own; documents saved before are fixed when
  they are recomputed.
- **Polar Face froze FreeCAD** for 30 s to minutes ("All the stock" / "Only round the part", bigger stock, small
  cutters): every move was measured against the whole 0.25 mm grid. It now looks only at the points near each move
  and checks exactly in one boolean per run: 44 s → 3 s, 68 s → 4 s, the heaviest case tried under 10 s, the same
  path. A progress bar shows while it works and **Esc stops it**; the panel no longer remakes the path on every
  change of a field (OK or Apply does).
- **Polar Wrap** was as slow (51 s for a Ø80 × 120 bar): the part is now sliced as a fine mesh in one call,
  5–7 times faster, on the safe side by at most 2.5 µm. Progress bar and Esc too.
- Picking the face to hold: the direction out of a face is found from the solid itself (some faces gave the
  opposite one and the part turned upside down).

### Added
- **Chuck from one click**: click the face that goes into the chuck, press Chuck. The part is turned, put on the
  axis with Z0 on the stock top, and your chuck that holds it (K11-125 3-jaw for round stock, K72-125 4-jaw for
  square) is chosen with the grip under the part. Undo puts it back.
- **Help animations like WikiTips**: 1248 × 750, recorded at 150 % scale, one palette, no words in the picture
  (one animation for every language), the step playing lit in the card; a smaller card (30 % of the screen,
  400–540 px), drawn sharp at that size. New animations for *What to cut*, the *Ramp*, and Polar Wrap's
  strategies and finishing.
- Tests: `setup_test.py` (the one-click chuck), `ops_test.py` (Profile, Pocket Offset and ZigZag, Helix, Drilling off
  and on the axis, Adaptive, Polar Face in all its modes: made, checked against the chuck, Post Process, simulator).

## 2.17.0 — Polar Face: what to cut

### Added
- **Polar Face → What to cut**: *Face only* (as before), *All the stock round the part* (everything outside the
  part down to the final depth: a square bar becomes the round part, a round bar is turned down to it), or *Only
  round the part* (a band of *Band width* round it, the rest of the stock left and kept clear). For round and
  square stock alike. The final depth follows the choice: the part bottom, but above the jaws (or the faceplate).
- **Ramp entry** (*Ramp angle*, default 3°): where Polar Face must go down into material it no longer plunges.
  It ramps down along the cut it is about to make (on a circle the chuck turns while Z goes down: a helix round
  the axis), back and forth on a short cut, then back to the start at depth. 0 = straight down as before.
- **SAN OU K11-125** 3-jaw preset (replaces the scaled "3-jaw SAN OU 125"): K11 table body 58, bore Ø30, jaws
  25.5 / 53 / 16 measured on a real chuck. The chuck says when the stock needs the reversed jaws (normal Ø2.5-40,
  reversed Ø38-110) or is too big; the same ranges for the K12-125.
- README: where X0 Y0 and Z0 are (chuck axis; stock top).

### Fixed
- **Polar Face could pass up to ~0.3 mm closer to the part, jaws or clamps than allowed**: moves round a circle
  between two cuts were checked on a 0.25 mm grid only. Near anything that must not be touched they are now also
  checked exactly. Found when the ramps (drawn point by point) were measured against the clamps.

## 2.16.0 — help inside FreeCAD (Greek/English), settings dialog, review fixes

### Added
- **Help inside Polar CNC, Greek and English.** Hovering a *Polar CNC* toolbar button shows a card with what it
  does, an animation recorded in a real FreeCAD (chuck, clamps, Polar Face, Polar Wrap, the simulator), numbered
  steps and a warning. The Polar Face and Polar Wrap panels have a **?** button on every field. Refusals come as
  **error cards**: what happened, why, what to do, and the original message. Language follows FreeCAD (Greek or
  English); toolbar button *Polar CNC help language* chooses it or switches the popups off. No extra packages.
  Test: `tests/freecad/help_test.py`.
- **Machine settings in one small dialog** when a Job becomes polar: Face or Wrap, X Max (required, never
  guessed), cutting side, bar diameter, tool lengths in X; each with its **?**. Cancel keeps the properties.
- **Chuck chooser: type first, then the size**, with the sizes of the choice shown under it.

### Fixed (from a professional review)
- **Polar Face could pass over the jaw tops** (clearance sideways only); jaws within the clearance below the cut
  are now kept clear. Found when the chuck got its real shape.
- **Offsets of joined areas could go the wrong way**: a face that came out of a boolean upside down was shrunk
  instead of grown (`grow`); the direction is now checked by the area, holes one by one.
- Round stock: the jaws can be anywhere round it, so they are kept clear as a ring (chuck property *Jaws At Known
  Angle* to use their drawn angle).
- Post Process checks the polar program as the machine moves it (joint space), not only the CAM paths; never
  shows a raw traceback; adds setup lines (where Z0 is, the chuck and grip) at the top.
- Wrap: G43 refused until the tool lengths are in the X column (*Polar Wrap Tool Length In X*); inactive
  operations no longer refused; a part with a gap along Z refused (the cutter would go to the axis); X past
  X Axis Max refused, not only reported; warnings when the stock diameter or length differs from the part.
- Polar Face: refuses a tool controller without feed; warns when X0 Y0 is outside the stock; raises a Safe Height
  that is below the jaw tops.
- Simulator: an empty program or any error never leaves the document hidden; it frames the whole chuck.
- The live chuck check runs only for paths of a usual size (big paths are checked by Post Process); the converter
  engine is loaded once; Wrap paths are thinned where the joint move is exact.

- **Clamps were drawn at 0 degrees whatever their angle** (the checks used the right place, the clamp object
  did not). A clamp turned to another angle now also moves in to the stock edge again.

### Changed
- The chuck looks like the real one: chamfered body, bore, jaw slots, steel colours.

## 2.15.0 — FreeCAD addon (Polar CNC for the CAM workbench, in testing) and Wrap

### Added
- **Wrap: the outside of a cylinder** (layout *Wrap (router radial)*, web page and FreeCAD). The router is turned to
  look at the part; the machine axes stay as they are (X radius, Z along the part, C round it). The CAM program is
  the cylinder's surface **unrolled flat**: X along the part, Y round it (mm of arc at the *wrap radius*), Z 0 on the
  surface. Each straight move becomes one X/Z/C block (the map is linear, so it is exact); arcs are split within the
  chord tolerance; G93 times use the true path of the tool tip at its real radius. Simulator: the cylinder with the
  router radial. FreeCAD: Job → *Polar Layout* = Wrap and *Polar Wrap Radius*. `tests/wrap.test.js` replays the
  output in joint space; `tests/freecad/wrap_test.py` runs a Wrap Job through Post Process and the simulator.
  **FreeCAD: Polar Wrap** — no flat drawing: the real 3D part (solid or STL, axis on Z) and the stock diameter.
  It maps the part's radius round the axis (slices; solid and STL agree within 0.02 mm), finds how far a flat or
  ball end mill may go in without cutting the part (radial drop-cutter, conservative between grid points), and
  cuts helices round it: roughing layers from the stock down, then a finishing helix; it stops clear of the jaws.
  Post Process unrolls its path for the converter. Tests: `tests/freecad/wrapcut_geometry_test.py` (no cutter
  point inside the solid, groove and flat reached), `tests/freecad/wrap_test.py` (the whole Job).
  The chuck works in Wrap too: it holds the cylinder from the chuck end (X min of the unrolled stock), is shown in
  the simulator, and Post Process refuses a wrapped program whose radial router runs into the body or the jaws.
- **FreeCAD addon** (`freecad/`, `package.xml`): polar face machining from the FreeCAD CAM workbench. A
  post-processor `polar_linuxcnc` turns a normal CAM Job into polar G-code; the command *Polar machine settings*
  adds the Job's machine settings (X Axis Max, cutting side, optional profile). It runs the converter in `src/core`
  itself, through Qt's JavaScript engine: no second copy, the web page and FreeCAD always convert the same way.
  The converter itself is unchanged (golden 144/144). See [freecad/README.md](freecad/README.md) and
  [docs/FREECAD.md](docs/FREECAD.md).
- **Polar Jobs offer only polar operations**: 3D Pocket, 3D Surface, Waterline, Planar/Rotary Surface and Probe
  are greyed out while the current Job is polar; new Pockets default to Offset and Facings to Spiral; Adaptive,
  V-carve, Slot, Deburr, Thread milling and line-by-line patterns get a warning (Report view, never a dialog).
- **Polar Face** operation: facing that follows the real stock (round, square, hexagon, plate, off the centre) —
  circles round the chuck axis clipped to the stock at every depth, linked without fast moves over uncut material;
  16–60 % less time than full circles in the tests, nothing left uncut, the part never touched. FreeCAD's Facing
  (bounding rectangle, cuts air) is greyed out in polar Jobs.
- **Chuck, 4-jaw chuck and faceplate** (*Chuck* / *Add clamp* buttons): a parametric chuck object on the Job;
  the *Chuck* button asks which chuck (a catalogue size or *Custom (my own sizes)*).
  Presets from catalogue tables (SAN OU K72-125 4-jaw independent (the default), K12-125 4-jaw self-centring and 3-jaw 125; 3-jaw SC-3 … SC-16, 4-jaw independent 12–24 in, faceplate Ø250/Ø400) or your own
  sizes. The jaws close on the real stock (independent 4-jaw: each jaw on its own; self-centring 3- or 4-jaw: a
  note when the stock cannot be centred, e.g. a square in a 3-jaw, a rectangle in a 4-jaw). On a faceplate you place clamps by angle and radius; they reach the stock edge by
  themselves. Polar Face keeps *Chuck clearance* (2 mm) from jaws and clamps; the simulator shows the chuck
  turning with the part (jaws and clamps in red). An operation that cuts below the jaw / clamp tops gets a warning
  (the collet nut is not checked). Every operation and its rapids are checked against the chuck body, jaws and
  clamps; Post Process refuses a program that runs into them.
- **Polar Face**: a part made of several separate solids is now fully protected (only the first one was before),
  and a final pass round off-centre parts of the part removes the cusps the rings leave beside them.
- **Polar simulation in FreeCAD**: plays the polar program (what Post Process writes) — machine view with the part
  turning on the chuck, or part view — with program time, chuck turns and chuck speed.
- `tests/freecad/run.sh`: tests the addon in a real FreeCAD (golden set inside FreeCAD, refusals, output equal to
  the Node converter on FreeCAD's own LinuxCNC output).

## 2.14.1 — simulator: cutter on the side where it is on the machine

### Added
- **Cutter side** selector next to the view-mode button: right, left, top or bottom, as seen when looking at the
  chuck from the cutter's side. The Rotary Mill view turns about the chuck axis, so the cutter appears where it
  sits on the real machine. The part and the cut turn with it, so the direction of rotation stays as it is. Static 3D
  still shows the part as the CAM drew it. Display only: the G-code does not change. The choice is remembered in
  the browser.

## 2.14.0 — arcs off the chuck axis split directly in joint space (smooth X, far fewer blocks)

Found on the first real facing cut: from about 50 mm radius inward, X went in and out on almost every block and the
machine moved in jerks.

### Fixed
- **Arcs that are not centred on the chuck axis** (and stay away from the pole) are now split **directly into
  joint-space blocks**. Every block ends on a point ON the arc, X and C move linearly between them, and each block is
  checked against the arc itself (both ways, within 0.8 of the chord tolerance). Before, an arc was first cut into
  chords and then each chord into polar pieces. Each chord dips toward the pole in its middle, and the output
  followed that dip, so on a slightly off-centre arc **X reversed direction on almost every block**. Example: a
  FreeCAD facing (60° arcs, centre 0.18 mm off the axis): X reversed 7,147 times, 0.007-0.014 mm each, about every
  0.05 s. The path was within tolerance, but on steppers it made stop-go motion. Now there are 2 reversals, and
  731 blocks instead of 11,633, with the same path length.
- The arc's distance from the pole is checked first. An arc that comes within 4 × max(centre zone, chord
  tolerance) of the pole keeps the previous method, with its pole handling.

### Checked
- Sweeps: random arcs, worst 0.0223 → **0.0210 mm**; near-pole lines and polylines unchanged (0.0225).
- Golden 132/144 identical. The 12 that changed are all the `offCircle` program (an off-centre circle), in every
  option set and centre mode: 64 → 60 blocks, deviation from the CAM path 0.0209 → 0.0198 mm (`alt`, chord tolerance
  0.05: 46 → 42 blocks, 0.0408 → 0.0396 mm), F on every block. Updated with `--update` after this check.

## 2.13.0 — C report: range in turns, C speed the CAM feed needs (from Fanuc / Siemens practice)

From the 2026-10-13 study of how professional controls and CAM posts handle polar machining. Golden 144/144: each output gains only the new report comment lines at the top (at most 8); every
other byte is the same (checked per output). Sweeps unchanged.

### Added
- **C range** at the top of the output: lowest and highest C written (rapids and centre turns included) and the
  turns between them. **Warning past ±99,999°**: the usual LinuxCNC rotary soft limit (also in the delivered
  example machine `.ini`, about 277 turns) — LinuxCNC would stop the program there. Siemens monitors rotary turns, and
  Autodesk's posts check rotary limits, for the same reason.
- **C speed the CAM feed needs**: the mm of cut (and blocks) that need C faster than 90 / 180 / 360 / 720 deg/s,
  and the fastest block with its distance from the centre and source line. Where this is above the machine's
  `[AXIS_C] MAX_VELOCITY`, LinuxCNC stretches the block and cuts slower than the CAM feed — Fanuc (AFC, parameters
  5450/5463) and Siemens TRANSMIT do the same near the centre automatically. Only a report: no C speed setting
  (DECISIONS), the motion is not changed. A spin at the centre itself is left out (it cuts nothing).
- Moves carry their source line number from the input stage to the layout (`ev.line`).

### Not done
- One-direction C approach for holes (Okuma, Mastercam): not needed without measurable backlash; LinuxCNC's own
  `[JOINT_n] BACKLASH` covers a small one.

## 2.12.3 — fixes found by comparing with the real LinuxCNC interpreter

Exhaustive audit (2026-10-13): the CAM input and the converter output were both run through LinuxCNC
2.9.10's own interpreter (`rs274`) and compared — golden programs, three real FreeCAD programs, about 60 edge
cases, the options, and 2000 random programs. One-side cutting had no error. Golden 144/144
identical; FreeCAD programs identical; sweeps unchanged (worst 0.0225 mm).

### Fixed
- **Signed-X ramp through the centre, both-sides cutting only (X Min < 0).** After a line that ramped in Z through
  the centre, the way back to the centre (to change from negative X to positive X) ran at the line's final Z. On a
  ramp going down that is deeper than the ramp was near the centre: 0.13 mm too deep in the comparison, 0.33 mm in
  the new geometry test. The way back now follows the line's own Z (never lower than it, never lower than the
  current Z), so it only moves where the tool has already cut. Flat lines give the same output as before.
- **Canned cycle changing code without `G80`** (`G99 G81 …` then `G98 G83 …`): the G98 holes retracted only to R,
  because the initial level was taken again at the code change. It is kept now, as LinuxCNC does (`cycle_il`).

### Changed
- **A rapid INTO the centre** (end inside the centre zone) is one block (X alone at the current C, exact); it was
  cut into 0.5 mm pieces (42 blocks for X21 → X0). Same rule as the rapid out of the centre (2.12.1).

### Added
- `tools/linuxcnc-compare.js` — the comparison with LinuxCNC's interpreter as an optional tool (see README).
- README: the two known differences from LinuxCNC in drilling cycles (default `G98`, `G85`/`G89` retract), both only
  above R.

## 2.12.2 — only known G codes are read; G16 keeps a left-out radius/angle (Fanuc manual)

Found by reading the whole Fanuc Series 16i/18i-MB operator's manual (B-63534EN/02, 1257 pages) and running its
codes through the converter. Golden 144/144 identical; the FreeCAD test programs identical; sweeps unchanged.

### Fixed
- **Unknown G codes passed through, some with their X/Y taken as a move.** Until 2.12.1 only a list of known-bad codes
  was refused. `G4 X1` (Fanuc dwell, 1 s) moved the tool to X1; the X/Y of `G51` (scaling centre), `G50.1` (mirror
  axis), `G22` (stroke area), `G29`, `G45` and `G60` became moves; `G6.2` (NURBS), `G2.2` (involute) and `G2.4`
  (3-D arc) became straight lines; `G33` (threading) became a plain `G1`; `G5 P10000`, `G5.1 Q1` (Fanuc high-speed
  modes — splines in LinuxCNC), `G43.4/G43.5`, `G65/G66` (macro calls), `G95` (feed per revolution, read as
  mm/min) passed through. Now only known codes are read (see README); any other G code stops with the line number.
- **`G91` on a canned cycle's own line** (`G91 G81 X5 Z-3 R-2`) was not seen by the "no cycles in G91" check: the
  hole was drilled at absolute X5 with the wrong depth. Refused now, like a cycle after a separate `G91`.
- **Block delete `/`**: the `/` landed on an output line of its own, so the move ran always. Refused now.
- **Chamfer / corner rounding `,C` `,R`** (Fanuc): `,R` was ignored (sharp corner instead of the rounding), `,C`
  was refused as a "C axis word". Both refused now with their own reason.
- **`G4 X`** refused with the reason (write `G4 P` in seconds). **Fanuc `G08 P1`** (advanced preview) left a stray
  `P1` line after the `G8` removal; refused now.
- A **Fanuc program number** (`O1000`, alone or with moves on the line) was copied out; LinuxCNC reads it as an
  o-word without a keyword. Kept as a comment now.

### Changed
- **`G16` (E):** as in Fanuc B-63534EN §8.2 (p.138-140), a line may leave out the radius or the angle; it
  keeps its last value (`N3 Y150.0` = 100 mm at 150°, the manual's example). `G91 Y120` turns the angle by +120°
  with the same radius and the pole still at the work origin (example 2). Still refused: `G91` with a radius (the
  pole becomes the current position), and a first point after `G16` without both values.

## 2.12.1 — G16 polar coordinates converted; subprograms, parameters and mixed R + I/J arcs refused; radial rapids in one block

### Added
- **Fanuc `G16` / `G15`** (polar coordinate command, used for hand-written bolt circles) is converted instead of
  refused: in `G17` with `G90`, `X` = radius and `Y` = angle (degrees, counter-clockwise from +X) from the work origin.
  Each such line is rewritten to Cartesian X/Y before anything else reads it (canned cycles included) and noted in a
  comment; `G16`/`G15` are removed (LinuxCNC does not know them). A G16 bolt circle gives exactly the same motion as
  the same holes written in X/Y. Refused with the line number, because their meaning is not certain: `G91` in
  polar mode, a line with only the radius or only the angle, X/Y on the `G16` line itself (some sources make
  them the pole, others a first point), arcs in polar mode, other planes, and
  `G10/G28/G30/G52/G53/G92` with X/Y. `G12.1/G13.1`, `G112/G113` and `@ ^` stay refused (2.11.4); Mitsubishi `G12.2/G13.2` and cylindrical
  interpolation `G7.1`/`G107` are refused too (they passed through).

### Fixed
- **Program flow and computed values** passed through unconverted: `M98`/`M99` subprograms (the sub body was converted
  where it stands in the file, after `M30`, from the position of the line before it — not from the call), LinuxCNC
  o-word `sub/call/if/while/repeat…`, and parameters / expressions (`#1=5`, `G1 X#1`, `X[5+5]` lost their X). All are
  now refused with the line number; a CAM posts them as plain moves. A Fanuc program number (`O1001`) and `#`/`[ ]`
  inside comments are still fine.
- An arc with **both R and I/J** (`G3 X0 Y10 I-10 J0 R10`) was converted with R, whatever I/J said; LinuxCNC refuses
  such a block ("mixed radius-ijk format"). Now refused too.

### Changed
- **The program states its X mode** (F): `G8` (radius) after `G93`, or `G7` when the output profile writes X as
  a diameter — only for a rotary axis named C (lathe-style XZC); A/B profiles (mill-style controls such as Mach3 Mill)
  get neither. On a LinuxCNC lathe configuration (`LATHE = 1`) a `G7` left active would read the radius X as a
  diameter: a half-size part. A `G7` in the input is now refused; a `G8` in the input is removed (the header sets it).
- A **radial rapid** (on a ray from the centre, C constant — e.g. from the centre out to a bolt circle) is one block;
  it was cut into 0.5 mm pieces (200 blocks for X0 → X100). Rapids that turn C are segmented as before.

### Golden baseline
- 144/144 outputs changed by exactly ONE line: `G8` inserted after `G93` (checked for every output: removing that
  line gives the old output byte for byte). Input tests 116 (new: G16 conversion = Cartesian version, 5 refusals, `;` comments, mixed
  R + I/J, radial rapids, subprograms / o-words / parameters). Sweeps and the near-pole stress test unchanged; the FreeCAD test programs: same G1 output,
  one of them 2 rapid blocks fewer.


## 2.12.0 — arcs centred on the chuck axis are exact

### Changed
- A `G2`/`G3` arc whose centre is on the chuck axis (within 0.001 mm) — a circle about the centre of the part, also a
  helix — is now written as a few blocks in which **only C turns and X stays constant** (at most 45° of C per block;
  Z linear for a helix). The machine draws that circle exactly. It used to be cut into chords and every chord into
  polar pieces: an R10 circle was ~219 blocks, each up to ~0.01 mm off the circle; now 8 blocks, zero geometric error.
  Same idea as the "G20" module of Zhang, Chen & Du (IJAMT 2013). Radii and end angle are taken about the axis
  itself, so the last block lands exactly on the programmed end point (a rounded I/J or R gives the same small
  spiral LinuxCNC itself would cut). All other arcs take the general path, unchanged.
- `geometry.js`: the arc centre/sweep maths is split out as `arcGeometry()` (linearizeArc unchanged).

### Golden baseline
- 24/144 outputs changed — exactly the fixtures with an arc centred on the axis (`circle`, `rArc`, all option sets and
  centre modes). Checked one by one: only `G1` lines of those arcs differ (all other lines identical), end point
  identical, G93 cut time within 0.02 % (the true arc is a hair longer than the polygon), deviation 0.0094–0.0193 mm
  → 0.0000–0.0009 mm (0.0009 is the replay tool's own 400-piece arc approximation), blocks 219 → 9 and 47 → 3.
- New input tests (4); random sweep of 2000 arcs centred on/near the axis (radii 0.01–150 mm, I/J and R, full
  circles, helices, centre offsets up to 0.003 mm), both cutting sides: no NaN, no bad F; the only cases over
  0.026 mm (3, also on 2.11.4) are sub-0.0125 mm helices inside the centre zone, where the replay compares Z at a
  point 0.012 mm from the pole — the cut is a plunge at the pole either way.


## 2.11.4 — polar input is refused, never read as Cartesian

### Fixed
- `G16` (Fanuc polar coordinates: X = radius, Y = angle) was not recognised: `G16 X20 Y45` was converted as the
  Cartesian point X20 Y45 (49.24 mm from the centre instead of 20 mm at 45°) and `G16` was copied to the output.
  It is now refused with the line number, like other input that cannot be converted exactly.
- Polar interpolation in the input (`G12.1/G13.1`, Haas `G112/G113`) and LinuxCNC polar words (`@` radius, `^` angle)
  passed through unconverted — now refused with a clear message.
- `G15` (polar off — the default) is removed with a note: Fanuc-style safety lines carry it and LinuxCNC 2.9 does not
  know it (`_gees` table: G15 is not a valid G-code), so such a program used to be refused by LinuxCNC itself.

### Golden baseline
- 144/144 identical. New input tests (6). Found while reading Fanuc G15/G16 bolt-circle examples.


## 2.11.3 — Signed-X only for lines really on the pole axis

### Fixed
- A line passing very close to the centre (up to 0.025 mm off the axis through the pole) was treated as lying **on**
  that axis and cut with C frozen (Signed-X). Its end point was then written up to 0.02 mm off, and the next block added
  its own error: **0.0268 mm** against the 0.025 mm tolerance in 3/3000 (one side) and 9/3000 (both sides) random
  near-pole polylines. A line now counts as on the axis only within a quarter of the chord tolerance (0.00625 mm by
  default); the others go to Index at Pole or are converted point by point.
  Random near-pole sweep: **0/3000** over 0.026 mm on both cutting sides (worst 0.0225 mm).

### Golden baseline
- 144/144 outputs **identical** (no change). `tools/sweeps.js` unchanged (worst 0.0225 mm). the FreeCAD test programs
  give identical output. New input test (the 0.0268 case, both sides); the "no fill" message test uses a line that
  still takes that path.


## 2.11.2 — fixes found by the 2026-10-11 research (63 test cases from other polar projects)

### Fixed
- **Merge of very short moves (< 0.15 mm)** — affected every machine:
  - a small Z step followed by an XY move became one ramp: a 0.1 mm step **up** cut 0.1 mm into the part, a 0.1 mm
    plunge left 0.1 mm uncut (the merge check looked at XY only — it now checks X, Y and Z);
  - the merged point was cut at the **next line's feed** (an F100 plunge at F1000, F50 at F3000) — points are no longer
    merged across a feed change, and a waiting point is written at its own feed.
- **Cutting side "Both sides" (Signed-X):** a Signed-X move shorter than 0.15 mm was still waiting when the return to
  the pole was decided; one block then swung X through 0 while C turned ~159° (0.12 mm off; random near-pole sweep:
  275/3000 over 0.026 mm → 9/3000, worst 0.0268, the same level as one side).
- The comment "using Pocket Fill" was printed when no fill is done → "converted point by point, no fill".
- The header showed the centre zone as "0.01 mm" when it is 0.0125 mm.

### Golden baseline
- 144/144 outputs changed **only in the header comment** (centre-zone number, e.g. `0.01` → `0.0125`, `3.00` → `3`);
  motion identical (checked line by line). New tests: input 76 checks.


## 2.11.1 — the page shows its version; no stale cached files

### Added
- The header shows the converter version (`v2.11.1`), so it is clear which version is open (an old page can stay in the
  browser cache on GitHub Pages after an update).
- Every script and stylesheet is loaded with `?v=<version>`: after a new release the browser fetches the new files
  instead of mixing cached old ones with the new page. `tests/ui.test.js` checks they all equal `package.json`.


## 2.11.0 — no "Safe retract Z" setting: retracts go to the program's own highest Z

### Changed
- `G53 G0 Z…`, `G28 … Z…`, `G30 … Z…` retracts become `G0 Z<the highest Z of the program>` (work coordinates —
  the CAM's own clearance height; drilling R planes count). Nothing about the machine is needed, so it is right on
  any machine (the converter stays universal). The setting, its field and the profile entries are gone.
- The retract is an ordinary rapid that the machine layout handles; afterwards Z is known (it was unknown before).
  An incremental mode set on the retract line (`G28 G91 Z0`) is switched off for the move and restored after it.
- Tilt layout: the router turns upright after a retract at that height, keeping the tool tip in place (rapids).
- A retract in a program with no Z of its own is rejected; `G28`/`G30` with no axis words still are.

### Added
- **Direction check** on the page (folding note under the Invert boxes): X must move away from the centre on
  `G0 X50`; on `G0 C90` the chuck must turn clockwise seen from the cutter (ISO / LinuxCNC); fix a wrong one in the
  controller rather than with the boxes; prove with an asymmetric test cut.

### Unchanged
- Golden 144/144 identical (none of those programs has a machine retract), sweeps unchanged.


## 2.10.0 — machine X settings made plain and required

### Changed
- **X Axis Min → "Cutting side"**: a choice *One side of the centre only* / *Both sides* (+ how far past the
  centre), with no default. The option `xMin` is unchanged (0 or −distance), so profiles keep working.
- **X Axis Max is required**: no default. Missing → the conversion stops with a message.
- The old defaults −1000 / 1000 ("no limit", kept by users who never set them) are gone: `convert()` refuses when
  `xMin` or `xMax` is missing; saved browser settings with exactly −1000 / 1000 are dropped so the page asks again;
  the two generic example profiles no longer carry them (a generic profile cannot know a machine's travel).
- Required fields are marked ⚠ on the page.

### Unchanged
- Motion: golden 144/144 identical, sweeps unchanged (all test programs state their X travel).


## 2.9.0 — no Tool Diameter setting: the diameter comes only from the program

### Removed
- The **Tool Diameter** field (page, profiles, `toolDia` option; old saved values are ignored). The CAM states
  the diameter, so the converter takes it from the program. The motion never depended on it.

### Changed
- No diameter in the program → `( polar-cnc tool: T1 - no diameter in the program )`; the material map stamps the
  tool centre path and the page says so; Pocket Fill with Auto Stepover is refused (a fixed Fill Step still works,
  starting at r = 0.1 mm); the tilt layout refuses a ball tool with no diameter in `tool.tbl` or the program.
- Golden baseline: the test programs now state their diameter as a CAM comment (`(T1 D=6)`, `alt`: 10) instead of
  the setting. All 144 outputs gained exactly two comment lines (`(T1 D=6)` and `( polar-cnc tool: T1 D=6.0000 - the
  only tool listed, no tool change )`) and are otherwise byte-for-byte unchanged.

### Checked
- A FreeCAD test program (5 mm tool, profile, 5 pockets, concentric facing): T2 D=5 read, worst G1 deviation
  0.0151 mm, real feed along the path exactly 278 / 557 mm/min, X 0.30 … 66.74 (inside 0 … 113).


## 2.8.0 — cutter diameter from the tool comments of any CAM

### Added
- The tool diameter is read from the tool comments of **any CAM**, not only Fusion and Kiri:Moto: Mastercam
  (`TOOL DIA. - .25`), FreeCAD (`(TC: 5mm Endmill)`, `(Compensated Tool Path. Diameter: 5.0)`), CamBam-style
  `( T1 : 6.0 )`, APT/CL `(TOOL/MILL,3.175,...)` (Carbide Create), generic `Tool Diameter: / DIA / Ø`, and a size
  with a unit inside a tool name (`5mm`, `End Mill (6 mm)`, `1/4"`). A comment without a tool number belongs to the
  tool change that follows it (before any motion), else to the tool already selected; a program that never selects a
  tool uses the stated one. A stated diameter beats a size in a name; `( polar-cnc tool: ... - from the tool name "…" )`
  marks the weaker source. Stock, part, hole and feed comments are ignored.
- Warning `( !! two diameters for T.. )` when one tool is given two different diameters.

### Fixed
- Mastercam's `| D1 |` (the diameter OFFSET register) was read as a 1 mm diameter.
- Tool numbers written with leading zeros (`T02` in a comment, `T2` in the code) now match.

### Unchanged
- Golden 144/144 identical, sweeps worst 0.0225 mm.


## 2.7.0 — layout "XZC + tilt": ball-end tools lean while cutting

### Added
- **Machine layout selector** (page and profiles): *XZC* (today's machine, unchanged) or *XZC + tilt* — a router that
  tilts in the X-Z plane. Tilt letter **B** by ISO 841 / LinuxCNC (A as a rename), *invert tilt*.
- `src/core/layout-xzcb.js`: built on the XZC layout. **Ball-end tools lean** by the set angle while cutting, with the
  **ball centre kept exactly on the CAM path**; the lean is reduced automatically where the X travel or the tilt travel
  would not allow it (X = r + K·sin B, Z = z + K·(cos B − 1), K = pivot → ball centre; C unchanged). Each XZC block is
  split so the tilt adds at most 0.08 × chord tolerance (K·dB²/8). Other tools stay at B 0; B returns to 0 before a tool
  change, after a machine retract and at the end. G43 stays valid.
- Tool lengths from the machine's own **LinuxCNC `tool.tbl`** (load the file or paste it); ball-end tools listed by
  number or marked "ball" in the tool-table comment. Pivot length, tilt travel and tool lengths have **no defaults** —
  missing values stop the conversion with a message.
- Simulator: reads B, shows the tool tip (not the head), draws the **tilted tool**, Tilt telemetry; the X-travel check
  uses the head's real X.
- `tests/tilt.test.js` (150 checks): joint-space replay (X, Z, B, C linear) with the ball centre recovered and compared
  with the CAM path — worst **0.0229 mm** (leans up to 45°, 43 programs incl. 40 random), rapids ≤ 0.39 mm, X and B
  inside their travel, flat tools upright, upright at tool change / retract / end, letter A + inverted, refusals.
  `tests/lint.test.js` also checks the tilted output of every golden program.

### Unchanged
- Layout XZC: golden 144/144 identical, sweeps worst 0.0225 mm.

## 2.6.0 — the converter in three stages (no output change)

Step 2 of the plan for other machine layouts (a tilting router, XZC + B) and for use inside another CAM
(Kiri:Moto). **The output is byte-for-byte the same.**

### Changed
- `src/core/converter.js` was one 1,600-line function. It is now three stages:
  - `src/core/gcode-input.js` — reads and checks the Cartesian program (units, G91, cycles, retracts, tools,
    every rejection with its line number) and hands every line over **in order**: motion as events, the rest
    as text;
  - `src/core/layout-xzc.js` — the machine layout XZC: pole handling, segmentation, C unwrap, G93 blocks;
  - `src/core/converter.js` — options, the common header and end, clean-up; `convert(text, options)` is
    unchanged for its users.
- The code was **moved, not rewritten**: a script cut the old function into the stages line by line and
  stopped if any anchor line had moved; only the glue between the stages is new.
- `index.html` loads the two new files.

### Verified
- `npm test` (golden 144/144 identical), sweeps (worst G1 0.0225 mm), and a one-off comparison of the old and
  the new converter on 13,671 program × settings combinations (all golden programs plus 1,500 random programs
  with lines, arcs, rapids, comments, tool changes, cycles, G91, inches, G53/G28, M0/M30, × 9 option sets
  covering every centre mode and output profile): **0 differences**, identical error messages.

## 2.5.0 — real feed on short blocks, Kiri:Moto tool list, works offline

The remaining findings of the 2026-10-07 review, fixed.

### Fixed
- **The cutting feed was silently lowered on short blocks.** Every G1 block had a minimum time of 0.06 s
  (F_g93 ≤ 1000), so a block shorter than feed × 0.06 s ran slower than the CAM asked: measured on a circle
  r20, F1500 ran at ~844 mm/min and F3000 at ~856. The floor is now 0.6 ms — below LinuxCNC's 1 ms servo
  period, so it never changes motion; the controller alone limits speed (as DECISIONS.md says). Now F1500 →
  F1500. Golden: 68 outputs changed, **only** the F word of blocks that sat exactly at F1000 (checked line
  by line: same lines, same geometry).
- **Cutter diameter from Kiri:Moto programs** was not read (its tool list is a `;` comment,
  `; tool#=2 flute=3.175 len=20 unit=metric`); the Tool Diameter setting was used instead. Now read, inches
  converted. Also: a program that lists exactly **one** tool and has no tool change at all now uses that
  tool's diameter (was the setting).
- **Radial lines** (C constant, e.g. a cut along X at Y=0) were cut into ~1.4 mm pieces for nothing; X alone
  traces them exactly, so they now go in 5 mm pieces like Signed-X lines. Golden: 29 outputs changed, all
  with fewer G1 blocks, identical rapids/comments, same deviation (checked by replay).
- `G53 G0 X.. Y..` (Fusion's optional end park) was rejected while `G28 G91 X0 Y0` was skipped. Both
  are skipped now (not moving can hit nothing); a Z on the same line is still the safe retract.
- Numbers in exponent form (`F1E3`) were half-read and left a stray `e3` line. Refused with the line number.

### Changed
- **three.js is included** (`lib/three/`, r134, MIT, unmodified npm files) instead of being loaded from a CDN:
  the page now works **without internet** (checked in Chromium from disk: no network request, no error).

## 2.4.1 — arcs, feed and dwell checked like LinuxCNC checks them

Found in a full code review (2026-10-07). Output of every existing test program is unchanged
(golden 144/144); only programs that were converted wrongly before now behave differently.

### Fixed
- **A half circle in R format could become a straight line.** If the CAM rounded the end points so
  they were a hair more than 2R apart (0.0001 mm is enough), the arc was cut as a straight chord —
  10 mm off on an R10 half circle. It is now a half circle, as in LinuxCNC (`interp_arc.cc`, "allow a
  small error for semicircle").
- **An I/J arc whose end radius differs slightly from its start radius** (rounded I/J) ended next to
  its end point instead of on it. It is now a spiral that ends exactly on the end point — what
  LinuxCNC does.
- **No more invented feed rate.** A program without an F word was cut at 500 mm/min that nobody chose.
  A cut (G1/G2/G3 or drilling cycle) with no feed rate is now rejected with its line number, as
  LinuxCNC rejects it.

### Added
- Arcs LinuxCNC 2.9 would refuse are refused here too, with the line number and LinuxCNC's default
  tolerances: no I/J/R, R too small to reach the end point, R-format full circle, zero radius, end
  radius too far from the start radius. Before, the first three became straight lines.
- A dwell `G4 P` of 60 or more gets a warning comment (and a count at the end of the file): in
  LinuxCNC P is seconds, while Fanuc-style posts write milliseconds (`G04 P2000` = 33 minutes).

### Docs
- README: test table brought up to date (144 golden outputs, 80 geometry cases, the input/lint/words
  tests), drilling cycles are expanded (not rejected), the chuck-end note depends on the installed
  `.ini`, the removed `T_crot` no longer mentioned. `index.html` header: SPDX line, no "C velocity
  limiting" (removed in 2.3).

## 2.4.0 — exact near the centre, every line and arc within tolerance

Found while checking the converter against the Core R-Theta 4-axis printer research (bug list B1-B9).

### Fixed
- **Lines passing NEAR (not through) the centre were cut off their path**: 0.05-0.5 mm away up to
  0.36 mm off (Index at Pole turned C at the line's closest radius), 0.8-1.8 mm away up to **3.8 mm**
  off (Pocket Fill cleared a disk round the centre). A zig-zag facing pass whose rows passed 1 mm from
  the centre was 1.9 mm off. The centre zone is now automatic — half the chord tolerance — so only
  lines passing practically through the pole get special handling; all others are converted exactly.
  Measured over 1,424 lines 0-3 mm from the centre, flat and ramping: worst 0.0225 mm.
- **Arcs were not split for the polar transform** (a code comment said they were): each arc chord went
  out as one block, and away from the pole the machine bows it — 0.034 mm on off-centre arcs. Every
  chord is now split, with half the tolerance for the chord and 0.4 for the polar step.
- **An arc leaving the pole was a spiral** (0.50 mm off): C now turns first at r = 0, as lines did.
- **Merging of tiny moves undid accuracy**: near the pole it re-joined the fine pieces; a waiting point
  was thrown away instead of written when the next one could not be merged; and a point at a corner
  (between arc chords or CAM lines) was skipped, cutting the corner. Merging now checks the real error
  of the merged block and keeps any point that is not on it.
- The validator (tests/lib/replay.js) did not understand R-format arcs, so they were never really
  checked. It does now (self-checked against equivalent I/J arcs).

### Changed
- **Local segmentation**: each piece is sized by its own distance from the pole and accepted by its
  measured error, instead of sizing a whole line by its closest approach. About 20% fewer blocks over
  the test programs (half as many on passes through the centre) at the same or better accuracy — this
  also helps LinuxCNC, which does not blend moves that involve a rotary axis.
- **Center Zone** field (Advanced): empty = automatic. A stored 2 mm (the old default) is upgraded to
  automatic; the shipped profiles no longer set it. An explicit larger zone keeps the old behaviour.

### Tests
- geometry: 80 cases (was 33) — near-pole lines and ramps, arcs at the pole, R arcs, all also with X Min 0.
- Sweeps used to validate this release (not part of `npm test`): 1,424 near-pole lines, 3,000 random
  arcs (I/J and R, flat and helical), 800 random polylines with tiny segments and sharp corners — all
  within 0.0225 mm.


## 2.3.1 — author's machine profile follows the mill-style Z numbering

- The author's machine now numbers machine Z like a mill (Z0 = home park, 10 mm from the switch,
  negative towards the chuck), so a CAM's `G53 G0 Z0` is a safe retract there. The example profile's
  Safe retract Z is therefore `0` (was 590, which with the new numbering would be beyond the soft limit).
- `examples/linuxcnc-vismach-xzc-lathe` synced with the real machine: final X layout (switch X -20,
  0 … 113), mill-style Z (-590 … 7, park 0), C 120 deg/s; stock face at machine Z -490.


## 2.3.0 — valid G-code guaranteed, simpler page

### Fixed
- **"Nested comment found" in LinuxCNC.** An input line with a comment, such as `G21 (mm)`, was copied
  into one of the converter's own comments, giving `( absorbed modal from: G21 (mm) )`. LinuxCNC refuses
  a comment inside a comment, so the program would not load. Same for `G53`/`G28` retracts with a
  comment. Found on the author's machine with a real benchmark program.
- Four of the converter's own messages also contained parentheses (`move(s)`, `(not on the pole axis)`,
  `(Fanuc PS214 list)`, the tool note `(from settings ...)`) — reworded.
- Safety net: before the file is written, any parenthesis inside a comment is removed (its text is
  kept) — whatever its source, including a bad comment in the input.

### Added
- `tests/lint.test.js`: every output line of every golden program and of real-world inputs (including
  the failing benchmark, `tests/fixtures/benchmark-comments.ngc`) is checked against LinuxCNC rules —
  no nested or unbalanced comments, no duplicate words, one motion code per line, an F on every move in
  G93.

### Changed — simpler page
- Removed: the inert "G93 inverse-time" button (output is always G93), the four Center Crossing buttons
  (Auto chooses; **X Axis Min** now decides the machining side), Center Fill Step, Center Retract and
  Auto stepover (pocket-fill details; defaults are used).
- Chord Tolerance and Center Threshold moved to a closed **Advanced** section.
- Options without a control on the page are still honoured when they come from a loaded profile or the
  browser's saved settings — nothing in a profile is lost.


## 2.2.1 — machining side made explicit

- **X Axis Min now says what it also controls: the machining side.** `0` = one side of the centre only
  (X never negative; cuts through the centre turn the chuck 180 deg at the centre). A negative value
  allows crossing the centre by up to that many mm, only on cuts that pass exactly through it.
  The old help text also wrongly said the fallback was Pocket Fill (it is Index at Pole since 2.2.0).
- Fixed: with X Min = 0, a RAPID crossing the centre still dipped to about -1.4 mm (inside the small
  centre zone). It now stops at the centre, turns C there and leaves on the same side. New test.
- `profiles/example-marioskiv-holzmann-xzc` (now `example-lathe-xzc-one-side`) updated to the final layout: X 0 … 113, one side.


## 2.2.0 — machine-independent, everything in the program kept

The converter is no longer tied to one machine, and it never drops a word from the program.

### SAFETY — fixed
- **`G43 H` (tool length) was dropped** when it shared a line with a Z move (`G43 Z15 H1`, as Fusion
  writes it): tool length compensation never switched on. It is now kept.
- **Spindle/coolant words on a motion line were dropped** (`G0 X30 Y10 S20000 M3`): after a tool change the
  next tool entered the material with the spindle stopped. Every non-motion word is now kept and emitted
  before the move (stop codes `M0/M1/M2/M30/M60` after it), as a controller executes a line.

### Changed — geometry here, dynamics in the controller
- Removed the converter's C velocity limit, C acceleration, C motor RPM and corner feed multiplier. The
  controller already limits every move to its axes' velocity and acceleration (LinuxCNC
  `getStraightVelocity()`; same rule documented for g2core/TinyG), so these duplicated machine data and
  could disagree with it. G93 times now carry the CAM's feed along the real 3-D path; coordinates are
  unchanged (verified on all 144 golden programs with the F words removed).
- Simulator timing is the program's own; the info line shows the **peak chuck speed the program asks
  for**, instead of a machine-specific limit.

### Added
- **Machine output profile**: rotary axis letter (C/A/B), X as radius or diameter, invert rotary, invert X.
  Settings are remembered by the browser and can be **saved/loaded as a profile file**; `profiles/` ships
  generic examples and the author's machine. The simulator reads output through the same profile.
- **Tools**: active tool tracked through `T`/`M6`; its diameter is read from the CAM's tool comments
  (e.g. `(T2 D=3. ...)`) or falls back to the setting; used for pocket fill and the material map.
- **Drilling cycles expanded**: `G81, G82, G83, G73, G85, G89`, with `G98/G99`, `R`, `Q`, `P`, modal holes,
  `G80`. Tapping/threading/spindle-stop cycles are still rejected.
- Rejected with the line number: rotary-axis words in the input, multi-turn arcs (`G2/G3 P`).
- Comment-only lines from the CAM are kept.
- `examples/linuxcnc-vismach-xzc-lathe` (moved from `linuxcnc/vismach-sim`), clearly marked as one machine.
- Tests: `words.test.js` (30 checks); every shipped profile is loaded through the page in `ui.test.js`.


## 2.1.0 — machine-safe retracts, material removal, LinuxCNC machine simulation

### SAFETY — correction to 2.0.0 / 2.0.1
2.0.0 passed `G53 G0 Z0` and `G28 G91 Z0` straight to the machine as "safe retracts". That holds
on a mill, where machine Z0 is the top of Z. **On this lathe conversion the Z home switch is at the
tailstock end, so machine Z0 is at the chuck end: those lines would rapid the carriage toward the
chuck.** `G28`'s stored position is also machine 0,0,0 unless set with `G28.1`. Do not run programs
containing `G53`/`G28` produced by 2.0.0 or 2.0.1.
- Machine-coordinate Z retracts are now replaced by `G53 G0 Z<Safe retract Z>`, a machine-specific
  value the user enters (e.g. the Z home park position). With no value, they are rejected with an
  explanation. `G28`/`G30` X/Y parks are skipped; `G28`/`G30` with no axes are rejected.

### Added
- **Material removal depth map** in the simulator (`src/core/material.js`): the face turns with
  the chuck and shows what has been cut; cells cut by a rapid are red and reported as collisions.
- **LinuxCNC machine simulation** (`linuxcnc/vismach-sim/`): a vismach 3D model of the lathe and an
  INI with the real machine's motion settings, so programs can be run through LinuxCNC's own planner
  with no hardware.
- Tests: `material.test.js` (9 checks), more input checks (32), UI check for collision warnings.

### Fixed
- Simulator X velocity is 18 mm/s, the machine's `[AXIS_X] MAX_VELOCITY` (was 25).


## 2.0.1 — simulator matches the machine

Found by running real converter output (Fusion "LinuxCNC" and "grbl" posts) through the simulator,
and by comparing with LinuxCNC vismach and Kiri:Moto's animator.
- `G53 G0 Z0` was shown as a descent onto the stock at the start and end of the program. Retracts
  (`G53`, `G28`, `G30`) are now shown going up to a safe height; `G28 G91 X0` as a park.
- `G28 G91 Z0` was shown as a cutting move to Z0. A retract is never displayed as a cut.
- While Z is unknown at the start, the tool was drawn at Z0 (on the stock). It now starts at the
  safe height and at the outer radius, where the machine actually starts.
- Rapid time ignored the C axis: a 180-degree spin at the pole took 0.001 s instead of 2 s. Every
  block now takes at least as long as its slowest joint needs (C 90 deg/s, X 18 mm/s, Z 25 mm/s from the
  machine's .ini), as LinuxCNC enforces. Cycle-time estimates are now realistic (acceleration is
  not modelled, so they are still a lower bound).
- Blocks with a large C turn were drawn as one straight chord (a 90-degree rapid at r = 30 mm drew
  its midpoint at r = 21 mm). Such blocks are now subdivided in joint space where the chord would
  deviate by more than 0.05 mm; fine converter output is not inflated.
- Page diagnostics ignore the symbolic retract/park positions and compute the C rate from the
  commanded time, so subdivided blocks report correctly.
- New `tests/sim.test.js` (14 checks).


## 2.0.0 — project restructure and input safety

### Fixed — input handling (found by testing real CAM post output)
Researched against the LinuxCNC interpreter source (`convert_home`, percent handling) and the
output of Fusion's "LinuxCNC" and "grbl" posts.
- `G53 G0 Z0` (Fusion LinuxCNC safe retract) was **dropped**, and the next rapid went to work Z0 —
  the stock surface. At program end the tool went down instead of up. Now passed through.
- `G91 G28 Z0` (Fusion grbl retract) was converted into a **cutting move to Z0**. Now passed
  through and followed by `G90`; `G28 G91 X0 Y0` becomes an X park.
- **The first rapid of every program went to `X0 C.. Z0`** (chuck centre at work Z0) because the
  pole-spin logic mistook the unknown start position for the pole. Introduced in 1.x; the golden
  baseline had recorded it as "expected". Now the first rapid goes straight to the target.
- With Z unknown (start, after a retract, after `M6`) rapids no longer invent a Z: X/C move at the
  current height, then Z.
- `G91` input reached the machine, which then read every absolute value as a move. Now converted.
- `G20` (inch) programs came out 25.4x too small. Now converted to mm.
- `%` landed mid-file, where LinuxCNC does not accept it. Now first and last line.
- `G90 G54` dropped the `G54`. Work offsets are now kept.
- Cutter compensation, canned cycles, coordinate offsets, probing, `G90.1`, `G93` input,
  `G18/G19` arcs, and cuts before the position is known are rejected with the line number.
- `G17` no longer raises a false warning.
- Page: a failed conversion now clears the output and disables Export (the previous program could
  otherwise be exported by mistake); travel-limit warning uses the corrected option parsing.
- New `tests/input.test.js` (28 checks) covers all of the above.


**No change to converter output.** Proven byte-for-byte on 156 program/mode/settings combinations
(54,833 lines of G-code) and on the simulator's parsed toolpath (51,971 points).

### Structure
- Split the 2,657-line single `index.html` into `css/`, `src/core/` (pure, testable),
  `src/sim/` and `src/ui/`.
- The converter no longer reads the DOM: `convert(text, options)` with `DEFAULT_OPTIONS` as the
  single source of truth. The settings panel is read in one place (`src/ui/settings.js`).
- Node test suite (`npm test`) and GitHub Actions CI.

### Fixed
- `0` was treated as "missing" in three settings (`parseFloat(v) || default`):
  X Min 0 silently became -1000 (allowing Signed-X into negative X the machine may not have);
  Center Fill Step 0 could never disable the fill; Center Retract 0 could never disable the retract.
- Non-ASCII characters in emitted G-code comments are now escaped in the source, so output is
  identical however the script file is decoded. Scripts and CSS declare UTF-8 explicitly.
- Fallback defaults inside the converter disagreed with the form (chord tolerance 0.05 vs 0.025,
  C velocity 1800 vs 3600). Now one set of defaults, enforced by a test.

## 1.x — correctness fixes (see commit history)
Centre handling (Signed-X exactness, Index at Pole, threshold 10 -> 2 mm), segmented rapids,
dropped-rapid fix, G94 removal, clamp diagnostics, and the rosekins-based verification harness.
