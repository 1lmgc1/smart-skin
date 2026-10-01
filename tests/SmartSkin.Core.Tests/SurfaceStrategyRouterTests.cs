using System;
using System.Linq;
using System.Reflection;
using SmartSkin.Core;
using SmartSkin.Core.Preflight;
using SmartSkin.Core.Routing;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class SurfaceStrategyRouterTests
{
    private readonly GeometryPreflightAnalyzer _preflightAnalyzer = new GeometryPreflightAnalyzer();
    private readonly SurfaceStrategyRouter _router = new SurfaceStrategyRouter();

    [Fact]
    public void Route_SinglePlanarClosedCurve_PrefersPlanarSrf()
    {
        var report = Route(ClosedCurve("boundary", isPlanar: true));

        Assert.Equal(RouteStatus.Ready, report.Status);
        Assert.Equal(TopologyKind.SingleClosedBoundary, report.Topology.Kind);
        AssertPrimary(report, SurfaceStrategy.PlanarSrf);
        Assert.Equal(new[] { SurfaceStrategy.PlanarSrf, SurfaceStrategy.Patch }, report.Candidates.Select(item => item.Strategy));
    }

    [Fact]
    public void Route_SingleNonPlanarClosedCurve_PrefersPatch()
    {
        var report = Route(ClosedCurve("boundary", isPlanar: false));

        Assert.Equal(RouteStatus.Ready, report.Status);
        Assert.Equal(TopologyKind.SingleClosedBoundary, report.Topology.Kind);
        AssertPrimary(report, SurfaceStrategy.Patch);
    }

    [Fact]
    public void Route_FourCurveClosedLoop_PrefersEdgeSrf()
    {
        var report = Route(
            OpenCurve("bottom", Point(0.0, 0.0), Point(10.0, 0.0)),
            OpenCurve("right", Point(10.0, 0.0), Point(10.0, 10.0)),
            OpenCurve("top", Point(10.0, 10.0), Point(0.0, 10.0)),
            OpenCurve("left", Point(0.0, 10.0), Point(0.0, 0.0)));

        Assert.Equal(RouteStatus.Ready, report.Status);
        Assert.Equal(TopologyKind.ClosedBoundaryLoop, report.Topology.Kind);
        Assert.Equal(4, report.Topology.EndpointNodeCount);
        Assert.Equal(1, report.Topology.ConnectedComponentCount);
        Assert.Equal(4, report.Topology.ThroughNodeCount);
        AssertPrimary(report, SurfaceStrategy.EdgeSrf);
    }

    [Fact]
    public void Route_FiveCurveClosedLoop_UsesPatchAndRequiresReview()
    {
        var report = Route(
            OpenCurve("a", Point(0.0, 0.0), Point(4.0, 0.0)),
            OpenCurve("b", Point(4.0, 0.0), Point(6.0, 3.0)),
            OpenCurve("c", Point(6.0, 3.0), Point(3.0, 6.0)),
            OpenCurve("d", Point(3.0, 6.0), Point(0.0, 3.0)),
            OpenCurve("e", Point(0.0, 3.0), Point(0.0, 0.0)));

        Assert.Equal(RouteStatus.Review, report.Status);
        Assert.Equal(TopologyKind.ClosedBoundaryLoop, report.Topology.Kind);
        AssertPrimary(report, SurfaceStrategy.Patch);
        Assert.DoesNotContain(report.Candidates, item => item.Strategy == SurfaceStrategy.EdgeSrf);
    }

    [Fact]
    public void Route_DisconnectedOpenCurves_PrefersLoft()
    {
        var report = Route(
            OpenCurve("section-a", Point(0.0, 0.0), Point(10.0, 0.0)),
            OpenCurve("section-b", Point(0.0, 5.0), Point(10.0, 5.0)));

        Assert.Equal(RouteStatus.Ready, report.Status);
        Assert.Equal(TopologyKind.SectionSet, report.Topology.Kind);
        Assert.Equal(2, report.Topology.ConnectedComponentCount);
        AssertPrimary(report, SurfaceStrategy.Loft);
    }

    [Fact]
    public void Route_OpenChain_IsBlockedWithNoCandidate()
    {
        var report = Route(
            OpenCurve("a", Point(0.0, 0.0), Point(5.0, 0.0)),
            OpenCurve("b", Point(5.0, 0.0), Point(10.0, 3.0)),
            OpenCurve("c", Point(10.0, 3.0), Point(15.0, 3.0)));

        Assert.Equal(RouteStatus.Blocked, report.Status);
        Assert.Equal(TopologyKind.OpenChain, report.Topology.Kind);
        Assert.Null(report.PrimaryStrategy);
        Assert.Empty(report.Candidates);
        Assert.Contains(report.Notes, note => note.Contains("boundary fragment"));
    }

    [Fact]
    public void Route_BranchedFrame_PrefersPatchAndRequiresReview()
    {
        var origin = Point(0.0, 0.0);
        var report = Route(
            OpenCurve("a", origin, Point(10.0, 0.0)),
            OpenCurve("b", origin, Point(0.0, 10.0)),
            OpenCurve("c", origin, Point(-10.0, 0.0)));

        Assert.Equal(RouteStatus.Review, report.Status);
        Assert.Equal(TopologyKind.BranchedFrame, report.Topology.Kind);
        Assert.Equal(1, report.Topology.JunctionNodeCount);
        AssertPrimary(report, SurfaceStrategy.Patch);
    }

    [Fact]
    public void Route_NearGap_KeepsCandidateButRequiresReview()
    {
        var report = Route(
            OpenCurve("section-a", Point(0.0, 0.0), Point(10.0, 0.0)),
            OpenCurve("section-b", Point(10.05, 0.0), Point(20.0, 0.0)));

        Assert.Equal(RouteStatus.Review, report.Status);
        Assert.Equal(TopologyKind.SectionSet, report.Topology.Kind);
        AssertPrimary(report, SurfaceStrategy.Loft);
        Assert.Contains(report.Notes, note => note.Contains(PreflightIssueCodes.NearGap));
    }

    [Fact]
    public void Route_CurveAndPoint_PrefersPatchAndRequiresReview()
    {
        var guidePoint = new GeometrySnapshot(
            "guide-point",
            GeometryKind.Point,
            true,
            new Bounds3Value(Point(5.0, 5.0), Point(5.0, 5.0)));

        var report = Route(ClosedCurve("boundary", isPlanar: true), guidePoint);

        Assert.Equal(RouteStatus.Review, report.Status);
        Assert.Equal(TopologyKind.PointGuidedFrame, report.Topology.Kind);
        AssertPrimary(report, SurfaceStrategy.Patch);
    }

    [Fact]
    public void Route_SurfaceContextOnly_IsBlocked()
    {
        var surface = new GeometrySnapshot(
            "surface",
            GeometryKind.Surface,
            true,
            Bounds(0.0, 0.0, 0.0, 10.0, 10.0, 2.0),
            isPlanar: false,
            degree: 3,
            spanCount: 4);

        var report = Route(surface);

        Assert.Equal(RouteStatus.Blocked, report.Status);
        Assert.Equal(TopologyKind.SurfaceContextOnly, report.Topology.Kind);
        Assert.Empty(report.Candidates);
    }

    [Fact]
    public void Route_BlockingPreflightError_ReturnsNoCandidate()
    {
        var invalid = new GeometrySnapshot(
            "invalid-boundary",
            GeometryKind.Curve,
            false,
            Bounds(0.0, 0.0, 0.0, 10.0, 10.0, 0.0),
            length: 40.0,
            isClosed: true,
            isPlanar: true,
            degree: 3,
            spanCount: 4);

        var report = Route(invalid);

        Assert.Equal(RouteStatus.Blocked, report.Status);
        Assert.Empty(report.Candidates);
        Assert.Contains(report.Notes, note => note.Contains(PreflightIssueCodes.InvalidGeometry));
    }

    [Fact]
    public void MachineLine_IsStableAndIncludesRouteAndDocumentInvariant()
    {
        var report = Route(ClosedCurve("boundary", isPlanar: true));
        var identity = BuildIdentity.FromAssembly(Assembly.GetExecutingAssembly());

        var line = report.ToMachineLine(identity, 12, 12);

        Assert.StartsWith("SMARTSKIN_P03F1 PASS", line);
        Assert.Contains("route_status=READY", line);
        Assert.Contains("topology=SINGLE_CLOSED_BOUNDARY", line);
        Assert.Contains("primary=PLANAR_SRF", line);
        Assert.EndsWith("objects=12->12", line);
    }

    private SurfaceRouteReport Route(params GeometrySnapshot[] snapshots)
    {
        var preflight = _preflightAnalyzer.Analyze(
            snapshots,
            new PreflightOptions(0.01));
        return _router.Route(preflight);
    }

    private static void AssertPrimary(SurfaceRouteReport report, SurfaceStrategy expected)
    {
        Assert.True(report.PrimaryStrategy.HasValue);
        Assert.Equal(expected, report.PrimaryStrategy.Value);
    }

    private static GeometrySnapshot ClosedCurve(string label, bool isPlanar)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Curve,
            true,
            Bounds(0.0, 0.0, 0.0, 10.0, 10.0, isPlanar ? 0.0 : 3.0),
            length: 40.0,
            isClosed: true,
            isPlanar: isPlanar,
            degree: 3,
            spanCount: 4);
    }

    private static GeometrySnapshot OpenCurve(
        string label,
        Point3Value start,
        Point3Value end)
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
            degree: 1,
            spanCount: 1);
    }

    private static Point3Value Point(double x, double y, double z = 0.0)
    {
        return new Point3Value(x, y, z);
    }

    private static Bounds3Value Bounds(
        double minX,
        double minY,
        double minZ,
        double maxX,
        double maxY,
        double maxZ)
    {
        return new Bounds3Value(
            new Point3Value(minX, minY, minZ),
            new Point3Value(maxX, maxY, maxZ));
    }
}
