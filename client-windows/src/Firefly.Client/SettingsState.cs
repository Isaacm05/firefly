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

    /// <summary>Off by default (NFR-03): the guidance overlay is excluded from screen capture
    /// so a stale highlight never gets shared. Turn on only to record a demo/screen share.</summary>
    public bool CaptureVisible { get; set; } = false;

    public double PreviewFontSize => TextSize switch
    {
        TextSize.Small => 15,
        TextSize.Medium => 18,
        _ => 24,
    };

    public string HighlightHex => HighlightColor switch
    {
        HighlightColor.Yellow => "#FFD60A",
        HighlightColor.Blue => "#64D2FF",
        _ => "#FF6FB5",
    };

    public System.Windows.Media.Color HighlightColorValue => HighlightColor switch
    {
        HighlightColor.Yellow => System.Windows.Media.Color.FromRgb(0xFF, 0xD6, 0x0A),
        HighlightColor.Blue => System.Windows.Media.Color.FromRgb(0x64, 0xD2, 0xFF),
        _ => System.Windows.Media.Color.FromRgb(0xFF, 0x6F, 0xB5),
    };

    public double TextScale => TextSize switch
    {
        TextSize.Small => 0.85,
        TextSize.Medium => 1.0,
        _ => 1.35,
    };

    public SettingsState Clone() => new()
    {
        CallMode = CallMode,
        TextSize = TextSize,
        HighlightColor = HighlightColor,
        ReadAloud = ReadAloud,
        ShowCaptions = ShowCaptions,
        CaptureVisible = CaptureVisible,
    };

    public void CopyFrom(SettingsState other)
    {
        CallMode = other.CallMode;
        TextSize = other.TextSize;
        HighlightColor = other.HighlightColor;
        ReadAloud = other.ReadAloud;
        ShowCaptions = other.ShowCaptions;
        CaptureVisible = other.CaptureVisible;
    }
}
