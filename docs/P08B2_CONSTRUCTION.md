# P08B.2F1 — compound logical sides, explicit per-source roles

This is a focused layout correction to the P08B.2 constructive experiment, NOT a new RHP release. The experimental script remains PREVIEW ONLY. `main`, installed P07F2, runtime, numerical solver, native G0/Join proof and source protection remain unchanged. Enter/Esc only close a transient preview, never add geometry.

## Correct boundary interpretation

A selected BrepEdge is a source segment, not necessarily one entire logical side of a patch. Two opposing G0 sides can each consist of two source edges, while two curved G2 sides each consist of one source edge: six source segments, four logical sides, 4G0 + 2G2. User roles, not curvature, planarity, position on screen or assumed edge count, define the contract.

P08B.2 previously required exactly one contiguous G0 chain and partitioned all remaining source intervals into three smooth sides. It therefore stopped at layout creation for two disjoint G0 chains, before creating or measuring any surface. This is an unsupported layout assumption, not evidence that mixed construction failed or the selected geometry was bad.

P08B.2F1 partitions the already ordered closed ring into homogeneous role runs. Two G0 runs separated by two G2 runs map directly to bottom/right/top/left; top and left traversal are reversed for tensor-product coordinates. Every source key, original edge/trim/face link, interval and explicit role is retained. No native curve is joined/rebuilt/split by this helper. The one-G0-chain route and its bounded alternative layouts remain available. More than two separated G0 chains remain an explicit unsupported four-side layout, not an excuse to silently change roles.

Canonical cyclic start affects parameter placement only. Selection order does not assign G0 or G2. Whole-loop geometry ordering/closure still uses the original capture guards. Within-side geometric fitting and regularity are still measured by the unchanged construction kernel; grouping metadata is not proof of a good surface.

## Field action

Use the NEW bundled script `SmartSkin_MixedBoundary_Prototype.py` (the conversation copy can have suffix `_P08B2F1.py`). No reinstallation or runtime changes.

1. In Rhino run `_RunPythonScript`, choose the script, then a new TXT report path.
2. Select ALL six source Brep edges of the already prepared opening, then Enter.
3. Select ALL FOUR source segments forming the two G0 sides, including both pieces of each side, then Enter. Leave the two curved edges for preferred G2. Do not manually Join, merge, rebuild or delete source geometry.
4. Expect `experiment=P08B.2F1`; `SELECTION sharp=4 smooth=2`; `ROLE_CHAINS g0_chains=2 g2_chains=2`; `LAYOUT_PLAN logical_sides=4 source_edges=6 side_edge_counts=2,1,2,1`. `SIDE` lines record membership, role and direction, followed by actual fitting/refinement and per-edge evidence.
5. A retained candidate is shown only after completed native G0 and copied-context Join proof. If a cyan preview exists, take a screenshot before Enter/Esc closes it. Nothing is added to the document. Attach the complete saved TXT, including later failure details if any.

The old instruction to select only two end-face source edges does not describe the revised 4G0+2G2 contract. Successful layout is only permission to TRY construction, not a geometry pass. No all-G0 fallback, tolerance increase or parent edit is introduced.

## Preserved construction and safety

Four chains are fitted as clamped cubic B-splines with shared endpoints, then a Coons net is formed. Outer control rows stay fixed during global parent-normal and second-derivative refinement. Every full candidate is remeasured; a failed later candidate cannot replace a previously verified positional preview. Data for unaffected original intervals remain distinct rather than being averaged into one side-level success.

The single-patch route has no internal Brep seams. The separate two-surface seam measurement helper remains tested, but automatic multipatch construction is not implemented. Budgets remain at most six layouts, control resolutions 10/16, four refinements and a 120-second soft limit; Esc is observed at supported checkpoints. Individual native calls cannot be force-aborted.

High-order evidence remains sampled tangent-plane and full shape-operator comparison, with the same 5% tensor threshold and declared nearly-flat floor. This is not the old P07 cross-curvature/radius percentage and is not an analytical all-points G2 certificate. Sampled regularity/orientation are not complete self-intersection or fairness proof. These limitations are why the experiment has no commit operation.

The Rhino adapter converts each eligible full net to a native Brep, compares native evaluations, measures its complete boundary in both directions against all original selected edges, then joins copies of its parents and proves the cap boundary became a closed internal seam. G0 feature edges are not required to be smooth. Original snapshots/counts are compared at exit. The full UTF-8 TXT is flushed per record; only short progress goes to the console.

## Verification scope

New tests cover the 2+1+2+1 role layout, all cyclic starts and both traversal directions, endpoints, wraparound chains, exact source coverage and reference preservation, nonmutation, unequal fragment counts, old one-chain layouts and explicit rejection of unsupported or missing identities. A constructive synthetic case has four G0 source segments on two opposing sides plus two CURVED G2 sides. The real kernel constructs that surface from the new layout; it is independently sampled on denser non-training boundary points, checked for frozen boundary rows and exercised with reversed traversal.

OpenNURBS conversion/point/normal tests and 3dm roundtrip now include that third constructed case in addition to the two original cases. Source checks require the exact previous numerical kernel and native evaluation/Join/retention/disposal methods. Exact CI output, rather than this document, establishes which checks actually passed.

Synthetic analytic support callbacks are not a Rhino trim-extraction test. CPython, OpenNURBS and an API compile probe do not execute Rhino UI/Join or the private model. Those levels remain NOT VERIFIED until the next field TXT. This branch contains no private logs, model UUIDs or coordinates. No dependencies are installed in the user's Rhino.

## References retained for unchanged native interfaces

- Surface derivatives: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.surface/evaluate
- Native NURBS: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.nurbssurface
- JoinBreps: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.brep/joinbreps
- OpenNURBS/rhino3dm scope: https://www.rhino3d.com/features/developer/rhino3dm/
