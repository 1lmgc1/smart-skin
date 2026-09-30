# Repository rules

## Product boundary

Smart Skin is a Rhino 8 surface-assistance plug-in. P00 is diagnostic-only. Do not add geometry features to P00.

## Patch discipline

- One patch has one architectural objective.
- State invariants, acceptance criteria, regressions and intentionally untouched areas.
- Use `VERIFIED`, `STATICALLY CHECKED` and `NOT VERIFIED` literally.
- Do not start the next patch before reviewing the previous field test.
- Never overwrite a released bundle; increment the version.

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
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.1-p00 -Commit local
```

