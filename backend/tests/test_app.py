"""The HTTP layer: request validation, routing, and JSON shape (Gemini is faked)."""
import base64
import json

import pytest

import app
from targets import Step, Target

IMAGE_B64 = base64.b64encode(b"fake-jpeg-bytes").decode()
TARGET = Target(x=0.7, y=0.8, w=0.2, h=0.1, label="Print", instruction="Click Print",
                caption="The blue button.", needs_caption=False, confidence=0.9)


def call(path, body):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return app.handle(path, raw)


def test_plan_returns_steps_and_target(monkeypatch):
    seen = {}

    def fake_plan(image, instruction):
        seen.update(image=image, instruction=instruction)
        return [Step("Print", "Click Print"), Step("OK", "Click OK")], TARGET
    monkeypatch.setattr(app, "create_instructions", fake_plan)

    status, payload = call("/plan", {"instruction": " print it ", "image": IMAGE_B64})

    assert status == 200
    assert seen == {"image": b"fake-jpeg-bytes", "instruction": "print it"}
    assert payload["steps"][1] == {"label": "OK", "instruction": "Click OK"}
    assert payload["target"]["x"] == 0.7
    json.dumps(payload)  # must be JSON-serializable


def test_plan_with_no_target_returns_null(monkeypatch):
    monkeypatch.setattr(app, "create_instructions", lambda image, instruction: ([], None))
    assert call("/plan", {"instruction": "x", "image": IMAGE_B64}) == (200, {"steps": [], "target": None})


@pytest.mark.parametrize(("error", "status"), [
    (TimeoutError("slow"), 504),
    (RuntimeError("api down"), 502),
])
def test_plan_gemini_failure_maps_to_status(monkeypatch, error, status):
    def boom(image, instruction):
        raise error
    monkeypatch.setattr(app, "create_instructions", boom)
    assert call("/plan", {"instruction": "x", "image": IMAGE_B64})[0] == status


def test_locate_returns_target(monkeypatch):
    monkeypatch.setattr(app, "locate_button", lambda image, step: TARGET)
    status, payload = call("/locate", {"step": {"label": "Print", "instruction": "Click Print"},
                                       "image": IMAGE_B64})
    assert status == 200
    assert payload["target"]["label"] == "Print"


@pytest.mark.parametrize("body", [
    b"not json",
    b"[1, 2]",
    {"image": IMAGE_B64},                          # missing instruction
    {"instruction": "  ", "image": IMAGE_B64},     # blank instruction
    {"instruction": "x"},                          # missing image
    {"instruction": "x", "image": "%%%not-b64%%%"},
])
def test_bad_plan_requests_are_400(body):
    status, payload = call("/plan", body)
    assert status == 400
    assert payload["error"] == "bad_request"


def test_bad_locate_step_is_400():
    assert call("/locate", {"step": {"label": "Print"}, "image": IMAGE_B64})[0] == 400


def test_unknown_path_is_404():
    assert call("/nope", {})[0] == 404


# ---- local-server terminal prompt ------------------------------------------

def test_typed_instruction_replaces_client_instruction_on_plan(monkeypatch):
    monkeypatch.setitem(app._typed, "instruction", "open settings")
    raw = app._with_typed_instruction("/plan", json.dumps({"instruction": "demo", "image": "x"}).encode())
    assert json.loads(raw) == {"instruction": "open settings", "image": "x"}


def test_no_typed_instruction_leaves_request_alone(monkeypatch):
    monkeypatch.setitem(app._typed, "instruction", None)
    raw = b'{"instruction": "demo"}'
    assert app._with_typed_instruction("/plan", raw) is raw


@pytest.mark.parametrize(("path", "raw"), [("/locate", b'{"step": {}}'), ("/plan", b"not json")])
def test_typed_instruction_only_touches_valid_plan_bodies(monkeypatch, path, raw):
    monkeypatch.setitem(app._typed, "instruction", "open settings")
    assert app._with_typed_instruction(path, raw) is raw
