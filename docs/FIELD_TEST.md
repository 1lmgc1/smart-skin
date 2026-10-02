# P07 Rhino 8.21+ field test — G2 matched cap and exact Join

Use only the green `build-p07` artifact for the exact published commit.
Expected version: `0.0.12-p07`. Rhino 8.21 or later is required. Installation
is not a test; report it only if an actual problem occurs.

This is one focused geometry check. Do not repeat earlier toolbar or installer
tests.

## Test

1. Open the original private `error_shape.3dm` with 12 active objects.
2. Run `SmartSurfaceVersion` once and keep its complete `SMARTSKIN_P07 PASS`
   line.
3. Click the single `Smart Skin` button. Sub-select the same six naked Brep
   edges around one opening and finish selection with Enter.
4. In `Smart Skin — matched result`, keep `Curvature (G2)`, `Refine match`,
   `Automatic` and `Average surfaces` off. The supplied opening contains
   trimmed target edges; Rhino's native Average is not valid for that loop.
5. Wait for `READY · G2_SAMPLED_VERIFIED`. Confirm that the cap is cyan, the averaged
   context is absent, and the status reports gap, normal-angle and curvature
   values.
6. Press Enter, Space or right-click once. Do not look for an Accept button.
7. Select the new cap and the four neighboring source Breps, run Rhino `Join`,
   and confirm they become one joined Brep. Undo `Join` once to leave the P07
   result and original sources as they were after step 6.

## Expected result

- The opening is filled by one cap with a soft transition into the neighboring
  faces, and Rhino `Join` accepts all six matched seams.
- P07 itself adds exactly one cap and leaves all source Breps unchanged. For the
  unchanged 12-object fixture the expected P07 count is `12->13`.
- The final line contains `SMARTSKIN_P07 PASS`, `code=P07_ACCEPTED`,
  `strategy=MATCH_SRF`, `continuity=G2`, `verified=G2_SAMPLED_VERIFIED`,
  `supports=6`, `parents=4`, `proved_target_edges=6`, `average=OFF`, `added=1`,
  `replaced=0`, and measured
  `max_gap`, `sampled_max_normal_deg`, `sampled_max_curvature_pct` and
  `samples` values.
- One Undo after P07 itself removes only the new cap.

## Return

Return the complete command output and one viewport screenshot showing the
accepted result and single Smart Skin button. No installer or PowerShell log is
needed.
