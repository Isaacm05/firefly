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

PROMPT = """
Look at this screenshot.

The user wants to: {instruction}

Identify the exact icons, buttons, or clickable UI elements visible on this screen that they need to click, in order, to accomplish this task.
For every item, ALWAYS specify both the specific icon/button name and its visual location on the screen in parentheses (for example: 'bottom-right taskbar', 'top-left menu', 'left sidebar', 'center of window').

Return ONLY a comma-separated list of the clickable icons/buttons with their location.
Do not include explanations, numbering, or extra text.

Example:
Wi-Fi icon (bottom-right taskbar), Network & Internet (left sidebar), Wi-Fi toggle switch (top-right of main panel)
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
        "body": json.dumps({"steps": steps}),
    }
