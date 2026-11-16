"""Unit tests for FR-12 (Completion Detection) and FR-06 (Sequential Step Queue).

Covers:
  - Condition 1: Passive observe-only click-inside detection (< 500 ms clear SLA)
  - Condition 2: Manual dismissal via API/UI hook or on-screen dismiss button (< 500 ms)
  - Condition 3: 15-second timeout (< 500 ms clear SLA)
  - Rephrased instruction replacement of an active highlight
  - Multi-step sequential queue progression (TC-FR12-1 & TC-FR12-2)
"""
from __future__ import annotations

import time

import pytest

from completion_detector import (
    DEFAULT_TIMEOUT_S,
    MAX_CLEAR_LATENCY_MS,
    BoundingBox,
    CompletionDetector,
    CompletionReason,
    PassiveMouseObserver,
    SequentialStepQueue,
    StepStatus,
)
from targets import Step, Target


class SimulatedEnvironment:
    """Deterministic clock, mouse observer, and highlight state for unit tests."""

    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S, clear_delay_s: float = 0.002):
        self.now = 100.0
        self.cursor = (0.0, 0.0)
        self.button_down = False
        self.highlight_visible = False
        self.clear_delay_s = clear_delay_s
        self.completed_events = []

        self.mouse = PassiveMouseObserver(
            pos_reader=lambda: self.cursor,
            button_reader=lambda: self.button_down,
        )
        self.detector = CompletionDetector(
            on_clear_highlight=self._clear_highlight,
            on_step_completed=self.completed_events.append,
            mouse_observer=self.mouse,
            clock=lambda: self.now,
            timeout_s=timeout_s,
        )

    def _clear_highlight(self):
        # Simulate UI render/clear work taking `clear_delay_s` seconds
        self.now += self.clear_delay_s
        self.highlight_visible = False

    def show_highlight(
        self,
        box: BoundingBox,
        step_index: int = 0,
        step_label: str = "Print",
        dismiss_box: BoundingBox | None = None,
    ):
        self.highlight_visible = True
        return self.detector.start_step(
            box=box,
            step_index=step_index,
            step_label=step_label,
            dismiss_box=dismiss_box,
        )

    def move_to(self, x: float, y: float):
        self.cursor = (x, y)
        return self.detector.poll()

    def click_at(self, x: float, y: float):
        self.cursor = (x, y)
        self.button_down = True
        event = self.detector.poll()
        self.button_down = False
        self.detector.poll()
        return event

    def advance_time(self, seconds: float):
        self.now += seconds
        return self.detector.poll()


# ---- Condition 1: Click Inside (FR-12 & FR-11) ------------------------------

def test_click_inside_clears_highlight_under_500ms():
    env = SimulatedEnvironment()
    box = BoundingBox(left=100, top=100, width=200, height=80)
    env.show_highlight(box, step_index=0, step_label="Print")

    assert env.highlight_visible is True
    assert env.detector.status is StepStatus.ACTIVE

    event = env.click_at(150, 140)

    assert event is not None
    assert event.reason is CompletionReason.CLICK_INSIDE
    assert event.step_index == 0
    assert event.step_label == "Print"
    assert event.click_coords == (150, 140)
    assert env.highlight_visible is False
    assert env.detector.status is StepStatus.COMPLETED
    assert event.clear_latency_ms < MAX_CLEAR_LATENCY_MS
    assert event.within_sla is True


def test_click_outside_does_not_clear_or_complete():
    env = SimulatedEnvironment()
    box = BoundingBox(left=100, top=100, width=200, height=80)
    env.show_highlight(box, step_index=0, step_label="Print")

    assert env.click_at(50, 50) is None
    assert env.click_at(350, 250) is None
    assert env.highlight_visible is True
    assert env.detector.status is StepStatus.ACTIVE
    assert env.completed_events == []


# ---- Condition 2: Manual Dismissal (FR-12) ----------------------------------

def test_manual_dismiss_api_hook_clears_highlight_under_500ms():
    env = SimulatedEnvironment()
    box = BoundingBox(left=100, top=100, width=200, height=80)
    env.show_highlight(box, step_index=1, step_label="Settings")

    event = env.detector.dismiss()

    assert event is not None
    assert event.reason is CompletionReason.MANUAL_DISMISS
    assert event.step_index == 1
    assert event.step_label == "Settings"
    assert env.highlight_visible is False
    assert env.detector.status is StepStatus.COMPLETED
    assert event.clear_latency_ms < MAX_CLEAR_LATENCY_MS
    assert event.within_sla is True


def test_manual_dismiss_ui_button_click_clears_highlight_under_500ms():
    env = SimulatedEnvironment()
    target_box = BoundingBox(left=100, top=100, width=200, height=80)
    dismiss_box = BoundingBox(left=880, top=60, width=100, height=30)
    env.show_highlight(target_box, step_index=0, step_label="Print", dismiss_box=dismiss_box)

    event = env.click_at(920, 75)

    assert event is not None
    assert event.reason is CompletionReason.MANUAL_DISMISS
    assert event.click_coords == (920, 75)
    assert env.highlight_visible is False
    assert env.detector.status is StepStatus.COMPLETED
    assert event.clear_latency_ms < MAX_CLEAR_LATENCY_MS


# ---- Condition 3: 15-Second Timeout (FR-12) ---------------------------------

def test_timeout_15s_clears_highlight_under_500ms():
    env = SimulatedEnvironment(timeout_s=15.0)
    box = BoundingBox(left=100, top=100, width=200, height=80)
    env.show_highlight(box, step_index=2, step_label="OK")

    # At 14.9 seconds, highlight must still be active
    assert env.advance_time(14.9) is None
    assert env.highlight_visible is True
    assert env.detector.status is StepStatus.ACTIVE

    # Passing 15.0 seconds triggers timeout completion and clears highlight
    event = env.advance_time(0.2)
    assert event is not None
    assert event.reason is CompletionReason.TIMEOUT
    assert event.step_index == 2
    assert event.step_label == "OK"
    assert env.highlight_visible is False
    assert env.detector.status is StepStatus.COMPLETED
    assert event.clear_latency_ms < MAX_CLEAR_LATENCY_MS
    assert event.within_sla is True


# ---- TC-FR12-1: 10 Attempts Per Condition All Clear Within 500 ms -----------

@pytest.mark.parametrize("condition", ["click_inside", "manual_dismiss", "timeout_15s"])
def test_tc_fr12_1_ten_attempts_all_clear_within_500ms(condition):
    env = SimulatedEnvironment(timeout_s=15.0, clear_delay_s=0.005)
    box = BoundingBox(left=200, top=150, width=160, height=60)

    for attempt in range(10):
        env.show_highlight(box, step_index=attempt, step_label=f"Step-{attempt}")
        assert env.highlight_visible is True

        if condition == "click_inside":
            event = env.click_at(250, 180)
            expected_reason = CompletionReason.CLICK_INSIDE
        elif condition == "manual_dismiss":
            event = env.detector.dismiss()
            expected_reason = CompletionReason.MANUAL_DISMISS
        else:
            event = env.advance_time(15.05)
            expected_reason = CompletionReason.TIMEOUT

        assert event is not None, f"Attempt {attempt} failed to produce a completion event"
        assert event.reason is expected_reason
        assert env.highlight_visible is False
        assert env.detector.status is StepStatus.COMPLETED
        assert event.clear_latency_ms < MAX_CLEAR_LATENCY_MS
        assert event.within_sla is True


# ---- TC-FR12-2: Multi-Step Sequential Queue Advancement ---------------------

def test_tc_fr12_2_multistep_commands_advance_sequentially():
    env = SimulatedEnvironment(timeout_s=15.0)
    queue = SequentialStepQueue()
    steps = [
        Step("File", "Click File"),
        Step("Print", "Click Print"),
        Step("OK", "Click OK"),
    ]
    boxes = {
        "File": BoundingBox(20, 10, 60, 30),
        "Print": BoundingBox(40, 80, 100, 35),
        "OK": BoundingBox(400, 300, 90, 40),
    }
    first_target = Target(0.02, 0.01, 0.06, 0.03, "File", "Click File", "", False, 0.95)
    queue.load_steps(steps, first_target=first_target)

    # Step 1: Click inside "File"
    item1 = queue.pop_next_step()
    assert item1 is not None and item1.step.label == "File"
    assert item1.status is StepStatus.ACTIVE
    assert queue.items[1].status is StepStatus.PENDING
    env.show_highlight(boxes["File"], step_index=item1.index, step_label=item1.step.label)
    ev1 = env.click_at(50, 25)
    assert ev1 is not None and ev1.reason is CompletionReason.CLICK_INSIDE
    queue.mark_current_completed(ev1)
    assert item1.status is StepStatus.COMPLETED

    # Step 2: Manual dismiss on "Print"
    item2 = queue.pop_next_step()
    assert item2 is not None and item2.step.label == "Print"
    assert item2.status is StepStatus.ACTIVE
    assert queue.items[2].status is StepStatus.PENDING
    env.show_highlight(boxes["Print"], step_index=item2.index, step_label=item2.step.label)
    ev2 = env.detector.dismiss()
    assert ev2 is not None and ev2.reason is CompletionReason.MANUAL_DISMISS
    queue.mark_current_completed(ev2)
    assert item2.status is StepStatus.COMPLETED

    # Step 3: 15-second timeout on "OK"
    item3 = queue.pop_next_step()
    assert item3 is not None and item3.step.label == "OK"
    env.show_highlight(boxes["OK"], step_index=item3.index, step_label=item3.step.label)
    ev3 = env.advance_time(15.1)
    assert ev3 is not None and ev3.reason is CompletionReason.TIMEOUT
    queue.mark_current_completed(ev3)
    assert item3.status is StepStatus.COMPLETED

    # Queue is now finished
    assert queue.pop_next_step() is None
    assert queue.is_finished is True
    assert [e.reason for e in queue.completed_events] == [
        CompletionReason.CLICK_INSIDE,
        CompletionReason.MANUAL_DISMISS,
        CompletionReason.TIMEOUT,
    ]
    assert all(e.within_sla for e in queue.completed_events)


# ---- Rephrased Instruction Replacement & Background Thread ------------------

def test_rephrased_instruction_replaces_active_highlight():
    env = SimulatedEnvironment()
    box1 = BoundingBox(100, 100, 120, 50)
    box2 = BoundingBox(300, 250, 140, 60)

    env.show_highlight(box1, step_index=0, step_label="Old Target")
    replaced = env.show_highlight(box2, step_index=1, step_label="New Rephrased Target")

    assert replaced is not None
    assert replaced.reason is CompletionReason.REPLACED
    assert replaced.step_label == "Old Target"
    assert replaced.within_sla is True
    assert env.detector.is_active is True
    assert env.detector.step_label == "New Rephrased Target"


def test_real_wall_clock_background_polling_clears_under_500ms():
    cleared_flag = {"cleared": False, "cleared_at": 0.0}

    def _on_clear():
        cleared_flag["cleared"] = True
        cleared_flag["cleared_at"] = time.monotonic()

    detector = CompletionDetector(
        on_clear_highlight=_on_clear,
        clock=time.monotonic,
        timeout_s=0.05,  # 50 ms real wall-clock timeout to verify background thread reactivity
    )
    detector.start_step(BoundingBox(10, 10, 100, 50), step_index=0, step_label="LiveTimer")
    detector.start_background_polling(interval_s=0.01)
    try:
        deadline = time.monotonic() + 0.5
        while detector.is_active and time.monotonic() < deadline:
            time.sleep(0.01)
        assert detector.is_active is False
        assert cleared_flag["cleared"] is True
        assert detector.last_event is not None
        assert detector.last_event.reason is CompletionReason.TIMEOUT
        assert detector.last_event.clear_latency_ms < MAX_CLEAR_LATENCY_MS
    finally:
        detector.stop_background_polling()
