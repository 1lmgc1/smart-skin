using System;
using System.Collections.Generic;
using System.Linq;
using Rhino;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeMatchBoundaryBinding
{
    internal readonly List<BrepEdge>[] Sides = { new(), new(), new(), new() };
    internal readonly int[] Corners = new int[4];
    internal static NativeMatchBoundaryBinding? Capture(Brep candidate, NativeCompareInput input)
    {
        if (candidate.Faces.Count != 1 || candidate.Loops.Count != 1 || candidate.Loops[0].LoopType != BrepLoopType.Outer) return null;
        var trims = candidate.Loops[0].Trims.ToArray();
        if (trims.Length < 4 || trims.Any(trim => trim.Edge is null || trim.Edge.Valence != EdgeAdjacency.Naked)) return null;
        var result = new NativeMatchBoundaryBinding();
        for (var side = 0; side < 4; side++)
        {
            var previous = input.Sides[(side + 3) % 4];
            var a = previous[previous.Count - 1].End; var b = input.Sides[side][0].Start;
            var matches = candidate.Vertices.Where(vertex => vertex.Location.DistanceTo(a) <= input.Tolerance
                && vertex.Location.DistanceTo(b) <= input.Tolerance).ToArray();
            if (matches.Length != 1) return null;
            result.Corners[side] = matches[0].VertexIndex;
        }
        if (result.Corners.Distinct().Count() != 4) return null;
        var starts = trims.Select(trim => trim.StartVertex.VertexIndex).ToArray();
        if (result.Corners.Any(corner => starts.Count(vertex => vertex == corner) != 1)) return null;
        var first = Array.IndexOf(starts, result.Corners[0]);
        var nextCorner = -1;
        for (var step = 1; step < trims.Length; step++)
        {
            var corner = Array.IndexOf(result.Corners, starts[(first + step) % trims.Length]);
            if (corner >= 0) { nextCorner = corner; break; }
        }
        if (nextCorner != 1 && nextCorner != 3) return null;
        var forward = nextCorner == 1;
        var seen = new HashSet<int>();
        for (var side = 0; side < 4; side++)
        {
            var at = Array.IndexOf(starts, result.Corners[side]);
            var end = Array.IndexOf(starts, result.Corners[(side + 1) % 4]);
            for (var steps = 0; at != end && steps < trims.Length; steps++)
            {
                var index = forward ? at : (at + trims.Length - 1) % trims.Length;
                var edge = trims[index].Edge;
                if (!seen.Add(edge.EdgeIndex)) return null;
                result.Sides[side].Add(edge);
                at = forward ? (at + 1) % trims.Length : (at + trims.Length - 1) % trims.Length;
                if (at != end && result.Corners.Contains(starts[at])) return null;
            }
            if (at != end || result.Sides[side].Count == 0) return null;
        }
        return seen.Count == candidate.Edges.Count ? result : null;
    }
}

internal sealed class NativeMatchPieceMetrics
{
    internal NativeCompareInput.Edge Source = null!;
    internal string Identity = string.Empty;
    internal int Side, SourceStations, CandidateStations, G0Failures, Unresolved, RequiredJets, PairedNormals, PairedJets, UpperPointExceptions, ResolvedSidedness, SidednessFailures;
    internal double MaximumGap = double.NaN, MaximumAngleRadians = double.NaN, MaximumW = double.NaN;
    internal double MinimumSignedNormalDot = 1, MaximumSignedNormalDot = -1, MaximumInwardDot = double.NaN;
    internal string WorstGap = "NONE", WorstAngle = "NONE", WorstW = "NONE", FirstFailure = "NONE";
    internal bool Resolved => SourceStations > 0 && CandidateStations > 0 && Unresolved == 0;
    internal bool G0 => NativeMatchMeasuredPiecePolicy.G0(SourceStations, CandidateStations, Unresolved, G0Failures);
    internal bool G1(double angle) => NativeMatchMeasuredPiecePolicy.G1(G0, RequiredJets, PairedNormals, MaximumAngleRadians, angle)
        && NativeMatchSidednessPolicy.Complete(RequiredJets, ResolvedSidedness, SidednessFailures);
    internal bool G2(double angle, double? limit) => NativeMatchMeasuredPiecePolicy.G2(G1(angle), RequiredJets, PairedJets, MaximumW, limit);
}

internal sealed class NativeMatchEvaluation
{
    internal NativeMatchState State = null!;
    internal NativeMatchBoundaryBinding? Binding;
    internal NativeMatchPieceMetrics[] Pieces = Array.Empty<NativeMatchPieceMetrics>();
    internal string Reason = "NOT_MEASURED";
}

internal sealed class NativeMatchBoundaryEvaluator
{
    private readonly NativeCompareInput _input;
    private readonly (NativeCompareInput.Edge Edge, double Parameter)[] _upper;
    private readonly Dictionary<(NativeCompareInput.Edge Edge, long Parameter), NativeCompareMeasure.SurfaceFrame?> _parentFrames = new();
    private static readonly double[] ZeroOperator = new double[9];
    private NativeMatchSidedness _sidedness = new();
    internal double MaximumParentCurvature { get; private set; }
    private readonly double[] _sideCurvature = new double[4];
    private readonly bool[] _sideCurvatureComplete = { true, true, true, true };
    internal bool ParentCurvatureComplete => _sideCurvatureComplete.All(value => value);
    internal double SideCurvature(int side) => _sideCurvature[side];
    internal bool SideCurvatureComplete(int side) => _sideCurvatureComplete[side];
    internal double? OperatorLimit { get; }
    internal string OperatorContract { get; }
    internal NativeMatchBoundaryEvaluator(NativeCompareInput input, Action checkpoint)
    {
        _input = input; _upper = NativeBuildCapQualification.UpperBindings(input).ToArray();
        try
        {
            var source = NativeSupportSource.Create(input, checkpoint);
            OperatorLimit = source.Policy?.OperatorTolerance;
            OperatorContract = source.ContractStatus;
        }
        catch (NativeCompareUnsupported error) { OperatorContract = error.Message; }
        // Fixed source-only cache and solver scale. Candidate projections never extend this cache.
        for (var side = 0; side < 4; side++)
            foreach (var edge in input.Sides[side])
            foreach (var parameter in NativeSeedJoinExperiment.Stations(edge.Native, edge.Features))
            {
                checkpoint(); if (IsUpper(edge, parameter)) continue;
                if (_parentFrames.Count >= 32768) throw new NativeCompareUnsupported("IMPROVE_SOURCE_FRAME_CACHE_LIMIT");
                var frame = NativeCompareMeasure.Frame(edge.Native, parameter, input.Tolerance, out var measured) ? measured : null;
                _parentFrames[(edge, BitConverter.DoubleToInt64Bits(parameter))] = frame;
                if (frame is null) { _sideCurvatureComplete[side] = false; continue; }
                var k = NativeCompareMath.OperatorSpectralResidual(frame.Operator, ZeroOperator, 1);
                if (!NativeCompareMath.Finite(k)) _sideCurvatureComplete[side] = false;
                else { MaximumParentCurvature = Math.Max(MaximumParentCurvature, k); _sideCurvature[side] = Math.Max(_sideCurvature[side], k); }
            }
    }
    internal NativeMatchEvaluation Evaluate(string stage, Brep candidate, Action checkpoint, Action<string> write)
    {
        var result = new NativeMatchEvaluation();
        _sidedness = new NativeMatchSidedness();
        var pieces = _input.Sides.SelectMany((side, index) => side.Select(source => new NativeMatchPieceMetrics
        { Source = source, Side = index, Identity = _input.Owners[source.OwnerIndex].Id.ToString("N") + ":" + source.Native.EdgeIndex
            + ":" + Number(source.Native.Domain.T0) + ":" + Number(source.Native.Domain.T1) })).ToArray();
        result.Pieces = pieces;
        var bounded = NativeCompareMeasure.Bounded(candidate, out var cp);
        result.Binding = bounded ? NativeMatchBoundaryBinding.Capture(candidate, _input) : null;
        if (result.Binding is null)
        {
            foreach (var piece in pieces) piece.Unresolved++;
            result.Reason = "UNRESOLVED_PHYSICAL_CORNER_OR_LOOP_BINDING";
        }
        else
        {
            result.Reason = "PHYSICAL_LOOP_BOUND_AND_MEASURED";
            for (var side = 0; side < 4; side++)
            {
                var originals = pieces.Where(piece => piece.Side == side).ToArray();
                var edges = result.Binding.Sides[side];
                var candidateParameters = edges.ToDictionary(edge => edge.EdgeIndex,
                    edge => new SortedSet<double>(NativeSeedJoinExperiment.Stations(edge, Array.Empty<double>())));
                foreach (var piece in originals)
                    foreach (var parameter in NativeSeedJoinExperiment.Stations(piece.Source.Native, piece.Source.Features))
                    {
                        checkpoint(); piece.SourceStations++;
                        var point = piece.Source.Native.PointAt(parameter);
                        var hits = Closest(point, edges, out var resolved);
                        if (!resolved) { Fail(piece, "SOURCE_TO_SIDE_UNRESOLVED", parameter); continue; }
                        foreach (var hit in hits)
                        {
                            var samples = candidateParameters[hit.Edge.EdgeIndex];
                            samples.Add(hit.Parameter);
                            var offset = Math.Abs(hit.Edge.Domain.Length) * 1e-8;
                            samples.Add(Math.Max(hit.Edge.Domain.T0, hit.Parameter - offset));
                            samples.Add(Math.Min(hit.Edge.Domain.T1, hit.Parameter + offset));
                            Record(piece, parameter, hit.Edge, hit.Parameter, hit.Gap,
                                IsUpper(piece.Source, parameter), "SOURCE_TO_SIDE", checkpoint);
                        }
                    }
                foreach (var edge in edges)
                    foreach (var parameter in candidateParameters[edge.EdgeIndex])
                    {
                        checkpoint();
                        var point = edge.PointAt(parameter);
                        var sourceHits = ClosestOriginal(point, originals, out var resolved);
                        if (!resolved)
                        { foreach (var piece in originals) Fail(piece, "SIDE_TO_SOURCE_UNRESOLVED", parameter); continue; }
                        foreach (var hit in sourceHits)
                        {
                            hit.Piece.CandidateStations++;
                            var exactCandidateEndpoint = parameter == edge.Domain.T0 || parameter == edge.Domain.T1;
                            var upper = exactCandidateEndpoint && IsUpper(hit.Piece.Source, hit.Parameter)
                                && _upper.Any(bound => bound.Edge.Native.PointAt(bound.Parameter).DistanceTo(point) <= Roundoff(point));
                            Record(hit.Piece, hit.Parameter, edge, parameter, hit.Gap, upper, "SIDE_TO_SOURCE", checkpoint);
                        }
                    }
            }
        }
        var face = candidate.Faces.Count == 1 ? candidate.Faces[0] : null;
        result.State = new NativeMatchState(pieces.Select(piece => new NativeMatchPieceState(piece.Identity, piece.Side, piece.Resolved,
            piece.G0, piece.G1(_input.AngleTolerance), piece.G2(_input.AngleTolerance, OperatorLimit))), cp,
            face?.Degree(0) ?? 0, face?.Degree(1) ?? 0);
        write("SMARTSKIN_NATIVE_IMPROVE_BINDING | stage=" + stage + " | status=" + result.Reason
            + " | physical_corner_vertices=" + (result.Binding is null ? "UNRESOLVED" : string.Join(",", result.Binding.Corners))
            + " | edges_per_logical_side=" + (result.Binding is null ? "UNRESOLVED" : string.Join(",", result.Binding.Sides.Select(side => side.Count)))
            + " | control_points=" + cp + " | endpoint_and_whole_locus_tests=REQUIRED | parameter_lineage_assumed=false");
        foreach (var piece in pieces)
            write("SMARTSKIN_NATIVE_IMPROVE_PIECE | stage=" + stage + " | source=" + piece.Identity + " | side=" + piece.Side
                + " | source_stations=" + piece.SourceStations + " | candidate_stations=" + piece.CandidateStations
                + " | unresolved=" + piece.Unresolved + " | G0_failures=" + piece.G0Failures + " | paired_normals=" + piece.PairedNormals + " | paired_required_jets=" + piece.PairedJets + "/" + piece.RequiredJets
                + " | resolved_required_sidedness=" + piece.ResolvedSidedness + "/" + piece.RequiredJets
                + " | sidedness_failures=" + piece.SidednessFailures + " | max_inward_conormal_dot=" + Metric(piece.MaximumInwardDot)
                + " | local_sidedness=EXACT_TRIM_LOOP_MATERIAL_SIDE | global_parent_collision=NOT_VERIFIED"
                + " | upper_point_exceptions=" + piece.UpperPointExceptions + " | G0=" + piece.G0 + " | G1=" + piece.G1(_input.AngleTolerance)
                + " | G2=" + piece.G2(_input.AngleTolerance, OperatorLimit) + " | max_gap=" + Metric(piece.MaximumGap)
                + " | max_angle_degrees=" + Metric(RhinoMath.ToDegrees(piece.MaximumAngleRadians)) + " | max_full_W=" + (piece.PairedJets > 0 ? Number(piece.MaximumW) : "NOT_MEASURED")
                + " | signed_normal_dot_range=" + (piece.PairedNormals > 0 ? Number(piece.MinimumSignedNormalDot) + ":" + Number(piece.MaximumSignedNormalDot) : "NOT_MEASURED")
                + " | worst_gap=" + piece.WorstGap + " | worst_angle=" + piece.WorstAngle + " | worst_W=" + piece.WorstW
                + " | first_failure=" + piece.FirstFailure + " | coverage=FINITE_SPANS_FEATURES_AND_APPROACHES | global_continuity=NOT_VERIFIED");
        return result;
    }
    private void Record(NativeMatchPieceMetrics piece, double sourceParameter, BrepEdge candidate, double candidateParameter,
        double gap, bool upper, string direction, Action checkpoint)
    {
        checkpoint(); var provenance = direction + ":t=" + Number(sourceParameter) + ":edge=" + candidate.EdgeIndex + ":candidate_t=" + Number(candidateParameter);
        if (NativeCompareMath.Finite(gap) && (!NativeCompareMath.Finite(piece.MaximumGap) || gap > piece.MaximumGap)) { piece.MaximumGap = gap; piece.WorstGap = provenance; }
        if (!NativeCompareMath.Finite(gap) || gap > _input.Tolerance)
        { piece.G0Failures++; if (piece.FirstFailure == "NONE") piece.FirstFailure = "G0:" + provenance; return; }
        if (upper) { piece.UpperPointExceptions++; return; }
        piece.RequiredJets++;
        var parentSide = _sidedness.Inward(piece.Source.Native, sourceParameter, _input.Tolerance,
            checkpoint, out var parentInward, out var parentSideReason);
        var candidateSide = _sidedness.Inward(candidate, candidateParameter, _input.Tolerance,
            checkpoint, out var candidateInward, out var candidateSideReason);
        if (parentSide && candidateSide)
        {
            var opposite = NativeMatchSidednessPolicy.Opposed(new[] { parentInward.X, parentInward.Y, parentInward.Z },
                new[] { candidateInward.X, candidateInward.Y, candidateInward.Z }, out var inwardDot);
            if (NativeCompareMath.Finite(inwardDot))
            {
                piece.ResolvedSidedness++;
                if (!NativeCompareMath.Finite(piece.MaximumInwardDot) || inwardDot > piece.MaximumInwardDot) piece.MaximumInwardDot = inwardDot;
            }
            if (!opposite) { piece.SidednessFailures++; if (piece.FirstFailure == "NONE") piece.FirstFailure = "SAME_OR_UNRESOLVED_OCCUPIED_SIDE:" + provenance; }
        }
        else if (piece.FirstFailure == "NONE") piece.FirstFailure = "SIDEDNESS:" + parentSideReason + ":" + candidateSideReason + ":" + provenance;
        var key = (piece.Source, BitConverter.DoubleToInt64Bits(sourceParameter));
        if (!_parentFrames.TryGetValue(key, out var parent))
            parent = NativeCompareMeasure.Frame(piece.Source.Native, sourceParameter, _input.Tolerance, out var frame) ? frame : null;
        var actual = NativeCompareMeasure.Frame(candidate, candidateParameter, _input.Tolerance, out var measured) ? measured : null;
        var parentNormal = parent?.Normal ?? TangentNormal(piece.Source.Native, sourceParameter, _input.Tolerance);
        var actualNormal = actual?.Normal ?? TangentNormal(candidate, candidateParameter, _input.Tolerance);
        if (!parentNormal.IsValid || !actualNormal.IsValid || !parentNormal.Unitize() || !actualNormal.Unitize())
        { if (piece.FirstFailure == "NONE") piece.FirstFailure = "NORMAL_FRAME:" + provenance; return; }
        var dot = Math.Max(-1, Math.Min(1, parentNormal * actualNormal));
        var angle = Math.Acos(Math.Abs(dot));
        if (!NativeCompareMath.Finite(angle)) return;
        piece.PairedNormals++;
        piece.MinimumSignedNormalDot = Math.Min(piece.MinimumSignedNormalDot, dot); piece.MaximumSignedNormalDot = Math.Max(piece.MaximumSignedNormalDot, dot);
        if (!NativeCompareMath.Finite(piece.MaximumAngleRadians) || angle > piece.MaximumAngleRadians) { piece.MaximumAngleRadians = angle; piece.WorstAngle = provenance; }
        if (parent is null || actual is null)
        { if (piece.FirstFailure == "NONE") piece.FirstFailure = "CURVATURE_FRAME:" + provenance; return; }
        var curvature = NativeCompareMath.OperatorSpectralResidual(parent.Operator, actual.Operator, dot < 0 ? -1 : 1);
        if (!NativeCompareMath.Finite(curvature)) return;
        piece.PairedJets++;
        if (!NativeCompareMath.Finite(piece.MaximumW) || curvature > piece.MaximumW) { piece.MaximumW = curvature; piece.WorstW = provenance; }
    }
    private static Vector3d TangentNormal(BrepEdge edge, double parameter, double tolerance)
    {
        var trims = edge.TrimIndices();
        if (trims.Length != 1) return Vector3d.Unset;
        var trim = edge.Brep.Trims[trims[0]]; var face = trim.Face;
        if (!trim.GetTrimParameter(parameter, out var t)) return Vector3d.Unset;
        var uv = trim.PointAt(t);
        if (!uv.IsValid || !face.Evaluate(uv.X, uv.Y, 1, out var point, out var derivatives)
            || !point.IsValid || !NativeCompareMath.Finite(point.DistanceTo(edge.PointAt(parameter)))
            || point.DistanceTo(edge.PointAt(parameter)) > tolerance || derivatives is null || derivatives.Length < 2
            || !derivatives[0].IsValid || !derivatives[1].IsValid) return Vector3d.Unset;
        var du = derivatives[0]; var dv = derivatives[1];
        if (!du.Unitize() || !dv.Unitize()) return Vector3d.Unset;
        var normal = Vector3d.CrossProduct(du, dv);
        if (!normal.Unitize()) return Vector3d.Unset;
        if (face.OrientationIsReversed) normal.Reverse();
        return normal;
    }
    private bool IsUpper(NativeCompareInput.Edge edge, double parameter) => _upper.Any(bound => ReferenceEquals(bound.Edge, edge) && bound.Parameter == parameter);
    private static void Fail(NativeMatchPieceMetrics piece, string reason, double parameter)
    { piece.Unresolved++; if (piece.FirstFailure == "NONE") piece.FirstFailure = reason + ":t=" + Number(parameter); }
    private readonly struct Hit
    {
        internal readonly BrepEdge Edge; internal readonly double Parameter, Gap;
        internal Hit(BrepEdge edge, double parameter, double gap) { Edge = edge; Parameter = parameter; Gap = gap; }
    }
    private static List<Hit> Closest(Point3d point, IEnumerable<BrepEdge> edges, out bool resolved)
    {
        var hits = new List<Hit>(); resolved = false;
        foreach (var edge in edges)
        {
            if (!edge.ClosestPoint(point, out var t)) return hits;
            var gap = edge.PointAt(t).DistanceTo(point);
            if (!NativeCompareMath.Finite(gap)) return hits;
            hits.Add(new Hit(edge, t, gap));
        }
        if (hits.Count == 0) return hits;
        hits.Sort((a, b) => a.Gap.CompareTo(b.Gap));
        var near = hits.Where(hit => hit.Gap - hits[0].Gap <= Roundoff(point)).ToList();
        if (near.Count > 1)
        {
            var vertices = near.Select(hit => VertexAt(hit.Edge, hit.Parameter, Roundoff(point))).ToArray();
            if (vertices.Any(vertex => vertex < 0) || vertices.Distinct().Count() != 1) return near;
        }
        resolved = true; return near;
    }
    private static List<(NativeMatchPieceMetrics Piece, double Parameter, double Gap)> ClosestOriginal(Point3d point,
        NativeMatchPieceMetrics[] pieces, out bool resolved)
    {
        var result = new List<(NativeMatchPieceMetrics, double, double)>(); resolved = false;
        var hits = new List<(int Member, double Parameter, double Gap)>();
        for (var i = 0; i < pieces.Length; i++)
        {
            var edge = pieces[i].Source.Native;
            if (!edge.ClosestPoint(point, out var parameter)) return result;
            var gap = edge.PointAt(parameter).DistanceTo(point);
            if (!NativeCompareMath.Finite(gap)) return result;
            hits.Add((i, parameter, gap));
        }
        if (hits.Count == 0) return result;
        var minimum = hits.Min(hit => hit.Gap);
        var near = hits.Where(hit => hit.Gap - minimum <= Roundoff(point)).OrderBy(hit => hit.Member).ToArray();
        if (near.Length > 1)
        {
            if (near.Length != 2 || near[1].Member != near[0].Member + 1) return result;
            var a = pieces[near[0].Member].Source; var b = pieces[near[1].Member].Source;
            if (a.Native.PointAt(near[0].Parameter).DistanceTo(a.End) > Roundoff(point)
                || b.Native.PointAt(near[1].Parameter).DistanceTo(b.Start) > Roundoff(point)) return result;
        }
        foreach (var hit in near) result.Add((pieces[hit.Member], hit.Parameter, hit.Gap));
        resolved = true; return result;
    }
    private static int VertexAt(BrepEdge edge, double parameter, double tolerance)
    {
        var point = edge.PointAt(parameter); var a = point.DistanceTo(edge.PointAtStart) <= tolerance; var b = point.DistanceTo(edge.PointAtEnd) <= tolerance;
        return a != b ? (a ? edge.StartVertex.VertexIndex : edge.EndVertex.VertexIndex) : -1;
    }
    private static double Roundoff(Point3d point) => 64 * 2.2204460492503131e-16 * Math.Max(1, Math.Max(Math.Abs(point.X), Math.Max(Math.Abs(point.Y), Math.Abs(point.Z))));
    private static string Metric(double value) => NativeCompareMath.Finite(value) ? Number(value) : "NOT_MEASURED";
    private static string Number(double value) => NativeCompareProbeProtocol.Number(value);
}
