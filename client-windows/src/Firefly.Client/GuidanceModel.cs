using System;
using System.Windows;

namespace Firefly.Client;

/// <summary>Ports guidance-highlight/guidance_overlay.py's state machine and per-frame tracking
/// (FR-10/11/12), with no WPF rendering or Win32 dependency, so it's testable exactly like the
/// Python version's FakeInput harness: callers pass cursor/button/clock in instead of this class
/// polling them itself.</summary>
public sealed class GuidanceModel
{
    public const double RingPad = 6;
    public const double GlowRange = 450;   // px: glow ramps from dim (far) to full (touching the ring)
    public const double Near = 0.75;       // proximity at which the pill says "Click the glowing button"
    public const double StepTimeoutS = 15;
    public const double FoundPillS = 1.0;

    public GuidanceState State { get; private set; } = GuidanceState.Idle;
    public string HelperText { get; private set; } = "";
    public string StatusText { get; private set; } = "";
    public Target? Target { get; private set; }
    public Rect Ring { get; private set; }
    public Point Cursor { get; private set; }
    public double Proximity { get; private set; }

    public event Action<string>? StepFinished;

    private bool _wasDown;
    private double _stepStartedAt;

    public void ShowHelper(string text) => HelperText = text;

    public void ShowLooking() => SetState(GuidanceState.Looking, "Looking…");

    public void ShowTarget(Target target, Size viewport, bool currentlyDown, double now)
    {
        var box = new Rect(target.X * viewport.Width, target.Y * viewport.Height,
                            target.W * viewport.Width, target.H * viewport.Height);
        Target = target;
        Ring = GuidanceGeometry.Inflate(box, RingPad);
        _wasDown = currentlyDown; // ignore a press already in progress
        _stepStartedAt = now;
        SetState(GuidanceState.Guiding, "Found it");
    }

    public void ShowMessage(string text)
    {
        Target = null;
        SetState(GuidanceState.Message, text);
    }

    public void ShowFinished(string text)
    {
        Target = null;
        SetState(GuidanceState.Confirmed, text);
    }

    public void Tick(Point cursor, bool down, double now)
    {
        if (State == GuidanceState.Idle) return;

        Cursor = cursor;
        if (State == GuidanceState.Guiding)
        {
            Proximity = Math.Max(0.0, 1.0 - GuidanceGeometry.Distance(cursor, Ring) / GlowRange);

            if (down && !_wasDown && Ring.Contains(cursor))
            {
                SetState(GuidanceState.Confirmed, "Done! Waiting for the next step");
                StepFinished?.Invoke("clicked");
            }
            else if (now - _stepStartedAt > StepTimeoutS)
            {
                Target = null; // FR-12: remove the highlight and move on
                SetState(GuidanceState.Looking, "Moving on…");
                StepFinished?.Invoke("timeout");
            }
            else
            {
                var elapsed = now - _stepStartedAt;
                if (elapsed > FoundPillS)
                    StatusText = Proximity >= Near ? "Click the glowing button" : "Follow the trail";
            }

            _wasDown = down;
        }
    }

    private void SetState(GuidanceState state, string status)
    {
        State = state;
        StatusText = status;
    }
}
