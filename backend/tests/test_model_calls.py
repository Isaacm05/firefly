"""Planning and locating, with the Gemini call replaced by canned answers (no API key)."""
import numpy as np
import pytest

import create_instructions
import highlight_button
from targets import Step

IMAGE = np.zeros((10, 10, 3), dtype=np.uint8)


def fake_ask(answer, calls=None):
    def _ask(prompt, image, schema, timeout_ms):
        if calls is not None:
            calls.append(dict(prompt=prompt, schema=schema, timeout_ms=timeout_ms))
        if isinstance(answer, Exception):
            raise answer
        return answer
    return _ask


# ---- create_instructions ---------------------------------------------------

def test_plan_returns_steps_and_first_target(monkeypatch, make_answer):
    plan = create_instructions._Plan(
        steps=[create_instructions._PlanStep(label=" Print ", instruction=" Click Print "),
               create_instructions._PlanStep(label="OK", instruction="Click OK")],
        first_target=make_answer(),
    )
    calls = []
    monkeypatch.setattr(create_instructions, "ask_about_screen", fake_ask(plan, calls))

    steps, target = create_instructions.create_instructions(IMAGE, "print it")

    assert steps == [Step("Print", "Click Print"), Step("OK", "Click OK")]
    assert target.label == "Print"
    assert 'Their helper said: "print it"' in calls[0]["prompt"]
    assert calls[0]["schema"] is create_instructions._Plan


def test_plan_with_no_answer_returns_nothing(monkeypatch):
    monkeypatch.setattr(create_instructions, "ask_about_screen", fake_ask(None))
    assert create_instructions.create_instructions(IMAGE, "x") == ([], None)


def test_plan_with_no_steps_returns_nothing(monkeypatch, make_answer):
    plan = create_instructions._Plan(steps=[], first_target=make_answer())
    monkeypatch.setattr(create_instructions, "ask_about_screen", fake_ask(plan))
    assert create_instructions.create_instructions(IMAGE, "x") == ([], None)


def test_plan_with_bad_first_box_keeps_steps_but_no_target(monkeypatch, make_answer):
    plan = create_instructions._Plan(
        steps=[create_instructions._PlanStep(label="Print", instruction="Click Print")],
        first_target=make_answer(confidence=0.1),
    )
    monkeypatch.setattr(create_instructions, "ask_about_screen", fake_ask(plan))
    steps, target = create_instructions.create_instructions(IMAGE, "x")
    assert len(steps) == 1 and target is None


# ---- highlight_button ------------------------------------------------------

def test_locate_returns_target(monkeypatch, make_answer, step):
    calls = []
    monkeypatch.setattr(highlight_button, "ask_about_screen", fake_ask(make_answer(), calls))
    target = highlight_button.locate_button(IMAGE, step)
    assert target.label == "Print"
    assert 'Find the element labelled "Print"' in calls[0]["prompt"]


def test_locate_uses_ten_second_timeout(monkeypatch, make_answer, step):
    calls = []
    monkeypatch.setattr(highlight_button, "ask_about_screen", fake_ask(make_answer(), calls))
    highlight_button.locate_button(IMAGE, step)
    assert calls[0]["timeout_ms"] == 10000  # FR-09


@pytest.mark.parametrize("error", [TimeoutError("slow"), RuntimeError("api down")])
def test_locate_fails_safe_on_errors(monkeypatch, step, error):
    monkeypatch.setattr(highlight_button, "ask_about_screen", fake_ask(error))
    assert highlight_button.locate_button(IMAGE, step) is None


def test_locate_low_confidence_gives_no_target(monkeypatch, make_answer, step):
    monkeypatch.setattr(highlight_button, "ask_about_screen", fake_ask(make_answer(confidence=0.2)))
    assert highlight_button.locate_button(IMAGE, step) is None
