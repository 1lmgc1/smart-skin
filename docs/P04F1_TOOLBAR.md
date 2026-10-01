# P04F1 four-command toolbar contract

Version: `0.0.9-p04f1`.
Baseline: accepted P04 commit
`a9e854dec93cde1a0e74d2596081d863803993ae`.

## Single objective

Expand the accepted native Smart Skin toolbar from one button to buttons for
all four commands already registered by the plug-in. Do not add a command,
solver, panel, menu, right-click action or automatic selection/acceptance.

| Order | Button | Exact macro | Behavior |
| --- | --- | --- | --- |
| 1 | Build | `! _SmartSurfaceBuild` | Existing preview and explicit commit |
| 2 | Plan | `! _SmartSurfacePlan` | Existing read-only route plan |
| 3 | Preflight | `! _SmartSurfacePreflight` | Existing read-only diagnostics |
| 4 | Version | `! _SmartSurfaceVersion` | Existing identity/runtime report |

The leading `!` cancels an ordinary active command before invoking the
selected Smart Skin command. No macro contains `SelNone`, Enter, Accept or a
second command.

## Stable UI identity

The P04 RUI, group, group item, dock, toolbar, Build button, Build macro and
Build bitmap GUIDs remain unchanged. P04F1 adds stable GUIDs for three buttons,
three macros and three bitmap cells. The toolbar remains one group and one
toolbar; Rhino menus remain untouched.

The inline legacy atlases retain 250 columns at 16, 24 and 32 pixels. Cells
zero through three contain distinct Build, Plan, Preflight and Version glyphs.
English and Russian tooltips are required for every macro.

## Invariants

- Every production C# file remains byte-for-byte identical to P04/P03F1.
- Command names, selection filters, object-count checks, routing, construction,
  preview, Accept/Cancel and plug-in GUID do not change.
- Packaging and the managed installer continue to copy and hash-check the
  same-name RUI beside the RHP.
- No Rhino settings, cached RUI, unrelated toolbar or user model is modified.

## Verification

`Test-Toolbar.ps1` must prove one group, one toolbar, four ordered buttons,
four exact macros, stable references, four non-empty bitmap cells in each
atlas, localized tooltips and no menu extension. CI retains all 31 Core tests,
package identity checks and installer lifecycle coverage.

The Rhino field check is limited to the changed layer: four visible buttons
with distinct glyphs and correct command dispatch. P03/P03F1 geometry cases and
P04 installation behavior are not repeated.
