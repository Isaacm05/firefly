using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using System.Windows.Threading;

namespace Firefly.Client;

public partial class MainWindow : Window
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

    public MainWindow()
    {
        InitializeComponent();
        Corner.StartRequested += Corner_StartRequested;
        Corner.SettingsRequested += Corner_SettingsRequested;
    }

    private async void Corner_StartRequested(object? sender, EventArgs e)
    {
        ApiStatusText.Text = "Capturing the screen and calling the grounding API…";
        try
        {
            var screenshot = CaptureScreenshotBase64();
            var text = await CallGroundingApiAsync(DemoInstruction, screenshot);
            ApiStatusText.Text = $"API said: “{text}”";
            ShowOverlay(text);
        }
        catch (Exception ex)
        {
            ApiStatusText.Text = $"API call failed: {ex.Message}";
        }
    }

    private void Corner_SettingsRequested(object? sender, EventArgs e)
    {
        var dialog = new Window
        {
            Title = "Firefly Settings",
            Content = new SettingsPanel(),
            SizeToContent = SizeToContent.WidthAndHeight,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Owner = this,
            Background = new SolidColorBrush(System.Windows.Media.Color.FromArgb(0xFF, 0xD8, 0xE1, 0xEE)),
            ResizeMode = ResizeMode.NoResize,
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

    private static async Task<string> CallGroundingApiAsync(string instruction, string imageBase64)
    {
        var payload = JsonSerializer.Serialize(new { instruction, image = imageBase64 });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");
        using var response = await Http.PostAsync(GroundingApiUrl, content);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.GetProperty("text").GetString() ?? "(empty response)";
    }
}
