namespace Firefly.Client;

public enum WidgetState { Idle, MenuOpen, Listening, Stopped }

/// <summary>Pure state transitions for the corner widget (issue #34): idle pill -> start menu
/// -> listening bar -> stopped toast -> back to idle. No WPF dependency so it's cheaply testable.</summary>
public static class CornerWidgetFlow
{
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
}
