using System;
using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

public class CornerWidgetFlowTests
{
    [Fact]
    public void FullLifecycle_GoesIdleToListeningToStoppedAndBack()
    {
        var state = WidgetState.Idle;

        state = CornerWidgetFlow.OpenMenu(state);
        Assert.Equal(WidgetState.MenuOpen, state);

        state = CornerWidgetFlow.Start(state);
        Assert.Equal(WidgetState.Listening, state);

        state = CornerWidgetFlow.Stop(state);
        Assert.Equal(WidgetState.Stopped, state);

        state = CornerWidgetFlow.Reset(state);
        Assert.Equal(WidgetState.Idle, state);
    }

    [Theory]
    [InlineData(WidgetState.Idle)]
    [InlineData(WidgetState.Listening)]
    [InlineData(WidgetState.Stopped)]
    public void Start_OnlyFiresFromMenuOpen_OtherwiseNoOp(WidgetState current)
    {
        Assert.Equal(current, CornerWidgetFlow.Start(current));
    }

    [Theory]
    [InlineData(WidgetState.Idle)]
    [InlineData(WidgetState.MenuOpen)]
    [InlineData(WidgetState.Stopped)]
    public void Stop_OnlyFiresFromListening_OtherwiseNoOp(WidgetState current)
    {
        Assert.Equal(current, CornerWidgetFlow.Stop(current));
    }

    [Fact]
    public void CallMode_DefaultsToVideoCall_AndUpdatesWhenSelectedOrStarted()
    {
        var flow = new CornerWidgetFlow();
        Assert.Equal(CallMode.VideoCall, flow.CallMode);
        Assert.Equal("#FFD54A", flow.IndicatorColorHex);

        flow.OpenMenu();
        flow.SelectCallMode(CallMode.PhoneSpeaker);
        Assert.Equal(CallMode.PhoneSpeaker, flow.CallMode);

        flow.Start();
        Assert.Equal(WidgetState.Listening, flow.State);
        Assert.Equal(CallMode.PhoneSpeaker, flow.CallMode);
        Assert.Equal("Finding it…", flow.StatusText);
        Assert.Equal(IndicatorStatus.Active, flow.Indicator);
        Assert.Equal("#2EAD6B", flow.IndicatorColorHex);
    }

    [Fact]
    public void TextScale_IncrementsAndDecrementsByTenths_AndClampsBetween0Point9And1Point4()
    {
        var flow = new CornerWidgetFlow();
        Assert.Equal(1.0, flow.TextScale);

        Assert.Equal(0.9, flow.DecreaseTextScale());
        Assert.Equal(0.9, flow.DecreaseTextScale()); // Clamped at 0.9

        Assert.Equal(1.0, flow.IncreaseTextScale());
        Assert.Equal(1.1, flow.IncreaseTextScale());
        Assert.Equal(1.2, flow.IncreaseTextScale());
        Assert.Equal(1.3, flow.IncreaseTextScale());
        Assert.Equal(1.4, flow.IncreaseTextScale());
        Assert.Equal(1.4, flow.IncreaseTextScale()); // Clamped at 1.4
    }

    [Fact]
    public void ReadAloud_And_ControlsTray_ToggleStateCorrectly()
    {
        var flow = new CornerWidgetFlow();
        Assert.False(flow.IsReadAloudEnabled);
        Assert.False(flow.IsControlsTrayOpen);

        Assert.True(flow.ToggleReadAloud());
        Assert.True(flow.IsReadAloudEnabled);

        Assert.False(flow.ToggleReadAloud());
        Assert.False(flow.IsReadAloudEnabled);

        Assert.True(flow.ToggleControlsTray());
        Assert.True(flow.IsControlsTrayOpen);

        Assert.False(flow.ToggleControlsTray());
        Assert.False(flow.IsControlsTrayOpen);
    }

    [Fact]
    public void MultiStepFlow2Progression_TracksStepsStatusesAndCaptions()
    {
        var flow = new CornerWidgetFlow();
        flow.OpenMenu();
        flow.Start(CallMode.VideoCall);

        var plan = new[]
        {
            new GuidanceStep("Print", "Click Print", "The blue button at the bottom right of this window."),
            new GuidanceStep("OK", "Click OK")
        };

        // Screen 1: Location returned
        flow.LoadPlan(plan);
        Assert.Equal(GuidanceStage.LocationReturned, flow.Stage);
        Assert.Equal("Found it", flow.StatusText);
        Assert.Equal(1, flow.CurrentStep);
        Assert.Equal(2, flow.TotalSteps);
        Assert.Equal("Step 1 of 2: Click Print", flow.StepSummaryText);
        Assert.Equal("The blue button at the bottom right of this window.", flow.StepCaption);
        Assert.Equal("#2EAD6B", flow.IndicatorColorHex);

        // Screen 2: Draw mouse path
        flow.SetFollowTrail();
        Assert.Equal(GuidanceStage.FollowTrail, flow.Stage);
        Assert.Equal("Follow the trail", flow.StatusText);

        // Screen 3: Highlight target
        flow.SetHighlightTarget();
        Assert.Equal(GuidanceStage.HighlightTarget, flow.Stage);
        Assert.Equal("Click the glowing button", flow.StatusText);

        // Screen 4: Text overlay / explicit SetStep
        flow.SetStep(1, 2, "Click Print", "The blue button at the bottom right of this window.");
        Assert.Equal(GuidanceStage.TextOverlay, flow.Stage);
        Assert.Equal("Click the glowing button", flow.StatusText);
        Assert.Equal("Step 1 of 2: Click Print", flow.StepSummaryText);
        Assert.Equal("The blue button at the bottom right of this window.", flow.StepCaption);

        // Screen 5: Click and confirm -> Advance to Step 2
        flow.SetStepCompleted();
        Assert.Equal(GuidanceStage.StepCompleted, flow.Stage);
        Assert.Equal("Done! Waiting for the next step", flow.StatusText);

        Assert.True(flow.AdvanceToNextStep());
        Assert.Equal(2, flow.CurrentStep);
        Assert.Equal(2, flow.TotalSteps);
        Assert.Equal("Step 2 of 2: Click OK", flow.StepSummaryText);
        Assert.Equal("Click the glowing button", flow.StatusText);
        Assert.Null(flow.StepCaption);

        // No further steps after Step 2
        Assert.False(flow.AdvanceToNextStep());
    }

    [Fact]
    public void NoStepsFallback_SetsExpectedMessageAndErrorIndicator()
    {
        var flow = new CornerWidgetFlow();
        flow.OpenMenu();
        flow.Start();

        flow.LoadPlan(Array.Empty<GuidanceStep>());

        Assert.Equal(GuidanceStage.NoStepsError, flow.Stage);
        Assert.Equal("I could not work out the steps. Ask your helper to say it another way", flow.StatusText);
        Assert.True(flow.IsError);
        Assert.Equal(IndicatorStatus.Error, flow.Indicator);
        Assert.Equal("#FF5A52", flow.IndicatorColorHex);
        Assert.False(flow.HasActiveStep);
    }

    [Fact]
    public void ApiErrorFallback_SetsExpectedMessageAndRedErrorIndicator()
    {
        var flow = new CornerWidgetFlow();
        flow.OpenMenu();
        flow.Start();
        flow.SetStep(1, 2, "Click Print", "The blue button at the bottom right of this window.");

        flow.SetApiErrorFallback();

        Assert.Equal(GuidanceStage.ApiError, flow.Stage);
        Assert.Equal("Something went wrong. Ask your helper to try again", flow.StatusText);
        Assert.True(flow.IsError);
        Assert.Equal(IndicatorStatus.Error, flow.Indicator);
        Assert.Equal("#FF5A52", flow.IndicatorColorHex);
        Assert.False(flow.HasActiveStep);
    }
}
