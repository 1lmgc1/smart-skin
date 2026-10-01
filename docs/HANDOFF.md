# Smart Skin handoff - P04F1 four-command toolbar

## Verified baseline

P03F1 remains the verified runtime geometry/counting baseline at
`ada5c269c9d270e44952fcc297b611236c4a4782`.

P04 `0.0.8-p04` is accepted in Rhino 8.18 at
`a9e854dec93cde1a0e74d2596081d863803993ae`. GitHub Actions run 13 passed,
the native Smart Skin toolbar was visible, and its Build button produced and
accepted a Loft with `objects=2->3`. See `P04_CLOSURE.md`.

## Current objective

P04F1 `0.0.9-p04f1` expands that same accepted toolbar to all four existing
commands: Build, Plan, Preflight and Version. This is one UI mapping patch.
It adds no command, solver or panel.

All production C# source must remain byte-for-byte identical to P04/P03F1.
Only the RUI, its exact validator, version/identity expectations, packaging
metadata, workflow labels, icon sources and release documentation may change.

## Source of truth

Repository: <https://github.com/1lmgc1/smart-skin>.
GitHub is authoritative for source, workflow results and artifacts. Google
Drive stores only the project journal. Do not upload source ZIPs or CI artifacts
to Drive and do not ask the user to publish a prepared patch.

## Completion path

1. Verify one group, one toolbar, four ordered buttons, four exact macros,
   localized tooltips and four non-empty bitmap cells at 16/24/32.
2. Prove the production C# tree is unchanged from P04.
3. Run parser/diff/version/YAML checks and the available targeted tests.
4. Publish one fast-forward P04F1 commit to GitHub.
5. Require green `build-p04f1`: 31/31 Core tests, toolbar validation, package
   and installer lifecycle.
6. Field-test only the changed mapping: Version, Preflight, Plan and Build
   Cancel through the four buttons. Do not repeat installation diagnostics or
   the closed P03/P03F1 geometry suite.

## Safety

Preserve every released P04 UI GUID and the fixed plug-in GUID. Never reset
Rhino layouts, manually import the RUI as a passing workaround, force-push,
publish user evidence, or alter source geometry behavior.
