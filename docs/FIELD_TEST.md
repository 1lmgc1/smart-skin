# P04F1 Rhino 8.18 field test - four command buttons

Use the green `build-p04f1` artifact for the exact published commit. Expected
version: `0.0.9-p04f1`. Installation is not a separate test; report it only if
an actual problem occurs.

This test covers only the changed toolbar mapping. Do not repeat the closed
P03/P03F1 geometry suite.

## One focused pass

1. Start Rhino normally and confirm one Smart Skin toolbar with four distinct
   buttons in this order: Build, Plan, Preflight, Version.
2. Hover each button and confirm that its tooltip names the intended action.
3. Click Version. Keep the complete `SMARTSKIN_P04F1 PASS` line and confirm
   version `0.0.9-p04f1`, the exact CI commit and an unchanged object count.
4. Select the same two closed curves used for the accepted P04 Loft and click
   Preflight. Finish selection if Rhino asks. Keep its final machine line and
   confirm `objects=2->2`.
5. Select the same curves and click Plan. Confirm `SECTION_SET`, primary
   `LOFT` and `objects=2->2`.
6. Select the same curves and click Build. When its existing preview appears,
   choose Cancel. Confirm `action=CANCELLED` and no added object.

Stop at the first wrong button, duplicate toolbar, missing glyph, incorrect
command or mutation by a read-only command. Do not reset Rhino UI or manually
import the RUI as a workaround.

## Return evidence

Return one screenshot showing the four buttons and the complete machine output
from the four clicks. User models and screenshots remain private and are not
committed to the public repository.
