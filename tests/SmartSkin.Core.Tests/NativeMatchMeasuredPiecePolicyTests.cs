using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeMatchMeasuredPiecePolicyTests
{
    [Fact]
    public void G0RequiresBothSamplingDirectionsAndNoUnresolvedOrGapFailures()
    {
        Assert.True(NativeMatchMeasuredPiecePolicy.G0(11, 7, 0, 0));
        Assert.True(NativeMatchMeasuredPiecePolicy.G0(int.MaxValue, int.MaxValue, 0, 0));
        foreach (var counts in new[] { (0, 0, 0, 0), (11, 0, 0, 0), (0, 7, 0, 0),
            (-1, 7, 0, 0), (11, -1, 0, 0), (11, 7, -1, 0), (11, 7, 0, -1),
            (11, 7, 1, 0), (11, 7, 0, 1), (11, 7, 99, 99) })
            Assert.False(NativeMatchMeasuredPiecePolicy.G0(counts.Item1, counts.Item2, counts.Item3, counts.Item4));
    }

    [Theory]
    [InlineData(0, 0)]
    [InlineData(0, 1)]
    [InlineData(1, 0)]
    [InlineData(3, 2)]
    [InlineData(3, 4)]
    [InlineData(-1, -1)]
    [InlineData(3, -1)]
    public void MissingOrInconsistentNormalAndFullFrameCountsReject(int required, int measured)
    {
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, required, measured, 0, .01));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, required, measured, 0, .02));
    }

    [Fact]
    public void UpperExceptionsCannotTurnAnEmptyRequiredSetIntoContinuity()
    {
        var g0 = NativeMatchMeasuredPiecePolicy.G0(2, 2, 0, 0);
        Assert.True(g0);
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(g0, 0, 0, 0, .01));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, 0, 0, 0, .02));
    }

    [Fact]
    public void MissingFullWFramesRejectG2WithoutErasingMeasuredG1()
    {
        var g0 = NativeMatchMeasuredPiecePolicy.G0(9, 13, 0, 0);
        var g1 = NativeMatchMeasuredPiecePolicy.G1(g0, 7, 7, .001, .01);
        Assert.True(g1);
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(g1, 7, 6, .001, .02));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(g1, 7, 0, double.NaN, .02));
        Assert.True(NativeMatchMeasuredPiecePolicy.G2(g1, 7, 7, .001, .02));
    }

    [Fact]
    public void UpstreamFailureCannotBeOverriddenByCompleteDownstreamMetrics()
    {
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(false, 7, 7, 0, .01));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(false, 7, 7, 0, .02));
    }

    [Fact]
    public void ExactThresholdEqualityAndZeroErrorPassButExceededGateFails()
    {
        Assert.True(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, .01, .01));
        Assert.True(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, 0, double.Epsilon));
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, .010001, .01));
        Assert.True(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, .02, .02));
        Assert.True(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, 0, double.Epsilon));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, .020001, .02));
    }

    [Fact]
    public void NonfiniteOrNegativeMaximaNeverPass()
    {
        foreach (var invalid in new[] { double.NaN, double.NegativeInfinity, double.PositiveInfinity, -double.Epsilon })
        {
            Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, invalid, .01));
            Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, invalid, .02));
        }
    }

    [Fact]
    public void InvalidCapturedGatesNeverPass()
    {
        foreach (var invalid in new[] { double.NaN, double.NegativeInfinity, double.PositiveInfinity, -1.0, 0 })
        {
            Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, 0, invalid));
            Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, 0, invalid));
        }
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, 0, Math.PI / 2));
        Assert.False(NativeMatchMeasuredPiecePolicy.G1(true, 7, 7, 0, Math.PI));
        Assert.False(NativeMatchMeasuredPiecePolicy.G2(true, 7, 7, 0, null));
    }
}
