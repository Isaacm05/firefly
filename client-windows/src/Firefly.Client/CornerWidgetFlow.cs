using System;
using System.Collections.Generic;

namespace Firefly.Client;

public enum WidgetState
{
    Idle,
    MenuOpen,
    Listening,
    Stopped
}

public enum CallMode
{
    VideoCall,
    PhoneSpeaker
}

public enum IndicatorStatus
{
    Idle,
    Active,
    Error
}

public enum GuidanceStage
{
    None,
    Finding,
    LocationReturned,
    FollowTrail,
    HighlightTarget,
    TextOverlay,
    StepCompleted,
    NoStepsError,
    ApiError
}

public record GuidanceStep(string Label, string Instruction, string? Caption = null);

/// <summary>Pure state transitions and Flow 2 guidance state model for the corner widget (issue #34):
/// idle pill -> start menu -> listening bar -> stopped toast -> back to idle, plus call mode,
/// text scaling, read-aloud toggle, step progression, and error fallbacks.
/// No WPF dependency so it is cheaply testable.</summary>
public class CornerWidgetFlow
{
    public const double DefaultTextScale = 1.0;
    public const double MinTextScale = 0.9;
    public const double MaxTextScale = 1.4;
    public const double TextScaleStep = 0.1;

    public const string IdleColorHex = "#FFD54A";
    public const string ActiveColorHex = "#2EAD6B";
    public const string ErrorColorHex = "#FF5A52";

    public const string FindingStatus = "Finding it…";
    public const string FoundStatus = "Found it";
    public const string FollowTrailStatus = "Follow the trail";
    public const string HighlightTargetStatus = "Click the glowing button";
    public const string StepCompletedStatus = "Done! Waiting for the next step";
    public const string NoStepsFallbackMessage = "I could not work out the steps. Ask your helper to say it another way";
    public const string ApiErrorFallbackMessage = "Something went wrong. Ask your helper to try again";

    private readonly List<GuidanceStep> _steps = new();

    public WidgetState State { get; private set; } = WidgetState.Idle;
    public CallMode CallMode { get; private set; } = CallMode.VideoCall;
    public bool IsReadAloudEnabled { get; private set; }
    public bool IsControlsTrayOpen { get; private set; }
    public double TextScale { get; private set; } = DefaultTextScale;

    public GuidanceStage Stage { get; private set; } = GuidanceStage.None;
    public IndicatorStatus Indicator { get; private set; } = IndicatorStatus.Idle;
    public string StatusText { get; private set; } = FindingStatus;

    public int CurrentStep { get; private set; }
    public int TotalSteps { get; private set; }
    public string? StepInstruction { get; private set; }
    public string? StepCaption { get; private set; }
    public string? StepSummaryText =>
        CurrentStep > 0 && TotalSteps > 0 && !string.IsNullOrWhiteSpace(StepInstruction)
            ? $"Step {CurrentStep} of {TotalSteps}: {StepInstruction}"
            : null;

    public bool HasActiveStep => CurrentStep > 0 && TotalSteps > 0 && !string.IsNullOrWhiteSpace(StepInstruction);
    public bool IsError => Indicator == IndicatorStatus.Error;
    public IReadOnlyList<GuidanceStep> Steps => _steps;

    public string IndicatorColorHex => Indicator switch
    {
        IndicatorStatus.Active => ActiveColorHex,
        IndicatorStatus.Error => ErrorColorHex,
        _ => IdleColorHex
    };

    // ---- Pure static transitions (kept compatible with existing callers) ----

    public static WidgetState OpenMenu(WidgetState current) =>
        current == WidgetState.Idle ? WidgetState.MenuOpen : current;

    public static WidgetState CloseMenu(WidgetState current) =>
        current == WidgetState.MenuOpen ? WidgetState.Idle : current;

    public static WidgetState Start(WidgetState current) =>
        current == WidgetState.MenuOpen ? WidgetState.Listening : current;

    public static WidgetState Stop(WidgetState current) =>
        current == WidgetState.Listening ? WidgetState.Stopped : current;

    public static WidgetState Reset(WidgetState current) =>
        current == WidgetState.Stopped ? WidgetState.Idle : current;

    public static double ClampTextScale(double scale) =>
        Math.Round(Math.Clamp(scale, MinTextScale, MaxTextScale), 1, MidpointRounding.AwayFromZero);

    // ---- Instance transitions & Flow 2 state management ----

    public WidgetState OpenMenu()
    {
        State = OpenMenu(State);
        if (State == WidgetState.MenuOpen)
        {
            Indicator = IndicatorStatus.Idle;
        }
        return State;
    }

    public WidgetState CloseMenu()
    {
        State = CloseMenu(State);
        if (State == WidgetState.Idle)
        {
            Indicator = IndicatorStatus.Idle;
        }
        return State;
    }

    public void SelectCallMode(CallMode mode) => CallMode = mode;

    public WidgetState Start(CallMode? mode = null)
    {
        if (mode.HasValue)
        {
            CallMode = mode.Value;
        }

        var next = Start(State);
        if (next != State)
        {
            State = next;
            IsControlsTrayOpen = false;
            SetFinding();
        }
        return State;
    }

    public WidgetState Stop()
    {
        var next = Stop(State);
        if (next != State)
        {
            State = next;
            Stage = GuidanceStage.None;
            Indicator = IndicatorStatus.Idle;
            IsControlsTrayOpen = false;
            ClearStepDetails();
        }
        return State;
    }

    public WidgetState Reset()
    {
        var next = Reset(State);
        if (next != State)
        {
            State = next;
            Stage = GuidanceStage.None;
            Indicator = IndicatorStatus.Idle;
            StatusText = FindingStatus;
            IsControlsTrayOpen = false;
            ClearStepDetails();
        }
        return State;
    }

    public bool ToggleControlsTray()
    {
        IsControlsTrayOpen = !IsControlsTrayOpen;
        return IsControlsTrayOpen;
    }

    public void SetControlsTrayOpen(bool open) => IsControlsTrayOpen = open;

    public bool ToggleReadAloud()
    {
        IsReadAloudEnabled = !IsReadAloudEnabled;
        return IsReadAloudEnabled;
    }

    public void SetReadAloud(bool enabled) => IsReadAloudEnabled = enabled;

    public double IncreaseTextScale()
    {
        TextScale = ClampTextScale(TextScale + TextScaleStep);
        return TextScale;
    }

    public double DecreaseTextScale()
    {
        TextScale = ClampTextScale(TextScale - TextScaleStep);
        return TextScale;
    }

    public void SetFinding()
    {
        EnsureListening();
        Stage = GuidanceStage.Finding;
        Indicator = IndicatorStatus.Active;
        StatusText = FindingStatus;
        ClearStepDetails();
    }

    public void LoadPlan(IEnumerable<GuidanceStep>? steps, string? firstTargetCaption = null)
    {
        EnsureListening();
        _steps.Clear();
        if (steps != null)
        {
            _steps.AddRange(steps);
        }

        if (_steps.Count == 0)
        {
            SetNoStepsFallback();
            return;
        }

        var first = _steps[0];
        var caption = firstTargetCaption ?? first.Caption;
        SetStep(1, _steps.Count, first.Instruction, caption);
        Stage = GuidanceStage.LocationReturned;
        StatusText = FoundStatus;
    }

    public void SetStep(int currentStep, int totalSteps, string instruction, string? caption = null)
    {
        if (currentStep < 1) throw new ArgumentOutOfRangeException(nameof(currentStep));
        if (totalSteps < currentStep) throw new ArgumentOutOfRangeException(nameof(totalSteps));
        if (string.IsNullOrWhiteSpace(instruction)) throw new ArgumentException("Instruction cannot be empty.", nameof(instruction));

        EnsureListening();
        CurrentStep = currentStep;
        TotalSteps = totalSteps;
        StepInstruction = instruction.Trim();
        StepCaption = string.IsNullOrWhiteSpace(caption) ? null : caption.Trim();
        Stage = string.IsNullOrWhiteSpace(StepCaption) ? GuidanceStage.HighlightTarget : GuidanceStage.TextOverlay;
        Indicator = IndicatorStatus.Active;
        // Match Figma Flow 2: top-right corner bubble shows the clean guidance cue ("Click the glowing button")
        // while StepSummaryText ("Step 1 of 2: Click Print") holds the step metadata.
        StatusText = HighlightTargetStatus;
    }

    public void SetFollowTrail()
    {
        EnsureListening();
        Stage = GuidanceStage.FollowTrail;
        Indicator = IndicatorStatus.Active;
        StatusText = FollowTrailStatus;
    }

    public void SetHighlightTarget()
    {
        EnsureListening();
        Stage = GuidanceStage.HighlightTarget;
        Indicator = IndicatorStatus.Active;
        StatusText = HighlightTargetStatus;
    }

    public void SetStepCompleted()
    {
        EnsureListening();
        Stage = GuidanceStage.StepCompleted;
        Indicator = IndicatorStatus.Active;
        StatusText = StepCompletedStatus;
    }

    public bool AdvanceToNextStep()
    {
        if (_steps.Count > 0 && CurrentStep > 0 && CurrentStep < _steps.Count)
        {
            var nextIndex = CurrentStep; // 0-based index for CurrentStep + 1
            var nextStep = _steps[nextIndex];
            SetStep(CurrentStep + 1, _steps.Count, nextStep.Instruction, nextStep.Caption);
            return true;
        }

        return false;
    }

    public void DismissStepBanner()
    {
        ClearStepDetails();
        if (State == WidgetState.Listening && Indicator != IndicatorStatus.Error)
        {
            StatusText = FindingStatus;
            Stage = GuidanceStage.Finding;
        }
    }

    public void SetNoStepsFallback()
    {
        EnsureListening();
        _steps.Clear();
        ClearStepDetails();
        Stage = GuidanceStage.NoStepsError;
        Indicator = IndicatorStatus.Error;
        StatusText = NoStepsFallbackMessage;
    }

    public void SetApiErrorFallback()
    {
        EnsureListening();
        _steps.Clear();
        ClearStepDetails();
        Stage = GuidanceStage.ApiError;
        Indicator = IndicatorStatus.Error;
        StatusText = ApiErrorFallbackMessage;
    }

    private void EnsureListening()
    {
        if (State != WidgetState.Listening)
        {
            State = WidgetState.Listening;
        }
    }

    private void ClearStepDetails()
    {
        CurrentStep = 0;
        TotalSteps = 0;
        StepInstruction = null;
        StepCaption = null;
    }
}
