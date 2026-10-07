using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Rhino;
using Rhino.Commands;
using Rhino.DocObjects;
using Rhino.Geometry;
using Rhino.Input;
using Rhino.Input.Custom;
using SmartSkin.Core;

namespace SmartSkin.Rhino8;

internal static class NativeBuildWorkflow
{
    internal static Result Run(RhinoDoc document, RunMode mode)
    {
        var report = new NativeCompareReportBuffer(DateTime.UtcNow, Guid.NewGuid().ToString("N"));
        var result = Result.Failure;
        var failureReason = string.Empty;
        var createdId = Guid.Empty;
        NativeCompareReportCapture.Run(report, NativeCompareReportExport.Store, NativeCompareReportExport.Message, write =>
        {
            var identity = BuildIdentity.FromAssembly(typeof(SmartSurfaceBuildCommand).Assembly);
            write("SMARTSKIN_NATIVE_REPORT_START | command=SmartSurfaceBuild | report_id=" + report.ReportId
                + " | started_utc=" + report.StartedUtc.ToString("O") + " | version=" + identity.Version + " | commit=" + identity.Commit
                + " | rhino=" + RhinoApp.Version + " | runtime=" + RuntimeInformation.FrameworkDescription
                + " | model_units=" + document.ModelUnitSystem + " | absolute_tolerance=" + NativeCompareProbeProtocol.Number(document.ModelAbsoluteTolerance)
                + " | angle_tolerance_radians=" + NativeCompareProbeProtocol.Number(document.ModelAngleToleranceRadians)
                + " | user_status=" + NativeBuildCapQualification.UserStatus + " | run_mode=" + mode);
            result = Execute(document, mode, write, out failureReason, out createdId); return result.ToString();
        });
        // Functional Build ends in a surface or a visible reason. The complete report is
        // retained in-session and can be saved explicitly with SmartSkinNativeReport.
        if (result == Result.Failure && mode == RunMode.Interactive)
            Rhino.UI.Dialogs.ShowMessage("Поверхность не создана.\n" + FailureDescription(failureReason), "Smart Skin");
        else if (result == Result.Success && createdId != Guid.Empty)
        {
            // Presentation follows the completed transaction and native cleanup. It cannot
            // roll back a valid cap, and never changes any existing object's selection.
            try { document.Objects.Select(createdId); } catch { }
            try { document.Views.Redraw(); } catch { }
            try { RhinoApp.WriteLine("Поверхность создана. Добавлен 1 объект. Undo отменяет добавление."); } catch { }
        }
        return result;
    }

    private static string FailureDescription(string reason)
    {
        if (reason.StartsWith("BUILD_ROLLBACK_INCOMPLETE", StringComparison.Ordinal))
            return "Не удалось завершить добавление и полностью отменить его. Проверьте новую поверхность в модели.\n" + reason;
        if (reason.Contains("UNDO")) return "Запись Undo недоступна; добавление остановлено.\n" + reason;
        if (reason.Contains("JOIN") || reason.Contains("BOUNDARY") || reason.Contains("SEAM"))
            return "Не удалось подтвердить стыковку новой поверхности со всеми выбранными рёбрами.\n" + reason;
        if (reason.Contains("NONREGULAR") || reason.Contains("RANK") || reason.Contains("VALIDITY"))
            return "Кандидат не прошёл проверку корректности поверхности.\n" + reason;
        if (reason.Contains("CHANGED") || reason.Contains("MISMATCH"))
            return "Модель или подготовленный кандидат изменились; добавление остановлено.\n" + reason;
        return string.IsNullOrEmpty(reason) ? "Операция завершилась ошибкой до добавления." : reason;
    }

    private static Result Execute(RhinoDoc doc, RunMode mode, Action<string> write, out string failureReason, out Guid createdId)
    {
        failureReason = string.Empty; createdId = Guid.Empty;
        var beforeCount = RhinoDocumentMetrics.ActiveObjectCount(doc);
        NativeCompareInput? input = null; NativeSeedJoinResult? join = null;
        NativeCompareCandidate? candidate = null; NativeBuildDocumentAdapter? adapter = null;
        NativeBuildPreview? preview = null; NativeBuildStatusForm? form = null; NativeBuildMouseConfirmation? mouse = null;
        var controller = new NativeBuildController();
        var watch = new Stopwatch(); long lastPump = -50;
        NativeBuildTransaction.Result? transaction = null;
        void Escape(object? sender, EventArgs args)
        { controller.Cancel(); form?.Cancel(); }
        void Keyboard(int key)
        {
            if (key == 16 || key == 17 || key == 18 || key == 91 || key == 92)
            { mouse?.CancelGesture(); controller.InputContextLost(); }
            if (RhinoDoc.ActiveDoc?.RuntimeSerialNumber == doc.RuntimeSerialNumber && NativeBuildPhysicalInput.ConfirmationEventAllowed(key))
                controller.ConfirmationInput();
        }
        void Checkpoint()
        {
            if (watch.ElapsedMilliseconds - lastPump >= 50) { lastPump = watch.ElapsedMilliseconds; RhinoApp.Wait(); }
            if (controller.Cancelled || doc.IsClosing) throw new OperationCanceledException();
            if (watch.ElapsedMilliseconds > 45000) throw new TimeoutException("NATIVE_BUILD_TIME_BUDGET_EXHAUSTED");
        }
        try
        {
            if (!NativeBuildPhysicalInput.Supported) throw new NativeCompareUnsupported("BUILD_WINDOWS_PHYSICAL_CONFIRMATION_REQUIRED");
            if (mode != RunMode.Interactive) throw new NativeCompareUnsupported("BUILD_REQUIRES_INTERACTIVE_FRESH_CONFIRMATION");
            using var selection = new GetObject();
            selection.SetCommandPrompt("Smart Skin: выберите замкнутый контур из открытых рёбер исходных поверхностей");
            selection.GeometryFilter = ObjectType.Curve; selection.SubObjectSelect = true; selection.GroupSelect = false;
            selection.GetMultiple(4, 32);
            if (selection.CommandResult() != Result.Success) return selection.CommandResult();
            watch.Start(); RhinoApp.EscapeKeyPressed += Escape;
            input = NativeCompareInput.Capture(doc, selection, Checkpoint);
            write("SMARTSKIN_NATIVE_BUILD_PLAN | selected_edges=" + input.Edges.Count + " | owners=" + input.Owners.Count
                + " | derivation=" + input.Derivation + " | seed_calls=1 | join_calls=1 | fallback=NONE");
            NativeCompareSideBinding.TraceSources(input, write);
            var curves = new List<Curve>();
            Brep? seed = null;
            try
            {
                for (var side = 0; side < 4; side++) curves.Add(input.SideCurve(side));
                Checkpoint(); var native = Stopwatch.StartNew();
                seed = Brep.CreateEdgeSurface(curves);
                var milliseconds = native.ElapsedMilliseconds;
                if (seed is null || !NativeCompareMeasure.Bounded(seed, out _)) throw new NativeCompareUnsupported("BUILD_NATIVE_SEED_INVALID");
                write("SMARTSKIN_NATIVE_BUILD_SEED | native_ms=" + milliseconds + " | valid=true | candidate=FIRST_EDGESRF_SEED");
                join = NativeSeedJoinExperiment.Run(seed, input, null, Checkpoint, write);
            }
            finally { seed?.Dispose(); foreach (var curve in curves) curve.Dispose(); }
            var qualification = NativeBuildCapQualification.Evaluate(join, input, Checkpoint, write);
            if (!qualification.Ready || join.Cap is null) throw new NativeCompareUnsupported(qualification.Reason);
            if (!input.SourcesUnchanged(doc) || !input.CopiesUnchanged()) throw new NativeCompareUnsupported("BUILD_SOURCES_CHANGED_DURING_PREPARATION");
            var copy = join.Cap.DuplicateBrep();
            try { candidate = new NativeCompareCandidate("First native cap", copy); copy = null!; }
            finally { copy?.Dispose(); }
            if (input.GeometryFingerprint(candidate.Brep) != input.GeometryFingerprint(join.Cap))
                throw new NativeCompareUnsupported("BUILD_PREVIEW_COPY_ARCHIVE_MISMATCH");
            adapter = new NativeBuildDocumentAdapter(doc, input, candidate.Brep, qualification, controller);
            var displayed = adapter.CaptureState();
            if (!displayed.IsWellFormed) throw new NativeCompareUnsupported("BUILD_ACTIVE_COMMAND_UNDO_OR_RECEIPT_UNAVAILABLE");
            preview = new NativeBuildPreview(doc, candidate) { Enabled = true };
            form = new NativeBuildStatusForm(doc, controller); form.Show();
            mouse = new NativeBuildMouseConfirmation(doc, controller) { Enabled = true };
            RhinoApp.KeyboardEvent += Keyboard;
            controller.Prepared(); form.Prepared(); doc.Views.Redraw();
            write("SMARTSKIN_NATIVE_BUILD_PREVIEW | prepared_ms=" + watch.ElapsedMilliseconds
                + " | cached_meshes=" + candidate.Meshes.Length + " | user_status=" + NativeBuildCapQualification.UserStatus
                + " | confirmation=EXPLICIT_CREATE_BUTTON_OR_RELEASE_THEN_FRESH_INPUT | physical_state=WINDOWS_CURRENT_HIGH_BIT | commit_geometry=ISOLATED_CAP_ONLY | G1_G2=NOT_VERIFIED");
            using var decision = new GetOption();
            decision.SetCommandPrompt("Smart Skin: «Создать поверхность» или Enter/Space/правая кнопка; Esc — отменить");
            decision.AcceptNothing(true); decision.SetWaitDuration(100);
            while (controller.Current != NativeBuildController.Phase.Confirming)
            {
                if (controller.Current == NativeBuildController.Phase.Invalidated || doc.IsClosing)
                    throw new NativeCompareUnsupported("BUILD_MODEL_CHANGED_DURING_PREVIEW");
                if (controller.Cancelled || !form.Visible) return Result.Cancel;
                if (!adapter.PreviewMetadataCurrent(displayed))
                { controller.Invalidate(); throw new NativeCompareUnsupported("BUILD_MODEL_CHANGED_DURING_PREVIEW"); }
                var answer = decision.Get();
                if (controller.Current == NativeBuildController.Phase.Invalidated)
                    throw new NativeCompareUnsupported("BUILD_MODEL_CHANGED_DURING_PREVIEW");
                if (controller.Cancelled || !form.Visible) return Result.Cancel;
                if (controller.Current == NativeBuildController.Phase.Confirming) break;
                if (answer == GetResult.Timeout)
                { mouse.Idle(); controller.IdleGetCycle(NativeBuildPhysicalInput.ConfirmationInputsReleased, NativeBuildPhysicalInput.ContextAvailable); if (controller.Current == NativeBuildController.Phase.Ready) form.Ready(); continue; }
                if (answer == GetResult.Nothing)
                {
                    if (controller.BeginConfirmation()) break;
                    write("SMARTSKIN_NATIVE_BUILD_INPUT | ignored=NO_FRESH_POST_READY_CONFIRMATION");
                    continue;
                }
                controller.Cancel(); return Result.Cancel;
            }
            transaction = NativeBuildTransaction.Run(adapter, new NativeBuildTransaction.Confirmation(displayed), adapter.Acceptance(displayed));
            if (transaction.Status == NativeBuildTransaction.Outcome.Added)
            { controller.Added(); createdId = transaction.AddedObjectId; }
            else failureReason = transaction.Cleanup == NativeBuildTransaction.Rollback.Incomplete
                ? "BUILD_ROLLBACK_INCOMPLETE: " + transaction.Reason : transaction.Reason;
            write("SMARTSKIN_NATIVE_BUILD_TRANSACTION | status=" + transaction.Status + " | reason=" + transaction.Reason
                + " | added_id=" + transaction.AddedObjectId + " | add_attempted=" + transaction.AddAttempted
                + " | rollback=" + transaction.Cleanup + " | parent_replacements=0 | user_status=" + NativeBuildCapQualification.UserStatus);
            return transaction.Status == NativeBuildTransaction.Outcome.Added ? Result.Success
                : transaction.Status == NativeBuildTransaction.Outcome.Cancelled && controller.Current != NativeBuildController.Phase.Invalidated
                    ? Result.Cancel : Result.Failure;
        }
        catch (OperationCanceledException) { write("SMARTSKIN_NATIVE_BUILD_END | status=CANCELLED"); return Result.Cancel; }
        catch (NativeCompareUnsupported error)
        { failureReason = error.Message; write("SMARTSKIN_NATIVE_BUILD_END | status=" + error.Message); return Result.Failure; }
        catch (Exception error)
        {
            failureReason = error.GetType().Name + ": " + error.Message;
            write("SMARTSKIN_NATIVE_BUILD_END | status=" + (transaction?.Status == NativeBuildTransaction.Outcome.Added ? "ADDED_REPORT_ERROR" : "FAILED")
                + " | type=" + error.GetType().Name);
            return transaction?.Status == NativeBuildTransaction.Outcome.Added ? Result.Success : Result.Failure;
        }
        finally
        {
            var failures = new List<string>();
            NativeCompareReportCleanup.Attempt("escape", () => RhinoApp.EscapeKeyPressed -= Escape, failures);
            NativeCompareReportCleanup.Attempt("keyboard", () => RhinoApp.KeyboardEvent -= Keyboard, failures);
            NativeCompareReportCleanup.Attempt("mouse", () => mouse?.Dispose(), failures);
            var previewDisposed = NativeCompareReportCleanup.Attempt("preview", () => preview?.Dispose(), failures);
            NativeCompareReportCleanup.Attempt("form_close", () => form?.CloseForCommand(), failures);
            NativeCompareReportCleanup.Attempt("form", () => form?.Dispose(), failures);
            NativeCompareReportCleanup.Attempt("adapter", () => adapter?.Dispose(), failures);
            var sourceUnchanged = false; var copiesUnchanged = false;
            NativeCompareReportCleanup.Attempt("source_archive", () => sourceUnchanged = input?.SourcesUnchanged(doc) ?? false, failures);
            NativeCompareReportCleanup.Attempt("copy_archive", () => copiesUnchanged = input?.CopiesUnchanged() ?? false, failures);
            NativeCompareReportCleanup.Attempt("candidate", () => candidate?.Dispose(), failures);
            NativeCompareReportCleanup.Attempt("join_cap", () => join?.Dispose(), failures);
            NativeCompareReportCleanup.Attempt("input", () => input?.Dispose(), failures);
            NativeCompareReportCleanup.Attempt("redraw", () => doc.Views.Redraw(), failures);
            var afterCount = "NOT_VERIFIED";
            NativeCompareReportCleanup.Attempt("object_count", () => afterCount = RhinoDocumentMetrics.ActiveObjectCount(doc).ToString(), failures);
            write(NativeCompareReportBuffer.CleanupPrefix + " command=SmartSurfaceBuild | document_objects=" + beforeCount + "->" + afterCount
                + " | source_archive=" + (sourceUnchanged ? "VERIFIED_UNCHANGED" : "NOT_VERIFIED")
                + " | captured_copy_archive=" + (copiesUnchanged ? "VERIFIED_UNCHANGED" : "NOT_VERIFIED")
                + " | transaction=" + (transaction?.Status.ToString() ?? "NO_ADD_ATTEMPT")
                + " | added=" + (transaction?.Status == NativeBuildTransaction.Outcome.Added ? "1"
                    : transaction?.Cleanup == NativeBuildTransaction.Rollback.Incomplete ? "NOT_VERIFIED" : "0")
                + " | rollback=" + (transaction?.Cleanup.ToString() ?? "NotNeeded") + " | replaced=0"
                + " | preview_disposed=" + previewDisposed + " | cleanup_failures=" + (failures.Count == 0 ? "NONE" : string.Join(",", failures)));
        }
    }
}
