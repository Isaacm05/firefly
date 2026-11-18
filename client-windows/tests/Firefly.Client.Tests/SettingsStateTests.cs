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
    [InlineData(HighlightColor.Yellow, "#FFD60A")]
    [InlineData(HighlightColor.Blue, "#5AC8FA")]
    [InlineData(HighlightColor.Pink, "#FF375F")]
    public void HighlightHex_MatchesSelectedColor(HighlightColor color, string expected)
    {
        var state = new SettingsState { HighlightColor = color };
        Assert.Equal(expected, state.HighlightHex);
    }
}
