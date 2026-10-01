using System;
using SmartSkin.Core.Construction;
using SmartSkin.Core.Preflight;
using SmartSkin.Core.Routing;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class CandidateConstructionPolicyTests
{
    private readonly GeometryPreflightAnalyzer _preflight = new GeometryPreflightAnalyzer();
    private readonly SurfaceStrategyRouter _router = new SurfaceStrategyRouter();
    private readonly CandidateConstructionPolicy _policy = new CandidateConstructionPolicy();

    [Fact]
    public void Evaluate_PlanarBoundary_IsReady()
    {
        var snapshots = new[] { ClosedCurve("boundary", Point(0.0, 0.0), 4, isPlanar: true) };

        var plan = Evaluate(snapshots);

        Assert.True(plan.IsReady);
        Assert.Equal(SurfaceStrategy.PlanarSrf, plan.Strategy);
        Assert.Equal(CandidateConstructionCodes.Ready, plan.Code);
        Assert.Equal(1, plan.CurveCount);
        Assert.Equal(4, plan.TotalSpanCount);
    }

    [Fact]
    public void Evaluate_FourCurveBoundary_IsReadyForEdgeSrf()
    {
        var snapshots = new[]
        {
            OpenCurve("bottom", Point(0.0, 0.0), Point(10.0, 0.0)),
            OpenCurve("right", Point(10.0, 0.0), Point(10.0, 10.0)),
            OpenCurve("top", Point(10.0, 10.0), Point(0.0, 10.0)),
            OpenCurve("left", Point(0.0, 10.0), Point(0.0, 0.0))
        };

        var plan = Evaluate(snapshots);

        Assert.True(plan.IsReady);
        Assert.Equal(SurfaceStrategy.EdgeSrf, plan.Strategy);
        Assert.Equal("EDGE_SRF", plan.StrategyToken);
    }

    [Fact]
    public void Evaluate_TwoDisconnectedSections_IsReadyForLoft()
    {
        var snapshots = new[]
        {
            ClosedCurve("section-a", Point(0.0, 0.0), 4, isPlanar: true),
            ClosedCurve("section-b", Point(0.0, 10.0), 4, isPlanar: true)
        };

        var plan = Evaluate(snapshots);

        Assert.True(plan.IsReady);
        Assert.Equal(SurfaceStrategy.Loft, plan.Strategy);
    }

    [Fact]
    public void Evaluate_ThreeSections_BlocksUntilSectionSortingExists()
    {
        var snapshots = new[]
        {
            ClosedCurve("section-a", Point(0.0, 0.0), 4, isPlanar: true),
            ClosedCurve("section-b", Point(0.0, 10.0), 4, isPlanar: true),
            ClosedCurve("section-c", Point(0.0, 20.0), 4, isPlanar: true)
        };

        var plan = Evaluate(snapshots);

        Assert.False(plan.IsReady);
        Assert.Equal(SurfaceStrategy.Loft, plan.Strategy);
        Assert.Equal(CandidateConstructionCodes.LoftTwoSectionsOnly, plan.Code);
    }

    [Fact]
    public void Evaluate_ReviewRoute_IsBlockedBeforeConstruction()
    {
        var snapshots = new[]
        {
            OpenCurve("a", Point(0.0, 0.0), Point(10.0, 0.0)),
            OpenCurve("b", Point(10.05, 0.0), Point(20.0, 0.0))
        };

        var plan = Evaluate(snapshots);

        Assert.False(plan.IsReady);
        Assert.Equal(CandidateConstructionCodes.RouteNotReady, plan.Code);
    }

    [Fact]
    public void Evaluate_PatchPrimary_IsExplicitlyUnsupported()
    {
        var snapshots = new[] { ClosedCurve("non-planar", Point(0.0, 0.0), 4, isPlanar: false) };

        var plan = Evaluate(snapshots);

        Assert.False(plan.IsReady);
        Assert.Equal(SurfaceStrategy.Patch, plan.Strategy);
        Assert.Equal(CandidateConstructionCodes.StrategyUnsupported, plan.Code);
    }

    [Fact]
    public void Evaluate_SelectionAboveConstructionCurveLimit_IsBlocked()
    {
        var snapshots = new[]
        {
            OpenCurve("a", Point(0.0, 0.0), Point(5.0, 0.0)),
            OpenCurve("b", Point(0.0, 10.0), Point(5.0, 10.0)),
            OpenCurve("c", Point(0.0, 20.0), Point(5.0, 20.0)),
            OpenCurve("d", Point(0.0, 30.0), Point(5.0, 30.0)),
            OpenCurve("e", Point(0.0, 40.0), Point(5.0, 40.0))
        };

        var plan = Evaluate(snapshots);

        Assert.False(plan.IsReady);
        Assert.Equal(CandidateConstructionCodes.CurveLimit, plan.Code);
    }

    [Fact]
    public void Evaluate_CombinedSpansAboveConstructionLimit_IsBlocked()
    {
        var snapshots = new[]
        {
            OpenCurve("section-a", Point(0.0, 0.0), Point(10.0, 0.0), spanCount: 33),
            OpenCurve("section-b", Point(0.0, 10.0), Point(10.0, 10.0), spanCount: 33)
        };

        var plan = Evaluate(snapshots);

        Assert.False(plan.IsReady);
        Assert.Equal(CandidateConstructionCodes.SpanLimit, plan.Code);
        Assert.Equal(66, plan.TotalSpanCount);
    }

    private CandidateConstructionPlan Evaluate(GeometrySnapshot[] snapshots)
    {
        var preflight = _preflight.Analyze(snapshots, new PreflightOptions(0.01));
        var route = _router.Route(preflight);
        return _policy.Evaluate(route, snapshots);
    }

    private static GeometrySnapshot ClosedCurve(
        string label,
        Point3Value origin,
        int spanCount,
        bool isPlanar)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Curve,
            true,
            new Bounds3Value(
                origin,
                new Point3Value(origin.X + 10.0, origin.Y + 10.0, origin.Z + (isPlanar ? 0.0 : 3.0))),
            length: 40.0,
            isClosed: true,
            isPlanar: isPlanar,
            degree: 3,
            spanCount: spanCount);
    }

    private static GeometrySnapshot OpenCurve(
        string label,
        Point3Value start,
        Point3Value end,
        int spanCount = 1)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Curve,
            true,
            new Bounds3Value(
                new Point3Value(
                    Math.Min(start.X, end.X),
                    Math.Min(start.Y, end.Y),
                    Math.Min(start.Z, end.Z)),
                new Point3Value(
                    Math.Max(start.X, end.X),
                    Math.Max(start.Y, end.Y),
                    Math.Max(start.Z, end.Z))),
            length: start.DistanceTo(end),
            isClosed: false,
            startPoint: start,
            endPoint: end,
            isPlanar: true,
            degree: 3,
            spanCount: spanCount);
    }

    private static Point3Value Point(double x, double y, double z = 0.0)
    {
        return new Point3Value(x, y, z);
    }
}
