# Smart Skin handoff

## Current state

P00 and the P01F1 read-only snapshot/preflight baseline are `VERIFIED` in Rhino 8.18. P01F1 field build commit `550b74ff9f5bd8953d80c28560a9951d39214d55` also verified the managed installer lifecycle, one active registration, object/sub-object identity, cancellation without mutation and behavior after restart. P02 now adds a read-only endpoint-topology classifier and strategy router. Its Core source, tests, workflow and field protocol are `STATICALLY CHECKED`; compilation, CI and Rhino behavior are `NOT VERIFIED` until the P02 workflow and field test complete.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Treat P01F1 as the verified read-only snapshot baseline; do not reinterpret it as verification of P02 routing.
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

## Required next verification

1. Publish the P02 commit through the immutable patch kit.
2. Require green Restore, Build, all Core tests, Package and Installer lifecycle.
3. Install only the resulting `SmartSkin-P02-...` artifact.
4. Run `docs/FIELD_TEST.md` for `PlanarSrf`, `EdgeSrf`, `Loft`, open-chain
   blocking, cancellation and restart.
5. Do not begin construction or preview code before reviewing that field result.
