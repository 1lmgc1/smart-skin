using System;
using System.Collections.Generic;
using Rhino;
using Rhino.Geometry;
using Rhino.Input.Custom;

// Compile-only public API contract. Never label this as execution in Rhino.
public static class RhinoApiProbe
{
    public static Brep? Probe(BrepEdge edge, Brep parent, double tolerance, GetObject picker)
    {
        picker.EnablePreSelect(false, true);
        var trim = edge.Brep.Trims[edge.TrimIndices()[0]];
        var identity = (trim.TrimIndex, trim.Face.FaceIndex, edge.EdgeIndex);
        if (!trim.GetTrimParameter(edge.Domain.Mid, out var tp)) return null;
        var uv = trim.PointAt(tp);
        var n = trim.Face.NormalAt(uv.X, uv.Y);
        _ = trim.Face.Evaluate(uv.X, uv.Y, 2, out var ep, out var derivatives);
        var c = trim.Face.CurvatureAt(uv.X, uv.Y);
        if (trim.Face.OrientationIsReversed) n.Reverse();
        var k = c.Kappa(0) + c.Kappa(1) + c.Direction(0).Length + c.Direction(1).Length + identity.Item1;
        using var surface = NurbsSurface.Create(3, false, 4, 4, 8, 8);
        surface.Points.SetPoint(0, 0, new Point3d(k, 0, 0));
        surface.KnotsU[0] = 0; surface.KnotsV[0] = 0;
        using var cap = surface.ToBrep();
        var joined = Brep.JoinBreps(new[] { parent, cap }, tolerance, RhinoMath.ToRadians(1));
        Curve.GetDistancesBetweenCurves(edge, edge, tolerance, out _, out _, out _, out _, out _, out _);
        foreach (var face in parent.Faces) { using var s = face.DuplicateSurface(); _ = GeometryBase.GeometryEquals(s, surface); }
        foreach (var e in parent.Edges) { _ = e.AdjacentFaces(); _ = e.Valence; }
        if (joined is null || joined.Length != 1) return null;
        return joined[0];
    }
}
