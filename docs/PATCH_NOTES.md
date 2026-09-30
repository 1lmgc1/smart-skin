# P00 Bootstrap — patch notes

Version: `0.0.1-p00`

## Goal

Establish a reproducible Rhino 8 plug-in build and field-test loop before adding geometry logic.

## Included

- `SmartSkin.Core`, independent of Rhino UI.
- `SmartSkin.Rhino8`, using a conservative `net48` compatibility baseline for the first Rhino 8 load test.
- Diagnostic-only `SmartSurfaceVersion` command.
- Unit tests for build identity output.
- Windows GitHub Actions build, test and artifact packaging.
- Versioned Rhino 8 field-test package.

## Invariants

- The command does not add, delete, replace or transform document objects.
- No network access, cloud dependency or secret is required at runtime.
- No forum `.3dm` files or user evidence are committed.
- RhinoCommon is a compile-time dependency and is not bundled with the plug-in.
- Failed build, test or packaging stops artifact publication.

## Intentionally not included

- Surface construction.
- Object selection or preview.
- GeometryReport/Preflight.
- UI panels or settings.
- Yak publication.

## Verification status

- `STATICALLY CHECKED`: source structure, bounded P00 scope and packaging contract.
- `NOT VERIFIED`: NuGet restore, compilation, unit tests and Rhino loading must run in GitHub Actions and Rhino 8.
