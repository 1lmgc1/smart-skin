# P01F1 Rhino 8 field test

Use the ZIP produced by the successful `build-p01f1` GitHub Actions run. Do not mix it with P01 files.

## Install

1. Close every Rhino window and confirm `Rhino.exe` is no longer running.
2. Extract the P01F1 artifact to a new folder.
3. Double-click `INSTALL.cmd` and wait for `SMARTSKIN_INSTALL PASS`.
4. The installer copies the new build to `%LOCALAPPDATA%\SmartSkin\Rhino8\current`, registers that stable path for Rhino 8, and removes the previously registered Smart Skin binaries. It never recursively deletes an external download/source folder or unrelated files beside an old build.
5. Do not start Rhino yet. Record the complete `SMARTSKIN_INSTALL PASS` line. Its `path` must end in `\AppData\Local\SmartSkin\Rhino8\current\SmartSkin.Rhino8.rhp`. When migrating a still-present manual installation, `removed_old_files` must be greater than zero; a zero result requires a separate registry/path check before Rhino starts.
6. Start Rhino 8 normally only after the installation line has been accepted. Do not use `Tools → Options → Plug-ins → Install…` for this or later Smart Skin artifacts.

If the installer reports that Rhino is open, close all Rhino windows and run `INSTALL.cmd` again. A failed install must be returned as the complete `SMARTSKIN_INSTALL FAIL` line.

## Uninstall

Close Rhino and run `UNINSTALL.cmd`. A successful uninstall returns `SMARTSKIN_UNINSTALL PASS`, removes the Smart Skin registry entry and deletes the managed `%LOCALAPPDATA%\SmartSkin\Rhino8` folder.

## Test A — build identity

1. Run `SmartSurfaceVersion`.
2. Confirm `Patch: P01F1`, `Version: 0.0.3-p01f1` and the artifact commit.
3. Keep the final `SMARTSKIN_P01F1 PASS` line.

## Test B — parent object versus sub-object

1. Start a blank millimetre document and create one ordinary `Box`.
2. Turn the Rhino Selection Filter `Sub-objects` option off.
3. Run `SmartSurfacePreflight`, select the whole Box normally, and press Enter.
4. Confirm `Types: Extrusion=1`; `Curve=1` is a failure.
5. Confirm the item label contains `object:Extrusion` and the final line ends with `objects=1->1`.
6. Run `SmartSurfacePreflight` again.
7. Ctrl+Shift-click one Box edge and press Enter.
8. Confirm `Types: BrepEdge=1`, a `subobject:` label and `objects=1->1`.

## Test C — cancellation

1. Run `SmartSurfacePreflight`.
2. Press Esc before selecting anything.
3. Run `SmartSurfaceVersion` and confirm the object count is still 1.

## Test D — restart

1. Close Rhino completely and reopen the same Box file.
2. Run `SmartSurfaceVersion` and one whole-Box `SmartSurfacePreflight`.
3. Confirm `P01F1`, `Extrusion=1` and unchanged object count.

## Pass criteria

- Build identity matches the artifact.
- Whole Extrusion and sub-selected Brep edge retain distinct types.
- No completed or cancelled command changes document geometry.
- Classification remains correct after a full Rhino restart.

## Recorded reference result

P01F1 is `VERIFIED` in Rhino 8.18 for field build commit
`550b74ff9f5bd8953d80c28560a9951d39214d55`. The completed test covered the
managed installation, build identity, whole saved Extrusion, sub-selected Brep
edge, cancellation without an object-count change, and a full Rhino restart.

## Return this evidence

```text
version_machine_line:
whole_box_types_line:
whole_box_machine_line:
brep_edge_types_line:
brep_edge_machine_line:
after_cancel_version_machine_line:
after_restart_types_line:
after_restart_machine_line:
result: PASS / FAIL
complete_error_if_any:
```
