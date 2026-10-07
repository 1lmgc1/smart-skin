# P08E1N5: first-candidate native Join check

Version: **0.0.26-p08e1n5**. This read-only test answers whether the first `EdgeSrf:Seed` candidate can join the selected parent edges. Join verifies topology and position separately from surface smoothness. It does not replace ordinary Build or relax its G1/G2 requirements.

## Native operation and evidence

`SmartSkinNativeCompare` now runs the raw EdgeSrf seed followed by one `Brep.JoinBreps` call on a fresh seed copy and fresh copies of the full owning Breps. It passes the captured document distance and angular tolerances unchanged. No Match, Blend, Split, extension, forced JoinEdge, parent trimming/rebuilding or tolerance increase runs in this focused path. Older diagnostic helpers are retained but not dispatched.

The TXT reports native Join timing, result count, validity, manifold/solid state, naked and nonmanifold edge counts and the input-contributor map. A single returned Brep is not automatically success: the selected source intervals and the complete seed boundary must correspond to ordinary two-face mated seams involving the seed and the correct parent face.

Fresh disposable face tags, unchanged underlying surface/domain evidence and the native contributor map qualify attribution after the Join call. If native output does not preserve that provenance, the native topology is still reported and selected-opening verification remains unresolved. It is not silently guessed or prevented by a pre-call tag assumption.

Both directions of boundary correspondence are checked at bounded span, feature and endpoint stations. Coincident unrelated edges, selected naked overlaps, nonmanifold seams or unresolved stations prevent a positive selected-opening label. Unrelated open boundaries elsewhere on the full parents are reported separately; the overall result may legitimately remain open at another end. Finite coverage does not establish exact whole-interval equality or full unchanged trim-region equivalence.

Original document geometry, captured parents and the raw seed are checked for changes. All temporary Join inputs/results are disposed. Nothing is added or replaced in the document, and no acceptance option is provided.

## Coherent curvature reporting

The N4 field audit identified a normal-orientation mismatch in the C# diagnostic on reversed Brep faces: a separately evaluated `NormalAt` can already include face reversal while the curvature result uses its own signed frame. The correction obtains Normal, Kappa and Direction from the same `SurfaceCurvature` result and applies face parity to the normal and full operator together.

This changes diagnostic frame interpretation, including the generic physical-join classifier. Native construction operators/settings and physical tolerances are unchanged; universal byte-identical output on every input is not claimed. Earlier reversed-face W magnitudes must not be treated as confirmed geometry error without corrected host evaluation. The millimeter source-to-support gaps are independent of this issue. Analytic plane/cylinder parity tests verify the arithmetic; corrected native values remain a field check.

Join is never gated on a successful G2 report and never relabeled G1/G2 because topology joined.

## Полевой запуск

1. Закройте все окна Rhino, распакуйте весь новый install ZIP и выполните `INSTALL.cmd`. После успешной установки откройте Rhino.
2. Выполните `SmartSurfaceVersion`: нужна версия `0.0.26-p08e1n5` и commit из проверенного CI-пакета.
3. Запустите `SmartSkinNativeCompare` и выберите тот же исходный замкнутый набор рёбер.
4. Первый просмотр — исходный `EdgeSrf:Seed`. `Next` показывает копию грани нового колпачка из результата Join, если её происхождение удалось однозначно проверить. Копии родителей не рисуются поверх исходников. Данные об общем соединённом Brep и его швах находятся в TXT.
5. Enter/Done или Esc закрывает просмотр и удаляет только временные кандидаты из памяти. Затем выберите папку для полного TXT. `SmartSkinNativeReport` повторяет сохранение последнего отчёта в этой сессии без пересчёта.

Передайте полный TXT. Успешный Join не подтверждает плавность, G2 или готовность основной команды Build. Исходные объекты документа не меняются.

## Verification boundary

Managed policy tests and compilation against RhinoCommon 8.21/net48 cover only their stated layers. Native Join, face-tag propagation, selected seam topology and actual timing require the Rhino field run. The existing 45-second checkpoint budget can cancel between native calls but cannot interrupt one opaque native operation.

Delivery retains the exact published separate-branch SHA, successful Windows CI, actual packaged Windows PowerShell5.1 installer tests and unchanged audited CI ZIP. The Python geometry runtime, one-button toolbar and installer algorithms remain unchanged. Main is not merged. All native G1/G2, global separation and production acceptance claims remain **NOT VERIFIED** in this diagnostic.
