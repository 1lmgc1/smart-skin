using System;
using System.Collections.Generic;
using System.Linq;
using Rhino;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

/// <summary>Conditional natural-parameter-side lineage, never a proof that Match preserves physical correspondence.</summary>
internal sealed class NativeCompareSideBinding
{
    private readonly IsoStatus[] _iso = new IsoStatus[4];

    internal static NativeCompareSideBinding CaptureSeed(Brep seed, NativeCompareInput input)
    {
        var binding = new NativeCompareSideBinding();
        for (var side = 0; side < 4; side++)
        {
            var start = input.Sides[side][0].Start;
            var end = input.Sides[side][input.Sides[side].Count - 1].End;
            var matches = seed.Edges.Where(IsNatural).Where(edge =>
                (edge.PointAtStart.DistanceTo(start) <= input.Tolerance && edge.PointAtEnd.DistanceTo(end) <= input.Tolerance)
                || (edge.PointAtStart.DistanceTo(end) <= input.Tolerance && edge.PointAtEnd.DistanceTo(start) <= input.Tolerance)).ToArray();
            if (matches.Length != 1) throw new NativeCompareUnsupported("UNSUPPORTED_SEED_LOGICAL_SIDE_ENDPOINT_MAPPING");
            binding._iso[side] = Trim(matches[0]).IsoStatus;
        }
        if (binding._iso.Distinct().Count() != 4)
            throw new NativeCompareUnsupported("UNSUPPORTED_SEED_NATURAL_SIDE_LINEAGE");
        return binding;
    }

    internal BrepEdge? Resolve(Brep candidate, int side)
    {
        if (candidate.Faces.Count != 1) return null;
        var matches = candidate.Edges.Where(IsNatural).Where(edge => Trim(edge).IsoStatus == _iso[side]).ToArray();
        return matches.Length == 1 ? matches[0] : null;
    }

    internal static bool IsNatural(BrepEdge edge) => edge.Valence == EdgeAdjacency.Naked
        && BoundaryMatchVerifier.IsNaturalBoundary(edge) && NativeCompareMeasure.NaturalTrimLocus(Trim(edge));
    internal static BrepTrim Trim(BrepEdge edge) => edge.Brep.Trims[edge.TrimIndices()[0]];
    private static string Point(Point3d point) => NativeCompareProbeProtocol.Point(point.X, point.Y, point.Z);
    private static string Domain(Interval domain) => "[" + NativeCompareProbeProtocol.Number(domain.T0)
        + "," + NativeCompareProbeProtocol.Number(domain.T1) + "]";

    internal static void TraceSources(NativeCompareInput input)
    {
        // Private runtime values stay in this user's local Rhino command history. No artifact/file export.
        for (var side = 0; side < 4; side++)
            for (var member = 0; member < input.Sides[side].Count; member++)
            {
                var source = input.Sides[side][member];
                var edge = source.Native; var trim = Trim(edge);
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_SOURCE | side=" + side + " | logical_member=" + member
                    + " | owner=" + source.OwnerIndex + " | source_object_id=" + input.Owners[source.OwnerIndex].Id
                    + " | edge=" + edge.EdgeIndex + " | trim=" + trim.TrimIndex + " | face=" + trim.Face.FaceIndex
                    + " | loop=" + trim.Loop.LoopIndex + " | iso=" + trim.IsoStatus
                    + " | domain=" + Domain(edge.Domain) + " | native_start=" + Point(edge.PointAtStart)
                    + " | native_end=" + Point(edge.PointAtEnd) + " | native_vs_logical=" + (source.Reverse ? "REVERSED" : "SAME")
                    + " | logical_start=" + Point(source.Start) + " | logical_end=" + Point(source.End)
                    + " | trim_reversed=" + trim.IsReversed() + " | face_reversed=" + trim.Face.OrientationIsReversed
                    + " | target_runtime_type=BrepEdge | export=LOCAL_COMMAND_HISTORY_ONLY");
            }
    }

    internal void TraceCandidate(string recipe, string phase, Brep candidate, NativeCompareInput input)
    {
        for (var side = 0; side < 4; side++)
        {
            var edge = Resolve(candidate, side);
            if (edge is null)
            {
                RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_MAPPING | recipe=" + recipe + " | phase=" + phase
                    + " | side=" + side + " | seed_iso=" + _iso[side] + " | mapping=NOT_VERIFIED_MISSING_OR_DUPLICATE_NATURAL_SIDE");
                continue;
            }
            var corners = input.Sides.Select(run => run[0].Start).ToArray();
            var startDistances = corners.Select(point => edge.PointAtStart.DistanceTo(point)).ToArray();
            var endDistances = corners.Select(point => edge.PointAtEnd.DistanceTo(point)).ToArray();
            var next = (side + 1) % 4;
            var expectedPair = startDistances[side] <= input.Tolerance && endDistances[next] <= input.Tolerance ? "FORWARD"
                : startDistances[next] <= input.Tolerance && endDistances[side] <= input.Tolerance ? "REVERSED" : "MOVED_OR_REPARAMETERIZED";
            var trim = Trim(edge);
            RhinoApp.WriteLine("SMARTSKIN_NATIVE_COMPARE_MAPPING | recipe=" + recipe + " | phase=" + phase
                + " | side=" + side + " | relation=" + NativeCompareProbeProtocol.Relation(side)
                + " | seed_iso=" + _iso[side] + " | current_iso=" + trim.IsoStatus
                + " | candidate_edge=" + edge.EdgeIndex + " | candidate_trim=" + trim.TrimIndex
                + " | candidate_face=" + trim.Face.FaceIndex + " | domain=" + Domain(edge.Domain)
                + " | native_start=" + Point(edge.PointAtStart) + " | native_end=" + Point(edge.PointAtEnd)
                + " | start_to_corners_0_1_2_3=[" + string.Join(",", startDistances.Select(NativeCompareProbeProtocol.Number)) + "]"
                + " | end_to_corners_0_1_2_3=[" + string.Join(",", endDistances.Select(NativeCompareProbeProtocol.Number)) + "]"
                + " | expected_corner_pair=" + expectedPair
                + " | attribution=CONDITIONAL_NATURAL_PARAMETER_SIDE | physical_correspondence=NOT_VERIFIED");
        }
    }
}
