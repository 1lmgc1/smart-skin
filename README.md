# Smart Skin — P08E1F2

Rhino8.21+ / Windows. Version **0.0.16-p08e1f2**.

One Smart Skin button builds the supported native-edge family and opens a live shoulder-curvature control. Original source objects remain unchanged. The bounded experimental geometry and its disclosed continuity limits are unchanged from P08E1.

- [Install the verified CI runtime ZIP](docs/INSTALL_CURVATURE_RU.md)
- [Pipeline restoration scope and acceptance](docs/P08E1F2_PIPELINE_REPAIR.md)
- [Geometry workflow and supported input family](docs/P08E1_CURVATURE_CONTROL.md)

Use the single install ZIP from the successful exact-SHA Windows CI run. It has INSTALL.cmd and manifest.json at its root. This source checkout is not an install package, and scripts/INSTALL.cmd must not silently build or install it.

The installer uses the established HKCU/current lifecycle. It neither requires nor forbids an administrator token and never migrates HKLM plug-in registrations. UNINSTALL.cmd genuinely uninstalls Smart Skin. Stable plug-in/toolbar GUIDs and unrelated files are preserved.

## Build and checks

Run `dotnet restore SmartSkin.sln`, then `dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=<exact commit>` and Core tests. Use the dependency pins in Python/smart_skin.py for numerical tests. Production packaging and real Windows PowerShell5.1 CMD lifecycle tests run in `.github/workflows/build.yml` before an install artifact is delivered.

The compiled plug-in targets net48; Core targets netstandard2.0. Rhino supplies RhinoCommon/Eto. Python runs inside Rhino ScriptEditor, with explicit pinned dependencies. Native Rhino UI and geometry acceptance remain separate from CI checks.
