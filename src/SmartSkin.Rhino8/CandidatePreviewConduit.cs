using System;
using System.Drawing;
using Rhino.Display;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class CandidatePreviewConduit : DisplayConduit
{
    private static readonly Color PreviewColor = Color.FromArgb(0, 174, 239);

    private readonly Brep _candidate;
    private readonly BoundingBox _bounds;
    private readonly DisplayMaterial _material;

    public CandidatePreviewConduit(Brep candidate)
    {
        _candidate = candidate ?? throw new ArgumentNullException(nameof(candidate));
        _bounds = candidate.GetBoundingBox(accurate: true);
        _material = new DisplayMaterial(PreviewColor, transparency: 0.55);
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
        e.Display.DrawBrepShaded(_candidate, _material);
        e.Display.DrawBrepWires(_candidate, PreviewColor, wireDensity: 1);
    }
}
