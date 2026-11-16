"""Local test runner for Firefly Lambda Handler.

Usage:
    # Test with your own screenshot and instruction:
    python backend/test_local.py --image path/to/screenshot.png --instruction "Turn on Wi-Fi"

    # Test in mock mode (no API key needed, tests the pipeline locally):
    python backend/test_local.py --image path/to/screenshot.png --instruction "Turn on Wi-Fi" --mock

    # Generate a dummy test image and run:
    python backend/test_local.py --generate-sample
"""

import argparse
import base64
import json
import os
import sys
import time
from unittest.mock import MagicMock

# 1. Helper to load a .env file if present in backend/ or root
def _load_env_file():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(backend_dir)
    for env_path in [os.path.join(backend_dir, ".env"), os.path.join(root_dir, ".env")]:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            print(f"[info] Loaded environment variables from: {env_path}")
            break

_load_env_file()

# 2. Add backend/src to sys.path so we can import app
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


def generate_sample_image(output_path="sample_screenshot.png"):
    """Generates a synthetic UI screenshot with labeled buttons for testing."""
    import cv2
    import numpy as np

    # Create a 1280x720 light gray canvas
    img = np.full((720, 1280, 3), 245, dtype=np.uint8)

    # Title header
    cv2.putText(img, "System Settings", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (40, 40, 40), 2)
    cv2.line(img, (50, 100), (1230, 100), (200, 200, 200), 2)

    # Simulated button items
    buttons = [
        ("Wi-Fi", (50, 160)),
        ("Bluetooth", (50, 260)),
        ("Display & Brightness", (50, 360)),
        ("Sound & Vibration", (50, 460)),
        ("Network & Internet", (50, 560)),
    ]

    for label, (x, y) in buttons:
        # Draw button box
        cv2.rectangle(img, (x, y - 40), (x + 360, y + 25), (255, 255, 255), -1)
        cv2.rectangle(img, (x, y - 40), (x + 360, y + 25), (210, 210, 210), 1)
        # Draw text
        cv2.putText(img, label, (x + 20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2)

    cv2.imwrite(output_path, img)
    print(f"[info] Generated synthetic screenshot at: {output_path}")
    return output_path


def build_mock_event(image_path: str, instruction: str) -> dict:
    """Reads an image from disk and wraps it into an API Gateway proxy event."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at: {image_path}")

    with open(image_path, "rb") as f:
        encoded_image = base64.b64encode(f.read()).decode("utf-8")

    body_payload = {
        "instruction": instruction,
        "image": encoded_image,
    }

    return {
        "resource": "/action",
        "path": "/action",
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_payload),
        "isBase64Encoded": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Test Firefly Lambda Handler Locally")
    parser.add_argument("--image", "-i", type=str, help="Path to image file (PNG/JPG)")
    parser.add_argument(
        "--instruction",
        "-t",
        type=str,
        default="Turn on Wi-Fi",
        help="Voice/text instruction (default: 'Turn on Wi-Fi')",
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate a synthetic UI screenshot to test with",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode without calling Gemini API (no API key required)",
    )

    args = parser.parse_args()

    # Determine image path
    image_path = args.image
    if args.generate_sample or not image_path:
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_screenshot.png")
        if not image_path and not os.path.exists(sample_path):
            print("[info] No image specified. Generating a sample UI screenshot...")
            image_path = generate_sample_image(sample_path)
        elif not image_path:
            image_path = sample_path

    # Check API key if not in mock mode
    if not args.mock and not os.environ.get("GEMINI_API_KEY"):
        print("\n" + "=" * 60)
        print("[!] ERROR: GEMINI_API_KEY environment variable is not set.")
        print("To run with the real Gemini model, set your API key:")
        print("  In PowerShell:")
        print('    $env:GEMINI_API_KEY="your-api-key"')
        print("  Or add it to a backend/.env file:")
        print("    GEMINI_API_KEY=your-api-key")
        print("\nTo test without an API key right now, use the --mock flag:")
        print(f"  python backend/test_local.py --image \"{image_path}\" --mock")
        print("=" * 60 + "\n")
        sys.exit(1)

    # Set dummy key for import if in mock mode and no key provided
    if args.mock and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = "mock_key_for_testing"

    # Import app module
    try:
        import app
    except ImportError as e:
        print(f"[!] Error importing app from backend/src: {e}")
        sys.exit(1)

    # Apply mock if requested
    if args.mock:
        mock_response = MagicMock()
        mock_response.text = "Wi-Fi icon (bottom-right taskbar), Network & Internet (left sidebar), Wi-Fi toggle switch (top-right of main panel)"
        app._client.models.generate_content = MagicMock(return_value=mock_response)
        print("[info] Running in MOCK mode (simulated Gemini response: 'Wi-Fi icon (bottom-right taskbar), Network & Internet (left sidebar), Wi-Fi toggle switch (top-right of main panel)')")

    print("\n--- Running Firefly Local Test ---")
    print(f"Image File  : {image_path}")
    print(f"Instruction : {args.instruction}")
    print(f"Mode        : {'MOCK' if args.mock else 'LIVE (Gemini 3.8 Flash)'}")
    print("-" * 34)

    # Build event
    event = build_mock_event(image_path, args.instruction)
    payload_kb = len(event["body"]) / 1024
    print(f"Constructed API Gateway event payload size: {payload_kb:.1f} KB")

    # Run lambda handler
    start_time = time.time()
    try:
        result = app.lambda_handler(event, None)
    except Exception as exc:
        print(f"\n[!] lambda_handler raised an exception: {exc}")
        raise exc

    elapsed = time.time() - start_time

    # Output results
    status_code = result.get("statusCode")
    body = json.loads(result.get("body", "{}"))
    steps = body.get("steps", [])

    print(f"\nCompleted in {elapsed:.2f}s | HTTP Status: {status_code}")
    print("\nIdentified Clickable Icons / Elements:")
    if steps:
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
    else:
        print("  (No steps returned)")

    print("\nFull Lambda Response:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
