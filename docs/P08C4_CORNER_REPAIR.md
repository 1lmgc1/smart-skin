# P08C.4 — corner construction with explicit candidate-edge relief

## Scope

A source patch for the P08C research constructor, based on P08C.3. It does not update the installed RHP, main branch, toolbar, runtime or installer. The numerical module is developer CPython; the separate `scripts/field/SmartSkin_P08C4_JoinCheck.py` is a Rhino 8 RunPythonScript field checker compatible with IronPython 2.7 syntax. Do not run developer test modules in Rhino.

The objective is to remove severe near-tangent corner curvature by reconstructing the corner derivative fields, then optimizing the full surface shape operator rather than only U/V section curvature. Full numerical proposal screening and native seam checks remain separate from solving. No function grants a product geometry commit.

## Explicit policy, not a silent exact-contour fallback

The optional `CAP_EDGE_RELIEF` path permits a small local change to the CANDIDATE curved edge, never to parent objects. The caller must explicitly set `allow_cap_edge_relief=True` and pass a finite positional budget. The field experiment uses one quarter of its existing document tolerance as this budget. Exact-contour mode refuses the relief when needed. Do not claim numerical equality to all original boundaries after enabling this mode.

Both compound feature boundaries, their internal junctions, the complete middle band, and the previously active side-matching intervals retain their functions. The local curved-edge relief tapers to zero with its first and second derivatives before the active interval. Its positional difference is bounded using the maximum control-vector difference in a nonnegative spline basis, in floating-point arithmetic. Native seam validation must still verify the actual returned Brep topology and deviation at the unchanged document tolerance.

The old `lock_evidence` record intentionally shows `ok=False` for the first relief construction because it reports an exact-boundary test. The new policy checks and reports this boundary change separately while retaining core/active-jet locks. This must not be reinterpreted as a passed exact-contour test. The subsequent optimization must pass the original full locks relative to the explicitly relieved candidate.

## Construction

Use the supplied longitudinal direction and inspect the lower curved-edge parameter derivative. A negative axial endpoint derivative is replaced by its positive counterpart only under the explicit policy, with a finite quintic end correction and a numerical polynomial critical-point test for residual axial backtracking. This is a specialized local route, not a universal contour-healing or axis-inference algorithm.

Reconstruct the full first and second transverse derivative fields across each lower strip using endpoint/core Hermite jets. At each endpoint, choose the normal component of the mixed derivative that minimizes the local shape-operator Frobenius norm with the remaining jets fixed. This is not a proof of a globally attainable optimum. The fixed center is not moved.

A subsequent bounded nonlinear solve includes k1^2+k2^2, using mixed derivatives and analytical gradients tested by finite differences. Corner mixed-normal values are retained in coefficient null modes. The previous section-curvature and silhouette terms remain. Final coupled XYZ displacement is clipped, then locks are checked again. Bounds apply to each construction stage; final cumulative displacement must be measured by the caller. Budgets are finite, and cancellation errors cannot become acceptance.

The low-level functions return proposals. Independent checks must compare both U/V maxima and p99, principal-curvature maxima/p99, silhouette excursions, all boundary budgets and source junctions, fixed core and active jets, and local regularity after the final step. Poor candidates, including a candidate whose U curvature increases, are not field results simply because an objective decreases. Degree 5x5 is a deliberately bounded route, not an inferred universal optimum.

## Native field checker

The separately exported private .3dm has one new result and its old baseline, plus the original objects. Only the new result carries a small JSON source-segment contract in its object attributes. Source IDs and model coordinates are private file metadata; none are embedded in this public script or sent to CI.

Open that .3dm using File > Open. Run only `SmartSkin_P08C4_JoinCheck.py` with `_RunPythonScript`. Select one TXT destination and then the new cap. The helper resolves the six input segments and their parents through the contract; no repeated six-edge selection or plug-in installation is required. Units and tolerance are checked. Do not Explode, Join, transform or manually MatchSrf the test model first.

All operations are on copies. Ordinary `Brep.JoinBreps` must return one valid manifold result. Identify the cap face, reject remaining naked/nonmanifold cap edges, match every target segment to interior seam chains adjacent to the expected parent surface, measure both distance directions, and account for every cap seam. A joined object count alone is not proof that all six required seams closed. Existing unrelated source holes do not require the result to be a solid.

Then execute a native Brep/Brep intersection screen against the parents. Sample returned intersection curves to flag events away from the cap boundary. This is diagnostic finite sampling, not a global self/parent-intersection certificate. A successful Join is not surface fairness or G2. The checker never adds/replaces/deletes document geometry and does not authorize the construction result as a finished product.

TXT writing has one save dialog, explicit overwrite confirmation, flush per line and final checksum/readback. An error stops without a repeated-save loop. Native calls cannot be force-aborted; budgets and Esc are observed between supported operations. Actual Rhino execution, file-dialog/CLR binding and final Join results remain NOT VERIFIED until the returned field report.

## Evidence discipline

CI runs the old 40-test UV suite, old 30-test geometric suite, and the new synthetic numerical and actual file-I/O tests. Python-2 grammar is checked for the field helper, and its native API signatures are compiled against the project's existing RhinoCommon 8.21 package. Grammar and compilation do NOT execute Rhino, model geometry or the IronPython binder. Source guards preserve the installed product and preceding constructors.

The real-model run, exact surface net, deviation and curvature metrics, relief budget, source hashes and roundtrip evidence belong in the private journal/recovery. Do not publish private models, coordinates, object IDs, or raw field reports to this repository.

## References

- https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.brep/joinbreps
- https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.curve/getdistancesbetweencurves
- https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_BrepBrep.htm
- https://docs.mcneel.com/rhino/8/help/en-us/commands/runpythonscript.htm
