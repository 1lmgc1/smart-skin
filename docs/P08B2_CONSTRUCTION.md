# P08B.2F2 — adaptive positional boundary before frozen-row refinement

## Objective and diagnosis

A logical four-sided layout can be valid while its initial least-squares boundary approximation is outside the positional tolerance. Freezing those inaccurate outer control rows preserves the error; interior-only G1/G2 refinement cannot fix it. The old adapter tested uniform 10/16-control Coons baselines and skipped all refinement when either failed sampled position. Its successful execution footer was not a successful geometric result.

This patch adds a bounded boundary-fitting stage. It is not permission to increase document tolerance, ignore G0, change assigned G0/G2 roles, move parent geometry or declare a sampled result globally certified. The published RHP and `main` stay P07F2. The script remains PREVIEW ONLY.

## Implementation

`adaptive_boundary.py` fits the four chains with the same endpoint-constrained Householder least-squares solver, inspects each original interval on a separate, denser validation lattice, then adds simple knots near observed residual peaks and refits. Knots alone do not improve the approximation; the subsequent coefficient fit does. Each iteration evaluates all four curves again. Shared U/V knots keep the existing square-net and native conversion APIs unchanged. The final Coons net uses those nonuniform knots and then freezes its outer rows for the existing jet solver.

The internal target is one quarter of document positional tolerance (0.0025 for a 0.01 document). It is a fitting objective, not a new document tolerance. A finite baseline within document tolerance may still proceed when the tighter objective was not met before its budget; every candidate still needs the unchanged native position/Join checks before preview. An unresolved positional baseline does not enter jet refinement. Exact boundary reproduction is not claimed: this remains approximation of original chains with independent measurements.

Training and validation grids differ; both include the original callback's junction/near-junction sites, and both add samples in each positive knot span. Multiple interior fitting sites prevent newly refined spans from becoming data-free. Worst side, original source key, parameter, target point, fitted point, knots and residuals are logged to the private TXT. Distances are sampled known-correspondence distances, not certified global shortest distances. No source segmentation, role or parent association is erased by grouping.

Only simple interior knots are added. This patch does not insert creases/full-multiplicity internal knots or implement automatic multipatch splitting. A source that cannot be approximated within this bounded smooth representation remains explicitly unresolved. Missing/invalid data and fitting failures never become zero residual or successful G2.

Limits: initial counts 10/16, at most 32 controls per direction, 10 adaptation rounds per layout, existing six-layout and 120-second soft budget, Esc checkpoints between calls. A native call is not force-aborted. A previous fitted baseline can survive a later fitting failure, but it is not called a Join-verified retained preview. The existing native candidate pool remains separate and unchanged.

## Preserved layers and evidence boundaries

`mixed_kernel.py` remains byte-identical to P08B.2/F1. Its global jet solver, shape operator metric, sampled regularity, retention helpers and mathematical surface evaluator are not replaced. The adapter's make_brep, native deviation, native_evidence, candidate and source-safety methods are unchanged and checksum-tested. The F1 compound-side mapping and all per-source conditions are preserved: two opposed two-edge G0 sides and two one-edge curved G2 sides are six segments and four logical sides.

The new tests include a synthetic localized boundary where BOTH original uniform counts fail position, then check the adaptive result with independent dense SciPy evaluation, independent NumPy least squares, distinct sampling lattices, source-role retention, bounds, cancellation, failure retention and frozen outer rows through refinement. The synthetic localized fixture is arbitrary and is NOT an exact replay of private user geometry. It tests positional fitting, not private-hole G2 feasibility.

OpenNURBS additionally receives the real nonuniform net, validates its Brep and independently evaluates its dense boundary, then writes/reads a 3dm. This is actual native geometry execution, not a RhinoCommon Join or UI run. Current requested G2, analytic all-points G2, global self-intersection/fairness and actual private-hole success remain separate unproven levels. No user result is committable in this experiment.

## One field attempt

Use the NEW bundled script (conversation filename may end `_P08B2F2.py`) with `_RunPythonScript` in Rhino. No plug-in installation or runtime change. Select a fresh TXT path, select ALL six original opening edges and Enter, then select all FOUR G0 source segments (both pairs) and Enter. Leave the TWO curved boundaries at preferred G2. Do not merge, rebuild, delete or otherwise edit the source edges.

Expect `experiment=P08B.2F2` and the same `sharp=4 smooth=2`, role chains 2/2 and logical sides 2,1,2,1. New `BOUNDARY_FIT_BEGIN`, `BOUNDARY_FIT`, `BOUNDARY_FIT_SIDE` and `BOUNDARY_FIT_END` records show the positional stage. `JET_START` proves a refinement step was actually entered. `STAGE_SKIPPED` distinguishes unresolved boundary position from a later whole-baseline failure. `SEARCH_END result=NO_CANDIDATE` is unambiguous even if the report footer says execution COMPLETE.

When a native G0/Join-verified candidate is retained, the cyan transient preview may show less than requested smoothness and the per-edge evidence remains explicit. Enter/Esc ONLY closes; no object is added. Return the saved TXT and one screenshot only when a preview appears. Repeating the old all-G2 audit or changing selection count is not part of this test.

## Primary references

- NURBS knots, nonuniform representation and knot insertion semantics: https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/
- Independent least-squares reference and knot/data rank requirements: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.make_lsq_spline.html

These references describe interfaces/mathematics; they do not establish success on the private model. Previous construction and F1 documentation remain in Git history at f3b6ef1905ab4b3af18ffae14efe895693edc3e0.
