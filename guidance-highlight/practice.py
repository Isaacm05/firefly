"""Practice mode: a fake "Print a recipe" window with known button positions.

Lets you run the full Guidance A loop without a Gemini key, and gives exact
ground-truth boxes. Same idea as the practice run in Setup Candidate B.
"""
from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from targets import Step, Target

INSTRUCTION = "Click Print, then OK"
STEPS = [Step("Print", "Click Print"), Step("OK", "Click OK")]


class PracticeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Practice · Print a recipe")
        self.resize(560, 320)

        form = QFormLayout()
        form.addRow("Printer", QLineEdit("Office Printer"))
        form.addRow("Copies", QLineEdit("1"))
        form.addRow("Pages", QLineEdit("All"))

        self.status = QLabel("")
        self.cancel_btn = QPushButton("Cancel")
        self.print_btn = QPushButton("Print")
        self.ok_btn = QPushButton("OK")
        self.ok_btn.hide()
        for b in (self.cancel_btn, self.print_btn, self.ok_btn):
            b.setMinimumSize(96, 36)
        self.print_btn.setStyleSheet("background:#0A84FF; color:white; border-radius:6px; font-weight:600;")
        self.ok_btn.setStyleSheet("background:#0A84FF; color:white; border-radius:6px; font-weight:600;")

        buttons = QHBoxLayout()
        buttons.addWidget(self.status)
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.print_btn)
        buttons.addWidget(self.ok_btn)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addStretch()
        root.addLayout(buttons)

        self.print_btn.clicked.connect(self._printed)
        self.ok_btn.clicked.connect(self.close)

    def _printed(self):
        self.status.setText("Printed! Now click OK.")
        self.print_btn.hide()
        self.cancel_btn.hide()
        self.ok_btn.show()

    def box_of(self, step: Step) -> Target | None:
        btn = {"Print": self.print_btn, "OK": self.ok_btn}[step.label]
        if not btn.isVisible():
            return None
        screen = QGuiApplication.primaryScreen().geometry()
        tl = btn.mapToGlobal(QPoint(0, 0))
        return Target(
            x=(tl.x() - screen.x()) / screen.width(),
            y=(tl.y() - screen.y()) / screen.height(),
            w=btn.width() / screen.width(),
            h=btn.height() / screen.height(),
            label=step.label,
            instruction=step.instruction,
            caption="The blue button at the bottom right of the practice window.",
            needs_caption=step.label == "OK",  # show the caption branch on step 2
            confidence=1.0,
        )


class PracticeGuide:
    """Stands in for Gemini: same plan/locate interface, exact boxes."""

    def __init__(self, window: PracticeWindow):
        self.window = window

    def plan(self, _image, _task):
        return STEPS, self.window.box_of(STEPS[0])

    def locate(self, _image, step):
        return self.window.box_of(step)
