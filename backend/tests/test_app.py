import base64
import json
import os
import sys

os.environ.setdefault("GEMINI_API_KEY", "test")

import io

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app as grounding_app  # noqa: E402


class _FakeModels:
    def generate_content(self, **kwargs):
        return type("R", (), {"text": "the Settings gear icon, top right"})()


class _FakeClient:
    models = _FakeModels()


def test_lambda_handler_calls_gemini_and_returns_text():
    grounding_app._client = _FakeClient()

    image = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    event = {
        "body": json.dumps(
            {
                "instruction": "open settings",
                "image": base64.b64encode(buf.getvalue()).decode(),
            }
        )
    }

    result = grounding_app.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["text"] == "the Settings gear icon, top right"


if __name__ == "__main__":
    test_lambda_handler_calls_gemini_and_returns_text()
    print("ok")
