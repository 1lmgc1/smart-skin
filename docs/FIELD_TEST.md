# P01 Rhino 8 field test

Use the ZIP produced by the successful `build-p01` GitHub Actions run. Do not mix it with P00 files.

## Install

1. Close Rhino completely.
2. Extract the new artifact to a new folder.
3. Start Rhino 8 normally, not in Safe Mode.
4. Open `Tools → Options → Plug-ins`, click `Install…`, and select `net48\SmartSkin.Rhino8.rhp` from the new folder.
5. Keep `SmartSkin.Rhino8.rhp` and `SmartSkin.Core.dll` together.

## Test A — build identity

1. Run `SmartSurfaceVersion`.
2. Confirm `Patch: P01`, `Version: 0.0.2-p01` and the expected commit.
3. Keep the final `SMARTSKIN_P01 PASS` line.

## Test B — read-only report on the working file

1. Open a disposable copy of the 35-object control file.
2. Record the document object count.
3. Run `SmartSurfacePreflight`.
4. Select 2–8 relevant curves, edges, surfaces or polysurfaces and press Enter.
5. Copy the complete command output.
6. Confirm the output includes `Status`, `Types`, `Selection scale`, `absolute tolerance`, item summaries and `Issues`.
7. Confirm the final line begins with `SMARTSKIN_P01 PASS` and ends with `objects=35->35`.

`status=READY`, `WARNING` or `BLOCKED` are all valid command outcomes. They describe the selected geometry. A `SMARTSKIN_P01 FAIL` line is a plug-in/test failure.

## Test C — Brep edge and cancellation

1. Run `SmartSurfacePreflight` and sub-select one Brep edge with Ctrl+Shift-click, then press Enter.
2. Confirm the item type is `BrepEdge` and the command ends with `SMARTSKIN_P01 PASS`.
3. Run the command again and press Esc during selection.
4. Confirm no object was added, removed or changed.

## Test D — restart

1. Close Rhino completely.
2. Reopen the control file.
3. Run `SmartSurfacePreflight` on one curve.
4. Confirm the command still ends with `SMARTSKIN_P01 PASS` and the object count remains 35.

## Pass criteria

- Both commands are found and complete without an exception.
- Build identity matches the downloaded artifact.
- Top-level geometry and a sub-selected Brep edge are reported.
- Human-readable diagnostics and the machine line are present.
- The document object count remains unchanged in every run.
- Cancel returns to Rhino without geometry changes.
- The command still works after a full Rhino restart.

## Return this evidence

```text
artifact_name:
rhino_version:
runtime:
commit:
version_machine_line:
working_file_preflight_machine_line:
brep_edge_machine_line:
restart_machine_line:
object_count_before:
object_count_after:
cancel_changed_geometry: yes / no
result: PASS / FAIL
complete_command_output_or_error:
```
