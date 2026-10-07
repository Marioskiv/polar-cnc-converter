# ==============================================================================
# AXIS customisations for THIS machine configuration only.
#
# Loaded through  [DISPLAY] USER_COMMAND_FILE = axis_user.py  (same folder as
# the INI). Unlike ~/.axisrc it does not affect other configurations, e.g. the
# vismach simulation. AXIS runs this file just before showing its window; if
# it contains an error, AXIS shows an error dialog and carries on.
#
# What it does: lists the PS4/PS5 gamepad controls (gamepad.hal) under
# Help > Quick Reference, so they are always at hand at the machine.
# It does not change any behaviour.
#
# Deliberately NOT included: the "Ctrl+Q = quit" shortcut from the LinuxCNC
# documentation. It closes LinuxCNC at once, skipping the "really quit?"
# question, so one stray key press would stop a running job.
# ==============================================================================

help2.extend([
    ("", ""),
    ("GAMEPAD", "gamepad.hal  (needs Home All)"),
    ("L1 (hold)", "Jog enable - nothing moves without it"),
    ("R1 (hold)", "Fast jog speed"),
    ("Left stick <->", "Z"),
    ("Right stick up/down", "X  (down = +X, away from the switch)"),
    ("L2 / R2", "C+ / C-  (press further = faster)"),
    ("L1 + Share", "Home All"),
    ("L1 + D-pad down", "Touch off Z0 here (G10 L20 P0 Z0)"),
    ("Cross / Circle", "Machine on / off"),
    ("Triangle / Square", "Router start / stop"),
    ("Options / PS", "E-stop / E-stop reset"),
])
