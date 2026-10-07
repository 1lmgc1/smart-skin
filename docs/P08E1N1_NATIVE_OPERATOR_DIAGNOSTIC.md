# N1 — native operator comparison

Version `0.0.22-p08e1n1`. This is a read-only diagnostic command. It preserves the existing `SmartSurfaceBuild` route and does not claim to fix its default shape or interactive performance.

## Purpose and planning rule

`SmartSkinNativeCompare` compares native Rhino construction recipes on the actual selected edge parents. It captures an ordered naked-edge opening, derives logical sides from geometry and parent branches, and retains internal geometric features within their chains. Selection order, native knot count and preset profile counts are not a new shape specification.

The bounded input is one uniquely identifiable four-chain cell. Native method eligibility is separate from the logical plan: a valid logical side made of several parent edges may be unsupported by an API that requires one edge. Such cases are reported explicitly. This diagnostic does not claim arbitrary topology or complete representation/orientation invariance of every native operator.

There is no scaled-loft center seed, fixed five-profile/nine-row network or hidden Patch fallback. NetworkSurface is deferred when no valid parent-aware crossing network has been established; it is not used to invent the topology.

## Native recipes and evidence

- EdgeSrf creates an eligible seed from the real four boundary chains. Sequential Match attempts may then match its natural edges to the original target chains on copied owners.
- Blend creates an eligible seed between an opposing pair of actual parent faces/edges over their finite native intervals. Eligible natural end edges may then be matched to the remaining target chains.
- Match receives actual copied-owner BrepEdges for G2 targets. `Average=false` prevents intentional parent averaging. `OtherEnd` protects only the opposite end, so every operation is followed by measurements of the whole selected boundary.

Native calls are bounded attempts, not a search for the best-looking surface. Refinement is disabled for this first comparison. Nominal native curvature-percent settings are not treated as the existing absolute physical shape-operator threshold.

Reports distinguish requested continuity, measured position and normal residuals, full ambient shape-operator residuals, coverage, validity/complexity and elapsed operation time. Shape-operator metrics are labeled by norm and inverse-model-unit dimensions. Internal source features receive additional probes and no continuity exception. Sampled measurements do not establish continuous/global G2, interior regularity, outward continuation or absence of intersections; unperformed checks remain `NOT_VERIFIED`.

All original owners remain unchanged. Native work uses disposable copies, and archives are checked for source/copy changes. Bounding, classification and mesh caches must not be mistaken for geometry edits. Native calls cannot be force-interrupted; cancellation/time limits apply at checkpoints between supported calls.

## Field procedure

1. Close Rhino, install the verified exact-CI ZIP normally, reopen the original model and check `SmartSurfaceVersion` for the delivered version and commit.
2. Run `SmartSkinNativeCompare`. Select the complete original naked-edge loop, then Enter. Avoid selecting a previous generated result over the opening.
3. Read recipe eligibility, each native operation's timing and the boundary measurements. A named unsupported recipe is not a pass or a fallback to a different shape.
4. Cycle the available candidate options in the read-only preview. Each label identifies the last successfully produced stage; a failed later Match is not presented as completed geometry.
5. Enter/Done/Esc exits and disposes every candidate. There is no acceptance, export or document-addition path. Copy command history from `SMARTSKIN_NATIVE_COMPARE_START` through `SMARTSKIN_NATIVE_COMPARE_CLEANUP`; screenshots of the selected candidate can show its form.

## Verification boundary

Compile checks target the exact official RhinoCommon8.21 SDK. Pure managed tests cover arithmetic/planner contracts; they do not execute native Rhino surface construction. Exact-SHA Windows CI must pass build, test, package-integrity and installer-lifecycle gates before delivery. Native Rhino API results, timings and diagnostic viewport behavior require this field test.

Mixed or reversed native target-chain direction remains unverified in this first diagnostic; a failed direction-dependent call must not be interpreted as evidence that Rhino cannot construct the surface.

The experiment will inform recipe selection and identify native API limitations on the captured opening. Finite probes cannot establish general impossibility or full attachment suitability. It is not a completed general calculator, a new production skin, or permission to relax source geometry or finite attachment requirements.
