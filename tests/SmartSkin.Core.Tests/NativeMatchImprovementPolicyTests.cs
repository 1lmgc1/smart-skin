using System;
using System.Collections.Generic;
using System.Linq;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeMatchImprovementPolicyTests
{
    [Fact]
    public void FourFixedIndependentFirstStageRecipesHaveOnlyTwoRefinedContinuations()
    {
        var recipes = NativeMatchImprovementPolicy.FirstStageRecipes;
        Assert.Equal(4, recipes.Count);
        Assert.Equal(new[] { 0, 1, 2, 3 }, recipes.Select(recipe => recipe.Order));
        Assert.Equal(new[] { NativeMatchPreservation.Automatic, NativeMatchPreservation.Automatic,
            NativeMatchPreservation.Preserve, NativeMatchPreservation.Preserve }, recipes.Select(recipe => recipe.Preservation));
        Assert.Equal(new[] { false, true, false, true }, recipes.Select(recipe => recipe.Refine));
        Assert.Equal(2, recipes.Count(recipe => NativeMatchImprovementPolicy.CanContinueG1(recipe, true)));
        Assert.All(recipes, recipe => Assert.False(NativeMatchImprovementPolicy.CanContinueG1(recipe, false)));
        Assert.False(NativeMatchImprovementPolicy.CanContinueG1(
            new NativeMatchRecipe(7, NativeMatchPreservation.Preserve, true), true));
        Assert.Equal(new[] { 0, 2, 1, 3 }, NativeMatchImprovementPolicy.CanonicalSideOrder);
    }

    [Theory]
    [InlineData(4)]
    [InlineData(6)]
    [InlineData(9)]
    [InlineData(17)]
    public void BoundaryStateUsesEveryOriginalPieceWithNoLiteralPieceCount(int count)
    {
        var baseline = State(count: count);
        var candidate = State(count: count, g1Sides: new[] { 0 });
        Assert.True(NativeMatchImprovementPolicy.ValidateBaseline(baseline, out _));
        Assert.True(Accept(baseline, baseline, candidate, 0));
        Assert.Equal(NativeMatchTier.G0, NativeMatchImprovementPolicy.Tier(candidate));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(baseline, candidate));
        var complete = State(count: count, g1Sides: AllSides);
        Assert.True(NativeMatchImprovementPolicy.CanPromote(baseline, complete));
    }

    [Fact]
    public void ATargetSideNeedsEveryOriginalPieceOnThatSide()
    {
        var baseline = State(count: 9);
        var candidate = State(count: 9, g1Sides: new[] { 0 });
        candidate = Edit(candidate, 4, g1: false);
        Assert.False(Accept(baseline, baseline, candidate, 0));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(baseline, candidate));
    }

    [Fact]
    public void MissingPartialOrUnresolvedMetricsNeverPass()
    {
        var baseline = State(count: 8);
        var complete = State(count: 8, g1Sides: AllSides);
        Assert.False(NativeMatchImprovementPolicy.ValidateBaseline(null, out _));
        Assert.False(NativeMatchImprovementPolicy.ValidateBaseline(
            new NativeMatchState(Array.Empty<NativeMatchPieceState>(), 16, 3, 3), out _));
        Assert.False(Accept(baseline, baseline, Copy(complete, complete.Pieces.Take(7)), 0));
        Assert.False(Accept(baseline, baseline, Copy(complete, complete.Pieces.Where(piece => piece.SideIndex != 3)), 0));
        Assert.False(Accept(baseline, baseline, Edit(complete, 7, resolved: false), 0));
        Assert.False(Accept(baseline, baseline, Edit(complete, 7, g0: false), 0));
        Assert.False(Accept(baseline, baseline, Copy(complete, complete.Pieces.Append(complete.Pieces[0])), 0));
        Assert.False(Accept(baseline, baseline, Copy(complete, complete.Pieces.Append(null!)), 0));
    }

    [Fact]
    public void IdentityOrSideChangesRejectEvenWhenEveryContinuityBitPasses()
    {
        var baseline = State(count: 8);
        var candidate = State(count: 8, g1Sides: AllSides);
        Assert.False(Accept(baseline, baseline, Edit(candidate, 7, identity: "different-source"), 0));
        Assert.False(Accept(baseline, baseline, Edit(candidate, 7, side: 1), 0));
        Assert.False(Accept(baseline, baseline, Edit(candidate, 7, identity: " "), 0));
        Assert.False(Accept(baseline, baseline, Edit(candidate, 7, side: 4), 0));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(baseline,
            Edit(candidate, 7, identity: "different-source")));
        Assert.True(Accept(baseline, baseline, Copy(candidate, candidate.Pieces.Reverse()), 0));
    }

    [Fact]
    public void SourceIdentityMustBeUniqueAcrossDifferentLogicalSides()
    {
        var complete = State(count: 8, g1Sides: AllSides);
        var duplicate = Edit(complete, 7, identity: complete.Pieces[0].SourceIdentity);
        Assert.NotEqual(duplicate.Pieces[0].SideIndex, duplicate.Pieces[7].SideIndex);
        Assert.False(NativeMatchImprovementPolicy.ValidateBaseline(duplicate, out var reason));
        Assert.Equal("INVALID_OR_DUPLICATED_ORIGINAL_PIECE_IDENTITY", reason);
        Assert.Equal(NativeMatchTier.Invalid, NativeMatchImprovementPolicy.Tier(duplicate));
        Assert.False(Accept(duplicate, duplicate, duplicate, 0));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(State(count: 8), duplicate));
    }

    [Fact]
    public void BaselineG1AndG2BitsAreMandatoryOnNontargetPieces()
    {
        var baseline = State(g1Sides: new[] { 2 }, g2Sides: new[] { 3 });
        var candidate = State(g1Sides: new[] { 0, 2 }, g2Sides: new[] { 3 });
        Assert.True(Accept(baseline, baseline, candidate, 0));
        Assert.False(Accept(baseline, baseline, Edit(candidate, 2, g1: false), 0));
        Assert.False(Accept(baseline, baseline, Edit(candidate, 3, g2: false), 0));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(baseline,
            State(g1Sides: AllSides))); // Complete G1 still loses the baseline's G2 piece.
    }

    [Fact]
    public void EveryAcceptedIncidentalGainMustSurviveLaterCalls()
    {
        var baseline = State();
        var previous = State(g1Sides: new[] { 0, 2 }, g2Sides: new[] { 1 });
        var candidate = State(g1Sides: AllSides, g2Sides: new[] { 1 });
        Assert.True(Accept(baseline, previous, candidate, 3));
        Assert.False(Accept(baseline, previous, Edit(candidate, 2, g1: false), 3));
        Assert.False(Accept(baseline, previous, Edit(candidate, 1, g2: false), 3));
        Assert.False(Accept(baseline, Edit(previous, 3, resolved: false), candidate, 3));
        Assert.False(Accept(baseline, Edit(previous, 3, identity: "other"), candidate, 3));
    }

    [Fact]
    public void PreviousStateCannotAlreadyHaveLostBaselineEvidence()
    {
        var baseline = State(g2Sides: new[] { 2 });
        var previous = State(g1Sides: new[] { 0, 2 });
        var candidate = State(g1Sides: AllSides, g2Sides: new[] { 2 });
        Assert.False(Accept(baseline, previous, candidate, 1));
    }

    [Fact]
    public void G2RequiresMeasuredG1AndFullRequestedPieceG2()
    {
        var baseline = State();
        var previous = State(g1Sides: AllSides);
        Assert.False(Accept(baseline, previous, previous, 0, NativeMatchTier.G2));
        var candidate = State(g1Sides: AllSides, g2Sides: new[] { 0 });
        Assert.True(Accept(baseline, previous, candidate, 0, NativeMatchTier.G2));
        Assert.False(Accept(baseline, previous, Edit(candidate, 0, g1: false), 0, NativeMatchTier.G2));
    }

    [Fact]
    public void G2RequiresCompleteBoundaryG1BeforeAndAfterTheCall()
    {
        var baseline = State();
        var partialPrevious = State(g1Sides: new[] { 0, 2, 1 });
        var partialCandidate = State(g1Sides: new[] { 0, 2, 1 }, g2Sides: new[] { 0 });
        var completePrevious = State(g1Sides: AllSides);
        var completeCandidate = State(g1Sides: AllSides, g2Sides: new[] { 0 });
        foreach (var pair in new[] { (partialPrevious, partialCandidate),
            (partialPrevious, completeCandidate), (completePrevious, partialCandidate) })
        {
            Assert.False(NativeMatchImprovementPolicy.TryAcceptCall(baseline, pair.Item1,
                pair.Item2, 0, NativeMatchTier.G2, out var reason));
            Assert.Equal("G2_REQUIRES_COMPLETE_BOUNDARY_G1", reason);
        }
        Assert.True(Accept(baseline, completePrevious, completeCandidate, 0, NativeMatchTier.G2));
    }

    [Fact]
    public void PartialTargetsNeverPromoteAndWholeBoundaryTierMustRise()
    {
        var g0 = State();
        var partial = State(g1Sides: new[] { 0, 2, 1 });
        var g1 = State(g1Sides: AllSides);
        var partialG2 = State(g1Sides: AllSides, g2Sides: new[] { 0, 2, 1 });
        var g2 = State(g2Sides: AllSides);
        Assert.False(NativeMatchImprovementPolicy.CanPromote(g0, partial));
        Assert.True(NativeMatchImprovementPolicy.CanPromote(g0, g1));
        Assert.True(NativeMatchImprovementPolicy.CanPromote(g0, g2));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(g1, partialG2));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(g1, State(g1Sides: AllSides, controlPoints: 8)));
        Assert.True(NativeMatchImprovementPolicy.CanPromote(g1, g2));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(g2, g2));
    }

    [Fact]
    public void ControlsCanQualifyButNeverReceiveG1Continuation()
    {
        var baseline = State(); var complete = State(g1Sides: AllSides);
        foreach (var control in NativeMatchImprovementPolicy.FirstStageRecipes.Where(recipe => !recipe.Refine))
        {
            Assert.True(Accept(baseline, baseline, complete, 0));
            Assert.True(NativeMatchImprovementPolicy.CanPromote(baseline, complete));
            Assert.False(NativeMatchImprovementPolicy.CanContinueG1(control, true));
        }
    }

    [Fact]
    public void ContinuationSkipsAchievedSidesWithoutWrappingOrRepeating()
    {
        Assert.Equal(0, NativeMatchImprovementPolicy.NextRequiredSide(State(), NativeMatchTier.G1, -1));
        Assert.Equal(2, NativeMatchImprovementPolicy.NextRequiredSide(State(g1Sides: new[] { 0 }), NativeMatchTier.G1, 0));
        Assert.Equal(1, NativeMatchImprovementPolicy.NextRequiredSide(State(g1Sides: new[] { 0, 2 }), NativeMatchTier.G1, 0));
        Assert.Equal(3, NativeMatchImprovementPolicy.NextRequiredSide(State(g1Sides: new[] { 0, 2, 1 }), NativeMatchTier.G1, 0));
        Assert.Equal(-1, NativeMatchImprovementPolicy.NextRequiredSide(State(g1Sides: AllSides), NativeMatchTier.G1, 0));
        Assert.Equal(-1, NativeMatchImprovementPolicy.NextRequiredSide(State(), NativeMatchTier.G1, 3));
        Assert.Equal(-1, NativeMatchImprovementPolicy.NextRequiredSide(State(), NativeMatchTier.G1, 19));
        Assert.Equal(-1, NativeMatchImprovementPolicy.NextRequiredSide(State(), NativeMatchTier.Invalid, -1));
        Assert.Equal(2, NativeMatchImprovementPolicy.NextRequiredSide(State(g1Sides: AllSides, g2Sides: new[] { 0 }), NativeMatchTier.G2, -1));
    }

    [Fact]
    public void WorstCasePlanHasTenG1AndFourG2Calls()
    {
        var budget = new NativeMatchAttemptBudget();
        foreach (var recipe in NativeMatchImprovementPolicy.FirstStageRecipes)
        {
            Assert.True(budget.TryTakeCall(NativeMatchTier.G1));
            if (NativeMatchImprovementPolicy.CanContinueG1(recipe, true))
                foreach (var side in NativeMatchImprovementPolicy.CanonicalSideOrder.Skip(1))
                    Assert.True(budget.TryTakeCall(NativeMatchTier.G1));
        }
        Assert.Equal(10, budget.G1Calls);
        Assert.False(budget.TryTakeCall(NativeMatchTier.G1));
        foreach (var side in NativeMatchImprovementPolicy.CanonicalSideOrder)
            Assert.True(budget.TryTakeCall(NativeMatchTier.G2));
        Assert.Equal(4, budget.G2Calls); Assert.Equal(14, budget.TotalCalls);
        Assert.False(budget.TryTakeCall(NativeMatchTier.G1));
        Assert.False(budget.TryTakeCall(NativeMatchTier.G2));
        Assert.False(budget.TryTakeCall(NativeMatchTier.G0));
    }

    [Fact]
    public void FewerG1CallsNeverPermitExtraG2Passes()
    {
        var budget = new NativeMatchAttemptBudget();
        Assert.True(budget.TryTakeCall(NativeMatchTier.G1));
        for (var i = 0; i < 4; i++) Assert.True(budget.TryTakeCall(NativeMatchTier.G2));
        Assert.False(budget.TryTakeCall(NativeMatchTier.G2));
        Assert.Equal(5, budget.TotalCalls);
    }

    [Fact]
    public void SelectionIsTierThenControlPointCountThenFixedRecipeOrder()
    {
        var g1 = State(g1Sides: AllSides, controlPoints: 16);
        var expensiveG2 = State(g2Sides: AllSides, controlPoints: 4096);
        Assert.True(Compare(expensiveG2, 3, g1, 0) < 0);
        Assert.True(Compare(g1, 0, expensiveG2, 3) > 0);
        var small = State(g1Sides: AllSides, controlPoints: 9);
        Assert.True(Compare(small, 3, g1, 0) < 0);
        Assert.True(Compare(g1, 0, g1, 3) < 0);
        Assert.Equal(0, Compare(g1, 2, g1, 2));
        var entries = new[] { (State: g1, Order: 3), (State: small, Order: 2),
            (State: small, Order: 0), (State: g1, Order: 1) };
        foreach (var rotation in Enumerable.Range(0, entries.Length))
        {
            var sorted = entries.Skip(rotation).Concat(entries.Take(rotation)).ToList();
            sorted.Sort((left, right) => Compare(left.State, left.Order, right.State, right.Order));
            Assert.Same(small, sorted[0].State); Assert.Equal(0, sorted[0].Order);
        }
    }

    [Fact]
    public void RetainedSimpleG1BeatsCostlierPartialG2ButCompleteG2Wins()
    {
        var baseline = State();
        var retainedG1 = State(g1Sides: AllSides, controlPoints: 16);
        var partialG2 = State(g1Sides: AllSides, g2Sides: new[] { 0 }, controlPoints: 48);
        var completeG2 = State(g2Sides: AllSides, controlPoints: 96);
        Assert.True(Accept(baseline, retainedG1, partialG2, 0, NativeMatchTier.G2));
        Assert.True(Compare(retainedG1, 1, partialG2, 1) < 0);
        Assert.True(Compare(completeG2, 1, retainedG1, 1) < 0);
        Assert.Equal(NativeMatchTier.G1, NativeMatchImprovementPolicy.Tier(retainedG1));
        Assert.All(retainedG1.Pieces, piece => Assert.False(piece.G2));
    }

    [Theory]
    [InlineData(4097, 3, 3)]
    [InlineData(0, 3, 3)]
    [InlineData(-1, 3, 3)]
    [InlineData(16, 12, 3)]
    [InlineData(16, 3, 12)]
    [InlineData(16, 0, 3)]
    public void ExistingComplexityCapsRemainMandatory(int controlPoints, int degreeU, int degreeV)
    {
        var candidate = new NativeMatchState(State(g1Sides: AllSides).Pieces, controlPoints, degreeU, degreeV);
        Assert.False(NativeMatchImprovementPolicy.ValidateBaseline(candidate, out _));
        Assert.False(Accept(State(), State(), candidate, 0));
        Assert.False(NativeMatchImprovementPolicy.CanPromote(State(), candidate));
        Assert.Equal(NativeMatchTier.Invalid, NativeMatchImprovementPolicy.Tier(candidate));
    }

    [Fact]
    public void ExactComplexityCapsAndImmutableInputCopiesAreAccepted()
    {
        var source = State().Pieces.ToArray();
        var state = new NativeMatchState(source, 4096, 11, 11);
        source[0] = new NativeMatchPieceState("bad", 0, false, false, false, false);
        Assert.True(NativeMatchImprovementPolicy.ValidateBaseline(state, out _));
        Assert.Equal("original-piece-0", state.Pieces[0].SourceIdentity);
        Assert.False(state.Pieces is NativeMatchPieceState[]);
    }

    [Theory]
    [InlineData(0, 1, 5)]
    [InlineData(1, 1, 5)]
    [InlineData(19, 1, 5)]
    [InlineData(99, 1, 1)]
    [InlineData(999, 1, .1)]
    [InlineData(1e10, 1e-3, 9.999999999999e-12)]
    public void RadiusUsesAbsoluteWGateOnlyForSolverInput(double curvature, double tau, double expected)
    {
        Assert.True(NativeMatchImprovementPolicy.TryRadiusPercent(curvature, tau, out var percent, out _));
        Assert.InRange(percent, expected * (1 - 1e-14), expected * (1 + 1e-14));
        Assert.InRange(percent, double.Epsilon, 5);
    }

    [Fact]
    public void RadiusAvoidsOverflowAndPreservesRepresentableTinyPercentWithoutLowerFloor()
    {
        AssertRadius(double.MaxValue, double.MaxValue, 5);
        AssertRadius(double.MaxValue, double.MaxValue / 99, 1);
        AssertRadius(double.MaxValue, 1, 100 / double.MaxValue);
        AssertRadius(100, double.Epsilon, double.Epsilon);
        AssertRadius(1000, 1e-323, double.Epsilon, exact: true, expectSuccess: false);
        AssertRadius(1e300, 1e-20, 1e-318);
        AssertRadius(0, double.Epsilon, 5);
        Assert.False(NativeMatchImprovementPolicy.TryRadiusPercent(double.MaxValue, double.Epsilon, out var percent, out _));
        Assert.True(double.IsNaN(percent));
    }

    [Fact]
    public void RadiusRejectsNonfiniteNegativeOrZeroGate()
    {
        foreach (var invalid in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity, -1.0 })
        {
            Assert.False(NativeMatchImprovementPolicy.TryRadiusPercent(invalid, 1, out _, out _));
            Assert.False(NativeMatchImprovementPolicy.TryRadiusPercent(1, invalid, out _, out _));
        }
        Assert.False(NativeMatchImprovementPolicy.TryRadiusPercent(1, 0, out _, out _));
        Assert.False(NativeMatchImprovementPolicy.TryRadiusPercent(0, 0, out _, out _));
    }

    private static readonly int[] AllSides = { 0, 1, 2, 3 };

    private static NativeMatchState State(int count = 4, int[]? g1Sides = null, int[]? g2Sides = null,
        int controlPoints = 16) => new(Enumerable.Range(0, count).Select(index =>
        new NativeMatchPieceState("original-piece-" + index, index % 4, true, true,
            (g1Sides ?? Array.Empty<int>()).Contains(index % 4) || (g2Sides ?? Array.Empty<int>()).Contains(index % 4),
            (g2Sides ?? Array.Empty<int>()).Contains(index % 4))), controlPoints, 3, 3);

    private static NativeMatchState Copy(NativeMatchState state, IEnumerable<NativeMatchPieceState> pieces) =>
        new(pieces, state.ControlPointCount, state.DegreeU, state.DegreeV);

    private static NativeMatchState Edit(NativeMatchState state, int index, string? identity = null,
        int? side = null, bool? resolved = null, bool? g0 = null, bool? g1 = null, bool? g2 = null) =>
        Copy(state, state.Pieces.Select((piece, i) => i != index ? piece :
            new NativeMatchPieceState(identity ?? piece.SourceIdentity, side ?? piece.SideIndex,
                resolved ?? piece.Resolved, g0 ?? piece.G0, g1 ?? piece.G1, g2 ?? piece.G2)));

    private static bool Accept(NativeMatchState baseline, NativeMatchState previous, NativeMatchState candidate,
        int side, NativeMatchTier tier = NativeMatchTier.G1) =>
        NativeMatchImprovementPolicy.TryAcceptCall(baseline, previous, candidate, side, tier, out _);

    private static int Compare(NativeMatchState left, int leftOrder, NativeMatchState right, int rightOrder) =>
        NativeMatchImprovementPolicy.CompareQualified(left, leftOrder, right, rightOrder);

    private static void AssertRadius(double curvature, double tau, double expected,
        bool exact = false, bool expectSuccess = true)
    {
        Assert.Equal(expectSuccess, NativeMatchImprovementPolicy.TryRadiusPercent(curvature, tau, out var actual, out _));
        if (!expectSuccess) { Assert.True(double.IsNaN(actual)); return; }
        if (exact || expected < 1e-300) Assert.Equal(expected, actual);
        else Assert.InRange(actual, expected * (1 - 1e-14), expected * (1 + 1e-14));
    }
}
