# P00 Rhino 8 field test

Use the ZIP produced by the successful `build-p00` GitHub Actions run. Do not test a locally mixed folder.

## Install

1. Extract the artifact to a new folder.
2. Start Rhino 8 normally, not in Safe Mode.
3. Use `net48\SmartSkin.Rhino8.rhp`. P00 deliberately uses this compatibility baseline; the command reports Rhino's actual runtime so the next target can be selected from evidence.
4. In Rhino open `Tools → Options → Plug-ins`, press `Install…`, and select the `.rhp` file.
5. If Windows blocks the downloaded file, close Rhino, unblock the extracted files in Windows Properties, and retry.

## Test

1. Open a disposable document containing at least one object.
2. Record the object count.
3. Run `SmartSurfaceVersion`.
4. Copy the complete Rhino command history produced by the command.
5. Confirm the final line begins with `SMARTSKIN_P00 PASS`.
6. Confirm the object count is unchanged.
7. Close and reopen Rhino, then run `SmartSurfaceVersion` once more.

## Pass criteria

- Plug-in loads without an exception.
- Command is found and completes successfully twice, including after restart.
- Output reports `Patch: P00`, version, commit, Rhino version, runtime and x64 process.
- Final machine line reports `PASS`.
- Document object count is unchanged.

## Return this evidence

```text
artifact_name:
rhino_version:
runtime:
first_run_machine_line:
second_run_machine_line:
object_count_before:
object_count_after:
result: PASS / FAIL
error_or_observation:
```
