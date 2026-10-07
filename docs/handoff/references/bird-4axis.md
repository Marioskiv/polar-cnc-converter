# Reference — Joshua Bird: Core R-Theta 4-axis printer and slicers

*Moved here from `reference-kirimoto-bird-4axis.md` (2026-10-07). Read from source on 2026-10-07.
GPL-3 (two repos with a no-sell clause): **method only, no code in the MIT converter.***

## 1. Repositories and licences (verified in the files)
| Repo | Commit | Licence |
|---|---|---|
| `jyjblrd/S4_Slicer` | `bc4b8d9` (2025-04-27) | GPL-3.0 |
| `jyjblrd/Radial_Non_Planar_Slicer` | `6a01738` (2025-06-08) | GPL-3.0 **+ no-sell exception** |
| `jyjblrd/Core-R-Theta-4-Axis-Printer` | `107e2c1` (2025-06-08) | GPL-3.0 (hardware) **+ no-sell exception** |

All copyleft → **no code may go into the MIT converter.** Method only.

## 2. Machine
C = rotating bed, X = radial arm, Z = lead screw, **B = nozzle tilt about the tangential axis** (the nozzle leans
toward/away from the centre, in the plane through the bed axis). X and B share one belt (CoreXY-like mixing).

## 3. Radial slicer (`main.ipynb`, 272 lines of code)
- **Tilt is a rule of the radius:** `ROTATION = lambda r: deg2rad(15 + 30·r/r_max)` (propeller/tree); alternatives
  in comments: fixed `-40°`, or `-40 + 30·(1 - r/r_max)²` (bridge).
- **Segmentation:** every G1 cut into fixed **1 mm** pieces *before* the transform.
- **Feed:** G93 inverse time, `F = 1 / (seg_length / feed)` per piece.
- **Transform per point:** `r = |xy|`, `θ = atan2(y, x)`, shortest-delta unwrap (±π) accumulated into C.
- **Nozzle-offset compensation** (L = pivot-to-tip): `r += sin(tilt)·L`, `z += (cos(tilt) − 1)·L`;
  output `B = −tilt`.
- Rapids: written in **G94 with F50000**, then back to G93. Points with z < 0 or NaN are skipped.
- **No pole handling.**

## 4. S4 slicer (`main.ipynb`, 1316 lines of code)
- Tetrahedral mesh; a **rotation field** per cell (about the tangential vector `cross(Z, cell_center_xy)` → always
  radial-plane tilt), initial value from the overhang angle, then optimised (neighbour smoothness + target,
  scipy). The mesh is deformed, sliced with Cura, and every G-code point is mapped back by barycentric
  interpolation, giving position **and tilt** per point.
- **Tilt smoothing:** exponential moving average, α = 0.2.
- **Max tilt change per point: 1°** (`ROTATION_MAX_DELTA`). Larger jumps get interpolated points (inverse-time F
  multiplied by the number of pieces) "to prevent the nozzle hitting the part as it rotates".
- `NOZZLE_OFFSET = 42` (comment: "actually 41.5").
- Travel moves: **1 mm hop along the tool axis**: `r += −sin(tilt)·(L + hop)`,
  `z += (cos(tilt) − 1)·(L + hop) + hop`; output `B = +tilt` (sign convention opposite to the radial slicer).
- Same θ unwrap. **No pole handling.**

## 5. Firmware (RepRapFirmware, `reprap firmware config/`)
- **Two modes:** `topolar.g` uses RRF's **built-in polar kinematics** (`M669 K7`) for normal printing;
  `to4axis.g` switches to `M669 K0` (linear motor-mixing matrix) with `M584 … S0` = "treat all as linear axes in
  feedrate calculations (have to use inverse time feed rate in gcode)".
- 4-axis limits: **C ±20,000,000** (practically unlimited turns), B −180 … (90 − offset).
- Max speeds (units/min): C 21600, X 20000, Z 8000, B 21600; accel: C 2000, X 5000, Z 1500, B 2000.
- Mixing: `M669 K0 C0:0:0:0:1 X-1:0:0:1:0 Z0:0:1:0:0 B0.22222222:0:0:0.222222222:0`.

## 6. What we take (as method)
- Tilt in the **radial plane** (about the tangential axis): C stays the polar angle, the pole logic still works.
- Pivot-to-tip compensation, **per tool** for a router (L changes with every tool and stick-out).
- Tilt smoothing and a **max tilt change per block** with interpolated points.
- Hop along the tool axis for travel moves.
- G93 for every move, and practically unlimited C limits in the controller.
- What Bird does **not** have and we already do: pole handling, error-controlled segmentation, verification.
