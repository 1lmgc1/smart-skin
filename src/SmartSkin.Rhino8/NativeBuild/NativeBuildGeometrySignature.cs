using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

// Exact defining geometry for the bounded isolated cap, independent of document metadata.
// Included: homogeneous supports and curves, knots, dimensions, degrees, rational flags,
// domains, effective proxy curves/surfaces, vertices, incidence, order, and orientation.
// Excluded: UUIDs, user data/copy counters, display/packing/mesh/bounding caches, unused
// geometry-table entries, derived tolerance estimates and IsoStatus. Each referenced
// curve/support is stored inline: internal table sharing is not part of the cap's shape.
// Both source/candidate archive seals remain separate, unchanged transaction checks.
internal static class NativeBuildGeometrySignature
{
    internal static byte[] Capture(Brep cap)
    {
        // The memory bound may include native display caches; it is a resource limit,
        // never evidence that the defining geometry differs.
        if (cap.MemoryEstimate() > 32 * 1024 * 1024)
            throw new InvalidOperationException("CAP_SIGNATURE_SNAPSHOT_MEMORY_LIMIT");
        if (cap.Faces.Count != 1 || cap.Edges.Count > 32 || cap.Vertices.Count > 64 || cap.Trims.Count > 64 || cap.Loops.Count != 1)
            throw new InvalidOperationException("CAP_SIGNATURE_TOPOLOGY_LIMIT");
        // Validity and proxy conversion may fill native caches. Never do those reads on
        // the sealed preview or live document geometry itself.
        using var snapshot = cap.DuplicateBrep();
        if (snapshot is null) throw new InvalidOperationException("CAP_SIGNATURE_SNAPSHOT_FAILED");
        return CaptureSnapshot(snapshot);
    }
    private static byte[] CaptureSnapshot(Brep cap)
    {
        if (!cap.IsValid || cap.Faces.Count != 1 || cap.Edges.Count < 1 || cap.Edges.Count > 32
            || cap.Vertices.Count < 1 || cap.Vertices.Count > 64 || cap.Trims.Count < 1 || cap.Trims.Count > 64
            || cap.Loops.Count != 1 || cap.Loops[0].LoopType != BrepLoopType.Outer)
            throw new InvalidOperationException("UNSUPPORTED_OR_INVALID_INSERTED_CAP_GEOMETRY");
        using var writer = new NativeBuildGeometryWriter();
        writer.Integers("brep_topology_counts", cap.Vertices.Count, cap.Edges.Count, cap.Trims.Count, cap.Loops.Count, cap.Faces.Count);
        foreach (var vertex in cap.Vertices)
        {
            writer.Integers("vertex", vertex.VertexIndex);
            writer.Numbers("location", vertex.Location.X, vertex.Location.Y, vertex.Location.Z);
        }
        foreach (var edge in cap.Edges)
        {
            writer.Integers("edge", edge.EdgeIndex, edge.StartVertex.VertexIndex, edge.EndVertex.VertexIndex,
                edge.ProxyCurveIsReversed ? 1 : 0);
            writer.Integers("edge_trim_incidence", edge.TrimIndices().OrderBy(index => index).ToArray());
            writer.Numbers("edge_proxy_domain", edge.Domain.T0, edge.Domain.T1);
            WriteCurve(writer, "edge_underlying_curve3d", edge.EdgeCurve);
            // The effective NURBS captures the proxy's actual real-curve subdomain and mapping;
            // RhinoCommon 8.21 exposes reversal but no raw ProxyCurveDomain getter.
            WriteCurve(writer, "edge_effective_proxy_curve3d", edge);
        }
        foreach (var trim in cap.Trims)
        {
            writer.Integers("trim", trim.TrimIndex, trim.Loop.LoopIndex, trim.Face.FaceIndex,
                trim.Edge?.EdgeIndex ?? -1, trim.StartVertex.VertexIndex, trim.EndVertex.VertexIndex,
                (int)trim.TrimType, trim.ProxyCurveIsReversed ? 1 : 0, trim.IsReversed() ? 1 : 0);
            writer.Numbers("trim_proxy_domain", trim.Domain.T0, trim.Domain.T1);
            WriteCurve(writer, "trim_underlying_curve2d", trim.TrimCurve);
            WriteCurve(writer, "trim_effective_proxy_curve2d", trim);
        }
        foreach (var loop in cap.Loops)
        {
            writer.Integers("loop", loop.LoopIndex, loop.Face.FaceIndex, (int)loop.LoopType);
            writer.Integers("loop_trim_order", loop.Trims.Select(trim => trim.TrimIndex).ToArray());
        }
        foreach (var face in cap.Faces)
        {
            writer.Integers("face", face.FaceIndex, face.OrientationIsReversed ? 1 : 0);
            writer.Integers("face_loop_order", face.Loops.Select(loop => loop.LoopIndex).ToArray());
            writer.Numbers("face_proxy_domains", face.Domain(0).T0, face.Domain(0).T1, face.Domain(1).T0, face.Domain(1).T1);
            WriteSurface(writer, "underlying_surface", face.UnderlyingSurface());
            WriteSurface(writer, "effective_face_surface", face);
        }
        return writer.Finish();
    }
    private static void WriteCurve(NativeBuildGeometryWriter writer, string role, Curve curve)
    {
        using var nurbs = curve.ToNurbsCurve();
        if (nurbs is null || nurbs.Points.Count < 2 || nurbs.Points.Count > 8192 || nurbs.Knots.Count > 16384)
            throw new InvalidOperationException("UNSUPPORTED_CAP_CURVE_SIGNATURE");
        var points = new List<double[]>(nurbs.Points.Count);
        for (var i = 0; i < nurbs.Points.Count; i++)
        {
            if (!nurbs.Points.GetPoint(i, out Point4d point)) throw new InvalidOperationException("CAP_CURVE_HOMOGENEOUS_READ_FAILED");
            points.Add(new[] { point.X, point.Y, point.Z, point.W });
        }
        writer.Curve(role, nurbs.Dimension, nurbs.Degree, nurbs.IsRational, nurbs.Domain.T0, nurbs.Domain.T1, nurbs.Knots.ToArray(), points);
    }
    private static void WriteSurface(NativeBuildGeometryWriter writer, string role, Surface surface)
    {
        using var nurbs = surface.ToNurbsSurface();
        if (nurbs is null || nurbs.Points.CountU * (long)nurbs.Points.CountV > 4096
            || nurbs.KnotsU.Count > 8192 || nurbs.KnotsV.Count > 8192)
            throw new InvalidOperationException("UNSUPPORTED_CAP_SURFACE_SIGNATURE");
        var points = new List<double[]>();
        for (var u = 0; u < nurbs.Points.CountU; u++)
            for (var v = 0; v < nurbs.Points.CountV; v++)
            {
                if (!nurbs.Points.GetPoint(u, v, out Point4d point)) throw new InvalidOperationException("CAP_SURFACE_HOMOGENEOUS_READ_FAILED");
                points.Add(new[] { point.X, point.Y, point.Z, point.W });
            }
        // 8.21 has no Surface.Dimension getter. ON_Brep::IsValidGeometry (required
        // above) explicitly rejects any support whose native dimension is not 3.
        writer.Surface(role, 3, nurbs.Degree(0), nurbs.Degree(1), nurbs.IsRational,
            nurbs.Points.CountU, nurbs.Points.CountV, nurbs.Domain(0).T0, nurbs.Domain(0).T1, nurbs.Domain(1).T0, nurbs.Domain(1).T1,
            nurbs.KnotsU.ToArray(), nurbs.KnotsV.ToArray(), points);
    }
}
