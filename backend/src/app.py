import base64
import json
import os

import cv2
import numpy as np
from google import genai
from google.genai import types

# ponytail: cv2 pulled in to match prototype/gemini_instructions.py's resize logic;
# opencv-python-headless is large for a Lambda zip — switch to a container image
# or a Pillow-only resize if the deployed package exceeds the 250MB unzipped limit.
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MAX_DIM = 1568  # Gemini's own recommended cap
MIN_CONFIDENCE = 0.70  # FR-09 confidence threshold
DEFAULT_STEP_TIMEOUT_S = 15.0  # FR-12 completion timeout

PROMPT = """
Look at this screenshot.

The user wants to: {instruction}

Identify the buttons or UI elements they need to click from this page, in order,
to accomplish this task.

Return ONLY a comma-separated list of the button names.
Do not include explanations, numbering, or extra text.

Example:
Settings, Wi-Fi, Network
"""


def _prep_image(image_bytes):
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image.shape[:2]
    scale = MAX_DIM / max(h, w)
    if scale < 1:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError("Could not encode image")
    return encoded.tobytes()


def validate_normalized_bbox(box_2d, confidence: float = 1.0) -> dict | None:
    """Validate [ymin, xmin, ymax, xmax] (0-1000 scale) into normalized [0, 1] bbox (FR-09)."""
    if confidence < MIN_CONFIDENCE:
        return None
    if not isinstance(box_2d, (list, tuple)) or len(box_2d) != 4:
        return None
    ymin, xmin, ymax, xmax = (float(v) / 1000.0 for v in box_2d)
    if not (0.0 <= xmin < xmax <= 1.0 and 0.0 <= ymin < ymax <= 1.0):
        return None
    return {
        "left": xmin,
        "top": ymin,
        "width": xmax - xmin,
        "height": ymax - ymin,
        "confidence": float(confidence),
    }


def build_step_queue(steps: list[str], first_bbox: dict | None = None) -> list[dict]:
    """Build structured sequential step queue entries for FR-06 / FR-12 client consumption."""
    return [
        {
            "index": idx,
            "label": label,
            "status": "pending",
            "timeout_s": DEFAULT_STEP_TIMEOUT_S,
            "bbox": first_bbox if idx == 0 else None,
        }
        for idx, label in enumerate(steps)
    ]


def lambda_handler(event, context):
    body = json.loads(event["body"])
    instruction = body["instruction"]
    image_bytes = _prep_image(base64.b64decode(body["image"]))

    response = _client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            PROMPT.format(instruction=instruction),
            {"inline_data": {"mime_type": "image/png", "data": image_bytes}},
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    steps = [label.strip() for label in response.text.split(",") if label.strip()]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "steps": steps,
            "step_queue": build_step_queue(steps),
        }),
    }
