using System.Collections.Generic;
using System.Windows;
using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

// Mirrors guidance-highlight/tests/test_overlay.py's mouse-tracking/completion tests (FR-10/11/12),
// using the same 1000x800 viewport and coordinates so the assertions carry over directly.
public class GuidanceModelTests
{
    private static readonly Size Viewport = new(1000, 800);

    private static Target MakeTarget(double x, double y, double w, double h) =>
        new(x, y, w, h, Label: "Print", Instruction: "Click Print", Caption: "", NeedsCaption: false);

    [Fact]
    public void ShowTarget_MapsNormalizedBoxToPixelsWithRingPadding()
    {
        var model = new GuidanceModel();
        model.ShowTarget(MakeTarget(0.5, 0.25, 0.1, 0.05), Viewport, currentlyDown: false, now: 0);

        var pad = GuidanceModel.RingPad;
        Assert.Equal(new Rect(500 - pad, 200 - pad, 100 + 2 * pad, 40 + 2 * pad), model.Ring);
        Assert.Equal(GuidanceState.Guiding, model.State);
        Assert.Equal("Found it", model.StatusText);
    }

    [Fact]
    public void Proximity_GetsStrongerAsPointerGetsCloser()
    {
        var model = new GuidanceModel();
        model.ShowTarget(MakeTarget(0.5, 0.5, 0.1, 0.05), Viewport, currentlyDown: false, now: 0);

        model.Tick(new Point(0, 0), down: false, now: 0);
        var far = model.Proximity;
        model.Tick(new Point(450, 380), down: false, now: 0);
        var near = model.Proximity;
        model.Tick(new Point(520, 410), down: false, now: 0); // inside the ring

        Assert.True(far < near);
        Assert.True(near < model.Proximity);
        Assert.Equal(1.0, model.Proximity);
    }

    [Fact]
    public void StatusText_SwitchesFromFoundToFollowToClick()
    {
        var model = new GuidanceModel();
        model.ShowTarget(MakeTarget(0.5, 0.5, 0.1, 0.05), Viewport, currentlyDown: false, now: 0);

        model.Tick(new Point(0, 0), down: false, now: 0);
        Assert.Equal("Found it", model.StatusText);

        model.Tick(new Point(0, 0), down: false, now: GuidanceModel.FoundPillS + 0.1);
        Assert.Equal("Follow the trail", model.StatusText);

        model.Tick(new Point(520, 410), down: false, now: GuidanceModel.FoundPillS + 0.1);
        Assert.Equal("Click the glowing button", model.StatusText);
    }

    [Fact]
    public void ClickInsideRing_ConfirmsStep()
    {
        var model = new GuidanceModel();
        var results = new List<string>();
        model.StepFinished += results.Add;
        model.ShowTarget(MakeTarget(0.5, 0.5, 0.1, 0.05), Viewport, currentlyDown: false, now: 0);

        model.Tick(new Point(520, 410), down: false, now: 0);
        model.Tick(new Point(520, 410), down: true, now: 0);

        Assert.Equal(new[] { "clicked" }, results);
        Assert.Equal(GuidanceState.Confirmed, model.State);
        Assert.Equal("Done! Waiting for the next step", model.StatusText);
    }

    [Fact]
    public void ClickOutsideRing_DoesNothing()
    {
        var model = new GuidanceModel();
        var results = new List<string>();
        model.StepFinished += results.Add;
        model.ShowTarget(MakeTarget(0.5, 0.5, 0.1, 0.05), Viewport, currentlyDown: false, now: 0);

        model.Tick(new Point(100, 100), down: false, now: 0);
        model.Tick(new Point(100, 100), down: true, now: 0);

        Assert.Empty(results);
        Assert.Equal(GuidanceState.Guiding, model.State);
    }

    [Fact]
    public void ButtonAlreadyHeldWhenStepStarts_IsIgnoredUntilReleased()
    {
        var model = new GuidanceModel();
        var results = new List<string>();
        model.StepFinished += results.Add;
        // e.g. still holding from the previous step's click
        model.ShowTarget(MakeTarget(0.5, 0.5, 0.1, 0.05), Viewport, currentlyDown: true, now: 0);

        model.Tick(new Point(520, 410), down: true, now: 0);
        Assert.Empty(results);

        model.Tick(new Point(520, 410), down: false, now: 0);
        model.Tick(new Point(520, 410), down: true, now: 0);
        Assert.Equal(new[] { "clicked" }, results);
    }
}
