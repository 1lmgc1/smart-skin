# Repository rules

## Product boundary

Smart Skin is a Rhino 8 surface-assistance plug-in. P01/P01F1 GeometryReport/Preflight and the P02 topology classifier/router are read-only. P03 may build one bounded disposable PlanarSrf, EdgeSrf or two-section Loft candidate from copies, preview it, and add exactly one Brep only after explicit `Accept`. P03F1 changes only document-count diagnostics so deleted Undo records are excluded. P04 adds a native same-name RUI and its delivery lifecycle; all production C# geometry, selection and counting code remains unchanged. It must never repair, replace or transform source geometry.

## Patch discipline

- One patch has one architectural objective.
- State invariants, acceptance criteria, regressions and intentionally untouched areas.
- Use `VERIFIED`, `STATICALLY CHECKED` and `NOT VERIFIED` literally.
- Do not start the next patch before reviewing the previous field test.
- Never overwrite a released bundle; increment the version.
- P04 restarts as version `0.0.8-p04`, planned publication kit `SmartSkin-P04-v002`; do not impersonate the interrupted `0.0.7-p04`/v001 draft.
- Preserve fixed plug-in and UI GUIDs. Never reset Rhino layouts or delete shared UI settings to repair a toolbar.

## Safety invariants

- Never modify source geometry silently. Future repair operations work on copies and explain changes.
- Rhino API calls stay on Rhino's supported command/UI execution path.
- Expensive operations require cancellation, a complexity limit and a timeout strategy.
- A bad input must fail with a diagnosis rather than hang.
- Do not commit secrets, user evidence or forum models without confirmed redistribution rights.

## Verification economy

- Run targeted tests for the changed layer on ordinary patches.
- Run Rhino smoke tests when plug-in loading, commands or Rhino-facing behavior changes.
- Run the full regression corpus before releases and after shared Router/Validator/Core changes.
- Update the Drive journal at checkpoints, architecture decisions, verified patches, serious blockers or handoff—not after every minor edit.

## Commands

```powershell
dotnet restore SmartSkin.sln
dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=local
dotnet test tests\SmartSkin.Core.Tests\SmartSkin.Core.Tests.csproj -c Release --no-build
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.8-p04 -Commit local
```
