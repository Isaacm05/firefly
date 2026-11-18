namespace Firefly.Client;

public enum CallMode { VideoCall, PhoneSpeaker }
public enum TextSize { Small, Medium, Large }
public enum HighlightColor { Yellow, Blue, Pink }

/// <summary>Current selections on the "Make it comfortable" settings panel (issue #38).</summary>
public class SettingsState
{
    public CallMode CallMode { get; set; } = CallMode.VideoCall;
    public TextSize TextSize { get; set; } = TextSize.Large;
    public HighlightColor HighlightColor { get; set; } = HighlightColor.Yellow;
    public bool ReadAloud { get; set; } = true;
    public bool ShowCaptions { get; set; } = true;

    public double PreviewFontSize => TextSize switch
    {
        TextSize.Small => 15,
        TextSize.Medium => 18,
        _ => 24,
    };

    public string HighlightHex => HighlightColor switch
    {
        HighlightColor.Yellow => "#FFD60A",
        HighlightColor.Blue => "#5AC8FA",
        _ => "#FF375F",
    };
}
