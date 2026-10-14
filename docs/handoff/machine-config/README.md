# machine-config — last DELIVERED versions (2026-10-04; `.ini` C speed 2026-10-12)

These are the files Claude delivered to Marios. They are NOT necessarily what runs on the machine:
- **2026-10-14: Marios copied all of these files onto the machine** (C speed, mill-style Z, gamepad). Home All works,
  machine X/Z/C = 0 after Home, X and Z directions checked correct.
- **2026-10-14: C `STEP_SCALE` sign reversed to -91.733333** (G1 C90 turned the chuck counter-clockwise seen from
  the cutter). Marios edits the same line on the machine; re-test G1 C90 after it.
- 2026-10-12: C speed 360 deg/s, 720 deg/s^2, stepgen 450/900 (Marios: keep these as final); search "C SPEED".
  Marios takes the whole file from here. After installing: one G0 C3600 / G0 C0 mark check.

Always read the real files in `~/linuxcnc/configs/holzmann_cnc_mesa_7i92` first and compare. See ../STATUS.md.
Files: `holzmann_cnc_mesa_7i92.ini`, `holzmann_cnc_mesa_7i92.hal`, `gamepad.hal`, `axis_user.py`.
