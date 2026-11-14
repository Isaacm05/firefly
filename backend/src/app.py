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
CONFIDENCE_THRESHOLD = 0.70  # FR-09
CALL_TIMEOUT_MS = 10_000  # FR-09: no response within 10s -> fail safe, no highlight

PROMPT = """
You are locating a single target in an image for an accessibility tool that highlights
it for a learner, based on an instruction from a sighted helper.

Instruction: {instruction}

Find the single UI element or physical object this instruction refers to.
Respond with its bounding box as a fraction (0 to 1) of the image's width and height
(left, top, width, height), plus your confidence (0 to 1) that this is the correct
target. If the target is not visible in the image, set "found" to false and leave the
box fields as 0.
"""

_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "found": types.Schema(type=types.Type.BOOLEAN),
        "left": types.Schema(type=types.Type.NUMBER),
        "top": types.Schema(type=types.Type.NUMBER),
        "width": types.Schema(type=types.Type.NUMBER),
        "height": types.Schema(type=types.Type.NUMBER),
        "confidence": types.Schema(type=types.Type.NUMBER),
    },
    required=["found", "left", "top", "width", "height", "confidence"],
)


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


def _is_valid_box(result):
    for key in ("left", "top", "width", "height"):
        value = result.get(key)
        if not isinstance(value, (int, float)) or not (0 <= value <= 1):
            return False
    return result["left"] + result["width"] <= 1.0001 and result["top"] + result["height"] <= 1.0001


def _not_found_response():
    # FR-09: malformed box, low confidence, or timeout all fail the same way —
    # no highlight, let the helper rephrase.
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"found": False, "message": "Target could not be found"}),
    }


def lambda_handler(event, context):
    body = json.loads(event["body"])
    instruction = body["instruction"]
    image_bytes = _prep_image(base64.b64decode(body["image"]))

    try:
        response = _client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                PROMPT.format(instruction=instruction),
                {"inline_data": {"mime_type": "image/png", "data": image_bytes}},
            ],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                http_options=types.HttpOptions(timeout=CALL_TIMEOUT_MS),
            ),
        )
        result = json.loads(response.text)
    except Exception:
        return _not_found_response()

    if (
        not result.get("found")
        or result.get("confidence", 0) < CONFIDENCE_THRESHOLD
        or not _is_valid_box(result)
    ):
        return _not_found_response()

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "found": True,
                "box": {k: result[k] for k in ("left", "top", "width", "height")},
                "confidence": result["confidence"],
            }
        ),
    }
