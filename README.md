# Smart Skin

Rhino 8 surface-assistance plug-in. The intended product is a small, dependable command that diagnoses irregular curve/edge frameworks, infers a likely surface strategy, builds candidates and returns a native Rhino result with an explanation.

## Current patch: P00 Bootstrap

P00 contains no surface solver. It proves the repository → CI → artifact → Rhino field-test loop with the diagnostic command:

```text
SmartSurfaceVersion
```

The command prints the patch, version, commit, Rhino/runtime information and a machine-readable PASS line. It verifies that the document object count is unchanged.

## Projects

- `src/SmartSkin.Core` — Rhino-independent code.
- `src/SmartSkin.Rhino8` — Rhino 8 `.rhp`, initially targeting the `net48` compatibility baseline.
- `tests/SmartSkin.Core.Tests` — console/unit tests.

## Build

Requirements for a Windows developer machine:

- Visual Studio 2022 or the .NET SDK tooling.
- .NET 8 SDK for tests.
- .NET Framework 4.8 targeting pack.

```powershell
dotnet restore SmartSkin.sln
dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=local
dotnet test tests\SmartSkin.Core.Tests\SmartSkin.Core.Tests.csproj -c Release --no-build
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.1-p00 -Commit local
```

GitHub Actions performs the same build on Windows and publishes a versioned ZIP for the Rhino test.

Repository upload instructions: [`docs/UPLOAD.md`](docs/UPLOAD.md).

## Test in Rhino

Follow [`docs/FIELD_TEST.md`](docs/FIELD_TEST.md). A green CI run is not equivalent to a Rhino field test.

## Development sequence

1. P00 — reproducible build/load loop.
2. P01 — read-only GeometryReport/Preflight.
3. Router and candidate adapters only after the input report is verified on cleared fixtures.

## Data and licensing

The repository is public. Do not commit secrets, private models, user evidence or downloaded forum `.3dm` files unless redistribution rights are confirmed. Synthetic and explicitly cleared fixtures will be stored separately from raw research material.

## Official Rhino references

- [Your First Plugin (Windows)](https://developer.rhino3d.com/guides/rhinocommon/your-first-plugin-windows/)
- [Moving to .NET Core](https://developer.rhino3d.com/en/guides/rhinocommon/moving-to-dotnet-core/)
- [Rhino Package Manager guides](https://developer.rhino3d.com/en/guides/yak/)
