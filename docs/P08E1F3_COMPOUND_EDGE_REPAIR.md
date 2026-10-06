# P08E1F3: native attachments and selected U/V controls

Version: **0.0.17-p08e1f3**. **Experimental field-test candidate.**

## Objective and invariants

Repair representation-dependent opening recognition, construct the supported native opening with correctly oriented attachments, and let the operator edit generated U/V guides. Original source objects and boundary loci remain immutable. Generated guide positions, patch layout and row count are design variables, not source constraints.

A straight central run may occupy only part of a compound rational NURBS edge. Recognition now analyzes exact homogeneous knot-span coefficients and the selected interval, rather than requiring an entire selected edge to be straight. Curved spans are not approximated as lines.

The command still requires explicit selected native naked-edge subobjects, 4–16 edges. Whole surfaces, extrusions and groups are not automatically expanded into a chosen opening. `SmartSurfaceBuildLegacy` retains earlier routes. Ambiguous or unsupported input is rejected with a reason, rather than silently selecting another loop or substituting a stock cap.

## Attachment policy

- Preserve the complete original boundary and the required physical native-parent attachment on every finite source interval.
- Preserve G0/G1/G2 compatibility across new shared joins, including after a guide edit. Generated shared traces and their parameter-speed jets may move together.
- The two captured upper-chain/source-side intersections may be hard points. Their chart edges may collapse to the same physical source vertex, and curvature may increase without a finite bound as that vertex is approached.
- This exception does not authorize a finite weakened band, a lower singular corner or a separate internal seam/junction exception.
- Check actual native trim-domain inward/outward information. Unsigned normal/curvature agreement alone cannot distinguish a correct extension from returning onto the parent's side.
- A regular lower corner whose two native parent curvature operators cannot both meet the unchanged tolerance is unsupported. Report that conflict before construction; do not invent a new hard-point exception.

## Construction and rejection history

The old single rectangular layout is insufficient for the supported reflex lower corner. A reversed-arrival candidate was rejected because it attached on the native parent's side. A positive Jacobian did not make that attachment correct.

The current lower repair uses three regular sectors and a coherent shared physical two-jet field. Its support may extend over a larger generated region and rebuild the adjacent generated interface. Source boundaries remain exact. The free internal junction is conditioned through a compatible parameter-speed change; no native tolerance increase is used.

The upper repair uses two source-preserving corner charts. The exceptional parameter edge maps to one approved physical source vertex. Positive-radius attachment and shared-join checks, together with an exact projected-Jacobian factor test, distinguish the isolated hard point from a finite fold or excluded band.

## Known numerical-placement limitation

The high-degree lower construction is sensitive to binary64 coefficient rounding under rotation. A rigidly rotated version of an otherwise passing input can exceed the unchanged stored-geometry curvature gate, even when recognition and the source-relative scale are correct. An independent high-precision replay distinguishes this from noisy validation.

This experimental field candidate does **not** guarantee successful construction at every orientation. Such input must stop with a numerical encoding/conditioning diagnosis; no source movement, tolerance increase or acceptance of the failed stored geometry is permitted. The failure must not be described as a wrongly selected loop. A local construction frame alone does not remove this exported-coefficient limitation.

## Selected U/V workflow

The intended workflow is one toolbar button, one live preview window, a generated U/V guide list, a handle list and a slider. The catalog comes from the actual repaired layout. It must not display an old row that no longer lies on the skin.

The bounded version couples mirror partners. The evaluator returns actual handle positions after all active edits, and independently checks geometric symmetry. Every new setting rebuilds compatible incident patches and receives fresh source-attachment, shared-join and geometry checks. An unsafe value is rejected and the last valid preview is restored. Enter, Space or right-click accepts the current verified result; Esc or closing the window cancels. No original object is replaced.

Viewport dragging is not implemented in this version. Lists, highlight and slider are the explicit selection/manipulation interface.

## Current verification boundary

**VERIFIED, component scope:** exact split/merged span recognition and numerical preservation tests; native-format upper-corner readback and finite attachment checks; both regular lower repairs, their neighboring interfaces and complete lower-chain numerical checks; exact local projected-Jacobian and individual simple-boundary checks; controller/request/transaction regressions.

Whole-atlas finite attachment/guide/orientation checks and the bounded projected cap-cap screen also pass for the neutral, independent endpoint and recorded combined edit cases. This is finite numerical evidence, not a universal all-parameter/global injectivity certificate. The complete native owner screen and actual Rhino interaction remain field checks; runtime acceptance requires fresh successful screen receipts. Individual handle ranges do not certify their entire Cartesian product.

Preparation and cached editing have separate180-second and60-second total budgets; the native-owner screen has its own15-second between-call limit. Progress and Esc are observed between bounded operations. No individual native kernel call can be force-interrupted. Exact-SHA Windows CI is mandatory before delivery.

**NOT VERIFIED:** licensed Rhino capture/binding behavior, Eto rendering and native input interaction, native Join and the final field workflow. OpenNURBS readback, synthetic tests and mocks are distinct evidence and must not be described as licensed Rhino execution. Numerical boundary samples are not a universal mathematical certificate for arbitrary inputs.

All public tests use synthetic geometry. Private user models and evidence remain outside the repository and CI artifacts.

## Delivery

Keep the proven P08E1F2 HKCU/current installer and token-neutral behavior. Publish only to the approved separate branch. Deliver the unchanged install ZIP from a successful Windows CI run at the exact final source SHA, after checking its artifact ID, hashes, manifest, build-info and runtime identity. A source archive and a private recovery checkpoint are not install packages.
