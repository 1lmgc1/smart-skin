using System;
using System.Drawing;
using Rhino.Display;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class CandidatePreviewConduit : DisplayConduit
{
    private static readonly Color PreviewColor = Color.FromArgb(0, 174, 239);

    private Brep? _candidate;
    private BoundingBox _bounds;
    private DisplayMaterial _material;
    private bool _showWires;

    public CandidatePreviewConduit(int opacityPercent, bool showWires)
    {
        _bounds = BoundingBox.Unset;
        _material = CreateMaterial(opacityPercent);
        _showWires = showWires;
    }

    public void SetCandidate(Brep? candidate)
    {
        _candidate = candidate;
        _bounds = candidate?.GetBoundingBox(accurate: true) ?? BoundingBox.Unset;
    }

    public void SetAppearance(int opacityPercent, bool showWires)
    {
        _material = CreateMaterial(opacityPercent);
        _showWires = showWires;
    }

    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs e)
    {
        if (_bounds.IsValid)
        {
            e.IncludeBoundingBox(_bounds);
        }
    }

    protected override void PreDrawObjects(DrawEventArgs e)
    {
        var candidate = _candidate;
        if (candidate is null)
        {
            return;
        }

        e.Display.DrawBrepShaded(candidate, _material);
        if (_showWires)
        {
            e.Display.DrawBrepWires(candidate, PreviewColor, wireDensity: 1);
        }
    }

    private static DisplayMaterial CreateMaterial(int opacityPercent)
    {
        if (opacityPercent < CandidateBuildSettings.MinimumPreviewOpacity
            || opacityPercent > CandidateBuildSettings.MaximumPreviewOpacity)
        {
            throw new ArgumentOutOfRangeException(nameof(opacityPercent));
        }

        var transparency = 1.0 - (opacityPercent / 100.0);
        return new DisplayMaterial(PreviewColor, transparency);
    }
}
