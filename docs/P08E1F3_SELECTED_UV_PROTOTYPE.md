# Selected U/V handle prototype

Status: experimental field candidate, capability-gated. **Native Rhino API/UI execution is NOT VERIFIED.**

This document describes the selected U/V controller and its integration contract.
The coupled edit basis now exists separately, and the lower narrow repair has
passed independent numerical attachment, shared-seam and regularity checks. Main
integration supplies a numerical-ready result and fresh attachment/atlas evidence.
Those numerical results alone do not enable READY or authorize document additions:
the current Rhino session must additionally issue and verify its own bounded
native-owner separation receipt.
The user chose hard upper corners on 2026-10-06:
curvature may rise as the exact approved corner point is approached. This does
not permit a finite band of weakened attachment. No package or feature-readiness
claim follows from these tests.

## Interaction contract

- Keep the existing single toolbar button and one modeless live window.
- Select one U row or V profile from a list; its exact preview curve pieces are
  highlighted. U/V means the parameter varying along that guide. Counts come from
  the evaluated network/catalog, not a fixed nine-row assumption. The current
  lower-repaired layout declares eight complete U rows and five V profiles.
- Select a handle belonging to that guide. A capable engine supplies its anchor,
  movement direction, range and units. The highlighted handle belongs to the
  currently displayed geometry, not an unbuilt slider request.
- Current catalog labels are U N normal lift and V N normal lift. The two outer
  V profiles additionally offer Upper shoulder lift and Lower shoulder lift in
  the same handle picker. The eight-row layout has 17 descriptors: eight row
  lifts, five profile body lifts, and four shoulder descriptors. Mirror coupling
  produces 13 independent scalar modes. These counts describe this catalog and
  are not hardcoded into the UI.
- The slider is a selected normal displacement in model units, not a curvature
  tolerance or a global shoulder factor. Shoulder support/ranges come from the
  geometry. An unsupported meaningful range is displayed as a locked handle;
  the UI does not widen the range or relax attachment checks.
- The slider atomically changes that handle and its mirrored partner to equal
  values. On-axis handles reference themselves. Other handle values are retained;
  intersecting U/V fields may still move their evaluated positions. There is no
  asymmetric toggle and no fallback mapping from selected handles to global h.
- New shared guide geometry may move. Its post-edit G0/G1/G2 attachment must remain
  compatible across adjacent patches; it is not required to equal the old shared
  trace. Original source geometry and required source attachments remain fixed.
- Preserve debounce, immutable request snapshots, obsolete-revision cancellation,
  and last-valid preview restoration. A failed edit restores all last-valid handle
  values; accepting the restored result requires a new native confirmation.
- Enter, Space and right-click are still native confirmation inputs. Esc/window
  close cancel. No visible Accept/Cancel buttons and no temporary document objects.
- Viewport dragging is outside this first prototype. The lists and highlighted
  geometry are its only selection/manipulation interface.

## Current integration gate

The UI starts with “EXPERIMENTAL FIELD CANDIDATE: PREPARING AND CHECKING,” and
editing/acceptance stay disabled until all required checks pass. It changes to experimental
native-screened preview only after the actual current-session numerical,
projected-atlas, conversion and native-owner screening stages all pass. This
conditional runtime state is not a release claim or native-host test result.
The old experimental PARTIAL result cannot authorize acceptance. Both baseline
acceptance and every edited result require the new full finite-boundary evidence.
Preserving an incorrect baseline is insufficient. The acceptance gate is checked
before every native addition and again after the batch. The commit helper has no
missing-proof or experimental-PARTIAL fallback, including direct helper calls.
When an edit request is supplied, its exact echo and both source/shared two-jet
invariants are rechecked at those same transaction checkpoints.
Geometry disposition is independently required: valid and geometry_valid must be
true, fatal false, disposition exactly native_screen_pending, and
experimental_commit_allowed false. This one explicit pending state permits
conversion only; it is not permission to commit. A separate current receipt
completes the gate without mutating the kernel's flags. Positive attachment flags
cannot override a numerical failure or any other blocked/inspection-only state.
Current controller values and request revision must still match the displayed
token at every checkpoint. A new slider event during a native Add callback,
including a repeated scalar value, triggers rollback before the next addition.

The controller does not invent kernel proof fields or trust result-side native
pass booleans. A stored-control rotation/conditioning failure remains an explicit
known limitation: it blocks the result with unchanged tolerances and original
sources, rather than applying an unverified rounding repair.

## Numerical-ready to native-screened pipeline

1. Evaluate the exact immutable baseline/edit request and require its numerical
   readiness, attachment-v2 proof and local regularity/orientation/guide gates.
2. Call atlas_separation.verify_atlas_separation(result, capture.model, request).
   It recomputes current geometry/source/request bindings; declared hashes alone
   are insufficient. Projected-atlas cap-cap screening must be checked and passed.
3. Create a session-owned copied-original-owner context through
   native_owner_separation.create_owner_context, then convert exact homogeneous
   descriptors to disposable Rhino Breps and guides. Raw homogeneous control
   coefficients and native control-point readback are preserved; they are not
   round-tripped through Euclidean XYZ times weight.
   After that readback, the converter issues an in-process binding for the exact
   ordered surface/guide/request descriptors and exact native object identities.
   It stores bounded native fingerprints for both Breps and guides. A result-side
   flag cannot issue this binding; a same-count stale native list is rejected.
4. Call screen_native_owners on the actual converted Breps, copied owner context,
   checked native_contact_ledger, and exact current request. Verify the returned
   in-process SeparationReceipt before state completion or READY.
5. Hold that receipt separately from all result dictionaries. Before each native
   Add and after the batch, reverify its exact native-geometry, copied-source,
   request, ledger and tolerance binding, plus the current atlas evidence.
   The converter binding and both Brep/guide fingerprints are also rechecked:
   replacement or mutation before screening or during additions revokes authority
   and rolls back only this transaction's new IDs, without rebuilding geometry.

Every new request, cancellation, failed evaluation or failed verification
invalidates the prior receipt and its held conversion binding. Merely restoring the old numeric values does not
revive it. A new confirmation of a restored preview first regenerates exact native
copies and obtains a fresh receipt under the cached budget; failure keeps
acceptance blocked. Closing the session disposes the copied-owner context and
revokes the receipt. Original document geometry is never used as temporary output.

Both separation stages are bounded numerical screens. They do not certify global
injectivity or the absence of all unsampled overlaps. The native screen report's
finite interior-witness coverage limitation remains applicable.

## Bounded kernel contract

A prepared edit model supplies handle_edit_catalog() and evaluate_edit(request,
cancelled=callback). The catalog contains:

- schema: smartskin.uv-handles.v1
- enabled: true only when the actual constrained basis exists
- basis_id: stable identity for that prepared numerical basis
- preserves_attachment_order: 2
- shared_tolerances: fixed position, normal_angle_degrees and shape_operator limits
- symmetry_tolerance: fixed finite geometric mirror-error limit
- handles: at most 128 generated descriptors

Each descriptor has id, guide_id, varying_axis (u/v), label, minimum, maximum,
neutral, units, anchor, position, direction and mirror_handle_id, plus optional
locked_reason. Mirror links must be reciprocal, or self-referential on-axis;
paired ranges, neutral values, units and direction labels must match. The evaluator
applies each canonical mirrored response once, not once per equal alias value.
Coordinates come from the prepared model. Existing guide identities are row:N and
profile:N. Body handle IDs append :lift; outer-profile shoulder IDs append :upper
or :lower. Catalog row_count and native_v describe the actual selectable rows;
neither the retained guide count nor the number of curve pieces is assumed from
the old layout. No private fixture identities are required.

The immutable request payload contains schema, basis_id, revision, and values:
a mapping of every generated handle ID to its scalar value. A request has no h
field. A failed evaluate_edit call must not be retried through evaluate(global_h).

Every edit result must echo the exact edit_request and include edit_proof with
schema smartskin.edit-proof.v2, checked, source_2jets_unchanged and
shared_2jets_compatible all true. shared_residuals and shared_tolerances each
contain position, normal_angle_degrees and shape_operator. All residuals must be
finite, nonnegative and within their corresponding limits. Result limits must
equal the prepared catalog limits; a live edit cannot loosen seam acceptance.
These checks supplement normal geometry/regularity gates. A catalog declaration
or echoed request alone is not mathematical evidence.

Mirror-coupled mode additionally requires symmetry_checked and symmetry_compatible
to be true, with a finite nonnegative symmetry_residual no greater than the fixed
symmetry_tolerance. This must be fresh geometric evidence for the evaluated result;
equal scalar pair values do not prove geometric symmetry. The UI rejects missing
evidence, failed/nonfinite residuals and a changed prepared symmetry threshold.

Results also supply handle_positions, mapping every handle ID to its actual
evaluated xyz position, plus handle_positions_request equal to the exact request.
Missing, incomplete, nonfinite or stale positions block the result. The UI stores
positions only with the accepted displayed preview and never estimates them as
the initial point plus that handle's scalar alone. Crossing-field and mirrored
motion therefore remain visible. Pending edits retain the previous positions;
restoration restores the corresponding values. The commit helper rechecks this
displayed state, mirrored equality and fixed catalog tolerances before each add.

Every acceptable baseline or edited result must separately include
attachment_proof with:

- schema: smartskin.attachments.v2
- checked: true
- source_full_finite_boundary_pass: true
- shared_full_finite_boundary_pass: true
- corner_policy: hard_upper_source_corners
- excluded_intervals: an empty list
- excluded_points: an explicit list of zero, one or both approved source vertices

An excluded point must contain exactly its captured binding: corner_id
(upper:side0 or upper:side1), role (upper_source_corner), side_role, upper_source_key,
upper_native_parameter, side_source_key and side_native_parameter. The allowlist
is derived independently from capture.model.source_boundaries. The upper-chain
start must meet the side0 traversal start; the upper-chain end must meet the side1
traversal start. Original native endpoint domains and captured endpoint witnesses
are retained even for reversed traversal. No private fixture IDs are embedded.

The only approved locations are those two upper-chain/source-side intersections.
An interior upper-chain endpoint, lower endpoint, unrelated internal junction or
generic seam endpoint is not an approved corner. A seam genuinely incident to
the same approved physical source vertex may use that vertex's identity only;
the kernel must establish that incidence. The schema grants no independent seam
or internal-junction exception. Result-declared allowlists and unexpected proof
fields are rejected rather than treated as authorization.

Any positive-width excluded interval blocks acceptance, however small. Growing
curvature approaching the approved hard point does not remove the requirement
for correct attachment on every remaining finite interval. Only the main fresh
validator may emit the complete attachment proof; source-role bindings or passing
component repairs alone cannot enable editing or commit.

## Runtime budget and bounded additions

- A 250 ms timer debounces handle changes. Cold preparation has a 180-second
  total cooperative budget; cached edits and restored-preview screening have
  60 seconds. Numerical checks, atlas verification, copied-owner setup, native
  conversion and owner screening share the applicable outer budget. Imports,
  dependency resolution, input capture and the final commit are outside it.
- Supported checkpoints pump Rhino UI events and observe close/Esc, timeout and
  obsolete revisions. A single running native/numerical call is not forcibly
  interrupted, so these are not hard wall-clock cutoffs. The UI explicitly says
  “Esc between supported operations; one native call cannot be force-interrupted.”
  Visible stage labels distinguish preparation, numerical checks, owner copying,
  conversion and native owner screening. Native cold timing
  for the newly integrated complete result is still NOT VERIFIED.
- A first-build timeout produces no accepted preview and no automatic retry.
  The user must cancel/re-run unless a later requested operation can use an
  already prepared model. Successful prior preview geometry and values are kept
  when a subsequent edit fails.
- Native conversion permits at most 128 patches and 128 exact curve descriptors,
  degree at most 64, at most 16,384 control points per patch and 4,096 per guide.
  It checks cancellation between objects and periodically between surface rows.
  The adapter has no additional aggregate control-point cap; the numerical
  constructor must retain its own aggregate budget.
- The commit helper independently bounds and snapshots at most 128 skins plus
  128 guides before any additions. Oversized or infinite iterables are rejected,
  and a native Add callback cannot expand the captured input lists. Thus the
  direct helper and the UI path permit at most 256 additions per transaction.
- Native-owner screening independently retains its 15-second per-screen budget,
  32-patch/16-owner/512-pair limits and aggregate native geometry/call budgets.
  It also receives the outer cancellation/deadline callback. The stricter screen
  limits can reject a result that fits the conversion count limit; no stage is
  skipped to make a timeout or incomplete pair pass.
- Commit cancellation uses only the current close/Esc/disposed state, never the
  expired preview deadline. It is checked before commit, before every Add and
  after the batch. Cancellation or proof failure rolls back only this operation's
  new IDs; source geometry stays unchanged. Individual Add calls are not forcibly
  interrupted, and no wall-clock commit guarantee or native Esc responsiveness
  has been verified in licensed Rhino.

## Verification and limits

**VERIFIED:** 47 controller/dispatch/acceptance/synthetic tests, 46
preview/transaction/loader tests and 22 two-stage pipeline/import tests pass. The pipeline
tests use actual receipt issuance/binding with a mock native adapter and a mock
atlas verifier; they are not native Rhino or geometric atlas certification.
Tests cover independent handle
values, immutable snapshots, no global fallback, stale cancellation, proof
mismatches, restoration, old-PARTIAL rejection and pre-add transaction blocking.
Wrong source points/roles, internal junctions, positive-width bands, forged
result-side allowlists and missing proofs are rejected before any additions.
Attachment/edit proof invalidation during a transaction rolls back only its own
new IDs. Role/endpoint mapping also passed a targeted check against replay-
validated synthetic native-boundary evidence with reversed traversal.
Additional cases cover atomic mirror updates, asymmetric-request rejection,
post-edit shared compatibility rather than frozen shared traces, unchanged
thresholds, exact-request positions, cross-handle motion and stale-position
rejection. The native adapter honors explicit orientation_reversed metadata with
Brep.Flip while preserving parameter coordinates; this has a mock regression test.
Final helper tests reject invalid/fatal/no-commit dispositions even with true
attachment flags, roll back changed or repeated handle requests during native Add
callbacks, and reject missing/failed/relaxed geometric symmetry evidence.
Additional direct-helper tests reject oversized/infinite inputs, freeze list
membership against Add callbacks, and roll back only new IDs when cancellation
arrives during either the first or final addition.
Two-stage cases reject missing/stale atlas evidence, missing/result-forged native
receipts, failed/cancelled screens, changed native geometry and reused receipts
after restoration. Receipts are rechecked before each Add and after the batch.
Additional cases reject same-count native replacement, changed initial numeric
descriptors, guide mutation before screening/during Add, and result-forged
conversion flags. Fingerprint memory is bounded. Import fallbacks occur only when
the exact versioned module is absent; transitive dependency failures propagate.

The displayed curvature maximum is explicitly the ordinary/interior-grid value.
A separate logarithmic hard-corner-approach metric and growth note are shown when
present. The ordinary-grid number is not presented as a global curvature bound.

The synthetic geometry test changes one interior degree-(6,6) Bernstein control
point using B(3,6,u) B(3,6,v). It produces a nonzero interior displacement while
all four fixed-boundary derivatives through order two remain exactly zero.
Adjacent synthetic patches retain their shared boundary two-jets. This proves
only that this simple interior bubble is boundary-safe. It does not solve an
arbitrary fan or demonstrate movement of a guide lying on a shared patch trace.
An additional two-patch graph test restricts a single global polynomial to
adjacent charts: their shared trace moves with identical post-edit two-jets,
while all exterior boundary two-jets remain zero. This is synthetic contract
evidence, not verification of the native-fan implementation.

**STATICALLY CHECKED:** Python 3.9 syntax; guide grouping and conduit/list/slider
wiring. Rhino's official display-conduit picking example confirms preview geometry
can be represented independently of document objects:
https://developer.rhino3d.com/en/samples/rhinocommon/pick-points/
No viewport-picking implementation is claimed here.

**NOT VERIFIED:** native Rhino/Eto rendering or input behavior; the complete
integrated repaired result and all requested handle combinations; native cold
runtime and Esc responsiveness; licensed Rhino acceptance. Separate numerical
tests of the coupled basis/lower repair are not a full native UI or release pass.

Intentionally unchanged: source extraction, kernel mathematics, installer,
publication pipeline, toolbar identities, native document rollback discipline.
