# P06 Rhino 8.18 field test — one-button live result

Use only the green `build-p06` artifact for the exact published commit.
Expected version: `0.0.11-p06`. Installation is not a test; report it only if
an actual problem occurs.

This is one focused interaction check. Do not repeat P03/P04/P05 tests.

## Test

1. Open the returned P05 result model: it has 13 active objects, one accepted
   cap and the other six-edge opening still unfilled.
2. Run `SmartSurfaceVersion` once and keep its complete `SMARTSKIN_P06 PASS`
   line.
3. Confirm the Smart Skin toolbar contains one button labelled `Smart Skin`.
4. Click that button, sub-select the six naked Brep edges around the other,
   still-unfilled opening and finish selection with Enter.
5. Confirm one `Smart Skin — result preview` window appears and one cyan Patch
   preview is visible. The default must read `Balanced`, 8×8 spans, sample 1×
   and flexibility 1.
6. Choose `Flexible`. The viewport preview must update without adding or
   changing document objects; the status must return to `READY` and show
   flexibility 10.
7. Press Enter, Space or right-click once. Do not look for an Accept button.

## Expected result

- The settings window closes.
- Exactly one Brep is added; every source object remains unchanged.
- The final line contains `SMARTSKIN_P06 PASS`, `action=ACCEPTED`,
  `code=P06_ACCEPTED`, `preset=FLEXIBLE`, `flexibility=10`, `added=1` and
  `objects=13->14`.

## Return

Return the complete command output and one viewport screenshot showing the
result and the single-button toolbar. No installer or PowerShell log is needed.
