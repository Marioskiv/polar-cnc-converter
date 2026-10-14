# Work log — newest first

One entry per working session: what was asked, what was done, what is left, what Marios decided.
Short and factual. Current state lives in `STATUS.md`, permanent decisions in `DECISIONS.md`.

---

## 2026-10-14 (19) — first programs on the machine; the F test is CORRECT

**Marios:** sent FreeCAD programs (MillFacing + Pocket, plastic). Checked each converted file with rs274 + the
machine `.ini` (0.022 mm, feeds as CAM). Advice taken: H900 V300 (was H200 V400, plunge faster than cut). Air run:
facing slow (25 % stepover, 14 m) and pulsing at low C speed; pocket smooth. "joint 0 following error" at a pocket
rapid → X `STEPGEN_MAXACCEL` 125 → 200 (PR #13; the Ethernet link drop in dmesg was 3.5 h earlier). **The F test
(pocket only) cut correctly.** The Claude app keeps showing PR #11 for this chat (app display, not GitHub).
**Pending (Marios):** facing joint-space arcs (STATUS). **Open:** photo, C3600 mark check, pulsing test, E-stop.

---

## 2026-10-14 (18) — delivered machine files installed; C direction wrong → STEP_SCALE sign

**Marios:** merged PR #11; copied the delivered `.ini`/`.hal`/gamepad files from GitHub onto the machine. **Done
together (screenshots):** Home All OK (machine 0/0/0); G54 X had 71.585 → `G10 L2 P1 X0 C0` (first try typed the
letter O instead of zero); new direction tests: X ✔, Z ✔, **C wrong** (counter-clockwise) → `[JOINT_2] STEP_SCALE`
−91.733333 given and put in the repo copy (Marios: "yes, also on GitHub"). Marios does not want per-job thickness
arithmetic → solution 1: FreeCAD Z0 at the stock top, touch off with 0 (probe button later, needs P11).
**Open:** re-test C after the change, `G0 C3600/C0` mark check, measure 20 mm on X and Z, Z touch-off, then air cut + "F".

---

## 2026-10-13 (17) — study of professional polar controls / CAM posts; 2.13.0 C report

**Marios:** use as many features of existing polar machines as possible ("find how they handle it and write the code").
**Done:** three web studies (Siemens/Heidenhain, lathe controls Fanuc/Haas/Mitsubishi/Mazak/Okuma, CAM posts
Fusion/Mastercam/NX) → `references/polar-controls-2026-10-13.md`. Result: the converter already matched them; gaps
offered: (1) pole speed report, (2) C turns/limit check, (3) one-direction C for holes. Marios: 1 and 2 yes, 3 not
needed (no backlash). 2.13.0: report at the top (C range, ±99,999° warning, C speed bands + fastest block with source
line). Golden 144/144 changed only by those comment lines (checked per output), input 159, tilt/A rename OK.
**Limits:** vendor PDFs unreachable from here (excerpts only). **Not done:** item 3.

---

## 2026-10-13 (16) — exhaustive audit with LinuxCNC's own interpreter; 2.12.3

**Marios:** "many changes, I don't like that — do an exhaustive check of the project" (no file changes, report first),
then "do them" (Claude's proposal: 1, 3, 6, 7 + the tool, README notes for 2 and 4). **Done:** built LinuxCNC 2.9.10
`rs274` from source; compared input vs output on golden, his 3 FreeCAD programs, ~60 edge cases, options, 2000 random
programs. One-side cutting clean (his programs <= 0.022 mm, time equal). 2.12.3: (1) Signed-X ramp retrace at the
line's own Z (both sides only); (3) cycle initial level kept without G80 (as LinuxCNC `cycle_il`); (6) rapid into
the centre one block; (7) STATUS, profile text, vismach C 360/720; `tools/linuxcnc-compare.js`; README notes on the
G98 default and G85/G89. New tests fail on the old code (input 30; geometry ramp case 0.333 mm). Golden 144/144,
sweeps 0.0225, FreeCAD identical. **Not done:** L repeat (5); unwind time in both-sides mode (needs lookahead).

---

## 2026-10-12 (15) — whole Fanuc 16i/18i-MB manual read; 2.12.2 (whitelist of G codes, E)

**Marios:** uploaded the full Fanuc manual (B-63534EN/02, 1257 pages) to a new PRIVATE repo `Marioskiv/cnc-manuals`
(Claude could not create it: the GitHub integration may not create repos); asked to read it all; then "if they
matter, do them". **Done:** text extracted and read in full (8 parallel readers + the key chapters by Claude);
notes in `references/fanuc-b63534en.md`. Tested the manual's codes on the converter → real bugs (unknown codes
passed, some X/Y as moves; G91 on a cycle line; `/`; `,R`). 2.12.2: whitelist of G codes, those fixes, E for G16.
Golden 144/144 identical, input 152, sweeps worst 0.0225, FreeCAD programs identical. **Not done:** G12.1 import,
dwell/integer warnings (ideas in STATUS). Note: the org's monthly spend limit was hit by one reader near the end.

---

## 2026-10-12 (14) — F done; first primary Fanuc source (B-63524EN §4.6)

**Marios:** "do F, both parts" + a Fanuc manual excerpt on G12.1. **Done:** header G8/G7 (rotary C only), input G7
refused, G8 removed; golden 144/144 changed by exactly one inserted `G8` line (verified per output); input 116.
Also refused G12.2/G13.2, G7.1, G107 (passed through). Manual notes in references §9: F is tangential feed (= our
G93 approach), Fanuc does not solve the pole (alarm / F < L·R·π/180) — basis for the pole-governor idea.
E still waits for the G16 section of a Fanuc manual.

---

## 2026-10-12 (13) — D done; more G16/G12.1 sources

**Marios:** sent Machining Doctor (G16), a Fanuc G12.1 turn-mill document and a vendor G12.1 article; "do D".
**Done:** 2.12.1 also refuses X/Y on the G16 line (pole vs first point differs between sources), subprograms,
o-word flow and `#`/`[ ]` (all were passed through). Input tests 107, golden 144/144. Sources compared in
`references/polar-papers-2026-10-12.md` §5–7. **Waiting:** E (modal radius/angle in G16) — needs the Fanuc manual.

---

## 2026-10-12 (12) — 2.12.1: A, B, C (Marios: "ok kane to A kai to G kai B")

**Done:** radial rapids in one block; G16 converted in its certain form (G17 + G90, both words per line, pole =
work origin), everything else in G16 refused with the line; arcs with R and I/J refused like LinuxCNC. Verified:
G16 bolt circle = Cartesian version (identical motion), golden 144/144, sweeps/pole stress unchanged, FreeCAD
programs same G1 output, zip tested. **Note:** the G16 rules come from the sources read + general Fanuc knowledge,
not from a Fanuc manual (not available here); uncertain forms are refused rather than guessed.

---

## 2026-10-12 (11) — 2.12.0 exact arcs about the axis; Marios on 2.11.4; ENCY text

**Marios:** (a) he did not ask to remove/refuse G16, G12.1, G15 … — "only if they ever cause a problem; if there
is no problem, do not remove them"; (b) yes to exact arcs about the chuck axis; (c) pasted the ENCY polar page.
**Done:** 2.12.0 exact arcs (see STATUS/CHANGELOG), ENCY notes in `references/polar-papers-2026-10-12.md`.
Found but NOT fixed: none new — the 3 sweep cases over 0.026 are sub-zone helices (replay artefact, also on main).
**Then Marios chose "keep 2.11.4"** (explained: the codes did cause problems). 2.12.0 pushed into PR #10.

---

## 2026-10-12 (10) — 2.11.4: polar input refused; Zhang/Chen/Du paper read

**Marios:** "not sure it is right, ok do it" (proposal A) + a paper (polar interpolation module, 2013) + ENCY CAM link.
**Done:** 2.11.4 — `G16`, `G12.1/G13.1`, `G112/G113`, `@ ^` refused with the line; `G15` removed (LinuxCNC 2.9 does not
know it, verified in `interp_array.cc`). 6 new input tests (fail on 2.11.3), golden identical, sweeps unchanged, zip
tested. Paper notes in `references/polar-papers-2026-10-12.md` (confirms our spiral-error method and the exact
X-constant arc idea; no pole handling). ENCY page blocked by the network policy (not read).

---

## 2026-10-12 (9) — Fanuc G15/G16 examples (helmancnc.com) → polar input not handled

**Marios:** read the helmancnc G15/G16 bolt-circle page for ideas. **Could not:** host blocked by the session network
policy (mirrors too). **Checked the converter instead:** G16 input silently mis-converted, `@ ^`, G112 passed through
→ proposal A (refuse) / B (support G16) in STATUS. Idea confirmed: bolt circles are native on XZC (X fixed, only C).

---

## 2026-10-12 (8) — variable-speed router: saved as a later item

**Marios:** can CAM / converter control a variable-speed router? → yes for per-tool/per-operation `S` (already passes
through); hardware + HAL/INI needed (VFD, BOB 0-10 V unknown). Idea: spindle speed following real feed near the
centre (HAL). **Saved as a later item in STATUS** at his request; nothing changed.

---

## 2026-10-12 (7) — Enéias Eringer (LinuxCNC users group): what he does, and our answer

**Marios:** showed Enéias Eringer (Brazil, "Eringer Retrofit CNC", LinuxCNC retrofits) — FreeCAD 1.1.1 video with
operations "Surface5Axis…" and a tilted-tool simulator; asked if his work is on GitHub; then their Facebook thread
(15 weeks old).
**Found:** no public GitHub work of his ("eringer" on GitHub is someone else). "Surface5Axis" is not in official
FreeCAD (1.1 or 26.3; only a multi-axis discussion, FreeCAD #23042) → his own modification. In the thread he says:
his G-code came from hyperMILL for a normal 5-axis Fanuc machine, **LinuxCNC does TCP**, it is not an XYZ→XCZ
converter; he suggested modifying LinuxCNC's code with AI and adding a remapped G12.1. **Our position unchanged**
(DECISIONS: no real-time kinematics): G12.1/polarkins in real time cannot look ahead, so the pole (C up to 180° at
r≈0) gives following errors or silent stalls; patched LinuxCNC C code must be re-patched on every update and a bug
moves the machine. TCP is fine for a 5-axis table/head mill, not for this polar machine. Possible contact later (tilt
axis B, oriented toolpaths), after the real test cuts.

---

## 2026-10-12 (6) — 2.11.3: the 0.0268 mm near-pole fix (Marios: yes)

**Marios:** C speed values fine → PR #7 merged by him. Then "yes, do the 2.11.3 fix".
**Done:** branch restarted from `main`; `SIGNED_EXACT_R = CHORD_TOL * 0.25`; input test for the 0.0268 case (fails on
2.11.2, passes now) and the "no fill" message test moved to a line that still takes that path; version 2.11.3
(package, lock, page, `?v=`), CHANGELOG. `npm test` all pass, golden 144/144 identical, sweeps worst 0.0225,
near-pole stress 0/3000 both sides, extracted zip tested. PR to `main` waiting for his merge.

---

## 2026-10-12 (5) — C axis speed: motor datasheet received

**Marios:** wants to set the C speed properly (chuck rpm low because of the 10.32:1 belts); sent the 57-112 page.
**Found:** integrated driver, SW1 = direction, ALM alarm output, generic speed curve (open loop to ~800 motor rpm).
Today 120 deg/s (delivered) = 206 motor rpm. Plan: step test 120 → 180 → 240 → 300 → 360 deg/s with `G0 C3600` /
`G0 C0` and a mark; keep ~70 % of the highest that returns exactly. **Waiting for:** the real `[AXIS_C]`/`[JOINT_2]`
from the machine, closed loop or not, max pulse frequency. Proposed: wire ALM to a LinuxCNC fault input (pin to be
chosen with him; nothing assumed).
**Then:** Marios: the delivered files are what he will install, update them (he replaces the whole `.ini`).
Done: C speed TEST values written into `machine-config/holzmann_cnc_mesa_7i92.ini` (header warning, a comment on
every change, no inline comments, HAL unchanged). **Then Marios: the values are fine, make them final and put it on
`main`** → comments relabelled (values unchanged), PR to `main`. Advised: one G0 C3600 / G0 C0 mark check after install.

---

## 2026-10-12 (4) — C direction: the standard; F test saved as Marios's checklist

**Marios:** is there a rule for the C direction, so the machine is set by the rule? Save the F test as a pending item.
**Answered:** yes — ISO 841 right-hand rule (tool motion on the part); the converter already follows it; with the
chuck turning the part, `G0 C90` must turn the chuck clockwise seen from the cutter; a wrong direction is fixed by the
sign of the C `STEP_SCALE`, then proven by the "F" cut. Procedure written in STATUS (testing before a real part).
Still waiting for his yes on the one-line `SIGNED_EXACT_R` fix (2.11.3).

---

## 2026-10-12 (3) — full check of the converter (no code changed); FreeCAD addon postponed

**Marios:** not the addon yet — keep it as a future item; first he wants to know the converter works flawlessly.
**Done (all on v2.11.2, repo code unchanged):** `npm test` all pass (golden 144/144); `tools/sweeps.js` 0 over 0.026
(worst 0.0225); about 75 tricky cases, both cutting sides: all pass, the 8 expected refusals refuse; G93 time = length/feed
checked by hand on the 5 cases the old checker flagged (checker artifacts: G91, other feeds); his 3 FreeCAD programs:
worst 0.0222 / 0.0151 / 0.0151 mm, no missing F, no nested comments, no line > 251. Near-pole stress 3000 polylines:
3 (one side) / 9 (both) at 0.0268 mm. **Cause found** (`SIGNED_EXACT_R = CHORD_TOL`), fix tried in a scratch copy:
`CHORD_TOL * 0.25` → 0/3000, all tests and sweeps pass, golden unchanged, his programs identical. Waiting for his yes.
**Not proven by software:** C direction and X sign (only the asymmetric "F" cut), real machine dynamics.

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
