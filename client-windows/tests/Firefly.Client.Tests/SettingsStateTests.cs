using System.Windows.Media;
using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

public class SettingsStateTests
{
    [Theory]
    [InlineData(TextSize.Small, 15)]
    [InlineData(TextSize.Medium, 18)]
    [InlineData(TextSize.Large, 24)]
    public void PreviewFontSize_MatchesSelectedTextSize(TextSize size, double expected)
    {
        var state = new SettingsState { TextSize = size };
        Assert.Equal(expected, state.PreviewFontSize);
    }

    [Theory]
    [InlineData(TextSize.Small, 0.85)]
    [InlineData(TextSize.Medium, 1.0)]
    [InlineData(TextSize.Large, 1.35)]
    public void TextScale_MatchesSelectedTextSize(TextSize size, double expected)
    {
        var state = new SettingsState { TextSize = size };
        Assert.Equal(expected, state.TextScale);
    }

    [Theory]
    [InlineData(HighlightColor.Yellow, "#FFD60A")]
    [InlineData(HighlightColor.Blue, "#64D2FF")]
    [InlineData(HighlightColor.Pink, "#FF6FB5")]
    public void HighlightHex_MatchesSelectedColor(HighlightColor color, string expected)
    {
        var state = new SettingsState { HighlightColor = color };
        Assert.Equal(expected, state.HighlightHex);
    }

    [Fact]
    public void HighlightColorValue_ReturnsExpectedRgbColors()
    {
        var yellow = new SettingsState { HighlightColor = HighlightColor.Yellow };
        Assert.Equal(Color.FromRgb(0xFF, 0xD6, 0x0A), yellow.HighlightColorValue);

        var blue = new SettingsState { HighlightColor = HighlightColor.Blue };
        Assert.Equal(Color.FromRgb(0x64, 0xD2, 0xFF), blue.HighlightColorValue);

        var pink = new SettingsState { HighlightColor = HighlightColor.Pink };
        Assert.Equal(Color.FromRgb(0xFF, 0x6F, 0xB5), pink.HighlightColorValue);
    }

    [Fact]
    public void CopyFrom_And_Clone_DuplicateAllValues()
    {
        var original = new SettingsState
        {
            CallMode = CallMode.PhoneSpeaker,
            TextSize = TextSize.Small,
            HighlightColor = HighlightColor.Pink,
            ReadAloud = false,
            ShowCaptions = false,
            CaptureVisible = true,
        };

        var cloned = original.Clone();
        Assert.Equal(CallMode.PhoneSpeaker, cloned.CallMode);
        Assert.Equal(TextSize.Small, cloned.TextSize);
        Assert.Equal(HighlightColor.Pink, cloned.HighlightColor);
        Assert.False(cloned.ReadAloud);
        Assert.False(cloned.ShowCaptions);
        Assert.True(cloned.CaptureVisible);

        var copy = new SettingsState();
        copy.CopyFrom(original);
        Assert.Equal(cloned.HighlightHex, copy.HighlightHex);
        Assert.Equal(cloned.TextScale, copy.TextScale);
        Assert.True(copy.CaptureVisible);
    }
}
