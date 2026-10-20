# Pending — open items and questions for Marios

Newest first. Move an item to `memory.md` (Decisions) when it is decided, delete it when it is done.

## Waiting for Marios
- **C wind-up in long Wrap programs** (found 2026-10-20). The 3-cutter relief test ends at C ≈ 167 000°
  (≈ 465 turns one way): roughing layers alternate direction, finishing helices all turn the same way.
  `polarlathe-sim.ini` has `[AXIS_C]`/`[JOINT_2]` `MIN_LIMIT = -99999`, `MAX_LIMIT = 99999`, so that program
  would stop on a C soft limit in the simulation (and on the real machine if it has the same limits).
  Options (he has not chosen):
  1. Finishing helices turn the other way on alternate passes/operations (no machine change, C stays small).
  2. The post writes C back to near 0 between operations with a short unwind move (no G92).
  3. Wider C limits in the .ini (e.g. ±9 999 999) — the chuck has no stop; only float precision limits it.
  4. G92 C0 / G92.4 reset between operations (as Kiri:Moto) — rejected in 2026-09 (offsets persist).
  Do nothing until he answers.
- Polar mode with FreeCAD's own operations: he has not yet cut a real part with 2.20/2.21.
- Polar Wrap with After operation and the tool report: not yet tried on his PC.

## Not covered by tests yet
- Wrap: grid point exactly on a mesh vertex/edge; a mesh with holes; feed between points when C turns fast near
  the axis.
- FreeCAD 26.3 has its own Rotary Surface (OpenCAMLib, A axis on a mill). Polar Wrap stays for the XZC lathe;
  noted only, nothing to do.
