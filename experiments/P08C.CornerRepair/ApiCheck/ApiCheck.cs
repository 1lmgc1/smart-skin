using System;
using System.Collections.Generic;
using Rhino;
using Rhino.Geometry;
using Rhino.Geometry.Intersect;
using Rhino.DocObjects;
using Rhino.Input.Custom;

// Compile-time API contract only. This library is never executed as a Rhino test.
public static class NativeApiContract
{
    public static void Check(RhinoDoc doc, Brep cap, Brep parent, BrepEdge edge, Curve curve)
    {
        var settings = new ObjectEnumeratorSettings { ActiveObjects = true, DeletedObjects = false,
            NormalObjects = true, LockedObjects = true, HiddenObjects = true, ReferenceObjects = true,
            IdefObjects = false };
        foreach (var obj in doc.Objects.GetObjectList(settings))
        {
            _ = doc.Objects.FindId(obj.Id);
            _ = obj.Attributes.GetUserString("SmartSkin.P08C4.Contract");
        }
        using var selection = new GetObject();
        selection.GeometryFilter = ObjectType.Surface | ObjectType.Brep;
        selection.SubObjectSelect = false;
        selection.EnablePreSelect(false, true);
        selection.SetCommandPrompt("API contract only");
        _ = selection.CommandResult();
        var joined = Brep.JoinBreps(new[] { cap, parent }, doc.ModelAbsoluteTolerance, doc.ModelAngleToleranceRadians);
        _ = cap.IsValid; _ = cap.IsManifold; _ = cap.IsSolid;
        _ = edge.TrimCount; _ = edge.TrimIndices(); _ = edge.AdjacentFaces();
        _ = edge.Valence == EdgeAdjacency.Interior;
        using var surface = cap.Faces[0].DuplicateSurface();
        _ = GeometryBase.GeometryEquals(surface, cap.Faces[0].DuplicateSurface());
        _ = Curve.JoinCurves(new List<Curve> { curve }, doc.ModelAbsoluteTolerance);
        _ = Curve.GetDistancesBetweenCurves(curve, edge, doc.ModelAbsoluteTolerance,
            out double max, out double ta, out double tb, out double min, out double ua, out double ub);
        _ = RhinoMath.IsValidDouble(max);
        _ = Intersection.BrepBrep(cap, parent, doc.ModelAbsoluteTolerance, out Curve[] curves, out Point3d[] points);
        _ = curve.ClosestPoint(curve.PointAt(curve.Domain.ParameterAt(.5)), out double parameter);
        _ = doc.ModelUnitSystem == UnitSystem.Millimeters;
    }
}
