using System;
using System.Collections.Generic;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using SmartSkin.Core.Construction;

namespace SmartSkin.Rhino8;

internal sealed class SmartSkinLivePreviewSession : IDisposable
{
    private readonly RhinoDoc _document;
    private readonly CandidateConstructionPlan _plan;
    private readonly IReadOnlyList<ObjRef> _references;
    private readonly double _absoluteTolerance;
    private readonly double _angleToleranceRadians;
    private readonly RhinoCandidateBuilder _builder = new();
    private readonly CandidatePreviewConduit _conduit;
    private CandidateBuildOutcome? _currentOutcome;
    private CandidateBuildSettings _currentSettings;
    private volatile bool _cancellationRequested;
    private bool _disposed;

    public SmartSkinLivePreviewSession(
        RhinoDoc document,
        CandidateConstructionPlan plan,
        IReadOnlyList<ObjRef> references,
        double absoluteTolerance,
        double angleToleranceRadians,
        CandidateBuildSettings initialSettings)
    {
        _document = document ?? throw new ArgumentNullException(nameof(document));
        _plan = plan ?? throw new ArgumentNullException(nameof(plan));
        _references = references is null
            ? throw new ArgumentNullException(nameof(references))
            : new List<ObjRef>(references);
        _absoluteTolerance = absoluteTolerance;
        _angleToleranceRadians = angleToleranceRadians;
        _currentSettings = initialSettings ?? throw new ArgumentNullException(nameof(initialSettings));
        _conduit = new CandidatePreviewConduit(
            initialSettings.PreviewOpacityPercent,
            initialSettings.ShowWires)
        {
            Enabled = true,
        };
        RhinoApp.EscapeKeyPressed += HandleEscapeKeyPressed;
    }

    public CandidateBuildOutcome? CurrentOutcome => _currentOutcome;

    public CandidateBuildSettings CurrentSettings => _currentSettings;

    public Brep? Candidate => _currentOutcome?.Success == true
        ? _currentOutcome.Candidate
        : null;

    public bool HasCandidate => Candidate is not null;

    public CandidateBuildOutcome Rebuild(CandidateBuildSettings settings)
    {
        ThrowIfDisposed();
        if (settings is null)
        {
            throw new ArgumentNullException(nameof(settings));
        }

        _cancellationRequested = false;
        var next = _builder.Build(
            _plan,
            _references,
            _absoluteTolerance,
            _angleToleranceRadians,
            settings,
            () => _cancellationRequested);
        var previous = _currentOutcome;
        _currentOutcome = next;
        _currentSettings = settings;
        _conduit.SetCandidates(
            next.Success ? next.Candidate : null,
            next.Success ? next.AveragedContext : null);
        _conduit.SetAppearance(settings.PreviewOpacityPercent, settings.ShowWires);
        previous?.Dispose();
        _document.Views.Redraw();
        return next;
    }

    public void UpdateAppearance(CandidateBuildSettings settings)
    {
        ThrowIfDisposed();
        if (settings is null)
        {
            throw new ArgumentNullException(nameof(settings));
        }

        _currentSettings = settings;
        _conduit.SetAppearance(settings.PreviewOpacityPercent, settings.ShowWires);
        _document.Views.Redraw();
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        RhinoApp.EscapeKeyPressed -= HandleEscapeKeyPressed;
        _conduit.Dispose();
        _currentOutcome?.Dispose();
        _currentOutcome = null;
        _document.Views.Redraw();
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(SmartSkinLivePreviewSession));
        }
    }

    private void HandleEscapeKeyPressed(object? sender, EventArgs eventArgs)
    {
        _cancellationRequested = true;
    }
}
