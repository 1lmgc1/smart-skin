# Smart Skin

Rhino 8 surface-assistance plug-in. The intended product is a small, dependable command that diagnoses irregular curve/edge frameworks, infers a likely surface strategy, builds candidates and returns a native Rhino result with an explanation.

## Current state: P05 contextual tangent Patch

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

The diagnostic and preflight commands verify that the active saved document
object count is unchanged.

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
shown through a temporary viewport conduit. The document changes only after
explicit preview confirmation; Esc, a blocked route, or a native
construction failure leaves `objects=N->N`. Confirmation adds exactly one native
Brep while preserving every source object.

P03 does not run `Patch` or `NetworkSrf`, sort more than two Loft sections,
align closed-curve seams, repair source curves, trim, join, or score surface
quality. Commit `acdcba9cc0586a769bae7a97ed61dadf74055573` passed GitHub Actions
run 11 and Rhino 8.18 field tests for PlanarSrf, EdgeSrf, Loft, preview,
Accept/Cancel, blocked input, Undo, save, and restart.

The field test also exposed a diagnostic defect: `RhinoDoc.Objects.Count`
includes deleted objects retained for Undo. Geometry and Undo behaved correctly,
but later machine lines reported historical totals. P03F1 version
`0.0.6-p03f1` replaces every direct table count with one active-object
enumerator shared by Version, Preflight, Plan, and Build. Construction behavior
is unchanged. P03F1 is `VERIFIED` for runtime commit
`ada5c269c9d270e44952fcc297b611236c4a4782`. Existing CI and Rhino field evidence
are summarized in [`docs/P03F1_CLOSURE.md`](docs/P03F1_CLOSURE.md).

P04 version `0.0.8-p04` added one native `Smart Skin` toolbar and one button
for `SmartSurfaceBuild`, through a same-name RUI beside the RHP. GitHub Actions
run 13 passed for commit
`a9e854dec93cde1a0e74d2596081d863803993ae`; Rhino 8.18 field evidence showed
the visible toolbar invoking an accepted Loft with `objects=2->3`. The user
accepted the toolbar and P04 is `VERIFIED` for that objective. See
[`docs/P04_CLOSURE.md`](docs/P04_CLOSURE.md).

P04F1 version `0.0.9-p04f1` keeps that toolbar and exposes all four existing
commands as distinct buttons: Build, Plan, Preflight and Version. It adds no
runtime command or solver and changes no production C# source. See
[`docs/P04F1_TOOLBAR.md`](docs/P04F1_TOOLBAR.md).

P05 version `0.0.10-p05` adds the first context-aware soft hole-fill route.
When five to eight selected Brep edges form one strict closed loop, routing
keeps their owning trims instead of reducing them to detached curves.
Construction requires every edge to be naked with one adjacent face, then asks
Rhino for one trimmed tangent Patch using the trim normals. Ordinary curve
loops, manifold edges and ambiguous trim ownership remain blocked or under
review. The log says `G1_REQUESTED`; measured continuity and candidate ranking
remain future work. Preview confirmation now uses Enter, Space or right-click;
Esc cancels. See [`docs/PATCH_NOTES.md`](docs/PATCH_NOTES.md).

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
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.10-p05 -Commit local
```

GitHub Actions performs the same build on Windows and publishes a versioned ZIP for the Rhino test.

The ZIP contains `INSTALL.cmd` and `UNINSTALL.cmd`. `INSTALL.cmd` keeps one managed copy at `%LOCALAPPDATA%\SmartSkin\Rhino8\current`, updates the Rhino 8 per-user registry entry for the fixed Smart Skin plug-in GUID, and removes the known binaries from the previously registered Smart Skin location. Rhino must be closed during either operation.

Repository upload instructions: [`docs/UPLOAD.md`](docs/UPLOAD.md).

## Test in Rhino

Extract the artifact, close Rhino and run `INSTALL.cmd` normally, then follow
[`docs/FIELD_TEST.md`](docs/FIELD_TEST.md). Installation is not a separate
field test; report it only if an actual problem occurs. Do not manually
register the `.rhp` from the extracted download folder. A green CI run is not
equivalent to the focused four-button Rhino check.

## Development sequence

1. P00 — reproducible build/load loop (`VERIFIED`).
2. P01 — read-only GeometryReport/Preflight.
3. P01F1 — preserve top-level versus sub-object selection identity (`VERIFIED`).
4. P02 — input topology classification and candidate routing without geometry mutation (`VERIFIED`).
5. P03 — bounded PlanarSrf/EdgeSrf/Loft candidate preview and explicit one-Brep accept (`VERIFIED` construction behavior on commit `acdcba9cc0586a769bae7a97ed61dadf74055573`).
6. P03F1 — exclude deleted Undo records from all document-count diagnostics (`VERIFIED` on commit `ada5c269c9d270e44952fcc297b611236c4a4782`).
7. P04 — native one-button Build toolbar, version `0.0.8-p04` (`VERIFIED` on commit `a9e854dec93cde1a0e74d2596081d863803993ae`).
8. P04F1 — expand the accepted toolbar to all four existing commands, version `0.0.9-p04f1`.
9. P05 — contextual tangent Patch for one five-to-eight-edge Brep boundary, version `0.0.10-p05`.

## Data and licensing

The repository is public. Do not commit secrets, private models, user evidence or downloaded forum `.3dm` files unless redistribution rights are confirmed. Synthetic and explicitly cleared fixtures will be stored separately from raw research material.

## Official Rhino references

- [Your First Plugin (Windows)](https://developer.rhino3d.com/guides/rhinocommon/your-first-plugin-windows/)
- [Moving to .NET Core](https://developer.rhino3d.com/en/guides/rhinocommon/moving-to-dotnet-core/)
- [Rhino Package Manager guides](https://developer.rhino3d.com/en/guides/yak/)
