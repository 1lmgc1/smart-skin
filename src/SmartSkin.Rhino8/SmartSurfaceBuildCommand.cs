using System;
using System.Collections.Generic;
using System.Globalization;
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
    public override string EnglishName => "SmartSurfaceBuild";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
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

            var objectCountBeforeBuild = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountBeforeBuild != objectCountBefore)
            {
                WriteFailureLine(identity, "P03_DOCUMENT_MUTATED_BEFORE_BUILD", objectCountBefore, objectCountBeforeBuild);
                return Result.Failure;
            }

            var initialSettings = CandidateBuildSettings.Balanced;
            using var previewSession = new SmartSkinLivePreviewSession(
                doc,
                construction,
                references,
                doc.ModelAbsoluteTolerance,
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
                && construction.Strategy != SurfaceStrategy.Patch)
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

            var candidate = previewSession.Candidate;
            if (candidate is null || !finalOutcome.Success)
            {
                WriteFailureLine(identity, "P06_ACCEPT_WITHOUT_CANDIDATE", objectCountBefore, objectCountAfterPreview);
                return Result.Failure;
            }

            var addedId = doc.Objects.AddBrep(candidate);
            if (addedId == Guid.Empty)
            {
                WriteFailureLine(identity, "P03_ADD_FAILED", objectCountBefore, RhinoDocumentMetrics.ActiveObjectCount(doc));
                return Result.Failure;
            }

            doc.Views.Redraw();
            var objectCountAfter = RhinoDocumentMetrics.ActiveObjectCount(doc);
            if (objectCountAfter != objectCountBefore + 1)
            {
                WriteFailureLine(identity, "P03_ADD_COUNT_MISMATCH", objectCountBefore, objectCountAfter);
                return Result.Failure;
            }

            RhinoApp.WriteLine(
                $"SMARTSKIN_{identity.Patch} PASS"
                + $" | version={identity.Version}"
                + $" | commit={identity.Commit}"
                + $" | strategy={construction.StrategyToken}"
                + " | action=ACCEPTED"
                + " | code=P06_ACCEPTED"
                + " | built=1"
                + " | added=1"
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
                    return new PreviewDecision(true, Result.Success, "P06_ACCEPTED");
                }

                if (form.CancelRequested || !form.Visible)
                {
                    return new PreviewDecision(false, Result.Cancel, "P06_PREVIEW_CANCELLED");
                }

                var getResult = decision.Get();
                if (form.AcceptRequested)
                {
                    return new PreviewDecision(true, Result.Success, "P06_ACCEPTED");
                }

                if (form.CancelRequested || !form.Visible)
                {
                    return new PreviewDecision(false, Result.Cancel, "P06_PREVIEW_CANCELLED");
                }

                if (getResult == GetResult.Timeout)
                {
                    continue;
                }

                if (getResult == GetResult.Nothing)
                {
                    if (form.PrepareForAcceptance())
                    {
                        return new PreviewDecision(true, Result.Success, "P06_ACCEPTED");
                    }

                    continue;
                }

                var commandResult = decision.CommandResult();
                return new PreviewDecision(
                    false,
                    commandResult == Result.Success ? Result.Cancel : commandResult,
                    "P06_PREVIEW_CANCELLED");
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
        if (!construction.UsesBoundaryTangency)
        {
            return string.Empty;
        }

        var settings = outcome.Settings;
        return $"{separator} supports={outcome.SupportedEdgeCount.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} parents={outcome.ParentObjectCount.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} preset={settings.PresetToken}"
            + $"{separator} u_spans={settings.USpans.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} v_spans={settings.VSpans.ToString(CultureInfo.InvariantCulture)}"
            + $"{separator} sample_spacing_scale={settings.SampleSpacingScale.ToString("G4", CultureInfo.InvariantCulture)}"
            + $"{separator} flexibility={settings.Flexibility.ToString("G4", CultureInfo.InvariantCulture)}"
            + $"{separator} continuity={(settings.AdjustTangency ? "G1_REQUESTED" : "G0_ONLY")}"
            + $"{separator} trim={(settings.AutomaticTrim ? "ON" : "OFF")}"
            + $"{separator} point_spacing={outcome.PointSpacing.ToString("G6", CultureInfo.InvariantCulture)}";
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
        RhinoApp.WriteLine("Mode: one live settings window and one in-memory preview; source geometry is unchanged; Enter/Space/right-click adds one Brep; Esc cancels.");
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
