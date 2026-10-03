# P07F1 verification contract

## Limits of evidence

The repo's hosted Windows runner compiles the actual Rhino-facing assembly, runs all Core unit tests, validates the unchanged RUI, packages the result and tests the installer against isolated paths/registry keys. It does not contain a licensed Rhino runtime. Eight native regression fixtures are compiled into the plug-in and run automatically once before its first match in a Rhino process, on the command/UI path, in disposable in-memory geometry. No native success is inferred from Core tests or compilation.

## Native cases

1. One circular trimmed closed output edge, identical planar target: G2 pass expected.
2. Four-edge rectangular output: G2 pass expected.
3. Same rectangle with one edge split into two: same-face endpoint mapping and G2 pass expected.
4. Translated boundary gap above the old 2x search cutoff: numeric available gap, BOUNDARY_GAP_OUT_OF_TOLERANCE, no acceptance.
5. Annulus: reject the extra boundary component.
6. Bicubic cap with unchanged boundary positions and tilted normals: reject G1.
7. Quintic cap with first boundary derivative preserved and nonzero second derivative: reject planar G2.
8. Average eligibility: trimmed circular targets denied, untrimmed rectangular targets remain eligible.

Failure of any fixture reports P07F1_VALIDATOR_SELFTEST_FAILED and blocks the matching route. These fixtures exercise the verifier only, not arbitrary hole construction, the complete Average replacement path, UI decisions or Undo. The one private field test covers the original hole and actual commit/Join behavior.

## Invariants

One closed topological naked cycle; connected manifold cap; finite valid measurements; original trim/face mapping; full boundary distance plus bidirectional bounded sampling. Output may have multiple edges, but the source edge passed to native MatchSrf must still satisfy its original untrimmed seed contract. Tolerances are never inflated to make a candidate pass. All selected target edges must be covered, and the original disposable-context Join proof must pass before acceptance. Neither a G2 request nor a returned Brep is a G2 verification.

No private inputs are included. Earlier action-code names remain P07_* while build identity and new diagnostic lines are P07F1. Native operations cannot be force-aborted; cancellation is checked between supported calls and sampling operations.
