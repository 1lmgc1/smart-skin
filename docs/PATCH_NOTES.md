# P05 contextual tangent Patch

Version: `0.0.10-p05`.
Baseline: P04F1 commit
`98abb7bfd1483406675469c6437e4fc3621e392f`.

## Objective

Build one field-testable soft hole-fill candidate from the real boundary type
found in the supplied private shell model: one strict closed loop of five to eight Brep edge
sub-objects, with the surrounding faces preserved as continuity context.

The private user model is evidence only and is not committed.

## Changed behavior

- A five-to-eight-edge `CLOSED_BOUNDARY_LOOP` routes to `Patch` only when every
  item is a Brep edge.
- Construction verifies that every selected edge is naked, has exactly one
  owning trim and retains one adjacent face.
- The native Patch input contains those owning `BrepTrim` objects rather than
  detached curve copies, so Rhino can sample their surface normals.
- Native construction requests trimming and tangency on one bounded 8x8 Patch.
- The log reports support count, distinct parent count, sample spacing and
  `continuity=G1_REQUESTED`. P05 does not claim measured G1/G2 quality yet.
- Preview confirmation uses Rhino's normal Enter, Space or right-click. Esc
  cancels. No additional Accept/Cancel options are added.

## Safety bounds

- Five to eight boundary edges and at most 64 combined curve spans.
- One disposable in-memory candidate and at most one added Brep.
- Source objects are never changed, joined, trimmed, repaired or deleted.
- Ordinary five-plus-curve loops remain `REVIEW`; only Brep edges can enter the
  contextual route.
- Internal/manifold edges, missing trims and ambiguous trim ownership block
  before native Patch construction.

## Intentionally unchanged

P03 PlanarSrf, EdgeSrf and two-section Loft construction remain available.
Candidate ranking, measured continuity, multiple candidate variants, automatic
joining, both-hole batching and the final settings dialog are not part of P05.
The P04F1 diagnostic toolbar remains temporary and unchanged.

## Acceptance

- Core routing and policy tests cover the new six-edge Brep loop and preserve
  the existing five-curve `REVIEW` behavior.
- GitHub Actions must build, pass the full Core suite, validate the toolbar,
  package `0.0.10-p05` and pass the existing installer lifecycle automation.
- One Rhino 8.18 field test uses one opening from the supplied private shell model. Installation
  is not a separate user test.
