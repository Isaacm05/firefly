"""main.Pipeline: the step loop, with a fake guide and a fake overlay (no API, no screen)."""
import threading

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal

import main
from targets import Step


class FakeOverlay(QObject):
    """Records what the pipeline asked it to show; 'clicks' every target immediately."""
    step_finished = Signal(str)

    def __init__(self, step_result="clicked", excluded_from_capture=True):
        super().__init__()
        self.calls = []
        self.step_result = step_result
        self.excluded_from_capture = excluded_from_capture

    def show_helper(self, text): self.calls.append(("helper", text))
    def show_looking(self): self.calls.append(("looking",))
    def show_message(self, text): self.calls.append(("message", text))
    def show_finished(self, text): self.calls.append(("finished", text))
    def restore(self): self.calls.append(("restore",))

    def hide_for_capture(self, ready):
        self.calls.append(("hide",))
        ready.set()

    def show_target(self, target):
        self.calls.append(("target", target.label))
        self.step_finished.emit(self.step_result)

    def kinds(self):
        return [c[0] for c in self.calls]


class FakeGuide:
    def __init__(self, steps, targets):
        self.steps, self.targets = steps, dict(targets)
        self.located = []

    def plan(self, image, task):
        return self.steps, self.targets.get(self.steps[0].label) if self.steps else None

    def locate(self, image, step):
        self.located.append(step.label)
        return self.targets.get(step.label)


STEPS = [Step("File", "Click File"), Step("Print", "Click Print")]


@pytest.fixture(autouse=True)
def no_waiting_no_screen(monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "take_screenshot", lambda: np.zeros((4, 4, 3), np.uint8))


def run(overlay, guide, instruction="print it"):
    p = main.Pipeline(overlay, guide, instruction)
    p._run()  # synchronously, on this thread
    return p


def test_all_steps_found_and_clicked(qapp, make_target):
    overlay = FakeOverlay()
    guide = FakeGuide(STEPS, {"File": make_target(label="File"), "Print": make_target(label="Print")})
    p = run(overlay, guide)

    assert overlay.calls == [
        ("helper", "print it"), ("looking",), ("target", "File"),
        ("looking",), ("target", "Print"), ("finished", "All done!"),
    ]
    assert guide.located == ["Print"]  # first target came from the plan call
    assert p.step_results == ["clicked", "clicked"]


def test_first_target_missing_shows_message_and_stops(qapp, make_target):
    overlay = FakeOverlay()
    guide = FakeGuide(STEPS, {"Print": make_target()})
    run(overlay, guide)
    assert overlay.kinds()[-1] == "message"
    assert "“File”" in overlay.calls[-1][1]
    assert "target" not in overlay.kinds()
    assert guide.located == []


def test_later_target_missing_stops_after_first_step(qapp, make_target):
    overlay = FakeOverlay()
    guide = FakeGuide(STEPS, {"File": make_target(label="File")})
    run(overlay, guide)
    assert ("target", "File") in overlay.calls
    assert overlay.kinds()[-1] == "message"
    assert "finished" not in overlay.kinds()


def test_no_steps_shows_message(qapp):
    overlay = FakeOverlay()
    run(overlay, FakeGuide([], {}))
    assert overlay.kinds()[-1] == "message"
    assert "steps" in overlay.calls[-1][1]


def test_timeout_still_moves_to_next_step(qapp, make_target):
    overlay = FakeOverlay(step_result="timeout")
    guide = FakeGuide(STEPS, {"File": make_target(label="File"), "Print": make_target(label="Print")})
    p = run(overlay, guide)
    assert p.step_results == ["timeout", "timeout"]
    assert overlay.kinds()[-1] == "finished"


def test_crash_in_guide_shows_friendly_message(qapp):
    class Broken(FakeGuide):
        def plan(self, image, task):
            raise RuntimeError("boom")
    overlay = FakeOverlay()
    run(overlay, Broken(STEPS, {}))
    assert overlay.calls[-1] == ("message", "Something went wrong. Ask your helper to try again.")


def test_overlay_is_hidden_during_capture_when_not_excluded(qapp, make_target):
    overlay = FakeOverlay(excluded_from_capture=False)
    guide = FakeGuide(STEPS[:1], {"File": make_target(label="File")})
    run(overlay, guide)
    kinds = overlay.kinds()
    assert kinds.index("hide") < kinds.index("restore") < kinds.index("target")


def test_overlay_not_hidden_when_excluded_from_capture(qapp, make_target):
    overlay = FakeOverlay(excluded_from_capture=True)
    run(overlay, FakeGuide(STEPS[:1], {"File": make_target(label="File")}))
    assert "hide" not in overlay.kinds()
