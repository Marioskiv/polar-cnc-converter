# Polar programming sources read 2026-10-12 (Marios)

## 1. Zhang, Chen, Du — "A CNC program module based on polar coordinate system"
Int J Adv Manuf Technol (2013) 68:1767–1773, DOI 10.1007/s00170-013-4974-1 (Springer, copyrighted; PDF given by
Marios, read in full, 7 pages). Nothing copied; method in our own words.

- Machine: custom turn-mill-hob centre; milling with the workpiece spindle as rotary axis C1 and two linear axes
  (X1 radial, Z1) — the same kinematic family as Marios's lathe (radius + angle + axial).
- Two G-codes on their own controller (motion cards only interpolate linearly in joint space):
  - `G20 C θ2 X r2`: arc **centred on the rotary axis** — only C moves (X constant), interpolation error **zero**.
  - `G21 C θ2 X r2 N n`: line from the current point, split into n pieces; each piece is linear in (r, θ), i.e. an
    **Archimedean spiral** r = a + bθ; the error is the distance of that spiral from the true line, made small by n.
- Error analysis = ours: every joint-linear block is a spiral; choose the piece count from the wanted accuracy.
- Result on a 2.2 mm watch part (0.36 mm cutter): contour errors < 0.02 mm, better than a Tornos Deco with
  Mastercam polar output (one block per line/arc).
- Not covered: the pole (passing through or near r = 0), feed control (they use F directly; no inverse time),
  rapids. Their part does not cross the centre.

**For us:** confirms the converter's core (adaptive pieces sized by the spiral error, `jointChordErr`). Confirms
proposal (1) of `research-2026-10-11.md`: an arc centred on the chuck axis should be ONE exact block with X constant
(today a polygon: 127 blocks for R10). Nothing new for the pole — our Index at Pole / Signed-X go further.

## 2. ENCY CAM — "Polar interpolation" (docs.encycam.com/ENCY/1/en/10083.html)
Host blocked here; Marios pasted the page text (2026-10-12). What it says, in our words:
- Polar transformation turns an XYZ milling path into X(radius) C(angle) Z for lathes with a driven tool; needs a
  rotary axis turning the part, parallel to the tool axis, a radial axis and an axial axis — exactly this machine.
- R = sqrt(X² + Y²), A = atan2(Y, X); a **tolerance** (mm) for the deviation of the transformed path.
- Two ways: the CAM writes X C Z itself (our converter's way), or the control does it (Fanuc/Mori/Haas `G112/G113`,
  Siemens `TRANSMIT/TRAOFF`, Heidenhain none) — then the CAM writes XYZ between on/off commands.
- Nothing about the pole, inverse-time feed or rapids. Confirms our architecture (CAM-side transform with a
  tolerance) and the input refusal of `G112/G113` (those belong to controls that transform themselves).

## 3. Fanuc G15/G16 (helmancnc.com bolt-circle page)
**Not read:** host blocked by the session's network policy (also the mirrors). Known in general: G16 = polar
coordinate *command* on a normal mill (X = radius, Y = angle; pole at the work origin with G90, at the current point
with G91), used for hand-written bolt circles. Led to fix 2.11.4: polar input (G16, G12.1/G13.1, G112/G113, `@ ^`)
is refused instead of being read as Cartesian; `G15` is removed (LinuxCNC 2.9 does not know it — `_gees[150] = -1`).
Idea kept: bolt circles are native on XZC (X fixed, only C turns).

## 4. etcnmachining.com "Mastering CNC Programming with G16" (text pasted by Marios 2026-10-12; host blocked here)
**Unreliable — do not use as a reference.** Its three "G16 examples" contain no G16 at all; it says polar mode is left
with G17 (it is G15), mixes I/J and R on one arc (`G3 I-10 J0 R10` — LinuxCNC refuses "mixed radius-ijk"), gives arcs
without end points, suggests radians (Fanuc G16 angles are degrees), calls R the radius word and A the angle (in G16
the plane's 1st axis word is the radius, the 2nd the angle) and "G82 R30" as an angle. Correct and consistent with the
others: angle 0 = +X (3 o'clock), counter-clockwise positive; G15 cancels; used for bolt circles. Claim "Mach3
supports G16": not verified. **For proposal B (G16 input) the Fanuc operator's manual is the reference, not blogs.**
Found through it: the converter accepts an arc with BOTH R and I/J (`G3 X0 Y10 I-10 J0 R10`) and picks one meaning,
where LinuxCNC refuses the block → proposal C (refuse, like LinuxCNC).

## 5. Machining Doctor — G15/G16 (text pasted by Marios 2026-10-12)
- X = radius, Y = angle from 3 o'clock; `G16` alone → pole at X0 Y0; G15 cancels. Same as the others.
- **Differs:** "`G16 X5.0 Y6.0` places the pole at X5 Y6". Our 2.12.1 first draft read X/Y on the G16 line as a polar
  point → conflicting meanings → now refused (G16 must stand alone).
- Its bolt-circle example omits the radius on later lines (`G00 Y90`) — the radius is modal. 2.12.1 refuses lines
  with only one of the two words (safe); supporting "last radius/angle kept" is proposal E (needs a firm source).
- It uses `M98 P2000` subprograms. Found: the converter passes M98 through and converts the O2000 body where it
  stands in the file (after M30), with the position state of the line before it, not of the call → proposal D:
  refuse M98/M99 and O-word subroutine calls (`o… call/sub`) until handled properly.
