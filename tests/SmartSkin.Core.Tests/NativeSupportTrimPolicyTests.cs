using System;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

// Pure diagnostic policy tests. No native mapping, Split or attachment certificate is simulated here.
public sealed class NativeSupportTrimPolicyTests
{
    private static NativeSupportTrimPolicy Policy() => new(0.01, Math.PI / 180, 20);

    [Fact]
    public void TrimPrecheckRequiresIncidenceBeforeAnyJetResult()
    {
        var p = Policy();
        Assert.True(p.StationEligible(true, true, p.PositionTolerance, p.AngleToleranceRadians, p.OperatorTolerance, false));
        Assert.False(p.StationEligible(false, true, 0, 0, 0, false));
        Assert.False(p.StationEligible(true, true, p.PositionTolerance * 1.0001, 0, 0, false));
        Assert.False(p.StationEligible(true, true, -0.01, 0, 0, false));
    }

    [Fact]
    public void FiniteSourceStationsNeedRegularityAndBothPhysicalJetLimits()
    {
        var p = Policy();
        Assert.False(p.StationEligible(true, false, 0, 0, 0, false));
        Assert.False(p.StationEligible(true, true, 0, p.AngleToleranceRadians * 1.0001, 0, false));
        Assert.False(p.StationEligible(true, true, 0, 0, p.OperatorTolerance * 1.0001, false));
        Assert.False(p.StationEligible(true, true, 0, -1, 0, false));
        Assert.False(p.StationEligible(true, true, 0, 0, -1, false));
    }

    [Fact]
    public void ExactApprovedUpperPointStillNeedsResolvedUnmovedPosition()
    {
        var p = Policy();
        // Caller must bind this flag to the exact approved original vertex, never a near-end band.
        Assert.True(p.StationEligible(true, false, 0, double.NaN, double.NaN, true));
        Assert.False(p.StationEligible(false, false, 0, double.NaN, double.NaN, true));
        Assert.False(p.StationEligible(true, false, p.PositionTolerance * 2, double.NaN, double.NaN, true));
        // The same singular frame at any unapproved station is ineligible.
        Assert.False(p.StationEligible(true, false, 0, double.NaN, double.NaN, false));
    }

    [Fact]
    public void NonfiniteMeasurementsCannotCreateEligibility()
    {
        var p = Policy();
        foreach (var invalid in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity })
        {
            Assert.False(p.StationEligible(true, true, invalid, 0, 0, false));
            Assert.False(p.StationEligible(true, true, invalid, 0, 0, true));
            Assert.False(p.StationEligible(true, true, 0, invalid, 0, false));
            Assert.False(p.StationEligible(true, true, 0, 0, invalid, false));
        }
    }

    [Fact]
    public void InvalidOrUnboundedCapturedPolicyIsRejected()
    {
        foreach (var invalid in new[] { 0.0, -1, double.NaN, double.PositiveInfinity, double.NegativeInfinity })
        {
            Assert.Throws<ArgumentOutOfRangeException>(() => new NativeSupportTrimPolicy(invalid, 0.01, 20));
            Assert.Throws<ArgumentOutOfRangeException>(() => new NativeSupportTrimPolicy(0.01, invalid, 20));
            Assert.Throws<ArgumentOutOfRangeException>(() => new NativeSupportTrimPolicy(0.01, 0.01, invalid));
        }
        Assert.Throws<ArgumentOutOfRangeException>(() => new NativeSupportTrimPolicy(0.01, Math.PI / 2, 20));
        Assert.Throws<ArgumentOutOfRangeException>(() => new NativeSupportTrimPolicy(0.01, Math.PI, 20));
    }

    [Fact]
    public void GeometricallyScaledMeasurementHasTheSameDisposition()
    {
        var p = Policy();
        var scaled = new NativeSupportTrimPolicy(p.PositionTolerance * 10, p.AngleToleranceRadians, p.SourceScale * 10);
        // Stay on either side of the boundary; different binary64 division orders can
        // round an exactly-on-threshold unit conversion to opposite adjacent doubles.
        foreach (var factor in new[] { 0.5, 0.99, 1.01, 2.0 })
        {
            Assert.Equal(p.StationEligible(true, true, 0.005, 0.001, p.OperatorTolerance * factor, false),
                scaled.StationEligible(true, true, 0.05, 0.001, p.OperatorTolerance * factor / 10, false));
        }
        // Retain the documented pre-existing floor rather than silently tightening the contract.
        Assert.Equal(1e-8, new NativeSupportTrimPolicy(0.01, 0.01, 1e6).OperatorTolerance);
    }

    [Fact]
    public void NoOrMultipleRegionsCannotBeChosenByReturnedOrder()
    {
        Assert.Equal(-1, NativeSupportTrimPolicy.UniqueIndex(Array.Empty<bool>()));
        Assert.Equal(-1, NativeSupportTrimPolicy.UniqueIndex(new[] { false, false }));
        Assert.Equal(1, NativeSupportTrimPolicy.UniqueIndex(new[] { false, true, false }));
        Assert.Equal(-2, NativeSupportTrimPolicy.UniqueIndex(new[] { true, false, true }));
        Assert.Equal(-2, NativeSupportTrimPolicy.UniqueIndex(new[] { false, true, true }));
    }

    [Fact]
    public void SplitResultNeedsCompleteBidirectionalBoundaryCoverage()
    {
        Assert.True(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 6, 6, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 6, 5, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 6, 6, 8, 7, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 6, 6, 8, 8, false));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, false, 6, 6, 8, 8, true));
    }

    [Fact]
    public void InvalidEmptyHoledOrExtraRimRegionsAreIneligible()
    {
        Assert.False(NativeSupportTrimPolicy.RegionEligible(false, 1, 0, true, 6, 6, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 2, 0, true, 6, 6, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 1, true, 6, 6, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 0, 0, true, 6, 6, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 0, 0, 8, 8, true));
        Assert.False(NativeSupportTrimPolicy.RegionEligible(true, 1, 0, true, 6, 6, 0, 0, true));
    }

    [Fact]
    public void ScreeningLoopClosesOnlyItsCopyAfterTinyEndpointDisagreement()
    {
        var original = new[] { (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1e-12, -1e-12) };
        Assert.True(NativeSupportTrimPolicy.TryCloseScreeningLoop(original, 1e-8, out var closed));
        Assert.Equal(closed[0], closed[closed.Length - 1]);
        Assert.Equal((1e-12, -1e-12), original[original.Length - 1]);
        Assert.NotSame(original, closed);
    }

    [Fact]
    public void ScreeningLoopDoesNotBridgeARealUvBranchGap()
    {
        var original = new[] { (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1e-4, 0.0) };
        Assert.False(NativeSupportTrimPolicy.TryCloseScreeningLoop(original, 1e-8, out var closed));
        Assert.Empty(closed);
    }
}
