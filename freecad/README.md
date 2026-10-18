# Polar CNC for FreeCAD

Polar (XZC) face machining from the FreeCAD **CAM** workbench. You make a normal CAM Job, and **Post Process**
writes polar G-code: X radius, C chuck, Z depth, with G93 inverse-time feed. The conversion is done by the same
converter as the [web page](https://marioskiv.github.io/polar-cnc-converter/), so both always give the same
result.

> [!IMPORTANT]
> **Status: first version, in testing.** The same rules as for the web page apply: cut in the air first, check
> the rotary direction, keep a hand on the E-stop.

Needs FreeCAD 1.1 or newer (tested on 26.3). Nothing else to install.

## Install

FreeCAD → **Tools → Addon Manager** → ⚙ (settings) → **Custom repositories** → add
`https://github.com/Marioskiv/polar-cnc-converter`, branch `main`. Then install **PolarCNC** and restart
FreeCAD.

## Use

1. Draw the part with its **face centre at X0 Y0**: that point is the chuck axis. Make the CAM Job as usual
   (stock, tool controllers with **feeds**, operations).
2. Select the Job and click **Polar machine settings** (toolbar *Polar CNC* in the CAM workbench). This adds a
   **Polar CNC** group to the Job's properties and chooses the `polar_linuxcnc` post-processor.
3. In the Job's properties, group **Polar CNC**, set:
   - **Polar X Max**: the largest X your machine can reach (its X soft limit). Required.
   - **Polar Cutting Side**: one side of the centre, or both sides (then **Polar Past Centre**: how far).
   - **Polar Profile** (optional): a `.polar-profile.json` saved from the web page (rotary letter, directions,
     X as diameter, chord tolerance).
4. **Polar simulation** (second button on the *Polar CNC* toolbar) plays the polar program — exactly what Post
   Process writes, read back the way LinuxCNC moves the axes:
   - *Machine view*: the part turns with the chuck and the cutter only moves in X and Z, as on the machine;
   - *Part view*: the part stands still and the cutter moves over it — compare it with the CAM paths.

   It shows the program time, how many turns the chuck makes, the fastest chuck speed the program asks for, and
   for every moment the line, X, C, Z and the chuck speed. Play, pause, scrub, speed 1× … 500×. Close puts the
   document back as it was.
5. **Post Process**. If something cannot be converted safely, no file is written and the message names the line,
   exactly as on the web page.

The operations stay normal CAM operations, so FreeCAD shows and simulates them as usual. The polar conversion
happens only when the G-code is written.

## Which operations suit polar machining

The chuck turns and the cutter only moves in X and Z. Close to the centre the chuck must turn very fast to keep
the feed; it cannot, so the controller slows the cut there. Commercial CAM systems therefore offer 2D / 2.5D
operations on a polar face (contour, pocket, facing, drilling) and no 3D surfacing. In a **polar Job** the addon
does the same:

| | Operations |
|---|---|
| **Offered** | Profile, Pocket (**Offset** by default), Facing (**Spiral** by default), Drilling, Helix, Engrave |
| **Offered, with a warning** | Adaptive (many direction changes of the chuck, large files: pockets away from the centre), V-carve (Z moves together with many direction changes), Slot, Deburr, Thread milling (fine away from the centre) |
| **Greyed out** | 3D Pocket, 3D Surface, Waterline, Planar / Rotary Surface (3D), Probe (probing is not converted) |

- The defaults are the Job's own *Operation defaults* (SetupSheet), set by *Polar machine settings*; they apply
  to operations made after that. Operations that were already there are checked once and reported.
- If a pattern that crosses the face line by line is chosen (ZigZag, Line, Grid, ZigZag Offset; Facing ZigZag,
  Bidirectional, Directional), a warning appears in the Report view and the status bar — never a dialog. The same
  for the dressups AxisMap, Drag knife and Z correction, and for a Drilling operation set to Tapping (the converter
  refuses tapping cycles).
- Greying out follows the Job CAM would put a new operation in: the selected Job, the Job of the selected
  operation, or the only Job of the document. Ordinary Jobs keep every operation.
