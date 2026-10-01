using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Rhino.DocObjects;
using Rhino.Geometry;
using SmartSkin.Core.Construction;
using SmartSkin.Core.Routing;

namespace SmartSkin.Rhino8;

internal static class CandidateBuildCodes
{
    public const string Built = "P03_BUILT";
    public const string ReferenceMismatch = "P03_REFERENCE_MISMATCH";
    public const string CurveExtractionFailed = "P03_CURVE_EXTRACTION_FAILED";
    public const string EdgeOrderingFailed = "P03_EDGE_ORDERING_FAILED";
    public const string NativeConstructionFailed = "P03_NATIVE_CONSTRUCTION_FAILED";
    public const string NativeResultAmbiguous = "P03_NATIVE_RESULT_AMBIGUOUS";
    public const string InvalidCandidate = "P03_INVALID_CANDIDATE";
    public const string ResultLimit = "P03_RESULT_LIMIT";
    public const string NativeException = "P03_NATIVE_EXCEPTION";
}

internal sealed class CandidateBuildOutcome : IDisposable
{
    private CandidateBuildOutcome(
        bool success,
        string code,
        string message,
        Brep? candidate,
        int reversedCurveCount,
        long elapsedMilliseconds)
    {
        Success = success;
        Code = code;
        Message = message;
        Candidate = candidate;
        ReversedCurveCount = reversedCurveCount;
        ElapsedMilliseconds = elapsedMilliseconds;
    }

    public bool Success { get; }

    public string Code { get; }

    public string Message { get; }

    public Brep? Candidate { get; }

    public int ReversedCurveCount { get; }

    public long ElapsedMilliseconds { get; }

    public static CandidateBuildOutcome Succeeded(
        Brep candidate,
        int reversedCurveCount,
        long elapsedMilliseconds)
    {
        return new CandidateBuildOutcome(
            true,
            CandidateBuildCodes.Built,
            "One valid disposable Brep candidate was built in memory.",
            candidate,
            reversedCurveCount,
            elapsedMilliseconds);
    }

    public static CandidateBuildOutcome Failed(
        string code,
        string message,
        int reversedCurveCount,
        long elapsedMilliseconds)
    {
        return new CandidateBuildOutcome(
            false,
            code,
            message,
            null,
            reversedCurveCount,
            elapsedMilliseconds);
    }

    public void Dispose()
    {
        Candidate?.Dispose();
    }
}

internal sealed class RhinoCandidateBuilder
{
    private const int MaximumResultFaces = 64;
    private const int MaximumResultEdges = 256;

    public CandidateBuildOutcome Build(
        CandidateConstructionPlan plan,
        IReadOnlyList<ObjRef> references,
        double absoluteTolerance)
    {
        if (plan is null)
        {
            throw new ArgumentNullException(nameof(plan));
        }

        if (references is null)
        {
            throw new ArgumentNullException(nameof(references));
        }

        if (!plan.IsReady || !plan.Strategy.HasValue)
        {
            throw new ArgumentException("The construction plan must be READY.", nameof(plan));
        }

        var stopwatch = Stopwatch.StartNew();
        var duplicates = new List<Curve>(references.Count);
        var reversedCurveCount = 0;
        Brep? candidate = null;

        try
        {
            if (references.Count != plan.CurveCount)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.ReferenceMismatch,
                    "The selected object-reference count no longer matches the construction plan.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds);
            }

            foreach (var reference in references)
            {
                var duplicate = DuplicateSelectedCurve(reference);
                if (duplicate is null)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.CurveExtractionFailed,
                        "Rhino could not duplicate one selected curve or edge without using its parent object.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds);
                }

                duplicates.Add(duplicate);
            }

            switch (plan.Strategy.Value)
            {
                case SurfaceStrategy.PlanarSrf:
                    candidate = RequireSingle(Brep.CreatePlanarBreps(duplicates[0], absoluteTolerance), out var planarCode);
                    if (candidate is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            planarCode,
                            "Rhino did not return exactly one PlanarSrf candidate.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds);
                    }

                    break;

                case SurfaceStrategy.EdgeSrf:
                    var ordered = OrderClosedEdgeLoop(
                        duplicates,
                        absoluteTolerance,
                        out reversedCurveCount);
                    if (ordered is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            CandidateBuildCodes.EdgeOrderingFailed,
                            "Curve copies could not be ordered and oriented into one tolerance-closed loop.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds);
                    }

                    candidate = Brep.CreateEdgeSurface(ordered);
                    if (candidate is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            CandidateBuildCodes.NativeConstructionFailed,
                            "Rhino did not return an EdgeSrf candidate.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds);
                    }

                    break;

                case SurfaceStrategy.Loft:
                    if (!Curve.DoDirectionsMatch(duplicates[0], duplicates[1]))
                    {
                        if (!duplicates[1].Reverse())
                        {
                            return CandidateBuildOutcome.Failed(
                                CandidateBuildCodes.CurveExtractionFailed,
                                "The second Loft section copy could not be direction-aligned.",
                                reversedCurveCount,
                                stopwatch.ElapsedMilliseconds);
                        }

                        reversedCurveCount++;
                    }

                    candidate = RequireSingle(
                        Brep.CreateFromLoft(
                            duplicates,
                            Point3d.Unset,
                            Point3d.Unset,
                            LoftType.Normal,
                            closed: false),
                        out var loftCode);
                    if (candidate is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            loftCode,
                            "Rhino did not return exactly one Loft candidate.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds);
                    }

                    break;

                default:
                    throw new ArgumentOutOfRangeException();
            }

            if (candidate is null)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.NativeConstructionFailed,
                    "Rhino returned no candidate.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds);
            }

            if (!candidate.IsValid || candidate.Faces.Count < 1)
            {
                candidate.Dispose();
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.InvalidCandidate,
                    "Rhino returned a candidate that is invalid or has no faces.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds);
            }

            if (candidate.Faces.Count > MaximumResultFaces || candidate.Edges.Count > MaximumResultEdges)
            {
                candidate.Dispose();
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.ResultLimit,
                    $"Candidate faces/edges exceed P03 result limits {MaximumResultFaces}/{MaximumResultEdges}.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds);
            }

            stopwatch.Stop();
            return CandidateBuildOutcome.Succeeded(
                candidate,
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds);
        }
        catch (Exception exception)
        {
            candidate?.Dispose();
            stopwatch.Stop();
            return CandidateBuildOutcome.Failed(
                CandidateBuildCodes.NativeException,
                $"Native candidate construction raised {exception.GetType().Name}.",
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds);
        }
        finally
        {
            foreach (var duplicate in duplicates)
            {
                duplicate.Dispose();
            }
        }
    }

    private static Curve? DuplicateSelectedCurve(ObjRef reference)
    {
        if (reference is null)
        {
            return null;
        }

        var componentIndex = reference.GeometryComponentIndex;
        if (componentIndex.ComponentIndexType == ComponentIndexType.InvalidType)
        {
            return (reference.Object()?.Geometry as Curve)?.DuplicateCurve();
        }

        var edge = reference.Edge();
        if (edge is not null)
        {
            return edge.DuplicateCurve();
        }

        return (reference.Geometry() as Curve)?.DuplicateCurve();
    }

    private static IReadOnlyList<Curve>? OrderClosedEdgeLoop(
        IReadOnlyList<Curve> curves,
        double tolerance,
        out int reversedCurveCount)
    {
        reversedCurveCount = 0;
        if (curves.Count < 2 || curves.Count > 4)
        {
            return null;
        }

        var unused = new List<Curve>(curves.Skip(1));
        var ordered = new List<Curve>(curves.Count) { curves[0] };

        while (unused.Count > 0)
        {
            var currentEnd = ordered[ordered.Count - 1].PointAtEnd;
            var nextIndex = -1;
            var reverse = false;

            for (var index = 0; index < unused.Count; index++)
            {
                if (currentEnd.DistanceTo(unused[index].PointAtStart) <= tolerance)
                {
                    nextIndex = index;
                    break;
                }

                if (currentEnd.DistanceTo(unused[index].PointAtEnd) <= tolerance)
                {
                    nextIndex = index;
                    reverse = true;
                    break;
                }
            }

            if (nextIndex < 0)
            {
                return null;
            }

            var next = unused[nextIndex];
            unused.RemoveAt(nextIndex);
            if (reverse)
            {
                if (!next.Reverse())
                {
                    return null;
                }

                reversedCurveCount++;
            }

            ordered.Add(next);
        }

        return ordered[ordered.Count - 1].PointAtEnd.DistanceTo(ordered[0].PointAtStart) <= tolerance
            ? ordered
            : null;
    }

    private static Brep? RequireSingle(Brep[]? candidates, out string code)
    {
        if (candidates is null || candidates.Length == 0)
        {
            code = CandidateBuildCodes.NativeConstructionFailed;
            return null;
        }

        if (candidates.Length != 1)
        {
            foreach (var candidate in candidates)
            {
                candidate?.Dispose();
            }

            code = CandidateBuildCodes.NativeResultAmbiguous;
            return null;
        }

        code = CandidateBuildCodes.Built;
        return candidates[0];
    }
}
