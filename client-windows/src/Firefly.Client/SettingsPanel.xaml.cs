using System;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Firefly.Client;

public partial class SettingsPanel : UserControl
{
    private readonly SettingsState _state = new();

    public event EventHandler? CloseRequested;
    public event EventHandler<SettingsState>? SettingsChanged;

    public SettingsPanel(SettingsState? initial = null)
    {
        InitializeComponent();

        if (initial != null)
        {
            _state.CopyFrom(initial);
            ApplyStateToUi();
        }
        else
        {
            UpdatePreview();
        }

        Loaded += (_, _) => AnimateIn();
    }

    private void ApplyStateToUi()
    {
        if (CallModeVideoRadio != null) CallModeVideoRadio.IsChecked = _state.CallMode == CallMode.VideoCall;
        if (CallModePhoneRadio != null) CallModePhoneRadio.IsChecked = _state.CallMode == CallMode.PhoneSpeaker;

        if (TextSizeSmallRadio != null) TextSizeSmallRadio.IsChecked = _state.TextSize == TextSize.Small;
        if (TextSizeMediumRadio != null) TextSizeMediumRadio.IsChecked = _state.TextSize == TextSize.Medium;
        if (TextSizeLargeRadio != null) TextSizeLargeRadio.IsChecked = _state.TextSize == TextSize.Large;

        if (HighlightYellowRadio != null) HighlightYellowRadio.IsChecked = _state.HighlightColor == HighlightColor.Yellow;
        if (HighlightBlueRadio != null) HighlightBlueRadio.IsChecked = _state.HighlightColor == HighlightColor.Blue;
        if (HighlightPinkRadio != null) HighlightPinkRadio.IsChecked = _state.HighlightColor == HighlightColor.Pink;

        if (ReadAloudToggle != null) ReadAloudToggle.IsChecked = _state.ReadAloud;
        if (CaptionsToggle != null) CaptionsToggle.IsChecked = _state.ShowCaptions;
        if (CaptureVisibleToggle != null) CaptureVisibleToggle.IsChecked = _state.CaptureVisible;

        UpdatePreview();
    }

    private void UpdatePreview()
    {
        var brush = (Brush)new BrushConverter().ConvertFromString(_state.HighlightHex)!;
        if (PreviewDot != null) PreviewDot.Fill = brush;
        if (PreviewText != null)
        {
            PreviewText.FontSize = _state.PreviewFontSize;
            PreviewText.Foreground = brush;
        }
    }

    private void AnimateIn()
    {
        var fade = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(220))
        {
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut }
        };
        var scale = new DoubleAnimation(0.94, 1, TimeSpan.FromMilliseconds(340))
        {
            EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.3 }
        };
        var slide = new DoubleAnimation(16, 0, TimeSpan.FromMilliseconds(300))
        {
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut }
        };

        SheetRoot.BeginAnimation(OpacityProperty, fade);
        SheetScale.BeginAnimation(ScaleTransform.ScaleXProperty, scale);
        SheetScale.BeginAnimation(ScaleTransform.ScaleYProperty, scale);
        SheetSlide.BeginAnimation(TranslateTransform.YProperty, slide);
    }

    private void Close_Click(object sender, RoutedEventArgs e)
    {
        CloseRequested?.Invoke(this, EventArgs.Empty);
    }

    private void CallModeChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<CallMode>(tag, out var mode))
        {
            _state.CallMode = mode;
            SettingsChanged?.Invoke(this, _state);
        }
    }

    private void TextSizeChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<TextSize>(tag, out var size))
        {
            _state.TextSize = size;
            UpdatePreview();
            SettingsChanged?.Invoke(this, _state);
        }
    }

    private void HighlightColorChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<HighlightColor>(tag, out var color))
        {
            _state.HighlightColor = color;
            UpdatePreview();
            SettingsChanged?.Invoke(this, _state);
        }
    }

    private void ReadAloudToggled(object sender, RoutedEventArgs e)
    {
        _state.ReadAloud = ReadAloudToggle.IsChecked == true;
        SettingsChanged?.Invoke(this, _state);
    }

    private void CaptionsToggled(object sender, RoutedEventArgs e)
    {
        _state.ShowCaptions = CaptionsToggle.IsChecked == true;
        SettingsChanged?.Invoke(this, _state);
    }

    private void CaptureVisibleToggled(object sender, RoutedEventArgs e)
    {
        _state.CaptureVisible = CaptureVisibleToggle.IsChecked == true;
        SettingsChanged?.Invoke(this, _state);
    }

    private async void SaveClicked(object sender, RoutedEventArgs e)
    {
        SavedToast.Visibility = Visibility.Visible;
        await Task.Delay(1600);
        SavedToast.Visibility = Visibility.Collapsed;
    }
}
