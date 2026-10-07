using System;
using System.Collections.Generic;

namespace SmartSkin.Rhino8;

/// <summary>Sort-only points for corners whose incident endpoints already passed native partner validation.</summary>
internal readonly struct NativeCompareCornerPoint
{
    internal readonly double X, Y, Z;
    internal NativeCompareCornerPoint(double x, double y, double z) { X = x; Y = y; Z = z; }
    internal bool IsFinite => Finite(X) && Finite(Y) && Finite(Z);
    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
}

internal static class NativeCompareCornerOrdering
{
    internal static bool TryChoose(IReadOnlyList<NativeCompareCornerPoint> incomingEnds,
        IReadOnlyList<NativeCompareCornerPoint> outgoingStarts, out int first, out bool reverse)
    {
        first = 0; reverse = false;
        if (incomingEnds.Count != 4 || outgoingStarts.Count != 4) return false;
        var corners = new NativeCompareCornerPoint[4];
        for (var i = 0; i < 4; i++)
        {
            var a = incomingEnds[i]; var b = outgoingStarts[i];
            if (!a.IsFinite || !b.IsFinite) return false;
            // Commutative and overflow-safe. This key never replaces either native endpoint.
            corners[i] = new NativeCompareCornerPoint(0.5 * a.X + 0.5 * b.X,
                0.5 * a.Y + 0.5 * b.Y, 0.5 * a.Z + 0.5 * b.Z);
            if (!corners[i].IsFinite) return false;
            for (var j = 0; j < i; j++)
                if (Compare(corners[i], corners[j]) == 0) return false;
            if (Compare(corners[i], corners[first]) < 0) first = i;
        }
        reverse = Compare(corners[(first + 1) % 4], corners[(first + 3) % 4]) > 0;
        return true;
    }

    private static int Compare(NativeCompareCornerPoint a, NativeCompareCornerPoint b)
    {
        var x = a.X.CompareTo(b.X); if (x != 0) return x;
        var y = a.Y.CompareTo(b.Y); return y != 0 ? y : a.Z.CompareTo(b.Z);
    }
}
