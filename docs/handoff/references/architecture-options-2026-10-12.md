# Where should the converter live? — analysis 2026-10-12

Asked by Marios: compare three homes for the XYZ → XZC conversion and recommend a roadmap:
(1) FreeCAD CAM addon / post-processor (Python), (2) Kiri:Moto post-processing (JavaScript),
(3) LinuxCNC real-time kinematics (`userkins.comp` in C, with the Mesa 7i92).
Facts from `research-2026-10-11.md` plus the LinuxCNC 2.9.10 source read today.

## Verified in the LinuxCNC 2.9.10 source (`src/emc/motion/control.c`)
- In coordinated mode, every servo period the planner's **Cartesian** position goes through
  `kinematicsInverse()` and the joint positions go **straight** into the cubic interpolator
  (lines ~1340-1385). There is **no clamp to the joint velocity/acceleration limits** at that point.
- Joint limits act afterwards only as: the following-error check (`ferror_limit` scales with `vel_cmd / vel_limit`,
  lines ~462-485) and the Mesa stepgen's own `maxvel`/`maxaccel`. A stepgen that cannot follow lags → following error →
  motion aborts mid-cut. If the stepgen limits are set above what the motor can do, the **stepper stalls silently**
  (open loop, no chuck encoder yet) — LinuxCNC keeps going with a wrong position.
- The planner (`tp.c`) plans in world (X, Y, Z) space with the `[TRAJ]`/`[AXIS_*]` limits. It does not know that
  C must turn at ω = v / r near the centre. Master (2.10-pre) added an optional `kinematicsJacobian()` (rosekins
  returns "singular" at r = 0), but **nothing in the planner uses it yet**.
- LinuxCNC already ships **rosekins** (radius, Z, angle — exactly this machine) — a userkins would only rewrite it.

## Comparison
| | Pre-processor (today) | (1) FreeCAD addon | (2) Kiri:Moto hook | (3) LinuxCNC kinematics |
|---|---|---|---|---|
| Look-ahead over the whole path | yes | yes | yes | no (servo tick + planner queue in XYZ) |
| Pole: Signed-X / Index at Pole / exact through-centre | yes | yes (same core) | yes (same core) | no — C would have to jump 180° at r≈0: following error or stall |
| Feed near the centre | G93 per block; controller slows the block to the C limit (safe) | same | same | planner unaware of C → asks for impossible C speed → error/stall |
| Feed elsewhere | G93, exact surface feed; no blend arcs with a rotary axis | same | same | **better**: native Cartesian F, G64 blending, native arcs, straight G0 |
| Finish quality | chords ≤ 0.025 mm, many short blocks, small stops at block ends | same | same | smoother where r is large; ruined where r is small |
| Hardware-crash risk | low: output checked offline (tests, replay, simulator) before it runs | low | low | **highest**: a bug in RT C code = wrong joint commands live; stall undetected without encoder |
| Effort | done | 2-4 weeks (Python port + `.fcm` + post class), golden tests as the spec | 1-2 days (wrapper + self-hosted Kiri) | weeks for less than rosekins already gives; the hard part (joint-aware planning near the pole) is LinuxCNC core work, not kinematics |
| Universal (any controller) | yes | yes (FreeCAD posts for any controller) | yes | LinuxCNC only |
| Needs anyone's permission | no | no (Addon Manager) | self-host: no; upstream: the author | no |
| User experience | paste → convert | choose the machine in the CAM, post → done | export dialog only; preview Cartesian | load XYZ code directly; AXIS preview correct |

## Recommendation
- **Do not move the logic into LinuxCNC.** The reasons the pre-processor exists (pole strategies, C speed near the centre,
  G93) need look-ahead and joint-aware planning, which the 2.9 real-time path does not have. rosekins can be used in
  the vismach simulator to *compare*, never for cutting. Revisit only if a released LinuxCNC planner uses the Jacobian
  to respect joint limits.
- **One core, several front ends.** The JavaScript core stays the reference; the golden tests become a
  language-neutral specification (input + options → expected output). Front ends: the web page (now), a FreeCAD
  addon (Python port checked against the same tests — the long-term "polar setting inside the CAM"), optionally the
  Kiri hook on a self-hosted Kiri.
- **FreeCAD is the long-term home** (machine definition `.fcm` + post class, `POST_TRANSFORM` slot reserved upstream,
  Addon Manager, LGPL subclassing allows an MIT addon). Kiri only if its author wants it.

## Roadmap
0. **Prove on the machine** (before any port): E-stop; install the delivered `.ini`; C direction check; air cut; F test
   cut; aluminium part measured and photographed. Merge PR #6 (2.11.2).
1. **Finish the core:** exact arcs around the centre; the rare 0.0268 mm near the pole; simulator deviation + axis-speed
   colouring; cycle-time estimate (proposals in `research-2026-10-11.md`).
2. **Freeze the spec:** document `convert(text, options)` and its options; export the golden/edge cases as JSON fixtures.
3. **FreeCAD addon "Polar XZC":** Python port of the core, `.fcm` machines (XZC, XZC+B), `PostProcessor` subclass
   (`_expand_postprocessor_commands`, `get_property_schema`), CI running the same fixtures; publish via Addon Manager;
   ask sliptonic / Billy Huddleston about non-XYZ chains, `POST_TRANSFORM`, G93, rotary in CAM Sim.
4. **Tilt axis B** when the hardware exists (config first, then layout `xzcb` tests on the machine).
5. Kiri: hook + contact the author with photos, if wanted.
