# Knurling & Wrap — notes (moved from WikiTips on 2026-10-20)

Marios's decision (2026-10-20): Knurl and Wrap-on-a-cylinder leave WikiTips and live in this repo as a
SEPARATE part of the FreeCAD addon (`cad/`), only on a Part Design toolbar, with NO WikiTips inside.
Licence MIT (his own code, he agreed). WikiTips stays only help + error explanations, in its own repo.

## How it is packed
- `package.xml` has a second `<workbench>` content item `KnurlWrap`, subdirectory `cad`. FreeCAD adds every
  workbench subdirectory to `sys.path` and runs its `InitGui.py` (FreeCADInit.py `process_metadata`).
  One repository = one entry in the Addon Manager; the two parts are independent inside it.
- Commands `KnurlWrap_Knurl`, `KnurlWrap_Wrap` (were `WikiTips_Knurl`, `WikiTips_Wrap`). Toolbar:
  `BaseApp/Workbench/PartDesignWorkbench/Toolbar/KnurlWrap` (a Part Design custom toolbar; not in CAM —
  tested).
- Old documents store the proxies as `wikitips_knurl.Knurl` etc. `cad/wikitips_knurl.py`, `cad/wikitips_wrap.py`
  re-export the classes. **FreeCAD 26.3 blocks imports during document restore** unless the module is already
  in `sys.modules` or its file is under `FreeCAD.__ModDirs__` (src/App/PropertyPythonObject.cpp
  `isAllowedModule`); a symlinked install failed that path test, so `gui.install()` imports both shims at
  start-up. Saved again, the objects are stored as `knurlwrap.knurl` / `knurlwrap.wrap` (tested).
- The Greek guidance that WikiTips' error explainer used to show (wrong selection, too big knurl, no closed
  shapes) is now `knurl._tell` / `knurl.explain`: a small non-modal message box + the status bar.
- The enumeration values are Greek (`Διαμάντι`, `Ίσιο`, `Πραγματικό`, `Ελαφρύ`, `Χάραξη`, `Ανάγλυφο`,
  `Μέχρι τον άξονα`) and are SAVED in documents: never rename them.

## Knurl (WikiTips PR 14, 2026-10-17)
- Real teeth: `direct_knurl` (groove, then the teeth and the rest of the part written as one BREP text, see
  `_Brep`; no sewing, no boolean) when the band is a clean ring, else the boolean. Limits: MAX_FACES 60000
  (direct), MAX_FACES_BOOLEAN 25000; bigger is refused with a Greek message. Light kind: lines drawn by the
  view provider only; the solid is unchanged.
- Teeth: 90° flanks with a flat top (5 faces a diamond tooth, 3 a straight ridge). Depth 0 = auto = 75 % of
  the full height (0.5 x pitch x cos(angle)); any depth is held between 20 % and 100 % of it (Marios's 0.8
  on pitch 0.3 was impossible and took 10 minutes); also capped at half the radius.
- Panel: Ok | Apply | Cancel. Apply computes and stays open, OK closes, Cancel restores all values.
- Default pitch by diameter: ≤8 mm 0.6, ≤16 mm 0.8, ≤32 mm 1.0, else 1.2 (ideas from DIN 82 tables).
- In a Body it is a `PartDesign::FeaturePython`: 26.3 SEGFAULTS when creating
  FeatureAdditivePython / FeatureSubtractivePython / FeatureAddSubPython with the GUI up (checked 2026-10-17).
- Booleans with many faces tangent to the cut surface are slow (tooth tips 2 µm inside: 3-5x faster).
- Not done: inner (bore) knurling, G-code for a 4th axis, a GIF for the button, English texts.

## Wrap: drawing on a cylinder (WikiTips PR 14, 2026-10-17)
- Uses the picked point (Selection PickedPoints) for the tangent sketch (MapMode Deactivated, Placement set;
  in a Body: body.newObject). Construction frame 2πR wide x cylinder length. The Wrap feature reads the
  sketch Placement on every recompute, so moving the sketch moves the drawing.
- Method: each sketch edge → B-spline, poles mapped to the cylinder's (u = x/R, v = y)
  (Geom2d BSplineCurve2d, then toShape(surface)); one face per wire with Part.Face(surface, wire), holes cut,
  then `face.makeOffsetShape(h, 1e-6, fill=True)` gives the emboss/engrave solid. Exact (area preserved).
- Only closed shapes count (Bullseye face maker: letters with holes work). Open lines are ignored.
- The side face of a Pad may have its cylinder Axis opposite to the Pad direction: never take the surface's
  axis as "up".

## Verified (real FreeCAD 26.3, 2026-10-20, this repo, no WikiTips installed)
- knurl_test: 31 checks (button only in Part Design, wrong selection message, panel, preview, Apply/OK,
  depth limits, direct build, Tip, Pocket after it, too big refused + message, Part cylinder, cross hole
  boolean, pitch 0.3/depth 0.8, auto depth, save + reopen).
- cyl_wrap_test: 16 checks (sketch where clicked, not mirrored, three modes, lands where drawn, reopen,
  upstream edit).
- knurlwrap_old_file_test: the WikiTips 0.4.1 file opens, same volumes to 0.001 mm³, saved under the new names.

## Hole on any surface (2026-10-22, Marios: "only a hole for now")
- Why: Marios could not open a radial hole in the grooves of his HTD 5M pulley (Pocket: "result is empty").
  Cause (checked in FreeCAD 26.3 on his file): his Part Design Hole M14x2.0 with **Model Thread** leaves a solid
  that looks valid but on which any cut THROUGH the thread fails (a Ø3 cut removes the whole part). Through all
  does not help; unticking Model Thread does. A plain M14 modelled thread on a plain cylinder does NOT reproduce
  it (tried several settings): it comes from his pulley geometry + the thread.
- `cad/knurlwrap/hole.py`, command `KnurlWrap_Hole`, feature `HoleOnSurface` (`PartDesign::FeaturePython` in a
  Body, `Part::FeaturePython` with `Base` otherwise). Stores Point + Direction (numbers), Diameter, Mode, Depth.
- Direction = minus the face normal at the picked point, checked against the solid with `isInside` (the normal
  of a face of a broken solid can point into the material). The drill starts outside the part (whatever lies
  on the hole's line above the point is cut too) and ends: `Ως το πρώτο κενό` (default: where the line first
  leaves the material, + 0.01 mm), `Βάθος`, `Διαμπερής`. Mode values are Greek and SAVED: never rename.
- Broken-solid test (`cut_ok`): result valid, has solids, volume > 0, removed between 0 and the drill's volume.
  At creation the command walks back from the Tip (`healthy_place`) and puts the hole (Body.insertObject) after
  the last feature where the cut is right, i.e. before the one that breaks it, with a Greek message naming it.
  On recompute a failing cut raises with the Greek explanation (untick Model Thread / move the hole up).
- On his pulley file: "first empty" from a tooth or a groove cuts fine even AFTER the thread (it never reaches
  it); "right through" goes before the thread Hole and the thread still builds on it.
- Test `tests/freecad/surface_hole_test.py` (in run.sh): the broken solid is stood in for by a feature that
  turns its base inside out (a real one could not be reproduced without his file).
- Not done (Marios: only a plain hole for now): screw holes M3/M4/M5, counterbore, nut pocket; moving the point
  with the mouse after creation (Point is editable in the property view).
