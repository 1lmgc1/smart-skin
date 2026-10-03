# P07F2 / 0.0.14-p07f2 — restore the field-test path

## Diagnosis and objective

The synthetic split-edge fixture in P07F1 called `SplitEdgeAtParameters` followed only by `Compact`. Low-level splitting may leave the new vertex tolerance unset. McNeel's documented completion pattern computes missing vertex tolerances before compacting. P07F2 finishes this fixture before testing boundary correspondence. This is not an instruction to repair user geometry and is not a solver change.

P07F1 also placed full-width notes and checkboxes in the first column of the same DynamicLayout as label/input pairs. That lets the long note push the input column outside the fixed window. P07F2 uses independent nested rows for each field, a bounded wrapping note and a separate opacity row. A fatal self-test message no longer suggests that a settings change can fix it.

## Unchanged safety and geometry

Production `BoundaryMatchVerifier`, `RhinoCandidateBuilder`, `CandidateBuildSettings`, `SmartSkinLivePreviewSession`, `SmartSurfaceBuildCommand`, Core, RUI and project runtime target are byte-identical to baseline b0581d2f627b323ec4f89fee7df0f1171ce18594. Source guards check this in CI. No self-test bypass, tolerance increase, G2 downgrade, new seed or Patch fallback is introduced. The existing fail-closed gate remains. One button, one live window, Enter/Space/right-click confirmation, Esc cancellation and source ownership rules remain.

## Native fixture acceptance

All eight original cases must still run. `split_edge_same_face` now records post-split validity and Rhino's diagnostic log, computes only unset vertex tolerances, compacts, and requires `IsValidWithLog` success. It must keep one face, five vertices, five naked boundary edges, four target edges and the same underlying surface. The unchanged verifier must then report verified G2 with every candidate and target edge covered at the original tolerance. Merely making the Brep structurally valid is not a passing test.

The raw post-split state is observed, not asserted invalid, so a later Rhino version that initializes its own vertex tolerance is allowed. Fixture setup errors are named `FIXTURE_INVALID` separately from measured continuity failures.

## Evidence boundary

- CI compilation, Core tests, static source guards, RUI validation and isolated installer tests can be VERIFIED only from their actual exact-commit run.
- Source guards are STATICALLY CHECKED evidence, not native execution or proof of rendered control placement.
- Native self-tests, new UI rendering, loading and the private hole are NOT VERIFIED until the actual Rhino field run.
- Prior P07F1 field evidence and private model/screenshot stay in the private development journal, not in this repository.

## Diagnostic compatibility

The current assembly identity and self-test/fixture prefix are `P07F2`. Unmodified input/boundary/attempt protocols still use `SMARTSKIN_P07F1_*`; existing `P07_*` outcome codes and `P07F1_VALIDATOR_SELFTEST_FAILED` remain intentional stable identifiers. Read version and commit from SmartSurfaceVersion. An action=CANCELLED line with PASS is safe command completion, not a successful geometric result.

## Primary references

- https://discourse.mcneel.com/t/bug-brepedgelist-splitedgeatparameters-leaves-brep-in-invalid-state/161849/3
- https://developer.rhino3d.com/api/rhinocommon/rhino.geometry.brep/settolerancesboxesandflags
- https://developer.rhino3d.com/guides/rhinopython/eto-layouts-python/
