using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Firefly.Client;

public partial class CornerWidget : UserControl
{
    private WidgetState _state = WidgetState.Idle;

    /// <summary>Raised when "Start Firefly" is clicked, after the widget has already switched to
    /// the Listening visual. The host (CornerWidgetWindow) is responsible for the real guidance
    /// flow - this control only owns its own idle/menu/listening/stopped chrome.</summary>
    public event EventHandler? StartRequested;

    /// <summary>Raised from either "Settings" entry point (the start-menu link or the listening
    /// bar's chip). The host decides how to show settings (dialog, pane, etc).</summary>
    public event EventHandler? SettingsRequested;

    /// <summary>Raised when "Stop" is clicked. The host is responsible for actually tearing down
    /// the guidance overlay it opened on StartRequested - this control has no reference to it.</summary>
    public event EventHandler? StopRequested;

    public CornerWidget()
    {
        InitializeComponent();
    }

    private void OpenMenu_Click(object sender, RoutedEventArgs e) => Transition(CornerWidgetFlow.OpenMenu(_state));

    private void CloseMenu_Click(object sender, RoutedEventArgs e) => Transition(CornerWidgetFlow.CloseMenu(_state));

    private void StartFirefly_Click(object sender, RoutedEventArgs e)
    {
        Transition(CornerWidgetFlow.Start(_state));
        StartRequested?.Invoke(this, EventArgs.Empty);
    }

    private void Stop_Click(object sender, RoutedEventArgs e)
    {
        Transition(CornerWidgetFlow.Stop(_state));
        StopRequested?.Invoke(this, EventArgs.Empty);
    }

    private void StartAgain_Click(object sender, RoutedEventArgs e) => Transition(CornerWidgetFlow.Reset(_state));

    private void Settings_Click(object sender, RoutedEventArgs e) => SettingsRequested?.Invoke(this, EventArgs.Empty);

    private void SettingsLink_MouseUp(object sender, System.Windows.Input.MouseButtonEventArgs e) =>
        SettingsRequested?.Invoke(this, EventArgs.Empty);

    private void Transition(WidgetState next)
    {
        _state = next;

        IdleButton.Visibility = next == WidgetState.Idle ? Visibility.Visible : Visibility.Collapsed;
        MenuPanel.Visibility = next == WidgetState.MenuOpen ? Visibility.Visible : Visibility.Collapsed;
        ListeningPanel.Visibility = next == WidgetState.Listening ? Visibility.Visible : Visibility.Collapsed;
        StoppedPanel.Visibility = next == WidgetState.Stopped ? Visibility.Visible : Visibility.Collapsed;

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
        var pulse = new DoubleAnimation(1.0, 0.55, TimeSpan.FromMilliseconds(650))
        {
            AutoReverse = true,
            RepeatBehavior = RepeatBehavior.Forever,
            EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut }
        };
        ListeningMascot.BeginAnimation(OpacityProperty, pulse);
    }

    private void StopMascotPulse() => ListeningMascot.BeginAnimation(OpacityProperty, null);
}
