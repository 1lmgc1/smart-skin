# P07F1: one matched-boundary field test

Expected version: **0.0.13-p07f1**. Use the green build-p07f1 artifact for the exact published commit. Rhino 8.21+ is required; no .NET setting change. Installation is not a separate test: close Rhino, extract the bundle and run INSTALL.cmd normally. Do not manually register another RHP.

## Goal and starting geometry

Use the same private opening with six naked Brep edges on four source Breps, without an old cap covering it. Keep the original file unmodified and work on a copy. The object count is the actual N immediately before this command, not a fixed 12.

## Actions

1. Run SmartSurfaceVersion once and retain its complete line.
2. Click the single Smart Skin button; select the same six opening edges and finish with Enter. No separate whole-object selection is required.
3. Keep Curvature (G2), Refine ON, curvature tolerance 5%, Automatic. Average must remain OFF and should be disabled with its natural-target eligibility explanation for trimmed targets.
4. On the first match in this Rhino process, eight small native validator regressions run automatically in memory. They never access RhinoDoc. This is part of this one test, not an extra command. A regression failure blocks building and reports its case.
5. If the result is READY / G2_SAMPLED_VERIFIED, inspect the cyan cap and confirm with Enter, Space or right-click. Select cap and the four neighbors, run Join, and confirm one joined Brep. Undo Join to restore the separate cap and sources.
6. If BLOCKED, do not increase tolerance, lower continuity, toggle Average or recreate the input. Press Esc and keep the complete log. A numeric large-gap rejection is a useful diagnostic but is NOT a successful geometry test.

## Expected evidence

Successful command identity: SMARTSKIN_P07F1 PASS; version=0.0.13-p07f1; exact commit. Existing P07 action codes are retained: code=P07_ACCEPTED; strategy=MATCH_SRF; continuity=G2; verified=G2_SAMPLED_VERIFIED; supports=6; parents=4; proved_target_edges=6; average=OFF; added=1; replaced=0; objects=N->N+1. Undo the P07F1 command itself removes only its result.

All native variants now emit SMARTSKIN_P07F1_ATTEMPT_START, SMARTSKIN_P07F1_BOUNDARY and SMARTSKIN_P07F1_ATTEMPT_END. Keep both successful and rejected variants, including reason, phase, boundary_edges, boundary_components, max_gap, samples and covered_target_edges. A BLOCKED/Esc finish must not add a result.

## Return

Return the complete Rhino command history from SmartSurfaceVersion through this command's final line and one viewport screenshot. No installer or PowerShell log is needed unless installation actually fails. Do not publish the private model or field evidence to the public repository.
