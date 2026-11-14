"""Guidance overlay: box placement, mouse tracking, completion (FR-10, FR-11, FR-12).

Mouse position, button state and the clock are faked, so no real input is needed.
"""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage

import guidance_overlay as go
from guidance_overlay import RING_PAD, GuidanceOverlay, State


class FakeInput:
    """Stands in for the real cursor, left button and clock."""

    def __init__(self, monkeypatch, overlay):
        self.overlay = overlay
        self.local = QPointF(0, 0)
        self.down = False
        self.now = 1000.0
        monkeypatch.setattr(go, "_left_button_down", lambda: self.down)
        monkeypatch.setattr(go, "QCursor", SimpleNamespace(pos=self._global_pos))
        monkeypatch.setattr(go, "time", SimpleNamespace(monotonic=lambda: self.now))

    def _global_pos(self):
        return self.overlay.mapToGlobal(self.local.toPoint())

    def move(self, x, y):
        self.local = QPointF(x, y)
        self.overlay._tick()

    def click(self):
        self.down = True
        self.overlay._tick()
        self.down = False
        self.overlay._tick()

    def wait(self, seconds):
        self.now += seconds
        self.overlay._tick()


@pytest.fixture
def overlay(qapp):
    o = GuidanceOverlay()
    o.resize(1000, 800)  # fixed size so the math below is easy to check
    yield o
    o.close()


@pytest.fixture
def fake(monkeypatch, overlay):
    return FakeInput(monkeypatch, overlay)


@pytest.fixture
def results(overlay):
    out = []
    overlay.step_finished.connect(out.append)
    return out


# ---- geometry helpers -----------------------------------------------------

def test_nearest_point_inside_rect_is_itself():
    r = QRectF(10, 10, 100, 50)
    assert go._nearest_point(QPointF(50, 30), r) == QPointF(50, 30)


def test_nearest_point_outside_rect_is_on_edge():
    r = QRectF(10, 10, 100, 50)
    assert go._nearest_point(QPointF(200, 30), r) == QPointF(110, 30)


def test_distance_to_rect():
    r = QRectF(0, 0, 100, 100)
    assert go._distance(QPointF(50, 50), r) == 0
    assert go._distance(QPointF(103, 104), r) == pytest.approx(5)


# ---- FR-11: never blocks or sends input -------------------------------------

def test_overlay_is_transparent_for_input(overlay):
    flags = overlay.windowFlags()
    assert flags & Qt.WindowTransparentForInput
    assert flags & Qt.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowStaysOnTopHint


# ---- FR-10: normalized box -> screen pixels ---------------------------------

def test_target_is_mapped_to_pixels_with_ring_padding(overlay, fake, make_target):
    overlay.show_target(make_target(x=0.5, y=0.25, w=0.1, h=0.05))
    assert overlay.ring == QRectF(500 - RING_PAD, 200 - RING_PAD, 100 + 2 * RING_PAD, 40 + 2 * RING_PAD)
    assert overlay.state is State.GUIDING
    assert overlay.status_text == "Found it"


# ---- mouse tracking ---------------------------------------------------------

def test_glow_gets_stronger_as_pointer_gets_closer(overlay, fake, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(0, 0)
    far = overlay.proximity
    fake.move(450, 380)
    near = overlay.proximity
    fake.move(520, 410)  # inside the ring
    assert far < near < overlay.proximity == 1.0


def test_status_switches_from_found_to_follow_to_click(overlay, fake, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(0, 0)
    assert overlay.status_text == "Found it"
    fake.wait(go.FOUND_PILL_S + 0.1)
    assert overlay.status_text == "Follow the trail"
    fake.move(520, 410)
    assert overlay.status_text == "Click the glowing button"


# ---- FR-12: completion ------------------------------------------------------

def test_click_inside_ring_confirms_step(overlay, fake, results, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(520, 410)
    fake.click()
    assert results == ["clicked"]
    assert overlay.state is State.CONFIRMED
    assert overlay.status_text == "Done! Waiting for the next step"


def test_click_outside_ring_does_nothing(overlay, fake, results, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(100, 100)
    fake.click()
    assert results == []
    assert overlay.state is State.GUIDING


def test_button_already_held_when_step_starts_is_ignored(overlay, fake, results, make_target):
    fake.down = True  # e.g. still holding from the previous step's click
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(520, 410)
    assert results == []
    fake.down = False
    fake.overlay._tick()
    fake.click()
    assert results == ["clicked"]


def test_only_one_completion_per_step(overlay, fake, results, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(520, 410)
    fake.click()
    fake.click()
    assert results == ["clicked"]


def test_timeout_removes_highlight_and_finishes_step(overlay, fake, results, make_target):
    overlay.show_target(make_target(x=0.5, y=0.5, w=0.1, h=0.05))
    fake.move(0, 0)
    fake.wait(go.STEP_TIMEOUT_S - 1)
    assert results == []
    fake.wait(2)
    assert results == ["timeout"]
    assert overlay.target is None


def test_idle_overlay_ignores_clicks(overlay, fake, results):
    fake.click()
    assert results == []


# ---- drawing smoke tests: every state paints without errors ----------------

def _paint(overlay):
    img = QImage(overlay.size(), QImage.Format_ARGB32)
    img.fill(0)
    overlay.render(img)
    return img


@pytest.mark.parametrize("needs_caption", [False, True])
def test_paints_guiding_state(overlay, fake, make_target, needs_caption):
    overlay.show_helper("Click the Print button")
    overlay.show_target(make_target(x=0.5, y=0.02, needs_caption=needs_caption))  # near top: caption goes below
    fake.move(10, 700)
    img = _paint(overlay)
    center = img.pixelColor(QPoint(int(overlay.ring.left()), int(overlay.ring.center().y())))
    assert center.alpha() > 0  # the ring was drawn


def test_paints_looking_confirmed_message_and_finished(overlay, fake, make_target):
    overlay.show_looking()
    _paint(overlay)
    overlay.show_target(make_target())
    fake.move(450, 360)
    fake.click()
    _paint(overlay)
    overlay.show_message("I couldn't find it.")
    _paint(overlay)
    overlay.show_finished("All done!")
    _paint(overlay)
