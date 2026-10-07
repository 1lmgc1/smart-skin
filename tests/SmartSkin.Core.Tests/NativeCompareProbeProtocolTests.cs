using System;
using System.Collections.Generic;
using System.Globalization;
using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

// Synthetic managed experiments. These do not execute Rhino or validate native side lineage.
public sealed class NativeCompareProbeProtocolTests
{
    private sealed class Seed : IDisposable
    {
        internal int Value;
        internal bool Disposed;
        public void Dispose() => Disposed = true;
    }

    [Fact]
    public void EachDirectionReceivesAnIndependentUnmodifiedBaseline()
    {
        using var seed = new Seed { Value = 7 };
        var copies = new List<Seed>();
        var reversals = new List<bool>();
        NativeCompareProbeProtocol.RunIndependent(seed, original =>
        {
            var copy = new Seed { Value = original.Value };
            copies.Add(copy);
            return copy;
        }, (copy, reverse) =>
        {
            Assert.Equal(7, copy.Value);
            reversals.Add(reverse);
            copy.Value = 99; // Mutating the first probe must never feed the second probe.
        });
        Assert.Equal(new[] { false, true }, reversals);
        Assert.Equal(7, seed.Value);
        Assert.False(seed.Disposed);
        Assert.All(copies, copy => Assert.True(copy.Disposed));
        Assert.NotSame(copies[0], copies[1]);
        Assert.Equal(0, NativeCompareProbeProtocol.TargetSide);
        Assert.Equal(3, NativeCompareProbeProtocol.MaximumConstructionCalls);
    }

    [Fact]
    public void FatalFailureDisposesItsCopyAndDoesNotStartAnotherProbe()
    {
        using var seed = new Seed();
        Seed? copy = null;
        var calls = 0;
        Assert.Throws<TimeoutException>(() => NativeCompareProbeProtocol.RunIndependent(seed,
            original => copy = new Seed(), (candidate, reverse) => { calls++; throw new TimeoutException(); }));
        Assert.Equal(1, calls);
        Assert.NotNull(copy);
        Assert.True(copy!.Disposed);
        Assert.False(seed.Disposed);
    }

    [Fact]
    public void AliasedSeedIsRejectedBeforeMutationOrDisposal()
    {
        using var seed = new Seed();
        Assert.Throws<InvalidOperationException>(() => NativeCompareProbeProtocol.RunIndependent(seed,
            original => original, (candidate, reverse) => throw new Exception("Must not run")));
        Assert.False(seed.Disposed);
    }

    [Fact]
    public void LocatedOrTouchedStationsDoNotImplyG0Coverage()
    {
        var metrics = new NativeCompareStationMetrics();
        metrics.LocatedStation(true, 0.0001, 0.001);
        metrics.LocatedStation(false, 2.0, 0.001);
        metrics.UnresolvedStation(true);
        Assert.Equal(3, metrics.Expected);
        Assert.Equal(2, metrics.Located);
        Assert.Equal(1, metrics.WithinG0);
        Assert.Equal(1, metrics.Unresolved);
        Assert.Equal(2, metrics.ExpectedEndpoints);
        Assert.Equal(1, metrics.UnresolvedEndpoints);
        Assert.Contains("within_G0=1 | outside_G0=1", metrics.Format());
        Assert.Contains("max_gap=2", metrics.Format());
        Assert.Contains("global_G2=NOT_VERIFIED", metrics.Format());
    }

    [Fact]
    public void UnavailableMeasurementsRemainUnavailableRatherThanZero()
    {
        var metrics = new NativeCompareStationMetrics();
        metrics.UnresolvedStation(true);
        Assert.Contains("max_gap=NOT_VERIFIED", metrics.Format());
        Assert.Contains("projected_aligned_normal_degrees=NOT_VERIFIED", metrics.Format());
        Assert.Contains("projected_full_W_spectral_per_model_unit=NOT_VERIFIED", metrics.Format());
    }

    [Fact]
    public void SeparatedProjectedFramesAreDistinctFromG0QualifiedFramesAndKeepNormalParity()
    {
        var metrics = new NativeCompareStationMetrics();
        metrics.LocatedStation(false, 2, 0.001);
        metrics.PairedFrame(-1, 0, 0.3, 0.4, false);
        Assert.Equal(1, metrics.PairedFrames);
        Assert.Equal(0, metrics.FramesWithinG0);
        Assert.Equal(-1, metrics.MinimumSignedNormalDot);
        Assert.Equal(0, metrics.MaximumAlignedNormalDegrees);
        Assert.Contains("projected_frames_are_not_continuity_proof=true", metrics.Format());
        Assert.True(double.IsNaN(metrics.MaximumG0QualifiedSpectralW));
        metrics.LocatedStation(false, 0, 0.001);
        metrics.PairedFrame(1, 0.01, 0.02, 0.03, true);
        Assert.Equal(0.3, metrics.MaximumSpectralW);
        Assert.Equal(0.02, metrics.MaximumG0QualifiedSpectralW);
        Assert.Equal(0.01, metrics.MaximumG0QualifiedNormalDegrees);
    }

    [Fact]
    public void InvalidFrameValuesDoNotBecomeMeasuredZeros()
    {
        var metrics = new NativeCompareStationMetrics();
        metrics.PairedFrame(double.NaN, 0, 0, 0, true);
        Assert.Equal(0, metrics.PairedFrames);
        Assert.Equal(1, metrics.FrameFailures);
        Assert.True(double.IsNaN(metrics.MaximumSpectralW));
    }

    [Fact]
    public void RuntimeCoordinateAndDomainFormattingIsCultureIndependentAndRoundTrips()
    {
        var previous = CultureInfo.CurrentCulture;
        try
        {
            CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("fr-FR");
            const double value = 0.12345678901234567;
            var text = NativeCompareProbeProtocol.Number(value);
            Assert.Equal(value, double.Parse(text, CultureInfo.InvariantCulture));
            Assert.Equal("(1.5,-2.25,0)", NativeCompareProbeProtocol.Point(1.5, -2.25, 0));
            Assert.Equal("TARGET", NativeCompareProbeProtocol.Relation(0));
            Assert.Equal("OPPOSITE", NativeCompareProbeProtocol.Relation(2));
            Assert.Equal("ADJACENT", NativeCompareProbeProtocol.Relation(1));
            Assert.Equal("ADJACENT", NativeCompareProbeProtocol.Relation(3));
        }
        finally { CultureInfo.CurrentCulture = previous; }
    }
}
