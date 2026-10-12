# Work log — newest first

One entry per working session: what was asked, what was done, what is left, what Marios decided.
Short and factual. Current state lives in `STATUS.md`, permanent decisions in `DECISIONS.md`.

---

## 2026-10-12 (2) — FreeCAD addon: feasibility proven on real FreeCAD 26.3 (no repo code changed)

**Marios:** has FreeCAD 1.1, tries 26.3; wants it done properly as an addon, first for himself, idea to FreeCAD later;
research only, no code changes; verify it really works and is professional.
**Done:** installed FreeCAD 26.3.0 headless (conda-forge 2026.09.16), built a throw-away addon in /tmp and a real CAM
job → `references/freecad-addon-feasibility-2026-10-12.md`. Works: XZC machine valid, addon discovery (needs an
`Init.py`), post gets arcs/feeds (mm/s)/tool diameter, G93 lines pass as-is, `G0 C0` poses must be dropped; end-to-end
output identical to the page (0.0094 mm). 1.1 cannot do it. Decision on building the real addon: waiting for him.

---

## 2026-10-12 — where should the converter live? (analysis, no code change)

**Marios:** compare FreeCAD addon / Kiri hook / LinuxCNC `userkins.comp` (real time, Mesa 7i92) and give a roadmap.
**Done:** `references/architecture-options-2026-10-12.md`. Read LinuxCNC 2.9.10 `control.c`: in coordinated mode the
joint positions come straight from `kinematicsInverse()` of the planner's XYZ position, no joint speed clamp → near the
centre: following error or silent stepper stall. Recommended: keep the offline core (JS reference, golden tests as the
spec), FreeCAD addon long-term, Kiri optional, **no real-time kinematics**. Waiting for his decision; PR #6 still open.

---

## 2026-10-11 (10) — 2.11.2: the two bugs fixed (Marios: yes)

**Done:** merge of short moves (3-D check, never across a feed change, waiting point at its own feed) and the both-sides
Signed-X flush; "no fill" message; centre-zone number in the header. No line-length guard (his decision). Tests: input
76 checks, golden 144/144 header comment only (explained in CHANGELOG), sweeps unchanged, near-pole both-sides sweep
275 → 9 / 3000; his two FreeCAD programs unchanged (worst 0.0151 mm, feeds 278/557); Chromium page v2.11.2.

---

## 2026-10-11 (9) — Bird re-checked, more polar printers, 63 test cases → 2 real bugs (fix waiting)

**Marios:** re-check Bird and more polar printers ("many examples, the converter must be flawless"); is the 255 limit
certain; centre-height compensation not needed (router base milled on the machine → DECISIONS).
**Done:** two more searches (`references/research-2026-10-11.md` part 2). Line limit verified in LinuxCNC 2.9.10
source: ≤ 252 chars (LF) / 251 (CR LF). **Bugs confirmed by me:** (1) merge of moves < 0.15 mm: Z step → ramp
(0.1 mm gouge) and wrong feed; (2) both-sides Signed-X short move → 0.12 mm off. Fixes + messages + line-length
guard prepared in a scratch copy: all tests pass, sweeps same, golden header comment only. **Not applied — waiting
for his yes** (CLAUDE.md rule 1). Then Marios: leave the line length alone (practically never happens) → guard
removed from the prepared fix (DECISIONS). Still open: rare 0.0268 mm near the pole.

---

## 2026-10-11 (8) — PR #5 merged; research: other projects, simulator, trixie, CAM

**Marios:** PR #5 merged (v2.11.1 on `main`). Asked: where are the notes (answered: `docs/handoff/` in the repo,
auto-loaded by `CLAUDE.md`; artifacts are not read by later sessions), open items, then serious research: more
projects like Bird's, ideas for the simulator, what LinuxCNC on trixie needs, and again polar-inside-a-CAM.
**Done:** four read-only searches → `references/research-2026-10-11.md`. Verified myself: arcs around the centre
become polygons (R10 circle = 127 blocks, could be 8 exact); a CAM comment > 255 chars passes through (LinuxCNC limit).
Corrected two wrong sub-report claims (convert() returns text; Kiri tool comments already read).
**Proposals waiting for his yes (nothing changed):** exact arcs around the centre; 255-char guard; centre-offset
compensation / warning; simulator deviation + axis-speed colouring, finer height map, line link, report;
FreeCAD addon later. Branch restarted from `main`.

---

## 2026-10-11 (7) — PR #4 merged; "nothing changed" = browser cache; 2.11.1 version on the page

**Marios** merged PR #4, then opened https://marioskiv.github.io/polar-cnc-converter/ and still saw X Axis Min −1000 /
X Axis Max 1000 / Safe retract Z −2. **Checked:** `main` has 2.11.0 and the "pages build and deployment" run
(18:57, from `main` 2b64747) succeeded — he saw the **old page from his browser cache**; −2 was never a default, it is
a value his browser had saved. (The sandbox cannot reach github.io to look.) **Done (2.11.1, his yes):** version shown
in the header; `?v=<version>` on every script/css so a new release never mixes with cached files; test checks it.
Told him: Ctrl+F5 once. **Note for releases:** bump the `?v=` in `index.html` with `package.json` (the UI test fails
otherwise).

---

## 2026-10-11 (6) — direction check added to the page

**Marios:** yes to the written direction check; reminded we already settled his axis directions. **Checked the notes:**
X was settled 2026-10-04 (`STEP_SCALE -400`, "+" moves away from the switch = away from the centre, confirmed on the
machine). **C has never been checked on the machine** (STATUS open item). **Done:** a folding "Direction check"
under the Invert boxes (X away from centre; mark on chuck, `G0 C90` → chuck turns clockwise seen from the cutter;
fix in the controller rather than with the boxes; F test cut). His profile keeps both boxes unticked.

---

## 2026-10-11 (5) — 2.11.0: Safe retract Z removed ("β"); directions asked

**Marios:** Safe retract Z → (β); X Axis Max without default (done in 2.10.0); reminded that other machines will use
the converter; asked whether the directions (Invert rotary / Invert X) can be known.
**Done (2.11.0):** G53/G28/G30 Z retracts → `G0 Z<program's highest Z>` (pre-scan of absolute Z and cycle R, mm),
spliced in as an ordinary rapid + marker; G91 on the retract line restored after; tilt layout turns upright at the
marker (tip kept). Setting/field/profile entries removed. Tests updated (input 71, sim 12), golden unchanged, sweeps.
**Answered on directions:** the converter cannot know them (they depend on wiring / `.ini` sign / which side the
tool sits); LinuxCNC convention: +X away from the centre, +C = the CHUCK turns clockwise seen from the cutter
(tool counter-clockwise relative to the part; checked: CAM point (0,10) → C90). A 1-minute
check without cutting is possible (mark on the chuck, `G0 C90`; `G0 X50`) — proposed adding it to the page; final proof
is the "F" test cut. Waiting for his answer.

---

## 2026-10-11 (4) — 2.10.0: Cutting side + X Axis Max required; Safe retract Z explained

**Marios** asked what X Axis Min / X Axis Max / Safe retract Z do, wants them plain, with ticks/choices and
"required" warnings. Proposed first; his answers: **X Axis Max: keep, required. X Axis Min: yes, make it clear.
Safe retract Z: asked why his machine is "opposite" to a mill** — answered: only the installed `.ini` numbers Z like a
lathe (Z0 at the chuck end); the mill-style `.ini` (delivered 2026-10-04, in `machine-config/`) makes `G53 G0 Z0` go
up to home like any mill (then Safe retract Z = 0, touch off Z again). **No change to Safe retract Z yet** — waiting
for his choice: keep it (explained better) or replace G53/G28 with the program's own highest Z.
**Done (2.10.0):** "Cutting side" radio (one side / both + distance), X Axis Max required, no −1000/1000 defaults,
old saved defaults dropped, generic profiles without X travel. Not merged to `main` yet.

---

## 2026-10-11 (3) — second FreeCAD program + his converted output checked

**Marios** sent a revised FreeCAD program (MillFace001 first at −2, Profile at −5/−8/−10 with 4 rings 0.4 mm apart,
four 20 mm pockets at −5/−8/−10) and the output he made on the page. **Checked:** his output's motion is identical to
ours; worst G1 deviation 0.0151 mm, real feed exactly 278/557 mm/min, X 1.00 … 67.74 (no negative X), depth −10.
**Found:** his page still had the DEFAULT X travel −1000 … 1000 (header line) — harmless for this program (never
crosses the centre) but must be set to X min 0 / X max 113 (and Safe retract Z 590) before real programs.
Told him: face-first fixed; plunges still straight down (3 mm into faced stock at 278 mm/min) — slower plunge or helix;
first profile ring is a full 5 mm slot 3–5 mm deep; innermost facing circles are C-speed limited (slower than shown).

---

## 2026-10-11 (2) — PR #3 merged

**Marios** asked to update GitHub with all changes. Opened PR #3 (2.8.0 + 2.9.0), CI green; my merge call was blocked
by the session's safety check (no merge to `main` without a human), so **Marios merged it himself** (merge commit
`9e24f2e`). `main` = v2.9.0. Branch restarted from `main` for later work.

---

## 2026-10-11 — his FreeCAD program checked; 2.9.0: Tool Diameter setting removed

**Marios:** made a rough FreeCAD CAM (5 mm 2-flute Izar, T2, profile + 5 pockets + facing, feeds 278/557) and asked
whether it converts correctly; the program states the diameter, so **remove the diameter option** from the converter.
**Checked his program:** converts without errors; T2 D=5 read; worst G1 deviation 0.0151 mm; real feed along the
path exactly 278/557 mm/min; X 0.30 … 66.74; depth −17; C up to ~9,400° (limit 99,999). The page asks up to 289 rpm
of the chuck on the innermost facing circle (r 0.3 mm) — LinuxCNC will slow those (C max 120 °/s delivered), so the
~23.5 min estimate is optimistic. **Told him (FreeCAD set-up, not converter):** step-downs are large (profile 0 → −7
in one pass, pockets 5 mm per step, straight plunges), and the facing (−2) runs LAST after everything else — face
first; use ramp/helix entry; check G43 H2 has T2's length in `tool.tbl`.
**Done (2.9.0):** Tool Diameter field/option/profile entries removed; missing diameter → "no diameter in the program",
material map shows centre path + note, Pocket Fill auto-stepover refused, tilt ball needs a diameter. Golden: inputs
now carry `(T1 D=..)`; 144/144 outputs gained exactly two comment lines, otherwise identical. Tests 70 input checks,
sweeps worst 0.0225 mm, Chromium check, release zip tested. Not merged to `main` (he said "not yet" on 2026-10-08).
**Still open:** his answer on FreeCAD vs Kiri:Moto.

---

## 2026-10-08 (2) — FreeCAD or Kiri:Moto as the home of the converter?

**Marios:** not merging 2.8.0 yet. Asked whether the converter should go into FreeCAD rather than Kiri:Moto; he
believes being part of a CAM computes all operations better.
**Answered (no decision yet):** partly right — inside a CAM the operations can be planned for polar (no centre
crossing, spiral facing, feed limited by C speed near the pole, tilt from the surface, machine simulation); as a post
it only transforms. The transform math is the same either way. Recommended **FreeCAD** as the long-term home (he
uses it, CAD + CAM, official post-processor extension, large community, its CAM is building a rotary machine model
and RotarySurface) with a thin **FreeCAD post that calls our converter** first (one codebase, no permission needed);
Kiri `gcodeProc` stays the cheap JS proof. Costs said plainly: Python vs our JavaScript, LGPL for code inside
FreeCAD, slow core review, FreeCAD CAM sim is 3-axis. Real test cuts first. **Waiting for his choice.**

---

## 2026-10-08 — 2.8.0: cutter diameter from any CAM

**Marios said:** yes — read the tool diameters from all CAMs.
**Done (2.8.0):** `scanToolDiameters()` in `gcode-input.js` reads Fusion/HSM, Mastercam, FreeCAD, Kiri:Moto, CamBam-style,
APT `TOOL/MILL` (Carbide Create), generic `Tool Diameter:/DIA/Ø` and a size with a unit in a tool name. Untagged
comments bind to the next tool change (before motion) or the current tool. Stated diameter beats a name size (marked
in the output comment). Conflicting diameters → warning. **Bug found and fixed:** Mastercam `| D1 |` (offset register)
was read as D = 1 mm; tool numbers with leading zeros did not match. Web research on CAM formats was thin (forums
blocked); formats taken from forum snippets — Vectric/Estlcam/SheetCam exact output unverified, covered by the generic
rules. Tests: input 67 checks (+10), golden 144/144 unchanged, sweeps worst 0.0225 mm. His FreeCAD program now gives
`T1 D=5`. **Still needed from him:** feed rates in the FreeCAD Tool Controller.

---

## 2026-10-07 (end, 2) — FreeCAD program refused: no feed rate

**Marios** converted a FreeCAD program (post `linuxcnc_post`, tool "TC: 5mm Endmill") and got "Line 25 … cutting
move without a feed rate". **Cause:** the program has no F word anywhere: the FreeCAD Tool Controller feeds are 0
(the default), so the post writes no F. The refusal is correct (2.4.1 rule; LinuxCNC itself refuses a G1 without F).
Checked: the same program with `F600` on the first G1 converts cleanly (no warnings, radius up to ~70.6 mm, fits X).
**Told him:** set Horizontal/Vertical Feed (and spindle speed) in the Tool Controller and post again.
**Noticed, not changed:** FreeCAD tool comments `(TC: 5mm Endmill)` / `(Compensated Tool Path. Diameter: 5.0)` are
not read (the page's Tool diameter, default 6, is used — set it to 5); FreeCAD Z0 is the stock bottom (Z positive,
clearance Z40) → touch off accordingly. **Offered (waiting for his yes):** read the FreeCAD diameter comment.

---

## 2026-10-07 (end) — PR #2 merged

**Marios** pressed the PR button in the app and asked what it is and to update the repository in his account.
Explained the PR; CI green and no conflicts → merged PR #2 into `main` (merge commit `3c79a11`). His GitHub
repository now has v2.7.0. Branch `claude/youthful-goldberg-a6qv5t` restarted from `main` for later work.

---

## 2026-10-07 (late night, 6) — 2.7.0: layout XZC + tilt (ball-end lean)

**Marios said:** the router may not reach 90° (X travel) and big parts cannot be machined on the periphery — then chose
option 2: tilt that changes while cutting, ball-end, automatic, as far as it fits.

**Done (2.7.0):** layout selector XZC / XZC + tilt (page, profiles, `normalizeOptions`). `layout-xzcb.js` on top of the
XZC layout: K = pivot→ball centre per tool (pivot setting + `tool.tbl` length − ball radius); X = r + K sin B,
Z = z + K (cos B − 1), C unchanged; lean auto-limited by X and B travel; blocks split so the tilt error ≤ 0.08·tol;
upright at tool change / after machine retract / end; flat tools upright; missing pivot/travel/length refused.
**Found while building: G43 stays valid** (research note §3 corrected). Simulator: B read, tool tip recovered, tilted
tool drawn, Tilt telemetry. Tests: `tilt.test.js` 150 checks (ball centre worst 0.0229 mm), lint on tilted outputs,
golden 144/144 unchanged, sweeps, Chromium check with screenshots.

**Open:** B direction on the real machine needs a test cut; tilt following the shape needs CAM orientation (Kiri);
fixed B for non-ball tools; periphery input. Machine not built: nothing for the `.ini`/`.hal`.

---

## 2026-10-07 (late night, 5) — which CAM: not Fusion; FreeCAD checked

**Marios said:** most likely **not Fusion** for the tilted work (no subscription) — maybe Kiri:Moto or FreeCAD;
Fusion perhaps for plain XYZ. If merged into Kiri one day, it should feel like a **professional program**.

**Done:** FreeCAD CAM source read (`e326ee2`, dev 2026-10-07) → `references/freecad-cam.md`: indexed tilt per
operation and a machine kinematic model, continuous 4th-axis RotarySurface (tool radial), **no simultaneous
tilt**. Neither Kiri nor FreeCAD gives a tool orientation that changes while cutting.

**Proposed:** XZC + B layout in stages — B fixed per program for face work; periphery at B 90 from 4th-axis
programs (FreeCAD RotarySurface, Kiri lathe); simultaneous tilt for ball-end tools computed by the converter;
full tilt operations later inside Kiri. Waiting for his go-ahead.

---

## 2026-10-07 (late night, 4) — step 2 done: converter in three stages (2.6.0)

**Asked:** go-ahead ("NAI") for step 2, the restructure.

**Done:** `src/core/converter.js` (one 1,600-line function) split into `gcode-input.js` (reads/checks the CAM
program, emits events in order: text / flush / move / tool / programEnd), `layout-xzc.js` (the polar transform,
unchanged code) and `converter.js` (options, header, end, clean-up). Done by a script that cut the old code line
by line with anchor checks — moved, not rewritten. Verified: npm test (golden 144/144), sweeps 0.0225 mm,
Chromium offline, release zip, and 13,671 old-vs-new comparisons (all golden programs + 1,500 random programs ×
9 option sets): 0 differences, identical errors. `index.html` loads the two new files.

**Next (needs Marios):** the selector "XZC / XZC + B" (a `layout-xzcb.js` next to `layout-xzc.js`), which CAM
gives the tool orientation; or first the Kiri:Moto `gcodeProc` proof.

---

## 2026-10-07 (late night, 3) — goal: converter merged into Kiri:Moto

**Marios said:** later the converter must be adapted to Kiri:Moto; if its author allows, merge them into a CAM
for polar (and multi-axis) machining where everything is computed inside the CAM, like a professional CAM:
choose the machine layout, set all parameters in the CAM, do all operations there.

**Claude's answer:** agreed, it is the right direction (already in `references/kirimoto.md` §6/§10). Kiri is public
and MIT (headers say "All Rights Reserved" → ask Stewart); merging into his main code needs his agreement, a
fork is legal but costly to maintain. Phases: gcodeProc proof → converter as a clean machine-layout library
(= step 2, serves both) → Kiri device option "machine layout" + export/preview/animation → tilt ops in Kiri
(needs tool orientation per point there; biggest part). Recommended to start step 2 now; asked for go-ahead.

---

## 2026-10-07 (late night, 2) — tilt direction confirmed: like Bird's printer → B

**Marios said:** "it will rotate the way Bird's 3D printer rotates, something like that." → radial plane, **B**
(DECISIONS.md). Proposed next steps and asked for go-ahead + which CAM will provide tool orientations.

---

## 2026-10-07 (late night) — Marios's answers on the tilt axis

**Marios said:** (1) the tilt must **change while cutting** (simultaneous), not fixed 0/90 positions;
(2) on tool lengths in a settings list + cancelling G43: "I don't know which is more correct — what do you
believe?"; (3) "the router will turn *kata ton axona X*, i.e. while it does face machining, when asked to tilt,
to make **propellers** and difficult spots".

**Open — must be clarified before any code:** "kata ton axona X" is ambiguous: *about* X (tool leans sideways,
tangential = **A**) or *along/toward* X (tool leans toward/away from the centre, radial plane = **B**, as in
Bird's printer and as assumed so far). It matters: B reaches the periphery (B 90 points at the chuck axis) and
keeps the pole logic; A leans into the gaps between propeller blades but leaves an unreachable disk of radius
L·|sin a| around the centre and cannot point radially at the periphery (except at X = 0). Asked him to describe
which way the tool tip moves. Also open: which CAM will produce simultaneous tool orientations (Fusion
multi-axis may need a paid extension — not verified).

**Claude's recommendation given:** the converter must know each tool's length when tilting (trivkins `G43` adds
it to Z only); best source = LinuxCNC's own `tool.tbl` (same numbers the machine uses) + one measured pivot
length; `G43` then not used in tilted output. Not implemented — waiting for his OK.

---

## 2026-10-07 (night) — tilt axis: letter B, research, selector design proposed

**Asked:** the 4th axis is not ready (router fixed for now) → no `.ini`/`.hal` changes, converter only; make sure
which letter LinuxCNC needs (A or B); a selector "XZC or XZC + A/B" must go in; search the web, GitHub and
LinuxCNC for such layouts.

**Done:** LinuxCNC source/docs (master `46a388f`) and web searched; notes in `references/tilt-axis-research.md`.
Result: **B** (A about X, B about Y, C about Z — LinuxCNC docs, ISO 841; LinuxCNC's own tilting-head kins and
industry B-axis mill-turns use B). With trivkins the letter has no geometry (A would run too); direction must be
an invert option + test cut. Big consequence: at B = 90 `G43` adds tool length to the wrong axis → the converter
needs per-tool lengths in the tilted layout. Face = polar interpolation (today); periphery = cylindrical
interpolation (G7.1 style): inputs either a mill 4th-axis XYZA program (Fusion rotary, Kiri lathe op) or an
unrolled 2-D program + radius. Forums of LinuxCNC/Autodesk are blocked in this sandbox (titles only).

**Not done — waiting for Marios** (proposal in the chat): first version indexed only (B fixed per section: 0 face,
90 periphery) or simultaneous; which periphery input first (XYZA program or unrolled 2-D); tool lengths from a
list in the settings + `G49` in periphery sections. No converter code written for the selector yet (rule 1).

---

## 2026-10-07 (evening) — converter 2.5.0, Bird repos in detail

**Asked:** (1) "it should behave like a Fusion 360 CAM for polar / multi-axis machines — a universal CAM for all
machine types"; (2) fix the remaining review findings, especially the cutter diameter not being read; (3) he will
often ask about Kiri:Moto; (4) he plans a 4th axis: the router, on X and Z, will **tilt about 90°** to machine
the periphery of the part, like Bird's printer — read `Core-R-Theta-4-Axis-Printer` and `S4_Slicer` in detail,
because the converter must support it with a **layout selector**; say if they must be downloaded.

**Done — converter 2.5.0** (all tests, sweeps 0.0225 mm, release zip, Chromium offline check):
- G93 floor 0.06 s → 0.6 ms: real feed now = CAM feed on short blocks (F1500: 844 → ~1443 measured).
  Golden 68 changed — only F of blocks at the old F1000 floor (script-checked line by line).
- Kiri:Moto tool list `; tool#=N flute=D … unit=` read (imperial → mm); single listed tool used without M6.
- Radial lines in 5 mm pieces (was ~1.4 mm). Golden 29 changed — fewer blocks, same rapids, same deviation.
- `G53 G0 X Y` park skipped like `G28` park; exponent numbers refused.
- three.js r134 in `lib/three/` (MIT, from the npm package — cdn.jsdelivr.net is blocked in this sandbox).

**Done — Bird repos:** cloned here (Marios does not need to download anything); firmware read completely, S4
notebook read completely. Notes rewritten: `references/bird-4axis.md` (pipeline, kinematics, what carries over to
milling and what not, consequences for his machine). Key points: same layout as his plan (B in the radial plane);
RRF 4-axis mode = offline transform + G93 like ours; S4's optimiser is for printing overhangs, not milling;
**adding the axis moves C to joint 3**; a mill 4th-axis program (Kiri's lathe op, Fusion rotary) maps directly
to "router at 90°".

**Waiting for Marios:** indexed or simultaneous tilt; axis letter, travel, motor/drive/reduction, homing, BOB
output, pivot-to-tip L per tool, pivot offset, router clearance at 90° (rule 4: not assumed).

---

## 2026-10-07 (later) — references folder, full Kiri:Moto CAM read

**Asked:** set up a place to remember other people's code (one notes file per project); check Kiri:Moto in
full, because Marios may one day offer the converter to its author so Kiri becomes a CAM for complex machines
"like mine XZC, XZCYA, ZCZA and the others" (his words; those layouts still need to be defined with him).
Next he will give another project's code to check and say what he wants done with it.

**Done:**
- `docs/handoff/references/` with an index (`README.md`, incl. how to add a project). Old
  `reference-kirimoto-bird-4axis.md` split into `references/kirimoto.md` and `references/bird-4axis.md`.
  CLAUDE.md rule 10 points to the index.
- Kiri:Moto `d138275` (4.7.0, no newer commit) re-read: the whole CAM output path (slice → prepare → export),
  the rotary ops, engine/CLI, export dialog, mods, docs. Notes in `references/kirimoto.md`.
- **Key finding:** Kiri already has a post-processor hook — device JSON `gcodeProc` names a page function that
  receives the whole G-code. Our converter can plug in **without changing Kiri** (UI export only, not the
  headless engine). Other findings: no G93 anywhere; CLI broken (30/59 files missing); a docs/code directive
  name mismatch; a dwell time-estimate bug; our converter does not read Kiri's `; tool#=` comments yet.
- Corrected two wrong points of the first notes (lerp points are not exported; AXISMAP exists).

**Not done / next:** proof of concept (self-hosted Kiri + `gcodeProc` + our converter) only with Marios's
go-ahead; reading Kiri's tool comments is a converter change (his OK first).

---

## 2026-10-07 — full code review, converter 2.4.1

**Asked:** read the whole repo, check the code, list the open items; then "fix what you believe is
wrong" and keep notes from now on.

**Checked:** `npm test` all green; `node tools/sweeps.js` worst G1 0.0225 mm (limit 0.026), 0 over.
Read every file in `src/`, `index.html`, profiles, README, CHANGELOG, `docs/handoff/machine-config/*`.
No open issues or PRs on GitHub. v2.4.0 is already on GitHub (PR #1 merged).

**Fixed (2.4.1), verified against the LinuxCNC 2.9 source (`interp_arc.cc`, `interp_internal.hh`):**
- R-format half circle with rounded end points became a straight line (10 mm off on R10) → half circle.
- I/J arc with slightly different end radius ended beside its end point → spiral to the exact end point.
- Arcs LinuxCNC refuses are refused with the line number (no I/J/R, R too small, R full circle, zero
  radius, end radius too far off). Before, some became straight lines.
- Missing F: was silently 500 mm/min → rejected with the line number (as LinuxCNC).
- `G4 P` >= 60 gets a warning comment (seconds vs milliseconds).
- Docs: README test table, cycles text, chuck-end note, `T_crot`; `index.html` SPDX header and old
  "C velocity limiting" text; `isNode ? factory() : factory()` in geometry/parser.
- Golden 144/144 unchanged. New checks in `tests/input.test.js` (49 checks).

**Not changed — waiting for Marios's decision:**
1. Feed floor: `MIN_TIME = 0.001 min` per G1 block (0.06 s) silently lowers the cutting feed on short
   blocks. Measured on a circle r20: F1000 → ~767, F1500 → ~844, F3000 → ~856 mm/min real. Options:
   lower the floor, or keep it and show a warning with the real feed. (Converter change → his choice.)
2. `G53 G0 X.. Y..` park is rejected while `G28 G91 X0 Y0` park is skipped. Skip it too?
3. Pure radial lines (C constant) are cut into many blocks without need. Optimisation, changes output.
4. Three.js is loaded from a CDN: the simulator does not open without internet. Ship a local copy
   (three.js is MIT)?
5. Exponent numbers (`F1e3`) are accepted by the parser and leave a stray `e3` line. No CAM writes them.

**Machine files — NOT edited** (the copies in `machine-config/` may differ from the real ones; fix on
the real files, rule 3):
- `.ini` header still says "CALIBRATION STILL TO DO: HOME_OFFSET = 135" — stale, it is -20 now.
- `.hal` Z comment says the switch is "coordinate 600" — with the new `.ini` it is 10.
- `axis_user.py` has no copyright/licence header.

**Safety items found (added to STATUS.md):** no hardware E-stop (only the gamepad Options button;
`estop-ext` reads the raw pin, not fail-safe); input P11 (`gpio.014`, Z zeroing sensor) not responding.
