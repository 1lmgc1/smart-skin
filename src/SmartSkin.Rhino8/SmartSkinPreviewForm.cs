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
    private static readonly string[] PresetNames =
    {
        "Balanced",
        "Stiff",
        "Flexible",
        "Detailed",
        "Custom",
    };

    private readonly CandidateConstructionPlan _plan;
    private readonly SmartSkinLivePreviewSession _session;
    private readonly DropDown _preset = new();
    private readonly NumericStepper _uSpans = new();
    private readonly NumericStepper _vSpans = new();
    private readonly NumericStepper _sampleSpacingPercent = new();
    private readonly NumericStepper _flexibility = new();
    private readonly CheckBox _adjustTangency = new();
    private readonly CheckBox _automaticTrim = new();
    private readonly Slider _previewOpacity = new();
    private readonly Label _previewOpacityValue = new();
    private readonly CheckBox _showWires = new();
    private readonly Label _status = new();
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

        Title = "Smart Skin — result preview";
        ClientSize = new Size(440, 590);
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

        _preset.DataStore = PresetNames;
        _preset.SelectedIndex = (int)settings.Preset;
        _preset.Width = 205;

        ConfigureStepper(
            _uSpans,
            CandidateBuildSettings.MinimumSpans,
            CandidateBuildSettings.MaximumSpans,
            settings.USpans,
            increment: 1.0,
            decimalPlaces: 0,
            "Surface control-point spans in the U direction.");
        ConfigureStepper(
            _vSpans,
            CandidateBuildSettings.MinimumSpans,
            CandidateBuildSettings.MaximumSpans,
            settings.VSpans,
            increment: 1.0,
            decimalPlaces: 0,
            "Surface control-point spans in the V direction.");
        ConfigureStepper(
            _sampleSpacingPercent,
            CandidateBuildSettings.MinimumSampleSpacingScale * 100.0,
            CandidateBuildSettings.MaximumSampleSpacingScale * 100.0,
            settings.SampleSpacingScale * 100.0,
            increment: 25.0,
            decimalPlaces: 0,
            "Spacing between boundary samples. Lower values sample the edge more densely.");
        ConfigureStepper(
            _flexibility,
            CandidateBuildSettings.MinimumFlexibility,
            CandidateBuildSettings.MaximumFlexibility,
            settings.Flexibility,
            increment: 0.1,
            decimalPlaces: 3,
            "Lower values make the result stiffer; higher values make it more flexible.");

        _adjustTangency.Text = "Match boundary tangency (G1 request)";
        _adjustTangency.Checked = settings.AdjustTangency;
        _adjustTangency.ToolTip = "Use adjacent Brep-face normals while fitting the Patch.";

        _automaticTrim.Text = "Trim result to selected boundary";
        _automaticTrim.Checked = settings.AutomaticTrim;
        _automaticTrim.ToolTip = "Return the Patch trimmed to the selected closed edge loop.";

        _previewOpacity.MinValue = CandidateBuildSettings.MinimumPreviewOpacity;
        _previewOpacity.MaxValue = CandidateBuildSettings.MaximumPreviewOpacity;
        _previewOpacity.Value = settings.PreviewOpacityPercent;
        _previewOpacity.TickFrequency = 5;
        _previewOpacity.SnapToTick = true;
        _previewOpacity.Width = 205;
        _previewOpacityValue.Text = $"{settings.PreviewOpacityPercent.ToString(CultureInfo.InvariantCulture)}%";

        _showWires.Text = "Show preview wires";
        _showWires.Checked = settings.ShowWires;

        var patchControlsEnabled = _plan.Strategy == SurfaceStrategy.Patch;
        _preset.Enabled = patchControlsEnabled;
        _uSpans.Enabled = patchControlsEnabled;
        _vSpans.Enabled = patchControlsEnabled;
        _sampleSpacingPercent.Enabled = patchControlsEnabled;
        _flexibility.Enabled = patchControlsEnabled;
        _adjustTangency.Enabled = patchControlsEnabled;
        _automaticTrim.Enabled = patchControlsEnabled;

        _rebuildTimer.Interval = 0.25;
        _suppressChanges = false;
    }

    private Control BuildLayout()
    {
        var heading = new Label
        {
            Text = $"Result: {_plan.StrategyToken}",
            Wrap = WrapMode.Word,
        };

        var routeNote = new Label
        {
            Text = _plan.Strategy == SurfaceStrategy.Patch
                ? "Tune the Patch while its cyan preview stays in the viewport."
                : "This route uses its bounded native construction. Patch controls are disabled.",
            Wrap = WrapMode.Word,
        };

        var reset = new Button
        {
            Text = "Reset Balanced",
            ToolTip = "Restore the bounded default Patch settings.",
            Enabled = _plan.Strategy == SurfaceStrategy.Patch,
        };
        reset.Click += (_, _) => ApplyPreset(CandidatePreset.Balanced, scheduleRebuild: true);

        var patchLayout = new DynamicLayout
        {
            Padding = new Padding(10),
            Spacing = new Size(8, 7),
        };
        patchLayout.AddRow(new Label { Text = "Preset" }, _preset);
        patchLayout.AddRow(new Label { Text = "U spans" }, _uSpans);
        patchLayout.AddRow(new Label { Text = "V spans" }, _vSpans);
        patchLayout.AddRow(new Label { Text = "Sample spacing" }, _sampleSpacingPercent);
        patchLayout.AddRow(new Label { Text = "Flexibility" }, _flexibility);
        patchLayout.AddRow(_adjustTangency);
        patchLayout.AddRow(_automaticTrim);
        patchLayout.AddRow(reset);

        var patchGroup = new GroupBox
        {
            Text = "Patch result settings",
            Content = patchLayout,
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
        _status.Height = 82;

        var instruction = new Label
        {
            Text = "Enter / Space / right-click — add one Brep    •    Esc — cancel",
            Wrap = WrapMode.Word,
        };

        var layout = new DynamicLayout
        {
            Padding = new Padding(14),
            Spacing = new Size(8, 9),
        };
        layout.AddRow(heading);
        layout.AddRow(routeNote);
        layout.AddRow(patchGroup);
        layout.AddRow(appearanceGroup);
        layout.AddRow(_status);
        layout.AddRow(instruction);
        return layout;
    }

    private void WireEvents()
    {
        _preset.SelectedIndexChanged += (_, _) =>
        {
            if (_suppressChanges)
            {
                return;
            }

            var selected = (CandidatePreset)_preset.SelectedIndex;
            if (selected != CandidatePreset.Custom)
            {
                ApplyPreset(selected, scheduleRebuild: true);
            }
        };

        _uSpans.ValueChanged += (_, _) => MarkCustomAndSchedule();
        _vSpans.ValueChanged += (_, _) => MarkCustomAndSchedule();
        _sampleSpacingPercent.ValueChanged += (_, _) => MarkCustomAndSchedule();
        _flexibility.ValueChanged += (_, _) => MarkCustomAndSchedule();
        _adjustTangency.CheckedChanged += (_, _) => MarkCustomAndSchedule();
        _automaticTrim.CheckedChanged += (_, _) => MarkCustomAndSchedule();

        _previewOpacity.ValueChanged += (_, _) => UpdateAppearance();
        _showWires.CheckedChanged += (_, _) => UpdateAppearance();

        _rebuildTimer.Elapsed += (_, _) =>
        {
            _rebuildTimer.Stop();
            RebuildNow();
        };

        KeyDown += HandleDecisionKey;
        _preset.KeyDown += HandleDecisionKey;
        _uSpans.KeyDown += HandleDecisionKey;
        _vSpans.KeyDown += HandleDecisionKey;
        _sampleSpacingPercent.KeyDown += HandleDecisionKey;
        _flexibility.KeyDown += HandleDecisionKey;
        _adjustTangency.KeyDown += HandleDecisionKey;
        _automaticTrim.KeyDown += HandleDecisionKey;
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

    private static void ConfigureStepper(
        NumericStepper stepper,
        double minimum,
        double maximum,
        double value,
        double increment,
        int decimalPlaces,
        string toolTip)
    {
        stepper.MinValue = minimum;
        stepper.MaxValue = maximum;
        stepper.Value = value;
        stepper.Increment = increment;
        stepper.DecimalPlaces = decimalPlaces;
        stepper.MaximumDecimalPlaces = Math.Max(decimalPlaces, 3);
        stepper.Width = 205;
        stepper.ToolTip = toolTip;
    }

    private void ApplyPreset(CandidatePreset preset, bool scheduleRebuild)
    {
        var appearance = ReadAppearance();
        var settings = CandidateBuildSettings.CreatePreset(
            preset,
            appearance.OpacityPercent,
            appearance.ShowWires);

        _suppressChanges = true;
        _preset.SelectedIndex = (int)preset;
        _uSpans.Value = settings.USpans;
        _vSpans.Value = settings.VSpans;
        _sampleSpacingPercent.Value = settings.SampleSpacingScale * 100.0;
        _flexibility.Value = settings.Flexibility;
        _adjustTangency.Checked = settings.AdjustTangency;
        _automaticTrim.Checked = settings.AutomaticTrim;
        _suppressChanges = false;

        if (scheduleRebuild)
        {
            ScheduleRebuild();
        }
    }

    private void MarkCustomAndSchedule()
    {
        if (_suppressChanges || _plan.Strategy != SurfaceStrategy.Patch)
        {
            return;
        }

        _suppressChanges = true;
        _preset.SelectedIndex = (int)CandidatePreset.Custom;
        _suppressChanges = false;
        ScheduleRebuild();
    }

    private void ScheduleRebuild()
    {
        _rebuildTimer.Stop();
        _status.Text = "UPDATING · waiting for the current setting change…";
        _rebuildTimer.Start();
    }

    private void RebuildNow()
    {
        var settings = ReadSettings();
        _status.Text = "UPDATING · rebuilding one disposable preview…";
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
            (CandidatePreset)_preset.SelectedIndex,
            (int)Math.Round(_uSpans.Value),
            (int)Math.Round(_vSpans.Value),
            _sampleSpacingPercent.Value / 100.0,
            _flexibility.Value,
            _adjustTangency.Checked == true,
            _automaticTrim.Checked == true,
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
        if (outcome?.Success == true && candidate is not null)
        {
            var settings = _session.CurrentSettings;
            _status.Text = "READY · one valid in-memory Brep"
                + $"\nFaces {candidate.Faces.Count.ToString(CultureInfo.InvariantCulture)}"
                + $" · edges {candidate.Edges.Count.ToString(CultureInfo.InvariantCulture)}"
                + $" · {outcome.ElapsedMilliseconds.ToString(CultureInfo.InvariantCulture)} ms"
                + (_plan.Strategy == SurfaceStrategy.Patch
                    ? $"\n{settings.PresetToken} · {settings.USpans.ToString(CultureInfo.InvariantCulture)}×{settings.VSpans.ToString(CultureInfo.InvariantCulture)} spans"
                        + $" · sample {settings.SampleSpacingScale.ToString("0.##", CultureInfo.InvariantCulture)}×"
                        + $" · flexibility {settings.Flexibility.ToString("G4", CultureInfo.InvariantCulture)}"
                    : string.Empty);
            return;
        }

        _status.Text = "BLOCKED · no candidate will be added"
            + (outcome is null ? string.Empty : $"\n{outcome.Message}");
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
