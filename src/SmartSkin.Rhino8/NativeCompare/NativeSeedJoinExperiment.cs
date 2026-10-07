using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeSeedJoinResult : IDisposable
{
    internal bool ProvenanceResolved;
    internal bool SelectedOpeningJoined;
    internal bool TemporariesDisposed;
    internal string Status = "JOIN_NOT_COMPLETED";
    internal Brep? Cap;
    public void Dispose() { Cap?.Dispose(); Cap = null; }
}

internal static class NativeSeedJoinExperiment
{
    private const int MaximumFaces = 256;
    private const int MaximumEdges = 2048;
    private sealed class FaceOrigin
    {
        internal Guid Tag;
        internal int Input;
        internal int Face;
        internal string SurfaceArchive = string.Empty;
        internal Interval U, V;
    }
    private sealed class OutputEdge
    {
        internal int Output;
        internal BrepEdge Edge = null!;
        internal FaceOrigin[] Faces = Array.Empty<FaceOrigin>();
        internal bool HasSeed => Faces.Any(face => face.Input == 0);
    }

    internal static NativeSeedJoinResult Run(Brep seed, NativeCompareInput input, List<NativeCompareCandidate>? previews,
        Action checkpoint, Action<string> write)
    {
        var result = new NativeSeedJoinResult();
        var copies = new List<Brep>();
        Brep[]? joined = null;
        var seedArchive = input.GeometryFingerprint(seed);
        try
        {
            checkpoint();
            if (1 + input.Owners.Sum(owner => owner.Copy.Faces.Count) > MaximumFaces
                || seed.Edges.Count + input.Owners.Sum(owner => owner.Copy.Edges.Count) > MaximumEdges)
                throw new NativeCompareUnsupported("JOIN_INPUT_COMPLEXITY_LIMIT");
            var origins = new Dictionary<Guid, FaceOrigin>();
            AddCopy(seed, 0, copies, origins, input);
            for (var owner = 0; owner < input.Owners.Count; owner++)
                AddCopy(input.Owners[owner].Copy, owner + 1, copies, origins, input);
            var freshArchives = copies.Select(input.GeometryFingerprint).ToArray();
            var selectedKeys = new HashSet<string>(input.Edges.Select(edge => edge.OwnerIndex + ":" + edge.Native.EdgeIndex));
            var unselectedOriginalNaked = input.Owners.SelectMany((owner, i) => owner.Copy.Edges
                .Where(edge => edge.Valence == EdgeAdjacency.Naked && !selectedKeys.Contains(i + ":" + edge.EdgeIndex))).Count();
            write("SMARTSKIN_NATIVE_JOIN_START | candidate=EdgeSrf:Seed | inputs=" + copies.Count
                + " | input0=FRESH_SEED_COPY | other_inputs=FRESH_FULL_OWNER_COPIES | selected_source_pieces=" + input.Edges.Count
                + " | original_unselected_owner_naked_edges=" + unselectedOriginalNaked
                + " | tolerance=" + Number(input.Tolerance) + " | angle_tolerance_radians=" + Number(input.AngleTolerance)
                + " | max_join_calls=1 | forced_join=false | face_tags=FRESH_COPIES_ONLY | tag_propagation=TO_BE_MEASURED");
            checkpoint();
            var native = Stopwatch.StartNew();
            joined = Brep.JoinBreps(copies, input.Tolerance, input.AngleTolerance, out var indexMap);
            var nativeMilliseconds = native.ElapsedMilliseconds;
            write("SMARTSKIN_NATIVE_JOIN_RETURN | native_ms=" + nativeMilliseconds
                + " | output_count=" + (joined?.Length ?? 0) + " | contributor_map="
                + (indexMap is null ? "NULL" : string.Join(";", indexMap.Select((indices, i) => i + ":[" + (indices is null ? "NULL" : string.Join(",", indices)) + "]")))
                + " | topology_does_not_verify_G1_G2=true");
            var freshUnchanged = copies.Select((copy, i) => input.GeometryFingerprint(copy) == freshArchives[i]).All(equal => equal);
            var capturedUnchanged = input.CopiesUnchanged();
            var seedUnchanged = input.GeometryFingerprint(seed) == seedArchive;
            write("SMARTSKIN_NATIVE_JOIN_GUARD | fresh_join_inputs_unchanged=" + freshUnchanged
                + " | captured_owners_unchanged=" + capturedUnchanged + " | raw_seed_unchanged=" + seedUnchanged);
            if (!freshUnchanged || !capturedUnchanged || !seedUnchanged)
                throw new InvalidOperationException("JOIN_INPUT_ARCHIVE_CHANGED");
            checkpoint();
            if (joined is null || joined.Length == 0) throw new NativeCompareUnsupported("NATIVE_JOIN_NO_OUTPUT");
            if (joined.Length > copies.Count || joined.Sum(brep => brep.Faces.Count) > MaximumFaces
                || joined.Sum(brep => brep.Edges.Count) > MaximumEdges)
                throw new NativeCompareUnsupported("JOIN_OUTPUT_COMPLEXITY_LIMIT");
            for (var i = 0; i < joined.Length; i++)
                write("SMARTSKIN_NATIVE_JOIN_OUTPUT | output=" + i + " | valid=" + joined[i].IsValid
                    + " | faces=" + joined[i].Faces.Count + " | edges=" + joined[i].Edges.Count
                    + " | solid=" + joined[i].IsSolid + " | manifold=" + joined[i].IsManifold
                    + " | naked_edges=" + joined[i].Edges.Count(edge => edge.Valence == EdgeAdjacency.Naked)
                    + " | nonmanifold_edges=" + joined[i].Edges.Count(edge => edge.Valence == EdgeAdjacency.NonManifold));
            result.ProvenanceResolved = ResolveFaces(joined, indexMap, origins, copies.Count, input, checkpoint, write);
            if (!result.ProvenanceResolved)
            {
                write("SMARTSKIN_NATIVE_JOIN_RESULT | selected_opening=NOT_VERIFIED | reason=FACE_PROVENANCE_UNRESOLVED"
                    + " | native_topology_reported=true | global_G1_G2=NOT_VERIFIED | join_probe_document_additions=0");
                result.Status = "FACE_PROVENANCE_UNRESOLVED";
                return result;
            }
            var edges = joined.SelectMany((brep, i) => brep.Edges.Select(edge => new OutputEdge
            {
                Output = i, Edge = edge,
                Faces = edge.AdjacentFaces().Distinct().Select(face => origins[brep.Faces[face].Id]).ToArray(),
            })).ToArray();
            result.SelectedOpeningJoined = Measure(input, joined, edges, unselectedOriginalNaked, checkpoint, write);
            result.Status = result.SelectedOpeningJoined ? "SAMPLED_SELECTED_SEAMS_JOINED" : "SELECTED_SEAMS_NOT_VERIFIED";
            // Preview only the joined seed face; the actual full owner copies are never overdrawn.
            var seedFace = joined.SelectMany(brep => brep.Faces).Single(face => origins[face.Id].Input == 0);
            if (seedFace.Brep.IsValid)
            {
                result.Cap = seedFace.DuplicateFace(false);
                if (previews is not null)
                {
                var preview = result.Cap.DuplicateBrep();
                try
                {
                    previews.Add(new NativeCompareCandidate("EdgeSrf:JoinedSeedFaceCopy:POSITION_PREVIEW:G1_G2_NOT_VERIFIED", preview));
                    preview = null!;
                    write("SMARTSKIN_NATIVE_JOIN_PREVIEW | candidate=EdgeSrf:JoinedSeedFaceCopy | geometry=JOINED_SEED_DUPLICATE_FACE"
                        + " | full_joined_assembly_shown=false | paired_topology_in_report_only=true | G1_G2=NOT_VERIFIED");
                }
                finally { preview?.Dispose(); }
                }
            }
        }
        catch (NativeCompareUnsupported exception)
        {
            result.Status = exception.Message;
            write("SMARTSKIN_NATIVE_JOIN_RESULT | selected_opening=NOT_VERIFIED | reason=" + exception.Message + " | G1_G2=NOT_VERIFIED");
        }
        catch { result.Dispose(); throw; }
        finally
        {
            var failures = new List<string>();
            if (joined is not null)
                for (var i = 0; i < joined.Length; i++)
                    NativeCompareReportCleanup.Attempt("join_output_" + i, joined[i].Dispose, failures);
            for (var i = 0; i < copies.Count; i++)
                NativeCompareReportCleanup.Attempt("join_input_" + i, copies[i].Dispose, failures);
            result.TemporariesDisposed = failures.Count == 0;
            // Reserved terminal sink path, including when an earlier ordinary report entry overflowed.
            write(NativeCompareReportBuffer.CleanupPrefix + " stage=JOIN_TEMPORARIES | all_join_temporaries_disposed=" + (failures.Count == 0)
                + " | cleanup_failures=" + (failures.Count == 0 ? "NONE" : string.Join(",", failures)));

        }
        return result;
    }

    private static void AddCopy(Brep original, int index, List<Brep> copies, Dictionary<Guid, FaceOrigin> origins, NativeCompareInput input)
    {
        var copy = original.DuplicateBrep();
        try
        {
            if (copy is null || !copy.IsValid) throw new NativeCompareUnsupported("JOIN_COPY_FAILED");
            foreach (var face in copy.Faces)
            {
                var tag = Guid.NewGuid(); face.Id = tag;
                origins.Add(tag, new FaceOrigin { Tag = tag, Input = index, Face = face.FaceIndex,
                    SurfaceArchive = input.GeometryFingerprint(face.UnderlyingSurface()), U = face.Domain(0), V = face.Domain(1) });
            }
            copies.Add(copy); copy = null!;
        }
        finally { copy?.Dispose(); }
    }

    private static bool ResolveFaces(Brep[] outputs, List<int[]>? indexMap, Dictionary<Guid, FaceOrigin> origins,
        int inputCount, NativeCompareInput input, Action checkpoint, Action<string> write)
    {
        var seen = new HashSet<Guid>();
        var evidence = new List<IReadOnlyList<NativeSeedJoinPolicy.FaceEvidence>>();
        for (var i = 0; i < outputs.Length; i++)
        {
            var faces = new List<NativeSeedJoinPolicy.FaceEvidence>();
            foreach (var face in outputs[i].Faces)
            {
                checkpoint();
                var known = origins.TryGetValue(face.Id, out var origin);
                var unique = seen.Add(face.Id);
                var geometry = known && face.Domain(0) == origin!.U && face.Domain(1) == origin.V
                    && input.GeometryFingerprint(face.UnderlyingSurface()) == origin.SurfaceArchive;
                faces.Add(new NativeSeedJoinPolicy.FaceEvidence(face.Id, geometry));
                write("SMARTSKIN_NATIVE_JOIN_FACE | output=" + i + " | face=" + face.FaceIndex
                    + " | input=" + (known ? origin!.Input.ToString() : "UNRESOLVED")
                    + " | original_face=" + (known ? origin!.Face.ToString() : "UNRESOLVED")
                    + " | unique_tag=" + unique + " | unchanged_surface_and_domain=" + geometry
                    + " | orientation_reversed=" + face.OrientationIsReversed);
            }
            evidence.Add(faces);
        }
        var resolved = NativeSeedJoinPolicy.ResolveFaceProvenance(origins.ToDictionary(pair => pair.Key, pair => pair.Value.Input),
            evidence, indexMap, inputCount, out var contributors);
        for (var i = 0; i < outputs.Length; i++)
        {
            var agrees = indexMap is not null && indexMap.Count > i
                && NativeSeedJoinPolicy.ContributorsAgree(indexMap[i], contributors[i], inputCount);
            write("SMARTSKIN_NATIVE_JOIN_PROVENANCE | output=" + i
                + " | contributor_map=" + (indexMap is null ? "ABSENT" : "SUPPLIED")
                + " | contributor_source=" + (indexMap is null ? "TAG_DERIVED" : "TAG_DERIVED_WITH_NATIVE_MAP_CHECK")
                + " | tag_derived_contributors=[" + string.Join(",", contributors[i]) + "]"
                + " | contributor_map_agrees=" + (indexMap is null ? "NOT_AVAILABLE" : agrees.ToString()));
        }
        write("SMARTSKIN_NATIVE_JOIN_PROVENANCE | all_faces=" + (resolved ? "VERIFIED_TAG_AND_SURFACE_ARCHIVE" : "NOT_VERIFIED")
            + " | input_faces=" + origins.Count + " | distinct_output_tags=" + seen.Count
            + " | optional_native_map=" + (indexMap is null ? "ABSENT_TAG_EVIDENCE_REQUIRED" : "SUPPLIED_MUST_AGREE"));
        return resolved;
    }

    private static bool Measure(NativeCompareInput input, Brep[] outputs, OutputEdge[] edges, int originalUnselectedNaked,
        Action checkpoint, Action<string> write)
    {
        var passedPieces = 0; var unresolvedTotal = 0;
        foreach (var source in input.Edges)
        {
            var expectedFace = NativeCompareMeasure.Face(source.Native)!;
            var parentEdges = edges.Where(edge => edge.Faces.Any(face => face.Input == source.OwnerIndex + 1
                && face.Face == expectedFace.FaceIndex)).ToArray();
            var matching = parentEdges.Where(edge => Ordinary(edge, source.OwnerIndex + 1, expectedFace.FaceIndex)).ToArray();
            var expected = 0; var located = 0; var unresolved = 0; var gapMaximum = 0.0; var gapMeasured = false;
            var touched = new HashSet<OutputEdge>();
            foreach (var parameter in Stations(source.Native, source.Features))
            {
                checkpoint(); expected++;
                var point = source.Native.PointAt(parameter);
                var hits = Locate(point, matching, input.Tolerance, out var gap);
                if (NativeCompareMath.Finite(gap)) { gapMeasured = true; gapMaximum = Math.Max(gapMaximum, gap); }
                if (hits.Count == 0) { unresolved++; continue; }
                // A coincident naked/unrelated edge on the expected owner face must not be hidden by
                // selecting only the successfully paired edge. Shared native vertices are legitimate.
                var parentHits = Locate(point, parentEdges, input.Tolerance, out _);
                var locations = parentHits.Select(hit => (hit.Output, EndpointVertex(hit.Edge, point, input.Tolerance))).ToArray();
                if (!NativeSeedJoinPolicy.OneTopologicalLocation(locations)) { unresolved++; continue; }
                located++; foreach (var hit in hits) touched.Add(hit);
            }
            var passed = expected > 0 && located == expected && unresolved == 0;
            if (passed) passedPieces++;
            unresolvedTotal += unresolved;
            var overlapping = edges.Where(edge => edge.HasSeed || edge.Faces.Any(face => face.Input == source.OwnerIndex + 1 && face.Face == expectedFace.FaceIndex))
                .Where(edge => OverlapsInterior(source.Native, edge.Edge, input.Tolerance, checkpoint)).ToArray();
            write("SMARTSKIN_NATIVE_JOIN_SELECTED | source=" + source.Label + " | owner_id=" + input.Owners[source.OwnerIndex].Id
                + " | parent_face=" + expectedFace.FaceIndex + " | original_native_edge_tolerance=" + Number(source.Native.Tolerance) + " | original_domain=" + Number(source.Native.Domain.T0) + "," + Number(source.Native.Domain.T1)
                + " | expected_stations=" + expected + " | ordinary_paired_stations=" + located + " | unresolved_stations=" + unresolved
                + " | fully_sampled_source_covered=" + passed + " | max_source_to_seam_gap=" + (!gapMeasured ? "NOT_MEASURED" : Number(gapMaximum))
                + " | ordinary_output_edges=" + string.Join(",", touched.Select(edge => edge.Output + ":" + edge.Edge.EdgeIndex))
                + " | overlapping_naked=" + overlapping.Count(edge => edge.Edge.Valence == EdgeAdjacency.Naked)
                + " | overlapping_nonmanifold=" + overlapping.Count(edge => edge.Edge.Valence == EdgeAdjacency.NonManifold));
        }
        var seedEdges = edges.Where(edge => edge.HasSeed).ToArray();
        var passedSeedEdges = 0;
        foreach (var edge in seedEdges)
        {
            checkpoint();
            var parents = edge.Faces.Where(face => face.Input != 0).ToArray();
            var ordinary = parents.Length == 1 && Ordinary(edge, parents[0].Input, parents[0].Face);
            var sources = ordinary ? input.Edges.Where(source => source.OwnerIndex + 1 == parents[0].Input
                && NativeCompareMeasure.Face(source.Native)!.FaceIndex == parents[0].Face).ToArray() : Array.Empty<NativeCompareInput.Edge>();
            var expected = 0; var covered = 0; var maximumGap = 0.0; var gapMeasured = false;
            foreach (var parameter in Stations(edge.Edge, Array.Empty<double>()))
            {
                checkpoint(); expected++;
                var point = edge.Edge.PointAt(parameter);
                var gap = Closest(point, sources.Select(source => source.Native));
                if (NativeCompareMath.Finite(gap)) { gapMeasured = true; maximumGap = Math.Max(maximumGap, gap); }
                if (gap <= input.Tolerance && UniqueOriginalLocation(point, sources, input.Tolerance)) covered++;
            }
            if (ordinary && expected > 0 && expected == covered) passedSeedEdges++;
            write("SMARTSKIN_NATIVE_JOIN_SEED_BOUNDARY | output=" + edge.Output + " | edge=" + edge.Edge.EdgeIndex
                + " | valence=" + edge.Edge.Valence + " | trim_count=" + edge.Edge.TrimIndices().Length
                + " | ordinary_seed_parent_pair=" + ordinary + " | expected_stations=" + expected + " | original_locus_stations=" + covered
                + " | max_seam_to_original_gap=" + (!gapMeasured ? "NOT_MEASURED" : Number(maximumGap))
                + " | native_edge_tolerance=" + Number(edge.Edge.Tolerance));
        }
        var seedNaked = seedEdges.Count(edge => edge.Edge.Valence == EdgeAdjacency.Naked);
        var seedNonManifold = seedEdges.Count(edge => edge.Edge.Valence == EdgeAdjacency.NonManifold);
        var parentNaked = edges.Where(edge => !edge.HasSeed && edge.Edge.Valence == EdgeAdjacency.Naked).ToArray();
        var selectedOverlap = parentNaked.Count(edge => input.Edges.Any(source => edge.Faces.Any(face => face.Input == source.OwnerIndex + 1
            && face.Face == NativeCompareMeasure.Face(source.Native)!.FaceIndex)
            && OverlapsInterior(source.Native, edge.Edge, input.Tolerance, checkpoint)));
        var openingPassed = NativeSeedJoinPolicy.SampledSelectedOpeningJoined(outputs.All(brep => brep.IsValid), true,
            input.Edges.Count, passedPieces, seedEdges.Length, passedSeedEdges, seedNaked, seedNonManifold, selectedOverlap, unresolvedTotal);
        write("SMARTSKIN_NATIVE_JOIN_RESULT | selected_opening=" + (openingPassed ? "SAMPLED_POSITION_AND_ORDINARY_PAIRED_TOPOLOGY" : "NOT_VERIFIED")
            + " | completely_sampled_source_pieces=" + passedPieces + "/" + input.Edges.Count
            + " | completely_sampled_seed_boundary_edges=" + passedSeedEdges + "/" + seedEdges.Length
            + " | remaining_seed_naked_edges=" + seedNaked + " | seed_nonmanifold_edges=" + seedNonManifold
            + " | parent_naked_with_selected_interior_overlap=" + selectedOverlap
            + " | original_unselected_owner_naked_edges=" + originalUnselectedNaked
            + " | other_parent_naked_edges_without_sampled_selected_overlap=" + (parentNaked.Length - selectedOverlap)
            + " | whole_result_may_remain_open=true | coverage=BOUNDED_SPAN_FEATURE_AND_ENDPOINT_STATIONS"
            + " | exact_continuous_locus=NOT_VERIFIED | full_joined_parent_trim_regions=NOT_VERIFIED | G1_G2=NOT_VERIFIED | join_probe_document_additions=0");
        return openingPassed;
    }

    private static bool Ordinary(OutputEdge edge, int parentInput, int parentFace)
    {
        var trims = edge.Edge.TrimIndices();
        return NativeSeedJoinPolicy.OrdinarySelectedSeam(edge.Edge.Valence == EdgeAdjacency.Interior, trims.Length,
            trims.All(index => edge.Edge.Brep.Trims[index].TrimType == BrepTrimType.Mated), edge.Faces.Length,
            edge.HasSeed, edge.Faces.Any(face => face.Input == parentInput && face.Face == parentFace), true);
    }
    private static List<OutputEdge> Locate(Point3d point, IEnumerable<OutputEdge> edges, double tolerance, out double gap)
    {
        var hits = new List<OutputEdge>(); gap = double.PositiveInfinity;
        foreach (var edge in edges)
        {
            if (!edge.Edge.ClosestPoint(point, out var parameter)) continue;
            var distance = edge.Edge.PointAt(parameter).DistanceTo(point);
            if (!NativeCompareMath.Finite(distance)) continue;
            gap = Math.Min(gap, distance);
            if (distance <= tolerance) hits.Add(edge);
        }
        return hits;
    }
    private static int EndpointVertex(BrepEdge edge, Point3d point, double tolerance)
    {
        var start = point.DistanceTo(edge.PointAtStart) <= tolerance;
        var end = point.DistanceTo(edge.PointAtEnd) <= tolerance;
        if (start == end) return -1;
        return start ? edge.StartVertex.VertexIndex : edge.EndVertex.VertexIndex;
    }
    private static bool UniqueOriginalLocation(Point3d point, IReadOnlyList<NativeCompareInput.Edge> sources, double tolerance)
    {
        var hits = new List<(int Output, int Vertex)>();
        foreach (var source in sources)
            if (source.Native.ClosestPoint(point, out var parameter) && source.Native.PointAt(parameter).DistanceTo(point) <= tolerance)
                hits.Add((source.OwnerIndex, EndpointVertex(source.Native, point, tolerance)));
        return NativeSeedJoinPolicy.OneTopologicalLocation(hits);
    }
    private static bool OverlapsInterior(Curve source, Curve candidate, double tolerance, Action checkpoint)
    {
        // Interior stations only: a single shared corner must not classify an unrelated opening edge.
        foreach (var fraction in new[] { .125, .25, .5, .75, .875 })
        {
            checkpoint();
            if (!source.NormalizedLengthParameter(fraction, out var parameter)) continue;
            var point = source.PointAt(parameter);
            if (candidate.ClosestPoint(point, out var target) && candidate.PointAt(target).DistanceTo(point) <= tolerance) return true;
        }
        return false;
    }
    private static double Closest(Point3d point, IEnumerable<BrepEdge> edges)
    {
        var gap = double.PositiveInfinity;
        foreach (var edge in edges)
            if (edge.ClosestPoint(point, out var parameter)) gap = Math.Min(gap, point.DistanceTo(edge.PointAt(parameter)));
        return gap;
    }
    internal static IEnumerable<double> Stations(Curve curve, IEnumerable<double> features)
    {
        if (curve.SpanCount < 1 || curve.SpanCount > 512) throw new NativeCompareUnsupported("JOIN_STATION_SPAN_LIMIT");
        var result = new SortedSet<double>();
        for (var span = 0; span < curve.SpanCount; span++)
        {
            var domain = curve.SpanDomain(span);
            var a = Math.Max(domain.T0, curve.Domain.T0); var b = Math.Min(domain.T1, curve.Domain.T1);
            if (b <= a) continue;
            foreach (var fraction in new[] { 0.0, 1e-7, 1e-5, .125, .25, .5, .75, .875, 1 - 1e-5, 1 - 1e-7, 1.0 })
                result.Add(a + (b - a) * fraction);
        }
        foreach (var feature in features)
            foreach (var offset in new[] { -1e-8, 0.0, 1e-8 })
                result.Add(Math.Max(curve.Domain.T0, Math.Min(curve.Domain.T1, feature + curve.Domain.Length * offset)));
        if (result.Count == 0 || result.Count > 8192) throw new NativeCompareUnsupported("JOIN_STATION_BUDGET");
        return result;
    }
    private static string Number(double value) => NativeCompareProbeProtocol.Number(value);
}
