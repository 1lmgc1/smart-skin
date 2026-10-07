using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeMatchImprovementResult : IDisposable
{
    internal NativeSeedJoinResult? Join;
    internal NativeBuildCapQualification? Qualification;
    internal string Reason = "NO_WHOLE_BOUNDARY_IMPROVEMENT";
    internal NativeMatchTier Tier = NativeMatchTier.G0;
    internal bool Improved => Join?.Cap is not null && Qualification?.Ready == true;
    internal string PreviewSummary => Improved ? "Улучшен: " + Tier + " по выборочным проверкам."
        : Reason == "IMPROVE_TIME_BUDGET" ? "Исходный вариант: лимит времени улучшения."
        : "Исходный вариант: улучшение не прошло проверки.";
    public void Dispose() { Join?.Dispose(); Join = null; }
}

// The ordinary Build never calls this engine. Every native Match gets fresh candidate
// and owner copies; failed experiments cannot mutate the qualified baseline.
internal static class NativeMatchImprovementEngine
{
    private sealed class Branch : IDisposable
    {
        internal Brep Cap = null!;
        internal NativeMatchEvaluation Evaluation = null!;
        internal NativeMatchRecipe Recipe = null!;
        internal bool FirstAccepted;
        public void Dispose() => Cap?.Dispose();
    }
    internal static NativeMatchImprovementResult Run(Brep seed, NativeCompareInput input,
        Action cancellationCheckpoint, Action assertSources, Action<string> write)
    {
        var result = new NativeMatchImprovementResult();
        var branches = new List<Branch>(); var watch = Stopwatch.StartNew();
        var budget = new NativeMatchAttemptBudget();
        var seedArchive = input.GeometryFingerprint(seed);
        void AssertSources()
        {
            assertSources();
            if (input.GeometryFingerprint(seed) != seedArchive)
                throw new InvalidOperationException("IMPROVE_ORIGINAL_SEED_CHANGED");
        }
        void Checkpoint()
        {
            cancellationCheckpoint();
            if (watch.Elapsed.TotalSeconds >= NativeMatchImprovementPolicy.AttemptBudgetSeconds)
                throw new TimeoutException("IMPROVE_TIME_BUDGET");
        }
        try
        {
            write("SMARTSKIN_NATIVE_IMPROVE_START | max_match_calls=14 | max_G1_calls=10 | max_G2_calls=4 | between_call_budget_s=15"
                + " | degree_cap=11 | control_point_cap=4096 | baseline_retained=true | target_owners=FRESH_PER_CALL"
                + " | native_calls_not_preempted=true | source_piece_count=" + input.Edges.Count);
            AssertSources();
            var evaluator = new NativeMatchBoundaryEvaluator(input, Checkpoint);
            var baseline = evaluator.Evaluate("BaselinePreJoin", seed, Checkpoint, write);
            if (!NativeMatchImprovementPolicy.ValidateBaseline(baseline.State, out var baselineReason))
            { result.Reason = baselineReason; return result; }
            var radius = new double[4]; var g2Available = new bool[4];
            for (var side = 0; side < 4; side++)
            {
                var radiusReason = "SOURCE_CURVATURE_OR_W_GATE_INCOMPLETE";
                g2Available[side] = evaluator.SideCurvatureComplete(side) && evaluator.OperatorLimit.HasValue
                    && NativeMatchImprovementPolicy.TryRadiusPercent(evaluator.SideCurvature(side), evaluator.OperatorLimit.Value,
                        out radius[side], out radiusReason);
                write("SMARTSKIN_NATIVE_IMPROVE_POLICY | side=" + side + " | G0=" + Number(input.Tolerance) + " | angle_radians=" + Number(input.AngleTolerance)
                    + " | W=" + (evaluator.OperatorLimit.HasValue ? Number(evaluator.OperatorLimit.Value) : "NOT_AVAILABLE")
                    + " | W_contract=" + evaluator.OperatorContract + " | source_K=" + Number(evaluator.SideCurvature(side))
                    + " | source_K_complete=" + evaluator.SideCurvatureComplete(side) + " | G2_available=" + g2Available[side]
                    + " | native_G2_radius_percent=" + Number(radius[side]) + " | radius_status=" + radiusReason
                    + " | K_scope=ORIGINAL_CURRENT_SIDE_FIXED_STATIONS | native_radius_is_not_full_W_acceptance=true");
            }
            foreach (var recipe in NativeMatchImprovementPolicy.FirstStageRecipes)
            {
                Checkpoint();
                var branch = new Branch { Cap = seed.DuplicateBrep(), Evaluation = baseline, Recipe = recipe };
                branches.Add(branch);
                branch.FirstAccepted = Call(branch, 0, NativeMatchTier.G1, recipe.Refine, 5.0);
            }
            foreach (var branch in branches)
            {
                if (!NativeMatchImprovementPolicy.CanContinueG1(branch.Recipe, branch.FirstAccepted)) continue;
                var side = NativeMatchImprovementPolicy.NextRequiredSide(branch.Evaluation.State, NativeMatchTier.G1, 0);
                while (side >= 0)
                {
                    if (!Call(branch, side, NativeMatchTier.G1, true, 5.0)) break;
                    side = NativeMatchImprovementPolicy.NextRequiredSide(branch.Evaluation.State, NativeMatchTier.G1, side);
                }
            }
            Branch? BestBranch() => branches.Where(branch => branch.FirstAccepted
                && NativeMatchImprovementPolicy.Tier(branch.Evaluation.State) >= NativeMatchTier.G1)
                .OrderBy(branch => branch, Comparer<Branch>.Create((left, right) => NativeMatchImprovementPolicy.CompareQualified(
                    left.Evaluation.State, left.Recipe.Order, right.Evaluation.State, right.Recipe.Order))).FirstOrDefault();
            var winner = BestBranch();
            if (winner is null) return result;
            if (g2Available.All(value => value) && NativeMatchImprovementPolicy.Tier(winner.Evaluation.State) < NativeMatchTier.G2)
            {
                // Preserve the already accepted G1 geometry. Partial G2 may cost more
                // control points without raising the whole-boundary tier.
                winner = new Branch { Cap = winner.Cap.DuplicateBrep(), Evaluation = winner.Evaluation,
                    Recipe = winner.Recipe, FirstAccepted = true };
                branches.Add(winner);
                var side = NativeMatchImprovementPolicy.NextRequiredSide(winner.Evaluation.State, NativeMatchTier.G2, -1);
                while (side >= 0)
                {
                    if (!Call(winner, side, NativeMatchTier.G2, true, radius[side])) break;
                    side = NativeMatchImprovementPolicy.NextRequiredSide(winner.Evaluation.State, NativeMatchTier.G2, side);
                }
            }
            // Refined partial-G2 gains may increase CP without raising whole-boundary
            // tier. Rank existing branches again; no new native attempt is authorized.
            winner = BestBranch();
            if (winner is null || !NativeMatchImprovementPolicy.CanPromote(baseline.State, winner.Evaluation.State)) return result;
            write("SMARTSKIN_NATIVE_IMPROVE_SELECTION | recipe=" + winner.Recipe.Order
                + " | tier=" + NativeMatchImprovementPolicy.Tier(winner.Evaluation.State)
                + " | control_points=" + winner.Evaluation.State.ControlPointCount + " | order=WHOLE_TIER_THEN_CP_THEN_RECIPE");
            Checkpoint();
            if (!NativeMatchFinalistScreen.Check(winner.Cap, input, Checkpoint, write, out var screenReason))
            { result.Reason = screenReason; return result; }
            AssertSources();
            var joined = NativeSeedJoinExperiment.Run(winner.Cap, input, null, Checkpoint, write, "Match:Finalist:Recipe" + winner.Recipe.Order);
            try
            {
                var qualification = NativeBuildCapQualification.Evaluate(joined, input, Checkpoint, write);
                if (!qualification.Ready || joined.Cap is null) { result.Reason = qualification.Reason; return result; }
                var final = evaluator.Evaluate("FinalJoinedCap", joined.Cap, Checkpoint, write);
                var tier = NativeMatchImprovementPolicy.Tier(winner.Evaluation.State);
                if (!NativeMatchImprovementPolicy.CanPromote(baseline.State, final.State)
                    || !NativeMatchImprovementPolicy.TryAcceptCall(baseline.State, winner.Evaluation.State, final.State, 0, tier, out _))
                { result.Reason = "FINAL_JOINED_CAP_CONTINUITY_NOT_PRESERVED"; return result; }
                Checkpoint(); AssertSources();
                var evidence = "FINITE_MATCH_V1|tier=" + tier + "|recipe=" + winner.Recipe.Order
                    + "|angle=" + Number(input.AngleTolerance) + "|W=" + (evaluator.OperatorLimit.HasValue ? Number(evaluator.OperatorLimit.Value) : "NONE")
                    + "|pieces=" + string.Join(";", final.State.Pieces.Select(piece => piece.SourceIdentity + ":" + piece.SideIndex
                        + ":" + piece.Resolved + ":" + piece.G0 + ":" + piece.G1 + ":" + piece.G2))
                    + "|screen=FINITE_UV_MESH|local_sidedness=EXACT_TRIM_LOOP_MATERIAL_SIDE|global_continuity_regularity_separation=NOT_VERIFIED";
                qualification.BindImprovement(input, joined.Cap, evidence);
                result.Join = joined; joined = null!; result.Qualification = qualification;
                result.Tier = tier; result.Reason = "WHOLE_BOUNDARY_SAMPLED_IMPROVEMENT";
            }
            finally { joined?.Dispose(); }
            return result;

            bool Call(Branch branch, int side, NativeMatchTier continuity, bool refine, double percent)
            {
                Checkpoint(); AssertSources();
                var binding = NativeMatchBoundaryBinding.Capture(branch.Cap, input);
                if (binding is null || binding.Sides[side].Count != 1)
                { write("SMARTSKIN_NATIVE_IMPROVE_STEP | status=UNSUPPORTED_SINGLE_UNTRIMMED_CANDIDATE_SIDE | side=" + side); return false; }
                using var candidateCopy = branch.Cap.DuplicateBrep();
                var copiedBinding = NativeMatchBoundaryBinding.Capture(candidateCopy, input);
                if (copiedBinding is null || copiedBinding.Sides[side].Count != 1) return false;
                var edge = copiedBinding.Sides[side][0];
                var trim = NativeCompareSideBinding.Trim(edge);
                if (!candidateCopy.Faces[0].IsSurface || (trim.IsoStatus != IsoStatus.North && trim.IsoStatus != IsoStatus.South
                    && trim.IsoStatus != IsoStatus.East && trim.IsoStatus != IsoStatus.West))
                { write("SMARTSKIN_NATIVE_IMPROVE_STEP | status=UNSUPPORTED_TRIMMED_CANDIDATE_SIDE | side=" + side); return false; }
                var owners = new List<Brep>(); Brep? matched = null; Brep? unusedTarget = null;
                try
                {
                    foreach (var owner in input.Owners)
                    {
                        var copy = owner.Copy.DuplicateBrep();
                        if (copy is null) throw new NativeCompareUnsupported("IMPROVE_TARGET_COPY_FAILED");
                        owners.Add(copy);
                        if (!copy.IsValid || copy.Edges.Count != owner.Copy.Edges.Count || copy.Faces.Count != owner.Copy.Faces.Count)
                            throw new NativeCompareUnsupported("IMPROVE_TARGET_COPY_BINDING_FAILED");
                    }
                    var archives = owners.Select(input.GeometryFingerprint).ToArray();
                    var targets = input.Sides[side].Select(part => owners[part.OwnerIndex].Edges[part.Native.EdgeIndex]).ToArray();
                    for (var i = 0; i < targets.Length; i++)
                        if (targets[i].Domain != input.Sides[side][i].Native.Domain)
                            throw new NativeCompareUnsupported("IMPROVE_TARGET_DOMAIN_CHANGED");
                    var settings = new MatchSrfSettings(continuity == NativeMatchTier.G2 ? Continuity.G2_continuous : Continuity.G1_continuous,
                        Continuity.G2_continuous)
                    { Average = false, MatchClosestPoints = false, ReverseMatchDirection = false, ReverseAverageTargetDirection = false,
                        PreserveIso = branch.Recipe.Preservation == NativeMatchPreservation.Automatic ? PreserveIsoCurveMethod.Automatic : PreserveIsoCurveMethod.Preserve };
                    settings.EnableRefinement(refine, input.Tolerance, input.AngleTolerance, percent);
                    Checkpoint(); if (!budget.TryTakeCall(continuity)) throw new NativeCompareUnsupported("IMPROVE_CALL_LIMIT");
                    write("SMARTSKIN_NATIVE_IMPROVE_SETTINGS | recipe=" + branch.Recipe.Order + " | side=" + side + " | requested=" + continuity
                        + " | preserve_iso=" + settings.PreserveIso + " | refine=" + refine + " | average=false | other_end=G2_OPPOSITE_ONLY"
                        + " | reverse=false_CONTROLLED | match_closest_points=false | native_radius_percent=" + Number(percent)
                        + " | candidate_edge=" + edge.EdgeIndex + " | candidate_iso=" + trim.IsoStatus
                        + " | native_endpoint_to_logical_endpoint_distances="
                        + Number(edge.PointAtStart.DistanceTo(input.Sides[side][0].Start)) + ","
                        + Number(edge.PointAtStart.DistanceTo(input.Sides[side][input.Sides[side].Count - 1].End)) + ","
                        + Number(edge.PointAtEnd.DistanceTo(input.Sides[side][0].Start)) + ","
                        + Number(edge.PointAtEnd.DistanceTo(input.Sides[side][input.Sides[side].Count - 1].End))
                        + " | targets=" + string.Join(",", input.Sides[side].Select(part => part.Label + ":logical_reverse=" + part.Reverse)));
                    var native = Stopwatch.StartNew();
                    bool returned;
                    try { returned = Brep.CreateFromMatch(edge, targets.Cast<Curve>(), settings, out matched, out unusedTarget); }
                    catch (Exception error)
                    {
                        native.Stop(); AssertSources();
                        write("SMARTSKIN_NATIVE_IMPROVE_NATIVE | recipe=" + branch.Recipe.Order + " | side=" + side
                            + " | native_ms=" + native.ElapsedMilliseconds + " | exception=" + error.GetType().Name
                            + " | copied_targets_unchanged=" + owners.Select((owner, i) => input.GeometryFingerprint(owner) == archives[i]).All(value => value));
                        throw new NativeCompareUnsupported("IMPROVE_NATIVE_MATCH_EXCEPTION:" + error.GetType().Name);
                    }
                    native.Stop(); AssertSources();
                    var targetsUnchanged = owners.Select((owner, i) => input.GeometryFingerprint(owner) == archives[i]).All(value => value);
                    write("SMARTSKIN_NATIVE_IMPROVE_NATIVE | recipe=" + branch.Recipe.Order + " | side=" + side
                        + " | returned=" + returned + " | native_ms=" + native.ElapsedMilliseconds + " | copied_targets_unchanged=" + targetsUnchanged);
                    Checkpoint();
                    if (!targetsUnchanged || matched is null || !NativeCompareMeasure.Bounded(matched, out _)) return false;
                    var evaluated = evaluator.Evaluate("Recipe" + branch.Recipe.Order + ":" + continuity + ":Side" + side, matched, Checkpoint, write);
                    var accepted = NativeMatchImprovementPolicy.TryAcceptCall(baseline.State, branch.Evaluation.State, evaluated.State,
                        side, continuity, out var reason);
                    if (!returned) { accepted = false; reason = "NATIVE_MATCH_RETURNED_FALSE"; }
                    write("SMARTSKIN_NATIVE_IMPROVE_STEP | recipe=" + branch.Recipe.Order + " | side=" + side + " | accepted=" + accepted + " | reason=" + reason);
                    if (!accepted) return false;
                    branch.Cap.Dispose(); branch.Cap = matched; matched = null; branch.Evaluation = evaluated;
                    return true;
                }
                catch (NativeCompareUnsupported error)
                { write("SMARTSKIN_NATIVE_IMPROVE_STEP | recipe=" + branch.Recipe.Order + " | status=" + error.Message); return false; }
                finally
                {
                    var failures = new List<string>();
                    NativeCompareReportCleanup.Attempt("matched", () => matched?.Dispose(), failures);
                    NativeCompareReportCleanup.Attempt("unused_target", () => unusedTarget?.Dispose(), failures);
                    foreach (var owner in owners) NativeCompareReportCleanup.Attempt("target_copy", owner.Dispose, failures);
                    if (failures.Count != 0) throw new InvalidOperationException("IMPROVE_COPY_CLEANUP_FAILED:" + string.Join(",", failures));
                }
            }
        }
        catch (TimeoutException error) { result.Reason = error.Message; return result; }
        catch (NativeCompareUnsupported error) { result.Reason = error.Message; return result; }
        finally
        {
            var failures = new List<string>();
            foreach (var branch in branches) NativeCompareReportCleanup.Attempt("branch", branch.Dispose, failures);
            write("SMARTSKIN_NATIVE_IMPROVE_END | selected=" + (result.Improved ? result.Tier.ToString() : "BASELINE")
                + " | reason=" + result.Reason + " | match_calls=" + budget.TotalCalls + " | elapsed_ms=" + watch.ElapsedMilliseconds
                + " | cleanup=" + (failures.Count == 0 ? "COMPLETE" : string.Join(",", failures)));
            if (failures.Count != 0) { result.Dispose(); throw new InvalidOperationException("IMPROVE_BRANCH_CLEANUP_FAILED"); }
        }
    }
    private static string Number(double value) => NativeCompareProbeProtocol.Number(value);
}
