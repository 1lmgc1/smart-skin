# P08B.2 — boundary-fixed constructive experiment

This is an actual B-spline construction prototype and a PREVIEW-ONLY Rhino adapter, not a replacement RHP or a proven private-hole solution. `main`, released P07F2 code, installer and UI are unchanged. P08B.1's acceptance policy is not bypassed or claimed integrated. The experimental adapter NEVER adds/replaces/deletes document geometry; Enter/Esc only closes its transient preview.

## Implemented construction

Four boundary chains are fitted to clamped cubic B-splines by Householder least squares with shared endpoint conditions. A tensor-product Coons control net establishes the positional baseline. All outer control rows are then locked exactly, so every refinement preserves the same complete fitted boundary rather than moving one edge while matching another.

The next steps solve sparse, globally assembled normal constraints at all requested smooth boundaries simultaneously. G1 imposes `n·S_cross=0`. G2 adds the linearized normal-second-derivative condition `n·S_cross,cross=II_parent(S_cross_tangent,S_cross_tangent)`. A bounded preconditioned iterative solve regularizes unconstrained displacement to the prior net. The next full candidate is evaluated from scratch; failed refinements cannot erase a previously retained eligible candidate. A target request is never relabelled as an achieved grade.

Input boundary coordinates are expressed relative to a local origin for conditioning. Face normals and world-space shape operators retain their original parent/trim/edge identity, orientation and interval. Joining boundary curves is not used to invent derivative support. Sharp G0 intervals contribute position but not tangent/curvature constraints. No inference from planarity alone and no hardcoded model IDs, indices, filenames, coordinates or selection order assigns G0.

This iteration implements a SINGLE regular four-sided patch with fragmented side chains, not automatic multipatch layout. A sampled seam-measurement helper is implemented and tested on distinct surfaces, including gap, tangent kink and curvature discontinuity. In the constructed single-patch candidate there are zero internal Brep seams; the adapter reports that explicitly. Automatic seam-aware multipatch generation remains future work, not a claimed completed feature.

## Scope of geometry evidence

Every candidate is independently sampled over all original intervals, endpoints and near-junction points. Position uses explicit boundary correspondence; derivative evidence includes tangent plane and a relative full shape-operator residual. This tensor residual with a 5% threshold is NOT the old P07 single cross-curvature/radius metric and is not directly comparable to its numeric percentage. Both nearly-flat tensors below 1e-9 inverse model units use a declared numerical floor. Endpoint singularities and missing parent data remain unavailable, not zero. No analytic/global G2 claim is made.

A sampled Jacobian/projected-orientation check rejects observed degeneracy and foldback in the regular interior. It is conservative and is NOT an exhaustive self-intersection, foldover or fairness certificate. The adapter therefore never enables document commit even when all its checks pass.

On Rhino, each eligible whole candidate is converted to native NURBS/Brep. Its points are compared to the numerical net, its entire boundary is measured natively in both directions against the original selected edges, and copies of all parents plus the candidate are joined. A Join proof requires a unique preserved candidate face, all its boundary edges becoming two-face interior seams, one closed cap-to-context seam and native deviation within the original document tolerance. A positional end-feature seam is intentionally not required to be smooth. Neither Join nor this proof runs on originals.

All evidence is bound to one candidate/contract revision. The best candidate is retained only after native position/Join checks; new failures or the soft time budget do not erase it. High-order unavailability may leave a useful positional preview, not a false smoothness claim. Source snapshot equality and counts are checked on final exit.

## Bounded experiment and field action

The compiled plug-in stays P07F2. Run the bundled `SmartSkin_MixedBoundary_Prototype.py` inside Rhino via `_RunPythonScript`; no package installation, external Python, second RHP or runtime change is required.

1. Choose a TXT destination (full UTF-8 report with per-record flush).
2. Select all opening Brep edges (the prepared six-edge opening), finish with Enter.
3. Select ONLY the two opening edges at the end face to preserve as sharp G0, finish with Enter. This is an explicit boundary-role selection, NOT selecting entire parent objects. Other selected opening edges keep preferred G2.
4. The prototype enumerates up to six four-side chain layouts and 10/16 control-point resolutions, with four refinement steps. The 120-second budget and Esc are checked between bounded calls; one native call cannot be force-aborted. The preview shows only a candidate with a completed native G0/Join proof. Enter or Esc closes without adding anything.
5. Return the saved TXT and, when a preview exists, one screenshot BEFORE closing. Do not rerun the old all-G2 audit. Do not delete another surface or increase tolerances.

One contiguous sharp chain and at least three remaining smooth source intervals are the bounded layout prerequisite here. General mixed networks with several disjoint sharp chains require the future layout stage. Unsupported input reports this explicitly rather than guessing roles or moving parents.

## Verification and limitations

The automated tests construct real numerical B-spline surfaces from boundary/parent differential data, rather than supplying fabricated achieved grades. They include nonplanar boundaries, a nonflat mixed 4G2/2G0 case, incompatible normals, frozen G0 rows, independent dense checks, late-failure retention and actual two-surface seam measurements. Basis/derivative/least-squares results are checked against independent SciPy/NumPy implementations.

A separate test converts the resulting control nets through compiled OpenNURBS (`rhino3dm 8.17.0`), validates the Breps, compares native point/normal evaluations and writes/reads a synthetic 3dm. That is actual native geometry evidence, but it does NOT run licensed RhinoCommon Join, the Rhino UI, trim-based field extraction or the private model. A compile-only RhinoCommon 8.21 probe verifies public API availability, not Python binding/runtime execution. Exact CI logs must be checked; the private hole and adapter's Rhino execution remain NOT VERIFIED until field evidence.

OpenNURBS test dependencies exist only in CI. The user script is standard Python plus the installed RhinoCommon environment; no numpy/scipy/rhino3dm installation is requested from the user. The TXT can contain source identities and coordinates and must stay in the private conversation/journal. Public fixtures are synthetic only.

## References

- Surface evaluation derivative order: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.surface/evaluate
- Native NURBS construction: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.nurbssurface
- JoinBreps: https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.brep/joinbreps
- Orientation: https://discourse.mcneel.com/t/brep-flip-brep-face-reverse-brep-surface-reverse-inconsistencies/153688/3
- OpenNURBS/rhino3dm scope: https://www.rhino3d.com/features/developer/rhino3dm/
