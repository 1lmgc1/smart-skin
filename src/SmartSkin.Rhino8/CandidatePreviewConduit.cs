using System;
using System.Drawing;
using Rhino.Display;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class CandidatePreviewConduit : DisplayConduit, IDisposable
{
    private static readonly Color PreviewColor = Color.FromArgb(0, 174, 239);
    private static readonly Color ContextColor = Color.FromArgb(242, 140, 40);

    private Brep? _candidate;
    private Brep? _averagedContext;
    private BoundingBox _bounds;
    private DisplayMaterial _material;
    private DisplayMaterial _contextMaterial;
    private bool _showWires;
    private bool _disposed;

    public CandidatePreviewConduit(int opacityPercent, bool showWires)
    {
        _bounds = BoundingBox.Unset;
        _material = CreateMaterial(opacityPercent);
        _contextMaterial = CreateContextMaterial(opacityPercent);
        _showWires = showWires;
    }

    public void SetCandidates(Brep? candidate, Brep? averagedContext)
    {
        _candidate = candidate;
        _averagedContext = averagedContext;
        _bounds = BoundingBox.Unset;
        if (candidate is not null)
        {
            _bounds = candidate.GetBoundingBox(accurate: true);
        }

        if (averagedContext is not null)
        {
            var contextBounds = averagedContext.GetBoundingBox(accurate: true);
            if (_bounds.IsValid)
            {
                _bounds.Union(contextBounds);
            }
            else
            {
                _bounds = contextBounds;
            }
        }
    }

    public void SetAppearance(int opacityPercent, bool showWires)
    {
        var nextMaterial = CreateMaterial(opacityPercent);
        DisplayMaterial? nextContextMaterial = null;
        try
        {
            nextContextMaterial = CreateContextMaterial(opacityPercent);
        }
        catch
        {
            nextMaterial.Dispose();
            throw;
        }

        var previousMaterial = _material;
        var previousContextMaterial = _contextMaterial;
        _material = nextMaterial;
        _contextMaterial = nextContextMaterial;
        _showWires = showWires;
        previousMaterial.Dispose();
        previousContextMaterial.Dispose();
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        Enabled = false;
        _candidate = null;
        _averagedContext = null;
        _bounds = BoundingBox.Unset;
        _material.Dispose();
        _contextMaterial.Dispose();
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
        var averagedContext = _averagedContext;
        if (candidate is null && averagedContext is null)
        {
            return;
        }

        if (averagedContext is not null)
        {
            e.Display.DrawBrepShaded(averagedContext, _contextMaterial);
            if (_showWires)
            {
                e.Display.DrawBrepWires(averagedContext, ContextColor, wireDensity: 1);
            }
        }

        if (candidate is not null)
        {
            e.Display.DrawBrepShaded(candidate, _material);
            if (_showWires)
            {
                e.Display.DrawBrepWires(candidate, PreviewColor, wireDensity: 1);
            }
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

    private static DisplayMaterial CreateContextMaterial(int opacityPercent)
    {
        var transparency = 1.0 - (Math.Min(opacityPercent, 55) / 100.0);
        return new DisplayMaterial(ContextColor, transparency);
    }
}
