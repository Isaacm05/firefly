using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;

namespace Firefly.Client;

/// <summary>Ports guidance-highlight/guidance_overlay.py's window setup: a full-screen, always-on-top,
/// click-through overlay that only reads the cursor/left-button state, never sends input (FR-11),
/// and is excluded from screen capture by default so a stale highlight never gets shared (ported
/// 1:1 from the Python showEvent's SetWindowDisplayAffinity call).</summary>
public partial class GuidanceWindow : Window
{
    private const int GwlExStyle = -20;
    private const int WsExTransparent = 0x20;
    private const int WsExLayered = 0x80000;
    private const int WsExToolWindow = 0x80;
    private const uint WdaExcludeFromCapture = 0x11;
    private const int VkLButton = 0x01;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

    [DllImport("user32.dll")]
    private static extern bool SetWindowDisplayAffinity(IntPtr hWnd, uint dwAffinity);

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out Win32Point lpPoint);

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    [StructLayout(LayoutKind.Sequential)]
    private struct Win32Point { public int X; public int Y; }

    public GuidanceModel Model { get; } = new();
    public SettingsState Settings { get; private set; }
    public double Now => _clock.Elapsed.TotalSeconds;
    public event Action<string>? StepFinished;

    private readonly GuidanceOverlay _overlay;
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromMilliseconds(16) };
    private readonly Stopwatch _clock = Stopwatch.StartNew();

    public GuidanceWindow(SettingsState? settings = null)
    {
        Settings = settings ?? new SettingsState();
        InitializeComponent();
        Width = SystemParameters.PrimaryScreenWidth;
        Height = SystemParameters.PrimaryScreenHeight;

        _overlay = new GuidanceOverlay(Model, Settings);
        Content = _overlay;

        Model.StepFinished += reason => StepFinished?.Invoke(reason);

        SourceInitialized += (_, _) => MakeClickThroughAndCaptureExcluded();
        Closed += (_, _) => _timer.Stop(); // a zombie timer on a closed window is how Tick() below crashes
        _timer.Tick += (_, _) => Tick();
    }

    private void MakeClickThroughAndCaptureExcluded()
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        var exStyle = GetWindowLongPtr(hwnd, GwlExStyle).ToInt64();
        exStyle |= WsExTransparent | WsExLayered | WsExToolWindow;
        SetWindowLongPtr(hwnd, GwlExStyle, new IntPtr(exStyle));

        // Keep the overlay out of our own screenshots so the model never sees a stale highlight.
        // Settings.CaptureVisible (off by default) or FIREFLY_CAPTURE_VISIBLE=1 keeps it visible
        // to screen recorders / screen share instead, e.g. for a demo recording.
        var captureVisible = Settings.CaptureVisible || Environment.GetEnvironmentVariable("FIREFLY_CAPTURE_VISIBLE") == "1";
        if (!captureVisible)
            SetWindowDisplayAffinity(hwnd, WdaExcludeFromCapture);
    }

    public void Start() => _timer.Start();

    public void Stop() => _timer.Stop();

    public void ApplySettings(SettingsState settings)
    {
        Settings = settings;
        _overlay.ApplySettings(settings);
    }

    private void Tick()
    {
        if (Model.State == GuidanceState.Idle) return;
        // The window isn't connected yet (layered/AllowsTransparency windows can lag a frame or
        // two behind Show()) or has already been closed — either way, skip this frame rather
        // than letting PointFromScreen throw.
        if (PresentationSource.FromVisual(this) is null) return;

        GetCursorPos(out var screen);
        var local = PointFromScreen(new Point(screen.X, screen.Y));
        var down = (GetAsyncKeyState(VkLButton) & 0x8000) != 0;

        Model.Tick(local, down, _clock.Elapsed.TotalSeconds);
        _overlay.InvalidateVisual();
    }
}
