using System;

namespace SmartSkin.Core.Preflight;

public enum PreflightSeverity
{
    Information,
    Warning,
    Error
}

public enum PreflightStatus
{
    Ready,
    Warning,
    Blocked
}

public sealed class PreflightIssue
{
    public PreflightIssue(string code, PreflightSeverity severity, string message, string? itemLabel = null)
    {
        if (string.IsNullOrWhiteSpace(code))
        {
            throw new ArgumentException("An issue code is required.", nameof(code));
        }

        if (string.IsNullOrWhiteSpace(message))
        {
            throw new ArgumentException("An issue message is required.", nameof(message));
        }

        Code = code;
        Severity = severity;
        Message = message;
        ItemLabel = itemLabel;
    }

    public string Code { get; }

    public PreflightSeverity Severity { get; }

    public string Message { get; }

    public string? ItemLabel { get; }
}

public static class PreflightIssueCodes
{
    public const string NoInput = "P01_NO_INPUT";
    public const string SelectionLimit = "P01_SELECTION_LIMIT";
    public const string InvalidTolerance = "P01_INVALID_TOLERANCE";
    public const string SnapshotFailure = "P01_SNAPSHOT_FAILURE";
    public const string AnalysisLimited = "P01_ANALYSIS_LIMITED";
    public const string InvalidGeometry = "P01_INVALID_GEOMETRY";
    public const string UnsupportedGeometry = "P01_UNSUPPORTED_GEOMETRY";
    public const string NoScale = "P01_NO_SCALE";
    public const string ToleranceExceedsScale = "P01_TOLERANCE_EXCEEDS_SCALE";
    public const string ToleranceLarge = "P01_TOLERANCE_LARGE";
    public const string DegenerateLength = "P01_DEGENERATE_LENGTH";
    public const string ShortCurve = "P01_SHORT_CURVE";
    public const string ShortEdge = "P01_SHORT_EDGE";
    public const string HighSpanCount = "P01_HIGH_SPAN_COUNT";
    public const string NakedEdges = "P01_NAKED_EDGES";
    public const string ShortBrepEdges = "P01_SHORT_BREP_EDGES";
    public const string NearGap = "P01_NEAR_GAP";
}

public sealed class PreflightOptions
{
    public const int DefaultMaximumItems = 256;
    public const int DefaultMaximumIssues = 64;
    public const int DefaultHighSpanCount = 200;

    public PreflightOptions(
        double absoluteTolerance,
        int maximumItems = DefaultMaximumItems,
        int maximumIssues = DefaultMaximumIssues,
        int highSpanCount = DefaultHighSpanCount,
        double nearGapToleranceMultiplier = 10.0,
        double toleranceToScaleWarningRatio = 0.01)
    {
        if (maximumItems < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumItems));
        }

        if (maximumIssues < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumIssues));
        }

        if (highSpanCount < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(highSpanCount));
        }

        if (nearGapToleranceMultiplier <= 1.0)
        {
            throw new ArgumentOutOfRangeException(nameof(nearGapToleranceMultiplier));
        }

        if (toleranceToScaleWarningRatio <= 0.0)
        {
            throw new ArgumentOutOfRangeException(nameof(toleranceToScaleWarningRatio));
        }

        AbsoluteTolerance = absoluteTolerance;
        MaximumItems = maximumItems;
        MaximumIssues = maximumIssues;
        HighSpanCount = highSpanCount;
        NearGapToleranceMultiplier = nearGapToleranceMultiplier;
        ToleranceToScaleWarningRatio = toleranceToScaleWarningRatio;
    }

    public double AbsoluteTolerance { get; }

    public int MaximumItems { get; }

    public int MaximumIssues { get; }

    public int HighSpanCount { get; }

    public double NearGapToleranceMultiplier { get; }

    public double ToleranceToScaleWarningRatio { get; }
}
