namespace Firefly.Client;

/// <summary>Normalized (0-1, top-left origin) screen-relative box to highlight, plus the copy
/// shown alongside it. Mirrors guidance-highlight/targets.py's Target — intentionally without
/// its TargetAnswer/validation (FR-09) half, which belongs to the grounding pipeline, not this
/// rendering port.</summary>
public sealed record Target(double X, double Y, double W, double H, string Label, string Instruction, string Caption, bool NeedsCaption);
