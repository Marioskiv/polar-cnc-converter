# machine-config — last DELIVERED versions (2026-10-04; `.ini` C speed TEST values 2026-10-12)

These are the files Claude delivered to Marios. They are NOT necessarily what runs on the machine:
- already installed: the X layout and the C `STEP_SCALE`;
- not installed yet: C speeds, mill-style Z numbering, the latest gamepad revision.
- 2026-10-12: the `.ini` carries C speed **TEST** values (360 deg/s, 720 deg/s^2, stepgen 450/900); search
  "C SPEED TEST". Marios takes the whole file from here; after his test the final values replace them.

Always read the real files in `~/linuxcnc/configs/holzmann_cnc_mesa_7i92` first and compare. See ../STATUS.md.
Files: `holzmann_cnc_mesa_7i92.ini`, `holzmann_cnc_mesa_7i92.hal`, `gamepad.hal`, `axis_user.py`.
