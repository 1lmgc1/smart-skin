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
            + " | max_construction_calls=11 | budget_ms=" + BudgetMilliseconds
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

            // Data-derived eligibility priority: measure an available natural-parent blend before
            // spending the shared soft budget on a four-Match edge seed. No shape ranking/search.
            var priorityPairs = Enumerable.Range(0, 2).Where(pair => NaturalBlendPair(input, pair)).ToArray();
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_ORDER | priority=ELIGIBLE_NATURAL_PARENT_BLEND"
                + " | priority_pairs=" + string.Join(",", priorityPairs) + " | remainder=EDGESRF_THEN_OTHER_BLEND");
            foreach (var pair in priorityPairs)
                RunRecipe("Blend" + pair + "Match", () => BlendSeed(input, pair),
                    new[] { (pair + 1) % 4, (pair + 3) % 4 }, input, candidates, Checkpoint);
            RunRecipe("EdgeSrfMatch", () => EdgeSeed(input), new[] { 0, 2, 1, 3 }, input, candidates, Checkpoint);
            foreach (var pair in Enumerable.Range(0, 2).Except(priorityPairs))
                RunRecipe("Blend" + pair + "Match", () => BlendSeed(input, pair),
                    new[] { (pair + 1) % 4, (pair + 3) % 4 }, input, candidates, Checkpoint);
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=NetworkSurface"
                + " | status=UNSUPPORTED_MISSING_VALID_PARENT_AWARE_CROSSING_NETWORK"
                + " | guide_geometry=NONE_INVENTED");
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

    private static bool NaturalBlendPair(NativeCompareInput input, int pair)
    {
        return new[] { pair, pair + 2 }.All(side => input.Sides[side].Count == 1
            && BoundaryMatchVerifier.IsNaturalBoundary(input.Sides[side][0].Native)
            && NativeCompareMeasure.Face(input.Sides[side][0].Native)?.IsPlanar(input.Tolerance) == false);
    }

    private static Brep BlendSeed(NativeCompareInput input, int pair)
    {
        var a = input.Sides[pair]; var b = input.Sides[pair + 2];
        if (a.Count != 1 || b.Count != 1)
            throw new NativeCompareUnsupported("UNSUPPORTED_NATIVE_COMPOUND_CHAIN_BINDING;logical_recipe=BLEND_OPPOSING_SIDES");
        var ea = a[0]; var eb = b[0];
        var fa = NativeCompareMeasure.Face(ea.Native); var fb = NativeCompareMeasure.Face(eb.Native);
        if (fa is null || fb is null || !ea.Native.Domain.IsValid || !eb.Native.Domain.IsValid)
            throw new NativeCompareUnsupported("UNSUPPORTED_BLEND_PARENT_OR_DOMAIN");
        var breps = Brep.CreateBlendSurface(fa, ea.Native, ea.Native.Domain, ea.Reverse, BlendContinuity.Curvature,
            fb, eb.Native, eb.Native.Domain, !eb.Reverse, BlendContinuity.Curvature);
        if (breps is null || breps.Length == 0) throw new NativeCompareUnsupported("NATIVE_BLEND_RETURNED_EMPTY");
        if (breps.Length != 1)
        {
            foreach (var brep in breps) brep?.Dispose();
            throw new NativeCompareUnsupported("UNSUPPORTED_BLEND_MULTIPLE_PATCHES");
        }
        return breps[0];
    }

    private static void RunRecipe(string name, Func<Brep> seed, int[] matchSides, NativeCompareInput input,
        List<NativeCompareCandidate> candidates, Action checkpoint)
    {
        var watch = Stopwatch.StartNew();
        Brep? current = null;
        var stage = "Seed";
        var completedStage = "Seed";
        var retain = false;
        try
        {
            checkpoint();
            var nativeWatch = Stopwatch.StartNew();
            current = seed();
            var operationMilliseconds = nativeWatch.ElapsedMilliseconds;
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=" + name + " | step=Seed | construction_ms=" + operationMilliseconds);
            checkpoint();
            if (!NativeCompareMeasure.Bounded(current, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_NATIVE_SEED");
            NativeCompareMeasure.Report(name, stage, current, input, checkpoint);
            retain = true;
            foreach (var side in matchSides)
            {
                stage = "MatchSide" + side;
                checkpoint();
                var edge = ResolveNaturalCandidateEdge(current, input.Sides[side], input.Tolerance);
                var targetRun = input.Sides[side];
                var targets = targetRun.Select(e => (Curve)e.Native).ToArray();
                var targetStart = targetRun[0].Start;
                // These ARE copied owner BrepEdges, never detached DuplicateCurve G2 targets.
                var settings = new MatchSrfSettings(Continuity.G2_continuous, Continuity.G2_continuous)
                {
                    Average = false, MatchClosestPoints = false, PreserveIso = PreserveIsoCurveMethod.Automatic,
                    ReverseMatchDirection = edge.PointAtStart.DistanceTo(targetStart) > edge.PointAtEnd.DistanceTo(targetStart),
                };
                settings.EnableRefinement(false, input.Tolerance, input.AngleTolerance, 5.0);
                Brep? matched = null; Brep? unusedTarget = null;
                nativeWatch.Restart();
                try
                {
                    var success = Brep.CreateFromMatch(edge, targets, settings, out matched, out unusedTarget);
                    operationMilliseconds = nativeWatch.ElapsedMilliseconds;
                    if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
                    RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_STEP | recipe=" + name + " | step=" + stage
                        + " | native_ms=" + operationMilliseconds + " | returned=" + success
                        + " | requested=G2 | refine=false | match_closest_points=false | native_curvature_radius_percent=5"
                        + " | reverse_match=" + settings.ReverseMatchDirection
                        + " | target_chain_orientation=NATIVE_NOT_VERIFIED"
                        + " | physical_W_gate=NOT_APPLIED | other_end=G2_OPPOSITE_ONLY | all_boundaries_rechecked=true");
                    checkpoint();
                    if (!success || matched is null) throw new NativeCompareUnsupported("NATIVE_MATCH_FAILED");
                    if (!NativeCompareMeasure.Bounded(matched, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_MATCH_RESULT");
                    current.Dispose(); current = matched; matched = null;
                    completedStage = stage;
                    // Required after EVERY native Match: OtherEnd does not preserve adjacent boundaries.
                    NativeCompareMeasure.Report(name, stage, current, input, checkpoint);
                }
                finally { matched?.Dispose(); unusedTarget?.Dispose(); }
            }
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name
                + " | status=NATIVE_CALLS_COMPLETED | elapsed_ms=" + watch.ElapsedMilliseconds + " | global_G2=NOT_VERIFIED");
        }
        catch (NativeCompareUnsupported exception)
        {
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_RECIPE | recipe=" + name + " | step=" + stage
                + " | status=" + exception.Message + " | elapsed_ms=" + watch.ElapsedMilliseconds + " | global_G2=NOT_VERIFIED");
        }
        catch
        {
            retain = false;
            throw;
        }
        finally
        {
            if (current is not null)
            {
                try
                {
                    if (retain && NativeCompareMeasure.Bounded(current, out _))
                    {
                        candidates.Add(new NativeCompareCandidate(name + ":last_output=" + completedStage + ":NOT_VERIFIED", current));
                        current = null;
                    }
                }
                finally { current?.Dispose(); }
            }
        }
    }

    private static BrepEdge ResolveNaturalCandidateEdge(Brep candidate, IReadOnlyList<NativeCompareInput.Edge> side, double tolerance)
    {
        var start = side[0].Start; var end = side[side.Count - 1].End;
        var matches = candidate.Edges.Where(edge => edge.Valence == EdgeAdjacency.Naked
            && BoundaryMatchVerifier.IsNaturalBoundary(edge)
            && NativeCompareMeasure.NaturalTrimLocus(edge.Brep.Trims[edge.TrimIndices()[0]])
            && ((edge.PointAtStart.DistanceTo(start) <= tolerance && edge.PointAtEnd.DistanceTo(end) <= tolerance)
                || (edge.PointAtStart.DistanceTo(end) <= tolerance && edge.PointAtEnd.DistanceTo(start) <= tolerance))).ToArray();
        if (matches.Length != 1) throw new NativeCompareUnsupported("UNSUPPORTED_UNIQUE_NATURAL_CANDIDATE_END");
        return matches[0];
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
