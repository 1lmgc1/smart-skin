# P08D.1B — geometric attachment freedom without a positional relaxation

Developer CPython layer on `2007a5793a9e9270ea64190e9d473675b26b1bda`. Not a Rhino RunPythonScript command, RHP update, UI, or accepted surface. Earlier production and experimental sources remain unchanged.

## Architectural objective

Replace a frozen active parameter two-jet with a bounded, geometrically equivalent chart family. The common outer curves, both compound junctions, central profile, and internal shared C/D/E stay constrained. The center around the profile may move. The active smooth interval is not shortened. The geometric reference is the supplied baseline active two-jet; this module does not independently query original Rhino parent faces.

On an active polynomial span use the local chart `r=a*t+c*t^2/2`, `s=v+b*t+d*t^2/2`, with `a>0`. If the reference derivatives are A=P_r, T=P_s, B=P_rr, M=P_rs, F=P_ss, the new derivatives are:

- S_t = a*A + b*T; S_v = T.
- S_tt = a^2*B + 2*a*b*M + b^2*F + c*A + d*T.
- S_tv = a*M + b*F; S_vv = F.

The coefficients are constant on the active interval in this bounded version. Variable coefficients would require their derivatives and a representable longitudinal basis; they are not implemented by these equations. The transformation preserves the oriented normal and full ambient shape operator at regular boundary points. Positions stay fixed. Compare actual evaluated geometric jets, not raw second-derivative vector equality or only principal eigenvalues.

## Implementation

An explicit labeled constraint system has the D1A fixed functions and shared seams. Its active rows receive a nonlinear polynomial right-hand side. A compatible particular response is computed once; incompatible or ill-conditioned restrictions fail rather than approximate the condition silently. Ordinary null modes remain jointly solved for all three patches. The nonlinear chart responses couple XYZ. Reflection linking is explicit and verified; independent left/right charts are available without reflection.

Lower corner mixed derivatives may change in their two tangent-plane components while the normal component stays fixed. The normal and full corner second fundamental form are independently checked. This opens a previously frozen parameter freedom; it is NOT construction of all four redesigned end-zone normal laws. The current finite route requires one active polynomial span in a shared longitudinal basis.

The optimizer reuses the existing geometric U/V curvature, ambient shape, silhouette and normal-flow objective. It adds no boundary error budget. The side functions remain exactly those of the supplied baseline. An inherited CAP_EDGE_RELIEF bound remains measured against the original source, not reset after each step. Parent healing is not implemented.

## Nonlinear rollback is mandatory

A linear average of two control nets with equivalent G2 attachments need not retain G2, because the second-jet law is quadratic in a and b. Step reduction and backtracking therefore scale solver/chart variables and rebuild the nonlinear response. They never interpolate the final control nets. A synthetic regression explicitly detects the incorrect linear alternative. Each trial receives fresh normal/shape-operator, fixed-function and shared-seam checks.

Per-control XYZ displacement, iteration, objective-evaluation and search-time budgets are finite. Search time does not include all initialization/validation work. Cancellation propagates; it is not an acceptance. Returned proposals are not product-ready. Acceptance is a separate conservative finite-sample screen with physical sections and immutable retained-candidate behavior.

## Station alternatives and screening

`station_graphs` prepares one to five explicitly supplied paired station layouts by exact splitting, preserving source interval coverage. Splitting is a representation-only initializer. Each layout must be solved anew to change form. This is not continuous/independent sliding of all seam endpoints, automatic width selection or axis inference. The host chooses a finite set and records every result.

Each before/after pair uses identical knot-aware sites. Raw percentiles of different station layouts must not be compared as though their sampling were identical. Physical sections use the same coordinate planes and longitudinal stations. Strict non-regression screens remain unchanged in meaning; no visual success follows from a smaller objective. Record every rejected reason. The old single-cap Join result never transfers to these three patches.

## Verification scope

Synthetic tests execute transformed curved jets, analytic gradients, a real bounded solve, incorrect linear rollback, independent/symmetric charts, lower-corner shape preservation, both compound source chains, shared seams, physical sections, cancellation, finite limits and rollback. CI must also write/read changed synthetic patches through OpenNURBS. Missing local rhino3dm is an explicit skip, never a claimed native test.

Private-model computations and coefficient arrays stay in private recovery, not GitHub fixtures. Native Rhino Join, both lifted trim traces, parent/self collisions, redesigned user-model visual acceptance and UI are NOT VERIFIED by this module. No function authorizes a CAD commit.

## Remaining work

Variable speed/shear fields and full corner-rotation laws; a bounded geometric construction using those variables rather than endless scalar weight changes; independent station endpoints/maps; the multi-face native verifier with separate pre-Join and trim-image evidence; then the existing one-window product interaction. Do not send another user field test while independent form screens reject the proposal.

Primary terminology/API references:
- https://docs.mcneel.com/rhino/8/help/en-us/commands/matchsrf.htm
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.lstsq.html
