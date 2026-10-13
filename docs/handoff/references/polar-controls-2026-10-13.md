# How professional controls and CAM posts do polar (face) machining — study 2026-10-13

- **Asked by Marios (2026-10-13):** "use as many features of existing polar machines as possible so the converter is
  correct — find how they handle it and write the code". Three parallel web studies; no file was copied.
- **Limits:** vendor PDFs (Siemens, Fanuc, Heidenhain, manualslib) could not be downloaded here (proxy/DNS); those
  facts come from search excerpts of the vendor documents and are tagged [DOC] (vendor excerpt), [SEC]/[FORUM]
  (third party), [INF] (inference), [MEM]/[RECALL] (memory, not re-checked). Autodesk posts and the Mastercam post
  were read in full from public copies (licence: "All rights reserved" / proprietary → **method only**).
- **Outcome:** the converter already matched them (pole crossing both ways = Siemens POLE_SIDE_FIX 0 and 1/2,
  shortest turn at the pole, C-only arcs about the axis, G93 F every block, direction in the machine config, refuse
  what is not certain, rapids along the Cartesian line). Built from it: **2.13.0 C report** (C range / ±99,999°
  warning; C speed the CAM feed needs, as Fanuc AFC / Siemens slow down there). Not built: one-direction C approach
  for holes (Marios: C has no measurable backlash), retracts at C limits and centre-height compensation (rejected
  in DECISIONS), spiral rapids (less safe), cutter compensation in the control (CAM does it).
- To confirm details later (if Marios uploads them to `Marioskiv/cnc-manuals`): Siemens 840D sl "Transformations"
  Function Manual (A5E47435470B); Fanuc 0i-TF lathe operator's manual B-64604EN + parameter manual (AFC 5450/5463).

The three study notes follow unchanged (each lists its sources).

---

## How professional controls handle polar (face / TRANSMIT) transformation, research 2026-10-13

## Access limits (read first)
- Direct download of the vendor PDFs was **blocked** in this session. The egress proxy refused
  cache.industry.siemens.com, support.industry.siemens.com, content.heidenhain.de, manualslib.com and
  scribd.com, and WebFetch failed DNS for every host.
- Everything below therefore comes from **web-search excerpts** of the primary documents: short quoted
  sentences or paraphrases returned by the search engine. Excerpts carry the document and section names.
  Page numbers are given only where the excerpt showed them.
- Tags used below:
  - **[DOC]**: stated in a vendor-document excerpt.
  - **[FORUM]**: third-party source.
  - **[INF]**: my own inference.
  - **[MEM]**: background I remember but could not re-verify here. Treat [MEM] as unverified.
- To confirm details, read the PDFs themselves. The most valuable ones are listed at the end.

---------------------------------------------------------------------------------------------------
## 1. Siemens SINUMERIK 840D sl / 828D / 808D: TRANSMIT (function M1 "Kinematic transformation")

Primary sources (seen through excerpts):
- S1: *SINUMERIK 840D sl Transformations, Function Manual* 06/2019 (A5E47435470B AA), chapter TRANSMIT.
  - https://cache.industry.siemens.com/dl/files/453/109767453/att_991396/v1/840Dsl_transformations_fct_man_0619_en-US.pdf
  - Newer editions: 10/2020 (109783237), 07/2021 (109801200); SINUMERIK MC 07/2021 (109801269);
    SINUMERIK ONE 07/2024 (109973970).
- S2: *SINUMERIK 808D / 808D ADVANCED Function Manual*, chapter 12 "Kinematic Transformation (M1)",
  "Special features of TRANSMIT and TRACYL" (manualslib page 135).
  https://cache.industry.siemens.com/dl/files/572/109748572/att_923598/v1/808D_808D_ADV_fct_man_0617_en-US.pdf
- S3: Siemens alarm/diagnostics manuals (802D sl, 828D, 840D sl) for alarms 21617 / 21618 / 21619.
  Quoted via helmancnc.com and silo.tips copies.

### 1.1 Activation and machine data
- **[DOC S1]** Transformation types and data sets:
  - TRAFO_TYPE **256** = TRANSMIT with one rotary axis + one linear axis.
  - TRAFO_TYPE **257** = TRANSMIT with one rotary axis + two linear axes.
  - At most two TRANSMIT data sets per channel. Machine data come in pairs, `_1` for the first and `_2` for the
    second TRANSMIT (MD249xx / MD249(5)x).
- **[DOC S1]** Machine data named in the excerpts:
  - `$MC_TRANSMIT_ROT_AX_OFFSET_t`: angle between the rotary axis zero and the zero of the transformation's
    Cartesian frame.
  - `$MC_TRANSMIT_ROT_SIGN_IS_PLUS_t` (MD24910): the rotary axis counts as positive if, looking along −Z
    (down the Z axis), it turns **counter-clockwise** in the X/Y plane when it moves positive. This is the same
    right-hand-rule convention as our converter.
  - `$MC_TRANSMIT_BASE_TOOL_t` (MD24920, index 0..2 = X/Y/Z): the vector of the tool zero point relative to the
    origin of the TRANSMIT Cartesian frame. It describes a tool that does not sit on the centre line.
  - `$MC_TRANSMIT_POLE_SIDE_FIX_t` (MD24911 / MD24951): how the pole is traversed (see 1.2).
  - `$MC_TRAFO_INCLUDES_TOOL_n`: whether the transformation handles the tool offset.
  - `$MC_TRAFO_AXES_IN_n`: which channel axes the transformation uses. I saw only the name.
- **[DOC S1, 2020+]** Newer software can define TRANSMIT through **kinematic chains** and system variables:
  - `$NT_ROT_AX_NAME[n,1]`: exactly one rotary (polar) axis.
  - `$NT_ROT_AX_OFFSET`: −1 means "not evaluated".
  - `$NT_POLE_SIDE_FIX`, `$NT_POLE_TOL`, `$NT_CORR_ELEM_P` / `$NT_CORR_ELEM_T`.
  - `$NT_POLE_TOL` (a tolerance radius around the pole) was seen only as a heading. Its exact semantics were
    not visible. **To check.**
- **[DOC S1]** The rotary axis **does not need to be a modulo axis** for TRANSMIT.
- **[DOC S2]** Selecting TRANSMIT does three things:
  - it deselects an active working-area limit for the axes involved (WALIMOF);
  - it interrupts continuous-path mode / rounding;
  - it requires tool radius compensation to be off (G40) at the moment of selection.

### 1.2 The pole: definition, crossing methods, POLE_SIDE_FIX
- **[DOC S1]** The pole is the point where the radial linear axis crosses the rotary-axis centre, i.e. the zero of
  the TRANSMIT plane. Near it, small Cartesian changes cause large rotary-axis motion.
- **[DOC S1]** A pole exists for a path when the line of the tool centre point passes through the turning centre.
- **[DOC S1]** "A tool center point path through the pole does not cause the part program to be aborted.
  There are no restrictions with respect to programmable traversing commands or active tool radius compensations."
  - The manual still advises against machining close to the pole, because of the sharp feed reductions it can
    force (see 1.3).
  - The manual's exceptions are linear motions **into** or **through** the pole. These get the special pole
    handling below.
- **[DOC S1]** There are two ways to traverse the pole, selected by **MD24911 `TRANSMIT_POLE_SIDE_FIX_1`**
  (MD24951 `_2` for the second TRANSMIT):

  | Value | Name | What the TCP path does |
  |---|---|---|
  | **0** | pole crossing | The tool-centre path, in the linear axis, crosses the pole on one continuous path: the linear axis goes through zero to the other sign while the rotary axis stays put. |
  | **1** | rotation around the pole, positive side | The path is restricted to the **positive** traversing range of the linear axis (in front of the turning centre). The tool runs into the pole, the rotary axis turns there, the tool runs out. |
  | **2** | rotation around the pole, negative side | As 1, but on the **negative** range (behind the turning centre). |

  - Value 0 is our Signed-X. Values 1 and 2 are our Index at Pole.
- **[DOC S1]** Pole traversal along the linear axis is available in AUTOMATIC **and JOG** modes.
  - **[INF]** One excerpt said a JOG traversal of the pole runs "at creep speed". I did not see that sentence in
    context, so treat it as unconfirmed.
- **[DOC S1, excerpt]** "The control system inserts a traversing block at the step change point. This block
  generates the smallest possible rotation to allow processing of the contour to continue."
  - **[INF]** Context not visible. It most likely belongs to pole traversal by rotation: where the polar angle
    jumps at the pole (incoming and outgoing directions differ), the NC inserts a pure rotation block at the pole
    and takes the **shorter** direction.
- **[DOC S1]** Some controls can traverse the axes without evaluating MD24911 (the excerpt says the control
  "traverses the axes participating in the transformation without evaluating MD24911"). The context is probably
  JOG or the case where the transformation is deselected. Unconfirmed.

### 1.3 Feed near the pole (automatic slow-down)
- **[DOC S1]** When the TCP path passes near or through the pole, the control **automatically reduces the
  feedrate and the path acceleration** so that the machine-axis limits MD32000 (MAX_AX_VELO) and MD32300
  (MAX_AX_ACCEL) are not exceeded. The reduction is stronger the closer the path is to the pole.
  - There is no separate TRANSMIT velocity parameter in the excerpts. The normal axis limits plus look-ahead do
    the job.
- **[DOC S2, 808D]** Machining close to the pole is "not recommended since these may require sharp feedrate
  reductions to prevent overloading of the rotary axis". The 808D TRACYL text says the TCP path should not go
  through the X0/Y0 pole.
- **[INF]** On LinuxCNC this is equivalent to our G93 + `[AXIS_C] MAX_VELOCITY` / `MAX_ACCELERATION`. The trajectory
  planner slows each G93 block whose C speed would exceed the limit. What Siemens has and LinuxCNC does not have
  is look-ahead that accounts for the coupled X/C path through a transformation.

### 1.4 Working-area limitation (tool off-centre)
- **[DOC S1]** If the tool centre point **cannot** be positioned at the turning centre (an offset tool, e.g. a
  Y offset via TRANSMIT_BASE_TOOL), the pole is replaced by a **working-area limitation**:
  - the distance between the axes defines a **cylinder** around the rotary axis that the tool cannot enter;
  - $MC_TRANSMIT_POLE_SIDE_FIX also fixes whether that limitation applies in front of or behind the pole;
  - any motion that would enter the unreachable cylinder is **rejected with alarm 21619**.
- **[INF]** Type 257 (a second, "real" linear axis, e.g. Y) is what lets the control compensate such an offset.
  I did not see the 257 Y-compensation text itself. **To check in S1.**

### 1.5 Rotary-axis position, turns and direction
- **[DOC S1 §2.1.1.5, title only]** "Monitoring of rotary axis rotations over 360°". The excerpt says the rotary
  axis positions are **ambiguous with respect to the number of rotations**, so the control monitors them.
  - The method itself was not visible.
  - **[MEM]** As I remember it, the transformation keeps the rotary axis continuous: it chooses the solution
    closest to the current position and does not wrap. That matches our cumulative C.
- **[DOC S1]** Direction convention: `TRANSMIT_ROT_SIGN_IS_PLUS` (see 1.1).
  - **[FORUM, industrialmonitordirect]** reports that on an 840C a wrong direction was fixed with this MD,
    not by changing the program.
- **[DOC, alarm text S3]** Alarm 21619 can also come from selecting TRANSMIT at an unsuitable position, e.g.
  **selection in the pole**. The documented remedy is to move slightly off the pole before selection.
  - **[INF]** At r = 0 the angle is undefined, so the NC refuses to start the transformation there.
  - Our equivalent is the first move from the pole: we spin C to the line direction first.

### 1.6 Alarms (S3 excerpts)
- **21617** "transformation does not allow to traverse the pole": the programmed path goes through the pole or
  through a forbidden area. A RESET is not enough while the transformation stays active; the transformation
  must be deselected.
- **21618** "transformation active: overlaid motion too great": the transformation monitors superimposed motion,
  e.g. handwheel or DRF.
- **21619** "transformation active: motion not possible": the machine kinematics do not allow the motion, e.g.
  the tool cannot reach the pole (offset), or selection happened in the pole.

### 1.7 Rapid traverse inside TRANSMIT
- **[DOC, PG 840D/810D 03.04 (Chinese edition)]** G0 runs either as RTLION (linear interpolation of the path
  axes) or RTLIOF (each axis on its own, non-linear).
- **[MEM / not verified]** With an active transformation, Siemens interpolates G0 **as a Cartesian path**
  (RTLION behaviour), even if RTLIOF is programmed. A rapid inside TRANSMIT is therefore a straight Cartesian
  line, the same thing our segmented rapids reproduce.
- I could not find this stated in a TRANSMIT excerpt. **To check in S1 / the Fundamentals PG ("G0 with
  transformation").**

---------------------------------------------------------------------------------------------------
## 2. HEIDENHAIN

### 2.1 TNC 640 / TNC 620 / TNC7: `FUNCTION POLARKIN` (machining with polar kinematics)
Sources: *TNC 640 User's Manual Klartext Programming*, NC SW 34059x-11 (892903-29) and 34059x-16 (892903-2A),
section "Machining with polar kinematics" / "Activating FUNCTION POLARKIN" (excerpt says p. 379 in one edition).
Also *TNC 640 Setup, Testing and Running* 1261174-22, and the TNC7 81762x-17 manual (1358773-21).
- https://content.heidenhain.de/doku/tnc_guide/pdf_files/TNC640/34059x-16/bhb/892903-2A.pdf
- **[DOC]** POLARKIN switches on a polar kinematic model. The control makes the motion with **one rotary axis and
  two linear axes**. In the function the user defines:
  - **the positioning behaviour of the rotary axis**;
  - **whether machining is allowed at the centre of rotation** of the rotary axis.
- **[DOC]** A status icon shows while POLARKIN or PARAXMODE is active. FUNCTION POLARKIN has its own
  deactivation.
- **[FORUM, LinkedIn by a Heidenhain applications engineer]** Needs NC software 11 (34059x-11). The typical use
  is a rotary table's C axis replacing a missing Y stroke.
- **[MEM / not verified]** The syntax is roughly
  `FUNCTION POLARKIN AXES <lin> <lin> <rot> MODE: <...> POLE: <ALLOWED|SKIPPED>`.
  - MODE (e.g. `+POS`, `-POS`, `+NEG`, `-NEG`, `KEEP`) fixes **on which side of the centre the linear axis
    stays** and the **preferred rotary direction**.
  - POLE decides whether a path may pass the centre, or whether the control skips or refuses the pole.
  - Searches for these keywords returned nothing, so this needs the Klartext manual, which I could not download.
- **[INF]** If the memory is right, POLARKIN's MODE equals Siemens POLE_SIDE_FIX 0/1/2 plus a direction
  preference. That preference would be new for us.

### 2.2 iTNC 530
- **[DOC, search]** I found only ordinary polar coordinates (pole CC, PR/PA programming), i.e. polar **input**,
  not a kinematic transformation. No polar-kinematics function was found for the iTNC 530.

### 2.3 MANUALplus 620 / CNC PILOT 620/640 (lathe controls)
Source: *MANUALplus 620, CNC PILOT 620/640 User's Manual* (1118606-20):
https://content.heidenhain.de/doku/dp_mp620/pdf/smart/68894x-03/1118606-20.pdf
- **[DOC]** It has separate "Rapid traverse on front/rear face", "Linear path on front/rear face" and "Circular arc
  on front/rear face" G functions (G100/G101/G102/G103 family).
- **[DOC]** Positions on the front/rear face are entered **either Cartesian (XK, YK) or polar (X diameter, C)**.
- **[DOC]** Related functions: G152 (C-axis zero-point shift) and G153 (normalising the C axis).
- **[INF]** G153 normalising probably resets the accumulated C turns to the 0..360 range.
- Pole handling details were not visible in the excerpts.

---------------------------------------------------------------------------------------------------
## 3. Other controls

### 3.1 FANUC G12.1 / G13.1 (= G112 / G113)
Sources: B-63524EN §4.6 and B-63534EN §4.8 (already in `references/fanuc-b63534en.md`); *Series 0i-A Parameter
Manual*, cncmanuals.com; *0i-TF Operator's Manual* (Scribd); *0i-F lathe B-64604EN-1/01*
(vmclathe.com mirror); GSK 988TA manual p.67 (same scheme).
- **[DOC]** Feed near the centre:
  - The C component of the feed grows near the centre and can exceed the C maximum cutting feed.
  - The rule is **F < L·R·π/180** (L = closest distance of the tool centre to the centre, R = max C feed in deg/min).
- **[DOC, Parameter manual 0i-A] Parameter 5450 bit AFC.** In polar coordinate interpolation the control
  performs "**automatic override operation and automatic feedrate clamp operation**" when AFC = 1:
  - near the centre the NC itself lowers the programmed feed so C stays within its limit, instead of raising an
    alarm;
  - **parameter 5463** sets the allowable percentage (0..100) of the C limit used for that automatic override.
- **[DOC]** Parameter 5450 bit PLS enables the **polar-coordinate-interpolation shift**: the work origin need
  not be on the rotary centre and the program can be shifted.
- **[DOC]** 5460 / 5461 set the linear and rotary axis. Alarm 145 means illegal conditions (e.g. wrong
  5460/5461, or G12.1 without G40).
- **[DOC]** At G12.1 the virtual axis is 0 at the current tool position (angle 0 = current C). G41/G42 are
  allowed inside G12.1. G0 is not allowed inside (see project notes / README).

### 3.2 Haas G112 / G113 (lathe)
Source: Haas G-code reference https://www.haascnc.com/service/codes-settings.type=gcode.machine=lathe.value=G112.html
- **[DOC]** XY programming is converted to XC moves:
  - G17 is used for the plane;
  - G01 makes straight XY strokes, G02/G03 make arcs;
  - the C axis must be in C-axis mode.
- **[FORUM, eMastercam]** "Milling through the part centre with a linear move requires the geometry to be
  broken at the centreline".
  - **[INF]** Haas apparently does not handle a crossing inside one block, so CAM posts split the line at the
    centre.
- **[FORUM]** "EXCESSIVE AXIS SPEED OR ACCELERATION" alarms happen right after G112 when the first move is
  awkward. The workaround reported is a straight lead-in.

### 3.3 Beckhoff / ISG TwinCAT CNC (TF5200): `#FACE[X, C]` / `#FACE OFF`
Sources: infosys.beckhoff.com
- TF5200 programming manual "Face machining (#FACE, #FACE OFF)":
  https://infosys.beckhoff.com/content/1033/tf5200_programming_manual/208128523.html
- channel parameter P-CHAN-00008:
  https://infosys.beckhoff.com/content/1033/tf5200_channel_parameter/149146635.html
- turning functions "Kinematics":
  https://infosys.beckhoff.com/content/1033/tf5200_turning_functions/400210955.html

Findings:
- **[DOC]** `#CAX[S,C]` turns the spindle into a rotary path axis. `#FACE[X,C]` then programs the face in a
  virtual Cartesian X/Y. G18/G19 are not allowed while it is active.
- **[DOC]** **P-CHAN-00008** selects the machine type for C-axis face machining:
  - **1 = lathe**: "automatic orientation of the rotary axis in the centre of rotation", called
    "**180° alignment / orientation**" in older pages; kinematic ID 13;
  - **2 = milling machine**: no orientation; kinematic ID 14.
- **[INF]** Type 1 means that when the path passes the centre, the CNC turns C by 180° so the linear axis stays
  on its side, like Siemens POLE_SIDE_FIX 1/2. Type 2 lets the linear axis go to the other side, like Siemens 0.
- **[DOC]** A C angular offset in the kinematic parameters (trafo[0].param[1], unit 10⁻⁴°) sets the C zero
  relative to the transformation frame.
- **[DOC, TF5240 kinematic manual, general]** Near singular positions large dynamic loads occur. When leaving a
  singularity the controller chooses the angular solution with the **shortest path**.

### 3.4 Okuma OSP (G137 / G136)
- **[FORUM / G-code lists only]** G137 starts "coordinate conversion" (polar / Y-axis mode), G136 ends it.
  The official text is in the OSP programming manuals, section "Coordinate System Conversion"; no access.
  Nothing on pole handling.

### 3.5 Mazak (EIA G12.1/G13.1), Mitsubishi M70/M700/M800 (G12.1 = G112, G13.1)
- **[FORUM / lists only]** Same Fanuc-style scheme.
  - A Mazak 550MY user reported that X travels far below the centre line in polar mode (i.e. the linear axis
    may be driven to the "other side").
  - No primary text on pole or feed behaviour was found.

### 3.6 Fagor 8065
- No primary text found. The public manual index mentions a C-axis option. G30/G31 are only polar **origin**
  for input.

### 3.7 Autodesk Fusion post engine (CAM side, "IN_COMPUTER")
Source: https://cam.autodesk.com/posts/reference/classPostProcessor.html
- **[DOC]** `activatePolarMode(tolerance, currentAngle, polarDirection, interpolateRapidMoves, optimizeType)`
  returns a VectorPair. Related: `deactivatePolarMode()`, `Section.polarMode` / `Section.polarDirection`.
- **[INF from the signature]** The CAM-side transform takes:
  - a **chord tolerance**;
  - the **current C angle**, to keep C continuous;
  - a **preferred polar direction**, i.e. which half-plane / side of the centre the linear axis works on;
  - a flag **whether rapids are interpolated (segmented) too**;
  - an **optimisation type for C** (shortest / keep direction).
- Posts expose manual NC commands `usePolarMode` / `useXZCMode`.

---------------------------------------------------------------------------------------------------
## 4. Features these controls have that the converter might lack

1. **Automatic feed reduction at the pole done by the NC with look-ahead**
   - Siemens TRANSMIT: feed and path acceleration are reduced against MD32000/MD32300. Fanuc AFC: automatic
     override and clamp, with 5463 as % of the C limit.
   - On LinuxCNC + G93 the TP clamps each block to the joint limits. **[INF]** Our blocks near the pole are
     short, and G93 asks for the CAM feed, so LinuxCNC already slows them. It does not *plan* the deceleration
     across the coupled path the way Siemens does.
   - Possible converter feature (not a motion change, in line with DECISIONS): a **pole-governor report**, i.e.
     a warning/listing of blocks where F > L·ω_C. This is the idea already noted in STATUS.
2. **A user choice of which side of the centre the linear axis may use (`POLE_SIDE_FIX` 0/1/2, Beckhoff
   P-CHAN-00008, POLARKIN MODE, Fusion `polarDirection`)**
   - The converter has "Cutting side: one side / both sides".
   - **Missing:** Siemens 2 / POLARKIN `-POS`-style, i.e. *only the negative side*. Our X Axis Min/Max model
     covers it only if the user enters negative limits. **[INF]** Check that a negative-only travel works.
3. **A preferred rotary direction / shortest-rotation rule at the pole**
   - Siemens inserts the *smallest possible rotation* block at a step change; Beckhoff leaves a singularity by
     the *shortest path*; POLARKIN MODE has (from memory) a direction preference; Fusion has `optimizeType`.
   - **Check:** does Index at Pole always spin the shorter way (≤ 180°)? An option "always + / always −" could
     matter for cables or a non-homing C.
4. **Monitoring of accumulated rotary turns**
   - Siemens §2.1.1.5 monitors C turns beyond 360°. Heidenhain MANUALplus G153 normalises C.
   - Our C is cumulative, and the machine soft limit is ±99,999° (≈ 277 turns, see STATUS).
   - Possible features: a **report of total C travel / max |C|** checked against a C limit, or an optional
     unwind or reset (G92-free, e.g. `G0 C<mod 360>` only while retracted) at tool changes or program end.
5. **An unreachable cylinder for an off-centre tool (TRANSMIT_BASE_TOOL / type 257 with Y; alarm 21619)**
   - If the cutter is not on the chuck axis (Y offset e), Siemens computes the true polar transform with the
     offset and refuses points with r < e.
   - Marios decided "no centre-height compensation" (DECISIONS). **Do not propose again**; listed only for
     completeness.
6. **Refusal to start the transformation at the pole (21619 "selection in the pole")**
   - We handle this by spinning C at r = 0 to the line's direction, which is already better.
7. **No cutter compensation through the pole issue**
   - Siemens allows G41/G42 inside TRANSMIT, and Fanuc allows them inside G12.1. Compensation is done in the
     virtual Cartesian plane before the polar transform.
   - We refuse G41/G42; the CAM must output a compensated path ("in computer"). **[INF]** This could be added
     only if a CAM ever cannot compensate. Low priority.
8. **G0 as a Cartesian straight line inside the transformation**
   - **[MEM]** Siemens does this (RTLION behaviour under a transformation). Fanuc/Haas forbid G0 inside the
     mode.
   - We already segment rapids, so nothing is missing. Fusion has the same switch (`interpolateRapidMoves`).
9. **Work origin not on the rotary centre (Fanuc 5450 PLS "polar interpolation shift"; Siemens
   TRANSMIT_ROT_AX_OFFSET, Beckhoff C angular offset)**
   - These set the C zero relative to the frame. We assume the work origin = chuck centre, with C zero = the
     CAM +X direction.
   - **[INF]** An optional "C angle offset" (rotate the part in C) would be the equivalent of
     ROT_AX_OFFSET. Today it can be done in the CAM or with a G54 C offset on LinuxCNC. Probably not needed.
10. **The rotary-direction sign as a machine setting (`TRANSMIT_ROT_SIGN_IS_PLUS`)**
    - This is exactly the policy already decided: fix the sign in the machine config (C `STEP_SCALE` sign), not
      the program. Siemens confirms the approach. Nothing to add.

### To verify by reading the PDFs (could not download here)
- S1 (840D sl Transformations 06/2019 or later), TRANSMIT chapter:
  - pole traversal figures and the exact rule for MD24911 = 1/2;
  - the "inserted traversing block / smallest rotation" context;
  - §2.1.1.5 monitoring of turns;
  - `$NT_POLE_TOL`;
  - type 257 Y compensation;
  - G0 under transformation.
- TNC 640 Klartext 892903-2A, "Machining with polar kinematics": exact POLARKIN MODE / POLE keywords.
- Fanuc 0i-F parameter manual, 5450 AFC and 5463: exact override algorithm.

---

## Polar (face) interpolation on real lathe controls: research 2026-10-13

## How this was gathered (read first)
- In this session, page fetching (WebFetch, curl) failed for every host (DNS or proxy 403). The only working tool
  was the web search engine, which returns short extracts of the pages it finds. Every fact below comes from those
  extracts of the cited URL. I could not open a PDF page to check page numbers myself.
- Confidence labels:
  - **[DOC]**: an extract of an official manual or vendor page (Fanuc, Mitsubishi, Siemens, Haas).
  - **[SEC]**: a third-party guide, or forum text that quotes a manual.
  - **[FORUM]**: a user report.
  - **[INF]**: my own inference. **[RECALL]**: from memory and not verified this session; check it before relying on it.
- Already covered by `references/fanuc-b63534en.md` and skipped here unless something is added: G12.1 angle 0 =
  tool position at G12.1, F < L·R·π/180, no stroke check, G16.

## 1. Fanuc lathe series (0i-TA … 0i-TF, 16i/18i-TB, 30i) — G12.1/G13.1 (G112/G113 in G-code system A)
| Topic | Fact | Label / source |
|---|---|---|
| Axis setup | Linear and rotary axis for polar interpolation are set in parameters **5460** (linear, e.g. 1 = X) and **5461** (rotary, e.g. 3 = C). A wrong value gives alarm **145** "illegal conditions in polar coordinate interpolation". | [DOC] 0i-TF/0i-F lathe operator's manual B-64604EN (https://www.vmclathe.com/wp-content/uploads/2024/06/Fanuc-controller-%E5%8F%91%E9%82%A3%E7%A7%91%E8%8B%B1%E6%96%87.pdf); [SEC] https://www.helmancnc.com/fanuc-alarm-145-illegal-conditions-in-polar-coordinate-interpolation/ ; [FORUM] https://en.cncarena.com/forum/thread/189836-help/ |
| Origin | Before G12.1, a local or work coordinate system must be set whose origin is the centre of the rotary axis. | [SEC] quoting the manual: https://www.allaboutcncs.com/fanuc-cnc-lathe-g12-1-and-g13-1-codes-polar-coordinate-interpolation/ |
| Feed | F = tangential speed in the Cartesian polar-interpolation plane. | [DOC] B-64604EN (same URL) |
| **Automatic override / clamp (pole governor)** | Parameter **5450 bit AFC**: 0 = not performed, 1 = automatic override and automatic feedrate clamp are performed in polar mode. Parameter **5463** (byte, %, 0-100) = "allowable percentage" used to find the allowable feedrate of the rotation axis. The rotary limit is the axis's maximum cutting feedrate (parameter **1422**). Without AFC, the C feed rises near the centre and can exceed 1422 (alarm / servo error). | [DOC] Series 0i-Model A parameter manual B-63510EN, extract via http://www.cncmanuals.com/fanuc/202/series-0i-model-a-parameter-manual ; [FORUM] https://www.cnczone.com/forums/fanuc/142129-c-axis-post-help.html |
| AFC behaviour in detail | When the C speed needed for the commanded F exceeds (max cutting feed of C × 5463 %), the control automatically lowers F so that C stays at that speed. Even closer to the centre, where override alone cannot hold the limit, the feed is clamped. | [RECALL] the 0i/16i manual section "Automatic override and automatic feedrate clamp"; parameter names confirmed [DOC], the exact algorithm is not |
| **Coordinate shift (centre not at work origin)** | Parameter **5450 bit 2 PLS**: in polar mode the work coordinate system can be shifted. Program `G12.1 X_ C_`, where X and C give the position of the rotary-axis centre in the X-C plane relative to the work origin. | [SEC] https://en.cncforum.net/t/g12-1-code-polar-coordinate-interpolation/77 (quotes the Fanuc text); an older 2006 guide says "the origin X0 C0 must not be shifted", i.e. before this option: https://www.scribd.com/document/423908381/G12-1 |
| **Hypothetical-axis compensation (tool off the X line)** | The manual has a section "Compensation in the direction of the hypothetical axis in polar coordinate interpolation" (§6.4 in the guide's table of contents), meant for a tool centre that lies off the line through the rotary centre (a misalignment in the Y direction). I found the heading only, not the body. | [SEC] TOC extract via https://www.scribd.com/document/744611326/Fanuc-0i-TF-Operator-Manual-Trang-1 ; [RECALL] a parameter holds the offset amount and the control corrects the X/C conversion for it, number probably 5464 (unconfirmed) |
| Mode rules | G12.1 and G13.1 go in separate blocks. G13.1 restores the plane that was active before G12.1. The plane cannot be changed in polar mode. | [DOC] B-64604EN; [SEC] allaboutcncs |
| Tool nose / cutter radius compensation | Allowed. "Polar coordinate interpolation is performed for a path obtained after tool radius compensation". G40 must be active when G12.1 or G13.1 is commanded; G41/G42 come after G12.1; G40 again before G13.1. The X offset represents the cutter centre (tip quadrant 9); size is controlled with the radius offset, not the X offset. | [DOC] B-64604EN; [SEC] https://www.scribd.com/document/423908381/G12-1 |
| Rapids | **G00 is not allowed** in G12.1 mode. Positioning uses G01 with a moderate F. Rapid to the start point before G12.1. | [SEC] Zweifel G12.1 guide (scribd 423908381); [FORUM] cncarena 189836, practicalmachinist g112-breakdown |
| Z | X-Z or C-Z interpolation is not allowed in G12.1. Z moves are separate blocks with no X or C. | [SEC] scribd 423908381 |
| Near the centre | "Feed rate must be reduced in case when circular interpolation is done near the X-C zero point. Velocity of the rotary axis may become excessive …servo errors or servo overload". Fanuc itself notes that profile accuracy is limited. | [SEC] scribd 423908381; [FORUM] industryarena 78279 |
| Passing the centre | Not found in a manual extract. One guide says that with a negative X command "the cutter centre will not travel past X0" (a convention of that guide). | [SEC] scribd 423908381. [INF] Fanuc relies on the operator plus AFC; no documented pole-flip strategy was found |
| C start / rollover | Angle 0 = C position at G12.1 (already in B-63534EN). Practice: orient or reference C to C0 before G12.1, and reference C again after tool changes. | [SEC] allaboutcncs / industryarena 142129 |
| Arcs | G02/G03 in the polar plane with R, or I (linear axis) and J (hypothetical axis) (already in B-63534EN). | — |
| Option | Polar interpolation is a paid option on some models. | [FORUM] |

## 2. Haas lathe — G112 / G113 (Group 04)
| Topic | Fact | Label / source |
|---|---|---|
| Function | "Lets you program subsequent blocks in Cartesian XY coordinates, which the control automatically converts to polar XC coordinates." While active, G17 XY is used for G01 lines and G02/G03 arcs. X/Y become C rotation and linear X. G113 cancels. | [DOC] https://www.haascnc.com/service/codes-settings.type=gcode.machine=lathe.value=G112.html and …value=G113.html |
| Units / axis | Haas mode: X in **radius**, with a Y word for the virtual Y. Fanuc mode on a Haas: X in diameter, virtual Y on the C address. C must be in C-axis mode (M154 engage; one blog says "M40 mode"). | [FORUM] https://www.practicalmachinist.com/forum/threads/g112-breakdown.350386/ ; [SEC] https://plasticranger.com/g112-cnc-code/ |
| Feed | Haas training: "feed rates will remain constant when using G112" (F is the path feed in XY); use G98 feed per minute. | [SEC] https://www.productivity.com/wp-content/uploads/2019/01/Haas-Live-Tooling-for-Haas-Lathes.pdf (extract) |
| No real Y | No Y-axis motion is made in G112 (on Y-axis lathes as well). | [SEC] same Productivity/Haas training PDF |
| Cutter comp | Mill-style cutter comp is active in G112. G41/G42 must be cancelled (G40) before G113. Otherwise **alarm 455 "G112 block ends w/o cancel cutter comp"**: an X/Y comp exit move is required before G113. | [SEC] https://www.helmancnc.com/haas-alarm-455-g112-block-ends-wo-cancel-cutter-comp-haas-lathe/ ; https://cncreplacementparts.com/haas-alarm-455-g112-block-ends-w-o-cancel-cutter-comp-haas-lathe/ ; [FORUM] Autodesk thread quoting the manual: https://forums.autodesk.com/t5/hsm-post-processor-forum/g41-g42-haas-mill-turn/td-p/7754197 |
| Rapids | Disputed. The Haas manual example has a `G00` move inside G112. Users say Fanuc forbids it, and Haas posts still output G0. | [FORUM] cnczone 26453 / practicalmachinist g112-breakdown. [INF] Haas apparently allows G0 in G112 (interpolated in XY); not confirmed |
| Centre, feed governor, start angle | Nothing documented was found. One source: "start at C0 before you enter polar mode". | [SEC/FORUM] |
| Training manual | The Haas "Y-Axis Lathe Applications Training" Rev D (2016, software L11.10A) has a "G112 XY to XC Interpretation" section on p. 57. Its body text was not readable. | [DOC title only] https://service.haascnc.com/sites/default/files/Locked/3/Y-Axis%20Lathe%20Applications%20Training_Rev_D.pdf |

## 3. Mitsubishi M700V / M800 / M80 (lathe system) — G12.1/G13.1 (or G112/G113)
| Topic | Fact | Label / source |
|---|---|---|
| Plane | The plane is the linear axis (1st axis) plus a hypothetical axis that crosses it at right angles (2nd axis). The **work-coordinate zero point** is the origin during polar interpolation. | [DOC] M700V Programming Manual §6.10 p.83: https://www.manualslib.com/manual/1283281/Mitsubishi-Electric-M700v-Series.html?page=83 |
| Block rule | G12.1/G13.1 are modal and must stand alone in a block. With another G code in the same block → **program error P33**. Axes are assigned by parameters. | [DOC] same |
| Manual location (M800) | M800/M80/C80 Lathe Programming Manual IB-1501276, §6.10. Not readable this session. | [DOC title] https://dl.mitsubishielectric.com/dl/fa/document/manual/cnc/ib1501276/ib1501276engd.pdf |
| High-accuracy | SSS high-accuracy control is disabled temporarily in polar mode (machining-centre manual). | [DOC extract] IB-1501278 (scribd 488142001) |
| Near the pole | Not found. A user report: at higher F the C axis exceeds its maximum deg/min and alarms. | [FORUM] |

## 4. Mazak (EIA/ISO on Mazatrol Matrix / Integrex; NC built on Mitsubishi)
- The G12.1 block must be preceded by a plane select (G17 with the C axis): "The block of G12.1 must be preceded by a
  command of selecting the appropriate plane (G17XC)". [DOC] Integrex e-Series Programming Manual, Group 26 p.193:
  https://www.manualslib.com/manual/1585216/Yamazaki-Mazak-Integrex-E-Series.html?page=193
- Matrix EIA manual H740PB0030E: https://victoriacaruk.com/Mazak%20EIA%20-%20Programming%20Manula%20for%20Mazatrol%20Matrix.pdf
  (polar section not readable). Polar and cylindrical interpolation are paid options [FORUM]. Without the option →
  alarm 708 "illegal G code" [FORUM].
- [INF] Since the NC is Mitsubishi-based, the rules are probably those of §3 (origin = work zero, own block).

## 5. Okuma OSP (P200L/P300L)
- No polar-interpolation manual text was found. Code lists show **G137** = start of "coordinate system conversion" and
  **G136** = end. In this mode XY programming on the face is converted to X-C by the control (and X-Y-C on Y-axis
  machines). A CAM post outputs G137 when the path does not fit the Y travel. [SEC] https://www.helmancnc.com/okuma-lathe-g-and-m-codes/ ;
  [FORUM] https://www.cnczone.com/forums/okuma/317436-read-xy-g137.html ; https://forums.autodesk.com/t5/hsm-post-processor-forum/post-for-okuma-p300/td-p/7498496
- One mill code list gives G137 a different meaning ("contour mode OFF") → it depends on the control generation and the mill/lathe variant. Check
  the OSP-P300L manual (ManualsLib lists the P200L manual, 364 pages). Nothing found on pole, feed, or comp.

## 6. Doosan / Hyundai-Wia (Fanuc i)
- They follow Fanuc (section 1). Daewoo may use G112.1/G113.1 on old models (user memory) [FORUM]. Nothing builder-specific was found.

## 7. Extra: Siemens SINUMERIK TRANSMIT (the clearest documented pole handling, for comparison)
- Pole = where the radial linear axis meets the rotary axis. With **MD24911 TRANSMIT_POLE_SIDE_FIX_1** (and MD24951
  for TRANSMIT 2) = 1 or 2, the path stays on one side of the pole. To pass through: "Linear axis traverses into pole;
  rotary axis turns through 180°, with the other axes … stationary. Execution of remaining block. The linear axis now
  exits from the pole again." The control inserts that traversing block itself, and it works only in AUTOMATIC. In JOG
  the motion stops in the pole and may leave only along its approach tangent. If the tool centre cannot reach the
  turning centre, the pole is replaced by a **working-area limitation**. [DOC] 840D sl Transformations Function Manual 06/2019:
  https://cache.industry.siemens.com/dl/files/453/109767453/att_991396/v1/840Dsl_transformations_fct_man_0619_en-US.pdf
- 808D: two ways through the pole: move the linear axis alone through it, or move to the pole, rotate C there, then move away. Advice:
  avoid paths whose tool centre passes through X0/Y0. Tool radius compensation must be deselected before TRAFOOF.
  [DOC] https://www.manualslib.com/manual/1586231/Siemens-Sinumerik-802d-Sl.html?page=247 ;
  https://cache.industry.siemens.com/dl/files/107/109745107/att_910379/v1/808D_808D_ADV_fct_man_0117_en-US.pdf
- (Our DECISIONS already cite POLE_SIDE_FIX for Index-at-Pole; this confirms the documented sequence.)

## Answers per focus question (summary)
| | Fanuc | Haas | Mitsubishi/Mazak | Okuma | Siemens |
|---|---|---|---|---|---|
| (a) through or near the centre | operator must reduce F; AFC option | not documented | not found | not found | POLE_SIDE_FIX: into pole, C 180°, out (auto block) |
| (b) automatic feed reduction | 5450 AFC + 5463 % of 1422 | not documented ("feed constant") | not found | not found | (not searched) |
| (c) C start / rollover | 0 = C at G12.1; orient C0 first | start at C0 | not found | — | — |
| (d) arcs | G02/G03, R or I/J | G02/G03 in G17 | G02/G03 | — | — |
| (e) cutter comp | yes, G40 at entry/exit | yes, alarm 455 if not cancelled | yes (GSK too) | — | deselect before TRAFOOF |
| (f) rapids in mode | G00 forbidden | apparently allowed (disputed) | — | — | — |
| (g) centre / tool offset | 5450 PLS shift `G12.1 X_ C_`; hypothetical-axis compensation | — | origin = work zero | — | working-area limit if the centre cannot be reached |
| (h) alarms | 145 (bad 5460/5461, illegal conditions); C over 1422 → servo alarm | 455 | P33 | — | — |

## Features these controls have that the converter might lack
1. **Automatic feed limit near the centre (Fanuc 5450 AFC + 5463; "pole governor").** The control computes the C speed
   that the commanded path feed needs. If it exceeds a set percentage of C's maximum cutting speed, it lowers the
   feed so that C stays at that limit; closer in, it clamps. For us: our G93 output asks for a time per block, and
   LinuxCNC already caps any axis at its `[AXIS_C]` limit (DECISIONS: the controller decides). What we lack is the
   *warning/report* (already in STATUS as an unbuilt idea): list the blocks where the requested time is shorter than C
   travel / C max, i.e. where the real feed will be lower than the CAM feed. [INF] No motion change needed.
2. **Centre shift (Fanuc PLS, `G12.1 X_ C_`).** The polar centre can be placed away from the work origin. For us the pole
   is always the CAM XY origin. An option "pole at X_ Y_ of the CAM drawing" would let a part whose origin is at a
   corner run without moving the origin in CAM. [INF] Small and universal, but each wrong value gives a wrong part.
3. **Hypothetical-axis (Y) compensation (Fanuc §6.4).** It corrects the X/C conversion when the cutter centre lies off
   the line through the chuck centre (spindle height error). The exact maths: radius = sqrt(x²+y²−e²)-style
   correction plus an angle correction atan(e/…) [INF]. **DECISIONS rejects centre-height compensation** (router base
   milled on the machine), so only note it. Do not propose it again unless Marios raises it.
4. **Cutter radius compensation inside polar mode (Fanuc, Haas, GSK).** Rejected for us by design: G41/G42 refused and CAM
   compensation used ("in computer"). No action.
5. **Explicit pole-crossing sequence (Siemens POLE_SIDE_FIX).** Into the pole, C 180°, out, with the other axes stopped. Our
   Signed-X and Index-at-Pole already do this, and offline, so nothing is missing; the Siemens text confirms the method.
   Siemens also replaces the pole with a working-area limit when the tool cannot reach the centre. That is like our X Axis Min / one-side
   rule.
6. **Mode entry/exit rules as alarms (Fanuc 145, Haas 455, Mitsubishi P33).** The controls refuse illegal states.
   The converter's refusal-with-line-number policy already matches this. No gap found.
7. **G00 forbidden in polar mode (Fanuc).** Fanuc rejects rapids because a joint-space G0 is a spiral. We already
   segment rapids (RAPID_TOL) and make radial rapids one block. This is consistent; no gap.

## Not found (would need the PDFs opened)
- Exact Fanuc AFC algorithm text, the hypothetical-axis compensation parameter number and formula, 30i-specific
  parameters, the bodies of the Haas G112 training section and of Mitsubishi IB-1501276 §6.10, and Okuma's G137 manual section.

---

## How CAM post processors do polar / XZC (research 2026-10-13)

Read-only research. Nothing in `/home/user/polar-cnc-converter` was changed. Clones and downloads are in
`scratchpad/research/src/` (`cps/`, `mc/`, `cam-posteditor/`, `nvim/`, `polarToolsJS/`). Nothing was executed.

**Access limits in this sandbox.** `cam.autodesk.com`, `autodesk.com`, `help.autodesk.com`, `web.archive.org`,
`ncmatic.com`, `bu.edu` and `machsupport.com` could not be reached (DNS errors or proxy 403). For Autodesk the API
text therefore comes from Autodesk's own MIT-licensed type definitions (`Autodesk/cam-posteditor`, below). That file
mirrors the cam.autodesk.com reference and links to it. Post code was read from copies of Autodesk-released `.cps`
files that users put on GitHub; the headers are intact, with revision, date and copyright. Facts about Mastercam,
SolidCAM and NX come partly from search-result snippets and are marked **(snippet)**.

**Licences.** The Autodesk `.cps` posts say "Copyright (C) 2012-2026 by Autodesk, Inc. All rights reserved" and
ship without a licence file. Autodesk pages describe the library as "open source … use without limitation"
(snippet), but there is no formal licence, so we use the **method only**. `Autodesk/cam-posteditor`
(the VS Code extension with the API type definitions) is **MIT**, "Copyright (c) 2017 by Autodesk, Inc.". The
Mastercam `.pst` files are CNC Software generic posts ("intended for modification"), but they are proprietary:
**method only**. polarToolsJS / gCodePolarizerJS are GPL-3: method only.

---

## 1. Autodesk Fusion / HSM / Inventor CAM post engine — "polar mode"

### 1.1 Sources read
| Source | Version | Notes |
|---|---|---|
| `Autodesk/cam-posteditor` `vs-code-extension/res/language files/globals.d.ts` | commit `c95cce0` (2026-09-11), MIT | API docs (doc comments copied from the cam.autodesk.com reference) |
| `DrPhilDSI/fusion-post-nvim` `lua/fusion_post/types/globals.d.ts` | `3a87e05` (2026-03-06) | second copy of the same API, shorter |
| "doosan mill-turn fanuc.cps" (Autodesk) | Revision 44210 `aab7925`, 2026-01-20; repo RGTUSA/Doosan-Lynx-220-LSYC `7d14b07` | most complete current XZC code |
| "okuma lb3000 mill-turn.cps" (Autodesk) | Revision 44210, 2026-01-20; Jazzer360/fusion-posts `150ebba` | same structure; Okuma C direction codes |
| "nakamura mill-turn fanuc.cps" (Autodesk) | Revision 44083, 2023-08-12; peteoxenham/… `32acd1e` | |
| SKOL-PUMA (Autodesk Doosan, customised) | Revision 44132, 2024-06-21; Andrux51/skol-cnc-post `b5af7ec` | |
| "HAAS - Mill - NGC" (customised Autodesk Haas NGC) | header Revision 10, 2022-10-08; Adam-Con-pro/KINTECH_POST `e2b7e49` | polar on a **mill** with a rotary table + inverse time |
| "fanuc.cps" generic mill (Autodesk) | Revision 44242 `3cf9e6b`, **2026-09-07**; elcf-robot/autodesk-fanuc `7191abc` | new automatic polar mode |
| "emc_custom.cps" (Autodesk EMC/LinuxCNC mill, maybe user-edited) | Revision 44195, 2025-09-16; mark0815/linuxcnc-configs `3c43897` | |
| "haas ds-30ssy.cps" (Autodesk, **legacy, before the kernel had polar mode**) | Revision 40489, 2015-12-18; chroja/AXHS7145-post `c04b213` | home-made XZC code in the post |
| "Centroid_Mill …-005.cps" (Autodesk-based) | Revision 42680, 2020-03-09; swissi2000/… `4d7d635` | older post-side inverse-time / DPM code |

### 1.2 Kernel API (documented, `globals.d.ts` `c95cce0`)
- `activatePolarMode(tolerance, currentAngle, polarDirection, interpolateRapidMoves, optimizeType) → VectorPair`
  (line 4266-4268). Documented: it turns polar mode on and returns the start position and direction after the polar
  transform. `.first` = machine X Y Z, `.second` = A B C. The doc example passes `cOutput.getCurrent()` as
  `currentAngle`. Search-snippet text of the cam.autodesk.com page (it could not be fetched here) **(snippet)**:
  - the tolerance is for linearization, in mm;
  - `currentAngle` is the present angle of the rotary axis;
  - `polarDirection` is "the line the tool can move along"; (1,0,0) = the X axis, and (0,0,0) means "take it from the
    section's start position";
  - `interpolateRapidMoves = true` linearizes rapids like feed moves.
- `deactivatePolarMode()`, `isPolarModeActive()`, `getPolarPosition(x, y, z) → VectorPair`
  (`fusion-post-nvim` globals.d.ts lines 2168-2176).
- `activateAutoPolarMode(options)` (line 4272-4274): "Activates automatic polar mode handling". The options in use
  are `{tolerance, optimizeType, expandCycles}` (generic fanuc.cps rev 44242 line 858, only when kernel
  `revision >= 50294`).
- `Section.polarMode` / `getPolarMode()` ("polar mode type") and `Section.polarDirection` / `getPolarDirection()`
  ("user-specified direction for polar machining type"). Lines 1646, 1951-1956, 1992.
- `Section.isPolarRapidLinks()` (line 1984): "true, if rapid polar links should be used, false - for linear rapid
  links, undefined - if not specified (Fusion assumes they are linear)". So Fusion can now be asked to make the
  **link moves themselves polar** (rotary) instead of straight.
- `Section.isCuttingMotionAwayFromRotary(distance, tolerance)` (line ~1981): "true if the milling motion for the section
  is further away from X0 Y0 than the given distance. Can be used to check if motion gets close to the rotary axis for
  XZC milling." It is a **pole-proximity check per operation**. Only one GitHub post uses it (GSK mill-turn).
- `Section.doesToolpathFitWithinLimits(machine, abc)`: the mill-turn posts use it to pick XY (Y axis) or polar.
- Feed: `MachineConfiguration.setMultiAxisFeedrate(feedMode, maximumFeedrate, feedType, outputTolerance, bpwRatio)`
  (line 2646). The modes are `FEED_INVERSE_TIME`, `FEED_DPM` (degrees per minute) and `FEED_FPM`. The types are
  `INVERSE_MINUTES`/`INVERSE_SECONDS` and `DPM_STANDARD`/`DPM_COMBINATION`. `outputTolerance` = "tolerance to
  determine when the DPM feed has changed". `bpwRatio` = rotary/linear accuracy ratio for DPM.
  `getMultiAxisMoveLength(x,y,z,a,b,c) → MoveLength` (line 4000) gives the linear, rotary and **tool-tip** lengths.
- Rewind: `enableMachineRewinds()`, `performRewinds()`, `setSafeRetractDistance/Feedrate`, `setSafePlungeFeedrate`,
  `setRewindStockExpansion(vector)`, `setRewindStrategy(MINIMIZE_REWINDS | AXIS_PREFERENCE)` (line 2686: minimize
  the number of rewinds before reaching the rotary limits, or follow axis preference). Entry points:
  `onRewindMachineEntry(a,b,c)` (return true = the post handles it; `onRewindMachine` is deprecated, line 4321),
  `onMoveToSafeRetractPosition`, `onRotateAxes`, `onReturnFromSafeRetractPosition`.
- `Axis` reset (line 2832): "0: disabled. 1: reset to 0 at new operation. 2: reset to 0 at rewind. 3: both". This
  brings a cyclic C back near 0 at each operation.
- `MachineConfiguration.setSingularity(adjust, method, cone, angle, tolerance, linearizationTolerance)`,
  `preserveRotaryAtZero(currentDirection, previousABC, currentABC)` ("keep secondary angle when tool axis is perp to
  rotary axis", hidden). This is the 5-axis singularity handling. Inference: it is the 5-axis counterpart of "keep C at the pole".
- `setShortestAngularRotation(bool)`. `OutputVariable` `cyclicLimit` / `setCyclicSign(-1|0|1)` maps output into
  [-L,0], [-L,L] or [0,L] (line 735, the older FormatNumber form, deprecated since r45877).

### 1.3 How the current mill-turn posts use it (Doosan rev 44210; Okuma, Nakamura and SKOL are the same)
- **Two polar modes** (`getOperationPolarMode`, Doosan lines 2608-2634): **IN_CONTROL** = G12.1/G112 polar
  interpolation in the CNC, and **IN_COMPUTER** = "polar coordinates", which the post computes as X C moves.
  They are chosen from the operation parameters `operation:usePolarWhenNecessary` and `operation:polarMode` =
  `"computer"|"control"`, or from `section.polarMode`. In **automatic** mode the post uses IN_CONTROL when the
  machine supports it, but **forces IN_COMPUTER when `section.polarDirection` differs from (1,0,0)**, because
  only computer mode can hold the tool on another line. Manual NC actions `usePolarInterpolation` /
  `usePolarCoordinates` (old names `usePolarMode` / `useXZCMode`) force a mode for the next operation (lines 21-22,
  3824-3831).
- **Automatic choice of polar** (`updateMachiningMode`, lines 2637-2740), for axial (face) 2D milling only:
  - if the path fits the machine's XY (Y-axis) limits at the best C (`getBestABC` + `doesToolpathFitWithinLimits`),
    the post outputs plain XY;
  - otherwise it uses polar (G12.1 if available, else computed XZC);
  - for drilling with holes off centre, polar positions are used unless "use Y axis for drilling" is set and fits;
  - polar is refused for radial (G19) work and for multi-axis operations;
  - computer polar + cutter compensation "in control" is an **error** (compensation needs G12.1);
  - the Autodesk support article (snippet) describes it the same way: a path outside the X-axis minimum or Y range
    switches to C moves.
- **Activation** (`setPolarCoordinates`, Doosan lines 3004-3056): the post picks the rotary axis whose vector is not
  perpendicular to the work-plane normal (else error "Polar coordinates require an active rotary axis…"). It then
  calls `activatePolarMode(getTolerance()/2, 0, direction)`. The tolerance is **half** the operation tolerance;
  Okuma line 2768 passes the full tolerance in one place. **currentAngle = 0** and the default direction is (1,0,0).
  After that, `getPolarPosition(start)` → `setCurrentPositionAndDirection`.
- `getTolerance()` (Okuma lines 849-854) = the smaller of the post's `tolerance` variable and the operation's own
  `operation:tolerance`, converted to mm.
- **Haas mill NGC (lines 3622-3689) adds:** if `polarDirection` is the zero vector, direction = unit vector from the
  rotary axis offset to the section's start point. That is, **the tool line is put through the first point, so the
  operation starts without a C rotation**. The direction is then projected into the plane of the rotary axis
  (two cross products). At activation it calls `setPolarFeedMode(true)`, which switches multi-axis feed to
  **FEED_INVERSE_TIME / INVERSE_MINUTES** (or DPM_COMBINATION if "useDPMFeeds"). At deactivation it restores the
  previous mode.
- **Motion after activation:** the kernel turns every linear move (and, by inference, every arc, because the posts
  have no polar branch in `onCircular`) into rotary moves and calls `onLinear5D(x,y,z,a,b,c,feed,feedMode)` /
  `onRapid5D`. The post only formats X, Z and C. Doosan/Nakamura/SKOL write G1 with `getFeed(feed)` under **FEED_DPM,
  DPM_COMBINATION, max 99999, output tolerance 0.5** (Doosan lines 1103-1109). Haas NGC and EMC write
  `G93 … F<inverse>` when `feedMode == FEED_INVERSE_TIME`, with F forced on every block (Haas lines 3523-3555).
  The inverse-time maximum is 9999.99.
- **Rapids in polar:** `onRapid5D` writes G0 X Z C as one block, or G1 at a high feed when more than one axis moves
  and the "useG0" property is off (Doosan lines 2961-2981: "axes are not synchronized"). The entry move is written as
  **Z first, then X+C together in one G0** (Doosan lines 2509-2519). Rapids are linearized only if
  `interpolateRapidMoves` is true. The current posts call `activatePolarMode` with 3 arguments, so this is undefined
  (inference: rapids not linearized; G0 X C is a spiral in joint space).
- **Cycles:** drilling cycles stay canned in computer polar. `getCommonCycle` (Doosan lines 3490-3509) converts each
  hole position with `getPolarPosition` and writes `X C Z R`. The C axis is driven to the polar angle of each hole.
  In the new auto mode, `expandCycles` (`EXPAND_NONE/TCP/NON_TCP/ALL`, setting `polarCycleExpandMode`) chooses
  which cycles the kernel expands (fanuc.cps 44242 line 392, EMC line 241).
- **C output** for lathes: `createOutputVariable({prefix:"C", cyclicLimit:360})` (Doosan line 556, Okuma 567), so
  C is written as 0..360 for a rollover C axis. Okuma (lines 859-869) writes a **C direction M-code** (CW/CCW, from
  the sign of ΔC folded to ±180°) unless "useShortestDirection" is set. Its drilling comment (line 3424): "manual
  recommends using a single direction for accuracy", so holes are approached with **C always turning the same way**
  (backlash). The sub-spindle reverses the C scale sign (`getCScale`, `invertAxes`, lines 1941-1975).
- **Retract/reconfigure ("rewind")**, Doosan lines 1094-1101: `enableMachineRewinds()`, safe retract distance
  25 mm (1 in), retract feed 500, plunge feed 250, stock expansion 0.1 in. When a rotary axis would pass its limit,
  the kernel retracts out of the (expanded) stock along the tool axis (`onMoveToSafeRetractPosition`), turns the
  rotary axis to an equivalent angle (`onRotateAxes`, which writes only ABC in G0), and returns
  (`onReturnFromSafeRetractPosition`, XY first, then Z) (Haas lines 3566-3620). Generic posts ship with
  `performRewinds = false` (Haas line 1018). The C axis on mill-turns is `cyclic:true`, so it never needs a rewind
  (Doosan line 1056).
- **Arc sweep limit:** `maximumCircularSweep = toRad(120)` "reduced sweep due to G112 support" (Doosan line 48).
  This applies to in-control G112 only.

### 1.4 How Autodesk did XZC before the kernel had it (legacy Haas DS-30SSY, rev 40489, 2015)
Useful because the method is fully visible:
- `getC(x,y) = atan2(y,x)`. `getCClosest(x,y,c,clockwise)` adds or subtracts 2π until the new angle is within
  ±π of the current C. For arcs it uses the arc direction instead: always ≥ or ≤ the current C.
- `onLinear` in XZC mode (lines 1424-1474):
  - radius = **min(start radius, end radius)**;
  - **error "Cannot machine radius 0." if that radius < 0.1 mm** (except drilling);
  - **error "Cannot machine 180deg sweep."** if the C change of one line is ≥ π;
  - segment count from the sagitta formula `n = ceil(sweep / (2·acos(1 − tol/r)))` (`getNumberOfSegments`, lines
    152-158). The points are spaced evenly along the Cartesian line, each converted to X = √(x²+y²) and C = the
    closest angle. **Weakness:** the end radii do not see a line passing close to the centre between them.
- `onRapid` in XZC: a **single G0 X C Z** (no segmentation).
- `onCircular` in XZC (lines 1578-1604): an XY arc **centred on the rotary axis** becomes **one G1 X C Z** with C in
  the arc direction, the same idea as our C-only arcs but with no sweep limit. A **G18 (ZX) arc with C unchanged**
  is written as a native `G18 G2/G3 X C Z I K`. Everything else is linearized with `linearize(tol)`.
- Feed: nothing special in this post (plain F). In the 2020 Centroid post (`getMultiaxisFeed`, `getInverseTime`,
  `getFeedDPM`, `getMoveLength`), inverse time = feed / tool-tip length. The tool-tip length is the **XYZ
  length + the "radial" length** (radius × angle per rotary axis), a sum and not a Pythagorean combination. A
  zero-length move gets the maximum inverse time (999999 or `maxInverseTime`). The value is capped at the maximum.
  DPM combination = √(xyz² + (deg·bpw)²) / time, capped, and changed only when it differs from the last value by more
  than `dpmFeedToler` (0.5).

---

## 2. Mastercam, SolidCAM, Siemens NX (documented behaviour only)

### 2.1 Mastercam (generic lathe C-axis post, `NAKAMURA 4X MT_Lathe.pst`)
This file is really `Mplfan.pst`, "GENERIC FANUC LATHE C-AXIS POST", POST_VERSION V26.00, revision 23.84;
hasankorkmazdev/nakamura `7c7b323`. Proprietary, method only.
- The operation type is **"C-axis / Face Contour"**. Polar conversion is done in the post (`pxyzcout2`, lines
  4337-4355): X = √(x²+y²), C = atan2(y,x) + tool-plane angle. "C0" is defined by a view (View 3 = C zero), and
  +C is CCW seen from the side view (lines 215-228).
- **A point exactly on the centre keeps the previous C** (`pnt_at_zero` → `csav = prv_csav`, pcoutrev lines
  4409-4420).
- **Arcs centred on the centre** in the XY plane are detected in the post (`cir_at_zero`, pcir0$ lines 2425-2441).
  Arc breaking is switched off, and the move becomes **one C move with C = previous + sweep** (G1, "only C is
  moving"). Arcs in plane 2 (G18) set `c_ax_flp` when X is negative. Other arcs are linearized (`linarc$ = 1`).
- **Lines** are broken by the MP engine itself (`brklinestype$ = 6` for face cuts, 4 for cross cuts, plin0$ lines
  2399-2413). The tolerance lives in the machine/control definition (not visible in the post).
- **C continuity:** a revolution counter `rev`. When |ΔC| > `ctol` (270° in this post, 225° in others), it adds or
  subtracts 360 until |ΔC| ≤ ctol, giving C = rev·360 + C. At a tool change or tool-plane change it takes the
  shortest way (≤ 180°). `frc_cinit = 1` "Force C axis reset at toolchange" resets rev and C to 0 (lines 381,
  1926-1931). `c_axistype` chooses 1 = winds up, 2 = signed absolute (warns on a move > 360°), 3 = indexer
  (tolerance check against the table step), 4 = shortest direction (line 449).
- **Feed** for C moves (`pfcalc` / `pfclc_deg_inv`, lines 4487-4517): if C barely moves (< `vtol`), or at a
  centre point, or for G0, it uses units/min. Otherwise it uses **degrees/min**: circumference from the **average
  radius** of the two ends, cdelta = ΔC/360·circ, length = √(cdelta² + linear²), frdeg = (cdelta/length)·F·360/circ,
  capped at `maxfrdeg` (2000). A new F is written only when it changes by more than `frdegstp` (10 deg/min).
- The 4-axis mill post (`Generic Fanuc 4X Mill.pst`, wildbeta/mp-post-robodrill `ac8ba6b`, lines 290-293, 2378-2410)
  has **inverse time**: `use_frinv` (set by the control definition, `rotfeed4$ = 2`), frinv = F / length (or
  F/60/length for seconds), capped at `maxfrinv` 999.99, F forced on every block, G93.
- G112 (in-control polar) needs every path to "start and end at the C0 location" (lines 239-243). Forum (snippet):
  activated by a Misc integer (mi4); mill posts lack polar output by default.

### 2.2 SolidCAM (snippet level only)
SolidCAM supports "Polar Interpolation cycles (radial and face)" and gives "full control over the C-axis output for
the selected contour… to avoid collisions and axis limits" (solidcam.com mill-turn page, snippet). The Mill-Turn
training guide (bu.edu PDF, unreachable) has the sections "Y Axis Interpolation and C Axis Interpolation",
"C Axis Interpolation for Polar and Cylindrical Milling" and a "Rotate" tab. No algorithm details were found.

### 2.3 Siemens NX (snippet level)
- NX help (snippet): the mill-turn XZC output is linearized only when output is **polar** (`SET/POLAR,ON`, the
  default). OFF gives Cartesian XYZ with no linearization.
- Siemens KB **PL8009822** "XZC mill post — is it possible to machine across the centerline (from X+ to X−)": answer
  (snippet) = put the **"Set Polar" UDE** in the operation to **allow −X**. So by default NX keeps X positive, and
  crossing the centre with negative X (our Signed-X) is an explicit per-operation option.
- A Siemens community answer (snippet) recommends doing polar in the control (G12.1/TRANSMIT). Linearizing in the
  post "requires breaking up linear point moves based on kinematic change", which can produce very many points and
  slow the post. NCmatic describes a **"Lock Axis" UDE** that forces XZC output (X and C instead of X and Y);
  the page itself was unreachable.

---

## 3. LinuxCNC-side approaches and open-source tools
- Already studied (`references/research-2026-10-11.md`): `rosekins`, `millturn`, Klipper/grblHAL/Marlin/RRF polar,
  gCodePolarizerJS, PolarGcoder, spinny-cnc, Klipper-Polar-Support, Sandify. Nothing new.
  `kadirilkimen/polarToolsJS` (`72fe0de`, 2022, **GPL-3**) is the web front-end of the same gCodePolarizer code:
  fixed-length splitting `ceil(xyDistance/t)` (js/gcodePolarizer.js line 171), angle = atan2(x, y). Method only;
  nothing better than ours.
- `xyzac-trt-kins` etc. are table-tilting 5-axis kinematics, not relevant to polar faces.
- LinuxCNC forum "XZC Lathe Rotational feed rate – Kinematics?" (thread 29276, snippet): the advice is to compute
  feeds outside and use **G93**, because LinuxCNC does not know the tool's distance from the C centre. A later poster
  says G93 fixed it. This confirms our architecture.
- Forum thread 44162 (NoJo "home built 5C CNC lathe – polar interp. and live tooling", snippet): a **custom HAL
  component + switchkins** gives G12.1 (C/polar mode) and G13.1 (back to turn mode) in LinuxCNC. Problems were mode
  switching (the position must be converted with forward/inverse kinematics at the switch), reading G54 (#5221) in the
  component, and C homing. It is not in LinuxCNC; LinuxCNC 2.9 has no G12.1. This is the real-time alternative to our
  offline pre-processor (DECISIONS: real-time kinematics rejected).
- Forum thread 18713 "Peculiar behavior with inverse time mode" (snippet, old EMC2): G93 moves slowed down when a
  coordinate was not a whole number of microsteps. Old; worth a look if G93 timing ever looks wrong.
- No other open-source offline Cartesian→XZC converter was found on GitHub (repo searches "polar gcode", "polar cnc",
  "XZC gcode", "theta rho gcode converter"). Marioskiv/polar-cnc-converter is itself in the results.

---

## 4. Features these CAM posts / tools have that the converter might lack

Each item: what it is, where it comes from, how it works (our words), and a short note on fit. "Fit" is inference.

1. **Unwind C at a tool change or new operation (cheap rewind).** Mastercam `frc_cinit` resets C to 0 at a tool
   change, with the shortest move (≤ 180°) at tool-plane changes (Mplfan pcoutrev). Autodesk `Axis reset` 1/2/3
   (globals.d.ts line 2832). Method: when the tool is already up at a tool change or at program end, replace the
   accumulated C by the equivalent angle nearest 0 (C mod 360, folded to ±180) and move there in the air. This uses
   no extra retract, so it does not conflict with Marios's rejection of retracts that leave material uncut. Fit:
   STATUS says the C soft limits (±99,999°) allow only ~277 turns per program. The converter has `nearestEquivalentAngle`
   only for the centre-fill return (layout-xzc.js ~1084), not a general unwind.
2. **Rotary-limit check with retract/reconfigure.** Autodesk `enableMachineRewinds` + safe retract distance, stock
   expansion, `onRotateAxes`, and `setRewindStrategy(MINIMIZE_REWINDS)`. Method: know the C travel limits; when the
   next block would pass one, retract along the tool axis out of the stock (+ margin), turn C by whole turns, and come
   back. A lighter version: **warn or refuse** when the cumulative C would exceed a given C limit. Fit: the warning
   alone fits "few settings"; a mid-cut retract is the kind Marios rejected (DECISIONS), so propose only the check.
3. **Pole-proximity report per operation.** Autodesk `Section.isCuttingMotionAwayFromRotary(distance, tol)`.
   The legacy Autodesk XZC simply refused radius < 0.1 mm and sweeps ≥ 180° per move. Method: compute each
   operation's closest cutting approach to the axis and report it, with the C speed it needs. The converter already
   handles the pole; the gain is a report (it overlaps the STATUS "pole governor" idea).
4. **Keep canned drilling cycles with one X C per hole.** Doosan `getCommonCycle`, Autodesk `expandCycles` option,
   Mastercam drill polar. Method: write the cycle once, then each hole as `X<r> C<θ>`. Fit, inference to verify: the
   LinuxCNC docs say rotary words in a canned cycle must equal the current position (the rotary axis must not move),
   so for LinuxCNC our expansion is right. It could be a profile option for other controllers only.
5. **Unidirectional C positioning for holes / indexing (backlash).** Okuma post comment line 3424 ("manual
   recommends using a single direction for accuracy"); Mastercam indexer type. Method: before each hole, always
   approach the target C from the same side, overshooting a few degrees and coming back if needed. Fit: the C drive
   has belts (backlash unmeasured); useful for bolt circles. Optional.
6. **Polar direction / start angle choice.** Autodesk `polarDirection` (tool line in any XY direction), and the
   zero vector means "line through the first point", so there is no initial C turn (Haas NGC lines 3657-3664).
   Mastercam's C0 comes from a view plus a tool-plane angle. Method: a C offset (or "first point at C = 0") rotates
   the whole C stream by a constant. Fit: today C0 = CAM +X. A constant offset only helps when the part must line up
   with an existing feature, or to save the first rotation. Low priority.
7. **Polar rapid links from the CAM.** Fusion `Section.isPolarRapidLinks()`: the CAM itself can make link moves as
   rotary moves. Autodesk `interpolateRapidMoves` decides whether rapids are linearized (default in current posts:
   no → G0 X C spiral). Method for us: an option to let rapids **above the program's highest Z** be single joint-space
   G0s (spiral, faster), while keeping segmented rapids near the stock. Fit: the converter segments all rapids on
   purpose (CLAUDE.md safety fact). This is a speed option with a real safety trade-off, so only with Marios's yes.
8. **Native G18 arc when the arc lies in a radial plane.** Legacy Autodesk DS-30SSY: a ZX arc with C unchanged
   becomes `G18 G2/G3 X C Z I K`; Mastercam `cir_at_zero = -1` + `c_ax_flp`. Method: if a G18 arc has Y = 0 (its plane
   contains the axis), C is constant and X/Z are a true arc, so pass it as a G18 arc (sign by side). Fit: the
   converter refuses G18/G19 arcs. This would accept the simple case exactly; rare in CAM output.
9. **DPM feed mode as a fallback for controls without G93.** Autodesk `FEED_DPM` + `DPM_COMBINATION`, output
   tolerance 0.5, max 99999 (Doosan); Mastercam deg/min with `frdegstp` hysteresis and `maxfrdeg`. Fit: DECISIONS
   say output is always G93 (G94 removed because LinuxCNC ignores the C arc). Only relevant for a non-LinuxCNC
   profile on a control without G93; not for LinuxCNC.
10. **Feed hysteresis / maximum inverse-time cap.** Autodesk max 9999.99 inverse; Mastercam `maxfrinv` 999.99. A
    move that would need a larger number is clamped (it runs slower). Fit: the converter's 0.6 ms minimum block time
    plays the same role (= 100,000/min). The difference is the format limit: some controls cannot read F above 9999.99,
    which could be a profile value for other controls.
11. **Rollover C output (0-360 + direction codes).** Autodesk `cyclicLimit:360` + Okuma CW/CCW M-codes;
    Mastercam `c_axistype` 2/4. Method: write C modulo 360 and give the turning direction separately (M-code or
    signed value). Fit: not for this LinuxCNC machine (continuous C). Inference to verify: if anyone sets
    `[JOINT_n] WRAPPED_ROTARY = 1` in LinuxCNC 2.9, absolute C values are taken modulo 360, which would break
    cumulative-C output. Worth one warning line in the README.
12. **Automatic XY vs polar per operation (machines with a Y axis).** Doosan `updateMachiningMode`. Method: if the
    operation fits the Y travel, output XY; else polar. Fit: Marios's machine has no Y axis. It only matters for the
    universal goal (a future "XYZC" layout).
13. **Tolerance taken from the operation.** Autodesk `getTolerance()` = min(post tolerance, operation tolerance),
    then /2 for polar. Fit: G-code files do not carry the CAM tolerance, so this is not applicable to an offline
    converter. The /2 split matches ours.

**Where the converter is already ahead (for balance).** The legacy Autodesk XZC segments by end radii only (a line
passing near the centre gets too few segments). Autodesk's inverse-time length adds the linear and rotary parts
(approximate). Mastercam DPM uses the average radius. Neither has error-checked joint-space replay, segmented rapids
by default, or Signed-X through the pole (NX needs a manual "Set Polar" UDE for −X; Autodesk computer polar keeps
the tool on one direction line).

## Sources (URLs)
- https://github.com/Autodesk/cam-posteditor (MIT) — `vs-code-extension/res/language files/globals.d.ts` @ `c95cce0`
- https://github.com/DrPhilDSI/fusion-post-nvim @ `3a87e05`
- https://github.com/RGTUSA/Doosan-Lynx-220-LSYC — "doosan mill-turn fanuc.cps" rev 44210
- https://github.com/Jazzer360/fusion-posts — "okuma lb3000 mill-turn.cps" rev 44210
- https://github.com/peteoxenham/nakamura-mill-turn-fanuc — rev 44083
- https://github.com/Andrux51/skol-cnc-post — SKOL-PUMA rev 44132, fanuc.cps rev 44188
- https://github.com/Adam-Con-pro/KINTECH_POST — "Haas - Mill - NGC IS.cps"
- https://github.com/elcf-robot/autodesk-fanuc — fanuc.cps rev 44242 (2026-09-07)
- https://github.com/mark0815/linuxcnc-configs — fusion-posts/emc_custom.cps rev 44195
- https://github.com/chroja/AXHS7145-post — "HSM original/haas ds-30ssy.cps" rev 40489 (2015)
- https://github.com/swissi2000/Fusion-360-Milling-Post-Processor-for-Centroid — rev 42680 (2020)
- https://github.com/hasankorkmazdev/nakamura — Mastercam Mplfan lathe C-axis post V26
- https://github.com/wildbeta/mp-post-robodrill — Mastercam Generic Fanuc 4X Mill
- https://github.com/kadirilkimen/polarToolsJS (GPL-3) @ `72fe0de`
- Snippets: https://cam.autodesk.com/posts/reference/classPostProcessor.html ;
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-define-XC-versus-XY-machining-in-Fusion-360.html ;
  https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-output-XYZ-moves-rather-than-C-axis-polar-moves-from-HAAS-ST-35Y-Mill-Turn-in-Fusion-360.html ;
  https://support.sw.siemens.com/en-US/okba/PL8009822/XZC-mill-post-is-it-possible-to-machine-across-the-centerline-from-X-to-X/index.html ;
  https://ncmatic.com/technical-tuesday/lock-axis-ude-millturn/ ; https://solidcam.com/cam-modules/mill-turn-machining/ ;
  https://forum.linuxcnc.org/10-advanced-configuration/29276-xzc-lathe-rotational-feed-rate-kinematics ;
  https://forum.linuxcnc.org/10-advanced-configuration/44162-developments-on-my-home-built-5c-cnc-lathe-polar-interp-and-live-tooling ;
  https://forum.linuxcnc.org/20-g-code/18713-peculiar-behavior-with-inverse-time-mode ;
  https://www.emastercam.com/forums/topic/33552-c-axis-face-contour/
