# Bounded coupled U/V coefficient basis

Status: **VERIFIED** in the synthetic and generic numerical tests listed below.
**NOT VERIFIED** in licensed Rhino, on the repaired native hard-corner/fan result,
or as a complete source-attachment solution. No publication or installer change.

## Architectural objective

Provide real scalar handles on the current full U rows and five V profiles, using a fixed
source-derived layout and a linear response cache. A selected shared guide moves
on both incident patches. Original source geometry and its required two-jets stay
fixed. Changed shared geometry is checked for post-edit compatibility; the old
shared curve, tangent and curvature values are not frozen.

`constrained_uv.PreparedUVEdits(model, baseline_result, validator, kernel)` is an
integration wrapper. The caller supplies a repaired baseline and a per-value
validator; the wrapper does not obtain an acceptable result from the legacy
constructor. Default preparation requires a supplied checked attachments-v2
proof. The explicit `differential_only=True` test mode permits an unproved
baseline but returns a disabled capability catalog. It cannot grant acceptance.
No baseline attachment proof is copied to an edit result. Only the supplied
validator can return fresh attachment evidence for the edited value.

## Actual selected regions

- Each U-row handle uses a compact degree-9 V cardinal on the two adjacent row
  intervals (the original source end is the outside endpoint for the first or
  last row). Its transverse profile is the degree-10 bump
  `1024 q^5 (1-q)^5`, with q derived from cumulative native section widths.
  It affects all four middle bands, including their common traces, and has zero
  derivatives through order four at the two outer V profiles.
- Each V-profile handle uses the degree-10 V bump supported between the first
  and last U rows. Both neighboring middle/collar strips receive the same
  changed trace through quintic Hermite endpoint lifts. Cross-displacement
  derivatives through order two are zero at those incident boundaries.
- Profile 0 and 4 values are mirror-coupled; profile 1 and 3 are mirror-coupled;
  profile 2 is self-coupled. A paired response is applied exactly once. All U-row
  fields are mirror-coupled across the source-derived transverse network.
- Direction is the captured upper-plane normal. Scalar units are model units.
  Bounds are finite source-scale bounds, not a promise that every combination
  is regular. Every requested value still goes through the supplied validator.
- The first/last source corner repair charts, including unknown
  `upper_hard_corner`, `fan_prototype`, `lower_chart`, and `lower_bridge` records, have no response and pass
  through unchanged. No finite source attachment interval is relaxed.

Preparation verifies that compact profile support lies entirely within retained
body strips and rejects a corner layout that overlaps that support. Unsupported
rational denominators, layouts, degree growth, and control-point budgets fail
closed. In particular, these strip lifts require a fixed U-only denominator.

## Regenerated row layout and repaired guides

`baseline_result.network.native_v` and `row_count` define the current selectable
row layout. Handle IDs, anchors, support endpoints, and basis identity all use
that layout. For the lower repair supported on V=.9..1, the historical full row
at .95 is removed: eight complete rows end at .9, yielding thirteen row/profile
body handles plus four mirrored outer-profile shoulder descriptors (17 total). The original parameter map, including the hidden .95 interpolation knot,
is retained in `network.parameter_map` unchanged. No tmap refitting occurs.

Every selected U row must still cover both complete native-U collars plus all
four middle bands. A row that enters a replaced chart and leaves missing guide
pieces is rejected rather than silently shortened. The generated rows are exact
traces of the edited surfaces.

Repaired inspection guides carry `binding` with schema
`smartskin.guide-isocurve.v1`, `surface_index`, `varying_axis`, and
`constant_parameter`. `surface_isocurve` regenerates the entire rational trace
independently. A copied guide must match it and remain bound to unchanged chart
geometry. Every repaired chart requires complete boundary coverage; missing,
unbound, partial, stale, or off-surface guides fail closed. These inspection
guides do not create extra editable handles.

An upper hard-corner chart's collapsed bottom is a point, not a degenerate curve
guide. The only allowed omission is recorded in
`network.collapsed_boundary_bindings` as surface_index, edge=bottom, corner_id.
The checker verifies a constant rational point, the chart's approved corner ID,
independently captured original upper/side endpoint witnesses, and the exact
current attachment-proof exclusion. Three noncollapsed edge guides plus that
verified point complete the chart. No lower or other corner receives this rule.

## Transported common jets

For shared displacement curve C(v), left cross displacement D(v), and left
second cross displacement A(v), the neighbor receives

    R_u  = alpha D + beta C_v
    R_uu = alpha^2 A + 2 alpha beta D_v + beta^2 C_vv
           + gamma D + delta C_v

`transported_jets` implements these polynomial identities, including variable
speed, shear and acceleration coefficients. `coupled_seam_displacements` lifts
the common and transported two-jets to both incident patches with zero opposite
edge two-jets. Endpoint factors vanish through order four: shear makes C_vv
enter the transported second cross jet, so a second derivative along an original
source edge can involve C_vvvv. Merely preserving the endpoint position and first
two derivatives is insufficient.

The actual bounded profile support starts after the first-row transport fade and
ends before the last-row source repair. Its last-collar artificial seam has zero
displacement two-jets. Middle-band row responses use the native transverse speed
ratios. The dedicated synthetic tests exercise nonzero variable shear explicitly;
they do not pretend that the actual central-band specialization has shear.

## Fixed coefficient cache and proof contract

Each independent handle stores a homogeneous coefficient response with zero
weight component. Degree elevation is algebraic and nonnegative in Bernstein
form. The new numerator is the old numerator plus the unchanged denominator
times the polynomial displacement. Degrees are capped at 40, individual strips
at 16,384 control points, and the complete skin at 65,536 control points.
Preparation checks whole source-edge response coefficient rows, rather than only
sampling their points. Three zero outer rows preserve all source partials of
order at most two; the denominators remain unchanged. Source records are hashed
and checked for changes on every evaluation.

Catalog/request schema remains `smartskin.uv-handles.v1`. Every handle contains
`mirror_handle_id` (reciprocal or self). The catalog binds fixed
`shared_tolerances`. Results include:

- exact `edit_request` echo
- `handle_positions` for every handle, evaluated on the resulting surfaces
- exact `handle_positions_request` echo
- `edit_proof.schema = smartskin.edit-proof.v2`
- checked `source_2jets_unchanged`
- post-edit `shared_2jets_compatible`
- `shared_residuals` and `shared_tolerances`, each containing position,
  normal_angle_degrees, and shape_operator
- fresh geometric `symmetry_checked`, `symmetry_compatible`, `symmetry_residual`,
  and catalog-bound `symmetry_tolerance`

Every edited result separately checks geometric mirror symmetry. The mirror
plane comes from the captured transverse direction and the outer section
midpoint. Every middle, collar, hard-corner, and fan chart must have a matching
geometric partner. Middle-band U is reversed; opposite-side corner/body charts
use their declared corresponding parameters. The validator computes a
whole-surface positional upper bound from reflected rational control points and
positive B-spline basis weights. Proportional homogeneous weight rescaling is
accepted; nonproportional weights add a conservative total-variation bound.
Unknown charts, missing partners, or mismatched parameter bases fail closed.
Equal paired scalar values alone never establish symmetry. The symmetry
threshold is fixed at preparation and no greater than source position tolerance.
This coefficient bound can conservatively reject different representations of
the same surface; it never substitutes sparse visual similarity for proof.

A handle position includes displacement induced by other intersecting/coupled
handles. It must not be reconstructed in the UI from only its own scalar.
Displayed guides are extracted as exact traces of the edited tensors.

Full source/shared finite-boundary evidence, outward orientation, regularity and
native transaction checks remain independent mandatory gates. A valid affine
response, catalog declaration, source-preservation proof, or good synthetic test
does not replace those gates.

## Tests

    python -B -m unittest discover -s tests/python -p test_constrained_uv.py -v

The focused tests cover a moving shared curve on two patches, nontrivial variable
transport, immutable outer two-jets, axis-swapped U/V seam edits, the need for
order-four endpoint zeros, actual source-derived profile and row responses,
mirror coupling, unchanged source records and jets, exact output guide traces,
strict requests/cancellation, and refusal to enable an unproved baseline.

These are numerical and algebraic tests, not Rhino GUI or openNURBS readback.
They neither repair nor certify the source-side corner attachments.

## Endpoint shoulder controls and final callback contract

Outer profiles 0 and 4 also expose mirrored Upper shoulder lift and Lower
shoulder lift choices through the existing picker. Supports are the actual
source endpoint to first full row, and last full row to source endpoint. Each
compact factor vanishes through order four. The last collar, generated lower
bridge, and adjacent middle band move together; first-corner/fan charts remain
unchanged. Every affected bound guide is regenerated. The fixed end portions of
the body mode are an implementation support choice, not source constraints.

Every independent mode now derives its own slider range from sampled affine
Jacobian response with a 50% projection margin. This is not a global regularity
certificate. Individual ranges do not certify their Cartesian product: every
value vector must pass fresh whole-model checks, and rejected combinations
restore the last valid preview. Equal mirror values are insufficient on their own.

The optional constructor keyword validator_receives_result=True supplies the
validator a candidate containing current surfaces, freshly regenerated guides,
network, request echo, guide coverage and handle positions. The legacy surface-
list callback remains the default. Fresh attachment proof may be returned in a
complete result or a flat report. A numerically ready edited result is explicitly
native_screen_pending with experimental_commit_allowed=False. Only the preview
layer's source/request/geometry-bound native-owner receipt may clear that gate.

Guide coverage is separate from exported curves. Additional coincident_bindings
verify the same whole rational guide under degree/knot/gauge changes. Certified
native-source and retained-body boundary_roles may account for existing source
or row edges without exporting duplicate curves; new_shared_2jet may never use
that exemption. Explicit numeric-only research without owner proof keeps role
coverage unchecked and the edit capability disabled.
