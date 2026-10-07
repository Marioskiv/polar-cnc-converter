#!/usr/bin/env python3
#
# Polar CNC — vismach 3D model of the XZC lathe conversion.
#
# LinuxCNC drives this model straight from the JOINT positions (X radius,
# Z axial, C chuck angle), exactly like the official configs/sim/axis/vismach
# examples. So what you see here is LinuxCNC's own trajectory planner — real
# accelerations, blending, G53/G28 semantics — not a re-interpretation.
# The tool path is plotted on the stock face and turns with the chuck.
#
# Machine (from the machine's .ini): spindle axis = Z; X = radius, 0 on the
# chuck centreline; Z home switch at the TAILSTOCK end (positive), so machine
# Z grows AWAY from the chuck. The router points at the chuck (-Z).
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT

from vismach import *
import hal

# ---- Adjust to your setup (machine coordinates, mm) -------------------------
FACE_Z   = -490.0   # machine Z of the stock FRONT face. Set G54 Z to the same
                   # value (README) so that work Z0 is the stock face.
STOCK_R  = 60.0    # stock radius
STOCK_T  = 30.0    # stock thickness (protrusion from the jaws)
CHUCK_R  = 80.0    # chuck body radius
CHUCK_T  = 50.0    # chuck body length
TOOL_D   = 6.0     # cutter diameter
C_SIGN   = -1.0    # the part turns by -C about +Z: C = theta brings the point
                   # at angle theta to the tool on +X (the converter's
                   # convention). Your real chuck must turn the same way —
                   # check with an asymmetric test cut (README).
# -----------------------------------------------------------------------------

# HAL: LinuxCNC 2.9 names the float type HAL_FLOAT, newer versions HAL_REAL.
PIN_REAL = getattr(hal, 'HAL_REAL', None)
if PIN_REAL is None:
    PIN_REAL = hal.HAL_FLOAT

c = hal.component("polarlathe")
c.newpin("jointX", PIN_REAL, hal.HAL_IN)
c.newpin("jointZ", PIN_REAL, hal.HAL_IN)
c.newpin("jointC", PIN_REAL, hal.HAL_IN)
c.ready()

# ---- Rotating group: chuck, jaws, stock, and the work reference --------------
chuck = CylinderZ(FACE_Z - STOCK_T - CHUCK_T, CHUCK_R, FACE_Z - STOCK_T, CHUCK_R)
chuck = Color([0.55, 0.55, 0.6, 1], [chuck])
jaws = []
for k in range(3):                       # three jaws, 120 deg apart
    jaw = Box(STOCK_R, -8, FACE_Z - STOCK_T - 12, STOCK_R + 22, 8, FACE_Z - STOCK_T + 8)
    jaws.append(Rotate([jaw], 120 * k, 0, 0, 1))
jaws = Color([0.35, 0.35, 0.4, 1], jaws)
stock = CylinderZ(FACE_Z - STOCK_T, STOCK_R, FACE_Z, STOCK_R)
stock = Color([0.75, 0.8, 0.9, 1], [stock])
mark = Box(STOCK_R - 10, -1.5, FACE_Z, STOCK_R, 1.5, FACE_Z + 0.5)   # C = 0 marker on the face
mark = Color([1, 0.3, 0.1, 1], [mark])
work = Capture()                          # backplot is drawn relative to this
work_on_face = Translate([work], 0, 0, FACE_Z)
spindle = Collection([chuck, jaws, stock, mark, work_on_face])
spindle = HalRotate([spindle], c, "jointC", C_SIGN, 0, 0, 1)

headstock = Box(-130, -130, FACE_Z - STOCK_T - CHUCK_T - 120, 130, 130, FACE_Z - STOCK_T - CHUCK_T)
headstock = Color([0.25, 0.3, 0.35, 1], [headstock])

# ---- Moving group: router on the carriage ------------------------------------
tooltip = Capture()                       # the controlled point (tool tip)
cutter = CylinderZ(0, TOOL_D / 2, 25, TOOL_D / 2)
cutter = Color([1, 0.85, 0.1, 1], [cutter])
collet = CylinderZ(25, 9, 45, 12)
motor = CylinderZ(45, 35, 175, 35)
router = Color([0.15, 0.15, 0.18, 1], [collet, motor])
clamp = Box(-40, -45, 70, 40, 45, 130)
clamp = Color([0.3, 0.5, 0.8, 1], [clamp])
head = Collection([tooltip, cutter, router, clamp])
head = HalTranslate([head], c, "jointX", 1, 0, 0)       # X: radius, cross-slide
cross = Box(-30, -60, 130, 200, 60, 150)                 # cross-slide (moves in Z only)
cross = Color([0.3, 0.5, 0.8, 1], [cross])
carriage = Collection([head, cross])
carriage = HalTranslate([carriage], c, "jointZ", 0, 0, 1)  # Z: along the bed

bed = Box(-60, -150, FACE_Z - 220, 260, -130, FACE_Z + 650)
bed = Color([0.2, 0.22, 0.25, 1], [bed])

model = Collection([headstock, spindle, carriage, bed])
main(model, tooltip, work, size=600, lat=-55, lon=35)
