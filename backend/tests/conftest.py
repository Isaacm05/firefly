import pytest

from targets import Step, Target, TargetAnswer


@pytest.fixture
def step():
    return Step("Print", "Click Print")


@pytest.fixture
def make_answer():
    def _make(**overrides):
        fields = {"found": True, "box_2d": [800, 700, 900, 900], "confidence": 0.9,
                      "needs_caption": False, "caption": " The blue button. "}
        fields.update(overrides)
        return TargetAnswer(**fields)
    return _make


@pytest.fixture
def make_target():
    def _make(**overrides):
        fields = {"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.1, "label": "Print", "instruction": "Click Print",
                      "caption": "The blue button.", "needs_caption": False, "confidence": 1.0}
        fields.update(overrides)
        return Target(**fields)
    return _make
