using SmartSkin.Rhino8;
using Xunit;

namespace SmartSkin.Core.Tests;

public sealed class NativeBuildControllerTests
{
    [Fact]
    public void SelectionEnterAndPreparationTypeaheadCannotConfirmReadyPreview()
    {
        var flow = new NativeBuildController();
        flow.ConfirmationInput(); Assert.False(flow.BeginConfirmation());
        flow.Prepared(); flow.ConfirmationInput(); Assert.False(flow.BeginConfirmation());
        flow.IdleGetCycle(); Assert.Equal(NativeBuildController.Phase.Ready, flow.Current);
        Assert.False(flow.BeginConfirmation());
    }
    [Fact]
    public void NativeNothingRequiresFreshInputInTheReadyGetCycle()
    {
        var flow = Ready();
        Assert.False(flow.BeginConfirmation());
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
        Assert.False(flow.BeginConfirmation());
    }
    [Fact]
    public void UnconsumedInputExpiresAtNextIdleCycle()
    {
        var flow = Ready(); flow.ConfirmationInput(); flow.IdleGetCycle();
        Assert.False(flow.BeginConfirmation());
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
    }
    [Fact]
    public void LongPassiveInspectionDoesNotInvalidateGeneration()
    {
        var flow = Ready(); var generation = flow.Generation;
        for (var i = 0; i < 1000; i++) flow.IdleGetCycle();
        Assert.Equal(generation, flow.Generation);
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
    }
    [Fact]
    public void EscapeOrWindowCloseBeforeAndDuringAddRemainsCancellation()
    {
        var before = Ready(); before.Cancel(); before.ConfirmationInput();
        Assert.False(before.BeginConfirmation()); Assert.True(before.Cancelled);
        var during = Ready(); during.ConfirmationInput(); Assert.True(during.BeginConfirmation());
        during.Cancel(); during.Added();
        Assert.True(during.Cancelled); Assert.Equal(NativeBuildController.Phase.Cancelled, during.Current);
    }
    [Fact]
    public void ReentrantDocumentEditInvalidatesTheDisplayedGeneration()
    {
        var flow = Ready(); flow.ConfirmationInput(); var generation = flow.Generation;
        flow.Invalidate(); Assert.Equal(generation + 1, flow.Generation);
        Assert.False(flow.BeginConfirmation()); Assert.True(flow.Cancelled);
        flow.Prepared(); flow.IdleGetCycle(); flow.ConfirmationInput();
        Assert.False(flow.BeginConfirmation());
    }
    [Fact]
    public void SuccessfulCommitCleanupCannotBecomeLateCancellation()
    {
        var flow = Ready(); flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation()); flow.Added();
        flow.Cancel(); flow.Invalidate();
        Assert.Equal(NativeBuildController.Phase.Committed, flow.Current); Assert.False(flow.Cancelled);
    }
    [Fact]
    public void ReadyWithoutExplicitConfirmationCannotBeMarkedAdded()
    {
        var flow = Ready(); flow.Added();
        Assert.Equal(NativeBuildController.Phase.Ready, flow.Current);
    }
    [Fact]
    public void HeldSelectionKeyCannotArmThroughTimeoutOrAutoRepeat()
    {
        var flow = new NativeBuildController(); flow.Prepared();
        for (var repeat = 0; repeat < 20; repeat++)
        { flow.IdleGetCycle(false); flow.ConfirmationInput(); Assert.False(flow.BeginConfirmation()); }
        Assert.Equal(NativeBuildController.Phase.AwaitingFreshInput, flow.Current);
        flow.IdleGetCycle(true); Assert.False(flow.BeginConfirmation());
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
    }
    [Fact]
    public void CompletedSlowRightClickSurvivesIdleTimeoutAndIsOneUse()
    {
        var flow = Ready(); var click = new NativeBuildClickTracker();
        click.Down(7, 40, 50, true, true, 4, 4);
        flow.IdleGetCycle(false); flow.IdleGetCycle(false);
        Assert.True(click.Up(7, 41, 50, true, flow.Current == NativeBuildController.Phase.Ready));
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
        Assert.False(click.Up(7, 41, 50, true, true));
    }
    [Fact]
    public void RightDragOrModifierOrChangedViewDoesNotAuthorizeAnAdd()
    {
        var click = new NativeBuildClickTracker();
        click.Down(7, 40, 50, true, true, 4, 4); click.Move(7, 80, 50, true);
        Assert.False(click.Up(7, 40, 50, true, true));
        click.Down(7, 40, 50, false, true, 4, 4); Assert.False(click.Up(7, 40, 50, true, true));
        click.Down(7, 40, 50, true, true, 4, 4); Assert.False(click.Up(7, 40, 50, false, true));
        click.Down(7, 40, 50, true, true, 4, 4); Assert.False(click.Up(8, 40, 50, true, true));
    }
    [Fact]
    public void CancelledOrPreReadyClickCannotBeReusedAfterReady()
    {
        var click = new NativeBuildClickTracker();
        click.Down(7, 40, 50, true, false, 4, 4); Assert.False(click.Up(7, 40, 50, true, true));
        click.Down(7, 40, 50, true, true, 4, 4); Assert.False(click.Up(7, 40, 50, true, false));
        Assert.False(click.Up(7, 40, 50, true, true));
        click.Down(7, 40, 50, true, true, 4, 4); Assert.True(click.Up(7, 40, 50, true, true));
    }
    [Fact]
    public void ReturningFromLostFocusWithHeldEnterRequiresReleaseAndAnotherPress()
    {
        var flow = Ready(); flow.ConfirmationInput(); flow.IdleGetCycle(true, false);
        Assert.Equal(NativeBuildController.Phase.AwaitingFreshInput, flow.Current);
        flow.IdleGetCycle(false, true); flow.ConfirmationInput(); Assert.False(flow.BeginConfirmation());
        flow.IdleGetCycle(true, true); Assert.False(flow.BeginConfirmation());
        flow.ConfirmationInput(); Assert.True(flow.BeginConfirmation());
    }
    private static NativeBuildController Ready()
    {
        var flow = new NativeBuildController(); flow.Prepared(); flow.IdleGetCycle(); return flow;
    }
}
