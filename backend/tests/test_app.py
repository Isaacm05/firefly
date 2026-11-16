import base64
import json
import os
import sys

os.environ.setdefault("GEMINI_API_KEY", "test")

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app as grounding_app  # noqa: E402


class _FakeResponse:
    text = "Settings, Wi-Fi, Network"


class _FakeClient:
    class models:
        @staticmethod
        def generate_content(**kwargs):
            return _FakeResponse()


def test_lambda_handler_parses_steps():
    grounding_app._client = _FakeClient()

    image = np.zeros((10, 10, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", image)
    event = {
        "body": json.dumps(
            {
                "instruction": "connect to wifi",
                "image": base64.b64encode(encoded.tobytes()).decode(),
            }
        )
    }

    result = grounding_app.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"])["steps"] == ["Settings", "Wi-Fi", "Network"]


if __name__ == "__main__":
    test_lambda_handler_parses_steps()
    print("ok")
