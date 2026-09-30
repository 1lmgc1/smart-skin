using System.Linq;
using System.Reflection;
using SmartSkin.Core;
using SmartSkin.Core.Preflight;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class GeometryPreflightAnalyzerTests
{
    private readonly GeometryPreflightAnalyzer _analyzer = new GeometryPreflightAnalyzer();

    [Fact]
    public void Analyze_ValidClosedCurve_IsReady()
    {
        var curve = CurveSnapshot(
            "curve-1",
            new Point3Value(0.0, 0.0, 0.0),
            new Point3Value(10.0, 10.0, 0.0),
            length: 40.0,
            isClosed: true);

        var report = _analyzer.Analyze(
            new[] { curve },
            new PreflightOptions(0.001));

        Assert.Equal(PreflightStatus.Ready, report.Status);
        Assert.Equal(1, report.SelectedCount);
        Assert.Equal(1, report.ValidCount);
        Assert.Equal(0, report.WarningCount);
        Assert.Equal(0, report.ErrorCount);
        Assert.Empty(report.Issues);
    }

    [Fact]
    public void Analyze_InvalidShortCurveAndLargeTolerance_IsBlocked()
    {
        var curve = new GeometrySnapshot(
            "curve-bad",
            GeometryKind.Curve,
            false,
            Bounds(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            length: 0.005,
            isClosed: false,
            startPoint: new Point3Value(0.0, 0.0, 0.0),
            endPoint: new Point3Value(0.005, 0.0, 0.0),
            spanCount: 250);

        var report = _analyzer.Analyze(
            new[] { curve },
            new PreflightOptions(0.02));

        Assert.Equal(PreflightStatus.Blocked, report.Status);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.InvalidGeometry);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.ShortCurve);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.HighSpanCount);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.ToleranceLarge);
    }

    [Fact]
    public void Analyze_OpenCurvesWithNearEndpoint_ReportsGap()
    {
        var first = CurveSnapshot(
            "curve-a",
            new Point3Value(0.0, 0.0, 0.0),
            new Point3Value(10.0, 0.0, 0.0),
            length: 10.0,
            isClosed: false);
        var second = CurveSnapshot(
            "curve-b",
            new Point3Value(10.05, 0.0, 0.0),
            new Point3Value(20.0, 0.0, 0.0),
            length: 9.95,
            isClosed: false);

        var report = _analyzer.Analyze(
            new[] { first, second },
            new PreflightOptions(0.01));

        Assert.Equal(PreflightStatus.Warning, report.Status);
        Assert.Equal(1, report.NearGapCount);
        Assert.Equal(0, report.ConnectedCurvePairCount);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.NearGap);
    }

    [Fact]
    public void Analyze_BrepWithNakedAndShortEdges_ReportsBoth()
    {
        var brep = new GeometrySnapshot(
            "brep-1",
            GeometryKind.Brep,
            true,
            Bounds(0.0, 0.0, 0.0, 5.0, 5.0, 5.0),
            faceCount: 4,
            edgeCount: 12,
            nakedEdgeCount: 2,
            shortEdgeCount: 1);

        var report = _analyzer.Analyze(
            new[] { brep },
            new PreflightOptions(0.001));

        Assert.Equal(PreflightStatus.Warning, report.Status);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.NakedEdges);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.ShortBrepEdges);
    }

    [Fact]
    public void Analyze_ValidExtrusion_IsReadyAndRetainsItsType()
    {
        var extrusion = new GeometrySnapshot(
            "extrusion-1",
            GeometryKind.Extrusion,
            true,
            Bounds(0.0, 0.0, 0.0, 100.0, 100.0, 100.0),
            faceCount: 6,
            edgeCount: 12,
            nakedEdgeCount: 0,
            shortEdgeCount: 0);

        var report = _analyzer.Analyze(
            new[] { extrusion },
            new PreflightOptions(0.01));

        Assert.Equal(PreflightStatus.Ready, report.Status);
        Assert.Equal(1, report.TypeCounts[GeometryKind.Extrusion]);
        Assert.Contains(report.ToDisplayLines(), line => line == "Types: Extrusion=1");
        Assert.Contains(report.ToDisplayLines(), line => line.Contains("Extrusion | valid | faces=6 | edges=12"));
    }

    [Fact]
    public void Analyze_SafetyLimitedSnapshot_DoesNotClaimValidity()
    {
        var curve = new GeometrySnapshot(
            "curve-heavy",
            GeometryKind.Curve,
            null,
            Bounds(0.0, 0.0, 0.0, 100.0, 10.0, 0.0),
            isClosed: false,
            startPoint: new Point3Value(0.0, 0.0, 0.0),
            endPoint: new Point3Value(100.0, 0.0, 0.0),
            degree: 3,
            spanCount: 5001,
            analysisLimitReason: "Deep curve checks were skipped by the safety limit.");

        var report = _analyzer.Analyze(
            new[] { curve },
            new PreflightOptions(0.001));

        Assert.Equal(PreflightStatus.Warning, report.Status);
        Assert.Equal(0, report.ValidCount);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.AnalysisLimited);
        Assert.Contains(report.Issues, issue => issue.Code == PreflightIssueCodes.HighSpanCount);
    }

    [Fact]
    public void Analyze_SelectionAboveBound_IsBlockedWithoutDeepChecks()
    {
        var snapshots = new[]
        {
            CurveSnapshot("curve-a", new Point3Value(0.0, 0.0, 0.0), new Point3Value(1.0, 0.0, 0.0), 1.0, false),
            CurveSnapshot("curve-b", new Point3Value(0.0, 1.0, 0.0), new Point3Value(1.0, 1.0, 0.0), 1.0, false)
        };

        var report = _analyzer.Analyze(
            snapshots,
            new PreflightOptions(0.001, maximumItems: 1));

        Assert.Equal(PreflightStatus.Blocked, report.Status);
        Assert.Single(report.Issues);
        Assert.Equal(PreflightIssueCodes.SelectionLimit, report.Issues[0].Code);
    }

    [Fact]
    public void MachineLine_IsStableAndIncludesDocumentInvariant()
    {
        var report = _analyzer.Analyze(
            new[]
            {
                CurveSnapshot(
                    "curve-1",
                    new Point3Value(0.0, 0.0, 0.0),
                    new Point3Value(10.0, 0.0, 0.0),
                    10.0,
                    false)
            },
            new PreflightOptions(0.001));
        var identity = BuildIdentity.FromAssembly(Assembly.GetExecutingAssembly());

        var line = report.ToMachineLine(identity, 35, 35);

        Assert.StartsWith("SMARTSKIN_P01F1 PASS", line);
        Assert.Contains("status=READY", line);
        Assert.Contains("selected=1", line);
        Assert.Contains("valid=1", line);
        Assert.EndsWith("objects=35->35", line);
    }

    [Fact]
    public void DisplayLines_AreBoundedForLargeSelections()
    {
        var snapshots = Enumerable
            .Range(1, 30)
            .Select(index => CurveSnapshot(
                $"curve-{index}",
                new Point3Value(index, 0.0, 0.0),
                new Point3Value(index + 0.5, 0.0, 0.0),
                0.5,
                false))
            .ToArray();

        var report = _analyzer.Analyze(snapshots, new PreflightOptions(0.001));
        var lines = report.ToDisplayLines(maximumItemLines: 4);

        Assert.Contains(lines, line => line.Contains("26 additional item(s) omitted"));
        Assert.True(lines.Count < 20);
    }

    private static GeometrySnapshot CurveSnapshot(
        string label,
        Point3Value start,
        Point3Value end,
        double length,
        bool isClosed)
    {
        return new GeometrySnapshot(
            label,
            GeometryKind.Curve,
            true,
            new Bounds3Value(
                new Point3Value(
                    System.Math.Min(start.X, end.X),
                    System.Math.Min(start.Y, end.Y),
                    System.Math.Min(start.Z, end.Z)),
                new Point3Value(
                    System.Math.Max(start.X, end.X),
                    System.Math.Max(start.Y, end.Y),
                    System.Math.Max(start.Z, end.Z))),
            length: length,
            isClosed: isClosed,
            startPoint: start,
            endPoint: end,
            isPlanar: true,
            degree: 3,
            spanCount: 4);
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
