# P08E1F7 — requesting another edit after rejection

Version: `0.0.21-p08e1f7`. Parent: `0.0.20-p08e1f6`.

## Field evidence and diagnosis

The F6 field screenshot shows READY followed by a successful selected-U/V-mode commit, with original sources unchanged. The inspector is closed, so that screenshot does not identify the selected handle, its value, or an earlier rejected edit. Selected-U/V mode also names the all-neutral result; it does not prove a nonzero adjustment occurred.

A Session callback regression independently reproduces a recovery defect. In that regression test, normal slider events reach the kernel with the correct value; native field event propagation remains unknown. If an edit fails, F6 restores the previous shape and values and correctly revokes the native receipt, but then disables the slider. A smaller retry is ignored. Pressing Enter can rescreen and accept the restored shape, which does not provide a useful return to editing. The exact field sequence remains unknown.

## Bounded repair

- Separate eligibility to request another edit from eligibility to accept the displayed native geometry.
- Permit a retry from a previously validated restored numerical result and handle basis, after checking the existing captured source/tolerance state.
- Run the normal complete numerical, atlas, conversion and native-owner checks for the new request. Receipt validity remains mandatory for acceptance and viewport picking.
- Keep rejected geometry out of the document. No automatic acceptance, revived receipt, automatic rescreen loop or relaxed attachment gate is introduced.
- Log bounded handle IDs, requested/applied/restored values and revisions. The existing `SmartSkin.SelectedHandleRequest` object user text retains the exact final accepted request.
- Include guide/handle selection generation in the native confirmation token. If a consumed left pick propagates as `GetOption.Nothing`, that same input cycle cannot accept the result. A distinct later Enter/Space/right-click can still confirm it. A conditional regression demonstrates the old route; actual Rhino propagation is not established by the field screenshot.
- Initially select a catalogue-backed editable U/V guide. Mark structural inspection entries read-only and preserve a later deliberate selection of those entries.

The geometry constructor, handle ranges, movement directions and physical acceptance thresholds are unchanged. This is a UI recovery and observability correction, not a new baseline shape.

## Which shape does a handle affect?

The baseline central body uses a generated quintic section selected by its smoothness objective. That design is not uniquely forced by the source attachments. Current controls are compact local normal displacements, not unrestricted tangent-handle editing in every direction. A top U row does not necessarily affect the middle of the longitudinal profile. Select the central `V profile 3` to inspect that region; the eight structural seams remain read-only.

Until a new request finishes validation, the viewport retains the previous valid shape. A rejected value returns to the prior value and now allows another attempt. An unchanged view can therefore mean a pending computation, a rejected value or a guide whose local support does not cover the region being inspected; the new history distinguishes these cases.

## Verification boundary

Callback and state regressions cover normal value propagation, rejection followed by a smaller retry, source/tolerance changes, revoked-receipt acceptance, cancellation, stale revisions and pick-spanning versus later explicit confirmation. Exact-source Windows CI must verify all required suites and the unchanged installation lifecycle before delivery.

Native Rhino slider interaction and the user's intended shape correction remain **NOT VERIFIED** until the next field test. Existing upper-only hard-point scope, bounded native separation checks and fail-closed rotation-conditioning limitations remain. Deliver only the unchanged install ZIP from the successful exact-SHA Windows run.
