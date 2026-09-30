# Smart Skin

Rhino 8 surface-assistance plug-in. The intended product is a small, dependable command that diagnoses irregular curve/edge frameworks, infers a likely surface strategy, builds candidates and returns a native Rhino result with an explanation.

## Current patch: P01F1 selection-identity fix

P00 proved the repository → CI → artifact → Rhino field-test loop and is `VERIFIED` in Rhino 8.18.

P01 added the first read-only geometry command:

```text
SmartSurfacePreflight
```

Select curves, Brep edges, points, surfaces or polysurfaces. The command reports:

- selection types, validity and bounding-box scale;
- curve length, closure, planarity, degree and span count;
- near endpoint gaps above document tolerance;
- Brep face/edge counts, naked edges and edges not longer than tolerance;
- document tolerance relative to the selected geometry scale;
- bounded issue codes and a machine-readable PASS line.

P01 never creates or repairs geometry. The existing diagnostic command remains available:

```text
SmartSurfaceVersion
```

Both commands verify that the document object count is unchanged.

P01F1 fixes a field-test regression in the Rhino adapter: selecting an entire
`Extrusion` could be reported as the curve returned by `ObjRef.Curve()` instead
of as the selected document object. The adapter now uses
`GeometryComponentIndex` to separate sub-object picks from top-level objects.
Whole extrusions report as `Extrusion`; a sub-selected Brep edge still reports
as `BrepEdge`. Item labels include the parent object type and whether Rhino
returned an object or sub-object component. Geometry remains read-only.

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
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.3-p01f1 -Commit local
```

GitHub Actions performs the same build on Windows and publishes a versioned ZIP for the Rhino test.

The ZIP contains `INSTALL.cmd` and `UNINSTALL.cmd`. `INSTALL.cmd` keeps one managed copy at `%LOCALAPPDATA%\SmartSkin\Rhino8\current`, updates the Rhino 8 per-user registry entry for the fixed Smart Skin plug-in GUID, and removes the known binaries from the previously registered Smart Skin location. Rhino must be closed during either operation.

Repository upload instructions: [`docs/UPLOAD.md`](docs/UPLOAD.md).

## Test in Rhino

Extract the artifact, close Rhino and run `INSTALL.cmd`, then follow [`docs/FIELD_TEST.md`](docs/FIELD_TEST.md). Do not manually register the `.rhp` from the extracted download folder. A green CI run is not equivalent to a Rhino field test.

## Development sequence

1. P00 — reproducible build/load loop (`VERIFIED`).
2. P01 — read-only GeometryReport/Preflight.
3. P01F1 — preserve top-level versus sub-object selection identity (current patch).
4. Router and candidate adapters only after P01F1 is verified in Rhino.

## Data and licensing

The repository is public. Do not commit secrets, private models, user evidence or downloaded forum `.3dm` files unless redistribution rights are confirmed. Synthetic and explicitly cleared fixtures will be stored separately from raw research material.

## Official Rhino references

- [Your First Plugin (Windows)](https://developer.rhino3d.com/guides/rhinocommon/your-first-plugin-windows/)
- [Moving to .NET Core](https://developer.rhino3d.com/en/guides/rhinocommon/moving-to-dotnet-core/)
- [Rhino Package Manager guides](https://developer.rhino3d.com/en/guides/yak/)
