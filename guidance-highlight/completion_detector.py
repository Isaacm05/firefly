"""FR-12 Completion Detection and FR-06 Sequential Step Queue.

Implements the three completion conditions for an active highlight:
  1. Click Inside (CompletionReason.CLICK_INSIDE): Passive, observe-only OS mouse
     detection when the learner clicks inside the active bounding box (FR-11 safe).
  2. Manual Dismissal (CompletionReason.MANUAL_DISMISS): UI or API hook to manually
     dismiss the active highlight.
  3. Time-out (CompletionReason.TIMEOUT): Automatically clears the highlight when
     15 seconds pass without completion.

Also supports replacing an active highlight when a helper rephrases an instruction
(CompletionReason.REPLACED). When any condition triggers, the highlight is cleared
within 500 ms, the step is marked COMPLETED, and the sequential queue advances.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

try:
    import ctypes
    import ctypes.wintypes
except ImportError:  # pragma: no cover
    ctypes = None  # type: ignore[assignment]

from targets import Step, Target

DEFAULT_TIMEOUT_S = float(os.getenv("FIREFLY_STEP_TIMEOUT", "15.0"))
MAX_CLEAR_LATENCY_MS = 500.0
VK_LBUTTON = 0x01
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202


class CompletionReason(str, Enum):
    """Reason an active guidance step completed (values match overlay signal strings)."""
    CLICK_INSIDE = "clicked"
    MANUAL_DISMISS = "dismissed"
    TIMEOUT = "timeout"
    REPLACED = "replaced"


class StepStatus(str, Enum):
    """Lifecycle state of a guided step in the sequential queue."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True)
class BoundingBox:
    """Screen-space bounding box in pixels (top-left origin)."""
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.width / 2.0, self.top + self.height / 2.0)

    def contains(self, x: float, y: float) -> bool:
        """Return True if screen coordinates (x, y) fall inside or on the box edge."""
        return (self.left <= x <= self.right) and (self.top <= y <= self.bottom)

    def padded(self, pad: float) -> BoundingBox:
        """Return a copy expanded by `pad` pixels on all sides."""
        return BoundingBox(
            left=self.left - pad,
            top=self.top - pad,
            width=self.width + 2.0 * pad,
            height=self.height + 2.0 * pad,
        )

    @classmethod
    def from_normalized(
        cls,
        x: float,
        y: float,
        w: float,
        h: float,
        screen_width: float,
        screen_height: float,
        pad: float = 0.0,
    ) -> BoundingBox:
        """Convert normalized [0, 1] Target coordinates into screen pixel coordinates."""
        box = cls(
            left=x * screen_width,
            top=y * screen_height,
            width=w * screen_width,
            height=h * screen_height,
        )
        return box.padded(pad) if pad else box


@dataclass(frozen=True)
class CompletionEvent:
    """Audit record produced when a highlight step finishes under FR-12."""
    step_index: int
    step_label: str
    reason: CompletionReason
    triggered_at: float
    cleared_at: float
    clear_latency_ms: float
    click_coords: tuple[float, float] | None = None

    @property
    def within_sla(self) -> bool:
        """Verify highlight removal completed within the 500 ms FR-12 requirement."""
        return 0.0 <= self.clear_latency_ms <= MAX_CLEAR_LATENCY_MS


class PassiveMouseObserver:
    """Strictly observe-only OS mouse reader (FR-11 compliant).

    Reads cursor position and left mouse button state via Win32 read-only APIs
    (GetCursorPos / GetAsyncKeyState, or an optional WH_MOUSE_LL read-only hook
    that immediately forwards every event via CallNextHookEx). Never intercepts,
    blocks, or synthesizes any user input.
    """

    def __init__(
        self,
        pos_reader: Callable[[], tuple[float, float]] | None = None,
        button_reader: Callable[[], bool] | None = None,
    ):
        self._pos_reader = pos_reader
        self._button_reader = button_reader
        self._hook_id: int | None = None
        self._hook_proc = None
        self._hooked_down = False
        self._hooked_pos: tuple[float, float] = (0.0, 0.0)

    def position(self) -> tuple[float, float]:
        """Return current (x, y) cursor position in screen pixels."""
        if self._pos_reader is not None:
            return self._pos_reader()
        if self._hook_id is not None:
            return self._hooked_pos
        if sys.platform != "win32" or ctypes is None:
            return (0.0, 0.0)
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return (float(pt.x), float(pt.y))

    def is_left_down(self) -> bool:
        """Return True if the physical left mouse button is currently pressed."""
        if self._button_reader is not None:
            return bool(self._button_reader())
        if self._hook_id is not None:
            return self._hooked_down
        if sys.platform != "win32" or ctypes is None:
            return False
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

    def install_win32_readonly_hook(self) -> bool:
        """Optionally register a low-level WH_MOUSE_LL observe-only hook on Windows.

        The hook callback only records coordinates/button state and unconditionally
        calls CallNextHookEx so OS input flow is never blocked or altered (FR-11).
        """
        if sys.platform != "win32" or ctypes is None or self._hook_id is not None:
            return False

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", ctypes.wintypes.POINT),
                ("mouseData", ctypes.wintypes.DWORD),
                ("flags", ctypes.wintypes.DWORD),
                ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        CMPFUNC = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        )

        def _low_level_handler(n_code: int, w_param: int, l_param: int) -> int:
            if n_code >= 0 and l_param:
                info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                self._hooked_pos = (float(info.pt.x), float(info.pt.y))
                if w_param == WM_LBUTTONDOWN:
                    self._hooked_down = True
                elif w_param == WM_LBUTTONUP:
                    self._hooked_down = False
            return ctypes.windll.user32.CallNextHookEx(self._hook_id, n_code, w_param, l_param)

        self._hook_proc = CMPFUNC(_low_level_handler)
        hook = ctypes.windll.user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_proc, 0, 0)
        if not hook:
            self._hook_proc = None
            return False
        self._hook_id = int(hook)
        return True

    def uninstall_win32_readonly_hook(self) -> None:
        """Remove the low-level read-only mouse hook if installed."""
        if sys.platform == "win32" and ctypes is not None and self._hook_id is not None:
            ctypes.windll.user32.UnhookWindowsHookEx(self._hook_id)
        self._hook_id = None
        self._hook_proc = None


class CompletionDetector:
    """Monitors an active highlight for the three FR-12 completion conditions.

    Conditions:
      - Click inside the target bounding box (`CompletionReason.CLICK_INSIDE`)
      - Manual dismissal via UI button or API hook (`CompletionReason.MANUAL_DISMISS`)
      - 15-second timeout (`CompletionReason.TIMEOUT`)
      - Replacement by a new/rephrased instruction (`CompletionReason.REPLACED`)
    """

    def __init__(
        self,
        on_clear_highlight: Callable[[], None] | None = None,
        on_step_completed: Callable[[CompletionEvent], None] | None = None,
        mouse_observer: PassiveMouseObserver | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self._on_clear_highlight = on_clear_highlight
        self._on_step_completed = on_step_completed
        self.mouse = mouse_observer or PassiveMouseObserver()
        self._clock = clock
        self.timeout_s = float(timeout_s)

        self._lock = threading.RLock()
        self.active_box: BoundingBox | None = None
        self.dismiss_box: BoundingBox | None = None
        self.step_index: int = 0
        self.step_label: str = ""
        self.status: StepStatus = StepStatus.PENDING
        self.step_started: float = 0.0
        self.was_down: bool = False
        self.last_event: CompletionEvent | None = None
        self.history: list[CompletionEvent] = []

        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self.status is StepStatus.ACTIVE and self.active_box is not None

    def start_step(
        self,
        box: BoundingBox,
        step_index: int = 0,
        step_label: str = "",
        dismiss_box: BoundingBox | None = None,
    ) -> CompletionEvent | None:
        """Begin monitoring a newly displayed highlight bounding box.

        If a previous highlight was still active, it is immediately cleared and
        recorded with `CompletionReason.REPLACED` (rephrased instruction handling).
        """
        with self._lock:
            replaced_event = None
            if self.status is StepStatus.ACTIVE and self.active_box is not None:
                replaced_event = self._complete_locked(CompletionReason.REPLACED, None)

            self.active_box = box
            self.dismiss_box = dismiss_box
            self.step_index = step_index
            self.step_label = step_label
            self.status = StepStatus.ACTIVE
            self.step_started = self._clock()
            # Ignore a mouse button press that was already held down before this step began
            self.was_down = self.mouse.is_left_down()
            return replaced_event

    def dismiss(self, click_coords: tuple[float, float] | None = None) -> CompletionEvent | None:
        """Manually dismiss the active highlight (UI button, voice command, or API hook)."""
        with self._lock:
            if self.status is not StepStatus.ACTIVE or self.active_box is None:
                return None
            return self._complete_locked(CompletionReason.MANUAL_DISMISS, click_coords)

    def poll(self) -> CompletionEvent | None:
        """Check mouse state and elapsed time once; return CompletionEvent if completed."""
        with self._lock:
            if self.status is not StepStatus.ACTIVE or self.active_box is None:
                return None

            x, y = self.mouse.position()
            down = self.mouse.is_left_down()

            # Rising-edge click detection (learner pressed mouse button during this step)
            if down and not self.was_down:
                self.was_down = True
                if self.dismiss_box is not None and self.dismiss_box.contains(x, y):
                    return self._complete_locked(CompletionReason.MANUAL_DISMISS, (x, y))
                if self.active_box.contains(x, y):
                    return self._complete_locked(CompletionReason.CLICK_INSIDE, (x, y))

            self.was_down = down

            # 15-second timeout check
            elapsed = self._clock() - self.step_started
            if elapsed > self.timeout_s:
                # Measure clear latency relative to the timeout deadline or current tick
                return self._complete_locked(CompletionReason.TIMEOUT, None)

            return None

    def _complete_locked(
        self,
        reason: CompletionReason,
        click_coords: tuple[float, float] | None,
    ) -> CompletionEvent:
        triggered_at = self._clock()
        self.active_box = None
        self.dismiss_box = None
        self.status = StepStatus.COMPLETED

        if self._on_clear_highlight is not None:
            self._on_clear_highlight()

        cleared_at = self._clock()
        clear_latency_ms = max(0.0, (cleared_at - triggered_at) * 1000.0)

        event = CompletionEvent(
            step_index=self.step_index,
            step_label=self.step_label,
            reason=reason,
            triggered_at=triggered_at,
            cleared_at=cleared_at,
            clear_latency_ms=clear_latency_ms,
            click_coords=click_coords,
        )
        self.last_event = event
        self.history.append(event)

        if self._on_step_completed is not None:
            self._on_step_completed(event)

        return event

    def start_background_polling(self, interval_s: float = 0.016) -> None:
        """Run a background polling loop at ~60 Hz so timeout/click clears within <50 ms."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.wait(interval_s):
                self.poll()

        self._worker = threading.Thread(target=_loop, name="firefly-fr12-detector", daemon=True)
        self._worker.start()

    def stop_background_polling(self) -> None:
        """Stop the background polling thread cleanly."""
        self._stop_event.set()
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=0.5)
        self._worker = None


@dataclass
class QueuedStepItem:
    """Tracks one step inside `SequentialStepQueue`."""
    index: int
    step: Step
    target: Target | None = None
    status: StepStatus = StepStatus.PENDING
    completion: CompletionEvent | None = None


@dataclass
class SequentialStepQueue:
    """Manages ordered multi-step instructions and advances only on FR-12 completion (FR-06)."""
    items: list[QueuedStepItem] = field(default_factory=list)
    current_index: int = -1

    def load_steps(self, steps: list[Step], first_target: Target | None = None) -> None:
        """Replace the queue with a new ordered list of steps."""
        self.items = [
            QueuedStepItem(
                index=i,
                step=s,
                target=first_target if i == 0 else None,
                status=StepStatus.PENDING,
            )
            for i, s in enumerate(steps)
        ]
        self.current_index = -1

    @property
    def current_item(self) -> QueuedStepItem | None:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    @property
    def is_finished(self) -> bool:
        return bool(self.items) and all(item.status is StepStatus.COMPLETED for item in self.items)

    def pop_next_step(self) -> QueuedStepItem | None:
        """Advance to the next PENDING step and mark it ACTIVE."""
        next_idx = self.current_index + 1
        if next_idx >= len(self.items):
            return None
        self.current_index = next_idx
        item = self.items[next_idx]
        item.status = StepStatus.ACTIVE
        return item

    def mark_current_completed(self, event: CompletionEvent) -> QueuedStepItem | None:
        """Mark the active step COMPLETED with its FR-12 CompletionEvent."""
        item = self.current_item
        if item is None:
            return None
        item.status = StepStatus.COMPLETED
        item.completion = event
        return item

    @property
    def completed_events(self) -> list[CompletionEvent]:
        return [item.completion for item in self.items if item.completion is not None]
