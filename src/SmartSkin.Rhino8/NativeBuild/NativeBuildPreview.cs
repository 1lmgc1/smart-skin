using System;
using Eto.Drawing;
using Eto.Forms;
using Rhino;
using Rhino.Display;
using Rhino.UI;

namespace SmartSkin.Rhino8;

internal sealed class NativeBuildPreview : DisplayConduit, IDisposable
{
    private readonly uint _document;
    private readonly NativeCompareCandidate _candidate;
    private readonly DisplayMaterial _material = new(System.Drawing.Color.FromArgb(0, 174, 239), .25);
    internal NativeBuildPreview(RhinoDoc document, NativeCompareCandidate candidate)
    { _document = document.RuntimeSerialNumber; _candidate = candidate; }
    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs args)
    {
        if (args.RhinoDoc?.RuntimeSerialNumber == _document && _candidate.Bounds.IsValid) args.IncludeBoundingBox(_candidate.Bounds);
    }
    protected override void PreDrawObjects(DrawEventArgs args)
    {
        if (args.RhinoDoc?.RuntimeSerialNumber != _document) return;
        foreach (var mesh in _candidate.Meshes) args.Display.DrawMeshShaded(mesh, _material);
        args.Display.DrawBrepWires(_candidate.Brep, System.Drawing.Color.DarkCyan, 1);
    }
    public void Dispose() { Enabled = false; _material.Dispose(); }
}

internal sealed class NativeBuildStatusForm : Form
{
    private readonly NativeBuildController _controller;
    private readonly Label _instruction = new() { Wrap = WrapMode.Word };
    private readonly Button _create = new() { Text = "Создать поверхность", Enabled = false };
    private bool _closingForCommand;
    internal NativeBuildStatusForm(RhinoDoc document, NativeBuildController controller)
    {
        _controller = controller;
        Title = "Smart Skin"; ClientSize = new Size(430, 220); Resizable = false;
        Maximizable = false; Minimizable = false; ShowActivated = false;
        Owner = RhinoEtoApp.MainWindowForDocument(document); this.UseRhinoStyle();
        var layout = new DynamicLayout { Padding = new Padding(16), Spacing = new Size(8, 10) };
        layout.AddRow(new Label { Text = NativeBuildCapQualification.UserStatus, Wrap = WrapMode.Word });
        layout.AddRow(new Label { Text = "Предпросмотр новой поверхности. Исходные поверхности сохраняются.", Wrap = WrapMode.Word });
        _instruction.Text = "Подготовка подтверждения…";
        layout.AddRow(_instruction);
        layout.AddRow(_create); Content = layout;
        // Not a default/cancel button and never auto-focused. Click requests confirmation;
        // only the command loop may invoke the checked document transaction.
        _create.Click += (_, _) =>
        {
            _create.Enabled = false;
            if (_controller.BeginButtonConfirmation()) _instruction.Text = "Создание поверхности…";
        };
        KeyDown += (_, args) =>
        {
            if (args.Key == Keys.Escape) { args.Handled = true; Cancel(); }
            else if (args.Key == Keys.Enter || args.Key == Keys.Space)
            {
                args.Handled = true;
                var key = args.Key == Keys.Enter ? 13 : 32;
                if (NativeBuildPhysicalInput.ConfirmationEventAllowed(key))
                { _controller.ConfirmationInput(); _controller.BeginConfirmation(); }
            }
        };
        Closing += (_, _) => { _create.Enabled = false; if (!_closingForCommand) _controller.Cancel(); };
    }
    internal void Prepared()
    {
        _create.Enabled = true;
        _instruction.Text = "Нажмите «Создать поверхность».\nEsc или закрытие окна — отменить.";
    }
    internal void Ready()
    {
        if (_controller.Current != NativeBuildController.Phase.Ready) return;
        _instruction.Text = "Нажмите «Создать поверхность» или Enter / Space / правую кнопку мыши.\nEsc или закрытие окна — отменить.";
    }
    internal void Cancel() { _create.Enabled = false; _controller.Cancel(); }
    internal void CloseForCommand() { _closingForCommand = true; _create.Enabled = false; Close(); }
}

internal sealed class NativeBuildMouseConfirmation : MouseCallback, IDisposable
{
    private readonly uint _document;
    private readonly NativeBuildController _controller;
    private readonly NativeBuildClickTracker _click = new();
    internal NativeBuildMouseConfirmation(RhinoDoc document, NativeBuildController controller)
    { _document = document.RuntimeSerialNumber; _controller = controller; }
    protected override void OnMouseDown(MouseCallbackEventArgs args)
    {
        if (args.MouseButton != MouseButton.Right) return;
        _click.Down(args.View?.RuntimeSerialNumber ?? 0, args.ViewportPoint.X, args.ViewportPoint.Y,
            Unmodified(args), _controller.Current == NativeBuildController.Phase.Ready,
            NativeBuildPhysicalInput.DragWidth, NativeBuildPhysicalInput.DragHeight);
    }
    protected override void OnMouseMove(MouseCallbackEventArgs args) => _click.Move(args.View?.RuntimeSerialNumber ?? 0,
        args.ViewportPoint.X, args.ViewportPoint.Y, Unmodified(args));
    protected override void OnMouseUp(MouseCallbackEventArgs args)
    {
        if (args.MouseButton == MouseButton.Right && _click.Up(args.View?.RuntimeSerialNumber ?? 0,
            args.ViewportPoint.X, args.ViewportPoint.Y, Unmodified(args), _controller.Current == NativeBuildController.Phase.Ready))
        { _controller.ConfirmationInput(); _controller.BeginConfirmation(); }
    }
    internal void CancelGesture() => _click.Cancel();
    internal void Idle() { if (!NativeBuildPhysicalInput.Unmodified || _controller.Cancelled) _click.Cancel(); }
    private bool Unmodified(MouseCallbackEventArgs args) => args.View?.Document?.RuntimeSerialNumber == _document
        && !args.ShiftKeyDown && !args.CtrlKeyDown && NativeBuildPhysicalInput.Unmodified;
    public void Dispose() { Enabled = false; }
}
