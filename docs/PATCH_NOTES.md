# P04 Native One-Button Toolbar - source checkpoint

Version: `0.0.8-p04`. Planned publication kit: `SmartSkin-P04-v002`.
Baseline: `ada5c269c9d270e44952fcc297b611236c4a4782` (P03F1 VERIFIED).
Prior closure evidence: `P03F1_CLOSURE.md`.

## Single objective

Make the existing SmartSurfaceBuild command available through one native
Smart Skin toolbar button. No second builder, options panel or new solver.

## Included

- One same-name `SmartSkin.Rhino8.rui` beside `SmartSkin.Rhino8.rhp`.
- One visible legacy toolbar group (converted to a container by Rhino 8),
  one toolbar, one left-click macro `! _SmartSurfaceBuild` and one button.
- Stable UI GUIDs, original PNG glyphs at 16/24/32, English/Russian tooltips.
- RUI copy in build/publish output, package validation and delivery.
- Managed installer requires and validates RUI before modifying installation;
  verifies its hash after staging and installation; records toolbar_sha256.
- Known-file migration/uninstall includes this RUI, never shared Rhino UI
  settings or unrelated toolbars.
- Lifecycle coverage extends to RUI presence, hash, failed missing-RUI update,
  old RUI cleanup, one installed copy after update and unrelated-file retention.
- CI keeps all existing Core tests and validates the RUI; installer lifecycle
  runs under Windows PowerShell, matching the existing powershell.exe launcher.

## Invariants and intentionally untouched areas

Every production C# file in Core and Rhino8 stays byte-for-byte identical to
P03F1, including selection, geometry snapshot, routing, constructors, preview,
Accept/Cancel, active counts, plug-in load code and plug-in GUID. Test-source
changes are limited to expected patch identity. Target frameworks and packages
stay unchanged. The macro has no SelNone, Enter, Accept, second command or
right-click action. The leading ! cancels a current command using normal Rhino
macro behavior; P04 does not define new selection behavior.

No Rhino-wide reset, startup script injection, forced docking, cached-RUI
sweep, registry layout manipulation or repeated programmatic toolbar import.
Native loading is intentional; visibility and persistence are still field
test gates, not properties proven by XML parsing.

## Verification status at this checkpoint

- P03F1 remains VERIFIED on its original runtime; no new Rhino run is claimed.
- P04 source is implemented. Bounded local XML/PNG/version/diff inspection is
  recorded with the source checkpoint, not presented as CI or runtime proof.
- P04 Windows compilation, current 31 Core tests, PowerShell parser/execution,
  RUI validator execution, packaging and installer lifecycle are NOT VERIFIED.
- P04 initial visibility, command demand-load, preselection, duplicate-free
  restart and UI cleanup are NOT VERIFIED until FIELD_TEST.md passes.
- No P04 publication kit or compiled P04 artifact is delivered by this commit.

## Next gate

Queue P04.3: targeted source/script checks, parser checks and publication
harness tests. Then P04.4: immutable v002 kit, exact base/target hashes, full
bundle and verified durable backup. Only then publication, exact green CI,
managed installation and the focused GUI test. P05 remains blocked.
