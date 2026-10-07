using System;

namespace SmartSkin.Rhino8;

// Completeness of one original piece's native measurements. A touched piece or an
// exception-only sample set supplies no continuity proof. These finite measurements
// do not establish global regularity or continuity between sampled stations.
internal static class NativeMatchMeasuredPiecePolicy
{
    internal static bool G0(int sourceStations, int candidateStations, int unresolved, int gapFailures) =>
        sourceStations > 0 && candidateStations > 0 && unresolved == 0 && gapFailures == 0;

    // Normal measurements stand on their own: missing W frames cannot erase measured G1.
    // limit is the unchanged captured document angle tolerance, in radians.
    internal static bool G1(bool g0, int required, int normals, double maxAngle, double limit) =>
        g0 && required > 0 && normals == required
        && Finite(maxAngle) && maxAngle >= 0 && Finite(limit) && limit > 0 && limit < Math.PI / 2
        && maxAngle <= limit;

    // limit is the unchanged absolute full-W gate, not the native solver radius percent.
    internal static bool G2(bool g1, int required, int fullFrames, double maxW, double? limit) =>
        g1 && required > 0 && fullFrames == required && Finite(maxW) && maxW >= 0
        && limit.HasValue && Finite(limit.Value) && limit.Value > 0 && maxW <= limit.Value;

    private static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
}
