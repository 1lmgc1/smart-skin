# P08E1F5 — preview lifecycle and U/V selection

Version: `0.0.19-p08e1f5`. Parent: `0.0.18-p08e1f4`.

## Field evidence and diagnosed defect

F4 installed and loaded; native capture passed for the selected six-edge opening and four immutable owners. The screenshot showed a visible preview window still doing its first numerical construction/checks, with empty disabled selectors. The user deliberately cancelled; no geometry was added. The SciPy bounded-step warning alone is not a fatal construction result.

An independent source/test diagnosis found a deterministic lifecycle bug. The window requested its handle catalog immediately after preparation, before the kernel's first successful evaluation created the constrained basis. That initial catalog was intentionally empty, but the window never refreshed it. Thus even a successful baseline would leave handles unavailable.

## Repair

- Evaluate and check the baseline first, then reread the actual lazy catalog.
- Evaluate its real neutral selected-handle request before exposing controls. Geometry, handle positions, attachment/edit proofs and native-screen receipts stay bound to that same request.
- Show the real current stage, elapsed time and build budget. Emit stage and terminal READY/BLOCKED/cancel information in Rhino history. The first construction can be substantially slower than a cached edit.
- Enable viewport left-click guide/handle picking only for the current verified preview. Keep the Guide/Handle lists as a fallback. Picking acts on disposable preview geometry and never adds selection objects to the document.
- Preserve Enter/Space/right-click acceptance and Esc/window-close cancellation. A failed, cancelled or superseded build cannot enable editing or acceptance.

The original source owners, geometry constructor, source/shared G0/G1/G2 tolerances, native-owner tests and commit transaction remain unchanged. No finite-band attachment relief or lower hard-corner permission is introduced.

## Use

1. Select the complete native naked-edge opening as before.
2. Allow the displayed initial construction/check stages to finish. Editing is unavailable until READY; Esc cancels between supported operations.
3. At READY, choose a U/V guide and its handle in the viewport or in the lists, then adjust its slider. A new setting is checked before it becomes acceptable. Unsafe settings remain rejected.
4. Enter/Space/right-click accepts only a current verified result. Esc or closing the window discards it.

## Verification boundary

Numerical and mock regressions establish catalog activation, request binding, guarded picking and transaction behavior; exact-source Windows CI verifies build/package/install lifecycle. They do not establish native Rhino viewport callback behavior, UI rendering, timing or owner-query success. Native callback coexistence with Rhino input/navigation requires the next field test; the list fallback remains available.

F3/F4 experimental scope and fail-closed rotation-conditioning limitations remain. The released package must be the unchanged CI ZIP for the exact published F5 commit. Source/recovery archives are not installers.
