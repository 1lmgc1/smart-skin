# Smart Skin handoff

## Current state

P00, P01F1, and P02 are `VERIFIED` in Rhino 8.18. P03 commit
`acdcba9cc0586a769bae7a97ed61dadf74055573` passed GitHub Actions run 11 and
field verification for bounded PlanarSrf, EdgeSrf, and two-section Loft
preview/Accept, Cancel/Esc, blocked open chain, Undo, save, and restart.

The field test exposed one diagnostic defect: `RhinoDoc.Objects.Count` includes
deleted Undo records. Geometry and Undo were correct, but machine lines could
report historical totals. P03F1 version `0.0.6-p03f1` changes only that shared
Rhino-adapter counter and is `VERIFIED` on runtime commit
`ada5c269c9d270e44952fcc297b611236c4a4782`; see `P03F1_CLOSURE.md`.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>

The repository is authoritative for code, workflows, commits, and build
artifacts. The Google Drive project journal stores distilled decisions and
checkpoint summaries.

## Current patch

`RhinoDocumentMetrics.ActiveObjectCount` enumerates active saved objects,
including normal, locked, and hidden objects, while excluding deleted Undo
records and non-document/reference helper objects. Version, Preflight, Plan,
and Build use this one counter. P03 construction code and source-geometry
handling are unchanged.

## Resume procedure

1. Read `README.md`, `AGENTS.md`, `docs/PATCH_NOTES.md`, and
   `docs/FIELD_TEST.md`.
2. Inspect the latest GitHub Actions run and exact commit SHA.
3. Preserve the verified P03F1 runtime; do not reinstall a docs-only rebuild.
4. Use `P03F1_CLOSURE.md` for the already-reviewed count/Undo/restart evidence.
5. Prepare the separate minimal toolbar patch with its own CI and GUI gate.

## Next product patch

The next separate objective is a minimal Rhino toolbar with a primary
`SmartSurfaceBuild` button. A large options panel is not yet justified.
