# Polar CNC converter

Turns ordinary 3-axis milling G-code (from Fusion 360, FreeCAD, Kiri:Moto or any CAM) into **polar G-code for face
machining**: one radial axis (X), one rotary axis (the chuck, C) and the depth axis (Z). The typical machine is a lathe
converted so that the chuck turns the part while a spindle on the cross-slide machines its face.

**Use it online:** https://marioskiv.github.io/polar-cnc-converter/ — or download the repository and open
`index.html` in any browser. No installation and no internet connection needed.

> [!IMPORTANT]
> **Status: working, still in testing.** Real parts have been cut with it on a LinuxCNC lathe conversion; an
> asymmetric test shape came out correct, not mirrored. Accuracy on metal, other machines and other controllers is
> still being tested.
>
> On a new machine, always cut in the air first, check the rotary direction (see below) and keep a hand on the
> E-stop. Use at your own risk.

## What it does

- Converts lines and arcs to X / C / Z moves with **G93 inverse-time feed**, so the tool moves along the part at
  the feed your CAM asked for.
- Keeps the path within **0.025 mm** of the CAM path (adjustable), including cuts that pass through the centre.
- Keeps tool changes, spindle, coolant, tool length and comments in the right order, and expands drilling cycles.
- Refuses anything it cannot convert safely, and names the line. It never guesses.
- Shows the result in a **3D simulator**, with material removal and rapid-collision warnings.
- Adds a short report at the top of every file: how many turns the chuck makes, and where the machine will have
  to slow down near the centre.
- **Wrap** (new): with the router turned to look at the part, it machines the **outside of a cylinder** from an
  ordinary 3-axis program of its surface unrolled flat — see [Technical notes](docs/TECHNICAL.md).

## Quick start

1. Open the page and paste your G-code (or open the file).
2. Under **Machine**, set the **cutting side** and **X Axis Max** (your X soft limit) once, or load a profile from
   `profiles/`.
3. Click **Convert & Simulate**, check the simulation, then **export** the polar G-code.

## CAM settings

Post for a 3-axis mill with a LinuxCNC (or grbl) post, in mm or inch:

- **work origin X0 Y0 = the centre of the chuck**; Z0 wherever you touch off (the top of the stock is simplest);
- cutter compensation *in computer* (no G41/G42);
- arcs in the XY plane only (or output them as lines), feed in units/min (G94).

## Before the first real part

1. **Rotary direction:** in MDI run `G0 C90`. Seen from the cutter, the chuck must turn **clockwise**. If it turns
   the other way, reverse the sign of the rotary axis `STEP_SCALE` in your machine configuration.
2. **Centre:** with X = 0 the cutter must be exactly on the chuck axis. To check, plunge 0.5 mm at X0 and turn the
   chuck one full turn. The hole must come out exactly the cutter diameter. If X0 is off, straight lines come out
   slightly curved toward the centre.
3. **Test shape:** cut a letter "F" off-centre in scrap. It must read normally, not mirrored.

## FreeCAD addon (in testing)

[`freecad/`](freecad/README.md) brings the same conversion into the FreeCAD CAM workbench (FreeCAD 1.1 or newer,
tested in 26.3). It has not yet cut a real part on the author's machine.

- **Polar Job:** make the Job with FreeCAD's own operations (Face, Pocket, Profile, Drilling…) and choose
  *Polar* in the PolarCNC machine settings. Post Process (`polar_linuxcnc`) writes the polar X / C / Z program.
- **Checked when made:** every operation of a polar Job is converted as soon as it is made. Warnings only (a
  pattern not recommended for polar, slower by a percentage, material left), and if the cutter would hit the
  chuck, or the operation cannot be written as polar, a card says so and Post Process refuses the program.
  Ordinary XYZ Jobs get no warnings.
- **Chuck:** 3- and 4-jaw chucks and a faceplate as solids, checked against every cutter with its own radius.
- **Polar Wrap:** the outside of a part with the router radial, straight from the 3D part (roughing and
  finishing helices). Several cutters one after another (*After operation*); the tool report says which ball
  end reaches every hollow. Its depth map is cross-checked against OpenCAMLib.
- **Simulator** in the 3D view, and help in Greek and English with short GIFs (the "?" button switches language).

## Knurling & Wrap (Part Design)

[`cad/`](cad/README.md): a separate part of the same FreeCAD addon, on its own **Part Design** toolbar. It does
not need Polar CNC or WikiTips.

- **Knurl**: knurling on a cylinder in one click (diamond or straight, real teeth or lines on screen only).
- **Wrap on a cylinder**: click the cylinder, draw in the sketch that opens there; text, shapes and holes are
  wrapped round it, engraved, raised or cut down to the axis. (Not the *Polar Wrap* machining operation.)
- **Hole on any surface**: click the part where the hole goes (flat, cylinder, pulley teeth, any curved face),
  press the button: a round hole square to the surface there, through the wall, to a depth or right through.

Until 2026-10-20 the first two were part of WikiTips; files made with them still open.

## More

- [FreeCAD addon notes](docs/FREECAD.md): how the addon works inside, what is tested and what is open.
- [Technical notes](docs/TECHNICAL.md): how it works, centre handling, accepted G-codes, tests.
- [CHANGELOG](CHANGELOG.md): what changed in each version.
- [`examples/linuxcnc-vismach-xzc-lathe`](examples/linuxcnc-vismach-xzc-lathe/): a LinuxCNC simulation of a lathe
  conversion, to try programs before they reach a machine.
- Tests: run `npm install` once, then `npm test`. The addon's tests run in a real FreeCAD:
  `FREECAD=/path/to/freecad sh tests/freecad/run.sh`.

## Credits

Inspired by **kadirilkimen**'s PolarBear CNC work ([Polar-Bear-Cnc-Machine](https://github.com/kadirilkimen/Polar-Bear-Cnc-Machine),
[polarToolsJS](https://github.com/kadirilkimen/polarToolsJS), [gCodePolarizerJS](https://github.com/kadirilkimen/gCodePolarizerJS)),
which first explored this kind of conversion. This is an independent implementation; no code is reused.

## License

Copyright (c) 2026 **Marioskiv** — <https://github.com/Marioskiv/polar-cnc-converter>

Released under the MIT License — see [`LICENSE`](./LICENSE). You are free to use, modify and redistribute
this code, including in other CAM software. The license requires that the copyright notice above and the
license text are kept in all copies or substantial portions. Every source file carries this notice in its
header; please leave it in place, and a link back to this repository is appreciated.
