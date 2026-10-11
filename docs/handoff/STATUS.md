# Status — updated 2026-10-11 (converter v2.11.1)

Session history: `LOG.md` (newest first).

The real machine is the source of truth. Where this file and the files on the LinuxCNC computer disagree,
trust the computer and tell Marios about the difference.

## !! Machine Z0 is at the CHUCK end until the mill-style .ini is installed
- A mill-style Z numbering `.ini` was delivered 2026-10-04 but is **NOT installed yet** (Marios will install it later).
  With the currently installed `.ini`, machine Z0 is at the CHUCK end, so `G53 G0 Z0` typed in MDI would rapid toward
  the chuck. **The converter no longer needs this (2.11.0):** it never outputs G53; CAM retracts become
  `G0 Z<program's highest Z>`. (2.10.0 and older: Safe retract Z had to be 590.)
- After installing it: touch off Z again (the G54 Z offset shifts by 590).

## Machine
- Holzmann lathe converted to a CNC face-milling machine. Chuck = C (rotary), router on the X cross-slide, Z axial.
  LinuxCNC 2.9.10, trivkins `COORDINATES=XZC`, Mesa 7i92 + 5-axis BOB, steppers, one 48 V supply.
- Config dir on the LinuxCNC computer: `~/linuxcnc/configs/holzmann_cnc_mesa_7i92` (do not run PNCconf).
- X: 135 mm travel, NEMA17 0.8 N·m, 2 mm screw, 400 steps/mm, 18 mm/s. Z: 600 mm, NEMA23, 25 mm/s, BACKLASH 0.3.
  C: NEMA23 57-112 (~3 N·m), belts 20→48→20→86 = 10.32:1. X and Z are near their practical speed limit.
- C driver runs at 3200 steps/rev (a DIP switch is broken, cannot set 1600) → `STEP_SCALE = 91.733333`.
  `G0 C360` measured = exactly one turn. Max pulse rate of the driver is unverified (model unknown).
- Chuck encoder (600 PPR NPN, 1:1, scale 6.666667) is NOT mounted yet; needs its own 9–12 V supply, A/B to P1.

## INSTALLED and confirmed on the real machine
- `[DISPLAY] LATHE = 1`, `CYCLE_TIME = 0.100`, `OPEN_FILE = ""`, `USER_COMMAND_FILE = axis_user.py`,
  `G8` in the startup code, `gamepad.hal` as the last HALFILE (jogging works, needs Home All first).
- X layout (2026-10-04): router in the former tool-post position, cutter on the chuck centre **20 mm from the X switch**.
  X = −20 at the switch, 0 at the centre, soft limits −18 … +113, `STEP_SCALE = -400`, homing toward the switch
  (`HOME_SEARCH_VEL -3`, `HOME_LATCH_VEL 0.5`), `HOME 0`, `HOME_OFFSET -20`. HAL: switch = home + `neg-lim-sw-in`.
  Home works; "+" and the down-arrow move X away from the switch. One side of the centre only; parts up to ~220 mm.
- C `STEP_SCALE = 91.733333` (see above).

## DELIVERED but NOT installed yet (files in `docs/handoff/machine-config/`)
- C speed: `MAX_VELOCITY 120`, `MAX_ACCELERATION 360`, `STEPGEN_MAXVEL 150`, `STEPGEN_MAXACCEL 450`,
  `MAX_ANGULAR_VELOCITY 120` in `[DISPLAY]` and `[TRAJ]`, `DEFAULT_ANGULAR_VELOCITY 60`.
- Mill-style Z (all old values minus 590): `HOME_OFFSET 10`, `HOME 0`, `MAX_LIMIT 7`, `MIN_LIMIT -590`.
- `gamepad.hal`: X dead zone ±0.45, Z ±0.35, C trigger gain ×6, right stick DOWN = +X. Not yet confirmed by Marios.

## Open items — machine
- **SAFETY: no hardware E-stop.** `estop-ext` reads the raw input `gpio.013.in` (TEMPORARY, not
  fail-safe: a broken wire looks like "all clear"). The only E-stop is the gamepad Options button.
  Wire an NC E-stop button and switch the `.hal` to `gpio.013.in_not` (the line is already there).
- Input P11 (`gpio.014`, Z zeroing / probe sensor) does not respond. Replace the ribbon cable; if dead,
  move the wire to P13 and use `gpio.016` (see the `.hal`).
- Stale comments to correct on the REAL files (not urgent): `.ini` header "HOME_OFFSET is set to 135"
  (it is -20); `.hal` Z comment "coordinate 600" (10 with the mill-style `.ini`).
- Align the router on the chuck centre at X0 after Home, in X AND height (dial indicator, or V-bit on a centre dot).
- Check C+ direction with the page's Direction check: `G0 C90` → chuck clockwise seen from the cutter (else mirrored
  parts; fix the C `STEP_SCALE` sign); `G0 C3600` then `G0 C0` must return exactly (else lower C speed to 105/90).
- C soft limits ±99,999° allow only ~277 chuck turns per program — raise them in `[AXIS_C]`/`[JOINT_2]`.
- Mount and wire the chuck encoder. Confirm the gamepad layout (if X drifts: read `input.0.abs-ry-position` at rest).
- Measure real vs predicted cycle time (LinuxCNC `tp.c` gives moves with a rotary axis no blend arc / tangent merge;
  plain G64 blending may still apply). Verify whether `[TRAJ] MAX_ANGULAR_VELOCITY` is used (documented only in `[DISPLAY]`).

## Open items — testing before a real part
- vismach simulation (`examples/linuxcnc-vismach-xzc-lathe`, synced to the new X layout and mill-style Z; sim only).
- Air cut; Home C before every program; X = 0 at the chuck centre; then the asymmetric "F" cut; then an aluminium part,
  measured and photographed (the first thing the Kiri:Moto author will ask for).
- Fusion post: LinuxCNC, compensation "in computer", expanded drilling cycles, no G18/G19 arcs, mm, clearance-height retracts.

## Open items — software
- **v2.9.0 is on `main`** (PR #3 merged by Marios 2026-10-11, CI green): 2.8.0 tool diameter from any CAM,
  2.9.0 Tool Diameter setting removed. (PR #2 = 2.4.1 – 2.7.0, merged 2026-10-07.)
- **v2.11.1 is on `main`** and on GitHub Pages (PRs #4, #5 merged by Marios 2026-10-11): Cutting side / X Axis Max
  required, no Safe retract Z, direction check, version in the header. Marios uses
  https://marioskiv.github.io/polar-cnc-converter/ (Pages deploys from `main`; Ctrl+F5 after an update).
- **BUGS FOUND 2026-10-11 (fix prepared, waiting for Marios's yes):** merge of moves < 0.15 mm turns a small Z step into
  a ramp (0.1 mm gouge) and uses the next line's feed; both-sides Signed-X short move 0.12 mm off. See research file part 2.
- **Research 2026-10-11** (`references/research-2026-10-11.md`) — proposals waiting for Marios's yes:
  (1) arcs centred on the chuck axis as exact X-constant blocks (now polygons, 127 blocks for R10);
  (2) guard against output lines ≥ 255 chars (LinuxCNC refuses them; long CAM comments pass through today);
  (3) dropped — router base will be milled on the machine (DECISIONS);
  (4) simulator: deviation colouring, axis-speed colouring, finer height map, line link, report export;
  (5) long term: FreeCAD addon "Polar XZC" (machine `.fcm` + Python port of the core), after real test cuts.
- LinuxCNC on trixie: stay on 2.9.x (≥ 2.9.9 on 6.12 kernels), `linux-image-rt-amd64`, `linuxcnc-uspace`, install
  `iptables` for hm2_eth, NIC static + RX coalescing 0, run latency-histogram (see the research file §3).
- Direction check written on the page (2026-10-11). For Marios: X settled 2026-10-04; **C still to be checked** with
  it (chuck must turn clockwise seen from the cutter on `G0 C90`), then the F cut.
- FreeCAD programs: the Tool Controller feeds must be set (default 0 → no F → refused). FreeCAD Z0 = stock bottom.
- Future router tilt axis (rotates continuously during a program; Marios calls it A, conventional letter in the X-Z
  plane would be B). Plan, each step only with his go-ahead:
  1. Study Kiri:Moto's code — DONE (full CAM read 2026-10-07), see `references/kirimoto.md`; Bird: `references/bird-4axis.md`.
  2. Restructure the converter into input → machine layout → output with **zero output change** (golden 144/144).
     **DONE 2.6.0** (`gcode-input.js` → `layout-xzc.js` → `converter.js`; 13,671 old-vs-new comparisons, 0 differences).
     Step 3 first part **DONE 2.7.0**: layout `xzcb` — ball-end lean while cutting, auto-limited by X/B travel
     (`layout-xzcb.js`, `tests/tilt.test.js`). Still open: tilt following the part's shape (needs CAM orientation →
     Kiri), fixed B per program for non-ball tools, periphery from 4th-axis programs.
  3. Add the tilt layout: per-point tool direction (from Kiri:Moto / 5-axis G-code), pivot-to-tip distance per tool,
     tilt smoothing, max tilt change per block, tip + orientation error checks, simulator with a tilted tool.
  Bird's printer and S4 slicer read in detail 2026-10-07: `references/bird-4axis.md` §5-6. **Before any work,
  Marios must answer:** indexed (0°/90° fixed per cut) or simultaneous tilt? axis letter, travel, motor/drive/
  reduction, homing, BOB output, pivot-to-tip L per tool and pivot offset, router clearance at 90°.
  Machine config first: adding the axis moves C from joint 2 to joint 3 (canonical order X Z B C).
  **2026-10-07 Marios: the axis is not built, the router stays fixed → NO `.ini`/`.hal` changes now; only a
  converter layout selector "XZC / XZC + tilt (B, A as rename)".** Letter researched: **B**
  (`references/tilt-axis-research.md`). Marios: tilt must change **while cutting** (simultaneous), for propellers
  and hard-to-reach spots. **Confirmed 2026-10-07: it tilts "like Bird's printer" → radial plane → B.**
  Tool length: proposed reading LinuxCNC `tool.tbl`. CAM for tilt (Marios, 2026-10-07): **not Fusion** (no
  subscription; Fusion maybe for plain XYZ) → Kiri:Moto or FreeCAD. Verified: neither gives simultaneous tilt
  (`references/freecad-cam.md`); FreeCAD RotarySurface / Kiri lathe give periphery (B 90) programs.
- Marios's goal (2026-10-07): "behave like Fusion 360 CAM for polar / multi-axis machines — a universal CAM for
  all machine types". Clarified later the same night: **the converter is to be merged into Kiri:Moto** (if its
  author agrees) → a professional-style CAM where one chooses the machine layout and all parameters, all
  operations inside the CAM, no post-editing. He wants the **user experience of a professional program**. Consequence: step 2 (restructure) must make the converter a clean
  machine-layout **library** usable both by our page and inside Kiri (see `references/kirimoto.md` §6, §10). Agreed direction proposed: the CAM (Fusion, Kiri:Moto, …) makes the toolpaths, the
  converter is the universal **machine-layout** stage (like Fusion's machine definition + post).
- Ideas not built: overcut difference map, polar-native operations (spiral facing, bolt circles, radial and concentric
  grooves), a "pole governor" warning (feed near the centre is limited by C speed: v = ω·d), acceleration in simulator timing.
- Collaboration with the Kiri:Moto author (Stewart Allen) only AFTER the real tests and photos exist.
