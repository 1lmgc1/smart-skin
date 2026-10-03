# P08B.1 — mixed boundary conditions and local recovery

## Status and scope

Architecture and a standalone executable acceptance-policy prototype. This is NOT a released Rhino plug-in, a new hole solver or an upgrade to the P07F2 native verification gate. `main`, RHP source, current version, installer and product UI stay unchanged. The prototype consumes synthetic/supplied observations; it does not measure geometry or prove mathematical feasibility. Native mixed construction, result verification, UI integration and actual model acceptance remain NOT VERIFIED / NOT IMPLEMENTED here.

## Product decision

Failure to obtain one requested smooth transition must not by itself discard an otherwise usable closed candidate or force every boundary to the same continuity. Position and topology remain non-negotiable; preferred smoothness, minimum allowed smoothness, geometric method and achieved evidence are separate per-boundary concepts. A positional G0 feature is a legitimate design boundary, not a failed G2 edge. Planarity alone never authorizes reducing continuity.

Maintain an immutable `BoundaryContract` across all construction attempts. Each condition has a stable source object/edge/trim/face identity and interval, preferred G0/G1/G2, explicit minimum, role (smooth continuation or preserved feature), source edit permission and the reason/authority for any change. Do not use selection order, a hardcoded slot number, screen direction, filenames or model coordinates as the rule identifier. Topological splits must retain interval coverage and ancestry; splitting one edge does not create extra quality credit.

The current default exploratory hierarchy is: first try the selected preferred conditions; try other methods at the SAME conditions; only then propose a local G2->G1 or G1->G0 candidate on affected unlocked intervals. A sharp feature remains positional. An explicitly locked G2 edge does not silently become G1. Finding an adequate mixed result does not prove that all higher grades are impossible. Unknown metrics and a native call failure must be labelled unavailable/algorithm failure, not geometric impossibility.

## Candidate-level hard conditions

Every committable candidate must provide G0 within the unchanged document tolerance over the complete selected opening and every internal seam, valid bounded Brep topology, unambiguous source/face mapping, required seam coverage and Join proof, no unintended naked cap boundaries, preserved original parents in source-fixed mode and the declared shape/feature checks. A high angle is not a failure on an intentional sharp boundary. Relaxing smoothness does not authorize a gap, loose unjoined patches, self-intersections, missing faces, silent parent edits or larger document tolerance.

Brep.IsValid alone is not a foldover/self-intersection or fairness certificate. The native adapter must state which shape checks were actually performed and their limitations. A check cannot be marked Passed because a constructor returned a Brep. Unknown hard evidence does not allow commit.

## Policy prototype implemented in this branch

`experiments/P08B.MixedBoundary/BoundaryAcceptance.cs` evaluates one immutable candidate revision under one contract revision. It requires one observation for each stable boundary key, rejects stale/mixed or duplicate records, applies per-edge G0/G1/G2 evidence prerequisites and retains the grades for unaffected edges. Its states are:

- Ready: all preferred conditions met, including legitimately mixed G2/G0 conditions.
- ReviewRequired: all hard conditions and edge minima met; some preferred smoothness not met or not measured. The exact supported grades/reasons must be displayed before normal user confirmation may accept it.
- PreviewOnly: a closed verified baseline exists, but one locked minimum remains unsatisfied. Retain it for continued work/inspection without commit. Change the contract explicitly or try another method.
- Rejected: incomplete/failed position, identity, topology, seam or other hard evidence. Reject THIS candidate, not necessarily the whole operation or a previously retained good candidate.

Confirmation is bound to both candidate and contract revisions. All final evidence must describe the SAME complete result: never combine good edge measurements from different attempts to fabricate a passing surface. Missing high-order data is not zero error. The prototype is only a policy model and is not wired into the product command.

## Construction routes to evaluate next

The released closed radial seed has one principal closed boundary and one global MatchSrfSettings. The documented CreateFromMatch overload accepts one settings object for the entire passed target collection, not six independent boundary requirements. Splitting its topological edge alone is not proof that the resulting pieces are supported untrimmed matching sides. Passing detached curves alongside BrepEdge under G2 is not a documented way to request per-target G0/G2.

1. Prefer a support-aware three/four-sided layout or a small connected patch layout whose sides correspond to compatible boundary chains. Preserve true BrepEdge/face constraints rather than losing them when joining or rebuilding curves. A mixed chain needs explicit per-segment support handling; the ordered Network API's four side conditions are not arbitrary six-edge conditions.
2. Evaluate ordered NurbsSurface.CreateNetworkSurface, which exposes independent first/last U/V continuity. Validate its actual surface support and all output conditions. It is a candidate constructor, not a guarantee of meeting them.
3. Evaluate local MatchSrf or constrained control-row refinement on suitable untrimmed result sides, preserving relevant ends. Sequential matching can disturb previously fitted adjacent sides; after EVERY change invalidate/recompute the whole candidate's boundary and internal-seam evidence. Preserve-other-end only constrains the opposite end, not all other boundaries.
4. When one surface is unsuitable, use a bounded number of connected NURBS patches and, where justified, a local transition strip. Keep the visible product one result Brep with one preview and one Undo operation. Every new internal seam must meet its declared condition; do not move the failure from the external boundary into an unmeasured interior seam.
5. Topology/trim/edge repair is a separate evidence-driven route on copies, not a generic response to conflicting smoothness. Rebuild/split/extend/retrim only when diagnosed and revalidate geometry and feature preservation. Changes to original parent geometry remain an explicit separate mode; current authorization to try local methods is not unrestricted authorization to move parents.

No automatic CreatePatch fallback and no all-G0-only strategy that abandons already attainable smoothness. Method search is bounded by attempts, complexity and time, with Esc at supported checkpoints. Retain the best fully evaluated candidate; a failed later attempt must not erase it. Rank on hard feasibility, locked conditions, retained preferred boundary coverage and shape quality, not only total gap or raw count of subdivided edges. Search/ranking/retention integration is NOT implemented by the standalone policy prototype.

## UI and reporting contract

Keep the accepted one-button, one live-window, Enter/Space/right-click acceptance and Esc cancellation. Highlight affected intervals and show requested/minimum/achieved grades in the same window. A mixed success is `READY_MIXED`, not `G2_VERIFIED` for the whole cap. A local compromise is visible before the ordinary confirmation; there is no silent downgrade. Do not ask for a separate confirmation dialog for every internal solver attempt. An unfinished estimate cannot authorize commit.

Keep the complete result and attempt log in a user-selected TXT, short console progress, and explicit final action/safety status. No repetition of installation, runtime or parent-selection tests. No model identities or field logs are included in this public branch.

## Next work and acceptance gates

B1 (this iteration): accepted behavior, API feasibility review, executable policy states and synthetic regression checks.
B2: native constructive prototype with support-aware layout, mixed conditions and per-edge/internal-seam measurement; evaluate on synthetic geometry before one consolidated field attempt. Do not rerun the old all-G2 audit as a substitute.
B3: integrate only the demonstrated route, best-candidate retention, mixed-status preview, bound confirmation and TXT reporting into a new versioned RHP. Run Core/native regressions; distinguish CI compilation from field geometry evidence.

Needed native tests include a smooth opening, an intentional sharp boundary, conflicting corner limits, a curved trimmed target, fragmented source edges, a deliberately bad gap, an internal seam failure, failed late refinement preserving a previous candidate, source preservation and rejection of stale measurements. Exact analytical G2 and sampled verification are not interchangeable.

## Official API references checked for this decision

- CreateFromMatch target/continuity contract: https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Brep_CreateFromMatch_1.htm
- MatchSrf supported edges and preserve-other-end semantics: https://docs.mcneel.com/rhino/8/help/en-us/commands/matchsrf.htm
- Ordered Network independent U/V side conditions: https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_NurbsSurface_CreateNetworkSurface_1.htm

A public documentation page may reflect a later build; use only APIs available in the installed Rhino 8 baseline and compile/check its exact signatures before native integration. The references establish available interfaces, not tested success on a private model.
