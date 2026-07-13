# Polar CNC — Cartesian → Polar (XCZ) G-code Converter &amp; Simulator

A browser-based tool that converts standard Cartesian XY G-code (from Fusion 360, any CAM package, or a
slicer) into **Polar XCZ G-code** for a 2-linear + 1-rotary-axis CNC machine (X = radius, C = rotary table
angle, Z = depth), ...running on LinuxCNC configured as a native XCZ machine (using trivkins) with G93 inverse-time feed.

Live demo (once GitHub Pages is enabled for this repo): https://marioskiv.github.io/polar-cnc-converter/

Open [`index.html`](./index.html) directly in any modern browser — no build step, no server required.

---

## Why this exists

Converting a Cartesian XY toolpath to Polar (radius + angle) is conceptually simple — but naively doing it
introduces two hard problems on a real machine:

1. **Feed-rate correctness.** A polar machine's tangential tool-tip speed depends on the radius
   (`v = r · ω`). A feed rate that's correct for a Cartesian machine is wrong on a polar one — too slow near
   the edge, or physically impossible near the center. Just re-emitting the original F value (as most simple
   postprocessors do) produces an inefficient or physically incorrect program.
2. **The center singularity.** At small radius, a tiny Cartesian move can demand a huge, sudden rotation of
   the C axis (in the limit, infinite angular velocity at r = 0). Something has to give: freeze the axis,
   detour around it, or reformulate the move.

This project solves both, specifically for **LinuxCNC**:

- **G93 inverse-time feed** — every emitted `G1` block carries its own computed `F` (`F = 1/T`), rather than
  letting the controller reinterpret a Cartesian-style F on non-Cartesian motion.
- **Physics-based feed cap** — `F_eff = min(F_cam, C_VEL_LIMIT × r × π/180)`, so the tool never exceeds the
  rotary table's real angular velocity limit (configurable: max deg/min and max motor RPM).
- **Look-ahead cornering** — feed is reduced at sharp direction changes (> 45°) to avoid jerk.
- **Center-zone handling**, three selectable strategies:
  - **Signed X** — freeze C for a whole line that crosses the centre and let X sweep through zero into
    negative values (X<0 at a fixed C is geometrically the same point as +|X| at C+180°) — avoids any abrupt
    180° table rotation for near-diametrical cuts.
  - **Auto** *(default)* — detects genuine diameter-like crossings (enters one side of the centre zone, exits
    the far side) via line/circle intersection math, and only uses Signed X when it's geometrically justified
    *and* stays within configured **X axis travel limits**; everything else falls back to:
  - **Pocket Fill** — mills the centre disk with a concentric-circle pocess the first time it's entered at a
    given Z depth (classic strategy, always physically safe, never asks for negative X).
- **Adaptive chordal segmentation** — subdivides lines/arcs based on distance-to-centre and a chord-tolerance
  setting, denser near the centre where curvature (in polar space) is highest.
- **3D toolpath simulator** (Three.js) with continuous, feedrate-accurate playback (not just point-to-point
  jumps), Rotary-Mill and Static-3D view modes, and live telemetry (X/C/Z/F, max radius/angular velocity warnings, X
  travel-limit warnings).

## Quick start

1. Open `index.html` in a browser.
2. Paste Cartesian G-code (X/Y/Z, G0/G1/G2/G3) into **Step 1**.
3. Click **Convert &amp; Simulate**.
4. Review/adjust **Converter Settings** (chord tolerance, center threshold, rotary table limits, center
   crossing mode, X axis travel limits, cornering) — they re-apply live on the next conversion.
5. Export the Polar G-code (`.nc`) from **Step 2**, or watch it run in the 3D simulator below.

## Settings reference

| Setting | Meaning |
|---|---|
| Chord Tolerance | Max chordal deviation (mm) allowed per segment — smaller = denser/more accurate curves |
| Center Threshold | Radius (mm) below which the C axis is considered "in the centre zone" |
| Center Fill Step / Retract | Stepover and Z-retract clearance for the Pocket Fill strategy |
| Center Crossing | `Signed X` / `Auto` (recommended) / `Pocket Fill` — see above |
| X Axis Min/Max | Physical X (radial) travel limits (mm) — Signed-X output is validated against these |
| Max C Vel / Max C Motor | Rotary table angular velocity limit (deg/min) and motor RPM cap |
| Corner Multiplier | Feed multiplier applied at sharp (>45°) direction changes |
| G93 / G94 | Output feed mode toggle (G93 inverse-time recommended for LinuxCNC; G94 mm/min available) |

## Credit / prior art

This project was inspired by **kadirilkimen**'s PolarBear CNC ecosystem, which first explored Cartesian-to-
Polar G-code postprocessing for this class of machine:

- [Polar-Bear-Cnc-Machine](https://github.com/kadirilkimen/Polar-Bear-Cnc-Machine) — the physical machine concept
- [polarToolsJS](https://github.com/kadirilkimen/polarToolsJS) — web UI g-code converter
- [gCodePolarizerJS](https://github.com/kadirilkimen/gCodePolarizerJS) — core Cartesian→Polar JS library

No code from those repositories is reused verbatim here; this is an independent implementation targeting
LinuxCNC specifically, with its own feed-physics model, center-singularity strategies, and simulator. Full
credit to the original author for pioneering the underlying concept.

Also referenced during design/validation (see repo memory for details): grblHAL's `kinematics/polar.c` and
Duet3D RepRapFirmware's `PolarKinematics.cpp`, both of which implement native polar kinematics in firmware —
useful cross-checks for the angle-unwrap math and radius-limit handling used here.

## License

MIT — see [`LICENSE`](./LICENSE).
