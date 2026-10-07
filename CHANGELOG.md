# Changelog

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

The remaining findings of the 2026-10-07 review, fixed at Marios's request.

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
- `profiles/example-marioskiv-holzmann-xzc` updated to the author's final layout: X 0 … 113, one side.


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
