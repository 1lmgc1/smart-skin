# P03F1 Active Document Count — patch notes

Version: `0.0.6-p03f1`

## Goal

Correct every Smart Skin document-count diagnostic so `objects=` means active,
saved Rhino document objects rather than the size of Rhino's component table,
which also retains deleted objects for Undo.

## Field evidence that triggered the fix

P03 commit `acdcba9cc0586a769bae7a97ed61dadf74055573` passed GitHub Actions run 11
and the Rhino 8.18 construction protocol:

- PlanarSrf preview, Accept, source retention, and Undo worked;
- an unordered four-edge loop previewed and accepted one EdgeSrf;
- Loft preview, Cancel, Accept, Undo, save, and restart worked;
- an open chain blocked before preview and selection Esc cancelled safely;
- every accepted candidate was one Brep and every source curve remained.

After PlanarSrf Undo, only the source circle remained selectable, but
`SmartSurfaceVersion` printed `objects=2`. Repeated EdgeSrf tests similarly
reported increasing totals after successful Undo. The surface behavior was
correct; the diagnostic used `RhinoDoc.Objects.Count`, whose contract includes
deleted records retained for Undo.

Official RhinoCommon API basis:

- `ObjectTable.Count` returns all items, including deleted ones:
  <https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/T_Rhino_DocObjects_Tables_ObjectTable.htm>.
- `ObjectEnumeratorSettings.ActiveObjects` returns objects in the current model
  that are saved in the file, while the deleted-object filter is separate:
  <https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/T_Rhino_DocObjects_ObjectEnumeratorSettings.htm>.

## Included

- Add one Rhino-adapter helper that enumerates active, saved document objects.
- Include normal, locked, and hidden active objects.
- Exclude deleted Undo records, instance-definition contents, reference
  objects, grips, lights, and phantoms.
- Use the same helper in `SmartSurfaceVersion`, `SmartSurfacePreflight`,
  `SmartSurfacePlan`, and `SmartSurfaceBuild`.
- Retain all P03 constructors, bounds, copy-only source handling, preview, and
  explicit Accept/Cancel behavior without modification.
- Update patch identity, packaging, installer metadata, CI names, and the
  focused Rhino field protocol.

## Invariants

- A deleted or undone candidate does not contribute to `objects=`.
- `Cancel`, Esc, blocked input, and handled native failure return
  `objects=N->N` using active object counts.
- `Accept` returns `objects=N->N+1`.
- `Undo` followed by `SmartSurfaceVersion` returns N.
- No source geometry is deleted, replaced, transformed, reversed, or edited.

## Intentionally not included

- No constructor, routing, topology, repair, or quality-ranking changes.
- No toolbar or panel. The field test confirmed that command-line-only use is
  inefficient; a minimal `SmartSurfaceBuild` toolbar is the next separate
  product patch.
- No change to the existing P03 machine codes such as `P03_ACCEPTED` and
  `P03_ROUTE_NOT_READY`; only the build identity becomes `P03F1`.

## Verification status

P03F1 is `VERIFIED` on runtime commit
`ada5c269c9d270e44952fcc297b611236c4a4782`: GitHub Actions run 12 passed build,
31/31 Core tests, packaging and installer lifecycle; the existing Rhino 8.18
count/Undo/restart field results were closed in journal record 017.
See `P03F1_CLOSURE.md` for provenance. This closure does not claim a new Rhino
run and does not require reinstalling or retesting the unchanged runtime.
