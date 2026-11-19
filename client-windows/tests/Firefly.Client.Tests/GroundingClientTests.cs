using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Firefly.Client;
using Xunit;

namespace Firefly.Client.Tests;

// Response bodies below are copied from mock-frameworks/ (doc/api-contract.md), so these tests
// pin the client to the same JSON the real backend returns.
public class GroundingClientTests
{
    private const string PlanJson = """
        {"steps": [{"label": "Print", "instruction": "Click Print"},
                   {"label": "OK", "instruction": "Click OK"}],
         "target": {"x": 0.705, "y": 0.812, "w": 0.085, "h": 0.05, "label": "Print",
                    "instruction": "Click Print", "caption": "The blue button.",
                    "needs_caption": true, "confidence": 0.93}}
        """;

    private sealed class FakeHandler(HttpStatusCode status, string body) : HttpMessageHandler
    {
        public HttpRequestMessage? Request { get; private set; }
        public string? RequestBody { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token)
        {
            Request = request;
            RequestBody = request.Content is null ? null : await request.Content.ReadAsStringAsync(token);
            return new HttpResponseMessage(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };
        }
    }

    private static (GroundingClient, FakeHandler) Make(HttpStatusCode status, string body, string baseUrl = "http://127.0.0.1:8000")
    {
        var handler = new FakeHandler(status, body);
        return (new GroundingClient(new HttpClient(handler), new Uri(baseUrl)), handler);
    }

    [Fact]
    public async Task Plan_ParsesStepsAndSnakeCaseTarget()
    {
        var (api, handler) = Make(HttpStatusCode.OK, PlanJson);

        var plan = await api.PlanAsync("print it", "aW1n", CancellationToken.None);

        Assert.Equal(new[] { new Step("Print", "Click Print"), new Step("OK", "Click OK") }, plan.Steps);
        Assert.Equal(new Target(0.705, 0.812, 0.085, 0.05, "Print", "Click Print", "The blue button.", NeedsCaption: true),
                     plan.Target);
        Assert.Equal("http://127.0.0.1:8000/plan", handler.Request!.RequestUri!.ToString());
        Assert.Equal("""{"instruction":"print it","image":"aW1n"}""", handler.RequestBody);
    }

    [Fact]
    public async Task Plan_NoStepsAndNullTarget()
    {
        var (api, _) = Make(HttpStatusCode.OK, """{"steps": [], "target": null}""");
        var plan = await api.PlanAsync("x", "aW1n", CancellationToken.None);
        Assert.Empty(plan.Steps);
        Assert.Null(plan.Target);
    }

    [Fact]
    public async Task Locate_SendsStepAndReturnsNullWhenNotFound()
    {
        var (api, handler) = Make(HttpStatusCode.OK, """{"target": null}""");

        var target = await api.LocateAsync(new Step("OK", "Click OK"), "aW1n", CancellationToken.None);

        Assert.Null(target);
        Assert.EndsWith("/locate", handler.Request!.RequestUri!.ToString());
        Assert.Equal("""{"step":{"label":"OK","instruction":"Click OK"},"image":"aW1n"}""", handler.RequestBody);
    }

    [Theory]
    [InlineData(HttpStatusCode.BadRequest, """{"error": "bad_request", "detail": "x"}""")]
    [InlineData(HttpStatusCode.BadGateway, """{"error": "model_error"}""")]
    [InlineData(HttpStatusCode.GatewayTimeout, """{"error": "timeout"}""")]
    public async Task ErrorStatus_Throws(HttpStatusCode status, string body)
    {
        var (api, _) = Make(status, body);
        var ex = await Assert.ThrowsAsync<GroundingApiException>(() => api.PlanAsync("x", "aW1n", CancellationToken.None));
        Assert.Equal((int)status, ex.Status);
    }

    [Fact]
    public async Task BaseUrlWithPath_KeepsThePath()
    {
        var (api, handler) = Make(HttpStatusCode.OK, PlanJson, "https://example.com/Prod");
        await api.PlanAsync("x", "aW1n", CancellationToken.None);
        Assert.Equal("https://example.com/Prod/plan", handler.Request!.RequestUri!.ToString());
    }
}
