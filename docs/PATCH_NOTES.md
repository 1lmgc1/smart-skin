# P04F1 All Existing Commands in the Native Toolbar

Version: `0.0.9-p04f1`.
Baseline: accepted P04 runtime
`a9e854dec93cde1a0e74d2596081d863803993ae`.

## Objective

Keep the accepted Smart Skin native toolbar and expose every command already
implemented by the plug-in:

1. `SmartSurfaceBuild`
2. `SmartSurfacePlan`
3. `SmartSurfacePreflight`
4. `SmartSurfaceVersion`

## Changed layer

- The same `SmartSkin.Rhino8.rui` now contains four ordered buttons and four
  exact one-command macros.
- Plan, Preflight and Version receive stable button, macro and bitmap GUIDs.
- The 16/24/32 legacy atlases contain four distinct cyan glyphs.
- English and Russian tooltips describe each existing command.
- `Test-Toolbar.ps1` validates the complete four-command mapping and rejects
  empty icon cells, extra menus, right-click actions or altered scripts.
- Version, workflow, package and identity expectations advance to P04F1.

## Intentionally unchanged

All production C# source remains byte-for-byte identical to P04 and P03F1.
This patch does not change command behavior, selection, preflight, routing,
candidate construction, preview, object counting, loading or installation
ownership. No geometry operation is added.

## Acceptance

- One Smart Skin toolbar, four distinct buttons, no duplicate container.
- Each button invokes exactly its labeled existing command.
- Plan, Preflight and Version remain read-only.
- Build retains preview and explicit Accept/Cancel behavior.
- CI passes 31/31 Core tests, native toolbar validation, packaging and installer
  lifecycle for the exact published P04F1 commit.
- Rhino field testing checks only button visibility and dispatch; the closed
  P03/P03F1 geometry suite and P04 installation path are not repeated.

P04 field evidence and the user's acceptance are recorded in
`P04_CLOSURE.md`. The durable toolbar mapping is in
`P04F1_TOOLBAR.md`.
