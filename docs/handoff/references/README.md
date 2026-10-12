# References — other people's code we have studied

One file per project, so a new session knows what was already read without reading it again.
**Read this list at the start of any work that touches another project.**

| Project | File | Licence | What it is for us |
|---|---|---|---|
| Kiri:Moto (GridSpace/grid-apps) `d138275` | [kirimoto.md](kirimoto.md) | MIT (file headers say "All Rights Reserved") | CAM in the browser; candidate home for the converter (post-processor hook `gcodeProc`); its 4th-axis code |
| Tilt axis research: LinuxCNC source/docs `46a388f`, industry B-axis mill-turns, cylindrical interpolation | [tilt-axis-research.md](tilt-axis-research.md) | — (docs; one GitHub project without licence → method only) | Why the tilt axis is **B**, joint renumbering, tool length at B = 90, face vs periphery inputs |
| FreeCAD CAM workbench `e326ee2` (dev, 2026-10-07) | [freecad-cam.md](freecad-cam.md) | LGPL-2.1 — **method only** | Indexed tilt per operation + continuous 4th-axis surfacing (RotarySurface); **no simultaneous tilt** |
| FreeCAD addon feasibility 2026-10-12: FreeCAD 26.3.0 (conda-forge 2026.09.16) run headless with a prototype addon | [freecad-addon-feasibility-2026-10-12.md](freecad-addon-feasibility-2026-10-12.md) | LGPL host, our addon MIT | Proven: XZC `.fcm` valid, addon discovery (needs `Init.py`), post gets arcs + tool diameter, G93 as-is lines survive, `G0 C0` poses to drop; end-to-end identical to the page |
| Architecture options 2026-10-12: pre-processor vs FreeCAD addon vs Kiri hook vs LinuxCNC kinematics (LinuxCNC 2.9.10 `control.c` read) | [architecture-options-2026-10-12.md](architecture-options-2026-10-12.md) | — | Recommendation: keep the offline core, FreeCAD addon long-term, no real-time kinematics; roadmap |
| Research 2026-10-11: Klipper, grblHAL, Marlin, RRF, LinuxCNC rosekins, Sandify; simulators (CAMotics, FreeCAD, Kiri); LinuxCNC on trixie; FreeCAD machine definition `dd5f963`, Kiri `rel-next` `76d509f` | [research-2026-10-11.md](research-2026-10-11.md) | mostly GPL / LGPL — **method only** | Ideas list (arcs around the centre exact, centre-offset compensation, 255-char lines, simulator deviation/speed maps), trixie checklist, updated CAM recommendation (FreeCAD addon) |
| Polar programming 2026-10-12: Zhang/Chen/Du 2013 (polar interpolation module, IJAMT 68:1767); Fanuc G15/G16 + ENCY pages (blocked, not read) | [polar-papers-2026-10-12.md](polar-papers-2026-10-12.md) | paper: Springer © — **method only** | Confirms spiral-error pieces and exact X-constant arcs around the centre; nothing new for the pole; led to 2.11.4 (polar input refused) |
| Joshua Bird — Core R-Theta printer `107e2c1`, S4 slicer `bc4b8d9` (+ radial slicer, first pass) | [bird-4axis.md](bird-4axis.md) | GPL-3 (+ no-sell clause on the printer) — **method only** | Model for Marios's tilting router (B in the radial plane): pivot compensation, max tilt per block, G93, firmware limits; what does NOT carry over to milling |

## How to add a project (when Marios gives a URL or files)
1. Clone into the scratchpad (never into this repo): `git clone --depth 50 <url>`; note the **commit hash**.
2. Read the **licence file and the file headers**. GPL / no-sell / "All Rights Reserved" → method only.
3. Write `references/<name>.md`:
   - URL, commit, date read, licence (verified);
   - what was read in full, what was skimmed, what was not read;
   - the method in our own words (formulas, pseudo-code — never pasted code);
   - key files and functions (path:line) so a later session can go straight back to them;
   - what is useful to us, what is not, problems found;
   - Marios's goal for this project, in his words.
4. Add a row to the table above and an entry in `../LOG.md`.
