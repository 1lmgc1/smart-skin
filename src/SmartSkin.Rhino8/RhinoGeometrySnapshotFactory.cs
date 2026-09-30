using System;
using Rhino.DocObjects;
using Rhino.Geometry;
using SmartSkin.Core.Preflight;

namespace SmartSkin.Rhino8;

internal static class RhinoGeometrySnapshotFactory
{
    private const int MaximumDeepCurveSpans = 1000;
    private const int MaximumDeepSurfaceSpans = 1000;
    private const int MaximumDeepBrepFaces = 2000;
    private const int MaximumDeepBrepEdges = 5000;

    public static string CreateLabel(ObjRef reference, int selectionIndex)
    {
        if (reference is null)
        {
            throw new ArgumentNullException(nameof(reference));
        }

        var objectId = reference.ObjectId.ToString("N");
        var shortId = objectId.Length > 8 ? objectId.Substring(0, 8) : objectId;
        return $"selection[{selectionIndex}]/{shortId}";
    }

    public static GeometrySnapshot Create(ObjRef reference, int selectionIndex, double absoluteTolerance)
    {
        if (reference is null)
        {
            throw new ArgumentNullException(nameof(reference));
        }

        var label = CreateLabel(reference, selectionIndex);
        var selectedCurve = reference.Curve();
        if (selectedCurve is not null)
        {
            var kind = selectedCurve is BrepEdge ? GeometryKind.BrepEdge : GeometryKind.Curve;
            return FromCurve(label, kind, selectedCurve, absoluteTolerance);
        }

        var geometry = reference.Geometry();
        return geometry switch
        {
            Rhino.Geometry.Point point => FromPoint(label, point),
            Brep brep => FromBrep(label, brep, absoluteTolerance),
            Surface surface => FromSurface(label, surface, absoluteTolerance),
            _ => FromOther(label, geometry)
        };
    }

    private static GeometrySnapshot FromCurve(
        string label,
        GeometryKind kind,
        Curve curve,
        double absoluteTolerance)
    {
        var spanCount = curve.SpanCount;
        if (spanCount > MaximumDeepCurveSpans)
        {
            return new GeometrySnapshot(
                label,
                kind,
                null,
                ToBounds(curve, accurate: false),
                isClosed: curve.IsClosed,
                startPoint: ToPoint(curve.PointAtStart),
                endPoint: ToPoint(curve.PointAtEnd),
                degree: curve.Degree,
                spanCount: spanCount,
                analysisLimitReason: $"Deep curve checks were skipped because span count {spanCount} exceeds the safety limit {MaximumDeepCurveSpans}.");
        }

        return new GeometrySnapshot(
            label,
            kind,
            curve.IsValid,
            ToBounds(curve, accurate: true),
            length: curve.GetLength(),
            isClosed: curve.IsClosed,
            startPoint: ToPoint(curve.PointAtStart),
            endPoint: ToPoint(curve.PointAtEnd),
            isPlanar: curve.IsPlanar(absoluteTolerance),
            degree: curve.Degree,
            spanCount: spanCount);
    }

    private static GeometrySnapshot FromPoint(string label, Rhino.Geometry.Point point)
    {
        var location = ToPoint(point.Location);
        return new GeometrySnapshot(
            label,
            GeometryKind.Point,
            point.IsValid,
            new Bounds3Value(location, location));
    }

    private static GeometrySnapshot FromSurface(
        string label,
        Surface surface,
        double absoluteTolerance)
    {
        var spanCountU = surface.SpanCount(0);
        var spanCountV = surface.SpanCount(1);
        var spanCount = spanCountU > int.MaxValue - spanCountV
            ? int.MaxValue
            : spanCountU + spanCountV;
        var degree = Math.Max(surface.Degree(0), surface.Degree(1));

        if (spanCount > MaximumDeepSurfaceSpans)
        {
            return new GeometrySnapshot(
                label,
                GeometryKind.Surface,
                null,
                ToBounds(surface, accurate: false),
                degree: degree,
                spanCount: spanCount,
                analysisLimitReason: $"Deep surface checks were skipped because combined span count {spanCount} exceeds the safety limit {MaximumDeepSurfaceSpans}.");
        }

        return new GeometrySnapshot(
            label,
            GeometryKind.Surface,
            surface.IsValid,
            ToBounds(surface, accurate: true),
            isPlanar: surface.IsPlanar(absoluteTolerance),
            degree: degree,
            spanCount: spanCount);
    }

    private static GeometrySnapshot FromBrep(
        string label,
        Brep brep,
        double absoluteTolerance)
    {
        var faceCount = brep.Faces.Count;
        var edgeCount = brep.Edges.Count;
        if (faceCount > MaximumDeepBrepFaces || edgeCount > MaximumDeepBrepEdges)
        {
            return new GeometrySnapshot(
                label,
                GeometryKind.Brep,
                null,
                ToBounds(brep, accurate: false),
                faceCount: faceCount,
                edgeCount: edgeCount,
                analysisLimitReason: $"Deep Brep checks were skipped because faces/edges {faceCount}/{edgeCount} exceed safety limits {MaximumDeepBrepFaces}/{MaximumDeepBrepEdges}.");
        }

        var nakedEdgeCount = 0;
        var shortEdgeCount = 0;

        foreach (var edge in brep.Edges)
        {
            if (edge.Valence == EdgeAdjacency.Naked)
            {
                nakedEdgeCount++;
            }

            var length = edge.GetLength();
            if (length <= absoluteTolerance)
            {
                shortEdgeCount++;
            }
        }

        return new GeometrySnapshot(
            label,
            GeometryKind.Brep,
            brep.IsValid,
            ToBounds(brep, accurate: true),
            faceCount: faceCount,
            edgeCount: edgeCount,
            nakedEdgeCount: nakedEdgeCount,
            shortEdgeCount: shortEdgeCount);
    }

    private static GeometrySnapshot FromOther(string label, GeometryBase geometry)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Other,
            geometry.IsValid,
            ToBounds(geometry, accurate: false));
    }

    private static Bounds3Value ToBounds(GeometryBase geometry, bool accurate)
    {
        var bounds = geometry.GetBoundingBox(accurate);
        return bounds.IsValid
            ? new Bounds3Value(ToPoint(bounds.Min), ToPoint(bounds.Max))
            : default;
    }

    private static Point3Value ToPoint(Point3d point)
    {
        return new Point3Value(point.X, point.Y, point.Z);
    }
}
