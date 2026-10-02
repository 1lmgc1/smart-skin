# Smart Skin handoff — P07 measured surface matching

## Authority and baseline

- GitHub is authoritative for source, CI and artifacts.
- Google Drive is the durable journal only.
- P06 baseline: `a33f0e92bfa14ad0cbe2a7a38e7b180545212d40`.
- P06 one-button/live-window interaction is `VERIFIED` by the user.
- P06 contextual `CreatePatch` geometry is rejected: it is not a continuity
  solution and missed the six-edge target by up to about `0.215 mm` at
  `0.01 mm` model tolerance.
- Private `.3dm` files and screenshots stay out of the public repository.

## P07 objective

P07 `0.0.12-p07` keeps the accepted interaction and introduces a real
Rhino 8.21 MatchSrf path for the five-to-eight-edge contextual hole:

- Position/G0, Tangency/G1 and Curvature/G2;
- Refine with explicit measured acceptance;
- native Average surfaces for all-natural target-edge loops, with a distinct
  context preview, all-seam join proof and exact source-replacement accounting;
- a `MATCH_SRF` route token and disposable Join proof for Match-only as well as
  Average mode;
- bounded direction retries, context-complexity gates and trim-parameter
  near-end/span-scaled continuity sampling;
- one current candidate, one command undo, no stale preview commit.

The contextual route has no `CreatePatch` fallback.

## Completion path

1. Compile against exact RhinoCommon `8.21.25188.17001` with warnings as errors.
2. Run Core regression and native RUI validation.
3. Publish one fast-forward P07 commit to `main`.
4. Require green `build-p07` on that exact commit and inspect artifact identity.
5. Run only the focused Rhino test in `docs/FIELD_TEST.md`.
6. Review evidence and journal the result before expanding geometry scope.

## Queue after P07 evidence

1. If the real six-edge fixture passes G2 Match-only and Rhino Join, close the
   first single-hole continuity milestone.
2. Add automatic opening discovery from one selected shell.
3. Decide a separate, honest strategy for averaging arbitrary trimmed targets;
   native MatchSrf Average does not support them.
4. Add a small ranked seed/cap-shape set only where MatchSrf needs a better
   interior shape; do not weaken verified boundary criteria.
5. Consider multi-hole batching after the single-hole path is reliable.
