# P03 Bounded Candidate Preview and Accept — patch notes

Version: `0.0.5-p03`

## Goal

Turn the verified P02 primary route into one disposable native Rhino Brep,
preview it without changing the document, and add exactly one object only after
the user explicitly chooses `Accept`.

## Included

- Add `SmartSurfaceBuild` while retaining `SmartSurfaceVersion`,
  `SmartSurfacePreflight`, and `SmartSurfacePlan`.
- Re-run the existing snapshot, preflight, topology, and route pipeline before
  every build.
- Add a Rhino-independent construction policy with stable block codes.
- Construct only these `READY` primary routes:
  - `PlanarSrf`: exactly one closed curve proven planar;
  - `EdgeSrf`: two to four open curves in a tolerance-closed loop;
  - `Loft`: exactly two sections with matching open/closed state.
- Duplicate every selected curve or Brep edge before ordering, reversing, or
  passing it to a Rhino constructor.
- Order and orient EdgeSrf curve copies around their endpoint loop.
- Preserve Loft selection order and direction-align only the second copy.
- Show one cyan shaded/wire preview through a temporary `DisplayConduit`.
- Offer explicit `Accept` and `Cancel`; Esc follows the cancellation path.
- Add the accepted candidate with `RhinoDoc.Objects.AddBrep`. The enclosing
  Rhino command supplies the normal Rhino Undo record.
- Emit machine-readable `ACCEPTED`, `CANCELLED`, or `BLOCKED` outcomes including
  strategy, code, construction time, reversal count, and object counts.

## Construction bounds

| Bound | P03 value | Reason |
|---|---:|---|
| Accepted route state | `READY` only | Warnings and semantic ambiguity never enter construction. |
| Curves | 4 maximum | Covers the admitted constructors without broad selection work. |
| Combined curve spans | 64 maximum | Keeps the first native-construction slice deliberately small. |
| Loft sections | exactly 2 | P03 does not infer section order for larger sets. |
| Native result | exactly 1 Brep | Avoids an ambiguous multi-result commit. |
| Result faces / edges | 64 / 256 maximum | Rejects unexpectedly complex output before preview. |

The admitted Rhino methods are short synchronous native constructors on the
supported Rhino command/UI thread. P03 does not claim a hard interrupt once a
native call begins. Its hang-risk strategy is to exclude Patch/NetworkSrf and
all repair/intersection searches, and to enforce the input bounds before the
call. A later patch that admits expensive solvers must add a real cancellable
API and timeout strategy.

## Document invariants

- Selection, snapshot extraction, routing, construction, and preview must leave
  the document object count unchanged.
- Source objects are never deleted, replaced, transformed, reversed, or edited.
- `Cancel`, Esc, blocked input, and handled native failure return
  `objects=N->N`.
- `Accept` is the only commit path and must return `objects=N->N+1`.
- A successful Rhino `Undo` after Accept must return the document to N objects.
- Preview is disabled in a `finally` block on every decision path.

## Intentionally not included

- `Patch`, `NetworkSrf`, Sweep, SubD, mesh wrapping, or multi-candidate ranking.
- Three-or-more-section ordering or closed-section seam alignment.
- Gap repair, snapping, rebuilding, trimming, joining, or source replacement.
- Curvature, fairness, deviation, self-intersection, or G0/G1/G2 scoring.
- Background execution or an unsafe attempt to call Rhino geometry APIs off the
  command/UI thread.
- Toolbar, panel, persistent options, or automatic command invocation.

## Acceptance criteria

- CI restore and Release build succeed with warnings treated as errors.
- All Core tests pass, including the new construction-policy cases.
- Packaging and the managed installer lifecycle pass for the exact P03 commit.
- `SmartSurfaceVersion` reports `P03`, `0.0.5-p03`, and that commit.
- Circle Accept produces one planar Brep and preserves the circle.
- A scrambled selection of four exploded rectangle sides previews and accepts
  one EdgeSrf Brep.
- Two circles can be cancelled with no object change and accepted as one Loft.
- An open chain blocks before preview and changes nothing.
- Undo removes the accepted candidate while preserving all inputs.
- Cancellation and command loading still work after a full Rhino restart.

## Verification status

- `VERIFIED`: P02 field baseline commit
  `450bf1e28b77abdb5e17ca6b06fa5c1564963a5b` and P02 closure commit
  `aa3402bc922f74af7867fa799014447861c74304`.
- `STATICALLY CHECKED`: P03 source architecture, bounds, mutation paths, machine
  output, packaging metadata, and Core test cases after local review.
- `NOT VERIFIED`: P03 compilation and Core tests until GitHub Actions runs on
  the exact target commit (the current environment has no .NET SDK).
- `NOT VERIFIED`: P03 package, managed update, viewport preview, native Rhino
  constructors, Accept/Cancel/Undo, and restart behavior until the field test
  in `docs/FIELD_TEST.md` passes.
