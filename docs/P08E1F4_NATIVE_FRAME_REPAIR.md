# P08E1F4 — native corner-frame evidence repair

Version: `0.0.18-p08e1f4`. Parent release: `0.0.17-p08e1f3`.

## Field finding

F3 installed and loaded in Rhino 8.35 on .NET Framework 4.8. Its native input capture then stopped with `NATIVE_BOUNDARY_EVIDENCE: Native owner frame is not orthogonal`, before skin construction.

A Brep stores its selected 3D edge and its 2D trim on the owning surface as distinct native representations. Their positions can agree within the native mapping tolerance while their endpoint tangent directions differ slightly. F3 constructed corner occupancy evidence from the actual trim push-forward, then required that trim-derived co-normal to be orthogonal to the separate exact 3D edge tangent. This mixed two different frames and could reject valid native evidence.

The error was reproduced independently on a synthetic input and confirmed by read-only official openNURBS extraction of the recovered native input. No private model or its coordinates are shipped.

## Correction and invariants

- Keep an exact selected-edge tangent/co-normal frame for source attachment and lower construction.
- Keep the actual native trim tangent/co-normal, adjacent trim rays, nested membership probes and exterior wedge for the trimmed owner's occupied side.
- Bind and validate their correspondence explicitly, retaining the existing local branch-agreement threshold. Each frame is checked for orthogonality in its own basis.
- Re-evaluate the actual adjacent trim frame during native-owner separation instead of comparing its captured co-normal to a different 3D-edge tangent.
- Report scalar residuals and station/endpoint context when evidence fails. Do not print source coordinates or object identifiers.

Original geometry, source loci, G0/G1/G2 tolerances, hard-upper-point scope, selected U/V controls and the constructed skin algorithm are unchanged. Wrong tangent planes, reversed/ambiguous branches, forged or incomplete provenance and inward occupancy remain failures. There is no new intersection exemption or finite attachment-relief interval.

## Verification boundary

VERIFIED: the mixed-frame failure is reproduced on the recovered native representation and on a public synthetic counterpart. Targeted and aggregate regression tests and exact-source Windows CI must pass before an F4 install artifact is delivered.

NOT VERIFIED before the next field test: this correction's execution through Rhino 8.35 capture, native-owner queries, preview interaction and acceptance. Portable tests and openNURBS readback do not establish a licensed Rhino UI pass.

All F3 limitations remain, including possible fail-closed stored-coefficient conditioning failures after rotation, the bounded explicit naked-edge selection family, the unapproved incompatible regular lower-corner case, and numerical rather than universal global nonintersection certification.

## Delivery

Use the unchanged install ZIP produced by successful Windows CI for the exact published F4 commit. Preserve the proven `current`/HKCU installer lifecycle, real uninstall, token-neutral execution and unchanged HKLM registrations. A source archive is not an install package.
