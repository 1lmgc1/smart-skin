using SmartSkin.Core.Construction;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class BoundaryCycleTopologyTests
{
    [Fact]
    public void SingleClosedEdgeIsACycle()
    {
        var result = BoundaryCycleTopology.Analyze(new[] { (7, 7) });
        Assert.True(result.IsSingleCycle);
        Assert.Equal(1, result.Components);
        Assert.Equal(0, result.Junctions);
    }

    [Fact]
    public void SegmentationDoesNotChangeClosure()
    {
        foreach (var count in new[] { 2, 4, 6, 32, 128 })
        {
            var edges = Enumerable.Range(0, count).Select(i => (i, (i + 1) % count)).ToArray();
            Assert.True(BoundaryCycleTopology.Analyze(edges).IsSingleCycle);
        }
    }

    [Fact]
    public void DirectionOrderAndVertexNumbersDoNotMatter()
    {
        Assert.True(BoundaryCycleTopology.Analyze(new[] { (100, 20), (30, 100), (20, 30) }).IsSingleCycle);
    }

    [Fact]
    public void ExtraLoopIsRejected()
    {
        var result = BoundaryCycleTopology.Analyze(new[] { (0, 0), (1, 1) });
        Assert.False(result.IsSingleCycle);
        Assert.Equal(2, result.Components);
        Assert.Equal("MULTIPLE_BOUNDARY_COMPONENTS", result.Reason);
    }

    [Fact]
    public void MissingSideIsAnOpenChain()
    {
        var result = BoundaryCycleTopology.Analyze(new[] { (0, 1), (1, 2), (2, 3) });
        Assert.Equal("OPEN_BOUNDARY_CHAIN", result.Reason);
        Assert.Equal(2, result.Ends);
    }

    [Fact]
    public void TouchingLoopsAreBranchedNotOneBoundary()
    {
        var result = BoundaryCycleTopology.Analyze(new[] { (0, 1), (1, 0), (0, 2), (2, 0) });
        Assert.Equal("BRANCHED_BOUNDARY", result.Reason);
    }

    [Fact]
    public void EmptyBoundaryIsNotACap()
    {
        Assert.Equal("NO_NAKED_BOUNDARY", BoundaryCycleTopology.Analyze(Array.Empty<(int, int)>()).Reason);
    }

    [Fact]
    public void InvalidVertexIsRejected()
    {
        Assert.Equal("INVALID_BOUNDARY_VERTEX", BoundaryCycleTopology.Analyze(new[] { (-1, 0) }).Reason);
    }
}
