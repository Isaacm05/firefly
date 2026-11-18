# Firefly Grounding API Contract

Version: 0.1 (draft) · Issue: #33 · Owner: Natalia Hombs

The grounding API is the only component that calls Gemini, so the API key never
ships to any client. A client sends a screenshot plus what the helper said; the API
returns an ordered list of steps and where to highlight. The client never sends
clicks or keystrokes. It only draws a highlight.

## Conventions

- Transport: HTTPS, JSON bodies, `Content-Type: application/json`
- Base URL: from the SAM stack output (`GroundingApiUrl`), e.g.
  `https://<api-id>.execute-api.us-east-2.amazonaws.com/Prod`
- Images: the client captures the screen, scales it down to **at most 1280 px wide**,
  JPEG-encodes it (quality 80), and sends it base64-encoded. Only one screen per request.
- Coordinates: every box is **normalized 0–1, top-left origin**, relative to the
  screenshot that was sent. The client maps it back to real pixels (DPI and monitor offset).
- Privacy (NFR-03): the API keeps images in memory only. It never writes them to disk,
  never logs them, and frees them as soon as the response is built.

## Data types

### Step
| Field | Type | Description |
|---|---|---|
| `label` | string | The element's exact visible text, or a short name if it has none (e.g. `"Print"`) |
| `instruction` | string | A short command, under 6 words (e.g. `"Click Print"`) |

### Target
| Field | Type | Description |
|---|---|---|
| `x` | float 0–1 | Left edge of the box |
| `y` | float 0–1 | Top edge of the box |
| `w` | float 0–1 | Box width |
| `h` | float 0–1 | Box height |
| `label` | string | Copied from the step |
| `instruction` | string | Copied from the step |
| `caption` | string | One plain sentence saying where the element is |
| `needs_caption` | bool | `true` if the element is small or looks like elements near it. The client should show `caption` only when this is `true`. |
| `confidence` | float 0–1 | How sure the model is. Always ≥ 0.7, because anything lower becomes `null`. |

A target is returned as **`null`** (meaning: don't highlight) when the model:
- says the element isn't visible
- returns a box that isn't 4 values, or falls outside the screen
- reports confidence below **0.7** (FR-09)
- returns a box covering more than **50%** of the screen

## Endpoints

### `POST /plan`
Splits the helper's instruction into ordered steps and locates the **first** step,
all in one Gemini call. The server allows Gemini up to **20 s**.

Request:
```json
{
  "instruction": "Click Print, then OK",
  "image": "<base64 JPEG>"
}
```

Response `200`:
```json
{
  "steps": [
    { "label": "Print", "instruction": "Click Print" },
    { "label": "OK", "instruction": "Click OK" }
  ],
  "target": {
    "x": 0.705, "y": 0.812, "w": 0.085, "h": 0.050,
    "label": "Print",
    "instruction": "Click Print",
    "caption": "The blue button at the bottom right of this window.",
    "needs_caption": false,
    "confidence": 0.93
  }
}
```
- `steps` can be empty if the model couldn't work out the task.
- `target` can be `null` even when `steps` isn't empty.

### `POST /locate`
Locates one step's element on a **new** screenshot. The client calls this for every
step after the first, once the learner has acted on the previous step. The server
allows Gemini up to **10 s** (FR-09).

Request:
```json
{
  "step": { "label": "OK", "instruction": "Click OK" },
  "image": "<base64 JPEG>"
}
```

Response `200`:
```json
{
  "target": {
    "x": 0.612, "y": 0.640, "w": 0.060, "h": 0.045,
    "label": "OK",
    "instruction": "Click OK",
    "caption": "The OK button under the printer list.",
    "needs_caption": true,
    "confidence": 0.88
  }
}
```
- `target` is `null` if the element wasn't found or failed the checks above.
- Timeouts and model errors on `/locate` **fail safe**: they return `200` with
  `target: null`, not an error status.

## Errors

| Status | Body | When |
|---|---|---|
| `400` | `{ "error": "bad_request", "detail": "..." }` | Missing or invalid `instruction`, `step`, or `image`, or the image isn't valid base64 |
| `502` | `{ "error": "model_error" }` | `/plan` only: Gemini returned an error or an answer that couldn't be read |
| `504` | `{ "error": "timeout" }` | `/plan` only: Gemini took longer than 20 s |

## What the client shows

| Situation | Message |
|---|---|
| `/plan` → `steps` is empty | "I could not work out the steps. Ask your helper to say it another way." |
| `target` is `null` | "I couldn't find "{label}". Ask your helper to say it another way." |
| Any `4xx` / `5xx`, or the network fails | "Something went wrong. Ask your helper to try again." |
| All steps done | "All done!" |

## Typical flow

1. The helper speaks. The client takes a screenshot and calls `POST /plan`.
2. The client highlights `target` for `steps[0]`, then waits for the learner to act.
3. For each later step, the client waits about 0.8 s, takes a new screenshot, and calls `POST /locate`.
4. After the last step, the client shows "All done!"

## Mock mode

If the Lambda's `MOCK_MODE` is set to `1`, both endpoints return canned responses
from `mock-frameworks/` (`plan.json`, `locate.json`) without calling Gemini. The
request is still validated (`400` rules apply). Use this to build the client
without an API key.

## Open questions

- Multi-monitor: add a `screen` index to each request and target?
- Should `label`/`caption` ever be shown, or is the highlight silent apart from `needs_caption`?
- Model: `gemini-3.5-flash` (prototype) vs `gemini-3.8-flash` (old scaffold). It's set by
  the `GEMINI_MODEL` env var either way.
