# P02 Rhino 8 field test

Use the ZIP produced by the successful `build-p02` GitHub Actions run. Do not
mix it with a P01F1 artifact.

## Install

1. Close every Rhino window and confirm `Rhino.exe` is no longer running.
2. Extract the P02 artifact to a new folder.
3. Double-click `INSTALL.cmd` and wait for `SMARTSKIN_INSTALL PASS`.
4. Confirm `version=0.0.4-p02` and a path ending in
   `\AppData\Local\SmartSkin\Rhino8\current\SmartSkin.Rhino8.rhp`.
5. This is an update of the managed P01F1 installation, so
   `removed_old_files=0` is expected: the managed `current` directory is
   replaced transactionally rather than treated as an external legacy folder.
6. Start Rhino normally. Do not use `Tools → Options → Plug-ins → Install…`.

If installation fails, return the complete `SMARTSKIN_INSTALL FAIL` line and do
not start Rhino.

## Test A — build identity

1. Run `SmartSurfaceVersion`.
2. Confirm `Patch: P02`, `Version: 0.0.4-p02` and the artifact commit.
3. Keep the final `SMARTSKIN_P02 PASS` line.

## Test B — one planar closed boundary

1. In a blank millimetre document create one ordinary `Circle`.
2. Run `SmartSurfacePlan`, select the circle and press Enter.
3. Confirm:
   - `Routing status: READY`
   - `Topology: SINGLE_CLOSED_BOUNDARY`
   - candidate `1. PlanarSrf`
   - machine fields `primary=PLANAR_SRF`, `selected=1`, `objects=1->1`.

## Test C — four-segment boundary loop

1. Start another blank millimetre document.
2. Create one `Rectangle`, then run `Explode` so it becomes four line curves.
3. Run `SmartSurfacePlan`, select all four lines and press Enter.
4. Confirm:
   - `Topology: CLOSED_BOUNDARY_LOOP`
   - endpoint graph `nodes=4`, `components=1`, `ends=0`, `through=4`
   - candidate `1. EdgeSrf`
   - machine fields `primary=EDGE_SRF`, `selected=4`, `objects=4->4`.

## Test D — section set

1. Start another blank millimetre document.
2. Create one circle, copy it vertically by 10 mm and keep both circles.
3. Run `SmartSurfacePlan`, select both circles and press Enter.
4. Confirm:
   - `Topology: SECTION_SET`
   - candidate `1. Loft`
   - machine fields `primary=LOFT`, `selected=2`, `objects=2->2`.
5. Save this two-circle document.

## Test E — open-chain diagnosis and cancellation

1. Start another blank millimetre document.
2. Create and explode a rectangle, then delete one of its four sides.
3. Run `SmartSurfacePlan`, select the remaining three connected lines and press Enter.
4. Confirm:
   - `Routing status: BLOCKED`
   - `Topology: OPEN_CHAIN`
   - `Candidates: none`
   - machine fields `primary=NONE`, `selected=3`, `objects=3->3`.
5. Run `SmartSurfacePlan` again and press Esc before selecting anything.
6. Run `SmartSurfaceVersion` and confirm `objects=3`.

## Test F — restart

1. Close Rhino completely and reopen the saved two-circle document from Test D.
2. Run `SmartSurfaceVersion` and `SmartSurfacePlan` on both circles.
3. Confirm `P02`, `SECTION_SET`, `primary=LOFT` and `objects=2->2`.

## Pass criteria

- Build identity matches the artifact.
- The four required topology/route pairs match exactly.
- Endpoint graph evidence matches the exploded rectangle.
- No completed or cancelled command changes document geometry.
- The managed update and section route survive a full Rhino restart.

## Recorded reference result

P02 is `VERIFIED` in Rhino 8.18 for field build commit
`450bf1e28b77abdb5e17ca6b06fa5c1564963a5b`. GitHub Actions run 9 completed
Restore, Release build, all 23 Core tests, packaging and the installer lifecycle.
The managed field installation reported `0.0.4-p02` at the expected `current`
path.

The field test confirmed `SINGLE_CLOSED_BOUNDARY` / `PLANAR_SRF`, a four-segment
`CLOSED_BOUNDARY_LOOP` / `EDGE_SRF` with the expected endpoint graph, and a
two-circle `SECTION_SET` / `LOFT`. The closed-loop document contained other
objects, so its object-count invariant was `6->6` rather than the isolated
protocol's `4->4`. The open-chain branch was exercised with two adjacent
segments rather than three and correctly returned `BLOCKED`, `OPEN_CHAIN` and
`primary=NONE` with `objects=6->6`.

Cancelling `SmartSurfacePlan` before selection left the saved two-circle
document at `objects=2`. After Rhino was fully closed, the saved file reopened
under the same P02 commit and again returned `SECTION_SET`, `primary=LOFT` and
`objects=2->2`.

## Return this evidence

```text
install_machine_line:
version_machine_line:
single_boundary_machine_line:
closed_loop_graph_line:
closed_loop_machine_line:
section_set_machine_line:
open_chain_machine_line:
after_cancel_version_machine_line:
after_restart_machine_line:
result: PASS / FAIL
complete_error_if_any:
```
