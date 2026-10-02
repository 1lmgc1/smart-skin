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
    private static readonly string[] ContinuityNames =
    {
        "Position (G0)",
        "Tangency (G1)",
        "Curvature (G2)",
    };

    private static readonly string[] IsoDirectionNames =
    {
        "Automatic",
        "Match target",
        "Perpendicular",
        "Preserve seed",
    };

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

    public SmartSkinPreviewForm(
        RhinoDoc document,
        CandidateConstructionPlan plan,
        SmartSkinLivePreviewSession session)
    {
        _plan = plan ?? throw new ArgumentNullException(nameof(plan));
        _session = session ?? throw new ArgumentNullException(nameof(session));
        if (document is null)
        {
            throw new ArgumentNullException(nameof(document));
        }

        Title = _plan.Strategy == SurfaceStrategy.MatchSrf
            ? "Smart Skin — matched result"
            : "Smart Skin — result preview";
        ClientSize = new Size(470, 560);
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
        if (_rebuildTimer.Started)
        {
            _rebuildTimer.Stop();
            RebuildNow();
        }

        return _session.HasCandidate;
    }

    public void CloseForCommand()
    {
        _closingForDecision = true;
        _rebuildTimer.Stop();
        if (Visible)
        {
            Close();
        }
    }

    private void ConfigureControls(CandidateBuildSettings settings)
    {
        _suppressChanges = true;

        _continuity.DataStore = ContinuityNames;
        _continuity.SelectedIndex = (int)settings.Continuity;
        _continuity.Width = 225;
        _continuity.ToolTip = "Match position, tangent direction, or radius of curvature to the adjacent Brep faces.";

        _refineMatch.Text = "Refine match to document tolerances";
        _refineMatch.Checked = settings.RefineMatch;
        _refineMatch.ToolTip = "Allow Rhino to add knot rows until the selected continuity is within tolerance.";

        _curvatureTolerance.MinValue = CandidateBuildSettings.MinimumCurvatureTolerancePercent;
        _curvatureTolerance.MaxValue = CandidateBuildSettings.MaximumCurvatureTolerancePercent;
        _curvatureTolerance.Value = settings.CurvatureTolerancePercent;
        _curvatureTolerance.Increment = 0.5;
        _curvatureTolerance.DecimalPlaces = 1;
        _curvatureTolerance.MaximumDecimalPlaces = 2;
        _curvatureTolerance.Width = 225;
        _curvatureTolerance.ToolTip = "Maximum radius-of-curvature deviation used by Refine and by commit verification.";

        _averageSurfaces.Text = "Average surfaces (changes adjacent Breps)";
        _averageSurfaces.Checked = settings.AverageSurfaces;
        _averageSurfaces.ToolTip = "For untrimmed target surfaces, move both sides to an intermediate shape. Enter replaces the selected owning Breps only after every seam joins; the result inherits the first source object's attributes.";

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
        _previewOpacityValue.Text = $"{settings.PreviewOpacityPercent.ToString(CultureInfo.InvariantCulture)}%";

        _showWires.Text = "Show preview wires";
        _showWires.Checked = settings.ShowWires;

        var matchControlsEnabled = _plan.Strategy == SurfaceStrategy.MatchSrf;
        _continuity.Enabled = matchControlsEnabled;
        _refineMatch.Enabled = matchControlsEnabled;
        _averageSurfaces.Enabled = matchControlsEnabled;
        _isoDirection.Enabled = matchControlsEnabled;
        UpdateCurvatureControlState();

        _rebuildTimer.Interval = 0.25;
        _suppressChanges = false;
    }

    private Control BuildLayout()
    {
        var heading = new Label
        {
            Text = _plan.Strategy == SurfaceStrategy.MatchSrf
                ? "Matched cap from adjacent Brep faces"
                : $"Result: {_plan.StrategyToken}",
            Wrap = WrapMode.Word,
        };

        var routeNote = new Label
        {
            Text = _plan.Strategy == SurfaceStrategy.MatchSrf
                ? "Cyan: new cap. Orange: averaged context when Average surfaces is on. Commit is enabled only after measured continuity passes."
                : "This route uses its bounded native constructor; match controls are disabled.",
            Wrap = WrapMode.Word,
        };

        var matchLayout = new DynamicLayout
        {
            Padding = new Padding(10),
            Spacing = new Size(8, 7),
        };
        matchLayout.AddRow(new Label { Text = "Continuity" }, _continuity);
        matchLayout.AddRow(_refineMatch);
        matchLayout.AddRow(new Label { Text = "Curvature tolerance, %" }, _curvatureTolerance);
        matchLayout.AddRow(_averageSurfaces);
        matchLayout.AddRow(new Label { Text = "Isocurve direction" }, _isoDirection);

        var matchGroup = new GroupBox
        {
            Text = "Surface match",
            Content = matchLayout,
        };

        var appearanceLayout = new DynamicLayout
        {
            Padding = new Padding(10),
            Spacing = new Size(8, 7),
        };
        appearanceLayout.AddRow(new Label { Text = "Opacity" }, _previewOpacity, _previewOpacityValue);
        appearanceLayout.AddRow(_showWires);

        var appearanceGroup = new GroupBox
        {
            Text = "Preview",
            Content = appearanceLayout,
        };

        _status.Wrap = WrapMode.Word;
        _status.Height = 112;
        _instruction.Wrap = WrapMode.Word;

        var layout = new DynamicLayout
        {
            Padding = new Padding(14),
            Spacing = new Size(8, 9),
        };
        layout.AddRow(heading);
        layout.AddRow(routeNote);
        layout.AddRow(matchGroup);
        layout.AddRow(appearanceGroup);
        layout.AddRow(_status);
        layout.AddRow(_instruction);
        return layout;
    }

    private void WireEvents()
    {
        _continuity.SelectedIndexChanged += (_, _) =>
        {
            if (_suppressChanges)
            {
                return;
            }

            UpdateCurvatureControlState();
            ScheduleRebuild();
        };
        _refineMatch.CheckedChanged += (_, _) =>
        {
            UpdateCurvatureControlState();
            ScheduleRebuild();
        };
        _curvatureTolerance.ValueChanged += (_, _) => ScheduleRebuild();
        _averageSurfaces.CheckedChanged += (_, _) => ScheduleRebuild();
        _isoDirection.SelectedIndexChanged += (_, _) => ScheduleRebuild();

        _previewOpacity.ValueChanged += (_, _) => UpdateAppearance();
        _showWires.CheckedChanged += (_, _) => UpdateAppearance();

        _rebuildTimer.Elapsed += (_, _) =>
        {
            _rebuildTimer.Stop();
            RebuildNow();
        };

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
            if (!_closingForDecision && !AcceptRequested)
            {
                CancelRequested = true;
            }
        };
    }

    private void UpdateCurvatureControlState()
    {
        _curvatureTolerance.Enabled = _plan.Strategy == SurfaceStrategy.MatchSrf
            && _continuity.SelectedIndex == (int)MatchContinuityLevel.Curvature;
    }

    private void ScheduleRebuild()
    {
        if (_suppressChanges || _plan.Strategy != SurfaceStrategy.MatchSrf)
        {
            return;
        }

        _rebuildTimer.Stop();
        _status.Text = "UPDATING · waiting for the current setting change…";
        _rebuildTimer.Start();
    }

    private void RebuildNow()
    {
        var settings = ReadSettings();
        _status.Text = "UPDATING · rebuilding and measuring one disposable preview…";
        _session.Rebuild(settings);
        RefreshStatus();
    }

    private void UpdateAppearance()
    {
        if (_suppressChanges)
        {
            return;
        }

        var appearance = ReadAppearance();
        _previewOpacityValue.Text = $"{appearance.OpacityPercent.ToString(CultureInfo.InvariantCulture)}%";
        _session.UpdateAppearance(
            _session.CurrentSettings.WithAppearance(
                appearance.OpacityPercent,
                appearance.ShowWires));
    }

    private CandidateBuildSettings ReadSettings()
    {
        var appearance = ReadAppearance();
        return new CandidateBuildSettings(
            (MatchContinuityLevel)_continuity.SelectedIndex,
            _refineMatch.Checked == true,
            _curvatureTolerance.Value,
            _averageSurfaces.Checked == true,
            (MatchIsoDirection)_isoDirection.SelectedIndex,
            appearance.OpacityPercent,
            appearance.ShowWires);
    }

    private (int OpacityPercent, bool ShowWires) ReadAppearance()
    {
        return (_previewOpacity.Value, _showWires.Checked == true);
    }

    private void RefreshStatus()
    {
        var outcome = _session.CurrentOutcome;
        var candidate = _session.Candidate;
        var settings = _session.CurrentSettings;
        if (outcome?.Success == true && candidate is not null)
        {
            var metrics = outcome.Metrics;
            _status.Text = "READY · " + (metrics?.Token ?? "BOUNDED_RESULT")
                + $"\nFaces {candidate.Faces.Count.ToString(CultureInfo.InvariantCulture)}"
                + $" · edges {candidate.Edges.Count.ToString(CultureInfo.InvariantCulture)}"
                + $" · {outcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)} ms"
                + (metrics is null
                    ? string.Empty
                    : $"\nGap {FormatMetric(metrics.MaximumGap)}"
                        + $" · sampled normal {FormatMetric(metrics.MaximumNormalAngleDegrees)}°"
                        + $" · sampled curvature {FormatMetric(metrics.MaximumCurvatureDeviationPercent)}%"
                        + $" · n={metrics.SampleCount.ToString(CultureInfo.InvariantCulture)}")
                + (settings.AverageSurfaces
                    ? $"\nAVERAGE ON · replaces {outcome.ParentObjectCount.ToString(CultureInfo.InvariantCulture)} source Breps with one joined result · first-source attributes"
                    : _plan.Strategy == SurfaceStrategy.MatchSrf
                        ? "\nSources unchanged · adds one matched cap"
                        : "\nSources unchanged · adds one result");
        }
        else
        {
            _status.Text = "BLOCKED · Enter will not change the document"
                + (outcome is null ? string.Empty : $"\n{outcome.Code} · {outcome.Message}");
        }

        _instruction.Text = settings.AverageSurfaces
            ? "Enter / Space / right-click — replace sources with averaged joined result    •    Esc — cancel"
            : _plan.Strategy == SurfaceStrategy.MatchSrf
                ? "Enter / Space / right-click — add matched cap    •    Esc — cancel"
                : "Enter / Space / right-click — add result    •    Esc — cancel";
    }

    private static string FormatMetric(double value)
    {
        if (double.IsNaN(value))
        {
            return "n/a";
        }

        if (double.IsPositiveInfinity(value))
        {
            return "∞";
        }

        return value.ToString("G5", CultureInfo.InvariantCulture);
    }

    private void RequestAccept()
    {
        if (AcceptRequested || CancelRequested)
        {
            return;
        }

        if (!PrepareForAcceptance())
        {
            RefreshStatus();
            return;
        }

        AcceptRequested = true;
        _closingForDecision = true;
        Close();
    }

    private void RequestCancel()
    {
        if (AcceptRequested || CancelRequested)
        {
            return;
        }

        CancelRequested = true;
        _closingForDecision = true;
        _rebuildTimer.Stop();
        Close();
    }

    private void HandleDecisionKey(object? sender, KeyEventArgs eventArgs)
    {
        if (eventArgs.Key == Keys.Escape)
        {
            eventArgs.Handled = true;
            RequestCancel();
            return;
        }

        if (eventArgs.Key == Keys.Enter || eventArgs.Key == Keys.Space)
        {
            eventArgs.Handled = true;
            RequestAccept();
        }
    }
}
