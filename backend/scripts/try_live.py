"""Live terminal test client for the local grounding API (stands in for the C# app).

Start the server first (`python src/app.py`), then in a second terminal:

    python scripts/try_live.py

Loop: type an instruction -> switch to the window you want guided -> it captures the
screen (in memory only), calls POST /plan, and prints where to click. For each later
step you do the click yourself, press Enter here, switch back, and it calls POST /locate
on a fresh screenshot. Empty instruction or Ctrl+C quits.
"""
import base64
import ctypes
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import ImageGrab

API = os.getenv("FIREFLY_API", "http://127.0.0.1:8000")
SWITCH_S = 3      # time to switch from this terminal to the window being guided
MAX_WIDTH = 1280  # same downscale + JPEG the real client does before sending


def capture():
    """Return (base64 JPEG, (width, height) of the real screen). Nothing touches disk."""
    shot = ImageGrab.grab()
    size = shot.size
    if shot.width > MAX_WIDTH:
        shot = shot.resize((MAX_WIDTH, round(shot.height * MAX_WIDTH / shot.width)))
    buf = io.BytesIO()
    shot.convert("RGB").save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode(), size


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        payload = {"http_error": e.code, **json.load(e)}
    print(f"  ({path} took {time.perf_counter() - t0:.1f}s)")
    return payload


def countdown(msg):
    print(msg, end="", flush=True)
    for i in range(SWITCH_S, 0, -1):
        print(f" {i}", end="", flush=True)
        time.sleep(1)
    print()


def show(target, screen):
    if target is None:
        print("  -> no highlight (not found, or not confident enough)")
        return False
    w, h = screen
    cx, cy = round((target["x"] + target["w"] / 2) * w), round((target["y"] + target["h"] / 2) * h)
    print(f"  -> {target['instruction']!r}: center at ({cx}, {cy}) px, "
          f"confidence {target['confidence']:.2f}")
    print(f"     {target['caption']}")
    return True


def run(instruction):
    countdown("Switch to the window to guide...")
    image, screen = capture()
    plan = post("/plan", {"instruction": instruction, "image": image})
    del image
    if "http_error" in plan:
        print(f"  error {plan['http_error']}: {plan}")
        return
    steps = plan["steps"]
    if not steps:
        print("  I could not work out the steps. Try saying it another way.")
        return
    print("  steps:", " -> ".join(s["instruction"] for s in steps))
    print(f"\n[1/{len(steps)}]")
    if not show(plan["target"], screen):
        return

    for i, step in enumerate(steps[1:], start=2):
        input(f"\nDo step {i - 1} yourself, then press Enter here for step {i}...")
        countdown("Switch back...")
        image, screen = capture()
        found = post("/locate", {"step": step, "image": image})
        del image
        print(f"[{i}/{len(steps)}]")
        if not show(found.get("target"), screen):
            return
    print("\nAll done!")


def main():
    ctypes.windll.user32.SetProcessDPIAware()  # capture real pixels on scaled displays
    print(f"Firefly live test -> {API}  (empty line or Ctrl+C to quit)")
    while True:
        try:
            instruction = input("\nWhat did your helper say? ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not instruction:
            break
        try:
            run(instruction)
        except urllib.error.URLError as e:
            print(f"  can't reach {API} - is `python src/app.py` running? ({e.reason})")
        except KeyboardInterrupt:
            print("\n  (cancelled)")
    sys.exit(0)


if __name__ == "__main__":
    main()
