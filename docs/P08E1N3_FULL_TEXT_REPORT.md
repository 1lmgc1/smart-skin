# N3 — complete local TXT report

Version `0.0.24-p08e1n3` adds report capture and saving to the existing native diagnostic. N2's EdgeSrf seed, two independent first-Match directions, measurement rules and disposable previews remain unchanged. Preliminary visual approval does not identify a recipe or establish continuity.

## Capture and save

`SmartSkinNativeCompare` records its diagnostic messages into a command-owned buffer from before selection. This records build identity, Rhino/runtime, model units and tolerances, selected input/topology, target and candidate correspondence, recipe settings and timing, per-side measurements, warnings/failures and final cleanup/source/object-count status. Console output remains available, but the report is not reconstructed from Rhino command history. It does not intercept unrelated Rhino commands or claim access to native engine messages that the API does not expose.

After cleanup, one folder chooser offers to save the completed report as UTF-8 text. The filename contains a timestamp and unique suffix; file creation must not overwrite an existing file. The command prints the saved path or an explicit save error. Dialog and saving time are separate from native-work timing. Reports stay on the user's selected local filesystem; there is no automatic upload.

Cancelling the folder chooser or a write failure preserves the latest completed buffer in the current Rhino session. `SmartSkinNativeReport` opens the chooser again and saves that buffer without constructing geometry. The buffer is replaced by the next completed diagnostic and is lost when Rhino closes. A failed write may require another folder; any partial-file outcome is reported honestly.

Capture is bounded. If an unexpectedly long session exhausts the report budget, further diagnostic work stops, the report is explicitly marked incomplete and final cleanup/status still receive reserved space. Nothing silently drops out of a report labeled complete.

## Field procedure

1. Close Rhino and install the unchanged verified CI ZIP. Reopen Rhino and check `SmartSurfaceVersion` for `0.0.24-p08e1n3` and the delivered commit.
2. Run `SmartSkinNativeCompare` and select the original complete opening. Use Next to inspect the available seed and reversal variants.
3. Finish with Done/Enter or cancel with Esc. Choose a folder in the report dialog; keep the displayed TXT path.
4. If saving was cancelled or failed, run `SmartSkinNativeReport`. Send the saved TXT and, if useful, a screenshot with the candidate name.

A new N3 run is required to obtain a complete report. Text already lost from an earlier Rhino history buffer cannot be recovered retroactively.

## Verification boundary

Managed tests exercise report ordering/completeness, file naming, UTF-8/Unicode paths, cancellation retention, collisions and I/O failure handling. Compilation uses the official RhinoCommon8.21/Eto APIs. Exact-source Windows CI and artifact integrity checks remain mandatory. Actual native folder selection and complete command integration require the field test; file-writer tests alone do not verify Rhino UI behavior.
