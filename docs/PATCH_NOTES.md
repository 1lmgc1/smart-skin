# P07 measured surface matching

Version: `0.0.12-p07`.
Baseline: P06 commit `a33f0e92bfa14ad0cbe2a7a38e7b180545212d40`.
Minimum runtime: Rhino `8.21`.

## Why P07 exists

The P06 interaction is accepted, but its contextual result is rejected as
geometry: `Brep.CreatePatch` produced a visible edge deviation of about
`0.215 mm` in a document with `0.01 mm` absolute tolerance and did not prove
position, tangency or curvature continuity. P07 preserves the one-button/live
window interaction and replaces only that geometry route.

## Matched-cap route

For one closed loop of five to eight naked Brep edges, Smart Skin now:

1. preserves each selected edge's adjacent Brep face;
2. joins copies of the owning Breps into one disposable context shell;
3. builds one disposable untrimmed closed-edge seed cap;
4. calls Rhino 8.21 `Brep.CreateFromMatch` against the mapped Brep edges;
5. samples the result and blocks confirmation unless the selected continuity
   passes its tolerances;
6. joins the cap to a disposable copy of the context and proves that the cap
   boundary became one closed interior seam at document tolerance.

The builder tries both closed-edge match directions (and both target directions
for Average) within a fixed two/four-attempt bound. It keeps the first variant
that passes continuity and Join proof and reports both direction flags.
Owning context is capped by face, edge and surface-complexity budgets; after a
slow native return, the ten-second build budget prevents starting more variants.
Esc is observed before variants and again after each synchronous native return;
Rhino's MatchSrf call itself is not force-aborted on another thread.

There is no contextual `CreatePatch` fallback. A failed context join, ambiguous
edge map, failed native match or unavailable measurement is a diagnosed
`BLOCKED` result.

## Window controls

- `Position (G0)`, `Tangency (G1)` and `Curvature (G2)` map to native MatchSrf
  continuity modes.
- `Refine match` uses document distance/angle tolerances and the displayed
  curvature tolerance.
- `Average surfaces` asks Rhino to modify both sides. Rhino supports this only
  when every target is an untrimmed natural surface edge. Smart Skin checks
  that precondition explicitly instead of pretending a trimmed edge was
  averaged. Its orange copy preview is explicit; confirmation replaces the
  exact owning Breps only after every selected seam is proved interior in one
  joined result. The new joined object explicitly inherits the first source
  object's attributes; this policy is shown in the window and machine log.
- Isocurve direction exposes Automatic, Match target, Perpendicular and
  Preserve.
- Opacity and wires affect display only.

Default is G2 + Refine, Average off. Enter, Space and right-click confirm;
Esc/window close cancel. No Accept/Cancel buttons were added.

## Verification and commit

- G0: maximum cap/target boundary gap must be at or below document absolute
  tolerance.
- G1: G0 plus sampled adjacent-face normal angle at or below document angle
  tolerance.
- G2: G1 plus sampled cross-boundary radius-of-curvature deviation at or below
  the selected percent tolerance.
- G1/G2 sampling is bounded, includes near-end samples, scales with edge spans,
  and is reported as `sampled_max_*` with its exact sample count.
- Match-only adds one cap and leaves sources unchanged, but only after the
  disposable joined-context proof succeeds.
- Average adds one joined result and deletes only the recorded owning Breps;
  any partial delete is rolled back before reporting failure.

The supplied six-edge fixture contains trimmed target edges, so its first P07
field test covers G2 Match-only and exact Join compatibility. Native Average is
available for eligible all-natural edge loops; converting arbitrary trimmed
targets into averageable surfaces is not claimed by this patch.

Machine output uses `strategy=MATCH_SRF`, reports the selected boundary count as
`proved_target_edges` only after the complete loop passes Join proof, and
distinguishes `G0_VERIFIED`, `G1_SAMPLED_VERIFIED`,
`G2_SAMPLED_VERIFIED`, `NOT_VERIFIED` and `*_OUT_OF_TOLERANCE`; a request is
never logged as proof.

## Acceptance state

- Rhino 8.21 API compilation: `STATICALLY CHECKED` locally.
- GitHub `build-p07`, Core regression, toolbar validation, packaging and
  artifact identity: pending exact published commit.
- Rhino geometry behavior: `NOT VERIFIED` until the single test in
  `FIELD_TEST.md` returns.
