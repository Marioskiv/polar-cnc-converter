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

## 6. "Polar Coordinates FANUC Example" (Scribd-style 4-page document, text pasted by Marios 2026-10-12)
Fanuc **turn-mill** programs with `G12.1` (polar interpolation on) / `G13.1` (off): 28 mm square (G42 and G41),
24 mm hexagon, 12.8 mm two flats, axial live tool. Method, in our words:
- Inside G12.1 the program is written in a **virtual Cartesian plane**: `X` = the linear axis in the control's
  lathe (DIAMETER) units, `C` = the virtual second axis in mm (not degrees). `X28 C14` = corner of a 28 mm square
  (x = 28/2, y = 14). The control does the polar transform itself, in real time.
- Cutter radius compensation G41/G42 works inside G12.1 (the control compensates in the virtual plane), feed G94
  mm/min in that plane, approach/retract with G40 outside the profile; spindle oriented `G0 C0` / `G28 C0` first.
- Set-up: machine X zero on the spindle axis, tool offset to the cutter axis, radius only in the geometry offset;
  parameters 5460 (linear axis) / 5461 (rotary axis) name the axes, 3706#6.
- No word on the pole: none of the profiles passes through the centre (smallest square/hexagon stays away from it).

**For us:** (1) confirms the 2.11.4 refusal of G12.1 input — such a program is not XYZ milling input (X diameter,
C in mm), so converting it as if it were would be wrong; (2) these are exactly the "polar-native operations" in the
ideas list (squares, hexagons, flats on a part's face) — today: draw them in the CAM, the converter makes XZC;
(3) possible later idea: an import mode for Fanuc G12.1 lathe programs (X/2 → x, C → y, G41/G42 not possible —
CAM-side compensation only). Not proposed now.

## 7. "Fanuc C-Axis Polar Interpolation Square Machining Program" (vendor blog, text pasted by Marios 2026-10-12)
Same subject as §6 (G12.1/G13.1 = G112/G113, Fanuc 0i/16i/18i/21i-T, option "B1", alarm P/S010 without it;
M-codes for C-axis engage / live tool are machine-builder specific; G41/G42 engaged after G12.1 and cancelled
before G13.1). **Partly unreliable:** it says in one breath that arcs are "prohibited in polar mode" and then uses
`G03` with R and I/J (Fanuc does allow G02/G03 in G12.1 — §6 and the manual titles it cites); it calls C "degrees or
mm of arc" (in G12.1 the C word is a virtual linear axis in mm, §6); its "feed vs radius" paragraph mixes feed per
rev with surface speed. The Nakamura example uses inch, G99 feed per rev, `G28 H0` to home C. Nothing new for the
pole. **For us:** nothing to change — G12.1/G112 input stays refused; confirms the CAM-side approach.

## 8. "G112 Polar Interpolation Programming — Axial Square Milling" (vendor blog, text pasted by Marios 2026-10-12)
Codes: Haas `G112/G113`, Mitsubishi Meldas `G12.2/G13.2`, Fanuc `G12.1/G13.1`; cylindrical interpolation Fanuc
`G7.1`, Mitsubishi `G7.2`, Haas `G107`. Correct and useful: X becomes the radial, C a virtual linear axis; the
control never drives X negative — a "negative X" corner is reached as +X with C turned 180° (exactly our Index at
Pole / one-side rule); dry-run lifted first, then a shallow scratch cut on aluminium, document the setup.
**Partly confused:** calls a tool "axial" when perpendicular to Z and applies polar interpolation to flats "on the
side of a shaft" (that is cylindrical interpolation / Y axis; polar interpolation mills the END FACE); parameter
numbers and "Y-intercept cap" are unverified; feed mixes in/rev with linear feed. Nothing on the pole itself.
**For us:** found that `G12.2/G13.2`, `G7.1`, `G107` passed through → now refused (2.12.1). Also found: lathe
diameter mode **`G7` passes through** — on a `LATHE = 1` machine it would make LinuxCNC read our radius X as a
DIAMETER (part half size) → proposal F (refuse G7; maybe write G8 in the header).

## 9. FANUC manual excerpt — B-63524EN/01 (Series 0i/16i-T style lathe programming), §4.6 Polar coordinate
## interpolation G12.1/G13.1 (pages 58–60, text pasted by Marios 2026-10-12 as "APP2008-047")
The first PRIMARY source. In our words:
- G12.1 / G13.1 (= G112 / G113) in blocks of their own; reset/power-on → G13.1; linear and rotary axis set by
  parameters 5460 / 5461. G12.1 cancels the G17/G18/G19 plane, G13.1 restores it.
- In the mode, commands are Cartesian in the plane (linear axis, virtual axis named by the rotary address, both in
  mm/inch); the virtual axis is 0 right after G12.1, and the start angle is taken as 0 at the tool's position.
- **F is the tangential speed in that Cartesian plane (mm/min)** — what our G93 blocks give the CAM feed.
- Allowed in the mode: G01, G02/G03 (I/J for an X-based plane, or R), G04, G40–G42 (compensation applied before the
  polar transform), G65–G67, G98/G99. Not allowed: changing the coordinate system (G92, G52, G53, G54–G59); G12.1/G13.1
  only with G40 active; no program restart inside the mode. The work origin must be on the rotary centre first.
- Radius/diameter: "even when diameter programming is used for X, radius programming is applied to the rotary
  (virtual) axis"; and the first axis follows the rotary axis's setting → in G12.1 the coordinates are radius values.
  (So the §6 document's "X28 = 28 mm square" depends on that machine's parameters — not general.)
- **The pole (WARNING in the manual):** near the centre the C component of the feed grows and can exceed the max C
  cutting feed (parameter 1422) → alarm. Rule: **F < L × R × π / 180** (L = closest distance tool centre ↔ centre,
  mm; R = max C feed, deg/min); or keep the tool centre away from the centre. **Fanuc does not solve the pole — it
  limits F or forbids going near it.** Our converter goes through/near the pole (Signed-X, Index at Pole) and LinuxCNC
  slows each G93 block to the C limit instead of raising an alarm. The formula is the basis for the "pole governor"
  warning idea (STATUS, ideas).
- Nothing here about G16 (that is a different section) → proposal E still needs the G16 page of a Fanuc manual.
