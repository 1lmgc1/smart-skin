# P05 Rhino 8.18 field test — one soft hole

Use the green `build-p05` artifact for the exact published commit. Expected
version: `0.0.10-p05`. Installation is not a test; report it only if it fails.

This is one new geometry case. Do not repeat P03/P03F1 or the P04 toolbar tests.

## Test

1. Open the supplied private shell model.
2. Run `SmartSurfaceVersion` once. Keep the complete `SMARTSKIN_P05 PASS` line.
3. Run `SmartSurfaceBuild` and sub-select the same six naked Brep edges around
   one opening that produced the P04F1 blocked log. Finish selection with Enter.
4. Expected before preview:
   - `Routing status: READY`
   - `Topology: CLOSED_BOUNDARY_LOOP`
   - primary `Patch`, confidence `95`
   - `code=P05_TANGENT_PATCH_READY`
   - candidate `READY`, `supports=6`, `parents=4`,
     `continuity=G1_REQUESTED`
5. Inspect the preview. It must read as a soft continuation of the surrounding
   shell, not a flat lid, inward dent, fold or self-intersection.
6. If the preview is plausible, confirm with Enter, Space or right-click.
   Expect exactly one added Brep and `objects=12->13`. If it is visibly wrong,
   press Esc; expect `objects=12->12` and stop.

## Return

Return the complete command output and one viewport screenshot where the cap
profile and its boundary are visible. No installer or PowerShell test log is
needed.
