# P01 GeometryReport/Preflight — patch notes

Version: `0.0.2-p01`

## Goal

Turn selected Rhino geometry into a bounded, read-only preflight report before any surface solver or automatic repair is introduced.

## Included

- New `SmartSurfacePreflight` Rhino command.
- Selection of curves, Brep edges, points, surfaces, extrusions and polysurfaces.
- Rhino-independent `SmartSkin.Core.Preflight` snapshots, analyzer, issue codes and report formatter.
- Checks for invalid geometry, invalid or oversized tolerance, degenerate/short curves, short Brep edges, naked edges, high span count and endpoint gaps between 1x and 10x document tolerance.
- Per-item summary, selection scale and machine-readable result.
- Hard bounds of 256 selected elements, 64 issue records and 24 displayed item lines.
- Deep metrics are skipped with `P01_ANALYSIS_LIMITED` instead of forced when a curve/surface exceeds 1000 spans or a Brep exceeds 2000 faces / 5000 edges.
- Unit tests for READY/WARNING/BLOCKED reports, near gaps, Brep warnings, selection bounds and machine-line stability.

## Invariants

- P01 does not add, delete, replace, trim, join, transform or otherwise edit document geometry.
- A successful report ends with `SMARTSKIN_P01 PASS` even when the input status is `WARNING` or `BLOCKED`; `PASS` means the analyzer completed, not that the geometry is clean.
- Document object count is checked before and after the command.
- Unsupported or failed snapshots become explicit diagnostics instead of escaping the command as a crash.
- Selection and output are bounded; no network access or cloud dependency is used.
- RhinoCommon remains a compile-time dependency and is not bundled.

## Intentionally not included

- Surface construction or candidate routing.
- Automatic repair, rebuilding, joining or trimming.
- Duplicate-geometry comparison.
- Curvature/fairness scoring.
- Preview conduit, toolbar, panel or settings.
- Forum `.3dm` fixtures without confirmed redistribution rights.

## Acceptance criteria

- CI restore, Release build, unit tests and packaging succeed.
- `SmartSurfaceVersion` reports `P01`, `0.0.2-p01` and the artifact commit.
- `SmartSurfacePreflight` accepts top-level curves/Breps and a sub-selected Brep edge.
- The report contains types, scale, tolerance, item lines, status and a final `SMARTSKIN_P01 PASS` line.
- Object count is identical before and after successful, blocked-input and cancelled runs.
- Restarting Rhino does not break either command.

## Verification status

- `STATICALLY CHECKED`: source scope, deterministic Core design, bounded output and field-test contract reviewed.
- `NOT VERIFIED`: compilation, unit tests, packaging and Rhino 8 behavior require GitHub Actions and the P01 field test.
