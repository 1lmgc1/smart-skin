# P08E1N7: complete surface creation in Rhino

Version **0.0.28-p08e1n7** keeps the approved first native candidate and makes the primary Build workflow explicitly create a persistent document surface.

## Functional corrections

- The preview has a **«Создать поверхность»** button. Its deliberate Click requests the same sealed transaction through the running Rhino command; it does not depend on observing a key-release event. Stale/cancelled candidates still cannot add. Enter, Space and the qualified right-click path remain supplementary.
- Native insertion uses the RhinoCommon overload with **splitKinkySurfaces=false**. The former default overload could legitimately split kinked faces while the transaction required the qualified geometry to remain byte-identical, causing the transaction itself to roll back. The explicit insertion policy preserves the candidate; exact readback verification stays in place.
- Main Build retains its report in-session and finishes with the surface or a visible failure explanation. It no longer automatically opens a report-folder chooser. `SmartSkinNativeReport` saves the report only when explicitly invoked. Read-only `SmartSkinNativeCompare` retains its separate reporting flow.
- A successful cap is highlighted and the command states **«Поверхность создана»**. Only that new cap is added. Parents remain untouched and separate. Highlighting is a completion cue, not a substitute for persisted-object verification.

The exact stage of the user's N6 failure was not supplied. These changes correct identified workflow and API-contract defects without claiming that the particular field event was reproduced. Independent replay of the actual original curves did not support changing the corner rank threshold or the boundary-ambiguity policy; those geometry gates remain unchanged.

## Use

Install the exact verified CI ZIP, reopen Rhino and check `SmartSurfaceVersion` for **0.0.28-p08e1n7** and the package commit. Use the existing Smart Skin button or `SmartSurfaceBuild`, select the original closed boundary and press **«Создать поверхность»** after inspecting the candidate. The resulting cap is an ordinary document object. Esc or closing the window before creation cancels; one Undo removes the added cap.

The result remains labelled **«стыковка без гарантии плавности»**, as approved for this user test. It is not a G1/G2 guarantee. No parent trimming/replacement, forced Join, tolerance increase, hidden Python fallback or new geometric recipe is introduced.

## Verification boundary

The live path is the existing toolbar command → `SmartSurfaceBuild.RunCommand` → `NativeBuildWorkflow` → qualified cap → Create button/confirmation → `NativeBuildTransaction` → `NativeBuildDocumentAdapter` → actual `ObjectTable.AddBrep`. The corrections are on that path. The separate Compare command cannot add geometry. Earlier Match/Trim experiments are not undisclosed working replacements; the previous U/V constructor remains explicitly available as `SmartSurfaceBuildPython`.

The managed tests exercise explicit-button state transitions and the same current-input/receipt/Undo/rollback runner as the native adapter. Compilation checks the supported RhinoCommon 8.21 overload. Exact-SHA Windows CI validates the build, retained regressions and actual installer lifecycle; the unchanged package and actual compiled dispatch are independently audited.

The tests use a simulated document at the Rhino boundary. Source and compiled-dispatch checks verify integration but do not execute a licensed Rhino session. Current native cap/seam qualification, real document insertion, window/input coexistence and Undo/Redo remain host-verification boundaries. The build is provided for functional user testing, not advertised as proven generally stable.
