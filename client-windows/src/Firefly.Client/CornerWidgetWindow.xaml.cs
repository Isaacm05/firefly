using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;

namespace Firefly.Client;

/// <summary>Hosts <see cref="CornerWidget"/> as a real floating, always-on-top overlay anchored to
/// the screen's top-right corner - not confined to a separate launcher window, so it behaves like
/// the real product's corner pill (floats over whatever app you're using). This is the app's only
/// window: no title bar, so right-click gives the one way out (plus it's still in the taskbar).</summary>
public partial class CornerWidgetWindow : Window
{
    // No real speech-to-text here - standing in for "what the helper just said" during a call.
    // When running the local backend, an instruction typed into its terminal replaces this.
    private const string DemoInstruction = "Tell the learner which button to click to print this document.";

    // Messages from doc/api-contract.md "What the client shows".
    private const string NoStepsMessage = "I could not work out the steps. Ask your helper to say it another way.";
    private const string ErrorMessage = "Something went wrong. Ask your helper to try again.";
    private const int SettleMs = 800;          // let the app's UI react to a click before the next screenshot
    private const int MaxUploadWidth = 1280;   // contract: downscale before sending
    private const long JpegQuality = 80;

    private static readonly HttpClient Http = new();
    private readonly GroundingClient _api = new(Http, GroundingClient.DefaultBaseUrl);

    private GuidanceWindow? _overlay;
    private CancellationTokenSource? _sessionCts;

    public CornerWidgetWindow()
    {
        InitializeComponent();
        Corner.StartRequested += Corner_StartRequested;
        Corner.SettingsRequested += Corner_SettingsRequested;
        Corner.StopRequested += (_, _) =>
        {
            // The grounding call can still be in flight when Stop is clicked (screenshot + a real
            // network round-trip take a few seconds) - without this, the overlay it was about to
            // show still appears after the learner already stopped the call.
            _sessionCts?.Cancel();
            _overlay?.Stop();
            _overlay?.Close();
            _overlay = null;
        };

        // Width changes a lot (idle pill vs. the ~700px listening bar) - re-anchor the right edge
        // every time instead of fixing a Width that's too narrow for the widest state.
        SizeChanged += (_, _) => Left = SystemParameters.WorkArea.Right - ActualWidth;
        Top = SystemParameters.WorkArea.Top;
    }

    private void Corner_MouseRightButtonUp(object sender, MouseButtonEventArgs e)
    {
        var menu = new ContextMenu();
        var quit = new MenuItem { Header = "Quit Firefly" };
        quit.Click += (_, _) => System.Windows.Application.Current.Shutdown();
        menu.Items.Add(quit);
        menu.IsOpen = true;
    }

    /// <summary>One guidance session: plan the steps, then highlight each one in turn. The learner
    /// does every click themselves - this only watches for it (via the overlay) and moves on.</summary>
    private async void Corner_StartRequested(object? sender, EventArgs e)
    {
        _sessionCts?.Cancel();
        var cts = new CancellationTokenSource();
        _sessionCts = cts;
        var token = cts.Token;

        // The overlay is excluded from screen capture, so it can say "Looking…" while we screenshot.
        var overlay = OpenOverlay();
        overlay.Model.ShowLooking();

        try
        {
            var plan = await _api.PlanAsync(DemoInstruction, CaptureScreenshotBase64(), token);
            token.ThrowIfCancellationRequested();
            if (plan.Steps.Count == 0)
            {
                ShowMessageThenClose(overlay, NoStepsMessage);
                return;
            }
            overlay.Model.ShowHelper(string.Join(", then ", plan.Steps.Select(s => s.Instruction)));

            var target = plan.Target;
            for (var i = 0; i < plan.Steps.Count; i++)
            {
                if (i > 0)
                {
                    await Task.Delay(SettleMs, token);
                    overlay.Model.ShowLooking();
                    target = await _api.LocateAsync(plan.Steps[i], CaptureScreenshotBase64(), token);
                    token.ThrowIfCancellationRequested();
                }
                if (target is null) // FR-09: no confident box -> no highlight, short message instead
                {
                    ShowMessageThenClose(overlay,
                        $"I couldn't find “{plan.Steps[i].Label}”. Ask your helper to say it another way.");
                    return;
                }
                await WaitForStepAsync(overlay, target, token);
            }

            overlay.Model.ShowFinished("All done!");
            CloseOverlayAfter(overlay, TimeSpan.FromMilliseconds(1500));
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested)
        {
            // Stop was clicked mid-session - the overlay is already closed.
        }
        catch (Exception ex) // network down, server not running, HTTP timeout, 4xx/5xx
        {
            Debug.WriteLine($"[firefly] grounding session failed: {ex}");
            if (!token.IsCancellationRequested) ShowMessageThenClose(overlay, ErrorMessage);
        }
    }

    /// <summary>Highlights the target and completes when the learner clicks inside it, or when the
    /// step times out (FR-12: the overlay then moves on by itself).</summary>
    private static async Task WaitForStepAsync(GuidanceWindow overlay, Target target, CancellationToken token)
    {
        var done = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        void OnFinished(string reason) => done.TrySetResult(reason);
        overlay.StepFinished += OnFinished;
        try
        {
            overlay.Model.ShowTarget(target, OverlayViewport, currentlyDown: false, now: overlay.Now);
            using (token.Register(() => done.TrySetCanceled(token)))
                await done.Task;
        }
        finally
        {
            overlay.StepFinished -= OnFinished;
        }
    }

    private void Corner_SettingsRequested(object? sender, EventArgs e)
    {
        // Borderless, same as GuidanceWindow/this window - a native title bar read as "this is a
        // plain OS dialog," not part of the same floating-overlay product. SettingsPanel already
        // draws its own rounded card + shadow, so transparent chrome is all that's needed - but it
        // needs its own close control since there's no title bar X, and it should slide out next
        // to the widget (the "sidebar") rather than appear centered like an unrelated dialog.
        var closeButton = new Border
        {
            Width = 32,
            Height = 32,
            CornerRadius = new CornerRadius(16),
            Background = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0x1D, 0x1D, 0x1F)),
            Cursor = Cursors.Hand,
            HorizontalAlignment = System.Windows.HorizontalAlignment.Right,
            VerticalAlignment = System.Windows.VerticalAlignment.Top,
            Margin = new Thickness(0, 14, 14, 0),
            Child = new TextBlock
            {
                Text = "✕",
                FontSize = 13,
                FontWeight = FontWeights.Bold,
                Foreground = System.Windows.Media.Brushes.White,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                VerticalAlignment = System.Windows.VerticalAlignment.Center,
            },
        };

        var root = new Grid();
        root.Children.Add(new SettingsPanel());
        root.Children.Add(closeButton);

        var dialog = new Window
        {
            Content = root,
            WindowStyle = WindowStyle.None,
            AllowsTransparency = true,
            Background = System.Windows.Media.Brushes.Transparent,
            SizeToContent = SizeToContent.WidthAndHeight,
            WindowStartupLocation = WindowStartupLocation.Manual,
            ResizeMode = ResizeMode.NoResize,
            Topmost = true,
            ShowInTaskbar = false,
        };
        closeButton.MouseLeftButtonUp += (_, _) => dialog.Close();
        dialog.PreviewKeyDown += (_, args) =>
        {
            if (args.Key == Key.Escape) dialog.Close();
        };
        // Drop out from under the widget bar (the "sidebar") instead of appearing as a big
        // centered dialog that covers most of the screen.
        dialog.Loaded += (_, _) =>
        {
            dialog.Left = Left + ActualWidth - dialog.ActualWidth;
            dialog.Top = Top + ActualHeight + 8;
        };
        dialog.ShowDialog();
    }

    private static System.Windows.Size OverlayViewport =>
        new(SystemParameters.PrimaryScreenWidth, SystemParameters.PrimaryScreenHeight);

    private GuidanceWindow OpenOverlay()
    {
        _overlay?.Stop();
        _overlay?.Close();
        var overlay = new GuidanceWindow();
        _overlay = overlay;
        overlay.Show();
        overlay.Start();
        return overlay;
    }

    private void ShowMessageThenClose(GuidanceWindow overlay, string text)
    {
        overlay.Model.ShowMessage(text);
        CloseOverlayAfter(overlay, TimeSpan.FromSeconds(6));
    }

    private void CloseOverlayAfter(GuidanceWindow overlay, TimeSpan delay)
    {
        var timer = new DispatcherTimer { Interval = delay };
        timer.Tick += (_, _) =>
        {
            timer.Stop();
            if (_overlay != overlay) return; // already replaced by a new session or closed by Stop
            overlay.Stop();
            overlay.Close();
            _overlay = null;
        };
        timer.Start();
    }

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int nIndex);

    /// <summary>Primary screen as a base64 JPEG, downscaled to the contract's max width. Uses
    /// physical pixels (WPF apps are DPI-aware), so it covers the whole screen at 125%/150%
    /// scaling. In memory only - nothing is written to disk (NFR-03).</summary>
    private static string CaptureScreenshotBase64()
    {
        int width = GetSystemMetrics(0), height = GetSystemMetrics(1); // SM_CXSCREEN, SM_CYSCREEN
        using var full = new Bitmap(width, height);
        using (var graphics = Graphics.FromImage(full))
            graphics.CopyFromScreen(0, 0, 0, 0, full.Size);

        var scale = Math.Min(1.0, (double)MaxUploadWidth / width);
        using var upload = new Bitmap((int)Math.Round(width * scale), (int)Math.Round(height * scale));
        using (var graphics = Graphics.FromImage(upload))
        {
            graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
            graphics.DrawImage(full, 0, 0, upload.Width, upload.Height);
        }

        var jpeg = ImageCodecInfo.GetImageEncoders().First(c => c.FormatID == ImageFormat.Jpeg.Guid);
        using var quality = new EncoderParameters(1);
        quality.Param[0] = new EncoderParameter(System.Drawing.Imaging.Encoder.Quality, JpegQuality);
        using var stream = new MemoryStream();
        upload.Save(stream, jpeg, quality);
        return Convert.ToBase64String(stream.GetBuffer(), 0, (int)stream.Length);
    }
}
