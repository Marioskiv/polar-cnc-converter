# Chuck jaws: stepped jaws, gripping inside and outside — research (2026-10-21)

Status: **proposal, waiting for Marios's yes and his measurements**. Nothing built yet.

## What he asked
"With this drawing you can draw the chuck's jaws correctly, to represent the real grip: I may need to hold something
from the inside, and from the outside of course." He sent the SAN OU scroll-chuck catalogue page (drawing + two
tables; the image itself is the maker's, not stored here — only the numbers below).

## What the addon does today (checked in `freecad/polarcnc/chuck.py`, 2.24.0)
- Each jaw is **one solid block** of height K over its whole radial length (steps ignored): never smaller than the
  real jaw, so the checks are on the safe side, but not exact.
- **Outside gripping only**: `contact_radius` puts each jaw where a ray from the axis LEAVES the stock.
- `GRIP_RANGES` knows only A (normal jaws, outside) and C (reversed jaws, outside) for the K11-125 / K12-125:
  (2.5, 40, 38, 110). **B (normal jaws gripping INSIDE a bore, "jamming range") is missing.**

## SAN OU catalogue numbers (from the page he sent)
Body (mm): D chuck diameter, D1 / D2 mounting / bolt circle, D3 through bore, H body thickness, h spigot, z-d bolts.

| D | D1 | D2 | D3 | H | h | z-d |
|---|---|---|---|---|---|---|
| 80 | 55 | 66 | 16 | 50 | 3.5 | 3-M6 |
| 100 | 72 | 84 | 22 | 55 | 3.5 | 3-M8 |
| 125 | 95 | 108 | 30 | 58 | 4 | 3-M8 |
| 130 | 100 | 115 | 30 | 60 | 3.5 | 3-M8 |
| 160 | 130 | 142 | 40 | 65 | 5 | 3-M8 |
| 200 | 165 | 180 | 65 | 109 | 5 | 3-M10 |

Clamping ranges, stock diameter (mm):

| D | A–A1 normal jaws, outside | B–B1 normal jaws, inside a bore | C–C1 reversed jaws, outside |
|---|---|---|---|
| 80 | 2–22 | 25–70 | 22–63 |
| 100 | 2–30 | 30–90 | 30–80 |
| 125 | 2.5–40 | 38–125 | 38–110 |
| 130 | 3–40 | 40–130 | 40–120 |
| 160 | 3–55 | 50–160 | 55–145 |
| 200 | 4–85 | 65–200 | 65–200 |

**Not in the catalogue: the step sizes of the jaws** (3 steps). They must be measured, not guessed (rule: no
assumed hardware sizes). Already measured on his K11-125: jaw height 25.5, length 53, width 16 (K72-125 4-jaw:
21.7 / 56 / 18).

## Proposal (put to Marios 2026-10-21)
1. Chuck property **Grip mode**: outside with normal jaws (A) / inside a bore with normal jaws (B, jaws expand) /
   outside with reversed jaws (C).
2. **Stepped jaws**: 3 steps (height above the chuck face and radial depth of each), so the model knows which step
   holds the part and how high the jaw stands there; normal and reversed (reversed = the same jaw turned round).
3. **Inside grip**: find the part's bore, put the jaws inside it touching the bore wall from inside (the ray from the
   axis that first MEETS the material), and check the cutter never goes down onto the jaws in the bore (e.g. facing
   across the centre of a part held in its bore — his pulley test of 2026-10-15 was held this way).
4. All six catalogue sizes as presets (body H, bore D3, ranges A/B/C) + a warning when the part is outside the
   range of the chosen grip mode.

## Needed from Marios before building
- His yes.
- On ONE jaw of his K11-125 (calliper): for each of the 3 steps, its height above the chuck face and its radial
  depth; a side photo with the calliper helps. Same for the K72-125 if he uses its steps.
