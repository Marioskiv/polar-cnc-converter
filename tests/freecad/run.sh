#!/bin/sh
# Polar CNC — run the FreeCAD addon test in a real FreeCAD (not part of `npm test`: needs FreeCAD).
#
#   FREECAD=/path/to/bin/freecad sh tests/freecad/run.sh
#
# Uses a throw-away FreeCAD user folder with this repository installed as the PolarCNC addon,
# then converts FreeCAD's own LinuxCNC output with the Node converter and compares.
#
# Copyright (c) 2026 Marioskiv
# https://github.com/Marioskiv/polar-cnc-converter
# SPDX-License-Identifier: MIT
set -u
FREECAD=${FREECAD:-freecad}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${OUT:-/tmp/polarcnc-freecad-test}
rm -rf "$OUT"
mkdir -p "$OUT/home"
VER=$("$FREECAD" --version 2>/dev/null | sed -n 's/.* \([0-9][0-9]*\)\.\([0-9][0-9]*\).*/v\1-\2/p' | head -1)
MOD="$OUT/home/.local/share/FreeCAD/${VER:-v26-3}/Mod"
mkdir -p "$MOD"
ln -s "$REPO" "$MOD/PolarCNC"

HOME="$OUT/home" PC_OUT="$OUT/run" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/polar_post_test.py" > "$OUT/freecad.log" 2>&1
cat "$OUT/run/log.txt" 2>/dev/null
result=$(cat "$OUT/run/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad.log)")

# the simulator, in its own FreeCAD start (one task dialog per start)
HOME="$OUT/home" PC_OUT="$OUT/sim" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/simulator_test.py" > "$OUT/freecad-sim.log" 2>&1
cat "$OUT/sim/log.txt" 2>/dev/null
sim=$(cat "$OUT/sim/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-sim.log)")
echo "simulator: $sim"
[ "$sim" = "RESULT: PASS" ] || result="$result; simulator $sim"

# Polar Face: its geometry without the GUI (FreeCADCmd), then in the GUI with square stock
CMD=$(dirname "$FREECAD")/freecadcmd
HOME="$OUT/home" PC_OUT="$OUT/pfgeo" PC_REPO="$REPO" "$CMD" "$REPO/tests/freecad/polarface_geometry_test.py" \
    > "$OUT/freecad-pfgeo.log" 2>&1
cat "$OUT/pfgeo/log.txt" 2>/dev/null
pfgeo=$(cat "$OUT/pfgeo/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-pfgeo.log)")
echo "polar face geometry: $pfgeo"
[ "$pfgeo" = "RESULT: PASS" ] || result="$result; polar face geometry $pfgeo"
HOME="$OUT/home" PC_OUT="$OUT/pf" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/polarface_test.py" > "$OUT/freecad-pf.log" 2>&1
cat "$OUT/pf/log.txt" 2>/dev/null
pfr=$(cat "$OUT/pf/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-pf.log)")
echo "polar face: $pfr"
[ "$pfr" = "RESULT: PASS" ] || result="$result; polar face $pfr"

# the chuck, 4-jaw chuck and faceplate with clamps
HOME="$OUT/home" PC_OUT="$OUT/ch" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/chuck_test.py" > "$OUT/freecad-ch.log" 2>&1
cat "$OUT/ch/log.txt" 2>/dev/null
chr=$(cat "$OUT/ch/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-ch.log)")
echo "chuck: $chr"
[ "$chr" = "RESULT: PASS" ] || result="$result; chuck $chr"

same="no"
if [ -f "$OUT/run/cartesian.ngc" ] && [ -f "$OUT/run/polar.ngc" ]; then
    node "$REPO/tests/freecad/compare.js" "$OUT/run" && same="yes"
fi
echo "FreeCAD output identical to the Node converter on the same program: $same"
echo "$result"
case "$result $same" in
    "RESULT: PASS yes") exit 0 ;;
    *) exit 1 ;;
esac
