# P08E1F6 — native cache identity and initial-preview latency

Version: `0.0.20-p08e1f6`. Parent: `0.0.19-p08e1f5`.

## Field evidence

F5 installed, loaded and captured the original six-edge opening with four owners. The first construction reached native-owner screening after 116.2 seconds, then rejected at 118.9 seconds with `OWNER_SCREEN_STALE`. The user cancelled afterward; no objects were added and sources remained unchanged. The field log attributes about 94.7 seconds to baseline construction/checks and 15.4 seconds to the subsequent neutral handle check. These measured host times take precedence over headless estimates.

## Diagnosed identity defect and repair

A small public planar Brep reproduces a serialization change after read-only bounding-box and solid-classification queries, with unchanged vertices. Official openNURBS serializes those cached fields. F5 issued its generated-Brep fingerprint before preparing them; mesh serialization flags alone do not exclude these caches.

The shared native adapter now prepares `GetBoundingBox(False)` and `IsSolid` before every full archive SHA256 fingerprint, including conversion and screen receipt checks. The complete fingerprint comparison remains authoritative. Changes to geometry, trim, orientation, user data, source, request or screen inputs still revoke the result. Unknown later cache drift also rejects; bounded component/index diagnostics identify what changed. No failed receipt is silently refreshed or accepted.

## Bounded latency repair

- Seal the validated baseline surfaces, ordered guides, network, source/tolerance state and proof data. The initial all-neutral handle request reuses these exact descriptors and obtains fresh request-bound handle positions and evidence. A changed baseline or non-neutral request cannot take this path.
- Preserve a fresh native conversion and native-owner screen. Every native Add still checks the current geometry, source, request and receipt.
- Pump Rhino events at most once per 25ms checkpoint cadence, with reentrancy protection. Cancellation/state/deadline checks remain at every checkpoint. Log checkpoint/pump counts and time spent pumping.
- Pinned Linux component measurement: former regenerated neutral pass 15.22s; exact baseline handoff 1.63s, plus about 0.15s to create its seal. This is not a Rhino-host speed guarantee. F5's neutral regeneration changed four chart representations slightly; F6 retains the already-validated constructor baseline verbatim, rather than claiming byte identity with F5's regenerated neutral output.

Construction, finite source/shared G0/G1/G2 tolerances, upper-only hard-point scope and selected-handle ranges remain unchanged. Arbitrary rotated inputs can still fail the stored-coefficient conditioning gate. No lower-point or finite-band exception is introduced.

## Verification and field check

Numerical/mock tests cover immutable neutral handoff, invalidation, native cache preparation, detailed stale diagnostics and throttled cancellation/revision handling. Three actual openNURBS archive regressions run with CI-only `rhino3dm==8.17.0`; this is not a new Rhino runtime dependency. Exact-source Windows CI must pass build, managed coefficient checks, numerical suites, package integrity and the established real-CMD/PowerShell5.1 installer lifecycle before delivery.

Native Rhino8.35 cache-query sequencing, initial-preview time, owner-query success and viewport interaction remain **NOT VERIFIED** until the field test. The next useful report is the complete stage/timing history through READY or the first named BLOCKED component. Keep Esc cancellation available; a single native operation cannot be force-aborted.

At READY choose `U row 1`–`U row 8` or `V profile 1`–`V profile 5`. The eight structural seams remain read-only inspection guides. Enter/Space/right-click accepts only a current verified result; Esc/window close discards it.

Deliver only the unchanged install ZIP from the successful exact-SHA Windows run. Source/recovery archives are not installers. Installer algorithms, HKCU/current scope and toolbar identities are unchanged.
