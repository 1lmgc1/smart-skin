# P07F2: one field attempt after fixture and layout repair

Expected identity: **0.0.14-p07f2 / P07F2**, exact published commit. Use the green `build-p07f2` artifact. Keep the current Rhino/.NET setup; no runtime switch. Close Rhino, extract the bundle to the folder containing INSTALL.cmd, run it normally and reopen Rhino. No manual RHP registration or separate installer test.

## Geometry and actions

Use a copy of the same prepared model and the same opening. Do not delete another surface merely to repeat the previous preparation. Start with the opening already uncovered. The command's object count is actual N, not a fixed 12 or 20.

1. Run SmartSurfaceVersion and retain the full identity.
2. Click Smart Skin, select the same six naked opening edges and finish with Enter. No whole-object preselection is required.
3. Keep G2, Refine ON, 5%, Automatic, Average OFF. Continuity, curvature tolerance and Isocurve direction controls must now be visible; the Average explanation must wrap within the window.
4. The first contextual build in this process runs all eight native tests. Keep `SMARTSKIN_P07F2_FIXTURE` POST_SPLIT and FINALIZED lines plus every `SMARTSKIN_P07F2_SELFTEST` line. POST_SPLIT valid=False may be expected diagnostic evidence; FINALIZED must be valid=True and the suite must end PASS, cases=8, failed=0. A fixture that is valid but fails the actual G2 check is still a failure.
5. On READY / G2_SAMPLED_VERIFIED, inspect the cyan cap and confirm once with Enter, Space or right-click. It must add one cap and replace zero sources. Select the cap and its four neighboring Breps, run Join, verify one joined Brep, then Undo that Join. Undoing the Smart Skin command itself must remove only its result.
6. On BLOCKED, press Esc and return the full log. Do not change tolerances, lower continuity, toggle Average, bypass the tests or rebuild the input. If the self-tests pass and the solver reports another rejection, that is evidence of the next geometric stage, not a successful fill.

## Output and return

Identity/final command prefix is SMARTSKIN_P07F2. Existing P07F1 input/attempt/boundary protocol prefixes and P07 outcome codes are retained deliberately. Acceptance requires P07_ACCEPTED, MATCH_SRF, G2_SAMPLED_VERIFIED, six proved target edges, added=1, replaced=0 and N->N+1. Cancellation must add nothing. PASS together with action=CANCELLED does not mean a cap was built.

Return the complete command history from SmartSurfaceVersion through the final action line and one screenshot showing the settings fields and result/blocked status. No extra PowerShell or installer log unless installation actually fails. Keep private geometry and field evidence out of the public repository.
