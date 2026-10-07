using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeSupportSource
{
    internal sealed class Station
    {
        internal NativeCompareInput.Edge Source = null!;
        internal int Side;
        internal double Parameter;
        internal Point3d Point;
        internal string Kind = string.Empty;
        internal bool UpperPoint;
    }
    internal readonly List<Station> Stations = new();
    internal NativeSupportTrimPolicy? Policy;
    internal double PositionTolerance, AngleToleranceRadians, FullHullScale;
    internal NativeSupportContractScale? Compatibility;
    internal string ContractStatus = "NOT_VERIFIED";
    internal int UpperSide;
    internal const int MaximumStations = 8192;

    internal static NativeSupportSource Create(NativeCompareInput input, Action checkpoint)
    {
        var result = new NativeSupportSource { PositionTolerance = input.Tolerance, AngleToleranceRadians = input.AngleTolerance };
        var planar = new List<(int Side, Plane Plane)>();
        for (var side = 0; side < 4; side++)
        {
            var first = NativeCompareMeasure.Face(input.Sides[side][0].Native);
            if (first is null || !first.TryGetPlane(out var plane, input.Tolerance)) continue;
            if (input.Sides[side].All(edge =>
            {
                var face = NativeCompareMeasure.Face(edge.Native);
                return face is not null && face.TryGetPlane(out var other, input.Tolerance)
                    && Math.Abs(plane.DistanceTo(other.Origin)) <= input.Tolerance
                    && Math.Abs(plane.Normal * other.Normal) >= Math.Cos(1e-5);
            })) planar.Add((side, plane));
        }
        if (input.Derivation != "NATURAL_SIDE_PAIR_COPLANAR_PARENT_CHAIN_STRAIGHT_CHAIN" || planar.Count != 1)
            throw new NativeCompareUnsupported("UNSUPPORTED_COMPLETE_SOURCE_FRAME_OR_UPPER_ROLE");
        result.UpperSide = planar[0].Side;
        var upper = input.Sides[result.UpperSide];
        var previous = input.Sides[(result.UpperSide + 3) % 4];
        var next = input.Sides[(result.UpperSide + 1) % 4];
        if (!WholeNaturalBranch(previous, input.Tolerance) || !WholeNaturalBranch(next, input.Tolerance))
            throw new NativeCompareUnsupported("UNSUPPORTED_EXACT_UPPER_POINT_ROLE_BINDING");
        var upperIncidences = new[]
        {
            (upper[0], upper[0].Parameter(false)), (previous[previous.Count - 1], previous[previous.Count - 1].Parameter(true)),
            (upper[upper.Count - 1], upper[upper.Count - 1].Parameter(true)), (next[0], next[0].Parameter(false)),
        };
        var origin = upper[0].Start;
        var normal = planar[0].Plane.Normal;
        var width = upper[upper.Count - 1].End - origin;
        if (!normal.Unitize() || !width.Unitize() || Math.Abs(normal * width) > 1e-7)
            throw new NativeCompareUnsupported("UNSUPPORTED_ORTHONORMAL_SOURCE_FRAME");
        var depth = Vector3d.CrossProduct(normal, width);
        if (!depth.Unitize()) throw new NativeCompareUnsupported("UNSUPPORTED_ORTHONORMAL_SOURCE_FRAME");
        width = Vector3d.CrossProduct(depth, normal); width.Unitize();
        var bounds = BoundingBox.Empty;
        foreach (var edge in input.Edges)
        {
            checkpoint();
            using var curve = edge.Native.ToNurbsCurve();
            if (curve is null || curve.Points.Count > 512) throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_SCALE_CURVE");
            foreach (var control in curve.Points)
            {
                if (!NativeCompareMath.Finite(control.Weight) || control.Weight <= 0)
                    throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_SCALE_RATIONAL_HULL");
                var delta = control.Location - origin;
                bounds.Union(new Point3d(delta * normal, delta * width, delta * depth));
            }
        }
        var scale = bounds.Diagonal.Length;
        if (!NativeCompareMath.Finite(scale) || scale <= 0) throw new NativeCompareUnsupported("UNSUPPORTED_FULL_SOURCE_HULL_SCALE");
        result.FullHullScale = scale;
        try
        {
            result.Compatibility = NativeSupportContractScale.Create(input, result.UpperSide, normal, width, depth, checkpoint);
            result.Policy = new NativeSupportTrimPolicy(input.Tolerance, input.AngleTolerance, result.Compatibility.Scale);
            result.ContractStatus = NativeSupportContractScale.Provenance;
        }
        catch (NativeCompareUnsupported exception) { result.ContractStatus = exception.Message; }

        for (var side = 0; side < 4; side++)
            foreach (var edge in input.Sides[side])
            {
                var parameters = new SortedDictionary<double, string>();
                void Add(double parameter, string kind)
                {
                    if (!NativeCompareMath.Finite(parameter) || parameter < edge.Native.Domain.T0 || parameter > edge.Native.Domain.T1)
                        throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_STATION_PARAMETER");
                    if (!parameters.ContainsKey(parameter)) parameters.Add(parameter, kind);
                }
                Add(edge.Native.Domain.T0, "original_endpoint"); Add(edge.Native.Domain.T1, "original_endpoint");
                foreach (var fraction in new[] { 1e-7, 1e-5, 1 - 1e-5, 1 - 1e-7 })
                {
                    if (!edge.Native.NormalizedLengthParameter(fraction, out var parameter))
                        throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_ARC_APPROACH");
                    Add(parameter, "endpoint_approach");
                }
                if (edge.Native.SpanCount > 512) throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_SPAN_BUDGET");
                for (var span = 0; span < edge.Native.SpanCount; span++)
                {
                    var domain = edge.Native.SpanDomain(span);
                    var a = Math.Max(domain.T0, edge.Native.Domain.T0); var b = Math.Min(domain.T1, edge.Native.Domain.T1);
                    if (b <= a) continue;
                    foreach (var fraction in new[] { 0.0, 1e-7, 1e-5, .25, .5, .75, 1 - 1e-5, 1 - 1e-7, 1.0 })
                        Add(a + (b - a) * fraction, fraction == 0 || fraction == 1 ? "span_limit" : "span_interior");
                }
                foreach (var feature in edge.Features)
                {
                    parameters[feature] = "true_feature";
                    var offset = Math.Abs(edge.Native.Domain.Length) * 1e-8;
                    Add(Math.Max(edge.Native.Domain.T0, feature - offset), "feature_approach");
                    Add(Math.Min(edge.Native.Domain.T1, feature + offset), "feature_approach");
                }
                var ordered = edge.Reverse ? parameters.Reverse() : parameters;
                foreach (var pair in ordered)
                {
                    result.Stations.Add(new Station { Source = edge, Side = side, Parameter = pair.Key,
                        Point = edge.Native.PointAt(pair.Key), Kind = pair.Value,
                        UpperPoint = upperIncidences.Any(bound => ReferenceEquals(bound.Item1, edge) && bound.Item2 == pair.Key) });
                    if (result.Stations.Count > MaximumStations) throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_STATION_BUDGET");
                }
            }
        return result;
    }
    private static bool WholeNaturalBranch(IReadOnlyList<NativeCompareInput.Edge> branch, double tolerance)
    {
        if (branch.Count == 0) return false;
        var first = branch[0]; var face = NativeCompareMeasure.Face(first.Native);
        if (face is null) return false;
        var iso = NativeCompareSideBinding.Trim(first.Native).IsoStatus;
        if (branch.Any(edge => edge.OwnerIndex != first.OwnerIndex || NativeCompareMeasure.Face(edge.Native)?.FaceIndex != face.FaceIndex
            || NativeCompareSideBinding.Trim(edge.Native).IsoStatus != iso
            || !NativeCompareMeasure.NaturalTrimLocus(NativeCompareSideBinding.Trim(edge.Native)))) return false;
        var u = face.Domain(0); var v = face.Domain(1);
        var a = iso == IsoStatus.West ? face.PointAt(u.T0, v.T0) : iso == IsoStatus.East ? face.PointAt(u.T1, v.T0)
            : iso == IsoStatus.South ? face.PointAt(u.T0, v.T0) : face.PointAt(u.T0, v.T1);
        var b = iso == IsoStatus.West ? face.PointAt(u.T0, v.T1) : iso == IsoStatus.East ? face.PointAt(u.T1, v.T1)
            : iso == IsoStatus.South ? face.PointAt(u.T1, v.T0) : face.PointAt(u.T1, v.T1);
        var start = first.Start; var end = branch[branch.Count - 1].End;
        return (start.DistanceTo(a) <= tolerance && end.DistanceTo(b) <= tolerance)
            || (start.DistanceTo(b) <= tolerance && end.DistanceTo(a) <= tolerance);
    }

}
