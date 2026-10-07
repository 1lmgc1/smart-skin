using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using Rhino.FileIO;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

// A finite finalist screen, never a global regularity or nonintersection certificate.
// The mesh has ordinary span subdivisions. Logarithmic endpoint approaches are
// differential stations only; putting them in mesh connectivity manufactures slivers.
internal static class NativeMatchFinalistScreen
{
    internal const int MaximumMeshVertices = 4096;
    internal const int MaximumMeshTriangles = 8192;
    internal const int MaximumDifferentialGridStations = 16384;
    private const int NativeIntersectionBudgetMilliseconds = 5000;
    private const double NormalizedIntersectionTolerance = 1e-7;
    private static readonly double[] MeshFractions = { 0, .25, .5, .75, 1 };
    private static readonly double[] DifferentialFractions = { 0, 1e-7, 1e-5, .25, .5, .75, 1 - 1e-5, 1 - 1e-7, 1 };

    internal static bool Check(Brep cap, NativeCompareInput input, Action checkpoint, Action<string> write, out string reason)
    {
        reason = "FINALIST_SCREEN_NOT_COMPLETED";
        var passed = false; var vertices = 0; var triangles = 0; var rankStations = 0; var upperExceptions = 0;
        var perforations = -1; var overlapPolylines = -1; var overlapVertices = -1; var overlapFaces = -1;
        var diagonal = double.NaN;
        try
        {
            checkpoint();
            if (!NativeCompareMeasure.Bounded(cap, out _) || !cap.IsSurface || !cap.IsManifold
                || cap.Loops.Count != 1 || cap.Loops[0].LoopType != BrepLoopType.Outer
                || cap.Edges.Any(edge => edge.Valence != EdgeAdjacency.Naked))
                throw new NativeCompareUnsupported("FINALIST_SINGLE_NATURAL_RECTANGLE_REQUIRED");
            var face = cap.Faces[0];
            if (face.IsClosed(0) || face.IsClosed(1))
                throw new NativeCompareUnsupported("FINALIST_CLOSED_PARAMETER_DOMAIN_UNSUPPORTED");
            var us = SpanStations(face, 0, MeshFractions); var vs = SpanStations(face, 1, MeshFractions);
            var rankUs = SpanStations(face, 0, DifferentialFractions); var rankVs = SpanStations(face, 1, DifferentialFractions);
            var vertexCount = (long)us.Length * vs.Length;
            var triangleCount = 2L * (us.Length - 1) * (vs.Length - 1);
            if (vertexCount > MaximumMeshVertices || triangleCount > MaximumMeshTriangles)
                throw new NativeCompareUnsupported("FINALIST_MESH_GRID_BUDGET_EXCEEDED");
            if ((long)rankUs.Length * rankVs.Length > MaximumDifferentialGridStations)
                throw new NativeCompareUnsupported("FINALIST_DIFFERENTIAL_GRID_BUDGET_EXCEEDED");
            vertices = (int)vertexCount; triangles = (int)triangleCount;
            var upperUvs = ExactUpperCorners(face, input);
            var points = new Point3d[vertices];
            for (var i = 0; i < us.Length; i++)
                for (var j = 0; j < vs.Length; j++)
                {
                    checkpoint();
                    var point = face.PointAt(us[i], vs[j]);
                    if (!point.IsValid) throw new NativeCompareUnsupported("FINALIST_NONFINITE_MESH_VERTEX");
                    points[i * vs.Length + j] = point;
                }
            var box = new BoundingBox(points);
            diagonal = box.Diagonal.Length;
            if (!box.IsValid || !NativeCompareMath.Finite(diagonal) || diagonal <= 0)
                throw new NativeCompareUnsupported("FINALIST_MESH_NORMALIZATION_UNRESOLVED");
            using var mesh = new Mesh();
            mesh.Vertices.UseDoublePrecisionVertices = true;
            for (var i = 0; i < points.Length; i++)
            {
                points[i] = new Point3d((points[i].X - box.Min.X) / diagonal,
                    (points[i].Y - box.Min.Y) / diagonal, (points[i].Z - box.Min.Z) / diagonal);
                if (!points[i].IsValid) throw new NativeCompareUnsupported("FINALIST_MESH_NORMALIZATION_NONFINITE");
                mesh.Vertices.Add(points[i]);
            }
            var normals = new Vector3d[triangles];
            for (var i = 0; i < us.Length - 1; i++)
                for (var j = 0; j < vs.Length - 1; j++)
                {
                    checkpoint();
                    var a = i * vs.Length + j; var b = (i + 1) * vs.Length + j;
                    var c = b + 1; var d = a + 1; var index = 2 * (i * (vs.Length - 1) + j);
                    // Both triangles wind positively in UV. The derivative cross product
                    // uses the same parameter orientation, including on a reversed face.
                    normals[index] = TriangleNormal(points[a], points[b], points[c]);
                    normals[index + 1] = TriangleNormal(points[a], points[c], points[d]);
                    mesh.Faces.AddFace(a, b, c); mesh.Faces.AddFace(a, c, d);
                    CheckCentroid(i, j, 2.0 / 3, 1.0 / 3, normals[index]);
                    CheckCentroid(i, j, 1.0 / 3, 2.0 / 3, normals[index + 1]);
                }
            if (!mesh.IsValid || mesh.Vertices.Count != vertices || mesh.Faces.Count != triangles)
                throw new NativeCompareUnsupported("FINALIST_MESH_INVALID_OR_UNRESOLVED");
            foreach (var u in rankUs)
                foreach (var v in rankVs)
                {
                    checkpoint(); rankStations++;
                    var normal = DifferentialNormal(face, u, v, upperUvs.Contains((u, v)), out var exempt);
                    if (exempt) { upperExceptions++; continue; }
                    // At a mesh edge/corner check every incident triangle containing
                    // this UV station, rather than choosing an arbitrary side of a knot.
                    foreach (var i in IncidentIntervals(us, u))
                        foreach (var j in IncidentIntervals(vs, v))
                        {
                            var fu = (u - us[i]) / (us[i + 1] - us[i]);
                            var fv = (v - vs[j]) / (vs[j + 1] - vs[j]);
                            var index = 2 * (i * (vs.Length - 1) + j);
                            // Roundoff at the diagonal requires both corresponding
                            // triangles; it must not choose a convenient orientation.
                            var diagonalDelta = fv - fu;
                            if (diagonalDelta <= NativeBuildCapPolicy.MinimumRelativeJacobian) Agree(normal, normals[index]);
                            if (diagonalDelta >= -NativeBuildCapPolicy.MinimumRelativeJacobian) Agree(normal, normals[index + 1]);
                        }
                }

            checkpoint();
            using (var outputs = new NativeMatchMeshOutputPolicy<Mesh>())
            {
                using var log = new TextLog();
                using var cancellation = new CancellationTokenSource(NativeIntersectionBudgetMilliseconds);
                bool success; Polyline[]? perforationLines; Polyline[]? overlapLines;
                try
                {
                    success = mesh.GetSelfIntersections(NormalizedIntersectionTolerance, out perforationLines,
                        true, out overlapLines, true, out outputs.OverlapMesh, log, cancellation.Token, null);
                }
                catch (Exception error)
                {
                    // An optional native-screen failure rejects this candidate only.
                    // Caller checkpoints and source checks deliberately remain outside
                    // this catch so cancellation, deadlines and stale sources propagate.
                    throw new NativeCompareUnsupported("FINALIST_NATIVE_SELF_INTERSECTION_EXCEPTION:" + error.GetType().Name);
                }
                var nativeCancelled = cancellation.IsCancellationRequested;
                cancellation.CancelAfter(Timeout.Infinite);
                checkpoint();
                // Exact 8.21 MeshMesh_Helper IL initializes the polyline outputs to
                // null and assigns them only for Count > 0. With overlapsMesh=true it
                // always allocates the mesh before calling native intersection.
                var failure = outputs.Failure(success, nativeCancelled,
                    perforationLines?.Length, overlapLines?.Length, value => value.Vertices.Count, value => value.Faces.Count);
                perforations = outputs.Perforations; overlapPolylines = outputs.OverlapPolylines;
                overlapVertices = outputs.OverlapVertices; overlapFaces = outputs.OverlapFaces;
                // Any returned entry (even malformed/empty polyline data), face or
                // orphan overlap vertex is nonempty evidence and cannot promote.
                if (failure is not null) throw new NativeCompareUnsupported(failure);
            }
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            checkpoint();
            reason = "FINITE_RANK_LOCAL_ORIENTATION_AND_MESH_SCREEN_PASSED";
            passed = true;

            void CheckCentroid(int i, int j, double fu, double fv, Vector3d triangleNormal)
            {
                checkpoint(); rankStations++;
                var u = us[i] + (us[i + 1] - us[i]) * fu;
                var v = vs[j] + (vs[j + 1] - vs[j]) * fv;
                if (!(u > us[i] && u < us[i + 1] && v > vs[j] && v < vs[j + 1]))
                    throw new NativeCompareUnsupported("FINALIST_TRIANGLE_INTERIOR_PARAMETER_UNRESOLVED");
                Agree(DifferentialNormal(face, u, v, false, out _), triangleNormal);
            }
        }
        catch (NativeCompareUnsupported error) { reason = error.Message; }
        finally
        {
            write("SMARTSKIN_NATIVE_IMPROVE_FINALIST_SCREEN | passed=" + passed + " | reason=" + reason
                + " | mesh_vertices=" + vertices + " | mesh_triangles=" + triangles + " | differential_stations=" + rankStations
                + " | exact_upper_point_rank_exceptions=" + upperExceptions + " | finite_bands_excluded=0"
                + " | mesh_max_vertices=" + MaximumMeshVertices + " | mesh_max_triangles=" + MaximumMeshTriangles
                + " | differential_grid_max_stations=" + MaximumDifferentialGridStations
                + " | mesh_normalization=SAMPLED_BBOX_DIAGONAL | mesh_normalization_scale=" + NativeCompareProbeProtocol.Number(diagonal)
                + " | mesh_intersection_normalized_tolerance=" + NativeCompareProbeProtocol.Number(NormalizedIntersectionTolerance)
                + " | mesh_intersection_world_tolerance=" + NativeCompareProbeProtocol.Number(diagonal * NormalizedIntersectionTolerance)
                + " | native_intersection_budget_ms=" + NativeIntersectionBudgetMilliseconds
                + " | native_perforations=" + perforations + " | native_overlap_polylines=" + overlapPolylines
                + " | native_overlap_vertices=" + overlapVertices + " | native_overlap_faces=" + overlapFaces
                + " | physical_attachment_tolerances=UNCHANGED | global_regularity_nonintersection=NOT_VERIFIED");
        }
        return passed;
    }

    private static double[] SpanStations(Surface surface, int direction, double[] fractions)
    {
        var domain = surface.Domain(direction); var spans = surface.GetSpanVector(direction);
        if (!NativeCompareMath.Finite(domain.T0) || !NativeCompareMath.Finite(domain.T1)
            || !NativeCompareMath.Finite(domain.Length) || domain.Length <= 0
            || spans is null || spans.Length < 2 || spans.Length > 513 || spans.Any(value => !NativeCompareMath.Finite(value)))
            throw new NativeCompareUnsupported("FINALIST_SPAN_DOMAIN_OR_LIMIT_UNSUPPORTED");
        var values = new SortedSet<double>(); var covered = domain.T0;
        for (var i = 1; i < spans.Length; i++)
        {
            if (spans[i] < spans[i - 1]) throw new NativeCompareUnsupported("FINALIST_UNORDERED_KNOT_SPANS");
            var a = Math.Max(domain.T0, spans[i - 1]); var b = Math.Min(domain.T1, spans[i]);
            if (b <= a) continue;
            if (a != covered) throw new NativeCompareUnsupported("FINALIST_KNOT_SPAN_COVERAGE_UNRESOLVED");
            var previous = a;
            foreach (var fraction in fractions)
            {
                var value = fraction == 0 ? a : fraction == 1 ? b : a + (b - a) * fraction;
                if (!NativeCompareMath.Finite(value) || (fraction > 0 && value <= previous)
                    || (fraction < 1 && value >= b))
                    throw new NativeCompareUnsupported("FINALIST_PARAMETER_APPROACH_RESOLUTION_UNRESOLVED");
                values.Add(value); previous = value;
            }
            covered = b;
        }
        if (covered != domain.T1 || values.Count < 2)
            throw new NativeCompareUnsupported("FINALIST_KNOT_SPAN_COVERAGE_UNRESOLVED");
        return values.ToArray();
    }

    private static HashSet<(double U, double V)> ExactUpperCorners(BrepFace face, NativeCompareInput input)
    {
        var result = new HashSet<(double U, double V)>();
        var bindings = NativeBuildCapQualification.UpperBindings(input);
        if (bindings.Count != 4) return result;
        var mapped = new List<(double U, double V)>();
        foreach (var binding in bindings)
        {
            var point = binding.Edge.Native.PointAt(binding.Parameter); var matches = new List<(double U, double V)>();
            if (!point.IsValid) return result;
            foreach (var u in new[] { face.Domain(0).T0, face.Domain(0).T1 })
                foreach (var v in new[] { face.Domain(1).T0, face.Domain(1).T1 })
                    if (point.DistanceTo(face.PointAt(u, v)) <= input.Tolerance) matches.Add((u, v));
            if (matches.Count != 1) return result;
            mapped.Add(matches[0]);
        }
        // UpperBindings supplies upper-start/previous-end then upper-end/next-start.
        // Preserve those two original source-intersection pairs explicitly.
        if (mapped[0] == mapped[1] && mapped[2] == mapped[3] && mapped[0] != mapped[2])
        { result.Add(mapped[0]); result.Add(mapped[2]); }
        return result;
    }

    private static Vector3d DifferentialNormal(BrepFace face, double u, double v, bool exactUpper, out bool exempt)
    {
        exempt = false;
        if (!face.Evaluate(u, v, 1, out var point, out var derivatives) || !point.IsValid
            || derivatives is null || derivatives.Length < 2 || derivatives.Any(vector => !vector.IsValid))
            throw new NativeCompareUnsupported("FINALIST_NONFINITE_DIFFERENTIAL_STATION");
        if (!Regular(derivatives[0], derivatives[1]))
        {
            if (exactUpper) { exempt = true; return Vector3d.Unset; }
            throw new NativeCompareUnsupported("FINALIST_NONREGULAR_DIFFERENTIAL_STATION");
        }
        return CrossUnit(derivatives[0], derivatives[1]);
    }

    private static Vector3d TriangleNormal(Point3d a, Point3d b, Point3d c)
    {
        var ab = b - a; var ac = c - a;
        if (!Regular(ab, ac)) throw new NativeCompareUnsupported("FINALIST_MESH_TRIANGLE_RANK_UNRESOLVED");
        return CrossUnit(ab, ac);
    }

    private static bool Regular(Vector3d u, Vector3d v) => NativeBuildCapPolicy.RegularJacobian(
        new[] { u.X, u.Y, u.Z }, new[] { v.X, v.Y, v.Z });

    private static Vector3d CrossUnit(Vector3d u, Vector3d v)
    {
        // Independent component normalization prevents overflow/underflow before
        // crossing differently scaled U/V derivatives or normalized mesh edges.
        var us = Math.Max(Math.Abs(u.X), Math.Max(Math.Abs(u.Y), Math.Abs(u.Z)));
        var vs = Math.Max(Math.Abs(v.X), Math.Max(Math.Abs(v.Y), Math.Abs(v.Z)));
        u = new Vector3d(u.X / us, u.Y / us, u.Z / us);
        v = new Vector3d(v.X / vs, v.Y / vs, v.Z / vs);
        var cross = Vector3d.CrossProduct(u, v);
        if (!cross.IsValid || !cross.Unitize()) throw new NativeCompareUnsupported("FINALIST_NORMAL_UNRESOLVED");
        return cross;
    }

    private static void Agree(Vector3d derivativeNormal, Vector3d triangleNormal)
    {
        var dot = derivativeNormal * triangleNormal;
        if (!NativeCompareMath.Finite(dot) || dot <= NativeBuildCapPolicy.MinimumRelativeJacobian)
            throw new NativeCompareUnsupported("FINALIST_LOCAL_TRIANGLE_ORIENTATION_UNRESOLVED_OR_REVERSED");
    }

    private static IEnumerable<int> IncidentIntervals(double[] values, double value)
    {
        var index = Array.BinarySearch(values, value);
        if (index >= 0)
        {
            if (index > 0) yield return index - 1;
            if (index + 1 < values.Length) yield return index;
        }
        else
        {
            index = ~index - 1;
            if (index < 0 || index + 1 >= values.Length)
                throw new NativeCompareUnsupported("FINALIST_DIFFERENTIAL_TO_MESH_UV_UNRESOLVED");
            yield return index;
        }
    }
}
