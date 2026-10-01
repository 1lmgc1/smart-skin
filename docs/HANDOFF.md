# Smart Skin handoff — P05 contextual tangent Patch

## Baseline

- P03F1 runtime/counting baseline: `ada5c269c9d270e44952fcc297b611236c4a4782`.
- Accepted P04 toolbar: `a9e854dec93cde1a0e74d2596081d863803993ae`.
- P04F1 temporary four-command toolbar baseline:
  `98abb7bfd1483406675469c6437e4fc3621e392f`.

GitHub is authoritative for code, CI and artifacts. Google Drive is journal
only. Installation is not a separate field test.

## Real case

The supplied private shell model contains a shell assembled from separate Breps. Each end is
bounded by six naked edges from four parent objects. The failed P04F1 command
correctly found `CLOSED_BOUNDARY_LOOP` but discarded owning-face context and
therefore blocked `Patch` as `P03_ROUTE_NOT_READY`.

The private model and screenshots must not enter the public repository.

## P05 objective

P05 `0.0.10-p05` preserves the selected edges as owning Brep trims and requests
one trimmed tangent Patch. It accepts only five to eight naked Brep edges with
one trim each, keeps the 64-span bound and adds at most one Brep after standard
Rhino confirmation. It reports `G1_REQUESTED`, not verified G1/G2.

## Completion path

1. Static review and full Core regression.
2. One fast-forward P05 commit to `main`.
3. Green `build-p05` on the exact commit and artifact identity inspection.
4. One Rhino field test on one six-edge opening from the supplied private shell model.
5. Review the returned log and screenshot before the next patch.

## Queue after P05 evidence

1. Measure boundary gap and tangent-angle deviation; reject bad candidates.
2. Add a small candidate set for soft caps and rank fairness/continuity.
3. Test the second opening without repeating the first.
4. Replace the diagnostic toolbar with the final one-command settings dialog
   and live preview; then remove the temporary command piano.
