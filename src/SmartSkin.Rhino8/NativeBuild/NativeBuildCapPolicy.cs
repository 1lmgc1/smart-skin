using System;

namespace SmartSkin.Rhino8;

// One finite station's binary64 Jacobian-rank screen. This does not establish
// orientation, separation, nonintersection, or regularity between sampled stations.
// Any role-bound exact upper-point exception belongs to the native caller, never here.
internal static class NativeBuildCapPolicy
{
    // The spacing above 1.0, NOT System.Double.Epsilon (the smallest subnormal).
    internal const double Binary64MachineEpsilon = 2.2204460492503131e-16;
    internal const double MinimumRelativeJacobian = 64 * Binary64MachineEpsilon;

    // Pass native derivatives directly. Independent normalization cancels nonzero
    // affine U/V domain scale factors and common model-unit scale without first
    // multiplying by domain lengths or dividing by model extent (which could overflow).
    // The threshold diagnoses numerically unresolved rank, not physical G0/G1/G2 error.
    internal static bool RegularJacobian(double[] du, double[] dv)
    {
        if (!UnitDirection(du, out var ux, out var uy, out var uz)
            || !UnitDirection(dv, out var vx, out var vy, out var vz)) return false;
        var x = uy * vz - uz * vy;
        var y = uz * vx - ux * vz;
        var z = ux * vy - uy * vx;
        return Math.Sqrt(x * x + y * y + z * z) > MinimumRelativeJacobian;
    }

    private static bool UnitDirection(double[] vector, out double x, out double y, out double z)
    {
        x = y = z = 0;
        if (vector is null || vector.Length != 3) return false;
        var scale = 0.0;
        foreach (var value in vector)
        {
            if (double.IsNaN(value) || double.IsInfinity(value)) return false;
            scale = Math.Max(scale, Math.Abs(value));
        }
        if (scale == 0) return false;
        x = vector[0] / scale; y = vector[1] / scale; z = vector[2] / scale;
        var length = Math.Sqrt(x * x + y * y + z * z);
        x /= length; y /= length; z /= length;
        return true;
    }
}
