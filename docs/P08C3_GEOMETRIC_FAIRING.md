# P08C.3 — direct geometric curvature / silhouette experiment

## Objective and release boundary

Replace the use of quadratic parameter-derivative energy as the source of proposed shape improvement. Optimize the actual geometric curvature of both U/V section families and explicit silhouette halfspaces, preserving the previously compacted basis and verified boundary contract. This is a new bounded offline CPython/NumPy/SciPy experiment, NOT a Rhino command, new RHP or finished cap. The old P08C.2 module, previous constructors, UI, runtime, installer, and released plugin remain unchanged.

## Implemented construction

The P08C.2 coefficient null modes retain full boundary functions (including both pieces and their junctions), the complete central band, and first/second transverse derivative functions along the active parent-matching intervals. The new solve changes only those modes. It does not republish a requested G2 label as a measured result or shorten the active intervals. Existing source-induced knot jumps remain; the increment cannot introduce new C1/C2 jumps across them.

The nonlinear objective is a normalized smooth maximum of squared geometric section curvature plus a mean squared normalized curvature term, in BOTH parameter families. Curvature uses the actual expression |D cross DD| / |D|^3. Its analytical gradients are tested against finite differences. An explicitly supplied silhouette plane penalizes positive excursions. Orientation and displacement penalties guide the search; no penalty by itself authorizes acceptance.

Use bounded L-BFGS-B with iteration/evaluation/time budgets. A final coupled XYZ clipping of the coefficient-space increment enforces maximum Euclidean control-point displacement. All checks run again after clipping. Finite alpha backtracking retains the baseline if no proposal passes. Search convergence/limit status is reported separately from geometric screening; a useful screened iterate is not a claim that an optimum was reached.

Optional mirror symmetry is explicitly requested in a supplied local frame. Source control points and knot-vector symmetry are validated before use. It is not an automatic axis or symmetry detector. The public kernel has no source-specific coordinates, identifiers, private models, network requests, or document/file writes.

## Mandatory independent proposal screens

1. Complete coefficient-space boundary/core/active-jet locks, step bound and explicit symmetry.
2. Lower nonlinear geometric objective, evaluated on the same fixed fitting sites.
3. Maximum and 99th-percentile actual geometric section curvature must not increase in either U or V on the denser common knot-aware validation sites.
4. Maximum and 99th-percentile magnitude of principal surface curvature must not increase either. The shape operator is computed in an orthonormal tangent frame, including mixed derivatives; diagonal/oblique curvature must not be hidden by U/V section statistics.
5. Maximum and RMS positive excursion must not increase for every explicit silhouette halfspace.
6. The inherited bounded local 3D Bernstein regularity test must pass every positive knot cell.

No degenerate or nonfinite sample is silently discarded or flattened with an epsilon. Data or validation failure rejects the candidate. Both training and validation retain endpoints and short knot spans. They are nevertheless finite samples, not certified global maxima, a universal fairness definition, or a proof of global injectivity.

## What a selected research candidate DOES NOT mean

`GEOMETRIC_RESEARCH_CANDIDATE_NOT_JOINED` means these numerical non-regression screens passed. It does not mean all curvature is acceptably small, all corner conflicts have disappeared, silhouette excursion is zero, or Rhino Join succeeds. A silhouette reduction is not a complete parent-intersection test. Large residual principal-curvature peaks can remain near constrained corners and must be reported with their locations. Comparisons must use the same sample set; maxima on a denser grid can increase.

Native RhinoCommon Join, proof of every required input segment becoming the correct internal seam, self/parent intersections and the final visual assessment are still required. This module always reports `geometry_commit=False`, `Rhino_Join=NOT_RUN`, and `parent_intersections=NOT_CHECKED`. The baseline can also have defects; retaining it is not acceptance.

Do not insert this experiment into the production acceptance path or expose user sliders as though these obligations were finished. The private-model run and any native .3dm research exports belong to the private journal and conversation, not this public repository.

## Verification

The new synthetic tests execute real nonlinear optimization, coefficient locks, analytic gradients, curve-curvature scaling/reparameterization checks, shape-operator checks, symmetry, explicit error/budget paths, rejection/rollback and OpenNURBS .3dm roundtrip. The existing P08C.2 suite is run separately. CI uses no private model and does not start Rhino or IronPython.

Use VERIFIED only for exact-run numerical tests; STATICALLY CHECKED for unchanged source paths; NOT VERIFIED for Rhino UI/Join, all collisions and final cap acceptance.

## Developer reproduction — NOT RunPythonScript

```bash
python -m pip install numpy==2.2.6 scipy==1.15.3 rhino3dm==8.17.0
export PYTHONPATH=experiments/P08C.GeometricFairing:experiments/P08C.UVFairing
python -m unittest discover -s experiments/P08C.GeometricFairing -p 'test_*.py' -v
```

The .py files require developer CPython 3.11+. They are not compatible with Rhino's legacy IronPython runner. No user runtime change is required to inspect a separately exported .3dm.

## Primary technical references

- https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html
- https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/
- https://docs.mcneel.com/rhino/8/help/en-us/commands/join.htm
