using System;
using System.Windows;

namespace Firefly.Client;

/// <summary>Ports guidance-highlight/guidance_overlay.py's _nearest_point/_distance 1:1.</summary>
public static class GuidanceGeometry
{
    public static Point NearestPoint(Point p, Rect r) =>
        new(Math.Min(Math.Max(p.X, r.Left), r.Right), Math.Min(Math.Max(p.Y, r.Top), r.Bottom));

    public static double Distance(Point p, Rect r)
    {
        var n = NearestPoint(p, r);
        var dx = p.X - n.X;
        var dy = p.Y - n.Y;
        return Math.Sqrt(dx * dx + dy * dy);
    }

    public static Rect Inflate(Rect r, double amount) =>
        new(r.X - amount, r.Y - amount, r.Width + 2 * amount, r.Height + 2 * amount);
}
