# Smart Skin handoff

## Current state

P00, the P01F1 read-only snapshot/preflight baseline and P02 are `VERIFIED` in Rhino 8.18. P01F1 field build commit `550b74ff9f5bd8953d80c28560a9951d39214d55` verified the managed installer lifecycle, one active registration, object/sub-object identity, cancellation without mutation and behavior after restart. P02 field build commit `450bf1e28b77abdb5e17ca6b06fa5c1564963a5b` verifies the read-only endpoint-topology classifier and strategy router; closure commit `aa3402bc922f74af7867fa799014447861c74304` records its completed field evidence. P03 source implements bounded candidate preview/accept but remains `NOT VERIFIED` until its exact commit passes CI and the Rhino protocol.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA; do not infer P03 status from the verified P02 run.
3. Treat P01F1 as the verified snapshot baseline and P02 as the verified read-only routing baseline; neither verifies future construction code.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.
5. Install field-test artifacts only through `INSTALL.cmd`; manual `.rhp` registration is superseded.

## Current patch

P03 version `0.0.5-p03` adds `SmartSurfaceBuild`. It consumes the verified P02
route but permits native construction only for `READY` PlanarSrf, EdgeSrf and
exactly two-section Loft cases. The Core policy caps construction at four
curves and 64 combined spans. Rhino receives only duplicated curves. Edge
copies may be reordered/reversed to close the loop; the second Loft copy may be
reversed to match direction. Source document geometry is untouched.

One valid Brep is previewed through a temporary display conduit. `Accept` adds
exactly one Brep; Cancel/Esc, blocked input and handled build failure add none.
Patch/NetworkSrf, seam alignment, repair and quality ranking remain excluded.
See `docs/PATCH_NOTES.md` for the precise contract and `docs/FIELD_TEST.md` for
the required evidence.

## Verification boundary

P02 remains `VERIFIED`. P03 source may be called `STATICALLY CHECKED` only after
review. Compilation/tests, package lifecycle and every Rhino-facing behavior
remain `NOT VERIFIED` until the exact P03 commit passes the corresponding
checks. Do not start P04 or broaden constructors before P03 is closed with CI
and field evidence.
