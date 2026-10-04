# P08D.1A — executable joint strip graph and shared seam fields

This is the first executable layer of P08D.1, not the completed design. Base: documentation commit f7869f82a0d6fe58b39a254a6b83248871571d71. Product src/tests, RHP, UI, installers, earlier experiments and old native checker are unchanged.

## Implemented

- Three-strip PatchGraph with immutable proposal copies, two SharedSeam records, source-side interval allocation and omission/duplication checks. Logical source intervals may be split into more exterior pieces. Source parameter orientation is preserved. The generic source key is supplied by the host; private parent/face/trim identifiers are not in this module.
- Exact split as a negative control: it may initialize this graph but cannot claim any form repair. New shape is made only by a joint coefficient solve across all three patch nets.
- A single normalized linear constraint system enforces full outer boundary functions, the center profile, unchanged active external first/second parameter jets, retained lower corner mixed derivatives, and inherited knot jumps. Shared C/D/E are equal across the two sides in a common affine chart, including width-dependent derivative scaling. They are NOT frozen at their baseline values. All XYZ nets are solved together; both neighbors share the same seam fields.
- The surrounding center may move. Full-band lock is not used here. The current affine station layout is fixed, so seam endpoints do not slide in this version. The shared curves may move inside the shape while keeping those endpoints.
- Bounded nonlinear search uses geometric section curvature, the full shape operator, explicit silhouette halfspaces, and a chord-arc-length normal-rate variation term with analytical gradients including chord-length derivatives. The target is neither universal monotonicity nor an assertion of G3. A unit-normal path is reconstructed from the actual surface; independently prescribed normals are not treated as a surface.
- Optional symmetry and a fixed coordinate are explicit policies. Unverified symmetry is rejected. A fixed coordinate is an extra experiment, not an automatic axis detector.
- Bounded immutable rollback uses independent knot-aware common sites and fixed-coordinate plane sections. These sections use a sampled unique crossing bracket and implicit derivatives; ambiguous, missing, or singular crossings are unavailable, not zero. Their coverage is not a global intersection certificate.
- Normal flow, both section families, principal curvature, silhouette and local regularity are measured separately. A better aggregate objective cannot bypass a worse required measurement. Exact identity receives REPRESENTATION_ONLY_NOT_FORM_REPAIR. All statuses have geometry_commit=False and native_Join=NOT_RUN.

## Boundaries that remain incomplete

This first layer retains the active exterior parameter jets. It does not yet optimize geometrically equivalent parent-side speeds/shear, move seam endpoint stations, infer the axis, fit an arbitrary new profile, search topology/degree, or build the four revised corner rotation laws from scratch. The old compatible longitudinal basis is used. It is NOT the full P08D.1 guide optimizer.

The boundary policy may be EXACT_SOURCE or explicitly CAP_EDGE_RELIEF with an inherited cumulative bound. Joint updates leave the supplied boundary functions unchanged. Inherited relief is still relief relative to the original source, not exact source equality. Parent healing is not supported. The host must preserve the original provenance and recheck any inherited bound; no old Join outcome transfers to a new candidate.

The multi-face native Rhino Join/trim-image verifier and user UI are NOT IMPLEMENTED in this stage. Synthetic OpenNURBS roundtrip is not Rhino Join. No developer script in this directory is a Rhino RunPythonScript command. No revised private CAD result should be released for field use merely because these tests pass.

## Numerical scope and known limitations

Nonrational tensor bases, common longitudinal knot vector and degree, positive affine transverse intervals in a unit chart, bounded degree inherited from Tensor. A tiny actual positive knot span below the route resolution stops with a diagnosis. Only round-off duplicates in the sampled parameter set are coalesced; geometric spans are not removed.

The discrete normal-flow energy averages, over section paths, the integral of squared changes in dN/ds divided by path length; it has units length^-4. Finite chord lengths approximate arc length, and sampling affects the value. Use common site fingerprints and physical sections when comparing. No fairness, global injectivity, Class A, or convergence guarantee is implied. The baseline itself may have rejected form.

## Verification

Tests execute actual splines, a coupled solve, mixed-jet constraints, unequal widths, shared-field changes, interval coverage, reversals, relief policy, analytic gradients, physical sections, cancellation, finite budgets and rollback. A native three-surface OpenNURBS write/read test is mandatory in GitHub Actions, and explicitly skipped locally when rhino3dm is unavailable. Test outputs must distinguish those scopes.

Private model runs belong only in the private recovery and journal, never in repository fixtures. No private coordinates, IDs, reports, or model files are embedded here.

Developer invocation (NOT Rhino):

```bash
python -m pip install numpy==2.2.6 scipy==1.15.3 rhino3dm==8.17.0
export PYTHONPATH=experiments/P08D.StructuredTransition:experiments/P08C.CornerRepair:experiments/P08C.GeometricFairing:experiments/P08C.UVFairing
python -m unittest discover -s experiments/P08D.StructuredTransition -p 'test_*.py' -v
```

Primary API references: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.null_space.html ; https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html ; https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/
