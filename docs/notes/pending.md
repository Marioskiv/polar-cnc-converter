# Pending — open items and questions for Marios

Newest first. Move an item to `memory.md` (Decisions) when it is decided, delete it when it is done.

## Waiting for Marios
- **Rename this repo** (his request 2026-10-20: "XCZ converter polar, warp"). A GitHub name cannot have spaces
  or commas: confirm the exact name (and XZC, the machine's axes, or XCZ as he wrote). Only he can rename it
  (GitHub → Settings → Repository name). After it: the web page address changes
  (`marioskiv.github.io/<new name>`, the old link stops working), and every file header, README, package.xml
  URL and his Addon Manager custom repository must be updated (GitHub redirects the old git URL).
- **Tool-library repo** (his request 2026-10-20): the cutter libraries were only sent as zips (YG-1 26 bits,
  IZAR 85, Stepcraft 3, Amana 34; see WikiTips memory.md of 2026-10-17); they are not in any repo and not on
  this machine (only his Amana .tools and IZAR PDF uploads remain). Ask: repo name, private or public, and
  whether he uploads his zips or they are rebuilt from his catalogs.
- **Knurling & Wrap**: not yet tried on his PC after the move (2.23.0). The texts are Greek only (as in
  WikiTips); English not asked for.
- **Wrap .ini / .hal:** the router's side on the Wrap setup is not decided yet. Advice given (2026-10-20): work X0 =
  the chuck axis, X+ = away from it (flip the X scale sign in the Wrap .ini if needed); the same .hal if it reads
  scales/limits from the .ini; its own .ini and its own tool table (lengths in the X column). To write it: his
  decision on the router side + his real .hal. His real machine files are in his private repo `cnc-manuals`
  (not in this repo; `examples/.../polarlathe-sim.ini` is only the simulation copy).
- **Header text:** the converter always writes "C goes past 99999 deg" (fixed number) even when his .ini limit
  is larger. Cosmetic; ask before touching the converter.
- **C soft limit:** decided 2026-10-20 (see memory.md). Marios raises the limit in his real .ini himself.
  Not confirmed yet that he has done it.
- **Spindle:** switched by hand today (LinuxCNC later). Until then M3/M5 do nothing: he switches the router off
  himself at the tool-change dialog.
- Polar mode with FreeCAD's own operations: he has not yet cut a real part with 2.20–2.22.
- Polar Wrap with After operation and the tool report: not yet tried on his PC.
- 2.22.0 tool-change park: not yet run on the machine. Precondition (from the other chat): his real .ini must
  have the X fix of 2026-10-19 (HOME_OFFSET -24.039) so that machine X0 is the chuck centre.

## Not covered by tests yet
- Wrap: grid point exactly on a mesh vertex/edge; a mesh with holes; feed between points when C turns fast near
  the axis.
- The move from the park back to the next operation after M6 is not in the chuck check (the check sees the move
  from the previous operation instead). It is clear by construction: Wrap keeps X ≥ the operation's safe X all the
  way, polar moves X/C at the park Z and only then Z.
