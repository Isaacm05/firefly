using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Firefly.Client;

/// <summary>One step of the helper's instruction, e.g. ("Print", "Click Print").</summary>
public sealed record Step(string Label, string Instruction);

public sealed record PlanResult(IReadOnlyList<Step> Steps, Target? Target);

/// <summary>The grounding API answered with a non-200 status (see doc/api-contract.md, Errors).</summary>
public sealed class GroundingApiException(int status, string body)
    : Exception($"Grounding API returned {status}: {body}")
{
    public int Status { get; } = status;
}

/// <summary>Client for the grounding API's POST /plan and POST /locate (doc/api-contract.md).
/// Only sends a screenshot + text and reads back normalized boxes - it never sends input to
/// the learner's machine.</summary>
public sealed class GroundingClient(HttpClient http, Uri baseUrl)
{
    // Trailing slash so "plan" resolves under a path base too (.../Prod/ -> .../Prod/plan).
    private readonly Uri _base = baseUrl.AbsoluteUri.EndsWith('/') ? baseUrl : new Uri(baseUrl.AbsoluteUri + "/");

    /// <summary>Local backend (`python backend/src/app.py`) unless FIREFLY_API_URL overrides it.</summary>
    public static Uri DefaultBaseUrl =>
        new(Environment.GetEnvironmentVariable("FIREFLY_API_URL") ?? "http://127.0.0.1:8000");

    // The API speaks snake_case (needs_caption); extra fields like confidence are ignored.
    private static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    private sealed record PlanBody(List<Step>? Steps, Target? Target);
    private sealed record LocateBody(Target? Target);

    public async Task<PlanResult> PlanAsync(string instruction, string imageBase64, CancellationToken token)
    {
        var body = await PostAsync<PlanBody>("plan", new { instruction, image = imageBase64 }, token);
        return new PlanResult(body.Steps ?? [], body.Target);
    }

    /// <summary>Returns null when the step's element wasn't found (no highlight, FR-09).</summary>
    public async Task<Target?> LocateAsync(Step step, string imageBase64, CancellationToken token)
    {
        var body = await PostAsync<LocateBody>("locate",
            new { step = new { label = step.Label, instruction = step.Instruction }, image = imageBase64 }, token);
        return body.Target;
    }

    private async Task<T> PostAsync<T>(string path, object payload, CancellationToken token)
    {
        using var content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        using var response = await http.PostAsync(new Uri(_base, path), content, token);
        var json = await response.Content.ReadAsStringAsync(token);
        if (!response.IsSuccessStatusCode)
            throw new GroundingApiException((int)response.StatusCode, json);
        return JsonSerializer.Deserialize<T>(json, Json)
               ?? throw new GroundingApiException((int)response.StatusCode, "empty body");
    }
}
