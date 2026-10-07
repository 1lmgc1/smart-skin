using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
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
        using var selection = new GetObject();
        selection.SetCommandPrompt("Native comparison EXPERIMENT: select a complete native naked-edge loop");
        selection.GeometryFilter = ObjectType.Curve;
        selection.SubObjectSelect = true;
        selection.GroupSelect = false;
        selection.GetMultiple(4, MaximumSelectedEdges);
        if (selection.CommandResult() != Result.Success) return selection.CommandResult();

        var identity = BuildIdentity.FromAssembly(typeof(SmartSkinNativeCompareCommand).Assembly);
        var objectCount = RhinoDocumentMetrics.ActiveObjectCount(doc);
        var watch = Stopwatch.StartNew();
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
        RhinoApp.EscapeKeyPressed += Escape;
        RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_START | version=" + identity.Version + " | commit=" + identity.Commit
            + " | experimental=true | document_additions=0 | requested=G2 | average=false"
            + " | protocol=N2_FIRST_MATCH_REVERSAL | target_side=0 | independent_seed_copies=true"
            + " | max_construction_calls=" + NativeCompareProbeProtocol.MaximumConstructionCalls + " | budget_ms=" + BudgetMilliseconds
            + " | cancellation=BETWEEN_NATIVE_CALLS | upper_exceptions=NONE_GRANTED | global_G2=NOT_VERIFIED");
        try
        {
            input = NativeCompareInput.Capture(doc, selection, Checkpoint);
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_PLAN | ordered_cells=1 | logical_sides=4 | native_edges=" + input.Edges.Count
                + " | derivation=" + input.Derivation + " | knot_features=false"
                + " | full_source_archive=CAPTURED_IN_MEMORY | no_guides_invented=true");
            for (var side = 0; side < 4; side++)
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_SIDE | side=" + side + " | sources="
                    + string.Join(",", input.Sides[side].Select(e => e.Label))
                    + " | native_target_type=BrepEdge | chain_parts=" + input.Sides[side].Count
                    + " | within_chain_G1_features=" + input.Sides[side].Sum(e => e.Features.Count)
                    + " | feature_exceptions=NONE_GRANTED");

            NativeCompareSideBinding.TraceSources(input);
            RunFirstMatchProbe(input, candidates, Checkpoint);
            if (!input.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_ARCHIVE_CHANGED");
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_BUILD_END | elapsed_ms=" + watch.ElapsedMilliseconds
                + " | preview_candidates=" + candidates.Count + " | global_G2=NOT_VERIFIED");
            if (mode == RunMode.Interactive && candidates.Count != 0) Preview(doc, input, candidates);
            if (!input.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_ARCHIVE_CHANGED_AFTER_PREVIEW");
            return Result.Success;
        }
        catch (OperationCanceledException)
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_END | status=CANCELLED | candidates_discarded=true");
            return Result.Cancel;
        }
        catch (TimeoutException)
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_END | status=TIME_BUDGET_EXHAUSTED | candidates_discarded=true");
            return Result.Failure;
        }
        catch (NativeCompareUnsupported exception)
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_END | status=" + exception.Message + " | global_G2=NOT_VERIFIED");
            return Result.Failure;
        }
        catch (Exception exception)
        {
            // Do not serialize exception objects, source coordinates, paths or private model data.
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_END | status=NATIVE_EXCEPTION | type=" + exception.GetType().Name);
            return Result.Failure;
        }
        finally
        {
            RhinoApp.EscapeKeyPressed -= Escape;
            foreach (var candidate in candidates) candidate.Dispose();
            var unchanged = false;
            try { unchanged = input?.SourcesUnchanged(doc) ?? false; } catch { /* Report unverified; never mask cleanup. */ }
            input?.Dispose();
            doc.Views.Redraw();
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_CLEANUP | document_objects=" + objectCount + "->"
                + RhinoDocumentMetrics.ActiveObjectCount(doc) + " | source_archive=" + (unchanged ? "VERIFIED_UNCHANGED" : "NOT_VERIFIED")
                + " | all_candidates_disposed=true | added=0 | replaced=0");
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

    private static void RunFirstMatchProbe(NativeCompareInput input, List<NativeCompareCandidate> candidates, Action checkpoint)
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
        RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=EdgeSrfSeed | phase=Seed | construction_ms=" + seedMilliseconds
            + " | next=SIDE0_FALSE_AND_TRUE_FROM_INDEPENDENT_IDENTICAL_COPIES | later_matches=NONE | other_recipes=NONE");
        NativeCompareMeasure.ReportSides("EdgeSrfSeed", "Seed", seed, input, binding, checkpoint);
        AddPreviewCopy("EdgeSrf:Seed:NOT_VERIFIED", seed, candidates);
        NativeCompareProbeProtocol.RunIndependent(seed, original => original.DuplicateBrep(), (copy, reverse) =>
        {
            checkpoint();
            if (input.GeometryFingerprint(copy) != seedArchive)
                throw new InvalidOperationException("INDEPENDENT_SEED_ARCHIVE_MISMATCH");
            RunSingleMatch(copy, reverse, input, binding, candidates, checkpoint);
            if (input.GeometryFingerprint(seed) != seedArchive || !input.CopiesUnchanged())
                throw new InvalidOperationException("SEED_OR_COPIED_NATIVE_TARGET_CHANGED");
        });
    }

    private static void RunSingleMatch(Brep copy, bool reverse, NativeCompareInput input, NativeCompareSideBinding binding,
        List<NativeCompareCandidate> candidates, Action checkpoint)
    {
        var name = "Side0Reverse" + (reverse ? "True" : "False");
        var watch = Stopwatch.StartNew();
        Brep? matched = null; Brep? unusedTarget = null;
        try
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_PROBE | recipe=" + name
                + " | input=INDEPENDENT_IDENTICAL_EDGESRF_COPY | seed_archive=VERIFIED_EQUAL"
                + " | target_side=" + NativeCompareProbeProtocol.TargetSide + " | match_count=1 | reverse_match=" + reverse);
            NativeCompareMeasure.ReportSides(name, "Before", copy, input, binding, checkpoint);
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
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_SETTINGS | recipe=" + name
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
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=" + name + " | phase=MatchSide0"
                + " | native_ms=" + nativeMilliseconds + " | returned=" + returned + " | reverse_match=" + reverse);
            checkpoint();
            if (!returned || matched is null) throw new NativeCompareUnsupported("NATIVE_MATCH_FAILED");
            if (!NativeCompareMeasure.Bounded(matched, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_MATCH_RESULT");
            NativeCompareMeasure.ReportSides(name, "After", matched, input, binding, checkpoint);
            AddPreviewCopy(name + ":AfterSingleMatch:NOT_VERIFIED", matched, candidates);
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name
                + " | status=SINGLE_NATIVE_CALL_COMPLETED | elapsed_ms=" + watch.ElapsedMilliseconds
                + " | physical_correspondence=NOT_VERIFIED | global_G2=NOT_VERIFIED");
        }
        catch (NativeCompareUnsupported exception)
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name + " | status=" + exception.Message
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

    private static void Preview(RhinoDoc doc, NativeCompareInput input, IReadOnlyList<NativeCompareCandidate> candidates)
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
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_PREVIEW | candidate=" + candidates[index].Name + " | cached_meshes=" + candidates[index].Meshes.Length
                    + " | read_only=true | accept_available=false");
                doc.Views.Redraw();
                var result = choice.Get();
                if (result != GetResult.Option || choice.OptionIndex() == done) break;
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
