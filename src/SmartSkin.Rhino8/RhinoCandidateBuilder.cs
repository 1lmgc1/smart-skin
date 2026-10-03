using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using SmartSkin.Core.Construction;
using SmartSkin.Core.Routing;

namespace SmartSkin.Rhino8;

internal static class CandidateBuildCodes
{
    public const string Built = "P03_BUILT";
    public const string MatchBuilt = "P07_MATCH_BUILT";
    public const string ReferenceMismatch = "P03_REFERENCE_MISMATCH";
    public const string CurveExtractionFailed = "P03_CURVE_EXTRACTION_FAILED";
    public const string EdgeOrderingFailed = "P03_EDGE_ORDERING_FAILED";
    public const string NativeConstructionFailed = "P03_NATIVE_CONSTRUCTION_FAILED";
    public const string NativeResultAmbiguous = "P03_NATIVE_RESULT_AMBIGUOUS";
    public const string InvalidCandidate = "P03_INVALID_CANDIDATE";
    public const string NativeException = "P03_NATIVE_EXCEPTION";
    public const string BoundaryContextMissing = "P07_BOUNDARY_CONTEXT_MISSING";
    public const string BoundaryEdgeNotNaked = "P07_BOUNDARY_EDGE_NOT_NAKED";
    public const string BoundaryTrimAmbiguous = "P07_BOUNDARY_TRIM_AMBIGUOUS";
    public const string ContextJoinFailed = "P07_CONTEXT_JOIN_FAILED";
    public const string ContextComplexityLimit = "P07_CONTEXT_COMPLEXITY_LIMIT";
    public const string BuildTimeLimit = "P07_BUILD_TIME_LIMIT";
    public const string BuildCancelled = "P07_BUILD_CANCELLED";
    public const string ContextEdgeMappingFailed = "P07_CONTEXT_EDGE_MAPPING_FAILED";
    public const string SeedConstructionFailed = "P07_SEED_CONSTRUCTION_FAILED";
    public const string SeedEdgeMissing = "P07_SEED_EDGE_MISSING";
    public const string NativeMatchFailed = "P07_NATIVE_MATCH_FAILED";
    public const string AverageRequiresUntrimmedTarget = "P07_AVERAGE_REQUIRES_UNTRIMMED_TARGET";
    public const string AverageAttributesDiffer = "P07_AVERAGE_ATTRIBUTES_DIFFER";
    public const string AverageTargetMissing = "P07_AVERAGE_TARGET_MISSING";
    public const string JoinProofFailed = "P07_JOIN_PROOF_FAILED";
    public const string VerificationUnavailable = "P07_VERIFICATION_UNAVAILABLE";
    public const string ContinuityOutOfTolerance = "P07_CONTINUITY_OUT_OF_TOLERANCE";
}

internal sealed class CandidateBuildOutcome : IDisposable
{
    private CandidateBuildOutcome(
        bool success,
        string code,
        string message,
        Brep? candidate,
        Brep? averagedContext,
        Brep? commitBrep,
        IReadOnlyList<Guid> parentObjectIds,
        int reversedCurveCount,
        long elapsedMilliseconds,
        int supportedEdgeCount,
        int joinedSeamCount,
        bool reverseMatchDirection,
        bool reverseAverageTargetDirection,
        CandidateBuildSettings settings,
        BoundaryMatchMetrics? metrics)
    {
        Success = success;
        Code = code;
        Message = message;
        Candidate = candidate;
        AveragedContext = averagedContext;
        CommitBrep = commitBrep;
        ParentObjectIds = parentObjectIds;
        ReversedCurveCount = reversedCurveCount;
        ElapsedMilliseconds = elapsedMilliseconds;
        SupportedEdgeCount = supportedEdgeCount;
        JoinedSeamCount = joinedSeamCount;
        ReverseMatchDirection = reverseMatchDirection;
        ReverseAverageTargetDirection = reverseAverageTargetDirection;
        Settings = settings;
        Metrics = metrics;
    }

    public bool Success { get; }

    public string Code { get; }

    public string Message { get; }

    public Brep? Candidate { get; }

    public Brep? AveragedContext { get; }

    public Brep? CommitBrep { get; }

    public IReadOnlyList<Guid> ParentObjectIds { get; }

    public int ReversedCurveCount { get; }

    public long ElapsedMilliseconds { get; }

    public int SupportedEdgeCount { get; }

    public int JoinedSeamCount { get; }

    public bool ReverseMatchDirection { get; }

    public bool ReverseAverageTargetDirection { get; }

    public int ParentObjectCount => ParentObjectIds.Count;

    public CandidateBuildSettings Settings { get; }

    public BoundaryMatchMetrics? Metrics { get; }

    public bool ReplacesSources => Success && Settings.AverageSurfaces;

    public static CandidateBuildOutcome Succeeded(
        Brep candidate,
        int reversedCurveCount,
        long elapsedMilliseconds,
        CandidateBuildSettings? settings = null,
        string? code = null,
        string? message = null,
        Brep? averagedContext = null,
        Brep? commitBrep = null,
        IReadOnlyList<Guid>? parentObjectIds = null,
        int supportedEdgeCount = 0,
        int joinedSeamCount = 0,
        bool reverseMatchDirection = false,
        bool reverseAverageTargetDirection = false,
        BoundaryMatchMetrics? metrics = null)
    {
        return new CandidateBuildOutcome(
            true,
            code ?? CandidateBuildCodes.Built,
            message ?? "One valid disposable Brep candidate was built in memory.",
            candidate,
            averagedContext,
            commitBrep ?? candidate,
            parentObjectIds ?? Array.Empty<Guid>(),
            reversedCurveCount,
            elapsedMilliseconds,
            supportedEdgeCount,
            joinedSeamCount,
            reverseMatchDirection,
            reverseAverageTargetDirection,
            settings ?? CandidateBuildSettings.Default,
            metrics);
    }

    public static CandidateBuildOutcome Failed(
        string code,
        string message,
        int reversedCurveCount,
        long elapsedMilliseconds,
        CandidateBuildSettings? settings = null,
        int supportedEdgeCount = 0,
        IReadOnlyList<Guid>? parentObjectIds = null,
        BoundaryMatchMetrics? metrics = null,
        int joinedSeamCount = 0,
        bool reverseMatchDirection = false,
        bool reverseAverageTargetDirection = false)
    {
        return new CandidateBuildOutcome(
            false,
            code,
            message,
            null,
            null,
            null,
            parentObjectIds ?? Array.Empty<Guid>(),
            reversedCurveCount,
            elapsedMilliseconds,
            supportedEdgeCount,
            joinedSeamCount,
            reverseMatchDirection,
            reverseAverageTargetDirection,
            settings ?? CandidateBuildSettings.Default,
            metrics);
    }

    public void Dispose()
    {
        Candidate?.Dispose();
        if (AveragedContext is not null && !ReferenceEquals(AveragedContext, Candidate))
        {
            AveragedContext.Dispose();
        }

        if (CommitBrep is not null
            && !ReferenceEquals(CommitBrep, Candidate)
            && !ReferenceEquals(CommitBrep, AveragedContext))
        {
            CommitBrep.Dispose();
        }
    }
}

internal sealed class RhinoCandidateBuilder
{
    private const int MaximumResultFaces = 128;
    private const int MaximumResultEdges = 512;
    private const int MaximumContextFaces = 96;
    private const int MaximumContextEdges = 448;
    private const long MaximumContextSurfaceComplexity = 32768;
    private const long MaximumBuildMilliseconds = 10000;

    public CandidateBuildOutcome Build(
        CandidateConstructionPlan plan,
        IReadOnlyList<ObjRef> references,
        double absoluteTolerance,
        double angleToleranceRadians,
        CandidateBuildSettings? settings = null,
        Func<bool>? cancellationRequested = null)
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

        var effectiveSettings = settings ?? CandidateBuildSettings.Default;
        var stopwatch = Stopwatch.StartNew();

        if (cancellationRequested?.Invoke() == true)
        {
            return CandidateBuildOutcome.Failed(
                CandidateBuildCodes.BuildCancelled,
                "The Smart Skin build was cancelled before native construction started.",
                0,
                stopwatch.ElapsedMilliseconds,
                effectiveSettings);
        }

        if (references.Count != plan.CurveCount)
        {
            return CandidateBuildOutcome.Failed(
                CandidateBuildCodes.ReferenceMismatch,
                "The selected object-reference count no longer matches the construction plan.",
                0,
                stopwatch.ElapsedMilliseconds,
                effectiveSettings);
        }

        if (plan.Strategy.Value == SurfaceStrategy.MatchSrf)
        {
            return BuildMatchedBoundaryCap(
                references,
                absoluteTolerance,
                angleToleranceRadians,
                effectiveSettings,
                stopwatch,
                cancellationRequested);
        }

        var duplicates = new List<Curve>(references.Count);
        var reversedCurveCount = 0;
        Brep? candidate = null;

        try
        {
            foreach (var reference in references)
            {
                var duplicate = DuplicateSelectedCurve(reference);
                if (duplicate is null)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.CurveExtractionFailed,
                        "Rhino could not duplicate one selected curve or edge without using its parent object.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        effectiveSettings);
                }

                duplicates.Add(duplicate);
            }

            switch (plan.Strategy.Value)
            {
                case SurfaceStrategy.PlanarSrf:
                    candidate = RequireSingle(
                        Brep.CreatePlanarBreps(duplicates[0], absoluteTolerance),
                        out var planarCode);
                    if (candidate is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            planarCode,
                            "Rhino did not return exactly one PlanarSrf candidate.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds,
                            effectiveSettings);
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
                            stopwatch.ElapsedMilliseconds,
                            effectiveSettings);
                    }

                    candidate = Brep.CreateEdgeSurface(ordered.Curves);
                    if (candidate is null)
                    {
                        return CandidateBuildOutcome.Failed(
                            CandidateBuildCodes.NativeConstructionFailed,
                            "Rhino did not return an EdgeSrf candidate.",
                            reversedCurveCount,
                            stopwatch.ElapsedMilliseconds,
                            effectiveSettings);
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
                                stopwatch.ElapsedMilliseconds,
                                effectiveSettings);
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
                            stopwatch.ElapsedMilliseconds,
                            effectiveSettings);
                    }

                    break;

                default:
                    throw new ArgumentOutOfRangeException();
            }

            if (!IsBoundedValidResult(candidate))
            {
                candidate?.Dispose();
                candidate = null;
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.InvalidCandidate,
                    "Rhino returned a candidate that is invalid or outside the bounded result limits.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    effectiveSettings);
            }

            stopwatch.Stop();
            var result = CandidateBuildOutcome.Succeeded(
                candidate,
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds,
                effectiveSettings);
            candidate = null;
            return result;
        }
        catch (Exception exception)
        {
            return CandidateBuildOutcome.Failed(
                CandidateBuildCodes.NativeException,
                $"Native candidate construction raised {exception.GetType().Name}.",
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds,
                effectiveSettings);
        }
        finally
        {
            candidate?.Dispose();
            foreach (var duplicate in duplicates)
            {
                duplicate.Dispose();
            }
        }
    }

    private static CandidateBuildOutcome BuildMatchedBoundaryCap(
        IReadOnlyList<ObjRef> references,
        double absoluteTolerance,
        double angleToleranceRadians,
        CandidateBuildSettings settings,
        Stopwatch stopwatch,
        Func<bool>? cancellationRequested)
    {
        var duplicates = new List<Curve>(references.Count);
        var reversedCurveCount = 0;
        Brep? seed = null;
        Brep? matched = null;
        Brep? averagedContext = null;
        Brep? commitBrep = null;
        var joinedSeamCount = 0;
        var reverseMatchDirection = false;
        var reverseAverageTargetDirection = false;
        var ownershipTransferred = false;

        try
        {
            foreach (var reference in references)
            {
                var edge = reference.Edge();
                if (edge is null)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.BoundaryContextMissing,
                        "Every matched-cap input must remain a selected Brep edge sub-object.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        settings);
                }

                if (edge.Valence != EdgeAdjacency.Naked || edge.TrimCount != 1)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.BoundaryEdgeNotNaked,
                        "Every matched-cap input must be a naked edge with one adjacent Brep face.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        settings);
                }

                var trimIndices = edge.TrimIndices();
                if (trimIndices.Length != 1
                    || edge.Brep is null
                    || trimIndices[0] < 0
                    || trimIndices[0] >= edge.Brep.Trims.Count
                    || edge.Brep.Trims[trimIndices[0]].Face is null)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.BoundaryTrimAmbiguous,
                        "One selected boundary edge has no stable owning trim and adjacent face.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        settings);
                }

                var duplicate = edge.DuplicateCurve();
                if (duplicate is null)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.CurveExtractionFailed,
                        "Rhino could not duplicate one selected Brep edge.",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        settings);
                }

                duplicates.Add(duplicate);
            }

            var ordered = OrderClosedEdgeLoop(duplicates, absoluteTolerance, out reversedCurveCount);
            if (ordered is null)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.EdgeOrderingFailed,
                    "Selected Brep edges could not be ordered into one tolerance-closed loop.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings);
            }

            using var context = BuildBoundaryContext(
                references,
                ordered,
                absoluteTolerance,
                angleToleranceRadians,
                settings.AverageSurfaces,
                out var contextFailureCode,
                out var contextFailureMessage);
            if (context is null)
            {
                return CandidateBuildOutcome.Failed(
                    contextFailureCode,
                    contextFailureMessage,
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings,
                    references.Count);
            }

            using var boundary = JoinBoundary(ordered.Curves, absoluteTolerance);
            if (boundary is null)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.EdgeOrderingFailed,
                    "The ordered Brep edges did not produce one closed seed boundary.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings,
                    context.TargetEdges.Count,
                    context.ParentObjectIds);
            }

            seed = CreateSeedCap(boundary, ordered.Curves, absoluteTolerance);
            if (seed is null)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.SeedConstructionFailed,
                    "Rhino could not build the disposable untrimmed seed cap required by MatchSrf.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings,
                    context.TargetEdges.Count,
                    context.ParentObjectIds);
            }

            var seedEdge = FindSeedBoundaryEdge(seed, boundary, absoluteTolerance);
            if (seedEdge is null)
            {
                return CandidateBuildOutcome.Failed(
                    CandidateBuildCodes.SeedEdgeMissing,
                    "The disposable seed cap has no closed untrimmed boundary edge.",
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings,
                    context.TargetEdges.Count,
                    context.ParentObjectIds);
            }

            if (settings.AverageSurfaces)
            {
                var naturalTargetCount = context.TargetEdges.Count(BoundaryMatchVerifier.IsAverageTargetEligible);
                if (naturalTargetCount != context.TargetEdges.Count)
                {
                    return CandidateBuildOutcome.Failed(
                        CandidateBuildCodes.AverageRequiresUntrimmedTarget,
                        "Rhino MatchSrf can average only untrimmed target surface edges; "
                            + $"natural={naturalTargetCount.ToString(CultureInfo.InvariantCulture)}/"
                            + context.TargetEdges.Count.ToString(CultureInfo.InvariantCulture) + ".",
                        reversedCurveCount,
                        stopwatch.ElapsedMilliseconds,
                        settings,
                        context.TargetEdges.Count,
                        context.ParentObjectIds);
                }
            }

            var lastFailureCode = CandidateBuildCodes.NativeMatchFailed;
            var lastFailureMessage = "Rhino MatchSrf did not return a verified joined cap for any bounded direction variant.";
            BoundaryMatchMetrics? lastMetrics = null;
            var lastJoinedSeamCount = 0;
            var matchDirections = new[] { false, true };
            var averageDirections = settings.AverageSurfaces
                ? new[] { false, true }
                : new[] { false };
            var timeLimitReached = false;
            var cancellationReached = false;
            foreach (var reverseMatch in matchDirections)
            {
                foreach (var reverseAverage in averageDirections)
                {
                    if (stopwatch.ElapsedMilliseconds > MaximumBuildMilliseconds)
                    {
                        lastFailureCode = CandidateBuildCodes.BuildTimeLimit;
                        lastFailureMessage = "The bounded MatchSrf build time limit was reached before another direction variant could start.";
                        timeLimitReached = true;
                        break;
                    }

                    if (cancellationRequested?.Invoke() == true)
                    {
                        lastFailureCode = CandidateBuildCodes.BuildCancelled;
                        lastFailureMessage = "The Smart Skin build was cancelled before another direction variant could start.";
                        cancellationReached = true;
                        break;
                    }

                    if (!TryBuildMatchVariant(
                            seedEdge,
                            context,
                            settings,
                            absoluteTolerance,
                            angleToleranceRadians,
                            reverseMatch,
                            reverseAverage,
                            cancellationRequested,
                            out var attemptMatched,
                            out var attemptAveragedContext,
                            out var attemptCommitBrep,
                            out var attemptMetrics,
                            out var attemptJoinedSeamCount,
                            out lastFailureCode,
                            out lastFailureMessage))
                    {
                        lastMetrics = attemptMetrics;
                        lastJoinedSeamCount = attemptJoinedSeamCount;
                        reverseMatchDirection = reverseMatch;
                        reverseAverageTargetDirection = reverseAverage;
                        if (lastFailureCode == CandidateBuildCodes.BuildCancelled)
                        {
                            cancellationReached = true;
                            break;
                        }

                        continue;
                    }

                    matched = attemptMatched;
                    averagedContext = attemptAveragedContext;
                    commitBrep = attemptCommitBrep;
                    lastMetrics = attemptMetrics;
                    joinedSeamCount = attemptJoinedSeamCount;
                    reverseMatchDirection = reverseMatch;
                    reverseAverageTargetDirection = reverseAverage;
                    break;
                }

                if (matched is not null)
                {
                    break;
                }

                if (timeLimitReached || cancellationReached)
                {
                    break;
                }
            }

            if (matched is null || commitBrep is null || lastMetrics is null)
            {
                return CandidateBuildOutcome.Failed(
                    lastFailureCode,
                    lastFailureMessage,
                    reversedCurveCount,
                    stopwatch.ElapsedMilliseconds,
                    settings,
                    context.TargetEdges.Count,
                    context.ParentObjectIds,
                    lastMetrics,
                    lastJoinedSeamCount,
                    reverseMatchDirection,
                    reverseAverageTargetDirection);
            }

            stopwatch.Stop();
            var outcome = CandidateBuildOutcome.Succeeded(
                matched,
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds,
                settings,
                CandidateBuildCodes.MatchBuilt,
                settings.AverageSurfaces
                    ? "One verified matched cap and one averaged joined context are ready in memory."
                    : "One verified MatchSrf cap is ready in memory; source Breps remain unchanged.",
                averagedContext,
                commitBrep,
                context.ParentObjectIds,
                context.TargetEdges.Count,
                joinedSeamCount,
                reverseMatchDirection,
                reverseAverageTargetDirection,
                lastMetrics);
            ownershipTransferred = true;
            return outcome;
        }
        catch (Exception exception)
        {
            return CandidateBuildOutcome.Failed(
                CandidateBuildCodes.NativeException,
                $"Native matched-cap construction raised {exception.GetType().Name}.",
                reversedCurveCount,
                stopwatch.ElapsedMilliseconds,
                settings);
        }
        finally
        {
            seed?.Dispose();
            foreach (var duplicate in duplicates)
            {
                duplicate.Dispose();
            }

            if (!ownershipTransferred)
            {
                matched?.Dispose();
                if (averagedContext is not null && !ReferenceEquals(averagedContext, matched))
                {
                    averagedContext.Dispose();
                }

                if (commitBrep is not null
                    && !ReferenceEquals(commitBrep, matched)
                    && !ReferenceEquals(commitBrep, averagedContext))
                {
                    commitBrep.Dispose();
                }
            }
        }
    }

    private static bool TryBuildMatchVariant(
        BrepEdge seedEdge,
        BoundaryContext context,
        CandidateBuildSettings settings,
        double absoluteTolerance,
        double angleToleranceRadians,
        bool reverseMatchDirection,
        bool reverseAverageTargetDirection,
        Func<bool>? cancellationRequested,
        out Brep? matched,
        out Brep? averagedContext,
        out Brep? commitBrep,
        out BoundaryMatchMetrics? metrics,
        out int joinedSeamCount,
        out string failureCode,
        out string failureMessage)
    {
        matched = null;
        averagedContext = null;
        commitBrep = null;
        metrics = null;
        joinedSeamCount = 0;
        failureCode = CandidateBuildCodes.NativeMatchFailed;
        failureMessage = "Rhino MatchSrf did not return a matched cap for this direction variant.";
        Brep? joinedProof = null;
        var success = false;
        var variant = "reverse_match=" + (reverseMatchDirection ? "ON" : "OFF")
            + ";reverse_average_target=" + (reverseAverageTargetDirection ? "ON" : "OFF");
        var phase = "NATIVE_MATCH";
        var attemptWatch = Stopwatch.StartNew();

        try
        {
            RhinoApp.WriteLine("SMARTSKIN_P07F1_ATTEMPT_START | " + variant
                + " | continuity=" + settings.ContinuityToken);
            if (cancellationRequested?.Invoke() == true)
            {
                failureCode = CandidateBuildCodes.BuildCancelled;
                failureMessage = "The Smart Skin build was cancelled before MatchSrf started.";
                return false;
            }

            var matchSettings = new MatchSrfSettings(
                settings.RhinoContinuity,
                Rhino.Geometry.Continuity.None)
            {
                Average = settings.AverageSurfaces,
                MatchClosestPoints = false,
                PreserveIso = settings.RhinoPreserveIso,
                ReverseMatchDirection = reverseMatchDirection,
                ReverseAverageTargetDirection = reverseAverageTargetDirection,
            };
            matchSettings.EnableRefinement(
                settings.RefineMatch,
                absoluteTolerance,
                angleToleranceRadians,
                settings.CurvatureTolerancePercent);

            var targetCurves = context.TargetEdges.Select(edge => (Curve)edge).ToArray();
            if (!Brep.CreateFromMatch(
                    seedEdge,
                    targetCurves,
                    matchSettings,
                    out matched,
                    out averagedContext)
                || matched is null)
            {
                return false;
            }

            phase = "RESULT_VALIDATION";
            if (cancellationRequested?.Invoke() == true)
            {
                failureCode = CandidateBuildCodes.BuildCancelled;
                failureMessage = "The Smart Skin build was cancelled after MatchSrf returned.";
                return false;
            }

            if (!IsBoundedValidResult(matched))
            {
                failureCode = CandidateBuildCodes.InvalidCandidate;
                failureMessage = "Rhino MatchSrf returned an invalid or over-limit cap.";
                return false;
            }

            IReadOnlyList<BrepEdge> verificationTargets = context.TargetEdges;
            if (settings.AverageSurfaces)
            {
                phase = "AVERAGE_MAPPING";
                if (averagedContext is null || !IsBoundedValidResult(averagedContext))
                {
                    failureCode = CandidateBuildCodes.AverageTargetMissing;
                    failureMessage = "Average surfaces is unavailable: Rhino did not return a valid changed target Brep.";
                    return false;
                }

                var changedEdges = ResolveChangedTargetEdges(
                    averagedContext,
                    context,
                    absoluteTolerance);
                if (changedEdges is null)
                {
                    failureCode = CandidateBuildCodes.ContextEdgeMappingFailed;
                    failureMessage = "The averaged target Brep no longer exposes the selected closed boundary unambiguously.";
                    return false;
                }

                verificationTargets = changedEdges;
            }
            else
            {
                averagedContext?.Dispose();
                averagedContext = null;
            }

            phase = "BOUNDARY_VERIFICATION";
            metrics = BoundaryMatchVerifier.Verify(
                matched,
                verificationTargets,
                settings,
                absoluteTolerance,
                angleToleranceRadians,
                variant,
                writeDiagnostics: true,
                cancellationRequested);
            if (!metrics.Available)
            {
                failureCode = metrics.Reason == "VERIFICATION_CANCELLED"
                    ? CandidateBuildCodes.BuildCancelled
                    : CandidateBuildCodes.VerificationUnavailable;
                failureMessage = metrics.Message;
                return false;
            }

            if (!metrics.Verified)
            {
                failureCode = CandidateBuildCodes.ContinuityOutOfTolerance;
                failureMessage = metrics.Message;
                return false;
            }

            if (cancellationRequested?.Invoke() == true)
            {
                failureCode = CandidateBuildCodes.BuildCancelled;
                failureMessage = "The Smart Skin build was cancelled before Join verification.";
                return false;
            }

            phase = "JOIN";
            var joinContext = settings.AverageSurfaces ? averagedContext! : context.Shell;
            joinedProof = RequireSingle(
                Brep.JoinBreps(
                    new[] { joinContext, matched },
                    absoluteTolerance,
                    angleToleranceRadians),
                out _);
            if (joinedProof is null || !IsBoundedValidResult(joinedProof))
            {
                failureCode = CandidateBuildCodes.JoinProofFailed;
                failureMessage = "The matched cap did not join to its copied context as one Brep.";
                return false;
            }

            phase = "JOIN_PROOF";
            if (!ProveJoinedCapBoundary(
                    joinedProof,
                    matched,
                    verificationTargets,
                    settings,
                    absoluteTolerance,
                    angleToleranceRadians,
                    out joinedSeamCount,
                    out failureMessage))
            {
                failureCode = CandidateBuildCodes.JoinProofFailed;
                return false;
            }

            if (settings.AverageSurfaces)
            {
                commitBrep = joinedProof;
                joinedProof = null;
            }
            else
            {
                joinedProof.Dispose();
                joinedProof = null;
                commitBrep = matched;
            }

            phase = "READY";
            success = true;
            return true;
        }
        catch (Exception exception)
        {
            failureCode = CandidateBuildCodes.NativeException;
            failureMessage = $"Native matched-cap construction raised {exception.GetType().Name} for one direction variant.";
            return false;
        }
        finally
        {
            BoundaryAttemptTrace.Write(variant, phase, success, failureCode, failureMessage,
                matched, metrics, joinedSeamCount, attemptWatch.ElapsedMilliseconds);
            joinedProof?.Dispose();
            if (!success)
            {
                matched?.Dispose();
                if (averagedContext is not null && !ReferenceEquals(averagedContext, matched))
                {
                    averagedContext.Dispose();
                }

                if (commitBrep is not null
                    && !ReferenceEquals(commitBrep, matched)
                    && !ReferenceEquals(commitBrep, averagedContext))
                {
                    commitBrep.Dispose();
                }

                matched = null;
                averagedContext = null;
                commitBrep = null;
            }
        }
    }

    private static BoundaryContext? BuildBoundaryContext(
        IReadOnlyList<ObjRef> references,
        OrderedCurveLoop ordered,
        double absoluteTolerance,
        double angleToleranceRadians,
        bool requireCompatibleAttributes,
        out string failureCode,
        out string failureMessage)
    {
        failureCode = CandidateBuildCodes.ContextJoinFailed;
        failureMessage = "The owning Breps could not be joined into one disposable context shell.";

        var parentIds = new List<Guid>();
        var parentCopies = new List<Brep>();
        var totalContextFaces = 0;
        var totalContextEdges = 0;
        long totalSurfaceComplexity = 0;
        ObjectAttributes? firstParentAttributes = null;
        Brep[]? joined = null;
        try
        {
            var seen = new HashSet<Guid>();
            foreach (var reference in references)
            {
                if (!seen.Add(reference.ObjectId))
                {
                    continue;
                }

                var parentObject = reference.Object();
                if (parentObject is null)
                {
                    failureCode = CandidateBuildCodes.BoundaryContextMissing;
                    failureMessage = "One selected edge lost its owning document object before context construction.";
                    return null;
                }

                if (requireCompatibleAttributes
                    && firstParentAttributes is not null
                    && !HaveCompatibleAverageAttributes(firstParentAttributes, parentObject.Attributes))
                {
                    failureCode = CandidateBuildCodes.AverageAttributesDiffer;
                    failureMessage = "Average surfaces is blocked because the owning Breps have different layer, display, material, group or user-string attributes.";
                    return null;
                }

                firstParentAttributes ??= parentObject.Attributes;
                var owner = reference.Edge()?.Brep;
                if (owner is null
                    || !TryAccumulateContextComplexity(
                        owner,
                        ref totalContextFaces,
                        ref totalContextEdges,
                        ref totalSurfaceComplexity))
                {
                    failureCode = CandidateBuildCodes.ContextComplexityLimit;
                    failureMessage = "The owning Brep context exceeds the bounded P07 face, edge or surface-complexity limit.";
                    return null;
                }

                var duplicate = owner?.DuplicateBrep();
                if (duplicate is null)
                {
                    failureCode = CandidateBuildCodes.BoundaryContextMissing;
                    failureMessage = "One selected edge lost its owning Brep before context construction.";
                    return null;
                }

                parentIds.Add(reference.ObjectId);
                parentCopies.Add(duplicate);
            }

            if (parentCopies.Count == 0)
            {
                failureCode = CandidateBuildCodes.BoundaryContextMissing;
                failureMessage = "No owning Breps were available for the selected boundary.";
                return null;
            }

            if (parentCopies.Count == 1)
            {
                joined = new[] { parentCopies[0].DuplicateBrep() };
            }
            else
            {
                joined = Brep.JoinBreps(parentCopies, absoluteTolerance, angleToleranceRadians);
            }

            if (joined is null || joined.Length != 1 || !joined[0].IsValid)
            {
                return null;
            }

            var shell = joined[0];
            joined[0] = null!;
            var targetEdges = MapBoundaryEdges(shell, ordered, absoluteTolerance);
            if (targetEdges is null)
            {
                shell.Dispose();
                failureCode = CandidateBuildCodes.ContextEdgeMappingFailed;
                failureMessage = "The selected naked edges could not be mapped to the disposable joined context.";
                return null;
            }

            return new BoundaryContext(shell, targetEdges, parentIds);
        }
        finally
        {
            foreach (var parentCopy in parentCopies)
            {
                parentCopy.Dispose();
            }

            if (joined is not null)
            {
                foreach (var brep in joined)
                {
                    brep?.Dispose();
                }
            }
        }
    }

    private static bool HaveCompatibleAverageAttributes(
        ObjectAttributes first,
        ObjectAttributes other)
    {
        if (first.LayerIndex != other.LayerIndex
            || !string.Equals(first.Name, other.Name, StringComparison.Ordinal)
            || !string.Equals(first.Url, other.Url, StringComparison.Ordinal)
            || first.Mode != other.Mode
            || first.Visible != other.Visible
            || first.ColorSource != other.ColorSource
            || first.ObjectColor != other.ObjectColor
            || first.LinetypeSource != other.LinetypeSource
            || first.LinetypeIndex != other.LinetypeIndex
            || first.MaterialSource != other.MaterialSource
            || first.MaterialIndex != other.MaterialIndex
            || first.PlotColorSource != other.PlotColorSource
            || first.PlotColor != other.PlotColor
            || first.PlotWeightSource != other.PlotWeightSource
            || !first.PlotWeight.Equals(other.PlotWeight)
            || first.DisplayOrder != other.DisplayOrder
            || first.ObjectDecoration != other.ObjectDecoration
            || first.WireDensity != other.WireDensity
            || first.ViewportId != other.ViewportId
            || first.Space != other.Space
            || first.CastsShadows != other.CastsShadows
            || first.ReceivesShadows != other.ReceivesShadows
            || first.HasMapping
            || other.HasMapping)
        {
            return false;
        }

        var firstGroups = (first.GetGroupList() ?? Array.Empty<int>()).OrderBy(index => index);
        var otherGroups = (other.GetGroupList() ?? Array.Empty<int>()).OrderBy(index => index);
        if (!firstGroups.SequenceEqual(otherGroups))
        {
            return false;
        }

        var firstStrings = first.GetUserStrings();
        var otherStrings = other.GetUserStrings();
        if (firstStrings.Count != otherStrings.Count)
        {
            return false;
        }

        foreach (var key in firstStrings.AllKeys)
        {
            if (key is null
                || !string.Equals(firstStrings[key], otherStrings[key], StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static bool TryAccumulateContextComplexity(
        Brep owner,
        ref int totalFaces,
        ref int totalEdges,
        ref long totalSurfaceComplexity)
    {
        if (owner.Faces.Count > MaximumContextFaces - totalFaces
            || owner.Edges.Count > MaximumContextEdges - totalEdges)
        {
            return false;
        }

        totalFaces += owner.Faces.Count;
        totalEdges += owner.Edges.Count;
        foreach (var face in owner.Faces)
        {
            var uComplexity = (long)face.SpanCount(0) + face.Degree(0) + 1L;
            var vComplexity = (long)face.SpanCount(1) + face.Degree(1) + 1L;
            if (uComplexity <= 0
                || vComplexity <= 0
                || uComplexity > MaximumContextSurfaceComplexity
                || vComplexity > MaximumContextSurfaceComplexity)
            {
                return false;
            }

            var faceComplexity = uComplexity * vComplexity;
            if (faceComplexity > MaximumContextSurfaceComplexity - totalSurfaceComplexity)
            {
                return false;
            }

            totalSurfaceComplexity += faceComplexity;
        }

        return true;
    }

    private static IReadOnlyList<BrepEdge>? MapBoundaryEdges(
        Brep shell,
        OrderedCurveLoop ordered,
        double tolerance)
    {
        var mapped = new List<BrepEdge>(ordered.Curves.Count);
        var used = new HashSet<int>();
        foreach (var source in ordered.Curves)
        {
            BrepEdge? best = null;
            var bestDeviation = double.MaxValue;
            foreach (var edge in shell.Edges)
            {
                if (used.Contains(edge.EdgeIndex) || edge.Valence != EdgeAdjacency.Naked)
                {
                    continue;
                }

                if (!Curve.GetDistancesBetweenCurves(
                        source,
                        edge,
                        Math.Max(tolerance * 0.1, 1e-9),
                        out var maximumDistance,
                        out _,
                        out _,
                        out _,
                        out _,
                        out _))
                {
                    continue;
                }

                if (maximumDistance < bestDeviation)
                {
                    bestDeviation = maximumDistance;
                    best = edge;
                }
            }

            if (best is null || bestDeviation > Math.Max(tolerance * 2.0, 1e-8))
            {
                return null;
            }

            used.Add(best.EdgeIndex);
            mapped.Add(best);
        }

        return mapped;
    }

    private static IReadOnlyList<BrepEdge>? ResolveChangedTargetEdges(
        Brep changedTarget,
        BoundaryContext originalContext,
        double tolerance)
    {
        var mapped = new List<BrepEdge>(originalContext.TargetEdges.Count);
        var used = new HashSet<int>();
        var maximumAcceptedDeviation = Math.Max(tolerance * 5.0, 1e-8);
        var ambiguityTolerance = Math.Max(tolerance * 0.1, 1e-9);
        foreach (var original in originalContext.TargetEdges)
        {
            BrepEdge? best = null;
            var bestDeviation = double.MaxValue;
            var secondBestDeviation = double.MaxValue;
            foreach (var candidate in changedTarget.Edges)
            {
                if (used.Contains(candidate.EdgeIndex) || candidate.Valence != EdgeAdjacency.Naked)
                {
                    continue;
                }

                if (!Curve.GetDistancesBetweenCurves(
                        original,
                        candidate,
                        Math.Max(tolerance * 0.1, 1e-9),
                        out var deviation,
                        out _,
                        out _,
                        out _,
                        out _,
                        out _))
                {
                    continue;
                }

                if (deviation < bestDeviation)
                {
                    secondBestDeviation = bestDeviation;
                    bestDeviation = deviation;
                    best = candidate;
                }
                else if (deviation < secondBestDeviation)
                {
                    secondBestDeviation = deviation;
                }
            }

            if (best is null
                || bestDeviation > maximumAcceptedDeviation
                || secondBestDeviation - bestDeviation <= ambiguityTolerance)
            {
                return null;
            }

            used.Add(best.EdgeIndex);
            mapped.Add(best);
        }

        return mapped;
    }

    private static NurbsCurve? JoinBoundary(IReadOnlyList<Curve> ordered, double tolerance)
    {
        var joined = Curve.JoinCurves(ordered, tolerance, true);
        if (joined is null || joined.Length != 1 || !joined[0].IsClosed)
        {
            if (joined is not null)
            {
                foreach (var curve in joined)
                {
                    curve?.Dispose();
                }
            }

            return null;
        }

        try
        {
            return joined[0].ToNurbsCurve();
        }
        finally
        {
            foreach (var curve in joined)
            {
                curve?.Dispose();
            }
        }
    }

    private static Brep? CreateSeedCap(
        NurbsCurve boundary,
        IReadOnlyList<Curve> orderedEdges,
        double tolerance)
    {
        var samplePoints = new List<Point3d>();
        foreach (var edge in orderedEdges)
        {
            for (var index = 0; index < 8; index++)
            {
                if (edge.NormalizedLengthParameter((index + 0.5) / 8.0, out var parameter))
                {
                    samplePoints.Add(edge.PointAt(parameter));
                }
            }
        }

        if (samplePoints.Count < 3)
        {
            return null;
        }

        var center = new Point3d(
            samplePoints.Average(point => point.X),
            samplePoints.Average(point => point.Y),
            samplePoints.Average(point => point.Z));
        var innerA = boundary.DuplicateCurve();
        var innerB = boundary.DuplicateCurve();
        try
        {
            if (!innerA.Transform(Transform.Scale(center, 0.66))
                || !innerB.Transform(Transform.Scale(center, 0.33)))
            {
                return null;
            }

            return RequireSingle(
                Brep.CreateFromLoft(
                    new Curve[] { boundary, innerA, innerB },
                    Point3d.Unset,
                    center,
                    LoftType.Normal,
                    closed: false,
                    tolerance),
                out _);
        }
        finally
        {
            innerA.Dispose();
            innerB.Dispose();
        }
    }

    private static BrepEdge? FindSeedBoundaryEdge(Brep seed, Curve boundary, double tolerance)
    {
        BrepEdge? best = null;
        var bestDeviation = double.MaxValue;
        foreach (var edge in seed.Edges)
        {
            if (!edge.IsClosed || !BoundaryMatchVerifier.IsNaturalBoundary(edge))
            {
                continue;
            }

            if (!Curve.GetDistancesBetweenCurves(
                    edge,
                    boundary,
                    Math.Max(tolerance * 0.1, 1e-9),
                    out var maximumDistance,
                    out _,
                    out _,
                    out _,
                    out _,
                    out _))
            {
                continue;
            }

            if (maximumDistance < bestDeviation)
            {
                bestDeviation = maximumDistance;
                best = edge;
            }
        }

        return bestDeviation <= Math.Max(tolerance * 2.0, 1e-8) ? best : null;
    }

    private static bool ProveJoinedCapBoundary(
        Brep joinedResult,
        Brep matchedCap,
        IReadOnlyList<BrepEdge> targetEdges,
        CandidateBuildSettings settings,
        double absoluteTolerance,
        double angleToleranceRadians,
        out int joinedSeamCount,
        out string message)
    {
        joinedSeamCount = 0;
        message = "The joined result could not prove the cap-to-context seam.";

        var capFaceIndices = new HashSet<int>();
        foreach (var capFace in matchedCap.Faces)
        {
            using var capSurface = capFace.DuplicateSurface();
            if (capSurface is null)
            {
                message = "The matched cap has no stable underlying surface for Join verification.";
                return false;
            }

            var matchingFaceIndex = -1;
            foreach (var resultFace in joinedResult.Faces)
            {
                using var resultSurface = resultFace.DuplicateSurface();
                if (resultSurface is null
                    || !GeometryBase.GeometryEquals(capSurface, resultSurface))
                {
                    continue;
                }

                if (matchingFaceIndex >= 0)
                {
                    message = "The matched cap face is ambiguous inside the joined proof Brep.";
                    return false;
                }

                matchingFaceIndex = resultFace.FaceIndex;
            }

            if (matchingFaceIndex < 0 || !capFaceIndices.Add(matchingFaceIndex))
            {
                message = "The matched cap face was not preserved uniquely inside the joined proof Brep.";
                return false;
            }
        }

        if (capFaceIndices.Count == 0)
        {
            message = "The joined proof Brep contains no identifiable matched-cap face.";
            return false;
        }

        var seamEdges = new List<BrepEdge>();
        foreach (var edge in joinedResult.Edges)
        {
            var adjacentFaces = edge.AdjacentFaces();
            var touchesCap = adjacentFaces.Any(capFaceIndices.Contains);
            if (!touchesCap)
            {
                continue;
            }

            if (edge.Valence == EdgeAdjacency.Naked)
            {
                if (edge.GetLength() > absoluteTolerance + 1e-12)
                {
                    message = "The joined result still has a non-degenerate naked boundary on the matched cap.";
                    return false;
                }

                continue;
            }

            var touchesContext = adjacentFaces.Any(faceIndex => !capFaceIndices.Contains(faceIndex));
            if (touchesContext
                && (edge.Valence != EdgeAdjacency.Interior || adjacentFaces.Length != 2))
            {
                message = "A cap-to-context edge is non-manifold or does not have exactly two adjacent faces.";
                return false;
            }

            if (edge.Valence == EdgeAdjacency.Interior && touchesContext)
            {
                seamEdges.Add(edge);
            }
        }

        if (seamEdges.Count == 0)
        {
            message = "The joined result contains no interior edge between the matched cap and its context.";
            return false;
        }

        if (settings.Continuity != MatchContinuityLevel.Position
            && seamEdges.Any(edge => !edge.IsSmoothManifoldEdge(angleToleranceRadians)))
        {
            message = "The joined cap seam is not a smooth manifold edge at the document angle tolerance.";
            return false;
        }

        var seamCopies = seamEdges.Select(edge => edge.DuplicateCurve()).ToList();
        var targetCopies = targetEdges.Select(edge => edge.DuplicateCurve()).ToList();
        Curve[]? joinedSeams = null;
        Curve[]? joinedTargets = null;
        try
        {
            joinedSeams = Curve.JoinCurves(seamCopies, absoluteTolerance, false);
            joinedTargets = Curve.JoinCurves(targetCopies, absoluteTolerance, false);
            if (joinedSeams is null
                || joinedSeams.Length != 1
                || !joinedSeams[0].IsClosed
                || joinedTargets is null
                || joinedTargets.Length != 1
                || !joinedTargets[0].IsClosed)
            {
                message = "The joined cap seam and selected target edges do not each form one closed loop.";
                return false;
            }

            var measurementTolerance = Math.Max(absoluteTolerance * 0.1, 1e-9);
            if (!Curve.GetDistancesBetweenCurves(
                    joinedSeams[0],
                    joinedTargets[0],
                    measurementTolerance,
                    out var forwardGap,
                    out _,
                    out _,
                    out _,
                    out _,
                    out _)
                || !Curve.GetDistancesBetweenCurves(
                    joinedTargets[0],
                    joinedSeams[0],
                    measurementTolerance,
                    out var reverseGap,
                    out _,
                    out _,
                    out _,
                    out _,
                    out _))
            {
                message = "Rhino could not measure the joined seam against the selected target loop.";
                return false;
            }

            var maximumGap = Math.Max(forwardGap, reverseGap);
            if (double.IsNaN(maximumGap) || double.IsInfinity(maximumGap)
                || maximumGap > absoluteTolerance + 1e-12)
            {
                message = "The joined cap seam is outside document absolute tolerance from the selected target loop: "
                    + maximumGap.ToString("G6", CultureInfo.InvariantCulture) + ".";
                return false;
            }

            joinedSeamCount = targetEdges.Count;
            message = "The cap-to-context boundary is one closed joined seam within document tolerance.";
            return true;
        }
        finally
        {
            foreach (var curve in seamCopies)
            {
                curve.Dispose();
            }

            foreach (var curve in targetCopies)
            {
                curve.Dispose();
            }

            if (joinedSeams is not null)
            {
                foreach (var curve in joinedSeams)
                {
                    curve?.Dispose();
                }
            }

            if (joinedTargets is not null)
            {
                foreach (var curve in joinedTargets)
                {
                    curve?.Dispose();
                }
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

        return reference.Edge()?.DuplicateCurve()
            ?? (reference.Geometry() as Curve)?.DuplicateCurve();
    }

    private static OrderedCurveLoop? OrderClosedEdgeLoop(
        IReadOnlyList<Curve> curves,
        double tolerance,
        out int reversedCurveCount)
    {
        reversedCurveCount = 0;
        if (curves.Count < 2 || curves.Count > CandidateConstructionPolicy.MaximumBoundaryMatchEdgeCount)
        {
            return null;
        }

        var unused = new List<(Curve Curve, int SourceIndex)>();
        for (var index = 1; index < curves.Count; index++)
        {
            unused.Add((curves[index], index));
        }

        var orderedCurves = new List<Curve>(curves.Count) { curves[0] };
        var sourceIndices = new List<int>(curves.Count) { 0 };
        while (unused.Count > 0)
        {
            var currentEnd = orderedCurves[orderedCurves.Count - 1].PointAtEnd;
            var nextIndex = -1;
            var reverse = false;

            for (var index = 0; index < unused.Count; index++)
            {
                if (currentEnd.DistanceTo(unused[index].Curve.PointAtStart) <= tolerance)
                {
                    nextIndex = index;
                    break;
                }

                if (currentEnd.DistanceTo(unused[index].Curve.PointAtEnd) <= tolerance)
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
                if (!next.Curve.Reverse())
                {
                    return null;
                }

                reversedCurveCount++;
            }

            orderedCurves.Add(next.Curve);
            sourceIndices.Add(next.SourceIndex);
        }

        return orderedCurves[orderedCurves.Count - 1].PointAtEnd
                .DistanceTo(orderedCurves[0].PointAtStart) <= tolerance
            ? new OrderedCurveLoop(orderedCurves, sourceIndices)
            : null;
    }

    private static bool IsBoundedValidResult(Brep? candidate)
    {
        return candidate is not null
            && candidate.IsValid
            && candidate.Faces.Count > 0
            && candidate.Faces.Count <= MaximumResultFaces
            && candidate.Edges.Count <= MaximumResultEdges;
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

    private sealed class OrderedCurveLoop
    {
        public OrderedCurveLoop(IReadOnlyList<Curve> curves, IReadOnlyList<int> sourceIndices)
        {
            Curves = curves;
            SourceIndices = sourceIndices;
        }

        public IReadOnlyList<Curve> Curves { get; }

        public IReadOnlyList<int> SourceIndices { get; }
    }

    private sealed class BoundaryContext : IDisposable
    {
        public BoundaryContext(
            Brep shell,
            IReadOnlyList<BrepEdge> targetEdges,
            IReadOnlyList<Guid> parentObjectIds)
        {
            Shell = shell;
            TargetEdges = targetEdges;
            ParentObjectIds = parentObjectIds;
        }

        public Brep Shell { get; }

        public IReadOnlyList<BrepEdge> TargetEdges { get; }

        public IReadOnlyList<Guid> ParentObjectIds { get; }

        public void Dispose()
        {
            Shell.Dispose();
        }
    }
}
