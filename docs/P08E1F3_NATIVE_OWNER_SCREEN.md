# P08E1F3 bounded native-owner screen

## Status and claim

**VERIFIED:** headless policy/adapter tests using public synthetic rectangles, trim holes and scripted native outcomes. This tests Python control flow and the adapter contract.

**STATICALLY CHECKED:** RhinoCommon API availability/signatures, copied-owner lifecycle and integration API.

**NOT VERIFIED:** licensed Rhino 8 execution, CPython/.NET overload selection, Rhino geometry-kernel behavior, native timing and GUI cancellation. No private model was used.

The screen accounts for every generated patch × captured full-owner pair. It is a finite numerical intersection/overlap screen, not a global no-overlap theorem. `global_injectivity_certified` remains `false`. Cap-cap separation belongs to the separate atlas validator.

## Integration contract

Module: `src/SmartSkin.Rhino8/Python/native_owner_separation.py`.
Runtime alias: `_smartskin_p08e1_native_owner_separation`.

1. Create one context per source capture with `create_owner_context(doc, capture, Rhino, cancelled=None, limits=None)`. This copies the original full Breps, pins their fingerprints, and retains a live source/document/tolerance check. Original geometry and attributes are never changed. Both absolute and angular tolerances are pinned from the capture and compared with the current document before screening; changing document angle during numerical preparation cannot silently create a new native acceptance tolerance. Non-Brep owner conversion is deliberately unsupported.
2. Obtain the independently G0-validated `result['native_contact_ledger']`. It carries source and descriptor digests, exact selected-source/generated exterior intervals, and separate zero-dimensional corner contacts. Internal seams are never finite allowed contacts.
3. Convert the current numerical output using `make_native_geometry`.
4. Before publishing the result or marking preview/commit ready, call `screen_native_owners(breps, context, ledger, request=None, cancelled=None)`. `request` is the exact selected-handle request, or `None` for baseline.
5. Store the returned immutable `SeparationReceipt` separately from result dictionaries. `receipt.report` is a defensive copy for reporting. A receipt has no disposable native objects.
6. Before every document Add and after the batch, call `verify_receipt(receipt, breps, context, ledger, request=None, cancelled=None)`. Any changed native geometry, source copy/provenance, document tolerance, request, contact ledger or limits rejects. Live source verification is repeated.
7. Invalidate the current receipt on every new request, failed/cancelled evaluation, and restoration of an older preview. A restored preview must be screened afresh before confirmation. Never infer authority from a result-side `checked` flag.
8. Call `context.dispose()` when the preview session closes. Disposal is idempotent and affects copied owners/prepared boundary curves only.

All failures raise `SeparationError`, a `RuntimeError` with a `.code`. Failure, partial output, cancellation and exhausted budgets return no receipt.

## Stable native archive fingerprints

The full native archive SHA256 remains the integrity authority. Before every fingerprint (converter issue/verify and owner-screen issue/verify), the shared adapter calls `GetBoundingBox(false)` and reads `IsSolid` on Breps. These are bounded read-only cache preparations. Geometry, topology, trim data, orientation and UserData are not rebuilt, removed, rounded, or replaced by a CRC.

Official openNURBS serialization includes lazy Brep bounding-box and solid-classification fields. Public planar NURBS fixtures reproduce raw archive changes after those two reads while their surface definitions, vertices and orientations remain unchanged. Repeating the shared fingerprint preparation then remains stable. The separate accurate bounding-box operation uses a local result; the inexpensive false overload prepares the serialized Brep cache without repeating the costly tight calculation at every fingerprint. See [Brep archive writer](https://raw.githubusercontent.com/mcneel/opennurbs/8.x/opennurbs_brep_io.cpp) and [bounding-box/solid implementation](https://raw.githubusercontent.com/mcneel/opennurbs/8.x/opennurbs_brep.cpp).

Unexpected archive drift still rejects. Private component snapshots classify the mismatch as source, tolerances, limits, contacts, request, copied-owner scope, or generated patch archives. User-facing diagnostics include bounded zero-based patch/owner indices, without raw geometry, IDs, hashes or parameter payloads. No failure silently refreshes an acceptance receipt.

`tests/python/test_native_archive_cache.py` runs three public tests against pinned rhino3dm8.17: the cache-change reproduction, production adapter priming, and continued rejection of actual geometry/UserData changes. Jobs without this optional test dependency explicitly skip those tests. Adapter/mocked full-screen coverage separately verifies the false-box → accurate-box preparation → event/proximity checks → unchanged full fingerprint order. Actual Rhino8.35 intersector/closest-point behavior and all possible future cache effects remain NOT VERIFIED; residual drift stays fail-closed with component diagnostics.

## Screen stages

- Validate/bound all owner faces and all generated patches; prepare conservative native bounding boxes, copied actual Brep edges and native actual-trim interior witnesses. Reuse owner preparation across edits while immutable fingerprints match.
- Account for every pair. Prune only boxes separated beyond the fixed captured tolerance.
- For each remaining pair, run native Brep/Brep intersection and classify every curve and point.
- Even when native Brep/Brep produces empty arrays, run both generated-edge → owner and owner-edge → patch Curve/Brep screens.
- Test interior witnesses in both directions using trimmed-Brep closest points with `maximumDistance=0`. Every face uses a 5×5 native face-UV grid; sparse faces additionally try 9×9. Require at least four actual `Interior` witnesses per face. Topological membership uses zero tolerance so narrow interiors are not erased; document tolerance remains unchanged for intersection and contact calls. Missing coverage and failed queries reject. Distance at/below document tolerance rejects unless the generated-to-original-owner query passes the exact selected-boundary exterior classification below. Reciprocal owner-interior-to-cap queries remain conservative.

This finite complement detects common coincident-area/containment failures without silently accepting empty Brep/Brep output. Small unsampled coincidence regions can remain; the report explicitly states that limitation. `minimum_sampled_clearance` is a sampled metric, never a whole-surface clearance bound.

## Contact classification

An allowed finite curve must be wholly covered by native Curve/Curve overlap intervals against BOTH members of the SAME trusted source/generated exterior binding. Unioning multiple legitimate bindings is allowed; closing any positive parameter gap by epsilon is not. Point proximity cannot authorize a curve.

Isolated point contacts must bind a generated native patch corner to a selected-source parameter that is also an independently checked exterior-trace endpoint. The adapter re-evaluates both native points and uses the captured tolerance. Such bindings authorize event points only, never positive-length internal seam curves. For sampled proximity they may also identify the exact source corner used by the independent captured-sector and current-native-frame exterior classification below; point identity alone never permits an interior witness. They introduce no continuity/regularity exemptions or finite excluded strips.

### Narrow boundary-adjacent interiors

A nearest native boundary edge is different from coincident active face interior. For a generated witness within document tolerance of its original owner, the screen may classify positive, numerically resolved edge distance as exterior only when the closest component is the exact selected edge, its native parameter is in a current trusted contact binding, and captured native trim/face identity and orientation agree. Ordinary edge interiors require strict outward co-normal displacement evaluated from native derivatives. Frame recovery maps a surface closest-point UV seed onto the exact captured BrepTrim with Trim.ClosestPoint and Trim.PointAt; it verifies world reconstruction before evaluating the native derivatives. It does not rely on approximate recovered UV being reported as Boundary at zero tolerance. Exact native source endpoints use their captured exterior wedge. A current exact source-corner point binding may also classify proximity to the specifically captured same-face adjacent trim edge, provided its actual nearest parameter is interior to that adjacent edge, the witness is strictly in the captured exterior sector, and the native tangent/normal at the actual nearest point independently establish the exterior side. A fixed tangent wedge at the vertex alone is insufficient for a curved adjacent edge. A face-classified boundary point must resolve exactly to the selected edge; an active face-interior closest point still rejects.

This rule adds no spatial exclusion band. It cannot authorize any Brep/Brep or Curve/Brep event, any unbound contact, a zero-distance point, or a finite continuity exemption. The report counts exterior-edge and exterior-corner witnesses separately; sampled minimum clearance may therefore be below document tolerance without denoting overlap. Public adapter tests include an attached sector of width 0.0001 at document tolerance 0.001, wrong/missing side evidence, zero clearance, face-interior coincidence, an incident adjacent-edge case inside the selected-edge half-plane but outside the owner corner sector, rejection when the adjacent local frame turns inward, and a forbidden intersection curve.

## Explicit budgets

Default `ScreenLimits`: 32 patches, 16 owners, 512 pairs, 128 aggregate faces, 640 aggregate edges, 262,144 aggregate surface control points, degree ≤64, 4,096 curve controls, 4,096 aggregate events, 8,192 witnesses, 20,000 native calls, 64 MiB copied-owner memory estimate, and 15 seconds per screen observed between calls.

The outer preview phase budgets are separate: 180 seconds cold and 60 seconds cached. The native screen retains its own explicit 15-second cap; it must also honor the caller's phase-cancellation callback. Expiration rejects the current result instead of skipping a stage or accepting partial pair coverage. These limits are policy bounds, not measured native performance promises.

Native calls run synchronously on Rhino's supported UI/command path. They expose no hard cancellation within a Brep/Brep operation. Esc, supersession and time limits are checked before and after calls. Returned disposable objects are cleaned up even if cancellation is observed immediately after allocation.

## Rhino 8 API references

- [Intersection.BrepBrep](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_BrepBrep_1.htm): `bool BrepBrep(Brep, Brep, double, bool joinCurves, out Curve[], out Point3d[])`, since 8.12. The adapter sets `joinCurves=false`. False is an operation failure.
- [Intersection.CurveBrep](https://developer.rhino3d.com/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_CurveBrep.htm): `bool CurveBrep(Curve, Brep, double, out Curve[], out Point3d[])`, since 5.0. Output curves represent overlaps; false can accompany partial results and always rejects. The documented six-parameter overload also outputs `double[] curveParameters` (since 6.0); Python.NET may select this overload for the same three explicit inputs. The adapter accepts and validates either three- or four-item output, including finite in-domain parameters matching the point count. Brep/Brep remains strict three-item output.
- [Intersection.CurveCurve](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Intersect_Intersection_CurveCurve.htm): `CurveIntersections CurveCurve(Curve, Curve, double, double)`, since 5.0; [OverlapA](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/P_Rhino_Geometry_Intersect_IntersectionEvent_OverlapA.htm) supplies tested-curve overlap intervals.
- [Brep.ClosestPoint](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Brep_ClosestPoint_1.htm): `bool ClosestPoint(Point3d, out Point3d, out ComponentIndex, out double s, out double t, double maximumDistance, out Vector3d)`, since 5.0. It respects active trimmed geometry. Zero maximum distance avoids confusing an out-of-range miss with failure. Only `s` is meaningful for an edge component; both parameters are required for a face.
- [BrepFace.IsPointOnFace](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_BrepFace_IsPointOnFace_1.htm): `PointFaceRelation IsPointOnFace(double, double, double)`, since 7.0. Its tolerance is in 3D units.

## Tests and field gate

Run `python -B -m unittest discover -s tests/python -p test_native_owner_separation.py -v`.

Coverage includes all-pair accounting; bbox near misses; empty native intersection plus overlap/containment complement; complete/partial/mismatched overlap intervals; source identity and internal-seam rejection; isolated corners; trim holes and insufficient interior coverage; cancellation, deadlines, event/call budgets and cleanup; immutable-copy and request/geometry/ledger receipt checks; copied-source lifecycle; affine generated reparameterization, translation, quarter-turn rotation and reversed source direction.

Before native acceptance is described as field-tested, execute the actual Rhino path on public synthetic disjoint/attached/crossing/tangent/coincident/contained/trim-hole/extra-owner-face fixtures, plus repeated edits, Esc, source edits and transaction rollback. Mock passes do not establish those native results.
