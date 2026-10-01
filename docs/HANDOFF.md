# Smart Skin handoff

## Current state

P00, P01F1, and P02 are `VERIFIED` in Rhino 8.18. P03 commit
`acdcba9cc0586a769bae7a97ed61dadf74055573` passed GitHub Actions run 11 and
field verification for bounded PlanarSrf, EdgeSrf, and two-section Loft
preview/Accept, Cancel/Esc, blocked open chain, Undo, save, and restart.

The field test exposed one diagnostic defect: `RhinoDoc.Objects.Count` includes
deleted Undo records. Geometry and Undo were correct, but machine lines could
report historical totals. P03F1 version `0.0.6-p03f1` changes only that shared
Rhino-adapter counter and is `NOT VERIFIED` until its CI and focused Rhino test
pass.

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
3. Install only the exact green P03F1 artifact through `INSTALL.cmd`.
4. Run the focused count/Undo/restart protocol.
5. Do not start the GUI patch until P03F1 is closed.

## Next product patch

The next separate objective is a minimal Rhino toolbar with a primary
`SmartSurfaceBuild` button. A large options panel is not yet justified.
