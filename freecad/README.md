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

1. Draw the part with its **face centre at X0 Y0**: that point is the chuck axis. **Z0 = the stock top** (the face
   you touch the cutter off on; the program header says where the top is if it is not at Z0). Make the CAM Job as
   usual (stock, tool controllers with **feeds**, operations).
2. Select the Job and click **Machining type** (first button of the *Polar CNC* toolbar in the CAM workbench).
   Choose **Ordinary CAM**, **Polar** (the chuck turns, the router looks at the face) or **Wrap** (the router turned
   to a bar). It sets the post-processor and adds a **Polar CNC** group to the Job's properties. In a polar Job
   you make the operations with **FreeCAD's own tools** (Face, Pocket, Profile, Drilling, Helix…): nothing is
   greyed out and nothing is changed for you; each operation is **checked as soon as it is made** (see *Checked
   when made* below). **Ordinary CAM** takes the Job back: the Polar CNC settings go and its former post-processor
   comes back.
3. The settings (dialog, or the Job's properties, group **Polar CNC**):
   - **Polar X Max**: the largest X your machine can reach (its X soft limit). Required.
   - **Polar Wrap X Max** (Wrap): the largest X of the machine's Wrap profile (the router turned has its own travel
     and X zero); 0 = the same as Polar X Max.
   - **Polar Cutting Side**: one side of the centre, or both sides (then **Polar Past Centre**: how far).
   - **Polar Profile** (optional): a `.polar-profile.json` saved from the web page (rotary letter, directions,
     X as diameter, chord tolerance).
   - **Polar C Max Velocity** (optional): the C axis top speed, degrees per second (`MAX_VELOCITY` of the C joint
     in the LinuxCNC `.ini`). With it, each operation says how much slower it will run near the centre.
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
  FreeCAD, the numbered steps (the step playing in the animation is lit) and what to watch out for. The card is
  30 % of the screen wide (400–540 px); the animations are 1248 × 750, so they stay sharp on any screen.
- In the **Polar Wrap** panel every field has a **?** button with its explanation.
- When something is refused (Post Process, the simulator, a missing tool), an **error card** says what happened,
  **why**, and **what to do**, with the original message below it (button *Copy* for asking for help).
- Language: Greek when FreeCAD is in Greek, otherwise English. The **?** button at the end of the toolbar
  (*Polar CNC help language*) chooses Greek, English, automatic, or no popups (the plain tooltips again).

The texts are in `freecad/help/help.json`; the animations are made by `tools/help_gifs/record.py` (in a real
FreeCAD at 150 % scale, with the addon's own chuck, Polar Wrap and simulator) and
`tools/help_gifs/compose.py` (one shared 256-colour palette, as WikiTips does). The pictures have no words, only the
step numbers, so one animation serves every language.

## Wrap: the outside of the part (router radial)

Turn the router so that it looks at the part (the machine axes stay as they are: X radius, Z along the part, C the
chuck). **Nothing is drawn flat**: the part is used as it is.

1. Make the part (a solid, or import an STL) with its **axis on Z through X0 Y0**, its **lower end in the chuck**.
2. Make the Job, click **Machining type**, choose **Wrap**, enter the **bar diameter** and the Wrap X Max. In a
   Wrap Job every other operation is greyed out: the whole job is done with Polar Wrap.
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

## Checked when made

In a polar Job every operation is checked as soon as it is made or changed (OK or Apply in its panel), alone, the
way Post Process will write it: FreeCAD's LinuxCNC output for it, converted to **X C Z** by the same converter as the
web page, then read back the way LinuxCNC moves the joints.

- **It will crash** (the cutter or a rapid move runs into a jaw, a clamp or the chuck body), **it cannot be written
  as polar G-code** (the converter refuses it: e.g. X past X Max), or a **Y** is left in the polar output: a card
  says so, in Greek or English, and **Post Process refuses to write the program** until it is fixed. Nothing in the
  operation is changed for you.
- **Not recommended for polar** (a warning in the Report view and the status bar, never a dialog): patterns that
  cross the face line by line (ZigZag, Line, Grid, ZigZag Offset; Face Bidirectional / Directional), with the
  ring-shaped pattern to use instead when this FreeCAD offers one; FreeCAD's Face (it covers the stock's bounding
  rectangle: on round stock about 40 % of its path is in the air, and its lines are slow near the centre); Adaptive,
  V-carve, Slot, Deburr, Thread milling, 3D Surface, Waterline; a cut below the jaw tops (the collet nut is not
  checked); and, with *Polar C Max Velocity* set, how much slower the C axis makes the operation.
- A polar Job whose post-processor is not `polar_linuxcnc` is warned about: Post Process would write X Y Z, not X C Z.

## The chuck, the 4-jaw chuck and the faceplate

**One click:** click the face of the part (or of the stock) that goes **into** the chuck, then **Chuck**.

1. The Job's copy of the part (and a stock of its own) is turned so that face looks down, put on the chuck axis
   (the centre of round stock, else the middle of its outline) and moved so the **stock top is Z0**.
2. The chuck that holds this stock is chosen from **your chucks** (the SAN OU K11-125 3-jaw for round stock that
   fits it, the K72-125 4-jaw with independent jaws for square or odd shapes; a catalogue chuck if neither holds it),
   and the **grip** is the stock under the part (up to the jaw height), so the cutter never has to go there.
3. A small window shows what was found and lets you change the chuck or the grip. OK makes the chuck; Cancel (or
   Ctrl+Z afterwards) puts everything back as it was.

With no face clicked, **Chuck** says what to click, or lets you choose a catalogue chuck by hand (type, then size);
an existing chuck is changed the same way. Your chucks are the preference `Mod/PolarCNC/MyChucks` (one preset name
per line).

| Preset | What |
|---|---|
| 4-jaw SAN OU K72-125 | the default: 4 independent jaws, Ø125, body 56 (SAN OU K72 table); jaws 21.7 above the face, 56 long, 18 wide (measured on a real chuck) |
| 4-jaw SAN OU K12-125 | 4 jaws that move together (self-centring), Ø125, body 58, jaws 26 above the face (H 84 − H1 58) |
| 3-jaw SAN OU K11-125 | 3 jaws that move together, Ø125, body 58 (K11 table: H 84 − H1 58), bore Ø30; jaws 25.5 above the face, 53 long, 16 wide (measured). Holds Ø2.5–40 with the normal jaws, Ø38–110 reversed: the chuck says so when the stock needs the reversed jaws |
| 3-jaw SC-3 … SC-16 | self-centring scroll chuck, sizes from the usual catalogue table |
| 4-jaw 12in … 24in | independent jaws: each jaw closes on the stock by itself, so square and off-centre stock is held |
| Faceplate Ø250 / Ø400 | a plate; the work is held by clamps that you place |

Catalogue letters: **A** diameter, **B** body thickness, **H** jaw length (radial), **J** jaw width,
**K** jaw height above the face (the one that matters for collisions — measure your own chuck), **L** step.
For the SAN OU presets the tables give the body, but not always the jaw height above the face, the jaw length
and width: the K72-125 and K11-125 ones were measured on real chucks, the K12-125 ones scaled from the drawings.
Measure your chuck and correct them. *Grip length* is how much of the stock the jaws hold; *First jaw angle* turns the jaws.

- The jaws always close on the real stock. A self-centring chuck (3 or 4 jaws that move together) holds only
  stock that it can centre: a 3-jaw not a square, a 4-jaw self-centring not a rectangle or an off-centre stock.
  The chuck's *Notes* then say so (use a 4-jaw chuck with independent jaws).
- **Faceplate**: select the chuck and click **Add clamp** for each clamp. Give its *Angle* (where round the plate) and
  change *Length*, *Width*, *Overlap* if you like; it reaches the stock edge by itself and follows the stock if it
  changes.
- The simulator shows the chuck turning with the part (jaws and clamps in red).

- An operation that cuts lower than the top of the jaws (or clamps) gets a warning in the Report view and when
  posting: the cutter keeps clear of them, but the collet nut and spindle are not checked, so the cutter must stick
  out of the nut more than the depth shown.

- **Round stock: the jaws are checked as a ring.** A round bar can be clamped with the jaws at any angle, and
  nothing ties C0 on the machine to them, so below the jaw tops (+ clearance) nothing is cut beside the jaws all
  the way round. Tick the chuck's **Jaws At Known Angle** only if you set C0 so that the jaws really are where the
  CAM shows them. (Square, hexagon or off-centre stock: the jaws are where they grip it.)
- The clearance holds in height too: a cut at the jaw tops would rub them.
- **Every operation is checked against the chuck** (Profile, Pocket, Drilling, … and their rapid moves) when it is
  made: the cutter, tip and everything above it, against the body, the jaws and the clamps, on the polar program as
  the machine moves it (a rapid curves between its end points). A hit opens a card that says it will crash, and
  **Post Process writes no file** and names the operation, the move and the place.

Not done yet: the jaws' angle on the machine is not tied to C0 (see *Open items* in
[docs/FREECAD.md](../docs/FREECAD.md)).

## Which operations suit polar machining

The chuck turns and the cutter only moves in X and Z. Close to the centre the chuck must turn very fast to keep
the feed; it cannot, so the controller slows the cut there. Commercial CAM systems therefore use 2D / 2.5D
operations on a polar face (contour, pocket, facing, drilling). In a **polar Job** every FreeCAD operation can be
used; the addon only warns (see *Checked when made*):

| To make | Use | Notes |
|---|---|---|
| The face of the stock | **Face** (FreeCAD) or a **Pocket** (Offset) on the top face | Face covers the stock's rectangle and runs in lines: warned about; a Pocket Offset follows the real stock in rings |
| A pocket | **Pocket Shape**, pattern **Offset** (the default in a polar Job) | ZigZag works but is warned against: the chuck reverses on every line |
| A round hole | **Drilling** (any size of drill; the cycle is turned into X, C and Z moves) or **Helix** (bigger than the cutter) | a hole on the axis is ideal: only Z moves |
| A contour | **Profile** | for teeth or slots use a cutter that fits them |
| The outside of a bar, router radial | **Polar Wrap** (Wrap Job) | |

Only two things are the addon's own: **Polar Wrap** (FreeCAD has no radial router) and the **chuck** (not a tool:
what holds the part, so that every operation is checked against it). Everything was run end to end in
`tests/freecad/ops_test.py` and `tests/freecad/cut_check_test.py`.

- The defaults are the Job's own *Operation defaults* (SetupSheet), set by *Machining type* (Pocket Offset; Face
  Spiral where this FreeCAD has it); they apply to operations made after that.
- A Wrap Job greys out every operation but Polar Wrap (Post Process would refuse them).
