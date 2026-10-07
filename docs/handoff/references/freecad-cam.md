# Reference — FreeCAD CAM workbench (4th axis / tilt capabilities)

*Read 2026-10-07 from the source: `github.com/FreeCAD/FreeCAD`, commit `e326ee2` (2026-10-07, development
version), sparse checkout of `src/Mod/CAM/Path/{Op,Base,Post,Dressup}`. Why: Marios has no Fusion subscription;
the CAM for tilted (XZC + B) work will be FreeCAD or Kiri:Moto. **Licence LGPL-2.1-or-later → method only, no
code in our MIT repo.***

## What it can do (verified in the code)
- **Indexed tilt per operation (3+1 / 3+2):** every operation has a tool axis ("Workplane");
  `Path/Base/Util.py` `toolAxisForOp()`: the tool axis is *"constant for the whole operation, which is true for
  indexed machining and is the assumption that simultaneous motion removes"* — i.e. **no simultaneous tilt**.
- A **machine model with rotary axes** and a kinematic chain (`Path/Base/Generator/rotation.py`:
  `build_kinematic_chain`, `compute_rotation_matrix` = R_tilt · R_azimuth) that solves the axis angles for a
  wanted tool direction — used for the indexed operations and in `Post/Processor.py`.
- **Continuous 4th-axis surfacing** (tool radial, part rotating): `Op/RotarySurface.py` (new, 2026, sliptonic)
  with generators `rotary_dropcutter`, `rotary_parallel`, `rotary_rings`, `rotary_spiral`, `rotary_wrap`; also
  `Op/Surface.py` `ScanType = Rotational` (around X or Y). Output: mill 4th-axis program (A about X, or B about Y).
  `rotary_wrap.py` handles UNWOUND / MODULO / REZERO for the rotary values (same vocabulary as our converter).
- Requires OpenCamLib (`ocl`) for the surface operations.

## What it means for us
- **Periphery (router at B = 90):** FreeCAD's RotarySurface output (tool radial, A about X) maps directly to the
  XZC + B layout at B = 90 — same as Kiri's lathe op (`kirimoto.md` §5). Usable today.
- **Fixed tilt per operation:** possible in FreeCAD, but its posts write angles for *its* machine model; reading
  them needs a defined input form (to be decided).
- **Simultaneous tilt (changing while cutting): no free CAM provides it** (FreeCAD: no; Kiri: no). It has to be
  built — by the converter for special cases (ball-end lean keeping the ball centre on the CAM path), and in the
  long run inside Kiri:Moto as tilt operations.
