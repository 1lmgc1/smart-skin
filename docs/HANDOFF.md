# Smart Skin handoff

## Current state

P00, the P01F1 read-only snapshot/preflight baseline and P02 are `VERIFIED` in Rhino 8.18. P01F1 field build commit `550b74ff9f5bd8953d80c28560a9951d39214d55` verified the managed installer lifecycle, one active registration, object/sub-object identity, cancellation without mutation and behavior after restart. P02 field build commit `450bf1e28b77abdb5e17ca6b06fa5c1564963a5b` adds and verifies the read-only endpoint-topology classifier and strategy router. GitHub Actions run 9 passed the build, all 23 Core tests, packaging and installer lifecycle; Rhino testing verified the required routes, object-count invariants, cancellation and restart behavior.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Treat P01F1 as the verified snapshot baseline and P02 as the verified read-only routing baseline; neither verifies future construction code.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.
5. Install field-test artifacts only through `INSTALL.cmd`; manual `.rhp` registration is superseded.

## Current patch

P02 version `0.0.4-p02` adds `SmartSurfacePlan`. It consumes the existing
`GeometrySnapshot` and `PreflightReport`, builds a tolerance-clustered endpoint
graph, classifies topology and ranks a small set of Rhino-native strategies.
`READY` means the observed topology supports the route; `REVIEW` means a route
exists but warnings or semantic ambiguity remain; `BLOCKED` means no safe route
is claimed.

P02 never calls a construction command. `NetworkSrf` is only a secondary
recommendation because internal intersections and U/V families are not yet
measured. Selected parent surfaces are context only; continuity is not inferred.
Its acceptance scope is complete and `VERIFIED`.

## Next patch boundary

P03 may begin only as a new single-goal patch. Its intended boundary is
construction of disposable candidates from the verified P02 route; it must
define cancellation, complexity limits, timeout behavior, preview/commit
semantics and document-mutation invariants before implementation. P02 field
evidence must not be cited as verification of any P03 construction behavior.
