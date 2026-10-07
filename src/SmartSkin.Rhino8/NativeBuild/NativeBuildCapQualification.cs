using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeBuildCapQualification
{
    internal const string UserStatus = "стыковка без гарантии плавности";
    internal bool Ready { get; private set; }
    internal string Reason { get; private set; } = "CAP_NOT_QUALIFIED";
    private byte[] _evidence = Array.Empty<byte>();
    private string _qualifiedCapFingerprint = string.Empty;
    private string _sourceBinding = string.Empty;
    internal byte[] Evidence => (byte[])_evidence.Clone();
    internal bool Matches(NativeCompareInput input, Brep cap) => Ready
        && input.GeometryFingerprint(cap) == _qualifiedCapFingerprint && SourceBinding(input) == _sourceBinding;
    private static string SourceBinding(NativeCompareInput input) => string.Join(";", input.Owners.OrderBy(owner => owner.Id)
        .Select(owner => owner.Id.ToString("N") + ":" + owner.Serial + ":" + owner.Fingerprint + ":" + owner.CopyFingerprint))
        + "|derivation=" + input.Derivation + "|selected=" + string.Join(";", input.Sides.SelectMany((side, index) => side.Select(edge =>
            index + ":" + input.Owners[edge.OwnerIndex].Id.ToString("N") + ":" + edge.Native.EdgeIndex
            + ":" + NativeCompareProbeProtocol.Number(edge.Native.Domain.T0) + ":" + NativeCompareProbeProtocol.Number(edge.Native.Domain.T1)
            + ":" + edge.Reverse + ":features=" + string.Join(",", edge.Features.Select(NativeCompareProbeProtocol.Number)))));
    internal void BindImprovement(NativeCompareInput input, Brep cap, string improvementEvidence)
    {
        if (!Matches(input, cap) || string.IsNullOrEmpty(improvementEvidence))
            throw new InvalidOperationException("BUILD_IMPROVEMENT_CAP_SEAL_MISMATCH");
        _evidence = Encoding.UTF8.GetBytes(Encoding.UTF8.GetString(_evidence) + "|improvement=" + improvementEvidence);
    }
    internal int BoundaryStations { get; private set; }
    internal int RankStations { get; private set; }
    internal int ExactUpperExceptions { get; private set; }

    internal static NativeBuildCapQualification Evaluate(NativeSeedJoinResult join, NativeCompareInput input,
        Action checkpoint, Action<string> write)
    {
        var result = new NativeBuildCapQualification();
        try
        {
            if (!join.ProvenanceResolved || !join.SelectedOpeningJoined || !join.TemporariesDisposed || join.Cap is null)
                throw new NativeCompareUnsupported("BUILD_REQUIRES_QUALIFIED_SELECTED_JOIN_SEAMS");
            var cap = join.Cap;
            if (!NativeCompareMeasure.Bounded(cap, out _) || !cap.IsManifold || cap.Loops.Count != 1
                || cap.Loops[0].LoopType != BrepLoopType.Outer || cap.Edges.Any(edge => edge.Valence != EdgeAdjacency.Naked))
                throw new NativeCompareUnsupported("BUILD_CAP_VALIDITY_OR_SINGLE_REGION_FAILED");
            var face = cap.Faces[0];
            var upperBindings = UpperBindings(input);
            var upperUvs = new HashSet<(double U, double V)>();
            // Exceptions are optional, point-only, and require a unique actual parameter corner.
            foreach (var binding in upperBindings)
            {
                var point = binding.Edge.Native.PointAt(binding.Parameter);
                var matches = new List<(double U, double V)>();
                foreach (var u in new[] { face.Domain(0).T0, face.Domain(0).T1 })
                    foreach (var v in new[] { face.Domain(1).T0, face.Domain(1).T1 })
                        if (point.DistanceTo(face.PointAt(u, v)) <= input.Tolerance) matches.Add((u, v));
                if (matches.Count == 1) upperUvs.Add(matches[0]);
            }
            if (upperUvs.Count != 2) { upperUvs.Clear(); upperBindings.Clear(); }
            foreach (var original in input.Edges)
                foreach (var parameter in NativeSeedJoinExperiment.Stations(original.Native, original.Features))
                {
                    checkpoint();
                    var point = original.Native.PointAt(parameter);
                    var hits = BoundaryHits(cap, point, input.Tolerance);
                    if (hits.Count == 0 || !NativeSeedJoinPolicy.OneTopologicalLocation(hits.Select(hit =>
                        (0, EndpointVertex(hit.Edge, point, input.Tolerance))).ToArray()))
                        throw new NativeCompareUnsupported("BUILD_ORIGINAL_TO_CAP_BOUNDARY_UNRESOLVED");
                    result.BoundaryStations++;
                    var exactUpper = upperBindings.Any(binding => ReferenceEquals(binding.Edge, original) && binding.Parameter == parameter);
                    foreach (var hit in hits)
                    {
                        var trim = NativeCompareSideBinding.Trim(hit.Edge);
                        if (!trim.GetTrimParameter(hit.Parameter, out var t)) throw new NativeCompareUnsupported("BUILD_CAP_TRIM_PARAMETER_UNRESOLVED");
                        var uv = trim.PointAt(t);
                        if (!uv.IsValid || face.PointAt(uv.X, uv.Y).DistanceTo(point) > input.Tolerance)
                            throw new NativeCompareUnsupported("BUILD_CAP_TRIM_POSITION_FAILED");
                        CheckRank(face, uv.X, uv.Y, exactUpper && upperUvs.Contains((uv.X, uv.Y)), result);
                    }
                }
            foreach (var edge in cap.Edges)
                foreach (var parameter in NativeSeedJoinExperiment.Stations(edge, Array.Empty<double>()))
                {
                    checkpoint();
                    var point = edge.PointAt(parameter);
                    var gap = double.PositiveInfinity;
                    foreach (var original in input.Edges)
                        if (original.Native.ClosestPoint(point, out var t)) gap = Math.Min(gap, original.Native.PointAt(t).DistanceTo(point));
                    if (!NativeCompareMath.Finite(gap) || gap > input.Tolerance)
                        throw new NativeCompareUnsupported("BUILD_CAP_TO_ORIGINAL_BOUNDARY_FAILED");
                    result.BoundaryStations++;
                }

            var us = SpanStations(face, 0); var vs = SpanStations(face, 1);
            if ((long)us.Length * vs.Length > 16384) throw new NativeCompareUnsupported("BUILD_CAP_RANK_SAMPLE_LIMIT");
            var interior = 0;
            foreach (var u in us)
                foreach (var v in vs)
                {
                    checkpoint();
                    var relation = face.IsPointOnFace(u, v, 0.0);
                    if (relation == PointFaceRelation.Exterior) continue;
                    CheckRank(face, u, v, upperUvs.Contains((u, v)), result);
                    if (relation == PointFaceRelation.Interior) interior++;
                }
            if (interior == 0) throw new NativeCompareUnsupported("BUILD_CAP_INTERIOR_RANK_NOT_VERIFIED");
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            result.Ready = true; result.Reason = "SAMPLED_G0_JOIN_AND_CAP_RANK_READY";
            result._qualifiedCapFingerprint = input.GeometryFingerprint(cap);
            result._sourceBinding = SourceBinding(input);
            result._evidence = Encoding.UTF8.GetBytes("NATIVE_G0_USER_TEST_V1|" + result.Reason + "|"
                + result.BoundaryStations + "|" + result.RankStations + "|" + result.ExactUpperExceptions
                + "|" + NativeCompareProbeProtocol.Number(input.Tolerance) + "|" + UserStatus
                + "|cap=" + result._qualifiedCapFingerprint + "|sources=" + result._sourceBinding);
        }
        catch (NativeCompareUnsupported exception) { result.Reason = exception.Message; }
        write("SMARTSKIN_NATIVE_BUILD_QUALIFICATION | ready=" + result.Ready + " | reason=" + result.Reason
            + " | boundary_stations=" + result.BoundaryStations + " | rank_stations=" + result.RankStations
            + " | exact_upper_point_rank_exceptions=" + result.ExactUpperExceptions
            + " | finite_bands_excluded=0 | rank_threshold=64_BINARY64_MACHINE_EPSILON_RELATIVE"
            + " | user_status=" + UserStatus + " | global_regularity_separation_G1_G2=NOT_VERIFIED");
        return result;
    }

    private static void CheckRank(BrepFace face, double u, double v, bool exactApprovedUpper, NativeBuildCapQualification result)
    {
        result.RankStations++;
        var evaluated = face.Evaluate(u, v, 1, out var point, out var derivatives);
        var finite = evaluated && point.IsValid && derivatives is not null && derivatives.Length >= 2 && derivatives.All(vector => vector.IsValid);
        var regular = finite && NativeBuildCapPolicy.RegularJacobian(new[] { derivatives![0].X, derivatives[0].Y, derivatives[0].Z },
                new[] { derivatives[1].X, derivatives[1].Y, derivatives[1].Z });
        if (regular) return;
        if (exactApprovedUpper && finite)
        { result.ExactUpperExceptions++; return; }
        throw new NativeCompareUnsupported("BUILD_CAP_NONREGULAR_OR_NONFINITE_STATION;u="
            + NativeCompareProbeProtocol.Number(u) + ";v=" + NativeCompareProbeProtocol.Number(v));
    }
    internal static List<(NativeCompareInput.Edge Edge, double Parameter)> UpperBindings(NativeCompareInput input)
    {
        var result = new List<(NativeCompareInput.Edge, double)>();
        if (input.Derivation != "NATURAL_SIDE_PAIR_COPLANAR_PARENT_CHAIN_STRAIGHT_CHAIN") return result;
        var planar = new List<int>();
        for (var side = 0; side < input.Sides.Count; side++)
        {
            var face = NativeCompareMeasure.Face(input.Sides[side][0].Native);
            if (face is null || !face.TryGetPlane(out var plane, input.Tolerance)) continue;
            if (input.Sides[side].All(edge => NativeCompareMeasure.Face(edge.Native) is BrepFace parent
                && parent.TryGetPlane(out var other, input.Tolerance)
                && Math.Abs(plane.DistanceTo(other.Origin)) <= input.Tolerance
                && Math.Abs(plane.Normal * other.Normal) >= Math.Cos(1e-5))) planar.Add(side);
        }
        if (planar.Count != 1) return result;
        var upper = input.Sides[planar[0]];
        var previous = input.Sides[(planar[0] + 3) % 4]; var next = input.Sides[(planar[0] + 1) % 4];
        foreach (var branch in new[] { previous, next })
        {
            var first = branch[0]; var trim = NativeCompareSideBinding.Trim(first.Native);
            if (branch.Any(edge => edge.OwnerIndex != first.OwnerIndex
                || NativeCompareSideBinding.Trim(edge.Native).Face.FaceIndex != trim.Face.FaceIndex
                || NativeCompareSideBinding.Trim(edge.Native).IsoStatus != trim.IsoStatus
                || !NativeCompareMeasure.NaturalTrimLocus(NativeCompareSideBinding.Trim(edge.Native)))) return result;
        }
        result.Add((upper[0], upper[0].Parameter(false)));
        result.Add((previous[previous.Count - 1], previous[previous.Count - 1].Parameter(true)));
        result.Add((upper[upper.Count - 1], upper[upper.Count - 1].Parameter(true)));
        result.Add((next[0], next[0].Parameter(false)));
        return result;
    }

    private static double[] SpanStations(Surface face, int direction)
    {
        var spans = face.GetSpanVector(direction);
        if (spans is null || spans.Length < 2 || spans.Length > 513)
            throw new NativeCompareUnsupported("BUILD_CAP_SPAN_LIMIT");
        var domain = face.Domain(direction); var values = new SortedSet<double>();
        for (var i = 1; i < spans.Length; i++)
        {
            var a = Math.Max(domain.T0, spans[i - 1]); var b = Math.Min(domain.T1, spans[i]);
            if (b <= a) continue;
            foreach (var fraction in new[] { 0.0, 1e-7, 1e-5, .25, .5, .75, 1 - 1e-5, 1 - 1e-7, 1.0 })
                values.Add(a + (b - a) * fraction);
        }
        return values.ToArray();
    }
    private static List<(BrepEdge Edge, double Parameter)> BoundaryHits(Brep cap, Point3d point, double tolerance)
    {
        var hits = new List<(BrepEdge, double)>();
        foreach (var edge in cap.Edges)
            if (edge.ClosestPoint(point, out var parameter) && edge.PointAt(parameter).DistanceTo(point) <= tolerance)
                hits.Add((edge, parameter));
        return hits;
    }
    private static int EndpointVertex(BrepEdge edge, Point3d point, double tolerance)
    {
        var a = point.DistanceTo(edge.PointAtStart) <= tolerance; var b = point.DistanceTo(edge.PointAtEnd) <= tolerance;
        return a != b ? (a ? edge.StartVertex.VertexIndex : edge.EndVertex.VertexIndex) : -1;
    }
}
