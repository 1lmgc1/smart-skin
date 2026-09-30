# Smart Skin handoff

## Current state

P00 is `VERIFIED` in Rhino 8.18. P01 passed CI plus curve, near-gap and Brep-edge field checks, but its field test exposed a top-level selection-classification defect: a whole Extrusion could be reported as a Curve. P01F1 corrected the adapter and added a managed install/update/uninstall lifecycle. GitHub Actions run 7 built and packaged commit `550b74ff9f5bd8953d80c28560a9951d39214d55`, passed all 11 Core tests, exercised the real `INSTALL.cmd` launcher from a path containing spaces, and passed migration, repeat-update and uninstall checks. Rhino 8.18 field testing then verified the build identity, one active managed registration, whole-Extrusion versus sub-edge identity, cancellation without mutation and classification after closing Rhino and reopening the saved file. P01F1 is `VERIFIED`; P02 has not started.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Treat P01F1 as the verified read-only baseline; do not reinterpret its field evidence as verification of future construction code.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.
5. Install field-test artifacts only through `INSTALL.cmd`; manual `.rhp` registration is superseded.

## Current patch

P01F1 changes only Rhino selection identity. It uses `ObjRef.GeometryComponentIndex` to distinguish a sub-object from its parent document object before extracting geometry. A whole Box stored as an Extrusion must report `Extrusion=1`; a sub-selected edge must report `BrepEdge=1`.

The next patch may add input topology classification and candidate routing without yet committing geometry. Keep candidate generation and document mutation outside that patch unless its objective and acceptance criteria are explicitly revised first.
