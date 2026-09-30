# Smart Skin handoff

## Current state

P00 is `VERIFIED` in Rhino 8.18. P01 passed CI plus curve, near-gap and Brep-edge field checks, but the field test exposed a top-level selection-classification defect: a whole Extrusion could be reported as a Curve. P01F1 contains the read-only adapter correction plus a managed install/update/uninstall lifecycle that removes the previous registered Smart Skin binaries; CI and Rhino verification are pending.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits and build artifacts. The Google Drive project journal stores distilled decisions and checkpoint summaries.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md` and `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and its exact commit SHA.
3. Do not begin surface construction until P01F1 has a Rhino field-test result.
4. Preserve the patch discipline: one architectural goal, targeted checks, field test, then the next patch.
5. Install field-test artifacts only through `INSTALL.cmd`; manual `.rhp` registration is superseded.

## Current patch

P01F1 changes only Rhino selection identity. It uses `ObjRef.GeometryComponentIndex` to distinguish a sub-object from its parent document object before extracting geometry. A whole Box stored as an Extrusion must report `Extrusion=1`; a sub-selected edge must report `BrepEdge=1`.

After P01F1 is verified, the next patch may add input topology classification and candidate routing without yet committing geometry.
