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
- Make `INSTALL.cmd` pass its package directory without a quote-corrupting trailing backslash and exercise the launcher from a temporary path containing spaces.

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

- `VERIFIED`: GitHub Actions run 7 restored, built, packaged and passed all 11 Core tests for commit `550b74ff9f5bd8953d80c28560a9951d39214d55`.
- `VERIFIED`: run 7 exercised the actual `INSTALL.cmd` launcher from a path containing spaces, migration from a manual installation, repeat update and uninstall. The lifecycle removed two legacy binaries during the migration case and left no stale registration.
- `VERIFIED`: the field installer completed at `%LOCALAPPDATA%\SmartSkin\Rhino8\current\SmartSkin.Rhino8.rhp`; Rhino Plug-in Manager showed one enabled and loaded Smart Skin entry, and `SmartSurfaceVersion` reported the expected version and commit after a full restart.
- `VERIFIED`: Rhino 8.18 field testing reported a whole saved Box as `Extrusion=1` with `object:Extrusion`, a sub-selected edge as `BrepEdge=1` with a `subobject:` label, and `objects=1->1` for both completed reports.
- `VERIFIED`: cancelling `SmartSurfacePreflight` before selection returned control without changing the saved Box; the following version check reported `objects=1`. Reopening the saved `.3dm` after closing Rhino retained `Extrusion=1` and `objects=1->1`.
- `NOT VERIFIED`: none within the P01F1 acceptance scope. Surface construction and repair remain intentionally outside this patch.
