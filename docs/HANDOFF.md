# Smart Skin handoff

## Current state

P00 is `VERIFIED` in Rhino 8.18. P01 adds read-only GeometryReport/Preflight code; CI and Rhino verification are still pending.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Do not begin surface construction until P01 has a Rhino field-test result.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.

## Current patch

P01 adds `SmartSurfacePreflight`, a bounded read-only report for selected curves, Brep edges, points, surfaces and polysurfaces. It must not create or repair surfaces.

After P01 is verified on cleared or synthetic fixtures, the next patch may add input topology classification and candidate routing without yet committing geometry.
