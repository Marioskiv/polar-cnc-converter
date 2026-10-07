# Example: LinuxCNC simulation of an XZC lathe conversion (vismach)

> This folder is an **example for one machine** — the author's lathe conversion (see
> `profiles/example-marioskiv-holzmann-xzc.polar-profile.json`). The motion values in the `.ini` are
> that machine's. For your machine, copy the folder and change the `[AXIS_*]`/`[JOINT_*]` sections
> and the dimensions at the top of `polarlathe.py`.

The web simulator re-plays the converter's output. This folder goes one step further: it runs
**LinuxCNC itself** — its real interpreter and trajectory planner, with this machine's limits,
accelerations and homing — and shows a 3D model of the lathe whose chuck turns by C while the
router moves in X and Z. The tool path is drawn on the stock face and turns with it. No hardware
is needed.

| File | Purpose |
|---|---|
| `polarlathe-sim.ini` | The machine's real motion settings, with simulated joints instead of the Mesa card |
| `polarlathe.hal` | Feeds the joint positions to the model |
| `polarlathe.py` | The 3D model (dimensions at the top of the file) |
| `sim.tbl` | Tool table: T1 = 6 mm end mill |

## Run it

```bash
cp -r examples/linuxcnc-vismach-xzc-lathe ~/linuxcnc/configs/polarlathe-sim
cd ~/linuxcnc/configs/polarlathe-sim
chmod +x polarlathe.py
linuxcnc polarlathe-sim.ini
```

1. Machine on, **Home All**. Z goes to machine Z0 (park, tailstock end), X to 0 (chuck centre),
   C homes where it stands.
2. Once, in MDI, put work Z0 on the stock face of the model (`FACE_Z` in `polarlathe.py`):
   `G10 L2 P1 X0 Z-490 C0` — it is saved in `sim.var`.
3. In the converter, **Load profile** `profiles/example-marioskiv-holzmann-xzc.polar-profile.json`
   (X 0 / 113, one side; Safe retract Z 0). Convert, save, open the file in AXIS, run.

## What to look for

- The pattern drawn on the turning face is your CAM part — and **not mirrored**.
- Every retract moves the carriage **toward the tailstock**, never toward the chuck.
- Near the centre, the C axis motion stays smooth; AXIS reports no joint-limit or following
  errors.

## Limits of this simulation

The model's dimensions are approximate — edit the constants at the top of `polarlathe.py`.
It shows what LinuxCNC commands, not what the motors do: it cannot show lost steps, belt slip or
a chuck that turns the opposite way. The first real cut should still be in air, then an
asymmetric test piece.

Based on the structure of LinuxCNC's `configs/sim/axis/vismach/millturn` example. Works with the
HAL Python naming of LinuxCNC 2.9 (`HAL_FLOAT`) and newer (`HAL_REAL`).
