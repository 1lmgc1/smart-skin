using System;
using System.Collections.Generic;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeSeedJoinPolicyTests
{
    private static readonly Guid Seed = new("10000000-0000-0000-0000-000000000001");
    private static readonly Guid ParentA = new("20000000-0000-0000-0000-000000000002");
    private static readonly Guid ParentB = new("20000000-0000-0000-0000-000000000003");
    private static Dictionary<Guid, int> ExpectedFaces() => new() { [Seed] = 0, [ParentA] = 1, [ParentB] = 1 };
    private static NativeSeedJoinPolicy.FaceEvidence Face(Guid tag, bool unchanged = true) => new(tag, unchanged);
    private static IReadOnlyList<NativeSeedJoinPolicy.FaceEvidence>[] OneOutput(params NativeSeedJoinPolicy.FaceEvidence[] faces) => new[] { (IReadOnlyList<NativeSeedJoinPolicy.FaceEvidence>)faces };

    [Fact]
    public void AbsentNativeMapUsesCompleteUniqueUnchangedFaceEvidence()
    {
        Assert.True(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), OneOutput(Face(ParentB), Face(Seed), Face(ParentA)),
            null, 2, out var contributors));
        Assert.Equal(new[] { 0, 1 }, Assert.Single(contributors));
        // Provenance alone cannot certify that the selected seams were joined.
        Assert.False(NativeSeedJoinPolicy.SampledSelectedOpeningJoined(true, true, 6, 0, 4, 0, 4, 0, 6, 6));
    }

    [Fact]
    public void AbsentMapCannotHideMissingOriginalFace()
    {
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), OneOutput(Face(Seed), Face(ParentA)), null, 2, out _));
    }

    [Fact]
    public void AbsentMapCannotHideDuplicateOrUnknownOutputFace()
    {
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(),
            OneOutput(Face(Seed), Face(ParentA), Face(ParentB), Face(ParentB)), null, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(),
            OneOutput(Face(Seed), Face(ParentA), Face(ParentB), Face(Guid.Empty)), null, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(),
            OneOutput(Face(Seed), Face(ParentA), Face(Guid.Empty)), null, 2, out _));
    }

    [Fact]
    public void ChangedSupportOrDomainRejectsEvenWithCorroboratingMap()
    {
        var faces = OneOutput(Face(Seed), Face(ParentA, false), Face(ParentB));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, null, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, new[] { new[] { 0, 1 } }, 2, out _));
    }

    [Fact]
    public void SuppliedContradictoryOrMalformedMapCannotFallBackToTags()
    {
        var faces = OneOutput(Face(Seed), Face(ParentA), Face(ParentB));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, new[] { new[] { 1 } }, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, Array.Empty<int[]>(), 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, new int[][] { null! }, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, new[] { new[] { 0, 1 }, new[] { 1 } }, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), faces, new[] { new[] { 0, 1, 1 } }, 2, out _));
    }

    [Fact]
    public void MultipleOutputContributorSetsComeFromActualFaceDistribution()
    {
        var outputs = new[] { (IReadOnlyList<NativeSeedJoinPolicy.FaceEvidence>)new[] { Face(ParentA), Face(Seed) }, new[] { Face(ParentB) } };
        Assert.True(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), outputs, null, 2, out var contributors));
        Assert.Equal(new[] { 0, 1 }, contributors[0]);
        Assert.Equal(new[] { 1 }, contributors[1]);
        Assert.True(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), outputs, new[] { new[] { 1, 0 }, new[] { 1 } }, 2, out _));
        Assert.False(NativeSeedJoinPolicy.ResolveFaceProvenance(ExpectedFaces(), outputs, new[] { new[] { 1 }, new[] { 0, 1 } }, 2, out _));
    }

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
