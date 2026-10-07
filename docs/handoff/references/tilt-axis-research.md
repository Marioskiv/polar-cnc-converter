# Research — naming and handling the router tilt axis (XZC + tilt)

*2026-10-07. Asked by Marios: which letter must the new axis have so LinuxCNC understands it (A or B)? A layout
selector "XZC or XZC + A/B" must go into the converter. The axis is not built yet: the router stays fixed, so
**no `.ini`/`.hal` changes now — converter only.** Sources: LinuxCNC source + docs (master `46a388f`,
2026-10-07, sparse clone of `docs/src`, `configs/sim/axis/vismach`, `src/emc/kinematics`), web search.
forum.linuxcnc.org, forums.autodesk.com and autodesk.com are blocked in this sandbox (only search snippets).*

## 1. The letter: **B** (by the standard and by LinuxCNC's own examples)
- LinuxCNC docs, `docs/src/gcode/machining-center.adoc` ("Rotational Axes"): *"A rotates around a line parallel
  to X, B rotates around a line parallel to Y, and C rotates around a line parallel to Z."* Same as ISO 841 /
  RS274. Positive = counter-clockwise seen from the positive end of the axis (right-hand rule), "from the point
  of view of the workpiece".
- Marios's router tilts in the **X-Z plane** (from parallel-to-Z for the face to radial for the periphery) → it
  rotates about a line parallel to **Y** → **B**. **A** would be rotation about X = tilting **tangentially**
  (the tool leaning sideways, out of the plane through the chuck axis) — the variant DECISIONS.md avoids.
- LinuxCNC's own tilting-head example names the head axis B: `src/emc/kinematics/5axiskins.c` (XYZBC bridge mill,
  "B axis: polar angle wrt z axis"), and `xyzbc-trt-kins` (B = tilt about Y). Industry mill-turns with a milling
  head that swivels between axial and radial (Mazak Integrex, Okuma Multus, DMG CTX TC) call it the **B-axis**
  (Integrex i-150: B −10° … +190°; j-series: 220° in 5° steps — search results).
- **What LinuxCNC itself "understands":** with trivkins the letter carries **no geometry** — any of A/B/C is an
  `ANGULAR` axis in degrees, G93 works the same. So A would also run; B is what the standard, CAM posts and
  other people expect. The direction sign is NOT guaranteed by the letter: `5axiskins.c` note 10 says its own
  tilt axis runs *opposite* to the convention. ⇒ the converter needs an **invert B** option, proven by a test
  cut, like C.
- Sign check with our frame (X = radius outward, Z = axial, mill-style +Z away from the chuck, Y = Z × X):
  rotating the tool axis (+Z, tip→pivot) by +90° about +Y gives +X ⇒ **B +90 = tool tip pointing at the chuck
  axis from the outside** (periphery machining). Only a physical check proves it.

## 2. Joint numbering in LinuxCNC (when the axis is built — not now)
Canonical order X Y Z A B C: `coordinates=XZBC` → joints **X 0, Z 1, B 2, C 3**. C moves from joint 2 to 3
(`[JOINT_2]` → `[JOINT_3]`, HAL `joint.2` → `joint.3`, `halui.joint.2` …). Useful INI features for a B that only
goes to fixed positions: `[AXIS_B] LOCKING_INDEXER_JOINT` + `[JOINT_n] LOCKING_INDEXER = 1` (unlock → move →
lock pins), `docs/src/config/ini-config.adoc` ~l.1062, `ini-homing.adoc` ~l.346.

## 3. Tool length — the important consequence
- LinuxCNC's tilting-head kinematics add the tool length to the pivot length:
  `pivot_length` = mechanical pivot length **+ `motion.tooloffset.z`** (`5axiskins.c` notes 1, 5-axis docs
  "Tool-Length Compensation"). With **trivkins**, `G43 H` adds the tool length to **Z only** — right at B = 0,
  **wrong at B = 90** (the tool then sticks out along X).
- ⇒ In a tilted layout the converter must know **each tool's length** (pivot → tip = fixed pivot length + tool
  length) and compute X/Z itself.
- **Corrected 2026-10-07 (while building 2.7.0):** `G43` can stay. With the touch-off at B = 0, the machine
  X/Z mean "the tool tip when upright"; G43 only shifts Z by the tool length at every B alike, and the
  formula X = r + K sin B, Z = z + K (cos B − 1) (K = pivot → ball centre, which contains the tool length)
  is right with G43 active. Cancelling G43 is NOT needed.

## 4. Face vs periphery — industry names and inputs
- **Face, B = 0:** "polar coordinate interpolation" (Fanuc G12.1/G112, Siemens TRANSMIT) — what the converter does.
  Input: ordinary 3-axis XYZ G-code.
- **Periphery, B = 90:** "cylindrical interpolation" (Fanuc G7.1/G107, Siemens TRACYL): the pattern is
  programmed **unrolled** (U = arc length = θ·r, V = axial) and the control wraps it on a cylinder of given
  radius; X/C/Z move together. Two practical inputs for our converter:
  1. a mill **4th-axis program XYZA** (A about X, tool along Z, Y = 0): Fusion rotary/wrap toolpaths,
     **Kiri:Moto's lathe op** (`kirimoto.md` §5). Mapping: mill X → our Z (axial), mill Z (radius) → our X (+ pivot
     compensation), mill A → our C. Y ≠ 0 cannot be reached (no Y axis) → reject with the line number.
  2. an **unrolled 2-D program** (any CAM, flat) + cylinder radius, like G7.1. Same method as the GitHub project
     `SergioReyesSan/cnc_4th_axis_sim` (`551451a`, 2026-09-28; **no licence file → all rights reserved, method
     only**): U = θ·r, V → axial, Z = R₀ − depth, A continuous.
- Fusion mill-turn posts (search snippets): XZC "polar" logic exists in the generic mill-turn posts but is off by
  default; for B-head machines "when machining directions aren't axial or radial, TCP needs to be enabled" —
  i.e. arbitrary tilts need tool-centre-point handling (our pivot compensation).
- Feed: Fusion's LinuxCNC rotary output may already be **G93** — the converter rejects G93 input today; the
  periphery input would have to accept it (keep each block's time). Kiri's A output is G94 with the A angle
  ignored (wrong feed) → recompute from geometry.
- Without a Y axis, only tool orientations **in the radial plane** are possible (4 axes, not 5): any 5-axis path
  with a sideways (tangential) lean cannot run on this machine.

## 5. LinuxCNC classification
5-axis docs (`docs/src/motion/5-axis-kinematics.adoc`): "spindle tilting + table rotary" type (Fig. 10). LinuxCNC
has no stock kinematics for exactly X Z + tilting head + C table without Y; the agreed route stays **trivkins +
offline transform** (DECISIONS.md), i.e. the converter does the TCP / pivot compensation, like Fusion's
"IN_COMPUTER" mode.

## Sources (web)
- LinuxCNC docs: https://linuxcnc.org/docs/html/gcode/machining-center.html ·
  https://linuxcnc.org/docs/2.8/html/motion/5-axis-kinematics.html ·
  https://manpages.debian.org/unstable/linuxcnc-uspace/trivkins.9.en.html
- LinuxCNC forum (titles only, blocked): "B-axis setting in axis" (a CXZB lathe),
  "Add a rotary axis B on a lathe" (Fusion 360), "Developments on my Home built 5C CNC Lathe — Polar interp. and
  Live tooling".
- Mazak Integrex B-axis ranges: https://www.medicaldevicedirectory.com/company/555075/products/180509/mazak-integrex-i-150
- Cylindrical vs polar interpolation: https://industrialmonitordirect.com/blogs/knowledgebase/fanuc-g121-vs-g71-c-axis-3d-interpolation-compatibility ·
  https://kb.sprutcam.com/SC15manual/en/10082.html
- ISO 841 / right-hand rule: https://bobcad.com/components/webhelp/BCC/Content/Merge/CAM/Undertanding_RightHandRule.htm
- 4th-axis unroll simulator: https://github.com/SergioReyesSan/cnc_4th_axis_sim
