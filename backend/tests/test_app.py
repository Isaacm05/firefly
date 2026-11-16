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
    body = json.loads(result["body"])
    assert body["steps"] == ["Settings", "Wi-Fi", "Network"]
    assert "step_queue" in body
    assert len(body["step_queue"]) == 3
    assert body["step_queue"][0]["status"] == "pending"
    assert body["step_queue"][0]["timeout_s"] == 15.0


def test_validate_normalized_bbox_and_confidence_gate():
    """Verifies FR-09 normalized bbox validation and 70% confidence threshold."""
    valid = grounding_app.validate_normalized_bbox([200, 100, 400, 500], confidence=0.85)
    assert valid is not None
    assert round(valid["left"], 2) == 0.1
    assert round(valid["top"], 2) == 0.2
    assert round(valid["width"], 2) == 0.4
    assert round(valid["height"], 2) == 0.2

    # Low confidence (< 0.70) must be rejected
    assert grounding_app.validate_normalized_bbox([200, 100, 400, 500], confidence=0.65) is None
    # Malformed coordinates must be rejected
    assert grounding_app.validate_normalized_bbox([500, 100, 200, 500], confidence=0.95) is None


if __name__ == "__main__":
    test_lambda_handler_parses_steps()
    test_validate_normalized_bbox_and_confidence_gate()
    print("ok")
