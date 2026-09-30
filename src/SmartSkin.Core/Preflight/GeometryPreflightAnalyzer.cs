using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SmartSkin.Core.Preflight;

public sealed class GeometryPreflightAnalyzer
{
    public PreflightReport Analyze(IReadOnlyList<GeometrySnapshot> snapshots, PreflightOptions options)
    {
        if (snapshots is null)
        {
            throw new ArgumentNullException(nameof(snapshots));
        }

        if (options is null)
        {
            throw new ArgumentNullException(nameof(options));
        }

        var issueCollector = new IssueCollector(options.MaximumIssues);
        if (snapshots.Count == 0)
        {
            issueCollector.Add(
                PreflightIssueCodes.NoInput,
                PreflightSeverity.Error,
                "No geometry was supplied for analysis.");
            return CreateReport(snapshots, issueCollector, default, options, 0, 0);
        }

        if (snapshots.Count > options.MaximumItems)
        {
            issueCollector.Add(
                PreflightIssueCodes.SelectionLimit,
                PreflightSeverity.Error,
                $"Selection contains {snapshots.Count.ToString(CultureInfo.InvariantCulture)} items; the bounded limit is {options.MaximumItems.ToString(CultureInfo.InvariantCulture)}.");
            return CreateReport(snapshots, issueCollector, CombineBounds(snapshots), options, 0, 0);
        }

        var toleranceIsValid = IsPositiveFinite(options.AbsoluteTolerance);
        if (!toleranceIsValid)
        {
            issueCollector.Add(
                PreflightIssueCodes.InvalidTolerance,
                PreflightSeverity.Error,
                "Document absolute tolerance must be a finite value greater than zero.");
        }

        foreach (var snapshot in snapshots)
        {
            AnalyzeSnapshot(snapshot, options, toleranceIsValid, issueCollector);
        }

        var selectionBounds = CombineBounds(snapshots);
        AnalyzeScale(selectionBounds, options, toleranceIsValid, issueCollector);

        var nearGapCount = 0;
        var connectedCurvePairCount = 0;
        if (toleranceIsValid)
        {
            AnalyzeCurveEndpoints(
                snapshots,
                options,
                issueCollector,
                out nearGapCount,
                out connectedCurvePairCount);
        }

        return CreateReport(
            snapshots,
            issueCollector,
            selectionBounds,
            options,
            nearGapCount,
            connectedCurvePairCount);
    }

    private static void AnalyzeSnapshot(
        GeometrySnapshot snapshot,
        PreflightOptions options,
        bool toleranceIsValid,
        IssueCollector issues)
    {
        if (!string.IsNullOrWhiteSpace(snapshot.SourceProblem))
        {
            issues.Add(
                PreflightIssueCodes.SnapshotFailure,
                PreflightSeverity.Error,
                snapshot.SourceProblem!,
                snapshot.Label);
        }
        else if (snapshot.IsValid == false)
        {
            issues.Add(
                PreflightIssueCodes.InvalidGeometry,
                PreflightSeverity.Error,
                "Rhino reports this geometry as invalid.",
                snapshot.Label);
        }

        if (!string.IsNullOrWhiteSpace(snapshot.AnalysisLimitReason))
        {
            issues.Add(
                PreflightIssueCodes.AnalysisLimited,
                PreflightSeverity.Warning,
                snapshot.AnalysisLimitReason!,
                snapshot.Label);
        }

        if (snapshot.Kind == GeometryKind.Other)
        {
            issues.Add(
                PreflightIssueCodes.UnsupportedGeometry,
                PreflightSeverity.Warning,
                "The selected geometry type has no P01-specific checks.",
                snapshot.Label);
        }

        if (snapshot.Length.HasValue)
        {
            var length = snapshot.Length.Value;
            if (!IsPositiveFinite(length))
            {
                issues.Add(
                    PreflightIssueCodes.DegenerateLength,
                    PreflightSeverity.Error,
                    "Curve length is zero or could not be evaluated.",
                    snapshot.Label);
            }
            else if (toleranceIsValid && length <= options.AbsoluteTolerance)
            {
                var isEdge = snapshot.Kind == GeometryKind.BrepEdge;
                issues.Add(
                    isEdge ? PreflightIssueCodes.ShortEdge : PreflightIssueCodes.ShortCurve,
                    PreflightSeverity.Warning,
                    $"Length {FormatNumber(length)} is not greater than document tolerance {FormatNumber(options.AbsoluteTolerance)}.",
                    snapshot.Label);
            }
        }

        if (snapshot.SpanCount.HasValue && snapshot.SpanCount.Value > options.HighSpanCount)
        {
            issues.Add(
                PreflightIssueCodes.HighSpanCount,
                PreflightSeverity.Warning,
                $"Span count {snapshot.SpanCount.Value.ToString(CultureInfo.InvariantCulture)} exceeds the P01 review threshold {options.HighSpanCount.ToString(CultureInfo.InvariantCulture)}.",
                snapshot.Label);
        }

        if (snapshot.NakedEdgeCount.GetValueOrDefault() > 0)
        {
            issues.Add(
                PreflightIssueCodes.NakedEdges,
                PreflightSeverity.Warning,
                $"Brep has {snapshot.NakedEdgeCount!.Value.ToString(CultureInfo.InvariantCulture)} naked edge(s).",
                snapshot.Label);
        }

        if (snapshot.ShortEdgeCount.GetValueOrDefault() > 0)
        {
            issues.Add(
                PreflightIssueCodes.ShortBrepEdges,
                PreflightSeverity.Warning,
                $"Brep has {snapshot.ShortEdgeCount!.Value.ToString(CultureInfo.InvariantCulture)} edge(s) not longer than document tolerance.",
                snapshot.Label);
        }
    }

    private static void AnalyzeScale(
        Bounds3Value selectionBounds,
        PreflightOptions options,
        bool toleranceIsValid,
        IssueCollector issues)
    {
        var scale = selectionBounds.DiagonalLength;
        if (!IsPositiveFinite(scale))
        {
            issues.Add(
                PreflightIssueCodes.NoScale,
                PreflightSeverity.Warning,
                "Selection has no finite non-zero bounding-box diagonal.");
            return;
        }

        if (!toleranceIsValid)
        {
            return;
        }

        if (options.AbsoluteTolerance >= scale)
        {
            issues.Add(
                PreflightIssueCodes.ToleranceExceedsScale,
                PreflightSeverity.Error,
                $"Document tolerance {FormatNumber(options.AbsoluteTolerance)} is greater than or equal to selection scale {FormatNumber(scale)}.");
            return;
        }

        var ratio = options.AbsoluteTolerance / scale;
        if (ratio >= options.ToleranceToScaleWarningRatio)
        {
            issues.Add(
                PreflightIssueCodes.ToleranceLarge,
                PreflightSeverity.Warning,
                $"Document tolerance is {FormatNumber(ratio * 100.0)}% of selection scale; review units and tolerance before surface operations.");
        }
    }

    private static void AnalyzeCurveEndpoints(
        IReadOnlyList<GeometrySnapshot> snapshots,
        PreflightOptions options,
        IssueCollector issues,
        out int nearGapCount,
        out int connectedCurvePairCount)
    {
        var openCurves = snapshots
            .Where(IsOpenCurveWithFiniteEndpoints)
            .ToArray();
        var nearTolerance = options.AbsoluteTolerance * options.NearGapToleranceMultiplier;

        nearGapCount = 0;
        connectedCurvePairCount = 0;

        for (var firstIndex = 0; firstIndex < openCurves.Length; firstIndex++)
        {
            for (var secondIndex = firstIndex + 1; secondIndex < openCurves.Length; secondIndex++)
            {
                var first = openCurves[firstIndex];
                var second = openCurves[secondIndex];
                var distances = EndpointDistances(first, second);

                if (distances.Any(distance => distance <= options.AbsoluteTolerance))
                {
                    connectedCurvePairCount++;
                }

                var nearDistance = distances
                    .Where(distance => distance > options.AbsoluteTolerance && distance <= nearTolerance)
                    .DefaultIfEmpty(double.NaN)
                    .Min();

                if (!double.IsNaN(nearDistance))
                {
                    nearGapCount++;
                    issues.Add(
                        PreflightIssueCodes.NearGap,
                        PreflightSeverity.Warning,
                        $"Endpoint gap {FormatNumber(nearDistance)} is above tolerance {FormatNumber(options.AbsoluteTolerance)} but within {FormatNumber(options.NearGapToleranceMultiplier)}x tolerance ({first.Label} / {second.Label}).");
                }
            }
        }
    }

    private static bool IsOpenCurveWithFiniteEndpoints(GeometrySnapshot snapshot)
    {
        return (snapshot.Kind == GeometryKind.Curve || snapshot.Kind == GeometryKind.BrepEdge)
            && snapshot.IsClosed == false
            && snapshot.StartPoint.HasValue
            && snapshot.EndPoint.HasValue
            && snapshot.StartPoint.Value.IsFinite
            && snapshot.EndPoint.Value.IsFinite;
    }

    private static double[] EndpointDistances(GeometrySnapshot first, GeometrySnapshot second)
    {
        var firstStart = first.StartPoint!.Value;
        var firstEnd = first.EndPoint!.Value;
        var secondStart = second.StartPoint!.Value;
        var secondEnd = second.EndPoint!.Value;

        return new[]
        {
            firstStart.DistanceTo(secondStart),
            firstStart.DistanceTo(secondEnd),
            firstEnd.DistanceTo(secondStart),
            firstEnd.DistanceTo(secondEnd)
        };
    }

    private static Bounds3Value CombineBounds(IEnumerable<GeometrySnapshot> snapshots)
    {
        var bounds = default(Bounds3Value);
        foreach (var snapshot in snapshots)
        {
            bounds = bounds.Union(snapshot.Bounds);
        }

        return bounds;
    }

    private static PreflightReport CreateReport(
        IReadOnlyList<GeometrySnapshot> snapshots,
        IssueCollector issues,
        Bounds3Value bounds,
        PreflightOptions options,
        int nearGapCount,
        int connectedCurvePairCount)
    {
        return new PreflightReport(
            snapshots,
            issues.Items,
            bounds,
            options.AbsoluteTolerance,
            nearGapCount,
            connectedCurvePairCount,
            issues.SuppressedCount);
    }

    private static bool IsPositiveFinite(double value)
    {
        return value > 0.0 && !double.IsNaN(value) && !double.IsInfinity(value);
    }

    private static string FormatNumber(double value)
    {
        return value.ToString("G8", CultureInfo.InvariantCulture);
    }

    private sealed class IssueCollector
    {
        private readonly int _maximumCount;
        private readonly List<PreflightIssue> _items = new List<PreflightIssue>();

        public IssueCollector(int maximumCount)
        {
            _maximumCount = maximumCount;
        }

        public IReadOnlyList<PreflightIssue> Items => _items;

        public int SuppressedCount { get; private set; }

        public void Add(string code, PreflightSeverity severity, string message, string? itemLabel = null)
        {
            if (_items.Count >= _maximumCount)
            {
                SuppressedCount++;
                return;
            }

            _items.Add(new PreflightIssue(code, severity, message, itemLabel));
        }
    }
}
