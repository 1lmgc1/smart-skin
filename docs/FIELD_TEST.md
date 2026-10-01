# P04 Rhino 8.18 GUI field test - do not run before the CI gate

Use only the artifact from a successful build-p04 for the exact published
P04 commit. Expected version: 0.0.8-p04. This is a focused toolbar integration
test, not a repeat of the full P03/P03F1 geometry suite.

## Install gate

Close all Rhino windows and ensure Rhino.exe is stopped. Extract the exact
CI artifact to a new folder; run INSTALL.cmd. Stop on any FAIL. Keep
SMARTSKIN_INSTALL PASS, confirm version, managed current path and toolbar hash.
Do not drag-register an RHP, manually import RUI, or reset the Rhino UI.

## A - first-load visibility and demand-loading

Start Rhino normally. Before typing any Smart Skin command, verify one Smart
Skin toolbar/container with one visible button and a nonblank glyph/tooltip.
In a blank document create one Circle, leave it selected and click the button.
The command must run without a prior SmartSurfaceVersion call. Observe whether
preselection is honored exactly as by the existing SmartSurfaceBuild; do not
change selection options as a workaround. If the toolbar is not visible,
record that failure before attempting anything else.

## B - preview, explicit commit and Undo through the button

For that Circle finish selection if prompted, inspect the preview and choose
Accept explicitly. Keep strategy=PLANAR_SRF, action=ACCEPTED, built=1, added=1,
objects=1->2 with patch=P04 and the exact commit. Undo must remove only the
new surface; SmartSurfaceVersion must then report objects=1 and 0.0.8-p04.

Click empty viewport space to clear selection. Click the button, select the
Circle after command start, finish selection and choose Cancel. Confirm
preview disappears and objects=1->1. Click the button again without a
preselection and press Esc before selecting anything: expect
P03_SELECTION_CANCELLED, objects=1->1. That P03 code is intentionally retained.

## C - UI persistence and ordinary hide/show

Hide and show only the Smart Skin toolbar using native Rhino controls. The
button should not duplicate. Leave it visible, fully close Rhino, restart,
and verify one toolbar and one button without reimporting the RUI. Repeat a
button-driven preview and Cancel. Record unexpected selection or load behavior.

## D - update and uninstall scope

With Rhino closed, reinstall the same green artifact. Restart and confirm no
duplicate buttons/containers and no unexpected changes to other toolbars.
Then close Rhino, run this artifact's UNINSTALL.cmd and restart. Record whether
the Smart Skin button/container remains, and whether native UI emits warnings.
Do not delete Rhino settings or unrelated cached RUI files to manufacture PASS.
The installer owns its current directory/registration and this RUI; automatic
removal of Rhino-maintained UI references is a field condition, not yet proven.
Any remaining stale UI is a P04 blocker to diagnose, not an accepted workaround.

Finish with Rhino closed and reinstall the same verified P04 artifact. Confirm
one usable toolbar after startup. If a GUI defect prevents use, restore the
previously verified P03F1 artifact with the same managed installation procedure
and record the P04 failure; do not leave the user without the working plug-in.

## Return evidence

Keep the exact install/version/Accept/Undo/Cancel/Esc machine lines, screenshot
of the toolbar, first-click/preselection observation, restart/update and
uninstall/reinstall results. Send complete errors. Do not publish user models
or screenshots to the public repository. VERIFIED requires all these gates;
a valid RUI or a green CI run alone is not a Rhino field PASS.
