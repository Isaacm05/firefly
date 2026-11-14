"""Guidance A overlay: mouse trail + reactive glow ring (Figma "Flow 2 · Guidance · Candidate A").

A full-screen, always-on-top window that only draws. Every mouse/keyboard event
passes straight through it, and it never sends input (FR-11). Each frame it *reads*
the cursor position and left-button state to:
  - draw a dotted trail from the pointer to the target,
  - brighten the glow ring as the pointer gets closer,
  - confirm the step when the learner clicks inside the ring (FR-12).
"""
import ctypes
import math
import os
import sys
import time
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QGuiApplication,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import QWidget

from targets import Target

# Colors sampled from the Figma frame.
YELLOW = QColor("#FFD60A")
NAVY = QColor("#1D1B3A")
GREEN = QColor("#30D158")
INDIGO = QColor("#5856D6")
WHITE = QColor("#FFFFFF")
SOFT_WHITE = QColor("#E5E5EA")

TEXT_SCALE = float(os.getenv("FIREFLY_TEXT_SCALE", "1.0"))   # "Text size" setting
STEP_TIMEOUT_S = float(os.getenv("FIREFLY_STEP_TIMEOUT", "15"))  # FR-12 starting value
FOUND_PILL_S = 1.0     # how long "Found it" shows before switching to guidance text
RING_PAD = 6           # px between the element and the ring
GLOW_RANGE = 450       # px: glow ramps from dim (far) to full (touching the ring)
NEAR = 0.75            # proximity at which the pill says "Click the glowing button"
TRAIL_SPACING = 16     # px between trail dots
TRAIL_SPEED = 40       # px/s the dots march toward the target
PULSE_PERIOD_S = 1.4   # ring pulse: a non-color cue (NFR-05)

WDA_EXCLUDEFROMCAPTURE = 0x11
VK_LBUTTON = 0x01


class State(Enum):
    IDLE = auto()
    LOOKING = auto()
    GUIDING = auto()
    CONFIRMED = auto()
    MESSAGE = auto()


def _left_button_down() -> bool:
    """Read (never send) the left mouse button state."""
    if sys.platform != "win32":
        return False
    return bool(ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def _nearest_point(p: QPointF, r: QRectF) -> QPointF:
    return QPointF(min(max(p.x(), r.left()), r.right()), min(max(p.y(), r.top()), r.bottom()))


def _distance(p: QPointF, r: QRectF) -> float:
    n = _nearest_point(p, r)
    return math.hypot(p.x() - n.x(), p.y() - n.y())


def _font(px: float, bold=False) -> QFont:
    f = QFont("Segoe UI")
    f.setPixelSize(round(px * TEXT_SCALE))
    f.setBold(bold)
    return f


class GuidanceOverlay(QWidget):
    step_finished = Signal(str)  # "clicked" or "timeout"

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())

        self.state = State.IDLE
        self.helper_text = ""
        self.status_text = ""
        self.target: Target | None = None
        self.ring = QRectF()
        self.cursor = QPointF()
        self.proximity = 0.0
        self.was_down = False
        self.step_started = 0.0
        self.t0 = time.monotonic()
        self.excluded_from_capture = False

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ---- window setup -------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        # Keep the overlay out of our own screenshots so the model never sees an old
        # highlight. Set FIREFLY_CAPTURE_VISIBLE=1 to keep it visible to screen
        # recorders / screen share (the pipeline then hides it during capture instead).
        if sys.platform == "win32" and os.getenv("FIREFLY_CAPTURE_VISIBLE") != "1":
            self.excluded_from_capture = bool(
                ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), WDA_EXCLUDEFROMCAPTURE))

    @Slot(object)
    def hide_for_capture(self, ready):
        self.hide()
        QTimer.singleShot(150, ready.set)  # give the compositor a frame to drop us

    @Slot()
    def restore(self):
        self.show()

    # ---- states (called from the pipeline via queued signals) ---------------
    @Slot(str)
    def show_helper(self, text):
        self.helper_text = text
        self.update()

    @Slot()
    def show_looking(self):
        self._set(State.LOOKING, "Looking…")

    @Slot(object)
    def show_target(self, target: Target):
        g = self.rect()
        box = QRectF(target.x * g.width(), target.y * g.height(), target.w * g.width(), target.h * g.height())
        self.target = target
        self.ring = box.adjusted(-RING_PAD, -RING_PAD, RING_PAD, RING_PAD)
        self.was_down = _left_button_down()  # ignore a press already in progress
        self.step_started = time.monotonic()
        self._set(State.GUIDING, "Found it")

    @Slot(str)
    def show_message(self, text):
        self.target = None
        self._set(State.MESSAGE, text)

    @Slot(str)
    def show_finished(self, text):
        self.target = None
        self._set(State.CONFIRMED, text)

    def _set(self, state, status):
        self.state = state
        self.status_text = status
        self.update()

    # ---- per-frame tracking --------------------------------------------------
    def _tick(self):
        if self.state is State.IDLE:
            return
        self.cursor = QPointF(self.mapFromGlobal(QCursor.pos()))
        if self.state is State.GUIDING:
            self.proximity = max(0.0, 1.0 - _distance(self.cursor, self.ring) / GLOW_RANGE)
            down = _left_button_down()
            if down and not self.was_down and self.ring.contains(self.cursor):
                self._set(State.CONFIRMED, "Done! Waiting for the next step")
                self.step_finished.emit("clicked")
            elif time.monotonic() - self.step_started > STEP_TIMEOUT_S:
                self.target = None  # FR-12: remove the highlight and move on
                self._set(State.LOOKING, "Moving on…")
                self.step_finished.emit("timeout")
            else:
                elapsed = time.monotonic() - self.step_started
                if elapsed > FOUND_PILL_S:
                    self.status_text = ("Click the glowing button" if self.proximity >= NEAR
                                        else "Follow the trail")
            self.was_down = down
        self.update()

    # ---- drawing -----------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = time.monotonic() - self.t0

        if self.target is not None and self.state is State.GUIDING:
            if not self.ring.contains(self.cursor):
                self._draw_trail(p, t)
            self._draw_glow(p, t)
            self._draw_ring(p, YELLOW)
            if self.target.needs_caption and self.target.caption:
                self._draw_caption(p)
        elif self.target is not None and self.state is State.CONFIRMED:
            self._draw_ring(p, GREEN)
            self._draw_check(p)

        if self.helper_text:
            self._draw_helper_chip(p)
        if self.state is not State.IDLE and self.status_text:
            self._draw_status(p)

    def _draw_trail(self, p, t):
        end = _nearest_point(self.cursor, self.ring)
        dx, dy = end.x() - self.cursor.x(), end.y() - self.cursor.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        p.setPen(Qt.NoPen)
        s = 18 + (t * TRAIL_SPEED) % TRAIL_SPACING  # start just past the pointer tip
        while s < length:
            c = QPointF(self.cursor.x() + ux * s, self.cursor.y() + uy * s)
            p.setBrush(NAVY)    # dark rim keeps dots visible on white (NFR-05)
            p.drawEllipse(c, 5, 5)
            p.setBrush(YELLOW)
            p.drawEllipse(c, 3.5, 3.5)
            s += TRAIL_SPACING

    def _draw_glow(self, p, t):
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi / PULSE_PERIOD_S)
        strength = 0.3 + 0.7 * self.proximity  # "warmer, warmer"
        spread = 10 + 18 * strength * (0.6 + 0.4 * pulse)
        layers = 8
        p.setBrush(Qt.NoBrush)
        for i in range(layers):
            grow = (i + 1) * spread / layers
            c = QColor(YELLOW)
            c.setAlphaF(min(1.0, 0.45 * strength * (1 - i / layers) ** 1.5))
            p.setPen(QPen(c, spread / layers + 1))
            r = self.ring.adjusted(-grow, -grow, grow, grow)
            p.drawRoundedRect(r, 12 + grow, 12 + grow)

    def _draw_ring(self, p, color):
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(NAVY, 8))   # dual border: dark outside, bright inside (NFR-05)
        p.drawRoundedRect(self.ring, 12, 12)
        p.setPen(QPen(color, 4.5))
        p.drawRoundedRect(self.ring, 12, 12)

    def _draw_check(self, p):
        c = QPointF(self.ring.right(), self.ring.top())
        p.setPen(QPen(WHITE, 2.5))
        p.setBrush(GREEN)
        p.drawEllipse(c, 14, 14)
        path = QPainterPath(QPointF(c.x() - 6, c.y()))
        path.lineTo(c.x() - 1.5, c.y() + 5)
        path.lineTo(c.x() + 6.5, c.y() - 5)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(WHITE, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)

    def _draw_caption(self, p):
        title_f, body_f = _font(19, bold=True), _font(15)
        max_w, pad, gap = 340 * TEXT_SCALE, 14, 4
        flags = Qt.TextWordWrap
        title_r = QFontMetricsF(title_f).boundingRect(QRectF(0, 0, max_w, 1000), flags, self.target.instruction)
        body_r = QFontMetricsF(body_f).boundingRect(QRectF(0, 0, max_w, 1000), flags, self.target.caption)
        w = max(title_r.width(), body_r.width()) + 2 * pad
        h = title_r.height() + gap + body_r.height() + 2 * pad

        x = min(max(self.ring.center().x() - w / 2, 8), self.width() - w - 8)
        y = self.ring.top() - 14 - h
        if y < 60:  # no room above (status pill lives up there): go below
            y = self.ring.bottom() + 14
        card = QRectF(x, y, w, h)

        p.setPen(Qt.NoPen)
        p.setBrush(NAVY)
        p.drawRoundedRect(card, 12, 12)
        p.setPen(WHITE)
        p.setFont(title_f)
        p.drawText(QRectF(x + pad, y + pad, w - 2 * pad, title_r.height()), flags, self.target.instruction)
        p.setPen(SOFT_WHITE)
        p.setFont(body_f)
        p.drawText(QRectF(x + pad, y + pad + title_r.height() + gap, w - 2 * pad, body_r.height()),
                   flags, self.target.caption)

    def _draw_helper_chip(self, p):
        label_f, text_f = _font(15, bold=True), _font(15)
        label = "Helper: "
        text = QFontMetricsF(text_f).elidedText(f"“{self.helper_text}”", Qt.ElideRight, 560 * TEXT_SCALE)
        lw = QFontMetricsF(label_f).horizontalAdvance(label)
        tw = QFontMetricsF(text_f).horizontalAdvance(text)
        h, pad = 34 * TEXT_SCALE, 14
        chip = QRectF(16, 16, lw + tw + 2 * pad, h)
        p.setPen(QPen(QColor(29, 27, 58, 40), 1))
        p.setBrush(WHITE)
        p.drawRoundedRect(chip, h / 2, h / 2)
        p.setPen(INDIGO)
        p.setFont(label_f)
        p.drawText(QRectF(chip.x() + pad, chip.y(), lw, h), Qt.AlignVCenter, label)
        p.setPen(NAVY)
        p.setFont(text_f)
        p.drawText(QRectF(chip.x() + pad + lw, chip.y(), tw + 2, h), Qt.AlignVCenter, text)

    def _draw_status(self, p):
        ok = self.state is State.CONFIRMED
        f = _font(15, bold=True)
        tw = QFontMetricsF(f).horizontalAdvance(self.status_text)
        h, pad, dot = 36 * TEXT_SCALE, 14, 7 * TEXT_SCALE
        w = pad + 2 * dot + 10 + tw + pad
        pill = QRectF(self.width() - w - 16, 16, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(GREEN if ok else NAVY)
        p.drawRoundedRect(pill, h / 2, h / 2)
        # the firefly: a small glowing dot
        center = QPointF(pill.x() + pad + dot, pill.center().y())
        p.setBrush(NAVY if ok else YELLOW)
        p.drawEllipse(center, dot, dot)
        p.setPen(NAVY if ok else WHITE)  # navy on green keeps contrast high (NFR-05)
        p.setFont(f)
        p.drawText(QRectF(center.x() + dot + 10, pill.y(), tw + 2, h), Qt.AlignVCenter, self.status_text)


if __name__ == "__main__":
    # Quick visual check: a target in the middle of the screen, no API needed.
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    overlay = GuidanceOverlay()
    overlay.show()
    overlay.show_helper("Click the Print button")
    overlay.show_target(Target(0.45, 0.47, 0.1, 0.06, "Print", "Click Print",
                               "The box in the middle of your screen.", True, 1.0))
    overlay.step_finished.connect(lambda r: (print("step:", r), QTimer.singleShot(1500, app.quit)))
    sys.exit(app.exec())
