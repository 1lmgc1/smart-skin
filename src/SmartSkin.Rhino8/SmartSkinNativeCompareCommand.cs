using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using Rhino;
using Rhino.Commands;
using Rhino.DocObjects;
using Rhino.Geometry;
using Rhino.Input;
using Rhino.Input.Custom;
using SmartSkin.Core;

namespace SmartSkin.Rhino8;

/// <summary>Command-line-only, disposable native construction experiment. Never adds document geometry.</summary>
public sealed class SmartSkinNativeCompareCommand : Command
{
    public override string EnglishName => "SmartSkinNativeCompare";
    private const int MaximumSelectedEdges = 32;
    private const int BudgetMilliseconds = 45000;

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var report = new NativeCompareReportBuffer(DateTime.UtcNow, Guid.NewGuid().ToString("N"));
        var result = Result.Failure;
        NativeCompareReportCapture.Run(report, NativeCompareReportExport.Store, NativeCompareReportExport.Message, write =>
        {
            var identity = BuildIdentity.FromAssembly(typeof(SmartSkinNativeCompareCommand).Assembly);
            write("SMARTSKIN_NATIVE_REPORT_START | report_id=" + report.ReportId
                + " | started_utc=" + report.StartedUtc.ToString("O") + " | version=" + identity.Version
                + " | commit=" + identity.Commit + " | rhino=" + RhinoApp.Version
                + " | runtime=" + RuntimeInformation.FrameworkDescription
                + " | process=" + (System.Environment.Is64BitProcess ? "x64" : "x86")
                + " | model_units=" + doc.ModelUnitSystem
                + " | absolute_tolerance=" + NativeCompareProbeProtocol.Number(doc.ModelAbsoluteTolerance)
                + " | angle_tolerance_radians=" + NativeCompareProbeProtocol.Number(doc.ModelAngleToleranceRadians)
                + " | run_mode=" + mode + " | capture=DIRECT_DIAGNOSTIC_SINK | history_scrape=false");
            result = RunComparison(doc, mode, write);
            return result.ToString();
        });
        // The native helper has returned through cleanup and removed its Escape handler.
        // Folder selection and disk I/O cannot enter the construction stopwatch or affect a live preview.
        NativeCompareReportExport.ChooseFolderAndSave(doc, mode, report);
        return result;
    }

    private static Result RunComparison(RhinoDoc doc, RunMode mode, Action<string> write)
    {
        var identity = BuildIdentity.FromAssembly(typeof(SmartSkinNativeCompareCommand).Assembly);
        var objectCount = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var watch = new Stopwatch();
        var cancelled = false;
        long lastPump = -50;
        NativeCompareInput? input = null;
        var candidates = new List<NativeCompareCandidate>();
        void Escape(object? sender, EventArgs args) => cancelled = true;
        void Checkpoint()
        {
            if (watch.ElapsedMilliseconds - lastPump >= 50)
            {
                lastPump = watch.ElapsedMilliseconds;
                RhinoApp.Wait();
            }
            if (cancelled) throw new OperationCanceledException();
            if (watch.ElapsedMilliseconds > BudgetMilliseconds)
                throw new TimeoutException("NATIVE_COMPARE_TIME_BUDGET_EXHAUSTED");
        }
        try
        {
            using var selection = new GetObject();
            selection.SetCommandPrompt("Native comparison EXPERIMENT: select a complete native naked-edge loop");
            selection.GeometryFilter = ObjectType.Curve;
            selection.SubObjectSelect = true;
            selection.GroupSelect = false;
            write("SMARTSKIN_NATIVE_COMPARE_SELECTION | status=STARTED | native_naked_edges_required=true");
            selection.GetMultiple(4, MaximumSelectedEdges);
            var selectionResult = selection.CommandResult();
            write("SMARTSKIN_NATIVE_COMPARE_SELECTION | status=" + selectionResult + " | selected=" + selection.ObjectCount);
            if (selectionResult != Result.Success) return selectionResult;
            watch.Start();
            RhinoApp.EscapeKeyPressed += Escape;
            write("SMARTSKIN_NATIVE_COMPARE_START | version=" + identity.Version + " | commit=" + identity.Commit
                + " | experimental=true | document_additions=0 | requested=TOPOLOGY_AND_G0_ONLY | average=NOT_APPLICABLE"
                + " | protocol=FIRST_SEED_JOIN_ONLY | candidate=EdgeSrf:Seed | fresh_join_copies=true"
                + " | max_initial_construction_calls=" + 1
                + " | max_join_calls=1 | match_calls=0 | blend_calls=0 | split_calls=0" + " | budget_ms=" + BudgetMilliseconds
                + " | cancellation=BETWEEN_NATIVE_CALLS | join_point_exemptions=NONE | global_G2=NOT_VERIFIED");
            input = NativeCompareInput.Capture(doc, selection, Checkpoint);
            write("SMARTSKIN_NATIVE_COMPARE_PLAN | ordered_cells=1 | logical_sides=4 | native_edges=" + input.Edges.Count
                + " | owner_count=" + input.Owners.Count + " | derivation=" + input.Derivation + " | knot_features=false"
                + " | full_source_archive=CAPTURED_IN_MEMORY | no_guides_invented=true");
            for (var side = 0; side < 4; side++)
                write("SMARTSKIN_NATIVE_COMPARE_SIDE | side=" + side + " | sources="
                    + string.Join(",", input.Sides[side].Select(e => e.Label))
                    + " | native_target_type=BrepEdge | chain_parts=" + input.Sides[side].Count
                    + " | within_chain_G1_features=" + input.Sides[side].Sum(e => e.Features.Count)
                    + " | feature_exceptions=NONE_GRANTED");

            NativeCompareSideBinding.TraceSources(input, write);
            RunSeedJoinProbe(input, candidates, Checkpoint, write);
            if (!input.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_ARCHIVE_CHANGED");
            write("SMARTSKIN_NATIVE_COMPARE_BUILD_END | elapsed_ms=" + watch.ElapsedMilliseconds
                + " | preview_candidates=" + candidates.Count + " | global_G2=NOT_VERIFIED");
            if (mode == RunMode.Interactive && candidates.Count != 0) Preview(doc, input, candidates, write);
            if (!input.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_ARCHIVE_CHANGED_AFTER_PREVIEW");
            return Result.Success;
        }
        catch (NativeCompareReportCapacityException)
        {
            write("SMARTSKIN_NATIVE_COMPARE_END | status=REPORT_CAPACITY_EXCEEDED | complete_report=false");
            return Result.Failure;
        }
        catch (OperationCanceledException)
        {
            write("SMARTSKIN_NATIVE_COMPARE_END | status=CANCELLED | candidates_discarded=true");
            return Result.Cancel;
        }
        catch (TimeoutException)
        {
            write("SMARTSKIN_NATIVE_COMPARE_END | status=TIME_BUDGET_EXHAUSTED | candidates_discarded=true");
            return Result.Failure;
        }
        catch (NativeCompareUnsupported exception)
        {
            write("SMARTSKIN_NATIVE_COMPARE_END | status=" + exception.Message + " | global_G2=NOT_VERIFIED");
            return Result.Failure;
        }
        catch (Exception exception)
        {
            // Do not serialize exception objects, source coordinates, paths or private model data.
            write("SMARTSKIN_NATIVE_COMPARE_END | status=NATIVE_EXCEPTION | type=" + exception.GetType().Name);
            return Result.Failure;
        }
        finally
        {
            var cleanupFailures = new List<string>();
            NativeCompareReportCleanup.Attempt("escape_handler", () => RhinoApp.EscapeKeyPressed -= Escape, cleanupFailures);
            var allCandidatesDisposed = true;
            foreach (var candidate in candidates)
                allCandidatesDisposed &= NativeCompareReportCleanup.Attempt("candidate", candidate.Dispose, cleanupFailures);
            var unchanged = false;
            NativeCompareReportCleanup.Attempt("source_snapshot", () => unchanged = input?.SourcesUnchanged(doc) ?? false, cleanupFailures);
            var copiesUnchanged = false;
            NativeCompareReportCleanup.Attempt("copy_snapshot", () => copiesUnchanged = input?.CopiesUnchanged() ?? false, cleanupFailures);
            var inputDisposed = NativeCompareReportCleanup.Attempt("input", () => input?.Dispose(), cleanupFailures);
            NativeCompareReportCleanup.Attempt("redraw", () => doc.Views.Redraw(), cleanupFailures);
            var afterCount = "NOT_VERIFIED";
            NativeCompareReportCleanup.Attempt("object_count", () => afterCount = RhinoDocumentMetrics.ActiveObjectCount(doc).ToString(), cleanupFailures);
            write("SMARTSKIN_NATIVE_COMPARE_CLEANUP | document_objects=" + objectCount + "->" + afterCount
                + " | source_archive=" + (unchanged ? "VERIFIED_UNCHANGED" : "NOT_VERIFIED")
                + " | captured_copy_archive=" + (copiesUnchanged ? "VERIFIED_UNCHANGED" : "NOT_VERIFIED")
                + " | all_candidates_disposed=" + allCandidatesDisposed + " | input_disposed=" + inputDisposed
                + " | cleanup_failures=" + (cleanupFailures.Count == 0 ? "NONE" : string.Join(",", cleanupFailures))
                + " | added=0 | replaced=0");
        }
    }

    private static Brep EdgeSeed(NativeCompareInput input)
    {
        var curves = new List<Curve>();
        try
        {
            for (var side = 0; side < 4; side++) curves.Add(input.SideCurve(side));
            return Brep.CreateEdgeSurface(curves) ?? throw new NativeCompareUnsupported("NATIVE_EDGESRF_RETURNED_NULL");
        }
        finally { foreach (var curve in curves) curve.Dispose(); }
    }

    private static void RunSeedJoinProbe(NativeCompareInput input, List<NativeCompareCandidate> candidates, Action checkpoint, Action<string> write)
    {
        checkpoint();
        var watch = Stopwatch.StartNew();
        using var seed = EdgeSeed(input);
        var seedMilliseconds = watch.ElapsedMilliseconds;
        if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
        checkpoint();
        if (!NativeCompareMeasure.Bounded(seed, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_NATIVE_SEED");
        var binding = NativeCompareSideBinding.CaptureSeed(seed, input);
        write("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=EdgeSrfSeed | phase=Seed | construction_ms=" + seedMilliseconds
            + " | next=ONE_JOIN_WITH_FULL_OWNER_COPIES | later_recipes=NONE");
        NativeCompareMeasure.ReportSides("EdgeSrfSeed", "Seed", seed, input, binding, checkpoint, write);
        AddPreviewCopy("EdgeSrf:Seed:NOT_VERIFIED", seed, candidates);
        using var join = NativeSeedJoinExperiment.Run(seed, input, candidates, checkpoint, write);
        if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
    }

    private static void RunFirstMatchProbe(NativeCompareInput input, List<NativeCompareCandidate> candidates, Action checkpoint, Action<string> write)
    {
        checkpoint();
        var watch = Stopwatch.StartNew();
        using var seed = EdgeSeed(input);
        var seedMilliseconds = watch.ElapsedMilliseconds;
        if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
        checkpoint();
        if (!NativeCompareMeasure.Bounded(seed, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_NATIVE_SEED");
        var binding = NativeCompareSideBinding.CaptureSeed(seed, input);
        var seedArchive = input.GeometryFingerprint(seed);
        write("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=EdgeSrfSeed | phase=Seed | construction_ms=" + seedMilliseconds
            + " | next=SIDE0_FALSE_AND_TRUE_FROM_INDEPENDENT_IDENTICAL_COPIES | later_matches=NONE | next_stage=BOUNDED_SUPPORT_TRIM");
        NativeCompareMeasure.ReportSides("EdgeSrfSeed", "Seed", seed, input, binding, checkpoint, write);
        AddPreviewCopy("EdgeSrf:Seed:NOT_VERIFIED", seed, candidates);
        var matchSupports = new List<NativeSupportCandidate>();
        try
        {
            NativeCompareProbeProtocol.RunIndependent(seed, original => original.DuplicateBrep(), (copy, reverse) =>
            {
                checkpoint();
                if (input.GeometryFingerprint(copy) != seedArchive)
                    throw new InvalidOperationException("INDEPENDENT_SEED_ARCHIVE_MISMATCH");
                RunSingleMatch(copy, reverse, input, binding, candidates, matchSupports, checkpoint, write);
                if (input.GeometryFingerprint(seed) != seedArchive || !input.CopiesUnchanged())
                    throw new InvalidOperationException("SEED_OR_COPIED_NATIVE_TARGET_CHANGED");
            });
            NativeSupportTrimExperiment.Run(input, binding, matchSupports, candidates, checkpoint, write);
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
        }
        finally { foreach (var support in matchSupports) support.Dispose(); }
    }

    private static void RunSingleMatch(Brep copy, bool reverse, NativeCompareInput input, NativeCompareSideBinding binding,
        List<NativeCompareCandidate> candidates, List<NativeSupportCandidate> matchSupports, Action checkpoint, Action<string> write)
    {
        var name = "Side0Reverse" + (reverse ? "True" : "False");
        var watch = Stopwatch.StartNew();
        Brep? matched = null; Brep? unusedTarget = null;
        try
        {
            write("SMARTSKIN_NATIVE_COMPARE_PROBE | recipe=" + name
                + " | input=INDEPENDENT_IDENTICAL_EDGESRF_COPY | seed_archive=VERIFIED_EQUAL"
                + " | target_side=" + NativeCompareProbeProtocol.TargetSide + " | match_count=1 | reverse_match=" + reverse);
            NativeCompareMeasure.ReportSides(name, "Before", copy, input, binding, checkpoint, write);
            var edge = binding.Resolve(copy, NativeCompareProbeProtocol.TargetSide)
                ?? throw new NativeCompareUnsupported("UNSUPPORTED_UNIQUE_NATURAL_CANDIDATE_END");
            var targets = input.Sides[NativeCompareProbeProtocol.TargetSide].Select(part => (Curve)part.Native).ToArray();
            // Preserve actual native target owners and mixed edge directions. The only varying setting
            // reverses the candidate edge to match; it does not certify or normalize target-chain orientation.
            var settings = new MatchSrfSettings(Continuity.G2_continuous, Continuity.G2_continuous)
            {
                Average = false, MatchClosestPoints = false, PreserveIso = PreserveIsoCurveMethod.Automatic,
                ReverseMatchDirection = reverse, ReverseAverageTargetDirection = false,
            };
            settings.EnableRefinement(false, input.Tolerance, input.AngleTolerance, 5.0);
            write("SMARTSKIN_NATIVE_COMPARE_SETTINGS | recipe=" + name
                + " | requested=G2 | other_end=G2_OPPOSITE_ONLY | average=false | refine=false"
                + " | match_closest_points=false | preserve_iso=Automatic | reverse_match=" + reverse
                + " | reverse_average_target=false | positional_tolerance=" + NativeCompareProbeProtocol.Number(input.Tolerance)
                + " | angle_tolerance_radians=" + NativeCompareProbeProtocol.Number(input.AngleTolerance)
                + " | native_curvature_radius_percent=5 | physical_W_gate=NOT_APPLIED"
                + " | candidate_edge=" + edge.EdgeIndex + " | candidate_trim=" + NativeCompareSideBinding.Trim(edge).TrimIndex
                + " | candidate_iso=" + NativeCompareSideBinding.Trim(edge).IsoStatus
                + " | target_sequence=" + string.Join(",", input.Sides[NativeCompareProbeProtocol.TargetSide].Select(part => part.Label))
                + " | target_chain_order=LOGICAL_CAPTURE_ORDER | target_native_directions=UNMODIFIED"
                + " | reversal_semantics=CANDIDATE_EDGE_DIRECTION | target_chain_orientation=NOT_VERIFIED");
            checkpoint();
            var nativeWatch = Stopwatch.StartNew();
            var returned = Brep.CreateFromMatch(edge, targets, settings, out matched, out unusedTarget);
            var nativeMilliseconds = nativeWatch.ElapsedMilliseconds;
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            write("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=" + name + " | phase=MatchSide0"
                + " | native_ms=" + nativeMilliseconds + " | returned=" + returned + " | reverse_match=" + reverse);
            checkpoint();
            if (!returned || matched is null) throw new NativeCompareUnsupported("NATIVE_MATCH_FAILED");
            if (!NativeCompareMeasure.Bounded(matched, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_MATCH_RESULT");
            NativeCompareMeasure.ReportSides(name, "After", matched, input, binding, checkpoint, write);
            AddPreviewCopy(name + ":AfterSingleMatch:NOT_VERIFIED", matched, candidates);
            matchSupports.Add(new NativeSupportCandidate(name, matched.DuplicateBrep()));
            write("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name
                + " | status=SINGLE_NATIVE_CALL_COMPLETED | elapsed_ms=" + watch.ElapsedMilliseconds
                + " | physical_correspondence=NOT_VERIFIED | global_G2=NOT_VERIFIED");
        }
        catch (NativeCompareUnsupported exception)
        {
            write("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name + " | status=" + exception.Message
                + " | elapsed_ms=" + watch.ElapsedMilliseconds + " | no_later_match=true | no_fallback=true");
        }
        finally { matched?.Dispose(); unusedTarget?.Dispose(); }
    }

    private static void AddPreviewCopy(string name, Brep brep, List<NativeCompareCandidate> candidates)
    {
        var copy = brep.DuplicateBrep();
        try
        {
            candidates.Add(new NativeCompareCandidate(name, copy));
            copy = null!;
        }
        finally { copy?.Dispose(); }
    }

    private static void Preview(RhinoDoc doc, NativeCompareInput input, IReadOnlyList<NativeCompareCandidate> candidates, Action<string> write)
    {
        using var conduit = new NativeComparePreview();
        var index = 0;
        conduit.Candidate = candidates[index]; conduit.Enabled = true;
        using var choice = new GetOption();
        choice.SetCommandPrompt("Native diagnostic preview NOT VERIFIED: Next cycles; Enter/Done discards all");
        choice.AcceptNothing(true);
        var next = choice.AddOption("Next");
        var done = choice.AddOption("Done");
        try
        {
            while (true)
            {
                if (!input.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_CHANGED_DURING_PREVIEW");
                write("SMARTSKIN_NATIVE_COMPARE_PREVIEW | candidate=" + candidates[index].Name + " | cached_meshes=" + candidates[index].Meshes.Length
                    + " | read_only=true | accept_available=false");
                doc.Views.Redraw();
                var result = choice.Get();
                if (result != GetResult.Option || choice.OptionIndex() == done)
                {
                    write("SMARTSKIN_NATIVE_COMPARE_PREVIEW_END | input="
                        + (result == GetResult.Option ? "Done" : result.ToString()) + " | all_candidates_discarded_on_cleanup=true");
                    break;
                }
                if (choice.OptionIndex() == next)
                {
                    index = (index + 1) % candidates.Count;
                    conduit.Candidate = candidates[index];
                }
            }
        }
        finally { conduit.Enabled = false; conduit.Candidate = null; doc.Views.Redraw(); }
    }
}
