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
4. **Post Process**. If something cannot be converted safely, no file is written and the message names the line,
   exactly as on the web page.

The operations stay normal CAM operations, so FreeCAD shows and simulates them as usual. The polar conversion
happens only when the G-code is written.

## Which operations suit polar machining

The chuck turns and the cutter only moves in X and Z. Close to the centre the chuck must turn very fast to keep
the feed, so the controller slows down there.

| | Operations |
|---|---|
| **Best** | Drilling and Helix (a position, then Z); **Facing with the Spiral pattern** (stock centred on X0 Y0) and 3D Surface with the Circular / Spiral pattern, *Pattern Center At* = Custom X0 Y0 (the chuck turns steadily, the feed stays even); Profile of shapes away from the centre (a circle round the centre is a pure C turn); Engrave / V-carve |
| **Good, with care** | Pocket with the **Offset** pattern (crosses the centre correctly, but slowly); Adaptive (works, but many short moves make the chuck reverse often: large files, away from the centre only); Slot, Deburr, Thread milling away from the centre |
| **Avoid** | **ZigZag / Line patterns** (Pocket, Facing, Surface): every pass crosses the face, the chuck reverses at each line and crawls near the centre — use Spiral or Offset instead. Tapping and cutter compensation in the machine (G41/G42) are refused by the converter |
