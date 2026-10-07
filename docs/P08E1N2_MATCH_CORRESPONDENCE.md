# N2 — first-Match correspondence

Version `0.0.23-p08e1n2`. The separate `SmartSkinNativeCompare` command remains a disposable diagnostic. It does not replace the production constructor or change slider behavior.

## Question answered by this experiment

N1 showed that a native EdgeSrf seed can fit the selected boundary while a later Match produces a valid Brep with a worse boundary fit. Its aggregate metrics could not distinguish a target correspondence problem from movement of adjacent sides. A successful native return value does not establish the requested continuity.

N2 preserves the original EdgeSrf seed and performs only the first logical-side Match on independent copies, once for each documented `ReverseMatchDirection` value. It does not chain another Match onto either result. Original and copied parent identities are checked, `Average=false`, and actual parent BrepEdges remain the targets. The native setting reverses the matched edge; it is not a documented per-target-chain orientation adapter.

## Evidence and interpretation

The command reports source/target native intervals and endpoints, logical traversal directions, owning face/trim identity, candidate endpoint correspondence, settings and timings. These are generated locally from the selected input; no private fixture values are built into the command. Command history may contain model coordinates and should be shared only with the intended recipient.

Before and after the attempt, every logical side receives separate finite position, normal and full ambient shape-operator measurements. Unresolved correspondence and candidate-to-source coverage remain visible. Aligned normal angles use the absolute normal dot product; they do not prove occupied-side orientation. Curvature residuals use inverse model units. Edge coverage counts do not certify all-parameter coverage, and ambiguous corner samples are not silently treated as passes.

Seed sides are identified by their physical endpoints. After Match, a unique natural parameter side is tracked as explicitly unverified lineage and accompanied by endpoint distances to all logical corners. Native preservation of that parameter-side identity is not assumed. Missing or duplicate side mappings remain unresolved, and measurements for a named side cannot borrow an unrelated closer source edge.

- Target endpoints or target-side position moving incorrectly can identify a correspondence problem requiring further native evidence.
- A well-matched target accompanied by displaced adjacent sides identifies a preservation or cell-layout problem. Match's OtherEnd setting protects only the opposite side.
- Neither reversal succeeding is not proof that every native route is impossible. This is one bounded operation with specific settings.

The diagnostic grants no corner exemptions, global G2, interior regularity, occupied-side or nonintersection claim. Failed and partial candidates may be viewed for diagnosis but cannot be accepted into the document.

## Field procedure

1. Install the exact successful CI ZIP with all Rhino instances closed. Run `SmartSurfaceVersion` after reopening; verify `0.0.23-p08e1n2` and the delivered commit. This known command also loads the updated plug-in before command discovery.
2. Run `SmartSkinNativeCompare` on the same complete original naked-edge opening.
3. Use Next to inspect the seed and available reversal variants. The candidate label identifies the current output.
4. Enter/Done/Esc disposes the preview; no object is added or replaced. Copy command history from START through CLEANUP and identify any accompanying view by its candidate label.

## Verification boundary

The build targets the official RhinoCommon8.21 SDK. Managed tests and exact-SHA Windows CI check compilation, reporting/planner contracts and installation, without executing Rhino's native geometry engine. The two Match variants and their native measurements require field execution. Cancellation and the time budget are checked between native calls; an individual native call cannot be force-interrupted.
