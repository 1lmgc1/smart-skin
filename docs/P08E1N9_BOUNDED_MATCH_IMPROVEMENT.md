# P08E1N9: optional native boundary improvement

Version **0.0.30-p08e1n9** retains the user-confirmed N8 surface-creation route. The existing button and `SmartSurfaceBuild` perform no Match operations. The explicit **`SmartSurfaceBuildImprove`** command adds a bounded experiment and uses the same final preview, Create Surface action, exact insertion verification and normal-command Undo transaction.

## Controlled experiment

Keep the original pre-Join EdgeSrf seed, whose four natural sides are editable. The joined cap can have split edges and is not substituted for that input. Preserve all original parent BrepEdge pieces and owning faces in fresh disposable copies. Average remains false; parent geometry, trim regions and visible source loci are never changed.

The first stage compares four independent G1 attempts on the first logical side: Automatic versus Preserve isocurve direction, each with refinement off and on. These are actual `PreserveIsoCurveMethod` settings. Automatic can align differently at trimmed targets; Preserve is not a lock on every adjacent boundary. The existing measured reverse setting is held fixed and physical endpoint correspondence is checked; it is not assumed to normalize arbitrary compound-chain directions.

Only the two refined branches may continue, once, through the opposite side and then the remaining pair. An unrefined control is still eligible if its first result already satisfies the whole-boundary G1 screen. Already-satisfied targets may be skipped. Every step must retain all original-boundary G0 constraints and all previously achieved per-piece G1/G2 states. Wrong corners, unresolved pairing, invalid output or lost constraints terminate that branch.

One fully G1-qualified branch may make one four-side G2 pass with refinement enabled. The complete experiment uses at most **14 Match calls** and no repeated search loop. PreserveOtherEnd=G2 protects only the opposite edge, so every original piece is measured again after every operation. Multiple target curves in `CreateFromMatch` describe a chain for one edited edge; this is not an all-side simultaneous solver.

Refinement may add knot rows; spatial locality is not guaranteed. Output degree is capped at 11 and control points at 4096. A separate 15-second attempt budget is checked between operations. It cannot guarantee interruption of an opaque native call. Esc cancels the invocation with no additions; other unsuccessful experiments retain the prequalified baseline with an explicit reason.

## Measurements and promotion

Original source spans, features, endpoints, nearby one-sided stations and parent transitions are retained. A proven shared endpoint in a compound chain has both parent constraints; nearest-edge ties are not silently discarded. Compare the original source to its assigned candidate side and the candidate back to that named source chain. Use the corrected coherent surface-normal and curvature frame. G1/full-W measurements count only after G0-qualified correspondence; only the existing explicitly role-bound upper corner points have the historical point-only exception.

G1/G2 additionally require opposite physical inward directions at each required seam station. Matching tangent planes and curvature alone can otherwise accept a same-side cusp. Derive the inward direction from the actual oriented UV trim loop and its mapped tangent through the surface Jacobian; preserve relative U/V scale and do not infer occupancy from face-normal sign. Unresolved or same-side contact prevents the improved continuity tier. This is a local attachment screen, not a global parent-intersection proof, and does not change G0 or add a stricter angular tolerance.

Physical position, angular and full-W thresholds remain unchanged. Native curvature refinement uses a separate radius-percentage setting derived from the cached source curvature magnitude of the current logical target side and current W threshold. The four source-only settings are frozen and reported before the matrix. Its scalar radius interpretation is only a solver target, not a proof of the full shape operator. Flat-source handling is explicitly reported, and no arbitrary lower percentage floor relaxes acceptance.

An improved candidate is presented for explicit creation only after the required whole-boundary tier passes. Final selection is automatic and deterministic: achieved whole-boundary level, then fewer control points, then recipe order. The finalist also needs bounded interior/orientation and mesh self-overlap screening, fresh Join provenance/seam checks, cap qualification and a new source/candidate-bound receipt. Failed or unresolved screens cannot promote a candidate. Finite sampling and meshes do not prove global regularity or separation.

## Working path and test limits

The normal Build path remains available. The optional command completes its bounded attempt before opening the existing preview and clearly identifies an improved or retained baseline result. It does not add an in-session Original/Improved selector. Confirmation adds only that displayed cap; original parents remain separate and untouched. An earlier cap already present in the document is not replaced. Esc cancels the whole invocation with zero additions. Report saving stays optional. No automatic Python fallback, parent trimming, forced Join, default RefitTrim or unrequested template construction is introduced.

Managed tests cover the bounded recipe policy, advancement, stopping and result selection. API compilation and compiled command-to-transaction checks establish integration with the exact packaged code. Licensed Rhino Match/refinement output, performance, new command UI and actual insertion/Undo remain field-verification boundaries. N8 creation was user-confirmed; that evidence is not a native success claim for these new improvement attempts.

Official references: [MatchSrf behavior and limitations](https://docs.mcneel.com/rhino/8/help/en-us/commands/matchsrf.htm), [MatchSrfSettings](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/T_Rhino_Geometry_MatchSrfSettings.htm), [single-edge Match with target chain](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Brep_CreateFromMatch_1.htm).
