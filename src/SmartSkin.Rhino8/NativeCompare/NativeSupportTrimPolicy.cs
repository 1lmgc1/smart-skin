using System;
using System.Collections.Generic;

namespace SmartSkin.Rhino8;

// Diagnostic eligibility only. Neither these sampled thresholds nor a native Split return value authorizes Add.
internal sealed class NativeSupportTrimPolicy
{
    internal readonly double PositionTolerance, AngleToleranceRadians, SourceScale, OperatorTolerance;
    internal NativeSupportTrimPolicy(double positionTolerance, double angleToleranceRadians, double sourceScale)
    {
        if (!Positive(positionTolerance) || !Positive(angleToleranceRadians) || angleToleranceRadians >= Math.PI / 2 || !Positive(sourceScale))
            throw new ArgumentOutOfRangeException(nameof(sourceScale), "Finite bounded captured tolerances and a positive compatibility scale are required.");
        PositionTolerance = positionTolerance; AngleToleranceRadians = angleToleranceRadians; SourceScale = sourceScale;
        // Preserve the existing physical contract, including its historical large-model floor.
        // sourceScale is the original-curve tolerance-compatibility extent, never a new support hull.
        OperatorTolerance = Math.Max(1e-5 / sourceScale, 1e-8);
        if (!Positive(OperatorTolerance)) throw new ArgumentOutOfRangeException(nameof(sourceScale));
    }
    internal bool StationEligible(bool mappingResolved, bool regular, double gap, double angleRadians,
        double operatorResidual, bool approvedUpperPoint)
    {
        if (!mappingResolved || !NativeCompareMath.Finite(gap) || gap < 0 || gap > PositionTolerance) return false;
        if (approvedUpperPoint) return true; // Exact role-bound point only; never an interval or a G0 exception.
        return regular && NativeCompareMath.Finite(angleRadians) && angleRadians >= 0 && angleRadians <= AngleToleranceRadians
            && NativeCompareMath.Finite(operatorResidual) && operatorResidual >= 0 && operatorResidual <= OperatorTolerance;
    }
    internal static bool TryCloseScreeningLoop(IReadOnlyList<(double U, double V)> samples, double normalizedTolerance,
        out (double U, double V)[] closed)
    {
        closed = Array.Empty<(double U, double V)>();
        if (samples.Count < 4 || !Positive(normalizedTolerance)) return false;
        foreach (var point in samples)
            if (!NativeCompareMath.Finite(point.U) || !NativeCompareMath.Finite(point.V)) return false;
        var du = samples[0].U - samples[samples.Count - 1].U;
        var dv = samples[0].V - samples[samples.Count - 1].V;
        if (Math.Sqrt(du * du + dv * dv) > normalizedTolerance) return false;
        closed = new (double U, double V)[samples.Count];
        for (var i = 0; i < samples.Count; i++) closed[i] = samples[i];
        closed[closed.Length - 1] = closed[0]; // A derived bookkeeping loop only; original samples/cutters are untouched.
        return true;
    }
    internal static int UniqueIndex(IReadOnlyList<bool> eligible)
    {
        var result = -1;
        for (var i = 0; i < eligible.Count; i++)
            if (eligible[i]) { if (result >= 0) return -2; result = i; }
        return result;
    }
    internal static bool RegionEligible(bool valid, int outerLoops, int innerLoops,
        bool originalLoopMatched, int sourcePieces, int coveredSourcePieces,
        int outputBoundaryPieces, int coveredOutputBoundaryPieces, bool allStationsPassed)
        => valid && outerLoops == 1 && innerLoops == 0 && originalLoopMatched && sourcePieces > 0
            && sourcePieces == coveredSourcePieces && outputBoundaryPieces > 0
            && outputBoundaryPieces == coveredOutputBoundaryPieces && allStationsPassed;
    private static bool Positive(double value) => NativeCompareMath.Finite(value) && value > 0;
}
