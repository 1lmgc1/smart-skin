# P08D.1 — structured transition: construction contract

Status: DESIGN, not a new constructor, RHP, or accepted surface. Base: P08C.4 at 5bb29abbb6d6aa834720ebedeca27e4b5b04b850. Production, previous solvers and the field checker remain unchanged. No new Rhino/CI execution is claimed by this document.

## Evidence and purpose

The last field run established native connectivity for the prior candidate, while the user's subsequent shaded and reflection views rejected its shape. Keep this candidate as a connectivity regression, not as accepted form. The old field checker measures shared joined edges against source edges; it does not independently measure both surface-trim images. That limitation must remain explicit.

Earlier constructors already have a center and lateral ribbons. Repeating those words or splitting the existing tensor does not create a new method. Exact splitting changes representation, not geometry. An offline design probe on the archived net confirms this and must be retained as a negative control. Its private numbers, model, coordinates and identifiers belong only in the private recovery package.

## The actual architectural change

Replace the frozen complete central band and independently modified edge jets with a jointly solved profile-guided patch complex. Retain the prescribed central profile and source feature curves; let internal seam positions, compatible tangent-plane fields, transverse speeds and the surrounding center move within explicit limits. The previous whole-band lock becomes an optional designer lock, not the default inferred from an object axis.

Do not assume three faces are intrinsically better than one. Three strips are the first bounded topology candidate; count is not an acceptance criterion. The benefit must come from new guide/jet variables and parameter maps. A globally smooth patch complex still cannot satisfy incompatible fixed corner tangent-plane requirements by subdividing them.

## Input contract

BoundaryChain retains each source object/face/trim/edge and its parameter interval, reversal, role, junctions and source hash. Logical sides can contain more than one source segment. A single fitted curve must not replace a compound side without an explicit approximation policy.

BoundaryPolicy is one of EXACT_SOURCE, CAP_EDGE_RELIEF, or PARENT_HEALING. Exact source is preferred. Relief is explicit, applies only to the candidate and has a cumulative positional budget checked against the original source, not the preceding iterate. Reuse the previously declared relief budget only when explicitly selected; never infer it from a successful Join. Parent healing is a separate previewed source-changing mode and is outside the first prototype. The document tolerance is never enlarged.

AxisFrame consists of a longitudinal direction, cross direction, orientation and scale with evidence and override. Axis direction is not a sufficient definition of the central profile. User-prescribed features override a statistical axis guess. Local U/V labels are not world directions.

## First topology candidate: three strips and two shared seams

Call the compound feature sides B0 and B1 and the curved lateral sides EL and ER. The first candidate consists of left transition PL, center PC and right transition PR. Shared seams JL and JR each run from B0 to B1, ending away from the original corner conflicts and retained compound junctions. Each lateral patch contains its own curved source side plus portions of B0/B1. PC retains the central source junctions on B0/B1; those junctions do not have to become internal cap seams.

The old ribbon interfaces may supply initial endpoint stations only. Do not freeze the old isocurves as the new seams. Each seam is a new guide curve with endpoints constrained to their allocated source intervals, endpoint order constraints, bounded width and a noncrossing interior corridor. Endpoints may slide on those intervals within explicit station limits. No seam may collapse, cross the profile, or create a sliver patch. A fifth-patch corner alternative is considered only after a measured rejection of this first layout, not as an automatic cure.

Splitting source sides at new seam endpoints can produce more external Brep edges than the number of original source segments. Verification is coverage of original intervals, not equality of edge counts. New shared seams are additional obligations.

## Shared seam fields, not sequential matching

A shared seam is one record containing C(s), a compatible oriented transverse direction field D(s), a second transverse derivative field E(s), and parameter-map data. Both adjacent patches consume the same record. It is not reconstructed independently and matched afterward.

For the first bounded prototype use affine, orientation-consistent patch maps from local transverse coordinate t to a common signed coordinate r: r=a*t+b. At the shared seam, impose S=C, S_t=a*D, S_tt=a^2*E, S_s=C', S_ts=a*D', and S_ss=C''. The widths/scales a must be included; equal local CV rows are not sufficient when patch widths differ. For nonlinear or s-dependent maps use the full first/second chain rule, including mixed terms; do not reuse the affine equations unchanged. These C2 construction constraints are sufficient locally only with consistent maps and regularity; native geometry is still independently checked.

C, D and E are optimization variables subject to compatibility and shape constraints, not inherited frozen coefficient functions. Parent attachment is expressed geometrically: a boundary curve, tangent plane/oriented normal and second fundamental form. Positive transverse speed and tangential shear can vary while preserving the geometric match. At every proposal, recompute the actual normal and shape operator. A field of desired normals alone is not guaranteed to be integrable into a surface.

## Corner transition law

Before constructing jets, compare both incident boundary tangents with the requested parent tangent plane. Mark incompatible endpoints explicitly. Keep the agreed active smooth intervals unless an explicit revised continuity map is shown. Their endpoint exceptions must occupy measured finite zones, not samples silently dropped from verification.

Within each end zone, interpolate a compatible tangent-plane rotation about the boundary tangent, constrained by the corner geometry and the active parent's conditions. Optimize zone width and rotation distribution jointly with the seam fields. Desired angle laws must be checked on the constructed surface; their smoothness is not a proof that the realized geometry is smooth. Do not prescribe an impossible terminal normal or solve a corner by an unnoticed derivative collapse.

## Section and silhouette control

Define a common ordered family of source correspondences and middle-profile stations. Longitudinal maps must preserve order, segment junctions and positive speed. Transport frames continuously; recompute all jets after changing maps. Source-required inflections are permitted. A blanket rule that every curvature or every section must be monotone is not valid.

The silhouette guide is an internal envelope/shape constraint distinct from the fixed outer feature boundary. Do not require an interior guide that contradicts source endpoints. Evaluate excursions in the axis frame and in fixed comparison directions. Parent-collision checks remain separate.

## Basis choice

Compare bounded degree/knot alternatives separately in both directions. A single quintic transverse polynomial with prescribed position, first and second derivative at both ends has no remaining coefficient freedom. New freedom must come from permitted geometric jet variables, an additional span, or a tested degree increase followed by a new solve. Degree elevation alone is a representation change. Preserve exact source curve complexity and internal junctions; reduce other complexity only under a measured error budget.

The first prototype tries the existing compatible longitudinal basis with transverse quintics, then a limited extra span or septic alternative where necessary. Shared geometric seam fields must survive different local degrees. Avoid copying an entire parent's global CV grid into a small repair.

## Acceptance: geometry before ranking

Hard gates: source integrity, cumulative boundary budget and junction retention, full intended external coverage, compatible internal seams, regularity/nondegeneracy, bounded displacement, no unapproved continuity downgrade, and collision checks. A good objective or a single joined Brep is insufficient.

Shape ranking must include spatial distribution and variation, not only reduced maximum curvature. Measure curve curvature and its change with respect to physical arc length, oriented normal rotation, and the full surface shape operator including oblique directions. Observe one-sided behavior at knots and seams. Compare at fixed physical section planes/directions in addition to isocurves, so a UV map change cannot improve the score merely by changing the inspected paths. Use identical before/after validation sites or independently controlled resampling and retain worst-case witnesses.

Total normal turning minus endpoint angular separation is a useful diagnostic, not a universal zero target: required curve/parent geometry may force a longer normal path. Similarly, less total curvature is not always the intended form. Penalize unrequested turn reversals, localized concentration and oscillation relative to the intended transition, without erasing required inflections. Do not label a sampled screen as a global fairness or self-intersection certificate. Numerical improvement remains subject to a same-view visual review.

## Native verifier changes required before field delivery

Run Join on copies for every new geometry revision. Identify all cap faces and classify every shared edge by face provenance as external cap/parent or internal cap/cap. Trace complete source-interval coverage, allowing chains and extra edge splits; reject missing pieces, ambiguous assignments and unaccounted seams.

Report separately: (1) pre-Join candidate-to-source boundary deviation; (2) joined shared edge to source deviation; (3) each joined trim lifted through its own face to 3D versus the shared edge; (4) the two lifted traces versus one another using correct correspondence. Measure surface normals/curvature on the appropriate face points, respecting reversals. A shared-edge distance near zero does not eliminate a pre-Join relief error.

For every internal seam also test geometric G1/G2 and orientation. A global solid is not required when unrelated source openings remain, but no required cap perimeter or internal seam may remain naked. Repeat native parent-intersection screening and a separate self-intersection check. Match all verdicts to the same immutable candidate ID/net hash.

## Planned parameter panel, not implemented UI

Geometry controls: axis/profile override; left/right transition widths with an explicit symmetry link; end-zone lengths and rotation bias; transverse tension; a bounded internal silhouette guide. Expert controls: degree/span budget and boundary policy. Incompatible parameter combinations must fail or retain the last verified candidate with a reason. Do not let a width slider silently enlarge relief or downgrade continuity. The existing one-window/Enter-Esc product interaction is unchanged by this design.

## Implementation and verification order

D1-A: patch graph, interval provenance, shared-seam data and exact-split negative control.
D1-B: joint guide/compatible-jet construction on source copies with profile-only central constraint.
D1-C: independent arc-length section-flow and full shape/operator screens; retained-candidate rollback.
D1-D: multi-face native verifier with separate trim-image metrics and immutable candidate identity.
Only after these layers pass is a new field package prepared. Production integration and sliders follow measured field review, not this design note.

Required regressions include: exact splitting must not claim form improvement; unequal patch widths with correct derivative scaling; intentional shared-seam normal/twist perturbations; compound interval omission/duplication; relief budget accumulation; improved peak with worse curvature variation; valid intended S-sections; short-span oscillations; reparameterization-only changes; normal flips and zero speed; cancellation and bounded retries; unchanged source geometry; and Join with more seam pieces than source segments.

## Present verification boundary

Source inspection and the offline archived-net design probe are complete. The joint three-patch constructor, new native verifier, redesigned user model, UI and whole-product release are NOT IMPLEMENTED by this documentation commit. No new CAD acceptance or native Join result is claimed. Developer probe scripts are not Rhino RunPythonScript files. Private geometry and screenshots must not be committed here.

Primary terminology references: https://docs.mcneel.com/rhino/8/help/en-us/commands/matchsrf.htm and https://help.autodesk.com/cloudhelp/2026/ENU/Alias-Tool-Palette-Reference/files/Surfaces-palette/Alias_Tool_Palette_Reference_Surfaces_palette_Surface_Tools_Common_Parameters_html.html
