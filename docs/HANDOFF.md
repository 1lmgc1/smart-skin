# Smart Skin handoff — P06 product interaction

## Authority and baseline

- GitHub is authoritative for code, CI and artifacts.
- Google Drive is a durable journal only.
- P05 baseline: `59c41213482702b2ed212bfcc0c237937a176aa4`.
- P05 real-case result is `VERIFIED` for object preservation and one valid
  added Brep. Measured G1/G2 quality is not claimed.
- Private models, screenshots and Rhino lock files must not enter the public
  repository.

## P06 objective

P06 `0.0.11-p06` implements the intended interaction around existing bounded
construction: one visible Smart Skin toolbar button, selection, one modeless
settings window with a live in-memory result, and Rhino-native confirmation.
The P04F1 diagnostic button piano is removed. Plan, Preflight and Version remain
available by command name.

## Invariants

- No extra Accept/Cancel controls.
- Enter, Space or right-click adds one current valid Brep; Esc/window close adds
  nothing.
- Source geometry and active object count remain unchanged until confirmation.
- A failed settings rebuild clears the preview and cannot commit a stale result.
- Patch settings are bounded and effective; irrelevant controls are disabled on
  PlanarSrf, EdgeSrf and Loft.

## Completion path

1. Static Rhino/Eto API compilation and RUI inspection.
2. One fast-forward P06 commit to `main`.
3. Green `build-p06` on the exact commit and artifact identity inspection.
4. One Rhino 8.18 field test from `docs/FIELD_TEST.md`.
5. Review that evidence before starting the next geometry patch.

## Queue after P06 evidence

1. Measure boundary gap and tangent-angle deviation; reject bad candidates.
2. Add a small candidate set for soft caps and rank fairness/continuity.
3. Add automatic opening discovery from a selected shell.
4. Consider multi-hole batching and optional joining only after the single-hole
   path is measured and reliable.
