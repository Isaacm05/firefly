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

    public SettingsPanel()
    {
        InitializeComponent();
        Loaded += (_, _) => AnimateIn();
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

    private void CallModeChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<CallMode>(tag, out var mode))
            _state.CallMode = mode;
    }

    private void TextSizeChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<TextSize>(tag, out var size))
        {
            _state.TextSize = size;
            // ponytail: IsChecked="True" on the default selections fires this Checked handler
            // from within InitializeComponent, before later-declared fields like PreviewText exist.
            if (PreviewText != null) PreviewText.FontSize = _state.PreviewFontSize;
        }
    }

    private void HighlightColorChanged(object sender, RoutedEventArgs e)
    {
        if (sender is RadioButton { Tag: string tag } && Enum.TryParse<HighlightColor>(tag, out var color))
        {
            _state.HighlightColor = color;
            if (PreviewDot != null) PreviewDot.Fill = (Brush)new BrushConverter().ConvertFromString(_state.HighlightHex)!;
        }
    }

    private void ReadAloudToggled(object sender, RoutedEventArgs e) => _state.ReadAloud = ReadAloudToggle.IsChecked == true;

    private void CaptionsToggled(object sender, RoutedEventArgs e) => _state.ShowCaptions = CaptionsToggle.IsChecked == true;

    private async void SaveClicked(object sender, RoutedEventArgs e)
    {
        SavedToast.Visibility = Visibility.Visible;
        await Task.Delay(1600);
        SavedToast.Visibility = Visibility.Collapsed;
    }
}
