using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Linq;

namespace SmartSkin.Core.Preflight;

public sealed class PreflightReport
{
    internal PreflightReport(
        IReadOnlyList<GeometrySnapshot> snapshots,
        IReadOnlyList<PreflightIssue> issues,
        Bounds3Value selectionBounds,
        double absoluteTolerance,
        int nearGapCount,
        int connectedCurvePairCount,
        int suppressedIssueCount)
    {
        Snapshots = snapshots.ToArray();
        Issues = issues.ToArray();
        SelectionBounds = selectionBounds;
        AbsoluteTolerance = absoluteTolerance;
        NearGapCount = nearGapCount;
        ConnectedCurvePairCount = connectedCurvePairCount;
        SuppressedIssueCount = suppressedIssueCount;
        ValidCount = Snapshots.Count(snapshot => snapshot.IsValid == true);
        WarningCount = Issues.Count(issue => issue.Severity == PreflightSeverity.Warning);
        ErrorCount = Issues.Count(issue => issue.Severity == PreflightSeverity.Error);
        Status = ErrorCount > 0
            ? PreflightStatus.Blocked
            : WarningCount > 0
                ? PreflightStatus.Warning
                : PreflightStatus.Ready;

        var counts = Snapshots
            .GroupBy(snapshot => snapshot.Kind)
            .ToDictionary(group => group.Key, group => group.Count());
        TypeCounts = new ReadOnlyDictionary<GeometryKind, int>(counts);
    }

    public IReadOnlyList<GeometrySnapshot> Snapshots { get; }

    public IReadOnlyList<PreflightIssue> Issues { get; }

    public IReadOnlyDictionary<GeometryKind, int> TypeCounts { get; }

    public Bounds3Value SelectionBounds { get; }

    public double AbsoluteTolerance { get; }

    public double SelectionScale => SelectionBounds.DiagonalLength;

    public int SelectedCount => Snapshots.Count;

    public int ValidCount { get; }

    public int WarningCount { get; }

    public int ErrorCount { get; }

    public int NearGapCount { get; }

    public int ConnectedCurvePairCount { get; }

    public int SuppressedIssueCount { get; }

    public PreflightStatus Status { get; }

    public IReadOnlyList<string> ToDisplayLines(int maximumItemLines = 24)
    {
        if (maximumItemLines < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumItemLines));
        }

        var lines = new List<string>
        {
            $"Status: {Status.ToString().ToUpperInvariant()}",
            $"Selected: {SelectedCount.ToString(CultureInfo.InvariantCulture)}; valid: {ValidCount.ToString(CultureInfo.InvariantCulture)}",
            $"Types: {FormatTypeCounts()}",
            $"Selection scale: {FormatNumber(SelectionScale)}; absolute tolerance: {FormatNumber(AbsoluteTolerance)}",
            $"Endpoint pairs: connected={ConnectedCurvePairCount.ToString(CultureInfo.InvariantCulture)}; near_gaps={NearGapCount.ToString(CultureInfo.InvariantCulture)}"
        };

        var itemLines = Math.Min(Snapshots.Count, maximumItemLines);
        for (var index = 0; index < itemLines; index++)
        {
            lines.Add($"  {Snapshots[index].ToSummaryLine()}");
        }

        if (Snapshots.Count > itemLines)
        {
            lines.Add($"  ... {Snapshots.Count - itemLines} additional item(s) omitted from display");
        }

        if (Issues.Count == 0)
        {
            lines.Add("Issues: none");
        }
        else
        {
            lines.Add("Issues:");
            foreach (var issue in Issues)
            {
                var item = string.IsNullOrWhiteSpace(issue.ItemLabel) ? string.Empty : $" {issue.ItemLabel}:";
                lines.Add($"  [{issue.Severity.ToString().ToUpperInvariant()} {issue.Code}]{item} {issue.Message}");
            }
        }

        if (SuppressedIssueCount > 0)
        {
            lines.Add($"  ... {SuppressedIssueCount.ToString(CultureInfo.InvariantCulture)} additional issue(s) suppressed by the report limit");
        }

        return lines;
    }

    public string ToMachineLine(BuildIdentity identity, int objectCountBefore, int objectCountAfter)
    {
        if (identity is null)
        {
            throw new ArgumentNullException(nameof(identity));
        }

        return $"SMARTSKIN_{identity.Patch} PASS"
            + $" | version={identity.Version}"
            + $" | commit={identity.Commit}"
            + $" | status={Status.ToString().ToUpperInvariant()}"
            + $" | selected={SelectedCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | valid={ValidCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | warnings={WarningCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | errors={ErrorCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | near_gaps={NearGapCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}";
    }

    private string FormatTypeCounts()
    {
        if (TypeCounts.Count == 0)
        {
            return "none";
        }

        return string.Join(
            ", ",
            TypeCounts
                .OrderBy(pair => pair.Key)
                .Select(pair => $"{pair.Key}={pair.Value.ToString(CultureInfo.InvariantCulture)}"));
    }

    private static string FormatNumber(double value)
    {
        return value.ToString("G8", CultureInfo.InvariantCulture);
    }
}
