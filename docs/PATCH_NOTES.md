# P01F1 Selection Identity — patch notes

Version: `0.0.3-p01f1`

## Goal

Correct one Rhino-facing classification defect found during the P01 field test without widening the read-only GeometryReport/Preflight scope.

## Field-test finding

- A sub-selected Box edge correctly reported `BrepEdge=1`.
- Selecting the whole Box, stored by Rhino as an `Extrusion`, reported a closed `Curve` with the extrusion profile length.
- The document remained unchanged, so this is an input-identity defect rather than a geometry mutation.

## Cause

`RhinoGeometrySnapshotFactory` called `ObjRef.Curve()` before determining whether the reference represented a top-level object or a sub-object. Rhino can expose a curve associated with an Extrusion reference, so the helper result was mistaken for the user's selected document object.

## Included

- Use `ObjRef.GeometryComponentIndex` to separate sub-object references from parent-object references before geometry extraction.
- Resolve top-level geometry from `RhinoObject.Geometry` instead of probing `ObjRef.Curve()` first.
- Preserve explicit `BrepEdge` handling for sub-selected edges.
- Add `GeometryKind.Extrusion` and bounded Brep-derived face/edge metrics for whole Extrusions.
- Include `object:<type>` or `subobject:<component>@<parent-type>` in each selection label so Selection Filter behavior is explicit.
- Add a Core regression test proving that an Extrusion remains typed as `Extrusion` in the report.
- Update build identity, CI artifact names and the targeted Rhino field test.
- Add a per-user `INSTALL.cmd`/`UNINSTALL.cmd` lifecycle. Updates use the stable `%LOCALAPPDATA%\SmartSkin\Rhino8\current` path, replace the registered build and remove known binaries from the previously registered Smart Skin location.
- Add a Windows CI lifecycle test covering migration from a manually registered artifact, preservation of unrelated files, repeat update cleanup, registry replacement and uninstall.

## Invariants

- P01F1 does not add, delete, replace, trim, join, transform or otherwise edit document geometry.
- A whole Box stored as an Extrusion must not be downgraded to its profile curve.
- A sub-selected Brep edge must remain `BrepEdge`.
- Cancellation returns control to Rhino without geometry changes.
- Selection, analysis and output bounds from P01 remain unchanged.
- Installer cleanup is limited to the exact Smart Skin registry GUID, its managed install root, and the five known Smart Skin binary/debug filenames beside a previously registered `SmartSkin.Rhino8.rhp`.

## Intentionally not included

- Surface construction, candidate routing or automatic repair.
- SubD analysis.
- Duplicate comparison, curvature scoring, preview, toolbar or panel.
- Changes to the P01 tolerance and near-gap rules.

## Acceptance criteria

- CI restore, Release build, Core tests and packaging succeed.
- The installer lifecycle CI test succeeds and leaves no previous managed version or stale Smart Skin registration.
- `SmartSurfaceVersion` reports `P01F1`, `0.0.3-p01f1` and the artifact commit.
- Selecting a whole Rhino Box reports `Types: Extrusion=1`, not `Curve=1`.
- Sub-selecting a Box edge reports `Types: BrepEdge=1`.
- Item labels identify object versus sub-object scope and the parent Rhino object type.
- Both completed reports keep `objects=N->N`.
- Pressing Esc before selection cancels without changing the document.
- The same checks survive a full Rhino restart.

## Verification status

- `VERIFIED`: GitHub Actions run 4 restored, built, executed all 11 Core tests and packaged commit `0a53abd245924c5b3789a305b469910e553cd1f7`; all 11 Core tests passed, including the Extrusion regression.
- `STATICALLY CHECKED`: run 4 exposed a test-harness failure in `Installer lifecycle test`. The temporary nested registry branch is now created one level at a time, and the test always emits a machine-readable failure location plus a downloadable transcript.
- `NOT VERIFIED`: the corrected Windows installer lifecycle, field-test artifact publication and Rhino 8 behavior require the next GitHub Actions run and P01F1 field test.
