# P08A.2 — parent-context audit with a streaming TXT report

This is a separate geometry-read-only diagnostic script, not a replacement RHP, solver release or acceptance gate. The installed plug-in remains P07F2 / 0.0.14-p07f2 at a9b8281f9475fb29d38839614b1781ff21b26677. No runtime switch, installation, source deletion or whole-object preselection is required.

## P08A.2 reporting change

Ask for a TXT destination with Rhino's SaveFileName dialog BEFORE binding the assembly or selecting edges. Use a timestamped default name, append .txt to non-TXT names and require explicit confirmation before overwriting an existing TXT. Cancelling the save dialog does not start the audit. An unwritable destination prompts for another path.

Write every audit record directly to UTF-8 with BOM and CRLF, flushing each record. Detailed MAP, frame, distance, corner, STOP and SAFETY records are not truncated to fit command history. The console shows only short progress and the final saved path. The same records are retained in memory: a write/close failure is reported as incomplete and offers an explicit alternative destination without rerunning geometry. Cancelling that retry leaves the previous partial file, not a claimed successful save. Abrupt process/power loss cannot promise a final footer or safety check, but already flushed records are not deliberately discarded.

The original geometric method bodies, assembly pin, sample budgets, tolerances and native calls are unchanged. Only reporting, Unicode formatting and report lifecycle are changed; the existing checkpoint also stops further work after a file write failure. Keep any generated TXT private.

## Objective

Separate four questions: whether selected parent geometry is preserved by context construction; whether the mapped edges still belong to the intended faces; whether the seed and native match differ from the original opening; and whether adjacent support faces impose compatible tangent-plane limits at shared boundary vertices. Do not infer these answers from parent/edge counts or requested G2.

## How the audit uses the actual installed code

The script checks the assembly informational version and commit before accessing private implementation. It invokes the installed OrderClosedEdgeLoop, BuildBoundaryContext, JoinBoundary, CreateSeedCap, FindSeedBoundaryEdge, JoinLoop, FaceParameters and ActiveObjectCount methods through reflection. It does not implement a different context mapper, load a second RHP or call any acceptance/commit function. The output of the actual context factory is inspected using its SourceIndices and TargetEdges. Missing or changed private signatures cause a named stop. This intentionally pinned diagnostic is not a general public API or a future-version compatibility promise.

MAP records source object/edge/trim/face, mapped edge/trim/face, surface equality, orientation, trim iso state, degree and edge tolerance. MAP_FRAME records UV, normals and principal curvatures. Both native deviation directions and bidirectional sampled nearest-point distances are recorded for every mapped pair. Alternative full edges are filtered by endpoint proximity and listed with face equality; this is not an exhaustive uniqueness proof for arbitrary subedges.

CORNER records adjacent source-face tangent-plane angles at the ordered endpoint locations. For an everywhere regular C1 cap with a unique continuous tangent plane at a common vertex, the two required limiting planes must agree (up to normal orientation and tolerances). Disagreement raises a diagnostic review flag, not an automatic downgrade or a universal impossibility claim: singular corners, noncoincident endpoints and different per-edge requirements require separate analysis. Compatible normals alone do not prove G2 or solvability. The script does not invent which edges should receive G0 versus G2.

## Seed and measurement experiment

The original radial-loft seed is measured before matching. Reverse OFF and ON then run with fresh factory/seed copies, original document tolerances, G2, Refine ON, 5%, Automatic, Average OFF and MatchClosestPoints false. Initial seed/context equality and post-call unchanged checks are logged. Unlike production, failed candidates remain alive only long enough for inspection and are never added to the document. Native calls are made on Rhino's script/command thread.

Each returned valid bounded cap is compared against BOTH joined-context and original selected boundaries. Both GetDistancesBetweenCurves results, returned parameters and witness-point distances are recorded. A separate 65-sample-per-edge nearest-point pass locates observed error and tangent-plane discrepancies, including when the native deviation measurement is unavailable. A sampled maximum is not a certified maximum over the whole curve and never authorizes geometry acceptance. Native-failure directions remain unavailable, not zero. No direction result is hidden by Boolean short-circuit evaluation.

The fixed budgets are five to eight input edges, at most 8192 sample sites and a 45-second budget checked between supported calls. A single native call cannot be force-aborted. Esc is observed at checkpoints. Existing context complexity guards execute in the installed factory. Returned caps over the production 128-face/512-edge limits are not sampled.

## Safety

There are no document geometry write calls or network calls in the Rhino script. The only filesystem write is the user-selected TXT report, or its explicitly selected retry destination after an I/O failure. Selection highlighting may change. Source parent geometry snapshots and active object counts are compared at the end, including an interrupted audit where possible. All owned copies are disposed. No candidate is committable; COMPLETE means the audit ran, not that the hole passed. The production eight-case self-test and acceptance gate are untouched; this diagnostic does not run the product command or bypass it to accept a result.

The log includes model coordinates and object IDs. Keep it in the private project conversation/journal, never commit it or the model to this public repository.

## One field action

Keep the prepared opening; do not delete another surface. Run SmartSurfaceVersion once to load the existing P07F2 assembly. Then run _RunPythonScript, choose the updated SmartSkin_ContextAudit.py (the conversation download may be named SmartSkin_ContextAudit_TXT.py), select the report TXT location, select the same six naked opening edges and finish with Enter. Do not run the file in PowerShell or an external Python interpreter. The audit has no live-preview/Accept window. Attach the saved TXT instead of copying the command history. A STOP report is useful too. No additional screenshot is required unless a new UI error occurs.

Read MAP / MAP_FRAME, CORNER, SEED_VS_CONTEXT, REVERSE_*_CONTEXT, REVERSE_*_ORIGINAL and final SAFETY together. Do not conclude that a large native value is spurious merely because finite sampled values are lower.

## Verification scope

Local and CI checks cover Python syntax, helper arithmetic, explicit missing-data handling, source guards, actual temporary-file I/O, mocked save dialogs and the exact script blob. Tests include long/Unicode reports, per-record flush, cancel/error/finally paths, overwrite refusal/approval and alternate-save recovery. The geometry-method source checksum is compared with P08A.1. CPython tests do NOT execute Rhino geometry, reflection binding, native save dialogs or IronPython native interoperability. Native audit execution remains NOT VERIFIED until its field report. No new native self-test is injected into the user's production command. The RHP version, main branch, UI and geometry code are not modified by this diagnostic branch.

## Primary references

- SaveFileName: https://developer.rhino3d.com/api/RhinoScriptSyntax/#userinterface-SaveFileName
- CreateFromMatch target-edge contract: https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Brep_CreateFromMatch_1.htm
- Native curve-deviation measurement contract: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.curve/getdistancesbetweencurves
- McNeel developer discussion of deviation semantics: https://discourse.mcneel.com/t/is-the-curve-getdistancesbetweencurves-method-buggy/157501/11
- RunPythonScript: https://docs.mcneel.com/rhino/8/help/en-us/commands/runpythonscript.htm
