# P03 Rhino 8 field test

Use only the ZIP produced by a successful `build-p03` run for the exact commit
being tested.

## Install

1. Close every Rhino window and confirm `Rhino.exe` is no longer running.
2. Extract the P03 artifact to a new folder.
3. Run `INSTALL.cmd`; wait for `SMARTSKIN_INSTALL PASS`.
4. Confirm `version=0.0.5-p03` and the managed path ending in
   `\AppData\Local\SmartSkin\Rhino8\current\SmartSkin.Rhino8.rhp`.
5. Start Rhino normally. Do not manually register the downloaded `.rhp`.

If install fails, return the complete `SMARTSKIN_INSTALL FAIL` line and stop.

## Test A — identity

1. Run `SmartSurfaceVersion` in a blank millimetre document.
2. Confirm `Patch: P03`, `Version: 0.0.5-p03`, and the artifact commit.
3. Keep the final `SMARTSKIN_P03 PASS` line.

## Test B — PlanarSrf Accept and Undo

1. Create one ordinary circle.
2. Run `SmartSurfaceBuild`, select the circle, and press Enter to finish
   selection.
3. Confirm a cyan preview appears and the command offers `Accept` / `Cancel`.
4. Choose `Accept`.
5. Confirm the circle remains and one surface was added.
6. Keep the machine line with `strategy=PLANAR_SRF`, `action=ACCEPTED`,
   `built=1`, `added=1`, and `objects=1->2`.
7. Run `Undo`; confirm only the new surface disappears and one circle remains.

## Test C — EdgeSrf unordered selection

1. In a blank document create one rectangle and run `Explode`.
2. Select the four sides in a deliberately scrambled order when running
   `SmartSurfaceBuild`.
3. Choose `Accept` after the preview appears.
4. Confirm all four source curves remain and one surface was added.
5. Keep the machine line with `strategy=EDGE_SRF`, `action=ACCEPTED`, and
   `objects=4->5`. `reversed` may be zero or greater.
6. Run `Undo`; confirm four curves remain.

## Test D — Loft Cancel, Accept, and Undo

1. In a blank document create a circle and copy it vertically by 10 mm.
2. Run `SmartSurfaceBuild` on both circles and choose `Cancel`.
3. Confirm the preview disappears and keep the line with `strategy=LOFT`,
   `action=CANCELLED`, `added=0`, and `objects=2->2`.
4. Run the command again on the same two circles and choose `Accept`.
5. Confirm both circles remain and one Loft Brep was added; keep the line with
   `strategy=LOFT`, `action=ACCEPTED`, and `objects=2->3`.
6. Run `Undo`; confirm two circles remain, then save the document.

## Test E — blocked open chain and selection cancellation

1. In a blank document create and explode a rectangle; delete one side.
2. Run `SmartSurfaceBuild` on the three remaining connected segments.
3. Confirm no preview appears and keep the line with `action=BLOCKED`,
   `code=P03_ROUTE_NOT_READY`, and `objects=3->3`.
4. Run `SmartSurfaceBuild` again and press Esc before selecting geometry.
5. Keep the `action=CANCELLED`, `code=P03_SELECTION_CANCELLED`,
   `objects=3->3` line.

## Test F — restart

1. Fully close Rhino and reopen the saved two-circle document from Test D.
2. Run `SmartSurfaceVersion` and confirm the same P03 commit loads.
3. Run `SmartSurfaceBuild` on both circles, verify the preview, choose `Cancel`,
   and confirm `objects=2->2`.

## Pass criteria

- Identity matches the exact CI artifact.
- Each preview appears only after a `READY` bounded route.
- Cancel/Esc/blocked paths add nothing.
- Accept adds exactly one native Brep and retains all source geometry.
- Undo removes only the accepted Brep.
- The plug-in and cancellation path work after restart.

## Return this evidence

```text
install_machine_line:
version_machine_line:
planar_accept_machine_line:
planar_after_undo_object_count:
edge_accept_machine_line:
edge_after_undo_object_count:
loft_cancel_machine_line:
loft_accept_machine_line:
loft_after_undo_object_count:
open_chain_machine_line:
selection_cancel_machine_line:
after_restart_machine_line:
result: PASS / FAIL
complete_error_if_any:
```
