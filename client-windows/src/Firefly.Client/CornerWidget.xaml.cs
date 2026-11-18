using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Firefly.Client;

public partial class CornerWidget : UserControl
{
    public CornerWidgetFlow Flow { get; } = new();

    /// <summary>Raised when "Start Firefly" is clicked, passing the selected <see cref="CallMode"/>.</summary>
    public event EventHandler<CallMode>? Started;

    /// <summary>Parameterless start event kept for compatibility with CornerWidgetWindow (#44).</summary>
    public event EventHandler? StartRequested;

    /// <summary>Raised when "Stop" is clicked.</summary>
    public event EventHandler? Stopped;

    /// <summary>Parameterless stop event kept for compatibility with CornerWidgetWindow (#44).</summary>
    public event EventHandler? StopRequested;

    /// <summary>Raised from either "Settings" entry point (menu link or listening bar chip).</summary>
    public event EventHandler? SettingsRequested;

    /// <summary>Raised when the "Read aloud" chip is toggled.</summary>
    public event EventHandler<bool>? ReadAloudToggled;

    /// <summary>Raised when "A-" or "A+" changes the text scale factor.</summary>
    public event EventHandler<double>? TextScaleChanged;

    /// <summary>Raised when a step detail/controls tray is dismissed.</summary>
    public event EventHandler? StepDismissed;

    public CornerWidget()
    {
        InitializeComponent();
        RefreshFromFlow();
    }

    public void SetFinding()
    {
        var previous = Flow.State;
        Flow.SetFinding();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void LoadPlan(IEnumerable<GuidanceStep>? steps, string? firstTargetCaption = null)
    {
        var previous = Flow.State;
        Flow.LoadPlan(steps, firstTargetCaption);
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void SetStep(int currentStep, int totalSteps, string instruction, string? caption = null)
    {
        var previous = Flow.State;
        Flow.SetStep(currentStep, totalSteps, instruction, caption);
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void SetFollowTrail()
    {
        var previous = Flow.State;
        Flow.SetFollowTrail();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void SetHighlightTarget()
    {
        var previous = Flow.State;
        Flow.SetHighlightTarget();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void SetStepCompleted()
    {
        var previous = Flow.State;
        Flow.SetStepCompleted();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public bool AdvanceToNextStep()
    {
        var advanced = Flow.AdvanceToNextStep();
        RefreshFromFlow();
        return advanced;
    }

    public void SetNoStepsFallback()
    {
        var previous = Flow.State;
        Flow.SetNoStepsFallback();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void SetApiErrorFallback()
    {
        var previous = Flow.State;
        Flow.SetApiErrorFallback();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    public void DismissStep()
    {
        Flow.DismissStepBanner();
        RefreshFromFlow();
        StepDismissed?.Invoke(this, EventArgs.Empty);
    }

    private void OpenMenu_Click(object sender, RoutedEventArgs e)
    {
        var previous = Flow.State;
        Flow.OpenMenu();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    private void CloseMenu_Click(object sender, RoutedEventArgs e)
    {
        var previous = Flow.State;
        Flow.CloseMenu();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    private void CallMode_Checked(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<CallMode>(tag, out var mode))
        {
            Flow.SelectCallMode(mode);
        }
    }

    private void StartFirefly_Click(object sender, RoutedEventArgs e)
    {
        var selectedMode = PhoneSpeakerRadio?.IsChecked == true ? CallMode.PhoneSpeaker : CallMode.VideoCall;
        var previous = Flow.State;
        Flow.Start(selectedMode);
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();

        Started?.Invoke(this, Flow.CallMode);
        StartRequested?.Invoke(this, EventArgs.Empty);
    }

    private void ListeningBar_Click(object sender, MouseButtonEventArgs e)
    {
        Flow.ToggleControlsTray();
        RefreshFromFlow();
    }

    private void Stop_Click(object sender, RoutedEventArgs e)
    {
        var previous = Flow.State;
        Flow.Stop();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();

        Stopped?.Invoke(this, EventArgs.Empty);
        StopRequested?.Invoke(this, EventArgs.Empty);
    }

    private void StartAgain_Click(object sender, RoutedEventArgs e)
    {
        var previous = Flow.State;
        Flow.Reset();
        ApplyTransitionIfStateChanged(previous);
        RefreshFromFlow();
    }

    private void DecreaseTextSize_Click(object sender, RoutedEventArgs e)
    {
        var scale = Flow.DecreaseTextScale();
        RefreshFromFlow();
        TextScaleChanged?.Invoke(this, scale);
    }

    private void IncreaseTextSize_Click(object sender, RoutedEventArgs e)
    {
        var scale = Flow.IncreaseTextScale();
        RefreshFromFlow();
        TextScaleChanged?.Invoke(this, scale);
    }

    private void ToggleReadAloud_Click(object sender, RoutedEventArgs e)
    {
        var enabled = Flow.ToggleReadAloud();
        RefreshFromFlow();
        ReadAloudToggled?.Invoke(this, enabled);
    }

    private void Settings_Click(object sender, RoutedEventArgs e) =>
        SettingsRequested?.Invoke(this, EventArgs.Empty);

    private void SettingsLink_MouseUp(object sender, MouseButtonEventArgs e) =>
        SettingsRequested?.Invoke(this, EventArgs.Empty);

    private void ApplyTransitionIfStateChanged(WidgetState previous)
    {
        var next = Flow.State;
        if (previous == next)
        {
            return;
        }

        switch (next)
        {
            case WidgetState.MenuOpen:
                AnimateIn(StartMenuCard, MenuScale, MenuSlide);
                break;
            case WidgetState.Listening:
                AnimateScaleIn(BarScale);
                StartMascotPulse();
                break;
            case WidgetState.Stopped:
                AnimateScaleIn(ToastScale);
                StopMascotPulse();
                break;
            default:
                StopMascotPulse();
                break;
        }
    }

    public void RefreshFromFlow()
    {
        var state = Flow.State;
        IdleButton.Visibility = state == WidgetState.Idle ? Visibility.Visible : Visibility.Collapsed;
        MenuPanel.Visibility = state == WidgetState.MenuOpen ? Visibility.Visible : Visibility.Collapsed;
        ListeningPanel.Visibility = state == WidgetState.Listening ? Visibility.Visible : Visibility.Collapsed;
        StoppedPanel.Visibility = state == WidgetState.Stopped ? Visibility.Visible : Visibility.Collapsed;

        // Scale the entire widget proportionally (status pill, firefly icon, and all action buttons)
        WidgetScaleTransform.ScaleX = Flow.TextScale;
        WidgetScaleTransform.ScaleY = Flow.TextScale;

        // Update dynamic status text
        StatusText.Text = Flow.StatusText;

        // Collapsible quick-actions tray (toggled by clicking the status bubble)
        QuickActionsTray.Visibility = state == WidgetState.Listening && Flow.IsControlsTrayOpen
            ? Visibility.Visible
            : Visibility.Collapsed;

        // Update firefly belly glow: Red (#FF5A52) on error, warm firefly gold (#FFD54A) on dark pill or green pill
        var mascotHex = Flow.IsError ? CornerWidgetFlow.ErrorColorHex : CornerWidgetFlow.IdleColorHex;
        var mascotColor = (Color)ColorConverter.ConvertFromString(mascotHex);
        var mascotBrush = new SolidColorBrush(mascotColor);
        ListeningMascot.Fill = mascotBrush;
        ListeningMascotHalo.Fill = mascotBrush;
        ListeningMascotShadow.Color = mascotColor;

        // Match Figma Flow 2 Screen 5: green confirmation bar on StepCompleted, dark navy otherwise
        var barHex = Flow.Stage == GuidanceStage.StepCompleted ? "#2EAD6B" : "#1D1B3A";
        ListeningBar.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString(barHex));

        // Read Aloud toggle chip state
        var chipKey = Flow.IsReadAloudEnabled ? "ActiveChipStyle" : "ChipStyle";
        if (TryFindResource(chipKey) is Style chipStyle)
        {
            ReadAloudButton.Style = chipStyle;
        }
        ReadAloudButton.Content = Flow.IsReadAloudEnabled ? "Read aloud: On" : "Read aloud";
    }

    private static void AnimateIn(FrameworkElement target, ScaleTransform scale, TranslateTransform slide)
    {
        target.Opacity = 0;
        var fade = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(180)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } };
        var scaleAnim = new DoubleAnimation(0.94, 1, TimeSpan.FromMilliseconds(260)) { EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.3 } };
        var slideAnim = new DoubleAnimation(-10, 0, TimeSpan.FromMilliseconds(220)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } };

        target.BeginAnimation(OpacityProperty, fade);
        scale.BeginAnimation(ScaleTransform.ScaleXProperty, scaleAnim);
        scale.BeginAnimation(ScaleTransform.ScaleYProperty, scaleAnim);
        slide.BeginAnimation(TranslateTransform.YProperty, slideAnim);
    }

    private static void AnimateScaleIn(ScaleTransform scale)
    {
        var scaleAnim = new DoubleAnimation(0.9, 1, TimeSpan.FromMilliseconds(240)) { EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.35 } };
        scale.BeginAnimation(ScaleTransform.ScaleXProperty, scaleAnim);
        scale.BeginAnimation(ScaleTransform.ScaleYProperty, scaleAnim);
    }

    private void StartMascotPulse()
    {
        var pulse = new DoubleAnimation(1.0, 0.5, TimeSpan.FromMilliseconds(650))
        {
            AutoReverse = true,
            RepeatBehavior = RepeatBehavior.Forever,
            EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut }
        };
        ListeningMascot.BeginAnimation(OpacityProperty, pulse);
        ListeningMascotHalo.BeginAnimation(OpacityProperty, new DoubleAnimation(0.32, 0.12, TimeSpan.FromMilliseconds(650))
        {
            AutoReverse = true,
            RepeatBehavior = RepeatBehavior.Forever,
            EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut }
        });
    }

    private void StopMascotPulse()
    {
        ListeningMascot.BeginAnimation(OpacityProperty, null);
        ListeningMascotHalo.BeginAnimation(OpacityProperty, null);
    }
}
