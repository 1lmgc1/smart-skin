# P08C.2 — bounded basis selection and interior-section fairing

## Architectural objective

Implement the previously reviewed UV/degree policy without changing the released plugin, P08B construction, P08C.1 geometry, source contours, or tolerances. This is a CPython/NumPy/SciPy numerical experiment, NOT a Rhino `_RunPythonScript` command or a new RHP. The user's original geometry, identifiers, coordinates, and private measurements must never enter this public branch or CI.

## Implemented

- Validated nonrational clamped tensor B-splines with separate degrees and knot vectors for each direction.
- One-knot removal by inverse Boehm insertion. The reconstruction residual is measured in the original nonnegative basis, giving a floating-point coefficient bound on positional change. Accumulate the error budget; keep non-removable or explicitly protected source junctions. This is representation reduction, not shape repair or a claim of globally minimal control count.
- Independent degree trials per axis. Conversion is checked span by span using a common polynomial Bernstein representation. Reject a lower-degree trial when its bound exceeds the strict representation budget; elevation alone is not an improvement. Failure of this conversion does not prove no other low-degree or multipatch construction could work.
- Full first/second/mixed derivative transformation under a supplied nonsingular two-parameter map, including the map Hessians. This helper is NOT an implemented automatic correspondence optimizer. Existing verified parameter mappings remain unchanged unless an explicit new map is provided and validated.
- Actual quadratic interior optimization in coefficient-space null modes. Full boundary curves, compound junctions, the central band, and both transverse derivative functions on the active side intervals remain locked. Preserve the jumps of the original representation; do not introduce new C1/C2 jumps in the increment. A profile-only research option is explicit, not mislabeled as a fixed band.
- Bound a coupled XYZ control-point displacement. Rejected proposals never replace the baseline; backtracking is finite.
- Mandatory `screen_proposal`: locked boundary/core/active jets, actual geometric section-curvature non-regression in BOTH U and V, local 3D regularity, and a reduction of the quadratic objective. A lower least-squares energy alone can NEVER select the new result.

## Important distinction: objective vs geometry

The quadratic objective integrates squared parameter derivatives in explicit reference scales. It is not a parameterization-invariant curvature integral. A proposal can reduce this objective and still create a sharper geometric curvature peak in one family. Therefore independently screen actual isocurve curvature `|D x DD| / |D|^3` on identical knot-aware sites for both old and new surfaces, checking both maximum and 99th percentile in U and V. No sample is silently removed because it is degenerate. This is a conservative finite-site screen, not a proof of global extrema or a complete definition of aesthetic fairness.

Do not label a numerically solved or locally regular proposal as a finished cap. A failed screen returns `BASELINE_RETAINED_NOT_CERTIFIED`. The original baseline may itself still need repair. The low-level `fair_candidate` returns a proposal only and explicitly supplies no acceptance.

## Local regularity

Each actual positive knot cell is converted to a Bernstein representation. A separating direction bounds the 3D derivative cross-product; uncertain cells subdivide within explicit node/depth limits. Different local separating directions prove only local numerical non-vanishing, NOT global injectivity, orientability across arbitrary nonsmooth seams, absence of all self-intersections, or absence of parent collisions. Failed/unknown bounds are not reported as a positive default value. Cancellation callbacks are supported between cells.

## Verification and release boundary

Synthetic tests run genuine splines, constrained optimization, nonlinear second-jet transforms, knot/degree conversions, all-boundary and whole-band invariance, geometric curvature screens, rollback, local folds, and native OpenNURBS construction/3dm roundtrip. This does NOT execute RhinoCommon Join, Rhino UI, IronPython, or a private model. Inspect the exact CI run for actual pass/fail and count.

The private-model experiment is recorded in the private journal. It may accept a representation simplification and reject every shape proposal. Report those outcomes separately; do not promote an energy-only candidate or imply a universal optimum degree was found.

Native Join, proof of every intended source segment becoming the correct interior seam, parent-intersection checks, and final visual quality remain mandatory before a product result can be accepted. This branch contains no geometry commit or contour-healing path. No new field test or runtime change is required merely to evaluate these offline changes.

## Reproduction

```bash
python -m pip install numpy==2.2.6 scipy==1.15.3 rhino3dm==8.17.0
PYTHONPATH=experiments/P08C.UVFairing python -m unittest discover -s experiments/P08C.UVFairing -p 'test_*.py' -v
```

Use CPython 3.11+, not Rhino's legacy Python runner. Test modules are developer material, not user commands.

## References

- SciPy BSpline knot insertion: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.insert_knot.html
- McNeel NURBS basis and knot multiplicity: https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/
- Rhino ChangeDegree: https://docs.mcneel.com/rhino/8/help/en-us/commands/changedegree.htm
