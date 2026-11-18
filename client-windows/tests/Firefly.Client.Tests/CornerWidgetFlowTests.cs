using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

public class CornerWidgetFlowTests
{
    [Fact]
    public void FullLifecycle_GoesIdleToListeningToStoppedAndBack()
    {
        var state = WidgetState.Idle;

        state = CornerWidgetFlow.OpenMenu(state);
        Assert.Equal(WidgetState.MenuOpen, state);

        state = CornerWidgetFlow.Start(state);
        Assert.Equal(WidgetState.Listening, state);

        state = CornerWidgetFlow.Stop(state);
        Assert.Equal(WidgetState.Stopped, state);

        state = CornerWidgetFlow.Reset(state);
        Assert.Equal(WidgetState.Idle, state);
    }

    [Theory]
    [InlineData(WidgetState.Idle)]
    [InlineData(WidgetState.Listening)]
    [InlineData(WidgetState.Stopped)]
    public void Start_OnlyFiresFromMenuOpen_OtherwiseNoOp(WidgetState current)
    {
        Assert.Equal(current, CornerWidgetFlow.Start(current));
    }

    [Theory]
    [InlineData(WidgetState.Idle)]
    [InlineData(WidgetState.MenuOpen)]
    [InlineData(WidgetState.Stopped)]
    public void Stop_OnlyFiresFromListening_OtherwiseNoOp(WidgetState current)
    {
        Assert.Equal(current, CornerWidgetFlow.Stop(current));
    }
}
