using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using Rhino;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal static class NativeCompareMeasure
{
    internal sealed class SurfaceFrame
    {
        internal Vector3d Normal;
        internal double[] Operator = Array.Empty<double>();
        internal double Norm;
    }
    internal static BrepFace? Face(BrepEdge edge)
    {
        var trims = edge.TrimIndices();
        return trims.Length == 1 && edge.Brep is not null ? edge.Brep.Trims[trims[0]].Face : null;
    }
    internal static bool NaturalTrimLocus(BrepTrim trim)
    {
        var face = trim.Face;
        if (face is null || trim.TrimType != BrepTrimType.Boundary) return false;
        var iso = trim.IsoStatus;
        var direction = iso == IsoStatus.West || iso == IsoStatus.East ? 0
            : iso == IsoStatus.South || iso == IsoStatus.North ? 1 : -1;
        if (direction < 0) return false;
        var domain = face.Domain(direction);
        var value = iso == IsoStatus.West || iso == IsoStatus.South ? domain.T0 : domain.T1;
        var side = iso == IsoStatus.South ? 0 : iso == IsoStatus.East ? 1 : iso == IsoStatus.North ? 2 : 3;
        if (face.IsSingular(side)) return false;
        using var curve = trim.ToNurbsCurve();
        if (curve is null || curve.Points.Count > 512) return false;
        for (var i = 0; i < curve.Points.Count; i++)
        {
            var control = curve.Points[i];
            if (control.Weight <= 0 || !NativeCompareMath.Finite(control.Weight)) return false;
            var coordinate = direction == 0 ? control.Location.X : control.Location.Y;
            if (Math.Abs(coordinate - value) > Math.Max(1e-10, Math.Abs(domain.Length) * 1e-8)) return false;
        }
        return true;
    }

    internal static bool Frame(BrepEdge edge, double parameter, double tolerance, out SurfaceFrame frame)
    {
        frame = new SurfaceFrame();
        var trims = edge.TrimIndices();
        if (trims.Length != 1 || edge.Brep is null) return false;
        var trim = edge.Brep.Trims[trims[0]];
        var face = trim.Face;
        if (face is null || !trim.GetTrimParameter(parameter, out var t)) return false;
        var uv = trim.PointAt(t);
        if (!uv.IsValid || face.PointAt(uv.X, uv.Y).DistanceTo(edge.PointAt(parameter)) > tolerance) return false;
        var normal = face.NormalAt(uv.X, uv.Y);
        if (face.OrientationIsReversed) normal.Reverse();
        if (!normal.Unitize()) return false;
        var curvature = face.CurvatureAt(uv.X, uv.Y);
        if (curvature is null) return false;
        var d0 = curvature.Direction(0); var d1 = curvature.Direction(1);
        var k0 = curvature.Kappa(0); var k1 = curvature.Kappa(1);
        if (!d0.Unitize() || !d1.Unitize() || !NativeCompareMath.Finite(k0) || !NativeCompareMath.Finite(k1)
            || Math.Abs(d0 * d1) > 1e-5 || Math.Abs(d0 * normal) > 1e-5 || Math.Abs(d1 * normal) > 1e-5) return false;
        frame.Normal = normal;
        frame.Operator = NativeCompareMath.Operator(k0, new[] { d0.X, d0.Y, d0.Z }, k1,
            new[] { d1.X, d1.Y, d1.Z }, face.OrientationIsReversed ? -1 : 1);
        frame.Norm = Math.Sqrt(k0 * k0 + k1 * k1);
        return frame.Operator.All(NativeCompareMath.Finite);
    }

    internal static bool Bounded(Brep candidate, out int controlPoints)
    {
        controlPoints = 0;
        if (!candidate.IsValid || candidate.Faces.Count != 1 || candidate.Edges.Count > 32) return false;
        foreach (var face in candidate.Faces)
        {
            using var nurbs = face.ToNurbsSurface();
            if (nurbs is null || nurbs.Degree(0) > 11 || nurbs.Degree(1) > 11) return false;
            controlPoints += nurbs.Points.CountU * nurbs.Points.CountV;
        }
        return controlPoints <= 4096;
    }

    internal static void ReportSides(string recipe, string phase, Brep candidate, NativeCompareInput input,
        NativeCompareSideBinding binding, Action checkpoint)
    {
        var watch = Stopwatch.StartNew();
        var bounded = Bounded(candidate, out var cp);
        RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_BOUNDARY | recipe=" + recipe + " | phase=" + phase
            + " | valid=" + candidate.IsValid + " | bounded=" + bounded + " | faces=" + candidate.Faces.Count
            + " | control_points=" + cp + " | attribution=CONDITIONAL_NATURAL_PARAMETER_SIDE"
            + " | physical_correspondence=NOT_VERIFIED | occupied_side=NOT_VERIFIED | parent_separation=NOT_VERIFIED");
        binding.TraceCandidate(recipe, phase, candidate, input);
        for (var side = 0; side < 4; side++)
        {
            var edge = bounded ? binding.Resolve(candidate, side) : null;
            if (edge is null)
            {
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_SIDE_RESULT | recipe=" + recipe + " | phase=" + phase
                    + " | side=" + side + " | relation=" + NativeCompareProbeProtocol.Relation(side)
                    + " | both_directions=NOT_VERIFIED_UNRESOLVED_NATURAL_SIDE | global_G2=NOT_VERIFIED");
                continue;
            }
            for (var pass = 0; pass < 2; pass++)
            {
                var metrics = new NativeCompareStationMetrics();
                var targets = input.Sides[side].Select(part => part.Native).ToArray();
                var sources = pass == 0 ? targets : new[] { edge };
                var destinations = pass == 0 ? new[] { edge } : targets;
                var sourceEdgesTouched = new HashSet<BrepEdge>();
                var sourceEdgesWithG0 = new HashSet<BrepEdge>();
                var candidateEdgesTouched = new HashSet<BrepEdge>();
                foreach (var source in sources)
                {
                    var stations = new List<(double Parameter, bool Endpoint)>();
                    foreach (var fraction in Fractions())
                    {
                        var endpoint = fraction == 0 || fraction == 1;
                        if (source.NormalizedLengthParameter(fraction, out var parameter)) stations.Add((parameter, endpoint));
                        else metrics.UnresolvedStation(endpoint);
                    }
                    var capturedSource = input.Edges.FirstOrDefault(part => ReferenceEquals(part.Native, source));
                    if (capturedSource is not null)
                        foreach (var feature in capturedSource.Features)
                        {
                            var offset = Math.Abs(source.Domain.Length) * 1e-8;
                            stations.Add((Math.Max(source.Domain.T0, feature - offset), false));
                            stations.Add((feature, false));
                            stations.Add((Math.Min(source.Domain.T1, feature + offset), false));
                        }
                    foreach (var station in stations)
                    {
                        checkpoint();
                        var point = source.PointAt(station.Parameter);
                        if (!Locate(point, destinations, input.Tolerance, out var target, out var targetParameter, out var distance))
                        { metrics.UnresolvedStation(station.Endpoint); continue; }
                        metrics.LocatedStation(station.Endpoint, distance, input.Tolerance);
                        var sourceEdge = pass == 0 ? source : target;
                        sourceEdgesTouched.Add(sourceEdge);
                        candidateEdgesTouched.Add(pass == 0 ? target : source);
                        if (distance <= input.Tolerance) sourceEdgesWithG0.Add(sourceEdge);
                        // Projected frames are measured even when separated, and explicitly distinguished
                        // from frames whose point pair also meets G0. Neither is a continuity certificate.
                        if (!Frame(source, station.Parameter, input.Tolerance, out var a)
                            || !Frame(target, targetParameter, input.Tolerance, out var b))
                        { metrics.FrameFailures++; continue; }
                        var dot = Math.Max(-1, Math.Min(1, a.Normal * b.Normal));
                        metrics.PairedFrame(dot, RhinoMath.ToDegrees(Math.Acos(Math.Abs(dot))),
                            NativeCompareMath.OperatorSpectralResidual(a.Operator, b.Operator, dot < 0 ? -1 : 1),
                            NativeCompareMath.OperatorResidual(a.Operator, b.Operator, dot < 0 ? -1 : 1), distance <= input.Tolerance);
                    }
                }
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_SIDE_RESULT | recipe=" + recipe + " | phase=" + phase
                    + " | side=" + side + " | relation=" + NativeCompareProbeProtocol.Relation(side)
                    + " | direction=" + (pass == 0 ? "SOURCE_TO_CANDIDATE" : "CANDIDATE_TO_SOURCE")
                    + " | source_edges_touched=" + sourceEdgesTouched.Count + "/" + targets.Length
                    + " | source_edges_with_any_G0_station=" + sourceEdgesWithG0.Count + "/" + targets.Length
                    + " | candidate_edges_touched=" + candidateEdgesTouched.Count + "/1"
                    + " | touched_does_not_mean_complete_coverage=true | " + metrics.Format()
                    + " | finite_bands=NONE_EXCLUDED | corners=NOT_VERIFIED");
            }
        }
        RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_MEASURE_END | recipe=" + recipe + " | phase=" + phase
            + " | measurement_ms=" + watch.ElapsedMilliseconds);
    }

    private static IEnumerable<double> Fractions()
    {
        yield return 0;
        yield return 1e-7;
        yield return 1e-5;
        for (var i = 1; i < 32; i++) yield return i / 32.0;
        yield return 1 - 1e-5;
        yield return 1 - 1e-7;
        yield return 1;
    }

    private static bool Locate(Point3d point, IReadOnlyList<BrepEdge> edges, double tolerance,
        out BrepEdge edge, out double parameter, out double distance)
    {
        edge = null!; parameter = double.NaN; distance = double.PositiveInfinity;
        var tied = false;
        foreach (var next in edges)
        {
            if (!next.ClosestPoint(point, out var t)) return false;
            var d = next.PointAt(t).DistanceTo(point);
            if (!NativeCompareMath.Finite(d)) return false;
            if (d < distance - tolerance * 1e-4) { edge = next; parameter = t; distance = d; tied = false; }
            else if (Math.Abs(d - distance) <= tolerance * 1e-4)
            {
                // A tie at a genuine corner or overlapping source branches is unresolved, never guessed.
                tied = true;
            }
        }
        return edge is not null && !tied;
    }
    internal static string Number(double value) => value.ToString("G9", CultureInfo.InvariantCulture);
}
