import base64
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

#INSTRUCTION FORMAT: python backend/test_local.py --image "test_screen.png" --instruction "*Instrcution*"

# Ensure backend/src is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Provide dummy key before importing app so module-level client init does not fail
os.environ.setdefault("GEMINI_API_KEY", "dummy_key_for_unit_tests")

import app
import cv2
import numpy as np


class TestApp(unittest.TestCase):
    def setUp(self):
        # Create a small in-memory 100x100 white PNG image
        small_img = np.full((100, 100, 3), 255, dtype=np.uint8)
        _, encoded = cv2.imencode(".png", small_img)
        self.sample_bytes = encoded.tobytes()
        self.sample_b64 = base64.b64encode(self.sample_bytes).decode("utf-8")

    def test_prep_image_small_image(self):
        """Verifies _prep_image encodes valid PNG without downscaling when under MAX_DIM."""
        processed = app._prep_image(self.sample_bytes)
        self.assertIsInstance(processed, bytes)

        # Check it can be decoded back
        decoded = cv2.imdecode(np.frombuffer(processed, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape[:2], (100, 100))

    def test_prep_image_oversized_downscaling(self):
        """Verifies _prep_image scales images down if dimensions exceed MAX_DIM (1568)."""
        large_img = np.full((2000, 1000, 3), 255, dtype=np.uint8)
        _, encoded = cv2.imencode(".png", large_img)
        large_bytes = encoded.tobytes()

        processed = app._prep_image(large_bytes)
        decoded = cv2.imdecode(np.frombuffer(processed, np.uint8), cv2.IMREAD_COLOR)
        h, w = decoded.shape[:2]

        # Max dimension should be capped at app.MAX_DIM (1568)
        self.assertEqual(max(h, w), app.MAX_DIM)

    @patch.object(app._client.models, "generate_content")
    def test_lambda_handler_success(self, mock_generate):
        """Verifies lambda_handler parses the API gateway event and returns steps."""
        mock_resp = MagicMock()
        mock_resp.text = "Wi-Fi icon (bottom-right taskbar), Network & Internet (left sidebar), Wi-Fi toggle switch (top-right of main panel)"
        mock_generate.return_value = mock_resp

        event = {
            "body": json.dumps({
                "instruction": "turn on wifi",
                "image": self.sample_b64,
            })
        }

        result = app.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")

        body = json.loads(result["body"])
        self.assertIn("steps", body)
        self.assertEqual(
            body["steps"],
            [
                "Wi-Fi icon (bottom-right taskbar)",
                "Network & Internet (left sidebar)",
                "Wi-Fi toggle switch (top-right of main panel)",
            ],
        )
        self.assertIn("step_queue", body)
        self.assertEqual(len(body["step_queue"]), 3)
        self.assertEqual(body["step_queue"][0]["status"], "pending")
        self.assertEqual(body["step_queue"][0]["timeout_s"], 15.0)

    def test_validate_normalized_bbox_and_confidence_gate(self):
        """Verifies FR-09 normalized bbox validation and 70% confidence threshold."""
        valid = app.validate_normalized_bbox([200, 100, 400, 500], confidence=0.85)
        self.assertIsNotNone(valid)
        self.assertAlmostEqual(valid["left"], 0.1)
        self.assertAlmostEqual(valid["top"], 0.2)
        self.assertAlmostEqual(valid["width"], 0.4)
        self.assertAlmostEqual(valid["height"], 0.2)

        # Low confidence (< 0.70) must be rejected
        self.assertIsNone(app.validate_normalized_bbox([200, 100, 400, 500], confidence=0.65))
        # Malformed coordinates must be rejected
        self.assertIsNone(app.validate_normalized_bbox([500, 100, 200, 500], confidence=0.95))


if __name__ == "__main__":
    unittest.main()
