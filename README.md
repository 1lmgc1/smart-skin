# Smart Skin

Rhino 8 surface-assistance plug-in. One product button and one live result window; native editable Brep output, or an explicit reason why construction/verification is blocked.

## Current patch: P07F2 / 0.0.14-p07f2

P07F2 repairs the synthetic split-edge self-test setup and the settings-window layout. Low-level SplitEdgeAtParameters needs its new vertex tolerance finalized before the fixture is judged valid. The corrected fixture must still pass the unchanged G2 verifier with all five output edges mapped against four target edges. All eight native tests and the fail-closed gate remain. Full-width labels no longer share the input-caption column and push controls outside the window.

**This is not a replacement native solver.** The production verifier, P07's MatchSrf call and seed construction, tolerance settings and strict Join proof are unchanged from P07F1. A returned Brep, successful compilation, or a G2 request is not a verified G2 result.

See [P07F2 verification contract](docs/P07F2_VERIFICATION.md), [boundary verification contract](docs/P07F1_VERIFICATION.md), [field test](docs/FIELD_TEST.md), [patch notes](docs/PATCH_NOTES.md), and [handoff](docs/HANDOFF.md). Read the exact GitHub Actions commit before installing its artifact. New native execution, rendered UI and the private opening remain **NOT VERIFIED** until their actual Rhino evidence is returned.

## Interaction and safety

Select the boundary edges and finish with Enter. Their owning Breps are obtained automatically; no separate whole-object selection is necessary. The existing window controls G0/G1/G2, Refine, curvature tolerance, isocurve direction and preview appearance. Enter, Space or right-click adds the current verified result; Esc cancels. Average is an explicit source-replacement mode available only for supported natural untrimmed targets; it also requires attribute checks and proof that all selected seams joined. Match-only preserves sources and adds one cap. There is no CreatePatch fallback.

The first contextual build per Rhino process runs eight small disposable native validator regressions on the command/UI thread. They do not access RhinoDoc. Any regression failure blocks the matching route and reports its case. The supported input route remains five to eight naked Brep edges forming one closed loop. Existing bounded PlanarSrf, EdgeSrf and two-section Loft routes are unchanged. This release does not implement whole-object reconstruction, global fairness optimization, interior foldover certification or an analytic proof of continuous G2 along every point.

## Build and installation

- Windows; Rhino **8.21 or newer** for the MatchSrf API.
- .NET SDK for building, .NET 8 for Core tests, and .NET Framework 4.8 targeting pack.
- Rhino-host assembly keeps the net48 compatibility target; Core targets netstandard2.0. Earlier P07/P07F1 loading is not a substitute for loading this exact build.

```powershell
dotnet restore SmartSkin.sln
dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=local
dotnet test tests\SmartSkin.Core.Tests\SmartSkin.Core.Tests.csproj -c Release --no-build
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.14-p07f2 -Commit local
```

The hosted Windows workflow builds the actual RHP with warnings as errors, runs Core tests and static source-integrity checks, checks the unchanged native RUI, packages a versioned ZIP and tests the managed installer in isolated directories/registry keys. It does **not** run licensed Rhino native geometry or render the settings window. Its artifacts explicitly state that boundary.

Extract the field-test ZIP, close Rhino and run `INSTALL.cmd` normally. It keeps one managed copy at `%LOCALAPPDATA%\SmartSkin\Rhino8\current` and updates the fixed per-user plug-in registration. Do not manually register another RHP from a download folder. `UNINSTALL.cmd` removes the managed installation; Rhino must be closed. Installation is not a separate field test.

## Historical milestones

P00 proved the build/load loop; P01/P01F1 added read-only preflight and corrected sub-object identity; P02 added topology routing. P03 established bounded PlanarSrf/EdgeSrf/Loft preview and commit. P03F1 corrected active-object counts and is field-verified at `ada5c269c9d270e44952fcc297b611236c4a4782`. P04 established the native toolbar; P04F1 temporarily exposed diagnostic buttons. P05 introduced a contextual Patch, whose geometry was later rejected. P06 established the accepted one-button/live-window interaction; its Patch geometry was not accepted. P07 (`27a4d1e2f0e1b1363915e72cb674147f0a42eddd`) replaced that route with measured MatchSrf on Rhino 8.21+. P07F1 introduced whole-boundary verification and per-attempt diagnostics. P07F2 repairs its fixture initialization and layout without claiming that the private opening already passes.

Earlier detailed notes remain in Git history and `docs/P03F1_CLOSURE.md`, `docs/P04_CLOSURE.md` and `docs/P04F1_TOOLBAR.md`. The Google Drive journal is for development history, not code or release bundles.

## Projects and data

`src/SmartSkin.Core`: Rhino-independent analysis and boundary graph. `src/SmartSkin.Rhino8`: Rhino host, native verification and preview. `tests/SmartSkin.Core.Tests`: native-free regression suite. Private models, field evidence, secrets and downloaded forum models without redistribution permission must never be committed to this public repository. Native fixtures are synthetic and created in memory.

## Official references

- [Your first Rhino plug-in](https://developer.rhino3d.com/guides/rhinocommon/your-first-plugin-windows/)
- [Rhino runtime compatibility](https://developer.rhino3d.com/guides/rhinocommon/moving-to-dotnet-core/)
- [MatchSrf](https://docs.mcneel.com/rhino/8/help/en-us/commands/matchsrf.htm)
- [Finishing a low-level edge split](https://discourse.mcneel.com/t/bug-brepedgelist-splitedgeatparameters-leaves-brep-in-invalid-state/161849/3)
- [Eto layout column rules](https://developer.rhino3d.com/guides/rhinopython/eto-layouts-python/)
