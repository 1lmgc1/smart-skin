# Smart Skin — P08E1N3 complete diagnostic TXT report

Rhino8.21+ / Windows. Version **0.0.24-p08e1n3**.

N3 records `SmartSkinNativeCompare` directly into a complete diagnostic buffer, then offers a folder chooser for a UTF-8 TXT after cleanup. `SmartSkinNativeReport` can retry saving the last completed report in the current Rhino session. See [report instructions](docs/P08E1N3_FULL_TEXT_REPORT.md). The N2 EdgeSrf and two independent first-Match probes, ordinary Build, Python geometry and installer algorithms are unchanged.

This experimental field candidate repairs compound-edge recognition and constructs a boundary-preserving native skin with selectable U/V guide handles. Original source objects remain unchanged. Upper source corners may be hard at the two explicitly identified vertices; finite source intervals and generated joins receive no continuity exemption. Whole-skin numerical construction, selected-handle regressions and the bounded cap-cap screen pass. The actual Rhino owner-screen and interactive workflow remain a field-test boundary. Delivery requires successful exact-SHA Windows CI and its unchanged verified install ZIP.

Known limitation: rotated inputs can fail the unchanged stored-curvature gate because of high-degree coefficient conditioning. The experimental constructor fails closed with a numerical diagnosis; arbitrary-orientation robustness is not claimed.

- [Install the verified CI runtime ZIP](docs/INSTALL_CURVATURE_RU.md)
- [Compound-edge and profile-arrival repair](docs/P08E1F3_COMPOUND_EDGE_REPAIR.md)
- [Pipeline restoration scope and acceptance](docs/P08E1F2_PIPELINE_REPAIR.md)
- [Geometry workflow and supported input family](docs/P08E1_CURVATURE_CONTROL.md)
- [Native-owner screen and verification limits](docs/P08E1F3_NATIVE_OWNER_SCREEN.md)

Use the single install ZIP from the successful exact-SHA Windows CI run. It has INSTALL.cmd and manifest.json at its root. This source checkout is not an install package, and scripts/INSTALL.cmd must not silently build or install it.

The installer uses the established HKCU/current lifecycle. It neither requires nor forbids an administrator token and never migrates HKLM plug-in registrations. UNINSTALL.cmd genuinely uninstalls Smart Skin. Stable plug-in/toolbar GUIDs and unrelated files are preserved.

## Build and checks

Run `dotnet restore SmartSkin.sln`, then `dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=<exact commit>` and Core tests. Use the dependency pins in Python/smart_skin.py for numerical tests. Production packaging and real Windows PowerShell5.1 CMD lifecycle tests run in `.github/workflows/build.yml` before an install artifact is delivered.

The compiled plug-in targets net48; Core targets netstandard2.0. Rhino supplies RhinoCommon/Eto. Python runs inside Rhino ScriptEditor, with explicit pinned dependencies. Native Rhino UI and geometry acceptance remain separate from CI checks.
