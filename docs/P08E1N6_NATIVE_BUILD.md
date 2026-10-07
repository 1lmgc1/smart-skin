# P08E1N6: native Build for user testing

Version **0.0.27-p08e1n6**. The existing Smart Skin button and `SmartSurfaceBuild` use the first native EdgeSrf candidate, with the explicit status **«стыковка без гарантии плавности»**. This scope was approved for user testing. It does not establish G1/G2 or general production stability.

## Construction and evidence

The command derives the logical boundary from the selected original edges and parent faces, creates one EdgeSrf candidate, and tests one Join on full disposable parent copies. It does not construct the former fixed profile network or invoke Python as a fallback. Parent objects and their geometric loci remain unchanged.

N5's native field run returned a valid manifold 11-face Join in 8 ms, within a 258 ms diagnostic run. Its optional contributor map was null, so the earlier implementation did not reach the selected-seam checks. N6 accepts absence of that optional map only when every input face has a unique surviving tag and unchanged underlying surface/domain. A supplied map must agree. Selected-seam and isolated-cap boundary checks still have to pass on the current run; an output count of one is insufficient.

The cap receives bounded validity/regularity checks. These are finite screens, not proofs of global injectivity, separation or smooth attachment. The preview states the actual result and never turns a successful Join into a G1/G2 claim.

## Preview and document changes

The new cap is displayed from cached geometry/meshes. No surface is added while preparing or viewing. A distinct confirmation adds exactly that cap. The full joined assembly contains parent copies and is never added to the document. The resulting document therefore retains the original separate parents and one new surface; it is not automatically replaced by one joined body.

Acceptance binds the visible geometry to the current source objects, document, units and tolerances. It uses the active Undo record of the normal Rhino command. A changed source/candidate or failed Add postcondition rejects the transaction; cleanup removes only positively identified newly created objects. Esc or closing the preview leaves no additions.

No U/V sliders are shown in this native test route. The earlier experimental Python workflow remains explicitly available as `SmartSurfaceBuildPython`; `SmartSurfaceBuildLegacy` retains the older implementation. Neither is an automatic fallback. `SmartSkinNativeCompare` remains read-only.

## Полевой тест

1. Закройте все окна Rhino, полностью распакуйте новый install ZIP и выполните `INSTALL.cmd`.
2. После открытия Rhino проверьте `SmartSurfaceVersion`: `0.0.27-p08e1n6`, commit из проверенного пакета.
3. Нажмите существующую кнопку Smart Skin или выполните `SmartSurfaceBuild`. Выберите исходный замкнутый набор рёбер.
4. Дождитесь результата проверок. В окне должна быть надпись **«стыковка без гарантии плавности»**. Осмотрите поверхность и отдельно подтвердите её; Esc или закрытие окна отменяет создание.
5. После успешного добавления проверьте один Undo, затем Redo. Исходные объекты должны сохраниться; добавляется только новый колпачок.
6. Сохраните полный TXT в выбранную папку. `SmartSkinNativeReport` повторяет сохранение последнего отчёта в этой сессии без пересчёта.

Передайте TXT и результат проверки добавления, отмены, Undo/Redo. Если текущие геометрические проверки блокируют добавление, отчёт должен назвать причину; блокировка не запускает медленный запасной конструктор.

## Verification boundary

Managed tests exercise the same transaction runner used by the native adapter, including stale confirmation, cancellation, source/candidate changes, Add exceptions and bounded new-object rollback. Compilation targets the pinned RhinoCommon 8.21/net48 SDK. Exact-SHA Windows CI checks packaging and the actual installer lifecycle.

Those tests do not execute the Rhino host. Current native seam qualification, regularity screen behavior, window/input coexistence, Enter/Space/right-click, Undo/Redo and final timing require this field test. Native calls cannot be force-interrupted; cancellation is checked between them. No claim of full G2, parent-region equivalence or globally collision-free geometry is made.
