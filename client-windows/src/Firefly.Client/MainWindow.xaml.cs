using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Threading;

namespace Firefly.Client;

public partial class MainWindow : Window
{
    private const string DemoGeminiJson =
        """{"steps":[{"label":"Print","instruction":"Click Print"},{"label":"OK","instruction":"Click OK"}],"first_target":{"found":true,"box_2d":[810,820,890,920],"confidence":0.96,"needs_caption":true,"caption":"The blue button at the bottom right of this window."}}""";

    private static readonly IReadOnlyList<GuidanceStep> DemoPlan = new[]
    {
        new GuidanceStep("Print", "Click Print", "The blue button at the bottom right of this window."),
        new GuidanceStep("OK", "Click OK", "The confirmation button in the print dialog.")
    };

    private DispatcherTimer? _nextStepTimer;

    public MainWindow()
    {
        InitializeComponent();

        CornerWidgetControl.Started += (_, mode) =>
        {
            HelperChip.Visibility = Visibility.Visible;
            UpdateTelemetry($"Started Firefly in {mode} mode — status: \"{CornerWidgetControl.Flow.StatusText}\" (click status pill to toggle controls)");
        };

        CornerWidgetControl.Stopped += (_, _) =>
        {
            _nextStepTimer?.Stop();
            ResetCanvasVisuals();
            UpdateTelemetry("Stopped Firefly — session cleared (NFR-03).");
        };

        CornerWidgetControl.SettingsRequested += (_, _) =>
            UpdateTelemetry("SettingsRequested event fired from CornerWidget.");

        CornerWidgetControl.ReadAloudToggled += (_, enabled) =>
            UpdateTelemetry($"ReadAloudToggled: {(enabled ? "Enabled" : "Disabled")}");

        CornerWidgetControl.TextScaleChanged += (_, scale) =>
        {
            FloatingCaptionScale.ScaleX = scale;
            FloatingCaptionScale.ScaleY = scale;
            HelperChipScale.ScaleX = scale;
            HelperChipScale.ScaleY = scale;
            UpdateTelemetry($"TextScaleChanged: {scale:0.0}x (entire widget & cards scaled)");
        };

        CornerWidgetControl.StepDismissed += (_, _) =>
        {
            FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
            UpdateTelemetry("StepDismissed event fired.");
        };

        UpdateTelemetry("Ready. Click the top-right pill or use the Flow 2 simulator buttons below.");
    }

    // Screen 1: Initialize Listening & Receive Gemini API JSON
    private void SimScreen1_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        HelperChip.Visibility = Visibility.Visible;
        SimulatedPrintButton.Content = "Print";
        TrailOverlayCanvas.Visibility = Visibility.Collapsed;
        TargetGlowRing.Visibility = Visibility.Collapsed;
        FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
        TargetConfirmedBadge.Visibility = Visibility.Collapsed;

        CornerWidgetControl.LoadPlan(DemoPlan, DemoPlan[0].Caption);
        UpdateTelemetry($"Screen 1 (Location returned): {DemoGeminiJson}");
    }

    // Screen 2: Draw Mouse Path ("Follow the trail")
    private void SimScreen2_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        EnsurePlanLoaded();
        HelperChip.Visibility = Visibility.Visible;
        TrailOverlayCanvas.Visibility = Visibility.Visible;
        TargetGlowRing.Visibility = Visibility.Collapsed;
        FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
        TargetConfirmedBadge.Visibility = Visibility.Collapsed;

        CornerWidgetControl.SetFollowTrail();
        UpdateTelemetry("Screen 2 (Draw mouse path): Dotted trail active — Status: \"Follow the trail\"");
    }

    // Screen 3: Highlight Target ("Click the glowing button")
    private void SimScreen3_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        EnsurePlanLoaded();
        HelperChip.Visibility = Visibility.Visible;
        TrailOverlayCanvas.Visibility = Visibility.Visible;
        TargetGlowRing.Visibility = Visibility.Visible;
        FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
        TargetConfirmedBadge.Visibility = Visibility.Collapsed;

        CornerWidgetControl.SetHighlightTarget();
        UpdateTelemetry("Screen 3 (Highlight target): Reactive glow ring active — Status: \"Click the glowing button\"");
    }

    // Screen 4: Text Overlay / Caption ("Click Print — The blue button at the bottom right of this window.")
    private void SimScreen4_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        HelperChip.Visibility = Visibility.Visible;
        SimulatedPrintButton.Content = "Print";
        TrailOverlayCanvas.Visibility = Visibility.Visible;
        TargetGlowRing.Visibility = Visibility.Visible;
        FloatingTargetCaptionCard.Visibility = Visibility.Visible;
        TargetConfirmedBadge.Visibility = Visibility.Collapsed;

        CornerWidgetControl.SetStep(
            1,
            2,
            "Click Print",
            "The blue button at the bottom right of this window.");

        FloatingOverlayTitle.Text = "Click Print";
        FloatingOverlayBody.Text = "The blue button at the bottom right of this window.";
        UpdateTelemetry("Screen 4 (Text overlay): Corner status = \"Click the glowing button\" + on-target caption card.");
    }

    // Screen 5: Click & Confirm ("Done! Waiting for the next step" -> advances to Step 2 "Click OK")
    private void SimScreen5_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        EnsurePlanLoaded();
        HelperChip.Visibility = Visibility.Visible;
        TrailOverlayCanvas.Visibility = Visibility.Collapsed;
        TargetGlowRing.Visibility = Visibility.Collapsed;
        FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
        TargetConfirmedBadge.Visibility = Visibility.Visible;

        CornerWidgetControl.SetStepCompleted();
        UpdateTelemetry("Screen 5 (Click & confirm): \"Done! Waiting for the next step\" -> advancing to Step 2 (\"Click OK\")...");

        _nextStepTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(1400) };
        _nextStepTimer.Tick += (_, _) =>
        {
            _nextStepTimer.Stop();
            TargetConfirmedBadge.Visibility = Visibility.Collapsed;
            TargetGlowRing.Visibility = Visibility.Visible;
            FloatingTargetCaptionCard.Visibility = Visibility.Visible;
            FloatingOverlayTitle.Text = "Click OK";
            FloatingOverlayBody.Text = "The confirmation button in the print dialog.";
            SimulatedPrintButton.Content = "OK";
            CornerWidgetControl.SetStep(2, 2, "Click OK", "The confirmation button in the print dialog.");
            UpdateTelemetry("Advanced to Step 2 of 2: \"Click OK\"");
        };
        _nextStepTimer.Start();
    }

    // Error Fallback 1: No Steps Returned
    private void SimNoStepsError_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        ResetCanvasVisuals();
        HelperChip.Visibility = Visibility.Visible;

        CornerWidgetControl.SetNoStepsFallback();
        UpdateTelemetry($"No Steps Fallback triggered: \"{CornerWidgetControl.Flow.StatusText}\"");
    }

    // Error Fallback 2: API Error
    private void SimApiError_Click(object sender, RoutedEventArgs e)
    {
        _nextStepTimer?.Stop();
        ResetCanvasVisuals();
        HelperChip.Visibility = Visibility.Visible;

        CornerWidgetControl.SetApiErrorFallback();
        UpdateTelemetry($"API Error Fallback triggered (Red dot {CornerWidgetControl.Flow.IndicatorColorHex}): \"{CornerWidgetControl.Flow.StatusText}\"");
    }

    private void EnsurePlanLoaded()
    {
        if (CornerWidgetControl.Flow.Steps.Count == 0)
        {
            CornerWidgetControl.LoadPlan(DemoPlan, DemoPlan[0].Caption);
        }
    }

    private void ResetCanvasVisuals()
    {
        HelperChip.Visibility = Visibility.Collapsed;
        TrailOverlayCanvas.Visibility = Visibility.Collapsed;
        TargetGlowRing.Visibility = Visibility.Collapsed;
        FloatingTargetCaptionCard.Visibility = Visibility.Collapsed;
        TargetConfirmedBadge.Visibility = Visibility.Collapsed;
        SimulatedPrintButton.Content = "Print";
    }

    private void UpdateTelemetry(string logMessage)
    {
        var flow = CornerWidgetControl.Flow;
        SimulatorTelemetryText.Text =
            $"State: {flow.State} | Mode: {flow.CallMode} | Scale: {flow.TextScale:0.0}x | ReadAloud: {(flow.IsReadAloudEnabled ? "On" : "Off")}";
        SimulatorLogText.Text = logMessage;
    }
}
