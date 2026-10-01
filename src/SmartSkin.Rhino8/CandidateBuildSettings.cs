using System;

namespace SmartSkin.Rhino8;

internal enum CandidatePreset
{
    Balanced,
    Stiff,
    Flexible,
    Detailed,
    Custom,
}

internal sealed class CandidateBuildSettings
{
    public const int MinimumSpans = 2;
    public const int MaximumSpans = 16;
    public const double MinimumSampleSpacingScale = 0.25;
    public const double MaximumSampleSpacingScale = 4.0;
    public const double MinimumFlexibility = 0.001;
    public const double MaximumFlexibility = 100.0;
    public const int MinimumPreviewOpacity = 15;
    public const int MaximumPreviewOpacity = 90;

    public CandidateBuildSettings(
        CandidatePreset preset,
        int uSpans,
        int vSpans,
        double sampleSpacingScale,
        double flexibility,
        bool adjustTangency,
        bool automaticTrim,
        int previewOpacityPercent,
        bool showWires)
    {
        if (uSpans < MinimumSpans || uSpans > MaximumSpans)
        {
            throw new ArgumentOutOfRangeException(nameof(uSpans));
        }

        if (vSpans < MinimumSpans || vSpans > MaximumSpans)
        {
            throw new ArgumentOutOfRangeException(nameof(vSpans));
        }

        if (sampleSpacingScale < MinimumSampleSpacingScale
            || sampleSpacingScale > MaximumSampleSpacingScale)
        {
            throw new ArgumentOutOfRangeException(nameof(sampleSpacingScale));
        }

        if (flexibility < MinimumFlexibility || flexibility > MaximumFlexibility)
        {
            throw new ArgumentOutOfRangeException(nameof(flexibility));
        }

        if (previewOpacityPercent < MinimumPreviewOpacity
            || previewOpacityPercent > MaximumPreviewOpacity)
        {
            throw new ArgumentOutOfRangeException(nameof(previewOpacityPercent));
        }

        Preset = preset;
        USpans = uSpans;
        VSpans = vSpans;
        SampleSpacingScale = sampleSpacingScale;
        Flexibility = flexibility;
        AdjustTangency = adjustTangency;
        AutomaticTrim = automaticTrim;
        PreviewOpacityPercent = previewOpacityPercent;
        ShowWires = showWires;
    }

    public CandidatePreset Preset { get; }

    public int USpans { get; }

    public int VSpans { get; }

    public double SampleSpacingScale { get; }

    public double Flexibility { get; }

    public bool AdjustTangency { get; }

    public bool AutomaticTrim { get; }

    public int PreviewOpacityPercent { get; }

    public bool ShowWires { get; }

    public string PresetToken => Preset.ToString().ToUpperInvariant();

    public static CandidateBuildSettings Balanced => CreatePreset(CandidatePreset.Balanced);

    public static CandidateBuildSettings CreatePreset(
        CandidatePreset preset,
        int previewOpacityPercent = 45,
        bool showWires = true)
    {
        return preset switch
        {
            CandidatePreset.Balanced => new CandidateBuildSettings(
                preset, 8, 8, 1.0, 1.0, true, true, previewOpacityPercent, showWires),
            CandidatePreset.Stiff => new CandidateBuildSettings(
                preset, 8, 8, 1.0, 0.1, true, true, previewOpacityPercent, showWires),
            CandidatePreset.Flexible => new CandidateBuildSettings(
                preset, 8, 8, 1.0, 10.0, true, true, previewOpacityPercent, showWires),
            CandidatePreset.Detailed => new CandidateBuildSettings(
                preset, 12, 12, 0.5, 1.0, true, true, previewOpacityPercent, showWires),
            _ => throw new ArgumentOutOfRangeException(nameof(preset), "Custom is not a fixed preset."),
        };
    }

    public CandidateBuildSettings WithAppearance(int previewOpacityPercent, bool showWires)
    {
        return new CandidateBuildSettings(
            Preset,
            USpans,
            VSpans,
            SampleSpacingScale,
            Flexibility,
            AdjustTangency,
            AutomaticTrim,
            previewOpacityPercent,
            showWires);
    }
}
