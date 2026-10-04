# FIELD01F1 - modeless close hardening and local crash-evidence collection

One objective: make the Field review-window lifecycle safe against callback errors, reentrant close requests and stale document access. No numerical solver, source fixture or production RHP update.

## Evidence and uncertainty

The field report says Rhino displayed the FIELD01 modeless window and later crashed after it was closed. The supplied screenshot reaches FIELD_READY. No new Field session TXT, exception stack or native crash dump was supplied with that screenshot. The exact crashing instruction is therefore NOT VERIFIED. The production P07F2 PASS line is not evidence about Field01 close stability.

Inspection of the released FIELD01 shows that on_closed performs session log finalization and native snapshot disposal without an exception barrier. A try/except around main does not enclose later UI callbacks. Running the exact old callback body with injected write/readback/disposal errors demonstrates exceptions escaping it; this is a callback defect, NOT reproduction or proof of the user's native crash. FIELD01 did not directly call Form.Dispose(), so a double Form.Dispose explanation is not asserted.

## Changes

- Every UI event delegate is guarded, including folder launch, close, idle and document close. Secondary error logging is best effort and cannot throw into Eto.
- A pure-Python Lifetime controller owns no native geometry. It controls cancellation, close-pending, closed and finalized states.
- The modeless form holds no native geometry snapshots. Owned duplicates are scoped to startup verification or a Check call, then released there. Borrowed document geometry is never disposed.
- Closed only records the phase and schedules finalization on the next Rhino UI Idle turn. It does not finalize the file, dispose geometry or release the last strong panel reference inline. Eto disposes its own window; we do not call Form.Dispose.
- The later finalization catches report failures, unsubscribes callbacks and removes only its own sticky entry. During Check, a close request cancels between supported native calls and waits for Check to return. No forced native abort.
- The form is tied to MainWindowForDocument. Document closure disables document reads; the checker reports unavailable safety measurements rather than accessing a closed model.
- A duplicate script invocation never closes an already open panel automatically.
- install.cmd no longer launches Rhino automatically. A desktop shortcut and launch.cmd explicitly start a new field copy. Runtime settings, registry, production plugin and toolbar remain unchanged.
- collect_reports.cmd can run WITHOUT Rhino. It copies bounded recent Field text logs and matching Windows Application error events into one local ZIP. It does not collect model files/memory dumps, upload anything, change settings or start/kill Rhino. Logs may contain private local paths; inspect before sharing.

The comparison.3dm bytes and candidate acceptance states remain exactly the FIELD01 data. No new shape, G2 certificate, native Join success or solver release is implied.

## Verification scope

Tests execute pure callback logic, error injection, real log files, deferred cleanup ordering, cancellation and structural runtime guards. Windows CI runs installer and collector helper tests in PowerShell 5.1 and 7; RhinoCommon API signatures compile; all four entry/helper modules compile with actual IronPython 2.7.12 syntax. These scopes are not live Eto/Rhino tests. Native crash root cause and successful Rhino close remain NOT VERIFIED until field evidence exists.

Install to a new immutable release. Do not overwrite the previous released ZIP. Keep previous reports/work copies. First collect the existing failure logs; a later minimal smoke test is open/close without running Join. Requested geometry and parent objects must remain untouched.
