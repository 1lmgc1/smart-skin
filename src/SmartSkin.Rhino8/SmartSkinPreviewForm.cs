using System;
using System.Globalization;
using Eto.Drawing;
using Eto.Forms;
using Rhino;
using Rhino.UI;
using SmartSkin.Core.Construction;
using SmartSkin.Core.Routing;

namespace SmartSkin.Rhino8;

internal sealed class SmartSkinPreviewForm : Form
{
    private static readonly string[] ContinuityNames = { "Position (G0)", "Tangency (G1)", "Curvature (G2)" };
    private static readonly string[] IsoDirectionNames = { "Automatic", "Match target", "Perpendicular", "Preserve seed" };
    private readonly CandidateConstructionPlan _plan;
    private readonly SmartSkinLivePreviewSession _session;
    private readonly DropDown _continuity = new();
    private readonly CheckBox _refineMatch = new();
    private readonly NumericStepper _curvatureTolerance = new();
    private readonly CheckBox _averageSurfaces = new();
    private readonly DropDown _isoDirection = new();
    private readonly Slider _previewOpacity = new();
    private readonly Label _previewOpacityValue = new();
    private readonly CheckBox _showWires = new();
    private readonly Label _status = new();
    private readonly Label _instruction = new();
    private readonly UITimer _rebuildTimer = new();
    private bool _suppressChanges;
    private bool _closingForDecision;

    public SmartSkinPreviewForm(RhinoDoc document, CandidateConstructionPlan plan, SmartSkinLivePreviewSession session)
    {
        _plan = plan ?? throw new ArgumentNullException(nameof(plan));
        _session = session ?? throw new ArgumentNullException(nameof(session));
        if (document is null) throw new ArgumentNullException(nameof(document));
        Title = _plan.Strategy == SurfaceStrategy.MatchSrf ? "Smart Skin — matched result" : "Smart Skin — result preview";
        ClientSize = new Size(510, 640);
        Resizable = false;
        Maximizable = false;
        Minimizable = false;
        ShowActivated = false;
        CanFocus = true;
        Owner = RhinoEtoApp.MainWindowForDocument(document);
        this.UseRhinoStyle();
        ConfigureControls(session.CurrentSettings);
        Content = BuildLayout();
        WireEvents();
        RefreshStatus();
    }

    public bool AcceptRequested { get; private set; }
    public bool CancelRequested { get; private set; }

    public bool PrepareForAcceptance()
    {
        if (_rebuildTimer.Started) { _rebuildTimer.Stop(); RebuildNow(); }
        return _session.HasCandidate;
    }

    public void CloseForCommand()
    {
        _closingForDecision = true;
        _rebuildTimer.Stop();
        if (Visible) Close();
    }

    private void ConfigureControls(CandidateBuildSettings settings)
    {
        _suppressChanges = true;
        _continuity.DataStore = ContinuityNames;
        _continuity.SelectedIndex = (int)settings.Continuity;
        _continuity.Width = 225;
        _continuity.ToolTip = "Required continuity to the adjacent Brep faces; never silently downgraded.";
        _refineMatch.Text = "Refine match to document tolerances";
        _refineMatch.Checked = settings.RefineMatch;
        _refineMatch.ToolTip = "Ask Rhino to refine the native match. The independent verifier still must pass.";
        _curvatureTolerance.MinValue = CandidateBuildSettings.MinimumCurvatureTolerancePercent;
        _curvatureTolerance.MaxValue = CandidateBuildSettings.MaximumCurvatureTolerancePercent;
        _curvatureTolerance.Value = settings.CurvatureTolerancePercent;
        _curvatureTolerance.Increment = 0.5;
        _curvatureTolerance.DecimalPlaces = 1;
        _curvatureTolerance.MaximumDecimalPlaces = 2;
        _curvatureTolerance.Width = 225;
        _curvatureTolerance.ToolTip = "Maximum sampled cross-boundary radius-of-curvature deviation, in percent.";
        _averageSurfaces.Text = "Average surfaces (changes adjacent Breps)";
        _averageSurfaces.Checked = settings.AverageSurfaces;
        _averageSurfaces.ToolTip = _session.AverageNote;
        _isoDirection.DataStore = IsoDirectionNames;
        _isoDirection.SelectedIndex = (int)settings.IsoDirection;
        _isoDirection.Width = 225;
        _isoDirection.ToolTip = "Control how the matched cap isocurves meet the target boundary.";
        _previewOpacity.MinValue = CandidateBuildSettings.MinimumPreviewOpacity;
        _previewOpacity.MaxValue = CandidateBuildSettings.MaximumPreviewOpacity;
        _previewOpacity.Value = settings.PreviewOpacityPercent;
        _previewOpacity.TickFrequency = 5;
        _previewOpacity.SnapToTick = true;
        _previewOpacity.Width = 225;
        _previewOpacityValue.Text = settings.PreviewOpacityPercent.ToString(CultureInfo.InvariantCulture) + "%";
        _showWires.Text = "Show preview wires";
        _showWires.Checked = settings.ShowWires;
        var match = _plan.Strategy == SurfaceStrategy.MatchSrf;
        _continuity.Enabled = match;
        _refineMatch.Enabled = match;
        _averageSurfaces.Enabled = match && _session.AverageEligible;
        _isoDirection.Enabled = match;
        UpdateCurvatureControlState();
        _rebuildTimer.Interval = 0.25;
        _suppressChanges = false;
    }

    private Control BuildLayout()
    {
        var match = _plan.Strategy == SurfaceStrategy.MatchSrf;
        var heading = new Label { Text = match ? "Matched cap from adjacent Brep faces" : "Result: " + _plan.StrategyToken, Wrap = WrapMode.Word };
        var routeNote = new Label
        {
            Text = match ? "Cyan: new cap. Orange: averaged context. Commit requires measured continuity and a closed Join proof."
                : "This route uses its bounded native constructor; match controls are disabled.",
            Wrap = WrapMode.Word,
        };
        // Each outer row has ONE child. Full-width notes and checkboxes must not
        // share a table column with field captions, pushing inputs out of the window.
        var matchLayout = new DynamicLayout { Padding = new Padding(10), Spacing = new Size(8, 7) };
        matchLayout.AddRow(SettingRow("Continuity", _continuity));
        matchLayout.AddRow(_refineMatch);
        matchLayout.AddRow(SettingRow("Curvature tolerance, %", _curvatureTolerance));
        matchLayout.AddRow(_averageSurfaces);
        if (match) matchLayout.AddRow(new Label
        {
            Text = _session.AverageNote,
            Wrap = WrapMode.Word,
            Width = 430,
        });
        matchLayout.AddRow(SettingRow("Isocurve direction", _isoDirection));
        var matchGroup = new GroupBox { Text = "Surface match", Content = matchLayout };
        var appearance = new DynamicLayout { Padding = new Padding(10), Spacing = new Size(8, 7) };
        var opacityRow = new DynamicLayout { Spacing = new Size(8, 7) };
        opacityRow.AddRow(new Label { Text = "Opacity", Width = 130 }, _previewOpacity, _previewOpacityValue);
        appearance.AddRow(opacityRow);
        appearance.AddRow(_showWires);
        var appearanceGroup = new GroupBox { Text = "Preview", Content = appearance };
        _status.Wrap = WrapMode.Word;
        _status.Height = 155;
        _instruction.Wrap = WrapMode.Word;
        var layout = new DynamicLayout { Padding = new Padding(14), Spacing = new Size(8, 9) };
        layout.AddRow(heading);
        layout.AddRow(routeNote);
        layout.AddRow(matchGroup);
        layout.AddRow(appearanceGroup);
        layout.AddRow(_status);
        layout.AddRow(_instruction);
        return layout;
    }

    private static Control SettingRow(string caption, Control field)
    {
        var row = new DynamicLayout { Spacing = new Size(8, 7) };
        row.AddRow(new Label { Text = caption, Width = 180 }, field);
        return row;
    }

    private void WireEvents()
    {
        _continuity.SelectedIndexChanged += (_, _) =>
        {
            if (_suppressChanges) return;
            UpdateCurvatureControlState();
            ScheduleRebuild();
        };
        _refineMatch.CheckedChanged += (_, _) => { UpdateCurvatureControlState(); ScheduleRebuild(); };
        _curvatureTolerance.ValueChanged += (_, _) => ScheduleRebuild();
        _averageSurfaces.CheckedChanged += (_, _) => ScheduleRebuild();
        _isoDirection.SelectedIndexChanged += (_, _) => ScheduleRebuild();
        _previewOpacity.ValueChanged += (_, _) => UpdateAppearance();
        _showWires.CheckedChanged += (_, _) => UpdateAppearance();
        _rebuildTimer.Elapsed += (_, _) => { _rebuildTimer.Stop(); RebuildNow(); };
        KeyDown += HandleDecisionKey;
        _continuity.KeyDown += HandleDecisionKey;
        _refineMatch.KeyDown += HandleDecisionKey;
        _curvatureTolerance.KeyDown += HandleDecisionKey;
        _averageSurfaces.KeyDown += HandleDecisionKey;
        _isoDirection.KeyDown += HandleDecisionKey;
        _previewOpacity.KeyDown += HandleDecisionKey;
        _showWires.KeyDown += HandleDecisionKey;
        Closing += (_, _) =>
        {
            _rebuildTimer.Stop();
            if (!_closingForDecision && !AcceptRequested) CancelRequested = true;
        };
    }

    private void UpdateCurvatureControlState() => _curvatureTolerance.Enabled = _plan.Strategy == SurfaceStrategy.MatchSrf
        && _continuity.SelectedIndex == (int)MatchContinuityLevel.Curvature;

    private void ScheduleRebuild()
    {
        if (_suppressChanges || _plan.Strategy != SurfaceStrategy.MatchSrf) return;
        _rebuildTimer.Stop();
        _status.Text = "UPDATING · waiting for the current setting change…";
        _rebuildTimer.Start();
    }

    private void RebuildNow()
    {
        _status.Text = "UPDATING · rebuilding and measuring one disposable preview…";
        _session.Rebuild(ReadSettings());
        RefreshStatus();
    }

    private void UpdateAppearance()
    {
        if (_suppressChanges) return;
        _previewOpacityValue.Text = _previewOpacity.Value.ToString(CultureInfo.InvariantCulture) + "%";
        _session.UpdateAppearance(_session.CurrentSettings.WithAppearance(_previewOpacity.Value, _showWires.Checked == true));
    }

    private CandidateBuildSettings ReadSettings() => new(
        (MatchContinuityLevel)_continuity.SelectedIndex, _refineMatch.Checked == true,
        _curvatureTolerance.Value, _averageSurfaces.Checked == true,
        (MatchIsoDirection)_isoDirection.SelectedIndex, _previewOpacity.Value, _showWires.Checked == true);

    private void RefreshStatus()
    {
        var outcome = _session.CurrentOutcome;
        var candidate = _session.Candidate;
        var settings = _session.CurrentSettings;
        var metrics = outcome?.Metrics;
        if (outcome?.Success == true && candidate is not null)
        {
            _status.Text = "READY · " + (metrics?.Token ?? "BOUNDED_RESULT")
                + "\nFaces " + candidate.Faces.Count + " · edges " + candidate.Edges.Count
                + " · " + outcome.ElapsedMilliseconds + " ms" + MetricSummary(metrics)
                + (settings.AverageSurfaces ? "\nAVERAGE ON · replaces " + outcome.ParentObjectCount + " owning Breps with one joined result"
                    : "\nSources unchanged · adds one result");
        }
        else
        {
            _status.Text = "BLOCKED · Enter will not change the document"
                + (outcome is null ? string.Empty : "\n" + outcome.Code + " · " + outcome.Message)
                + MetricSummary(metrics);
        }
        _instruction.Text = outcome?.Code == "P07F1_VALIDATOR_SELFTEST_FAILED"
            ? "Esc — cancel. Internal self-test failed; changing settings cannot repair this build. See command history."
            : !_session.HasCandidate ? "Esc — cancel. Adjust settings to rebuild; see command history for every attempt."
            : settings.AverageSurfaces ? "Enter / Space / right-click — replace sources with averaged joined result    •    Esc — cancel"
            : "Enter / Space / right-click — add result    •    Esc — cancel";
    }

    private static string MetricSummary(BoundaryMatchMetrics? m) => m is null ? string.Empty
        : "\nGap " + BoundaryMatchVerifier.Number(m.MaximumGap)
            + " · normal " + BoundaryMatchVerifier.Number(m.MaximumNormalAngleDegrees) + "°"
            + " · curvature " + BoundaryMatchVerifier.Number(m.MaximumCurvatureDeviationPercent) + "%"
            + "\nBoundary edges " + m.BoundaryEdgeCount + " · loops " + m.BoundaryComponents
            + " · samples " + m.SampleCount;

    private void RequestAccept()
    {
        if (AcceptRequested || CancelRequested) return;
        if (!PrepareForAcceptance()) { RefreshStatus(); return; }
        AcceptRequested = true;
        _closingForDecision = true;
        Close();
    }

    private void RequestCancel()
    {
        if (AcceptRequested || CancelRequested) return;
        CancelRequested = true;
        _closingForDecision = true;
        _rebuildTimer.Stop();
        Close();
    }

    private void HandleDecisionKey(object? sender, KeyEventArgs eventArgs)
    {
        if (eventArgs.Key == Keys.Escape) { eventArgs.Handled = true; RequestCancel(); }
        else if (eventArgs.Key == Keys.Enter || eventArgs.Key == Keys.Space) { eventArgs.Handled = true; RequestAccept(); }
    }
}
