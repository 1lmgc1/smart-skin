# Smart Skin handoff

## Current state

P00 is a build-and-load bootstrap. Production geometry code has not started.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Do not begin P01 until P00 has a Rhino field-test result.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.

## Next patch after P00 passes

P01 adds a read-only `GeometryReport/Preflight` command and its first synthetic/cleared fixtures. It must not yet create or repair surfaces.

