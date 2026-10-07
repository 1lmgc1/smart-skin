using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Rhino;
using Rhino.DocObjects;
using Rhino.FileIO;
using Rhino.Geometry;
using Rhino.Input.Custom;

namespace SmartSkin.Rhino8;

// Experimental, copy-only native operator diagnostic. No coordinates or fixtures are embedded.
internal sealed class NativeCompareInput : IDisposable
{
    internal sealed class Owner
    {
        internal Guid Id;
        internal uint Serial;
        internal string Fingerprint = string.Empty;
        internal string CopyFingerprint = string.Empty;
        internal Brep Copy = null!;
    }
    internal sealed class Edge
    {
        internal int OwnerIndex;
        internal BrepEdge Native = null!;
        internal bool Reverse;
        internal readonly List<double> Features = new();
        internal Point3d Start => Reverse ? Native.PointAtEnd : Native.PointAtStart;
        internal Point3d End => Reverse ? Native.PointAtStart : Native.PointAtEnd;
        internal Vector3d Tangent(bool end)
        {
            var t = Native.TangentAt((end != Reverse) ? Native.Domain.T1 : Native.Domain.T0);
            if (Reverse) t.Reverse();
            return t;
        }
        internal double Parameter(bool end) => (end != Reverse) ? Native.Domain.T1 : Native.Domain.T0;
        internal string Label => "owner" + OwnerIndex + ":edge" + Native.EdgeIndex;
    }
    internal readonly List<Owner> Owners = new();
    internal readonly List<Edge> Edges = new();
    internal readonly List<List<Edge>> Sides = new();
    internal double Tolerance;
    internal double AngleTolerance;
    internal string Derivation = "PHYSICAL_G2_BREAKPOINTS";
    private uint _documentSerial;
    private double _loopLength;
    private readonly SerializationOptions _serialization = new()
    {
        WriteUserData = true, WriteRenderMeshes = false, WriteAnalysisMeshes = false,
    };

    internal static NativeCompareInput Capture(RhinoDoc doc, GetObject selection, Action checkpoint)
    {
        var result = new NativeCompareInput
        {
            Tolerance = doc.ModelAbsoluteTolerance,
            AngleTolerance = doc.ModelAngleToleranceRadians,
            _documentSerial = doc.RuntimeSerialNumber,
        };
        try
        {
            var seen = new HashSet<string>();
            long sourceBytes = 0;
            for (var i = 0; i < selection.ObjectCount; i++)
            {
                checkpoint();
                var reference = selection.Object(i);
                var original = reference.Edge();
                var obj = reference.Object();
                var brep = reference.Brep();
                if (original is null || obj is null || brep is null || original.Valence != EdgeAdjacency.Naked
                    || NativeCompareMeasure.Face(original) is null)
                    throw new NativeCompareUnsupported("UNSUPPORTED_NATIVE_NAKED_EDGE_OWNERSHIP");
                if (!(obj.Geometry is Brep directOwner) || original.EdgeIndex < 0 || original.EdgeIndex >= directOwner.Edges.Count)
                    throw new NativeCompareUnsupported("UNSUPPORTED_INDIRECT_OR_CONVERTED_SOURCE_OWNER");
                var directEdge = directOwner.Edges[original.EdgeIndex];
                if (directEdge.Domain != original.Domain
                    || directEdge.PointAtStart.DistanceTo(original.PointAtStart) > result.Tolerance
                    || directEdge.PointAtEnd.DistanceTo(original.PointAtEnd) > result.Tolerance)
                    throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_COMPONENT_PROVENANCE");
                brep = directOwner;
                if (!seen.Add(obj.Id + ":" + original.EdgeIndex))
                    throw new NativeCompareUnsupported("UNSUPPORTED_DUPLICATE_SELECTED_EDGE");
                var owner = result.Owners.FindIndex(o => o.Id == obj.Id);
                if (owner < 0)
                {
                    var bytes = (long)obj.MemoryEstimate();
                    sourceBytes += bytes;
                    if (bytes > 32 * 1024 * 1024 || sourceBytes > 64 * 1024 * 1024)
                        throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_MEMORY_BUDGET");
                    if (brep.Faces.Count > 128 || brep.Edges.Count > 512 || !brep.IsValid)
                        throw new NativeCompareUnsupported("UNSUPPORTED_OWNER_COMPLEXITY_OR_VALIDITY");
                    // Prepare disposable caches before serializing, matching the F6 snapshot lifecycle.
                    var copy = brep.DuplicateBrep();
                    var ownershipTransferred = false;
                    try
                    {
                        if (copy is null || !copy.IsValid)
                            throw new NativeCompareUnsupported("UNSUPPORTED_OWNER_COPY");
                        copy.GetBoundingBox(false);
                        _ = copy.IsSolid;
                        result.Owners.Add(new Owner { Id = obj.Id, Serial = obj.RuntimeSerialNumber,
                            Copy = copy, Fingerprint = result.Fingerprint(obj), CopyFingerprint = result.GeometryFingerprint(copy) });
                        ownershipTransferred = true;
                    }
                    finally
                    {
                        if (!ownershipTransferred) copy?.Dispose();
                    }
                    owner = result.Owners.Count - 1;
                }
                var edge = result.Owners[owner].Copy.Edges[original.EdgeIndex];
                if (!edge.IsValid || edge.GetLength() <= result.Tolerance)
                    throw new NativeCompareUnsupported("UNSUPPORTED_DEGENERATE_EDGE");
                using (var surface = NativeCompareMeasure.Face(edge)!.ToNurbsSurface())
                    if (surface is null || surface.Points.CountU * (long)surface.Points.CountV > 8192)
                        throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_FACE_COMPLEXITY");
                using (var curve = edge.ToNurbsCurve())
                    if (curve is null || curve.Points.Count > 512)
                        throw new NativeCompareUnsupported("UNSUPPORTED_SOURCE_CURVE_COMPLEXITY");
                // True within-chain geometric events are retained, not promoted into new cell sides
                // or hard-point exceptions. Knot insertion alone does not add a G1 discontinuity.
                var capturedEdge = new Edge { OwnerIndex = owner, Native = edge };
                var cursor = edge.Domain.T0;
                while (edge.GetNextDiscontinuity(Continuity.G1_continuous, cursor, edge.Domain.T1,
                    Math.Cos(1e-5), 1e-12, out var feature))
                {
                    checkpoint();
                    if (!NativeCompareMath.Finite(feature) || feature <= cursor || feature >= edge.Domain.T1)
                        throw new NativeCompareUnsupported("UNSUPPORTED_DISCONTINUITY_ENUMERATION");
                    capturedEdge.Features.Add(feature);
                    if (capturedEdge.Features.Count > 16) throw new NativeCompareUnsupported("UNSUPPORTED_GEOMETRIC_FEATURE_BUDGET");
                    cursor = feature;
                }
                result.Edges.Add(capturedEdge);
            }
            result.OrderAndPartition();
            if (!result.SourcesUnchanged(doc)) throw new NativeCompareUnsupported("SOURCE_CHANGED_DURING_CAPTURE");
            return result;
        }
        catch { result.Dispose(); throw; }
    }

    private void OrderAndPartition()
    {
        // Endpoints must have exactly one partner. No greedy joining and no tolerance-chain clusters.
        var partner = new int[Edges.Count * 2];
        var positions = Edges.SelectMany(e => new[] { e.Native.PointAtStart, e.Native.PointAtEnd }).ToArray();
        for (var i = 0; i < positions.Length; i++)
        {
            var matches = Enumerable.Range(0, positions.Length)
                .Where(j => j / 2 != i / 2 && positions[i].DistanceTo(positions[j]) <= Tolerance).ToArray();
            if (matches.Length != 1) throw new NativeCompareUnsupported("UNSUPPORTED_AMBIGUOUS_OR_OPEN_LOOP");
            partner[i] = matches[0];
        }
        var ordered = new List<Edge>();
        var visited = new HashSet<int>();
        var currentStart = 0;
        do
        {
            var index = currentStart / 2;
            if (!visited.Add(index)) throw new NativeCompareUnsupported("UNSUPPORTED_MULTIPLE_LOOPS");
            var edge = Edges[index];
            edge.Reverse = (currentStart % 2) != 0;
            ordered.Add(edge);
            currentStart = partner[currentStart ^ 1];
        } while (currentStart != 0);
        if (visited.Count != Edges.Count) throw new NativeCompareUnsupported("UNSUPPORTED_MULTIPLE_LOOPS");

        _loopLength = ordered.Sum(e => e.Native.GetLength());
        if (TryParentBranchPartition(ordered))
        {
            CanonicalizeSides();
            return;
        }
        var corners = new List<int>();
        for (var i = 0; i < ordered.Count; i++)
            if (!SmoothContinuation(ordered[(i + ordered.Count - 1) % ordered.Count], ordered[i])) corners.Add(i);
        if (corners.Count != 4)
            throw new NativeCompareUnsupported("UNSUPPORTED_FOUR_CHAIN_CELL_REQUIRED;geometric_breaks=" + corners.Count);
        // Canonical corner and traversal depend on geometry, never selection order or split count.
        var first = corners.OrderBy(i => ordered[i].Start.X).ThenBy(i => ordered[i].Start.Y)
            .ThenBy(i => ordered[i].Start.Z).First();
        var rotation = corners.IndexOf(first);
        corners = Enumerable.Range(0, 4).Select(i => corners[(i + rotation) % 4]).ToList();
        for (var c = 0; c < 4; c++)
        {
            var side = new List<Edge>();
            var stop = corners[(c + 1) % 4];
            for (var i = corners[c];; i = (i + 1) % ordered.Count)
            {
                side.Add(ordered[i]);
                if ((i + 1) % ordered.Count == stop) break;
            }
            Sides.Add(side);
        }
        CanonicalizeSides();
    }

    private void CanonicalizeSides()
    {
        var first = Enumerable.Range(0, 4).OrderBy(i => Sides[i][0].Start.X)
            .ThenBy(i => Sides[i][0].Start.Y).ThenBy(i => Sides[i][0].Start.Z).First();
        var rotated = Enumerable.Range(0, 4).Select(i => Sides[(first + i) % 4]).ToArray();
        Sides.Clear(); Sides.AddRange(rotated);
        var next = Sides[1][0].Start;
        var previous = Sides[3][0].Start;
        if (Compare(next, previous) > 0)
        {
            Sides.Reverse();
            foreach (var side in Sides)
            {
                side.Reverse();
                foreach (var edge in side) edge.Reverse = !edge.Reverse;
            }
        }
    }


    // Parent-aware family recognition: genuine curved natural side branches isolate
    // a coplanar parent chain and a straight opposite chain. Native edge count and
    // internal knot/split layout do not define these four logical boundaries.
    private bool TryParentBranchPartition(List<Edge> ordered)
    {
        var runs = new List<List<Edge>>();
        var n = ordered.Count;
        for (var i = 0; i < n; i++)
        {
            if (!NaturalBranch(ordered[i], out var face, out var iso)
                || (NaturalBranch(ordered[(i + n - 1) % n], out var previous, out var previousIso)
                    && ordered[i].OwnerIndex == ordered[(i + n - 1) % n].OwnerIndex
                    && face.FaceIndex == previous.FaceIndex && iso == previousIso)) continue;
            var run = new List<Edge>();
            for (var j = i; run.Count < n; j = (j + 1) % n)
            {
                if (!NaturalBranch(ordered[j], out var next, out var nextIso)
                    || ordered[j].OwnerIndex != ordered[i].OwnerIndex || face.FaceIndex != next.FaceIndex || nextIso != iso) break;
                run.Add(ordered[j]);
            }
            if (run.Count == 0 || run.All(e => e.Native.IsLinear(Tolerance))) continue;
            var u = face.Domain(0); var v = face.Domain(1);
            var a = iso == IsoStatus.West ? face.PointAt(u.T0, v.T0)
                : iso == IsoStatus.East ? face.PointAt(u.T1, v.T0)
                : iso == IsoStatus.South ? face.PointAt(u.T0, v.T0) : face.PointAt(u.T0, v.T1);
            var b = iso == IsoStatus.West ? face.PointAt(u.T0, v.T1)
                : iso == IsoStatus.East ? face.PointAt(u.T1, v.T1)
                : iso == IsoStatus.South ? face.PointAt(u.T1, v.T0) : face.PointAt(u.T1, v.T1);
            if ((run[0].Start.DistanceTo(a) <= Tolerance && run[run.Count - 1].End.DistanceTo(b) <= Tolerance)
                || (run[0].Start.DistanceTo(b) <= Tolerance && run[run.Count - 1].End.DistanceTo(a) <= Tolerance)) runs.Add(run);
        }
        var partitions = new List<List<Edge>[]>();
        for (var i = 0; i < runs.Count; i++)
            for (var j = i + 1; j < runs.Count; j++)
            {
                var a = Between(ordered, runs[i], runs[j]);
                var b = Between(ordered, runs[j], runs[i]);
                if (a.Count == 0 || b.Count == 0) continue;
                var planarA = CommonParentPlane(a); var planarB = CommonParentPlane(b);
                if (planarA == planarB) continue;
                var straight = planarA ? b : a;
                if (!StraightChain(straight)) continue;
                partitions.Add(new[] { runs[i], a, runs[j], b });
            }
        if (partitions.Count > 1) throw new NativeCompareUnsupported("UNSUPPORTED_AMBIGUOUS_NATURAL_SIDE_BRANCHES");
        if (partitions.Count == 0) return false;
        Sides.AddRange(partitions[0]);
        Derivation = "NATURAL_SIDE_PAIR_COPLANAR_PARENT_CHAIN_STRAIGHT_CHAIN";
        return true;
    }

    private bool NaturalBranch(Edge edge, out BrepFace face, out IsoStatus iso)
    {
        face = NativeCompareMeasure.Face(edge.Native)!;
        iso = IsoStatus.None;
        if (face is null || face.IsPlanar(Tolerance)) return false;
        var trim = edge.Native.Brep.Trims[edge.Native.TrimIndices()[0]];
        iso = trim.IsoStatus;
        return NativeCompareMeasure.NaturalTrimLocus(trim);
    }

    private static List<Edge> Between(List<Edge> ordered, List<Edge> first, List<Edge> second)
    {
        var result = new List<Edge>();
        var start = (ordered.IndexOf(first[first.Count - 1]) + 1) % ordered.Count;
        var end = ordered.IndexOf(second[0]);
        for (var i = start; i != end; i = (i + 1) % ordered.Count)
        {
            if (first.Contains(ordered[i]) || second.Contains(ordered[i])) return new List<Edge>();
            result.Add(ordered[i]);
        }
        return result;
    }

    private bool CommonParentPlane(List<Edge> edges)
    {
        var first = NativeCompareMeasure.Face(edges[0].Native);
        if (first is null || !first.TryGetPlane(out var plane, Tolerance)) return false;
        foreach (var edge in edges)
        {
            var face = NativeCompareMeasure.Face(edge.Native);
            if (face is null || !face.TryGetPlane(out var other, Tolerance)
                || Math.Abs(plane.DistanceTo(other.Origin)) > Tolerance
                || Math.Abs(plane.Normal * other.Normal) < Math.Cos(1e-5)) return false;
        }
        return true;
    }

    private bool StraightChain(List<Edge> edges)
    {
        var start = edges[0].Start;
        var direction = edges[edges.Count - 1].End - start;
        if (!direction.Unitize()) return false;
        return edges.All(e => e.Native.IsLinear(Tolerance)
            && Vector3d.CrossProduct(e.Start - start, direction).Length <= Tolerance
            && Vector3d.CrossProduct(e.End - start, direction).Length <= Tolerance);
    }

    private static int Compare(Point3d a, Point3d b)
    {
        var x = a.X.CompareTo(b.X); if (x != 0) return x;
        var y = a.Y.CompareTo(b.Y); return y != 0 ? y : a.Z.CompareTo(b.Z);
    }

    private bool SmoothContinuation(Edge a, Edge b)
    {
        var ta = a.Tangent(true); var tb = b.Tangent(false);
        if (!ta.Unitize() || !tb.Unitize()) throw new NativeCompareUnsupported("UNSUPPORTED_ENDPOINT_TANGENT");
        var tangentAngle = Vector3d.VectorAngle(ta, tb);
        if (tangentAngle > 1e-5) return false;
        var ka = a.Native.CurvatureAt(a.Parameter(true));
        var kb = b.Native.CurvatureAt(b.Parameter(false));
        if (!ka.IsValid || !kb.IsValid) throw new NativeCompareUnsupported("UNSUPPORTED_ENDPOINT_CURVATURE");

        if (!NativeCompareMeasure.Frame(a.Native, a.Parameter(true), Tolerance, out var fa)
            || !NativeCompareMeasure.Frame(b.Native, b.Parameter(false), Tolerance, out var fb))
            throw new NativeCompareUnsupported("UNSUPPORTED_PARENT_BRANCH_AT_VERTEX");
        var dot = fa.Normal * fb.Normal;
        var normalAngle = Math.Acos(Math.Min(1, Math.Abs(dot)));
        var residual = NativeCompareMath.OperatorResidual(fa.Operator, fb.Operator, dot < 0 ? -1 : 1);
        return NativeCompareMath.IsPhysicalContinuation(tangentAngle, (ka - kb).Length,
            Math.Max(ka.Length, kb.Length), normalAngle, residual, Math.Max(fa.Norm, fb.Norm), _loopLength);
    }

    internal Curve SideCurve(int side)
    {
        var pieces = new List<Curve>();
        try
        {
            foreach (var edge in Sides[side])
            {
                var curve = edge.Native.DuplicateCurve();
                if (edge.Reverse) curve.Reverse();
                pieces.Add(curve);
            }
            var joined = Curve.JoinCurves(pieces, Tolerance, true);
            if (joined is null || joined.Length != 1)
            {
                if (joined is not null) foreach (var curve in joined) curve.Dispose();
                throw new NativeCompareUnsupported("UNSUPPORTED_LOGICAL_SIDE_JOIN");
            }
            return joined[0];
        }
        finally { foreach (var piece in pieces) piece.Dispose(); }
    }

    private string Fingerprint(RhinoObject obj)
    {
        // Full geometry and attribute archives stay in memory; no source hashes or coordinates are logged.
        using var sha = SHA256.Create();
        var bytes = Encoding.UTF8.GetBytes(GeometryFingerprint(obj.Geometry) + "\n" + obj.Attributes.ToJSON(_serialization));
        return Convert.ToBase64String(sha.ComputeHash(bytes));
    }
    private string GeometryFingerprint(GeometryBase geometry)
    {
        // Canonicalize lazy caches on a fresh disposable copy, never on the document owner.
        using var snapshot = geometry.Duplicate();
        snapshot.GetBoundingBox(false);
        if (snapshot is Brep brep) _ = brep.IsSolid;
        using var sha = SHA256.Create();
        return Convert.ToBase64String(sha.ComputeHash(Encoding.UTF8.GetBytes(snapshot.ToJSON(_serialization))));
    }
    internal bool CopiesUnchanged() => Owners.All(owner => GeometryFingerprint(owner.Copy) == owner.CopyFingerprint);
    internal bool SourcesUnchanged(RhinoDoc doc) => doc.RuntimeSerialNumber == _documentSerial
        && doc.ModelAbsoluteTolerance == Tolerance && doc.ModelAngleToleranceRadians == AngleTolerance
        && Owners.All(owner =>
        {
            var obj = doc.Objects.FindId(owner.Id);
            return obj is not null && !obj.IsDeleted && obj.RuntimeSerialNumber == owner.Serial
                && Fingerprint(obj) == owner.Fingerprint;
        });
    public void Dispose() { foreach (var owner in Owners) owner.Copy.Dispose(); Owners.Clear(); }
}

internal sealed class NativeCompareUnsupported : Exception
{
    internal NativeCompareUnsupported(string reason) : base(reason) { }
}
