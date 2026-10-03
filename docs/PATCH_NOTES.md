# P07F1 — 0.0.13-p07f1

Objective: replace the verifier's single-natural-output-edge assumption with whole-boundary verification and truthful failure diagnostics. The native MatchSrf solver, seed construction, refinement tolerances and strict Join proof are unchanged. No claim that a formerly rejected native cap has become geometrically correct merely because its verifier changed.

- Accept one topological naked cycle represented by one or multiple edges, including trimmed output boundaries. Preserve original edge/trim/face ownership for sampling. Reject extra boundary components, branches, disconnected cap faces, invalid ownership and nonmanifold topology.
- Measure the complete candidate/target loop in both directions. Remove the output-boundary search's hidden 2x-tolerance cutoff; retain and report a large measured gap as BOUNDARY_GAP_OUT_OF_TOLERANCE.
- Sample both directions to cover short split output edges. Keep G0/G1/G2 thresholds, orientation-aware normal curvature, bounded sample limits and explicit ambiguity rejection. Same-face splits at a shared vertex are permitted; nonlocal overlap or ambiguous different-face correspondence is blocked.
- Print each native direction variant, its phase, topology, partial metrics and reason before disposing rejected geometry. Do not discard all evidence merely because the last variant fails.
- Disable Average for ineligible trimmed targets before changing it; explain eligibility in the same settings window. No object-first selection step. No new toolbar buttons.
- Eight new native-free topology unit tests and eight native synthetic validator self-tests. Native self-tests execute once before the first match on Rhino's command/UI thread and fail closed. CI compilation/core tests do not execute Rhino native geometry.
- Version identity P07F1. Existing P07 outcome codes remain to preserve log consumers.

## Verification status

Check the Actions run for the exact commit for compilation, Core regression and installer results. Native self-tests and the private opening are NOT VERIFIED until their actual Rhino log is returned. Green CI is not geometric acceptance. No global surface-fairness, interior foldover or universal G2 proof is claimed by these sampled boundary checks.

## Preserved history

P07 (0.0.12-p07) introduced measured MatchSrf on Rhino 8.21+. Its release notes remain in Git history at 27a4d1e2f0e1b1363915e72cb674147f0a42eddd. Earlier PlanarSrf/EdgeSrf/two-section Loft paths, managed installer, plug-in GUID and single RUI button are preserved.
