# Decisions and rejected ideas

## Architecture (final)
- **Pre-processor + trivkins + G93.** Real-time kinematics was rejected: no lookahead, and LinuxCNC enforces the
  `[AXIS_C]` limits on every move anyway. Equivalent to Fusion's "IN_COMPUTER"/XZC. Output is **always G93**
  (inverse time). G94 was removed on purpose: LinuxCNC applies a G94 F only to the X/Z length and ignores the C arc,
  so feed control was wrong on tangential moves.
- The converter does **not** model machine dynamics (axis speed, acceleration, gear ratio). The controller enforces them.
  Hence no minimum block time that changes motion (2.5.0: floor 0.6 ms, was 0.06 s and slowed short blocks).
- `convert(text, options)` stays a pure function, no DOM. Licence MIT, header in every source file.

## Accuracy
- Chord tolerance default **0.025 mm**; `G64 P0.025` in the machine startup code. Total budget for aluminium 0.05 mm.
- Centre zone is **automatic** (half the chord tolerance). A stored explicit 2 mm (old default) is upgraded to automatic.
  Strategies near the pole: Signed-X (only when exact: the line lies on the axis through the pole and fits the X travel)
  → Index at Pole (Siemens TRANSMIT POLE_SIDE_FIX style). Pocket Fill only by explicit request (`centerMode: fill` or an
  explicit zone larger than the chord tolerance) — it clears a disk the CAM did not ask for.
- **X Axis Min is the machining side**: 0 = one side of the centre only. Marios machines one side (rigid half of the
  cross-slide).
  **2.10.0:** on the page it is the choice "Cutting side: one side / both sides (+ distance)"; `xMin` and `xMax` have
  **no defaults** (−1000/1000 removed) — missing → refused. Marios wants X Axis Max kept and required.
- Arcs: chord at tol/2, polar split at 0.4·tol. Rapids (G0) are segmented along the straight Cartesian line
  (`RAPID_TOL = 0.5 mm`), because LinuxCNC interpolates in joint space (a spiral otherwise).
- Merging of tiny moves checks the real error of the merged block and never drops a point that is off the new block.

## Input handling
- Preserve every G-code word (G43 H, S, M, T, coolant, comments, tool changes) in the correct execution order.
- G53/G28/G30 retracts: **2.11.0 (Marios chose "β")** → `G0 Z<the program's own highest Z>` in work coordinates;
  no Safe retract Z setting (was: the user's machine Z, rejected if empty). Universal, needs no machine data. X/Y parks (`G28 G91 X0 Y0`,
  `G53 G0 X.. Y..`) are skipped — not moving can hit nothing (2.5.0). **2.12.1 (Marios: A, B, C):** Fanuc `G16`
  is CONVERTED in its certain form (G17, G90, both X=radius and Y=angle per line, pole = work origin; G15/G16 removed);
  G91 in G16, missing radius/angle, arcs in G16 → refused. **2.12.2 (E, Fanuc B-63534EN §8.2):** a left-out
  radius/angle keeps its last value; `G91 Y` (angle only) turns the angle; G91 with a radius and a first point
  without both values stay refused. **2.12.2: only KNOWN G codes are read** (a whitelist, not a list of bad codes);
  anything else stops with the line number. Also refused: `G4 X`, `,C ,R`, block delete `/`, `G08 P`, G91 on a cycle
  line. A Fanuc `O1000` program number becomes a comment. Polar interpolation input (G12.1/G112) and `@ ^` stay
  refused (2.11.4). Arcs with both R and I/J → refused like LinuxCNC. Radial rapids = one block.
  **D (Marios):** subprograms (M98/M99, o-word sub/call), o-word loops/conditions and parameters/expressions
  (`#`, `[ ]`) → refused (were passed through / converted out of order).
  **F (Marios, both parts):** header writes `G8` (or `G7` for a diameter profile) when the rotary axis is C; input
  `G7` refused, input `G8` removed. Not for A/B profiles (mill-style controls may not know G7/G8). G41/G42, G92/G52/G10 with XY,
  G90.1, G93 input, G18/G19 arcs, tapping/threading are rejected with the line number. Drilling cycles are expanded.
- Tool diameter comes from CAM tool comments of any CAM (2.8.0, `scanToolDiameters`): a stated diameter (D=, DIA,
  Diameter, TOOL/MILL, flute=) beats a size in a tool name; a bare `D1` is an offset register, never a diameter;
  **2.9.0 (Marios): there is NO Tool Diameter setting** — the diameter comes only from the program; when missing
  it is reported, never invented (fill auto-stepover and tilt ball refuse; material map shows the centre path). Tool length is
  never needed for XZC (LinuxCNC applies G43 H from its tool table). The tilting layout needs it (2.7.0): it reads the
  machine's own LinuxCNC `tool.tbl`; G43 stays valid (see `references/tilt-axis-research.md` §3).
- Converter-written comments never nest (LinuxCNC: "Nested comment found"); a safety net strips inner parentheses.

## REJECTED by Marios — do not propose again
- **Retracting Z before a large C rotation** (e.g. in Index at Pole): he does not accept any retract that leaves
  material uncut. A partial implementation was reverted at his instruction.
- C speed/acceleration/corner settings in the converter (removed; the controller decides).
- The "rotary axis letter" option is only a rename (C/A/B) of the same machine; it is not a second axis.

## Machine decisions
- **No guard for output lines over 251 characters** (Marios 2026-10-11): such lines practically never occur (only a very
  long CAM comment); LinuxCNC would just refuse the file with "Command too long". Limit verified in the source anyway.
- **No centre-height (router offset) compensation** (Marios 2026-10-11): the router base will be milled on the
  machine with the chuck, so the cutter is on the chuck axis by construction.
- C driver stays at 3200 steps/rev. X/Z are not sped up (the 2 mm screw is the limit, not the settings).
- Machine Z numbered like a mill (Z0 = home park, negative toward the chuck) — delivered, install pending.
- The `.ini` and `.hal` are never regenerated with PNCconf.

## Future tilt axis — principles agreed
- The tool tilts in the **radial plane** (X-Z plane); C stays the polar angle, so the pole logic keeps working.
  A tangential tilt would add an unreachable disk of radius L·|sin a| around the centre — avoid unless needed.
- The distance pivot → tool tip changes with every tool; it must be a per-tool value.
- Stay on trivkins (offline transform). Custom kinematics would move the pole problem into the controller.
- Bird's code is GPL: method only. See `references/bird-4axis.md`.
- **Marios confirmed (2026-10-07): the router tilts like Bird's printer (toward/away from the centre, radial plane),
  simultaneously while cutting.**
- Tilt axis letter: **B** (rotation about a line parallel to Y — LinuxCNC docs, ISO 841, LinuxCNC's own tilting-head
  example, industry B-axis mill-turns); A only as a rename option. Direction needs an invert option + test cut.
  Research: `references/tilt-axis-research.md` (2026-10-07). Hardware not built: no `.ini`/`.hal` change now.
- **Built 2.7.0 (layout `xzcb`):** ball-end tools lean by a wanted angle, reduced automatically to fit the X and B travel;
  the ball centre stays on the CAM path (exact for a ball). Other tools stay at B 0. B returns to 0 before a tool change,
  after a machine retract (at the top) and at the end. Built ON the XZC layout (its blocks, split for the tilt error
  K·dB²/8 ≤ 0.08·chord tol). Pivot, tilt travel and tool lengths have no defaults: missing → refused.
- Adding the tilt axis renumbers the joints (canonical order X Y Z A B C): XZBC → C becomes joint 3.
- For milling the tilt comes from the CAM's tool orientation (or a fixed 0°/90°), not from a printing-style
  optimiser; G93 time and the error checks use the **tool-tip** path, not the pivot path.
- G93 time of a block = max(tip path length / CAM feed, each joint's travel / its limit, a minimum time) — pure
  reorientation moves have zero tip length and must not produce F = 1/0.
