using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using SmartSkin.Core.Preflight;
using SmartSkin.Core.Routing;

namespace SmartSkin.Core.Construction;

public static class CandidateConstructionCodes
{
    public const string Ready = "P03_READY";
    public const string RouteNotReady = "P03_ROUTE_NOT_READY";
    public const string StrategyUnsupported = "P03_STRATEGY_UNSUPPORTED";
    public const string NonCurveInput = "P03_NON_CURVE_INPUT";
    public const string CurveLimit = "P03_CURVE_LIMIT";
    public const string SpanLimit = "P03_SPAN_LIMIT";
    public const string CurveAnalysisIncomplete = "P03_CURVE_ANALYSIS_INCOMPLETE";
    public const string InvalidPlanarInput = "P03_INVALID_PLANAR_INPUT";
    public const string InvalidEdgeInput = "P03_INVALID_EDGE_INPUT";
    public const string LoftTwoSectionsOnly = "P03_LOFT_TWO_SECTIONS_ONLY";
    public const string LoftClosureMismatch = "P03_LOFT_CLOSURE_MISMATCH";
}

public sealed class CandidateConstructionPlan
{
    internal CandidateConstructionPlan(
        bool isReady,
        SurfaceStrategy? strategy,
        string code,
        string message,
        int curveCount,
        int totalSpanCount)
    {
        IsReady = isReady;
        Strategy = strategy;
        Code = code ?? throw new ArgumentNullException(nameof(code));
        Message = message ?? throw new ArgumentNullException(nameof(message));
        CurveCount = curveCount;
        TotalSpanCount = totalSpanCount;
    }

    public bool IsReady { get; }

    public SurfaceStrategy? Strategy { get; }

    public string StrategyToken => Strategy.HasValue
        ? RoutingTokens.Strategy(Strategy.Value)
        : "NONE";

    public string Code { get; }

    public string Message { get; }

    public int CurveCount { get; }

    public int TotalSpanCount { get; }

    public string ToDisplayLine()
    {
        return $"Construction: {(IsReady ? "READY" : "BLOCKED")}"
            + $"; strategy={StrategyToken}"
            + $"; code={Code}"
            + $"; curves={CurveCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; spans={TotalSpanCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; {Message}";
    }
}

public sealed class CandidateConstructionPolicy
{
    public const int MaximumCurveCount = 4;
    public const int MaximumTotalSpanCount = 64;

    public CandidateConstructionPlan Evaluate(
        SurfaceRouteReport route,
        IReadOnlyList<GeometrySnapshot> snapshots)
    {
        if (route is null)
        {
            throw new ArgumentNullException(nameof(route));
        }

        if (snapshots is null)
        {
            throw new ArgumentNullException(nameof(snapshots));
        }

        var primary = route.PrimaryStrategy;
        var curves = snapshots
            .Where(snapshot => snapshot.Kind == GeometryKind.Curve || snapshot.Kind == GeometryKind.BrepEdge)
            .ToArray();

        if (route.Status != RouteStatus.Ready || !primary.HasValue)
        {
            return Blocked(
                primary,
                CandidateConstructionCodes.RouteNotReady,
                "Only a READY route can enter native candidate construction.",
                curves);
        }

        if (primary.Value != SurfaceStrategy.PlanarSrf
            && primary.Value != SurfaceStrategy.EdgeSrf
            && primary.Value != SurfaceStrategy.Loft)
        {
            return Blocked(
                primary,
                CandidateConstructionCodes.StrategyUnsupported,
                "P03 constructs only PlanarSrf, EdgeSrf, and Loft candidates.",
                curves);
        }

        if (curves.Length != snapshots.Count)
        {
            return Blocked(
                primary,
                CandidateConstructionCodes.NonCurveInput,
                "Candidate construction accepts only top-level curves and Brep edge sub-objects.",
                curves);
        }

        if (curves.Length > MaximumCurveCount)
        {
            return Blocked(
                primary,
                CandidateConstructionCodes.CurveLimit,
                $"Curve count exceeds the P03 construction limit of {MaximumCurveCount}.",
                curves);
        }

        if (curves.Any(curve => curve.IsValid != true || !curve.SpanCount.HasValue || curve.SpanCount.Value < 1))
        {
            return Blocked(
                primary,
                CandidateConstructionCodes.CurveAnalysisIncomplete,
                "Every construction curve must be valid and have a known positive span count.",
                curves);
        }

        var totalSpans = SumSpans(curves);
        if (totalSpans > MaximumTotalSpanCount)
        {
            return new CandidateConstructionPlan(
                false,
                primary,
                CandidateConstructionCodes.SpanLimit,
                $"Combined curve spans exceed the P03 construction limit of {MaximumTotalSpanCount}.",
                curves.Length,
                totalSpans);
        }

        switch (primary.Value)
        {
            case SurfaceStrategy.PlanarSrf:
                if (curves.Length != 1 || curves[0].IsClosed != true || curves[0].IsPlanar != true)
                {
                    return new CandidateConstructionPlan(
                        false,
                        primary,
                        CandidateConstructionCodes.InvalidPlanarInput,
                        "PlanarSrf requires exactly one closed curve proven planar by preflight.",
                        curves.Length,
                        totalSpans);
                }

                break;

            case SurfaceStrategy.EdgeSrf:
                if (curves.Length < 2
                    || curves.Length > 4
                    || curves.Any(curve => curve.IsClosed != false))
                {
                    return new CandidateConstructionPlan(
                        false,
                        primary,
                        CandidateConstructionCodes.InvalidEdgeInput,
                        "EdgeSrf requires two to four open curves in the verified closed-loop route.",
                        curves.Length,
                        totalSpans);
                }

                break;

            case SurfaceStrategy.Loft:
                if (curves.Length != 2)
                {
                    return new CandidateConstructionPlan(
                        false,
                        primary,
                        CandidateConstructionCodes.LoftTwoSectionsOnly,
                        "P03 limits Loft to exactly two sections; section sorting for larger sets is not implemented.",
                        curves.Length,
                        totalSpans);
                }

                if (curves[0].IsClosed != curves[1].IsClosed)
                {
                    return new CandidateConstructionPlan(
                        false,
                        primary,
                        CandidateConstructionCodes.LoftClosureMismatch,
                        "Both Loft sections must be either open or closed.",
                        curves.Length,
                        totalSpans);
                }

                break;

            default:
                throw new ArgumentOutOfRangeException();
        }

        return new CandidateConstructionPlan(
            true,
            primary,
            CandidateConstructionCodes.Ready,
            "One disposable candidate may be built for preview; source geometry remains unchanged.",
            curves.Length,
            totalSpans);
    }

    private static CandidateConstructionPlan Blocked(
        SurfaceStrategy? strategy,
        string code,
        string message,
        IReadOnlyCollection<GeometrySnapshot> curves)
    {
        return new CandidateConstructionPlan(
            false,
            strategy,
            code,
            message,
            curves.Count,
            SumSpans(curves));
    }

    private static int SumSpans(IEnumerable<GeometrySnapshot> curves)
    {
        var total = 0;
        foreach (var curve in curves)
        {
            if (!curve.SpanCount.HasValue)
            {
                continue;
            }

            if (curve.SpanCount.Value > int.MaxValue - total)
            {
                return int.MaxValue;
            }

            total += curve.SpanCount.Value;
        }

        return total;
    }
}
