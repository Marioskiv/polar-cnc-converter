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
4. **Polar simulation** (last button on the *Polar CNC* toolbar) plays the polar program — exactly what Post
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

## Help inside FreeCAD (Greek or English)

- **Hover** over a button of the *Polar CNC* toolbar: a card shows what it does, a short animation recorded in
  FreeCAD, the numbered steps (the same numbers as in the animation) and what to watch out for.
- In the **Polar Face** and **Polar Wrap** panels every field has a **?** button with its explanation.
- When something is refused (Post Process, the simulator, a missing tool), an **error card** says what happened,
  **why**, and **what to do**, with the original message below it (button *Copy* for asking for help).
- Language: Greek when FreeCAD is in Greek, otherwise English. The **?** button at the end of the toolbar
  (*Polar CNC help language*) chooses Greek, English, automatic, or no popups (the plain tooltips again).

The texts are in `freecad/help/help.json`; the animations are made by `tools/help_gifs/record.py` (in a real
FreeCAD, with the addon's own chuck, Polar Face, Polar Wrap and simulator) and `tools/help_gifs/compose.py`.

## Wrap: the outside of the part (router radial)

Turn the router so that it looks at the part (the machine axes stay as they are: X radius, Z along the part, C the
chuck). **Nothing is drawn flat**: the part is used as it is.

1. Make the part (a solid, or import an STL) with its **axis on Z through X0 Y0**, its **lower end in the chuck**.
2. Make the Job, click **Polar machine settings**, then in the Job's properties set **Polar Layout = Wrap** and
   **Polar Wrap Diameter** = the diameter of the bar in the chuck.
3. **Chuck** (optional, recommended): choose your chuck and the *Grip length*.
4. **Polar Wrap** (Polar CNC toolbar): the part is unrolled automatically — its radius round the axis is mapped
   on a fine grid (*Resolution*, 0.25 mm) — and the cutter runs **helices round it**, from the free end toward the
   chuck: **roughing** layers from the stock diameter down (*Step down*, leaving *Finish allowance*), then a
   **finishing** pass on the part (*Finish step over*; small with a ball end for a smooth surface). Flat and ball
   end mills; the cutter never goes into the part (checked against the solid in the tests). It stops clear of the
   jaws (*Chuck clearance* + the cutter radius) and runs past the free end by the cutter radius.
   - Roughing cuts each layer only where it removes material; over the part where it touches nothing it goes
     faster (*Air feed*); the layers turn the chuck one way and back, so C does not pile up turns.
   - Finishing: **Helix round the part** (one continuous cut, a full turn at each end; the best surface on round
     shapes) or **Lines along the part** (better for steps, grooves and flats along the axis).
   - Refused, with a message: finishing alone deeper than *Finish allowance* + *Step down*; a part bigger than
     the stock diameter; inches (`--inches`).
5. **Polar simulation** shows the part, the chuck and the router radial; **Post Process** writes the wrapped program
   (G93, X = radius, C round, Z along) and refuses it if the router would run into the chuck (often a rapid next to
   the jaws).

**Tool length in Wrap:** the router lies sideways, so its length runs along X. Put each tool's length in the **X
column** of the LinuxCNC tool table and tick the Job's **Polar Wrap Tool Length In X**; until then a program with
G43 is refused (it would shift everything along the part).

In a Wrap Job only Polar Wrap operations are used (the other CAM operations work on a flat face; they are warned
about and Post Process refuses them). Undercuts (a groove narrower than the cutter, a wall leaning over) are cut
only as far as the cutter fits. The web page keeps its own Wrap input: a program of the surface drawn flat, from any
CAM.

## Polar Face: facing any stock without cutting air

The stock in the chuck is often not round: square or hexagon bar, a plate, a casting, held off the centre in a
4-jaw chuck. **Polar Face** (on the *Polar CNC* toolbar) faces it from the stock top down to the part
top (or the depths you set), at every depth only where the stock really is:

- circles round the chuck axis, from the outside in, each cut only where it meets material. On a polar machine
  such a circle is a pure turn of the chuck at constant X — its smoothest move — and the converter writes it with no
  error; inside the largest circle that fits in the stock it is one continuous cut;
- where a circle leaves the stock (the corners of a square) the cutter goes on round the same circle — fast where
  it reaches nothing, at the cutting feed where it still touches material that later circles will cut — or lifts,
  whichever is quicker. A straight move at depth is never used to link two cuts (a chord runs inside the circle,
  where material may be). It goes down where it reaches nothing and comes into the material along the circle,
  never by plunging into it where it can avoid it;
- the part (everything of it at or above the depth being cut) is never touched; *Stock to leave* keeps a skin round
  it; the last pass runs straight into the centre (X only), where no circle could keep the feed.

Measured (`tests/freecad/polarface_geometry_test.py`, Ø6 cutter, step 40 %): nothing left uncut, the part never
touched, no fast move over uncut material, and compared with full circles over the whole swept circle the time is
16–21 % shorter on round stock, 37–41 % on a square, 44–46 % on a square turned and off the centre, 33–36 % on a
hexagon and 58–60 % on a plate off the centre.

## The chuck, the 4-jaw chuck and the faceplate

Select the Job and click **Chuck** (*Polar CNC* toolbar). A list opens: pick a catalogue chuck, or
**Custom (my own sizes)** and type the sizes in the chuck's properties. Click **Chuck** again at any time to change
it; the choice is also the chuck's **Preset** property.

| Preset | What |
|---|---|
| 4-jaw SAN OU K72-125 | the default: 4 independent jaws, Ø125, body 56 (SAN OU K72 table); jaws 21.7 above the face, 56 long, 18 wide (measured on a real chuck) |
| 4-jaw SAN OU K12-125 | 4 jaws that move together (self-centring), Ø125, body 58, jaws 26 above the face (H 84 − H1 58) |
| 3-jaw SAN OU 125 | Ø125, body 58 |
| 3-jaw SC-3 … SC-16 | self-centring scroll chuck, sizes from the usual catalogue table |
| 4-jaw 12in … 24in | independent jaws: each jaw closes on the stock by itself, so square and off-centre stock is held |
| Faceplate Ø250 / Ø400 | a plate; the work is held by clamps that you place |

Catalogue letters: **A** diameter, **B** body thickness, **H** jaw length (radial), **J** jaw width,
**K** jaw height above the face (the one that matters for collisions — measure your own chuck), **L** step.
For the SAN OU presets the tables give the body, but not always the jaw height above the face, the jaw length
and width: for the K12-125 and the 3-jaw 125 those were scaled from the catalogue drawings (3-jaw 125: 18 / 39 / 14 mm).
Measure your chuck and correct them. *Grip length* is how much of the stock the jaws hold; *First jaw angle* turns the jaws.

- The jaws always close on the real stock. A self-centring chuck (3 or 4 jaws that move together) holds only
  stock that it can centre: a 3-jaw not a square, a 4-jaw self-centring not a rectangle or an off-centre stock.
  The chuck's *Notes* then say so (use a 4-jaw chuck with independent jaws).
- **Faceplate**: select the chuck and click **Add clamp** for each clamp. Give its *Angle* (where round the plate) and
  change *Length*, *Width*, *Overlap* if you like; it reaches the stock edge by itself and follows the stock if it
  changes.
- **Polar Face** keeps *Chuck clearance* (default 2 mm) away from jaws and clamps; the simulator shows the chuck
  turning with the part (jaws and clamps in red).

- An operation that cuts lower than the top of the jaws (or clamps) gets a warning in the Report view and when
  posting: the cutter keeps clear of them, but the collet nut and spindle are not checked, so the cutter must stick
  out of the nut more than the depth shown.

- **Round stock: the jaws are checked as a ring.** A round bar can be clamped with the jaws at any angle, and
  nothing ties C0 on the machine to them, so below the jaw tops (+ clearance) nothing is cut beside the jaws all
  the way round. Tick the chuck's **Jaws At Known Angle** only if you set C0 so that the jaws really are where the
  CAM shows them. (Square, hexagon or off-centre stock: the jaws are where they grip it.)
- The clearance holds in height too: a cut at the jaw tops would rub them.
- **Every operation is checked against the chuck** (Profile, Pocket, Drilling, … and their rapid moves): the
  cutter, tip and everything above it, against the body, the jaws and the clamps. A hit is reported in the Report
  view, and **Post Process writes no file** and names the operation, the move and the place. Post Process then
  checks the polar program itself, as the machine moves it (a rapid curves between its end points).

Not done yet: the jaws' angle on the machine is not tied to C0 (see *Open items* in
[docs/FREECAD.md](../docs/FREECAD.md)).

## Which operations suit polar machining

The chuck turns and the cutter only moves in X and Z. Close to the centre the chuck must turn very fast to keep
the feed; it cannot, so the controller slows the cut there. Commercial CAM systems therefore offer 2D / 2.5D
operations on a polar face (contour, pocket, facing, drilling) and no 3D surfacing. In a **polar Job** the addon
does the same:

| | Operations |
|---|---|
| **Offered** | **Polar Face** (below), Profile, Pocket (**Offset** by default), Drilling, Helix, Engrave |
| **Offered, with a warning** | Adaptive (many direction changes of the chuck, large files: pockets away from the centre), V-carve (Z moves together with many direction changes), Slot, Deburr, Thread milling (fine away from the centre) |
| **Greyed out** | FreeCAD's Facing (it covers the stock's bounding rectangle: on round stock 40 % of its path is in the air — use Polar Face), 3D Pocket, 3D Surface, Waterline, Planar / Rotary Surface (3D), Probe (probing is not converted) |

- The defaults are the Job's own *Operation defaults* (SetupSheet), set by *Polar machine settings*; they apply
  to operations made after that. Operations that were already there are checked once and reported.
- If a pattern that crosses the face line by line is chosen (ZigZag, Line, Grid, ZigZag Offset; Facing ZigZag,
  Bidirectional, Directional), a warning appears in the Report view and the status bar — never a dialog. The same
  for the dressups AxisMap, Drag knife and Z correction, and for a Drilling operation set to Tapping (the converter
  refuses tapping cycles).
- Greying out follows the Job CAM would put a new operation in: the selected Job, the Job of the selected
  operation, or the only Job of the document. Ordinary Jobs keep every operation.
