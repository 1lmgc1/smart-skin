# P08E1N4: native support and trim experiment

Version: **0.0.25-p08e1n4**. This is a bounded, read-only attachment experiment. It does not replace the existing slow `SmartSurfaceBuild` path or claim that the native attachment problem is solved.

## What changes

The selected loop's four logical corners are ordered using both endpoints of each uniquely matched incident pair. Selection order and traversal can no longer choose different corner coordinates solely because coincident native endpoints differ slightly. This comparison never moves or snaps source curves. Exact splitting and degree-elevation checks cover the tested curve representations; arbitrary rotation covariance or every native Brep re-encoding is not claimed.

The command retains its EdgeSrf seed and two independent first-Match direction probes. It chooses a unique Match support by actual original-corner adjacency, without hardcoding a reversal flag. It then measures the original finite source curves against that untrimmed underlying surface and at most one side-Blend support built from actual parent edges and intervals. A gap to the current candidate edge is reported separately from a gap to the underlying support.

Measurements report source parameters, mapped UV, endpoints and one-sided feature approaches, incidence, normals and the complete ambient curvature operator. Strict jet values are qualified by independent 3D incidence; off-support projected values are labeled separately. Only the specifically identified upper attachment points retain the existing hard-point exception. No finite band, lower corner or internal junction is exempted.

The prior physical tolerance is preserved: captured position/angle tolerances and `max(1e-5 / compatibility_scale, 1e-8)` for the curvature operator. The historical five original-curve intersections across 85% of the usable half-width are evaluated solely to reproduce that validation scale. They do not position native surfaces, guides or trims. The full-source control-hull extent is informational and cannot impose a stricter gate. Unresolved compatibility produces metrics without permission to trim.

## Conditional trimming

Only a support that passes the finite source/jet precheck and independent UV-loop screen proceeds to `BrepFace.Split`. The target is a newly allocated support; cutters are the original finite 3D source curves. Parent surfaces and their trims are never modified. There is no extension, projected-cutter substitution, extruded cutter, raised tolerance or repeated Match search.

The returned actual trim loops are inspected. A region must be unique, have one outer loop with no additional hole, cover every original source piece, and have every output boundary lie on the original unjoined source curves. A joined copied loop is an additional check, not a replacement for original loci. The actual trimmed boundary is then checked again against the original positions and parent jets. Regions are never chosen by largest area or return order.

These outcomes are separate in the TXT: support precheck, Split/region selection, and final boundary recheck. Successful native calls and requested G2 are not measured full G2. Trimming cannot repair wrong curvature on an otherwise incident support. A failed native candidate does not establish that every construction is impossible.

## Полевой запуск

1. Закройте все окна Rhino, полностью распакуйте новый install ZIP и выполните `INSTALL.cmd`. После `SMARTSKIN_INSTALL PASS` откройте Rhino.
2. Выполните `SmartSurfaceVersion`. Нужна версия `0.0.25-p08e1n4` и commit из проверенного CI-пакета.
3. Запустите `SmartSkinNativeCompare`, выберите исходный полный замкнутый набор naked Brep edges и завершите выбор.
4. `Next` переключает временные варианты. Исходный EdgeSrf и результаты первого Match остаются доступны. Новый подрезанный вариант появляется только при прохождении дополнительных проверок. Если обе опоры непригодны, новых подрезанных вариантов не будет; причины и конкретные места записаны в TXT.
5. Enter/Done или Esc закрывает просмотр и освобождает временные объекты. В документ ничего не добавляется и не заменяется. После очистки выберите папку для полного TXT. `SmartSkinNativeReport` повторяет сохранение последнего отчёта в этой сессии без пересчёта.

Передайте полный TXT. При снимке укажите видимое имя варианта. Хорошая форма сама по себе не подтверждает сопряжение. Этот выпуск не содержит рабочей замены медленного Build или новых слайдеров.

## Bounds and verification

There are at most three initial construction calls, one side-Blend call and two conditional new-support Split calls. Measurement, intersection and topology queries are additional native calls. The existing 45-second checkpoint budget and cancellation apply between calls; one opaque native call cannot be forcibly interrupted.

Support mapping and regularity are bounded finite screens. Global branch uniqueness, whole-surface G2, global nonintersection and oriented separation from all original owners remain **NOT VERIFIED**. Compound natural side rails can retain Match-support measurement eligibility; the separate Blend route reports unsupported compound binding explicitly. New native construction, Split behavior, actual timing and UI require a field run.

Managed tests and API compilation are **STATICALLY CHECKED** or **VERIFIED** only for their named layer. Delivery requires successful exact-SHA Windows CI, actual packaged Windows installer lifecycle checks, unchanged artifact bytes and manifest/assembly identity verification. Native Rhino execution is **NOT VERIFIED** by CI. Python runtime geometry, ordinary Build, toolbar identities and installer algorithms remain unchanged.

The first N4 Windows run found two test-only array reversal expressions that newer C# span overload resolution treated as an in-place operation returning void. The correction explicitly calls `Enumerable.Reverse` at both test sites. Test coverage and every production geometry/acceptance file remain unchanged; the corrected source requires a new exact-SHA CI run.
