# Reference — Joshua Bird: Core R-Theta 4-axis printer and S4 slicer

*Detailed read 2026-10-07, from the source itself, at Marios's request. Why: Marios plans a **4th axis on his
machine — the router tilts (about 90°) so it can also machine the periphery of the part** — and the converter
must support it through a machine-layout selector. Bird's printer is the closest existing machine: C = rotating
bed, X = radius, Z = height, B = tool tilt in the radial plane.*

**Licence: GPL-3 → method only, never code in our MIT repo.** (Printer files: GPL-3 + "no selling" clause.)

| Repo | Commit (read) | Licence | Read |
|---|---|---|---|
| `github.com/jyjblrd/Core-R-Theta-4-Axis-Printer` | `107e2c1` (2025-06-08, 28 commits) | GPL-3 **+ no-sell** (hardware files) | README, licence, changelog, **all firmware files** (`reprap firmware config/*`). Not read: 23 STL, KiCad PCB (mechanics, not code) |
| `github.com/jyjblrd/S4_Slicer` | `bc4b8d9` (2025-04-27, 20 commits) | GPL-3 (no extra clause) | README, licence, **the whole `main.ipynb`** (21 cells, ~1,300 lines) |
| `github.com/jyjblrd/Radial_Non_Planar_Slicer` | `6a01738` (2025-06-08) | GPL-3 + no-sell | first pass only (2026-10-07), §4 |

Re-read: `git clone https://github.com/jyjblrd/<repo>.git && git checkout <commit>`. Marios does **not** need to
download anything — Claude clones them in its own session.

---

## 1. The machine (Core R-Theta printer)
- **C** = rotating bed (unlimited), **X** = radial arm, **Z** = lead-screw height, **B** = nozzle tilt about the
  **tangential** axis → the nozzle leans toward/away from the centre, in the vertical plane through the C axis.
  That is exactly Marios's planned layout (router tilting in the X-Z plane).
- X and B are a **"core" pair**: two motors on one belt loop; both move for X, they move in opposite directions
  for B (`to4axis.g`: `M669 K0 … X-1:0:0:1:0 … B0.2222:0:0:0.2222:0`). For a separate B motor this is irrelevant.
- Board: Fly-E3-Pro v3, RepRapFirmware 3.5. Sensorless homing on X and B, Z by probe, C "homes" in place
  (`homec.g`: `G92 C0` — same idea as LinuxCNC immediate homing of our C).

## 2. Firmware — two kinematic modes (`config.g` → `to4axis.g` or `topolar.g`)
- **Polar mode** (`topolar.g`): RRF's built-in polar kinematics `M669 K7 H115.5 F200 A5000 S4000 T0.1`
  (homed radius 115.5, turntable max speed 200 °/s, accel 5000 °/s², 4000 segments/s, minimum segment 0.1 mm).
  The firmware converts XY → polar in real time. Normal planar printing.
- **4-axis mode** (`to4axis.g`, used by the slicers): plain axes, `M584 … S0` = "treat all as linear axes in
  feed-rate calculations — **have to use inverse-time feed in the G-code**". So: offline transform + G93, the
  same architecture as our converter (DECISIONS.md).
- 4-axis limits: **C ±20,000,000°** (practically unlimited — our C is ±99,999°, see STATUS), **X −37.5 … 115.5**
  (X may go 37.5 mm past the centre), Z −50 … 200, **B −180 … 90**.
- Speeds (units/min): C 21,600 (= 360 °/s), X 20,000, Z 8,000, B 21,600; accel C 2000, X 5000, Z 1500, B 2000.
- Homing order (`homeall.g`): lift Z, home X (twice), then B against its end (sensorless), X again, probe Z with
  the probe turned down, then turn the nozzle down and zero B.

## 3. S4 slicer — the whole pipeline (`main.ipynb`)
Additive and support-free: the goal is to **tilt the nozzle so overhangs print without support**. Steps:
1. **Tetrahedral mesh** of the STL (`tetgen`), origin = centre-bottom of the bounding box; neighbour graphs.
2. Per cell: lowest surface normal → **overhang angle**; Dijkstra path to the bed; "in air" flag.
3. **Rotation field** (one tilt angle per cell, about the tangential axis `cross(Z, cell_xy)` — always the radial
   plane). Initial value from the overhang beyond `MAX_OVERHANG` (30°), direction from the gradient of the path
   length to the bed (plane fit); smoothed; scaled (`ROTATION_MULTIPLIER` 2); clipped.
4. **Optimise** the field (scipy `least_squares`, sparse Jacobian): neighbour smoothness (weight 20) + closeness to
   the initial field. 100 iterations.
5. **Deform the mesh** so every cell takes its rotation (`least_squares` over all vertex positions, 1000
   iterations) → export the deformed STL. Can be repeated.
6. **Slice the deformed STL in Cura** (planar, origin at bed centre, no z-hop/scripts; `cura_config.3mf`).
7. **Map the Cura G-code back** (cell 17):
   - every G0/G1 is cut into fixed **0.6 mm** pieces (`SEG_SIZE`) *before* the transform;
   - per point: find the containing tetrahedron → **barycentric interpolation** of the vertex displacement (new
     position) and of the vertex rotation (tilt);
   - tilt per cell from the deformation by a 2-D **Kabsch** fit in the radial plane; clipped to **+30 / −130°**;
   - **tilt smoothing:** exponential moving average along the path, α = 0.2;
   - **max tilt change 1° per point** (`ROTATION_MAX_DELTA`): bigger jumps get interpolated points (position and
     tilt linear, inverse-time F × number of pieces) "to prevent the nozzle hitting the part as it rotates";
   - travel over gaps: hop to the highest printed Z, tilt capped at ±45° (long nozzle body "hangs below");
   - extrusion scaled by the cell's volume change (cap ×10).
8. **Machine output** (cell 18), per point:
   - `r = |xy|`, `θ = atan2(y, x)`, **shortest-delta unwrap** accumulated into C (no pole handling at all);
   - **pivot compensation** with `L = NOZZLE_OFFSET = 42` mm (comment: "actually 41.5"), hop h = 1 mm on travel:
     `X = r − sin(b)·(L + h)`, `Z = z + (cos(b) − 1)·(L + h) + h`, `B = b` (degrees);
   - G93: `F = 1 / (piece length / feed)` with the piece length measured **in the deformed (slicing) space**, not
     on the real tool path — so the real speed is only approximate; zero-length moves switch to `G94 F20000`
     and back.
   - Header: `G28`, `G0 C0 X0 Z20 B0`, `G93`.

## 4. Radial slicer (separate repo, first pass only)
- Tilt is a rule of the radius: `deg2rad(15 + 30·r/r_max)` (alternatives: fixed −40°, or `−40 + 30·(1 − r/r_max)²`).
- Every G1 cut into **1 mm** pieces before the transform; G93 per piece; same unwrap; compensation
  `r += sin(t)·L`, `z += (cos(t) − 1)·L`, output `B = −t` (sign opposite to S4); rapids in G94 F50000.

## 5. What carries over to MILLING (Marios's tilting router) — and what does not
**Carries over (method):**
- Tilt in the **radial plane** (about the tangential axis): C stays the polar angle, so our pole handling still
  works (DECISIONS.md). B = 0 → tool parallel to Z (today's face milling); B = 90° → tool radial (periphery).
- **Inverse kinematics of the tilt head** (the core formula): the machine moves the **pivot**, the CAM gives the
  **tool tip** and the tool direction. Pivot = tip + L·(tool direction). With the tool in the radial plane:
  `X_pivot = r_tip + L·sin(b)`·(sign by convention), `Z_pivot = z_tip + L·cos(b)` (minus a constant so that
  B = 0 reads like today). **L must be per tool** (router: changes with every tool and stick-out) — Bird uses
  one fixed nozzle.
- **Max tilt change per block** with interpolation, and **G93 for every move**, are needed for the same reason.
- Unlimited C range in the controller (his ±20,000,000°).

**Does not carry over / must be done better for milling:**
- S4's whole rotation-field optimisation is about **printing overhangs**; a milling tilt comes from the
  **CAM's tool orientation** (or a simple rule: 0° for the face, 90° for the periphery), not from an optimiser.
- Fixed 0.6 mm / 1 mm segmentation → our **error-controlled** segmentation (measured joint-space error) must be
  extended to 4 joints (X, Z, B, C): the **tip** path error, not the pivot path, is what cuts the part.
- G93 time from the real **tip** path (Bird uses the pre-transform length).
- No pole handling, no collision checks beyond a heuristic, no verification. We have all three for 3 axes.
- Tilt smoothing by moving average **moves the tool off the CAM's orientation** — for cutting, smoothing must
  stay within an angle tolerance, or not be done at all.

## 6. Consequences for Marios's machine (to decide with him — see STATUS.md)
1. **Joint numbering changes.** LinuxCNC pairs joints with axes in canonical order X Y Z A B C. Today XZC:
   joint 0 X, 1 Z, 2 C. With a tilt axis named B (or A): **X 0, Z 1, B 2, C 3** — **C moves from joint 2 to
   joint 3**, so `[JOINT_2]` C values, the HAL nets and `halui.joint.2` lines all move. Machine config first.
2. **Simultaneous or indexed?** A router fixed at 0° or 90° during each cut (indexed, "3+1") is far simpler —
   and with B = 90° the machine is a C-axis lathe with a radial live tool. Simultaneous tilt (B moving while
   cutting) needs tool orientation from the CAM for every point.
3. **CAM source for the periphery (B = 90°):** a mill's 4th-axis program (A about X, tool along Z) is the same
   geometry: mill X → machine Z (axial), mill Z (radius) → machine X (+ pivot), mill A → machine C. **Kiri:Moto's
   lathe op** already produces exactly that (see `kirimoto.md` §5); so do Fusion's rotary/"wrap" toolpaths. A
   converter layout "4th-axis mill program → XZC with radial tool" would reuse them directly.
4. **Data needed from Marios** (rule 4 — not assumed): axis letter, B = 0 / 90 positions and direction, travel,
   motor + drive + reduction (steps/deg), homing switch, which BOB output (stepgen.03?), pivot position relative
   to the tool tip (L per tool, and any offset off the plane through the C axis — an offset there shifts every cut),
   router body clearance from the chuck at 90°.
