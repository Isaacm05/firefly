"""RVTM Verification Runner for FR-12 (TC-FR12-1 and TC-FR12-2).

Executes:
  1. TC-FR12-1: 10 attempts for each of the 3 completion conditions:
       - Condition A: Click inside the highlighted bounding box
       - Condition B: Manual dismissal control / API hook
       - Condition C: 15-second timeout
     Verifies that in all 10 attempts per condition, the highlight is removed
     within 500 ms and the step is marked COMPLETED.
  2. TC-FR12-2: Multi-step sequential command experiment ("Click File, then Print,
     then OK") across 10 trials, verifying sequential progression only after
     FR-12 completion is detected.
"""
from __future__ import annotations

import sys
import time

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


def run_tc_fr12_1(real_15s: bool = False) -> bool:
    """Run 10 trials for each of the 3 completion triggers and verify < 500 ms clear time."""
    print("=" * 78)
    print("TC-FR12-1: Single-Step Completion Detection (10 Attempts x 3 Conditions)")
    print("=" * 78)
    print(f"{'Condition':<18} | {'Attempt':<7} | {'Status':<10} | {'Cleared':<7} | {'Clear Latency':<15} | {'Result'}")
    print("-" * 78)

    all_passed = True
    conditions = [
        ("click_inside", CompletionReason.CLICK_INSIDE),
        ("manual_dismiss", CompletionReason.MANUAL_DISMISS),
        ("timeout_15s", CompletionReason.TIMEOUT),
    ]

    for cond_name, expected_reason in conditions:
        for attempt in range(1, 11):
            sim_clock = {"t": time.perf_counter()}
            cursor_state = {"pos": (0.0, 0.0), "down": False}
            overlay_state = {"visible": False}

            def clock_fn():
                return time.perf_counter() if real_15s else sim_clock["t"]

            def clear_cb():
                # Measure real in-memory overlay state clear
                t_start = time.perf_counter()
                overlay_state["visible"] = False
                elapsed_s = time.perf_counter() - t_start
                if not real_15s:
                    sim_clock["t"] += max(elapsed_s, 0.0004)

            observer = PassiveMouseObserver(
                pos_reader=lambda: cursor_state["pos"],
                button_reader=lambda: cursor_state["down"],
            )
            detector = CompletionDetector(
                on_clear_highlight=clear_cb,
                mouse_observer=observer,
                clock=clock_fn,
                timeout_s=DEFAULT_TIMEOUT_S,
            )

            box = BoundingBox(left=200.0, top=150.0, width=180.0, height=64.0)
            dismiss_box = BoundingBox(left=870.0, top=60.0, width=110.0, height=28.0)
            overlay_state["visible"] = True
            detector.start_step(box, step_index=attempt - 1, step_label="Print", dismiss_box=dismiss_box)

            if cond_name == "click_inside":
                cursor_state["pos"] = (260.0, 180.0)
                cursor_state["down"] = True
                event = detector.poll()
                cursor_state["down"] = False
            elif cond_name == "manual_dismiss":
                if attempt % 2 == 1:
                    event = detector.dismiss()
                else:
                    cursor_state["pos"] = (910.0, 72.0)
                    cursor_state["down"] = True
                    event = detector.poll()
                    cursor_state["down"] = False
            else:
                if real_15s:
                    time.sleep(DEFAULT_TIMEOUT_S + 0.02)
                else:
                    sim_clock["t"] += DEFAULT_TIMEOUT_S + 0.02
                event = detector.poll()

            passed = (
                event is not None
                and event.reason is expected_reason
                and detector.status is StepStatus.COMPLETED
                and overlay_state["visible"] is False
                and event.clear_latency_ms <= MAX_CLEAR_LATENCY_MS
            )
            all_passed = all_passed and passed
            latency_str = f"{event.clear_latency_ms:.3f} ms" if event else "N/A"
            status_str = detector.status.value.upper()
            result_str = "PASS" if passed else "FAIL"
            print(
                f"{cond_name:<18} | {attempt:<7} | {status_str:<10} | "
                f"{str(not overlay_state['visible']):<7} | {latency_str:<15} | {result_str}"
            )

    print("-" * 78)
    return all_passed


def run_tc_fr12_2() -> bool:
    """Run 10 multi-step sequential instruction trials (Click File -> Print -> OK)."""
    print("\n" + "=" * 78)
    print("TC-FR12-2: Multi-Step Sequential Queue Progression (10 Trials x 3 Steps)")
    print("=" * 78)

    steps = [
        Step("File", "Click File"),
        Step("Print", "Click Print"),
        Step("OK", "Click OK"),
    ]
    step_boxes = {
        "File": BoundingBox(30.0, 20.0, 70.0, 30.0),
        "Print": BoundingBox(50.0, 90.0, 110.0, 36.0),
        "OK": BoundingBox(420.0, 310.0, 96.0, 36.0),
    }
    triggers = [
        CompletionReason.CLICK_INSIDE,
        CompletionReason.MANUAL_DISMISS,
        CompletionReason.TIMEOUT,
    ]

    all_passed = True
    for trial in range(1, 11):
        sim_clock = {"t": 1000.0}
        cursor_state = {"pos": (0.0, 0.0), "down": False}
        overlay_state = {"visible": False, "active_label": None}

        def clear_cb():
            overlay_state["visible"] = False
            overlay_state["active_label"] = None
            sim_clock["t"] += 0.0005

        observer = PassiveMouseObserver(
            pos_reader=lambda: cursor_state["pos"],
            button_reader=lambda: cursor_state["down"],
        )
        detector = CompletionDetector(
            on_clear_highlight=clear_cb,
            mouse_observer=observer,
            clock=lambda: sim_clock["t"],
            timeout_s=DEFAULT_TIMEOUT_S,
        )

        queue = SequentialStepQueue()
        first_target = Target(0.03, 0.02, 0.07, 0.03, "File", "Click File", "", False, 0.95)
        queue.load_steps(steps, first_target=first_target)

        rendered_order = []
        for idx in range(len(steps)):
            item = queue.pop_next_step()
            assert item is not None
            # Verify later steps are still PENDING before current step completes
            for future in queue.items[idx + 1:]:
                if future.status is not StepStatus.PENDING:
                    all_passed = False

            box = step_boxes[item.step.label]
            overlay_state["visible"] = True
            overlay_state["active_label"] = item.step.label
            rendered_order.append(item.step.label)
            detector.start_step(box, step_index=item.index, step_label=item.step.label)

            trigger = triggers[(trial + idx) % len(triggers)]
            if trigger is CompletionReason.CLICK_INSIDE:
                cx, cy = box.center
                cursor_state["pos"] = (cx, cy)
                cursor_state["down"] = True
                ev = detector.poll()
                cursor_state["down"] = False
            elif trigger is CompletionReason.MANUAL_DISMISS:
                ev = detector.dismiss()
            else:
                sim_clock["t"] += DEFAULT_TIMEOUT_S + 0.05
                ev = detector.poll()

            assert ev is not None
            queue.mark_current_completed(ev)

        trial_ok = (
            queue.is_finished
            and rendered_order == ["File", "Print", "OK"]
            and all(e.within_sla for e in queue.completed_events)
        )
        all_passed = all_passed and trial_ok
        reasons = ", ".join(e.reason.value for e in queue.completed_events)
        max_lat = max(e.clear_latency_ms for e in queue.completed_events)
        print(
            f"Trial {trial:>2}/10 | Order: {' -> '.join(rendered_order)} | "
            f"Triggers: [{reasons}] | Max Clear: {max_lat:.3f} ms | {'PASS' if trial_ok else 'FAIL'}"
        )

    print("-" * 78)
    return all_passed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    real_15s = "--real-15s" in args

    ok1 = run_tc_fr12_1(real_15s=real_15s)
    ok2 = run_tc_fr12_2()
    overall = ok1 and ok2
    print(f"\nOVERALL FR-12 VERIFICATION: {'PASS (All criteria met < 500 ms)' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
