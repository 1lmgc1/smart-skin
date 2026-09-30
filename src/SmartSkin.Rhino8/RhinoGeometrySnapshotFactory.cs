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
        var parentType = reference.Object()?.ObjectType.ToString() ?? "Unknown";
        var componentIndex = reference.GeometryComponentIndex;
        var scope = componentIndex.ComponentIndexType == ComponentIndexType.InvalidType
            ? $"object:{parentType}"
            : $"subobject:{componentIndex.ComponentIndexType}[{componentIndex.Index}]@{parentType}";
        return $"selection[{selectionIndex}]/{shortId}/{scope}";
    }

    public static GeometrySnapshot Create(ObjRef reference, int selectionIndex, double absoluteTolerance)
    {
        if (reference is null)
        {
            throw new ArgumentNullException(nameof(reference));
        }

        var label = CreateLabel(reference, selectionIndex);
        var componentIndex = reference.GeometryComponentIndex;
        if (componentIndex.ComponentIndexType != ComponentIndexType.InvalidType)
        {
            return FromSubObject(reference, label, absoluteTolerance);
        }

        var geometry = reference.Object()?.Geometry ?? reference.Geometry();
        return FromTopLevelGeometry(label, geometry, absoluteTolerance);
    }

    private static GeometrySnapshot FromSubObject(
        ObjRef reference,
        string label,
        double absoluteTolerance)
    {
        var edge = reference.Edge();
        if (edge is not null)
        {
            return FromCurve(label, GeometryKind.BrepEdge, edge, absoluteTolerance);
        }

        var face = reference.Face();
        if (face is not null)
        {
            return FromSurface(label, face, absoluteTolerance);
        }

        var geometry = reference.Geometry();
        return geometry switch
        {
            Curve curve => FromCurve(label, GeometryKind.Curve, curve, absoluteTolerance),
            Rhino.Geometry.Point point => FromPoint(label, point),
            Brep brep => FromBrep(label, brep, absoluteTolerance),
            Surface surface => FromSurface(label, surface, absoluteTolerance),
            _ => FromOther(label, geometry)
        };
    }

    private static GeometrySnapshot FromTopLevelGeometry(
        string label,
        GeometryBase? geometry,
        double absoluteTolerance)
    {
        return geometry switch
        {
            Extrusion extrusion => FromExtrusion(label, extrusion, absoluteTolerance),
            Curve curve => FromCurve(label, GeometryKind.Curve, curve, absoluteTolerance),
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
        double absoluteTolerance,
        GeometryKind kind = GeometryKind.Brep)
    {
        var faceCount = brep.Faces.Count;
        var edgeCount = brep.Edges.Count;
        if (faceCount > MaximumDeepBrepFaces || edgeCount > MaximumDeepBrepEdges)
        {
            return new GeometrySnapshot(
                label,
                kind,
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
            kind,
            brep.IsValid,
            ToBounds(brep, accurate: true),
            faceCount: faceCount,
            edgeCount: edgeCount,
            nakedEdgeCount: nakedEdgeCount,
            shortEdgeCount: shortEdgeCount);
    }

    private static GeometrySnapshot FromExtrusion(
        string label,
        Extrusion extrusion,
        double absoluteTolerance)
    {
        var brep = extrusion.ToBrep();
        if (brep is not null)
        {
            return FromBrep(
                label,
                brep,
                absoluteTolerance,
                GeometryKind.Extrusion);
        }

        return new GeometrySnapshot(
            label,
            GeometryKind.Extrusion,
            extrusion.IsValid,
            ToBounds(extrusion, accurate: false),
            sourceProblem: "Rhino could not expose this extrusion as a Brep for bounded preflight checks.");
    }

    private static GeometrySnapshot FromOther(string label, GeometryBase? geometry)
    {
        if (geometry is null)
        {
            return GeometrySnapshot.Failed(
                label,
                "Rhino returned no geometry for the selected object reference.");
        }

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
