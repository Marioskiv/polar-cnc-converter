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

CMD=$(dirname "$FREECAD")/freecadcmd

# the chuck, 4-jaw chuck and faceplate with clamps
HOME="$OUT/home" PC_OUT="$OUT/ch" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/chuck_test.py" > "$OUT/freecad-ch.log" 2>&1
cat "$OUT/ch/log.txt" 2>/dev/null
chr=$(cat "$OUT/ch/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-ch.log)")
echo "chuck: $chr"
[ "$chr" = "RESULT: PASS" ] || result="$result; chuck $chr"

# Polar Wrap's drop-cutter against OpenCAMLib (FreeCAD's own rotary drop-cutter), and the seam,
# cone, leftover and grid checks (FreeCADCmd)
HOME="$OUT/home" PC_OUT="$OUT/wrapocl" PC_REPO="$REPO" "$CMD" "$REPO/tests/freecad/wrap_ocl_test.py" \
    > "$OUT/freecad-wrapocl.log" 2>&1
grep -v "^ok" "$OUT/wrapocl/log.txt" 2>/dev/null
wo=$(cat "$OUT/wrapocl/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-wrapocl.log)")
echo "wrap vs OpenCAMLib: $wo"
[ "$wo" = "RESULT: PASS" ] || result="$result; wrap vs OpenCAMLib $wo"

# Polar Wrap geometry without the GUI (solid and STL, the cutter never in the part)
HOME="$OUT/home" PC_OUT="$OUT/wrapgeo" PC_REPO="$REPO" "$CMD" "$REPO/tests/freecad/wrapcut_geometry_test.py" \
    > "$OUT/freecad-wrapgeo.log" 2>&1
cat "$OUT/wrapgeo/log.txt" 2>/dev/null
wg=$(cat "$OUT/wrapgeo/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-wrapgeo.log)")
echo "wrap geometry: $wg"
[ "$wg" = "RESULT: PASS" ] || result="$result; wrap geometry $wg"

# a Wrap Job (router radial): the real 3D part, Polar Wrap, chuck, Post Process, simulator
HOME="$OUT/home" PC_OUT="$OUT/wrap" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/wrap_test.py" > "$OUT/freecad-wrap.log" 2>&1
cat "$OUT/wrap/log.txt" 2>/dev/null
wr=$(cat "$OUT/wrap/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-wrap.log)")
echo "wrap: $wr"
[ "$wr" = "RESULT: PASS" ] || result="$result; wrap $wr"

# the chuck from one click (the face that goes into the chuck), and every usual CAM operation in
# a polar Job end to end (made, checked against the chuck, Post Process, simulator), and the cut
# check: the final polar program followed point by point against the part and the chuck
for t in setup ops cut_check old_file wrap_relief; do
    HOME="$OUT/home" PC_OUT="$OUT/$t" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
        "$FREECAD" "$REPO/tests/freecad/${t}_test.py" > "$OUT/freecad-$t.log" 2>&1
    grep -v "^ok" "$OUT/$t/log.txt" 2>/dev/null
    r=$(cat "$OUT/$t/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-$t.log)")
    echo "$t: $r"
    [ "$r" = "RESULT: PASS" ] || result="$result; $t $r"
done

# the help: popups on the toolbar, field help, error cards, Greek and English
HOME="$OUT/home" PC_OUT="$OUT/help" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
    "$FREECAD" "$REPO/tests/freecad/help_test.py" > "$OUT/freecad-help.log" 2>&1
cat "$OUT/help/log.txt" 2>/dev/null | grep -v "^ok"
hr=$(cat "$OUT/help/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-help.log)")
echo "help: $hr"
[ "$hr" = "RESULT: PASS" ] || result="$result; help $hr"

# Knurling & Wrap (the Part Design tools in cad/): Knurl, Wrap on a cylinder, and a file made while
# they were part of WikiTips (opened with no WikiTips installed)
for t in knurl cyl_wrap knurlwrap_old_file; do
    HOME="$OUT/home" PC_OUT="$OUT/$t" PC_REPO="$REPO" xvfb-run -a -s "-screen 0 1600x1000x24" \
        "$FREECAD" "$REPO/tests/freecad/${t}_test.py" > "$OUT/freecad-$t.log" 2>&1
    r=$(grep -h "^RESULT" "$OUT/$t/result.txt" 2>/dev/null || echo "RESULT: no result (see $OUT/freecad-$t.log)")
    grep -h "^FAIL" "$OUT/$t/result.txt" "$OUT/$t/log.txt" 2>/dev/null
    echo "$t: $r"
    [ "$r" = "RESULT: PASS" ] || result="$result; $t $r"
done

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
