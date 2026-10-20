# Pending — open items and questions for Marios

Newest first. Move an item to `memory.md` (Decisions) when it is decided, delete it when it is done.

## Waiting for Marios
- **His answers 2026-10-20:** changes cutters by hand; all tool lengths are in the LinuxCNC tool table; no
  tool setter mentioned; unsure whether to clamp each cutter at the same height or push it to the collet stop.
  Wants Wrap to go to a safe X AND a safe Z before every tool change. Proposed (waiting for his yes and the Z
  value): before each M6 in a Wrap program `G0 X<Wrap X max>` then `G0 Z<tool-change Z>`.
- **Tool change position (found 2026-10-20).** Wrap: before M6 the router is only 5 mm above the bar (no
  retract to X max). Face: at the CAM's clearance height. LinuxCNC moves nothing on M6 unless his .ini says so.
  Options to put to him: retract to X max (Wrap) / a safe Z (Face) before every M6 in the post; or
  `TOOL_CHANGE_QUILL_UP = 1` in his .ini (Face: Z to machine 0; Wrap: moves along the bar, X stays). Ask
  whether he has a tool setter and whether tool lengths are in his tool table. Do nothing until he answers.
- **Spindle after a tool change:** FreeCAD writes `M3 S` only if the Tool Controller has a spindle speed; the
  relief test has none, so its program has no M3 at all. Proposal (ask): Post Process warns/refuses a cut
  with no spindle start.
- **Header text:** the converter always writes "C goes past 99999 deg" (fixed number) even when his .ini limit
  is larger. Cosmetic; ask before touching the converter.
- **C soft limit:** decided 2026-10-20 (see memory.md). Marios raises the limit in his real .ini himself.
  Not confirmed yet that he has done it.
- Polar mode with FreeCAD's own operations: he has not yet cut a real part with 2.20/2.21.
- Polar Wrap with After operation and the tool report: not yet tried on his PC.

## Not covered by tests yet
- Wrap: grid point exactly on a mesh vertex/edge; a mesh with holes; feed between points when C turns fast near
  the axis.
- FreeCAD 26.3 has its own Rotary Surface (OpenCAMLib, A axis on a mill). Polar Wrap stays for the XZC lathe;
  noted only, nothing to do.
