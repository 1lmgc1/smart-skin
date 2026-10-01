# Smart Skin

Rhino 8 surface-assistance plug-in. The intended product is a small, dependable command that diagnoses irregular curve/edge frameworks, infers a likely surface strategy, builds candidates and returns a native Rhino result with an explanation.

## Current state: P03 implemented, field verification pending

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

The diagnostic and preflight commands verify that the document object count is unchanged.

P01F1 fixed a field-test regression in the Rhino adapter: selecting an entire
`Extrusion` could be reported as the curve returned by `ObjRef.Curve()` instead
of as the selected document object. The adapter now uses
`GeometryComponentIndex` to separate sub-object picks from top-level objects.
Whole extrusions report as `Extrusion`; a sub-selected Brep edge still reports
as `BrepEdge`. Item labels include the parent object type and whether Rhino
returned an object or sub-object component. Geometry remains read-only. The
correction, managed installer lifecycle, cancellation path and restart behavior
are `VERIFIED` in Rhino 8.18 for field build commit
`550b74ff9f5bd8953d80c28560a9951d39214d55`.

P02 adds a second read-only command:

```text
SmartSurfacePlan
```

It runs the verified snapshot/preflight path, clusters open-curve endpoints at
document tolerance, classifies the selected frame and ranks native Rhino
strategies. Current classifications cover a single closed boundary, a closed
loop of segments, disconnected sections, an open chain, branched or mixed
frames, point-guided inputs and surface-only context. Candidate strategies are
`PlanarSrf`, `EdgeSrf`, `Loft`, `Patch` and `NetworkSrf`.

P02 deliberately stops at an explained plan. It does not create preview or
document geometry, does not repair gaps, and does not claim internal
intersection families or G0/G1/G2 continuity that it has not measured.
`SmartSurfacePlan` also verifies the document object count before returning.
GitHub Actions run 9 restored, built, ran all 23 Core tests, packaged the
plug-in and passed the installer lifecycle for commit
`450bf1e28b77abdb5e17ca6b06fa5c1564963a5b`. Rhino 8.18 field testing verified
the `PlanarSrf`, `EdgeSrf`, `Loft` and blocked open-chain routes, cancellation
without mutation and the same section route after a full Rhino restart. P02 is
`VERIFIED`.

P03 adds the first geometry-producing command:

```text
SmartSurfaceBuild
```

It reuses the verified preflight and routing path, then admits only three
bounded routes: one planar closed curve for `PlanarSrf`, two to four open
curves forming a closed loop for `EdgeSrf`, or exactly two matching open/open
or closed/closed sections for `Loft`. Construction is capped at four curves
and 64 combined spans. A single Brep candidate is built from curve copies and
shown through a temporary viewport conduit. The document changes only when the
user explicitly chooses `Accept`; `Cancel`, Esc, a blocked route, or a native
construction failure leaves `objects=N->N`. Accept adds exactly one native
Brep while preserving every source object.

P03 does not run `Patch` or `NetworkSrf`, sort more than two Loft sections,
align closed-curve seams, repair source curves, trim, join, or score surface
quality. Source-level policy tests and static checks may be completed before
publication, but CI, packaging and Rhino behavior remain `NOT VERIFIED` until
the exact P03 commit passes those environments.

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
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.5-p03 -Commit local
```

GitHub Actions performs the same build on Windows and publishes a versioned ZIP for the Rhino test.

The ZIP contains `INSTALL.cmd` and `UNINSTALL.cmd`. `INSTALL.cmd` keeps one managed copy at `%LOCALAPPDATA%\SmartSkin\Rhino8\current`, updates the Rhino 8 per-user registry entry for the fixed Smart Skin plug-in GUID, and removes the known binaries from the previously registered Smart Skin location. Rhino must be closed during either operation.

Repository upload instructions: [`docs/UPLOAD.md`](docs/UPLOAD.md).

## Test in Rhino

Extract the artifact, close Rhino and run `INSTALL.cmd`, then follow [`docs/FIELD_TEST.md`](docs/FIELD_TEST.md). Do not manually register the `.rhp` from the extracted download folder. A green CI run is not equivalent to a Rhino field test.

## Development sequence

1. P00 — reproducible build/load loop (`VERIFIED`).
2. P01 — read-only GeometryReport/Preflight.
3. P01F1 — preserve top-level versus sub-object selection identity (`VERIFIED`).
4. P02 — input topology classification and candidate routing without geometry mutation (`VERIFIED`).
5. P03 — bounded PlanarSrf/EdgeSrf/Loft candidate preview and explicit one-Brep accept (`NOT VERIFIED` in Rhino until the field protocol passes).

## Data and licensing

The repository is public. Do not commit secrets, private models, user evidence or downloaded forum `.3dm` files unless redistribution rights are confirmed. Synthetic and explicitly cleared fixtures will be stored separately from raw research material.

## Official Rhino references

- [Your First Plugin (Windows)](https://developer.rhino3d.com/guides/rhinocommon/your-first-plugin-windows/)
- [Moving to .NET Core](https://developer.rhino3d.com/en/guides/rhinocommon/moving-to-dotnet-core/)
- [Rhino Package Manager guides](https://developer.rhino3d.com/en/guides/yak/)
