"""FR-09: model answers become a normalized box, or no highlight at all."""
import pytest

from targets import MIN_CONFIDENCE, to_target


def test_valid_answer_becomes_normalized_box(make_answer, step):
    t = to_target(make_answer(box_2d=[800, 700, 900, 900]), step)  # [ymin, xmin, ymax, xmax]
    assert (t.x, t.y) == pytest.approx((0.7, 0.8))
    assert (t.w, t.h) == pytest.approx((0.2, 0.1))


def test_step_text_and_caption_are_carried_over(make_answer, step):
    t = to_target(make_answer(needs_caption=True), step)
    assert t.label == "Print"
    assert t.instruction == "Click Print"
    assert t.caption == "The blue button."  # whitespace stripped
    assert t.needs_caption is True


def test_none_answer_means_no_highlight(step):
    assert to_target(None, step) is None


def test_not_found_means_no_highlight(make_answer, step):
    assert to_target(make_answer(found=False), step) is None


@pytest.mark.parametrize("box", [
    [100, 100, 200],            # too few values
    [100, 100, 200, 200, 300],  # too many
    [],
])
def test_malformed_box_is_rejected(make_answer, step, box):
    assert to_target(make_answer(box_2d=box), step) is None


@pytest.mark.parametrize("box", [
    [-10, 100, 200, 200],   # negative
    [100, 100, 200, 1200],  # past the edge
    [500, 100, 400, 200],   # ymin > ymax
    [100, 300, 200, 300],   # zero width
])
def test_out_of_range_or_inverted_box_is_rejected(make_answer, step, box):
    assert to_target(make_answer(box_2d=box), step) is None


def test_low_confidence_is_rejected(make_answer, step):
    assert to_target(make_answer(confidence=MIN_CONFIDENCE - 0.01), step) is None


def test_confidence_at_threshold_is_accepted(make_answer, step):
    assert to_target(make_answer(confidence=MIN_CONFIDENCE), step) is not None


def test_box_covering_most_of_screen_is_rejected(make_answer, step):
    assert to_target(make_answer(box_2d=[0, 0, 900, 900]), step) is None


def test_box_touching_screen_edges_is_accepted(make_answer, step):
    assert to_target(make_answer(box_2d=[950, 950, 1000, 1000]), step) is not None
