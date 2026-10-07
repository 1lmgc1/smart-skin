using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Rhino;
using Rhino.Commands;
using Rhino.DocObjects;
using Rhino.Input;
using Rhino.Input.Custom;
using SmartSkin.Core;
using SmartSkin.Core.Construction;
using SmartSkin.Core.Preflight;
using SmartSkin.Core.Routing;

namespace SmartSkin.Rhino8;

public sealed class SmartSurfaceBuildCommand : Command
{
    private static bool _nativeBuildActive;

    public override string EnglishName => "SmartSurfaceBuild";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        if (_nativeBuildActive) return Result.Cancel;
        if (RhinoApp.Version.CompareTo(new Version(8, 21)) < 0) return Result.Failure;
        _nativeBuildActive = true;
        try { return NativeBuildWorkflow.Run(doc, mode); }
        finally { _nativeBuildActive = false; }
    }

    internal static Result RunPythonCommand(RhinoDoc doc, RunMode mode)
    {
        if (_nativeBuildActive)
        {
            RhinoApp.WriteLine("SMARTSKIN_P08E1 BLOCKED | code=PREVIEW_ALREADY_ACTIVE");
            return Result.Cancel;
        }
        // Explicit historical Python entry. Rhino 8's supported
        // ScriptEditor runner owns CPython and its pinned package environment.
        // No document object references cross RunScript's command boundary.
        var assemblyDirectory = Path.GetDirectoryName(typeof(SmartSurfaceBuildCommand).Assembly.Location);
        var entry = Path.Combine(assemblyDirectory ?? string.Empty, "Python", "smart_skin.py");
        if (!File.Exists(entry))
        {
            RhinoApp.WriteLine("SMARTSKIN_P08E1 BLOCKED | code=PYTHON_ASSETS_MISSING | reinstall the complete Smart Skin bundle");
            return Result.Failure;
        }
        if (RhinoApp.Version.CompareTo(new Version(8, 21)) < 0)
        {
            RhinoApp.WriteLine("SMARTSKIN_P08E1 BLOCKED | code=RHINO_821_REQUIRED");
            return Result.Failure;
        }
        // A quote is not a legal Windows filename character; fail closed on
        // other platforms instead of allowing an installation path as a macro.
        if (entry.IndexOf('"') >= 0 || entry.IndexOf('\n') >= 0 || entry.IndexOf('\r') >= 0)
            return Result.Failure;
        _nativeBuildActive = true;
        try
        {
            return RhinoApp.RunScript("_-ScriptEditor _Run \"" + entry + "\"", false)
                ? Result.Success : Result.Failure;
        }
        finally
        {
            _nativeBuildActive = false;
        }
    }

    // Preserved for historical diagnostics and review. The single visible
    // toolbar enters the bounded native seed/Join workflow above.
    internal static Result RunLegacyCommand(RhinoDoc doc, RunMode mode)
    {
        var objectCountBefore = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var identity = BuildIdentity.FromAssembly(typeof(SmartSurfaceBuildCommand).Assembly);

        using var selection = new GetObject();
        selection.SetCommandPrompt("Select boundary curves or Brep edges for Smart Skin; press Enter when done");
        selection.GeometryFilter = ObjectType.Curve
            | ObjectType.Surface
            | ObjectType.Brep
            | ObjectType.Extrusion;
        selection.SubObjectSelect = true;
        selection.GroupSelect = true;
        selection.GetMultiple(1, 0);

        var selectionResult = selection.CommandResult();
        if (selectionResult != Result.Success)
        {
            WriteSafeActionLine(
                identity,
                "CANCELLED",
                "P03_SELECTION_CANCELLED",
                "NONE",
                objectCountBefore,
                RhinoDocumentMetrics.ActiveObjectCount(doc));
            return selectionResult;
        }

        if (selection.ObjectCount > PreflightOptions.DefaultMaximumItems)
        {
            WriteSafeActionLine(
                identity,
                "BLOCKED",
                "P03_SELECTION_LIMIT",
                "NONE",
                objectCountBefore,
                RhinoDocumentMetrics.ActiveObjectCount(doc),
                $" | selected={selection.ObjectCount.ToString(CultureInfo.InvariantCulture)}"
                + $" | max={PreflightOptions.DefaultMaximumItems.ToString(CultureInfo.InvariantCulture)}");
            return Result.Success;
        }

        try
        {
            var snapshots = new List<GeometrySnapshot>(selection.ObjectCount);
            var references = new List<ObjRef>(selection.ObjectCount);
            for (var index = 0; index < selection.ObjectCount; index++)
            {
                var reference = selection.Object(index);
                references.Add(reference);
                var label = RhinoGeometrySnapshotFactory.CreateLabel(reference, index + 1);

                try
                {
                    snapshots.Add(RhinoGeometrySnapshotFactory.Create(
                        reference,
                        index + 1,
                        doc.ModelAbsoluteTolerance));
                }
                catch (Exception exception)
                {
                    snapshots.Add(GeometrySnapshot.Failed(
                        label,
                        $"Snapshot extraction failed ({exception.GetType().Name}): {exception.Message}"));
                }
            }

            var preflight = new GeometryPreflightAnalyzer().Analyze(
                snapshots,
                new PreflightOptions(doc.ModelAbsoluteTolerance));
            var route = new SurfaceStrategyRouter().Route(preflight);
            var construction = new CandidateConstructionPolicy().Evaluate(route, snapshots);

            WritePlan(identity, doc, preflight, route, construction);

            if (!construction.IsReady)
            {
                WriteSafeActionLine(
                    identity,
                    "BLOCKED",
                    construction.Code,
                    construction.StrategyToken,
                    objectCountBefore,
                    RhinoDocumentMetrics.ActiveObjectCount(doc));
                return Result.Success;
            }

            if (construction.Strategy == SurfaceStrategy.MatchSrf
                && RhinoApp.Version.CompareTo(new Version(8, 21)) < 0)
            {
                WriteSafeActionLine(
                    identity,
                    "BLOCKED",
                    "P07_RHINO_821_REQUIRED",
                    construction.StrategyToken,
                    objectCountBefore,
                    RhinoDocumentMetrics.ActiveObjectCount(doc),
                    $" | runtime={RhinoApp.Version} | minimum=8.21");
                return Result.Success;
            }

            var objectCountBeforeBuild = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountBeforeBuild != objectCountBefore)
            {
                WriteFailureLine(identity, "P03_DOCUMENT_MUTATED_BEFORE_BUILD", objectCountBefore, objectCountBeforeBuild);
                return Result.Failure;
            }

            var initialSettings = CandidateBuildSettings.Default;
            using var previewSession = new SmartSkinLivePreviewSession(
                doc,
                construction,
                references,
                doc.ModelAbsoluteTolerance,
                doc.ModelAngleToleranceRadians,
                initialSettings);
            var outcome = previewSession.Rebuild(initialSettings);

            RhinoApp.WriteLine(
                $"Candidate build: {(outcome.Success ? "READY" : "BLOCKED")}"
                + $"; code={outcome.Code}"
                + $"; reversed={outcome.ReversedCurveCount.ToString(CultureInfo.InvariantCulture)}"
                + $"; elapsed_ms={outcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)}"
                + BoundaryBuildDetails(construction, outcome, separator: ";")
                + $"; {outcome.Message}");

            if ((!outcome.Success || previewSession.Candidate is null)
                && construction.Strategy != SurfaceStrategy.MatchSrf)
            {
                WriteSafeActionLine(
                    identity,
                    "BLOCKED",
                    outcome.Code,
                    construction.StrategyToken,
                    objectCountBefore,
                    RhinoDocumentMetrics.ActiveObjectCount(doc),
                    $" | stage=BUILD"
                    + BoundaryBuildDetails(construction, outcome, separator: " |")
                    + $" | elapsed_ms={outcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)}");
                return Result.Success;
            }

            var objectCountBeforePreview = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountBeforePreview != objectCountBefore)
            {
                WriteFailureLine(identity, "P03_DOCUMENT_MUTATED_BEFORE_PREVIEW", objectCountBefore, objectCountBeforePreview);
                return Result.Failure;
            }

            var previewResult = GetPreviewDecision(doc, construction, previewSession);
            var finalOutcome = previewSession.CurrentOutcome ?? outcome;
            if (!previewResult.Accepted)
            {
                WriteSafeActionLine(
                    identity,
                    "CANCELLED",
                    previewResult.Code,
                    construction.StrategyToken,
                    objectCountBefore,
                    RhinoDocumentMetrics.ActiveObjectCount(doc),
                    $" | built={(finalOutcome.Success ? "1" : "0")}"
                    + $" | added=0"
                    + $" | build_code={finalOutcome.Code}"
                    + BoundaryBuildDetails(construction, finalOutcome, separator: " |")
                    + $" | reversed={finalOutcome.ReversedCurveCount.ToString(CultureInfo.InvariantCulture)}"
                    + $" | elapsed_ms={finalOutcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)}");
                return previewResult.CommandResult;
            }

            var objectCountAfterPreview = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountAfterPreview != objectCountBefore)
            {
                WriteFailureLine(identity, "P03_DOCUMENT_MUTATED_DURING_PREVIEW", objectCountBefore, objectCountAfterPreview);
                return Result.Failure;
            }

            var candidate = finalOutcome.CommitBrep;
            if (candidate is null || !finalOutcome.Success)
            {
                WriteFailureLine(identity, "P07_ACCEPT_WITHOUT_CANDIDATE", objectCountBefore, objectCountAfterPreview);
                return Result.Failure;
            }

            if (!CommitResult(doc, finalOutcome, out var addedCount, out var replacedCount, out var commitCode))
            {
                WriteFailureLine(identity, commitCode, objectCountBefore, RhinoDocumentMetrics.ActiveObjectCount(doc));
                return Result.Failure;
            }

            doc.Views.Redraw();
            var objectCountAfter = RhinoDocumentMetrics.ActiveObjectCount(doc);
            var expectedObjectCount = objectCountBefore + addedCount - replacedCount;
            if (objectCountAfter != expectedObjectCount)
            {
                WriteFailureLine(identity, "P07_COMMIT_COUNT_MISMATCH", objectCountBefore, objectCountAfter);
                return Result.Failure;
            }

            RhinoApp.WriteLine(
                $"SMARTSKIN_{identity.Patch} PASS"
                + $" | version={identity.Version}"
                + $" | commit={identity.Commit}"
                + $" | strategy={construction.StrategyToken}"
                + " | action=ACCEPTED"
                + " | code=P07_ACCEPTED"
                + " | built=1"
                + $" | added={addedCount.ToString(CultureInfo.InvariantCulture)}"
                + $" | replaced={replacedCount.ToString(CultureInfo.InvariantCulture)}"
                + BoundaryBuildDetails(construction, finalOutcome, separator: " |")
                + $" | reversed={finalOutcome.ReversedCurveCount.ToString(CultureInfo.InvariantCulture)}"
                + $" | elapsed_ms={finalOutcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)}"
                + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}");
            return Result.Success;
        }
        catch (Exception exception)
        {
            var objectCountAfterFailure = RhinoDocumentMetrics.ActiveObjectCount(doc);
            RhinoApp.WriteLine(
                $"SMARTSKIN_{identity.Patch} FAIL"
                + $" | version={identity.Version}"
                + $" | commit={identity.Commit}"
                + " | code=P03_UNHANDLED"
                + $" | exception={exception.GetType().Name}"
                + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfterFailure.ToString(CultureInfo.InvariantCulture)}");
            return Result.Failure;
        }
    }

    private static PreviewDecision GetPreviewDecision(
        RhinoDoc doc,
        CandidateConstructionPlan construction,
        SmartSkinLivePreviewSession previewSession)
    {
        using var form = new SmartSkinPreviewForm(doc, construction, previewSession);
        form.Show();

        try
        {
            using var decision = new GetOption();
            decision.SetCommandPrompt("Smart Skin preview: adjust the settings window; Enter, Space, or right-click adds; Esc cancels");
            decision.AcceptNothing(true);
            decision.SetWaitDuration(100);

            while (true)
            {
                if (form.AcceptRequested)
                {
                    return new PreviewDecision(true, Result.Success, "P07_ACCEPTED");
                }

                if (form.CancelRequested || !form.Visible)
                {
                    return new PreviewDecision(false, Result.Cancel, "P07_PREVIEW_CANCELLED");
                }

                var getResult = decision.Get();
                if (form.AcceptRequested)
                {
                    return new PreviewDecision(true, Result.Success, "P07_ACCEPTED");
                }

                if (form.CancelRequested || !form.Visible)
                {
                    return new PreviewDecision(false, Result.Cancel, "P07_PREVIEW_CANCELLED");
                }

                if (getResult == GetResult.Timeout)
                {
                    continue;
                }

                if (getResult == GetResult.Nothing)
                {
                    if (form.PrepareForAcceptance())
                    {
                        return new PreviewDecision(true, Result.Success, "P07_ACCEPTED");
                    }

                    continue;
                }

                var commandResult = decision.CommandResult();
                return new PreviewDecision(
                    false,
                    commandResult == Result.Success ? Result.Cancel : commandResult,
                    "P07_PREVIEW_CANCELLED");
            }
        }
        finally
        {
            form.CloseForCommand();
        }
    }

    private static string BoundaryBuildDetails(
        CandidateConstructionPlan construction,
        CandidateBuildOutcome outcome,
        string separator)
    {
        if (!construction.UsesBoundaryMatch)
        {
            return string.Empty;
        }

        var settings = outcome.Settings;
        var metrics = outcome.Metrics;
        return $"{separator} supports={outcome.SupportedEdgeCount.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} parents={outcome.ParentObjectCount.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} proved_target_edges={outcome.JoinedSeamCount.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} continuity={settings.ContinuityToken}"
            + $"{separator} verified={(metrics?.Token ?? "NOT_MEASURED")}"
            + $"{separator} max_gap={FormatMetric(metrics?.MaximumGap)}"
            + $"{separator} sampled_max_normal_deg={FormatMetric(metrics?.MaximumNormalAngleDegrees)}"
            + $"{separator} sampled_max_curvature_pct={FormatMetric(metrics?.MaximumCurvatureDeviationPercent)}"
            + $"{separator} samples={(metrics?.SampleCount ?? 0).ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} refine={(settings.RefineMatch ? "ON" : "OFF")}"
            + $"{separator} curvature_tolerance_pct={settings.CurvatureTolerancePercent.ToString("G4", CultureInfo.InvariantCulture)}"
            + $"{separator} average={(settings.AverageSurfaces ? "ON" : "OFF")}"
            + $"{separator} reverse_match={(outcome.ReverseMatchDirection ? "ON" : "OFF")}"
            + $"{separator} reverse_average_target={(outcome.ReverseAverageTargetDirection ? "ON" : "OFF")}"
            + $"{separator} attribute_policy={(settings.AverageSurfaces ? "FIRST_PARENT" : "SOURCES_PRESERVED")}"
            + $"{separator} iso={settings.IsoDirection.ToString().ToUpperInvariant()}";
    }

    private static bool CommitResult(
        RhinoDoc doc,
        CandidateBuildOutcome outcome,
        out int addedCount,
        out int replacedCount,
        out string failureCode)
    {
        addedCount = 0;
        replacedCount = 0;
        failureCode = "P07_COMMIT_FAILED";
        var commitBrep = outcome.CommitBrep;
        if (!outcome.Success || commitBrep is null)
        {
            failureCode = "P07_COMMIT_WITHOUT_RESULT";
            return false;
        }

        if (!outcome.ReplacesSources)
        {
            var addedId = doc.Objects.AddBrep(commitBrep);
            if (addedId == Guid.Empty)
            {
                failureCode = "P07_ADD_FAILED";
                return false;
            }

            addedCount = 1;
            return true;
        }

        if (outcome.ParentObjectIds.Count == 0)
        {
            failureCode = "P07_AVERAGE_WITHOUT_PARENTS";
            return false;
        }

        if (!doc.UndoRecordingEnabled
            || !doc.UndoRecordingIsActive
            || doc.CurrentUndoRecordSerialNumber == 0)
        {
            failureCode = "P07_AVERAGE_UNDO_UNAVAILABLE";
            return false;
        }

        var undoRecordSerial = doc.CurrentUndoRecordSerialNumber;
        var activeCountBeforeCommit = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var parents = new List<RhinoObject>(outcome.ParentObjectIds.Count);
        var uniqueParentIds = new HashSet<Guid>();
        foreach (var parentId in outcome.ParentObjectIds)
        {
            if (!uniqueParentIds.Add(parentId))
            {
                failureCode = "P07_AVERAGE_PARENT_DUPLICATE";
                return false;
            }

            var parent = doc.Objects.FindId(parentId);
            if (parent is null || parent.IsDeleted)
            {
                failureCode = "P07_AVERAGE_PARENT_CHANGED";
                return false;
            }

            if (!parent.IsDeletable || parent.IsReference || parent.IsLocked)
            {
                failureCode = "P07_AVERAGE_PARENT_NOT_EDITABLE";
                return false;
            }

            parents.Add(parent);
        }

        using var attributes = parents[0].Attributes.Duplicate();
        var resultId = doc.Objects.AddBrep(commitBrep, attributes);
        if (resultId == Guid.Empty)
        {
            failureCode = "P07_AVERAGE_ADD_FAILED";
            return false;
        }

        addedCount = 1;
        var deletedParents = new List<RhinoObject>(parents.Count);
        foreach (var parent in parents)
        {
            if (doc.Objects.Delete(parent, quiet: true))
            {
                deletedParents.Add(parent);
                continue;
            }

            var rollbackComplete = TryRollbackAverageResult(
                doc,
                resultId,
                deletedParents,
                outcome.ParentObjectIds,
                activeCountBeforeCommit);
            addedCount = rollbackComplete ? 0 : 1;
            failureCode = rollbackComplete
                ? "P07_AVERAGE_DELETE_FAILED"
                : "P07_AVERAGE_ROLLBACK_FAILED";
            return false;
        }

        var committedResult = doc.Objects.FindId(resultId);
        var everyParentInactive = outcome.ParentObjectIds.All(parentId =>
        {
            var source = doc.Objects.FindId(parentId);
            return source is null || source.IsDeleted;
        });
        var expectedActiveCount = activeCountBeforeCommit + 1 - parents.Count;
        var commitPostcondition = committedResult is not null
            && !committedResult.IsDeleted
            && everyParentInactive
            && RhinoDocumentMetrics.ActiveObjectCount(doc) == expectedActiveCount
            && doc.UndoRecordingIsActive
            && doc.CurrentUndoRecordSerialNumber == undoRecordSerial;
        if (!commitPostcondition)
        {
            var rollbackComplete = TryRollbackAverageResult(
                doc,
                resultId,
                deletedParents,
                outcome.ParentObjectIds,
                activeCountBeforeCommit);
            addedCount = rollbackComplete ? 0 : 1;
            failureCode = rollbackComplete
                ? "P07_AVERAGE_COMMIT_POSTCONDITION_FAILED"
                : "P07_AVERAGE_ROLLBACK_FAILED";
            return false;
        }

        replacedCount = deletedParents.Count;
        return true;
    }

    private static bool TryRollbackAverageResult(
        RhinoDoc doc,
        Guid resultId,
        IReadOnlyList<RhinoObject> deletedParents,
        IReadOnlyList<Guid> parentObjectIds,
        int expectedActiveCount)
    {
        var resultObject = doc.Objects.FindId(resultId);
        var resultRemoved = resultObject is null
            || resultObject.IsDeleted
            || doc.Objects.Delete(resultId, quiet: true);
        var everyParentRestored = true;
        foreach (var deletedParent in deletedParents)
        {
            everyParentRestored &= doc.Objects.Undelete(deletedParent);
        }

        resultObject = doc.Objects.FindId(resultId);
        var resultInactive = resultObject is null || resultObject.IsDeleted;
        var everyParentActive = parentObjectIds.All(parentId =>
        {
            var restored = doc.Objects.FindId(parentId);
            return restored is not null && !restored.IsDeleted;
        });
        return resultRemoved
            && everyParentRestored
            && resultInactive
            && everyParentActive
            && RhinoDocumentMetrics.ActiveObjectCount(doc) == expectedActiveCount;
    }

    private static string FormatMetric(double? value)
    {
        if (!value.HasValue || double.IsNaN(value.Value))
        {
            return "n/a";
        }

        if (double.IsPositiveInfinity(value.Value))
        {
            return "inf";
        }

        return value.Value.ToString("G6", CultureInfo.InvariantCulture);
    }

    private static void WritePlan(
        BuildIdentity identity,
        RhinoDoc doc,
        PreflightReport preflight,
        SurfaceRouteReport route,
        CandidateConstructionPlan construction)
    {
        RhinoApp.WriteLine("Smart Skin bounded candidate construction");
        RhinoApp.WriteLine($"Patch: {identity.Patch}");
        RhinoApp.WriteLine($"Version: {identity.Version}");
        RhinoApp.WriteLine($"Commit: {identity.Commit}");
        RhinoApp.WriteLine($"Units: {doc.ModelUnitSystem}");
        RhinoApp.WriteLine("Mode: one live settings window and measured in-memory preview; Enter/Space/right-click commits; Esc cancels; Average surfaces explicitly replaces owning Breps.");
        RhinoApp.WriteLine(
            $"Preflight: {preflight.Status.ToString().ToUpperInvariant()}"
            + $"; warnings={preflight.WarningCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; errors={preflight.ErrorCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; near_gaps={preflight.NearGapCount.ToString(CultureInfo.InvariantCulture)}");

        foreach (var line in route.ToDisplayLines())
        {
            RhinoApp.WriteLine(line);
        }

        RhinoApp.WriteLine(construction.ToDisplayLine());
    }

    private static void WriteSafeActionLine(
        BuildIdentity identity,
        string action,
        string code,
        string strategy,
        int objectCountBefore,
        int objectCountAfter,
        string suffix = "")
    {
        var invariant = objectCountBefore == objectCountAfter ? "PASS" : "FAIL";
        RhinoApp.WriteLine(
            $"SMARTSKIN_{identity.Patch} {invariant}"
            + $" | version={identity.Version}"
            + $" | commit={identity.Commit}"
            + $" | strategy={strategy}"
            + $" | action={action}"
            + $" | code={code}"
            + suffix
            + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}");
    }

    private static void WriteFailureLine(
        BuildIdentity identity,
        string code,
        int objectCountBefore,
        int objectCountAfter)
    {
        RhinoApp.WriteLine(
            $"SMARTSKIN_{identity.Patch} FAIL"
            + $" | version={identity.Version}"
            + $" | commit={identity.Commit}"
            + $" | code={code}"
            + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}");
    }

    private readonly struct PreviewDecision
    {
        public PreviewDecision(bool accepted, Result commandResult, string code)
        {
            Accepted = accepted;
            CommandResult = commandResult;
            Code = code;
        }

        public bool Accepted { get; }

        public Result CommandResult { get; }

        public string Code { get; }
    }
}
