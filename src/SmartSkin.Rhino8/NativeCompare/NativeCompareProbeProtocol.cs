using System;
using System.Globalization;

namespace SmartSkin.Rhino8;

/// <summary>Bounded N2 experiment and scalar reporting; no Rhino dependency or geometry claims.</summary>
internal static class NativeCompareProbeProtocol
{
    internal const int TargetSide = 0;
    internal const int MaximumConstructionCalls = 3; // One EdgeSrf seed and two independent Match calls.

    internal static void RunIndependent<T>(T seed, Func<T, T> duplicate, Action<T, bool> run)
        where T : class, IDisposable
    {
        foreach (var reverse in new[] { false, true })
        {
            var copy = duplicate(seed);
            if (copy is null || ReferenceEquals(seed, copy))
                throw new InvalidOperationException("INDEPENDENT_SEED_COPY_REQUIRED");
            try { run(copy, reverse); }
            finally { copy.Dispose(); }
        }
    }

    internal static string Number(double value) => NativeCompareMath.Finite(value)
        ? value.ToString("G17", CultureInfo.InvariantCulture) : "NOT_VERIFIED";
    internal static string Point(double x, double y, double z) => "(" + Number(x) + "," + Number(y) + "," + Number(z) + ")";
    internal static string Relation(int side) => side == TargetSide ? "TARGET" : side == 2 ? "OPPOSITE" : "ADJACENT";
}

internal sealed class NativeCompareStationMetrics
{
    internal int Expected, Located, WithinG0, Unresolved, ExpectedEndpoints, UnresolvedEndpoints;
    internal int PairedFrames, FramesWithinG0, FrameFailures;
    internal double MaximumGap = double.NaN;
    internal double MaximumAlignedNormalDegrees = double.NaN;
    internal double MinimumSignedNormalDot = double.NaN, MaximumSignedNormalDot = double.NaN;
    internal double MaximumSpectralW = double.NaN, MaximumFrobeniusW = double.NaN;
    internal double MaximumG0QualifiedNormalDegrees = double.NaN, MaximumG0QualifiedSpectralW = double.NaN;
    internal double MaximumG0QualifiedFrobeniusW = double.NaN;

    internal void UnresolvedStation(bool endpoint)
    {
        Expected++; Unresolved++;
        if (endpoint) { ExpectedEndpoints++; UnresolvedEndpoints++; }
    }
    internal void LocatedStation(bool endpoint, double gap, double tolerance)
    {
        if (!NativeCompareMath.Finite(gap) || gap < 0) throw new ArgumentOutOfRangeException(nameof(gap));
        Expected++; Located++;
        if (endpoint) ExpectedEndpoints++;
        MaximumGap = Max(MaximumGap, gap);
        if (gap <= tolerance) WithinG0++;
    }
    internal void PairedFrame(double signedNormalDot, double alignedDegrees, double spectralW, double frobeniusW, bool withinG0)
    {
        if (!NativeCompareMath.Finite(signedNormalDot) || !NativeCompareMath.Finite(alignedDegrees)
            || !NativeCompareMath.Finite(spectralW) || !NativeCompareMath.Finite(frobeniusW))
        { FrameFailures++; return; }
        PairedFrames++;
        if (withinG0)
        {
            FramesWithinG0++;
            MaximumG0QualifiedNormalDegrees = Max(MaximumG0QualifiedNormalDegrees, alignedDegrees);
            MaximumG0QualifiedSpectralW = Max(MaximumG0QualifiedSpectralW, spectralW);
            MaximumG0QualifiedFrobeniusW = Max(MaximumG0QualifiedFrobeniusW, frobeniusW);
        }
        MinimumSignedNormalDot = double.IsNaN(MinimumSignedNormalDot) ? signedNormalDot : Math.Min(MinimumSignedNormalDot, signedNormalDot);
        MaximumSignedNormalDot = Max(MaximumSignedNormalDot, signedNormalDot);
        MaximumAlignedNormalDegrees = Max(MaximumAlignedNormalDegrees, alignedDegrees);
        MaximumSpectralW = Max(MaximumSpectralW, spectralW);
        MaximumFrobeniusW = Max(MaximumFrobeniusW, frobeniusW);
    }
    internal string Format()
    {
        var n = new Func<double, string>(NativeCompareProbeProtocol.Number);
        return "expected_stations=" + Expected + " | located_stations=" + Located
            + " | within_G0=" + WithinG0 + " | outside_G0=" + (Located - WithinG0)
            + " | unresolved_stations=" + Unresolved + " | expected_endpoints=" + ExpectedEndpoints
            + " | unresolved_endpoints=" + UnresolvedEndpoints + " | max_gap=" + n(MaximumGap)
            + " | paired_frames=" + PairedFrames + " | paired_frames_within_G0=" + FramesWithinG0
            + " | failed_frames=" + FrameFailures + " | projected_signed_normal_dot_min=" + n(MinimumSignedNormalDot)
            + " | projected_signed_normal_dot_max=" + n(MaximumSignedNormalDot)
            + " | projected_aligned_normal_degrees=" + n(MaximumAlignedNormalDegrees)
            + " | projected_full_W_spectral_per_model_unit=" + n(MaximumSpectralW)
            + " | projected_full_W_frobenius_per_model_unit=" + n(MaximumFrobeniusW)
            + " | G0_qualified_aligned_normal_degrees=" + n(MaximumG0QualifiedNormalDegrees)
            + " | G0_qualified_full_W_spectral_per_model_unit=" + n(MaximumG0QualifiedSpectralW)
            + " | G0_qualified_full_W_frobenius_per_model_unit=" + n(MaximumG0QualifiedFrobeniusW)
            + " | projected_frames_are_not_continuity_proof=true | global_G2=NOT_VERIFIED";
    }
    private static double Max(double current, double value) => double.IsNaN(current) ? value : Math.Max(current, value);
}
