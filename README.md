# Smart Skin — P08E1N7 surface creation

Rhino 8.21+ / Windows. Version **0.0.28-p08e1n7**.

The existing Smart Skin button and `SmartSurfaceBuild` now use the first native EdgeSrf candidate, a copy-only Join qualification, a cached preview and an explicit **Создать поверхность** button. The result is labelled **«стыковка без гарантии плавности»**. The user approved this scope for testing; this release does not establish G1/G2 or general production stability.

Only the new cap is added, in the normal command's Undo record. Original parents remain separate and unchanged. No parent trimming, forced Join, tolerance increase, fake U/V controls or automatic slow Python fallback is used. Selected seams, isolated-cap boundaries and bounded validity/regularity checks must pass; these finite checks are not global geometry proofs.

- [Current installation and test steps](docs/INSTALL_CURVATURE_RU.md)
- [Current surface-creation correction](docs/P08E1N7_SURFACE_CREATION.md)
- [Native Build scope and verification boundary](docs/P08E1N6_NATIVE_BUILD.md)
- [Prior first-seed Join experiment](docs/P08E1N5_SEED_JOIN.md)
- [Pipeline restoration and installer contract](docs/P08E1F2_PIPELINE_REPAIR.md)

Build completes with the persisted cap or a visible failure explanation; it does not automatically open a report-folder picker. The native insertion explicitly preserves the qualified cap instead of allowing default kink splitting to conflict with exact readback. `SmartSkinNativeCompare` remains read-only and the local TXT reporter is available explicitly through `SmartSkinNativeReport`. `SmartSurfaceBuildPython` explicitly opens the earlier experimental high-degree U/V workflow; `SmartSurfaceBuildLegacy` retains its older route. Their historical limitations are documented in the F-series notes. The 16 Python runtime modules and pinned dependencies are retained unchanged, but the main native Build does not invoke them.

Use the single install ZIP from a successful exact-SHA Windows CI run. Its root contains INSTALL.cmd and manifest.json. A source checkout or recovery archive is not an installer. The established HKCU/current install lifecycle, fixed plug-in/toolbar GUIDs and unrelated files are preserved. UNINSTALL.cmd uninstalls the plug-in without changing shared Rhino layouts or HKLM registrations.

## Build and checks

Run `dotnet restore SmartSkin.sln`, `dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=<exact commit>` and Core tests. The compiled plug-in targets net48; Core targets netstandard2.0. Rhino supplies RhinoCommon/Eto. Production packaging, retained Python regressions and actual Windows PowerShell5.1 CMD lifecycle tests run in `.github/workflows/build.yml`.

Headless tests do not establish native window/input behavior, selected-seam results, Undo/Redo or final timing. Those remain explicit user-test gates. A successful Join is not a smoothness certificate.
