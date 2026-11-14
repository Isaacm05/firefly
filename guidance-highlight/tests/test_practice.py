"""Practice window: exact boxes for its own buttons, and a full run through the real overlay."""
import numpy as np
import pytest

import main
from practice import STEPS, PracticeGuide, PracticeWindow


@pytest.fixture
def window(qapp):
    w = PracticeWindow()
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def test_print_box_is_inside_the_screen(window):
    t = window.box_of(STEPS[0])
    assert t.label == "Print"
    assert 0 <= t.x < t.x + t.w <= 1
    assert 0 <= t.y < t.y + t.h <= 1
    assert t.needs_caption is False


def test_ok_is_not_available_until_print_is_clicked(window, qapp):
    assert window.box_of(STEPS[1]) is None
    window.print_btn.click()  # Qt's own test click on our own window, not OS input
    qapp.processEvents()
    t = window.box_of(STEPS[1])
    assert t is not None and t.needs_caption is True


def test_guide_plans_both_steps(window):
    steps, first = PracticeGuide(window).plan(None, "x")
    assert [s.label for s in steps] == ["Print", "OK"]
    assert first.label == "Print"


def test_full_practice_run_with_real_overlay(qapp, window, monkeypatch):
    """Pipeline + real GuidanceOverlay; a 'learner' clicks each glowing button."""
    from guidance_overlay import GuidanceOverlay
    monkeypatch.setattr(main, "SETTLE_S", 0)
    monkeypatch.setattr(main, "take_screenshot", lambda: np.zeros((4, 4, 3), np.uint8))

    overlay = GuidanceOverlay()
    overlay.excluded_from_capture = True
    pipeline = main.Pipeline(overlay, PracticeGuide(window), "Click Print, then OK")

    shown = []

    def learner_clicks(target):  # runs where the target is shown
        shown.append(target.label)
        (window.print_btn if target.label == "Print" else window.ok_btn).click()
        overlay.step_finished.emit("clicked")

    pipeline.target.disconnect(overlay.show_target)
    pipeline.target.connect(learner_clicks)
    finished = []
    pipeline.finished.connect(finished.append)

    pipeline._run()

    assert shown == ["Print", "OK"]
    assert finished == ["All done!"]
    assert pipeline.step_results == ["clicked", "clicked"]
