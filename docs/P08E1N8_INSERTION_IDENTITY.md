# P08E1N8: verify the inserted surface by its geometric definition

Version **0.0.29-p08e1n8** repairs the post-insertion check on the primary `SmartSurfaceBuild` path. The existing **«Создать поверхность»** button continues to add only the inspected cap, with the approved label **«стыковка без гарантии плавности»**.

## Observed failure and correction

The latest field image locates a failure after native Add: the inserted object's identity, marker or geometry comparison rejected it. That message occurs only after Add returned the planned ID, exactly one new document object existed, and current source/candidate/units/tolerances/Undo checks passed. The accompanying copied TXT records a separate cancellation after successful selected-seam and cap qualification; it does not contain the pictured failed insertion. It has no version/commit header, so it is not exact loaded-assembly identity evidence.

The old comparison used an entire serialized Brep archive as geometric identity. Such archives also contain cached and nongeometric state. Cache preparation does not turn that representation into a pure shape definition. The precise field-level archive difference was not captured, and this release does not claim that it was reproduced in a licensed Rhino host.

The transaction now retains distinct evidence for two purposes:

- Full source and prepared-candidate archive seals still detect changes before and during insertion.
- A separately captured geometric signature compares the actual inserted cap with the confirmed cap. It includes exact rational NURBS data, parameter domains, boundary curves, trims, vertices, connectivity and orientation. It excludes explicit cache/display/user-data fields, derived tolerances and derived isocurve classifications. These fields do not replace the defining geometry, and native validity remains mandatory. Identity and the ownership marker remain separate mandatory checks. Actual geometric or topological changes still reject and roll back only this transaction's new object.

The native construction, Join qualification, G0 and bounded rank checks, explicit Add policy, Create button and normal-command Undo workflow are unchanged. There is no tolerance increase, parent replacement, new construction recipe or hidden Python fallback. The post-Add failure message now distinguishes the failed verification component.

Extraction remains bounded: the Brep snapshot has a 32 MiB memory-estimate limit and the defining-data stream has a 4 MiB limit. The former can include display caches, so exceeding it is a resource/extraction failure rather than evidence that the shape changed. Metadata-only differences are accepted only when the independently extracted defining geometry is available and equal within these limits.

## Use and verification limits

Install the verified exact-SHA CI ZIP and use the ordinary Smart Skin button or `SmartSurfaceBuild`. Select the original closed contour, inspect the preview and press **«Создать поверхность»**. Successful completion leaves one highlighted cap in the document. Esc or closing the preview before confirmation leaves no new surface. Reports remain optional through `SmartSkinNativeReport`.

Managed regressions exercise the production signature writer and transaction using explicit geometry data, including metadata-insensitive identity and rejection of coefficient, boundary, trim, connectivity and orientation changes. They do not execute the native Rhino extraction calls. Official openNURBS replay independently demonstrates that metadata-only changes can alter an archive while preserving its geometric payload. API compilation and the shipped assembly's actual call path are checked separately. Headless checks do not execute Rhino's licensed Add/UI/Undo implementation; those remain field-verification limits. This is a functional user-test build, not a claim of general stability, global regularity or G1/G2 continuity.
