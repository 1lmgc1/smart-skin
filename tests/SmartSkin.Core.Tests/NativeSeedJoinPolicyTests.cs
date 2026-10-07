using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeSeedJoinPolicyTests
{
    [Fact]
    public void OrdinarySeamRequiresSeedAndExactParentProvenance()
    {
        Assert.True(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, true, 2, true, true, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, true, 2, false, true, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, true, 2, true, false, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, true, 2, true, true, false));
    }

    [Fact]
    public void ClosedPeriodicSeamAndNonmanifoldStitchAreNotOrdinaryAttachment()
    {
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, true, 1, true, true, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(true, 2, false, 2, true, true, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(false, 3, true, 3, true, true, true));
        Assert.False(NativeSeedJoinPolicy.OrdinarySelectedSeam(false, 1, false, 1, true, true, true));
    }

    [Fact]
    public void ContributorsMustExactlyCorroborateFaceOrigins()
    {
        Assert.True(NativeSeedJoinPolicy.ContributorsAgree(new[] { 2, 0 }, new[] { 0, 2, 2 }, 3));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(new[] { 1, 2 }, new[] { 0, 1, 2 }, 3));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(new[] { 0, 1, 2 }, new[] { 0, 2 }, 3));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(new[] { 0, 0 }, new[] { 0 }, 3));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(new[] { 0, 3 }, new[] { 0, 3 }, 3));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(null, new[] { 0, 1 }, 2));
        Assert.False(NativeSeedJoinPolicy.ContributorsAgree(Array.Empty<int>(), Array.Empty<int>(), 2));
    }

    [Fact]
    public void ExactSplitSharedVertexIsOneLocationButCoincidentUnrelatedEdgesAreAmbiguous()
    {
        Assert.True(NativeSeedJoinPolicy.OneTopologicalLocation(new[] { (0, -1) }));
        Assert.True(NativeSeedJoinPolicy.OneTopologicalLocation(new[] { (2, 7), (2, 7) }));
        Assert.False(NativeSeedJoinPolicy.OneTopologicalLocation(new[] { (2, 7), (3, 7) }));
        Assert.False(NativeSeedJoinPolicy.OneTopologicalLocation(new[] { (2, 7), (2, 8) }));
        Assert.False(NativeSeedJoinPolicy.OneTopologicalLocation(new[] { (2, -1), (2, -1) }));
        Assert.False(NativeSeedJoinPolicy.OneTopologicalLocation(Array.Empty<(int, int)>()));
    }

    [Fact]
    public void AllSelectedPiecesAndAllSeedEdgesMustPassBothDirections()
    {
        Assert.True(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 8, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 5, 8, 8, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 7, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 8, 0, 0, 0, 1));
    }

    [Fact]
    public void OneJoinedOutputAndGoodCoverageCannotHideRemainingSelectedNakedOrNonmanifoldEdges()
    {
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 8, 1, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 8, 0, 1, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 8, 8, 0, 0, 1, 0));
    }

    [Fact]
    public void MissingProvenanceInvalidOutputOrEmptyCoverageCannotPass()
    {
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(false, true, 6, 6, 8, 8, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, false, 6, 6, 8, 8, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 0, 0, 0, 0, 0, 0, 0, 0));
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 6, 0, 0, 0, 0, 0, 0));
    }
}
