# References — other people's code we have studied

One file per project, so a new session knows what was already read without reading it again.
**Read this list at the start of any work that touches another project.**

| Project | File | Licence | What it is for us |
|---|---|---|---|
| Kiri:Moto (GridSpace/grid-apps) `d138275` | [kirimoto.md](kirimoto.md) | MIT (file headers say "All Rights Reserved") | CAM in the browser; candidate home for the converter (post-processor hook `gcodeProc`); its 4th-axis code |
| Tilt axis research: LinuxCNC source/docs `46a388f`, industry B-axis mill-turns, cylindrical interpolation | [tilt-axis-research.md](tilt-axis-research.md) | — (docs; one GitHub project without licence → method only) | Why the tilt axis is **B**, joint renumbering, tool length at B = 90, face vs periphery inputs |
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
