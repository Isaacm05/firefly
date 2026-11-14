"""Firefly prototype: Guidance A (mouse trail + reactive glow ring).

    python main.py                          # type the helper's instruction; Gemini finds targets
    python main.py "click print, then OK"   # same, instruction on the command line
    python main.py --practice               # practice window, no API key needed

Loop per step: screenshot (in memory) -> bounding box -> trail + glow ring ->
wait for the learner's own click inside the ring (or timeout) -> next step.
"""
import argparse
import logging
import signal
import sys
import threading
import time
from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

from guidance_overlay import GuidanceOverlay
from take_screenshot import take_screenshot

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("firefly")

SETTLE_S = 0.8  # after a click, let the app's UI react before the next screenshot


class Pipeline(QObject):
    """Runs model calls on a worker thread and drives the overlay through signals."""
    helper = Signal(str)
    looking = Signal()
    target = Signal(object)
    message = Signal(str)
    finished = Signal(str)
    hide_for_capture = Signal(object)
    restore = Signal()

    def __init__(self, overlay: GuidanceOverlay, guide, instruction: str):
        super().__init__()
        self.overlay, self.guide, self.instruction = overlay, guide, instruction
        self._step_done = threading.Event()
        self.step_results = []

        self.helper.connect(overlay.show_helper)
        self.looking.connect(overlay.show_looking)
        self.target.connect(overlay.show_target)
        self.message.connect(overlay.show_message)
        self.finished.connect(overlay.show_finished)
        self.hide_for_capture.connect(overlay.hide_for_capture)
        self.restore.connect(overlay.restore)
        overlay.step_finished.connect(self._on_step_finished, Qt.DirectConnection)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _on_step_finished(self, result):
        self.step_results.append(result)
        self._step_done.set()

    def _capture(self):
        if self.overlay.excluded_from_capture:
            return take_screenshot()
        ready = threading.Event()
        self.hide_for_capture.emit(ready)
        ready.wait(2)
        try:
            return take_screenshot()
        finally:
            self.restore.emit()

    def _run(self):
        t0 = time.perf_counter()
        try:
            self._guide()
        except Exception:
            log.exception("[main] pipeline failed")
            self.message.emit("Something went wrong. Ask your helper to try again.")
        log.info("[main] total run time: %.2fs, steps: %s", time.perf_counter() - t0, self.step_results)

    def _guide(self):
        self.helper.emit(self.instruction)
        self.looking.emit()
        image = self._capture()
        steps, target = self.guide.plan(image, self.instruction)
        del image  # screenshots live only in memory and only as long as needed (NFR-03)
        log.info("[main] steps: %s", [s.instruction for s in steps])
        if not steps:
            self.message.emit("I couldn't work out the steps. Ask your helper to say it another way.")
            return

        for i, step in enumerate(steps):
            if i > 0:
                time.sleep(SETTLE_S)
                self.looking.emit()
                target = self.guide.locate(self._capture(), step)
            if target is None:  # FR-09: no highlight, short message instead
                self.message.emit(f"I couldn't find “{step.label}”. Ask your helper to say it another way.")
                return
            self._step_done.clear()
            self.target.emit(target)
            self._step_done.wait()
        self.finished.emit("All done!")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instruction", nargs="?", help="what the helper said")
    parser.add_argument("--practice", action="store_true", help="practice window, no API calls")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal.SIG_DFL)  # let Ctrl+C stop the Qt loop
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if args.practice:
        from practice import INSTRUCTION, PracticeGuide, PracticeWindow
        window = PracticeWindow()
        window.show()
        guide, instruction = PracticeGuide(window), INSTRUCTION
    else:
        from create_instructions import create_instructions
        from highlight_button import locate_button
        guide = SimpleNamespace(plan=create_instructions, locate=locate_button)
        instruction = args.instruction or input("What did your helper say? ")
        print("Switch to the window you want to use now (3s)...")
        time.sleep(3)

    overlay = GuidanceOverlay()
    overlay.show()
    pipeline = Pipeline(overlay, guide, instruction)
    pipeline.finished.connect(lambda _: QTimer.singleShot(4000, app.quit))
    pipeline.message.connect(lambda _: QTimer.singleShot(8000, app.quit))
    # start once the event loop is running so the overlay's window exists first
    QTimer.singleShot(0, pipeline.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
