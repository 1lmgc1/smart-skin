using System;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal enum MatchContinuityLevel
{
    Position,
    Tangency,
    Curvature,
}

internal enum MatchIsoDirection
{
    Automatic,
    MatchTarget,
    Perpendicular,
    Preserve,
}

internal sealed class CandidateBuildSettings
{
    public const double MinimumCurvatureTolerancePercent = 0.1;
    public const double MaximumCurvatureTolerancePercent = 100.0;
    public const int MinimumPreviewOpacity = 15;
    public const int MaximumPreviewOpacity = 90;

    public CandidateBuildSettings(
        MatchContinuityLevel continuity,
        bool refineMatch,
        double curvatureTolerancePercent,
        bool averageSurfaces,
        MatchIsoDirection isoDirection,
        int previewOpacityPercent,
        bool showWires)
    {
        if (curvatureTolerancePercent < MinimumCurvatureTolerancePercent
            || curvatureTolerancePercent > MaximumCurvatureTolerancePercent)
        {
            throw new ArgumentOutOfRangeException(nameof(curvatureTolerancePercent));
        }

        if (previewOpacityPercent < MinimumPreviewOpacity
            || previewOpacityPercent > MaximumPreviewOpacity)
        {
            throw new ArgumentOutOfRangeException(nameof(previewOpacityPercent));
        }

        Continuity = continuity;
        RefineMatch = refineMatch;
        CurvatureTolerancePercent = curvatureTolerancePercent;
        AverageSurfaces = averageSurfaces;
        IsoDirection = isoDirection;
        PreviewOpacityPercent = previewOpacityPercent;
        ShowWires = showWires;
    }

    public MatchContinuityLevel Continuity { get; }

    public bool RefineMatch { get; }

    public double CurvatureTolerancePercent { get; }

    public bool AverageSurfaces { get; }

    public MatchIsoDirection IsoDirection { get; }

    public int PreviewOpacityPercent { get; }

    public bool ShowWires { get; }

    public string ContinuityToken => Continuity switch
    {
        MatchContinuityLevel.Position => "G0",
        MatchContinuityLevel.Tangency => "G1",
        MatchContinuityLevel.Curvature => "G2",
        _ => throw new ArgumentOutOfRangeException(),
    };

    public Continuity RhinoContinuity => Continuity switch
    {
        MatchContinuityLevel.Position => Rhino.Geometry.Continuity.C0_continuous,
        MatchContinuityLevel.Tangency => Rhino.Geometry.Continuity.G1_continuous,
        MatchContinuityLevel.Curvature => Rhino.Geometry.Continuity.G2_continuous,
        _ => throw new ArgumentOutOfRangeException(),
    };

    public PreserveIsoCurveMethod RhinoPreserveIso => IsoDirection switch
    {
        MatchIsoDirection.Automatic => PreserveIsoCurveMethod.Automatic,
        MatchIsoDirection.MatchTarget => PreserveIsoCurveMethod.MatchTarget,
        MatchIsoDirection.Perpendicular => PreserveIsoCurveMethod.Perpendicular,
        MatchIsoDirection.Preserve => PreserveIsoCurveMethod.Preserve,
        _ => throw new ArgumentOutOfRangeException(),
    };

    public static CandidateBuildSettings Default => new(
        MatchContinuityLevel.Curvature,
        refineMatch: true,
        curvatureTolerancePercent: 5.0,
        averageSurfaces: false,
        MatchIsoDirection.Automatic,
        previewOpacityPercent: 45,
        showWires: true);

    public CandidateBuildSettings WithAppearance(int previewOpacityPercent, bool showWires)
    {
        return new CandidateBuildSettings(
            Continuity,
            RefineMatch,
            CurvatureTolerancePercent,
            AverageSurfaces,
            IsoDirection,
            previewOpacityPercent,
            showWires);
    }
}
