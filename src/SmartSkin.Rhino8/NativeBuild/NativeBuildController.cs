namespace SmartSkin.Rhino8;

// One immutable preview generation. Input observed before the first idle Get cycle cannot accept it.
internal sealed class NativeBuildController
{
    internal enum Phase { Preparing, AwaitingFreshInput, Ready, Confirming, Committed, Cancelled, Invalidated }
    internal Phase Current { get; private set; } = Phase.Preparing;
    internal long Generation { get; private set; }
    private bool _freshInput;
    internal bool Cancelled => Current == Phase.Cancelled || Current == Phase.Invalidated;
    internal void Prepared() { if (Current == Phase.Preparing) Current = Phase.AwaitingFreshInput; }
    internal void InputContextLost()
    {
        _freshInput = false;
        if (Current == Phase.Ready) Current = Phase.AwaitingFreshInput;
    }
    internal void IdleGetCycle(bool confirmationInputsReleased = true, bool inputContextAvailable = true)
    {
        if (!inputContextAvailable) { InputContextLost(); return; }
        _freshInput = false;
        if (Current == Phase.AwaitingFreshInput && confirmationInputsReleased) Current = Phase.Ready;
    }
    internal void ConfirmationInput() { if (Current == Phase.Ready) _freshInput = true; }
    internal bool BeginConfirmation()
    {
        if (Current != Phase.Ready || !_freshInput) return false;
        _freshInput = false; Current = Phase.Confirming; return true;
    }
    internal void Cancel()
    {
        if (Current == Phase.Committed) return;
        _freshInput = false; Current = Phase.Cancelled;
    }
    internal void Invalidate()
    {
        if (Current == Phase.Committed) return;
        Generation++; _freshInput = false; Current = Phase.Invalidated;
    }
    internal void Added() { if (Current == Phase.Confirming) Current = Phase.Committed; }
}

// Completed unmodified same-view clicks only. Timeout/idle cycles do not discard a held click.
internal sealed class NativeBuildClickTracker
{
    private bool _tracking;
    private uint _view;
    private int _x, _y, _dragX, _dragY;
    internal void Down(uint view, int x, int y, bool unmodified, bool ready, int dragX, int dragY)
    {
        _tracking = unmodified && ready && view != 0 && dragX > 0 && dragY > 0;
        _view = view; _x = x; _y = y; _dragX = dragX; _dragY = dragY;
    }
    internal void Cancel() => _tracking = false;
    internal void Move(uint view, int x, int y, bool unmodified)
    {
        if (_tracking && (!unmodified || view != _view || System.Math.Abs((long)x - _x) > _dragX || System.Math.Abs((long)y - _y) > _dragY))
            _tracking = false;
    }
    internal bool Up(uint view, int x, int y, bool unmodified, bool ready)
    {
        Move(view, x, y, unmodified);
        var accepted = _tracking && ready; _tracking = false; return accepted;
    }
}
