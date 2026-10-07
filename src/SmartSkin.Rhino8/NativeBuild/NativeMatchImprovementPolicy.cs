using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

namespace SmartSkin.Rhino8;

internal enum NativeMatchTier { Invalid = -1, G0 = 0, G1 = 1, G2 = 2 }
internal enum NativeMatchPreservation { Automatic, Preserve }

// These are immutable, source-bound results of the native evaluator's existing physical
// gates. A true bit is measured evidence, never a requested native Match setting.
internal sealed class NativeMatchPieceState
{
    internal string SourceIdentity { get; }
    internal int SideIndex { get; }
    internal bool Resolved { get; }
    internal bool G0 { get; }
    internal bool G1 { get; }
    internal bool G2 { get; }

    internal NativeMatchPieceState(string sourceIdentity, int sideIndex, bool resolved,
        bool g0, bool g1, bool g2)
    {
        SourceIdentity = sourceIdentity; SideIndex = sideIndex; Resolved = resolved;
        G0 = g0; G1 = g1; G2 = g2;
    }
}

internal sealed class NativeMatchState
{
    internal IReadOnlyList<NativeMatchPieceState> Pieces { get; }
    internal int ControlPointCount { get; }
    internal int DegreeU { get; }
    internal int DegreeV { get; }

    internal NativeMatchState(IEnumerable<NativeMatchPieceState> pieces, int controlPointCount,
        int degreeU, int degreeV)
    {
        Pieces = Array.AsReadOnly((pieces ?? Array.Empty<NativeMatchPieceState>()).ToArray());
        ControlPointCount = controlPointCount; DegreeU = degreeU; DegreeV = degreeV;
    }
}

internal sealed class NativeMatchRecipe
{
    internal int Order { get; }
    internal NativeMatchPreservation Preservation { get; }
    internal bool Refine { get; }

    internal NativeMatchRecipe(int order, NativeMatchPreservation preservation, bool refine)
    { Order = order; Preservation = preservation; Refine = refine; }
}

// Pure bounded advancement and ranking only. Geometry, native validity, original physical
// tolerances, source snapshots, and the 15-second between-call deadline remain with the
// native caller. A native call cannot be preempted. These finite screens are not global G2.
internal static class NativeMatchImprovementPolicy
{
    internal const int MaximumG1Calls = 10;
    internal const int MaximumMatchCalls = 14;
    internal const int MaximumControlPoints = 4096;
    internal const int MaximumDegree = 11;
    internal const double AttemptBudgetSeconds = 15;

    internal static IReadOnlyList<NativeMatchRecipe> FirstStageRecipes { get; } =
        new ReadOnlyCollection<NativeMatchRecipe>(new[]
        {
            new NativeMatchRecipe(0, NativeMatchPreservation.Automatic, false),
            new NativeMatchRecipe(1, NativeMatchPreservation.Automatic, true),
            new NativeMatchRecipe(2, NativeMatchPreservation.Preserve, false),
            new NativeMatchRecipe(3, NativeMatchPreservation.Preserve, true)
        });

    internal static IReadOnlyList<int> CanonicalSideOrder { get; } =
        Array.AsReadOnly(new[] { 0, 2, 1, 3 });

    internal static bool ValidateBaseline(NativeMatchState? state, out string reason) =>
        ValidateState(state, out reason);

    internal static NativeMatchTier Tier(NativeMatchState? state)
    {
        if (!ValidateState(state, out _)) return NativeMatchTier.Invalid;
        if (state!.Pieces.All(piece => piece.G2)) return NativeMatchTier.G2;
        return state.Pieces.All(piece => piece.G1) ? NativeMatchTier.G1 : NativeMatchTier.G0;
    }

    internal static bool TryAcceptCall(NativeMatchState baseline, NativeMatchState previous,
        NativeMatchState candidate, int targetSide, NativeMatchTier requestedTier, out string reason)
    {
        if (targetSide < 0 || targetSide > 3
            || (requestedTier != NativeMatchTier.G1 && requestedTier != NativeMatchTier.G2))
            return Reject("INVALID_MATCH_TARGET", out reason);
        if (!ValidateState(baseline, out reason) || !ValidateState(previous, out reason)
            || !ValidateState(candidate, out reason)) return false;
        if (!SameSources(baseline, previous) || !SameSources(baseline, candidate))
            return Reject("ORIGINAL_PIECE_IDENTITY_MISMATCH", out reason);
        if (requestedTier == NativeMatchTier.G2
            && (Tier(previous) < NativeMatchTier.G1 || Tier(candidate) < NativeMatchTier.G1))
            return Reject("G2_REQUIRES_COMPLETE_BOUNDARY_G1", out reason);
        if (!Preserves(baseline, previous) || !Preserves(baseline, candidate)
            || !Preserves(previous, candidate))
            return Reject("PREVIOUSLY_ACHIEVED_CONTINUITY_LOST", out reason);
        if (!SideAchieved(candidate, targetSide, requestedTier))
            return Reject("REQUESTED_ORIGINAL_PIECES_NOT_ACHIEVED", out reason);
        reason = "MATCH_ADVANCEMENT_ACCEPTED";
        return true;
    }

    internal static bool CanPromote(NativeMatchState baseline, NativeMatchState candidate)
    {
        var originalTier = Tier(baseline); var candidateTier = Tier(candidate);
        return originalTier >= NativeMatchTier.G0 && candidateTier >= NativeMatchTier.G1
            && candidateTier > originalTier && SameSources(baseline, candidate)
            && Preserves(baseline, candidate);
    }

    // Negative means left is preferred. Only candidates independently qualified against
    // the original baseline may be supplied by the caller; partial tiers do not promote.
    internal static int CompareQualified(NativeMatchState leftState, int leftRecipeOrder,
        NativeMatchState rightState, int rightRecipeOrder)
    {
        var tier = Tier(rightState).CompareTo(Tier(leftState));
        if (tier != 0) return tier;
        var controlPoints = leftState.ControlPointCount.CompareTo(rightState.ControlPointCount);
        return controlPoints != 0 ? controlPoints : leftRecipeOrder.CompareTo(rightRecipeOrder);
    }

    internal static bool CanContinueG1(NativeMatchRecipe recipe, bool firstStageAccepted) =>
        firstStageAccepted && IsRecipe(recipe) && recipe.Refine;

    // afterSideIndex is the previously attempted logical side, or -1 before a pass.
    // A satisfied side consumes no native call. Callers cannot wrap to a second pass.
    internal static int NextRequiredSide(NativeMatchState state, NativeMatchTier tier, int afterSideIndex)
    {
        if (!ValidateState(state, out _) || (tier != NativeMatchTier.G1 && tier != NativeMatchTier.G2))
            return -1;
        var start = -1;
        if (afterSideIndex != -1)
        {
            for (var i = 0; i < CanonicalSideOrder.Count; i++)
                if (CanonicalSideOrder[i] == afterSideIndex) start = i;
            if (start < 0) return -1;
        }
        for (var i = start + 1; i < CanonicalSideOrder.Count; i++)
            if (!SideAchieved(state, CanonicalSideOrder[i], tier)) return CanonicalSideOrder[i];
        return -1;
    }

    // This sets the solver's radius-percent input only. Acceptance still requires the
    // unchanged absolute full-W tolerance at every required original finite station.
    // K is the maximum absolute parent principal curvature cached by that evaluator.
    internal static bool TryRadiusPercent(double maxAbsParentPrincipalCurvature, double tau,
        out double percent, out string reason)
    {
        percent = double.NaN;
        var k = maxAbsParentPrincipalCurvature;
        if (!Finite(k) || k < 0 || !Finite(tau) || tau <= 0)
            return Reject("INVALID_PARENT_CURVATURE_OR_ABSOLUTE_W_GATE", out reason);
        if (k <= tau)
        {
            percent = 5;
            reason = k == 0 ? "ZERO_PARENT_CURVATURE_EXPLORATORY_RADIUS" : "RADIUS_PERCENT_READY";
            return true;
        }
        var ratio = tau / k; // <= 1; never forms the potentially overflowing K+tau.
        // Multiply first where safe so a small ratio that rounds to zero does not lose
        // a representable final percent. No arbitrary positive lower floor is allowed.
        var uncapped = tau <= double.MaxValue / 100
            ? ((100 * tau) / k) / (1 + ratio)
            : (100 * ratio) / (1 + ratio);
        if (!Finite(uncapped) || uncapped <= 0)
            return Reject("RADIUS_PERCENT_NOT_POSITIVELY_REPRESENTABLE", out reason);
        percent = Math.Min(5, uncapped);
        reason = "RADIUS_PERCENT_READY";
        return true;
    }

    internal static bool IsRecipe(NativeMatchRecipe? recipe) => recipe is not null
        && FirstStageRecipes.Any(expected => expected.Order == recipe.Order
            && expected.Preservation == recipe.Preservation && expected.Refine == recipe.Refine);

    private static bool ValidateState(NativeMatchState? state, out string reason)
    {
        if (state is null || state.Pieces.Count == 0)
            return Reject("MISSING_ORIGINAL_PIECE_METRICS", out reason);
        if (state.ControlPointCount <= 0 || state.ControlPointCount > MaximumControlPoints
            || state.DegreeU < 1 || state.DegreeU > MaximumDegree
            || state.DegreeV < 1 || state.DegreeV > MaximumDegree)
            return Reject("MATCH_COMPLEXITY_CAP", out reason);
        var identities = new HashSet<string>(StringComparer.Ordinal);
        var sides = new HashSet<int>();
        foreach (var piece in state.Pieces)
        {
            if (piece is null || string.IsNullOrWhiteSpace(piece.SourceIdentity)
                || piece.SideIndex < 0 || piece.SideIndex > 3
                || !identities.Add(piece.SourceIdentity))
                return Reject("INVALID_OR_DUPLICATED_ORIGINAL_PIECE_IDENTITY", out reason);
            if (!piece.Resolved || !piece.G0)
                return Reject("ORIGINAL_PIECE_G0_UNRESOLVED_OR_FAILED", out reason);
            if (piece.G2 && !piece.G1)
                return Reject("INCONSISTENT_CONTINUITY_METRICS", out reason);
            sides.Add(piece.SideIndex);
        }
        if (sides.Count != 4) return Reject("INCOMPLETE_LOGICAL_BOUNDARY", out reason);
        reason = "ORIGINAL_BOUNDARY_METRICS_VALID";
        return true;
    }

    private static bool SameSources(NativeMatchState original, NativeMatchState candidate)
    {
        var expected = new HashSet<(string Identity, int Side)>(
            original.Pieces.Select(piece => (piece.SourceIdentity, piece.SideIndex)));
        return expected.Count == candidate.Pieces.Count
            && candidate.Pieces.All(piece => expected.Contains((piece.SourceIdentity, piece.SideIndex)));
    }

    private static bool Preserves(NativeMatchState original, NativeMatchState candidate)
    {
        var measured = candidate.Pieces.ToDictionary(piece => (piece.SourceIdentity, piece.SideIndex));
        return original.Pieces.All(piece => measured.TryGetValue((piece.SourceIdentity, piece.SideIndex), out var after)
            && (!piece.G1 || after.G1) && (!piece.G2 || after.G2));
    }

    private static bool SideAchieved(NativeMatchState state, int side, NativeMatchTier tier) =>
        state.Pieces.Where(piece => piece.SideIndex == side)
            .All(piece => tier == NativeMatchTier.G2 ? piece.G2 : piece.G1);

    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    private static bool Reject(string diagnosis, out string reason) { reason = diagnosis; return false; }
}

internal sealed class NativeMatchAttemptBudget
{
    internal int G1Calls { get; private set; }
    internal int G2Calls { get; private set; }
    internal int TotalCalls => G1Calls + G2Calls;

    internal bool TryTakeCall(NativeMatchTier requestedTier)
    {
        if (TotalCalls >= NativeMatchImprovementPolicy.MaximumMatchCalls) return false;
        if (requestedTier == NativeMatchTier.G1 && G1Calls < NativeMatchImprovementPolicy.MaximumG1Calls)
        { G1Calls++; return true; }
        if (requestedTier == NativeMatchTier.G2 && G2Calls < 4)
        { G2Calls++; return true; }
        return false;
    }
}
