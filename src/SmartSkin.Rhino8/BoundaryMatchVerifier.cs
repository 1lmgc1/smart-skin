using System;
using System.Collections.Generic;
using System.Linq;
using Rhino;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class BoundaryMatchMetrics
{
    private BoundaryMatchMetrics(
        bool available,
        bool verified,
        string token,
        string message,
        double maximumGap,
        double maximumNormalAngleDegrees,
        double maximumCurvatureDeviationPercent,
        int sampleCount)
    {
        Available = available;
        Verified = verified;
        Token = token;
        Message = message;
        MaximumGap = maximumGap;
        MaximumNormalAngleDegrees = maximumNormalAngleDegrees;
        MaximumCurvatureDeviationPercent = maximumCurvatureDeviationPercent;
        SampleCount = sampleCount;
    }

    public bool Available { get; }

    public bool Verified { get; }

    public string Token { get; }

    public string Message { get; }

    public double MaximumGap { get; }

    public double MaximumNormalAngleDegrees { get; }

    public double MaximumCurvatureDeviationPercent { get; }

    public int SampleCount { get; }

    public static BoundaryMatchMetrics Unavailable(string message)
    {
        return new BoundaryMatchMetrics(
            false,
            false,
            "NOT_VERIFIED",
            message,
            double.NaN,
            double.NaN,
            double.NaN,
            0);
    }

    public static BoundaryMatchMetrics Evaluated(
        CandidateBuildSettings settings,
        double maximumGap,
        double maximumNormalAngleDegrees,
        double maximumCurvatureDeviationPercent,
        int sampleCount,
        double absoluteTolerance,
        double angleToleranceRadians)
    {
        var positionPass = maximumGap <= absoluteTolerance + 1e-12;
        var tangentPass = settings.Continuity == MatchContinuityLevel.Position
            || maximumNormalAngleDegrees <= RhinoMath.ToDegrees(angleToleranceRadians) + 1e-6;
        var curvaturePass = settings.Continuity != MatchContinuityLevel.Curvature
            || maximumCurvatureDeviationPercent <= settings.CurvatureTolerancePercent + 1e-9;
        var verified = positionPass && tangentPass && curvaturePass;
        var verificationToken = settings.Continuity == MatchContinuityLevel.Position
            ? settings.ContinuityToken
            : settings.ContinuityToken + "_SAMPLED";
        var token = verified
            ? verificationToken + "_VERIFIED"
            : verificationToken + "_OUT_OF_TOLERANCE";

        return new BoundaryMatchMetrics(
            true,
            verified,
            token,
            verified
                ? settings.Continuity == MatchContinuityLevel.Position
                    ? "G0 boundary position verified against the selected Brep edges."
                    : $"{settings.ContinuityToken} boundary continuity passed bounded near-end and span-scaled sampling against the adjacent Brep faces."
                : "The native match was built, but measured boundary continuity is outside the selected tolerance.",
            maximumGap,
            maximumNormalAngleDegrees,
            maximumCurvatureDeviationPercent,
            sampleCount);
    }
}

internal static class BoundaryMatchVerifier
{
    private const int MinimumSamplesPerTargetEdge = 12;
    private const int MaximumSamplesPerTargetEdge = 64;
    private const int SamplesPerSpan = 4;
    private const double NearEndFraction = 1e-5;

    public static BoundaryMatchMetrics Verify(
        Brep candidate,
        IReadOnlyList<BrepEdge> targetEdges,
        CandidateBuildSettings settings,
        double absoluteTolerance,
        double angleToleranceRadians)
    {
        if (candidate is null)
        {
            throw new ArgumentNullException(nameof(candidate));
        }

        if (targetEdges is null || targetEdges.Count == 0)
        {
            return BoundaryMatchMetrics.Unavailable("No target Brep edges were available for continuity verification.");
        }

        var targetCopies = targetEdges.Select(edge => edge.DuplicateCurve()).ToList();
        Curve[]? joinedTargets = null;
        try
        {
            joinedTargets = Curve.JoinCurves(targetCopies, absoluteTolerance, false);
            if (joinedTargets is null || joinedTargets.Length != 1 || !joinedTargets[0].IsClosed)
            {
                return BoundaryMatchMetrics.Unavailable(
                    "The matched target edges could not be rejoined into one closed verification loop.");
            }

            var targetLoop = joinedTargets[0];
            var candidateEdge = FindMatchingBoundaryEdge(candidate, targetLoop, absoluteTolerance);
            if (candidateEdge is null)
            {
                return BoundaryMatchMetrics.Unavailable(
                    "The matched cap does not expose one closed natural boundary edge for verification.");
            }

            if (!Curve.GetDistancesBetweenCurves(
                    candidateEdge,
                    targetLoop,
                    Math.Max(absoluteTolerance * 0.1, 1e-9),
                    out var maximumGap,
                    out _,
                    out _,
                    out _,
                    out _,
                    out _))
            {
                return BoundaryMatchMetrics.Unavailable("Rhino could not measure the matched boundary gap.");
            }

            if (!IsFinite(maximumGap))
            {
                return BoundaryMatchMetrics.Unavailable("Rhino returned a non-finite matched boundary gap.");
            }

            var candidateFace = AdjacentFace(candidateEdge);
            if (candidateFace is null)
            {
                return BoundaryMatchMetrics.Unavailable("The matched cap boundary has no unambiguous adjacent face.");
            }

            var maximumAngleDegrees = settings.Continuity == MatchContinuityLevel.Position
                ? double.NaN
                : 0.0;
            var maximumCurvaturePercent = settings.Continuity == MatchContinuityLevel.Curvature
                ? 0.0
                : double.NaN;
            var sampleCount = 0;

            if (settings.Continuity != MatchContinuityLevel.Position)
            {
                foreach (var targetEdge in targetEdges)
                {
                    var targetFace = AdjacentFace(targetEdge);
                    if (targetFace is null)
                    {
                        return BoundaryMatchMetrics.Unavailable(
                            "One target boundary edge has no unambiguous adjacent face.");
                    }

                    var samplesForEdge = Math.Min(
                        MaximumSamplesPerTargetEdge,
                        Math.Max(MinimumSamplesPerTargetEdge, (targetEdge.SpanCount * SamplesPerSpan) + 1));
                    for (var sample = 0; sample < samplesForEdge; sample++)
                    {
                        var normalizedLength = NearEndFraction
                            + ((1.0 - (2.0 * NearEndFraction)) * sample / (samplesForEdge - 1.0));
                        if (!targetEdge.NormalizedLengthParameter(normalizedLength, out var targetParameter))
                        {
                            return BoundaryMatchMetrics.Unavailable(
                                "Rhino could not parameterize one target edge for continuity sampling.");
                        }

                        var targetPoint = targetEdge.PointAt(targetParameter);
                        if (!candidateEdge.ClosestPoint(targetPoint, out var candidateParameter)
                            || !TryFaceParametersAtEdgeParameter(
                                candidateEdge,
                                candidateParameter,
                                out var candidateEdgeFace,
                                out var candidateU,
                                out var candidateV)
                            || !TryFaceParametersAtEdgeParameter(
                                targetEdge,
                                targetParameter,
                                out var targetEdgeFace,
                                out var targetU,
                                out var targetV)
                            || candidateEdgeFace.FaceIndex != candidateFace.FaceIndex
                            || targetEdgeFace.FaceIndex != targetFace.FaceIndex)
                        {
                            return BoundaryMatchMetrics.Unavailable(
                                "Rhino could not map one boundary sample through its Brep trims to both adjacent faces.");
                        }

                        var candidateNormal = OrientedNormal(candidateFace, candidateU, candidateV);
                        var targetNormal = OrientedNormal(targetFace, targetU, targetV);
                        if (!candidateNormal.Unitize() || !targetNormal.Unitize())
                        {
                            return BoundaryMatchMetrics.Unavailable(
                                "One boundary sample returned an invalid adjacent-face normal.");
                        }

                        var signedNormalDot = Vector3d.Multiply(candidateNormal, targetNormal);
                        if (!IsFinite(signedNormalDot))
                        {
                            return BoundaryMatchMetrics.Unavailable(
                                "One boundary sample returned a non-finite normal comparison.");
                        }

                        var dot = Math.Abs(signedNormalDot);
                        dot = Math.Max(-1.0, Math.Min(1.0, dot));
                        maximumAngleDegrees = Math.Max(
                            maximumAngleDegrees,
                            RhinoMath.ToDegrees(Math.Acos(dot)));

                        if (settings.Continuity == MatchContinuityLevel.Curvature)
                        {
                            var candidateCurvature = candidateFace.CurvatureAt(candidateU, candidateV);
                            var targetCurvature = targetFace.CurvatureAt(targetU, targetV);
                            if (candidateCurvature is null || targetCurvature is null)
                            {
                                return BoundaryMatchMetrics.Unavailable(
                                    "One boundary sample returned no surface-curvature data.");
                            }

                            var targetTangent = targetEdge.TangentAt(targetParameter);
                            var candidateTangent = candidateEdge.TangentAt(candidateParameter);
                            if (!targetTangent.Unitize() || !candidateTangent.Unitize())
                            {
                                return BoundaryMatchMetrics.Unavailable(
                                    "One boundary sample returned an invalid edge tangent.");
                            }

                            var targetAcross = Vector3d.CrossProduct(targetNormal, targetTangent);
                            var candidateAcross = Vector3d.CrossProduct(candidateNormal, candidateTangent);
                            if (!targetAcross.Unitize() || !candidateAcross.Unitize())
                            {
                                return BoundaryMatchMetrics.Unavailable(
                                    "One boundary sample returned an invalid cross-boundary direction.");
                            }

                            if (!TryNormalCurvature(
                                    targetCurvature,
                                    targetAcross,
                                    targetFace.OrientationIsReversed,
                                    out var targetNormalCurvature)
                                || !TryNormalCurvature(
                                    candidateCurvature,
                                    candidateAcross,
                                    candidateFace.OrientationIsReversed,
                                    out var candidateNormalCurvature))
                            {
                                return BoundaryMatchMetrics.Unavailable(
                                    "One boundary sample returned invalid principal-curvature data.");
                            }

                            if (signedNormalDot < 0.0)
                            {
                                candidateNormalCurvature = -candidateNormalCurvature;
                            }

                            maximumCurvaturePercent = Math.Max(
                                maximumCurvaturePercent,
                                RadiusDeviationPercent(targetNormalCurvature, candidateNormalCurvature));
                        }

                        sampleCount++;
                    }
                }
            }

            return BoundaryMatchMetrics.Evaluated(
                settings,
                maximumGap,
                maximumAngleDegrees,
                maximumCurvaturePercent,
                sampleCount,
                absoluteTolerance,
                angleToleranceRadians);
        }
        finally
        {
            foreach (var curve in targetCopies)
            {
                curve.Dispose();
            }

            if (joinedTargets is not null)
            {
                foreach (var curve in joinedTargets)
                {
                    curve?.Dispose();
                }
            }
        }
    }

    private static BrepEdge? FindMatchingBoundaryEdge(Brep candidate, Curve targetLoop, double tolerance)
    {
        BrepEdge? best = null;
        var bestDeviation = double.MaxValue;
        foreach (var edge in candidate.Edges)
        {
            if (edge.Valence != EdgeAdjacency.Naked || !edge.IsClosed || !IsNaturalBoundary(edge))
            {
                continue;
            }

            if (!Curve.GetDistancesBetweenCurves(
                    edge,
                    targetLoop,
                    Math.Max(tolerance * 0.1, 1e-9),
                    out var maximumDistance,
                    out _,
                    out _,
                    out _,
                    out _,
                    out _))
            {
                continue;
            }

            if (maximumDistance < bestDeviation)
            {
                bestDeviation = maximumDistance;
                best = edge;
            }
        }

        return bestDeviation <= Math.Max(tolerance * 2.0, 1e-8) ? best : null;
    }

    internal static bool IsNaturalBoundary(BrepEdge edge)
    {
        var trimIndices = edge.TrimIndices();
        if (trimIndices.Length != 1 || edge.Brep is null)
        {
            return false;
        }

        var trimIndex = trimIndices[0];
        if (trimIndex < 0 || trimIndex >= edge.Brep.Trims.Count)
        {
            return false;
        }

        var trim = edge.Brep.Trims[trimIndex];
        var face = trim.Face;
        if (face is null || trim.TrimType != BrepTrimType.Boundary)
        {
            return false;
        }

        var start = trim.PointAtStart;
        var end = trim.PointAtEnd;
        var uDomain = face.Domain(0);
        var vDomain = face.Domain(1);
        return trim.IsoStatus switch
        {
            IsoStatus.West => IsAt(start.X, uDomain.T0, uDomain)
                && IsAt(end.X, uDomain.T0, uDomain)
                && Covers(start.Y, end.Y, vDomain),
            IsoStatus.South => IsAt(start.Y, vDomain.T0, vDomain)
                && IsAt(end.Y, vDomain.T0, vDomain)
                && Covers(start.X, end.X, uDomain),
            IsoStatus.East => IsAt(start.X, uDomain.T1, uDomain)
                && IsAt(end.X, uDomain.T1, uDomain)
                && Covers(start.Y, end.Y, vDomain),
            IsoStatus.North => IsAt(start.Y, vDomain.T1, vDomain)
                && IsAt(end.Y, vDomain.T1, vDomain)
                && Covers(start.X, end.X, uDomain),
            _ => false,
        };
    }

    internal static bool IsAverageTargetEligible(BrepEdge edge)
    {
        if (!IsNaturalBoundary(edge))
        {
            return false;
        }

        var trimIndices = edge.TrimIndices();
        return edge.Brep is not null
            && trimIndices.Length == 1
            && trimIndices[0] >= 0
            && trimIndices[0] < edge.Brep.Trims.Count
            && edge.Brep.Trims[trimIndices[0]].Face?.IsSurface == true;
    }

    private static bool Covers(double first, double second, Interval domain)
    {
        return IsAt(Math.Min(first, second), domain.T0, domain)
            && IsAt(Math.Max(first, second), domain.T1, domain);
    }

    private static bool IsAt(double value, double expected, Interval domain)
    {
        var parameterTolerance = Math.Max(Math.Abs(domain.Length) * 1e-8, 1e-10);
        return Math.Abs(value - expected) <= parameterTolerance;
    }

    private static BrepFace? AdjacentFace(BrepEdge edge)
    {
        var trimIndices = edge.TrimIndices();
        if (trimIndices.Length != 1 || edge.Brep is null)
        {
            return null;
        }

        var trimIndex = trimIndices[0];
        return trimIndex >= 0 && trimIndex < edge.Brep.Trims.Count
            ? edge.Brep.Trims[trimIndex].Face
            : null;
    }

    private static bool TryFaceParametersAtEdgeParameter(
        BrepEdge edge,
        double edgeParameter,
        out BrepFace face,
        out double u,
        out double v)
    {
        face = null!;
        u = double.NaN;
        v = double.NaN;
        var trimIndices = edge.TrimIndices();
        if (trimIndices.Length != 1 || edge.Brep is null)
        {
            return false;
        }

        var trimIndex = trimIndices[0];
        if (trimIndex < 0 || trimIndex >= edge.Brep.Trims.Count)
        {
            return false;
        }

        var trim = edge.Brep.Trims[trimIndex];
        if (trim.Face is null
            || !trim.GetTrimParameter(edgeParameter, out var trimParameter))
        {
            return false;
        }

        var parameters = trim.PointAt(trimParameter);
        if (!parameters.IsValid || !IsFinite(parameters.X) || !IsFinite(parameters.Y))
        {
            return false;
        }

        face = trim.Face;
        u = parameters.X;
        v = parameters.Y;
        return true;
    }

    private static Vector3d OrientedNormal(BrepFace face, double u, double v)
    {
        var normal = face.NormalAt(u, v);
        if (face.OrientationIsReversed)
        {
            normal.Reverse();
        }

        return normal;
    }

    private static bool TryNormalCurvature(
        SurfaceCurvature curvature,
        Vector3d direction,
        bool orientationIsReversed,
        out double normalCurvature)
    {
        var direction0 = curvature.Direction(0);
        var direction1 = curvature.Direction(1);
        if (!direction0.Unitize() || !direction1.Unitize())
        {
            normalCurvature = double.NaN;
            return false;
        }

        var kappa0 = curvature.Kappa(0);
        var kappa1 = curvature.Kappa(1);
        if (!IsFinite(kappa0) || !IsFinite(kappa1))
        {
            normalCurvature = double.NaN;
            return false;
        }

        var component0 = Vector3d.Multiply(direction, direction0);
        var component1 = Vector3d.Multiply(direction, direction1);
        var value = (kappa0 * component0 * component0)
            + (kappa1 * component1 * component1);
        normalCurvature = orientationIsReversed ? -value : value;
        return IsFinite(normalCurvature);
    }

    private static bool IsFinite(double value)
    {
        return !double.IsNaN(value) && !double.IsInfinity(value);
    }

    private static double RadiusDeviationPercent(double curvatureA, double curvatureB)
    {
        const double flatThreshold = 1e-12;
        var flatA = Math.Abs(curvatureA) <= flatThreshold;
        var flatB = Math.Abs(curvatureB) <= flatThreshold;
        if (flatA && flatB)
        {
            return 0.0;
        }

        if (flatA || flatB)
        {
            return double.PositiveInfinity;
        }

        var radiusA = 1.0 / curvatureA;
        var radiusB = 1.0 / curvatureB;
        return Math.Abs(radiusA - radiusB)
            / Math.Max(Math.Abs(radiusA), Math.Abs(radiusB))
            * 100.0;
    }
}
