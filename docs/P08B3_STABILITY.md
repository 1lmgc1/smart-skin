# P08B.3 — bounded refinement and knot-cell shape control

## Objective

Prevent an accurately joined boundary from legitimizing an exploded interior.
Stabilize construction itself, not merely hide the resulting preview. This is a
preview-only experiment on `p08-mixed-boundary`; installed P07F2, `main`, document
tolerances, source objects and the explicit per-edge G0/G2 assignments are unchanged.

## Implemented path

The existing adaptive positional fit is retained unchanged. Each resulting cubic
Coons patch is inspected before becoming a baseline. An inadmissible Coons seed
may be replaced by a positive-weight, nonuniform discrete harmonic seed with the
SAME frozen outer rows. If neither seed meets the current bounded single-chart
checks, no candidate is shown; this is not a general impossibility claim.

G1 fitting now controls the full transverse derivative, with a nonzero conormal
speed anchored to the opening rather than only a scalar normal-dot equation.
Displacement regularization spreads changes and suppresses unconstrained modes.
Every proposal is scaled to at most 6% of the measured smaller mean opposing-side
span per control point; total movement from the safe baseline is capped at 45%.
These are conservative experimental shape limits, not document tolerances or
universal CAD quality thresholds. Since the basis is nonnegative and sums to one,
the uniform control displacement also bounds pointwise displacement from that
same-basis baseline (up to floating-point arithmetic).

Up to eight backtracking trials must improve measured evidence without sacrificing
an already attained requested grade. Failed trials leave the prior patch unchanged.
G2 acceleration/mixed-derivative equations run ONLY after ALL requested smooth
segments have measured G1. Curvature-only improvement cannot promote a candidate
while G1 remains unresolved. Missing normals, conflicting fixed tangents and
inconclusive shape bounds do not become success. G0-only output may be retained
only if the new shape checks AND unchanged native G0/Join proof pass.

## Shape guard — scope and limitations

`shape_guard.py` handles nonrational degree-three patches with simple interior
knots, matching the existing constructor. Every positive knot cell, including
short boundary strips, is converted to a tensor Bezier net. Its control hull must
fit a finite oriented envelope derived from the opening. A control-hull failure
is a conservative UNRESOLVED outcome, not proof that the surface itself is outside.

The projected Jacobian is formed as a degree-5 by degree-5 Bernstein polynomial.
Positive coefficient bounds establish positivity numerically within a cell;
inconclusive bounds are recursively subdivided. A negative coefficient by itself
is NOT reported as an observed inversion. Nonpositive witness values, nonfinite
values, or exhausted subdivision budgets are rejected. This is a numerical
single-chart guard, NOT outward-rounded interval arithmetic and NOT a universal
self-intersection certificate. Surfaces requiring overhangs/another chart can be
rejected by this conservative route despite being valid 3D surfaces. No automatic
multisurface chart decomposition is implemented in this patch.

Every boundary is measured on original source intervals and knot-aware sites.
The requested tolerances remain 0.01 positional / document angle / 5% curvature
in the current field case; actual document values are read, not overwritten.
Successful G1 or G2 is still a sampled statement. The relative curvature metric
has strict near-flat behaviour; reduced RMS error with a failed maximum remains
unresolved G2, never a claimed match.

## Native conversion, retention and logging

The native Brep conversion, curve deviation, copied-context Join/seam proof,
selection and source-cleanup methods are copied byte-for-byte from the previous
adapter and tested against that baseline. The legacy `rhino_prototype.py` and
`mixed_kernel.py` remain for regression comparison. The delivered bundle uses
`rhino_stable_adapter.py`, `stable_refinement.py`, and `shape_guard.py` instead of
calling the unrestricted legacy refinement loop.

Only a shape-admissible native-Join-verified candidate may replace the displayed
result. Preview grades are `POSITION_ONLY_PREVIEW`, `PARTIAL_G1_PREVIEW`,
`G1_ONLY_PREVIEW`, or `PREFERRED_SAMPLED_MET`, not implicit uniform G2.
Enter/Esc closes without adding an object. This experimental script has no commit path.

TXT writes use unbuffered binary UTF-8 records, with one BOM and record sequence
numbers. The final chosen numerical control net, knots, local origin and checksum
are recorded BEFORE preview. `REPORT_INTEGRITY` carries the preceding record count
and SHA-256 so a partial report is distinguishable. A missing final marker is not
a success or a proved safety check. This hardens reporting; the precise cause of
a previously truncated upload was not established. Logs and nets contain private
geometry and must not be committed to the public repository.

## Tests and publication boundary

New tests independently compare Bezier extraction/Jacobian polynomials with SciPy,
exercise a synthetic narrow spike missed by the legacy 15x15 grid, an out-of-plane
spike with positive projection, subdivision uncertainty, actual bounded G1/G2
attempts, harmonic recovery, rollback, missing supports and large TXT records.
The numerical solver really moves surfaces; tests are not merely policy flags.
OpenNURBS converts stabilized synthetic nets to valid Breps, checks native points
and normals, and writes/reads 3dm. Existing positional, topology and legacy solver
regressions continue to run. They are not substitutes for native Rhino UI and
Join execution on the private model. Those layers remain NOT VERIFIED until the
next field report. Read exact-commit CI before making test-count claims.

## One field action

Run the NEW bundled `SmartSkin_MixedBoundary_Prototype_P08B3.py` using
`_RunPythonScript`. Select a new TXT destination, all six original opening edges,
Enter, all four G0 source segments (both compound sides), Enter. Leave the two
curved segments assigned preferred G2. Do not reinstall the plugin, edit the model,
merge edges, or change runtime/tolerances. Look for `experiment=P08B.3`.

If a bounded candidate survives native checks, photograph its temporary preview.
Enter/Esc closes it; wait for `SMARTSKIN_P08B2_SAVED` and attach the TXT. Historical
`P08B2_*` record prefix is retained; experiment and commit identify this build.
If no candidate appears, the complete report is the result; do not rerun F2.

## Background references

- https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html

The implementation is a custom regularized proposal with bounded backtracking,
not SciPy's trust-region solver. References do not establish private-hole success.
