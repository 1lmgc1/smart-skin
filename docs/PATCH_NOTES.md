# P06 one-button live result settings

Version: `0.0.11-p06`.
Baseline: P05 commit
`59c41213482702b2ed212bfcc0c237937a176aa4`.

## Objective

Replace the temporary four-command test toolbar with the intended product
interaction: one Smart Skin button, one selection/routing pass, one settings
window with a live viewport result, then ordinary Rhino confirmation.

P06 changes the interaction layer around the existing bounded constructors. It
does not add a new surface strategy, automatic hole discovery, joining or
quality scoring.

## Product flow

1. Click the single `Smart Skin` toolbar button.
2. Select supported curves or Brep edge sub-objects and finish selection.
3. Inspect and tune one disposable cyan result in the modeless settings window.
4. Press Enter, Space or right-click to add exactly one Brep. Press Esc or close
   the window to add nothing.

There are no additional Accept/Cancel buttons or command-line options.

## Effective controls

The contextual Patch route exposes only values sent to Rhino's native
`Brep.CreatePatch` overload:

- presets: Balanced (8×8, 1× sampling, flexibility 1), Stiff (flexibility
  0.1), Flexible (flexibility 10) and Detailed (12×12, 0.5× sampling);
- U and V spans, bounded to 2–16;
- sample-spacing scale, bounded to 0.25–4× the automatic P05 spacing;
- flexibility, bounded to 0.001–100;
- adjacent-face tangency request and automatic boundary trim.

Preview opacity and preview wires affect display only. Direct edits become the
Custom preset. Changes are coalesced for 250 ms before rebuilding; confirmation
flushes a pending rebuild first. If a rebuild fails, the old preview is removed
and confirmation remains blocked until a valid result exists.

PlanarSrf, EdgeSrf and Loft use the same result window, but Patch-only controls
are disabled because those values do not affect their native constructors.

## Toolbar contract

- One visible group, one toolbar and one product button.
- The released RUI, plug-in, group, group-item, toolbar, Build macro, Build
  button and Build bitmap GUIDs remain fixed.
- The product button runs exactly `! _SmartSurfaceBuild`, is labelled
  `Smart Skin`, and names `SmartSurfaceBuild` in its tooltip.
- Plan, Preflight and Version remain supported command-line diagnostics. Their
  released macro and bitmap identities remain in the RUI but are not referenced
  by visible toolbar buttons.
- No Rhino menu, right-click macro, layout reset or shared UI deletion is added.

## Safety invariants

- Source objects are never changed, repaired, transformed, joined or deleted.
- At most one disposable candidate is retained; replacing it disposes the old
  candidate.
- The active document count must remain unchanged through selection, building,
  settings changes and preview.
- Only confirmation with a current valid candidate can add one native Brep.
- Esc, window close, a failed rebuild or a blocked route adds nothing.

## Acceptance

- `STATICALLY CHECKED`: compile against the Rhino 8.18 RhinoCommon, Rhino.UI and
  Eto APIs with warnings treated as errors.
- GitHub Actions must restore, build, run the full Core regression, validate the
  one-button RUI, package `0.0.11-p06` and pass installer lifecycle automation.
- `NOT VERIFIED` until one Rhino 8.18 field check proves the single button,
  visible settings window, live Patch change, native confirmation and exact
  object-count invariant.

## Intentionally untouched

Measured gap/tangent-angle quality, candidate ranking, G2 claims, automatic
opening detection, multi-hole batching, joining and source repair remain later
geometry objectives.
