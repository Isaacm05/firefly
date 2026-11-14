import base64
import io
import json
import os

from PIL import Image
from google import genai
from google.genai import types

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MAX_DIM = 1568  # Gemini's own recommended cap

PROMPT = """
Look at this screenshot.

The user wants to: {instruction}

Identify the UI element or object they need to interact with.
"""


def _prep_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    scale = MAX_DIM / max(image.size)
    if scale < 1:
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


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

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"text": response.text}),
    }
