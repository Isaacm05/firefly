"""Data passed from the model to the overlay, plus FR-09 validation.

Coordinates are normalized (0-1, top-left origin) against the captured screen,
so the overlay can map them to whatever resolution / scaling the learner has.
"""
import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.7  # FR-09: below this, show nothing rather than a wrong highlight
MAX_AREA = 0.5        # a "button" covering half the screen is a bad answer


@dataclass(frozen=True)
class Step:
    label: str        # visible text of the element, e.g. "Print"
    instruction: str  # short card title, e.g. "Click Print"


@dataclass(frozen=True)
class Target:
    x: float
    y: float
    w: float
    h: float
    label: str
    instruction: str
    caption: str          # plain-words location, shown only when needs_caption
    needs_caption: bool
    confidence: float


class TargetAnswer(BaseModel):
    """What the model returns for one element (structured JSON output)."""
    found: bool
    box_2d: list[int] = Field(description="[ymin, xmin, ymax, xmax] of the element, each scaled 0-1000")
    confidence: float = Field(description="0-1: how sure you are this is the right element")
    needs_caption: bool = Field(description="true only if the element is small or looks like nearby elements")
    caption: str = Field(description='one plain sentence saying where it is, e.g. "The blue button at the bottom right of this window."')


TARGET_RULES = """
For the element, return:
- found: false if it is not visible in this screenshot.
- box_2d: [ymin, xmin, ymax, xmax] tightly around the element, each scaled 0-1000.
- confidence: 0-1, how sure you are this is the right element.
- needs_caption: true only if the element is small, or looks similar to other nearby
  elements, so a beginner could pick the wrong one.
- caption: one short, plain sentence a beginner understands that says where it is,
  e.g. "The blue button at the bottom right of this window."
"""


def to_target(answer: TargetAnswer | None, step: Step) -> Target | None:
    """Validate a model answer. Returns None when Firefly should not highlight (FR-09)."""
    if answer is None or not answer.found:
        log.info("[target] %r not found", step.label)
        return None
    if len(answer.box_2d) != 4:
        log.info("[target] malformed box %r", answer.box_2d)
        return None
    ymin, xmin, ymax, xmax = (v / 1000 for v in answer.box_2d)
    if not (0 <= xmin < xmax <= 1 and 0 <= ymin < ymax <= 1):
        log.info("[target] box out of range %r", answer.box_2d)
        return None
    if answer.confidence < MIN_CONFIDENCE:
        log.info("[target] confidence %.2f below %.2f", answer.confidence, MIN_CONFIDENCE)
        return None
    if (xmax - xmin) * (ymax - ymin) > MAX_AREA:
        log.info("[target] box too large %r", answer.box_2d)
        return None
    return Target(
        x=xmin, y=ymin, w=xmax - xmin, h=ymax - ymin,
        label=step.label,
        instruction=step.instruction,
        caption=answer.caption.strip(),
        needs_caption=answer.needs_caption,
        confidence=answer.confidence,
    )
