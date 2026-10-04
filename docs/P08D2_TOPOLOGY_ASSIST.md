# P08D.2A — topology generalization and semantic Assist controls

Research branch only. This is not a released RHP, not a UI change, and not an accepted surface.

## Objective

Remove the hidden assumption that the target hole always reduces to the source-segment pattern `2/1/2/1`. The bounded route now accepts a simple boundary cycle with any number of source segments and recognizes the current strip family only from topology: two smooth support chains alternating with two feature arcs. A feature arc may contain any positive number of source segments. Every source segment must remain covered exactly once.

This deliberately separates **source segmentation** from **logical sides**. A six-segment loop and an eight-segment loop can therefore resolve to the same four-chain strip topology without deleting or approximating any source interval. Topologies outside this bounded family stop with `NOT_TWO_SUPPORT_STRIP_TOPOLOGY`; they are not silently coerced into a quadrilateral.

## Semantic Assist contract

The normal user-facing controls are intent variables:

- preferred flow axis;
- center-profile strength;
- start/end transition lengths;
- corner freedom;
- contour-relief budget;
- symmetry coupling;
- fairness strength;
- seam bias;
- default/per-chain continuity preference.

Degree, CV count, knot multiplicity, iteration count and numerical penalty weights are intentionally excluded from the semantic control surface. They remain implementation variables and may later appear only in Expert/Diagnostics.

The controls are preferences, not permission to fake continuity. A requested G2 target may still be reported as locally impossible; contour relief remains explicit and cumulative.

## Distributed attachment field

D1B used constant chart coefficients on the active support interval. D2A adds a bounded C2 piecewise-quintic schedule. For

`r = a(v)t + c(v)t^2/2`, `s = v + b(v)t + d(v)t^2/2`,

the boundary mixed derivative must include the longitudinal field derivatives:

`S_tv = a M + b F + a' A + b' T`.

The new `a' A + b' T` terms are tangential. At regular boundary points they therefore change parameter progression without changing the oriented normal or the full geometric second fundamental form. Tests verify this numerically against the ambient shape operator. This is the mathematical basis for future transition-length and flow controls.

## Current bounded topology family

D2A does not yet solve an arbitrary graph. It supports the family required for the next experiment: exactly two smooth supports separated by two feature arcs, with arbitrary source segmentation inside each arc. The patch count is still the three-strip construction from D1. General multi-support / branched region decomposition remains future work.

The opposite-side user model is private evidence and is not committed. Public tests use synthetic six- and eight-segment cycles only.

## Verification boundary

Verified in pure CPython tests:

- six-source-segment route;
- eight-source-segment route with unequal feature-arc segmentation;
- rotation/reversal invariance of segment coverage;
- explicit stop for a topology outside the bounded family;
- semantic-control validation and absence of NURBS implementation controls;
- C2 schedule anchor behavior;
- exact constant-chart reduction to D1B;
- varying speed/shear with mandatory `a'`, `b'` mixed-jet terms;
- oriented-normal and ambient shape-operator invariance.

Not verified here: Rhino topology extraction, parent-face classification, opposite-side native Join, collision/self-intersection screening, visual fairness, UI, or product acceptance.
