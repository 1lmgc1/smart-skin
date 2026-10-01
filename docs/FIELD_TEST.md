# P03F1 Rhino 8 field test

Use only the ZIP produced by a successful `build-p03f1` run for the exact
commit being tested. P03F1 changes document-count diagnostics only. The P03
PlanarSrf, EdgeSrf, Loft, preview, Accept, Cancel, Undo, blocked-input, and
restart paths were field-tested on commit
`acdcba9cc0586a769bae7a97ed61dadf74055573`.

## Install

1. Close every Rhino window and confirm `Rhino.exe` is no longer running.
2. Extract the P03F1 artifact to a new folder.
3. Run `INSTALL.cmd`; wait for `SMARTSKIN_INSTALL PASS`.
4. Confirm `version=0.0.6-p03f1` and the managed path ending in
   `\AppData\Local\SmartSkin\Rhino8\current\SmartSkin.Rhino8.rhp`.
5. Start Rhino normally. Do not manually register the downloaded `.rhp`.

If install fails, return the complete `SMARTSKIN_INSTALL FAIL` line and stop.

## Test A — identity and active count

1. Open a blank millimetre document.
2. Run `SmartSurfaceVersion`.
3. Confirm `Patch: P03F1`, `Version: 0.0.6-p03f1`, the artifact commit, and
   `objects=0`.

## Test B — Accept, Undo, and corrected count

1. Create one ordinary circle.
2. Run `SmartSurfaceBuild`, select the circle, finish selection, and choose
   `Accept` after the cyan preview appears.
3. Keep the machine line with `strategy=PLANAR_SRF`, `action=ACCEPTED`,
   `built=1`, `added=1`, and `objects=1->2`.
4. Run `Undo`; confirm only the new surface disappears.
5. Run `SmartSurfaceVersion` and confirm `objects=1`, not `objects=2`.

## Test C — deleted input is excluded

1. In a blank document create a rectangle, explode it, and delete one side.
2. Run `SmartSurfaceBuild` on the three remaining segments.
3. Confirm no preview appears and keep the line with `action=BLOCKED`,
   `code=P03_ROUTE_NOT_READY`, and `objects=3->3`.
4. Click empty viewport space to clear selection, run `SmartSurfaceBuild`, and
   press Esc before selecting geometry.
5. Confirm `action=CANCELLED`, `code=P03_SELECTION_CANCELLED`, and
   `objects=3->3`.

## Test D — saved document and restart

1. Open the saved two-circle P03 Loft test document.
2. Run `SmartSurfaceVersion`; confirm `objects=2`.
3. Run `SmartSurfaceBuild` on both circles, verify the preview, choose
   `Cancel`, and confirm `objects=2->2`.
4. Fully close Rhino, reopen the file, and repeat `SmartSurfaceVersion` once.

## Pass criteria

- Identity matches the exact CI artifact.
- Object fields count active saved document objects and exclude deleted Undo
  records.
- Accept still adds exactly one Brep; Undo removes only that Brep.
- Blocked and cancelled paths change nothing.
- Loading, counting, preview, and cancellation work after restart.

## Return this evidence

```text
install_machine_line:
version_blank_machine_line:
planar_accept_machine_line:
version_after_undo_machine_line:
open_chain_machine_line:
selection_cancel_machine_line:
saved_document_machine_line:
after_restart_machine_line:
result: PASS / FAIL
complete_error_if_any:
```
