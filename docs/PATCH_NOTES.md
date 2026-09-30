# P02 Topology Classifier and Strategy Router — patch notes

Version: `0.0.4-p02`

## Goal

Turn the verified P01F1 geometry snapshots into a deterministic, bounded and
read-only answer to two questions:

1. What endpoint topology does the selected frame have?
2. Which native Rhino surface strategy should be tried first?

P02 ranks strategies but does not invoke them.

## Evidence boundary

P02 uses only data already captured by the bounded preflight layer: object
kind, curve closure, endpoints, individual planarity, points, selected surface
context and document tolerance. Endpoint connections are strict: two endpoints
belong to the same node only when their distance is not greater than absolute
tolerance.

P02 does not inspect curve/curve intersections away from endpoints, curvature,
surface normals or continuity. It therefore never claims that a selection is a
valid `NetworkSrf` grid or that selected surface context implies G0/G1/G2.

## Included

- Add `SmartSurfacePlan`, a read-only Rhino command using the existing bounded
  snapshot and preflight path.
- Classify `SINGLE_CLOSED_BOUNDARY`, `CLOSED_BOUNDARY_LOOP`, `SECTION_SET`,
  `OPEN_CHAIN`, `BRANCHED_FRAME`, `HYBRID_FRAME`, `POINT_SET`,
  `POINT_GUIDED_FRAME`, `SURFACE_CONTEXT_ONLY`, `UNSUPPORTED` and `UNRESOLVED`.
- Build a tolerance-clustered endpoint graph with node, component, end,
  through-node and junction counts.
- Rank bounded candidates from `PlanarSrf`, `EdgeSrf`, `Loft`, `Patch` and
  `NetworkSrf`, with an explicit rationale and confidence value.
- Return `READY`, `REVIEW` or `BLOCKED`. A usable candidate may remain under
  `REVIEW` when preflight warnings or unresolved semantic roles exist.
- Preserve preflight warnings in routing notes; a blocking preflight returns no
  construction candidate.
- Add a stable machine-readable result containing route status, topology,
  primary strategy, candidate count, selection count and document object-count
  invariant.
- Add Core regression tests for planar and non-planar closed boundaries,
  two-to-four-edge loops, loops with more than four segments, disconnected
  sections, open chains, branches, near gaps, point guidance, surface-only
  context, blocking preflight and machine output.

## Routing rules in this patch

| Observed topology | Primary route | Important limitation |
|---|---|---|
| One planar closed curve | `PlanarSrf` | Planarity is taken from Rhino's curve check. |
| One closed non-planar curve | `Patch` | It is a fitted result, not an exact boundary surface. |
| Closed loop of 2–4 open curves | `EdgeSrf` | Only strict endpoint closure is proven. |
| Closed loop of more than 4 curves | `Patch` | `NetworkSrf` remains secondary and requires later intersection validation. |
| Disconnected curves | `Loft` | P02 does not yet infer or reorder section direction. |
| Branched or mixed frame | `Patch` | Boundary and guide roles remain unresolved. |
| Curves plus points, or points only | `Patch` | Boundary weights and edge constraints are not inferred. |
| Open chain | none | It is diagnosed as a boundary fragment. |
| Only surfaces/polysurfaces | none | Boundary edges or construction curves must be selected. |

## Safety and complexity bounds

- P02 does not add, delete, replace, trim, join, transform or otherwise modify
  document geometry.
- Selection remains bounded at 256 items. The endpoint graph contains at most
  512 endpoints and uses a bounded pairwise distance pass.
- Output candidates and notes are bounded.
- Cancellation returns control to Rhino before analysis.
- Source snapshots and P01 issue codes remain unchanged.

## Intentionally not included

- Calling any Rhino construction command or committing a candidate.
- Preview geometry, undo records, automatic repair or tolerance snapping.
- Internal curve-intersection analysis and U/V family inference.
- Section ordering, seam alignment or curve-direction correction.
- G0/G1/G2 inference, curvature scoring or result-quality comparison.
- SubD, toolbar, panel or persistent UI.

## Acceptance criteria

- CI restore, Release build, all Core tests, packaging and installer lifecycle
  succeed.
- `SmartSurfaceVersion` reports `P02`, `0.0.4-p02` and the artifact commit.
- A planar closed curve routes to `SINGLE_CLOSED_BOUNDARY` / `PLANAR_SRF`.
- Four endpoint-connected boundary curves route to
  `CLOSED_BOUNDARY_LOOP` / `EDGE_SRF`.
- Two disconnected closed or open section curves route to
  `SECTION_SET` / `LOFT`.
- An open chain returns `BLOCKED` with `primary=NONE`.
- Completed and cancelled commands keep `objects=N->N` or the unchanged
  version-command count.
- The same route survives a full Rhino restart.

## Verification status

- `VERIFIED`: P01F1 remains the Rhino-tested read-only snapshot and installer baseline.
- `STATICALLY CHECKED`: P02 source, bounded graph logic, routing contract, tests,
  workflow, versioning and field-test instructions were reviewed in the current
  environment.
- `NOT VERIFIED`: the current environment has no .NET SDK or Rhino. Compilation,
  Core tests, packaging, Windows installer lifecycle and Rhino 8 behavior require
  GitHub Actions and the P02 field test.
