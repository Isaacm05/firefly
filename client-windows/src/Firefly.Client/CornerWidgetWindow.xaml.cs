using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
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
    // The actually-deployed grounding Lambda (backend/, branch feature/lambda-gemini-scaffold).
    // Takes {instruction, image(base64 PNG)}, returns {"text": "..."} - raw Gemini text, no
    // structured box yet (see issue #44/#32), so this prototype shows the real text rather than
    // pretending we can position the ring from it.
    private const string GroundingApiUrl = "https://cupxc1h638.execute-api.us-east-2.amazonaws.com/Prod/ground";

    // No real speech-to-text here - standing in for "what the helper just said" during a call.
    private const string DemoInstruction = "Tell the learner which button to click to print this document.";

    private static readonly HttpClient Http = new();

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

    private async void Corner_StartRequested(object? sender, EventArgs e)
    {
        _sessionCts?.Cancel();
        var cts = new CancellationTokenSource();
        _sessionCts = cts;

        try
        {
            var screenshot = CaptureScreenshotBase64();
            var text = await CallGroundingApiAsync(DemoInstruction, screenshot, cts.Token);
            if (cts.Token.IsCancellationRequested) return; // stopped while the call was in flight
            ShowOverlay(text);
        }
        catch (OperationCanceledException)
        {
            // Stop was clicked while capturing/calling - nothing to show.
        }
        catch (Exception ex)
        {
            System.Windows.MessageBox.Show(this, $"Grounding API call failed: {ex.Message}", "Firefly",
                MessageBoxButton.OK, MessageBoxImage.Warning);
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

    private void ShowOverlay(string helperText)
    {
        _overlay?.Close();
        var overlay = new GuidanceWindow();
        _overlay = overlay;

        var viewport = new System.Windows.Size(SystemParameters.PrimaryScreenWidth, SystemParameters.PrimaryScreenHeight);
        // Demo target position: the real box coordinates aren't in the API response yet
        // (dropped {found, box, confidence} contract, see #44) - this keeps the ring/firefly
        // visual real while that's still open, rather than faking a coordinate parse.
        var demoTarget = new Target(0.45, 0.47, 0.1, 0.06, "Print", "Click Print", helperText, NeedsCaption: true);

        overlay.Model.ShowHelper(helperText);
        overlay.Model.ShowTarget(demoTarget, viewport, currentlyDown: false, now: overlay.Now);
        overlay.StepFinished += _ => Dispatcher.Invoke(() =>
        {
            var closeTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(1500) };
            closeTimer.Tick += (_, _) =>
            {
                closeTimer.Stop();
                overlay.Stop();
                overlay.Close();
            };
            closeTimer.Start();
        });

        overlay.Show();
        overlay.Start();
    }

    private static string CaptureScreenshotBase64()
    {
        var width = (int)SystemParameters.PrimaryScreenWidth;
        var height = (int)SystemParameters.PrimaryScreenHeight;
        using var bitmap = new Bitmap(width, height);
        using (var graphics = Graphics.FromImage(bitmap))
            graphics.CopyFromScreen(0, 0, 0, 0, bitmap.Size);

        using var stream = new MemoryStream();
        bitmap.Save(stream, ImageFormat.Png);
        return Convert.ToBase64String(stream.ToArray());
    }

    private static async Task<string> CallGroundingApiAsync(string instruction, string imageBase64, CancellationToken token)
    {
        var payload = JsonSerializer.Serialize(new { instruction, image = imageBase64 });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        using var response = await Http.PostAsync(GroundingApiUrl, content, token);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(token);
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.GetProperty("text").GetString() ?? "(empty response)";
    }
}
