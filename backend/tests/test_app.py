import base64
import json
import os
import sys

os.environ.setdefault("GEMINI_API_KEY", "test")

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import app as grounding_app  # noqa: E402


class _FakeClient:
    def __init__(self, reply):
        self._reply = reply

    class _Models:
        def __init__(self, reply):
            self._reply = reply

        def generate_content(self, **kwargs):
            return type("R", (), {"text": json.dumps(self._reply)})()

    @property
    def models(self):
        return self._Models(self._reply)


def _event():
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".png", image)
    return {
        "body": json.dumps(
            {
                "instruction": "click the print button",
                "image": base64.b64encode(encoded.tobytes()).decode(),
            }
        )
    }


def test_found_with_confident_valid_box():
    grounding_app._client = _FakeClient(
        {"found": True, "left": 0.1, "top": 0.2, "width": 0.1, "height": 0.05, "confidence": 0.95}
    )

    result = grounding_app.lambda_handler(_event(), None)

    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["found"] is True
    assert body["box"] == {"left": 0.1, "top": 0.2, "width": 0.1, "height": 0.05}


def test_low_confidence_reports_not_found():
    grounding_app._client = _FakeClient(
        {"found": True, "left": 0.1, "top": 0.2, "width": 0.1, "height": 0.05, "confidence": 0.5}
    )

    result = grounding_app.lambda_handler(_event(), None)

    assert json.loads(result["body"])["found"] is False


def test_out_of_range_box_reports_not_found():
    grounding_app._client = _FakeClient(
        {"found": True, "left": 0.9, "top": 0.2, "width": 0.5, "height": 0.05, "confidence": 0.95}
    )

    result = grounding_app.lambda_handler(_event(), None)

    assert json.loads(result["body"])["found"] is False


def test_model_not_found_reports_not_found():
    grounding_app._client = _FakeClient(
        {"found": False, "left": 0, "top": 0, "width": 0, "height": 0, "confidence": 0}
    )

    result = grounding_app.lambda_handler(_event(), None)

    assert json.loads(result["body"])["found"] is False


if __name__ == "__main__":
    test_found_with_confident_valid_box()
    test_low_confidence_reports_not_found()
    test_out_of_range_box_reports_not_found()
    test_model_not_found_reports_not_found()
    print("ok")
