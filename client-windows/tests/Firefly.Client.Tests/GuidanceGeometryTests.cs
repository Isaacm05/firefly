using System.Windows;
using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

// Mirrors guidance-highlight/tests/test_overlay.py's geometry-helper tests exactly.
public class GuidanceGeometryTests
{
    [Fact]
    public void NearestPoint_InsideRect_IsItself()
    {
        var r = new Rect(10, 10, 100, 50);
        Assert.Equal(new Point(50, 30), GuidanceGeometry.NearestPoint(new Point(50, 30), r));
    }

    [Fact]
    public void NearestPoint_OutsideRect_IsOnEdge()
    {
        var r = new Rect(10, 10, 100, 50);
        Assert.Equal(new Point(110, 30), GuidanceGeometry.NearestPoint(new Point(200, 30), r));
    }

    [Fact]
    public void Distance_ToRect()
    {
        var r = new Rect(0, 0, 100, 100);
        Assert.Equal(0, GuidanceGeometry.Distance(new Point(50, 50), r));
        Assert.Equal(5, GuidanceGeometry.Distance(new Point(103, 104), r), precision: 6);
    }
}
