# First cuts on a real machine (2026-10-14)

The first programs run on the author's machine: a Holzmann lathe converted to a CNC face mill (LinuxCNC 2.9.10,
trivkins `XZC`, Mesa 7i92, steppers; chuck = C, router on the X cross-slide). The machine configuration is in
[`docs/handoff/machine-config/`](../../docs/handoff/machine-config/).

| File | What it is |
|---|---|
| `polar_xzc_output_F_test.ngc` | **The "F" test.** A FreeCAD pocket job (an "F", a hexagon, a rectangle) converted with version 2.13.0. Cut in plastic: **correct** (the F reads normally, not mirrored). |
| `fierst_test_polar_xzc_output.ngc` | The first program (MillFacing spiral + the same pockets). Run in the air only. |

Both files are the converter's **output**, ready for LinuxCNC. Before they were added, the LinuxCNC 2.9.10 interpreter was run on each of them with the machine's `.ini`. It accepted both, with the feeds as programmed (cut 900 mm/min, plunge 300 mm/min).

## Settings used
- FreeCAD CAM, post `linuxcnc_legacy`. Z0 at the top of the stock. 5 mm 2-flute end mill (T2), 10,000 rpm.
- Feeds for plastic: H 900, V 300 mm/min.
- Converter: one side of the centre (X Min 0), X Axis Max 113, chord tolerance 0.025 mm.

## What the first cut showed
- **Correct:** the direction of the rotary axis, the X sign, the shapes, and clean edges in plastic.
- **To do:** centre the cutter on the chuck axis. The first cut was made before this, so straight lines bowed
  slightly toward the centre: an X0 offset moves every point the same distance toward the centre. A setup step, not
  the converter. After that, the dimensions get measured, and then comes an aluminium part.
- **Facing:** with a 25 % step-over and a low feed, the facing spiral took 16 minutes, and the axes pulsed at very
  low chuck speed. For the next run: step-over 60-70 %, its own tool controller with a higher feed, final depth
  −0.3 mm.
