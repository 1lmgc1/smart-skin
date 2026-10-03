using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Rhino;
using Rhino.Geometry;
using SmartSkin.Core.Construction;

namespace SmartSkin.Rhino8;

internal sealed class BoundaryMatchMetrics
{
    public bool Available { get; internal set; }
    public bool Verified { get; internal set; }
    public string Token { get; internal set; } = "NOT_VERIFIED";
    public string Reason { get; internal set; } = "NOT_EVALUATED";
    public string Message { get; internal set; } = string.Empty;
    public double MaximumGap { get; internal set; } = double.NaN;
    public double MaximumNormalAngleDegrees { get; internal set; } = double.NaN;
    public double MaximumCurvatureDeviationPercent { get; internal set; } = double.NaN;
    public int SampleCount { get; internal set; }
    public int BoundaryEdgeCount { get; internal set; }
    public int BoundaryComponents { get; internal set; }
    public int CoveredTargetEdges { get; internal set; }
    public int CoveredCandidateEdges { get; internal set; }

    public static BoundaryMatchMetrics Unavailable(string message) => new()
    {
        Reason = "VERIFICATION_UNAVAILABLE",
        Message = message,
    };
}

/// <summary>Verifies the whole naked boundary, retaining its original edge/trim/face
/// ownership. G1/G2 remain bounded sampled measurements, not an analytic proof.</summary>
internal static class BoundaryMatchVerifier
{
    private const int MaximumBoundaryEdges = 128;
    private const int MaximumSamples = 8192;
    private const double NearEndFraction = 1e-5;

    public static BoundaryMatchMetrics Verify(
        Brep candidate, IReadOnlyList<BrepEdge> targetEdges,
        CandidateBuildSettings settings, double absoluteTolerance, double angleToleranceRadians,
        string variant = "unspecified", bool writeDiagnostics = false,
        Func<bool>? cancellationRequested = null)
    {
        var result = new BoundaryMatchMetrics();
        BoundaryMatchMetrics Stop(string reason, string detail, bool measured = false)
        {
            result.Reason = reason;
            result.Message = reason + ": " + detail;
            result.Available = measured;
            result.Verified = false;
            if (measured) result.Token = reason == "BOUNDARY_GAP_OUT_OF_TOLERANCE"
                ? "G0_OUT_OF_TOLERANCE" : settings.ContinuityToken + "_SAMPLED_OUT_OF_TOLERANCE";
            return result;
        }

        Curve? candidateLoop = null;
        Curve? targetLoop = null;
        try
        {
            if (candidate is null || !candidate.IsValid || candidate.Faces.Count == 0
                || candidate.Faces.Count > 128 || candidate.Edges.Count > 512)
                return Stop("INVALID_CANDIDATE", "Invalid or over-limit Brep.");
            if (!IsFinite(absoluteTolerance) || absoluteTolerance <= 0
                || !IsFinite(angleToleranceRadians) || angleToleranceRadians <= 0
                || !IsFinite(settings.CurvatureTolerancePercent))
                return Stop("INVALID_TOLERANCE", "Tolerances must be finite and positive.");
            if (targetEdges is null || targetEdges.Count == 0 || targetEdges.Count > MaximumBoundaryEdges)
                return Stop("INVALID_TARGET_COUNT", "No target edges or target boundary exceeds the bounded limit.");
            if (cancellationRequested?.Invoke() == true)
                return Stop("VERIFICATION_CANCELLED", "Cancelled before boundary verification.");

            var candidateEdges = candidate.Edges.Where(edge => edge.Valence == EdgeAdjacency.Naked).ToArray();
            result.BoundaryEdgeCount = candidateEdges.Length;
            if (candidateEdges.Length > MaximumBoundaryEdges)
                return Stop("BOUNDARY_COMPLEXITY_LIMIT", "More than 128 naked boundary edges.");
            var topology = BoundaryCycleTopology.Analyze(candidateEdges.Select(edge =>
                (edge.StartVertex?.VertexIndex ?? -1, edge.EndVertex?.VertexIndex ?? -1)).ToArray());
            result.BoundaryComponents = topology.Components;
            if (!topology.IsSingleCycle)
                return Stop(topology.Reason, "Naked boundary must be one topological cycle; edges="
                    + candidateEdges.Length + ", components=" + topology.Components + ", ends="
                    + topology.Ends + ", junctions=" + topology.Junctions + ".");
            if (!FacesConnected(candidate))
                return Stop("DISCONNECTED_OR_NONMANIFOLD_CAP", "All cap faces must belong to one manifold component.");
            foreach (var edge in candidateEdges.Concat(targetEdges))
            {
                var length = edge.GetLength();
                if (!IsFinite(length) || length <= 0 || edge.Valence != EdgeAdjacency.Naked
                    || AdjacentFace(edge) is null)
                    return Stop("BOUNDARY_OWNERSHIP_INVALID", "An edge is degenerate or has no unique owning trim and face.");
            }
            candidateLoop = JoinLoop(candidateEdges, absoluteTolerance);
            if (candidateLoop is null)
                return Stop("CANDIDATE_LOOP_JOIN_FAILED", "Candidate boundary copies do not form one closed curve.");
            targetLoop = JoinLoop(targetEdges, absoluteTolerance);
            if (targetLoop is null)
                return Stop("TARGET_LOOP_JOIN_FAILED", "Target boundary copies do not form one closed curve.");
            // No proximity prefilter: large measured gaps are preserved and reported.
            var measureTolerance = Math.Max(absoluteTolerance * 0.1, 1e-9);
            if (!MeasureGap(candidateLoop, targetLoop, measureTolerance, out var forward)
                || !MeasureGap(targetLoop, candidateLoop, measureTolerance, out var reverse))
                return Stop("BOUNDARY_MEASUREMENT_FAILED", "Rhino could not measure both boundary directions.");
            result.MaximumGap = Math.Max(forward, reverse);
            if (result.MaximumGap > absoluteTolerance + 1e-12)
                return Stop("BOUNDARY_GAP_OUT_OF_TOLERANCE", "max_gap=" + Number(result.MaximumGap)
                    + "; allowed=" + Number(absoluteTolerance) + "; G1/G2 not evaluated.", true);

            result.MaximumNormalAngleDegrees = settings.Continuity == MatchContinuityLevel.Position ? double.NaN : 0;
            result.MaximumCurvatureDeviationPercent = settings.Continuity == MatchContinuityLevel.Curvature ? 0 : double.NaN;
            var coveredTargets = new HashSet<int>();
            var coveredCandidates = new HashSet<int>();
            // Both directions cover even a short candidate edge between target samples.
            for (var pass = 0; pass < 2; pass++)
            {
                IReadOnlyList<BrepEdge> sources = pass == 0 ? targetEdges : candidateEdges;
                IReadOnlyList<BrepEdge> destinations = pass == 0 ? candidateEdges : targetEdges;
                foreach (var source in sources)
                {
                    var count = (int)Math.Min(64L, Math.Max(12L, 4L * source.SpanCount + 1));
                    for (var sample = 0; sample < count; sample++)
                    {
                        if (cancellationRequested?.Invoke() == true)
                            return Stop("VERIFICATION_CANCELLED", "Cancelled between boundary samples; partial metrics retained.");
                        if (result.SampleCount >= MaximumSamples)
                            return Stop("SAMPLING_LIMIT", "Bounded sample budget exhausted; partial metrics retained.");
                        var fraction = NearEndFraction + (1 - 2 * NearEndFraction) * sample / (count - 1.0);
                        if (!source.NormalizedLengthParameter(fraction, out var sourceParameter))
                            return Stop("SAMPLE_PARAMETERIZATION_FAILED", "Could not parameterize one boundary sample.");
                        var point = source.PointAt(sourceParameter);
                        if (!Locate(point, destinations, absoluteTolerance, out var destination,
                                out var destinationParameter, out var gap, out var reason))
                            return Stop(reason, "Boundary correspondence could not be uniquely resolved; source_edge="
                                + source.EdgeIndex + "; pass=" + pass + ".");
                        result.MaximumGap = Math.Max(result.MaximumGap, gap);
                        if (gap > absoluteTolerance + 1e-12)
                            return Stop("BOUNDARY_GAP_OUT_OF_TOLERANCE", "sampled_gap=" + Number(gap)
                                + "; allowed=" + Number(absoluteTolerance) + ".", true);
                        var targetEdge = pass == 0 ? source : destination;
                        var capEdge = pass == 0 ? destination : source;
                        var targetParameter = pass == 0 ? sourceParameter : destinationParameter;
                        var capParameter = pass == 0 ? destinationParameter : sourceParameter;
                        if (!FaceParameters(targetEdge, targetParameter, out var targetFace, out var tu, out var tv)
                            || !FaceParameters(capEdge, capParameter, out var capFace, out var cu, out var cv))
                            return Stop("SAMPLE_TRIM_MAPPING_FAILED", "Could not map one sample through its owning trim to the face.");
                        if (settings.Continuity != MatchContinuityLevel.Position)
                        {
                            var targetNormal = OrientedNormal(targetFace, tu, tv);
                            var capNormal = OrientedNormal(capFace, cu, cv);
                            if (!targetNormal.Unitize() || !capNormal.Unitize())
                                return Stop("INVALID_NORMAL", "A boundary sample returned an invalid normal.");
                            var signedDot = Vector3d.Multiply(targetNormal, capNormal);
                            if (!IsFinite(signedDot)) return Stop("INVALID_NORMAL", "Normal comparison is non-finite.");
                            result.MaximumNormalAngleDegrees = Math.Max(result.MaximumNormalAngleDegrees,
                                RhinoMath.ToDegrees(Math.Acos(Math.Min(1, Math.Abs(signedDot)))));
                            if (settings.Continuity == MatchContinuityLevel.Curvature)
                            {
                                var targetCurvature = targetFace.CurvatureAt(tu, tv);
                                var capCurvature = capFace.CurvatureAt(cu, cv);
                                var targetTangent = targetEdge.TangentAt(targetParameter);
                                var capTangent = capEdge.TangentAt(capParameter);
                                if (targetCurvature is null || capCurvature is null
                                    || !targetTangent.Unitize() || !capTangent.Unitize())
                                    return Stop("INVALID_CURVATURE_DATA", "Missing curvature or tangent at boundary sample.");
                                var targetAcross = Vector3d.CrossProduct(targetNormal, targetTangent);
                                var capAcross = Vector3d.CrossProduct(capNormal, capTangent);
                                if (!targetAcross.Unitize() || !capAcross.Unitize()
                                    || !NormalCurvature(targetCurvature, targetAcross, targetFace.OrientationIsReversed, out var tk)
                                    || !NormalCurvature(capCurvature, capAcross, capFace.OrientationIsReversed, out var ck))
                                    return Stop("INVALID_CURVATURE_DATA", "Invalid cross-boundary or principal curvature data.");
                                if (signedDot < 0) ck = -ck;
                                result.MaximumCurvatureDeviationPercent = Math.Max(result.MaximumCurvatureDeviationPercent,
                                    RadiusDeviationPercent(tk, ck));
                            }
                        }
                        coveredTargets.Add(targetEdge.EdgeIndex);
                        coveredCandidates.Add(capEdge.EdgeIndex);
                        result.CoveredTargetEdges = coveredTargets.Count;
                        result.CoveredCandidateEdges = coveredCandidates.Count;
                        result.SampleCount++;
                    }
                }
            }
            if (result.CoveredTargetEdges != targetEdges.Count || result.CoveredCandidateEdges != candidateEdges.Length)
                return Stop("INCOMPLETE_BOUNDARY_COVERAGE", "Not every edge was covered by correspondence sampling.");
            if (settings.Continuity != MatchContinuityLevel.Position
                && result.MaximumNormalAngleDegrees > RhinoMath.ToDegrees(angleToleranceRadians) + 1e-6)
                return Stop("NORMAL_OUT_OF_TOLERANCE", "sampled_max_normal_deg=" + Number(result.MaximumNormalAngleDegrees) + ".", true);
            if (settings.Continuity == MatchContinuityLevel.Curvature
                && result.MaximumCurvatureDeviationPercent > settings.CurvatureTolerancePercent + 1e-9)
                return Stop("CURVATURE_OUT_OF_TOLERANCE", "sampled_max_curvature_pct=" + Number(result.MaximumCurvatureDeviationPercent) + ".", true);
            result.Available = result.Verified = true;
            result.Reason = "BOUNDARY_VERIFIED";
            result.Token = settings.ContinuityToken
                + (settings.Continuity == MatchContinuityLevel.Position ? "" : "_SAMPLED") + "_VERIFIED";
            result.Message = "Whole-boundary gap and bidirectional sampled continuity passed; Join proof is still required.";
            return result;
        }
        catch (Exception exception)
        {
            return Stop("VERIFICATION_EXCEPTION", exception.GetType().Name + "; partial metrics retained.");
        }
        finally
        {
            candidateLoop?.Dispose();
            targetLoop?.Dispose();
            if (writeDiagnostics) BoundaryAttemptTrace.WriteVerification(variant, result);
        }
    }

    private static bool FacesConnected(Brep brep)
    {
        var neighbors = Enumerable.Range(0, brep.Faces.Count).Select(_ => new List<int>()).ToArray();
        foreach (var edge in brep.Edges)
        {
            if (edge.Valence == EdgeAdjacency.Naked) continue;
            if (edge.Valence != EdgeAdjacency.Interior || edge.TrimCount != 2) return false;
            var faces = edge.AdjacentFaces();
            if (faces.Length < 1 || faces.Length > 2) return false;
            if (faces.Length == 2)
            {
                neighbors[faces[0]].Add(faces[1]);
                neighbors[faces[1]].Add(faces[0]);
            }
        }
        var seen = new HashSet<int> { 0 };
        var queue = new Stack<int>();
        queue.Push(0);
        while (queue.Count > 0)
            foreach (var next in neighbors[queue.Pop()]) if (seen.Add(next)) queue.Push(next);
        return seen.Count == brep.Faces.Count;
    }

    private static Curve? JoinLoop(IEnumerable<BrepEdge> edges, double tolerance)
    {
        var copies = edges.Select(edge => edge.DuplicateCurve()).ToArray();
        Curve[]? joined = null;
        try
        {
            joined = Curve.JoinCurves(copies, tolerance, false);
            if (joined is null || joined.Length != 1 || !joined[0].IsClosed) return null;
            var result = joined[0];
            joined[0] = null!;
            return result;
        }
        finally
        {
            foreach (var copy in copies) copy?.Dispose();
            if (joined is not null) foreach (var curve in joined) curve?.Dispose();
        }
    }

    private static bool MeasureGap(Curve a, Curve b, double tolerance, out double gap)
    {
        return Curve.GetDistancesBetweenCurves(a, b, tolerance, out gap,
            out _, out _, out _, out _, out _) && IsFinite(gap) && gap >= 0;
    }

    private static bool Locate(Point3d point, IReadOnlyList<BrepEdge> edges, double tolerance,
        out BrepEdge edge, out double parameter, out double gap, out string reason)
    {
        edge = null!;
        parameter = double.NaN;
        gap = double.PositiveInfinity;
        reason = "BOUNDARY_PROJECTION_FAILED";
        var hits = new List<(BrepEdge Edge, double Parameter, double Gap)>();
        foreach (var candidate in edges)
        {
            if (!candidate.ClosestPoint(point, out var t)) return false;
            var distance = candidate.PointAt(t).DistanceTo(point);
            if (!IsFinite(distance)) return false;
            hits.Add((candidate, t, distance));
        }
        if (hits.Count == 0) return false;
        hits.Sort((a, b) => a.Gap.CompareTo(b.Gap));
        var best = hits[0];
        var ambiguity = Math.Max(1e-10, tolerance * 1e-4);
        foreach (var other in hits.Skip(1))
        {
            if (other.Gap - best.Gap > ambiguity) break;
            // A split on the SAME face has one limit at its common vertex.
            // Nonlocal overlap and differing adjacent faces are not silently chosen.
            if (AdjacentFace(best.Edge)?.FaceIndex != AdjacentFace(other.Edge)?.FaceIndex
                || !AtCommonVertex(best.Edge, best.Parameter, other.Edge, other.Parameter, ambiguity))
            {
                reason = "AMBIGUOUS_BOUNDARY_MAPPING";
                return false;
            }
        }
        edge = best.Edge;
        parameter = best.Parameter;
        gap = best.Gap;
        return true;
    }

    private static bool AtCommonVertex(BrepEdge a, double ta, BrepEdge b, double tb, double tolerance)
    {
        var pa = a.PointAt(ta);
        var pb = b.PointAt(tb);
        foreach (var va in new[] { a.StartVertex, a.EndVertex })
            foreach (var vb in new[] { b.StartVertex, b.EndVertex })
                if (va is not null && vb is not null && va.VertexIndex == vb.VertexIndex
                    && pa.DistanceTo(va.Location) <= tolerance && pb.DistanceTo(vb.Location) <= tolerance)
                    return true;
        return false;
    }

    internal static bool IsNaturalBoundary(BrepEdge edge)
    {
        var indices = edge.TrimIndices();
        if (indices.Length != 1 || edge.Brep is null || indices[0] < 0 || indices[0] >= edge.Brep.Trims.Count) return false;
        var trim = edge.Brep.Trims[indices[0]];
        var face = trim.Face;
        if (face is null || trim.TrimType != BrepTrimType.Boundary) return false;
        var start = trim.PointAtStart;
        var end = trim.PointAtEnd;
        var u = face.Domain(0);
        var v = face.Domain(1);
        return trim.IsoStatus switch
        {
            IsoStatus.West => IsAt(start.X, u.T0, u) && IsAt(end.X, u.T0, u) && Covers(start.Y, end.Y, v),
            IsoStatus.East => IsAt(start.X, u.T1, u) && IsAt(end.X, u.T1, u) && Covers(start.Y, end.Y, v),
            IsoStatus.South => IsAt(start.Y, v.T0, v) && IsAt(end.Y, v.T0, v) && Covers(start.X, end.X, u),
            IsoStatus.North => IsAt(start.Y, v.T1, v) && IsAt(end.Y, v.T1, v) && Covers(start.X, end.X, u),
            _ => false,
        };
    }

    internal static bool IsAverageTargetEligible(BrepEdge edge) => IsNaturalBoundary(edge) && AdjacentFace(edge)?.IsSurface == true;
    private static bool IsAt(double value, double expected, Interval domain) => Math.Abs(value - expected) <= Math.Max(Math.Abs(domain.Length) * 1e-8, 1e-10);
    private static bool Covers(double a, double b, Interval domain) => IsAt(Math.Min(a, b), domain.T0, domain) && IsAt(Math.Max(a, b), domain.T1, domain);
    private static BrepFace? AdjacentFace(BrepEdge edge)
    {
        var indices = edge.TrimIndices();
        return indices.Length == 1 && edge.Brep is not null && indices[0] >= 0 && indices[0] < edge.Brep.Trims.Count
            ? edge.Brep.Trims[indices[0]].Face : null;
    }

    private static bool FaceParameters(BrepEdge edge, double parameter, out BrepFace face, out double u, out double v)
    {
        face = null!;
        u = v = double.NaN;
        var indices = edge.TrimIndices();
        if (indices.Length != 1 || edge.Brep is null || indices[0] < 0 || indices[0] >= edge.Brep.Trims.Count) return false;
        var trim = edge.Brep.Trims[indices[0]];
        if (trim.Face is null || !trim.GetTrimParameter(parameter, out var trimParameter)) return false;
        var uv = trim.PointAt(trimParameter);
        if (!uv.IsValid || !IsFinite(uv.X) || !IsFinite(uv.Y)) return false;
        face = trim.Face;
        u = uv.X;
        v = uv.Y;
        return true;
    }

    private static Vector3d OrientedNormal(BrepFace face, double u, double v)
    {
        var normal = face.NormalAt(u, v);
        if (face.OrientationIsReversed) normal.Reverse();
        return normal;
    }

    private static bool NormalCurvature(SurfaceCurvature curvature, Vector3d direction, bool reversed, out double value)
    {
        value = double.NaN;
        var d0 = curvature.Direction(0);
        var d1 = curvature.Direction(1);
        if (!d0.Unitize() || !d1.Unitize()) return false;
        var k0 = curvature.Kappa(0);
        var k1 = curvature.Kappa(1);
        if (!IsFinite(k0) || !IsFinite(k1)) return false;
        var c0 = Vector3d.Multiply(direction, d0);
        var c1 = Vector3d.Multiply(direction, d1);
        value = (k0 * c0 * c0 + k1 * c1 * c1) * (reversed ? -1 : 1);
        return IsFinite(value);
    }

    private static double RadiusDeviationPercent(double a, double b)
    {
        var flatA = Math.Abs(a) <= 1e-12;
        var flatB = Math.Abs(b) <= 1e-12;
        if (flatA && flatB) return 0;
        if (flatA || flatB) return double.PositiveInfinity;
        var ra = 1 / a;
        var rb = 1 / b;
        return Math.Abs(ra - rb) / Math.Max(Math.Abs(ra), Math.Abs(rb)) * 100;
    }

    internal static bool IsFinite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    internal static string Number(double value) => double.IsNaN(value) ? "n/a"
        : double.IsPositiveInfinity(value) ? "+inf" : double.IsNegativeInfinity(value) ? "-inf"
        : value.ToString("G9", CultureInfo.InvariantCulture);
}

internal static class BoundaryAttemptTrace
{
    public static void WriteVerification(string variant, BoundaryMatchMetrics metrics)
    {
        SafeWrite("SMARTSKIN_P07F1_BOUNDARY | " + variant + " | " + Format(metrics));
    }

    public static void Write(string variant, string phase, bool success, string code, string message,
        Brep? candidate, BoundaryMatchMetrics? metrics, int joinedSeams, long elapsedMilliseconds)
    {
        // Tracing must not throw through the builder's disposal path.
        try
        {
            SafeWrite("SMARTSKIN_P07F1_ATTEMPT_END | " + variant + " | phase=" + phase
                + " | result=" + (success ? "READY" : "BLOCKED")
                + " | code=" + (success ? CandidateBuildCodes.MatchBuilt : code)
                + " | faces=" + (candidate?.Faces.Count ?? 0)
                + " | edges=" + (candidate?.Edges.Count ?? 0)
                + " | " + (metrics is null ? "reason=NOT_EVALUATED" : Format(metrics))
                + " | proved_target_edges=" + joinedSeams + " | elapsed_ms=" + elapsedMilliseconds
                + " | " + (success ? "Match and Join proof passed." : message));
        }
        catch { /* Never prevent geometry cleanup because a diagnostic failed. */ }
    }

    private static string Format(BoundaryMatchMetrics m) => "reason=" + m.Reason + " | verified=" + m.Token
        + " | boundary_edges=" + m.BoundaryEdgeCount + " | boundary_components=" + m.BoundaryComponents
        + " | max_gap=" + BoundaryMatchVerifier.Number(m.MaximumGap)
        + " | sampled_max_normal_deg=" + BoundaryMatchVerifier.Number(m.MaximumNormalAngleDegrees)
        + " | sampled_max_curvature_pct=" + BoundaryMatchVerifier.Number(m.MaximumCurvatureDeviationPercent)
        + " | samples=" + m.SampleCount + " | covered_target_edges=" + m.CoveredTargetEdges
        + " | covered_candidate_edges=" + m.CoveredCandidateEdges;

    private static void SafeWrite(string line)
    {
        try { RhinoApp.WriteLine(line.Replace('\r', ' ').Replace('\n', ' ')); }
        catch { /* The verifier does not depend on command-history availability. */ }
    }
}
