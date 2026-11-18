using System;
using System.Diagnostics;
using System.Globalization;
using System.Windows;
using System.Windows.Media;

namespace Firefly.Client;

/// <summary>Ports guidance-highlight/guidance_overlay.py's paintEvent and _draw_* helpers to WPF.
/// Reads a <see cref="GuidanceModel"/> each frame; owns no input/timer logic itself (that lives in
/// GuidanceWindow, the Win32-interop host) so this stays a pure rendering layer.
///
/// Restyled (2026-11-16) away from the Figma file's thick yellow glowing borders toward
/// github.com/farzaa/clicky's DesignSystem.swift: dark elevated surfaces, one restrained
/// accent color, and a soft single-layer shadow instead of an 8-layer glow stack.</summary>
public sealed class GuidanceOverlay : FrameworkElement
{
    private static readonly Color Success = Color.FromRgb(0x34, 0xD3, 0x99);   // DS.Colors.success
    private static readonly Color Surface1 = Color.FromRgb(0x17, 0x19, 0x18);  // card backgrounds
    private static readonly Color BorderSubtle = Color.FromRgb(0x37, 0x3B, 0x39);
    private static readonly Color TextPrimary = Color.FromRgb(0xEC, 0xEE, 0xED);
    private static readonly Color TextSecondary = Color.FromRgb(0xAD, 0xB5, 0xB2);

    private const double PulsePeriodS = 2.5;   // a slow "breathing" cue, matching DS's primary-button glow

    // The demo-firefly loop: fly in, tap the target, fade, pause, repeat — like a looping
    // tutorial-recording ghost cursor, replayed on its own schedule rather than following the
    // learner's real pointer (that read as "a trail on the mouse," which wasn't what was wanted).
    private const double FlyS = 1.4;
    private const double ClickS = 0.35;
    private const double FadeS = 0.3;
    private const double PauseS = 1.1;
    private const double LoopS = FlyS + ClickS + FadeS + PauseS;

    private readonly Typeface _regular = new("Segoe UI");
    private readonly Typeface _bold = new(new FontFamily("Segoe UI"), FontStyles.Normal, FontWeights.Bold, FontStretches.Normal);
    private readonly double _envTextScale;
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private int _loopIndex = -1;
    private Point _loopStart;

    public GuidanceModel Model { get; }
    public SettingsState Settings { get; private set; }

    private Color Accent => Settings.HighlightColorValue;
    private double TextScale => Settings.TextScale * _envTextScale;

    public GuidanceOverlay(GuidanceModel model, SettingsState? settings = null)
    {
        Model = model;
        Settings = settings ?? new SettingsState();
        _envTextScale = ReadTextScale();
        IsHitTestVisible = false; // FR-11: this element never intercepts input either
    }

    public void ApplySettings(SettingsState settings)
    {
        Settings = settings;
        InvalidateVisual();
    }

    private static double ReadTextScale()
    {
        var raw = Environment.GetEnvironmentVariable("FIREFLY_TEXT_SCALE");
        return double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : 1.0;
    }

    protected override void OnRender(DrawingContext dc)
    {
        var t = _clock.Elapsed.TotalSeconds;
        var target = Model.Target;

        if (target is not null && Model.State == GuidanceState.Guiding)
        {
            DrawGlow(dc, t, Accent);
            DrawRing(dc, Accent);
            DrawFireflyDemo(dc, t);
            if (Settings.ShowCaptions && target.NeedsCaption && !string.IsNullOrEmpty(target.Caption))
                DrawCaption(dc, target);
        }
        else if (target is not null && Model.State == GuidanceState.Confirmed)
        {
            DrawGlow(dc, t, Success);
            DrawRing(dc, Success);
            DrawCheck(dc);
        }

        if (!string.IsNullOrEmpty(Model.HelperText))
            DrawHelperChip(dc);
        if (Model.State != GuidanceState.Idle && !string.IsNullOrEmpty(Model.StatusText))
            DrawStatus(dc);
    }

    /// <summary>A looping "ghost cursor" demo: a firefly flies from near the learner's current
    /// pointer to the target, taps it (a click-ripple), fades out, pauses, then replays — like a
    /// recorded tutorial clip showing the gesture, rather than anything tracking the real cursor
    /// live. Purely a rendering concern: lives here, not in GuidanceModel, so the tested state
    /// machine is untouched.</summary>
    private void DrawFireflyDemo(DrawingContext dc, double t)
    {
        var cycle = (int)(t / LoopS);
        if (cycle != _loopIndex)
        {
            _loopIndex = cycle;
            _loopStart = Model.Cursor; // re-anchor each replay to wherever the pointer is now
        }
        var elapsed = t - cycle * LoopS;
        var target = new Point(Model.Ring.X + Model.Ring.Width / 2, Model.Ring.Y + Model.Ring.Height / 2);

        if (elapsed < FlyS)
        {
            DrawFlightTrail(dc, elapsed, _loopStart, target);
            var progress = EaseInOutCubic(elapsed / FlyS);
            var pos = Lerp(_loopStart, target, progress);
            DrawFireflyGlow(dc, pos, 1.0);
        }
        else if (elapsed < FlyS + ClickS)
        {
            var progress = (elapsed - FlyS) / ClickS;
            DrawFireflyGlow(dc, target, 1.0);
            DrawClickRipple(dc, target, progress);
        }
        else if (elapsed < FlyS + ClickS + FadeS)
        {
            var progress = (elapsed - FlyS - ClickS) / FadeS;
            DrawFireflyGlow(dc, target, 1.0 - progress);
        }
        // else: pause phase, nothing to draw until the next replay
    }

    private static double EaseInOutCubic(double x) =>
        x < 0.5 ? 4 * x * x * x : 1 - Math.Pow(-2 * x + 2, 3) / 2;

    private static Point Lerp(Point a, Point b, double p) =>
        new(a.X + (b.X - a.X) * p, a.Y + (b.Y - a.Y) * p);

    /// <summary>A continuous tapered light streak behind the flying demo firefly — not dots.
    /// Since the flight is a deterministic replay (not live cursor motion), each segment is just
    /// "where the firefly was" a moment ago along the same eased path, connected into a line that
    /// thins and fades toward the tail.</summary>
    private void DrawFlightTrail(DrawingContext dc, double elapsed, Point start, Point target)
    {
        const double trailS = 0.22;
        const int steps = 18;
        Point? prev = null;
        for (var i = steps; i >= 0; i--)
        {
            var pastElapsed = elapsed - (double)i / steps * trailS;
            if (pastElapsed < 0) { prev = null; continue; }
            var pos = Lerp(start, target, EaseInOutCubic(pastElapsed / FlyS));
            if (prev is Point from)
            {
                var life = 1 - (double)i / steps;
                var color = Color.FromArgb((byte)Math.Round(0.75 * life * 255), Accent.R, Accent.G, Accent.B);
                var pen = new Pen(new SolidColorBrush(color), 2 + 5 * life) { StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round };
                dc.DrawLine(pen, from, pos);
            }
            prev = pos;
        }
    }

    private void DrawFireflyGlow(DrawingContext dc, Point at, double opacity)
    {
        var pulse = 0.5 + 0.5 * Math.Sin((_clock.Elapsed.TotalSeconds) * 2 * Math.PI / PulsePeriodS);
        const int layers = 3;
        var spread = 11 + 7 * pulse;
        for (var i = 0; i < layers; i++)
        {
            var grow = (i + 1) * spread / layers;
            var alpha = 0.38 * (1 - (double)i / layers) * opacity;
            var glow = Color.FromArgb((byte)Math.Round(alpha * 255), Accent.R, Accent.G, Accent.B);
            dc.DrawEllipse(new SolidColorBrush(glow), null, at, 3 + grow, 3 + grow);
        }
        dc.DrawEllipse(new SolidColorBrush(Color.FromArgb((byte)Math.Round(255 * opacity), Accent.R, Accent.G, Accent.B)), null, at, 5.5, 5.5);
        dc.DrawEllipse(new SolidColorBrush(Color.FromArgb((byte)Math.Round(255 * opacity), 255, 255, 255)), null, at, 2.2, 2.2);
    }

    private void DrawClickRipple(DrawingContext dc, Point at, double progress)
    {
        var radius = 5 + 30 * progress;
        var alpha = (1 - progress) * 0.8;
        var color = Color.FromArgb((byte)Math.Round(alpha * 255), Accent.R, Accent.G, Accent.B);
        dc.DrawEllipse(null, new Pen(new SolidColorBrush(color), 3), at, radius, radius);
    }

    private void DrawGlow(DrawingContext dc, double t, Color color)
    {
        // A soft, single-source breathing glow (DS's primary-button hover shadow), not an
        // 8-layer stack: 3 thin passes is enough to read as a blur without looking painted on.
        var pulse = 0.5 + 0.5 * Math.Sin(t * 2 * Math.PI / PulsePeriodS);
        var strength = 0.25 + 0.5 * Model.Proximity;
        var spread = 6 + 12 * strength * (0.7 + 0.3 * pulse);
        const int layers = 3;
        for (var i = 0; i < layers; i++)
        {
            var grow = (i + 1) * spread / layers;
            var alpha = 0.28 * strength * (1 - (double)i / layers);
            var glow = Color.FromArgb((byte)Math.Round(alpha * 255), color.R, color.G, color.B);
            var pen = new Pen(new SolidColorBrush(glow), spread / layers + 1);
            var r = GuidanceGeometry.Inflate(Model.Ring, grow);
            dc.DrawRoundedRectangle(null, pen, r, 8 + grow, 8 + grow);
        }
    }

    private void DrawRing(DrawingContext dc, Color color)
    {
        dc.DrawRoundedRectangle(null, new Pen(new SolidColorBrush(color), 3), Model.Ring, 8, 8);
    }

    private void DrawCheck(DrawingContext dc)
    {
        var c = new Point(Model.Ring.Right, Model.Ring.Top);
        dc.DrawEllipse(new SolidColorBrush(Success), new Pen(new SolidColorBrush(Surface1), 2), c, 11, 11);

        var geometry = new StreamGeometry();
        using (var ctx = geometry.Open())
        {
            ctx.BeginFigure(new Point(c.X - 5, c.Y), isFilled: false, isClosed: false);
            ctx.LineTo(new Point(c.X - 1, c.Y + 4), isStroked: true, isSmoothJoin: false);
            ctx.LineTo(new Point(c.X + 5.5, c.Y - 4.5), isStroked: true, isSmoothJoin: false);
        }
        var pen = new Pen(new SolidColorBrush(Surface1), 2.2) { StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round, LineJoin = PenLineJoin.Round };
        dc.DrawGeometry(null, pen, geometry);
    }

    private void DrawHelperChip(DrawingContext dc)
    {
        var labelText = Text("Helper: ", 14, bold: true, Accent);
        var valueText = Text($"“{Model.HelperText}”", 14, bold: false, TextPrimary, maxWidth: 560 * TextScale, ellipsize: true);

        var h = 32 * TextScale;
        const double pad = 14;
        var chip = new Rect(16, 16, labelText.Width + valueText.Width + 2 * pad, h);

        dc.DrawRoundedRectangle(new SolidColorBrush(Surface1), new Pen(new SolidColorBrush(BorderSubtle), 1), chip, 12, 12);
        dc.DrawText(labelText, new Point(chip.X + pad, chip.Y + (h - labelText.Height) / 2));
        dc.DrawText(valueText, new Point(chip.X + pad + labelText.Width, chip.Y + (h - valueText.Height) / 2));
    }

    private void DrawStatus(DrawingContext dc)
    {
        var ok = Model.State == GuidanceState.Confirmed;
        var text = Text(Model.StatusText, 14, bold: true, TextPrimary);
        var h = 34 * TextScale;
        var dot = 6 * TextScale;
        const double pad = 14;
        var w = pad + 2 * dot + 10 + text.Width + pad;
        var pill = new Rect(ActualWidth - w - 16, 16, w, h);

        dc.DrawRoundedRectangle(new SolidColorBrush(Surface1), new Pen(new SolidColorBrush(BorderSubtle), 1), pill, 12, 12);
        var center = new Point(pill.X + pad + dot, pill.Y + h / 2);
        dc.DrawEllipse(new SolidColorBrush(ok ? Success : Accent), null, center, dot, dot);
        dc.DrawText(text, new Point(center.X + dot + 10, pill.Y + (h - text.Height) / 2));
    }

    private void DrawCaption(DrawingContext dc, Target target)
    {
        var maxWidth = 340 * TextScale;
        const double pad = 14, gap = 4;

        var titleText = Text(target.Instruction, 17, bold: true, Accent, maxWidth);
        var bodyText = Text(target.Caption, 14, bold: false, TextPrimary, maxWidth);
        var w = Math.Max(titleText.Width, bodyText.Width) + 2 * pad;
        var h = titleText.Height + gap + bodyText.Height + 2 * pad;

        var x = Math.Min(Math.Max(Model.Ring.Left + Model.Ring.Width / 2 - w / 2, 8), ActualWidth - w - 8);
        var y = Model.Ring.Top - 14 - h;
        if (y < 60) y = Model.Ring.Bottom + 14; // no room above (status pill lives up there): go below
        var card = new Rect(x, y, w, h);

        dc.DrawRoundedRectangle(new SolidColorBrush(Surface1), new Pen(new SolidColorBrush(Accent), 1.5), card, 10, 10);
        dc.DrawText(titleText, new Point(x + pad, y + pad));
        dc.DrawText(bodyText, new Point(x + pad, y + pad + titleText.Height + gap));
    }

    private FormattedText Text(string s, double size, bool bold, Color color, double? maxWidth = null, bool ellipsize = false)
    {
        var ft = new FormattedText(s, CultureInfo.InvariantCulture, FlowDirection.LeftToRight, bold ? _bold : _regular,
            size * TextScale, new SolidColorBrush(color), VisualTreeHelper.GetDpi(this).PixelsPerDip);
        if (maxWidth is double mw)
        {
            ft.MaxTextWidth = mw;
            if (ellipsize)
            {
                ft.MaxLineCount = 1;
                ft.Trimming = TextTrimming.CharacterEllipsis;
            }
        }
        return ft;
    }
}
