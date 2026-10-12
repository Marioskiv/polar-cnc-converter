# Fanuc Series 16i/18i-MB Operator's Manual — B-63534EN/02 (read 2026-10-12)

- **Source:** PDF uploaded by Marios (GE Fanuc edition GFZ-63534EN/02, June 2002, 1257 pages), stored in his
  PRIVATE repo `Marioskiv/cnc-manuals` (`GE_FANUC_User_Manual_1.PDF`, commit `beb8e35`).
- **Licence:** © FANUC / GE Fanuc, "All Rights Reserved". Facts and short quotes only here; the PDF never goes into
  this public repo.
- **How it was read:** text extracted with `pdftotext -layout` and read in full: 8 consecutive chunks by
  parallel readers, plus the key chapters by Claude directly (§4.8 G12.1, §5.3 G93, §8.2 G16, the contents).
  Page numbers below are the printed ones.

## What it says that matters to the converter

### G15/G16 polar coordinate command (§8.2, p.138-140) — source for 2.12.2 "E"
- X = radius, Y = angle (in G17); + angle = counter-clockwise from the first axis +. Format `G17 G90 G16 ;`.
- G90: pole = work origin (or the G52 local origin). G91: pole = **current position**, radius measured from it.
- Example 1: `N2 G81 X100.0 Y30.0 …`, `N3 Y150.0` = "distance 100 mm, angle 150 degrees" → a left-out radius
  keeps its last value. Example 2: `N3 G91 Y120.0` = "100 mm, +120 degrees" (angle incremental, radius absolute).
- Arcs in G16 only with R. X/Y of G04, G10, G52, G92, G53, G22, G68, G51 are not polar. No `,C ,R` in G16.
- Power-on/reset state shows G15 (MDI modal screen p.794, 1010).

### G93 inverse time (§5.3, p.99-100)
- F = 1/time (min), 0.001 … 9999.999; **F is not modal in G93** (alarm 011 without it, or with F0).
- **Arcs:** F = feed / arc **radius** (not the block length) — differs from LinuxCNC (time of the block). Reason
  enough to keep refusing G93 input.
- G94 at power-on. In G94 a mixed linear + rotary move counts degrees as mm (p.46) — why our output uses G93.

### G12.1/G13.1 polar interpolation (§4.8, p.59-62) and G7.1 (§4.9, p.63)
- At `G12.1` the virtual axis C' is 0 and the angle is taken as 0 at the tool's position; X/C' are Cartesian mm
  about the C centre; arcs with I/J or R; coordinate system must not change inside. → an import of Fanuc G12.1 lathe
  programs would be possible with certainty (idea, not built).
- Feed limit near the centre: F < L × R × π/180 (L = closest distance to the centre, R = max C feed deg/min).
- No stroke check is made in polar or cylindrical interpolation mode (p.861).

### Arcs (§4.4, p.48-51)
- I/J/K always incremental from the start point; I0/J0/K0 may be omitted; R negative for > 180°.
- **R and I/J together: R wins, I/J ignored** (p.50). LinuxCNC refuses — we refuse (safer).
- Start/end radius difference > parameter 3410 → alarm 020.

### Dwell, decimal point, rapids
- `G04 X_` = seconds (decimal allowed); `G04 P_` = **milliseconds** (no decimal). LinuxCNC `G4 P` = seconds.
- Numbers without a decimal point = least input increment (X1000 = 1 mm at IS-B) unless "calculator" input
  (parameter 3401 DPI) is set (p.142, examples p.979-981). A CAM writes decimals; hand-written Fanuc programs may not.
- G00 is per-axis ("non-linear") by default (parameter 1401 LRP) — same as LinuxCNC joint-space rapids.
- G53/G28 are always non-linear (p.43). G53 in G91 is ignored. G28/G53 cancel the tool-length offset while moving.

### Rotary axis
- +C = counter-clockwise seen from +Z (p.385) — same as the converter.
- Roll-over and shortest path depend on machine parameters (1008 ROA/RAB, p.531-532) — never assumed.

### Codes found passing through the converter (fixed in 2.12.2 with a whitelist)
`G4 X`, `G51`, `G50.1`, `G22`, `G29`, `G45`, `G60` (X/Y became moves); `G6.2` NURBS, `G2.2` involute, `G2.4`
3-D arc (became lines); `G33`, `G95`, `G5 P10000`, `G5.1 Q1`, `G43.4/43.5`, `G41.2`, `G54.2`, `G10.6`, `G65/G66`,
`G39`; `G08 P1`; `,C ,R`; block delete `/`; `G91 G81` on one line; `O1000` program number.

## Not useful to us
Operation chapters (screens, keys, floppy/memory card/Ethernet, editing), tool life, grinding, hobbing/EGB,
two-path control, 5-axis TCP (G43.4/G43.5) details, alarms of servo/spindle hardware, batteries.
