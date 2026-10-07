using System;

namespace SmartSkin.Rhino8;

// Local attachment evidence from physical inward co-normals of the occupied
// parent and cap domains. This does not establish global separation or nonoverlap.
internal static class NativeMatchSidednessPolicy
{
    internal static bool Complete(int required, int resolved, int failed) =>
        required > 0 && resolved == required && failed == 0;

    internal static bool Opposed(double[] first, double[] second, out double signedDot)
    {
        signedDot = double.NaN;
        if (!Normalize(first, out var ax, out var ay, out var az)
            || !Normalize(second, out var bx, out var by, out var bz))
            return false;

        // Keep the sign: equal tangent planes and shape operators can still meet
        // on the same occupied side. Abs(dot) would incorrectly accept that cusp.
        // G1's physical normal-angle gate is evaluated separately. Do not impose
        // a second angular tolerance on trim/3D-edge correspondence here.
        signedDot = Math.Max(-1, Math.Min(1, ax * bx + ay * by + az * bz));
        return signedDot < 0;
    }

    internal static bool TryInward(double[] su, double[] sv, double trimU, double trimV,
        int materialLeftSign, out double[] inward)
    {
        inward = Array.Empty<double>();
        if (!ValidVector(su) || !ValidVector(sv) || !Finite(trimU) || !Finite(trimV)
            || (materialLeftSign != 1 && materialLeftSign != -1))
            return false;

        var trimScale = Math.Max(Math.Abs(trimU), Math.Abs(trimV));
        var surfaceScale = Math.Max(MaxComponent(su), MaxComponent(sv));
        if (trimScale == 0 || surfaceScale == 0) return false;
        trimU /= trimScale; trimV /= trimScale;
        var trimLength = Math.Sqrt(trimU * trimU + trimV * trimV);
        trimU /= trimLength; trimV /= trimLength;
        // One common Jacobian scale preserves the relative Su/Sv magnitudes.
        var mappedTangent = new[]
        {
            su[0] / surfaceScale * trimU + sv[0] / surfaceScale * trimV,
            su[1] / surfaceScale * trimU + sv[1] / surfaceScale * trimV,
            su[2] / surfaceScale * trimU + sv[2] / surfaceScale * trimV
        };
        if (!Normalize(mappedTangent, out var tx, out var ty, out var tz)) return false;

        // Independent derivative normalization is safe ONLY for the chart normal:
        // it preserves Su x Sv's direction, but would alter the mapped tangent.
        if (!Normalize(su, out var ux, out var uy, out var uz)
            || !Normalize(sv, out var vx, out var vy, out var vz)) return false;
        var normal = new[] { uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx };
        if (!Normalize(normal, out var nx, out var ny, out var nz)) return false;

        // Occupancy belongs to this face's mapped 2D trim frame, not to an
        // independently approximated 3D edge tangent or face-normal convention.
        var coNormal = new[] { ny * tz - nz * ty, nz * tx - nx * tz, nx * ty - ny * tx };
        if (!Normalize(coNormal, out var x, out var y, out var z)) return false;
        inward = new[] { materialLeftSign * x, materialLeftSign * y, materialLeftSign * z };
        return true;
    }

    private static bool Normalize(double[] vector, out double x, out double y, out double z)
    {
        x = y = z = 0;
        if (!ValidVector(vector)) return false;
        var scale = MaxComponent(vector);
        if (scale == 0) return false;

        // Divide before squaring, avoiding both overflow and subnormal underflow.
        x = vector[0] / scale; y = vector[1] / scale; z = vector[2] / scale;
        var length = Math.Sqrt(x * x + y * y + z * z);
        x /= length; y /= length; z /= length;
        return true;
    }

    private static bool ValidVector(double[] vector) => vector is not null && vector.Length == 3
        && Finite(vector[0]) && Finite(vector[1]) && Finite(vector[2]);
    private static double MaxComponent(double[] vector) =>
        Math.Max(Math.Abs(vector[0]), Math.Max(Math.Abs(vector[1]), Math.Abs(vector[2])));
    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
}
