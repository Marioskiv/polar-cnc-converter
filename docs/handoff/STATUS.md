# Status — updated 2026-10-07 (converter v2.5.0)

Session history: `LOG.md` (newest first).

The real machine is the source of truth. Where this file and the files on the LinuxCNC computer disagree,
trust the computer and tell Marios about the difference.

## !! Safe retract Z depends on which .ini is installed
- A mill-style Z numbering `.ini` was delivered 2026-10-04 but is **NOT installed yet** (Marios will install it later).
  With the currently installed `.ini`, machine Z0 is at the CHUCK end, so `G53 G0 Z0` would rapid toward the chuck.
  Until the new `.ini` is installed: converter **Safe retract Z = 590**, and do not load
  `profiles/example-marioskiv-holzmann-xzc` (it has 0).
- After installing it: Safe retract Z = 0, and touch off Z again (the G54 Z offset shifts by 590).

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
- Check C+ direction (else mirrored parts); `G0 C3600` then `G0 C0` must return exactly (else lower C speed to 105/90).
- C soft limits ±99,999° allow only ~277 chuck turns per program — raise them in `[AXIS_C]`/`[JOINT_2]`.
- Mount and wire the chuck encoder. Confirm the gamepad layout (if X drifts: read `input.0.abs-ry-position` at rest).
- Measure real vs predicted cycle time (LinuxCNC `tp.c` does not blend moves that involve a rotary axis).

## Open items — testing before a real part
- vismach simulation (`examples/linuxcnc-vismach-xzc-lathe`, synced to the new X layout and mill-style Z; sim only).
- Air cut; Home C before every program; X = 0 at the chuck centre; then the asymmetric "F" cut; then an aluminium part,
  measured and photographed (the first thing the Kiri:Moto author will ask for).
- Fusion post: LinuxCNC, compensation "in computer", expanded drilling cycles, no G18/G19 arcs, mm, clearance-height retracts.

## Open items — software
- v2.4.0 is on GitHub (PR #1 merged). v2.4.1 and v2.5.0 (all review findings fixed, incl. real feed on short
  blocks, Kiri tool list, offline three.js) are on branch `claude/youthful-goldberg-a6qv5t` — merge when
  Marios agrees.
- Future router tilt axis (rotates continuously during a program; Marios calls it A, conventional letter in the X-Z
  plane would be B). Plan, each step only with his go-ahead:
  1. Study Kiri:Moto's code — DONE (full CAM read 2026-10-07), see `references/kirimoto.md`; Bird: `references/bird-4axis.md`.
  2. Restructure the converter into input → machine layout → output with **zero output change** (golden 144/144).
  3. Add the tilt layout: per-point tool direction (from Kiri:Moto / 5-axis G-code), pivot-to-tip distance per tool,
     tilt smoothing, max tilt change per block, tip + orientation error checks, simulator with a tilted tool.
  Bird's printer and S4 slicer read in detail 2026-10-07: `references/bird-4axis.md` §5-6. **Before any work,
  Marios must answer:** indexed (0°/90° fixed per cut) or simultaneous tilt? axis letter, travel, motor/drive/
  reduction, homing, BOB output, pivot-to-tip L per tool and pivot offset, router clearance at 90°.
  Machine config first: adding the axis moves C from joint 2 to joint 3 (canonical order X Z B C).
  **2026-10-07 Marios: the axis is not built, the router stays fixed → NO `.ini`/`.hal` changes now; only a
  converter layout selector "XZC / XZC + tilt (B, A as rename)".** Letter researched: **B**
  (`references/tilt-axis-research.md`). Selector design proposed, waiting for his answers (see LOG.md).
- Marios's goal (2026-10-07): "behave like Fusion 360 CAM for polar / multi-axis machines — a universal CAM for
  all machine types". Agreed direction proposed: the CAM (Fusion, Kiri:Moto, …) makes the toolpaths, the
  converter is the universal **machine-layout** stage (like Fusion's machine definition + post).
- Ideas not built: overcut difference map, polar-native operations (spiral facing, bolt circles, radial and concentric
  grooves), a "pole governor" warning (feed near the centre is limited by C speed: v = ω·d), acceleration in simulator timing.
- Collaboration with the Kiri:Moto author (Stewart Allen) only AFTER the real tests and photos exist.
