# Repository rules

## Product boundary

Smart Skin is a Rhino 8 surface-assistance plug-in. P01/P01F1 GeometryReport/Preflight and the P02 topology classifier/router are read-only. P03 may build one bounded disposable PlanarSrf, EdgeSrf or two-section Loft candidate from copies, preview it, and add exactly one Brep only after explicit confirmation. P03F1 changes only document-count diagnostics so deleted Undo records are excluded. P04 adds a native same-name RUI and its delivery lifecycle. P04F1 temporarily expands that toolbar to four diagnostic buttons. P05 adds a contextual five-to-eight-edge hole-fill route. P06 establishes the accepted one-button/live-window interaction. P07 replaces that route's rejected `CreatePatch` geometry with Rhino 8.21 `MatchSrf`: measured G0/G1/G2, Refine and explicit Average surfaces. Sources remain unchanged unless the user turns Average on; that mode previews the changed context and replaces only the exact owning Breps on confirmation.

## Patch discipline

- One patch has one architectural objective.
- State invariants, acceptance criteria, regressions and intentionally untouched areas.
- Use `VERIFIED`, `STATICALLY CHECKED` and `NOT VERIFIED` literally.
- Do not start the next patch before reviewing the previous field test.
- Never overwrite a released bundle; increment the version.
- P04 was released as `0.0.8-p04` at `a9e854dec93cde1a0e74d2596081d863803993ae`; do not impersonate the interrupted `0.0.7-p04`/v001 draft or use a Drive kit as the publication channel.
- P04F1 is version `0.0.9-p04f1`: one existing Smart Skin toolbar with buttons for Build, Plan, Preflight and Version. Preserve every P04 GUID and add stable GUIDs for new controls.
- P05 is version `0.0.10-p05`: one contextual tangent Patch candidate from five to eight selected naked Brep edges. That release preserves all P04F1 toolbar identities and every earlier bounded route.
- P06 is version `0.0.11-p06`: one visible Smart Skin button, one modeless live-result window, and Rhino-native Enter/Space/right-click confirmation. Retire the three diagnostic button nodes without reusing their GUIDs; preserve their command, macro and bitmap identities. Keep Plan, Preflight and Version available only as command-line diagnostics. Do not add visible Accept/Cancel controls.
- P07 is version `0.0.12-p07` and requires Rhino 8.21 or later. Keep the P06 button/window contract. The five-to-eight-edge contextual route must use `Brep.CreateFromMatch`; do not silently fall back to `CreatePatch` or report requested continuity as verified continuity. Commit only after measured tolerances pass. Average surfaces is allowed only when every target is an untrimmed natural edge; it is an explicit destructive mode, must prove every seam joined and must be one Rhino undo operation.
- P07F1 is version `0.0.13-p07f1`: whole-boundary verification and mandatory native self-tests. P07F2 is `0.0.14-p07f2`: repair the synthetic split-edge fixture initialization and settings-column layout, without changing production geometry or acceptance. Finalize only the synthetic fixture's missing vertex tolerance, then require its native validity AND full G2 verification. Do not bypass the eight-case gate. P07F2 static source guards are not native or UI-rendering tests. Its actual field evidence is still required. Existing P07/P07F1 diagnostic protocol identifiers are intentionally retained where unchanged.
- Preserve fixed plug-in and UI GUIDs. Never reset Rhino layouts or delete shared UI settings to repair a toolbar.

## Safety invariants

- Never modify source geometry silently. P07 Match-only adds one cap and preserves sources. P07 Average may replace only the selected owning Breps after the user explicitly enables it; preview remains copy-only and the log must report exact added/replaced counts.
- Rhino API calls stay on Rhino's supported command/UI execution path.
- Expensive operations require bounded complexity, observable Esc cancellation between supported native calls, and a retry/time-budget strategy. Rhino geometry calls stay on the supported UI thread and are never force-aborted from a worker thread.
- A bad input must fail with a diagnosis rather than hang.
- Do not commit secrets, user evidence or forum models without confirmed redistribution rights.

## Verification economy

- Run targeted tests for the changed layer on ordinary patches.
- Run Rhino smoke tests when plug-in loading, commands or Rhino-facing behavior changes.
- Run the full regression corpus before releases and after shared Router/Validator/Core changes.
- Do not spend the user's field-test cycle on PowerShell installer checks; CI builds/packages, and the user reports installation only if it actually fails.
- Update the Drive journal at checkpoints, architecture decisions, verified patches, serious blockers or handoff—not after every minor edit.

## Commands

```powershell
dotnet restore SmartSkin.sln
dotnet build SmartSkin.sln -c Release -p:SourceRevisionId=local
dotnet test tests\SmartSkin.Core.Tests\SmartSkin.Core.Tests.csproj -c Release --no-build
.\scripts\Test-P07F2Guards.ps1
.\scripts\Package-Artifact.ps1 -Configuration Release -Version 0.0.14-p07f2 -Commit local
```

## P08E1 experimental full-cycle patch

- Version `0.0.15-p08e1`: one existing toolbar button dispatches the supported Rhino ScriptRunner/CPython full-cycle native-network constructor. Retain stable GUIDs and the prior implementation as a command-line legacy route.
- The supported family is explicitly bounded and must be derived from selected native edges/owners, never from a private fixture. Reject ambiguous or unsupported inputs. Preserve rational upper source boundaries homogeneously.
- Shoulder handle factor changes new guide/surface geometry only. Full-boundary failures, including finite source-side end strips, remain visible; never relabel experimental partial continuity as full G2.
- Test numerical reconstruction, native input family recognition, preview state and transactions separately. Neither mock tests nor openNURBS readback are licensed Rhino GUI tests.
- Installer behavior is superseded by the P08E1F2 restoration below. It never resets UI or launches Rhino and refuses an incomplete installer scaffold for production installation.
- New test commands: `python -B -m unittest discover -s tests -p test_skin_kernel.py -v`, `python -B -m unittest discover -s tests/python -p "test_*.py" -v`, and `scripts/Test-P08E1Guards.ps1`. Use exact runtime dependency pins from the entry script.

## P08E1F2 pipeline restoration

- Version `0.0.16-p08e1f2` restores the proven `current`/HKCU lifecycle and genuine uninstall. Do not reject an administrator token or require machine-registration migration merely because HKLM contains a matching GUID. Do not mutate HKLM plug-in registrations.
- Keep P08E1 geometry and one-button/live-handle UI unchanged. The correction concerns delivery, identity and installation only.
- A source checkout is not a runtime package: reject source-layout before prerequisites or identity-specific policy, without hidden building or downloading.
- Mandatory delivery chain: exact final published source SHA, successful Windows CI and Windows PowerShell 5.1 real-CMD tests, artifact ID, verified outer/inner ZIP hashes, manifest/build-info/runtime identity. Deliver the unchanged CI install ZIP, never a locally rebuilt/repacked substitute.
- Tests execute the actual packaged launcher and PS scripts with isolated destinations. Token cases, quoting/non-ASCII paths, legacy migration, unrelated-file preservation, repeat update, failure recovery and genuine uninstall must pass. Do not bypass the behavior being tested with IsTest or a stub script.

## P08E1F3 native attachment repair and selected U/V handles

- Field-candidate target `0.0.17-p08e1f3`: exact compound-span recognition, oriented local corner charts and independently selectable, mirror-coupled generated U/V handles. This is an experimental field candidate, not a finished general solution or native-host verification claim.
- Preserve exact native source loci and immutable owners. Generated guide positions, layout, row count and shared parameter jets may change; required physical source attachment and shared G0/G1/G2 compatibility may not be weakened to keep an arbitrary generated shape.
- Hard-point exceptions are restricted to the captured `upper:side0` and `upper:side1` source intersections. Increasing curvature toward these points is allowed. No finite excluded interval, lower corner or independent internal-junction exemption is permitted.
- Reject the previous same-side lower attachment and any invalid/folded candidate. Native trim-domain sidedness, complete source coverage, regularity, bounded nonoverlap screening, representation-invariant recognition and unchanged physical acceptance gates are mandatory. Full-construction arbitrary-orientation robustness is not claimed: stored high-degree coefficient conditioning can reject rotated inputs. Such failures remain fail-closed with an internal encoding diagnosis; do not loosen G2 or blame the selected loop.
- A regular lower corner whose native parent operators are incompatible with the fixed tolerance must fail with a named diagnosis before construction. It must not silently receive a hard-point exception.
- Every edited result needs fresh geometry/attachment/shared-join/symmetry evidence. The commit helper must recheck that evidence and the exact current request before every native addition, with rollback on reentrant edits or source changes.
- Do not change P08E1F2 installer behavior, token policy or verified delivery pipeline. Explicit selected naked-edge scope remains; group/whole-surface opening discovery is a separate unresolved design task.

## P08E1F4 native corner-frame evidence repair

- Version `0.0.18-p08e1f4` separates the exact selected 3D-edge attachment frame from the native 2D-trim push-forward frame used to identify the occupied corner wedge. Do not demand cross-representation orthogonality or silently discard native trim provenance.
- Retain exact original source data, physical G0/G1/G2 gates, sidedness/contact rules, F3 constructed geometry and selected U/V behavior. Reject ambiguous frame correspondence with scalar diagnostics.
- Preserve the F2 installer and exact-SHA Windows CI delivery pipeline. Native host behavior remains subject to a fresh field test.

## P08E1F5 preview lifecycle and selection

- Version `0.0.19-p08e1f5` repairs the lazy handle-catalog lifecycle: after a verified baseline creates the basis, refresh the catalog and obtain a real neutral edit result with the exact request/proofs/positions before enabling interaction.
- Preparation must show its current stage, elapsed time and bounded budget. A cancelled or failed initial build must not look like a finished empty inspector. Preserve deliberate Esc/window-close cancellation.
- READY-only viewport left-click selection may choose current generated U/V guides and handles without creating document objects. Keep dropdown fallback and Enter/Space/right-click acceptance. Native callback behavior remains a field-verification boundary.
- Do not weaken attachment, native-owner, source-snapshot, revision or transactional commit gates. Keep F4 geometry/capture, installer algorithms and exact-SHA CI delivery unchanged.

- F5 CI repair: a default-profile fallback may run only after all original optimizer attempts fail. Prove any omitted optimizer inequality redundant over the complete existing parameter box with conservative floating bounds, then require solver success, finite/bounded parameters and the original world-coordinate feasibility check. Preserve successful primary outputs exactly; do not loosen physical attachment gates.

## P08E1F6 native cache and initial-preview latency

- Version `0.0.20-p08e1f6` prepares disposable Brep bounding-box/solid caches before every full-archive fingerprint. Preserve exact later fingerprints and stale checks; unexplained drift must reject with bounded component diagnostics.
- Initial neutral U/V handoff may reuse only the sealed, fully validated baseline descriptors verbatim, with fresh source/request/position bindings and a fresh native-owner screen. Non-neutral edits retain full checks.
- Throttle native event pumping while checking cancellation, revision and deadlines at every numerical checkpoint. Report measured stage/pump timing; headless timing is not Rhino performance verification.
- Keep physical tolerances, source geometry, upper-only hard-point scope, installer algorithms and exact-SHA Windows CI unchanged. The openNURBS regression package is CI-only, never a Rhino runtime dependency.

## P08E1F7 rejected-edit recovery

- Version `0.0.21-p08e1f7` separates permission to request another slider edit from permission to accept the current native preview. A revoked receipt must still block acceptance and native picking; it must not permanently disable retries from a valid restored numerical baseline.
- Before the first restored retry, recheck the captured source/tolerance state; every resulting edit still runs the complete numerical and native checks. Do not revive receipts, auto-accept, or introduce retry loops.
- Log bounded generated handle IDs, requested/applied/restored values and revisions so field evidence distinguishes a missed event, rejected edit and accepted neutral state. Preserve the constructor, ranges, source geometry and physical gates.
- A consumed left guide/handle pick must invalidate the current native confirmation token; a distinct later Enter/Space/right-click remains valid. Test conditional native input propagation without claiming it occurred in the field.

## P08E1N1 native-operator diagnostic

- Version `0.0.22-p08e1n1` adds only the separate read-only SmartSkinNativeCompare command; ordinary Build, Python construction, existing handle behavior and installer algorithms stay unchanged. No new toolbar button.
- Derive the ordered logical boundary from actual selected edges/parent branches. Do not use five/nine density slots, copied center profiles or the legacy scaled-loft seed. Preserve within-chain geometric features, including exact representation splits; unsupported native bindings must be named.
- Native Match uses copied parent BrepEdges, Average=false, with all-boundary metrics after each operation. Requested G2 and native curvature-percent settings are not physical residual proofs. No automatic refinement/search loop or silent Patch fallback.
- Candidate previews are disposable and read-only. There is no Add, export or accept path in this diagnostic. Source and copied-owner archive integrity, bounded complexity and cancellation between native calls are mandatory.
- Report sampled full ambient shape-operator metrics, native eligibility and operation time separately from unverified global G2, oriented continuation and separation. Actual native API execution remains a field test.

## P08E1N2 first-Match correspondence diagnostic

- Version `0.0.23-p08e1n2` narrows the separate read-only command to one source-derived EdgeSrf seed and two independent first-side Match attempts with ReverseMatchDirection=false/true. Do not apply a second Match or add unrelated recipes.
- Preserve copied parent BrepEdge context. Report native and logical endpoint/domain directions, selected target trim provenance and candidate correspondence. Reversal variants are diagnostic probes, not a guarantee that compound target directions are normalized.
- Measure every logical side before and after each attempt, with direction, unresolved correspondence and finite-sampling limitations explicit. Requested G2, returned=true and a nonempty edge-coverage counter are not a verified attachment.
- Keep source/copy integrity, read-only disposal, unchanged Build/installer behavior and exact-SHA Windows CI delivery. Do not publish private model coordinates or field files.
