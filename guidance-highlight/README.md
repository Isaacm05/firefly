# Firefly prototype: Guidance A (mouse trail + reactive glow ring)

Implements the **Guidance A** flow from the Figma file (*Flow 2 · Guidance · Candidate A*):
the helper's instruction is turned into steps, each target is located as a bounding box,
a dotted trail leads from the learner's pointer to a glowing ring that brightens as the
pointer gets closer, and the learner's own click inside the ring advances to the next step.

Firefly only draws. The overlay passes all input through and never sends clicks or keys.

### Files

* **`main.py`**: runs the loop (screenshot → box → trail + ring → wait for click → next step).
* **`create_instructions.py`**: one Gemini call that plans the steps and locates the first target.
* **`highlight_button.py`**: locates a later step's target on a fresh screenshot.
* **`targets.py`**: `Step` / `Target` types, the JSON answer schema, and FR-09 validation
  (malformed box, confidence < 0.7, or timeout → no highlight, short message instead).
* **`gemini.py`**: shared Gemini client with structured JSON output.
* **`guidance_overlay.py`**: the click-through overlay: trail, glow ring, caption card,
  status pill, helper chip, mouse tracking and click/timeout completion.
* **`practice.py`**: fake "Print a recipe" window with known button boxes (no API needed).
* **`take_screenshot.py`**: captures the primary screen into memory (never written to disk).
* **`encode_for_api.py`**: downscales + JPEG-encodes a screenshot for the API.

## Installation

Keep the virtual environment **outside** Box/OneDrive-synced folders. Syncing
thousands of PySide6 files stalls Python.

```bash
python -m venv C:\Users\<you>\.venvs\firefly
C:\Users\<you>\.venvs\firefly\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

Create a `.env` file in this folder:

```text
GEMINI_API_KEY=your_api_key_here
```

## Running

```bash
python main.py --practice              # try the overlay with the practice window, no API key
python main.py                         # asks what the helper said, then guides on your real screen
python main.py "open the print menu"   # instruction on the command line
python guidance_overlay.py             # overlay only: a test target in the middle of the screen
```

## Tests

```bash
pip install pytest
python -m pytest            # from this folder; about 2 s, no API key, nothing shown on screen
```

| File | What it checks |
|---|---|
| `tests/test_targets.py` | FR-09: box conversion; rejects malformed, out-of-range, low-confidence, oversized boxes |
| `tests/test_model_calls.py` | Planning/locating with canned Gemini answers; timeouts and API errors fail safe |
| `tests/test_overlay.py` | FR-10 pixel mapping, FR-11 click-through flags, mouse tracking, FR-12 click/timeout completion, drawing |
| `tests/test_pipeline.py` | Step loop: success, missing targets, no steps, timeouts, crashes, overlay hidden during capture |
| `tests/test_practice.py` | Practice window boxes, plus a full run through the real overlay |
| `tests/test_capture.py` | Screenshot shape and NFR-03 (nothing written to disk) |
| `tests/test_safety_scan.py` | Static scan: no input-injection APIs, no file writes (Deliverable 2) |

These test the code around the model, not how accurate the model is. Accuracy needs a
benchmark set of real screenshots with hand-marked boxes (Deliverable 4).

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `FIREFLY_TEXT_SCALE` | `1.0` | Text size for chip, pill and caption |
| `FIREFLY_STEP_TIMEOUT` | `15` | Seconds before a step times out (FR-12) |
| `FIREFLY_CAPTURE_VISIBLE` | unset | `1` = overlay shows up in screen recordings / screen share (it is hidden during Firefly's own screenshots instead) |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Model used for planning and locating |

By default the overlay is excluded from screen capture so Firefly's own screenshots never
contain an old highlight. That also hides it from OBS and Zoom screen share, so set
`FIREFLY_CAPTURE_VISIBLE=1` when recording a demo.
